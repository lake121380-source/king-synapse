use synapse_core::adaptive::{
    MemoryInfluenceState, RuleBasedTemporalTransitionEngine, TemporalEvent, TemporalMemoryProfile,
    TemporalTransitionEngine,
};

#[test]
fn accumulated_pressure_supersedes_challenged_memory() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("old_remote_work_belief", 0.90)
        .with_state(MemoryInfluenceState::Challenged);

    let report = engine.apply_many(
        memory,
        &[TemporalEvent::Contradiction, TemporalEvent::FailureOutcome],
    );

    assert_eq!(report.memory.state, MemoryInfluenceState::Superseded);
    assert!(report.memory.supersession_pressure >= 0.65);
    assert!(report.memory.stored);
    assert!(report.memory.current_influence < report.memory.base_influence);
    assert!(report.memory.transition_history.iter().any(|step| {
        step.reason.contains("displacement pressure") && step.supersession_pressure_after >= 0.65
    }));
}

#[test]
fn supporting_evidence_reduces_pressure_without_supersession() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("old_tool_preference", 0.80);

    let report = engine.apply_many(
        memory,
        &[
            TemporalEvent::Contradiction,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::FailureOutcome,
        ],
    );

    assert_eq!(report.memory.state, MemoryInfluenceState::Challenged);
    assert!(report.memory.supersession_pressure < 0.65);
    assert!(report.memory.current_influence < report.memory.base_influence);
    assert!(report.memory.stored);
}

#[test]
fn superseded_memory_stays_stable_under_mixed_later_events() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("legacy_api_strategy", 0.85);

    let report = engine.apply_many(
        memory,
        &[
            TemporalEvent::Contradiction,
            TemporalEvent::FailureOutcome,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::FailureOutcome,
            TemporalEvent::NewPreference,
            TemporalEvent::SupportingEvidence,
        ],
    );

    assert_eq!(report.memory.state, MemoryInfluenceState::Superseded);
    assert!(report.memory.stored);
    assert!(report.memory.current_influence <= report.memory.base_influence * 0.25);
    assert!(report.memory.transition_history.iter().any(|step| {
        step.from == MemoryInfluenceState::Superseded
            && step.to == MemoryInfluenceState::Superseded
            && step.reason.contains("remains stored")
    }));
}
