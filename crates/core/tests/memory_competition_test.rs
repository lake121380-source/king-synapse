use synapse_core::adaptive::{
    MemoryCandidate, MemoryCompetition, MemoryCompetitionState, RuleBasedMemoryCompetition,
};

fn assert_close(actual: f32, expected: f32) {
    assert!(
        (actual - expected).abs() < 1e-6,
        "expected {expected}, got {actual}"
    );
}

#[test]
fn conflicting_memories_promote_new_failure_experience() {
    let competition = RuleBasedMemoryCompetition::default();
    let candidates = vec![
        MemoryCandidate::new("old_fast_preference", 0.85, 0.90, 0.45, 0.65),
        MemoryCandidate::new("new_fast_failure", 0.75, 0.95, 0.95, 0.05),
    ];

    let report = competition.compete(&candidates);

    assert_eq!(report.dominant.as_deref(), Some("new_fast_failure"));
    assert!(report
        .suppressed
        .contains(&"old_fast_preference".to_string()));
    assert_eq!(
        report.dominant_candidate().unwrap().state,
        MemoryCompetitionState::Dominant
    );
    assert!(report.decision_path.iter().any(
        |step| step.memory_id == "old_fast_preference" && step.reason.contains("contradiction")
    ));
}

#[test]
fn obsolete_memory_remains_suppressed_with_lower_influence() {
    let competition = RuleBasedMemoryCompetition::default();
    let old_success = MemoryCandidate::new("old_successful_strategy", 0.90, 0.90, 0.55, 0.50);
    let new_environment =
        MemoryCandidate::new("new_environment_constraint", 0.70, 0.95, 0.95, 0.00);

    let report = competition.compete(&[old_success.clone(), new_environment]);
    let old = report
        .candidates
        .iter()
        .find(|candidate| candidate.memory_id == "old_successful_strategy")
        .unwrap();

    assert_eq!(
        report.dominant.as_deref(),
        Some("new_environment_constraint")
    );
    assert_eq!(old.state, MemoryCompetitionState::Suppressed);
    assert!(report
        .suppressed
        .contains(&"old_successful_strategy".to_string()));
    assert!(old.final_influence < old_success.activation_score);
    assert_close(old.final_influence, 0.90 * 0.90 * 0.55 * 0.50);
}

#[test]
fn uncertain_weak_evidence_is_not_dominant() {
    let competition = RuleBasedMemoryCompetition::default();
    let candidates = vec![MemoryCandidate::new(
        "weak_keyword_similar_memory",
        0.60,
        0.35,
        0.40,
        0.40,
    )];

    let report = competition.compete(&candidates);

    assert_eq!(report.dominant, None);
    assert!(report
        .rejected
        .contains(&"weak_keyword_similar_memory".to_string()));
    assert_eq!(report.candidates[0].state, MemoryCompetitionState::Rejected);
    assert!(report.decision_path[0].reason.contains("confidence"));
}
