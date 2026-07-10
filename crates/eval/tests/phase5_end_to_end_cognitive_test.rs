use std::sync::OnceLock;
use synapse_eval::{
    load_phase5_end_to_end_workload, EndToEndPolicyResult, Phase5EndToEndCognitiveEvaluator,
    Phase5EndToEndReport,
};

fn report() -> &'static Phase5EndToEndReport {
    static REPORT: OnceLock<Phase5EndToEndReport> = OnceLock::new();
    REPORT.get_or_init(|| {
        Phase5EndToEndCognitiveEvaluator::evaluate("phase5-end-to-end-test")
            .expect("Phase 5.4 report")
    })
}

fn policy(family: &str) -> &'static EndToEndPolicyResult {
    report()
        .policies
        .iter()
        .find(|policy| policy.family == family)
        .expect("policy family")
}

#[test]
fn workload_has_real_retrieval_inputs_without_manual_scores() {
    let scenarios = load_phase5_end_to_end_workload().expect("workload");
    assert_eq!(scenarios.len(), 24);
    assert!(scenarios.iter().all(|scenario| scenario.memory.len() == 6));
    let raw = std::fs::read_to_string(
        std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("datasets/cognitive_end_to_end/agent_workload.toml"),
    )
    .expect("dataset text");
    assert!(!raw.contains("baseline_score"));
}

#[test]
fn recall_engine_retrieves_expected_candidates() {
    let report = report();
    assert!(report.guards.real_recall_engine_used);
    assert!(!report.guards.artificial_baseline_scores_used);
    assert_eq!(report.dataset.expected_candidate_retrieval_rate, 1.0);
    assert!(report.dataset.retrieved_candidates > 0);
    for scenario in &policy("retrieval_baseline").scenarios {
        assert!(scenario.expected_retrieved);
        assert!(!scenario.candidates.is_empty());
        assert!(scenario
            .candidates
            .iter()
            .all(|candidate| candidate.baseline_score > 0.0));
        assert!(scenario.candidates.iter().all(|candidate| {
            candidate
                .sources
                .iter()
                .any(|source| source == "fts" || source == "entity")
        }));
        assert_eq!(scenario.retrieval_profile.entity_candidates, 0);
    }
}

#[test]
fn five_locked_policies_share_the_same_candidate_pool() {
    let report = report();
    assert_eq!(report.policies.len(), 5);
    for policy in &report.policies {
        assert!(policy.candidate_pool_preserved);
        assert!(!policy.runtime_applied);
        assert_eq!(policy.metrics.determinism, 1.0);
    }
}

#[test]
fn decision_matches_observed_metrics_without_forcing_positive_gain() {
    let decision = &report().decision;
    let epsilon = 1e-12;
    assert_eq!(
        decision.cognitive_beats_baseline,
        decision.cognitive_mrr_at_5 > decision.baseline_mrr_at_5 + epsilon
    );
    assert_eq!(
        decision.cognitive_beats_confidence,
        decision.cognitive_mrr_at_5 > decision.confidence_mrr_at_5 + epsilon
    );
    assert_eq!(
        decision.cognitive_beats_recency,
        decision.cognitive_mrr_at_5 > decision.recency_mrr_at_5 + epsilon
    );
    assert_eq!(
        decision.cognitive_beats_failure,
        decision.cognitive_mrr_at_5 > decision.failure_mrr_at_5 + epsilon
    );
    assert_eq!(
        decision.independent_end_to_end_value_supported,
        decision.cognitive_beats_baseline
            && decision.cognitive_beats_confidence
            && decision.cognitive_beats_recency
            && decision.cognitive_beats_failure
            && decision.safety_preserved
    );
    assert!(decision.cognitive_beats_baseline);
    assert!(decision.cognitive_beats_confidence);
    assert!(decision.cognitive_matches_best_simple_control);
    assert!(decision.cognitive_delta_vs_best_simple_control.abs() <= epsilon);
    assert!(!decision.independent_end_to_end_value_supported);
    assert!(decision.safety_preserved);
}

#[test]
fn cognitive_policy_preserves_top1_safety_and_silent_correctness() {
    let cognitive = policy("margin_guard_cognitive");
    assert_eq!(cognitive.metrics.top1_regression_rate, 0.0);
    assert_eq!(cognitive.metrics.catastrophic_regression_rate, 0.0);
    assert_eq!(cognitive.metrics.unnecessary_intervention_rate, 0.0);
    assert_eq!(cognitive.metrics.successful_intervention_rate, 1.0);
    assert!(cognitive.metrics.silent_correctness_rate > 0.0);
    assert!(cognitive.metrics.mrr_at_5 > cognitive.metrics.baseline_mrr_at_5);
    assert!(cognitive.metrics.ndcg_at_5 > cognitive.metrics.baseline_ndcg_at_5);
}

#[test]
fn safety_gate_does_not_authorize_runtime() {
    let report = report();
    let guards = &report.guards;
    assert!(report.pass);
    assert!(guards.eval_only);
    assert!(guards.shadow_only);
    assert!(guards.baseline_authoritative);
    assert!(!guards.runtime_applied);
    assert!(!guards.policy_memory_written);
    assert!(!guards.memory_mutated);
    assert!(!guards.ranking_mutated);
    assert!(!guards.scores_mutated);
    assert!(!guards.activation_changed);
    assert!(!guards.candidate_pool_changed);
    assert!(!guards.recall_engine_integrated);
    assert!(!guards.runtime_booster_registered);
    assert!(!guards.production_claim_authorized);
    assert!(!report.decision.runtime_authorization);
}

#[test]
fn fresh_run_reproduces_quality_metrics() {
    let fresh =
        Phase5EndToEndCognitiveEvaluator::evaluate("fresh-end-to-end").expect("fresh report");
    for (left, right) in report().policies.iter().zip(&fresh.policies) {
        assert_eq!(left.family, right.family);
        assert_eq!(left.metrics.recall_at_1, right.metrics.recall_at_1);
        assert_eq!(left.metrics.recall_at_3, right.metrics.recall_at_3);
        assert_eq!(left.metrics.recall_at_5, right.metrics.recall_at_5);
        assert_eq!(left.metrics.mrr_at_5, right.metrics.mrr_at_5);
        assert_eq!(left.metrics.ndcg_at_5, right.metrics.ndcg_at_5);
        assert_eq!(left.metrics.determinism, right.metrics.determinism);
        assert_eq!(
            left.metrics.catastrophic_regression_rate,
            right.metrics.catastrophic_regression_rate
        );
        for (left_scenario, right_scenario) in left.scenarios.iter().zip(&right.scenarios) {
            assert_eq!(left_scenario.id, right_scenario.id);
            assert_eq!(
                left_scenario.baseline_ranking,
                right_scenario.baseline_ranking
            );
            assert_eq!(left_scenario.policy_ranking, right_scenario.policy_ranking);
        }
    }
}

#[test]
fn checked_in_report_keeps_claim_boundary_explicit() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("reports/phase5_end_to_end_cognitive.json");
    let value: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(path).expect("checked-in Phase 5.4 report"))
            .expect("valid report JSON");
    assert_eq!(value["schema_version"], 1);
    assert_eq!(
        value["phase"],
        "Phase 5.4 Independent End-to-End Cognitive Validation"
    );
    assert_eq!(value["pass"], true);
    assert_eq!(value["guards"]["runtime_applied"], false);
    assert_eq!(value["decision"]["runtime_authorization"], false);
}
