use crate::phase7_independent_adjudication_calibration::{
    load_phase7_adjudication_template, load_phase7_reviewer_a_template,
    load_phase7_reviewer_b_template,
};
use crate::phase7_inter_reviewer_agreement::{
    AgreementArtifactLineage, InterReviewerAgreementReport,
};
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

const PROTOCOL_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_3_1_artifact_lineage_protocol.json");
const SOURCE_EXECUTION_BYTES: &[u8] =
    include_bytes!("../reports/phase7_2_3_real_provider_execution.json");
const BLIND_REVIEW_PACKET_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_3_1_blind_review_packet.json");
const REVIEWER_A_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_3_1_reviewer_a_template.json");
const REVIEWER_B_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_3_1_reviewer_b_template.json");
const AGREEMENT_PROTOCOL_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_1_inter_reviewer_agreement_protocol.json"
);
const AGREEMENT_REPORT_BYTES: &[u8] =
    include_bytes!("../reports/phase7_inter_reviewer_agreement.json");
const ADJUDICATION_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_3_1_adjudication_template.json");
const EVALUATION_VERSION: &str = "phase7.3.1-artifact-lineage-irreversible-transition-gate-v1";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArtifactHashPolicy {
    pub algorithm: String,
    pub hashed_representation: String,
    pub embedded_self_hash_allowed: bool,
    pub downstream_references_upstream_hash: bool,
    pub hash_mismatch_invalidates_downstream: bool,
    pub generated_metadata_excluded: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowTransitionPolicy {
    pub skip_allowed: bool,
    pub backward_transition_allowed: bool,
    pub same_state_recheck_allowed: bool,
    pub agreement_must_precede_adjudication: bool,
    pub gold_must_precede_judge_calibration: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Phase7ArtifactLineageProtocol {
    pub schema_version: u32,
    pub protocol_id: String,
    pub parent_protocol_id: String,
    pub phase: String,
    pub purpose: String,
    pub review_completion_order_independent: bool,
    pub states: Vec<String>,
    pub hash_policy: ArtifactHashPolicy,
    pub transition_policy: WorkflowTransitionPolicy,
    pub required_lineage: Vec<String>,
    pub held_out_accessed: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
    pub memory_write_authorized: bool,
    pub extractor_modification_authorized: bool,
    pub judge_modification_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArtifactDigest {
    pub artifact_id: String,
    pub path: String,
    pub sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct IndependentReviewProgress {
    pub reviewer_a_completed: bool,
    pub reviewer_b_completed: bool,
    pub completed_count: usize,
    pub required_count: usize,
    pub completion_order_independent: bool,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase731WorkflowState {
    AwaitingIndependentReviews,
    RawReviewsCompleteAgreementRequired,
    AgreementReportFrozenAdjudicationAllowed,
    AdjudicationCompleteGoldFreezeRequired,
    GoldLabelsFrozen,
    JudgeCalibrationAllowed,
    ArtifactLineageInvalid,
}

impl Phase731WorkflowState {
    fn forward_index(self) -> Option<usize> {
        match self {
            Self::AwaitingIndependentReviews => Some(0),
            Self::RawReviewsCompleteAgreementRequired => Some(1),
            Self::AgreementReportFrozenAdjudicationAllowed => Some(2),
            Self::AdjudicationCompleteGoldFreezeRequired => Some(3),
            Self::GoldLabelsFrozen => Some(4),
            Self::JudgeCalibrationAllowed => Some(5),
            Self::ArtifactLineageInvalid => None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowPermissions {
    pub agreement_computation_allowed: bool,
    pub adjudication_allowed: bool,
    pub gold_freeze_allowed: bool,
    pub judge_calibration_allowed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowFacts {
    pub reviewer_a_completed: bool,
    pub reviewer_b_completed: bool,
    pub foundational_lineage_valid: bool,
    pub agreement_report_completed: bool,
    pub agreement_lineage_valid: bool,
    pub adjudication_completed: bool,
    pub adjudication_lineage_valid: bool,
    pub gold_labels_frozen: bool,
    pub gold_lineage_valid: bool,
    pub frozen_judge_available: bool,
    pub calibration_lineage_valid: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GoldLabelsLineageReference {
    pub adjudication_sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct JudgeCalibrationLineageReference {
    pub gold_labels_sha256: String,
    pub frozen_judge_sha256: String,
}

pub fn validate_gold_labels_artifact_lineage(
    lineage: &GoldLabelsLineageReference,
    current_adjudication_sha256: &str,
) -> Result<()> {
    if lineage.adjudication_sha256 != current_adjudication_sha256 {
        bail!("gold_labels_artifact_lineage_mismatch");
    }
    Ok(())
}

pub fn validate_judge_calibration_artifact_lineage(
    lineage: &JudgeCalibrationLineageReference,
    current_gold_labels_sha256: &str,
    current_frozen_judge_sha256: &str,
) -> Result<()> {
    if lineage.gold_labels_sha256 != current_gold_labels_sha256
        || lineage.frozen_judge_sha256 != current_frozen_judge_sha256
    {
        bail!("judge_calibration_artifact_lineage_mismatch");
    }
    Ok(())
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArtifactLineageStatus {
    pub foundational_lineage_valid: bool,
    pub agreement_lineage_valid: bool,
    pub adjudication_lineage_valid: bool,
    pub gold_lineage_valid: Option<bool>,
    pub calibration_lineage_valid: Option<bool>,
    pub artifact_lineage_broken: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArtifactLineageGuards {
    pub exact_file_sha256_used: bool,
    pub embedded_self_hash_used: bool,
    pub generated_metadata_included: bool,
    pub skipped_transition_allowed: bool,
    pub backward_transition_allowed: bool,
    pub same_state_recheck_allowed: bool,
    pub fake_reviewers_generated: bool,
    pub fake_agreement_metrics_generated: bool,
    pub adjudication_executed: bool,
    pub gold_labels_generated: bool,
    pub judge_calibration_executed: bool,
    pub held_out_accessed: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
    pub memory_write_authorized: bool,
    pub extractor_modified: bool,
    pub judge_modified: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Phase7ArtifactLineageTransitionReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub protocol: Phase7ArtifactLineageProtocol,
    pub state: Phase731WorkflowState,
    pub review_progress: IndependentReviewProgress,
    pub artifacts: Vec<ArtifactDigest>,
    pub agreement_report_sha256: String,
    pub adjudication_sha256: String,
    pub gold_labels_sha256: Option<String>,
    pub frozen_judge_sha256: Option<String>,
    pub lineage: ArtifactLineageStatus,
    pub permissions: WorkflowPermissions,
    pub guards: ArtifactLineageGuards,
    pub conclusion: String,
}

pub struct Phase7ArtifactLineageTransitionEvaluator;

impl Phase7ArtifactLineageTransitionEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7ArtifactLineageTransitionReport> {
        evaluate(tag.into())
    }
}

pub fn load_phase7_artifact_lineage_protocol() -> Result<Phase7ArtifactLineageProtocol> {
    serde_json::from_str(PROTOCOL_JSON).context("parse Phase 7.3.1 artifact lineage protocol")
}

pub fn exact_file_sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn independent_review_progress(
    reviewer_a_completed: bool,
    reviewer_b_completed: bool,
) -> IndependentReviewProgress {
    IndependentReviewProgress {
        reviewer_a_completed,
        reviewer_b_completed,
        completed_count: usize::from(reviewer_a_completed) + usize::from(reviewer_b_completed),
        required_count: 2,
        completion_order_independent: true,
    }
}

pub fn derive_phase7_workflow_state(facts: &WorkflowFacts) -> Phase731WorkflowState {
    if !facts.foundational_lineage_valid {
        return Phase731WorkflowState::ArtifactLineageInvalid;
    }
    if !(facts.reviewer_a_completed && facts.reviewer_b_completed) {
        return Phase731WorkflowState::AwaitingIndependentReviews;
    }
    if !facts.agreement_report_completed {
        return Phase731WorkflowState::RawReviewsCompleteAgreementRequired;
    }
    if !facts.agreement_lineage_valid {
        return Phase731WorkflowState::ArtifactLineageInvalid;
    }
    if !facts.adjudication_completed {
        return Phase731WorkflowState::AgreementReportFrozenAdjudicationAllowed;
    }
    if !facts.adjudication_lineage_valid {
        return Phase731WorkflowState::ArtifactLineageInvalid;
    }
    if !facts.gold_labels_frozen {
        return Phase731WorkflowState::AdjudicationCompleteGoldFreezeRequired;
    }
    if !facts.gold_lineage_valid {
        return Phase731WorkflowState::ArtifactLineageInvalid;
    }
    if !facts.frozen_judge_available {
        return Phase731WorkflowState::GoldLabelsFrozen;
    }
    if !facts.calibration_lineage_valid {
        return Phase731WorkflowState::ArtifactLineageInvalid;
    }
    Phase731WorkflowState::JudgeCalibrationAllowed
}

pub fn validate_phase7_workflow_transition(
    from: Phase731WorkflowState,
    to: Phase731WorkflowState,
) -> Result<()> {
    if from == Phase731WorkflowState::ArtifactLineageInvalid
        || to == Phase731WorkflowState::ArtifactLineageInvalid
    {
        bail!("artifact_lineage_invalid_is_not_an_authorized_transition");
    }
    let from_index = from.forward_index().expect("validated non-invalid state");
    let to_index = to.forward_index().expect("validated non-invalid state");
    if to_index == from_index {
        return Ok(());
    }
    if to_index < from_index {
        bail!("backward_workflow_transition_forbidden");
    }
    if to_index != from_index + 1 {
        bail!("skipped_workflow_transition_forbidden");
    }
    Ok(())
}

pub fn permissions_for_state(state: Phase731WorkflowState) -> WorkflowPermissions {
    WorkflowPermissions {
        agreement_computation_allowed: state
            == Phase731WorkflowState::RawReviewsCompleteAgreementRequired,
        adjudication_allowed: state
            == Phase731WorkflowState::AgreementReportFrozenAdjudicationAllowed,
        gold_freeze_allowed: state == Phase731WorkflowState::AdjudicationCompleteGoldFreezeRequired,
        judge_calibration_allowed: state == Phase731WorkflowState::JudgeCalibrationAllowed,
    }
}

pub fn validate_agreement_artifact_lineage(lineage: &AgreementArtifactLineage) -> bool {
    lineage.source_execution_sha256 == exact_file_sha256(SOURCE_EXECUTION_BYTES)
        && lineage.blind_review_packet_sha256 == exact_file_sha256(BLIND_REVIEW_PACKET_BYTES)
        && lineage.reviewer_a_submission_sha256 == exact_file_sha256(REVIEWER_A_BYTES)
        && lineage.reviewer_b_submission_sha256 == exact_file_sha256(REVIEWER_B_BYTES)
        && lineage.agreement_protocol_sha256 == exact_file_sha256(AGREEMENT_PROTOCOL_BYTES)
}

fn validate_protocol(protocol: &Phase7ArtifactLineageProtocol) -> Result<()> {
    let expected_states = [
        "awaiting_independent_reviews",
        "raw_reviews_complete_agreement_required",
        "agreement_report_frozen_adjudication_allowed",
        "adjudication_complete_gold_freeze_required",
        "gold_labels_frozen",
        "judge_calibration_allowed",
        "artifact_lineage_invalid",
    ];
    let expected_lineage = [
        "source_execution_sha256",
        "blind_review_packet_sha256",
        "reviewer_a_submission_sha256",
        "reviewer_b_submission_sha256",
        "agreement_protocol_sha256",
        "agreement_report_sha256",
        "adjudication_sha256",
        "gold_labels_sha256",
        "frozen_judge_sha256",
    ];
    if protocol
        .states
        .iter()
        .map(String::as_str)
        .collect::<Vec<_>>()
        != expected_states
        || protocol
            .required_lineage
            .iter()
            .map(String::as_str)
            .collect::<Vec<_>>()
            != expected_lineage
        || !protocol.review_completion_order_independent
        || protocol.hash_policy.algorithm != "sha256"
        || protocol.hash_policy.hashed_representation != "exact_file_bytes"
        || protocol.hash_policy.embedded_self_hash_allowed
        || !protocol.hash_policy.downstream_references_upstream_hash
        || !protocol.hash_policy.hash_mismatch_invalidates_downstream
        || protocol.hash_policy.generated_metadata_excluded
        || protocol.transition_policy.skip_allowed
        || protocol.transition_policy.backward_transition_allowed
        || !protocol.transition_policy.same_state_recheck_allowed
        || !protocol
            .transition_policy
            .agreement_must_precede_adjudication
        || !protocol
            .transition_policy
            .gold_must_precede_judge_calibration
        || protocol.held_out_accessed
        || protocol.runtime_authorized
        || protocol.hermes_authorized
        || protocol.memory_write_authorized
        || protocol.extractor_modification_authorized
        || protocol.judge_modification_authorized
    {
        bail!("phase7_3_1_artifact_lineage_protocol_invalid");
    }
    Ok(())
}

fn artifact(artifact_id: &str, path: &str, bytes: &[u8]) -> ArtifactDigest {
    ArtifactDigest {
        artifact_id: artifact_id.to_string(),
        path: path.to_string(),
        sha256: exact_file_sha256(bytes),
    }
}

fn evaluate(tag: String) -> Result<Phase7ArtifactLineageTransitionReport> {
    let protocol = load_phase7_artifact_lineage_protocol()?;
    validate_protocol(&protocol)?;

    let reviewer_a = load_phase7_reviewer_a_template()?;
    let reviewer_b = load_phase7_reviewer_b_template()?;
    let agreement_report: InterReviewerAgreementReport =
        serde_json::from_slice(AGREEMENT_REPORT_BYTES)
            .context("parse checked-in agreement report")?;
    let adjudication = load_phase7_adjudication_template()?;

    let agreement_lineage_valid = validate_agreement_artifact_lineage(&agreement_report.lineage);
    let agreement_report_completed = agreement_report.metrics.is_some()
        && agreement_report.guards.agreement_report_completed
        && agreement_report.guards.reviewer_a_completed
        && agreement_report.guards.reviewer_b_completed;
    let agreement_report_sha256 = exact_file_sha256(AGREEMENT_REPORT_BYTES);
    let adjudication_sha256 = exact_file_sha256(ADJUDICATION_BYTES);
    let adjudication_lineage_valid = if let Some(lineage) = &adjudication.lineage {
        lineage.reviewer_a_submission_sha256 == exact_file_sha256(REVIEWER_A_BYTES)
            && lineage.reviewer_b_submission_sha256 == exact_file_sha256(REVIEWER_B_BYTES)
            && lineage.agreement_report_sha256 == agreement_report_sha256
    } else {
        !adjudication.completed
    };

    let facts = WorkflowFacts {
        reviewer_a_completed: reviewer_a.completed,
        reviewer_b_completed: reviewer_b.completed,
        foundational_lineage_valid: agreement_lineage_valid,
        agreement_report_completed,
        agreement_lineage_valid,
        adjudication_completed: adjudication.completed,
        adjudication_lineage_valid,
        gold_labels_frozen: false,
        gold_lineage_valid: false,
        frozen_judge_available: false,
        calibration_lineage_valid: false,
    };
    let state = derive_phase7_workflow_state(&facts);
    let progress = independent_review_progress(reviewer_a.completed, reviewer_b.completed);
    let permissions = permissions_for_state(state);
    let artifact_lineage_broken = state == Phase731WorkflowState::ArtifactLineageInvalid;

    Ok(Phase7ArtifactLineageTransitionReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: protocol.phase.clone(),
        protocol,
        state,
        review_progress: progress,
        artifacts: vec![
            artifact(
                "source_execution",
                "crates/eval/reports/phase7_2_3_real_provider_execution.json",
                SOURCE_EXECUTION_BYTES,
            ),
            artifact(
                "blind_review_packet",
                "crates/eval/datasets/pattern_extraction/phase7_3_1_blind_review_packet.json",
                BLIND_REVIEW_PACKET_BYTES,
            ),
            artifact(
                "reviewer_a_submission",
                "crates/eval/datasets/pattern_extraction/phase7_3_1_reviewer_a_template.json",
                REVIEWER_A_BYTES,
            ),
            artifact(
                "reviewer_b_submission",
                "crates/eval/datasets/pattern_extraction/phase7_3_1_reviewer_b_template.json",
                REVIEWER_B_BYTES,
            ),
            artifact(
                "agreement_protocol",
                "crates/eval/datasets/pattern_extraction/phase7_3_1_inter_reviewer_agreement_protocol.json",
                AGREEMENT_PROTOCOL_BYTES,
            ),
            artifact(
                "agreement_report",
                "crates/eval/reports/phase7_inter_reviewer_agreement.json",
                AGREEMENT_REPORT_BYTES,
            ),
            artifact(
                "adjudication",
                "crates/eval/datasets/pattern_extraction/phase7_3_1_adjudication_template.json",
                ADJUDICATION_BYTES,
            ),
        ],
        agreement_report_sha256,
        adjudication_sha256,
        gold_labels_sha256: None,
        frozen_judge_sha256: None,
        lineage: ArtifactLineageStatus {
            foundational_lineage_valid: agreement_lineage_valid,
            agreement_lineage_valid,
            adjudication_lineage_valid,
            gold_lineage_valid: None,
            calibration_lineage_valid: None,
            artifact_lineage_broken,
        },
        permissions,
        guards: ArtifactLineageGuards {
            exact_file_sha256_used: true,
            embedded_self_hash_used: false,
            generated_metadata_included: true,
            skipped_transition_allowed: false,
            backward_transition_allowed: false,
            same_state_recheck_allowed: true,
            fake_reviewers_generated: false,
            fake_agreement_metrics_generated: false,
            adjudication_executed: false,
            gold_labels_generated: false,
            judge_calibration_executed: false,
            held_out_accessed: false,
            runtime_authorized: false,
            hermes_authorized: false,
            memory_write_authorized: false,
            extractor_modified: false,
            judge_modified: false,
        },
        conclusion: if artifact_lineage_broken {
            "An upstream exact-file SHA-256 mismatch invalidated all downstream authorization."
                .to_string()
        } else if state == Phase731WorkflowState::AwaitingIndependentReviews {
            "Artifact lineage is bound, but the workflow remains at 0/2 independent reviews; agreement, adjudication, Gold freezing, and Judge calibration are unauthorized."
                .to_string()
        } else {
            "The workflow state is derived only from completed upstream artifacts and exact-file SHA-256 lineage references."
                .to_string()
        },
    })
}
