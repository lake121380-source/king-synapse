#!/usr/bin/env python
"""Summarize the next allowed Phase 6 validation action.

This gate turns the current readiness evidence into a concrete action decision:
which heavy validation branch is allowed next, or why no heavy branch is ready.
It does not run benchmarks, hosted adapters, LLM judges, or product code.
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
    "raw_response_committed",
    "prompt_text_recorded",
    "external_dataset_content_committed",
]

TOP_CONTEXT_DMR_50_COMMAND = [
    "python",
    "scripts/eval/official_dmr_eval.py",
    "--sample-size",
    "50",
    "--mode",
    "vectors-rerank",
    "--generator",
    "top-context-extractive",
    "--llm-judge",
    "deepseek",
    "--judge-model",
    "deepseek-v4-flash",
    "--accelerator",
    "cuda",
    "--cuda-device-id",
    "0",
    "--embed-batch-size",
    "32",
    "--embed-max-length",
    "256",
    "--rerank-batch-size",
    "32",
    "--rerank-max-length",
    "256",
    "--output",
    "crates/eval/reports/official-dmr-50-top-context-judge.json",
    "--cleanup-cache",
]

HOSTED_EXTERNAL_COMMAND = [
    "cargo",
    "run",
    "-p",
    "synapse-eval",
    "--bin",
    "kr-external-eval",
    "--",
    "--graphiti-command",
    "python",
    "--graphiti-arg",
    "scripts/eval/graphiti_adapter.py",
    "--mem0-command",
    "python",
    "--mem0-arg",
    "scripts/eval/mem0_adapter.py",
    "--letta-command",
    "python",
    "--letta-arg",
    "scripts/eval/letta_adapter.py",
    "--json",
    "crates/eval/reports/external-comparison-hosted.json",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Summarize the next allowed Phase 6 validation action."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/next-validation-action-gate.json",
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
        "next_gate_readiness": root
        / "crates/eval/reports/phase6-next-gate-readiness.json",
        "official_dmr_task_gate": root
        / "crates/eval/reports/official-dmr-task-gate.json",
        "external_comparison_task_gate": root
        / "crates/eval/reports/external-comparison-task-gate.json",
        "productization_decision_gate": root
        / "crates/eval/reports/productization-decision-gate.json",
        "ranking_task_gate": root / "crates/eval/reports/ranking-task-gate.json",
        "long_horizon_task_gate": root
        / "crates/eval/reports/long-horizon-task-gate.json",
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


def command_record(command: list[str], *, allowed: bool, reason: str) -> dict[str, Any]:
    return {
        "allowed_now": allowed,
        "reason": reason,
        "command": command,
        "uses_cuda_device_0": "--accelerator" in command
        and "cuda" in command
        and "--cuda-device-id" in command
        and "0" in command,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    paths = input_paths(root)
    reports = {name: load_json(path) for name, path in paths.items()}
    raw_clean, raw_details = raw_policy_clean(reports)

    readiness = reports["next_gate_readiness"]
    official = reports["official_dmr_task_gate"]
    external = reports["external_comparison_task_gate"]
    productization = reports["productization_decision_gate"]
    ranking = reports["ranking_task_gate"]
    long_horizon = reports["long_horizon_task_gate"]

    top_context_ready = bool(safe_get(readiness, ["top_context_judge", "ready"]))
    hosted_ready = bool(safe_get(readiness, ["hosted_external", "ready"]))
    next_gate_ready = bool(safe_get(readiness, ["read", "next_gate_ready"]))
    official_top_context_ready = bool(
        safe_get(official, ["status", "top_context_judge_ready"])
    )
    top_context_dmr_50_allowed = top_context_ready and not official_top_context_ready
    hosted_official_ready = bool(
        safe_get(external, ["status", "hosted_official_external_ready"])
    )
    productization_allowed = bool(
        safe_get(productization, ["status", "productization_allowed"])
    )
    productization_ready = bool(
        safe_get(productization, ["status", "productization_ready"])
    )
    runtime_ranking_change_allowed = bool(
        safe_get(ranking, ["status", "runtime_ranking_change_allowed"])
    )
    public_long_memory_ready = bool(
        safe_get(long_horizon, ["status", "public_real_world_long_memory_ready"])
    )

    judge_blocked_consistent = (
        not top_context_ready
        and not official_top_context_ready
        and safe_get(readiness, ["top_context_judge", "status"])
        == "authorization_error"
        and safe_get(readiness, ["top_context_judge", "http_status"]) == 401
    )
    hosted_blocked_consistent = (
        not hosted_ready
        and not hosted_official_ready
        and safe_get(readiness, ["hosted_external", "last_report_measured_systems"]) == 1
        and safe_get(readiness, ["hosted_external", "last_report_not_configured_systems"])
        == 3
    )
    no_product_or_runtime_change = (
        not productization_allowed
        and not productization_ready
        and not runtime_ranking_change_allowed
        and not public_long_memory_ready
    )
    no_heavy_run_ready = not top_context_dmr_50_allowed and not hosted_ready

    if top_context_dmr_50_allowed:
        recommended_action = "run_top_context_dmr_50_judge_scoring"
        heavy_validation_allowed = True
    elif hosted_ready:
        recommended_action = "run_hosted_external_comparison"
        heavy_validation_allowed = True
    else:
        recommended_action = (
            "wait_for_hosted_external_or_next_dmr_expansion_scope"
            if official_top_context_ready
            else "wait_for_external_preconditions"
        )
        heavy_validation_allowed = False

    checks = [
        item(
            "top_context_judge_precondition",
            "satisfied"
            if official_top_context_ready or top_context_ready
            else "blocked_external"
            if judge_blocked_consistent
            else "failed",
            evidence=[paths["next_gate_readiness"], paths["official_dmr_task_gate"]],
            conclusion=(
                "Top-context DMR 50 judge scoring is complete."
                if official_top_context_ready
                else "Top-context DMR judge scoring is ready."
                if top_context_ready
                else
                "Top-context DMR judge scoring is blocked by the current authorization preflight."
                if judge_blocked_consistent
                else "Top-context DMR judge readiness is inconsistent."
            ),
            remaining=[]
            if official_top_context_ready or top_context_ready
            else [
                "Provide valid judge authorization for deepseek-v4-flash.",
                "Then rerun top-context DMR 50 with CUDA device 0.",
            ],
        ),
        item(
            "hosted_external_precondition",
            "blocked_external" if hosted_blocked_consistent else "satisfied"
            if hosted_ready
            else "failed",
            evidence=[paths["next_gate_readiness"], paths["external_comparison_task_gate"]],
            conclusion=(
                "Hosted/official external comparison is blocked because Graphiti/Zep, official Mem0, and Letta are not configured."
                if hosted_blocked_consistent
                else "Hosted/official external comparison is ready."
                if hosted_ready
                else "Hosted external readiness is inconsistent."
            ),
            remaining=[] if hosted_ready else [
                "Configure Graphiti/Zep Neo4j/OpenAI credentials.",
                "Configure official Mem0 OpenAI/custom config.",
                "Configure a Letta endpoint or local environment.",
            ],
        ),
        item(
            "heavy_validation_action_selected",
            "blocked_external" if no_heavy_run_ready else "satisfied",
            evidence=[paths["next_gate_readiness"]],
            conclusion=(
                "No heavy validation branch is currently selected by this gate."
                if no_heavy_run_ready
                else f"Next heavy validation branch is {recommended_action}."
            ),
            remaining=[] if not no_heavy_run_ready else [
                "Do not rerun DMR 50 after it is complete.",
                "Select the next DMR expansion scope or configure hosted external comparison before another heavy run.",
            ],
        ),
        item(
            "gpu_command_template_preserved",
            "satisfied",
            evidence=[paths["official_dmr_task_gate"], paths["next_gate_readiness"]],
            conclusion="The next DMR heavy-run command template uses --accelerator cuda --cuda-device-id 0.",
        ),
        item(
            "product_and_runtime_scope_frozen",
            "satisfied" if no_product_or_runtime_change else "failed",
            evidence=[
                paths["productization_decision_gate"],
                paths["ranking_task_gate"],
                paths["long_horizon_task_gate"],
            ],
            conclusion=(
                "Productization, runtime ranking changes, and public long-memory claims remain frozen."
                if no_product_or_runtime_change
                else "At least one product/runtime/public-long-memory gate appears open."
            ),
        ),
        item(
            "raw_or_generated_data_not_committed",
            "satisfied" if raw_clean else "failed",
            evidence=list(paths.values()),
            conclusion=(
                "Audited next-action inputs do not record committed raw records, prompts, responses, answers, dialogs, memory content, or generated answers."
                if raw_clean
                else "At least one next-action input records committed raw or generated data."
            ),
        ),
    ]

    hard_failures = [entry["id"] for entry in checks if entry["status"] == "failed"]
    action_gate_passed = not hard_failures and all(
        entry["status"] in {"satisfied", "blocked_external"} for entry in checks
    )
    input_metadata = {
        name: {
            "path": report_path(path),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for name, path in paths.items()
    }
    status_counts: dict[str, int] = {}
    for entry in checks:
        status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1

    return {
        "schema_version": "king-synapse.next-validation-action-gate.v1",
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
        "checks": checks,
        "status_counts": status_counts,
        "commands": {
            "top_context_dmr_50_judge_scoring": command_record(
                TOP_CONTEXT_DMR_50_COMMAND,
                allowed=top_context_dmr_50_allowed,
                reason=(
                    "Judge precondition is ready and DMR 50 top-context is not yet complete."
                    if top_context_dmr_50_allowed
                    else "DMR 50 top-context judge scoring is already complete."
                    if official_top_context_ready
                    else "Blocked until valid judge authorization is available."
                ),
            ),
            "hosted_external_comparison": command_record(
                HOSTED_EXTERNAL_COMMAND,
                allowed=hosted_ready,
                reason=(
                    "Hosted external preconditions are ready."
                    if hosted_ready
                    else "Blocked until hosted competitor credentials/endpoints are configured."
                ),
            ),
        },
        "status": {
            "next_validation_action_gate_passed": action_gate_passed,
            "recommended_action": recommended_action,
            "heavy_validation_allowed": heavy_validation_allowed,
            "top_context_dmr_50_judge_scoring_allowed": top_context_dmr_50_allowed,
            "hosted_external_comparison_allowed": hosted_ready,
            "productization_allowed": False,
            "runtime_default_change_allowed": False,
            "hard_failures": hard_failures,
            "open_preconditions": [
                "valid_top_context_judge_authorization"
            ]
            * (0 if top_context_ready else 1)
            + [
                "hosted_graphiti_zep_official_mem0_letta_configuration"
            ]
            * (0 if hosted_ready else 1),
        },
        "read": {
            "current_conclusion": (
                "DMR 50 top-context judge scoring is complete; no further heavy branch is currently selected by this gate."
                if official_top_context_ready and not heavy_validation_allowed
                else "No heavy next validation run is ready; the correct next action is to keep feature freeze and wait for either valid top-context judge authorization or hosted external comparison credentials/endpoints."
                if not heavy_validation_allowed
                else f"The next heavy validation action is {recommended_action}."
            ),
            "allowed_now": [
                "No-model/no-external evidence maintenance.",
                "Documentation/report synchronization that does not change runtime behavior.",
            ]
            if not heavy_validation_allowed
            else [recommended_action],
            "not_allowed_now": [
                "Heavy DMR judge scoring without valid judge authorization.",
                "Hosted external comparison without competitor credentials/endpoints.",
                "Productization, runtime default changes, Web demo, API server, Docker, or v0.1 packaging.",
            ],
            "next_action": (
                "Wait for valid judge authorization or hosted competitor configuration; then run the corresponding validation command with recorded CUDA policy."
                if not heavy_validation_allowed
                else f"Run {recommended_action} and update official/external reports before any new claim."
            ),
        },
        "limits": [
            "This gate reads committed aggregate evidence only.",
            "It does not run retrieval, ranking, generation, LLM judges, hosted adapters, or product code.",
            "It does not inspect raw benchmark records, prompts, responses, answers, memory content, generated answers, or API keys.",
            "A passing next-validation action gate means the action selection is evidence-backed, not that a heavy validation run has succeeded.",
        ],
    }


def main() -> None:
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
                "next_validation_action_gate_passed": report["status"][
                    "next_validation_action_gate_passed"
                ],
                "recommended_action": report["status"]["recommended_action"],
                "heavy_validation_allowed": report["status"][
                    "heavy_validation_allowed"
                ],
                "open_preconditions": report["status"]["open_preconditions"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
