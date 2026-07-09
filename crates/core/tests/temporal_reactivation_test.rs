use synapse_core::adaptive::{
    MemoryInfluenceState, RuleBasedTemporalTransitionEngine, TemporalEvent, TemporalMemoryProfile,
    TemporalTransitionEngine,
};

#[test]
fn weak_support_does_not_resurrect_superseded_memory() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("old_coffee_preference", 0.90)
        .with_state(MemoryInfluenceState::Superseded);

    let report = engine.apply(memory, TemporalEvent::SupportingEvidence);

    assert_eq!(report.memory.state, MemoryInfluenceState::Superseded);
    assert!(report.memory.stored);
    assert!(report.memory.reactivation_pressure > 0.0);
    assert!(
        report.memory.reactivation_pressure < engine.reactivation_policy().reactivation_threshold()
    );
    assert!(report.memory.current_influence <= report.memory.base_influence * 0.25);
}

#[test]
fn strong_support_reactivates_superseded_memory_to_challenged() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("old_coffee_preference", 0.90)
        .with_state(MemoryInfluenceState::Superseded);

    let report = engine.apply_many(
        memory,
        &[
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
        ],
    );

    assert_eq!(report.memory.state, MemoryInfluenceState::Challenged);
    assert!(report.memory.stored);
    assert!(
        report.memory.reactivation_pressure
            >= engine.reactivation_policy().reactivation_threshold()
    );
    assert!(report.memory.transition_history.iter().any(|step| {
        step.from == MemoryInfluenceState::Superseded
            && step.to == MemoryInfluenceState::Challenged
            && step.reason.contains("reactivated")
            && step.reactivation_pressure_after
                >= engine.reactivation_policy().reactivation_threshold()
    }));
}

#[test]
fn reactivated_memory_recovers_partial_influence_not_full_active_influence() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("old_architecture_strategy", 0.80)
        .with_state(MemoryInfluenceState::Superseded);

    let report = engine.apply_many(
        memory,
        &[
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
        ],
    );

    assert_eq!(report.memory.state, MemoryInfluenceState::Challenged);
    assert!(report.memory.current_influence > report.memory.base_influence * 0.25);
    assert!(report.memory.current_influence < report.memory.base_influence);
    assert_eq!(
        report.memory.current_influence,
        report.memory.base_influence * engine.challenged_multiplier()
    );
}

#[test]
fn counterevidence_decays_reactivation_pressure() {
    let engine = RuleBasedTemporalTransitionEngine::default();
    let memory = TemporalMemoryProfile::new("old_tooling_preference", 0.85)
        .with_state(MemoryInfluenceState::Superseded);

    let report = engine.apply_many(
        memory,
        &[
            TemporalEvent::SupportingEvidence,
            TemporalEvent::SupportingEvidence,
            TemporalEvent::Contradiction,
        ],
    );

    assert_eq!(report.memory.state, MemoryInfluenceState::Superseded);
    assert!(report.memory.reactivation_pressure < 0.40);
    assert!(
        report.transition.reactivation_pressure_after
            < report.transition.reactivation_pressure_before
    );
}
