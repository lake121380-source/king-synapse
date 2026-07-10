use std::{collections::BTreeSet, sync::OnceLock};
use synapse_eval::{Phase5CognitiveGeneralizationEvaluator, Phase5CognitiveGeneralizationReport};

fn report() -> &'static Phase5CognitiveGeneralizationReport {
    static REPORT: OnceLock<Phase5CognitiveGeneralizationReport> = OnceLock::new();
    REPORT.get_or_init(|| {
        Phase5CognitiveGeneralizationEvaluator::evaluate("phase5-3-4-test")
            .expect("Phase 5.3.4 report")
    })
}

fn split(name: &str) -> &synapse_eval::GeneralizationSplitReport {
    report()
        .splits
        .iter()
        .find(|split| split.split == name)
        .expect("split")
}

fn policy<'a>(
    split: &'a synapse_eval::GeneralizationSplitReport,
    family: &str,
) -> &'a synapse_eval::GeneralizationPolicySummary {
    split
        .policies
        .iter()
        .find(|policy| policy.family == family)
        .expect("policy family")
}

#[test]
fn benchmark_has_locked_30_12_21_split() {
    assert_eq!(split("train").benchmark.scenarios, 30);
    assert_eq!(split("validation").benchmark.scenarios, 12);
    assert_eq!(split("test").benchmark.scenarios, 21);
    assert_eq!(split("train").benchmark.candidates, 120);
    assert_eq!(split("validation").benchmark.candidates, 48);
    assert_eq!(split("test").benchmark.candidates, 84);
}

#[test]
fn every_split_covers_required_cognitive_categories() {
    for split in &report().splits {
        let observed = split
            .benchmark
            .categories
            .keys()
            .map(String::as_str)
            .collect::<BTreeSet<_>>();
        for required in &split.benchmark.required_categories {
            assert!(observed.contains(required.as_str()), "missing {required}");
        }
    }
}

#[test]
fn split_hashes_and_policy_lock_are_recorded() {
    let hashes = report()
        .splits
        .iter()
        .map(|split| split.dataset_sha256.as_str())
        .collect::<BTreeSet<_>>();
    assert_eq!(hashes.len(), 3);
    assert!(hashes.iter().all(|hash| hash.len() == 64));
    assert_eq!(report().policy_lock.margin_guard_threshold, 0.08);
    assert_eq!(report().policy_lock.margin_guard_alpha, 0.20);
    assert!(report().policy_lock.locked_before_hidden_test);
    assert!(!report().policy_lock.hidden_test_parameter_search_performed);
}

#[test]
fn every_split_compares_four_required_baselines() {
    for split in &report().splits {
        assert_eq!(split.policies.len(), 4);
        let families = split
            .policies
            .iter()
            .map(|policy| policy.family.as_str())
            .collect::<BTreeSet<_>>();
        assert_eq!(
            families,
            BTreeSet::from([
                "retrieval_baseline",
                "metadata_confidence",
                "recency_boost",
                "margin_guard",
            ])
        );
    }
}

#[test]
fn retrieval_baseline_is_preserved_without_intervention() {
    for split in &report().splits {
        let baseline = policy(split, "retrieval_baseline");
        assert_eq!(baseline.metrics.policy_interventions, 0);
        assert_eq!(baseline.metrics.changed_positions, 0);
        assert_eq!(baseline.metrics.baseline_mrr, baseline.metrics.policy_mrr);
    }
}

#[test]
fn locked_margin_guard_generalizes_beyond_simple_rules_on_hidden_fixture() {
    let hidden = split("test");
    let margin = policy(hidden, "margin_guard");
    let retrieval = policy(hidden, "retrieval_baseline");
    let metadata = policy(hidden, "metadata_confidence");
    let recency = policy(hidden, "recency_boost");
    assert!(margin.metrics.policy_mrr > retrieval.metrics.policy_mrr);
    assert!(margin.metrics.policy_mrr > metadata.metrics.policy_mrr);
    assert!(margin.metrics.policy_mrr > recency.metrics.policy_mrr);
    assert_eq!(margin.metrics.intervention_precision, 1.0);
    assert!(margin.metrics.intervention_recall >= 0.80);
    assert_eq!(margin.metrics.unnecessary_intervention_rate, 0.0);
    assert_eq!(margin.metrics.catastrophic_regression_rate, 0.0);
}

#[test]
fn hidden_decision_keeps_claim_boundary_explicit() {
    let decision = &report().hidden_test_decision;
    assert!(decision.controlled_generalization_supported);
    assert!(decision.safety_preserved);
    assert!(decision.intervention_quality);
    assert!(!decision.runtime_authorization);
    assert!(!decision.end_to_end_generalization_proven);
}

#[test]
fn factor_interactions_are_measured_on_hidden_test() {
    let interactions = &report().factor_interactions;
    assert_eq!(interactions.len(), 7);
    let full = interactions
        .iter()
        .find(|interaction| interaction.name == "full_cognitive")
        .expect("full interaction");
    let failure_temporal = interactions
        .iter()
        .find(|interaction| interaction.name == "failure_plus_temporal")
        .expect("failure temporal interaction");
    let context_preference = interactions
        .iter()
        .find(|interaction| interaction.name == "context_plus_preference")
        .expect("context preference interaction");
    assert!(full.metrics.policy_mrr >= failure_temporal.metrics.policy_mrr);
    assert!(failure_temporal.metrics.policy_mrr > context_preference.metrics.policy_mrr);
    assert_eq!(full.metrics.catastrophic_regression_rate, 0.0);
}

#[test]
fn determinism_boundedness_and_candidate_safety_hold() {
    for split in &report().splits {
        for policy in &split.policies {
            assert_eq!(policy.metrics.determinism, 1.0);
            assert_eq!(policy.metrics.bounded_rate, 1.0);
            assert!(policy.candidate_pool_preserved);
            assert!(!policy.runtime_applied);
        }
    }
    for interaction in &report().factor_interactions {
        assert_eq!(interaction.metrics.determinism, 1.0);
        assert_eq!(interaction.metrics.bounded_rate, 1.0);
    }
    let guards = &report().guards;
    assert!(guards.eval_only);
    assert!(guards.shadow_only);
    assert!(guards.baseline_authoritative);
    assert!(guards.split_ids_disjoint);
    assert!(!guards.hidden_test_used_for_tuning);
    assert!(!guards.runtime_applied);
    assert!(!guards.policy_memory_written);
    assert!(!guards.memory_mutated);
    assert!(!guards.ranking_mutated);
    assert!(!guards.scores_mutated);
    assert!(!guards.activation_changed);
    assert!(!guards.candidate_pool_changed);
    assert!(!guards.recall_engine_integrated);
    assert!(!guards.production_claim_authorized);
    assert!(!guards.end_to_end_claim_authorized);
}

#[test]
fn fresh_runs_preserve_hashes_and_quality_metrics() {
    let fresh = Phase5CognitiveGeneralizationEvaluator::evaluate("fresh-generalization")
        .expect("fresh report");
    for (left, right) in report().splits.iter().zip(&fresh.splits) {
        assert_eq!(left.split, right.split);
        assert_eq!(left.dataset_sha256, right.dataset_sha256);
        for (left_policy, right_policy) in left.policies.iter().zip(&right.policies) {
            assert_eq!(left_policy.policy, right_policy.policy);
            assert_eq!(
                left_policy.metrics.policy_mrr,
                right_policy.metrics.policy_mrr
            );
            assert_eq!(
                left_policy.metrics.intervention_recall,
                right_policy.metrics.intervention_recall
            );
            assert_eq!(
                left_policy.metrics.catastrophic_regressions,
                right_policy.metrics.catastrophic_regressions
            );
        }
    }
}

#[test]
fn checked_in_report_matches_schema_and_safety_gate() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase5_cognitive_generalization.json");
    let value: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(path).expect("report file"))
            .expect("valid report json");
    assert_eq!(value["schema_version"], 1);
    assert_eq!(value["phase"], "Phase 5.3.4 Generalization Validation");
    assert_eq!(value["pass"], true);
    assert_eq!(value["guards"]["runtime_applied"], false);
    assert_eq!(
        value["hidden_test_decision"]["end_to_end_generalization_proven"],
        false
    );
}
