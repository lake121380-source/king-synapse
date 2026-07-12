use std::collections::BTreeMap;
use synapse_eval::{
    derive_phase7_workflow_state, independent_review_progress, load_phase7_adjudication_template,
    validate_agreement_artifact_lineage, validate_judge_calibration_artifact_lineage,
    validate_phase7_adjudication_artifact_lineage, validate_phase7_workflow_transition,
    validate_silver_labels_artifact_lineage, AdjudicationLineageReference,
    JudgeCalibrationLineageReference, Phase731WorkflowState,
    Phase7ArtifactLineageTransitionEvaluator, SilverLabelsLineageReference, WorkflowFacts,
};

fn facts() -> WorkflowFacts {
    WorkflowFacts {
        reviewer_a_completed: false,
        reviewer_b_completed: false,
        foundational_lineage_valid: true,
        agreement_report_completed: false,
        agreement_lineage_valid: true,
        adjudication_completed: false,
        adjudication_lineage_valid: true,
        silver_labels_frozen: false,
        silver_lineage_valid: false,
        frozen_judge_available: false,
        calibration_lineage_valid: false,
    }
}

#[test]
fn current_workflow_has_two_reviews_and_frozen_agreement() {
    let report = Phase7ArtifactLineageTransitionEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.state, Phase731WorkflowState::SilverLabelsFrozen);
    assert_eq!(report.review_progress.completed_count, 2);
    assert_eq!(report.review_progress.required_count, 2);
    assert!(report.review_progress.completion_order_independent);
    assert!(report.lineage.foundational_lineage_valid);
    assert!(!report.lineage.artifact_lineage_broken);
    assert!(!report.permissions.agreement_computation_allowed);
    assert!(!report.permissions.adjudication_allowed);
    assert!(!report.permissions.silver_freeze_allowed);
    assert!(!report.permissions.judge_calibration_allowed);
    assert!(report.silver_labels_sha256.is_some());
    assert!(report.frozen_judge_sha256.is_none());
}

#[test]
fn reviewer_completion_is_order_independent() {
    let a_first = independent_review_progress(true, false);
    let b_first = independent_review_progress(false, true);
    assert_eq!(a_first.completed_count, 1);
    assert_eq!(b_first.completed_count, 1);
    assert_eq!(a_first.required_count, b_first.required_count);

    let mut a_facts = facts();
    a_facts.reviewer_a_completed = true;
    let mut b_facts = facts();
    b_facts.reviewer_b_completed = true;
    assert_eq!(
        derive_phase7_workflow_state(&a_facts),
        Phase731WorkflowState::AwaitingIndependentReviews
    );
    assert_eq!(
        derive_phase7_workflow_state(&b_facts),
        Phase731WorkflowState::AwaitingIndependentReviews
    );
}

#[test]
fn state_machine_requires_each_forward_gate() {
    let mut state_facts = facts();
    state_facts.reviewer_a_completed = true;
    state_facts.reviewer_b_completed = true;
    assert_eq!(
        derive_phase7_workflow_state(&state_facts),
        Phase731WorkflowState::RawReviewsCompleteAgreementRequired
    );

    state_facts.agreement_report_completed = true;
    assert_eq!(
        derive_phase7_workflow_state(&state_facts),
        Phase731WorkflowState::AgreementReportFrozenAdjudicationAllowed
    );

    state_facts.adjudication_completed = true;
    assert_eq!(
        derive_phase7_workflow_state(&state_facts),
        Phase731WorkflowState::AdjudicationCompleteSilverFreezeRequired
    );

    state_facts.silver_labels_frozen = true;
    state_facts.silver_lineage_valid = true;
    assert_eq!(
        derive_phase7_workflow_state(&state_facts),
        Phase731WorkflowState::SilverLabelsFrozen
    );

    state_facts.frozen_judge_available = true;
    state_facts.calibration_lineage_valid = true;
    assert_eq!(
        derive_phase7_workflow_state(&state_facts),
        Phase731WorkflowState::JudgeCalibrationAllowed
    );
}

#[test]
fn transition_validator_rejects_skips_and_backward_motion() {
    use Phase731WorkflowState::*;
    validate_phase7_workflow_transition(AwaitingIndependentReviews, AwaitingIndependentReviews)
        .expect("same-state recheck");
    validate_phase7_workflow_transition(
        AwaitingIndependentReviews,
        RawReviewsCompleteAgreementRequired,
    )
    .expect("single forward transition");

    assert!(validate_phase7_workflow_transition(
        AwaitingIndependentReviews,
        AgreementReportFrozenAdjudicationAllowed
    )
    .unwrap_err()
    .to_string()
    .contains("skipped_workflow_transition_forbidden"));
    assert!(validate_phase7_workflow_transition(
        AgreementReportFrozenAdjudicationAllowed,
        RawReviewsCompleteAgreementRequired
    )
    .unwrap_err()
    .to_string()
    .contains("backward_workflow_transition_forbidden"));
}

#[test]
fn any_required_lineage_mismatch_invalidates_downstream_state() {
    let report = Phase7ArtifactLineageTransitionEvaluator::evaluate("mutation").expect("evaluate");
    let checked: serde_json::Value = serde_json::from_str(include_str!(
        "../reports/phase7_inter_reviewer_agreement.json"
    ))
    .expect("agreement report");
    let mut lineage: synapse_eval::AgreementArtifactLineage =
        serde_json::from_value(checked["lineage"].clone()).expect("lineage");
    assert!(validate_agreement_artifact_lineage(&lineage));
    lineage.source_execution_sha256.replace_range(0..1, "0");
    if validate_agreement_artifact_lineage(&lineage) {
        lineage.source_execution_sha256.replace_range(0..1, "1");
    }
    assert!(!validate_agreement_artifact_lineage(&lineage));

    let mut invalid = facts();
    invalid.reviewer_a_completed = true;
    invalid.reviewer_b_completed = true;
    invalid.agreement_report_completed = true;
    invalid.agreement_lineage_valid = false;
    assert_eq!(
        derive_phase7_workflow_state(&invalid),
        Phase731WorkflowState::ArtifactLineageInvalid
    );
    assert!(!report.artifacts.is_empty());
}

#[test]
fn adjudication_requires_exact_agreement_and_review_hashes() {
    let report = Phase7ArtifactLineageTransitionEvaluator::evaluate("lineage").expect("evaluate");
    let digests = report
        .artifacts
        .iter()
        .map(|item| (item.artifact_id.as_str(), item.sha256.clone()))
        .collect::<BTreeMap<_, _>>();
    let mut adjudication = load_phase7_adjudication_template().expect("adjudication template");
    adjudication.completed = true;
    adjudication.lineage = Some(AdjudicationLineageReference {
        reviewer_a_submission_sha256: digests["reviewer_a_submission"].clone(),
        reviewer_b_submission_sha256: digests["reviewer_b_submission"].clone(),
        agreement_report_sha256: report.agreement_report_sha256.clone(),
    });
    validate_phase7_adjudication_artifact_lineage(&adjudication).expect("exact lineage");

    adjudication
        .lineage
        .as_mut()
        .unwrap()
        .agreement_report_sha256
        .replace_range(0..1, "0");
    if validate_phase7_adjudication_artifact_lineage(&adjudication).is_ok() {
        adjudication
            .lineage
            .as_mut()
            .unwrap()
            .agreement_report_sha256
            .replace_range(0..1, "1");
    }
    assert!(validate_phase7_adjudication_artifact_lineage(&adjudication)
        .unwrap_err()
        .to_string()
        .contains("adjudication_artifact_lineage_mismatch"));
}

#[test]
fn incomplete_adjudication_cannot_claim_lineage() {
    let report =
        Phase7ArtifactLineageTransitionEvaluator::evaluate("incomplete").expect("evaluate");
    let mut adjudication = load_phase7_adjudication_template().expect("adjudication template");
    adjudication.completed = false;
    adjudication.claims.clear();
    adjudication.lineage = Some(AdjudicationLineageReference {
        reviewer_a_submission_sha256: "0".repeat(64),
        reviewer_b_submission_sha256: "0".repeat(64),
        agreement_report_sha256: report.agreement_report_sha256,
    });
    assert!(validate_phase7_adjudication_artifact_lineage(&adjudication)
        .unwrap_err()
        .to_string()
        .contains("incomplete_adjudication_template_must_not_contain_lineage"));
}

#[test]
fn checked_in_report_preserves_governance_boundary() {
    let report: serde_json::Value = serde_json::from_str(include_str!(
        "../reports/phase7_artifact_lineage_transition_gate.json"
    ))
    .expect("checked report");
    assert_eq!(report["state"], "silver_labels_frozen");
    assert_eq!(report["review_progress"]["completed_count"], 2);
    assert_eq!(report["review_progress"]["required_count"], 2);
    assert_eq!(report["permissions"]["adjudication_allowed"], false);
    assert_eq!(report["permissions"]["silver_freeze_allowed"], false);
    assert_eq!(report["permissions"]["judge_calibration_allowed"], false);
    assert_eq!(report["guards"]["fake_reviewers_generated"], false);
    assert_eq!(report["guards"]["fake_agreement_metrics_generated"], false);
    assert_eq!(report["guards"]["silver_labels_generated"], true);
    assert_eq!(report["guards"]["held_out_accessed"], false);
    assert!(report["silver_labels_sha256"].is_string());
    assert!(report["frozen_judge_sha256"].is_null());
}

#[test]
fn silver_and_calibration_require_exact_upstream_hashes() {
    let adjudication_hash = "a".repeat(64);
    let silver_hash = "b".repeat(64);
    let judge_hash = "c".repeat(64);
    let silver = SilverLabelsLineageReference {
        adjudication_sha256: adjudication_hash.clone(),
    };
    validate_silver_labels_artifact_lineage(&silver, &adjudication_hash).expect("Silver lineage");
    assert!(validate_silver_labels_artifact_lineage(&silver, &"d".repeat(64)).is_err());

    let calibration = JudgeCalibrationLineageReference {
        silver_labels_sha256: silver_hash.clone(),
        frozen_judge_sha256: judge_hash.clone(),
    };
    validate_judge_calibration_artifact_lineage(&calibration, &silver_hash, &judge_hash)
        .expect("calibration lineage");
    assert!(validate_judge_calibration_artifact_lineage(
        &calibration,
        &"e".repeat(64),
        &judge_hash
    )
    .is_err());
}
