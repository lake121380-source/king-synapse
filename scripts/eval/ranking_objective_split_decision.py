#!/usr/bin/env python
"""Decide the DMR / LongMemEval ranking-objective split from sanitized evidence.

This is a no-model Phase 6 audit. It turns the observed cross-dataset ranking
conflict into an explicit validation boundary without changing runtime ranking,
memory schema, cognitive layers, CLI/MCP behavior, or product surfaces.
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
    "prompt_text_recorded",
    "raw_response_committed",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Decide DMR / LongMemEval ranking-objective split."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-objective-split-decision.json",
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
        "trend_alignment": root
        / "crates/eval/reports/longmem-dmr-trend-alignment.json",
        "objective_conflict": root
        / "crates/eval/reports/ranking-objective-conflict-audit.json",
        "pool_signal_guard": root
        / "crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json",
        "dmr_failure_taxonomy": root
        / "crates/eval/reports/dmr-failure-mode-taxonomy.json",
        "dmr_top_context_significance": root
        / "crates/eval/reports/dmr-top-context-significance.json",
        "long_horizon_task_gate": root
        / "crates/eval/reports/long-horizon-task-gate.json",
    }


def input_record(path: Path) -> dict[str, Any]:
    return {
        "path": report_path(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
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


def check(
    check_id: str,
    passed: bool,
    *,
    evidence: list[Path],
    conclusion: str,
    failure: str,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "passed" if passed else "failed",
        "evidence": [report_path(path) for path in evidence],
        "conclusion": conclusion if passed else failure,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    paths = input_paths(root)
    reports = {name: load_json(path) for name, path in paths.items()}
    raw_clean, raw_details = raw_policy_clean(reports)

    trend = reports["trend_alignment"]
    conflict = reports["objective_conflict"]
    guard = reports["pool_signal_guard"]
    failure = reports["dmr_failure_taxonomy"]
    significance = reports["dmr_top_context_significance"]
    long_horizon = reports["long_horizon_task_gate"]

    objective_alignment_counts = safe_get(
        trend, ["ranking_trend_alignment", "objective_alignment_counts"], {}
    )
    conflict_or_tradeoff_count = int(objective_alignment_counts.get("conflict", 0)) + int(
        objective_alignment_counts.get("tradeoff", 0)
    )
    ranking_consistent_for_default = bool(
        safe_get(
            trend,
            ["status", "longmem_dmr_ranking_trend_consistent_enough_for_global_default"],
        )
    )
    trend_audit_passed = bool(
        safe_get(trend, ["status", "trend_alignment_audit_passed"])
    )
    top_context_supported = bool(
        safe_get(trend, ["status", "dmr_top_context_generation_trend_supported"])
        and safe_get(
            significance,
            ["cross_scale_summary", "all_scales_mcnemar_significant_at_0_05"],
        )
    )
    global_default_candidate = safe_get(conflict, ["read", "global_default_candidate"])
    no_global_default = global_default_candidate is None
    no_safe_guard = (
        safe_get(guard, ["read", "best_safe_guard_id"]) is None
        and not safe_get(guard, ["read", "safe_guard_ids"], [])
    )
    longmem_public_ready = bool(
        safe_get(long_horizon, ["status", "public_real_world_long_memory_ready"])
    )

    objective_split_decided = (
        trend_audit_passed
        and not ranking_consistent_for_default
        and conflict_or_tradeoff_count > 0
        and no_global_default
        and no_safe_guard
    )

    dmr_taxonomy = failure.get("mutually_exclusive_outcome_taxonomy", {})
    guard_dataset_summary = safe_get(
        trend, ["ranking_trend_alignment", "guard_dataset_summary"], {}
    )

    checks = [
        check(
            "trend_alignment_audit_available",
            trend_audit_passed,
            evidence=[paths["trend_alignment"]],
            conclusion="LongMemEval / DMR trend-alignment audit is available.",
            failure="LongMemEval / DMR trend-alignment audit is missing or failed.",
        ),
        check(
            "cross_dataset_ranking_conflict_present",
            conflict_or_tradeoff_count > 0 and not ranking_consistent_for_default,
            evidence=[paths["trend_alignment"], paths["objective_conflict"]],
            conclusion="Cross-dataset ranking evidence contains conflicts/tradeoffs and is not consistent enough for a global default.",
            failure="Cross-dataset ranking conflict is not proven.",
        ),
        check(
            "dmr_answer_generation_separate_from_ranking",
            top_context_supported,
            evidence=[paths["trend_alignment"], paths["dmr_top_context_significance"]],
            conclusion="DMR top-context answer generation is supported separately from cross-dataset ranking.",
            failure="DMR generator evidence is not strong enough to separate from ranking.",
        ),
        check(
            "no_global_default_candidate",
            no_global_default,
            evidence=[paths["objective_conflict"]],
            conclusion="Objective-conflict audit reports no global default candidate.",
            failure="Objective-conflict audit reports a global default candidate.",
        ),
        check(
            "no_safe_pool_signal_guard",
            no_safe_guard,
            evidence=[paths["pool_signal_guard"]],
            conclusion="Pool-signal guard audit reports no safe screened guard.",
            failure="Pool-signal guard audit reports a safe screened guard.",
        ),
        check(
            "public_longmem_still_not_ready",
            not longmem_public_ready,
            evidence=[paths["long_horizon_task_gate"]],
            conclusion="Public real-world long-memory evidence remains not ready, so LongMemEval protections cannot be weakened for product claims.",
            failure="Public real-world long-memory evidence appears ready and needs a separate claim review.",
        ),
        check(
            "raw_or_generated_data_not_committed",
            raw_clean,
            evidence=list(paths.values()),
            conclusion="Audited inputs do not record committed raw records, prompts, answers, dialogs, memory content, generated answers, or raw responses.",
            failure="At least one audited input records committed raw or generated data.",
        ),
    ]
    hard_failures = [item["id"] for item in checks if item["status"] == "failed"]

    return {
        "schema_version": "king-synapse.ranking-objective-split-decision.v1",
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
        "raw_policy": {"clean": raw_clean, "details": raw_details},
        "checks": checks,
        "evidence_summary": {
            "objective_alignment_counts": objective_alignment_counts,
            "ranking_consistent_enough_for_global_default": ranking_consistent_for_default,
            "global_default_candidate": global_default_candidate,
            "safe_guard_ids": safe_get(guard, ["read", "safe_guard_ids"], []),
            "guard_dataset_summary": guard_dataset_summary,
            "dmr_failure_taxonomy": dmr_taxonomy,
            "top_context_significance": significance.get("cross_scale_summary", {}),
        },
        "objective_split": {
            "decision": "split_objectives_for_validation_only"
            if objective_split_decided
            else "not_decided",
            "dmr_track": {
                "primary_objective": "Improve answer-bearing context placement and answer synthesis under local official-style DMR.",
                "active_boundaries": [
                    "Mapping coverage under the pinned punctuation policy.",
                    "Retrieval top-10 misses and top-context ranking-boundary cases.",
                    "Answer synthesis quality after a relevant chunk is ranked first.",
                ],
                "must_not_claim": [
                    "Published-comparable official DMR performance.",
                    "Runtime generator or ranking default readiness.",
                ],
            },
            "longmem_track": {
                "primary_objective": "Protect long-memory retrieval stability across expanded LongMemEval views.",
                "active_boundaries": [
                    "Zero tolerated LongMemEval top-10 suppressions before runtime adoption.",
                    "No product claim without public real-world long-memory validation.",
                    "No latency acceptance until an explicit GPU/latency threshold is adopted.",
                ],
                "must_not_claim": [
                    "Global long-memory superiority.",
                    "A safe global ranking default.",
                ],
            },
            "global_default_rule": (
                "A global runtime ranking default remains blocked. Future ranking "
                "work must either introduce a new answer-free ordering signal that "
                "does not suppress LongMemEval top-10 hits, or keep objective-specific "
                "policies evaluation-only until separately validated."
            ),
        },
        "status": {
            "ranking_objective_split_decision_gate_passed": not hard_failures,
            "dmr_longmem_objective_split_decided": objective_split_decided
            and not hard_failures,
            "architecture_failure_supported": False,
            "global_runtime_default_still_blocked": True,
            "runtime_ranking_change_allowed": False,
            "productization_allowed": False,
            "hard_failures": hard_failures,
            "open_gates": [
                "no_safe_global_ranking_default",
                "objective_specific_ranking_policy_not_validated",
                "new_answer_free_ordering_signal_needed_for_global_default",
                "latency_acceptance_threshold_not_adopted",
                "published_comparable_dmr_mapping_policy_not_final",
                "public_real_world_long_memory_not_validated",
                "hosted_external_comparison_not_configured",
            ],
        },
        "read": {
            "current_conclusion": (
                "The LongMemEval / DMR ranking conflict is best treated as an "
                "objective split, not as a core architecture failure. DMR "
                "top-context answer generation is stable, but cross-dataset "
                "ranking evidence does not support a global runtime default."
            ),
            "why_this_is_not_a_design_bug": [
                "The system has stable DMR generator gains across 50, 200, and 500-request / 323-scored views.",
                "The same ranking changes create coverage, MRR, top-1, suppression, and latency tradeoffs across datasets.",
                "The guard audit finds no safe screened policy, so the correct decision is to preserve the feature freeze.",
            ],
            "next_action": (
                "Keep the split as validation-only evidence. Continue hosted external "
                "comparison when credentials/endpoints are configured; otherwise "
                "continue no-model failure analysis or design a new answer-free "
                "ordering signal without changing runtime defaults."
            ),
        },
        "limits": [
            "Reads committed sanitized aggregate reports only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, generated answers, prompts, raw responses, or API keys.",
            "Does not rerun retrieval, ranking, judges, hosted adapters, or product code.",
            "Does not change runtime defaults, memory schema, cognitive layers, CLI/MCP, or product surfaces.",
        ],
    }


def main() -> int:
    args = parse_args()
    output = normalize_path_arg(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": report_path(output),
                "ranking_objective_split_decision_gate_passed": report["status"][
                    "ranking_objective_split_decision_gate_passed"
                ],
                "dmr_longmem_objective_split_decided": report["status"][
                    "dmr_longmem_objective_split_decided"
                ],
                "architecture_failure_supported": report["status"][
                    "architecture_failure_supported"
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
