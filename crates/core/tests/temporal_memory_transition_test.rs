use synapse_core::adaptive::{
    MemoryInfluenceState, RuleBasedTemporalTransitionEngine, TemporalEvent, TemporalMemoryProfile,
    TemporalTransitionEngine,
};

#[test]
fn old_preference_failure_moves_active_to_challenged() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("fast_solution_preference", 0.90);

    let report = engine.apply_many(
        memory,
        &[TemporalEvent::FailureOutcome, TemporalEvent::FailureOutcome],
    );

    assert_eq!(report.memory.state, MemoryInfluenceState::Challenged);
    assert!(report.memory.stored);
    assert_eq!(report.memory.memory_id, "fast_solution_preference");
    assert!(report.memory.current_influence < report.memory.base_influence);
    assert!(report.memory.transition_history.iter().any(|step| {
        step.from == MemoryInfluenceState::Active
            && step.to == MemoryInfluenceState::Challenged
            && step.reason.contains("later evidence")
    }));
}

#[test]
fn repeated_counterevidence_moves_challenged_to_superseded() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("fast_solution_preference", 0.90)
        .with_state(MemoryInfluenceState::Challenged);

    let report = engine.apply_many(
        memory,
        &[
            TemporalEvent::FailureOutcome,
            TemporalEvent::FailureOutcome,
            TemporalEvent::FailureOutcome,
        ],
    );

    assert_eq!(report.memory.state, MemoryInfluenceState::Superseded);
    assert_eq!(report.memory.failure_count, 3);
    assert!(report.memory.transition_history.iter().any(|step| {
        step.from == MemoryInfluenceState::Challenged
            && step.to == MemoryInfluenceState::Superseded
            && step.reason.contains("displacement pressure")
    }));
}

#[test]
fn superseded_memory_remains_stored_with_low_influence() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("old_successful_strategy", 0.80);

    let report = engine.apply_many(
        memory,
        &[
            TemporalEvent::Contradiction,
            TemporalEvent::FailureOutcome,
            TemporalEvent::FailureOutcome,
            TemporalEvent::FailureOutcome,
        ],
    );

    assert!(report.memory.stored);
    assert_eq!(report.memory.state, MemoryInfluenceState::Superseded);
    assert_eq!(report.memory.memory_id, "old_successful_strategy");
    assert_eq!(report.memory.base_influence, 0.80);
    assert!(report.memory.current_influence <= report.memory.base_influence * 0.25);
    assert!(!report.memory.transition_history.is_empty());
    assert!(report.memory.transition_history.iter().all(|step| {
        step.memory_id == "old_successful_strategy"
            && step.influence_after <= report.memory.base_influence
    }));
}
