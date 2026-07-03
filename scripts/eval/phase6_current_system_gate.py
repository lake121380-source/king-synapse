#!/usr/bin/env python
"""Summarize whether the current Phase 6 system can safely continue.

This gate reads committed aggregate reports only. It does not run retrieval,
generation, hosted adapters, LLM judges, product code, or raw benchmark data.
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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_baseline_health_report(root: Path) -> Path:
    reports = sorted(
        (root / "crates/eval/reports").glob("phase6-baseline-health-check-*.json")
    )
    if not reports:
        return root / "crates/eval/reports/phase6-baseline-health-check-2026-07-04.json"
    return reports[-1]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Summarize the current Phase 6 system gate from committed evidence."
    )
    parser.add_argument(
        "--requirements-audit",
        type=Path,
        default=root / "crates/eval/reports/phase6-requirements-audit.json",
    )
    parser.add_argument(
        "--objective-coverage",
        type=Path,
        default=root / "crates/eval/reports/phase6-objective-coverage-audit.json",
    )
    parser.add_argument(
        "--next-gate-readiness",
        type=Path,
        default=root / "crates/eval/reports/phase6-next-gate-readiness.json",
    )
    parser.add_argument(
        "--readme-claims-audit",
        type=Path,
        default=root / "crates/eval/reports/readme-claims-support-audit.json",
    )
    parser.add_argument(
        "--official-dmr-task-gate",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-task-gate.json",
    )
    parser.add_argument(
        "--ranking-task-gate",
        type=Path,
        default=root / "crates/eval/reports/ranking-task-gate.json",
    )
    parser.add_argument(
        "--baseline-health",
        type=Path,
        default=latest_baseline_health_report(root),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/phase6-current-system-gate.json",
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


def phase_status(report: dict[str, Any], phase_name: str) -> str | None:
    for item in report.get("phase_status", []):
        if item.get("phase") == phase_name:
            return item.get("status")
    return None


def check(
    check_id: str,
    passed: bool,
    *,
    evidence: list[Path],
    conclusion: str,
    failure: str,
    severity: str = "required",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "passed" if passed else "failed",
        "severity": severity,
        "evidence": [report_path(path) for path in evidence],
        "conclusion": conclusion if passed else failure,
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


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "requirements_audit": normalize_path_arg(args.requirements_audit),
        "objective_coverage": normalize_path_arg(args.objective_coverage),
        "next_gate_readiness": normalize_path_arg(args.next_gate_readiness),
        "readme_claims_audit": normalize_path_arg(args.readme_claims_audit),
        "official_dmr_task_gate": normalize_path_arg(args.official_dmr_task_gate),
        "ranking_task_gate": normalize_path_arg(args.ranking_task_gate),
        "baseline_health": normalize_path_arg(args.baseline_health),
    }
    reports = {name: load_json(path) for name, path in paths.items()}
    raw_clean, raw_details = raw_policy_clean(reports)

    requirements = reports["requirements_audit"]
    objective = reports["objective_coverage"]
    readiness = reports["next_gate_readiness"]
    readme = reports["readme_claims_audit"]
    official_dmr = reports["official_dmr_task_gate"]
    ranking = reports["ranking_task_gate"]
    baseline = reports["baseline_health"]

    baseline_passed = safe_get(baseline, ["read", "current_baseline_health"]) == "passed"
    feature_freeze_active = (
        phase_status(requirements, "1_lock_current_version") == "active_policy"
    )
    readme_supported = bool(
        safe_get(readme, ["read", "readme_claims_conservative_enough"])
    ) and not readme.get("unsupported_claims")
    productization_blocked = (
        phase_status(requirements, "6_productization_decision") == "not_ready"
    )
    objective_current = (
        safe_get(objective, ["read", "overall"])
        == "phase6_validation_in_progress_productization_blocked"
    )
    no_ranking_default = (
        safe_get(objective, ["key_metrics", "ranking_global_default_candidate"]) is None
        and safe_get(objective, ["key_metrics", "ranking_best_safe_guard_id"]) is None
    )
    official_dmr_local_gate_passed = bool(
        safe_get(official_dmr, ["status", "local_official_style_dmr_gate_passed"])
    )
    published_comparable_dmr_not_ready = not bool(
        safe_get(official_dmr, ["status", "published_comparable_official_dmr_ready"])
    )
    ranking_evidence_gate_passed = bool(
        safe_get(ranking, ["status", "ranking_evidence_gate_passed"])
    )
    safe_ranking_default_not_ready = not bool(
        safe_get(ranking, ["status", "safe_global_ranking_default_ready"])
    )
    next_gate_ready = bool(safe_get(readiness, ["read", "next_gate_ready"]))
    top_context_ready = bool(safe_get(readiness, ["top_context_judge", "ready"]))
    hosted_ready = bool(safe_get(readiness, ["hosted_external", "ready"]))

    checks = [
        check(
            "baseline_health_passed",
            baseline_passed,
            evidence=[paths["baseline_health"]],
            conclusion="Latest local non-external Phase 6 baseline health is passed.",
            failure="Latest local non-external Phase 6 baseline health is not passed.",
        ),
        check(
            "feature_freeze_active",
            feature_freeze_active,
            evidence=[paths["requirements_audit"]],
            conclusion="Feature freeze remains the active Phase 6 policy.",
            failure="Feature freeze is not recorded as the active Phase 6 policy.",
        ),
        check(
            "readme_claims_supported",
            readme_supported,
            evidence=[paths["readme_claims_audit"]],
            conclusion="README public claims remain conservative enough for validation-stage presentation.",
            failure="README contains an unsupported or missing audited claim.",
        ),
        check(
            "official_dmr_local_gate_passed",
            official_dmr_local_gate_passed,
            evidence=[paths["official_dmr_task_gate"]],
            conclusion="Local official-style DMR gate is passed for the pinned extractive baseline.",
            failure="Local official-style DMR gate is not passed.",
        ),
        check(
            "published_comparable_dmr_not_overstated",
            published_comparable_dmr_not_ready,
            evidence=[paths["official_dmr_task_gate"]],
            conclusion="Published-comparable official DMR is still explicitly not ready.",
            failure="Published-comparable official DMR appears ready and needs a separate release decision.",
        ),
        check(
            "ranking_evidence_gate_passed",
            ranking_evidence_gate_passed,
            evidence=[paths["ranking_task_gate"]],
            conclusion="Ranking evidence gate is passed as a no-default validation decision.",
            failure="Ranking evidence gate is not passed.",
        ),
        check(
            "safe_ranking_default_not_overstated",
            safe_ranking_default_not_ready,
            evidence=[paths["ranking_task_gate"]],
            conclusion="Safe global runtime ranking default is still explicitly not ready.",
            failure="Safe global runtime ranking default appears ready and needs a separate implementation decision.",
        ),
        check(
            "raw_or_generated_data_not_committed",
            raw_clean,
            evidence=list(paths.values()),
            conclusion="Audited aggregate reports do not record committed raw records, prompts, answers, dialogs, memory content, or generated answers.",
            failure="At least one audited aggregate report records committed raw or generated data.",
        ),
        check(
            "phase6_status_not_overstated",
            objective_current,
            evidence=[paths["objective_coverage"]],
            conclusion="Objective coverage still reads as validation in progress with productization blocked.",
            failure="Objective coverage no longer matches the expected validation-stage posture.",
        ),
        check(
            "productization_blocked",
            productization_blocked,
            evidence=[paths["requirements_audit"]],
            conclusion="Productization remains explicitly not ready.",
            failure="Productization is not explicitly blocked by the requirements audit.",
        ),
        check(
            "no_runtime_ranking_default_supported",
            no_ranking_default,
            evidence=[paths["objective_coverage"]],
            conclusion="No global runtime ranking default is supported by current evidence.",
            failure="A runtime ranking default appears to be supported and needs a separate implementation decision.",
        ),
    ]

    current_system_gate_passed = all(item["status"] == "passed" for item in checks)
    blocked_next_gates = []
    if not top_context_ready:
        blocked_next_gates.append("top_context_candidate_not_judge_scored")
    if not hosted_ready:
        blocked_next_gates.append("hosted_external_comparison_not_configured")
    if productization_blocked:
        blocked_next_gates.append("productization_not_ready")

    input_metadata = {
        name: {
            "path": report_path(path),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for name, path in paths.items()
    }

    return {
        "schema_version": "king-synapse.phase6-current-system-gate.v1",
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
        "checks": checks,
        "raw_policy": {
            "clean": raw_clean,
            "details": raw_details,
        },
        "status": {
            "current_system_gate_passed": current_system_gate_passed,
            "current_work_mode": (
                "validation_only" if current_system_gate_passed else "repair_required"
            ),
            "heavy_next_gate_ready": next_gate_ready,
            "top_context_judge_ready": top_context_ready,
            "hosted_external_ready": hosted_ready,
            "productization_allowed": False,
            "runtime_ranking_change_allowed": False,
            "blocked_next_gates": blocked_next_gates,
        },
        "read": {
            "current_system_conclusion": (
                "Current Synapse is coherent enough to continue Phase 6 validation, "
                "but not to productize or change runtime ranking defaults."
                if current_system_gate_passed
                else "Current Synapse needs evidence-chain repair before continuing."
            ),
        "what_is_stable": [
                "Feature freeze is active.",
                "Local non-external baseline health is passed.",
                "Local official-style DMR is executable and judge-backed for the pinned extractive baseline.",
                "Ranking is a validated bottleneck, but current evidence supports no runtime default change.",
                "README claims are conservative enough against committed evidence.",
                "Raw benchmark data, prompts, answers, memory content, and generated answers remain out of the committed evidence chain.",
            ],
            "what_is_not_ready": [
                "Top-context DMR candidate judge scoring.",
                "Published-comparable official DMR performance.",
                "Hosted Graphiti/Zep, official Mem0, and live Letta comparison.",
                "Safe global runtime ranking default.",
                "Production readiness or v0.1 release readiness.",
            ],
            "next_action": (
                "Keep feature freeze. Continue only validation work until either "
                "valid judge authorization enables top-context DMR scoring or hosted "
                "competitor credentials/endpoints enable fair external comparison."
            ),
        },
        "limits": [
            "This gate consolidates already-committed aggregate evidence only.",
            "It does not run benchmarks, hosted adapters, LLM judges, or product code.",
            "A passing current-system gate is not a product-readiness claim.",
        ],
    }


def main() -> None:
    args = parse_args()
    output = normalize_path_arg(args.output)
    report = build_report(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": report_path(output),
                "current_system_gate_passed": report["status"][
                    "current_system_gate_passed"
                ],
                "current_work_mode": report["status"]["current_work_mode"],
                "heavy_next_gate_ready": report["status"]["heavy_next_gate_ready"],
                "productization_allowed": report["status"]["productization_allowed"],
                "blocked_next_gates": report["status"]["blocked_next_gates"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
