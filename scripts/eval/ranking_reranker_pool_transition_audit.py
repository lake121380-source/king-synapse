#!/usr/bin/env python
"""Sanitized reranker-pool transition audit for DMR 200.

This script compares reranker-pool variants from an existing ranking ablation
report. It uses sanitized per-query sample IDs, ranks, and metrics only; it
does not inspect raw third-party questions, answers, dialogs, sessions, memory
content, or generated answer text.
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
    parser = argparse.ArgumentParser(description="Audit DMR 200 reranker-pool rank transitions.")
    parser.add_argument(
        "--pool-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-200-reranker-pool.json",
    )
    parser.add_argument(
        "--late-rank-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-late-rank-audit-dmr-50-200.json",
    )
    parser.add_argument("--control-pool", type=int, default=50)
    parser.add_argument("--candidate-pools", default="25,100")
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-reranker-pool-transition-audit-dmr-200.json",
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


def parse_int_list(raw: str) -> list[int]:
    values: list[int] = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        parsed = int(value)
        if parsed <= 0:
            raise ValueError(f"candidate pools must be positive: {parsed}")
        values.append(parsed)
    if not values:
        raise ValueError("no candidate pools selected")
    return values


def runs_by_pool(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    dataset = report["datasets"][0]
    return {int(run["reranker_pool"]): run for run in dataset.get("runs", [])}


def per_query_by_sample(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["sample_id"]: item for item in run.get("per_query", [])}


def rank(item: dict[str, Any] | None) -> int | None:
    if item is None:
        return None
    value = item.get("first_relevant_rank")
    return int(value) if value is not None else None


def in_top(rank_value: int | None, k: int) -> bool:
    return rank_value is not None and rank_value <= k


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
    rank_value = rank(item)
    if item is None:
        return {
            "rank": None,
            "bucket": "absent",
            "returned_relevant_count": None,
            "recall_at_10": None,
            "rr": None,
            "ndcg_at_10": None,
        }
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
        "reranker_pool": run.get("reranker_pool"),
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


def dmr200_late_rank_sets(report: dict[str, Any]) -> dict[str, set[str]]:
    dataset = next(item for item in report["datasets"] if item.get("id") == "dmr200")
    late_cases = dataset.get("late_rank_cases", [])
    miss_cases = dataset.get("retrieval_miss_cases", [])
    top10_not_top1 = dataset.get("top10_not_top1_summary", {}).get("sample_ids", [])
    late_rank_all = {case["sample_id"] for case in late_cases}
    late_rank_11_25 = {
        case["sample_id"]
        for case in late_cases
        if (case.get("top50") or {}).get("rank") is not None and int(case["top50"]["rank"]) <= 25
    }
    late_rank_26_50 = late_rank_all.difference(late_rank_11_25)
    return {
        "late_rank_all": late_rank_all,
        "late_rank_11_25": late_rank_11_25,
        "late_rank_26_50": late_rank_26_50,
        "top50_retrieval_miss": {case["sample_id"] for case in miss_cases},
        "top10_not_top1": set(top10_not_top1),
    }


def subset_summary(cases: list[dict[str, Any]], sample_ids: set[str]) -> dict[str, Any]:
    subset = [case for case in cases if case["sample_id"] in sample_ids]
    return {
        "count": len(subset),
        "transition_counts": dict(sorted(Counter(case["transition"] for case in subset).items())),
        "sample_ids_by_transition": {
            name: [case["sample_id"] for case in subset if case["transition"] == name]
            for name in sorted({case["transition"] for case in subset})
        },
        "rank_pairs": [
            {
                "sample_id": case["sample_id"],
                "control_rank": case["control"]["rank"],
                "candidate_rank": case["candidate"]["rank"],
                "transition": case["transition"],
            }
            for case in subset
        ],
    }


def compare_pool(
    *,
    control_run: dict[str, Any],
    candidate_run: dict[str, Any],
    subset_sets: dict[str, set[str]],
) -> dict[str, Any]:
    control_by_id = per_query_by_sample(control_run)
    candidate_by_id = per_query_by_sample(candidate_run)
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

    return {
        "candidate_pool": candidate_run.get("reranker_pool"),
        "control": compact_run(control_run),
        "candidate": compact_run(candidate_run),
        "metric_deltas_candidate_minus_control": metric_deltas(control_run, candidate_run),
        "transition_counts": dict(sorted(Counter(case["transition"] for case in cases).items())),
        "subsets": {
            name: subset_summary(cases, values) for name, values in sorted(subset_sets.items())
        },
        "cases": cases,
    }


def main() -> int:
    args = parse_args()
    args.pool_report = args.pool_report if args.pool_report.is_absolute() else repo_root() / args.pool_report
    args.late_rank_report = (
        args.late_rank_report if args.late_rank_report.is_absolute() else repo_root() / args.late_rank_report
    )
    args.output = args.output if args.output.is_absolute() else repo_root() / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    pool_report = load_json(args.pool_report)
    late_rank_report = load_json(args.late_rank_report)
    runs = runs_by_pool(pool_report)
    if args.control_pool not in runs:
        raise ValueError(f"pool report missing control pool {args.control_pool}")
    candidate_pools = parse_int_list(args.candidate_pools)
    missing = [pool for pool in candidate_pools if pool not in runs]
    if missing:
        raise ValueError(f"pool report missing candidate pools {missing}")

    subset_sets = dmr200_late_rank_sets(late_rank_report)
    control_run = runs[args.control_pool]
    comparisons = [
        compare_pool(control_run=control_run, candidate_run=runs[pool], subset_sets=subset_sets)
        for pool in candidate_pools
    ]

    report = {
        "schema_version": "king-synapse.ranking-reranker-pool-transition-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_reranker_pool_transition_audit.py",
        "inputs": {
            "reranker_pool_ablation_report": {
                "path": report_path(args.pool_report),
                "sha256": sha256_file(args.pool_report),
            },
            "late_rank_audit_report": {
                "path": report_path(args.late_rank_report),
                "sha256": sha256_file(args.late_rank_report),
            },
        },
        "dataset": "DMR candidate MSC-Self-Instruct, punctuation-normalized 200",
        "control_pool": args.control_pool,
        "candidate_pools": candidate_pools,
        "subset_sizes": {name: len(values) for name, values in sorted(subset_sets.items())},
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "comparisons": comparisons,
        "limits": [
            "Uses sanitized per-query sample IDs, ranks, buckets, and metrics only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Compares existing reranker-pool ablation runs; it does not change retrieval or ranking behavior.",
            "Subset labels inherit the late-rank audit's top-50-only and retrieval-miss definitions.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(args.output),
                "control_pool": args.control_pool,
                "candidate_pools": candidate_pools,
                "comparisons": {
                    str(item["candidate_pool"]): {
                        "metric_deltas_candidate_minus_control": item[
                            "metric_deltas_candidate_minus_control"
                        ],
                        "transition_counts": item["transition_counts"],
                        "late_rank_11_25": item["subsets"]["late_rank_11_25"][
                            "transition_counts"
                        ],
                        "late_rank_26_50": item["subsets"]["late_rank_26_50"][
                            "transition_counts"
                        ],
                        "top50_retrieval_miss": item["subsets"]["top50_retrieval_miss"][
                            "transition_counts"
                        ],
                    }
                    for item in comparisons
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
