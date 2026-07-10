use std::{collections::BTreeSet, sync::OnceLock};
use synapse_eval::{
    load_cognitive_policy_benchmark, CognitivePolicyResult, Phase5CognitivePolicyEvaluator,
    Phase5CognitivePolicyReport,
};

fn report() -> &'static Phase5CognitivePolicyReport {
    static REPORT: OnceLock<Phase5CognitivePolicyReport> = OnceLock::new();
    REPORT.get_or_init(|| {
        Phase5CognitivePolicyEvaluator::evaluate("phase5-cognitive-policy-test")
            .expect("Phase 5.3.3 evaluation")
    })
}

fn policy(family: &str, alpha: Option<f64>) -> &'static CognitivePolicyResult {
    report()
        .policies
        .iter()
        .find(|policy| {
            policy.family == family
                && match (policy.alpha, alpha) {
                    (Some(left), Some(right)) => (left - right).abs() < 1e-12,
                    (None, None) => true,
                    _ => false,
                }
        })
        .expect("policy result")
}

#[test]
fn hard_benchmark_has_required_size_and_categories() {
    let scenarios = load_cognitive_policy_benchmark().expect("load benchmark");
    assert!((30..=50).contains(&scenarios.len()));
    assert_eq!(scenarios.len(), 42);

    let categories = scenarios
        .iter()
        .map(|scenario| scenario.category.as_str())
        .collect::<BTreeSet<_>>();
    for required in [
        "temporal_update",
        "failure_override",
        "reliability_conflict",
        "semantic_trap",
        "preference_evolution",
        "no_intervention",
    ] {
        assert!(categories.contains(required), "missing {required}");
    }
}

#[test]
fn benchmark_labels_are_unique_and_expected_targets_exist() {
    for scenario in load_cognitive_policy_benchmark().expect("load benchmark") {
        let labels = scenario
            .memory
            .iter()
            .map(|memory| memory.label.as_str())
            .collect::<BTreeSet<_>>();
        assert_eq!(labels.len(), scenario.memory.len(), "{}", scenario.id);
        assert!(scenario
            .memory
            .iter()
            .any(|memory| memory.label == scenario.expected_top && memory.relevant));
    }
    assert!(report().benchmark.label_mapping_stable);
}

#[test]
fn safety_gate_passes_without_runtime_authority() {
    let report = report();
    assert!(report.pass);
    assert_eq!(report.status, "PASS");
    assert!(report.guards.eval_only);
    assert!(report.guards.shadow_only);
    assert!(report.guards.baseline_authoritative);
    assert!(report.guards.fixture_setup_writes);
    assert!(!report.guards.runtime_applied);
    assert!(!report.guards.policy_memory_written);
    assert!(!report.guards.memory_mutated);
    assert!(!report.guards.ranking_mutated);
    assert!(!report.guards.scores_mutated);
    assert!(!report.guards.activation_changed);
    assert!(!report.guards.candidate_pool_changed);
    assert!(!report.guards.recall_engine_integrated);
    assert!(!report.guards.production_claim_authorized);
}

#[test]
fn absolute_bonus_reproduces_phase5_3_2_score_rule() {
    let absolute = policy("absolute_bonus", None);
    for scenario in &absolute.scenario_reports {
        for candidate in &scenario.candidates {
            assert!(
                (candidate.policy_score - (candidate.baseline_score + candidate.cognitive_bonus))
                    .abs()
                    < 1e-12
            );
        }
    }
    assert_eq!(absolute.metrics.bounded_rate, 1.0);
    assert_eq!(absolute.metrics.determinism, 1.0);
}

#[test]
fn weighted_fusion_uses_documented_normalized_scale() {
    for alpha in [0.05, 0.10, 0.20] {
        let weighted = policy("weighted_fusion", Some(alpha));
        for scenario in &weighted.scenario_reports {
            for candidate in &scenario.candidates {
                let expected = candidate.baseline_normalized * (1.0 - alpha)
                    + candidate.cognitive_normalized * alpha;
                assert!((candidate.policy_score - expected).abs() < 1e-12);
                assert!((0.0..=1.0).contains(&candidate.policy_score));
            }
        }
    }
}

#[test]
fn margin_guard_preserves_large_gap_no_intervention_cases() {
    let guarded = policy("margin_guard", Some(0.20));
    let no_intervention = guarded
        .scenario_reports
        .iter()
        .filter(|scenario| !scenario.intervention_required)
        .collect::<Vec<_>>();
    assert_eq!(no_intervention.len(), 6);
    assert!(no_intervention
        .iter()
        .all(|scenario| scenario.baseline_ranking == scenario.policy_ranking));
    assert_eq!(guarded.metrics.unnecessary_intervention_rate, 0.0);
    assert_eq!(guarded.metrics.catastrophic_regression_rate, 0.0);
}

#[test]
fn margin_guard_allows_small_gap_required_interventions() {
    let guarded = policy("margin_guard", Some(0.20));
    assert!(guarded.metrics.policy_interventions > 0);
    assert!(guarded.metrics.intervention_recall > 0.0);
    assert!(guarded
        .scenario_reports
        .iter()
        .filter(|scenario| scenario.intervention_required)
        .any(|scenario| scenario.successful_intervention));
}

#[test]
fn unnecessary_intervention_and_catastrophic_regression_are_measured() {
    let absolute = policy("absolute_bonus", None);
    let guarded = policy("margin_guard", Some(0.20));
    assert!(absolute.metrics.unnecessary_interventions > 0);
    assert!(absolute.metrics.catastrophic_regressions > 0);
    assert_eq!(guarded.metrics.unnecessary_interventions, 0);
    assert_eq!(guarded.metrics.catastrophic_regressions, 0);
}

#[test]
fn every_policy_preserves_candidate_pool_and_is_deterministic() {
    for policy in &report().policies {
        assert_eq!(policy.metrics.determinism, 1.0);
        assert_eq!(policy.metrics.bounded_rate, 1.0);
        assert!(policy.scenario_reports.iter().all(|scenario| {
            scenario.candidate_pool_preserved && !scenario.runtime_applied && scenario.deterministic
        }));
    }
}

#[test]
fn ablation_removes_only_declared_real_trace_factors() {
    let report = report();
    assert_eq!(report.ablations.len(), 6);
    let full = report
        .ablations
        .iter()
        .find(|ablation| ablation.name == "full_cognitive")
        .expect("full ablation baseline");
    assert!(full.omitted_factor.is_none());
    assert_eq!(full.removed_factor_count, 0);

    for name in [
        "without_temporal",
        "without_reliability",
        "without_failure",
        "without_preference",
        "without_context",
    ] {
        let ablation = report
            .ablations
            .iter()
            .find(|ablation| ablation.name == name)
            .expect("ablation");
        assert!(ablation.omitted_factor.is_some());
        assert!(ablation.removed_factor_count > 0);
        assert_eq!(ablation.metrics.bounded_rate, 1.0);
        assert_eq!(ablation.metrics.determinism, 1.0);
    }
}

#[test]
fn fresh_fixture_runs_preserve_quality_metrics_and_label_rankings() {
    let left = Phase5CognitivePolicyEvaluator::evaluate("fresh-left").expect("left run");
    let right = Phase5CognitivePolicyEvaluator::evaluate("fresh-right").expect("right run");
    assert_eq!(left.benchmark.scenarios, right.benchmark.scenarios);
    assert_eq!(left.benchmark.categories, right.benchmark.categories);

    for (left_policy, right_policy) in left.policies.iter().zip(&right.policies) {
        assert_eq!(left_policy.policy, right_policy.policy);
        assert_eq!(
            left_policy.metrics.policy_interventions,
            right_policy.metrics.policy_interventions
        );
        assert_eq!(
            left_policy.metrics.successful_required_interventions,
            right_policy.metrics.successful_required_interventions
        );
        assert_eq!(
            left_policy.metrics.catastrophic_regressions,
            right_policy.metrics.catastrophic_regressions
        );
        assert!((left_policy.metrics.policy_mrr - right_policy.metrics.policy_mrr).abs() < 1e-12);
        for (left_scenario, right_scenario) in left_policy
            .scenario_reports
            .iter()
            .zip(&right_policy.scenario_reports)
        {
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
fn report_schema_and_local_report_are_stable() {
    let report = report();
    let value = serde_json::to_value(report).expect("serialize report");
    assert_eq!(value["schema_version"], 1);
    assert_eq!(value["phase"], "Phase 5.3.3 Cognitive Ranking Policy Study");
    assert_eq!(value["benchmark"]["scenarios"], 42);
    assert!(value["policies"]
        .as_array()
        .is_some_and(|items| items.len() == 5));
    assert!(value["ablations"]
        .as_array()
        .is_some_and(|items| items.len() == 6));

    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase5_cognitive_policy.json");
    let committed: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(path).expect("read local report"))
            .expect("parse local report");
    assert_eq!(committed["schema_version"], 1);
    assert_eq!(committed["status"], "PASS");
    assert_eq!(committed["guards"]["runtime_applied"], false);
}
