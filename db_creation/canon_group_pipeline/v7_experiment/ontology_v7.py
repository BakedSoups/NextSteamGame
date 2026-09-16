from __future__ import annotations

import argparse
import json
import math
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


RELATIONS = ("synonym", "left_parent", "right_parent", "related", "unrelated")
HERE = Path(__file__).resolve().parent
DEFAULT_BENCHMARK = HERE / "benchmark.json"
DEFAULT_REPORT = Path(__file__).resolve().parents[2] / "analysis" / "canon_v7_experiment.json"


@dataclass(frozen=True)
class TagPair:
    left: str
    right: str
    context: str
    gold: str = ""
    note: str = ""


@dataclass(frozen=True)
class Judgment:
    relation: str
    confidence: float
    reason: str
    facet_left: str
    facet_right: str
    canonical_label: str

    @property
    def safe_to_replace(self) -> bool:
        return self.relation == "synonym" and self.confidence >= 0.85


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: int = 900):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Ollama request failed at {self.base_url}: {exc}") from exc

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        # This machine cannot comfortably retain both models. Unload the retriever
        # after candidate generation so the larger relation judge has the RAM.
        response = self._post(
            "/api/embed",
            {"model": model, "input": texts, "keep_alive": 0},
        )
        return response["embeddings"]

    def judge_pairs(self, pairs: list[TagPair], model: str) -> list[Judgment]:
        schema = {
            "type": "object",
            "properties": {
                "judgments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "relation": {"type": "string", "enum": list(RELATIONS)},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "reason": {"type": "string", "maxLength": 120, "description": "At most 12 words"},
                            "facet_left": {"type": "string"},
                            "facet_right": {"type": "string"},
                            "canonical_label": {"type": "string"},
                        },
                        "required": ["id", "relation", "confidence", "reason", "facet_left", "facet_right", "canonical_label"],
                    },
                }
            },
            "required": ["judgments"],
        }
        compact_pairs = [
            {"id": index, "left": pair.left, "right": pair.right, "context": pair.context}
            for index, pair in enumerate(pairs)
        ]
        prompt = f"""You are building a conservative ontology of video-game tags.
Classify every pair independently. A synonym means the tags are safely interchangeable
for every game. Do not call subtypes, siblings, commonly co-occurring concepts, or tags
from different facets synonyms. Parent direction is literal: left_parent means LEFT is
broader; right_parent means RIGHT is broader. Prefer related or unrelated when uncertain.
canonical_label must only be non-empty for synonyms and should be a concise natural label.

Use the parent relation when every instance of the narrower tag is also an instance of
the broader tag. For example, "shooter" / "arena shooter" is left_parent, while
"survival horror" / "horror" is right_parent. Two sibling genres are related.

Pairs:
{json.dumps(compact_pairs, ensure_ascii=False)}
"""
        response = self._post(
            "/api/chat",
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "format": schema,
                "keep_alive": "10m",
                "options": {"temperature": 0, "num_predict": 1800},
            },
        )
        parsed = json.loads(response["message"]["content"])
        by_id = {item["id"]: item for item in parsed["judgments"]}
        if set(by_id) != set(range(len(pairs))):
            raise ValueError("Relation judge did not return exactly one result per pair")
        judgments = [
            Judgment(
                relation=by_id[index]["relation"],
                confidence=float(by_id[index]["confidence"]),
                reason=by_id[index]["reason"],
                facet_left=by_id[index]["facet_left"],
                facet_right=by_id[index]["facet_right"],
                canonical_label=by_id[index]["canonical_label"],
            )
            for index in range(len(pairs))
        ]
        if any(judgment.relation not in RELATIONS for judgment in judgments):
            raise ValueError("Relation judge returned an unsupported relation")
        return judgments


def cosine(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    numerator = sum(a * b for a, b in zip(left_values, right_values))
    denominator = math.sqrt(sum(a * a for a in left_values)) * math.sqrt(sum(b * b for b in right_values))
    return numerator / denominator if denominator else 0.0


def load_benchmark(path: Path) -> list[TagPair]:
    return [TagPair(**item) for item in json.loads(path.read_text(encoding="utf-8"))]


def semantic_text(tag: str, context: str) -> str:
    return f"Video game tag: {tag}. Facet or source context: {context}."


def evaluate(
    pairs: list[TagPair],
    client: OllamaClient,
    embedding_model: str,
    judge_model: str,
) -> dict[str, Any]:
    unique_texts = list(dict.fromkeys(
        semantic_text(tag, pair.context)
        for pair in pairs
        for tag in (pair.left, pair.right)
    ))
    vectors = client.embed(unique_texts, embedding_model)
    embeddings = dict(zip(unique_texts, vectors))
    judgments = client.judge_pairs(pairs, judge_model)
    results = []
    for pair, judgment in zip(pairs, judgments):
        similarity = cosine(
            embeddings[semantic_text(pair.left, pair.context)],
            embeddings[semantic_text(pair.right, pair.context)],
        )
        results.append({
            **asdict(pair),
            "embedding_similarity": round(similarity, 4),
            **asdict(judgment),
            "safe_to_replace": judgment.safe_to_replace,
            "correct": judgment.relation == pair.gold if pair.gold else None,
            "dangerous_false_merge": judgment.safe_to_replace and pair.gold != "synonym",
        })
    scored = [result for result in results if result["correct"] is not None]
    true_synonyms = [result for result in scored if result["gold"] == "synonym"]
    predicted_safe = [result for result in scored if result["safe_to_replace"]]
    return {
        "models": {"embedding": embedding_model, "relation_judge": judge_model},
        "policy": "Only synonym judgments at confidence >= 0.85 may replace a raw tag.",
        "metrics": {
            "pairs": len(scored),
            "relation_accuracy": round(sum(r["correct"] for r in scored) / len(scored), 4) if scored else None,
            "merge_decision_accuracy": round(
                sum((r["relation"] == "synonym") == (r["gold"] == "synonym") for r in scored) / len(scored), 4
            ) if scored else None,
            "safe_merge_precision": round(sum(r["gold"] == "synonym" for r in predicted_safe) / len(predicted_safe), 4) if predicted_safe else None,
            "safe_merge_recall": round(sum(r["safe_to_replace"] for r in true_synonyms) / len(true_synonyms), 4) if true_synonyms else None,
            "dangerous_false_merges": sum(r["dangerous_false_merge"] for r in scored),
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the ontology-first v7 tag strategy")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--embedding-model", default="qwen3-embedding:0.6b")
    parser.add_argument("--judge-model", default="qwen3.5:9b")
    args = parser.parse_args()

    report = evaluate(
        load_benchmark(args.benchmark),
        OllamaClient(args.ollama_url),
        args.embedding_model,
        args.judge_model,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
