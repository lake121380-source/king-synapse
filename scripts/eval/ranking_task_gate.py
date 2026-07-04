#!/usr/bin/env python
"""Summarize the current Phase 3 ranking task gate.

This gate reads committed sanitized aggregate ranking reports only. It verifies
that ranking is a measured bottleneck while keeping runtime ranking defaults
frozen until a safe cross-dataset policy exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RAW_FLAGS = [
    "raw_records_committed",
    "raw_questions_committed",
    "raw_answers_committed",
    "raw_dialogs_committed",
    "raw_memory_content_committed",
    "generated_answers_committed",
]

REQUIRED_OBJECTIVE_VIEWS = {
    "rrf_k_50",
    "vector_weight_50",
    "reranker_pool_50",
    "reranker_pool_50_vs_100_signal",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Summarize ranking gate readiness from committed Phase 3 evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-task-gate.json",
    )
    return parser.parse_args()


def normalize_path_arg(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


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


def safe_get(data: dict[str, Any], path: list[Any], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int) and key < len(current):
            current = current[key]
        else:
            return default
    return current


def input_paths(root: Path) -> dict[str, Path]:
    return {
        "objective_conflict": root
        / "crates/eval/reports/ranking-objective-conflict-audit.json",
        "pool_signal_guard": root
        / "crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json",
        "objective_split_decision": root
        / "crates/eval/reports/ranking-objective-split-decision.json",
        "failure_dmr_50": root / "crates/eval/reports/ranking-failure-audit-dmr-50.json",
        "failure_dmr_200": root
        / "crates/eval/reports/ranking-failure-audit-dmr-200.json",
        "transition_dmr_50": root
        / "crates/eval/reports/ranking-transition-audit-dmr-50.json",
        "transition_dmr_200": root
        / "crates/eval/reports/ranking-transition-audit-dmr-200.json",
        "reranker_pool_transition_dmr_200": root
        / "crates/eval/reports/ranking-reranker-pool-transition-audit-dmr-200.json",
        "vector_weight_transition": root
        / "crates/eval/reports/ranking-vector-weight-transition-audit-dmr-longmem-50.json",
        "late_rank_audit": root
        / "crates/eval/reports/ranking-late-rank-audit-dmr-50-200.json",
    }


def raw_policy_clean(reports: dict[str, dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {}
    dirty = False
    for name, report in reports.items():
        flags = {flag: bool(report.get(flag)) for flag in RAW_FLAGS if flag in report}
        if any(flags.values()):
            dirty = True
        details[name] = flags
    return not dirty, details


def metric_delta(candidate: dict[str, Any], control: dict[str, Any], key: str) -> Any:
    cand = candidate.get(key)
    ctrl = control.get(key)
    if isinstance(cand, (int, float)) and isinstance(ctrl, (int, float)):
        return cand - ctrl
    return None


def compact_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    control = dataset.get("control", {})
    candidate = dataset.get("candidate", {})
    return {
        "dataset_key": dataset.get("dataset_key"),
        "dataset_id": dataset.get("id"),
        "sample_size": dataset.get("sample_size"),
        "control_variant": control.get("variant_id"),
        "candidate_variant": candidate.get("variant_id"),
        "recall_at_10_delta": metric_delta(candidate, control, "recall_at_10"),
        "mrr_at_10_delta": metric_delta(candidate, control, "mrr_at_10"),
        "top1_delta": metric_delta(
            candidate.get("rank_bucket_counts", {}),
            control.get("rank_bucket_counts", {}),
            "top_1",
        ),
        "retrieval_miss_delta": metric_delta(
            candidate.get("failure_type_counts", {}),
            control.get("failure_type_counts", {}),
            "retrieval_miss",
        ),
        "p50_latency_ms_delta": metric_delta(candidate, control, "p50_latency_ms"),
        "candidate_transition_counts": dataset.get("candidate_transition_counts", {}),
    }


def compact_view(view: dict[str, Any]) -> dict[str, Any]:
    dmr = view.get("dmr", {})
    longmem = view.get("longmem", {})
    return {
        "id": view.get("id"),
        "parameter": view.get("parameter"),
        "control_value": view.get("control_value"),
        "source_reports": view.get("source_reports", []),
        "dmr_best_by_recall": safe_get(dmr, ["best_by_recall_at_10", "value"]),
        "dmr_best_by_mrr": safe_get(dmr, ["best_by_mrr_at_10", "value"]),
        "longmem_best_by_recall": safe_get(longmem, ["best_by_recall_at_10", "value"]),
        "longmem_best_by_mrr": safe_get(longmem, ["best_by_mrr_at_10", "value"]),
    }


def item(
    item_id: str,
    status: str,
    *,
    evidence: list[Path],
    conclusion: str,
    remaining: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "status": status,
        "evidence": [report_path(path) for path in evidence],
        "conclusion": conclusion,
        "remaining": remaining or [],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    paths = input_paths(root)
    reports = {name: load_json(path) for name, path in paths.items()}
    raw_clean, raw_details = raw_policy_clean(reports)

    conflict = reports["objective_conflict"]
    guard = reports["pool_signal_guard"]
    split_decision = reports["objective_split_decision"]
    failure_50 = reports["failure_dmr_50"]
    failure_200 = reports["failure_dmr_200"]
    transition_50 = reports["transition_dmr_50"]
    transition_200 = reports["transition_dmr_200"]

    view_ids = {view.get("id") for view in conflict.get("views", [])}
    objective_views_covered = REQUIRED_OBJECTIVE_VIEWS.issubset(view_ids)
    conflict_read = conflict.get("read", {})
    guard_read = guard.get("read", {})
    guard_summaries = guard.get("guard_summaries", [])
    safe_guard_ids = guard_read.get("safe_guard_ids", [])
    objective_split_decided = bool(
        safe_get(split_decision, ["status", "dmr_longmem_objective_split_decided"])
    )
    guard_passes = [
        guard_item.get("id")
        for guard_item in guard_summaries
        if guard_item.get("passes_screening_gate")
    ]
    no_safe_guard = (
        guard_read.get("best_safe_guard_id") is None
        and not safe_guard_ids
        and not guard_passes
    )
    global_default_candidate = conflict_read.get("global_default_candidate")
    no_global_default = global_default_candidate is None
    longmem_violations = sorted(
        {
            dataset
            for guard_item in guard_summaries
            for dataset in guard_item.get("negative_recall_datasets", [])
            + guard_item.get("suppression_datasets", [])
            if str(dataset).startswith("longmem")
        }
    )
    longmem_protection_active = no_safe_guard and bool(longmem_violations)

    required_failure_buckets = {
        "top10_not_top1",
        "top1_hit",
        "top50_only_late_rank",
        "top50_retrieval_miss",
    }
    failure_buckets_present = all(
        required_failure_buckets.issubset(
            set(safe_get(report, ["audit", "bucket_counts"], {}).keys())
        )
        for report in [failure_50, failure_200]
    )
    effects_classified = all(
        safe_get(report, ["audit", "baseline_to_vector_effect_counts"], {})
        and safe_get(report, ["audit", "vector_to_reranker_effect_counts"], {})
        for report in [transition_50, transition_200]
    )
    latency_not_adopted = any(
        "no runtime latency threshold is adopted" in limit
        for limit in guard.get("limits", [])
    )

    checks = [
        item(
            "one_variable_ablation_views_registered",
            "satisfied" if objective_views_covered else "failed",
            evidence=[paths["objective_conflict"]],
            conclusion=(
                "One-variable ranking views are registered for RRF k, vector weight, reranker pool, and pool-signal checks."
                if objective_views_covered
                else "One or more required one-variable ranking views are missing."
            ),
        ),
        item(
            "dmr_failure_buckets_registered",
            "satisfied" if failure_buckets_present else "failed",
            evidence=[paths["failure_dmr_50"], paths["failure_dmr_200"]],
            conclusion=(
                "DMR 50 and DMR 200 classify top-1 hits, top-10-not-top-1 cases, late top-50 ranks, and top-50 retrieval misses."
                if failure_buckets_present
                else "DMR failure buckets are missing or incomplete."
            ),
        ),
        item(
            "vector_and_reranker_effects_classified",
            "satisfied" if effects_classified else "failed",
            evidence=[paths["transition_dmr_50"], paths["transition_dmr_200"]],
            conclusion=(
                "Vector and reranker transition effects are classified for DMR 50 and DMR 200."
                if effects_classified
                else "Vector/reranker transition effects are missing for DMR 50 or DMR 200."
            ),
        ),
        item(
            "objective_conflicts_block_global_default",
            "satisfied" if no_global_default else "failed",
            evidence=[paths["objective_conflict"]],
            conclusion=(
                "Objective conflict audit supports no global ranking default."
                if no_global_default
                else "Objective conflict audit reports a global default candidate."
            ),
        ),
        item(
            "pool_signal_guard_blocks_runtime_default",
            "satisfied" if no_safe_guard else "failed",
            evidence=[paths["pool_signal_guard"]],
            conclusion=(
                "Pool-signal guard audit has no safe guard ready for implementation."
                if no_safe_guard
                else "Pool-signal guard audit reports at least one safe guard."
            ),
        ),
        item(
            "longmem_regression_protection_active",
            "satisfied" if longmem_protection_active else "failed",
            evidence=[paths["pool_signal_guard"]],
            conclusion=(
                "LongMemEval regressions or suppressions are detected and block runtime adoption."
                if longmem_protection_active
                else "No LongMemEval regression signal is available to justify blocking runtime adoption."
            ),
        ),
        item(
            "dmr_longmem_objective_split_decided",
            "satisfied" if objective_split_decided else "failed",
            evidence=[paths["objective_split_decision"]],
            conclusion=(
                "DMR / LongMemEval objective split is explicitly decided as validation-only."
                if objective_split_decided
                else "DMR / LongMemEval objective split is not decided."
            ),
        ),
        item(
            "latency_threshold_not_adopted",
            "satisfied" if latency_not_adopted else "failed",
            evidence=[paths["pool_signal_guard"]],
            conclusion=(
                "Quality screening and latency budget remain separate; no runtime latency threshold is adopted."
                if latency_not_adopted
                else "The guard report does not explicitly preserve the latency-threshold boundary."
            ),
        ),
        item(
            "raw_or_generated_data_not_committed",
            "satisfied" if raw_clean else "failed",
            evidence=list(paths.values()),
            conclusion=(
                "Audited ranking reports do not record committed raw records, prompts, answers, dialogs, memory content, or generated answers."
                if raw_clean
                else "At least one audited ranking report records committed raw or generated data."
            ),
        ),
    ]

    hard_failures = [entry["id"] for entry in checks if entry["status"] == "failed"]
    ranking_evidence_gate_passed = not hard_failures
    status_counts: dict[str, int] = {}
    for entry in checks:
        status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1

    input_metadata = {
        name: {
            "path": report_path(path),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for name, path in paths.items()
    }

    failure_bucket_summary = {
        "dmr_50": safe_get(failure_50, ["audit", "bucket_counts"], {}),
        "dmr_200": safe_get(failure_200, ["audit", "bucket_counts"], {}),
    }
    transition_summary = {
        "dmr_50": {
            "baseline_to_vector": safe_get(
                transition_50, ["audit", "baseline_to_vector_effect_counts"], {}
            ),
            "vector_to_reranker": safe_get(
                transition_50, ["audit", "vector_to_reranker_effect_counts"], {}
            ),
        },
        "dmr_200": {
            "baseline_to_vector": safe_get(
                transition_200, ["audit", "baseline_to_vector_effect_counts"], {}
            ),
            "vector_to_reranker": safe_get(
                transition_200, ["audit", "vector_to_reranker_effect_counts"], {}
            ),
        },
    }

    return {
        "schema_version": "king-synapse.ranking-task-gate.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "git": {
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git_value("rev-parse", "HEAD"),
            "origin_main_delta": git_value(
                "rev-list", "--left-right", "--count", "origin/main...HEAD"
            ),
        },
        "inputs": input_metadata,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "raw_policy": {"clean": raw_clean, "details": raw_details},
        "one_variable_views": [compact_view(view) for view in conflict.get("views", [])],
        "objective_read": conflict_read,
        "failure_bucket_summary": failure_bucket_summary,
        "transition_summary": transition_summary,
        "guard_screening": {
            "guard_count": len(guard_summaries),
            "best_safe_guard_id": guard_read.get("best_safe_guard_id"),
            "safe_guard_ids": safe_guard_ids,
            "guard_passes": guard_passes,
            "longmem_blocking_datasets": longmem_violations,
            "dataset_views": [compact_dataset(dataset) for dataset in guard.get("datasets", [])],
        },
        "checks": checks,
        "status_counts": status_counts,
        "status": {
            "ranking_evidence_gate_passed": ranking_evidence_gate_passed,
            "ranking_validated_bottleneck": ranking_evidence_gate_passed,
            "safe_global_ranking_default_ready": False,
            "runtime_ranking_change_allowed": False,
            "hard_failures": hard_failures,
            "open_gates": [
                "no_safe_global_ranking_default",
                "objective_specific_ranking_policy_not_validated",
                "new_answer_free_ordering_signal_needed_for_global_default",
                "latency_acceptance_threshold_not_adopted",
            ],
        },
        "read": {
            "current_conclusion": (
                "Ranking is a validated bottleneck, but current one-variable evidence "
                "does not support a global runtime default."
            ),
            "strongest_supported_result": (
                "DMR failure buckets and transition audits show ranking movement, while "
                "objective conflict and guard audits block runtime adoption because gains "
                "trade off against LongMemEval and latency."
            ),
            "weak_surfaces": [
                "RRF k is mostly flat.",
                "Vector weight improves coverage only with MRR/top-1 tradeoffs.",
                "Reranker-pool preferences diverge between DMR and LongMemEval.",
                "Pool-signal guards have no screened safe default.",
                "DMR / LongMemEval objective split is decided as validation-only, not as a runtime default.",
            ],
            "next_action": safe_get(
                split_decision,
                ["read", "next_action"],
                conflict_read.get(
                    "next_ranking_gate",
                    "Use a new answer-free ordering signal or keep objective-specific policies evaluation-only before any runtime adoption.",
                ),
            ),
        },
        "limits": [
            "This gate reads committed sanitized aggregate ranking reports only.",
            "It does not rerun retrieval, ranking, hosted adapters, LLM judges, or product code.",
            "It does not inspect raw questions, answers, dialogs, memory content, generated answers, prompts, responses, or API keys.",
            "A passing ranking evidence gate is a no-default validation decision, not an optimization success claim.",
        ],
    }


def main() -> None:
    args = parse_args()
    output = normalize_path_arg(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": report_path(output),
                "ranking_evidence_gate_passed": report["status"][
                    "ranking_evidence_gate_passed"
                ],
                "safe_global_ranking_default_ready": report["status"][
                    "safe_global_ranking_default_ready"
                ],
                "runtime_ranking_change_allowed": report["status"][
                    "runtime_ranking_change_allowed"
                ],
                "open_gates": report["status"]["open_gates"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
