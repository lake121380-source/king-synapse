use synapse_eval::{
    CandidateType, CognitiveContext, ContextualCandidate, ContextualWeightParameters,
    Phase4CognitiveCompetitionEvaluator, Phase4ContextualWeightingEvaluator,
};

#[test]
fn phase4_contextual_weighting_report_loads() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-contextual-load")
        .expect("Phase 4.3 contextual weighting evaluation should run");

    assert_eq!(report.phase, "4.3");
    assert_eq!(report.mode, "evaluation_only");
    assert_eq!(
        report.evaluation_version,
        "phase4.3-contextual-cognitive-weighting"
    );
    assert_eq!(
        report.baseline_version,
        "phase4.2-cognitive-competition-model"
    );
    assert_eq!(report.scenarios, 6);
    assert!(report.pass);
}

#[test]
fn phase4_contextual_weighting_same_candidate_changes_by_context() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-same-candidate")
        .expect("Phase 4.3 contextual weighting evaluation should run");
    let trace = trace(
        &report,
        "contextual_weighting_001_same_memory_different_context",
    );
    let production = variant_weight(trace, "production", "lesson_check_resources");
    let local = variant_weight(trace, "local", "lesson_check_resources");

    assert!(production > local);
    assert!(production - local >= 0.20);
    assert!(trace.context_weight_correct);
    assert!(trace.adaptive_weight_shift);
}

#[test]
fn phase4_contextual_weighting_formula_uses_breakdown_components() {
    let candidate = ContextualCandidate {
        id: "lesson_formula".to_string(),
        candidate_type: CandidateType::Lesson,
        base_strength: 0.50,
        historical_confidence: 0.70,
        temporal_confidence: 0.80,
        reliability: 0.90,
        context_features: vec![
            "production".to_string(),
            "deployment".to_string(),
            "memory".to_string(),
            "limit".to_string(),
        ],
        contextual_weight: 0.0,
        final_influence: 0.0,
    };
    let context = CognitiveContext {
        task_type: "production deployment".to_string(),
        environment: "production".to_string(),
        constraints: vec!["memory limit".to_string()],
        urgency: 0.90,
    };
    let breakdown = Phase4ContextualWeightingEvaluator::score_candidate_for_context(
        &candidate,
        &context,
        ContextualWeightParameters::default(),
    );

    assert_close(breakdown.context_match, 1.0);
    assert_close(breakdown.constraint_match, 1.0);
    assert_close(breakdown.contextual_weight, 0.94);
    assert_close(breakdown.final_influence, 0.47);
}

#[test]
fn phase4_contextual_weighting_context_overrides_historical_strength() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-context-override")
        .expect("Phase 4.3 contextual weighting evaluation should run");
    let trace = trace(
        &report,
        "contextual_weighting_002_context_overrides_history",
    );

    assert_eq!(trace.dominant_candidate, "lesson_database_incident_context");
    assert_eq!(trace.dominant_candidate_type, CandidateType::Lesson);
    assert!(trace.conflict_resolved);
    assert!(
        influence(trace, "lesson_database_incident_context")
            > influence(trace, "memory_high_history_low_context")
    );
}

#[test]
fn phase4_contextual_weighting_temporal_context_interaction_prefers_new_lesson() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-temporal")
        .expect("Phase 4.3 contextual weighting evaluation should run");
    let trace = trace(
        &report,
        "contextual_weighting_003_temporal_context_interaction",
    );

    assert_eq!(trace.dominant_candidate, "lesson_new_runtime_strategy");
    assert!(trace.conflict_resolved);
    assert!(
        influence(trace, "lesson_new_runtime_strategy")
            > influence(trace, "lesson_old_runtime_strategy")
    );
}

#[test]
fn phase4_contextual_weighting_constraints_raise_matching_strategy() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-constraints")
        .expect("Phase 4.3 contextual weighting evaluation should run");
    let trace = trace(
        &report,
        "contextual_weighting_004_constraint_aware_weighting",
    );
    let efficient = weight(trace, "lesson_memory_efficient_strategy");
    let high_resource = weight(trace, "playbook_high_resource_strategy");

    assert_eq!(trace.dominant_candidate, "lesson_memory_efficient_strategy");
    assert!(efficient > high_resource);
    assert!(
        trace
            .candidate_weights
            .iter()
            .find(|candidate| candidate.candidate_id == "lesson_memory_efficient_strategy")
            .expect("efficient candidate should exist")
            .constraint_match
            > 0.90
    );
}

#[test]
fn phase4_contextual_weighting_cross_context_consistency_is_monotonic() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-consistency")
        .expect("Phase 4.3 contextual weighting evaluation should run");
    let trace = trace(
        &report,
        "contextual_weighting_005_cross_context_consistency",
    );
    let production = variant_weight(trace, "production", "lesson_deployment_readiness");
    let staging = variant_weight(trace, "staging", "lesson_deployment_readiness");
    let local = variant_weight(trace, "local", "lesson_deployment_readiness");

    assert!(production > staging);
    assert!(staging > local);
    assert!(trace.cross_context_consistent);
    assert_eq!(report.metrics.cross_context_consistency, 1.0);
}

#[test]
fn phase4_contextual_weighting_explanation_trace_is_complete() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-explanation")
        .expect("Phase 4.3 contextual weighting evaluation should run");
    let trace = trace(&report, "contextual_weighting_006_explanation_trace");

    assert_eq!(report.metrics.importance_explanation, 1.0);
    assert!(trace.explanation_complete);
    assert!(trace
        .explanation
        .iter()
        .any(|line| line.contains("candidate")));
    assert!(trace
        .explanation
        .iter()
        .any(|line| line.contains("context")));
    assert!(trace
        .explanation
        .iter()
        .any(|line| line.contains("weight_breakdown")));
    assert!(trace
        .explanation
        .iter()
        .any(|line| line.contains("final influence")));
    assert!(trace.explanation.iter().any(|line| line.contains("reason")));
}

#[test]
fn phase4_contextual_weighting_resolves_all_expected_conflicts() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-conflicts")
        .expect("Phase 4.3 contextual weighting evaluation should run");

    assert_eq!(report.metrics.conflict_resolution, 1.0);
    assert!(report.traces.iter().all(|trace| trace.conflict_resolved));
}

#[test]
fn phase4_contextual_weighting_report_schema_is_valid() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-schema")
        .expect("Phase 4.3 contextual weighting evaluation should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "phase",
        "mode",
        "evaluation_version",
        "baseline_version",
        "scenarios",
        "parameters",
        "metrics",
        "safety",
        "pass",
        "traces",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["metrics"].get("context_weight_accuracy").is_some());
    assert!(value["metrics"].get("adaptive_weight_shift").is_some());
    assert!(value["metrics"].get("cross_context_consistency").is_some());
    assert!(value["metrics"].get("importance_explanation").is_some());
    assert!(value["metrics"].get("conflict_resolution").is_some());
    assert!(value["safety"].get("core_changed").is_some());
    assert!(value["safety"].get("memory_written").is_some());
    assert!(value["safety"].get("runtime_weight_changed").is_some());
}

#[test]
fn phase4_contextual_weighting_is_eval_only_and_side_effect_safe() {
    let report = Phase4ContextualWeightingEvaluator::evaluate("phase4-safety")
        .expect("Phase 4.3 contextual weighting evaluation should run");

    assert!(!report.safety.core_changed);
    assert!(!report.safety.memory_written);
    assert!(!report.safety.runtime_weight_changed);
    assert!(report.traces.iter().all(|trace| {
        trace.contextual_weighting_safe
            && !trace.core_changed
            && !trace.memory_written
            && !trace.runtime_weight_changed
    }));
}

#[test]
fn phase4_contextual_weighting_does_not_regress_competition_eval() {
    let competition = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-competition-smoke")
        .expect("Phase 4.2 cognitive competition evaluation should still run");
    let weighting = Phase4ContextualWeightingEvaluator::evaluate("phase4-weighting-smoke")
        .expect("Phase 4.3 contextual weighting evaluation should run");

    assert!(competition.pass);
    assert!(weighting.pass);
    assert_eq!(weighting.metrics.context_weight_accuracy, 1.0);
}

fn trace<'a>(
    report: &'a synapse_eval::Phase4ContextualWeightingReport,
    scenario_id: &str,
) -> &'a synapse_eval::ContextualWeightingTrace {
    report
        .traces
        .iter()
        .find(|trace| trace.scenario_id == scenario_id)
        .expect("scenario should exist")
}

fn weight(trace: &synapse_eval::ContextualWeightingTrace, candidate_id: &str) -> f32 {
    trace
        .candidate_weights
        .iter()
        .find(|candidate| candidate.candidate_id == candidate_id)
        .expect("candidate weight should exist")
        .contextual_weight
}

fn influence(trace: &synapse_eval::ContextualWeightingTrace, candidate_id: &str) -> f32 {
    trace
        .candidate_weights
        .iter()
        .find(|candidate| candidate.candidate_id == candidate_id)
        .expect("candidate influence should exist")
        .final_influence
}

fn variant_weight(
    trace: &synapse_eval::ContextualWeightingTrace,
    label: &str,
    candidate_id: &str,
) -> f32 {
    trace
        .context_variants
        .iter()
        .find(|variant| variant.label == label && variant.candidate_id == candidate_id)
        .expect("context variant should exist")
        .contextual_weight
}

fn assert_close(actual: f32, expected: f32) {
    assert!(
        (actual - expected).abs() < 0.0001,
        "actual {actual} expected {expected}"
    );
}
