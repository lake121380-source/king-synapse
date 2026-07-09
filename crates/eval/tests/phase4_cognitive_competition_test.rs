use synapse_eval::{
    CandidateType, Phase4CognitiveCompetitionEvaluator, Phase4CognitiveInfluenceEvaluator,
};

#[test]
fn phase4_cognitive_competition_report_loads() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-competition-load")
        .expect("Phase 4.2 cognitive competition evaluation should run");

    assert_eq!(report.phase, "4.2");
    assert_eq!(report.mode, "evaluation_only");
    assert_eq!(
        report.evaluation_version,
        "phase4.2-cognitive-competition-model"
    );
    assert_eq!(
        report.baseline_version,
        "phase4.1-cognitive-influence-evaluation"
    );
    assert_eq!(report.scenarios, 6);
    assert!(report.pass);
}

#[test]
fn phase4_cognitive_competition_clear_winner_dominates() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-clear-winner")
        .expect("Phase 4.2 cognitive competition evaluation should run");
    let trace = trace(&report, "competition_001_clear_winner");

    assert_eq!(trace.dominant_candidate, "memory_clear_a");
    assert_eq!(trace.dominant_candidate_type, CandidateType::Memory);
    assert!(trace.dominant_correct);
    assert!(trace.confidence_gap > 0.10);
}

#[test]
fn phase4_cognitive_competition_context_override_wins() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-context-override")
        .expect("Phase 4.2 cognitive competition evaluation should run");
    let trace = trace(&report, "competition_002_context_override");

    assert_eq!(trace.dominant_candidate, "lesson_context_high");
    assert_eq!(trace.dominant_candidate_type, CandidateType::Lesson);
    assert!(trace.dominant_correct);
}

#[test]
fn phase4_cognitive_competition_near_tie_is_deterministic() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-near-tie")
        .expect("Phase 4.2 cognitive competition evaluation should run");
    let trace = trace(&report, "competition_003_near_tie");

    assert_eq!(trace.dominant_candidate, "memory_near_tie_a");
    assert!(trace.confidence_gap > 0.0);
    assert!(trace.stable_under_noise);
    assert!(trace
        .explanation
        .iter()
        .any(|line| line.contains("confidence gap")));
}

#[test]
fn phase4_cognitive_competition_inhibits_weaker_candidates() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-inhibition")
        .expect("Phase 4.2 cognitive competition evaluation should run");
    let trace = trace(&report, "competition_004_inhibition");

    assert_eq!(trace.dominant_candidate, "memory_inhibition_a");
    assert!(trace
        .suppressed_candidates
        .contains(&"lesson_inhibition_b".to_string()));
    assert!(trace
        .suppressed_candidates
        .contains(&"playbook_inhibition_c".to_string()));
    assert!(trace
        .suppressed_candidate_reports
        .iter()
        .all(|candidate| candidate.inhibited > 0.0));
}

#[test]
fn phase4_cognitive_competition_multihop_activation_path_boosts_playbook() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-multihop")
        .expect("Phase 4.2 cognitive competition evaluation should run");
    let trace = trace(&report, "competition_005_multi_hop");

    assert_eq!(trace.dominant_candidate, "playbook_multihop_c");
    assert_eq!(
        trace.dominant_candidate_type,
        CandidateType::PlaybookCandidate
    );
    assert_eq!(trace.activation_path.len(), 2);
    assert!(trace.rounds.iter().any(|round| {
        round
            .states
            .iter()
            .any(|state| state.candidate_id == "playbook_multihop_c" && state.path_boost > 0.0)
    }));
}

#[test]
fn phase4_cognitive_competition_stays_stable_under_noise() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-noise")
        .expect("Phase 4.2 cognitive competition evaluation should run");
    let trace = trace(&report, "competition_006_stability_under_noise");

    assert_eq!(trace.dominant_candidate, "lesson_stable_a");
    assert!(trace.stable_under_noise);
    assert_eq!(report.metrics.activation_stability, 1.0);
}

#[test]
fn phase4_cognitive_competition_converges_for_all_scenarios() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-convergence")
        .expect("Phase 4.2 cognitive competition evaluation should run");

    assert_eq!(report.metrics.competition_convergence, 1.0);
    assert!(report.traces.iter().all(|trace| trace.convergence));
    assert!(report
        .traces
        .iter()
        .all(|trace| trace.rounds.len() == report.parameters.rounds));
}

#[test]
fn phase4_cognitive_competition_explanation_is_complete() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-explanation")
        .expect("Phase 4.2 cognitive competition evaluation should run");

    assert_eq!(report.metrics.explanation_quality, 1.0);
    for trace in &report.traces {
        assert!(trace.explanation_complete);
        assert!(trace
            .explanation
            .iter()
            .any(|line| line.contains("dominant")));
        assert!(trace
            .explanation
            .iter()
            .any(|line| line.contains("suppressed")));
        assert!(trace
            .explanation
            .iter()
            .any(|line| line.contains("activation_path")));
    }
}

#[test]
fn phase4_cognitive_competition_report_schema_is_valid() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-schema")
        .expect("Phase 4.2 cognitive competition evaluation should run");
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

    assert!(value["metrics"]
        .get("dominant_selection_accuracy")
        .is_some());
    assert!(value["metrics"].get("competition_convergence").is_some());
    assert!(value["metrics"].get("suppression_quality").is_some());
    assert!(value["metrics"].get("activation_stability").is_some());
    assert!(value["metrics"].get("explanation_quality").is_some());
    assert!(value["safety"].get("core_changed").is_some());
    assert!(value["safety"].get("memory_written").is_some());
    assert!(value["safety"].get("runtime_activation_changed").is_some());
}

#[test]
fn phase4_cognitive_competition_is_eval_only_and_side_effect_safe() {
    let report = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-safety")
        .expect("Phase 4.2 cognitive competition evaluation should run");

    assert!(!report.safety.core_changed);
    assert!(!report.safety.memory_written);
    assert!(!report.safety.runtime_activation_changed);
    assert!(report.traces.iter().all(|trace| {
        trace.competition_safe
            && !trace.core_changed
            && !trace.memory_written
            && !trace.runtime_activation_changed
    }));
}

#[test]
fn phase4_cognitive_competition_does_not_regress_influence_eval() {
    let influence = Phase4CognitiveInfluenceEvaluator::evaluate("phase4-influence-smoke")
        .expect("Phase 4.1 cognitive influence evaluation should still run");
    let competition = Phase4CognitiveCompetitionEvaluator::evaluate("phase4-competition-smoke")
        .expect("Phase 4.2 cognitive competition evaluation should run");

    assert!(influence.pass);
    assert!(competition.pass);
    assert_eq!(competition.metrics.dominant_selection_accuracy, 1.0);
}

fn trace<'a>(
    report: &'a synapse_eval::Phase4CognitiveCompetitionReport,
    scenario_id: &str,
) -> &'a synapse_eval::CompetitionTrace {
    report
        .traces
        .iter()
        .find(|trace| trace.scenario_id == scenario_id)
        .expect("scenario should exist")
}
