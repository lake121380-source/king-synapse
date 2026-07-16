use crate::phase7_atomic_claim_measurement::{
    aggregate_candidate_label, AtomicClaimType, AtomicControlCase, AtomicControlDataset,
    ClaimCentrality, ClaimOrigin, ControlEvidence, SourceSpan,
};
use crate::phase7_independent_adjudication_calibration::HumanSupportLabel;
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const PROTOCOL_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_3_c_segmentation_controlled_classification_protocol_v1.json"
);
const PROVIDER_CONTROLS_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_3_c_segmentation_controlled_claim_controls_v1.json"
);
const ORIGINAL_CONTROLS_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_3_3_atomic_claim_controls.json");
const SUPPLEMENT_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_3_a_partial_atomic_claim_supplement_v1.json"
);
const PROMPT_BYTES: &[u8] =
    include_bytes!("../config/phase7_3_3_c_atomic_claim_classifier_prompt_v1.md");
const NEGATIVE_ANALYSIS_BYTES: &[u8] =
    include_bytes!("../reports/phase7_3_3_a_negative_result_analysis.json");
const EVALUATION_VERSION: &str =
    "phase7.3.3-c-segmentation-controlled-atomic-claim-classification-v1";

#[derive(Clone, Debug, Deserialize)]
struct ClassificationProtocol {
    protocol_id: String,
    status: String,
    frozen_artifact_sha256: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ControlledAtomicClaim {
    pub claim_id: String,
    pub source_span: SourceSpan,
    pub claim_text: String,
    pub claim_type: AtomicClaimType,
    pub centrality: ClaimCentrality,
    pub material: bool,
    pub claim_origin: ClaimOrigin,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ControlledProviderPacket {
    pub case_id: String,
    pub evaluation_lane: String,
    pub evidence: Vec<ControlEvidence>,
    pub candidate_text: String,
    pub atomic_claims: Vec<ControlledAtomicClaim>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
struct ProviderPacketGuards {
    expected_claim_labels_included: bool,
    expected_candidate_labels_included: bool,
    gold_evidence_attributions_included: bool,
    claim_boundaries_provider_mutable: bool,
    design_cases_included: bool,
    held_out_included: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
struct ControlledProviderDataset {
    schema_version: u32,
    dataset_id: String,
    phase: String,
    purpose: String,
    source_artifact_sha256: BTreeMap<String, String>,
    packet_count: usize,
    original_candidate_gate_packet_count: usize,
    diagnostics_only_supplement_packet_count: usize,
    provider_packets: Vec<ControlledProviderPacket>,
    guards: ProviderPacketGuards,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct LocalClaimJudgment {
    pub claim_id: String,
    pub support_label: HumanSupportLabel,
    pub evidence_ids: Vec<String>,
    pub reason_codes: Vec<String>,
    pub rationale: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct ControlledJudgeOutput {
    pub case_id: String,
    pub claim_judgments: Vec<LocalClaimJudgment>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SegmentationControlledValidation {
    pub provider_packet_count: usize,
    pub original_candidate_gate_packet_count: usize,
    pub diagnostics_supplement_packet_count: usize,
    pub atomic_claim_count: usize,
    pub all_packet_ids_unique: bool,
    pub all_claim_ids_unique: bool,
    pub all_protocol_owned_spans_exact: bool,
    pub provider_packets_match_frozen_gold_structure: bool,
    pub provider_packets_contain_no_gold_labels: bool,
    pub perfect_probe_accepted: bool,
    pub perfect_probe_candidate_aggregation_correct: bool,
    pub missing_claim_rejected: bool,
    pub duplicate_claim_rejected: bool,
    pub unknown_claim_rejected: bool,
    pub reordered_claim_rejected: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SegmentationControlledArtifactHashes {
    pub protocol_sha256: String,
    pub provider_controls_sha256: String,
    pub classifier_prompt_sha256: String,
    pub original_controls_sha256: String,
    pub partial_supplement_sha256: String,
    pub originating_negative_analysis_sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SegmentationControlledGuards {
    pub prior_negative_result_modified: bool,
    pub prior_manifest_retry_performed: bool,
    pub prompt_tuned_after_real_execution: bool,
    pub parser_tuned_after_real_execution: bool,
    pub aggregator_modified: bool,
    pub real_model_executed: bool,
    pub design_cases_accessed: bool,
    pub held_out_accessed: bool,
    pub runtime_authorized: bool,
    pub memory_write_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Phase7SegmentationControlledReadinessReport {
    pub schema_version: u32,
    pub report_id: String,
    pub phase: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub status: String,
    pub decision: String,
    pub originating_negative_result: String,
    pub measurement_change: String,
    pub validation: SegmentationControlledValidation,
    pub artifact_sha256: SegmentationControlledArtifactHashes,
    pub next_execution_requirements: Vec<String>,
    pub guards: SegmentationControlledGuards,
}

pub fn validate_controlled_output(
    packet: &ControlledProviderPacket,
    output: &ControlledJudgeOutput,
) -> Result<()> {
    if output.case_id != packet.case_id {
        bail!("case_id_mismatch");
    }
    if output.claim_judgments.len() != packet.atomic_claims.len() {
        bail!("claim_judgment_count_mismatch");
    }
    let valid_evidence_ids = packet
        .evidence
        .iter()
        .map(|row| row.evidence_id.as_str())
        .collect::<BTreeSet<_>>();
    let mut seen = BTreeSet::new();
    for (expected, judgment) in packet.atomic_claims.iter().zip(&output.claim_judgments) {
        if judgment.claim_id != expected.claim_id {
            bail!("claim_order_or_id_mismatch");
        }
        if !seen.insert(judgment.claim_id.as_str()) {
            bail!("duplicate_claim_id");
        }
        if judgment
            .evidence_ids
            .iter()
            .any(|evidence_id| !valid_evidence_ids.contains(evidence_id.as_str()))
        {
            bail!("unknown_evidence_id");
        }
        if judgment
            .reason_codes
            .iter()
            .any(|code| code.trim().is_empty())
        {
            bail!("empty_reason_code");
        }
        if judgment.rationale.trim().is_empty() {
            bail!("empty_rationale");
        }
    }
    Ok(())
}

fn aggregate_judgments(
    gold_case: &AtomicControlCase,
    output: &ControlledJudgeOutput,
) -> Result<HumanSupportLabel> {
    validate_controlled_output(
        &provider_packet_from_case(gold_case, "offline_probe"),
        output,
    )?;
    let predicted = output
        .claim_judgments
        .iter()
        .map(|row| (row.claim_id.as_str(), row.support_label))
        .collect::<BTreeMap<_, _>>();
    let mut claims = gold_case.claims.clone();
    for claim in &mut claims {
        claim.expected_support_label = *predicted
            .get(claim.claim_id.as_str())
            .context("missing_predicted_claim")?;
    }
    aggregate_candidate_label(&claims)
}

fn provider_packet_from_case(case: &AtomicControlCase, lane: &str) -> ControlledProviderPacket {
    ControlledProviderPacket {
        case_id: case.control_id.clone(),
        evaluation_lane: lane.to_string(),
        evidence: case.evidence.clone(),
        candidate_text: case.candidate_text.clone(),
        atomic_claims: case
            .claims
            .iter()
            .map(|claim| ControlledAtomicClaim {
                claim_id: claim.claim_id.clone(),
                source_span: claim.source_span.clone(),
                claim_text: claim.claim_text.clone(),
                claim_type: claim.claim_type,
                centrality: claim.centrality,
                material: claim.material,
                claim_origin: claim.claim_origin,
            })
            .collect(),
    }
}

fn perfect_output(case: &AtomicControlCase) -> ControlledJudgeOutput {
    ControlledJudgeOutput {
        case_id: case.control_id.clone(),
        claim_judgments: case
            .claims
            .iter()
            .map(|claim| LocalClaimJudgment {
                claim_id: claim.claim_id.clone(),
                support_label: claim.expected_support_label,
                evidence_ids: claim.evidence_ids.clone(),
                reason_codes: vec!["frozen_perfect_probe".to_string()],
                rationale: "Frozen perfect offline probe.".to_string(),
            })
            .collect(),
    }
}

fn all_gold_cases() -> Result<Vec<(AtomicControlCase, String)>> {
    let original: AtomicControlDataset = serde_json::from_slice(ORIGINAL_CONTROLS_BYTES)?;
    let supplement: AtomicControlDataset = serde_json::from_slice(SUPPLEMENT_BYTES)?;
    let mut cases = original
        .control_cases
        .into_iter()
        .map(|case| (case, "original_balanced_candidate_controls".to_string()))
        .collect::<Vec<_>>();
    cases.extend(supplement.control_cases.into_iter().map(|case| {
        (
            case,
            "partial_atomic_claim_diagnostics_supplement".to_string(),
        )
    }));
    Ok(cases)
}

fn exact_span(candidate: &str, claim: &ControlledAtomicClaim) -> bool {
    candidate
        .as_bytes()
        .get(claim.source_span.start..claim.source_span.end)
        .and_then(|bytes| std::str::from_utf8(bytes).ok())
        == Some(claim.claim_text.as_str())
}

pub fn build_segmentation_controlled_readiness_report(
) -> Result<Phase7SegmentationControlledReadinessReport> {
    let protocol: ClassificationProtocol = serde_json::from_slice(PROTOCOL_BYTES)?;
    let provider: ControlledProviderDataset = serde_json::from_slice(PROVIDER_CONTROLS_BYTES)?;
    let gold = all_gold_cases()?;
    if protocol.protocol_id != EVALUATION_VERSION {
        bail!("protocol_id_mismatch");
    }
    if protocol.status != "protocol_frozen_offline_validation_pending" {
        bail!("protocol_status_unexpected");
    }

    let packet_ids = provider
        .provider_packets
        .iter()
        .map(|packet| packet.case_id.as_str())
        .collect::<BTreeSet<_>>();
    let all_packet_ids_unique = packet_ids.len() == provider.provider_packets.len();
    let all_claim_ids = provider
        .provider_packets
        .iter()
        .flat_map(|packet| {
            packet
                .atomic_claims
                .iter()
                .map(|claim| claim.claim_id.as_str())
        })
        .collect::<Vec<_>>();
    let all_claim_ids_unique =
        all_claim_ids.iter().copied().collect::<BTreeSet<_>>().len() == all_claim_ids.len();
    let all_protocol_owned_spans_exact = provider.provider_packets.iter().all(|packet| {
        packet
            .atomic_claims
            .iter()
            .all(|claim| exact_span(&packet.candidate_text, claim))
    });

    let expected_packets = gold
        .iter()
        .map(|(case, lane)| provider_packet_from_case(case, lane))
        .collect::<Vec<_>>();
    let provider_packets_match_frozen_gold_structure =
        provider.provider_packets == expected_packets;
    let provider_packet_payload = serde_json::to_string(&provider.provider_packets)?;
    let provider_packets_contain_no_gold_labels = !provider_packet_payload
        .contains("expected_support_label")
        && !provider_packet_payload.contains("expected_candidate_label")
        && !provider_packet_payload.contains("expected_claim_labels");

    let mut perfect_probe_accepted = true;
    let mut perfect_probe_candidate_aggregation_correct = true;
    for ((case, _), packet) in gold.iter().zip(&provider.provider_packets) {
        let output = perfect_output(case);
        perfect_probe_accepted &= validate_controlled_output(packet, &output).is_ok();
        perfect_probe_candidate_aggregation_correct &=
            aggregate_judgments(case, &output)? == case.expected_candidate_label;
    }

    let multi_claim_index = provider
        .provider_packets
        .iter()
        .position(|packet| packet.atomic_claims.len() >= 2)
        .context("multi_claim_control_missing")?;
    let (probe_case, _) = &gold[multi_claim_index];
    let probe_packet = &provider.provider_packets[multi_claim_index];
    let perfect = perfect_output(probe_case);

    let mut missing = perfect.clone();
    missing.claim_judgments.pop();
    let missing_claim_rejected = validate_controlled_output(probe_packet, &missing).is_err();

    let mut duplicate = perfect.clone();
    duplicate.claim_judgments[1] = duplicate.claim_judgments[0].clone();
    let duplicate_claim_rejected = validate_controlled_output(probe_packet, &duplicate).is_err();

    let mut unknown = perfect.clone();
    unknown.claim_judgments[0].claim_id = "unknown_claim".to_string();
    let unknown_claim_rejected = validate_controlled_output(probe_packet, &unknown).is_err();

    let mut reordered = perfect;
    reordered.claim_judgments.swap(0, 1);
    let reordered_claim_rejected = validate_controlled_output(probe_packet, &reordered).is_err();

    let validation = SegmentationControlledValidation {
        provider_packet_count: provider.provider_packets.len(),
        original_candidate_gate_packet_count: provider.original_candidate_gate_packet_count,
        diagnostics_supplement_packet_count: provider.diagnostics_only_supplement_packet_count,
        atomic_claim_count: all_claim_ids.len(),
        all_packet_ids_unique,
        all_claim_ids_unique,
        all_protocol_owned_spans_exact,
        provider_packets_match_frozen_gold_structure,
        provider_packets_contain_no_gold_labels,
        perfect_probe_accepted,
        perfect_probe_candidate_aggregation_correct,
        missing_claim_rejected,
        duplicate_claim_rejected,
        unknown_claim_rejected,
        reordered_claim_rejected,
    };
    let ready = validation.all_packet_ids_unique
        && validation.all_claim_ids_unique
        && validation.all_protocol_owned_spans_exact
        && validation.provider_packets_match_frozen_gold_structure
        && validation.provider_packets_contain_no_gold_labels
        && validation.perfect_probe_accepted
        && validation.perfect_probe_candidate_aggregation_correct
        && validation.missing_claim_rejected
        && validation.duplicate_claim_rejected
        && validation.unknown_claim_rejected
        && validation.reordered_claim_rejected;

    let hashes = SegmentationControlledArtifactHashes {
        protocol_sha256: sha256(PROTOCOL_BYTES),
        provider_controls_sha256: sha256(PROVIDER_CONTROLS_BYTES),
        classifier_prompt_sha256: sha256(PROMPT_BYTES),
        original_controls_sha256: sha256(ORIGINAL_CONTROLS_BYTES),
        partial_supplement_sha256: sha256(SUPPLEMENT_BYTES),
        originating_negative_analysis_sha256: sha256(NEGATIVE_ANALYSIS_BYTES),
    };
    for (key, actual) in [
        (
            "provider_visible_controls",
            hashes.provider_controls_sha256.as_str(),
        ),
        (
            "classifier_prompt",
            hashes.classifier_prompt_sha256.as_str(),
        ),
        (
            "original_balanced_controls",
            hashes.original_controls_sha256.as_str(),
        ),
        (
            "partial_claim_supplement",
            hashes.partial_supplement_sha256.as_str(),
        ),
        (
            "originating_negative_result_analysis",
            hashes.originating_negative_analysis_sha256.as_str(),
        ),
    ] {
        if protocol.frozen_artifact_sha256.get(key).map(String::as_str) != Some(actual) {
            bail!("protocol_frozen_hash_mismatch:{key}");
        }
    }

    Ok(Phase7SegmentationControlledReadinessReport {
        schema_version: 1,
        report_id: "phase7.3.3-c-segmentation-controlled-readiness-v1".to_string(),
        phase: "Phase 7.3.3-C Segmentation-Controlled Atomic Claim Classification".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        status: if ready {
            "offline_protocol_ready_real_execution_not_started"
        } else {
            "offline_protocol_not_ready"
        }
        .to_string(),
        decision: if ready {
            "segmentation_controlled_classifier_manifest_may_be_prepared"
        } else {
            "real_execution_blocked"
        }
        .to_string(),
        originating_negative_result: "systematic_source_span_text_mismatch_20_of_20".to_string(),
        measurement_change: "protocol_supplies_claim_structure_judge_classifies_support_only"
            .to_string(),
        validation,
        artifact_sha256: hashes,
        next_execution_requirements: vec![
            "freeze provider model and execution adapter in a new immutable manifest".to_string(),
            "use the same relay model temperature and top_p for controlled comparison".to_string(),
            "record first returned output per packet as authoritative".to_string(),
            "do not execute design or held-out cases before control decision".to_string(),
        ],
        guards: SegmentationControlledGuards {
            prior_negative_result_modified: false,
            prior_manifest_retry_performed: false,
            prompt_tuned_after_real_execution: false,
            parser_tuned_after_real_execution: false,
            aggregator_modified: false,
            real_model_executed: false,
            design_cases_accessed: false,
            held_out_accessed: false,
            runtime_authorized: false,
            memory_write_authorized: false,
        },
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn readiness_separates_protocol_owned_segmentation_from_classification() {
        let report = build_segmentation_controlled_readiness_report().expect("readiness");
        assert_eq!(report.validation.provider_packet_count, 20);
        assert_eq!(report.validation.atomic_claim_count, 28);
        assert!(report.validation.all_protocol_owned_spans_exact);
        assert!(report.validation.provider_packets_contain_no_gold_labels);
        assert_eq!(
            report.status,
            "offline_protocol_ready_real_execution_not_started"
        );
        assert!(!report.guards.real_model_executed);
        assert!(!report.guards.design_cases_accessed);
        assert!(!report.guards.held_out_accessed);
    }

    #[test]
    fn strict_classifier_contract_rejects_claim_identity_failures() {
        let report = build_segmentation_controlled_readiness_report().expect("readiness");
        assert!(report.validation.missing_claim_rejected);
        assert!(report.validation.duplicate_claim_rejected);
        assert!(report.validation.unknown_claim_rejected);
        assert!(report.validation.reordered_claim_rejected);
    }
}
