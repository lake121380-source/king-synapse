use crate::phase7_independent_adjudication_calibration::HumanSupportLabel;
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const PROTOCOL_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_3_atomic_claim_measurement_protocol.json"
);
const CONTROL_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_3_3_atomic_claim_controls.json");
const PROMPT_BYTES: &[u8] = include_bytes!("../config/phase7_3_3_atomic_claim_judge_prompt_v1.md");
const SILVER_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_1_model_adjudicated_silver_labels.json"
);
const PHASE7_3_2_REPORT_BYTES: &[u8] =
    include_bytes!("../reports/phase7_semantic_judge_redesign.json");
const EVALUATION_VERSION: &str = "phase7.3.3-atomic-claim-measurement-v1";

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum AtomicClaimType {
    Proposition,
    Scope,
    Prediction,
    Causal,
    Counterexample,
    Limitation,
    Falsifiability,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimCentrality {
    Central,
    Material,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimOrigin {
    Explicit,
    Inferred,
    Synthesized,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SourceSpan {
    pub start: usize,
    pub end: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ControlEvidence {
    pub evidence_id: String,
    pub text: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicControlClaim {
    pub claim_id: String,
    pub source_span: SourceSpan,
    pub claim_text: String,
    pub claim_type: AtomicClaimType,
    pub centrality: ClaimCentrality,
    pub material: bool,
    pub claim_origin: ClaimOrigin,
    pub expected_support_label: HumanSupportLabel,
    pub evidence_ids: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicControlCase {
    pub control_id: String,
    pub evidence: Vec<ControlEvidence>,
    pub candidate_text: String,
    pub claims: Vec<AtomicControlClaim>,
    pub expected_candidate_label: HumanSupportLabel,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicControlGuards {
    pub provider_training_authorized: bool,
    pub prompt_tuning_authorized: bool,
    pub held_out_member: bool,
    pub human_gold_claimed_for_real_candidates: bool,
    pub runtime_authorized: bool,
    pub memory_write_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicControlDataset {
    pub schema_version: u32,
    pub dataset_id: String,
    pub purpose: String,
    pub label_balance: BTreeMap<String, usize>,
    pub control_cases: Vec<AtomicControlCase>,
    pub guards: AtomicControlGuards,
}

#[derive(Clone, Debug, Deserialize)]
struct MeasurementProtocol {
    protocol_id: String,
    hypothesis_status: String,
}

#[derive(Clone, Debug, Deserialize)]
struct SilverFreeze {
    candidates: Vec<SilverCandidate>,
}

#[derive(Clone, Debug, Deserialize)]
struct SilverCandidate {
    aggregate_support_label: HumanSupportLabel,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ConstantCollapseProbe {
    pub predicted_label: HumanSupportLabel,
    pub case_count: usize,
    pub exact_match_count: usize,
    pub exact_accuracy: f64,
    pub macro_recall: f64,
    pub prediction_entropy_bits: f64,
    pub single_class_prediction_rate: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct LegacyDesignDistribution {
    pub case_count: usize,
    pub label_counts: BTreeMap<String, usize>,
    pub majority_label: HumanSupportLabel,
    pub majority_class_accuracy: f64,
    pub phase7_3_2_collapsed_prediction: HumanSupportLabel,
    pub phase7_3_2_exact_agreement: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicClaimProtocolValidation {
    pub control_case_count: usize,
    pub atomic_claim_count: usize,
    pub exact_source_span_count: usize,
    pub unique_control_ids: bool,
    pub unique_claim_ids: bool,
    pub exactly_one_central_claim_per_case: bool,
    pub evidence_references_valid: bool,
    pub expected_aggregation_consistent: bool,
    pub balanced_four_class_controls: bool,
    pub all_claim_types_covered: bool,
    pub candidate_label_counts: BTreeMap<String, usize>,
    pub claim_type_counts: BTreeMap<String, usize>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicClaimArtifactHashes {
    pub protocol_sha256: String,
    pub balanced_controls_sha256: String,
    pub prompt_sha256: String,
    pub model_adjudicated_silver_sha256: String,
    pub phase7_3_2_report_sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicClaimGuards {
    pub controls_are_protocol_diagnostics_not_capability_evidence: bool,
    pub real_design_candidates_frozen: bool,
    pub extractor_frozen: bool,
    pub provider_frozen: bool,
    pub prompt_optimization_authorized: bool,
    pub aggregation_tuning_after_execution_authorized: bool,
    pub model_execution_completed: bool,
    pub held_out_cases_untouched: bool,
    pub human_gold_claimed: bool,
    pub memory_write_authorized: bool,
    pub pattern_promotion_authorized: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7AtomicClaimMeasurementReport {
    pub schema_version: u32,
    pub report_id: String,
    pub phase: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub status: String,
    pub hypothesis: String,
    pub hypothesis_status: String,
    pub protocol_id: String,
    pub protocol_validation: AtomicClaimProtocolValidation,
    pub legacy_design_distribution: LegacyDesignDistribution,
    pub collapse_probes: Vec<ConstantCollapseProbe>,
    pub aggregation_policy: String,
    pub aggregation_uses_numeric_weights: bool,
    pub decision: String,
    pub interpretation: Vec<String>,
    pub next_gate: Vec<String>,
    pub artifact_hashes: AtomicClaimArtifactHashes,
    pub guards: AtomicClaimGuards,
}

pub struct Phase7AtomicClaimMeasurementEvaluator;

impl Phase7AtomicClaimMeasurementEvaluator {
    pub fn evaluate(report_id: impl Into<String>) -> Result<Phase7AtomicClaimMeasurementReport> {
        let protocol: MeasurementProtocol =
            serde_json::from_slice(PROTOCOL_BYTES).context("parse Phase 7.3.3 protocol")?;
        let controls: AtomicControlDataset =
            serde_json::from_slice(CONTROL_BYTES).context("parse Phase 7.3.3 controls")?;
        let silver: SilverFreeze = serde_json::from_slice(SILVER_BYTES)
            .context("parse frozen model-adjudicated silver")?;

        let protocol_validation = validate_controls(&controls)?;
        let legacy_design_distribution = legacy_distribution(&silver)?;
        let collapse_probes = all_labels()
            .into_iter()
            .map(|label| constant_probe(&controls, label))
            .collect::<Vec<_>>();

        Ok(Phase7AtomicClaimMeasurementReport {
            schema_version: 1,
            report_id: report_id.into(),
            phase: "Phase 7.3.3 Atomic Claim Measurement Protocol".to_string(),
            evaluation_version: EVALUATION_VERSION.to_string(),
            generated_at: Utc::now().to_rfc3339(),
            status: "protocol_frozen_model_execution_pending".to_string(),
            hypothesis: "Candidate-level many-to-one labeling creates a partially-supported attractor; atomic local judgments plus deterministic aggregation may improve diagnostic discrimination.".to_string(),
            hypothesis_status: protocol.hypothesis_status,
            protocol_id: protocol.protocol_id,
            protocol_validation,
            legacy_design_distribution,
            collapse_probes,
            aggregation_policy: "phase7.3.3-central-claim-gate-v1".to_string(),
            aggregation_uses_numeric_weights: false,
            decision: "atomic_claim_protocol_ready_not_yet_capability_validated".to_string(),
            interpretation: vec![
                "The Phase 7.3.2 exact agreement of 0.70 is compatible with majority-class collapse because seven of ten Silver Candidate labels are partially_supported.".to_string(),
                "Balanced controls reduce every single-class predictor to 0.25 exact accuracy and 0.25 macro recall, so collapse cannot masquerade as strong agreement.".to_string(),
                "The controls validate measurement mechanics only; no atomic Judge capability result exists until a frozen model execution is completed.".to_string(),
                "Rule-based central-claim aggregation is frozen without numeric weights to avoid result-driven tuning.".to_string(),
            ],
            next_gate: vec![
                "Run the frozen atomic Judge on all sixteen balanced controls without prompt, parser, or aggregation changes.".to_string(),
                "Require all four labels to be predicted and macro recall to exceed the 0.25 single-class baseline before applying the protocol to the ten real design Candidates.".to_string(),
                "After control readiness, execute the same frozen protocol on the ten real design Candidates and compare discrimination with Phase 7.3.2.".to_string(),
                "Keep held-out data closed until control readiness and design-only diagnostic improvement are both established.".to_string(),
            ],
            artifact_hashes: AtomicClaimArtifactHashes {
                protocol_sha256: sha256(PROTOCOL_BYTES),
                balanced_controls_sha256: sha256(CONTROL_BYTES),
                prompt_sha256: sha256(PROMPT_BYTES),
                model_adjudicated_silver_sha256: sha256(SILVER_BYTES),
                phase7_3_2_report_sha256: sha256(PHASE7_3_2_REPORT_BYTES),
            },
            guards: AtomicClaimGuards {
                controls_are_protocol_diagnostics_not_capability_evidence: true,
                real_design_candidates_frozen: true,
                extractor_frozen: true,
                provider_frozen: true,
                prompt_optimization_authorized: false,
                aggregation_tuning_after_execution_authorized: false,
                model_execution_completed: false,
                held_out_cases_untouched: true,
                human_gold_claimed: false,
                memory_write_authorized: false,
                pattern_promotion_authorized: false,
                runtime_authorized: false,
                hermes_authorized: false,
            },
        })
    }
}

pub fn aggregate_candidate_label(claims: &[AtomicControlClaim]) -> Result<HumanSupportLabel> {
    let central = claims
        .iter()
        .filter(|claim| claim.centrality == ClaimCentrality::Central)
        .collect::<Vec<_>>();
    if central.len() != 1 {
        bail!(
            "exactly one central claim is required, found {}",
            central.len()
        );
    }
    match central[0].expected_support_label {
        HumanSupportLabel::Unsupported => return Ok(HumanSupportLabel::Unsupported),
        HumanSupportLabel::NotAssessable => return Ok(HumanSupportLabel::NotAssessable),
        HumanSupportLabel::PartiallySupported => return Ok(HumanSupportLabel::PartiallySupported),
        HumanSupportLabel::Supported => {}
    }
    if claims.iter().any(|claim| {
        claim.material
            && claim.centrality != ClaimCentrality::Central
            && claim.expected_support_label != HumanSupportLabel::Supported
    }) {
        return Ok(HumanSupportLabel::PartiallySupported);
    }
    Ok(HumanSupportLabel::Supported)
}

fn validate_controls(controls: &AtomicControlDataset) -> Result<AtomicClaimProtocolValidation> {
    if controls.control_cases.len() != 16 {
        bail!(
            "expected 16 balanced controls, found {}",
            controls.control_cases.len()
        );
    }
    let mut control_ids = BTreeSet::new();
    let mut claim_ids = BTreeSet::new();
    let mut candidate_label_counts = BTreeMap::<String, usize>::new();
    let mut claim_type_counts = BTreeMap::<String, usize>::new();
    let mut claim_count = 0usize;
    let mut exact_spans = 0usize;
    let mut central_ok = true;
    let mut evidence_ok = true;
    let mut aggregation_ok = true;

    for case in &controls.control_cases {
        if !control_ids.insert(case.control_id.clone()) {
            bail!("duplicate control id {}", case.control_id);
        }
        *candidate_label_counts
            .entry(label_name(case.expected_candidate_label).to_string())
            .or_default() += 1;
        let evidence_ids = case
            .evidence
            .iter()
            .map(|row| row.evidence_id.as_str())
            .collect::<BTreeSet<_>>();
        let central_count = case
            .claims
            .iter()
            .filter(|claim| claim.centrality == ClaimCentrality::Central)
            .count();
        central_ok &= central_count == 1;

        for claim in &case.claims {
            claim_count += 1;
            if !claim_ids.insert(claim.claim_id.clone()) {
                bail!("duplicate claim id {}", claim.claim_id);
            }
            *claim_type_counts
                .entry(claim_type_name(claim.claim_type).to_string())
                .or_default() += 1;
            let span = &claim.source_span;
            if span.start > span.end || span.end > case.candidate_text.len() {
                bail!("invalid source span for {}", claim.claim_id);
            }
            if !case.candidate_text.is_char_boundary(span.start)
                || !case.candidate_text.is_char_boundary(span.end)
            {
                bail!(
                    "source span is not on UTF-8 boundaries for {}",
                    claim.claim_id
                );
            }
            if &case.candidate_text[span.start..span.end] != claim.claim_text {
                bail!("source span text mismatch for {}", claim.claim_id);
            }
            exact_spans += 1;
            evidence_ok &= !claim.evidence_ids.is_empty()
                && claim
                    .evidence_ids
                    .iter()
                    .all(|id| evidence_ids.contains(id.as_str()));
        }
        aggregation_ok &= aggregate_candidate_label(&case.claims)? == case.expected_candidate_label;
    }

    let balanced = all_labels().into_iter().all(|label| {
        candidate_label_counts
            .get(label_name(label))
            .copied()
            .unwrap_or(0)
            == 4
    });
    let all_claim_types_covered = all_claim_types().into_iter().all(|claim_type| {
        claim_type_counts
            .get(claim_type_name(claim_type))
            .copied()
            .unwrap_or(0)
            > 0
    });
    if !balanced || !all_claim_types_covered || !central_ok || !evidence_ok || !aggregation_ok {
        bail!("Phase 7.3.3 control validation failed");
    }

    Ok(AtomicClaimProtocolValidation {
        control_case_count: controls.control_cases.len(),
        atomic_claim_count: claim_count,
        exact_source_span_count: exact_spans,
        unique_control_ids: control_ids.len() == controls.control_cases.len(),
        unique_claim_ids: claim_ids.len() == claim_count,
        exactly_one_central_claim_per_case: central_ok,
        evidence_references_valid: evidence_ok,
        expected_aggregation_consistent: aggregation_ok,
        balanced_four_class_controls: balanced,
        all_claim_types_covered,
        candidate_label_counts,
        claim_type_counts,
    })
}

fn legacy_distribution(silver: &SilverFreeze) -> Result<LegacyDesignDistribution> {
    if silver.candidates.is_empty() {
        bail!("frozen Silver Candidate list is empty");
    }
    let mut counts = BTreeMap::<String, usize>::new();
    for candidate in &silver.candidates {
        *counts
            .entry(label_name(candidate.aggregate_support_label).to_string())
            .or_default() += 1;
    }
    let (majority_name, majority_count) = counts
        .iter()
        .max_by_key(|(_, count)| **count)
        .map(|(name, count)| (name.clone(), *count))
        .context("determine Silver majority label")?;
    let majority_label = parse_label(&majority_name)?;
    Ok(LegacyDesignDistribution {
        case_count: silver.candidates.len(),
        label_counts: counts,
        majority_label,
        majority_class_accuracy: majority_count as f64 / silver.candidates.len() as f64,
        phase7_3_2_collapsed_prediction: HumanSupportLabel::PartiallySupported,
        phase7_3_2_exact_agreement: 0.7,
    })
}

fn constant_probe(
    controls: &AtomicControlDataset,
    predicted_label: HumanSupportLabel,
) -> ConstantCollapseProbe {
    let exact = controls
        .control_cases
        .iter()
        .filter(|case| case.expected_candidate_label == predicted_label)
        .count();
    let macro_recall = all_labels()
        .into_iter()
        .map(|label| if label == predicted_label { 1.0 } else { 0.0 })
        .sum::<f64>()
        / 4.0;
    ConstantCollapseProbe {
        predicted_label,
        case_count: controls.control_cases.len(),
        exact_match_count: exact,
        exact_accuracy: exact as f64 / controls.control_cases.len() as f64,
        macro_recall,
        prediction_entropy_bits: 0.0,
        single_class_prediction_rate: 1.0,
    }
}

fn all_claim_types() -> [AtomicClaimType; 7] {
    [
        AtomicClaimType::Proposition,
        AtomicClaimType::Scope,
        AtomicClaimType::Prediction,
        AtomicClaimType::Causal,
        AtomicClaimType::Counterexample,
        AtomicClaimType::Limitation,
        AtomicClaimType::Falsifiability,
    ]
}

fn all_labels() -> [HumanSupportLabel; 4] {
    [
        HumanSupportLabel::Supported,
        HumanSupportLabel::PartiallySupported,
        HumanSupportLabel::Unsupported,
        HumanSupportLabel::NotAssessable,
    ]
}

fn label_name(label: HumanSupportLabel) -> &'static str {
    match label {
        HumanSupportLabel::Supported => "supported",
        HumanSupportLabel::PartiallySupported => "partially_supported",
        HumanSupportLabel::Unsupported => "unsupported",
        HumanSupportLabel::NotAssessable => "not_assessable",
    }
}

fn parse_label(value: &str) -> Result<HumanSupportLabel> {
    match value {
        "supported" => Ok(HumanSupportLabel::Supported),
        "partially_supported" => Ok(HumanSupportLabel::PartiallySupported),
        "unsupported" => Ok(HumanSupportLabel::Unsupported),
        "not_assessable" => Ok(HumanSupportLabel::NotAssessable),
        _ => bail!("unknown support label {value}"),
    }
}

fn claim_type_name(claim_type: AtomicClaimType) -> &'static str {
    match claim_type {
        AtomicClaimType::Proposition => "proposition",
        AtomicClaimType::Scope => "scope",
        AtomicClaimType::Prediction => "prediction",
        AtomicClaimType::Causal => "causal",
        AtomicClaimType::Counterexample => "counterexample",
        AtomicClaimType::Limitation => "limitation",
        AtomicClaimType::Falsifiability => "falsifiability",
    }
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn controls() -> AtomicControlDataset {
        serde_json::from_slice(CONTROL_BYTES).expect("controls parse")
    }

    #[test]
    fn balanced_controls_are_structurally_valid() {
        let validation = validate_controls(&controls()).expect("controls valid");
        assert_eq!(validation.control_case_count, 16);
        assert!(validation.balanced_four_class_controls);
        assert!(validation.all_claim_types_covered);
        assert_eq!(validation.claim_type_counts.len(), 7);
        assert!(validation.expected_aggregation_consistent);
        assert_eq!(
            validation.atomic_claim_count,
            validation.exact_source_span_count
        );
    }

    #[test]
    fn aggregation_respects_central_claim_gate() {
        let dataset = controls();
        for case in dataset.control_cases {
            assert_eq!(
                aggregate_candidate_label(&case.claims).expect("aggregation"),
                case.expected_candidate_label,
                "{}",
                case.control_id
            );
        }
    }

    #[test]
    fn balanced_controls_expose_every_constant_predictor() {
        let dataset = controls();
        for label in all_labels() {
            let probe = constant_probe(&dataset, label);
            assert_eq!(probe.exact_accuracy, 0.25);
            assert_eq!(probe.macro_recall, 0.25);
            assert_eq!(probe.single_class_prediction_rate, 1.0);
        }
    }

    #[test]
    fn report_keeps_all_runtime_and_learning_gates_closed() {
        let report = Phase7AtomicClaimMeasurementEvaluator::evaluate("test").expect("report");
        assert_eq!(
            report.decision,
            "atomic_claim_protocol_ready_not_yet_capability_validated"
        );
        assert!(!report.guards.model_execution_completed);
        assert!(report.guards.held_out_cases_untouched);
        assert!(!report.guards.memory_write_authorized);
        assert!(!report.guards.pattern_promotion_authorized);
        assert!(!report.guards.runtime_authorized);
        assert!(!report.guards.hermes_authorized);
        assert_eq!(
            report.legacy_design_distribution.majority_class_accuracy,
            0.7
        );
    }
}
