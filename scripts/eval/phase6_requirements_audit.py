#!/usr/bin/env python
"""Consolidate Phase 6 validation requirements against current evidence.

This audit turns the validation plan into a machine-readable status matrix.
It reads committed reports and documentation only; it does not run retrieval,
ranking, answer generation, external adapters, LLM judges, or product code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Audit Phase 6 requirements against current validation evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/phase6-requirements-audit.json",
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


def safe_get(data: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def input_record(path: Path) -> dict[str, Any]:
    return {
        "path": report_path(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def dmr_run_summary(report: dict[str, Any]) -> dict[str, Any]:
    aggregate = safe_get(report, ["answer_generation", "aggregate"], {})
    retrieval = report.get("retrieval", {})
    return {
        "requested": report.get("sample_size_requested"),
        "scored": report.get("sample_size_used"),
        "accelerator": report.get("accelerator"),
        "generator": report.get("generator"),
        "retrieval_recall_at_10": retrieval.get("recall_at_10"),
        "retrieval_mrr_at_10": retrieval.get("mrr_at_10"),
        "exact_accuracy": aggregate.get("exact_accuracy"),
        "substring_accuracy": aggregate.get("answer_substring_accuracy"),
        "rouge_l_f1_mean": aggregate.get("rouge_l_f1_mean"),
        "llm_judge_accuracy": aggregate.get("llm_judge_accuracy"),
        "raw_records_committed": report.get("raw_records_committed"),
        "raw_answers_committed": report.get("raw_answers_committed"),
        "generated_answers_committed": report.get("generated_answers_committed"),
    }


def build_phase(
    *,
    phase: str,
    status: str,
    evidence: list[str],
    conclusion: str,
    remaining: list[str],
    next_action: str,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "evidence": evidence,
        "conclusion": conclusion,
        "remaining": remaining,
        "next_action": next_action,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    paths = {
        "system_validation_report": root / "docs/eval/SYSTEM_VALIDATION_REPORT.md",
        "experiment_log": root / "docs/eval/EXPERIMENT_LOG.md",
        "official_dmr_result": root / "docs/eval/OFFICIAL_DMR_RESULT.md",
        "ranking_ablation": root / "docs/eval/RANKING_ABLATION.md",
        "external_validation": root / "docs/eval/EXTERNAL_VALIDATION.md",
        "long_horizon_validation": root / "docs/eval/LONG_HORIZON_VALIDATION.md",
        "gpu_validation": root / "docs/eval/GPU_VALIDATION_2026-07-02.md",
        "official_dmr_50": root / "crates/eval/reports/official-dmr-50.json",
        "official_dmr_200": root / "crates/eval/reports/official-dmr-200.json",
        "official_dmr_500": root / "crates/eval/reports/official-dmr-500.json",
        "official_dmr_generator_summary": root
        / "crates/eval/reports/official-dmr-generator-ablation-summary.json",
        "official_dmr_bottleneck_taxonomy": root
        / "crates/eval/reports/official-dmr-bottleneck-taxonomy.json",
        "dmr_failure_mode_taxonomy": root
        / "crates/eval/reports/dmr-failure-mode-taxonomy.json",
        "dmr_mapping_boundary_impact": root
        / "crates/eval/reports/dmr-mapping-boundary-impact.json",
        "dmr_top_context_significance": root
        / "crates/eval/reports/dmr-top-context-significance.json",
        "official_dmr_top_context_judge_preflight": root
        / "crates/eval/reports/official-dmr-top-context-judge-preflight.json",
        "official_dmr_50_top_context_judge": root
        / "crates/eval/reports/official-dmr-50-top-context-judge.json",
        "official_dmr_200_top_context_judge": root
        / "crates/eval/reports/official-dmr-200-top-context-judge.json",
        "official_dmr_500_top_context_judge": root
        / "crates/eval/reports/official-dmr-500-top-context-judge.json",
        "phase6_next_gate_readiness": root
        / "crates/eval/reports/phase6-next-gate-readiness.json",
        "official_dmr_task_gate": root
        / "crates/eval/reports/official-dmr-task-gate.json",
        "ranking_task_gate": root / "crates/eval/reports/ranking-task-gate.json",
        "external_comparison_task_gate": root
        / "crates/eval/reports/external-comparison-task-gate.json",
        "long_horizon_task_gate": root
        / "crates/eval/reports/long-horizon-task-gate.json",
        "productization_decision_gate": root
        / "crates/eval/reports/productization-decision-gate.json",
        "next_validation_action_gate": root
        / "crates/eval/reports/next-validation-action-gate.json",
        "ranking_objective_conflict_audit": root
        / "crates/eval/reports/ranking-objective-conflict-audit.json",
        "ranking_pool_signal_guard_audit": root
        / "crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json",
        "longmem_dmr_trend_alignment": root
        / "crates/eval/reports/longmem-dmr-trend-alignment.json",
        "ranking_objective_split_decision": root
        / "crates/eval/reports/ranking-objective-split-decision.json",
        "external_comparison_hosted": root
        / "crates/eval/reports/external-comparison-hosted.json",
        "long_horizon_cognitive_memory": root
        / "crates/eval/reports/long-horizon-cognitive-memory.json",
        "long_horizon_stability_audit": root
        / "crates/eval/reports/long-horizon-stability-audit.json",
        "long_horizon_prediction_evidence_audit": root
        / "crates/eval/reports/long-horizon-prediction-evidence-audit.json",
        "phase6_benchmark_baseline": root
        / "crates/eval/reports/phase6-benchmark-baseline.json",
        "phase6_baseline_health_check": root
        / "crates/eval/reports/phase6-baseline-health-check-2026-07-04.json",
        "phase6_performance_profile": root
        / "crates/eval/reports/phase6-performance-profile.json",
    }

    missing_inputs = [name for name, path in paths.items() if not path.exists()]
    dmr_50 = load_json(paths["official_dmr_50"])
    dmr_200 = load_json(paths["official_dmr_200"])
    dmr_500 = load_json(paths["official_dmr_500"])
    generator_summary = load_json(paths["official_dmr_generator_summary"])
    bottleneck_taxonomy = load_json(paths["official_dmr_bottleneck_taxonomy"])
    failure_mode_taxonomy = load_json(paths["dmr_failure_mode_taxonomy"])
    mapping_boundary_impact = load_json(paths["dmr_mapping_boundary_impact"])
    top_context_significance = load_json(paths["dmr_top_context_significance"])
    top_context_preflight = load_json(paths["official_dmr_top_context_judge_preflight"])
    next_gate_readiness = load_json(paths["phase6_next_gate_readiness"])
    official_dmr_task_gate = load_json(paths["official_dmr_task_gate"])
    ranking_task_gate = load_json(paths["ranking_task_gate"])
    external_comparison_task_gate = load_json(paths["external_comparison_task_gate"])
    long_horizon_task_gate = load_json(paths["long_horizon_task_gate"])
    productization_decision_gate = load_json(paths["productization_decision_gate"])
    next_validation_action_gate = load_json(paths["next_validation_action_gate"])
    ranking_conflict = load_json(paths["ranking_objective_conflict_audit"])
    ranking_guard = load_json(paths["ranking_pool_signal_guard_audit"])
    trend_alignment = load_json(paths["longmem_dmr_trend_alignment"])
    split_decision = load_json(paths["ranking_objective_split_decision"])
    external_hosted = load_json(paths["external_comparison_hosted"])
    long_horizon = load_json(paths["long_horizon_cognitive_memory"])
    long_horizon_evidence = load_json(paths["long_horizon_prediction_evidence_audit"])
    performance = load_json(paths["phase6_performance_profile"])
    baseline = load_json(paths["phase6_benchmark_baseline"])
    baseline_health = load_json(paths["phase6_baseline_health_check"])

    dmr_runs = {
        "dmr_50": dmr_run_summary(dmr_50),
        "dmr_200": dmr_run_summary(dmr_200),
        "dmr_500_request": dmr_run_summary(dmr_500),
    }
    generator_findings = generator_summary["aggregate_findings"]
    ranking_read = ranking_conflict["read"]
    hosted_summary = external_hosted["summary"]
    next_gate_read = next_gate_readiness["read"]
    long_horizon_metrics = long_horizon["metrics"]
    long_horizon_evidence_aggregate = long_horizon_evidence["aggregate"]
    gpu_configuration = performance.get("gpu_configuration", {})
    recall_baselines = baseline.get("recall_baselines", [])

    current_branch = git_value("rev-parse", "--abbrev-ref", "HEAD")
    current_commit = git_value("rev-parse", "HEAD")
    origin_delta = git_value("rev-list", "--left-right", "--count", "origin/main...HEAD")

    phases = [
        build_phase(
            phase="1_lock_current_version",
            status="active_policy",
            evidence=[
                report_path(paths["system_validation_report"]),
                report_path(paths["experiment_log"]),
                report_path(paths["gpu_validation"]),
                report_path(paths["phase6_benchmark_baseline"]),
                report_path(paths["phase6_baseline_health_check"]),
                report_path(paths["phase6_performance_profile"]),
            ],
            conclusion=(
                "Feature growth is frozen by policy, Phase 6 replay baselines are "
                "registered, local health checks pass, and heavy validation is "
                "documented on CUDA device 0."
            ),
            remaining=[
                "Keep future changes in evaluation reports/scripts unless a later decision explicitly opens productization.",
                "Do not change memory schema, cognitive layers, CLI behavior, or runtime ranking defaults from current evidence.",
            ],
            next_action="Continue using current main as the validation baseline and log every experiment.",
        ),
        build_phase(
            phase="2_official_style_dmr",
            status="local_official_style_complete_not_published_comparable",
            evidence=[
                report_path(paths["official_dmr_result"]),
                report_path(paths["official_dmr_50"]),
                report_path(paths["official_dmr_200"]),
                report_path(paths["official_dmr_500"]),
                report_path(paths["official_dmr_generator_summary"]),
                report_path(paths["official_dmr_bottleneck_taxonomy"]),
                report_path(paths["dmr_failure_mode_taxonomy"]),
                report_path(paths["dmr_mapping_boundary_impact"]),
                report_path(paths["dmr_top_context_significance"]),
                report_path(paths["official_dmr_top_context_judge_preflight"]),
                report_path(paths["official_dmr_50_top_context_judge"]),
                report_path(paths["official_dmr_200_top_context_judge"]),
                report_path(paths["official_dmr_500_top_context_judge"]),
                report_path(paths["phase6_next_gate_readiness"]),
                report_path(paths["official_dmr_task_gate"]),
            ],
            conclusion=(
                "Retrieval -> answer generation -> local scoring exists for 50, "
                "200, and 500-request DMR views. Baseline extractive runs are "
                "judge-backed, and DMR 50/200/500-request top-context views are "
                "judge-backed. DMR 500 failure modes are classified, but absolute "
                "answer quality remains low. The largest mapping boundary is "
                "narrowed to scoring policy rather than empty memory chunks, and "
                "top-context judge gains are paired-significant across completed "
                "scale views."
            ),
            remaining=[
                "Published-comparable DMR mapping/scoring policy is not finalized.",
                "500-request run honestly scores 323 mappable samples, not 500/500.",
                "Answer synthesis remains weak even when retrieval finds a relevant chunk.",
                "DMR 500 failure taxonomy keeps mapping, retrieval/ranking, and answer synthesis separate.",
                "DMR mapping-boundary impact keeps relaxed-token rows diagnostic-only until separately validated.",
                "Top-context significance supports the generator direction, but not a runtime default or official product claim.",
                "Bottleneck taxonomy keeps mapping coverage, retrieval/ranking, and generator quality as separate active limits.",
            ],
            next_action="Stop expanding the DMR judge-scaling branch; continue with hosted external comparison or no-model failure analysis.",
        ),
        build_phase(
            phase="3_ranking_without_architecture_change",
            status="validated_no_global_default",
            evidence=[
                report_path(paths["ranking_ablation"]),
                report_path(paths["ranking_objective_conflict_audit"]),
                report_path(paths["ranking_pool_signal_guard_audit"]),
                report_path(paths["longmem_dmr_trend_alignment"]),
                report_path(paths["ranking_objective_split_decision"]),
                report_path(paths["ranking_task_gate"]),
            ],
            conclusion=(
                f"{ranking_read['conclusion']} "
                f"{trend_alignment['read']['primary_result']} "
                f"{split_decision['read']['current_conclusion']}"
            ),
            remaining=[
                "No screened pool-signal guard is ready for implementation.",
                "DMR and LongMemEval ranking objectives are now split as validation-only.",
                "The LongMemEval / DMR trend-alignment exit condition is not complete.",
                "Any runtime ranking policy still needs zero LongMemEval top-10 suppressions and an explicit latency budget.",
            ],
            next_action=split_decision["read"]["next_action"],
        ),
        build_phase(
            phase="4_external_fair_comparison",
            status="partial_local_complete_hosted_open",
            evidence=[
                report_path(paths["external_validation"]),
                report_path(paths["external_comparison_hosted"]),
                report_path(paths["phase6_next_gate_readiness"]),
                report_path(paths["external_comparison_task_gate"]),
            ],
            conclusion=(
                "The cognitive fixture shows Synapse's local trace surface, but "
                "hosted Graphiti/Zep, official Mem0, and live Letta are not "
                "configured in the current environment."
            ),
            remaining=[
                "Graphiti/Zep hosted or standard Neo4j/OpenAI run is not measured.",
                "Mem0 official/recommended embedding configuration is not measured.",
                "Letta live endpoint is not measured.",
            ],
            next_action="Provide or configure hosted competitor credentials/endpoints, then rerun the shared cognitive fixture.",
        ),
        build_phase(
            phase="5_long_horizon_stability",
            status="deterministic_fixture_complete_public_long_memory_open",
            evidence=[
                report_path(paths["long_horizon_validation"]),
                report_path(paths["long_horizon_cognitive_memory"]),
                report_path(paths["long_horizon_stability_audit"]),
                report_path(paths["long_horizon_prediction_evidence_audit"]),
                report_path(paths["long_horizon_task_gate"]),
            ],
            conclusion=(
                "The deterministic long-session fixture passes fixed metrics at "
                "1.000. The remaining weak surface is target-side future evidence "
                "labeling, not candidate recall, hidden-trace drift, or reinforcement."
            ),
            remaining=[
                "Fixture is deterministic and hand-shaped, not public real-world long-memory evidence.",
                "Future evidence policy remains validation-only and should not become a product claim yet.",
            ],
            next_action="Keep the regression gate fixed and add broader long-horizon evidence only as validation work.",
        ),
        build_phase(
            phase="6_productization_decision",
            status="not_ready",
            evidence=[
                report_path(paths["system_validation_report"]),
                report_path(paths["external_comparison_hosted"]),
                report_path(paths["official_dmr_result"]),
                report_path(paths["productization_decision_gate"]),
                report_path(paths["next_validation_action_gate"]),
            ],
            conclusion=(
                "Productization is premature. The no-go decision is now gate-backed: "
                "the productization decision gate keeps productization false, and "
                "the next-validation action gate keeps heavy reruns blocked until "
                "external preconditions change."
            ),
            remaining=[
                "Need clear supported task boundaries.",
                "Need measured hosted competitor comparisons.",
                "Need stronger DMR answer-generation quality and finalized scoring policy.",
                "Need explicit GPU cost acceptance and stable public demo criteria.",
                "Need hosted competitor configuration before the next hosted heavy run.",
            ],
            next_action="Do not start web demo, API server, Docker, release packaging, or product README claims. Follow next-validation-action gate: wait for hosted external configuration or continue no-model failure analysis.",
        ),
    ]

    open_phases = [phase["phase"] for phase in phases if phase["status"] not in {"active_policy"}]
    blocking_gaps = [
        "published_comparable_dmr_not_finished",
        "no_global_ranking_default_supported",
        "hosted_external_comparison_not_configured",
        "future_evidence_labeling_boundary",
        "public_real_world_long_memory_not_validated",
        "next_validation_action_waiting_on_hosted_or_failure_analysis",
        "productization_not_ready",
    ]

    return {
        "schema_version": "king-synapse.phase6-requirements-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "git": {
            "branch": current_branch,
            "commit": current_commit,
            "origin_main_delta": origin_delta,
        },
        "inputs": {name: input_record(path) for name, path in paths.items()},
        "missing_inputs": missing_inputs,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "generated_answers_committed": False,
        "phase_status": phases,
        "key_metrics": {
                "official_style_dmr": {
                "runs": dmr_runs,
                "generator_ablation": {
                    "improves_substring_all_scale_views": generator_findings[
                        "candidate_improves_substring_on_all_scale_views"
                    ],
                    "improves_rouge_l_all_scale_views": generator_findings[
                        "candidate_improves_rouge_l_f1_on_all_scale_views"
                    ],
                    "judge_status": generator_findings["judge_status"],
                    "judge_status_counts_by_generator": generator_findings[
                        "judge_status_counts_by_generator"
                    ],
                },
                "top_context_judge_preflight": {
                    "result": top_context_preflight.get("result"),
                    "decision": top_context_preflight.get("decision"),
                },
                "top_context_dmr_50_judge_report": input_record(
                    paths["official_dmr_50_top_context_judge"]
                ),
                "top_context_dmr_200_judge_report": input_record(
                    paths["official_dmr_200_top_context_judge"]
                ),
                "top_context_dmr_500_judge_report": input_record(
                    paths["official_dmr_500_top_context_judge"]
                ),
                "next_gate_readiness": {
                    "next_gate_ready": next_gate_read.get("next_gate_ready"),
                    "top_context_judge_ready": safe_get(
                        next_gate_readiness, ["top_context_judge", "ready"]
                    ),
                    "hosted_external_ready": safe_get(
                        next_gate_readiness, ["hosted_external", "ready"]
                    ),
                    "blocking_reason": next_gate_read.get("blocking_reason"),
                },
                "task_gate": official_dmr_task_gate["status"],
                "bottleneck_taxonomy": {
                    "mapping_boundary": bottleneck_taxonomy["mapping_boundary"],
                    "largest_local_view": bottleneck_taxonomy["largest_local_view"],
                    "conclusion": bottleneck_taxonomy["read"]["conclusion"],
                },
                "failure_mode_taxonomy": {
                    "scope": failure_mode_taxonomy["scope"],
                    "mutually_exclusive_outcome_taxonomy": failure_mode_taxonomy[
                        "mutually_exclusive_outcome_taxonomy"
                    ],
                    "generator_delta": failure_mode_taxonomy["generator_delta"],
                    "primary_result": failure_mode_taxonomy["read"]["primary_result"],
                },
                "mapping_boundary_impact": {
                    "scope": mapping_boundary_impact["scope"],
                    "punctuation_rejected_breakdown": mapping_boundary_impact[
                        "punctuation_rejected_breakdown"
                    ],
                    "primary_result": mapping_boundary_impact["read"]["primary_result"],
                    "official_boundary": mapping_boundary_impact["read"][
                        "official_boundary"
                    ],
                },
                "top_context_significance": {
                    "cross_scale_summary": top_context_significance[
                        "cross_scale_summary"
                    ],
                    "primary_result": top_context_significance["read"][
                        "primary_result"
                    ],
                    "statistical_read": top_context_significance["read"][
                        "statistical_read"
                    ],
                },
            },
            "ranking": {
                "task_gate": ranking_task_gate["status"],
                "global_default_candidate": ranking_read["global_default_candidate"],
                "conflict_or_tradeoff_views": ranking_read[
                    "conflict_or_tradeoff_views"
                ],
                "best_safe_guard_id": safe_get(ranking_guard, ["read", "best_safe_guard_id"]),
                "safe_guard_ids": safe_get(ranking_guard, ["read", "safe_guard_ids"], []),
                "trend_alignment": {
                    "status": trend_alignment["status"],
                    "primary_result": trend_alignment["read"]["primary_result"],
                    "decision": trend_alignment["read"]["decision"],
                },
                "objective_split_decision": {
                    "status": split_decision["status"],
                    "decision": split_decision["objective_split"]["decision"],
                    "current_conclusion": split_decision["read"]["current_conclusion"],
                },
            },
            "external_hosted": {
                "task_gate": external_comparison_task_gate["status"],
                "measured_systems": hosted_summary["measured_systems"],
                "not_configured_systems": hosted_summary["not_configured_systems"],
                "failed_systems": hosted_summary["failed_systems"],
            },
            "long_horizon": {
                "task_gate": long_horizon_task_gate["status"],
                "fixed_metrics": long_horizon_metrics,
                "candidate_present_all_phases_count": long_horizon_evidence_aggregate[
                    "candidate_present_all_phases_count"
                ],
                "matched_evidence_all_phases_count": long_horizon_evidence_aggregate[
                    "matched_evidence_all_phases_count"
                ],
                "context_overlap_explains_all_reported_matched_misses": long_horizon_evidence_aggregate[
                    "context_overlap_explains_all_reported_matched_misses"
                ],
            },
            "performance": {
                "gpu_configuration": gpu_configuration,
                "recall_baseline_count": len(recall_baselines),
            },
            "productization_decision": productization_decision_gate["status"],
            "next_validation_action": next_validation_action_gate["status"],
            "baseline_health": {
                "validated_commit": baseline_health.get("validated_commit"),
                "current_baseline_health": safe_get(
                    baseline_health, ["read", "current_baseline_health"]
                ),
                "feature_freeze_preserved": baseline_health.get(
                    "feature_freeze_preserved"
                ),
                "heavy_external_calls_run": baseline_health.get(
                    "heavy_external_calls_run"
                ),
                "checks": {
                    check.get("id"): check.get("status")
                    for check in baseline_health.get("checks", [])
                },
            },
        },
        "read": {
            "current_state": (
                "Synapse is still in Phase 6 system validation. Current evidence "
                "supports the architecture on deterministic cognitive fixtures and "
                "local official-style DMR execution, but not productization."
            ),
            "strongest_supported_claims": [
                "Cognitive trace introspection is richer than the measured local adapters in the shared fixture.",
                "Official-style DMR local scoring is executable on CUDA without committing raw records.",
                "Ranking and answer synthesis are the active bottlenecks, not a disproven core architecture.",
                "Long-horizon candidate recall and hidden trace behavior are stable in the deterministic fixture.",
            ],
            "claims_not_yet_supported": [
                "Published-comparable official DMR performance.",
                "Hosted Graphiti/Zep, official Mem0, or live Letta superiority.",
                "A safe global ranking-default change.",
                "Production readiness or v0.1 release readiness.",
                "Any heavy next validation rerun while external preconditions are blocked.",
            ],
            "blocking_gaps": blocking_gaps,
            "recommended_next_action": (
                "Keep feature freeze. The next-validation action gate says no "
                "heavy validation branch is currently selected: DMR 50 and 200 "
                "and 500-request top-context judge scoring are complete, and the "
                "next heavy branch is hosted external comparison once "
                "credentials/endpoints are ready."
            ),
        },
        "limits": [
            "This is an evidence consolidation pass only.",
            "It does not rerun benchmarks or verify external service availability.",
            "It should not be used to claim product readiness.",
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
                "phase_statuses": {
                    phase["phase"]: phase["status"] for phase in report["phase_status"]
                },
                "blocking_gaps": report["read"]["blocking_gaps"],
                "recommended_next_action": report["read"]["recommended_next_action"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
