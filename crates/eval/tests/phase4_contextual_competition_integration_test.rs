use synapse_eval::{
    ContextualCompetitionCandidate, ContextualCompetitionEvaluationContext,
    Phase4ContextualCompetitionIntegrationEvaluator, Phase4ContextualWeightingEvaluator,
};

#[test]
fn phase4_contextual_competition_integration_report_loads() {
    let report =
        Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-integration-load")
            .expect("Phase 4.4 contextual competition integration should run");

    assert_eq!(report.phase, "4.4");
    assert_eq!(report.mode, "evaluation_only");
    assert_eq!(
        report.evaluation_version,
        "phase4.4-contextual-competition-integration"
    );
    assert_eq!(
        report.baseline_version,
        "phase4.3-contextual-cognitive-weighting"
    );
    assert_eq!(report.scenarios, 3);
    assert_eq!(report.context_cases, 6);
    assert!(report.pass);
}

#[test]
fn test_speed_context_prefers_speed() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-speed-context")
        .expect("Phase 4.4 contextual competition integration should run");
    let result = result(&report, "prototype_building");

    assert_eq!(result.dominant_candidate, "speed_preference");
    assert!(result
        .suppressed_candidates
        .contains(&"failure_prevention".to_string()));
    assert!(result.dominance_correct);
}

#[test]
fn test_safety_context_prefers_failure_memory() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-safety-context")
        .expect("Phase 4.4 contextual competition integration should run");
    let result = result(&report, "production_deployment");

    assert_eq!(result.dominant_candidate, "failure_prevention");
    assert!(result
        .suppressed_candidates
        .contains(&"speed_preference".to_string()));
    assert!(result.dominance_correct);
}

#[test]
fn phase4_contextual_competition_speed_safety_context_flip_is_recorded() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-speed-flip")
        .expect("Phase 4.4 contextual competition integration should run");
    let pair = flip_pair(
        &report,
        "contextual_integration_001_speed_vs_safety",
        "prototype_building",
        "production_deployment",
    );

    assert_eq!(pair.left_dominant, "speed_preference");
    assert_eq!(pair.right_dominant, "failure_prevention");
    assert!(pair.dominant_changed);
}

#[test]
fn test_recent_evidence_overrides_old_preference() {
    let report =
        Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-recent-evidence")
            .expect("Phase 4.4 contextual competition integration should run");
    let result = result(&report, "large_system_design");

    assert_eq!(result.dominant_candidate, "recent_failure");
    assert!(score(result, "recent_failure") > score(result, "old_preference"));
}

#[test]
fn phase4_contextual_competition_preserves_old_preference_in_simple_context() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-simple-context")
        .expect("Phase 4.4 contextual competition integration should run");
    let result = result(&report, "simple_tooling");

    assert_eq!(result.dominant_candidate, "old_preference");
    assert!(score(result, "old_preference") > score(result, "recent_failure"));
}

#[test]
fn test_environment_changes_dominance() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-environment")
        .expect("Phase 4.4 contextual competition integration should run");
    let offline = result(&report, "offline_environment");
    let cloud = result(&report, "cloud_environment");

    assert_eq!(offline.dominant_candidate, "local_solution");
    assert_eq!(cloud.dominant_candidate, "cloud_solution");
    assert_ne!(offline.dominant_candidate, cloud.dominant_candidate);
}

#[test]
fn phase4_contextual_competition_context_flip_rate_passes_threshold() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-flip-rate")
        .expect("Phase 4.4 contextual competition integration should run");

    assert_eq!(report.context_flips.changed, 3);
    assert_eq!(report.context_flips.total, 3);
    assert_eq!(report.metric.context_flip_rate, 1.0);
}

#[test]
fn test_same_context_same_result() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-consistency")
        .expect("Phase 4.4 contextual competition integration should run");

    assert_eq!(report.metric.dominance_consistency, 1.0);
    assert!(report
        .scenario_reports
        .iter()
        .flat_map(|scenario| scenario.results.iter())
        .all(|result| result.dominance_consistent));
}

#[test]
fn phase4_contextual_competition_ranking_is_stable() {
    let report =
        Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-ranking-stability")
            .expect("Phase 4.4 contextual competition integration should run");

    assert_eq!(report.metric.ranking_stability, 1.0);
    assert!(report
        .scenario_reports
        .iter()
        .flat_map(|scenario| scenario.results.iter())
        .all(|result| result.ranking_stable));
}

#[test]
fn phase4_contextual_competition_suppression_correctness_passes() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-suppression")
        .expect("Phase 4.4 contextual competition integration should run");

    assert_eq!(report.metric.suppression_correctness, 1.0);
    assert!(report
        .scenario_reports
        .iter()
        .flat_map(|scenario| scenario.results.iter())
        .all(|result| result.suppression_correct));
}

#[test]
fn test_eval_only_no_core_change() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-safety")
        .expect("Phase 4.4 contextual competition integration should run");

    assert!(!report.core_changed);
    assert!(!report.memory_written);
    assert!(!report.runtime_weight_changed);
}

#[test]
fn phase4_contextual_competition_direct_compete_is_deterministic() {
    let candidates = vec![
        ContextualCompetitionCandidate {
            id: "speed_preference".to_string(),
            base_strength: 0.82,
            task_alignment: 0.90,
            environment_alignment: 0.80,
            constraint_alignment: 0.40,
            temporal_confidence: 0.80,
            reliability: 0.80,
        },
        ContextualCompetitionCandidate {
            id: "failure_prevention".to_string(),
            base_strength: 0.80,
            task_alignment: 0.60,
            environment_alignment: 0.70,
            constraint_alignment: 0.90,
            temporal_confidence: 0.90,
            reliability: 0.90,
        },
    ];
    let context = ContextualCompetitionEvaluationContext {
        task: "production_deployment".to_string(),
        environment: "production".to_string(),
        constraints: vec!["safety_priority".to_string(), "high_risk".to_string()],
    };

    let first = Phase4ContextualCompetitionIntegrationEvaluator::compete(
        "production_deployment",
        &candidates,
        &context,
    );
    let second = Phase4ContextualCompetitionIntegrationEvaluator::compete(
        "production_deployment",
        &candidates,
        &context,
    );

    assert_eq!(first.dominant_candidate, "failure_prevention");
    assert_eq!(first.ranked_candidates, second.ranked_candidates);
}

#[test]
fn phase4_contextual_competition_report_schema_is_valid() {
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-schema")
        .expect("Phase 4.4 contextual competition integration should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "phase",
        "mode",
        "evaluation_version",
        "baseline_version",
        "scenarios",
        "context_cases",
        "context_flips",
        "metric",
        "core_changed",
        "memory_written",
        "runtime_weight_changed",
        "pass",
        "scenario_reports",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["metric"].get("context_flip_rate").is_some());
    assert!(value["metric"].get("dominance_consistency").is_some());
    assert!(value["metric"].get("suppression_correctness").is_some());
    assert!(value["metric"].get("ranking_stability").is_some());
}

#[test]
fn phase4_contextual_competition_does_not_regress_contextual_weighting_eval() {
    let weighting = Phase4ContextualWeightingEvaluator::evaluate("phase4-weighting-smoke")
        .expect("Phase 4.3 contextual weighting evaluation should still run");
    let integration =
        Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-integration-smoke")
            .expect("Phase 4.4 contextual competition integration should run");

    assert!(weighting.pass);
    assert!(integration.pass);
    assert_eq!(integration.metric.context_flip_rate, 1.0);
}

fn result<'a>(
    report: &'a synapse_eval::Phase4ContextualCompetitionIntegrationReport,
    context_id: &str,
) -> &'a synapse_eval::ContextualCompetitionResult {
    report
        .scenario_reports
        .iter()
        .flat_map(|scenario| scenario.results.iter())
        .find(|result| result.context_id == context_id)
        .expect("context result should exist")
}

fn flip_pair<'a>(
    report: &'a synapse_eval::Phase4ContextualCompetitionIntegrationReport,
    scenario_id: &str,
    left_context_id: &str,
    right_context_id: &str,
) -> &'a synapse_eval::FlipPairReport {
    report
        .scenario_reports
        .iter()
        .find(|scenario| scenario.scenario_id == scenario_id)
        .expect("scenario should exist")
        .flip_pairs
        .iter()
        .find(|pair| {
            pair.left_context_id == left_context_id && pair.right_context_id == right_context_id
        })
        .expect("flip pair should exist")
}

fn score(result: &synapse_eval::ContextualCompetitionResult, candidate_id: &str) -> f64 {
    result
        .score_breakdown
        .iter()
        .find(|candidate| candidate.candidate_id == candidate_id)
        .expect("candidate score should exist")
        .total_score
}
