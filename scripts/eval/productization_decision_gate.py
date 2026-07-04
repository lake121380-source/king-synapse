#!/usr/bin/env python
"""Summarize the current Phase 6 productization decision gate.

This gate reads committed aggregate evidence only. It answers whether the
project can start product work now, and it keeps validation success separate
from release, demo, API, Docker, or v0.1 readiness.
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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Summarize productization readiness from committed Phase 6 evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/productization-decision-gate.json",
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
        "requirements_audit": root
        / "crates/eval/reports/phase6-requirements-audit.json",
        "objective_coverage": root
        / "crates/eval/reports/phase6-objective-coverage-audit.json",
        "next_gate_readiness": root
        / "crates/eval/reports/phase6-next-gate-readiness.json",
        "official_dmr_task_gate": root
        / "crates/eval/reports/official-dmr-task-gate.json",
        "ranking_task_gate": root / "crates/eval/reports/ranking-task-gate.json",
        "external_comparison_task_gate": root
        / "crates/eval/reports/external-comparison-task-gate.json",
        "long_horizon_task_gate": root
        / "crates/eval/reports/long-horizon-task-gate.json",
        "performance_profile": root
        / "crates/eval/reports/phase6-performance-profile.json",
        "system_validation_report": root / "docs/eval/SYSTEM_VALIDATION_REPORT.md",
        "experiment_log": root / "docs/eval/EXPERIMENT_LOG.md",
        "demo_doc": root / "docs/DEMO.md",
    }


def phase_status(report: dict[str, Any], phase_name: str) -> str | None:
    for item in report.get("phase_status", []):
        if item.get("phase") == phase_name:
            return item.get("status")
    return None


def raw_policy_clean(reports: dict[str, dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {}
    dirty = False
    for name, report in reports.items():
        flags = {flag: bool(report.get(flag)) for flag in RAW_FLAGS if flag in report}
        if any(flags.values()):
            dirty = True
        details[name] = flags
    return not dirty, details


def criterion(
    criterion_id: str,
    status: str,
    *,
    question: str,
    evidence: list[Path],
    conclusion: str,
    remaining: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "question": question,
        "status": status,
        "evidence": [report_path(path) for path in evidence],
        "conclusion": conclusion,
        "remaining": remaining or [],
    }


def perf_summary(profile: dict[str, Any]) -> dict[str, Any]:
    long_memory = profile.get("long_memory", [])
    reranker_modes = [
        item
        for item in long_memory
        if item.get("mode") == "vectors-rerank"
        and isinstance(item.get("p50_latency_ms"), (int, float))
    ]
    branch_delta = profile.get("branch_delta", [])
    return {
        "measurement_coverage": profile.get("measurement_coverage", {}),
        "reranker_p50_latency_ms": [
            {
                "dataset": item.get("dataset"),
                "p50_latency_ms": item.get("p50_latency_ms"),
                "p95_latency_ms": item.get("p95_latency_ms"),
            }
            for item in reranker_modes
        ],
        "branch_delta": [
            {
                "dataset": item.get("dataset"),
                "reranker_p50_delta_ms": item.get("reranker_p50_delta_ms"),
                "reranker_total_delta_ms": item.get("reranker_total_delta_ms"),
            }
            for item in branch_delta
        ],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    paths = input_paths(root)
    json_paths = {
        name: path
        for name, path in paths.items()
        if path.suffix.lower() == ".json" and path.exists()
    }
    reports = {name: load_json(path) for name, path in json_paths.items()}
    raw_clean, raw_details = raw_policy_clean(reports)

    requirements = reports["requirements_audit"]
    objective = reports["objective_coverage"]
    readiness = reports["next_gate_readiness"]
    official = reports["official_dmr_task_gate"]
    ranking = reports["ranking_task_gate"]
    external = reports["external_comparison_task_gate"]
    long_horizon = reports["long_horizon_task_gate"]
    performance = reports["performance_profile"]

    feature_freeze_active = (
        phase_status(requirements, "1_lock_current_version") == "active_policy"
    )
    requirements_productization_blocked = (
        phase_status(requirements, "6_productization_decision") == "not_ready"
    )
    objective_validation_only = (
        safe_get(objective, ["read", "overall"])
        == "phase6_validation_in_progress_productization_blocked"
    )
    official_local_ready = bool(
        safe_get(official, ["status", "local_official_style_dmr_gate_passed"])
    )
    official_published_ready = bool(
        safe_get(official, ["status", "published_comparable_official_dmr_ready"])
    )
    ranking_gate_ready = bool(
        safe_get(ranking, ["status", "ranking_evidence_gate_passed"])
    )
    ranking_default_ready = bool(
        safe_get(ranking, ["status", "safe_global_ranking_default_ready"])
    )
    external_local_ready = bool(
        safe_get(external, ["status", "local_external_comparison_gate_passed"])
    )
    hosted_external_ready = bool(
        safe_get(external, ["status", "hosted_official_external_ready"])
    )
    long_horizon_ready = bool(
        safe_get(long_horizon, ["status", "long_horizon_gate_passed"])
    )
    public_long_memory_ready = bool(
        safe_get(long_horizon, ["status", "public_real_world_long_memory_ready"])
    )
    next_gate_ready = bool(safe_get(readiness, ["read", "next_gate_ready"]))
    demo_doc_exists = paths["demo_doc"].exists()
    performance_measured = bool(performance.get("measurement_coverage"))
    latency_threshold_adopted = not any(
        "latency_acceptance_threshold_not_adopted" == gate
        for gate in safe_get(ranking, ["status", "open_gates"], [])
    )

    criteria = [
        criterion(
            "clear_supported_task_boundaries",
            "partial" if external_local_ready and official_local_ready else "failed",
            question="Synapse 在什么任务上明确强？",
            evidence=[
                paths["external_comparison_task_gate"],
                paths["official_dmr_task_gate"],
                paths["long_horizon_task_gate"],
            ],
            conclusion=(
                "The supported strength is clear but scoped: local cognitive-trace introspection and deterministic long-horizon fixture stability. Official DMR remains local and not published-comparable."
                if external_local_ready and official_local_ready
                else "The supported task boundary is not clear enough from current gates."
            ),
            remaining=[
                "Do not generalize local cognitive-trace strength into broad long-memory superiority.",
                "Keep DMR claims local until published-comparable policy and scoring are ready.",
            ],
        ),
        criterion(
            "weaknesses_vs_competitors_known",
            "blocked_external" if not hosted_external_ready else "satisfied",
            question="在什么任务上不如 Mem0 / Graphiti / Zep？",
            evidence=[paths["external_comparison_task_gate"]],
            conclusion=(
                "Hosted/official Graphiti/Zep, Mem0, and Letta are not configured, so competitor weaknesses and advantages cannot be fully measured yet."
                if not hosted_external_ready
                else "Hosted/official competitor comparison is complete enough to state relative weaknesses."
            ),
            remaining=[] if hosted_external_ready else [
                "Configure hosted Graphiti/Zep Neo4j/OpenAI.",
                "Configure official Mem0 embedding/recommended config.",
                "Configure a live or local Letta endpoint.",
            ],
        ),
        criterion(
            "unique_trace_capabilities_supported",
            "satisfied" if external_local_ready else "failed",
            question="哪些能力是别人没有的？",
            evidence=[paths["external_comparison_task_gate"]],
            conclusion=(
                "Local fixture evidence supports Synapse's inspectable dominant trace, suppressed alternatives, future continuation, and reinforcement isolation surfaces."
                if external_local_ready
                else "Unique trace capabilities are not supported by the external comparison gate."
            ),
        ),
        criterion(
            "gpu_cost_acceptance_ready",
            "not_ready" if performance_measured and not latency_threshold_adopted else "failed",
            question="GPU 成本是否能接受？",
            evidence=[paths["performance_profile"], paths["ranking_task_gate"]],
            conclusion=(
                "GPU and latency costs are measured, but no product acceptance threshold is adopted; reranking remains a cost boundary."
                if performance_measured and not latency_threshold_adopted
                else "GPU cost evidence is missing or a product threshold needs separate review."
            ),
            remaining=[
                "Adopt an explicit latency/GPU acceptance threshold before product claims.",
                "Do not ship a ranking policy while latency acceptance is unresolved.",
            ],
        ),
        criterion(
            "official_dmr_supports_readme_claims",
            "not_ready" if official_local_ready and not official_published_ready else "failed",
            question="DMR 官方结果是否能支撑 README 的说法？",
            evidence=[paths["official_dmr_task_gate"]],
            conclusion=(
                "README can describe local official-style evidence, but published-comparable official DMR is not ready."
                if official_local_ready and not official_published_ready
                else "Official DMR evidence does not match the expected local-ready / published-not-ready boundary."
            ),
            remaining=[
                "Finalize published-comparable mapping and scoring policy.",
                "Improve answer synthesis quality before stronger public claims.",
            ],
        ),
        criterion(
            "stable_public_demo_ready",
            "partial" if demo_doc_exists else "failed",
            question="是否有稳定 demo 可以让别人一眼看懂？",
            evidence=[paths["demo_doc"], paths["system_validation_report"]],
            conclusion=(
                "A disposable CLI demo exists, but product demo criteria for web/API/Docker/v0.1 are not open yet."
                if demo_doc_exists
                else "No demo document is available."
            ),
            remaining=[
                "Keep demo work documentation-only until productization opens.",
                "Do not start Web demo, API server, Docker, or v0.1 packaging from current evidence.",
            ],
        ),
        criterion(
            "runtime_defaults_ready",
            "not_ready" if ranking_gate_ready and not ranking_default_ready else "failed",
            question="是否可以改变运行时默认策略？",
            evidence=[paths["ranking_task_gate"]],
            conclusion=(
                "Ranking is a validated bottleneck, but no safe global runtime ranking default is ready."
                if ranking_gate_ready and not ranking_default_ready
                else "Ranking gate does not match the expected no-default state."
            ),
            remaining=[
                "Find a cross-dataset safe ordering signal or explicitly split DMR and LongMemEval objectives.",
                "Keep memory schema, cognitive layers, CLI, and runtime ranking defaults frozen.",
            ],
        ),
        criterion(
            "public_long_memory_ready",
            "not_ready" if long_horizon_ready and not public_long_memory_ready else "failed",
            question="长期记忆是否能作为公开产品主张？",
            evidence=[paths["long_horizon_task_gate"]],
            conclusion=(
                "Deterministic long-horizon fixture is stable, but public real-world long-memory evidence is not ready."
                if long_horizon_ready and not public_long_memory_ready
                else "Long-horizon gate does not match the expected deterministic-ready / public-not-ready state."
            ),
            remaining=[
                "Close future evidence labeling boundary.",
                "Add broader public long-memory validation before product claims.",
            ],
        ),
        criterion(
            "feature_freeze_and_no_product_work",
            "satisfied"
            if feature_freeze_active
            and requirements_productization_blocked
            and objective_validation_only
            else "failed",
            question="现在是否应该继续冻结功能？",
            evidence=[paths["requirements_audit"], paths["objective_coverage"]],
            conclusion=(
                "Feature freeze remains active and Phase 6 is still validation-only with productization blocked."
                if feature_freeze_active
                and requirements_productization_blocked
                and objective_validation_only
                else "Feature freeze or productization block is not recorded consistently."
            ),
        ),
        criterion(
            "raw_or_generated_data_not_committed",
            "satisfied" if raw_clean else "failed",
            question="产品化决策证据链是否保持干净？",
            evidence=[path for name, path in paths.items() if name in json_paths],
            conclusion=(
                "Audited reports do not record committed raw records, prompts, responses, answers, dialogs, memory content, or generated answers."
                if raw_clean
                else "At least one audited report records committed raw or generated data."
            ),
        ),
    ]

    hard_failures = [item["id"] for item in criteria if item["status"] == "failed"]
    blocking_criteria = [
        item["id"]
        for item in criteria
        if item["status"] in {"blocked_external", "not_ready", "partial"}
    ]
    productization_ready = (
        not hard_failures
        and not blocking_criteria
        and next_gate_ready
        and hosted_external_ready
        and official_published_ready
        and ranking_default_ready
        and public_long_memory_ready
        and latency_threshold_adopted
    )
    decision_gate_passed = not hard_failures and not productization_ready

    input_metadata = {
        name: {
            "path": report_path(path),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for name, path in paths.items()
    }
    status_counts: dict[str, int] = {}
    for entry in criteria:
        status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1

    return {
        "schema_version": "king-synapse.productization-decision-gate.v1",
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
        "productization_questions": criteria,
        "status_counts": status_counts,
        "performance_summary": perf_summary(performance),
        "status": {
            "productization_decision_gate_passed": decision_gate_passed,
            "current_decision": "no_go_validation_only",
            "productization_ready": productization_ready,
            "productization_allowed": False,
            "release_v0_1_allowed": False,
            "web_demo_allowed": False,
            "api_server_allowed": False,
            "docker_allowed": False,
            "runtime_default_change_allowed": False,
            "heavy_next_gate_ready": next_gate_ready,
            "hard_failures": hard_failures,
            "blocking_criteria": blocking_criteria,
            "open_gates": [
                "published_comparable_official_dmr_not_ready",
                "hosted_external_comparison_not_configured",
                "safe_runtime_ranking_default_not_ready",
                "future_evidence_labeling_boundary",
                "public_real_world_long_memory_not_validated",
                "gpu_latency_acceptance_threshold_not_adopted",
                "stable_public_demo_not_productized",
            ],
        },
        "read": {
            "current_conclusion": (
                "Productization is a no-go. Synapse has validated local cognitive-trace and deterministic long-horizon strengths, "
                "but official DMR, hosted external comparison, safe runtime defaults, public long-memory evidence, GPU cost acceptance, and public demo readiness are not closed."
            ),
            "what_is_ready": [
                "Local cognitive-trace advantage is supported on the shared fixture.",
                "Pinned extractive official-style DMR is locally executable and judge-backed.",
                "DMR 50/200/500-request top-context judge scaling is complete.",
                "Ranking bottlenecks are validated without adopting a runtime default.",
                "Deterministic long-horizon fixture stability is gate-backed.",
                "A disposable CLI demo exists for local explanation.",
            ],
            "what_blocks_productization": [
                "Published-comparable official DMR is not ready.",
                "DMR answer quality and mapping coverage are not ready for product claims.",
                "Hosted Graphiti/Zep, official Mem0, and Letta comparison are not configured.",
                "No safe global runtime ranking default exists.",
                "Public real-world long-memory stability is not validated.",
                "GPU/latency acceptance threshold is not adopted.",
                "Web demo, API server, Docker, and v0.1 packaging should not start yet.",
            ],
            "next_action": (
                "Keep feature freeze and validation-only mode. The next true hosted gate requires competitor credentials/endpoints; no-model failure analysis may continue."
            ),
        },
        "limits": [
            "This gate reads committed aggregate evidence and docs only.",
            "It does not run benchmarks, hosted adapters, LLM judges, product code, or external services.",
            "It does not inspect raw questions, answers, dialogs, memory content, generated answers, prompts, responses, or API keys.",
            "A passing productization decision gate means the no-go decision is evidence-backed; it is not product readiness.",
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
                "productization_decision_gate_passed": report["status"][
                    "productization_decision_gate_passed"
                ],
                "current_decision": report["status"]["current_decision"],
                "productization_ready": report["status"]["productization_ready"],
                "productization_allowed": report["status"]["productization_allowed"],
                "blocking_criteria": report["status"]["blocking_criteria"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
