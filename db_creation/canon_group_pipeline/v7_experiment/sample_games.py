from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from db_creation.canon_pipeline.layer_1_normalization import normalize_tag
from db_creation.canon_group_pipeline.v7_experiment.ontology_v7 import OllamaClient, TagPair
from db_creation.paths import analysis_dir, initial_noncanon_db_path


DEFAULT_APPIDS = (
    1687950,  # Persona 5 Royal
    1113000,  # Persona 4 Golden
    1875830,  # Shin Megami Tensei V: Vengeance
    1145360,  # Hades
    413150,   # Stardew Valley
    782330,   # DOOM Eternal
    646570,   # Slay the Spire
    2379780,  # Balatro
    620,      # Portal 2
    1245620,  # Elden Ring
    632470,   # Disco Elysium
    1551360,  # Forza Horizon 5
    504230,   # Celeste
    1794680,  # Vampire Survivors
)
DEFAULT_V6_CSV = analysis_dir() / "canon_groups_v6.csv"
DEFAULT_REPORT = analysis_dir() / "canon_v7_game_sample.json"
VECTOR_CONTEXTS = ("mechanics", "narrative", "vibe", "structure_loop")


@dataclass(frozen=True)
class Candidate:
    appid: int
    game: str
    context: str
    raw_tag: str
    v6_tag: str
    lexical_overlap: float
    source_weight: float


def _split_members(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def load_v6_mapping(path: Path) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = defaultdict(dict)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            context = row["context"]
            representative = (row.get("final_tag") or row.get("canon_tag") or "").strip()
            if not representative:
                continue
            for member in [representative, *_split_members(row.get("member_tags") or "")]:
                mapping[context][normalize_tag(member)] = representative
    return dict(mapping)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize_tag(value)))


def _overlap(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a or b else 1.0


def _tag_values(vectors: dict, metadata: dict):
    for context in VECTOR_CONTEXTS:
        values = vectors.get(context) or {}
        if isinstance(values, dict):
            for tag, weight in values.items():
                yield context, str(tag), float(weight or 0)
    for context in ("micro_tags", "niche_anchors", "identity_tags", "setting_tags"):
        for tag in metadata.get(context) or []:
            yield context, str(tag), 1.0
    for context in ("signature_tag", "music_primary", "music_secondary"):
        tag = metadata.get(context)
        if tag:
            yield context, str(tag), 1.0
    genre = metadata.get("genre_tree") or {}
    for level in ("primary", "sub", "sub_sub"):
        tag = genre.get(level)
        if tag:
            yield f"genre_tree.{level}", str(tag), 1.0


def collect_candidates(db_path: Path, appids: tuple[int, ...], mapping: dict[str, dict[str, str]]) -> list[Candidate]:
    placeholders = ",".join("?" for _ in appids)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            f"SELECT appid, name, vectors_json, metadata_json FROM raw_game_semantics WHERE appid IN ({placeholders})",
            appids,
        ).fetchall()
    finally:
        connection.close()
    candidates: list[Candidate] = []
    for row in rows:
        vectors = json.loads(row["vectors_json"] or "{}")
        metadata = json.loads(row["metadata_json"] or "{}")
        for context, raw_tag, weight in _tag_values(vectors, metadata):
            v6_tag = mapping.get(context, {}).get(normalize_tag(raw_tag), raw_tag)
            if normalize_tag(raw_tag) == normalize_tag(v6_tag):
                continue
            candidates.append(Candidate(
                appid=int(row["appid"]), game=row["name"], context=context,
                raw_tag=raw_tag, v6_tag=v6_tag,
                lexical_overlap=round(_overlap(raw_tag, v6_tag), 4), source_weight=weight,
            ))
    return candidates


def choose_sample(candidates: list[Candidate], per_game: int, limit: int) -> list[Candidate]:
    by_game: dict[int, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_game[candidate.appid].append(candidate)
    chosen: list[Candidate] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for appid in sorted(by_game):
        ordered = sorted(by_game[appid], key=lambda c: (c.lexical_overlap, -c.source_weight, c.context, c.raw_tag))
        game_count = 0
        for candidate in ordered:
            key = (candidate.context, normalize_tag(candidate.raw_tag), normalize_tag(candidate.v6_tag))
            if key in seen_pairs:
                continue
            chosen.append(candidate)
            seen_pairs.add(key)
            game_count += 1
            if game_count >= per_game:
                break
    return sorted(chosen, key=lambda c: (c.lexical_overlap, -c.source_weight))[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit v6 mappings on a sample of real games using v7")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--per-game", type=int, default=2)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--judge-model", default="qwen3.5:9b")
    args = parser.parse_args()

    candidates = collect_candidates(initial_noncanon_db_path(), DEFAULT_APPIDS, load_v6_mapping(DEFAULT_V6_CSV))
    sample = choose_sample(candidates, args.per_game, args.limit)
    pairs = [TagPair(item.raw_tag, item.v6_tag, item.context) for item in sample]
    judgments = OllamaClient(timeout=900).judge_pairs(pairs, args.judge_model)
    rows = []
    for candidate, judgment in zip(sample, judgments):
        rows.append({
            **asdict(candidate), **asdict(judgment),
            "v6_merge_safe_under_v7": judgment.safe_to_replace,
        })
    report = {
        "sample_games_requested": len(DEFAULT_APPIDS),
        "games_found": len({candidate.appid for candidate in candidates}),
        "changed_v6_mappings_found": len(candidates),
        "mappings_audited": len(rows),
        "v6_merges_accepted": sum(row["v6_merge_safe_under_v7"] for row in rows),
        "v6_merges_rejected": sum(not row["v6_merge_safe_under_v7"] for row in rows),
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
