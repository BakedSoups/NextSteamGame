from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from db_creation.canon_pipeline.layer_1_normalization import normalize_tag
from db_creation.canon_group_pipeline.v7_experiment.ontology_v7 import OllamaClient, TagPair
from db_creation.canon_group_pipeline.v7_experiment.ontology_v71 import load_gold, run_staged_pipeline
from db_creation.canon_group_pipeline.v7_experiment.sample_games import (
    DEFAULT_APPIDS,
    DEFAULT_V6_CSV,
    choose_sample,
    collect_candidates,
    load_v6_mapping,
)
from db_creation.paths import analysis_dir, initial_noncanon_db_path


DEFAULT_REPORT = analysis_dir() / "canon_v71_game_sample.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run staged v7.1 canonical decisions on the real-game sample")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--per-game", type=int, default=2)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--judge-model", default="qwen3.5:9b")
    args = parser.parse_args()

    candidates = collect_candidates(initial_noncanon_db_path(), DEFAULT_APPIDS, load_v6_mapping(DEFAULT_V6_CSV))
    sample = choose_sample(candidates, args.per_game, args.limit)
    pairs = [TagPair(candidate.raw_tag, candidate.v6_tag, candidate.context) for candidate in sample]
    decisions = run_staged_pipeline(pairs, OllamaClient(timeout=900), args.judge_model)
    gold = load_gold()
    results = []
    for candidate, decision in zip(sample, decisions):
        expected = gold.get((normalize_tag(candidate.raw_tag), normalize_tag(candidate.v6_tag)), {})
        predicted = bool(decision["safe_to_replace"])
        expected_equivalent = expected.get("equivalent")
        results.append({
            **asdict(candidate), **decision,
            "expected_equivalent": expected_equivalent,
            "expected_canonical": expected.get("preferred", ""),
            "correct_equivalence": predicted == expected_equivalent if expected_equivalent is not None else None,
            "dangerous_false_merge": predicted and expected_equivalent is False,
        })
    scored = [row for row in results if row["expected_equivalent"] is not None]
    accepted = [row for row in scored if row["safe_to_replace"]]
    positives = [row for row in scored if row["expected_equivalent"]]
    metrics = {
        "pairs": len(scored),
        "accuracy": round(sum(row["correct_equivalence"] for row in scored) / len(scored), 4),
        "merge_precision": round(sum(row["expected_equivalent"] for row in accepted) / len(accepted), 4) if accepted else None,
        "merge_recall": round(sum(row["safe_to_replace"] for row in positives) / len(positives), 4) if positives else None,
        "dangerous_false_merges": sum(row["dangerous_false_merge"] for row in scored),
        "accepted": len(accepted),
        "rejected": len(scored) - len(accepted),
        "normalizer_decisions": sum(row["source"] == "normalizer" for row in scored),
        "hard_rule_decisions": sum(row["source"] == "hard_rule" for row in scored),
        "model_decisions": sum(row["source"] == "model" for row in scored),
    }
    report = {"version": "7.1", "model": args.judge_model, "metrics": metrics, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
