#!/usr/bin/env python
"""Evaluate sanitized conditional reranker-pool triggers.

The audit simulates using a larger reranker pool only for queries selected by
score/rerank-margin signals from the control run. It reads existing sanitized
reports and does not inspect raw third-party questions, answers, dialogs,
sessions, memory content, or generated answer text.
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
    parser = argparse.ArgumentParser(description="Audit conditional reranker-pool triggers.")
    parser.add_argument(
        "--signal-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-200-reranker-pool-signal.json",
    )
    parser.add_argument(
        "--late-rank-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-late-rank-audit-dmr-50-200.json",
    )
    parser.add_argument("--control-pool", type=int, default=50)
    parser.add_argument("--candidate-pool", type=int, default=100)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-pool-signal-trigger-audit-dmr-200.json",
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


def runs_by_pool(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(run["reranker_pool"]): run for run in report["datasets"][0].get("runs", [])}


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


def late_rank_sets(report: dict[str, Any]) -> dict[str, set[str]]:
    dataset = next(item for item in report["datasets"] if item.get("id") == "dmr200")
    late_cases = dataset.get("late_rank_cases", [])
    miss_cases = dataset.get("retrieval_miss_cases", [])
    late_all = {case["sample_id"] for case in late_cases}
    late_11_25 = {
        case["sample_id"]
        for case in late_cases
        if (case.get("top50") or {}).get("rank") is not None and int(case["top50"]["rank"]) <= 25
    }
    return {
        "late_rank_all": late_all,
        "late_rank_11_25": late_11_25,
        "late_rank_26_50": late_all.difference(late_11_25),
        "top50_retrieval_miss": {case["sample_id"] for case in miss_cases},
    }


def signal(item: dict[str, Any], field: str) -> Any:
    summary = item.get("ranking_signal_summary") or {}
    if field == "score_margin":
        return summary.get("top1_top2_score_margin")
    if field == "rerank_margin":
        return summary.get("top1_top2_rerank_margin")
    if field == "top1_source_count":
        return (summary.get("top1") or {}).get("source_count")
    if field == "top1_sources":
        return (summary.get("top1") or {}).get("sources") or []
    if field == "top1_best_branch_rank":
        return (summary.get("top1") or {}).get("best_branch_rank")
    return None


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute percentile over empty values")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * pct / 100.0
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac


def rank_bucket_for_item(item: dict[str, Any]) -> str:
    value = rank(item)
    if value is None:
        return "absent"
    if value == 1:
        return "top_1"
    if value <= 10:
        return "top_10"
    if value <= 50:
        return "top_50"
    return "after_top_50"


def metric_mean(items: list[dict[str, Any]], key: str) -> float:
    if not items:
        return 0.0
    return sum(float(item.get(key) or 0.0) for item in items) / len(items)


def percentile_from_items(items: list[dict[str, Any]], key: str, pct: float) -> float | None:
    values = sorted(float(item.get(key) or 0.0) for item in items)
    if not values:
        return None
    return percentile(values, pct)


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


def build_cases(control: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    control_by_id = per_query_by_sample(control)
    candidate_by_id = per_query_by_sample(candidate)
    cases: list[dict[str, Any]] = []
    for sample_id in sorted(set(control_by_id) | set(candidate_by_id)):
        control_item = control_by_id[sample_id]
        candidate_item = candidate_by_id[sample_id]
        cases.append(
            {
                "sample_id": sample_id,
                "control": control_item,
                "candidate": candidate_item,
                "control_rank": rank(control_item),
                "candidate_rank": rank(candidate_item),
                "transition": transition(rank(control_item), rank(candidate_item)),
            }
        )
    return cases


def trigger_definitions(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    score_margins = sorted(
        float(value)
        for value in (signal(case["control"], "score_margin") for case in cases)
        if value is not None
    )
    rerank_margins = sorted(
        float(value)
        for value in (signal(case["control"], "rerank_margin") for case in cases)
        if value is not None
    )
    triggers: list[dict[str, Any]] = []
    for pct in (10, 20, 30, 40, 50):
        score_threshold = percentile(score_margins, pct)
        triggers.append(
            {
                "id": f"score_margin_p{pct}",
                "description": f"top1/top2 final-score margin <= p{pct}",
                "field": "score_margin",
                "operator": "lte",
                "threshold": score_threshold,
            }
        )
        rerank_threshold = percentile(rerank_margins, pct)
        triggers.append(
            {
                "id": f"rerank_margin_p{pct}",
                "description": f"top1/top2 rerank-logit margin <= p{pct}",
                "field": "rerank_margin",
                "operator": "lte",
                "threshold": rerank_threshold,
            }
        )
    triggers.extend(
        [
            {
                "id": "top1_single_source",
                "description": "top1 hit came from exactly one retrieval branch",
                "field": "top1_source_count",
                "operator": "lte",
                "threshold": 1,
            },
            {
                "id": "top1_vector_only",
                "description": "top1 hit came only from vector branch",
                "field": "top1_sources",
                "operator": "equals",
                "threshold": ["vector"],
            },
            {
                "id": "top1_branch_rank_gt20",
                "description": "best branch rank for top1 is worse than 20",
                "field": "top1_best_branch_rank",
                "operator": "gt",
                "threshold": 20,
            },
        ]
    )
    return triggers


def trigger_matches(case: dict[str, Any], trigger: dict[str, Any]) -> bool:
    value = signal(case["control"], trigger["field"])
    if value is None:
        return False
    operator = trigger["operator"]
    threshold = trigger["threshold"]
    if operator == "lte":
        return float(value) <= float(threshold)
    if operator == "gt":
        return float(value) > float(threshold)
    if operator == "equals":
        return value == threshold
    raise ValueError(f"unknown operator: {operator}")


def summarize_subsets(triggered: list[dict[str, Any]], subset_sets: dict[str, set[str]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name, sample_ids in sorted(subset_sets.items()):
        subset = [case for case in triggered if case["sample_id"] in sample_ids]
        summary[name] = {
            "triggered_count": len(subset),
            "transition_counts": dict(sorted(Counter(case["transition"] for case in subset).items())),
            "sample_ids": [case["sample_id"] for case in subset],
        }
    return summary


def projected_metrics(cases: list[dict[str, Any]], triggered_ids: set[str]) -> dict[str, Any]:
    projected: list[dict[str, Any]] = [
        case["candidate"] if case["sample_id"] in triggered_ids else case["control"]
        for case in cases
    ]
    bucket_counts = Counter(rank_bucket_for_item(item) for item in projected)
    failure_counts = Counter(item.get("failure_type") for item in projected)
    return {
        "recall_at_10": metric_mean(projected, "recall_at_10"),
        "mrr_at_10": metric_mean(projected, "rr"),
        "ndcg_at_10": metric_mean(projected, "ndcg_at_10"),
        "p50_latency_ms_estimate": percentile_from_items(projected, "latency_ms", 50.0),
        "p95_latency_ms_estimate": percentile_from_items(projected, "latency_ms", 95.0),
        "rank_bucket_counts": dict(sorted(bucket_counts.items())),
        "failure_type_counts": dict(sorted(failure_counts.items())),
    }


def metric_deltas(projected: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    return {
        "recall_at_10": projected["recall_at_10"] - float(control.get("recall_at_10") or 0.0),
        "mrr_at_10": projected["mrr_at_10"] - float(control.get("mrr_at_10") or 0.0),
        "ndcg_at_10": projected["ndcg_at_10"] - float(control.get("ndcg_at_10") or 0.0),
        "p50_latency_ms_estimate": projected["p50_latency_ms_estimate"]
        - float(control.get("p50_latency_ms") or 0.0),
        "p95_latency_ms_estimate": projected["p95_latency_ms_estimate"]
        - float(control.get("p95_latency_ms") or 0.0),
        "top1": int(projected["rank_bucket_counts"].get("top_1", 0))
        - int((control.get("rank_bucket_counts") or {}).get("top_1", 0)),
        "top10_not_top1": int(projected["rank_bucket_counts"].get("top_10", 0))
        - int((control.get("rank_bucket_counts") or {}).get("top_10", 0)),
        "retrieval_miss": int(projected["failure_type_counts"].get("retrieval_miss", 0))
        - int((control.get("failure_type_counts") or {}).get("retrieval_miss", 0)),
    }


def evaluate_trigger(
    cases: list[dict[str, Any]],
    trigger: dict[str, Any],
    control: dict[str, Any],
    subset_sets: dict[str, set[str]],
) -> dict[str, Any]:
    triggered = [case for case in cases if trigger_matches(case, trigger)]
    triggered_ids = {case["sample_id"] for case in triggered}
    projected = projected_metrics(cases, triggered_ids)
    return {
        "id": trigger["id"],
        "description": trigger["description"],
        "field": trigger["field"],
        "operator": trigger["operator"],
        "threshold": trigger["threshold"],
        "triggered_count": len(triggered),
        "triggered_fraction": len(triggered) / len(cases) if cases else 0.0,
        "triggered_transition_counts": dict(sorted(Counter(case["transition"] for case in triggered).items())),
        "subset_trigger_summary": summarize_subsets(triggered, subset_sets),
        "projected": projected,
        "deltas_vs_control": metric_deltas(projected, control),
    }


def main() -> int:
    args = parse_args()
    args.signal_report = args.signal_report if args.signal_report.is_absolute() else repo_root() / args.signal_report
    args.late_rank_report = (
        args.late_rank_report if args.late_rank_report.is_absolute() else repo_root() / args.late_rank_report
    )
    args.output = args.output if args.output.is_absolute() else repo_root() / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    signal_report = load_json(args.signal_report)
    late_rank_report = load_json(args.late_rank_report)
    runs = runs_by_pool(signal_report)
    if args.control_pool not in runs:
        raise ValueError(f"missing control pool {args.control_pool}")
    if args.candidate_pool not in runs:
        raise ValueError(f"missing candidate pool {args.candidate_pool}")

    control = runs[args.control_pool]
    candidate = runs[args.candidate_pool]
    cases = build_cases(control, candidate)
    subset_sets = late_rank_sets(late_rank_report)
    triggers = trigger_definitions(cases)
    evaluations = [
        evaluate_trigger(cases, trigger, control, subset_sets)
        for trigger in triggers
    ]
    evaluations.sort(
        key=lambda item: (
            item["deltas_vs_control"]["recall_at_10"],
            item["deltas_vs_control"]["mrr_at_10"],
            -item["triggered_count"],
        ),
        reverse=True,
    )

    report = {
        "schema_version": "king-synapse.ranking-pool-signal-trigger-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_pool_signal_trigger_audit.py",
        "inputs": {
            "signal_report": {
                "path": report_path(args.signal_report),
                "sha256": sha256_file(args.signal_report),
            },
            "late_rank_report": {
                "path": report_path(args.late_rank_report),
                "sha256": sha256_file(args.late_rank_report),
            },
        },
        "dataset": "DMR candidate MSC-Self-Instruct, punctuation-normalized 200",
        "control_pool": args.control_pool,
        "candidate_pool": args.candidate_pool,
        "control": compact_run(control),
        "candidate": compact_run(candidate),
        "candidate_transition_counts": dict(sorted(Counter(case["transition"] for case in cases).items())),
        "subset_sizes": {name: len(values) for name, values in sorted(subset_sets.items())},
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "trigger_evaluations": evaluations,
        "limits": [
            "Uses sanitized per-query ranks, metrics, and score summaries only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Simulates conditional use of the candidate reranker pool; it does not change retrieval or ranking behavior.",
            "Projected latency uses per-query wall-clock latency from existing reports and is an estimate, not a fresh conditional runtime.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(args.output),
                "control_pool": args.control_pool,
                "candidate_pool": args.candidate_pool,
                "top_triggers": [
                    {
                        "id": item["id"],
                        "triggered_count": item["triggered_count"],
                        "deltas_vs_control": item["deltas_vs_control"],
                        "triggered_transition_counts": item["triggered_transition_counts"],
                    }
                    for item in evaluations[:5]
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
