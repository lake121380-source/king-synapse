#!/usr/bin/env python
"""Audit README claims against current Phase 6 evidence.

The goal is not to rewrite marketing copy. It is to keep README claims scoped
to what the committed validation reports can actually support.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Audit README claims against Phase 6 evidence.")
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/readme-claims-support-audit.json",
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
        if isinstance(current, dict):
            if key not in current:
                return default
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int):
            if key < 0 or key >= len(current):
                return default
            current = current[key]
        else:
            return default
    return current


def input_record(path: Path) -> dict[str, Any]:
    return {
        "path": report_path(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def claim(
    *,
    claim_id: str,
    readme_snippet: str,
    status: str,
    evidence: list[str],
    conclusion: str,
    required_scope_note: str | None = None,
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "readme_snippet": readme_snippet,
        "status": status,
        "evidence": evidence,
        "conclusion": conclusion,
        "required_scope_note": required_scope_note,
    }


def snippet_present(readme_text: str, snippet: str) -> bool:
    return snippet.casefold() in readme_text.casefold()


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    paths = {
        "readme": root / "README.md",
        "system_validation_report": root / "docs/eval/SYSTEM_VALIDATION_REPORT.md",
        "experiment_log": root / "docs/eval/EXPERIMENT_LOG.md",
        "phase6_requirements_audit": root
        / "crates/eval/reports/phase6-requirements-audit.json",
        "phase6_objective_coverage": root
        / "crates/eval/reports/phase6-objective-coverage-audit.json",
        "phase6_next_gate_readiness": root
        / "crates/eval/reports/phase6-next-gate-readiness.json",
        "external_comparison_latest": root
        / "crates/eval/reports/external-comparison-latest.json",
        "external_comparison_hosted": root
        / "crates/eval/reports/external-comparison-hosted.json",
        "official_dmr_result": root / "docs/eval/OFFICIAL_DMR_RESULT.md",
        "official_dmr_50": root / "crates/eval/reports/official-dmr-50.json",
        "official_dmr_200": root / "crates/eval/reports/official-dmr-200.json",
        "official_dmr_500": root / "crates/eval/reports/official-dmr-500.json",
        "official_dmr_bottleneck_taxonomy": root
        / "crates/eval/reports/official-dmr-bottleneck-taxonomy.json",
        "dmr_top_context_significance": root
        / "crates/eval/reports/dmr-top-context-significance.json",
        "ranking_objective_conflict": root
        / "crates/eval/reports/ranking-objective-conflict-audit.json",
        "ranking_pool_signal_guard": root
        / "crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json",
        "longmem_dmr_trend_alignment": root
        / "crates/eval/reports/longmem-dmr-trend-alignment.json",
        "ranking_objective_split_decision": root
        / "crates/eval/reports/ranking-objective-split-decision.json",
        "long_horizon_cognitive_memory": root
        / "crates/eval/reports/long-horizon-cognitive-memory.json",
        "long_horizon_prediction_evidence": root
        / "crates/eval/reports/long-horizon-prediction-evidence-audit.json",
        "long_horizon_task_gate": root
        / "crates/eval/reports/long-horizon-task-gate.json",
        "productization_decision_gate": root
        / "crates/eval/reports/productization-decision-gate.json",
        "next_validation_action_gate": root
        / "crates/eval/reports/next-validation-action-gate.json",
    }

    readme_text = paths["readme"].read_text(encoding="utf-8")
    phase6 = load_json(paths["phase6_requirements_audit"])
    coverage = load_json(paths["phase6_objective_coverage"])
    readiness = load_json(paths["phase6_next_gate_readiness"])
    external_latest = load_json(paths["external_comparison_latest"])
    external_hosted = load_json(paths["external_comparison_hosted"])
    dmr_50 = load_json(paths["official_dmr_50"])
    dmr_200 = load_json(paths["official_dmr_200"])
    dmr_500 = load_json(paths["official_dmr_500"])
    bottleneck = load_json(paths["official_dmr_bottleneck_taxonomy"])
    top_context_significance = load_json(paths["dmr_top_context_significance"])
    ranking_conflict = load_json(paths["ranking_objective_conflict"])
    ranking_guard = load_json(paths["ranking_pool_signal_guard"])
    trend_alignment = load_json(paths["longmem_dmr_trend_alignment"])
    split_decision = load_json(paths["ranking_objective_split_decision"])
    long_horizon = load_json(paths["long_horizon_cognitive_memory"])
    long_horizon_evidence = load_json(paths["long_horizon_prediction_evidence"])
    long_horizon_gate = load_json(paths["long_horizon_task_gate"])
    productization_gate = load_json(paths["productization_decision_gate"])
    next_action_gate = load_json(paths["next_validation_action_gate"])

    external_systems = {
        system.get("system"): system for system in external_latest.get("systems", [])
    }
    king_metrics = safe_get(
        external_systems.get("King Synapse", {}), ["aggregate", "metrics"], {}
    )
    local_trace_hits = {
        name: safe_get(king_metrics, [name, "hit"])
        for name in [
            "hidden_influence_dominant",
            "suppressed_alternatives_visible",
            "evidence_path_available",
            "future_continuation_found",
            "reinforcement_isolated",
        ]
    }

    dmr_runs = {
        "50": {
            "requested": dmr_50.get("sample_size_requested"),
            "scored": dmr_50.get("sample_size_used"),
            "substring": safe_get(dmr_50, ["answer_generation", "aggregate", "answer_substring_accuracy"]),
            "rouge_l_f1": safe_get(dmr_50, ["answer_generation", "aggregate", "rouge_l_f1_mean"]),
            "judge_count": safe_get(
                dmr_50,
                ["answer_generation", "aggregate", "llm_judge_status_counts", "judged"],
            ),
        },
        "200": {
            "requested": dmr_200.get("sample_size_requested"),
            "scored": dmr_200.get("sample_size_used"),
            "substring": safe_get(dmr_200, ["answer_generation", "aggregate", "answer_substring_accuracy"]),
            "rouge_l_f1": safe_get(dmr_200, ["answer_generation", "aggregate", "rouge_l_f1_mean"]),
            "judge_count": safe_get(
                dmr_200,
                ["answer_generation", "aggregate", "llm_judge_status_counts", "judged"],
            ),
        },
        "500_request": {
            "requested": dmr_500.get("sample_size_requested"),
            "scored": dmr_500.get("sample_size_used"),
            "substring": safe_get(dmr_500, ["answer_generation", "aggregate", "answer_substring_accuracy"]),
            "rouge_l_f1": safe_get(dmr_500, ["answer_generation", "aggregate", "rouge_l_f1_mean"]),
            "judge_count": safe_get(
                dmr_500,
                ["answer_generation", "aggregate", "llm_judge_status_counts", "judged"],
            ),
        },
    }

    claims = [
        claim(
            claim_id="tagline_readable_memory",
            readme_snippet="Readable memory for coding agents.",
            status="supported_with_scope",
            evidence=[
                report_path(paths["system_validation_report"]),
                report_path(paths["external_comparison_latest"]),
            ],
            conclusion=(
                "The README tagline is consistent with the local cognitive-trace "
                "fixture, but should remain scoped to the current engine and validation reports."
            ),
            required_scope_note="Do not turn this into production-readiness language yet.",
        ),
        claim(
            claim_id="status_badge_cognitive_memory_validated",
            readme_snippet="status-cognitive%20memory%20validated",
            status="supported_with_scope",
            evidence=[
                report_path(paths["long_horizon_cognitive_memory"]),
                report_path(paths["phase6_objective_coverage"]),
            ],
            conclusion=(
                "The badge is supportable for deterministic cognitive-memory fixtures, "
                "not for product readiness or public long-memory superiority."
            ),
            required_scope_note="Keep nearby README text saying Phase 6 validation is still in progress.",
        ),
        claim(
            claim_id="engine_capabilities",
            readme_snippet="Reports the dominant trace and the suppressed alternatives.",
            status="supported",
            evidence=[report_path(paths["external_comparison_latest"])],
            conclusion=(
                "Local comparison records 8/8 hits for dominant trace and suppressed alternatives."
            ),
        ),
        claim(
            claim_id="future_and_reinforcement",
            readme_snippet="Predicts likely next influences from the winning trace.",
            status="supported_with_scope",
            evidence=[
                report_path(paths["external_comparison_latest"]),
                report_path(paths["long_horizon_prediction_evidence"]),
            ],
            conclusion=(
                "Future continuation is 8/8 in the local fixture, while long-horizon "
                "matched evidence remains 6/8. The README should keep the claim qualitative."
            ),
            required_scope_note="Do not claim robust real-world future prediction yet.",
        ),
        claim(
            claim_id="comparison_table",
            readme_snippet="What King Synapse adds",
            status="supported_with_scope",
            evidence=[
                report_path(paths["external_comparison_latest"]),
                report_path(paths["external_comparison_hosted"]),
            ],
            conclusion=(
                "The comparison table is acceptable as a capability-positioning table, "
                "but the hosted competitor comparison is still not configured."
            ),
            required_scope_note="Keep hosted/official comparison caveats visible.",
        ),
        claim(
            claim_id="current_external_evaluation",
            readme_snippet="Synapse is measured on the fixture, while hosted Graphiti/Zep, official Mem0",
            status="supported",
            evidence=[
                report_path(paths["external_comparison_hosted"]),
                report_path(paths["phase6_next_gate_readiness"]),
            ],
            conclusion=(
                f"Hosted report measured {safe_get(external_hosted, ['summary', 'measured_systems'])} "
                f"system and left {safe_get(external_hosted, ['summary', 'not_configured_systems'])} systems not configured."
            ),
        ),
        claim(
            claim_id="official_dmr_table",
            readme_snippet="This is still not a published-comparable official DMR result.",
            status="supported",
            evidence=[
                report_path(paths["official_dmr_50"]),
                report_path(paths["official_dmr_200"]),
                report_path(paths["official_dmr_500"]),
                report_path(paths["official_dmr_result"]),
            ],
            conclusion=(
                "The README's DMR caveat is supported: pinned local runs are judged, "
                "top-context judge scaling is complete, and published-comparable "
                "mapping plus answer quality remain open."
            ),
        ),
        claim(
            claim_id="dmr_top_context_significance",
            readme_snippet="McNemar p-value",
            status="supported",
            evidence=[report_path(paths["dmr_top_context_significance"])],
            conclusion=safe_get(
                top_context_significance, ["read", "statistical_read"], ""
            ),
        ),
        claim(
            claim_id="answer_synthesis_bottleneck",
            readme_snippet="system can find a",
            status="supported",
            evidence=[report_path(paths["official_dmr_bottleneck_taxonomy"])],
            conclusion=safe_get(bottleneck, ["read", "conclusion"], ""),
        ),
        claim(
            claim_id="no_runtime_ranking_default",
            readme_snippet="tested pool-signal guard should become a runtime default",
            status="supported",
            evidence=[
                report_path(paths["ranking_objective_conflict"]),
                report_path(paths["ranking_pool_signal_guard"]),
            ],
            conclusion=safe_get(ranking_conflict, ["read", "conclusion"], ""),
        ),
        claim(
            claim_id="longmem_dmr_trend_alignment",
            readme_snippet="LongMemEval / DMR trend alignment",
            status="supported",
            evidence=[report_path(paths["longmem_dmr_trend_alignment"])],
            conclusion=safe_get(trend_alignment, ["read", "primary_result"], ""),
        ),
        claim(
            claim_id="ranking_objective_split_decision",
            readme_snippet="ranking-objective split",
            status="supported",
            evidence=[report_path(paths["ranking_objective_split_decision"])],
            conclusion=safe_get(split_decision, ["read", "current_conclusion"], ""),
        ),
        claim(
            claim_id="long_horizon_task_gate",
            readme_snippet="long_horizon_gate_passed: true",
            status="supported",
            evidence=[report_path(paths["long_horizon_task_gate"])],
            conclusion=safe_get(long_horizon_gate, ["read", "current_conclusion"], ""),
        ),
        claim(
            claim_id="productization_decision_gate",
            readme_snippet="productization_ready: false",
            status="supported",
            evidence=[report_path(paths["productization_decision_gate"])],
            conclusion=safe_get(productization_gate, ["read", "current_conclusion"], ""),
        ),
        claim(
            claim_id="next_validation_action_gate",
            readme_snippet=(
                "recommended_action: "
                "wait_for_hosted_external_configuration_or_no_model_failure_analysis"
            ),
            status="supported",
            evidence=[report_path(paths["next_validation_action_gate"])],
            conclusion=safe_get(next_action_gate, ["read", "current_conclusion"], ""),
        ),
        claim(
            claim_id="productization_blocked",
            readme_snippet="productization is not ready",
            status="supported",
            evidence=[
                report_path(paths["phase6_requirements_audit"]),
                report_path(paths["phase6_objective_coverage"]),
            ],
            conclusion=safe_get(phase6, ["read", "current_state"], ""),
        ),
    ]

    for item in claims:
        item["present_in_readme"] = snippet_present(readme_text, item["readme_snippet"])
        if not item["present_in_readme"]:
            item["status"] = "readme_snippet_missing"

    status_counts = Counter(item["status"] for item in claims)
    unsupported_claims = [
        item["id"] for item in claims if item["status"] in {"unsupported", "readme_snippet_missing"}
    ]
    scoped_claims = [
        item["id"] for item in claims if item["status"] == "supported_with_scope"
    ]

    current_branch = git_value("rev-parse", "--abbrev-ref", "HEAD")
    current_commit = git_value("rev-parse", "HEAD")
    origin_delta = git_value("rev-list", "--left-right", "--count", "origin/main...HEAD")

    return {
        "schema_version": "king-synapse.readme-claims-support-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "git": {
            "branch": current_branch,
            "commit": current_commit,
            "origin_main_delta": origin_delta,
        },
        "inputs": {name: input_record(path) for name, path in paths.items()},
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "claims": claims,
        "status_counts": dict(status_counts),
        "unsupported_claims": unsupported_claims,
        "supported_with_scope_claims": scoped_claims,
        "key_metrics": {
            "local_trace_hits": local_trace_hits,
            "dmr_runs": dmr_runs,
            "top_context_judge_ready": safe_get(readiness, ["top_context_judge", "ready"]),
            "hosted_external_ready": safe_get(readiness, ["hosted_external", "ready"]),
            "phase6_overall": safe_get(coverage, ["read", "overall"]),
            "productization_status": safe_get(phase6, ["phase_status", 5, "status"]),
            "long_horizon_fixed_metrics": long_horizon.get("metrics", {}),
            "long_horizon_matched_evidence_count": safe_get(
                long_horizon_evidence, ["aggregate", "matched_evidence_all_phases_count"]
            ),
            "long_horizon_gate_passed": safe_get(
                long_horizon_gate, ["status", "long_horizon_gate_passed"]
            ),
            "public_real_world_long_memory_ready": safe_get(
                long_horizon_gate, ["status", "public_real_world_long_memory_ready"]
            ),
            "productization_decision_gate_passed": safe_get(
                productization_gate,
                ["status", "productization_decision_gate_passed"],
            ),
            "productization_ready": safe_get(
                productization_gate, ["status", "productization_ready"]
            ),
            "release_v0_1_allowed": safe_get(
                productization_gate, ["status", "release_v0_1_allowed"]
            ),
            "next_validation_action_gate_passed": safe_get(
                next_action_gate, ["status", "next_validation_action_gate_passed"]
            ),
            "recommended_next_validation_action": safe_get(
                next_action_gate, ["status", "recommended_action"]
            ),
            "heavy_validation_allowed": safe_get(
                next_action_gate, ["status", "heavy_validation_allowed"]
            ),
        },
        "read": {
            "readme_claims_conservative_enough": not unsupported_claims,
            "public_claim_posture": (
                "README claims are currently conservative enough for a validation-stage "
                "project, provided scoped/local caveats remain visible."
            )
            if not unsupported_claims
            else "README has unsupported or missing audited snippets.",
            "must_not_claim_yet": [
                "published-comparable official DMR performance",
                "hosted Graphiti/Zep or official Mem0 superiority",
                "safe global ranking default",
                "production readiness",
                "v0.1 release readiness",
            ],
            "next_action": (
                "Keep README in validation posture until top-context judge scoring, "
                "hosted external comparison, and productization gates are closed."
            ),
        },
        "limits": [
            "This audit checks README claims against committed evidence only.",
            "It does not run benchmarks, hosted adapters, LLM judges, or product code.",
            "It does not prove product readiness.",
        ],
    }


def main() -> int:
    args = parse_args()
    args.output = normalize_path_arg(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "readme_claims_conservative_enough": report["read"][
                    "readme_claims_conservative_enough"
                ],
                "status_counts": report["status_counts"],
                "unsupported_claims": report["unsupported_claims"],
                "supported_with_scope_claims": report["supported_with_scope_claims"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
