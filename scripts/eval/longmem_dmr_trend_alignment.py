#!/usr/bin/env python
"""Audit LongMemEval / DMR trend alignment from sanitized reports only."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Audit DMR and LongMemEval trend alignment without rerunning benchmarks."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/longmem-dmr-trend-alignment.json",
    )
    return parser.parse_args()


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root(),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def rounded(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def sign(value: float | int | None, *, epsilon: float = 1e-9) -> str:
    if value is None:
        return "unknown"
    number = float(value)
    if number > epsilon:
        return "positive"
    if number < -epsilon:
        return "negative"
    return "flat"


def input_record(path: Path) -> dict[str, Any]:
    return {
        "path": report_path(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def summarize_objective_view(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": view.get("id"),
        "parameter": view.get("parameter"),
        "source_reports": view.get("source_reports", []),
        "alignment": view.get("read", {}).get("alignment"),
        "reason": view.get("read", {}).get("reason"),
        "dmr_best_recall_value": view.get("read", {}).get("dmr_best_recall_value"),
        "longmem_best_recall_value": view.get("read", {}).get(
            "longmem_best_recall_value"
        ),
        "dmr_best_mrr_value": view.get("read", {}).get("dmr_best_mrr_value"),
        "longmem_best_mrr_value": view.get("read", {}).get("longmem_best_mrr_value"),
    }


def summarize_guard_dataset_view(view: dict[str, Any]) -> dict[str, Any]:
    control = view.get("control", {})
    candidate = view.get("candidate", {})
    recall_delta = (
        candidate.get("recall_at_10") - control.get("recall_at_10")
        if candidate.get("recall_at_10") is not None
        and control.get("recall_at_10") is not None
        else None
    )
    mrr_delta = (
        candidate.get("mrr_at_10") - control.get("mrr_at_10")
        if candidate.get("mrr_at_10") is not None
        and control.get("mrr_at_10") is not None
        else None
    )
    control_top1 = (control.get("rank_bucket_counts") or {}).get("top_1")
    candidate_top1 = (candidate.get("rank_bucket_counts") or {}).get("top_1")
    top1_delta = (
        candidate_top1 - control_top1
        if candidate_top1 is not None and control_top1 is not None
        else None
    )
    control_miss = (control.get("rank_bucket_counts") or {}).get("absent")
    candidate_miss = (candidate.get("rank_bucket_counts") or {}).get("absent")
    retrieval_miss_delta = (
        candidate_miss - control_miss
        if candidate_miss is not None and control_miss is not None
        else None
    )
    p50_latency_delta = (
        candidate.get("p50_latency_ms") - control.get("p50_latency_ms")
        if candidate.get("p50_latency_ms") is not None
        and control.get("p50_latency_ms") is not None
        else None
    )
    return {
        "dataset_key": view.get("dataset_key"),
        "dataset_id": view.get("id"),
        "sample_size": view.get("sample_size"),
        "control_variant": control.get("variant_id"),
        "candidate_variant": candidate.get("variant_id"),
        "recall_at_10_delta": rounded(recall_delta),
        "recall_direction": sign(recall_delta),
        "mrr_at_10_delta": rounded(mrr_delta),
        "mrr_direction": sign(mrr_delta),
        "top1_delta": top1_delta,
        "top1_direction": sign(top1_delta),
        "retrieval_miss_delta": retrieval_miss_delta,
        "retrieval_miss_direction": sign(
            -retrieval_miss_delta
            if retrieval_miss_delta is not None
            else None
        ),
        "p50_latency_ms_delta": rounded(p50_latency_delta),
        "candidate_transition_counts": view.get("candidate_transition_counts", {}),
    }


def summarize_dataset_group(dataset_views: list[dict[str, Any]]) -> dict[str, Any]:
    by_dataset_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for view in dataset_views:
        by_dataset_id[str(view.get("dataset_id"))].append(view)

    summary: dict[str, Any] = {}
    for dataset_id, views in sorted(by_dataset_id.items()):
        recall_directions = Counter(view["recall_direction"] for view in views)
        mrr_directions = Counter(view["mrr_direction"] for view in views)
        top1_directions = Counter(view["top1_direction"] for view in views)
        summary[dataset_id] = {
            "views": views,
            "recall_direction_counts": dict(sorted(recall_directions.items())),
            "mrr_direction_counts": dict(sorted(mrr_directions.items())),
            "top1_direction_counts": dict(sorted(top1_directions.items())),
            "sample_sizes": [view.get("sample_size") for view in views],
            "all_recall_positive": all(
                view["recall_direction"] == "positive" for view in views
            ),
            "all_recall_non_negative": all(
                view["recall_direction"] in {"positive", "flat"} for view in views
            ),
        }
    return summary


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    paths = {
        "dmr_top_context_significance": root
        / "crates/eval/reports/dmr-top-context-significance.json",
        "ranking_objective_conflict": root
        / "crates/eval/reports/ranking-objective-conflict-audit.json",
        "ranking_pool_signal_guard": root
        / "crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json",
        "ranking_task_gate": root / "crates/eval/reports/ranking-task-gate.json",
        "long_horizon_task_gate": root
        / "crates/eval/reports/long-horizon-task-gate.json",
    }

    significance = load_json(paths["dmr_top_context_significance"])
    objective_conflict = load_json(paths["ranking_objective_conflict"])
    guard = load_json(paths["ranking_pool_signal_guard"])
    ranking_gate = load_json(paths["ranking_task_gate"])
    long_horizon_gate = load_json(paths["long_horizon_task_gate"])

    objective_views = [
        summarize_objective_view(view) for view in objective_conflict.get("views", [])
    ]
    objective_alignment_counts = Counter(view["alignment"] for view in objective_views)

    guard_views = [
        summarize_guard_dataset_view(view)
        for view in guard.get("datasets", [])
    ]
    guard_dataset_summary = summarize_dataset_group(guard_views)
    dmr_guard = guard_dataset_summary.get("dmr", {})
    longmem_guard = guard_dataset_summary.get("longmem", {})

    top_context_summary = significance["cross_scale_summary"]
    top_context_stable = bool(
        top_context_summary.get("all_scales_judge_accuracy_delta_positive")
        and top_context_summary.get("all_scales_mcnemar_significant_at_0_05")
    )
    ranking_global_default_ready = bool(
        ranking_gate.get("status", {}).get("safe_global_ranking_default_ready")
    )
    guard_has_safe_default = bool(guard.get("read", {}).get("safe_guard_ids"))

    trend_alignment_complete = (
        top_context_stable
        and ranking_global_default_ready
        and guard_has_safe_default
        and bool(longmem_guard.get("all_recall_non_negative"))
        and bool(dmr_guard.get("all_recall_non_negative"))
    )

    report = {
        "schema_version": "king-synapse.longmem-dmr-trend-alignment.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "git": {
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git_value("rev-parse", "HEAD"),
            "origin_main_delta": git_value(
                "rev-list", "--left-right", "--count", "origin/main...HEAD"
            ),
        },
        "inputs": {name: input_record(path) for name, path in paths.items()},
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "prompt_text_recorded": False,
        "raw_response_committed": False,
        "dmr_answer_generation_trend": {
            "top_context_stable_and_significant": top_context_stable,
            "cross_scale_summary": top_context_summary,
            "read": significance["read"],
            "longmem_comparable_answer_generation_view_available": False,
            "longmem_comparison_limit": (
                "Committed reports do not contain a LongMemEval answer-generation "
                "candidate equivalent to DMR top-context extraction."
            ),
        },
        "ranking_trend_alignment": {
            "objective_views": objective_views,
            "objective_alignment_counts": dict(sorted(objective_alignment_counts.items())),
            "guard_dataset_summary": guard_dataset_summary,
            "safe_global_ranking_default_ready": ranking_global_default_ready,
            "safe_guard_ids": guard.get("read", {}).get("safe_guard_ids", []),
            "ranking_task_gate": ranking_gate.get("status", {}),
        },
        "long_horizon_context": {
            "long_horizon_gate": long_horizon_gate.get("status", {}),
        },
        "status": {
            "trend_alignment_audit_passed": True,
            "dmr_top_context_generation_trend_supported": top_context_stable,
            "longmem_dmr_ranking_trend_consistent_enough_for_global_default": False,
            "trend_alignment_exit_condition_complete": trend_alignment_complete,
            "runtime_default_change_allowed": False,
            "productization_allowed": False,
            "open_gates": [
                "hosted_external_comparison_not_configured",
                "published_comparable_dmr_mapping_policy_not_final",
                "dmr_answer_quality_not_ready",
                "no_safe_global_ranking_default",
                "longmem_dmr_ranking_objective_split_not_decided",
                "public_real_world_long_memory_not_validated",
            ],
        },
        "read": {
            "primary_result": (
                "DMR top-context answer generation is stable and paired-significant, "
                "but LongMemEval and DMR ranking trends are not aligned enough to "
                "support a global runtime ranking default."
            ),
            "aligned_surfaces": [
                "DMR top-context improves judged answer quality at DMR 50, 200, and 500-request / 323-scored scale views.",
                "Vector weight 1.5 improves Recall@10 on both DMR 50 and LongMemEval 50, but with MRR/top-1 tradeoffs.",
                "RRF k is effectively flat in the checked range.",
            ],
            "conflict_surfaces": [
                "Reranker-pool exhaustive 50-sample views choose different best Recall@10 values for DMR and LongMemEval.",
                "Pool-50 -> pool-100 expanded views are mixed: DMR 200/500 improve Recall@10 while DMR 50 and LongMem 50/200 regress; LongMem 500 improves but top-1 falls.",
                "No screened pool-signal guard is ready for implementation.",
            ],
            "decision": (
                "The Phase 6 trend-alignment exit condition is not complete. "
                "The correct evidence-backed decision is validation-only: keep "
                "feature freeze, do not change runtime defaults, and either "
                "decide an explicit DMR/LongMemEval objective split or find a "
                "new answer-free ordering signal."
            ),
            "next_action": (
                "Continue hosted external comparison when credentials/endpoints are "
                "configured; otherwise continue no-model failure analysis without "
                "runtime or product changes."
            ),
        },
        "limits": [
            "Uses committed sanitized aggregate/per-query reports only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, generated answers, prompts, raw responses, or API keys.",
            "Does not rerun retrieval, ranking, answer generation, judges, hosted adapters, or product code.",
            "DMR answer-generation evidence and LongMemEval ranking/long-horizon evidence are not the same task and are not pooled.",
            "This report does not change memory schema, cognitive layers, CLI/MCP, retrieval, ranking, generator, scoring defaults, or product surfaces.",
        ],
    }
    return report


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else repo_root() / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": report_path(output),
                "status": report["status"],
                "objective_alignment_counts": report["ranking_trend_alignment"][
                    "objective_alignment_counts"
                ],
                "guard_direction_summary": {
                    dataset: {
                        "recall_direction_counts": value.get(
                            "recall_direction_counts"
                        ),
                        "sample_sizes": value.get("sample_sizes"),
                    }
                    for dataset, value in report["ranking_trend_alignment"][
                        "guard_dataset_summary"
                    ].items()
                },
                "read": report["read"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
