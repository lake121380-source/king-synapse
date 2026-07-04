#!/usr/bin/env python
"""Map the user-defined Phase 6 objective to current committed evidence.

This is a coverage audit, not a benchmark runner. It reads sanitized reports
and docs, summarizes whether each objective requirement is supported, partial,
externally blocked, or not ready, and records the remaining proof gaps without
changing runtime behavior.
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
    parser = argparse.ArgumentParser(
        description="Audit Phase 6 objective coverage against current evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/phase6-objective-coverage-audit.json",
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


def requirement(
    *,
    item: str,
    status: str,
    evidence: list[str],
    conclusion: str,
    remaining: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "item": item,
        "status": status,
        "evidence": evidence,
        "conclusion": conclusion,
        "remaining": remaining or [],
    }


def phase(
    *,
    phase_id: str,
    title: str,
    status: str,
    requirements: list[dict[str, Any]],
    conclusion: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "phase": phase_id,
        "title": title,
        "status": status,
        "requirements": requirements,
        "conclusion": conclusion,
        "next_action": next_action,
    }


def dmr_evidence(report: dict[str, Any]) -> dict[str, Any]:
    aggregate = safe_get(report, ["answer_generation", "aggregate"], {})
    judge_counts = aggregate.get("llm_judge_status_counts", {})
    return {
        "requested": report.get("sample_size_requested"),
        "scored": report.get("sample_size_used"),
        "answer_match_policy": report.get("answer_match_policy"),
        "accelerator_requested": safe_get(report, ["accelerator", "requested"]),
        "cuda_device_id": safe_get(report, ["accelerator", "cuda_device_id"]),
        "generator_policy": safe_get(report, ["generator", "policy"]),
        "retrieval_recall_at_10": safe_get(report, ["retrieval", "recall_at_10"]),
        "exact_accuracy": aggregate.get("exact_accuracy"),
        "punctuation_accuracy": aggregate.get("punctuation_accuracy"),
        "answer_substring_accuracy": aggregate.get("answer_substring_accuracy"),
        "rouge_l_f1_mean": aggregate.get("rouge_l_f1_mean"),
        "llm_judge_accuracy": aggregate.get("llm_judge_accuracy"),
        "llm_judged_count": judge_counts.get("judged"),
        "raw_records_committed": report.get("raw_records_committed"),
        "raw_answers_committed": report.get("raw_answers_committed"),
        "generated_answers_committed": report.get("generated_answers_committed"),
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
        "performance_analysis": root / "docs/eval/PERFORMANCE_ANALYSIS.md",
        "phase6_requirements_audit": root
        / "crates/eval/reports/phase6-requirements-audit.json",
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
        "phase6_baseline_health": root
        / "crates/eval/reports/phase6-baseline-health-check-2026-07-04.json",
        "phase6_performance_profile": root
        / "crates/eval/reports/phase6-performance-profile.json",
        "official_dmr_50": root / "crates/eval/reports/official-dmr-50.json",
        "official_dmr_200": root / "crates/eval/reports/official-dmr-200.json",
        "official_dmr_500": root / "crates/eval/reports/official-dmr-500.json",
        "official_dmr_50_top_context_judge": root
        / "crates/eval/reports/official-dmr-50-top-context-judge.json",
        "official_dmr_200_top_context_judge": root
        / "crates/eval/reports/official-dmr-200-top-context-judge.json",
        "official_dmr_generator_summary": root
        / "crates/eval/reports/official-dmr-generator-ablation-summary.json",
        "official_dmr_bottleneck_taxonomy": root
        / "crates/eval/reports/official-dmr-bottleneck-taxonomy.json",
        "ranking_objective_conflict": root
        / "crates/eval/reports/ranking-objective-conflict-audit.json",
        "ranking_pool_signal_guard": root
        / "crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json",
        "external_comparison_latest": root
        / "crates/eval/reports/external-comparison-latest.json",
        "external_comparison_hosted": root
        / "crates/eval/reports/external-comparison-hosted.json",
        "long_horizon_cognitive_memory": root
        / "crates/eval/reports/long-horizon-cognitive-memory.json",
        "long_horizon_prediction_evidence": root
        / "crates/eval/reports/long-horizon-prediction-evidence-audit.json",
    }

    missing_inputs = [name for name, path in paths.items() if not path.exists()]
    phase6 = load_json(paths["phase6_requirements_audit"])
    readiness = load_json(paths["phase6_next_gate_readiness"])
    official_dmr_task_gate = load_json(paths["official_dmr_task_gate"])
    ranking_task_gate = load_json(paths["ranking_task_gate"])
    external_comparison_task_gate = load_json(paths["external_comparison_task_gate"])
    long_horizon_task_gate = load_json(paths["long_horizon_task_gate"])
    productization_decision_gate = load_json(paths["productization_decision_gate"])
    next_validation_action_gate = load_json(paths["next_validation_action_gate"])
    baseline_health = load_json(paths["phase6_baseline_health"])
    performance = load_json(paths["phase6_performance_profile"])
    dmr_50 = load_json(paths["official_dmr_50"])
    dmr_200 = load_json(paths["official_dmr_200"])
    dmr_500 = load_json(paths["official_dmr_500"])
    generator_summary = load_json(paths["official_dmr_generator_summary"])
    bottleneck = load_json(paths["official_dmr_bottleneck_taxonomy"])
    ranking_conflict = load_json(paths["ranking_objective_conflict"])
    ranking_guard = load_json(paths["ranking_pool_signal_guard"])
    external_latest = load_json(paths["external_comparison_latest"])
    external_hosted = load_json(paths["external_comparison_hosted"])
    long_horizon = load_json(paths["long_horizon_cognitive_memory"])
    long_horizon_evidence = load_json(paths["long_horizon_prediction_evidence"])

    dmr_runs = {
        "dmr_50": dmr_evidence(dmr_50),
        "dmr_200": dmr_evidence(dmr_200),
        "dmr_500_request": dmr_evidence(dmr_500),
    }
    dmr_required_scores = [
        "exact_accuracy",
        "punctuation_accuracy",
        "rouge_l_f1_mean",
        "llm_judge_accuracy",
    ]
    dmr_50_scores_present = all(
        dmr_runs["dmr_50"].get(name) is not None for name in dmr_required_scores
    )
    dmr_200_scores_present = all(
        dmr_runs["dmr_200"].get(name) is not None for name in dmr_required_scores
    )
    all_pinned_dmr_cuda = all(
        run.get("accelerator_requested") == "cuda" and run.get("cuda_device_id") == "0"
        for run in dmr_runs.values()
    )

    external_summary = external_hosted.get("summary", {})
    local_systems = {
        system.get("system"): {
            "status": system.get("status"),
            "metrics": safe_get(system, ["aggregate", "metrics"], {}),
        }
        for system in external_latest.get("systems", [])
    }
    king_metrics = local_systems.get("King Synapse", {}).get("metrics", {})
    trace_metric_names = [
        "hidden_influence_dominant",
        "suppressed_alternatives_visible",
        "evidence_path_available",
        "future_continuation_found",
        "reinforcement_isolated",
    ]
    king_trace_hits = {
        name: safe_get(king_metrics, [name, "hit"]) for name in trace_metric_names
    }
    king_trace_complete = all(hit == 8 for hit in king_trace_hits.values())

    phase_rows = [
        phase(
            phase_id="1_lock_current_version",
            title="Lock Current Version",
            status="policy_active",
            requirements=[
                requirement(
                    item="Use current main as the Phase 6 validation baseline.",
                    status="satisfied",
                    evidence=[
                        report_path(paths["phase6_requirements_audit"]),
                        report_path(paths["phase6_baseline_health"]),
                    ],
                    conclusion=(
                        f"Current branch is {git_value('rev-parse', '--abbrev-ref', 'HEAD')}; "
                        f"latest local health replay is recorded for "
                        f"{baseline_health.get('validated_commit')}."
                    ),
                ),
                requirement(
                    item="Keep feature growth frozen: no memory schema, cognitive layer, or CLI expansion.",
                    status="satisfied",
                    evidence=[report_path(paths["phase6_baseline_health"])],
                    conclusion=(
                        "The latest health replay records memory_schema_changed=false, "
                        "cognitive_layer_changed=false, and cli_feature_changed=false."
                    ),
                ),
                requirement(
                    item="Default heavy validation to CUDA device 0.",
                    status="partial",
                    evidence=[
                        report_path(paths["official_dmr_50"]),
                        report_path(paths["official_dmr_200"]),
                        report_path(paths["official_dmr_500"]),
                        report_path(paths["phase6_performance_profile"]),
                    ],
                    conclusion=(
                        "Pinned official-style DMR runs record accelerator=cuda and "
                        "cuda_device_id=0. This is supported for the current heavy "
                        "DMR evidence, while future heavy reruns still need the same gate."
                    ),
                    remaining=[
                        "Continue requiring --accelerator cuda --cuda-device-id 0 for every future heavy rerun."
                    ],
                ),
                requirement(
                    item="Record every experiment in SYSTEM_VALIDATION_REPORT and EXPERIMENT_LOG.",
                    status="satisfied",
                    evidence=[
                        report_path(paths["system_validation_report"]),
                        report_path(paths["experiment_log"]),
                    ],
                    conclusion="Current audits and replay evidence are logged in the Phase 6 docs.",
                ),
            ],
            conclusion=(
                "The current validation baseline is locked enough for continued Phase 6 work."
            ),
            next_action="Keep feature freeze and continue evidence-only validation.",
        ),
        phase(
            phase_id="2_official_dmr",
            title="Official-Style DMR",
            status="partial",
            requirements=[
                requirement(
                    item="Add answer generation from recalled memory chunks.",
                    status="satisfied",
                    evidence=[
                        report_path(paths["official_dmr_50"]),
                        report_path(paths["official_dmr_result"]),
                    ],
                    conclusion=(
                        "Pinned DMR reports include generator.policy=extractive and "
                        "answer_generation aggregates."
                    ),
                ),
                requirement(
                    item="Score generated answers with exact, punctuation-normalized, ROUGE-L, and LLM judge.",
                    status="satisfied",
                    evidence=[
                        report_path(paths["official_dmr_50"]),
                        report_path(paths["official_dmr_200"]),
                        report_path(paths["official_dmr_500"]),
                    ],
                    conclusion=(
                        "DMR 50 and 200 contain all required scoring surfaces; the "
                        "500-request run contains the same scoring on its 323 mappable samples."
                    ),
                ),
                requirement(
                    item="Run DMR 50, then DMR 200 / 500.",
                    status="partial",
                    evidence=[
                        report_path(paths["official_dmr_50"]),
                        report_path(paths["official_dmr_200"]),
                        report_path(paths["official_dmr_500"]),
                    ],
                    conclusion=(
                        "DMR 50 and 200 are fully selected/scored; DMR 500 is honestly "
                        "a 500-request / 323-scored local view because punctuation mapping "
                        "rejects 177 rows before scoring."
                    ),
                    remaining=[
                        "Do not claim 500/500 coverage under the current punctuation mapping policy."
                    ],
                ),
                requirement(
                    item="Decide whether weakness is retrieval/ranking or answer synthesis.",
                    status="satisfied",
                    evidence=[
                        report_path(paths["official_dmr_bottleneck_taxonomy"]),
                        report_path(paths["official_dmr_generator_summary"]),
                        report_path(paths["official_dmr_task_gate"]),
                    ],
                    conclusion=safe_get(bottleneck, ["read", "conclusion"], ""),
                ),
                requirement(
                    item="Judge-score top-context candidate before making stronger answer-quality claims.",
                    status="partial",
                    evidence=[
                        report_path(paths["official_dmr_50_top_context_judge"]),
                        report_path(paths["official_dmr_200_top_context_judge"]),
                        report_path(paths["official_dmr_task_gate"]),
                    ],
                    conclusion=(
                        "DMR 50 and 200 top-context candidates are now judge-scored; "
                        "the 500-request top-context view remains "
                        "lexical/ROUGE-only."
                    ),
                    remaining=[
                        "Judge-score DMR 500 top-context before broader answer-quality claims."
                    ],
                ),
            ],
            conclusion=(
                "Official-style DMR is executable and judge-backed for the pinned "
                "extractive baseline plus the DMR 50 and 200 top-context candidates, but it "
                "is not published-comparable and the largest candidate view is still "
                "not judge-scored."
            ),
            next_action="If continuing the DMR branch, judge-score DMR 500 top-context next.",
        ),
        phase(
            phase_id="3_ranking_without_architecture_change",
            title="Ranking Without Architecture Change",
            status="validated_no_default",
            requirements=[
                requirement(
                    item="Fix LongMemEval 50 and DMR 50 and classify failures.",
                    status="satisfied",
                    evidence=[
                        report_path(paths["ranking_ablation"]),
                        "crates/eval/reports/ranking-failure-audit-dmr-50.json",
                    ],
                    conclusion=(
                        "DMR 50 and LongMemEval 50 remain the fixed small-sample "
                        "ranking views; DMR failure buckets are recorded."
                    ),
                ),
                requirement(
                    item="Run one-variable ranking tests: RRF, vector weight, reranker pool, top-k, chunk, query expansion.",
                    status="satisfied",
                    evidence=[
                        report_path(paths["ranking_objective_conflict"]),
                        report_path(paths["ranking_pool_signal_guard"]),
                    ],
                    conclusion=(
                        "Current reports cover the named one-variable ranking families "
                        "and consolidate their conflicts/tradeoffs."
                    ),
                ),
                requirement(
                    item="Do not set a default if a parameter helps one dataset and hurts another.",
                    status="satisfied",
                    evidence=[report_path(paths["ranking_objective_conflict"])],
                    conclusion=safe_get(ranking_conflict, ["read", "conclusion"], ""),
                ),
                requirement(
                    item="Find a safe global ranking default.",
                    status="not_ready",
                    evidence=[
                        report_path(paths["ranking_objective_conflict"]),
                        report_path(paths["ranking_pool_signal_guard"]),
                        report_path(paths["ranking_task_gate"]),
                    ],
                    conclusion=safe_get(
                        ranking_task_gate,
                        ["read", "current_conclusion"],
                        "No safe global runtime ranking default is ready.",
                    ),
                    remaining=[
                        "Need a new answer-free ordering signal or an explicit DMR/LongMemEval objective split."
                    ],
                ),
            ],
            conclusion=(
                "Ranking is a validated bottleneck, but no runtime default change is supported."
            ),
            next_action=safe_get(ranking_conflict, ["read", "next_ranking_gate"], ""),
        ),
        phase(
            phase_id="4_external_fair_comparison",
            title="External Fair Comparison",
            status="blocked_external",
            requirements=[
                requirement(
                    item="Use the same cognitive fixture and mark unsupported separately from errors.",
                    status="satisfied",
                    evidence=[report_path(paths["external_comparison_latest"])],
                    conclusion=(
                        "The local comparison report records hit, unsupported, "
                        "not_configured, and failed counts separately."
                    ),
                ),
                requirement(
                    item="Check Synapse trace capabilities against measured adapters.",
                    status="partial",
                    evidence=[
                        report_path(paths["external_comparison_latest"]),
                        report_path(paths["external_validation"]),
                    ],
                    conclusion=(
                        "King Synapse records 8/8 local hits for dominant trace, "
                        "suppressed alternatives, evidence paths, future continuation, "
                        "and reinforcement isolation in the shared fixture."
                    ),
                    remaining=[
                        "Local adapter evidence is not the same as hosted Graphiti/Zep, official Mem0, or live Letta."
                    ],
                ),
                requirement(
                    item="Run Letta endpoint, hosted/standard Graphiti/Zep, and official Mem0.",
                    status="blocked_external",
                    evidence=[
                        report_path(paths["external_comparison_hosted"]),
                        report_path(paths["phase6_next_gate_readiness"]),
                        report_path(paths["external_comparison_task_gate"]),
                    ],
                    conclusion=(
                        f"Hosted report has measured_systems={external_summary.get('measured_systems')} "
                        f"and not_configured_systems={external_summary.get('not_configured_systems')}."
                    ),
                    remaining=[
                        "Configure Graphiti/Zep Neo4j/OpenAI credentials.",
                        "Configure official Mem0 embedding/config.",
                        "Configure Letta API/base URL or LETTA_ENVIRONMENT=local.",
                    ],
                ),
            ],
            conclusion=(
                "The local cognitive-trace comparison is useful but hosted/official fairness is still blocked."
            ),
            next_action="Provide hosted competitor credentials/endpoints, then rerun the shared fixture.",
        ),
        phase(
            phase_id="5_long_horizon_stability",
            title="Long-Horizon Stability",
            status="partial",
            requirements=[
                requirement(
                    item="Construct multi-day memory data and test old/new memory influence.",
                    status="satisfied",
                    evidence=[
                        report_path(paths["long_horizon_validation"]),
                        report_path(paths["long_horizon_cognitive_memory"]),
                    ],
                    conclusion=(
                        "The deterministic long-horizon fixture records fixed metrics "
                        "at 1.000 for RecallAt10, HebbianConsistency, and CognitiveTraceDominance."
                    ),
                ),
                requirement(
                    item="Trace hidden influence and reinforcement drift over time.",
                    status="satisfied",
                    evidence=[report_path(paths["long_horizon_prediction_evidence"])],
                    conclusion=(
                        "Candidate presence remains 8/8 and the evidence audit localizes "
                        "the two misses to target-side context overlap."
                    ),
                ),
                requirement(
                    item="Prove real-world/public long-memory stability.",
                    status="partial",
                    evidence=[report_path(paths["phase6_requirements_audit"])],
                    conclusion=safe_get(long_horizon_task_gate, ["read", "current_conclusion"], ""),
                    remaining=["Add broader long-memory evidence only as validation work."],
                ),
            ],
            conclusion=(
                "The time-network thesis is supported in the deterministic fixture, "
                "with future matched-evidence labeling still the weak surface."
            ),
            next_action="Keep the regression gate fixed and broaden only after current gates are clean.",
        ),
        phase(
            phase_id="6_productization_decision",
            title="Productization Decision",
            status="not_ready",
            requirements=[
                requirement(
                    item="Know what Synapse is clearly strong at.",
                    status="partial",
                    evidence=[
                        report_path(paths["external_comparison_latest"]),
                        report_path(paths["system_validation_report"]),
                        report_path(paths["productization_decision_gate"]),
                    ],
                    conclusion=(
                        "Strongest supported claim is cognitive-trace introspection in local fixtures."
                    ),
                ),
                requirement(
                    item="Know where it is weaker than Mem0 / Graphiti / Zep.",
                    status="blocked_external",
                    evidence=[report_path(paths["external_comparison_hosted"])],
                    conclusion=safe_get(
                        external_comparison_task_gate,
                        ["read", "current_conclusion"],
                        "Hosted competitor measurements are not configured yet.",
                    ),
                ),
                requirement(
                    item="Know which capabilities others do not expose.",
                    status="partial",
                    evidence=[report_path(paths["external_comparison_latest"])],
                    conclusion=(
                        "Local comparison supports dominant trace, suppressed alternatives, "
                        "future continuation, and reinforcement isolation as differentiators."
                    ),
                ),
                requirement(
                    item="Decide whether GPU cost is acceptable.",
                    status="partial",
                    evidence=[
                        report_path(paths["phase6_performance_profile"]),
                        report_path(paths["performance_analysis"]),
                        report_path(paths["productization_decision_gate"]),
                    ],
                    conclusion=(
                        "GPU memory and reranker latency are measured, but no product "
                        "acceptance threshold has been adopted."
                    ),
                ),
                requirement(
                    item="Ensure official DMR supports README claims.",
                    status="not_ready",
                    evidence=[
                        report_path(paths["official_dmr_result"]),
                        report_path(paths["phase6_requirements_audit"]),
                        report_path(paths["official_dmr_task_gate"]),
                    ],
                    conclusion=(
                        "Pinned official-style DMR exists, but answer quality is low, "
                        "mapping coverage is partial, and top-context DMR 500 is not judge-scored."
                    ),
                ),
                requirement(
                    item="Have a stable demo before web/API/Docker/release work.",
                    status="not_ready",
                    evidence=[
                        report_path(paths["phase6_requirements_audit"]),
                        report_path(paths["productization_decision_gate"]),
                        report_path(paths["next_validation_action_gate"]),
                    ],
                    conclusion=safe_get(productization_decision_gate, ["read", "current_conclusion"], ""),
                ),
                requirement(
                    item=(
                        "Select the next heavy validation action only when external "
                        "preconditions are ready."
                    ),
                    status="blocked_external",
                    evidence=[
                        report_path(paths["phase6_next_gate_readiness"]),
                        report_path(paths["next_validation_action_gate"]),
                    ],
                    conclusion=safe_get(next_validation_action_gate, ["read", "current_conclusion"], ""),
                    remaining=[
                        "Select the next DMR expansion scope or configure hosted competitor comparison."
                    ],
                ),
            ],
            conclusion="Productization remains premature.",
            next_action="Do not start web demo, API server, Docker, release packaging, or v0.1; follow the next-action gate and wait for external preconditions.",
        ),
    ]

    statuses = Counter()
    for row in phase_rows:
        statuses[row["status"]] += 1
        for item in row["requirements"]:
            statuses[item["status"]] += 1

    current_branch = git_value("rev-parse", "--abbrev-ref", "HEAD")
    current_commit = git_value("rev-parse", "HEAD")
    origin_delta = git_value("rev-list", "--left-right", "--count", "origin/main...HEAD")

    return {
        "schema_version": "king-synapse.phase6-objective-coverage-audit.v1",
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
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "phase_coverage": phase_rows,
        "key_metrics": {
            "dmr_runs": dmr_runs,
            "dmr_required_scores_present": {
                "dmr_50": dmr_50_scores_present,
                "dmr_200": dmr_200_scores_present,
                "dmr_500_request": all(
                    dmr_runs["dmr_500_request"].get(name) is not None
                    for name in dmr_required_scores
                ),
            },
            "pinned_official_dmr_cuda_device_0": all_pinned_dmr_cuda,
            "top_context_judge_ready": safe_get(readiness, ["top_context_judge", "ready"]),
            "hosted_external_ready": safe_get(readiness, ["hosted_external", "ready"]),
            "official_dmr_task_gate_status": official_dmr_task_gate["status"],
            "ranking_task_gate_status": ranking_task_gate["status"],
            "external_comparison_task_gate_status": external_comparison_task_gate["status"],
            "long_horizon_task_gate_status": long_horizon_task_gate["status"],
            "productization_decision_gate_status": productization_decision_gate["status"],
            "next_validation_action_gate_status": next_validation_action_gate["status"],
            "ranking_global_default_candidate": safe_get(
                ranking_conflict, ["read", "global_default_candidate"]
            ),
            "ranking_best_safe_guard_id": safe_get(
                ranking_guard, ["read", "best_safe_guard_id"]
            ),
            "external_local_synapse_trace_hits": king_trace_hits,
            "external_local_synapse_trace_complete": king_trace_complete,
            "external_hosted_summary": external_summary,
            "long_horizon_metrics": long_horizon.get("metrics", {}),
            "long_horizon_evidence": {
                "candidate_present_all_phases_count": safe_get(
                    long_horizon_evidence, ["aggregate", "candidate_present_all_phases_count"]
                ),
                "matched_evidence_all_phases_count": safe_get(
                    long_horizon_evidence, ["aggregate", "matched_evidence_all_phases_count"]
                ),
                "context_overlap_explains_all_reported_matched_misses": safe_get(
                    long_horizon_evidence,
                    ["aggregate", "context_overlap_explains_all_reported_matched_misses"],
                ),
            },
            "performance_gpu_configuration": performance.get("gpu_configuration", {}),
        },
        "status_counts": dict(statuses),
        "read": {
            "overall": "phase6_validation_in_progress_productization_blocked",
            "strongest_current_result": (
                "Synapse has strong local evidence for inspectable cognitive traces "
                "and executable official-style DMR scoring, but the decisive "
                "published-comparable and hosted-comparison gates are still open."
            ),
            "most_important_open_gates": [
                "top_context_500_not_judge_scored",
                "hosted_external_comparison_not_configured",
                "published_comparable_dmr_mapping_policy_not_final",
                "no_safe_global_ranking_default",
                "future_evidence_labeling_boundary",
                "public_real_world_long_memory_not_validated",
                "next_validation_action_waiting_on_hosted_or_dmr_expansion_scope",
                "productization_not_ready",
            ],
            "next_action": (
                "Keep feature freeze. DMR 50 and 200 top-context judge scoring are complete; "
                "the next validation action is to select DMR 500 top-context "
                "expansion or wait for hosted competitor credentials/endpoints."
            ),
        },
        "limits": [
            "This report is a coverage audit over existing evidence only.",
            "It does not run retrieval, generation, judging, hosted adapters, or product code.",
            "It should not be used as a product-readiness claim.",
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
                "overall": report["read"]["overall"],
                "status_counts": report["status_counts"],
                "most_important_open_gates": report["read"]["most_important_open_gates"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
