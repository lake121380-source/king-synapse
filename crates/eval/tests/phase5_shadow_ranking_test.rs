use std::path::Path;
use synapse_eval::Phase5ShadowRankingEvaluator;

fn evaluate(tag: &str) -> synapse_eval::Phase5ShadowRankingReport {
    Phase5ShadowRankingEvaluator::evaluate(tag)
        .expect("Phase 5.3.2 shadow ranking evaluation should run")
}

#[test]
fn phase5_shadow_ranking_quality_gate_passes() {
    let report = evaluate("phase5-3-2-quality-gate");

    assert!(report.pass);
    assert_eq!(report.status, "PASS");
    assert_eq!(report.metrics.bounded_rate, 1.0);
    assert_eq!(report.metrics.determinism, 1.0);
}

#[test]
fn shadow_bonus_never_exceeds_absolute_cap() {
    let report = evaluate("phase5-3-2-bounds");

    assert!(report.metrics.max_proposed_bonus <= report.max_bonus);
    assert!(report.scenario_reports.iter().all(|scenario| {
        scenario.candidates.iter().all(|candidate| {
            candidate.proposed_bonus >= 0.0 && candidate.proposed_bonus <= report.max_bonus
        })
    }));
}

#[test]
fn baseline_ranking_scores_activation_and_memory_are_unchanged() {
    let report = evaluate("phase5-3-2-no-mutation");

    assert!(report.scenario_reports.iter().all(|scenario| {
        scenario.baseline_ranking_unchanged
            && scenario.baseline_scores_unchanged
            && scenario.activation_unchanged
            && scenario.memory_unchanged
    }));
    assert!(!report.guards.ranking_mutated);
    assert!(!report.guards.scores_mutated);
    assert!(!report.guards.activation_changed);
    assert!(!report.guards.memory_mutated);
}

#[test]
fn shadow_ranking_preserves_candidate_pool() {
    let report = evaluate("phase5-3-2-pool");

    assert!(!report.guards.candidate_pool_changed);
    assert!(report.scenario_reports.iter().all(|scenario| {
        scenario.candidate_pool_preserved
            && scenario.baseline_ranking.len() == scenario.shadow_ranking.len()
    }));
}

#[test]
fn shadow_ranking_is_deterministic() {
    let report = evaluate("phase5-3-2-determinism");

    assert_eq!(report.metrics.determinism, 1.0);
    assert!(report
        .scenario_reports
        .iter()
        .all(|scenario| scenario.deterministic));
}

#[test]
fn fresh_fixture_runs_preserve_quality_metrics() {
    let first = evaluate("phase5-3-2-fresh-run-a");
    let second = evaluate("phase5-3-2-fresh-run-b");

    assert_eq!(
        first.metrics.proposal_coverage,
        second.metrics.proposal_coverage
    );
    assert_eq!(
        first.metrics.changed_positions,
        second.metrics.changed_positions
    );
    assert_eq!(
        first.metrics.avg_abs_rank_delta,
        second.metrics.avg_abs_rank_delta
    );
    assert_eq!(
        first.metrics.max_abs_rank_delta,
        second.metrics.max_abs_rank_delta
    );
    assert_eq!(
        first.metrics.max_proposed_bonus,
        second.metrics.max_proposed_bonus
    );
    assert_eq!(first.metrics.bounded_rate, second.metrics.bounded_rate);
    assert_eq!(
        first.metrics.baseline_recall_at_k,
        second.metrics.baseline_recall_at_k
    );
    assert_eq!(
        first.metrics.shadow_recall_at_k,
        second.metrics.shadow_recall_at_k
    );
    assert_eq!(first.metrics.baseline_mrr, second.metrics.baseline_mrr);
    assert_eq!(first.metrics.shadow_mrr, second.metrics.shadow_mrr);
}

#[test]
fn runtime_and_storage_authority_remain_disabled() {
    let report = evaluate("phase5-3-2-safety");

    assert!(report.guards.eval_only);
    assert!(report.guards.shadow_only);
    assert!(report.guards.baseline_authoritative);
    assert!(!report.guards.runtime_applied);
    assert!(!report.guards.memory_written);
    assert!(!report.guards.recall_engine_integrated);
    assert!(!report.guards.production_claim_authorized);
    assert!(report.scenario_reports.iter().all(|scenario| {
        !scenario.runtime_applied
            && !scenario.memory_mutated
            && scenario
                .candidates
                .iter()
                .all(|candidate| !candidate.runtime_applied)
    }));
}

#[test]
fn offline_quality_deltas_are_reported_without_positive_requirement() {
    let report = evaluate("phase5-3-2-offline-delta");

    assert!((0.0..=1.0).contains(&report.metrics.baseline_recall_at_k));
    assert!((0.0..=1.0).contains(&report.metrics.shadow_recall_at_k));
    assert!((0.0..=1.0).contains(&report.metrics.baseline_mrr));
    assert!((0.0..=1.0).contains(&report.metrics.shadow_mrr));
    assert_eq!(
        report.metrics.shadow_recall_delta,
        report.metrics.shadow_recall_at_k - report.metrics.baseline_recall_at_k
    );
    assert_eq!(
        report.metrics.shadow_mrr_delta,
        report.metrics.shadow_mrr - report.metrics.baseline_mrr
    );
}

#[test]
fn position_delta_sign_is_consistent() {
    let report = evaluate("phase5-3-2-position-delta");

    assert!(report.scenario_reports.iter().all(|scenario| {
        scenario.candidates.iter().all(|candidate| {
            candidate.position_delta
                == candidate.baseline_rank as i64 - candidate.shadow_rank as i64
        })
    }));
}

#[test]
fn phase5_shadow_report_schema_is_stable() {
    let report = evaluate("phase5-3-2-schema");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "schema_version",
        "phase",
        "mode",
        "algorithm",
        "evaluation_version",
        "baseline_version",
        "metric_cutoff",
        "candidate_limit",
        "max_bonus",
        "metrics",
        "guards",
        "latency",
        "pass",
        "status",
        "conclusion",
        "scenario_reports",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    for metric in [
        "proposal_coverage",
        "changed_positions",
        "avg_abs_rank_delta",
        "max_abs_rank_delta",
        "max_proposed_bonus",
        "bounded_rate",
        "determinism",
        "baseline_recall_at_k",
        "shadow_recall_at_k",
        "shadow_recall_delta",
        "baseline_mrr",
        "shadow_mrr",
        "shadow_mrr_delta",
    ] {
        assert!(
            value["metrics"].get(metric).is_some(),
            "missing metric {metric}"
        );
    }
}

#[test]
fn committed_phase5_shadow_report_loads_and_passes() {
    let report_path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase5_shadow_ranking.json");
    let report: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(report_path).expect("committed Phase 5.3.2 report should load"),
    )
    .expect("committed Phase 5.3.2 report should be valid JSON");

    assert_eq!(report["phase"], "5.3.2");
    assert_eq!(report["mode"], "offline_shadow_ranking");
    assert_eq!(report["pass"], true);
    assert_eq!(report["metrics"]["bounded_rate"], 1.0);
    assert_eq!(report["metrics"]["determinism"], 1.0);
    assert_eq!(report["guards"]["runtime_applied"], false);
}
