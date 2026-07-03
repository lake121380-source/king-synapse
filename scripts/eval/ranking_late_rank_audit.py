#!/usr/bin/env python
"""Sanitized DMR late-rank audit.

This script audits answer-bearing memories that appear only after rank 10 in
existing DMR top-k reports. It does not rerun retrieval and does not inspect
raw third-party questions, answers, dialogs, sessions, memory content, or
generated answer text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Audit sanitized DMR late-rank cases.")
    parser.add_argument(
        "--dmr50-top-k-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-50-top-k.json",
    )
    parser.add_argument(
        "--dmr200-top-k-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-200-top-k.json",
    )
    parser.add_argument(
        "--dmr50-transition-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-transition-audit-dmr-50.json",
    )
    parser.add_argument(
        "--dmr200-transition-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-transition-audit-dmr-200.json",
    )
    parser.add_argument(
        "--vector-weight-transition-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-vector-weight-transition-audit-dmr-longmem-50.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-late-rank-audit-dmr-50-200.json",
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


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def top_k_runs(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(run["k"]): run for run in report["datasets"][0]["runs"]}


def per_query_by_sample(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["sample_id"]: item for item in run.get("per_query", [])}


def rank(item: dict[str, Any] | None) -> int | None:
    if item is None:
        return None
    value = item.get("first_relevant_rank")
    return int(value) if value is not None else None


def in_top(rank_value: int | None, k: int) -> bool:
    return rank_value is not None and rank_value <= k


def rank_band(rank_value: int | None) -> str:
    if rank_value is None:
        return "absent"
    if rank_value == 1:
        return "top1"
    if rank_value <= 10:
        return "top2_10"
    if rank_value <= 15:
        return "rank11_15"
    if rank_value <= 25:
        return "rank16_25"
    if rank_value <= 35:
        return "rank26_35"
    if rank_value <= 50:
        return "rank36_50"
    return "after50"


def outcome_bucket(top10_rank: int | None, top50_rank: int | None) -> str:
    if top10_rank == 1:
        return "top1_hit"
    if in_top(top10_rank, 10):
        return "top10_not_top1"
    if in_top(top50_rank, 50):
        return "top50_only_late_rank"
    return "top50_retrieval_miss"


def transition_case_map(report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if report is None:
        return {}
    return {case["sample_id"]: case for case in report["audit"].get("cases", [])}


def vector_weight_case_map(report: dict[str, Any] | None, dataset_id: str) -> dict[str, dict[str, Any]]:
    if report is None:
        return {}
    for dataset in report.get("datasets", []):
        if dataset.get("id") == dataset_id:
            return {case["sample_id"]: case for case in dataset.get("cases", [])}
    return {}


def compact_transition_context(case: dict[str, Any] | None) -> dict[str, Any] | None:
    if case is None:
        return None
    return {
        "ranks": case.get("ranks"),
        "baseline_to_vector": case.get("baseline_to_vector"),
        "vector_to_reranker": case.get("vector_to_reranker"),
        "top10_to_top25": case.get("top10_to_top25"),
        "top25_to_top50": case.get("top25_to_top50"),
        "dialog_to_merged_session": case.get("dialog_to_merged_session"),
        "original_to_keyword_boost": case.get("original_to_keyword_boost"),
    }


def compact_vector_weight_context(case: dict[str, Any] | None) -> dict[str, Any] | None:
    if case is None:
        return None
    return {
        "control_rank": (case.get("control") or {}).get("rank"),
        "candidate_rank": (case.get("candidate") or {}).get("rank"),
        "rank_delta": case.get("rank_delta"),
        "transition": case.get("transition"),
    }


def compact_query(item: dict[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {
            "rank": None,
            "rank_band": "absent",
            "returned_relevant_count": None,
            "recall_at_10": None,
            "rr": None,
            "ndcg_at_10": None,
        }
    rank_value = rank(item)
    return {
        "rank": rank_value,
        "rank_band": rank_band(rank_value),
        "returned_relevant_count": item.get("returned_relevant_count"),
        "recall_at_10": item.get("recall_at_10"),
        "rr": item.get("rr"),
        "ndcg_at_10": item.get("ndcg_at_10"),
    }


def rank_stats(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"min": None, "max": None, "mean": None, "median": None}
    return {
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "median": median(values),
    }


def summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    top50_ranks = [case["top50"]["rank"] for case in cases if case["top50"]["rank"] is not None]
    return {
        "count": len(cases),
        "rank_stats": rank_stats(top50_ranks),
        "rank_band_counts": dict(sorted(Counter(case["top50"]["rank_band"] for case in cases).items())),
        "top25_recoverable_count": sum(1 for case in cases if in_top(case["top25"]["rank"], 25)),
        "rank26_to_50_count": sum(
            1
            for case in cases
            if case["top50"]["rank"] is not None and not in_top(case["top25"]["rank"], 25)
        ),
        "returned_relevant_count_distribution": dict(
            sorted(Counter(case["top50"]["returned_relevant_count"] for case in cases).items())
        ),
        "relevant_count_distribution": dict(sorted(Counter(case["relevant_count"] for case in cases).items())),
        "transition_effect_counts": dict(
            sorted(
                Counter(
                    (case.get("transition_context") or {}).get("vector_to_reranker")
                    for case in cases
                    if case.get("transition_context") is not None
                ).items()
            )
        ),
        "vector_weight_transition_counts": dict(
            sorted(
                Counter(
                    (case.get("vector_weight_1_to_1_5") or {}).get("transition")
                    for case in cases
                    if case.get("vector_weight_1_to_1_5") is not None
                ).items()
            )
        ),
        "sample_ids": [case["sample_id"] for case in cases],
    }


def summarize_misses(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(cases),
        "sample_ids": [case["sample_id"] for case in cases],
        "relevant_count_distribution": dict(sorted(Counter(case["relevant_count"] for case in cases).items())),
        "vector_weight_transition_counts": dict(
            sorted(
                Counter(
                    (case.get("vector_weight_1_to_1_5") or {}).get("transition")
                    for case in cases
                    if case.get("vector_weight_1_to_1_5") is not None
                ).items()
            )
        ),
    }


def audit_dataset(
    *,
    dataset_id: str,
    dataset_label: str,
    top_k_report: dict[str, Any],
    transition_report: dict[str, Any] | None,
    vector_weight_report: dict[str, Any] | None,
) -> dict[str, Any]:
    runs = top_k_runs(top_k_report)
    required = {10, 25, 50}
    missing = required.difference(runs)
    if missing:
        raise ValueError(f"{dataset_id} top-k report missing runs: {sorted(missing)}")

    top10_by_id = per_query_by_sample(runs[10])
    top25_by_id = per_query_by_sample(runs[25])
    top50_by_id = per_query_by_sample(runs[50])
    transitions = transition_case_map(transition_report)
    vector_weight = vector_weight_case_map(vector_weight_report, "dmr") if dataset_id == "dmr50" else {}
    sample_ids = sorted(set(top10_by_id) | set(top25_by_id) | set(top50_by_id))

    cases: list[dict[str, Any]] = []
    for sample_id in sample_ids:
        top10 = top10_by_id.get(sample_id)
        top25 = top25_by_id.get(sample_id)
        top50 = top50_by_id.get(sample_id)
        top10_rank = rank(top10)
        top50_rank = rank(top50)
        source = top50 or top25 or top10 or {}
        cases.append(
            {
                "sample_id": sample_id,
                "category": source.get("category"),
                "source_session_count": source.get("source_session_count"),
                "relevant_count": source.get("relevant_count"),
                "top10": compact_query(top10),
                "top25": compact_query(top25),
                "top50": compact_query(top50),
                "outcome": outcome_bucket(top10_rank, top50_rank),
                "transition_context": compact_transition_context(transitions.get(sample_id)),
                "vector_weight_1_to_1_5": compact_vector_weight_context(vector_weight.get(sample_id)),
            }
        )

    outcome_counts = Counter(case["outcome"] for case in cases)
    late_rank_cases = [case for case in cases if case["outcome"] == "top50_only_late_rank"]
    miss_cases = [case for case in cases if case["outcome"] == "top50_retrieval_miss"]
    top10_not_top1_cases = [case for case in cases if case["outcome"] == "top10_not_top1"]

    return {
        "id": dataset_id,
        "label": dataset_label,
        "sample_size": len(cases),
        "top_k_runs": {
            str(k): {
                "recall_at_10": runs[k].get("recall_at_10"),
                "mrr_at_10": runs[k].get("mrr_at_10"),
                "rank_bucket_counts": runs[k].get("rank_bucket_counts"),
                "failure_type_counts": runs[k].get("failure_type_counts"),
            }
            for k in sorted(required)
        },
        "outcome_counts_from_top10_vs_top50": dict(sorted(outcome_counts.items())),
        "late_rank_summary": summarize_cases(late_rank_cases),
        "retrieval_miss_summary": summarize_misses(miss_cases),
        "top10_not_top1_summary": {
            "count": len(top10_not_top1_cases),
            "sample_ids": [case["sample_id"] for case in top10_not_top1_cases],
        },
        "late_rank_cases": late_rank_cases,
        "retrieval_miss_cases": miss_cases,
    }


def main() -> int:
    args = parse_args()
    root = repo_root()
    args.output = args.output if args.output.is_absolute() else root / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    dmr50_top_k = load_json(args.dmr50_top_k_report)
    dmr200_top_k = load_json(args.dmr200_top_k_report)
    dmr50_transition = load_json(args.dmr50_transition_report)
    dmr200_transition = load_json(args.dmr200_transition_report)
    vector_weight_transition = load_json(args.vector_weight_transition_report)

    datasets = [
        audit_dataset(
            dataset_id="dmr50",
            dataset_label="DMR candidate MSC-Self-Instruct, punctuation-normalized 50",
            top_k_report=dmr50_top_k,
            transition_report=dmr50_transition,
            vector_weight_report=vector_weight_transition,
        ),
        audit_dataset(
            dataset_id="dmr200",
            dataset_label="DMR candidate MSC-Self-Instruct, punctuation-normalized 200",
            top_k_report=dmr200_top_k,
            transition_report=dmr200_transition,
            vector_weight_report=None,
        ),
    ]

    report = {
        "schema_version": "king-synapse.ranking-late-rank-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_late_rank_audit.py",
        "inputs": {
            "dmr50_top_k_report": {
                "path": report_path(args.dmr50_top_k_report),
                "sha256": sha256_file(args.dmr50_top_k_report),
            },
            "dmr200_top_k_report": {
                "path": report_path(args.dmr200_top_k_report),
                "sha256": sha256_file(args.dmr200_top_k_report),
            },
            "dmr50_transition_report": {
                "path": report_path(args.dmr50_transition_report),
                "sha256": sha256_file(args.dmr50_transition_report),
            },
            "dmr200_transition_report": {
                "path": report_path(args.dmr200_transition_report),
                "sha256": sha256_file(args.dmr200_transition_report),
            },
            "vector_weight_transition_report": {
                "path": report_path(args.vector_weight_transition_report),
                "sha256": sha256_file(args.vector_weight_transition_report),
            },
        },
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "datasets": datasets,
        "limits": [
            "Uses sanitized per-query sample IDs, ranks, buckets, and aggregate metrics only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Audits late-rank cases from existing top-k reports; it does not change retrieval or ranking behavior.",
            "Top-50-only means absent from the top-10 run but present within the top-50 run.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(args.output),
                "datasets": {
                    dataset["id"]: {
                        "sample_size": dataset["sample_size"],
                        "outcome_counts": dataset["outcome_counts_from_top10_vs_top50"],
                        "late_rank_summary": {
                            "count": dataset["late_rank_summary"]["count"],
                            "rank_band_counts": dataset["late_rank_summary"]["rank_band_counts"],
                            "top25_recoverable_count": dataset["late_rank_summary"][
                                "top25_recoverable_count"
                            ],
                            "rank26_to_50_count": dataset["late_rank_summary"]["rank26_to_50_count"],
                            "transition_effect_counts": dataset["late_rank_summary"][
                                "transition_effect_counts"
                            ],
                            "vector_weight_transition_counts": dataset["late_rank_summary"][
                                "vector_weight_transition_counts"
                            ],
                        },
                    }
                    for dataset in datasets
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
