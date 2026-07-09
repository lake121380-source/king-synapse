use std::collections::BTreeSet;
use synapse_eval::{
    LessonLifecycleState, Phase3FutureInfluenceEvaluator, Phase3LessonLifecycleEvaluator,
};

#[test]
fn phase3_lesson_lifecycle_loads_future_influence_source() {
    let future_influence = Phase3FutureInfluenceEvaluator::evaluate("phase3-lifecycle-source")
        .expect("Phase 3.4 future influence source should run");
    let report = Phase3LessonLifecycleEvaluator::evaluate("phase3-lifecycle-load")
        .expect("Phase 3.5 lesson lifecycle should run");

    assert_eq!(report.phase, "3.5");
    assert_eq!(report.mode, "evaluation_only");
    assert_eq!(
        report.evaluation_version,
        "phase3.5-lesson-lifecycle-evaluation"
    );
    assert_eq!(
        report.baseline_version,
        "phase3.4-future-influence-experiment"
    );
    assert_eq!(report.scenarios, 4);
    assert_eq!(
        report.future_influence_source_count,
        future_influence.traces.len()
    );
    assert!(report.pass);
}

#[test]
fn phase3_lesson_lifecycle_covers_required_final_states() {
    let report = Phase3LessonLifecycleEvaluator::evaluate("phase3-lifecycle-states")
        .expect("Phase 3.5 lesson lifecycle should run");
    let states = report
        .traces
        .iter()
        .map(|trace| trace.final_state)
        .collect::<BTreeSet<_>>();

    assert_eq!(report.states.active, 1);
    assert_eq!(report.states.challenged, 1);
    assert_eq!(report.states.superseded, 1);
    assert_eq!(report.states.candidate, 1);
    assert!(states.contains(&LessonLifecycleState::Active));
    assert!(states.contains(&LessonLifecycleState::Challenged));
    assert!(states.contains(&LessonLifecycleState::Superseded));
    assert!(states.contains(&LessonLifecycleState::Candidate));
}

#[test]
fn phase3_lesson_lifecycle_reinforcement_moves_proposed_to_active() {
    let report = Phase3LessonLifecycleEvaluator::evaluate("phase3-lifecycle-reinforcement")
        .expect("Phase 3.5 lesson lifecycle should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.lifecycle_pattern == "Reinforcement")
        .expect("reinforcement scenario should exist");

    assert_eq!(trace.initial_state, LessonLifecycleState::Proposed);
    assert_eq!(trace.final_state, LessonLifecycleState::Active);
    assert_eq!(trace.support_events, 3);
    assert!(trace.confidence_after > trace.confidence_before);
    assert!(trace.influence_after > trace.influence_before);
    assert!(trace.lifecycle_safe);
}

#[test]
fn phase3_lesson_lifecycle_contradiction_challenges_active_lesson() {
    let report = Phase3LessonLifecycleEvaluator::evaluate("phase3-lifecycle-challenge")
        .expect("Phase 3.5 lesson lifecycle should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.lifecycle_pattern == "Challenge")
        .expect("challenge scenario should exist");

    assert_eq!(trace.initial_state, LessonLifecycleState::Active);
    assert_eq!(trace.final_state, LessonLifecycleState::Challenged);
    assert_eq!(trace.contradiction_events, 1);
    assert!(trace.confidence_after < trace.confidence_before);
    assert!(trace.influence_after < trace.influence_before);
    assert!(trace.lifecycle_safe);
}

#[test]
fn phase3_lesson_lifecycle_supersession_replaces_old_lesson() {
    let report = Phase3LessonLifecycleEvaluator::evaluate("phase3-lifecycle-supersession")
        .expect("Phase 3.5 lesson lifecycle should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.lifecycle_pattern == "Supersession")
        .expect("supersession scenario should exist");

    assert_eq!(trace.initial_state, LessonLifecycleState::Active);
    assert_eq!(trace.final_state, LessonLifecycleState::Superseded);
    assert!(trace.replacement_lesson.is_some());
    assert!(trace.confidence_after < trace.confidence_before);
    assert!(trace.influence_after < trace.influence_before);
    assert!(trace.lifecycle_safe);
}

#[test]
fn phase3_lesson_lifecycle_protects_against_false_lesson_activation() {
    let report = Phase3LessonLifecycleEvaluator::evaluate("phase3-lifecycle-protection")
        .expect("Phase 3.5 lesson lifecycle should run");
    let trace = report
        .traces
        .iter()
        .find(|trace| trace.lifecycle_pattern == "FalseLessonProtection")
        .expect("false lesson protection scenario should exist");

    assert_eq!(trace.initial_state, LessonLifecycleState::Candidate);
    assert_eq!(trace.final_state, LessonLifecycleState::Candidate);
    assert_ne!(trace.final_state, LessonLifecycleState::Active);
    assert_eq!(trace.support_events, 1);
    assert!(trace.lifecycle_safe);
}

#[test]
fn phase3_lesson_lifecycle_report_schema_is_valid() {
    let report = Phase3LessonLifecycleEvaluator::evaluate("phase3-lifecycle-schema")
        .expect("Phase 3.5 lesson lifecycle should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "phase",
        "mode",
        "evaluation_version",
        "baseline_version",
        "scenarios",
        "states",
        "metrics",
        "safety",
        "pass",
        "traces",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["states"].get("active").is_some());
    assert!(value["states"].get("challenged").is_some());
    assert!(value["states"].get("superseded").is_some());
    assert!(value["states"].get("candidate").is_some());
    assert!(value["metrics"]
        .get("lifecycle_transition_accuracy")
        .is_some());
    assert!(value["metrics"]
        .get("contradiction_response_score")
        .is_some());
    assert!(value["metrics"].get("supersession_score").is_some());
    assert!(value["metrics"].get("reinforcement_score").is_some());
    assert!(value["metrics"].get("lifecycle_safety").is_some());
}

#[test]
fn phase3_lesson_lifecycle_is_eval_only_and_side_effect_safe() {
    let report = Phase3LessonLifecycleEvaluator::evaluate("phase3-lifecycle-safety")
        .expect("Phase 3.5 lesson lifecycle should run");

    assert!(!report.mechanism_changed);
    assert!(!report.schema_changed);
    assert!(!report.retrieval_changed);
    assert!(!report.activation_changed);
    assert!(!report.temporal_lifecycle_changed);
    assert!(!report.governance_changed);
    assert!(!report.safety.memory_written);
    assert!(!report.safety.lesson_persisted);
    assert!(!report.safety.playbook_created);
    assert!(!report.safety.future_influence_changed);
    assert_eq!(report.metrics.lifecycle_safety, 1.0);
    assert!(report.traces.iter().all(|trace| {
        trace.lifecycle_safe
            && !trace.memory_written
            && !trace.lesson_persisted
            && !trace.playbook_created
            && !trace.future_influence_changed
    }));
}
