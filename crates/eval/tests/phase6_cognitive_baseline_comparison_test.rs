use std::{collections::BTreeSet, sync::OnceLock};

use synapse_eval::{
    Phase6CognitiveBaselineComparisonEvaluator, Phase6CognitiveBaselineComparisonReport,
};

const EPSILON: f64 = 1e-12;

fn report() -> &'static Phase6CognitiveBaselineComparisonReport {
    static REPORT: OnceLock<Phase6CognitiveBaselineComparisonReport> = OnceLock::new();
    REPORT.get_or_init(|| {
        Phase6CognitiveBaselineComparisonEvaluator::evaluate("phase6.1-test")
            .expect("Phase 6.1 comparison report")
    })
}

#[test]
fn comparison_reuses_frozen_phase6_workload() {
    let report = report();
    assert!(report.pass);
    assert_eq!(report.dataset.scenarios, 320);
    assert_eq!(report.dataset.memories, 1920);
    assert_eq!(report.dataset.categories, 10);
    assert_eq!(report.dataset.split_counts.get("train"), Some(&160));
    assert_eq!(report.dataset.split_counts.get("validation"), Some(&80));
    assert_eq!(report.dataset.split_counts.get("test"), Some(&80));
}

#[test]
fn exactly_six_requested_policies_use_locked_authority_parameters() {
    let report = report();
    let names = report
        .policies
        .iter()
        .map(|policy| policy.policy.as_str())
        .collect::<BTreeSet<_>>();
    assert_eq!(report.policies.len(), 6);
    assert_eq!(
        names,
        BTreeSet::from([
            "retrieval_baseline",
            "confidence_only_margin_guarded",
            "recency_only_margin_guarded",
            "failure_only_margin_guarded",
            "simple_combined_margin_guarded",
            "margin_guard_cognitive",
        ])
    );
    assert!((report.protocol.policy_alpha - 0.20).abs() <= EPSILON);
    assert!((report.protocol.margin_threshold - 0.08).abs() <= EPSILON);
    for policy in &report.policies {
        if policy.policy == "retrieval_baseline" {
            assert_eq!(policy.alpha, None);
            assert_eq!(policy.margin_threshold, None);
        } else {
            assert_eq!(policy.alpha, Some(0.20));
            assert_eq!(policy.margin_threshold, Some(0.08));
        }
    }
}

#[test]
fn all_policies_are_deterministic_shadow_comparisons_over_the_same_pool() {
    for policy in &report().policies {
        assert_eq!(policy.metrics.scenarios, 320);
        assert_eq!(policy.metrics.expected_candidate_retrieval_rate, 1.0);
        assert_eq!(policy.metrics.determinism, 1.0);
        assert!(policy.candidate_pool_preserved);
        assert!(!policy.runtime_applied);
        assert!(policy.scenarios.iter().all(|scenario| {
            scenario.candidate_pool_preserved
                && scenario.deterministic
                && !scenario.runtime_applied
                && scenario
                    .baseline_ranking
                    .iter()
                    .cloned()
                    .collect::<BTreeSet<_>>()
                    == scenario
                        .policy_ranking
                        .iter()
                        .cloned()
                        .collect::<BTreeSet<_>>()
        }));
    }
}

#[test]
fn factor_ablation_removes_each_requested_factor_without_changing_policy_parameters() {
    let report = report();
    let names = report
        .factor_ablations
        .iter()
        .map(|ablation| ablation.ablation.as_str())
        .collect::<BTreeSet<_>>();
    assert_eq!(report.factor_ablations.len(), 6);
    assert_eq!(
        names,
        BTreeSet::from([
            "full_cognitive",
            "without_temporal",
            "without_failure",
            "without_reliability",
            "without_preference",
            "without_context",
        ])
    );
    for ablation in &report.factor_ablations {
        assert_eq!(ablation.alpha, 0.20);
        assert_eq!(ablation.margin_threshold, 0.08);
        assert_eq!(ablation.metrics.determinism, 1.0);
        assert!(ablation.candidate_pool_preserved);
        assert!(!ablation.runtime_applied);
    }
}

#[test]
fn independent_gain_is_computed_against_the_actual_best_simple_baseline() {
    let report = report();
    let decision = &report.decision;
    let best = report
        .policies
        .iter()
        .filter(|policy| {
            matches!(
                policy.policy.as_str(),
                "confidence_only_margin_guarded"
                    | "recency_only_margin_guarded"
                    | "failure_only_margin_guarded"
                    | "simple_combined_margin_guarded"
            )
        })
        .max_by(|left, right| {
            left.metrics
                .mrr_at_5
                .total_cmp(&right.metrics.mrr_at_5)
                .then_with(|| {
                    left.metrics
                        .recall_at_1
                        .total_cmp(&right.metrics.recall_at_1)
                })
        })
        .expect("best simple baseline");
    assert_eq!(decision.best_simple_baseline, best.policy);
    assert!(
        (decision.cognitive_gain_vs_best_simple_baseline
            - (decision.cognitive_mrr_at_5 - best.metrics.mrr_at_5))
            .abs()
            <= EPSILON
    );
    assert!(
        (decision.cognitive_recall_at_1_gain_vs_best_simple_baseline
            - (decision.cognitive_recall_at_1 - best.metrics.recall_at_1))
            .abs()
            <= EPSILON
    );
}

#[test]
fn observed_equal_result_is_reported_without_overclaiming_attribution() {
    let decision = &report().decision;
    assert_eq!(decision.outcome, "B_cognitive_matches_best_simple");
    assert!(decision.cognitive_matches_best_simple);
    assert!(!decision.cognitive_exceeds_best_simple);
    assert!(!decision.independent_value_supported);
    assert!(decision.zero_intervention_authority);
    assert!(!decision.attribution_resolved);
    assert!(!decision.metadata_aggregation_only);
    assert!(decision.contributing_factors.is_empty());
    assert!(!decision.hermes_shadow_integration_recommended);
    assert!(!decision.runtime_authorization);
    assert!(!decision.production_claim_authorized);
}

#[test]
fn fresh_evaluation_reproduces_policy_rankings_and_metrics() {
    let replay = Phase6CognitiveBaselineComparisonEvaluator::evaluate("phase6.1-replay")
        .expect("fresh Phase 6.1 replay");
    assert_eq!(replay.policies.len(), report().policies.len());
    for (left, right) in report().policies.iter().zip(&replay.policies) {
        assert_eq!(left.policy, right.policy);
        assert_eq!(left.metrics.recall_at_1, right.metrics.recall_at_1);
        assert_eq!(left.metrics.recall_at_3, right.metrics.recall_at_3);
        assert_eq!(left.metrics.mrr_at_5, right.metrics.mrr_at_5);
        assert_eq!(left.metrics.ndcg_at_5, right.metrics.ndcg_at_5);
        assert_eq!(
            left.scenarios
                .iter()
                .map(|scenario| &scenario.policy_ranking)
                .collect::<Vec<_>>(),
            right
                .scenarios
                .iter()
                .map(|scenario| &scenario.policy_ranking)
                .collect::<Vec<_>>()
        );
    }
}

#[test]
fn safety_guards_keep_runtime_and_storage_untouched() {
    let guards = &report().guards;
    assert!(guards.eval_only);
    assert!(guards.shadow_only);
    assert!(guards.baseline_authoritative);
    assert!(guards.real_recall_engine_used);
    assert!(!guards.artificial_baseline_scores_used);
    assert!(!guards.recall_engine_modified);
    assert!(!guards.candidate_generation_modified);
    assert!(!guards.retrieval_scores_mutated);
    assert!(!guards.candidate_pool_changed);
    assert!(!guards.policy_memory_written);
    assert!(!guards.memory_mutated);
    assert!(!guards.memory_schema_changed);
    assert!(!guards.runtime_applied);
    assert!(!guards.runtime_booster_registered);
    assert!(!guards.runtime_authorization);
    assert!(!guards.production_claim_authorized);
}

#[test]
fn checked_in_report_preserves_the_phase6_1_claim_boundary() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("reports/phase6_cognitive_baseline_comparison.json");
    let value: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(path).expect("checked-in Phase 6.1 report"))
            .expect("valid report JSON");
    assert_eq!(value["schema_version"], 1);
    assert_eq!(
        value["phase"],
        "Phase 6.1 Cognitive vs Simple Baseline Evaluation"
    );
    assert_eq!(value["pass"], true);
    assert_eq!(
        value["decision"]["outcome"],
        "B_cognitive_matches_best_simple"
    );
    assert_eq!(value["decision"]["attribution_resolved"], false);
    assert_eq!(
        value["decision"]["hermes_shadow_integration_recommended"],
        false
    );
    assert_eq!(value["decision"]["runtime_authorization"], false);
    assert_eq!(value["guards"]["runtime_applied"], false);
    assert_eq!(value["guards"]["production_claim_authorized"], false);
}
