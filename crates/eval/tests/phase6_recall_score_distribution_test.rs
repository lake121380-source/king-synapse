use serde_json::Value;
use std::{fs, path::PathBuf, sync::OnceLock};
use synapse_eval::{Phase6RecallScoreDistributionEvaluator, Phase6RecallScoreDistributionReport};

const EPSILON: f64 = 1e-9;

fn fresh_report() -> &'static Phase6RecallScoreDistributionReport {
    static REPORT: OnceLock<Phase6RecallScoreDistributionReport> = OnceLock::new();
    REPORT.get_or_init(|| {
        Phase6RecallScoreDistributionEvaluator::evaluate("phase6.2-test")
            .expect("Phase 6.2 evaluation")
    })
}

fn checked_report_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("reports/phase6_recall_score_distribution.json")
}

#[test]
fn study_reuses_the_frozen_real_recall_workload() {
    let report = fresh_report();
    assert_eq!(report.dataset.scenarios, 320);
    assert_eq!(report.dataset.memories, 1920);
    assert_eq!(report.dataset.categories, 10);
    assert!(report.guards.real_recall_engine_used);
    assert!(report.guards.source_phase6_benchmark_passed);
    assert_eq!(
        report.protocol.retrieval_mode,
        "real_recall_engine_fts_entity_no_vectors_no_reranker"
    );
}

#[test]
fn candidate_count_and_score_distributions_are_complete() {
    let report = fresh_report();
    assert_eq!(report.candidate_count.scenarios, 320);
    assert_eq!(report.candidate_count.histogram.get(&5), Some(&320));
    assert_eq!(report.candidate_count.summary.count, 320);
    assert!((report.candidate_count.summary.mean - 5.0).abs() <= EPSILON);
    assert_eq!(report.score_distribution.all_candidates.count, 1600);
    assert_eq!(report.score_distribution.by_rank.len(), 5);
    assert!(report
        .score_distribution
        .by_rank
        .iter()
        .all(|rank| rank.summary.count == 320));
}

#[test]
fn adjacent_gap_statistics_cover_every_observed_rank_pair() {
    let report = fresh_report();
    assert_eq!(report.adjacent_gaps.len(), 4);
    for (index, gap) in report.adjacent_gaps.iter().enumerate() {
        assert_eq!(gap.left_rank, index + 1);
        assert_eq!(gap.right_rank, index + 2);
        assert_eq!(gap.raw_gap.count, 320);
        assert_eq!(gap.adjacent_normalized_gap.count, 320);
        assert_eq!(gap.top_relative_gap.count, 320);
        assert!(gap.raw_gap.min >= 0.0);
        assert!(gap.adjacent_normalized_gap.min >= 0.0);
    }
}

#[test]
fn distribution_quantiles_are_ordered_and_finite() {
    let report = fresh_report();
    let summaries = report
        .adjacent_gaps
        .iter()
        .flat_map(|gap| {
            [
                &gap.raw_gap,
                &gap.adjacent_normalized_gap,
                &gap.top_relative_gap,
            ]
        })
        .chain(std::iter::once(&report.score_distribution.all_candidates));
    for summary in summaries {
        assert!(summary.min.is_finite());
        assert!(summary.max.is_finite());
        assert!(summary.mean.is_finite());
        assert!(summary.min <= summary.p50 + EPSILON);
        assert!(summary.p50 <= summary.p90 + EPSILON);
        assert!(summary.p90 <= summary.p95 + EPSILON);
        assert!(summary.p95 <= summary.p99 + EPSILON);
        assert!(summary.p99 <= summary.max + EPSILON);
        assert!((summary.median - summary.p50).abs() <= EPSILON);
    }
}

#[test]
fn requested_margin_coverage_is_descriptive_and_monotonic() {
    let report = fresh_report();
    let expected = [0.01, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20];
    assert_eq!(report.margin_coverage.len(), expected.len());
    for (coverage, expected_threshold) in report.margin_coverage.iter().zip(expected) {
        assert!((coverage.threshold - expected_threshold).abs() <= EPSILON);
        assert_eq!(coverage.scenarios, 320);
        assert!((0.0..=1.0).contains(&coverage.eligible_rate));
    }
    assert!(report
        .margin_coverage
        .windows(2)
        .all(|window| window[0].eligible_scenarios <= window[1].eligible_scenarios));
    assert_eq!(
        report.protocol.threshold_policy,
        "descriptive_only_no_threshold_selection_or_tuning"
    );
    assert!(!report.decision.threshold_selection_performed);
    assert!(!report.decision.margin_redesign_authorized);
}

#[test]
fn locked_margin_has_zero_authority_on_the_frozen_workload() {
    let report = fresh_report();
    let locked = report
        .margin_coverage
        .iter()
        .find(|coverage| coverage.is_locked_margin)
        .expect("locked margin coverage");
    assert!((locked.threshold - 0.08).abs() <= EPSILON);
    assert_eq!(locked.eligible_scenarios, 0);
    assert!(locked.eligible_rate.abs() <= EPSILON);
    assert!(report.decision.observed_minimum_top1_top2_normalized_gap > 0.08);
    assert!(report.decision.current_margin_below_observed_minimum_gap);
    assert!(!report.decision.current_margin_has_authority);
    assert!(report
        .scenarios
        .iter()
        .all(|scenario| !scenario.locked_margin_triggered));
}

#[test]
fn no_algorithm_ranking_or_runtime_boundary_is_crossed() {
    let report = fresh_report();
    assert!(report.pass);
    assert!(report.guards.eval_only);
    assert!(report.guards.distribution_study_only);
    assert!(!report.guards.recall_engine_modified);
    assert!(!report.guards.cognitive_booster_modified);
    assert!(!report.guards.cognitive_algorithm_executed);
    assert!(!report.guards.threshold_modified);
    assert!(!report.guards.alpha_modified);
    assert!(!report.guards.ranking_modified);
    assert!(!report.guards.retrieval_scores_mutated);
    assert!(!report.guards.candidate_generation_modified);
    assert!(!report.guards.memory_written);
    assert!(!report.guards.memory_mutated);
    assert!(!report.guards.runtime_applied);
    assert!(!report.guards.hermes_integration_performed);
    assert!(!report.guards.runtime_authorization);
    assert!(!report.decision.cognitive_value_evaluated);
    assert!(!report.decision.cognitive_failure_inferred);
    assert!(!report.decision.hermes_shadow_integration_recommended);
}

#[test]
fn checked_report_preserves_claim_and_safety_boundaries() {
    let source = fs::read_to_string(checked_report_path()).expect("checked Phase 6.2 report");
    let value: Value = serde_json::from_str(&source).expect("valid Phase 6.2 JSON");
    assert_eq!(value["status"], "PASS");
    assert_eq!(value["dataset"]["scenarios"], 320);
    assert_eq!(value["protocol"]["locked_margin_threshold"], 0.08);
    assert_eq!(value["protocol"]["locked_policy_alpha"], 0.20);
    assert_eq!(value["decision"]["locked_margin_eligible_scenarios"], 0);
    assert_eq!(value["decision"]["threshold_selection_performed"], false);
    assert_eq!(value["decision"]["cognitive_value_evaluated"], false);
    assert_eq!(
        value["decision"]["hermes_shadow_integration_recommended"],
        false
    );
    assert_eq!(value["guards"]["runtime_applied"], false);
    assert_eq!(value["guards"]["production_claim_authorized"], false);
}

#[test]
fn fresh_evaluation_reproduces_checked_coverage_and_distribution_shape() {
    let fresh = fresh_report();
    let source = fs::read_to_string(checked_report_path()).expect("checked Phase 6.2 report");
    let checked: Value = serde_json::from_str(&source).expect("valid Phase 6.2 JSON");
    let checked_coverages = checked["margin_coverage"]
        .as_array()
        .expect("coverage array");
    assert_eq!(checked_coverages.len(), fresh.margin_coverage.len());
    for (value, current) in checked_coverages.iter().zip(&fresh.margin_coverage) {
        assert_eq!(
            value["eligible_scenarios"].as_u64(),
            Some(current.eligible_scenarios as u64)
        );
    }
    assert_eq!(
        checked["candidate_count"]["histogram"]["5"].as_u64(),
        Some(320)
    );
    let checked_min = checked["decision"]["observed_minimum_top1_top2_normalized_gap"]
        .as_f64()
        .expect("checked minimum gap");
    assert!((checked_min - fresh.decision.observed_minimum_top1_top2_normalized_gap).abs() <= 1e-3);
}
