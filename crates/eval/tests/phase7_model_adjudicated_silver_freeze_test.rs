use synapse_eval::{
    validate_model_adjudicated_silver_freeze, HumanSupportLabel, Phase7ModelAdjudicatedSilverFreeze,
};

#[test]
fn freezes_exactly_77_claims_across_10_design_candidates() {
    let artifact = Phase7ModelAdjudicatedSilverFreeze::build().expect("silver freeze");
    assert_eq!(artifact.claim_count, 77);
    assert_eq!(artifact.candidate_count, 10);
    assert_eq!(artifact.claims.len(), 77);
    assert_eq!(artifact.candidates.len(), 10);
    validate_model_adjudicated_silver_freeze(&artifact).expect("valid freeze");
}

#[test]
fn silver_labels_are_never_presented_as_human_gold() {
    let artifact = Phase7ModelAdjudicatedSilverFreeze::build().expect("silver freeze");
    assert!(artifact.frozen);
    assert!(!artifact.human_gold);
    assert_eq!(
        artifact.label_status,
        "model_adjudicated_silver_not_human_gold"
    );
    assert!(artifact.conclusion.contains("not human Gold"));
}

#[test]
fn scope_calibration_remains_unavailable_without_adjudicated_scope_labels() {
    let artifact = Phase7ModelAdjudicatedSilverFreeze::build().expect("silver freeze");
    assert!(!artifact.scope_labels_adjudicated);
    assert!(!artifact.scope_calibration_available);
}

#[test]
fn candidate_aggregation_is_conservative_and_deterministic() {
    let first = Phase7ModelAdjudicatedSilverFreeze::build().expect("first");
    let second = Phase7ModelAdjudicatedSilverFreeze::build().expect("second");
    assert_eq!(first, second);
    assert!(first.candidates.iter().all(|candidate| {
        candidate.aggregate_support_label == HumanSupportLabel::Unsupported
            || candidate.aggregate_support_label == HumanSupportLabel::PartiallySupported
            || candidate.aggregate_support_label == HumanSupportLabel::Supported
            || candidate.aggregate_support_label == HumanSupportLabel::NotAssessable
    }));
}

#[test]
fn freeze_preserves_closed_system_boundaries() {
    let artifact = Phase7ModelAdjudicatedSilverFreeze::build().expect("silver freeze");
    assert!(!artifact.held_out_accessed);
    assert!(artifact.conclusion.contains("no learning"));
    assert!(artifact.conclusion.contains("memory write"));
    assert!(artifact.conclusion.contains("runtime"));
}
