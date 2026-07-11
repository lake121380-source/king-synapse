use crate::phase7_candidate_error_analysis::CandidateFailureKind;
use crate::phase7_real_provider_readiness::load_phase7_real_provider_execution;
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

const PROTOCOL_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_3_1_measurement_protocol.json");
const REVIEWER_A_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_3_1_reviewer_a_template.json");
const REVIEWER_B_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_3_1_reviewer_b_template.json");
const ADJUDICATION_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_3_1_adjudication_template.json");
const EVALUATION_VERSION: &str = "phase7.3.1-independent-adjudication-frozen-judge-calibration-v1";

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum MeasurementObjectKind {
    EvidenceBundle,
    Candidate,
    FrozenJudge,
    Prompt,
    Provider,
    Parser,
    RepairPolicy,
    ExtractionAlgorithm,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MeasurementObjectDefinition {
    pub object: MeasurementObjectKind,
    pub role: String,
    pub studied: bool,
    pub modified: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CalibrationPolicy {
    pub positive_class: String,
    pub threshold_change_allowed: bool,
    pub prompt_change_allowed: bool,
    pub rule_change_allowed: bool,
    pub semantic_judge_addition_allowed: bool,
    pub same_data_optimization_allowed: bool,
    pub report_confidence_intervals: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7AdjudicationMeasurementProtocol {
    pub schema_version: u32,
    pub protocol_id: String,
    pub phase: String,
    pub measurement_objects: Vec<MeasurementObjectDefinition>,
    pub one_experimental_variable_rule: String,
    pub evidence_boundary: String,
    pub claim_origin_definitions: serde_json::Value,
    pub support_label_definitions: serde_json::Value,
    pub binary_views: serde_json::Value,
    pub blind_review_requirements: Vec<String>,
    pub disagreement_kinds: Vec<DisagreementKind>,
    pub judge_failure_kinds: Vec<JudgeFailureKind>,
    pub calibration_policy: CalibrationPolicy,
    pub held_out_accessed: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ClaimSourceField {
    Proposition,
    PredictionStatement,
    PredictionObservable,
    PredictionSuccessCriterion,
    FalsificationStatement,
    FalsificationObservable,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimSourceAnchor {
    pub anchor_id: String,
    pub case_id: String,
    pub response_sha256: String,
    pub source_field: ClaimSourceField,
    pub source_index: usize,
    pub source_text: String,
    pub source_text_sha256: String,
    pub requires_independent_atomic_segmentation: bool,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ClaimOrigin {
    Explicit,
    Inferred,
    Synthesized,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum HumanSupportLabel {
    Supported,
    PartiallySupported,
    Unsupported,
    NotAssessable,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ScopeAssessment {
    Preserved,
    Expanded,
    NotAssessable,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CausalStrengthAssessment {
    Supported,
    Overstated,
    NotPresent,
    NotAssessable,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PredictionSupportAssessment {
    Supported,
    PartiallySupported,
    Unsupported,
    NotPresent,
    NotAssessable,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CounterexampleAssessment {
    Preserved,
    Ignored,
    NotPresent,
    NotAssessable,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum FalsifiabilityAssessment {
    DirectInScope,
    StructuralOnly,
    Invalid,
    NotAssessable,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AnnotationConfidence {
    Low,
    Medium,
    High,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimDimensionLabels {
    pub scope: ScopeAssessment,
    pub causal_strength: CausalStrengthAssessment,
    pub prediction_support: PredictionSupportAssessment,
    pub counterexample_handling: CounterexampleAssessment,
    pub falsifiability: FalsifiabilityAssessment,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicClaimAnnotation {
    pub claim_id: String,
    pub case_id: String,
    pub response_sha256: String,
    pub anchor_id: String,
    pub claim_text: String,
    pub claim_origin: ClaimOrigin,
    pub claimed_evidence_ids: Vec<String>,
    pub human_support_label: HumanSupportLabel,
    pub dimension_labels: ClaimDimensionLabels,
    pub failure_kinds: Vec<CandidateFailureKind>,
    pub reviewer_rationale: String,
    pub annotation_confidence: AnnotationConfidence,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReviewerAnnotationSubmission {
    pub schema_version: u32,
    pub submission_id: String,
    pub reviewer_id: String,
    pub reviewer_role: String,
    pub source_execution_id: String,
    pub protocol_id: String,
    pub completed: bool,
    pub blind_to_other_reviewer: bool,
    pub blind_to_frozen_judge: bool,
    pub blind_to_phase7_3_aggregates: bool,
    pub held_out_accessed: bool,
    pub claims: Vec<AtomicClaimAnnotation>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum DisagreementKind {
    BoundaryDisagreement,
    FundamentalDisagreement,
    SegmentationDisagreement,
    EvidenceDisagreement,
    ProvenanceDisagreement,
    TaxonomyDisagreement,
    ConfidenceDisagreement,
    Other,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum JudgeFailureKind {
    LexicalNoveltyFalsePositive,
    ScopeFieldPlacementFalsePositive,
    ParaphraseEntailmentMiss,
    BridgingInferenceFalsePositive,
    UnsupportedPredictionFalseNegative,
    CausalLeapFalseNegative,
    ScopeExpansionFalseNegative,
    PartialSupportCollapsed,
    ClaimBoundaryMismatch,
    Other,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AdjudicatedClaim {
    pub claim_id: String,
    pub reviewer_a_claim_ids: Vec<String>,
    pub reviewer_b_claim_ids: Vec<String>,
    pub final_support_label: HumanSupportLabel,
    pub final_claim_origin: ClaimOrigin,
    pub disagreements: Vec<DisagreementKind>,
    pub judge_failures: Vec<JudgeFailureKind>,
    pub adjudication_rationale: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AdjudicationSubmission {
    pub schema_version: u32,
    pub adjudication_id: String,
    pub protocol_id: String,
    pub reviewer_a_submission_id: String,
    pub reviewer_b_submission_id: String,
    pub completed: bool,
    pub held_out_accessed: bool,
    pub disagreements_preserved: bool,
    pub claims: Vec<AdjudicatedClaim>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BinaryCalibrationView {
    StrictSafety,
    StrongError,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CandidateJudgeCalibrationRow {
    pub case_id: String,
    pub human_support_label: HumanSupportLabel,
    pub frozen_judge_unsupported_warning: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ScopeJudgeCalibrationRow {
    pub case_id: String,
    pub human_scope_expanded: Option<bool>,
    pub frozen_judge_scope_warning: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ConfidenceInterval {
    pub lower: f64,
    pub upper: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ConfusionMatrix {
    pub true_positive: usize,
    pub false_positive: usize,
    pub false_negative: usize,
    pub true_negative: usize,
    pub excluded: usize,
    pub precision: Option<f64>,
    pub precision_wilson_95: Option<ConfidenceInterval>,
    pub recall_sensitivity: Option<f64>,
    pub recall_sensitivity_wilson_95: Option<ConfidenceInterval>,
    pub specificity: Option<f64>,
    pub specificity_wilson_95: Option<ConfidenceInterval>,
    pub false_positive_rate: Option<f64>,
    pub false_positive_rate_wilson_95: Option<ConfidenceInterval>,
    pub false_negative_rate: Option<f64>,
    pub false_negative_rate_wilson_95: Option<ConfidenceInterval>,
    pub balanced_accuracy: Option<f64>,
    pub matthews_correlation_coefficient: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SupportAgreementMetrics {
    pub aligned_claim_count: usize,
    pub excluded_not_assessable_count: usize,
    pub raw_agreement: Option<f64>,
    pub raw_agreement_wilson_95: Option<ConfidenceInterval>,
    pub linear_weighted_kappa: Option<f64>,
    pub boundary_disagreement_count: usize,
    pub fundamental_disagreement_count: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MetricDefinition {
    pub name: String,
    pub definition: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Phase7AdjudicationCalibrationGuards {
    pub frozen_phase7_2_3_outputs_reused: bool,
    pub evidence_bundle_frozen: bool,
    pub candidate_modified: bool,
    pub frozen_judge_modified: bool,
    pub prompt_modified: bool,
    pub provider_modified: bool,
    pub parser_modified: bool,
    pub repair_policy_modified: bool,
    pub extraction_algorithm_modified: bool,
    pub provider_calls_made: bool,
    pub reviewer_a_completed: bool,
    pub reviewer_b_completed: bool,
    pub independent_adjudication_completed: bool,
    pub scorer_calibration_completed: bool,
    pub held_out_cases_untouched: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
    pub candidate_learning_authorized: bool,
    pub knowledge_promotion_authorized: bool,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase7AdjudicationCalibrationDecision {
    ProtocolReadyWaitingForIndependentAnnotation,
    IndependentAnnotationsReadyAdjudicationRequired,
    AdjudicationCompleteCalibrationDiagnosticOnly,
    CandidateErrorsConfirmed,
    ScorerRecalibrationRequired,
    MixedCandidateAndScorerFailure,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7AdjudicationCalibrationReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub purpose: String,
    pub source_execution_sha256: String,
    pub protocol_sha256: String,
    pub reviewer_a_template_sha256: String,
    pub reviewer_b_template_sha256: String,
    pub adjudication_template_sha256: String,
    pub protocol: Phase7AdjudicationMeasurementProtocol,
    pub claim_source_anchors: Vec<ClaimSourceAnchor>,
    pub reviewer_a: ReviewerAnnotationSubmission,
    pub reviewer_b: ReviewerAnnotationSubmission,
    pub adjudication: AdjudicationSubmission,
    pub metric_definitions: Vec<MetricDefinition>,
    pub agreement: Option<SupportAgreementMetrics>,
    pub strict_safety_calibration: Option<ConfusionMatrix>,
    pub strong_error_calibration: Option<ConfusionMatrix>,
    pub scope_calibration: Option<ConfusionMatrix>,
    pub guards: Phase7AdjudicationCalibrationGuards,
    pub decision: Phase7AdjudicationCalibrationDecision,
    pub conclusion: String,
}

pub struct Phase7AdjudicationCalibrationEvaluator;

impl Phase7AdjudicationCalibrationEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7AdjudicationCalibrationReport> {
        evaluate(tag.into())
    }
}

pub fn load_phase7_adjudication_measurement_protocol(
) -> Result<Phase7AdjudicationMeasurementProtocol> {
    serde_json::from_str(PROTOCOL_JSON).context("parse Phase 7.3.1 measurement protocol")
}

pub fn load_phase7_reviewer_a_template() -> Result<ReviewerAnnotationSubmission> {
    serde_json::from_str(REVIEWER_A_JSON).context("parse Phase 7.3.1 Reviewer A template")
}

pub fn load_phase7_reviewer_b_template() -> Result<ReviewerAnnotationSubmission> {
    serde_json::from_str(REVIEWER_B_JSON).context("parse Phase 7.3.1 Reviewer B template")
}

pub fn load_phase7_adjudication_template() -> Result<AdjudicationSubmission> {
    serde_json::from_str(ADJUDICATION_JSON).context("parse Phase 7.3.1 adjudication template")
}

fn evaluate(tag: String) -> Result<Phase7AdjudicationCalibrationReport> {
    let execution = load_phase7_real_provider_execution()?;
    let protocol = load_phase7_adjudication_measurement_protocol()?;
    let reviewer_a = load_phase7_reviewer_a_template()?;
    let reviewer_b = load_phase7_reviewer_b_template()?;
    let adjudication = load_phase7_adjudication_template()?;

    validate_protocol(&protocol)?;
    let anchors = build_claim_source_anchors(&execution.outputs);
    validate_reviewer_submission(&reviewer_a, &protocol, &execution.execution_id, &anchors)?;
    validate_reviewer_submission(&reviewer_b, &protocol, &execution.execution_id, &anchors)?;
    validate_adjudication(&adjudication, &protocol, &reviewer_a, &reviewer_b)?;

    let guards = Phase7AdjudicationCalibrationGuards {
        frozen_phase7_2_3_outputs_reused: true,
        evidence_bundle_frozen: true,
        candidate_modified: false,
        frozen_judge_modified: false,
        prompt_modified: false,
        provider_modified: false,
        parser_modified: false,
        repair_policy_modified: false,
        extraction_algorithm_modified: false,
        provider_calls_made: false,
        reviewer_a_completed: reviewer_a.completed,
        reviewer_b_completed: reviewer_b.completed,
        independent_adjudication_completed: adjudication.completed,
        scorer_calibration_completed: false,
        held_out_cases_untouched: !protocol.held_out_accessed
            && !reviewer_a.held_out_accessed
            && !reviewer_b.held_out_accessed
            && !adjudication.held_out_accessed,
        runtime_authorized: false,
        hermes_authorized: false,
        candidate_learning_authorized: false,
        knowledge_promotion_authorized: false,
    };

    let decision = if !reviewer_a.completed || !reviewer_b.completed {
        Phase7AdjudicationCalibrationDecision::ProtocolReadyWaitingForIndependentAnnotation
    } else if !adjudication.completed {
        Phase7AdjudicationCalibrationDecision::IndependentAnnotationsReadyAdjudicationRequired
    } else {
        Phase7AdjudicationCalibrationDecision::AdjudicationCompleteCalibrationDiagnosticOnly
    };

    Ok(Phase7AdjudicationCalibrationReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: protocol.phase.clone(),
        purpose: "Freeze measurement-object separation, independent atomic-claim annotation, disagreement analysis, and frozen-judge calibration before any extractor or judge redesign.".to_string(),
        source_execution_sha256: sha256(include_bytes!(
            "../reports/phase7_2_3_real_provider_execution.json"
        )),
        protocol_sha256: sha256(PROTOCOL_JSON.as_bytes()),
        reviewer_a_template_sha256: sha256(REVIEWER_A_JSON.as_bytes()),
        reviewer_b_template_sha256: sha256(REVIEWER_B_JSON.as_bytes()),
        adjudication_template_sha256: sha256(ADJUDICATION_JSON.as_bytes()),
        protocol,
        claim_source_anchors: anchors,
        reviewer_a,
        reviewer_b,
        adjudication,
        metric_definitions: metric_definitions(),
        agreement: None,
        strict_safety_calibration: None,
        strong_error_calibration: None,
        scope_calibration: None,
        guards,
        decision,
        conclusion: "The Phase 7.3.1 protocol and calibration harness are ready, but no independent claim-level annotations or adjudicated semantic ground truth exist yet. Candidate and frozen-judge error rates must remain unreported until two blind submissions and adjudication are complete.".to_string(),
    })
}

fn validate_protocol(protocol: &Phase7AdjudicationMeasurementProtocol) -> Result<()> {
    if protocol.schema_version != 1 {
        bail!("unsupported_phase7_3_1_protocol_schema");
    }
    if protocol.measurement_objects.len() != 8 {
        bail!("phase7_3_1_requires_eight_separated_measurement_objects");
    }
    let objects = protocol
        .measurement_objects
        .iter()
        .map(|item| item.object)
        .collect::<BTreeSet<_>>();
    if objects.len() != protocol.measurement_objects.len() {
        bail!("phase7_3_1_measurement_objects_must_be_unique");
    }
    for item in &protocol.measurement_objects {
        let expected_studied = matches!(
            item.object,
            MeasurementObjectKind::Candidate | MeasurementObjectKind::FrozenJudge
        );
        if item.studied != expected_studied || item.modified {
            bail!("phase7_3_1_measurement_object_boundary_invalid");
        }
    }
    if protocol.calibration_policy.threshold_change_allowed
        || protocol.calibration_policy.prompt_change_allowed
        || protocol.calibration_policy.rule_change_allowed
        || protocol.calibration_policy.semantic_judge_addition_allowed
        || protocol.calibration_policy.same_data_optimization_allowed
    {
        bail!("phase7_3_1_is_calibration_not_optimization");
    }
    if protocol.held_out_accessed || protocol.runtime_authorized || protocol.hermes_authorized {
        bail!("phase7_3_1_boundary_violation");
    }
    Ok(())
}

fn validate_reviewer_submission(
    submission: &ReviewerAnnotationSubmission,
    protocol: &Phase7AdjudicationMeasurementProtocol,
    execution_id: &str,
    anchors: &[ClaimSourceAnchor],
) -> Result<()> {
    if submission.protocol_id != protocol.protocol_id
        || submission.source_execution_id != execution_id
    {
        bail!("phase7_3_1_reviewer_source_or_protocol_mismatch");
    }
    if !submission.blind_to_other_reviewer
        || !submission.blind_to_frozen_judge
        || !submission.blind_to_phase7_3_aggregates
        || submission.held_out_accessed
    {
        bail!("phase7_3_1_reviewer_must_remain_blind_and_design_only");
    }
    if !submission.completed {
        if !submission.claims.is_empty() {
            bail!("incomplete_reviewer_template_must_not_contain_partial_labels");
        }
        return Ok(());
    }
    if submission.claims.is_empty() {
        bail!("completed_reviewer_submission_requires_claims");
    }

    let valid_anchors = anchors
        .iter()
        .map(|anchor| anchor.anchor_id.as_str())
        .collect::<BTreeSet<_>>();
    let mut claim_ids = BTreeSet::new();
    for claim in &submission.claims {
        if !claim_ids.insert(claim.claim_id.as_str()) {
            bail!("duplicate_reviewer_claim_id");
        }
        if !valid_anchors.contains(claim.anchor_id.as_str()) {
            bail!("reviewer_claim_anchor_not_in_frozen_candidate_outputs");
        }
        let anchor = anchors
            .iter()
            .find(|anchor| anchor.anchor_id == claim.anchor_id)
            .context("resolve reviewer claim anchor")?;
        if claim.case_id != anchor.case_id || claim.response_sha256 != anchor.response_sha256 {
            bail!("reviewer_claim_candidate_identity_mismatch");
        }
        if claim.claim_text.trim().is_empty() || claim.reviewer_rationale.trim().is_empty() {
            bail!("reviewer_claim_text_and_rationale_required");
        }
    }
    Ok(())
}

fn validate_adjudication(
    adjudication: &AdjudicationSubmission,
    protocol: &Phase7AdjudicationMeasurementProtocol,
    reviewer_a: &ReviewerAnnotationSubmission,
    reviewer_b: &ReviewerAnnotationSubmission,
) -> Result<()> {
    if adjudication.protocol_id != protocol.protocol_id
        || adjudication.reviewer_a_submission_id != reviewer_a.submission_id
        || adjudication.reviewer_b_submission_id != reviewer_b.submission_id
    {
        bail!("phase7_3_1_adjudication_identity_mismatch");
    }
    if adjudication.held_out_accessed || !adjudication.disagreements_preserved {
        bail!("phase7_3_1_adjudication_boundary_invalid");
    }
    if !adjudication.completed {
        if !adjudication.claims.is_empty() {
            bail!("incomplete_adjudication_template_must_not_contain_results");
        }
        return Ok(());
    }
    if !reviewer_a.completed || !reviewer_b.completed || adjudication.claims.is_empty() {
        bail!("adjudication_requires_two_completed_independent_submissions");
    }
    Ok(())
}

fn build_claim_source_anchors(
    outputs: &[crate::phase7_pattern_provider_comparison::ModelProviderCaseOutput],
) -> Vec<ClaimSourceAnchor> {
    let mut anchors = Vec::new();
    for output in outputs {
        push_anchor(
            &mut anchors,
            output,
            ClaimSourceField::Proposition,
            0,
            &output.candidate.proposition,
        );
        for (index, prediction) in output.candidate.predictions.iter().enumerate() {
            push_anchor(
                &mut anchors,
                output,
                ClaimSourceField::PredictionStatement,
                index,
                &prediction.statement,
            );
            push_anchor(
                &mut anchors,
                output,
                ClaimSourceField::PredictionObservable,
                index,
                &prediction.observable,
            );
            push_anchor(
                &mut anchors,
                output,
                ClaimSourceField::PredictionSuccessCriterion,
                index,
                &prediction.success_criterion,
            );
        }
        for (index, falsification) in output.candidate.falsification_conditions.iter().enumerate() {
            push_anchor(
                &mut anchors,
                output,
                ClaimSourceField::FalsificationStatement,
                index,
                &falsification.statement,
            );
            push_anchor(
                &mut anchors,
                output,
                ClaimSourceField::FalsificationObservable,
                index,
                &falsification.observable,
            );
        }
    }
    anchors
}

fn push_anchor(
    anchors: &mut Vec<ClaimSourceAnchor>,
    output: &crate::phase7_pattern_provider_comparison::ModelProviderCaseOutput,
    source_field: ClaimSourceField,
    source_index: usize,
    text: &str,
) {
    let field = match source_field {
        ClaimSourceField::Proposition => "proposition",
        ClaimSourceField::PredictionStatement => "prediction_statement",
        ClaimSourceField::PredictionObservable => "prediction_observable",
        ClaimSourceField::PredictionSuccessCriterion => "prediction_success_criterion",
        ClaimSourceField::FalsificationStatement => "falsification_statement",
        ClaimSourceField::FalsificationObservable => "falsification_observable",
    };
    anchors.push(ClaimSourceAnchor {
        anchor_id: format!("{}-{}-{:02}", output.case_id, field, source_index + 1),
        case_id: output.case_id.clone(),
        response_sha256: output.response_sha256.clone(),
        source_field,
        source_index,
        source_text: text.to_string(),
        source_text_sha256: sha256(text.as_bytes()),
        requires_independent_atomic_segmentation: true,
    });
}

pub fn compute_support_agreement(
    labels: &[(HumanSupportLabel, HumanSupportLabel)],
) -> SupportAgreementMetrics {
    let excluded = labels
        .iter()
        .filter(|(a, b)| {
            *a == HumanSupportLabel::NotAssessable || *b == HumanSupportLabel::NotAssessable
        })
        .count();
    let usable = labels
        .iter()
        .copied()
        .filter(|(a, b)| {
            *a != HumanSupportLabel::NotAssessable && *b != HumanSupportLabel::NotAssessable
        })
        .collect::<Vec<_>>();
    let boundary = usable
        .iter()
        .filter(|(a, b)| support_distance(*a, *b) == 1)
        .count();
    let fundamental = usable
        .iter()
        .filter(|(a, b)| support_distance(*a, *b) == 2)
        .count();
    let agreements = usable.iter().filter(|(a, b)| a == b).count();

    SupportAgreementMetrics {
        aligned_claim_count: usable.len(),
        excluded_not_assessable_count: excluded,
        raw_agreement: ratio(agreements, usable.len()),
        raw_agreement_wilson_95: wilson_95(agreements, usable.len()),
        linear_weighted_kappa: linear_weighted_kappa(&usable),
        boundary_disagreement_count: boundary,
        fundamental_disagreement_count: fundamental,
    }
}

pub fn aggregate_candidate_support_label(
    labels: impl IntoIterator<Item = HumanSupportLabel>,
) -> HumanSupportLabel {
    let labels = labels.into_iter().collect::<Vec<_>>();
    if labels.contains(&HumanSupportLabel::Unsupported) {
        HumanSupportLabel::Unsupported
    } else if labels.contains(&HumanSupportLabel::PartiallySupported) {
        HumanSupportLabel::PartiallySupported
    } else if labels.contains(&HumanSupportLabel::Supported) {
        HumanSupportLabel::Supported
    } else {
        HumanSupportLabel::NotAssessable
    }
}

pub fn aggregate_candidate_scope_expansion(
    labels: impl IntoIterator<Item = ScopeAssessment>,
) -> Option<bool> {
    let labels = labels.into_iter().collect::<Vec<_>>();
    if labels.contains(&ScopeAssessment::Expanded) {
        Some(true)
    } else if labels.contains(&ScopeAssessment::Preserved) {
        Some(false)
    } else {
        None
    }
}

pub fn compute_confusion_matrix(
    rows: &[CandidateJudgeCalibrationRow],
    view: BinaryCalibrationView,
) -> ConfusionMatrix {
    compute_binary_confusion_matrix(rows.iter().map(|row| {
        (
            binary_human_label(row.human_support_label, view),
            row.frozen_judge_unsupported_warning,
        )
    }))
}

pub fn compute_scope_confusion_matrix(rows: &[ScopeJudgeCalibrationRow]) -> ConfusionMatrix {
    compute_binary_confusion_matrix(
        rows.iter()
            .map(|row| (row.human_scope_expanded, row.frozen_judge_scope_warning)),
    )
}

fn compute_binary_confusion_matrix(
    rows: impl IntoIterator<Item = (Option<bool>, bool)>,
) -> ConfusionMatrix {
    let mut tp = 0usize;
    let mut fp = 0usize;
    let mut false_negative = 0usize;
    let mut tn = 0usize;
    let mut excluded = 0usize;

    for (human_positive, scorer_positive) in rows {
        let human_positive = match human_positive {
            Some(value) => value,
            None => {
                excluded += 1;
                continue;
            }
        };
        match (human_positive, scorer_positive) {
            (true, true) => tp += 1,
            (false, true) => fp += 1,
            (true, false) => false_negative += 1,
            (false, false) => tn += 1,
        }
    }

    let precision = ratio(tp, tp + fp);
    let recall = ratio(tp, tp + false_negative);
    let specificity = ratio(tn, tn + fp);
    let false_positive_rate = ratio(fp, fp + tn);
    let false_negative_rate = ratio(false_negative, false_negative + tp);
    let balanced_accuracy = match (recall, specificity) {
        (Some(sensitivity), Some(specificity)) => Some((sensitivity + specificity) / 2.0),
        _ => None,
    };
    let denominator = ((tp + fp) as f64
        * (tp + false_negative) as f64
        * (tn + fp) as f64
        * (tn + false_negative) as f64)
        .sqrt();
    let mcc = if denominator == 0.0 {
        None
    } else {
        Some((tp as f64 * tn as f64 - fp as f64 * false_negative as f64) / denominator)
    };

    ConfusionMatrix {
        true_positive: tp,
        false_positive: fp,
        false_negative,
        true_negative: tn,
        excluded,
        precision,
        precision_wilson_95: wilson_95(tp, tp + fp),
        recall_sensitivity: recall,
        recall_sensitivity_wilson_95: wilson_95(tp, tp + false_negative),
        specificity,
        specificity_wilson_95: wilson_95(tn, tn + fp),
        false_positive_rate,
        false_positive_rate_wilson_95: wilson_95(fp, fp + tn),
        false_negative_rate,
        false_negative_rate_wilson_95: wilson_95(false_negative, false_negative + tp),
        balanced_accuracy,
        matthews_correlation_coefficient: mcc,
    }
}
fn binary_human_label(label: HumanSupportLabel, view: BinaryCalibrationView) -> Option<bool> {
    match (view, label) {
        (_, HumanSupportLabel::Supported) => Some(false),
        (BinaryCalibrationView::StrictSafety, HumanSupportLabel::PartiallySupported) => Some(true),
        (BinaryCalibrationView::StrictSafety, HumanSupportLabel::Unsupported) => Some(true),
        (BinaryCalibrationView::StrongError, HumanSupportLabel::Unsupported) => Some(true),
        (_, HumanSupportLabel::PartiallySupported | HumanSupportLabel::NotAssessable) => None,
    }
}

fn linear_weighted_kappa(labels: &[(HumanSupportLabel, HumanSupportLabel)]) -> Option<f64> {
    if labels.is_empty() {
        return None;
    }
    let mut observed = 0.0;
    let mut a_counts = [0usize; 3];
    let mut b_counts = [0usize; 3];
    for (a, b) in labels {
        let ai = support_index(*a)?;
        let bi = support_index(*b)?;
        observed += linear_weight(ai, bi);
        a_counts[ai] += 1;
        b_counts[bi] += 1;
    }
    observed /= labels.len() as f64;

    let total = labels.len() as f64;
    let mut expected = 0.0;
    for (ai, a_count) in a_counts.iter().enumerate() {
        for (bi, b_count) in b_counts.iter().enumerate() {
            expected +=
                (*a_count as f64 / total) * (*b_count as f64 / total) * linear_weight(ai, bi);
        }
    }
    if (1.0 - expected).abs() < f64::EPSILON {
        Some(if (1.0 - observed).abs() < f64::EPSILON {
            1.0
        } else {
            0.0
        })
    } else {
        Some((observed - expected) / (1.0 - expected))
    }
}

fn support_index(label: HumanSupportLabel) -> Option<usize> {
    match label {
        HumanSupportLabel::Supported => Some(0),
        HumanSupportLabel::PartiallySupported => Some(1),
        HumanSupportLabel::Unsupported => Some(2),
        HumanSupportLabel::NotAssessable => None,
    }
}

fn support_distance(a: HumanSupportLabel, b: HumanSupportLabel) -> usize {
    support_index(a)
        .zip(support_index(b))
        .map(|(a, b)| a.abs_diff(b))
        .unwrap_or(0)
}

fn linear_weight(a: usize, b: usize) -> f64 {
    1.0 - a.abs_diff(b) as f64 / 2.0
}

fn metric_definitions() -> Vec<MetricDefinition> {
    vec![
        metric("support_label_raw_agreement", "Exact agreement over aligned assessable atomic claims."),
        metric("linear_weighted_kappa", "Chance-corrected agreement that treats adjacent support-label disagreement as less severe than supported-versus-unsupported disagreement."),
        metric("boundary_disagreement_rate", "Adjacent Supported/Partially Supported or Partially Supported/Unsupported disagreements divided by aligned assessable claims."),
        metric("fundamental_disagreement_rate", "Supported-versus-Unsupported disagreements divided by aligned assessable claims."),
        metric("judge_precision", "Human-confirmed unsupported claims among frozen-judge unsupported warnings."),
        metric("judge_recall_sensitivity", "Human-confirmed unsupported claims detected by the frozen judge."),
        metric("judge_specificity", "Human-supported claims not warned on by the frozen judge."),
        metric("judge_false_positive_rate", "Human-supported claims warned on by the frozen judge."),
        metric("judge_false_negative_rate", "Human-unsupported claims missed by the frozen judge."),
        metric("balanced_accuracy", "Mean of frozen-judge sensitivity and specificity."),
        metric("matthews_correlation_coefficient", "Balanced binary calibration correlation, undefined when its denominator is zero."),
    ]
}

fn metric(name: &str, definition: &str) -> MetricDefinition {
    MetricDefinition {
        name: name.to_string(),
        definition: definition.to_string(),
    }
}

fn wilson_95(successes: usize, total: usize) -> Option<ConfidenceInterval> {
    if total == 0 {
        return None;
    }
    let z = 1.959_963_984_540_054_f64;
    let n = total as f64;
    let p = successes as f64 / n;
    let denominator = 1.0 + z * z / n;
    let center = (p + z * z / (2.0 * n)) / denominator;
    let margin = z * ((p * (1.0 - p) / n + z * z / (4.0 * n * n)).sqrt()) / denominator;
    Some(ConfidenceInterval {
        lower: (center - margin).max(0.0),
        upper: (center + margin).min(1.0),
    })
}

fn ratio(numerator: usize, denominator: usize) -> Option<f64> {
    if denominator == 0 {
        None
    } else {
        Some(numerator as f64 / denominator as f64)
    }
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
