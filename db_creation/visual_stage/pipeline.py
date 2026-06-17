from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

import requests
import torch
from openai import OpenAI
from PIL import Image
from transformers import AutoProcessor, CLIPModel

from paths import metadata_db_path


DEFAULT_MODEL_NAME = "openai/clip-vit-base-patch32"
DEFAULT_GAME_NAME = "ABZU"
DEFAULT_CLEANUP_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = (10, 20)
MAX_SCREENSHOTS = 4


def _styles_config_path() -> Path:
    return Path(__file__).resolve().with_name("styles.json")


def _load_styles_config() -> dict:
    with _styles_config_path().open("r", encoding="utf-8") as handle:
        return json.load(handle)


STYLES_CONFIG = _load_styles_config()
RENDER_FAMILY_LABELS = tuple(STYLES_CONFIG["render_family_labels"])
RENDER_SUBSTYLE_LABELS = {
    key: tuple(value)
    for key, value in STYLES_CONFIG["render_substyle_labels"].items()
}
VISUAL_TRAIT_LABELS = tuple(STYLES_CONFIG["visual_trait_labels"])
PRESENTATION_LABELS = tuple(STYLES_CONFIG["presentation_labels"])
PRESENTATION_GROUPS = {
    key: set(value)
    for key, value in STYLES_CONFIG["presentation_groups"].items()
}
TRAIT_GROUPS = {
    key: set(value)
    for key, value in STYLES_CONFIG["trait_groups"].items()
}


@dataclass
class ImageSource:
    kind: str
    url: str


class VisualClassifier:
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.model.eval()
        self.processor = AutoProcessor.from_pretrained(model_name)

    def score_labels(self, images: Sequence[Image.Image], labels: Sequence[str], prompt_template: str) -> dict[str, float]:
        if not images:
            return {}

        prompts = [prompt_template.format(label=label) for label in labels]
        inputs = self.processor(
            text=prompts,
            images=list(images),
            return_tensors="pt",
            padding=True,
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            image_embeds = outputs.image_embeds / outputs.image_embeds.norm(dim=-1, keepdim=True)
            text_embeds = outputs.text_embeds / outputs.text_embeds.norm(dim=-1, keepdim=True)
            logits = image_embeds @ text_embeds.T
            probabilities = torch.softmax(logits, dim=-1)
            averaged = probabilities.mean(dim=0)

        return {
            label: round(float(score) * 100.0, 2)
            for label, score in sorted(zip(labels, averaged.tolist()), key=lambda item: item[1], reverse=True)
        }


def _connect_metadata_db(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _load_game_row(connection: sqlite3.Connection, game_name: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT
            appid,
            name,
            header_image,
            capsule_image,
            capsule_imagev5,
            background_image,
            background_image_raw,
            library_hero_image,
            library_capsule_image
        FROM games
        WHERE lower(name) = lower(?)
        ORDER BY appid
        LIMIT 1
        """,
        (game_name,),
    ).fetchone()
    if row is None:
        db_file = connection.execute("PRAGMA database_list").fetchone()[2]
        raise RuntimeError(f"Could not find game named {game_name!r} in {db_file}")
    return row


def _load_screenshot_urls(connection: sqlite3.Connection, appid: int, limit: int = MAX_SCREENSHOTS) -> list[str]:
    rows = connection.execute(
        """
        SELECT path_full
        FROM game_screenshots
        WHERE appid = ?
        ORDER BY screenshot_id
        LIMIT ?
        """,
        (appid, limit),
    ).fetchall()
    return [str(row["path_full"]) for row in rows if row["path_full"]]


def _collect_image_sources(row: sqlite3.Row, screenshots: Iterable[str]) -> list[ImageSource]:
    ordered_sources: list[ImageSource] = []
    seen: set[str] = set()

    for kind, value in (
        ("library_hero", row["library_hero_image"]),
        ("background", row["background_image"]),
        ("background_raw", row["background_image_raw"]),
        ("header", row["header_image"]),
        ("capsule_v5", row["capsule_imagev5"]),
        ("capsule", row["capsule_image"]),
        ("library_capsule", row["library_capsule_image"]),
    ):
        url = str(value or "").strip()
        if url and url not in seen:
            seen.add(url)
            ordered_sources.append(ImageSource(kind=kind, url=url))

    for index, url in enumerate(screenshots, start=1):
        cleaned = str(url or "").strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered_sources.append(ImageSource(kind=f"screenshot_{index}", url=cleaned))

    return ordered_sources


def _download_image(session: requests.Session, source: ImageSource) -> Image.Image:
    response = session.get(source.url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGB")


def _top_labels(scores: dict[str, float], limit: int) -> list[dict[str, float | str]]:
    return [{"label": label, "score": score} for label, score in list(scores.items())[:limit]]


def _pick_distinct_labels(
    scores: dict[str, float],
    groups: dict[str, set[str]] | None,
    limit: int,
    min_gap: float = 0.0,
) -> list[str]:
    selected: list[str] = []
    used_groups: set[str] = set()
    prior_score: float | None = None

    label_to_group: dict[str, str] = {}
    if groups is not None:
        for group_name, labels in groups.items():
            for label in labels:
                label_to_group[label] = group_name

    for label, score in scores.items():
        group_name = label_to_group.get(label, label)
        if group_name in used_groups:
            continue
        if prior_score is not None and (prior_score - score) > min_gap and len(selected) >= 1:
            break
        selected.append(label)
        used_groups.add(group_name)
        prior_score = score
        if len(selected) >= limit:
            break

    return selected


def _maybe_cleanup_with_openai(
    *,
    game_name: str,
    render_family_scores: dict[str, float],
    render_style_scores: dict[str, float],
    presentation_scores: dict[str, float],
    trait_scores: dict[str, float],
    fallback_visual_identity: dict,
    cleanup_model: str,
) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback_visual_identity

    client = OpenAI(api_key=api_key)
    prompt = {
        "game": game_name,
        "task": (
            "Clean up noisy visual-classification output for a game. "
            "Return a concise, non-repetitive JSON object with these keys only: "
            "render_family, render_style_primary, render_style_secondary, presentation_style, visual_traits. "
            "presentation_style must contain 1-2 items. visual_traits must contain 2-4 items. "
            "Avoid near-synonyms and avoid repeating the same idea twice."
        ),
        "scores": {
            "render_family_scores": _top_labels(render_family_scores, 4),
            "render_style_scores": _top_labels(render_style_scores, 5),
            "presentation_scores": _top_labels(presentation_scores, 5),
            "visual_trait_scores": _top_labels(trait_scores, 8),
        },
        "fallback_visual_identity": fallback_visual_identity,
    }

    response = client.responses.create(
        model=cleanup_model,
        input=[
            {
                "role": "system",
                "content": (
                    "You clean up game visual taxonomy outputs. "
                    "Respond with valid JSON only. No markdown."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt),
            },
        ],
    )
    text = response.output_text.strip()
    cleaned = json.loads(text)

    return {
        "render_family": str(cleaned.get("render_family") or fallback_visual_identity["render_family"]),
        "render_style_primary": str(
            cleaned.get("render_style_primary") or fallback_visual_identity["render_style_primary"]
        ),
        "render_style_secondary": str(
            cleaned.get("render_style_secondary") or fallback_visual_identity["render_style_secondary"]
        ),
        "presentation_style": [
            str(item).strip()
            for item in (cleaned.get("presentation_style") or fallback_visual_identity["presentation_style"])
            if str(item).strip()
        ][:2],
        "visual_traits": [
            str(item).strip()
            for item in (cleaned.get("visual_traits") or fallback_visual_identity["visual_traits"])
            if str(item).strip()
        ][:4],
    }


def run_visual_probe(
    *,
    game_name: str = DEFAULT_GAME_NAME,
    db_path: Path | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
    cleanup_model: str = DEFAULT_CLEANUP_MODEL,
    use_openai_cleanup: bool = True,
) -> dict:
    resolved_db_path = Path(db_path or metadata_db_path())
    if not resolved_db_path.exists():
        raise FileNotFoundError(f"Metadata DB not found: {resolved_db_path}")

    with _connect_metadata_db(resolved_db_path) as connection:
        row = _load_game_row(connection, game_name)
        screenshots = _load_screenshot_urls(connection, int(row["appid"]))
        image_sources = _collect_image_sources(row, screenshots)

    if not image_sources:
        raise RuntimeError(f"No usable image sources found for {game_name!r}.")

    session = requests.Session()
    session.headers.update({"User-Agent": "SteamRecommenderVisualPipeline/1.0"})

    loaded_images: list[Image.Image] = []
    successful_sources: list[ImageSource] = []
    failed_sources: list[dict[str, str]] = []

    for source in image_sources:
        try:
            loaded_images.append(_download_image(session, source))
            successful_sources.append(source)
        except Exception as exc:  # pragma: no cover
            failed_sources.append({"kind": source.kind, "url": source.url, "error": str(exc)})

    if not loaded_images:
        raise RuntimeError(f"Failed to download any usable images for {game_name!r}.")

    classifier = VisualClassifier(model_name=model_name)
    render_family_scores = classifier.score_labels(
        loaded_images,
        RENDER_FAMILY_LABELS,
        "a video game screenshot with a {label} visual style",
    )
    render_family_primary = next(iter(render_family_scores), "stylized")
    render_substyle_scores = classifier.score_labels(
        loaded_images,
        RENDER_SUBSTYLE_LABELS.get(render_family_primary, ("stylized 3d",)),
        "a video game screenshot in a {label} art style",
    )
    trait_scores = classifier.score_labels(
        loaded_images,
        VISUAL_TRAIT_LABELS,
        "a video game screenshot with {label}",
    )
    presentation_scores = classifier.score_labels(
        loaded_images,
        PRESENTATION_LABELS,
        "a {label} video game scene",
    )
    selected_presentation = _pick_distinct_labels(presentation_scores, PRESENTATION_GROUPS, limit=2, min_gap=1.6)
    selected_traits = _pick_distinct_labels(trait_scores, TRAIT_GROUPS, limit=4, min_gap=1.2)
    fallback_visual_identity = {
        "render_family": render_family_primary,
        "render_style_primary": next(iter(render_substyle_scores), ""),
        "render_style_secondary": list(render_substyle_scores.keys())[1] if len(render_substyle_scores) > 1 else "",
        "presentation_style": selected_presentation,
        "visual_traits": selected_traits,
    }
    visual_identity = (
        _maybe_cleanup_with_openai(
            game_name=game_name,
            render_family_scores=render_family_scores,
            render_style_scores=render_substyle_scores,
            presentation_scores=presentation_scores,
            trait_scores=trait_scores,
            fallback_visual_identity=fallback_visual_identity,
            cleanup_model=cleanup_model,
        )
        if use_openai_cleanup
        else fallback_visual_identity
    )

    return {
        "game": {"appid": int(row["appid"]), "name": str(row["name"])},
        "model": model_name,
        "cleanup_model": cleanup_model if use_openai_cleanup and os.getenv("OPENAI_API_KEY") else None,
        "image_sources_used": [{"kind": source.kind, "url": source.url} for source in successful_sources],
        "image_sources_failed": failed_sources,
        "visual_identity": visual_identity,
        "evidence": {
            "render_family_scores": _top_labels(render_family_scores, 4),
            "render_style_scores": _top_labels(render_substyle_scores, 5),
            "presentation_scores": _top_labels(presentation_scores, 5),
            "visual_trait_scores": _top_labels(trait_scores, 8),
        },
    }


def print_visual_probe_json(
    *,
    game_name: str = DEFAULT_GAME_NAME,
    db_path: Path | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
    cleanup_model: str = DEFAULT_CLEANUP_MODEL,
    use_openai_cleanup: bool = True,
) -> None:
    result = run_visual_probe(
        game_name=game_name,
        db_path=db_path,
        model_name=model_name,
        cleanup_model=cleanup_model,
        use_openai_cleanup=use_openai_cleanup,
    )
    print(json.dumps(result, indent=2))
