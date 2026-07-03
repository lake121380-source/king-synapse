#!/usr/bin/env python
"""Sanitized DMR ranking-failure audit.

This script compares existing sanitized reports and classifies DMR 50 outcomes
without reading raw third-party questions, answers, dialogs, or generated text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Audit sanitized DMR ranking failures.")
    parser.add_argument(
        "--candidate-report",
        type=Path,
        default=root / "crates/eval/reports/dmr-50-punctuation-validation.json",
    )
    parser.add_argument(
        "--top-k-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-50-top-k.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-failure-audit-dmr-50.json",
    )
    parser.add_argument(
        "--dataset-label",
        default="DMR candidate MSC-Self-Instruct, punctuation-normalized 50",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_runs(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    runs = report["datasets"][0]["kr_eval_runs"]
    return {run["mode"]: run for run in runs}


def top_k_runs(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    runs = report["datasets"][0]["runs"]
    return {int(run["k"]): run for run in runs}


def per_query_by_sample(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["sample_id"]: item for item in run.get("per_query", [])}


def rank(item: dict[str, Any] | None) -> int | None:
    if item is None:
        return None
    value = item.get("first_relevant_rank")
    return int(value) if value is not None else None


def in_top(rank_value: int | None, k: int) -> bool:
    return rank_value is not None and rank_value <= k


def final_bucket(rerank10_rank: int | None, top50_rank: int | None) -> str:
    if rerank10_rank == 1:
        return "top1_hit"
    if in_top(rerank10_rank, 10):
        return "top10_not_top1"
    if top50_rank is not None and top50_rank <= 50:
        return "top50_only_late_rank"
    return "top50_retrieval_miss"


def vector_effect(baseline_rank: int | None, vector_rank: int | None) -> str:
    baseline_hit = in_top(baseline_rank, 10)
    vector_hit = in_top(vector_rank, 10)
    if not baseline_hit and vector_hit:
        return "vector_recovered_to_top10"
    if baseline_hit and not vector_hit:
        return "vector_suppressed_from_top10"
    if baseline_rank == 1 and vector_rank == 1:
        return "stable_top1"
    if baseline_hit and vector_hit:
        return "top10_preserved"
    return "no_top10_change"


def reranker_effect(vector_rank: int | None, rerank_rank: int | None) -> str:
    vector_hit = in_top(vector_rank, 10)
    rerank_hit = in_top(rerank_rank, 10)
    if not vector_hit and rerank_hit:
        return "reranker_recovered_to_top10"
    if vector_hit and not rerank_hit:
        return "reranker_suppressed_from_top10"
    if vector_rank == 1 and rerank_rank == 1:
        return "stable_top1"
    if vector_rank != 1 and rerank_rank == 1:
        return "reranker_promoted_to_top1"
    if vector_rank == 1 and rerank_rank != 1:
        return "reranker_demoted_from_top1"
    if vector_hit and rerank_hit:
        return "top10_preserved"
    return "no_top10_change"


def compact_case(
    *,
    sample_id: str,
    baseline: dict[str, Any] | None,
    vector: dict[str, Any] | None,
    rerank_candidate: dict[str, Any] | None,
    top10: dict[str, Any] | None,
    top25: dict[str, Any] | None,
    top50: dict[str, Any] | None,
) -> dict[str, Any]:
    baseline_rank = rank(baseline)
    vector_rank = rank(vector)
    rerank_candidate_rank = rank(rerank_candidate)
    top10_rank = rank(top10)
    top25_rank = rank(top25)
    top50_rank = rank(top50)
    source = top10 or rerank_candidate or top50 or vector or baseline or {}
    return {
        "sample_id": sample_id,
        "source_session_count": source.get("source_session_count"),
        "relevant_count": source.get("relevant_count"),
        "ranks": {
            "baseline_rrf": baseline_rank,
            "vectors": vector_rank,
            "vectors_rerank_candidate50": rerank_candidate_rank,
            "vectors_rerank_top10": top10_rank,
            "vectors_rerank_top25": top25_rank,
            "vectors_rerank_top50": top50_rank,
        },
        "final_bucket": final_bucket(top10_rank, top50_rank),
        "vector_effect": vector_effect(baseline_rank, vector_rank),
        "reranker_effect": reranker_effect(vector_rank, top10_rank),
    }


def audit(candidate_report: dict[str, Any], top_k_report: dict[str, Any]) -> dict[str, Any]:
    candidate = candidate_runs(candidate_report)
    top_k = top_k_runs(top_k_report)
    baseline_by_id = per_query_by_sample(candidate["baseline-rrf"])
    vector_by_id = per_query_by_sample(candidate["vectors"])
    rerank_by_id = per_query_by_sample(candidate["vectors-rerank"])
    top10_by_id = per_query_by_sample(top_k[10])
    top25_by_id = per_query_by_sample(top_k[25])
    top50_by_id = per_query_by_sample(top_k[50])
    sample_ids = sorted(set(rerank_by_id) | set(top50_by_id))

    cases = [
        compact_case(
            sample_id=sample_id,
            baseline=baseline_by_id.get(sample_id),
            vector=vector_by_id.get(sample_id),
            rerank_candidate=rerank_by_id.get(sample_id),
            top10=top10_by_id.get(sample_id),
            top25=top25_by_id.get(sample_id),
            top50=top50_by_id.get(sample_id),
        )
        for sample_id in sample_ids
    ]

    final_counts = Counter(case["final_bucket"] for case in cases)
    vector_counts = Counter(case["vector_effect"] for case in cases)
    reranker_counts = Counter(case["reranker_effect"] for case in cases)
    top50_only = [case for case in cases if case["final_bucket"] == "top50_only_late_rank"]
    top50_miss = [case for case in cases if case["final_bucket"] == "top50_retrieval_miss"]

    return {
        "sample_size": len(cases),
        "bucket_counts": dict(sorted(final_counts.items())),
        "vector_effect_counts": dict(sorted(vector_counts.items())),
        "reranker_effect_counts": dict(sorted(reranker_counts.items())),
        "top50_only_count": len(top50_only),
        "top50_retrieval_miss_count": len(top50_miss),
        "top50_only_cases": top50_only,
        "top50_retrieval_miss_cases": top50_miss,
        "cases": cases,
    }


def main() -> int:
    args = parse_args()
    args.output = args.output if args.output.is_absolute() else repo_root() / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    candidate_report = load_json(args.candidate_report)
    top_k_report = load_json(args.top_k_report)
    result = audit(candidate_report, top_k_report)

    report = {
        "schema_version": "king-synapse.ranking-failure-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_failure_audit.py",
        "inputs": {
            "candidate_report": {
                "path": str(args.candidate_report),
                "sha256": sha256_file(args.candidate_report),
            },
            "top_k_report": {
                "path": str(args.top_k_report),
                "sha256": sha256_file(args.top_k_report),
            },
        },
        "dataset": args.dataset_label,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "audit": result,
        "limits": [
            "Uses sanitized per-query ranks only.",
            "Does not inspect raw questions, answers, dialogs, sessions, or generated answer text.",
            "Classifies ranking outcomes; it does not change retrieval or ranking behavior.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sample_size": result["sample_size"],
                "bucket_counts": result["bucket_counts"],
                "vector_effect_counts": result["vector_effect_counts"],
                "reranker_effect_counts": result["reranker_effect_counts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
