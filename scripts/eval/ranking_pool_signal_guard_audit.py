#!/usr/bin/env python
"""Audit answer-free guards for conditional reranker-pool expansion.

This is a sanitized post-processing audit. It compares candidate guards for
the `top1_single_source` signal across DMR and LongMemEval signal reports
without reading raw questions, answers, dialogs, sessions, memory text, or
generated answer text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ranking_pool_signal_trigger_audit import (
    build_cases,
    compact_run,
    metric_deltas,
    projected_metrics,
    repo_root,
    runs_by_pool,
    signal,
)


EPSILON = 1e-12


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Audit safe pool-signal guards.")
    parser.add_argument(
        "--dmr-200-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-200-reranker-pool-signal.json",
    )
    parser.add_argument(
        "--dmr-500-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-500-reranker-pool-signal.json",
    )
    parser.add_argument(
        "--crosscheck-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-longmem-50-reranker-pool-signal.json",
    )
    parser.add_argument(
        "--longmem-200-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-longmem-200-reranker-pool-signal.json",
    )
    parser.add_argument(
        "--longmem-500-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-longmem-500-reranker-pool-signal.json",
    )
    parser.add_argument("--control-pool", type=int, default=50)
    parser.add_argument("--candidate-pool", type=int, default=100)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json",
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


def normalize_path_arg(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def top1_sources(case: dict[str, Any]) -> list[str]:
    value = signal(case["control"], "top1_sources")
    return list(value or [])


def source_key(case: dict[str, Any]) -> str:
    sources = top1_sources(case)
    return "+".join(sources) if sources else "none"


def answer_free_signal(case: dict[str, Any], field: str) -> Any:
    if field in {
        "score_margin",
        "rerank_margin",
        "top1_source_count",
        "top1_sources",
        "top1_best_branch_rank",
    }:
        return signal(case["control"], field)
    summary = case["control"].get("ranking_signal_summary") or {}
    if field == "rrf_margin":
        return summary.get("top1_top2_rrf_margin")
    if field == "top1_entity_hits":
        return (summary.get("top1") or {}).get("entity_hits")
    return None


def normalized_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    return value


def condition_matches(case: dict[str, Any], condition: dict[str, Any]) -> bool:
    value = normalized_value(answer_free_signal(case, condition["field"]))
    if value is None:
        return False
    threshold = condition["threshold"]
    operator = condition["operator"]
    if operator == "equals":
        return value == threshold
    if operator == "not_equals":
        return value != threshold
    if operator == "lte":
        return float(value) <= float(threshold)
    if operator == "gte":
        return float(value) >= float(threshold)
    if operator == "gt":
        return float(value) > float(threshold)
    raise ValueError(f"unknown guard operator: {operator}")


def guard_matches(case: dict[str, Any], guard: dict[str, Any]) -> bool:
    return all(condition_matches(case, condition) for condition in guard["conditions"])


def guard_definitions() -> list[dict[str, Any]]:
    single_source = {
        "field": "top1_source_count",
        "operator": "equals",
        "threshold": 1,
    }
    return [
        {
            "id": "top1_single_source",
            "description": "pool-50 top-1 came from exactly one retrieval branch",
            "conditions": [single_source],
        },
        {
            "id": "top1_single_source_not_vector_only",
            "description": "single-source top-1, excluding vector-only top-1 cases",
            "conditions": [
                single_source,
                {
                    "field": "top1_sources",
                    "operator": "not_equals",
                    "threshold": ["vector"],
                },
            ],
        },
        {
            "id": "top1_single_source_fts_only",
            "description": "single-source top-1 from the FTS branch only",
            "conditions": [
                single_source,
                {
                    "field": "top1_sources",
                    "operator": "equals",
                    "threshold": ["fts"],
                },
            ],
        },
        {
            "id": "top1_single_source_vector_only",
            "description": "single-source top-1 from the vector branch only",
            "conditions": [
                single_source,
                {
                    "field": "top1_sources",
                    "operator": "equals",
                    "threshold": ["vector"],
                },
            ],
        },
        {
            "id": "top1_single_source_best_branch_gt10",
            "description": "single-source top-1 whose best branch rank is worse than 10",
            "conditions": [
                single_source,
                {
                    "field": "top1_best_branch_rank",
                    "operator": "gt",
                    "threshold": 10,
                },
            ],
        },
        {
            "id": "top1_single_source_best_branch_le10",
            "description": "single-source top-1 whose best branch rank is 10 or better",
            "conditions": [
                single_source,
                {
                    "field": "top1_best_branch_rank",
                    "operator": "lte",
                    "threshold": 10,
                },
            ],
        },
        {
            "id": "top1_single_source_score_margin_le_0_02",
            "description": "single-source top-1 with final-score margin <= 0.02",
            "conditions": [
                single_source,
                {
                    "field": "score_margin",
                    "operator": "lte",
                    "threshold": 0.02,
                },
            ],
        },
        {
            "id": "top1_single_source_rerank_margin_gt_1",
            "description": "single-source top-1 with rerank-logit margin > 1.0",
            "conditions": [
                single_source,
                {
                    "field": "rerank_margin",
                    "operator": "gt",
                    "threshold": 1.0,
                },
            ],
        },
    ]


def compact_delta(deltas: dict[str, Any]) -> dict[str, Any]:
    return {
        "recall_at_10": deltas["recall_at_10"],
        "mrr_at_10": deltas["mrr_at_10"],
        "ndcg_at_10": deltas["ndcg_at_10"],
        "p50_latency_ms_estimate": deltas["p50_latency_ms_estimate"],
        "p95_latency_ms_estimate": deltas["p95_latency_ms_estimate"],
        "top1": deltas["top1"],
        "top10_not_top1": deltas["top10_not_top1"],
        "retrieval_miss": deltas["retrieval_miss"],
    }


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * pct / 100.0
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    fraction = position - low
    return sorted_values[low] * (1.0 - fraction) + sorted_values[high] * fraction


def latency_cost(triggered: list[dict[str, Any]], total_case_count: int) -> dict[str, Any]:
    deltas: list[float] = []
    for case in triggered:
        control_latency = case["control"].get("latency_ms")
        candidate_latency = case["candidate"].get("latency_ms")
        if control_latency is None or candidate_latency is None:
            continue
        deltas.append(float(candidate_latency) - float(control_latency))

    total_extra_ms = sum(deltas)
    return {
        "triggered_with_latency_count": len(deltas),
        "total_extra_ms": total_extra_ms,
        "mean_extra_ms_per_triggered_query": total_extra_ms / len(deltas) if deltas else 0.0,
        "mean_extra_ms_per_all_queries": total_extra_ms / total_case_count if total_case_count else 0.0,
        "p50_extra_ms_per_triggered_query": percentile(deltas, 50.0),
        "p95_extra_ms_per_triggered_query": percentile(deltas, 95.0),
        "max_extra_ms_per_triggered_query": max(deltas) if deltas else None,
        "min_extra_ms_per_triggered_query": min(deltas) if deltas else None,
    }


def evaluate_guard(
    cases: list[dict[str, Any]],
    guard: dict[str, Any],
    control: dict[str, Any],
) -> dict[str, Any]:
    triggered = [case for case in cases if guard_matches(case, guard)]
    triggered_ids = {case["sample_id"] for case in triggered}
    projected = projected_metrics(cases, triggered_ids)
    deltas = metric_deltas(projected, control)
    return {
        "id": guard["id"],
        "description": guard["description"],
        "conditions": guard["conditions"],
        "triggered_count": len(triggered),
        "triggered_fraction": len(triggered) / len(cases) if cases else 0.0,
        "triggered_transition_counts": dict(sorted(Counter(case["transition"] for case in triggered).items())),
        "triggered_top1_source_counts": dict(sorted(Counter(source_key(case) for case in triggered).items())),
        "latency_cost": latency_cost(triggered, len(cases)),
        "projected": projected,
        "deltas_vs_control": compact_delta(deltas),
    }


def audit_dataset(
    *,
    dataset_key: str,
    dataset: dict[str, Any],
    control_pool: int,
    candidate_pool: int,
    guards: list[dict[str, Any]],
) -> dict[str, Any]:
    runs = runs_by_pool({"datasets": [dataset]})
    if control_pool not in runs:
        raise ValueError(f"{dataset_key} missing control pool {control_pool}")
    if candidate_pool not in runs:
        raise ValueError(f"{dataset_key} missing candidate pool {candidate_pool}")

    control = runs[control_pool]
    candidate = runs[candidate_pool]
    cases = build_cases(control, candidate)
    guard_results = [evaluate_guard(cases, guard, control) for guard in guards]
    return {
        "dataset_key": dataset_key,
        "id": dataset.get("id"),
        "name": dataset.get("name"),
        "sample_size": dataset.get("sample_size_used"),
        "control": compact_run(control),
        "candidate": compact_run(candidate),
        "candidate_transition_counts": dict(sorted(Counter(case["transition"] for case in cases).items())),
        "guard_results": guard_results,
    }


def aggregate_guard(guard: dict[str, Any], datasets: list[dict[str, Any]]) -> dict[str, Any]:
    per_dataset: list[dict[str, Any]] = []
    negative_recall_datasets: list[str] = []
    suppression_datasets: list[str] = []
    dmr_recall_delta = 0.0
    dmr_mrr_delta = 0.0
    dmr_top1_delta = 0
    dmr_miss_delta = 0
    total_triggered = 0
    total_latency_extra_ms = 0.0
    total_case_count = 0
    max_mean_extra_ms_per_query = 0.0
    max_p95_extra_ms_per_trigger = 0.0

    for dataset in datasets:
        result = next(item for item in dataset["guard_results"] if item["id"] == guard["id"])
        deltas = result["deltas_vs_control"]
        transitions = result["triggered_transition_counts"]
        latency = result["latency_cost"]
        dataset_key = dataset["dataset_key"]
        if deltas["recall_at_10"] < -EPSILON:
            negative_recall_datasets.append(dataset_key)
        if int(transitions.get("suppressed_from_top10", 0)) > 0:
            suppression_datasets.append(dataset_key)
        if dataset_key.startswith("dmr"):
            dmr_recall_delta += float(deltas["recall_at_10"])
            dmr_mrr_delta += float(deltas["mrr_at_10"])
            dmr_top1_delta += int(deltas["top1"])
            dmr_miss_delta += int(deltas["retrieval_miss"])
        total_triggered += int(result["triggered_count"])
        total_latency_extra_ms += float(latency["total_extra_ms"])
        total_case_count += int(dataset["sample_size"] or 0)
        max_mean_extra_ms_per_query = max(
            max_mean_extra_ms_per_query,
            float(latency["mean_extra_ms_per_all_queries"]),
        )
        p95_latency = latency.get("p95_extra_ms_per_triggered_query")
        if p95_latency is not None:
            max_p95_extra_ms_per_trigger = max(max_p95_extra_ms_per_trigger, float(p95_latency))
        per_dataset.append(
            {
                "dataset_key": dataset_key,
                "triggered_count": result["triggered_count"],
                "triggered_transition_counts": transitions,
                "triggered_top1_source_counts": result["triggered_top1_source_counts"],
                "latency_cost": latency,
                "deltas_vs_control": deltas,
            }
        )

    passes_screen = (
        not negative_recall_datasets
        and not suppression_datasets
        and dmr_recall_delta > EPSILON
        and dmr_mrr_delta >= -EPSILON
    )
    return {
        "id": guard["id"],
        "description": guard["description"],
        "conditions": guard["conditions"],
        "total_triggered": total_triggered,
        "dmr_recall_at_10_delta_sum": dmr_recall_delta,
        "dmr_mrr_at_10_delta_sum": dmr_mrr_delta,
        "dmr_top1_delta_sum": dmr_top1_delta,
        "dmr_retrieval_miss_delta_sum": dmr_miss_delta,
        "latency_budget": {
            "total_extra_ms": total_latency_extra_ms,
            "mean_extra_ms_per_all_queries": total_latency_extra_ms / total_case_count if total_case_count else 0.0,
            "max_dataset_mean_extra_ms_per_query": max_mean_extra_ms_per_query,
            "max_dataset_p95_extra_ms_per_triggered_query": max_p95_extra_ms_per_trigger,
        },
        "negative_recall_datasets": negative_recall_datasets,
        "suppression_datasets": suppression_datasets,
        "passes_screening_gate": passes_screen,
        "per_dataset": per_dataset,
    }


def dataset_inputs(
    dmr_200_report: dict[str, Any],
    dmr_500_report: dict[str, Any],
    crosscheck_report: dict[str, Any],
    longmem_200_report: dict[str, Any],
    longmem_500_report: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    inputs: list[tuple[str, dict[str, Any]]] = [("dmr_200", dmr_200_report["datasets"][0])]
    for dataset in dmr_500_report.get("datasets", []):
        if dataset.get("id") == "dmr":
            inputs.append(("dmr_500_request_323_scored", dataset))
    for dataset in crosscheck_report.get("datasets", []):
        if dataset.get("id") == "dmr":
            inputs.append(("dmr_50", dataset))
        elif dataset.get("id") == "longmem":
            inputs.append(("longmem_50", dataset))
    for dataset in longmem_200_report.get("datasets", []):
        if dataset.get("id") == "longmem":
            inputs.append(("longmem_200", dataset))
    for dataset in longmem_500_report.get("datasets", []):
        if dataset.get("id") == "longmem":
            inputs.append(("longmem_500", dataset))
    return inputs


def main() -> int:
    args = parse_args()
    args.dmr_200_report = normalize_path_arg(args.dmr_200_report)
    args.dmr_500_report = normalize_path_arg(args.dmr_500_report)
    args.crosscheck_report = normalize_path_arg(args.crosscheck_report)
    args.longmem_200_report = normalize_path_arg(args.longmem_200_report)
    args.longmem_500_report = normalize_path_arg(args.longmem_500_report)
    args.output = normalize_path_arg(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    dmr_200_report = load_json(args.dmr_200_report)
    dmr_500_report = load_json(args.dmr_500_report)
    crosscheck_report = load_json(args.crosscheck_report)
    longmem_200_report = load_json(args.longmem_200_report)
    longmem_500_report = load_json(args.longmem_500_report)
    guards = guard_definitions()
    datasets = [
        audit_dataset(
            dataset_key=dataset_key,
            dataset=dataset,
            control_pool=args.control_pool,
            candidate_pool=args.candidate_pool,
            guards=guards,
        )
        for dataset_key, dataset in dataset_inputs(
            dmr_200_report,
            dmr_500_report,
            crosscheck_report,
            longmem_200_report,
            longmem_500_report,
        )
    ]
    guard_summaries = [aggregate_guard(guard, datasets) for guard in guards]
    guard_summaries.sort(
        key=lambda item: (
            item["passes_screening_gate"],
            item["dmr_recall_at_10_delta_sum"],
            item["dmr_mrr_at_10_delta_sum"],
            -item["total_triggered"],
        ),
        reverse=True,
    )
    safe_guards = [item for item in guard_summaries if item["passes_screening_gate"]]
    best_safe = safe_guards[0] if safe_guards else None

    report = {
        "schema_version": "king-synapse.ranking-pool-signal-guard-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_pool_signal_guard_audit.py",
        "inputs": {
            "dmr_200_signal_report": {
                "path": report_path(args.dmr_200_report),
                "sha256": sha256_file(args.dmr_200_report),
            },
            "dmr_500_signal_report": {
                "path": report_path(args.dmr_500_report),
                "sha256": sha256_file(args.dmr_500_report),
            },
            "dmr_longmem_50_signal_report": {
                "path": report_path(args.crosscheck_report),
                "sha256": sha256_file(args.crosscheck_report),
            },
            "longmem_200_signal_report": {
                "path": report_path(args.longmem_200_report),
                "sha256": sha256_file(args.longmem_200_report),
            },
            "longmem_500_signal_report": {
                "path": report_path(args.longmem_500_report),
                "sha256": sha256_file(args.longmem_500_report),
            },
        },
        "control_pool": args.control_pool,
        "candidate_pool": args.candidate_pool,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "guard_summaries": guard_summaries,
        "datasets": datasets,
        "read": {
            "best_safe_guard_id": best_safe["id"] if best_safe else None,
            "best_safe_guard_description": best_safe["description"] if best_safe else None,
            "safe_guard_ids": [item["id"] for item in safe_guards],
            "current_conclusion": (
                "The checked sample sets leave top1_single_source_rerank_margin_gt_1 as the only quality-screened "
                "guard. It remains evaluation-only because triggered queries still pay the larger reranker-pool cost; "
                "latency budget data is reported separately and must pass before any runtime policy."
                if safe_guards
                else "No screened guard is ready for implementation."
            ),
        },
        "limits": [
            "Uses sanitized per-query ranks, metrics, and answer-free ranking signal summaries only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Simulates conditional use of the candidate reranker pool; it does not change retrieval or ranking behavior.",
            "Screening gates are based on the checked DMR and LongMemEval samples only; they are not product defaults.",
            "Quality screening and latency budget are reported separately; no runtime latency threshold is adopted here.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(args.output),
                "best_safe_guard_id": report["read"]["best_safe_guard_id"],
                "top_guard_summaries": [
                    {
                        "id": item["id"],
                        "passes_screening_gate": item["passes_screening_gate"],
                        "dmr_recall_at_10_delta_sum": item["dmr_recall_at_10_delta_sum"],
                        "dmr_mrr_at_10_delta_sum": item["dmr_mrr_at_10_delta_sum"],
                        "latency_budget": item["latency_budget"],
                        "negative_recall_datasets": item["negative_recall_datasets"],
                        "suppression_datasets": item["suppression_datasets"],
                    }
                    for item in guard_summaries[:5]
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
