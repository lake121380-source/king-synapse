use synapse_eval::{CandidateType, InfluenceWeights, Phase4CognitiveInfluenceEvaluator};

#[test]
fn phase4_cognitive_influence_report_loads() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-influence-load")
        .expect("Phase 4.1 cognitive influence evaluation should run");

    assert_eq!(report.phase, "4.1");
    assert_eq!(report.mode, "evaluation_only");
    assert_eq!(
        report.evaluation_version,
        "phase4.1-cognitive-influence-evaluation"
    );
    assert_eq!(
        report.baseline_version,
        "phase3.6-experience-learning-freeze"
    );
    assert_eq!(report.scenarios, 5);
    assert!(report.pass);
}

#[test]
fn phase4_cognitive_influence_uses_configurable_weights() {
    let weights = InfluenceWeights {
        historical_strength: 0.30,
        temporal_confidence: 0.25,
        context_alignment: 0.35,
        reliability_score: 0.10,
    };
    let report = Phase4CognitiveInfluenceEvaluator::evaluate_with_weights(
        "phase4-influence-weights",
        weights,
    )
    .expect("Phase 4.1 cognitive influence evaluation should run");

    assert_eq!(report.weights.historical_strength, 0.30);
    assert_eq!(report.weights.temporal_confidence, 0.25);
    assert_eq!(report.weights.context_alignment, 0.35);
    assert_eq!(report.weights.reliability_score, 0.10);
    assert!(report.pass);
}

#[test]
fn phase4_cognitive_influence_context_can_beat_history() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-context-wins")
        .expect("Phase 4.1 cognitive influence evaluation should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.scenario_id == "cognitive_influence_001_context_wins")
        .expect("context wins scenario should exist");

    assert_eq!(trace.winning_candidate_id, "lesson_current_gpu_context");
    assert!(trace.winner_correct);
    assert!(trace.context_alignment_ok);
}

#[test]
fn phase4_cognitive_influence_historical_reliability_can_win() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-history-wins")
        .expect("Phase 4.1 cognitive influence evaluation should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.scenario_id == "cognitive_influence_002_historical_reliability_wins")
        .expect("historical reliability scenario should exist");

    assert_eq!(
        trace.winning_candidate_id,
        "memory_reliable_deployment_pattern"
    );
    assert_eq!(trace.winning_candidate_type, CandidateType::Memory);
    assert!(trace.winner_correct);
}

#[test]
fn phase4_cognitive_influence_temporal_decay_prefers_new_lesson() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-temporal-decay")
        .expect("Phase 4.1 cognitive influence evaluation should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.scenario_id == "cognitive_influence_003_temporal_decay")
        .expect("temporal decay scenario should exist");

    assert_eq!(
        trace.winning_candidate_id,
        "lesson_new_environment_strategy"
    );
    assert_eq!(trace.winning_candidate_type, CandidateType::Lesson);
    assert!(trace.winner_correct);
}

#[test]
fn phase4_cognitive_influence_contradiction_outputs_suppression() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-contradiction")
        .expect("Phase 4.1 cognitive influence evaluation should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.scenario_id == "cognitive_influence_004_contradictory_candidates")
        .expect("contradictory candidate scenario should exist");

    assert_eq!(trace.winning_candidate_id, "memory_recent_failure_pattern");
    assert_eq!(trace.suppressed_candidates.len(), 1);
    assert_eq!(
        trace.suppressed_candidates[0].candidate_id,
        "memory_old_success_pattern"
    );
    assert!(!trace.suppressed_candidates[0].why_rejected.is_empty());
}

#[test]
fn phase4_cognitive_influence_tie_handling_is_deterministic() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-tie")
        .expect("Phase 4.1 cognitive influence evaluation should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.scenario_id == "cognitive_influence_005_explanation_trace")
        .expect("explanation trace scenario should exist");

    assert_eq!(trace.winning_candidate_id, "playbook_traceable_checklist");
    assert_eq!(
        trace.winning_candidate_type,
        CandidateType::PlaybookCandidate
    );
    assert_eq!(
        trace.influence_ranking[1].candidate_id,
        "lesson_traceable_checklist"
    );
    assert!(trace.stable_under_perturbation);
}

#[test]
fn phase4_cognitive_influence_explanation_trace_is_complete() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-explanation")
        .expect("Phase 4.1 cognitive influence evaluation should run");

    assert_eq!(report.metrics.explanation_quality, 1.0);
    for trace in &report.traces {
        assert!(!trace.winning_candidate_id.is_empty());
        assert!(!trace.why_selected.is_empty());
        assert_eq!(trace.score_breakdown.len(), trace.influence_ranking.len());
        assert_eq!(
            trace.suppressed_candidates.len(),
            trace.influence_ranking.len() - 1
        );
        assert!(trace
            .suppressed_candidates
            .iter()
            .all(|candidate| !candidate.why_rejected.is_empty()));
    }
}

#[test]
fn phase4_cognitive_influence_report_schema_is_valid() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-schema")
        .expect("Phase 4.1 cognitive influence evaluation should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "phase",
        "mode",
        "evaluation_version",
        "baseline_version",
        "scenarios",
        "weights",
        "metrics",
        "safety",
        "pass",
        "traces",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["metrics"].get("influence_accuracy").is_some());
    assert!(value["metrics"].get("context_alignment_score").is_some());
    assert!(value["metrics"].get("competition_stability").is_some());
    assert!(value["metrics"].get("explanation_quality").is_some());
    assert!(value["safety"].get("core_changed").is_some());
    assert!(value["safety"].get("memory_written").is_some());
    assert!(value["safety"].get("runtime_influence_changed").is_some());
}

#[test]
fn phase4_cognitive_influence_is_eval_only_and_side_effect_safe() {
    let report = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-safety")
        .expect("Phase 4.1 cognitive influence evaluation should run");

    assert!(!report.safety.core_changed);
    assert!(!report.safety.memory_written);
    assert!(!report.safety.runtime_influence_changed);
    assert!(report.traces.iter().all(|trace| {
        trace.influence_safe
            && !trace.core_changed
            && !trace.memory_written
            && !trace.runtime_influence_changed
    }));
}
