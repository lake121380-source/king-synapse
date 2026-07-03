#!/usr/bin/env python
"""Sanitized vector-weight transition audit.

This script compares two vector-weight variants from an existing ranking
ablation report. It uses only sanitized per-query sample IDs, rank buckets, and
metric fields; it does not inspect raw third-party questions, answers, dialogs,
sessions, memory content, or generated text.
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
    parser = argparse.ArgumentParser(description="Audit sanitized vector-weight rank transitions.")
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-longmem-50-vector-weight.json",
    )
    parser.add_argument("--control-weight", type=float, default=1.0)
    parser.add_argument("--candidate-weight", type=float, default=1.5)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-vector-weight-transition-audit-dmr-longmem-50.json",
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


def run_vector_weight(run: dict[str, Any]) -> float:
    if run.get("vector_weight") is not None:
        return float(run["vector_weight"])
    weights = run.get("rrf_weights") or {}
    if weights.get("vector") is not None:
        return float(weights["vector"])
    return float(run["ablated_value"])


def runs_by_vector_weight(dataset: dict[str, Any]) -> dict[float, dict[str, Any]]:
    return {round(run_vector_weight(run), 6): run for run in dataset.get("runs", [])}


def per_query_by_sample(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["sample_id"]: item for item in run.get("per_query", [])}


def rank(item: dict[str, Any] | None) -> int | None:
    if item is None:
        return None
    value = item.get("first_relevant_rank")
    return int(value) if value is not None else None


def bucket(rank_value: int | None) -> str:
    if rank_value is None:
        return "absent"
    if rank_value == 1:
        return "top1"
    if rank_value <= 10:
        return "top10"
    if rank_value <= 50:
        return "top50"
    return "after50"


def in_top(rank_value: int | None, k: int) -> bool:
    return rank_value is not None and rank_value <= k


def transition(control_rank: int | None, candidate_rank: int | None) -> str:
    control_top10 = in_top(control_rank, 10)
    candidate_top10 = in_top(candidate_rank, 10)
    if control_rank == 1 and candidate_rank == 1:
        return "stable_top1"
    if control_rank != 1 and candidate_rank == 1:
        return "promoted_to_top1"
    if control_rank == 1 and candidate_rank != 1:
        return "demoted_from_top1"
    if not control_top10 and candidate_top10:
        return "recovered_to_top10"
    if control_top10 and not candidate_top10:
        return "suppressed_from_top10"
    if control_top10 and candidate_top10:
        return "top10_preserved"
    if control_rank is None and candidate_rank is None:
        return "miss_unchanged"
    if bucket(control_rank) != bucket(candidate_rank):
        return "bucket_changed_outside_top10"
    return "no_top10_change"


def compact_query(item: dict[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {
            "rank": None,
            "bucket": "absent",
            "returned_relevant_count": None,
            "recall_at_10": None,
            "rr": None,
            "ndcg_at_10": None,
        }
    rank_value = rank(item)
    return {
        "rank": rank_value,
        "bucket": bucket(rank_value),
        "returned_relevant_count": item.get("returned_relevant_count"),
        "recall_at_10": item.get("recall_at_10"),
        "rr": item.get("rr"),
        "ndcg_at_10": item.get("ndcg_at_10"),
    }


def safe_delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant_id": run.get("variant_id"),
        "vector_weight": run_vector_weight(run),
        "recall_at_10": run.get("recall_at_10"),
        "mrr_at_10": run.get("mrr_at_10"),
        "ndcg_at_10": run.get("ndcg_at_10"),
        "p50_latency_ms": run.get("p50_latency_ms"),
        "p95_latency_ms": run.get("p95_latency_ms"),
        "rank_bucket_counts": run.get("rank_bucket_counts"),
        "failure_type_counts": run.get("failure_type_counts"),
    }


def metric_deltas(control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "recall_at_10": safe_delta(candidate.get("recall_at_10"), control.get("recall_at_10")),
        "mrr_at_10": safe_delta(candidate.get("mrr_at_10"), control.get("mrr_at_10")),
        "ndcg_at_10": safe_delta(candidate.get("ndcg_at_10"), control.get("ndcg_at_10")),
        "p50_latency_ms": safe_delta(candidate.get("p50_latency_ms"), control.get("p50_latency_ms")),
        "p95_latency_ms": safe_delta(candidate.get("p95_latency_ms"), control.get("p95_latency_ms")),
        "top1": int((candidate.get("rank_bucket_counts") or {}).get("top_1", 0))
        - int((control.get("rank_bucket_counts") or {}).get("top_1", 0)),
        "top10_not_top1": int((candidate.get("rank_bucket_counts") or {}).get("top_10", 0))
        - int((control.get("rank_bucket_counts") or {}).get("top_10", 0)),
        "retrieval_miss": int((candidate.get("failure_type_counts") or {}).get("retrieval_miss", 0))
        - int((control.get("failure_type_counts") or {}).get("retrieval_miss", 0)),
    }


def summarize_subset(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(cases),
        "sample_ids": [case["sample_id"] for case in cases],
        "rank_pairs": [
            {
                "sample_id": case["sample_id"],
                "control_rank": case["control"]["rank"],
                "candidate_rank": case["candidate"]["rank"],
            }
            for case in cases
        ],
    }


def audit_dataset(
    *,
    dataset: dict[str, Any],
    control_weight: float,
    candidate_weight: float,
) -> dict[str, Any]:
    runs = runs_by_vector_weight(dataset)
    control_key = round(control_weight, 6)
    candidate_key = round(candidate_weight, 6)
    if control_key not in runs:
        raise ValueError(f"{dataset.get('id')} missing control vector weight {control_weight}")
    if candidate_key not in runs:
        raise ValueError(f"{dataset.get('id')} missing candidate vector weight {candidate_weight}")

    control = runs[control_key]
    candidate = runs[candidate_key]
    control_by_id = per_query_by_sample(control)
    candidate_by_id = per_query_by_sample(candidate)
    sample_ids = sorted(set(control_by_id) | set(candidate_by_id))

    cases: list[dict[str, Any]] = []
    for sample_id in sample_ids:
        control_item = control_by_id.get(sample_id)
        candidate_item = candidate_by_id.get(sample_id)
        source = candidate_item or control_item or {}
        control_rank = rank(control_item)
        candidate_rank = rank(candidate_item)
        rank_delta = None
        if control_rank is not None and candidate_rank is not None:
            rank_delta = candidate_rank - control_rank
        cases.append(
            {
                "sample_id": sample_id,
                "category": source.get("category"),
                "source_session_count": source.get("source_session_count"),
                "relevant_count": source.get("relevant_count"),
                "control": compact_query(control_item),
                "candidate": compact_query(candidate_item),
                "rank_delta": rank_delta,
                "transition": transition(control_rank, candidate_rank),
            }
        )

    transition_counts = Counter(case["transition"] for case in cases)
    control_bucket_counts = Counter(case["control"]["bucket"] for case in cases)
    candidate_bucket_counts = Counter(case["candidate"]["bucket"] for case in cases)
    transition_sets = {
        name: summarize_subset([case for case in cases if case["transition"] == name])
        for name in sorted(transition_counts)
    }

    return {
        "id": dataset.get("id"),
        "name": dataset.get("name"),
        "sample_size": len(cases),
        "control": compact_run(control),
        "candidate": compact_run(candidate),
        "metric_deltas_candidate_minus_control": metric_deltas(control, candidate),
        "control_bucket_counts": dict(sorted(control_bucket_counts.items())),
        "candidate_bucket_counts": dict(sorted(candidate_bucket_counts.items())),
        "transition_counts": dict(sorted(transition_counts.items())),
        "transition_sets": transition_sets,
        "cases": cases,
    }


def main() -> int:
    args = parse_args()
    args.input = args.input if args.input.is_absolute() else repo_root() / args.input
    args.output = args.output if args.output.is_absolute() else repo_root() / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(args.input)
    audits = [
        audit_dataset(
            dataset=dataset,
            control_weight=args.control_weight,
            candidate_weight=args.candidate_weight,
        )
        for dataset in source.get("datasets", [])
    ]

    report = {
        "schema_version": "king-synapse.ranking-vector-weight-transition-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_vector_weight_transition_audit.py",
        "inputs": {
            "vector_weight_ablation_report": {
                "path": report_path(args.input),
                "sha256": sha256_file(args.input),
            }
        },
        "control_weight": args.control_weight,
        "candidate_weight": args.candidate_weight,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "datasets": audits,
        "limits": [
            "Uses sanitized per-query sample IDs, rank buckets, and metrics only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Classifies vector-weight rank transitions; it does not change retrieval or ranking behavior.",
            "Compares existing vector-weight ablation runs and inherits their sample-size and mapping boundaries.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "control_weight": args.control_weight,
                "candidate_weight": args.candidate_weight,
                "datasets": {
                    audit["id"]: {
                        "sample_size": audit["sample_size"],
                        "metric_deltas_candidate_minus_control": audit[
                            "metric_deltas_candidate_minus_control"
                        ],
                        "transition_counts": audit["transition_counts"],
                    }
                    for audit in audits
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
