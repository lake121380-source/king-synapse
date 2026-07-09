use synapse_eval::{
    Phase4CognitiveCompetitionStabilityEvaluator, Phase4ContextualCompetitionIntegrationEvaluator,
    Phase4ContextualWeightingEvaluator, StabilityCandidate, StabilityContext,
};

#[test]
fn phase4_cognitive_competition_stability_report_loads() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-stability-load")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert_eq!(report.phase, "4.5");
    assert_eq!(report.mode, "evaluation_only");
    assert_eq!(
        report.evaluation_version,
        "phase4.5-cognitive-competition-stability"
    );
    assert_eq!(
        report.baseline_version,
        "phase4.4-contextual-competition-integration"
    );
    assert!(report.pass);
}

#[test]
fn test_same_context_same_dominant() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-same-dominant")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert_eq!(report.deterministic.expected_dominant, "candidate_a");
    assert!(report
        .deterministic
        .result
        .dominant_sequence
        .iter()
        .all(|dominant| dominant == "candidate_a"));
}

#[test]
fn test_100_runs_stable() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-100-runs")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert_eq!(report.deterministic.runs, 100);
    assert_eq!(report.deterministic.same_dominant_count, 100);
    assert_eq!(report.metrics.dominance_stability, 1.0);
}

#[test]
fn test_ranking_order_preserved() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-ranking")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert_eq!(
        report.deterministic.ranking_order,
        vec![
            "candidate_a".to_string(),
            "candidate_b".to_string(),
            "candidate_c".to_string()
        ]
    );
}

#[test]
fn phase4_cognitive_competition_stability_direct_ranking_is_deterministic() {
    let candidates = vec![
        StabilityCandidate {
            id: "candidate_a".to_string(),
            base_strength: 0.92,
            reliability: 0.95,
            temporal_confidence: 0.90,
            evidence_support: 0.82,
        },
        StabilityCandidate {
            id: "candidate_b".to_string(),
            base_strength: 0.74,
            reliability: 0.78,
            temporal_confidence: 0.74,
            evidence_support: 0.68,
        },
    ];
    let context = StabilityContext {
        task: "production_task".to_string(),
        environment: "safety_constraint".to_string(),
        constraint_strength: 0.90,
    };

    let first =
        Phase4CognitiveCompetitionStabilityEvaluator::rank_candidates(&candidates, &context);
    let second =
        Phase4CognitiveCompetitionStabilityEvaluator::rank_candidates(&candidates, &context);

    assert_eq!(first, second);
    assert_eq!(first.first().expect("winner should exist"), "candidate_a");
}

#[test]
fn test_minor_context_change_not_flip() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-minor-noise")
        .expect("Phase 4.5 cognitive competition stability should run");
    let case = noise_case(&report, "speed_request_noise");

    assert_eq!(case.dominant_candidate, "failure_prevention");
    assert_eq!(case.expected_dominant, "failure_prevention");
}

#[test]
fn test_safety_context_resists_speed_noise() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-speed-noise")
        .expect("Phase 4.5 cognitive competition stability should run");
    let case = noise_case(&report, "short_deadline_noise");

    assert_eq!(case.dominant_candidate, "failure_prevention");
    assert!(score(case, "failure_prevention") > score(case, "speed_preference"));
}

#[test]
fn test_environment_noise_resistance() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-env-noise")
        .expect("Phase 4.5 cognitive competition stability should run");
    let case = noise_case(&report, "minor_cost_noise");

    assert_eq!(case.context.environment, "production");
    assert_eq!(case.dominant_candidate, "failure_prevention");
}

#[test]
fn phase4_cognitive_competition_noise_resistance_metric_passes() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-noise")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert_eq!(report.noise.unchanged_cases, report.noise.cases);
    assert_eq!(report.metrics.noise_resistance, 1.0);
}

#[test]
fn test_evidence_accumulation_changes_state() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-transition")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert_eq!(
        report.transition.result.dominant_sequence,
        vec![
            "existing_preference".to_string(),
            "existing_preference".to_string(),
            "existing_preference".to_string(),
            "existing_preference".to_string(),
            "new_contradictory_evidence".to_string(),
            "new_contradictory_evidence".to_string()
        ]
    );
}

#[test]
fn test_transition_is_monotonic() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-monotonic")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert_eq!(report.transition.transition_count, 1);
    assert_eq!(report.transition.transition_consistency, 1.0);
    assert_eq!(report.metrics.transition_consistency, 1.0);
}

#[test]
fn test_no_oscillation() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-oscillation")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert_eq!(report.metrics.oscillation_rate, 0.0);
    assert!(report
        .results
        .iter()
        .all(|result| result.oscillation_events == 0));
}

#[test]
fn phase4_cognitive_competition_transition_scores_cross_once() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-cross-once")
        .expect("Phase 4.5 cognitive competition stability should run");
    let before = transition_step(&report, 0.6);
    let after = transition_step(&report, 0.8);

    assert_eq!(before.dominant_candidate, "existing_preference");
    assert_eq!(after.dominant_candidate, "new_contradictory_evidence");
}

#[test]
fn phase4_cognitive_competition_stability_report_schema_is_valid() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-schema")
        .expect("Phase 4.5 cognitive competition stability should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "phase",
        "mode",
        "evaluation_version",
        "baseline_version",
        "metrics",
        "experiments",
        "core_changed",
        "memory_written",
        "runtime_weight_changed",
        "pass",
        "deterministic",
        "noise",
        "transition",
        "results",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["metrics"].get("dominance_stability").is_some());
    assert!(value["metrics"].get("noise_resistance").is_some());
    assert!(value["metrics"].get("transition_consistency").is_some());
    assert!(value["metrics"].get("oscillation_rate").is_some());
}

#[test]
fn test_eval_only_boundary() {
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-safety")
        .expect("Phase 4.5 cognitive competition stability should run");

    assert!(!report.core_changed);
    assert!(!report.memory_written);
    assert!(!report.runtime_weight_changed);
    assert_eq!(report.experiments.deterministic, "PASS");
    assert_eq!(report.experiments.noise_resistance, "PASS");
    assert_eq!(report.experiments.evidence_transition, "PASS");
}

#[test]
fn test_phase4_3_weighting_unchanged() {
    let weighting = Phase4ContextualWeightingEvaluator::evaluate("phase4-weighting-smoke")
        .expect("Phase 4.3 contextual weighting evaluation should still run");
    let stability =
        Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-stability-smoke")
            .expect("Phase 4.5 cognitive competition stability should run");

    assert!(weighting.pass);
    assert!(stability.pass);
}

#[test]
fn test_phase4_4_competition_unchanged() {
    let integration =
        Phase4ContextualCompetitionIntegrationEvaluator::evaluate("phase4-integration-smoke")
            .expect("Phase 4.4 contextual competition integration should still run");
    let stability =
        Phase4CognitiveCompetitionStabilityEvaluator::evaluate("phase4-stability-smoke")
            .expect("Phase 4.5 cognitive competition stability should run");

    assert!(integration.pass);
    assert!(stability.pass);
}

fn noise_case<'a>(
    report: &'a synapse_eval::Phase4CognitiveCompetitionStabilityReport,
    case_id: &str,
) -> &'a synapse_eval::StabilityNoiseCaseReport {
    report
        .noise
        .case_reports
        .iter()
        .find(|case| case.case_id == case_id)
        .expect("noise case should exist")
}

fn transition_step<'a>(
    report: &'a synapse_eval::Phase4CognitiveCompetitionStabilityReport,
    evidence_support: f64,
) -> &'a synapse_eval::StabilityEvidenceStepReport {
    report
        .transition
        .steps
        .iter()
        .find(|step| (step.evidence_support - evidence_support).abs() < 0.0001)
        .expect("transition step should exist")
}

fn score(case: &synapse_eval::StabilityNoiseCaseReport, candidate_id: &str) -> f64 {
    case.ranking
        .iter()
        .find(|candidate| candidate.candidate_id == candidate_id)
        .expect("candidate score should exist")
        .total_score
}
