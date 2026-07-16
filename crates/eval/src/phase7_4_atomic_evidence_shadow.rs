//! Eval-only Atomic Evidence Shadow Overlay for Phase 7.4.1.
//!
//! This module intentionally owns no Store, RecallEngine, RecallHit, Memory,
//! writer, retriever, or runtime handle. It validates prospectively supplied
//! Atomic units against an immutable local snapshot DTO and returns a
//! serializable diagnostic artifact whose authority flags are constructor
//! controlled.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::error::Error;
use std::fmt::{Display, Formatter};

pub const SEGMENTATION_CONTRACT_VERSION: &str = "phase7.4-atomic-evidence-shadow-prototype-v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExistingMemoryKind {
    Fact,
    Preference,
    Failure,
    Playbook,
    State,
}

impl ExistingMemoryKind {
    pub fn parse(value: &str) -> Result<Self, ShadowOverlayError> {
        match value {
            "fact" => Ok(Self::Fact),
            "preference" => Ok(Self::Preference),
            "failure" => Ok(Self::Failure),
            "playbook" => Ok(Self::Playbook),
            "state" => Ok(Self::State),
            _ => Err(ShadowOverlayError::new(
                ShadowFailureKind::InputLineageFailure,
                format!("unsupported_memory_kind:{value}"),
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SupportState {
    Supported,
    PartiallySupported,
    Unsupported,
    NotAssessable,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConfidenceCalibrationStatus {
    UnvalidatedDiagnostic,
    FrozenCalibrated,
    NotAssessable,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReconstructionStatus {
    Complete,
    Partial,
    NotReconstructable,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "locator_type", rename_all = "snake_case")]
pub enum SourceLocator {
    SourceMemoryTextSpan { start_char: usize, end_char: usize },
    SourceEvidenceId { evidence_id: String },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FrozenMemorySnapshot {
    pub source_memory_id: String,
    pub source_memory_kind: ExistingMemoryKind,
    pub source_memory_content: String,
    pub source_memory_sha256: String,
    pub source_memory_content_sha256: String,
    pub source_evidence_ids: Vec<String>,
    pub source_event_ids: Vec<String>,
}

impl FrozenMemorySnapshot {
    pub fn new(
        source_memory_id: impl Into<String>,
        source_memory_kind: ExistingMemoryKind,
        source_memory_content: impl Into<String>,
        source_evidence_ids: Vec<String>,
        source_event_ids: Vec<String>,
    ) -> Self {
        let source_memory_id = source_memory_id.into();
        let source_memory_content = source_memory_content.into();
        let source_memory_content_sha256 = sha256_hex(source_memory_content.as_bytes());
        let source_memory_sha256 = memory_snapshot_sha256(
            &source_memory_id,
            source_memory_kind,
            &source_memory_content_sha256,
            &source_evidence_ids,
            &source_event_ids,
        );
        Self {
            source_memory_id,
            source_memory_kind,
            source_memory_content,
            source_memory_sha256,
            source_memory_content_sha256,
            source_evidence_ids,
            source_event_ids,
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn from_claimed(
        source_memory_id: impl Into<String>,
        source_memory_kind: ExistingMemoryKind,
        source_memory_content: impl Into<String>,
        source_memory_sha256: impl Into<String>,
        source_memory_content_sha256: impl Into<String>,
        source_evidence_ids: Vec<String>,
        source_event_ids: Vec<String>,
    ) -> Self {
        Self {
            source_memory_id: source_memory_id.into(),
            source_memory_kind,
            source_memory_content: source_memory_content.into(),
            source_memory_sha256: source_memory_sha256.into(),
            source_memory_content_sha256: source_memory_content_sha256.into(),
            source_evidence_ids,
            source_event_ids,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProspectiveAtomicUnit {
    pub ordinal: usize,
    pub claim_text: String,
    pub source_locator: SourceLocator,
    pub support_state: SupportState,
    pub source_evidence_provenance: Vec<String>,
    pub source_event_provenance: Vec<String>,
    pub extraction_confidence: f64,
    pub support_confidence: f64,
    pub confidence_calibration_status: ConfidenceCalibrationStatus,
    pub contradiction_links: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReconstructionInput {
    pub status: ReconstructionStatus,
    pub unresolved_gap_count: usize,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct AtomicEvidenceShadowOverlay {
    schema_version: u8,
    overlay_id: String,
    status: &'static str,
    source_memory_id: String,
    source_memory_sha256: String,
    source_memory_content_sha256: String,
    source_memory_kind: ExistingMemoryKind,
    segmentation_contract_version: &'static str,
    atomic_units: Vec<AtomicEvidenceUnit>,
    reconstruction: Reconstruction,
    authority: ShadowAuthority,
}

impl AtomicEvidenceShadowOverlay {
    pub fn overlay_id(&self) -> &str {
        &self.overlay_id
    }

    pub fn source_memory_id(&self) -> &str {
        &self.source_memory_id
    }

    pub fn atomic_units(&self) -> &[AtomicEvidenceUnit] {
        &self.atomic_units
    }

    pub fn reconstruction(&self) -> &Reconstruction {
        &self.reconstruction
    }

    pub fn authority(&self) -> &ShadowAuthority {
        &self.authority
    }

    pub fn canonical_json(&self) -> Result<String, serde_json::Error> {
        let value = serde_json::to_value(self)?;
        Ok(canonical_json_value(&value))
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct AtomicEvidenceUnit {
    atomic_claim_id: String,
    ordinal: usize,
    claim_text: String,
    claim_text_sha256: String,
    source_locator: SourceLocator,
    support_state: SupportState,
    provenance: ClaimProvenance,
    confidence: ClaimConfidence,
    contradiction_links: Vec<String>,
}

impl AtomicEvidenceUnit {
    pub fn atomic_claim_id(&self) -> &str {
        &self.atomic_claim_id
    }

    pub fn ordinal(&self) -> usize {
        self.ordinal
    }

    pub fn claim_text(&self) -> &str {
        &self.claim_text
    }

    pub fn source_locator(&self) -> &SourceLocator {
        &self.source_locator
    }

    pub fn support_state(&self) -> SupportState {
        self.support_state
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ClaimProvenance {
    source_memory_id: String,
    source_memory_sha256: String,
    source_evidence_ids: Vec<String>,
    source_event_ids: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ClaimConfidence {
    extraction_confidence: f64,
    support_confidence: f64,
    calibration_status: ConfidenceCalibrationStatus,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Reconstruction {
    source_memory_id: String,
    ordered_atomic_claim_ids: Vec<String>,
    status: ReconstructionStatus,
    deterministic: bool,
    overlap_characters: usize,
    unresolved_gap_count: usize,
}

impl Reconstruction {
    pub fn status(&self) -> ReconstructionStatus {
        self.status
    }

    pub fn ordered_atomic_claim_ids(&self) -> &[String] {
        &self.ordered_atomic_claim_ids
    }

    pub fn unresolved_gap_count(&self) -> usize {
        self.unresolved_gap_count
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ShadowAuthority {
    eval_only: bool,
    runtime_applied: bool,
    memory_mutated: bool,
    store_written: bool,
    recall_engine_mutated: bool,
    promotion_authorized: bool,
}

impl ShadowAuthority {
    pub fn eval_only(&self) -> bool {
        self.eval_only
    }

    pub fn runtime_applied(&self) -> bool {
        self.runtime_applied
    }

    pub fn memory_mutated(&self) -> bool {
        self.memory_mutated
    }

    pub fn store_written(&self) -> bool {
        self.store_written
    }

    pub fn recall_engine_mutated(&self) -> bool {
        self.recall_engine_mutated
    }

    pub fn promotion_authorized(&self) -> bool {
        self.promotion_authorized
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ShadowFailureKind {
    InputLineageFailure,
    SourceHashFailure,
    ClaimHashFailure,
    SpanBoundaryFailure,
    SpanOverlapFailure,
    OrdinalFailure,
    ProvenanceFailure,
    SupportStateFailure,
    ConfidenceFailure,
    ReconstructionFailure,
    RepresentationDegeneracy,
    SchemaContractFailure,
    AuthorityBoundaryFailure,
    ImplementationDependencyFailure,
    DeterminismFailure,
    LeakageFailure,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ShadowOverlayError {
    kind: ShadowFailureKind,
    detail: String,
}

impl ShadowOverlayError {
    fn new(kind: ShadowFailureKind, detail: impl Into<String>) -> Self {
        Self {
            kind,
            detail: detail.into(),
        }
    }

    pub fn kind(&self) -> ShadowFailureKind {
        self.kind
    }

    pub fn detail(&self) -> &str {
        &self.detail
    }
}

impl Display for ShadowOverlayError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{:?}:{}", self.kind, self.detail)
    }
}

impl Error for ShadowOverlayError {}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct PrototypeRepresentationCheck {
    pub atomic_unit_count: usize,
    pub memory_chunk_count: usize,
    pub whole_memory_unit_count: usize,
    pub atomic_unit_count_gt_memory_chunk_count: bool,
    pub whole_memory_single_unit_degeneracy: bool,
    pub passed: bool,
}

pub fn construct_shadow_overlay(
    snapshot: &FrozenMemorySnapshot,
    units: &[ProspectiveAtomicUnit],
    reconstruction_input: &ReconstructionInput,
) -> Result<AtomicEvidenceShadowOverlay, ShadowOverlayError> {
    validate_snapshot(snapshot)?;
    if units.is_empty() {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::RepresentationDegeneracy,
            "zero_atomic_units",
        ));
    }
    validate_unique_nonempty_ids(&snapshot.source_evidence_ids, "source_evidence_ids")?;
    validate_unique_ids(&snapshot.source_event_ids, "source_event_ids")?;

    let overlay_digest = sha256_hex(
        format!(
            "phase7.4|{}|{}|{}",
            snapshot.source_memory_id, snapshot.source_memory_sha256, SEGMENTATION_CONTRACT_VERSION
        )
        .as_bytes(),
    );
    let overlay_id = format!("aes-v1-{overlay_digest}");
    let evidence_ids: HashSet<&str> = snapshot
        .source_evidence_ids
        .iter()
        .map(String::as_str)
        .collect();
    let event_ids: HashSet<&str> = snapshot
        .source_event_ids
        .iter()
        .map(String::as_str)
        .collect();
    let frozen_target_ids: HashSet<&str> = evidence_ids.union(&event_ids).copied().collect();
    let mut output_units = Vec::with_capacity(units.len());
    let mut previous_span_end = None;
    let mut text_spans = Vec::with_capacity(units.len());
    let mut all_units_have_text_spans = true;

    for (expected_ordinal, unit) in units.iter().enumerate() {
        if unit.ordinal != expected_ordinal {
            return Err(ShadowOverlayError::new(
                ShadowFailureKind::OrdinalFailure,
                format!(
                    "expected_ordinal_{expected_ordinal}_observed_{}",
                    unit.ordinal
                ),
            ));
        }
        if unit.claim_text.is_empty() {
            return Err(ShadowOverlayError::new(
                ShadowFailureKind::ClaimHashFailure,
                format!("empty_claim_text_at_ordinal_{}", unit.ordinal),
            ));
        }
        validate_confidence(unit.extraction_confidence, "extraction_confidence")?;
        validate_confidence(unit.support_confidence, "support_confidence")?;
        validate_provenance(unit, &evidence_ids, &event_ids)?;
        validate_contradiction_links(unit, &frozen_target_ids)?;

        match &unit.source_locator {
            SourceLocator::SourceMemoryTextSpan {
                start_char,
                end_char,
            } => {
                let excerpt =
                    exact_char_span(&snapshot.source_memory_content, *start_char, *end_char)?;
                if excerpt != unit.claim_text {
                    return Err(ShadowOverlayError::new(
                        ShadowFailureKind::SpanBoundaryFailure,
                        format!("source_excerpt_mismatch_at_ordinal_{}", unit.ordinal),
                    ));
                }
                if let Some(previous_end) = previous_span_end {
                    if *start_char < previous_end {
                        return Err(ShadowOverlayError::new(
                            ShadowFailureKind::SpanOverlapFailure,
                            format!("overlapping_span_at_ordinal_{}", unit.ordinal),
                        ));
                    }
                }
                previous_span_end = Some(*end_char);
                text_spans.push((*start_char, *end_char));
            }
            SourceLocator::SourceEvidenceId { evidence_id } => {
                all_units_have_text_spans = false;
                if !evidence_ids.contains(evidence_id.as_str()) {
                    return Err(ShadowOverlayError::new(
                        ShadowFailureKind::ProvenanceFailure,
                        format!("unknown_evidence_locator:{evidence_id}"),
                    ));
                }
            }
        }

        let claim_text_sha256 = sha256_hex(unit.claim_text.as_bytes());
        let atomic_claim_id = format!(
            "aes-claim-v1-{}",
            sha256_hex(format!("{}|{}|{}", overlay_id, unit.ordinal, claim_text_sha256).as_bytes())
        );
        output_units.push(AtomicEvidenceUnit {
            atomic_claim_id,
            ordinal: unit.ordinal,
            claim_text: unit.claim_text.clone(),
            claim_text_sha256,
            source_locator: unit.source_locator.clone(),
            support_state: unit.support_state,
            provenance: ClaimProvenance {
                source_memory_id: snapshot.source_memory_id.clone(),
                source_memory_sha256: snapshot.source_memory_sha256.clone(),
                source_evidence_ids: unit.source_evidence_provenance.clone(),
                source_event_ids: unit.source_event_provenance.clone(),
            },
            confidence: ClaimConfidence {
                extraction_confidence: unit.extraction_confidence,
                support_confidence: unit.support_confidence,
                calibration_status: unit.confidence_calibration_status,
            },
            contradiction_links: unit.contradiction_links.clone(),
        });
    }

    validate_reconstruction(reconstruction_input)?;
    if all_units_have_text_spans {
        validate_text_span_gap_count(
            &text_spans,
            snapshot.source_memory_content.chars().count(),
            reconstruction_input.unresolved_gap_count,
        )?;
    }
    let ordered_atomic_claim_ids = output_units
        .iter()
        .map(|unit| unit.atomic_claim_id.clone())
        .collect();
    Ok(AtomicEvidenceShadowOverlay {
        schema_version: 1,
        overlay_id,
        status: "eval_only_shadow_overlay",
        source_memory_id: snapshot.source_memory_id.clone(),
        source_memory_sha256: snapshot.source_memory_sha256.clone(),
        source_memory_content_sha256: snapshot.source_memory_content_sha256.clone(),
        source_memory_kind: snapshot.source_memory_kind,
        segmentation_contract_version: SEGMENTATION_CONTRACT_VERSION,
        atomic_units: output_units,
        reconstruction: Reconstruction {
            source_memory_id: snapshot.source_memory_id.clone(),
            ordered_atomic_claim_ids,
            status: reconstruction_input.status,
            deterministic: true,
            overlap_characters: 0,
            unresolved_gap_count: reconstruction_input.unresolved_gap_count,
        },
        authority: ShadowAuthority {
            eval_only: true,
            runtime_applied: false,
            memory_mutated: false,
            store_written: false,
            recall_engine_mutated: false,
            promotion_authorized: false,
        },
    })
}

/// Validates deterministic identity, lineage, reconstruction order, and
/// constructor-controlled authority in a serialized overlay. This function
/// never returns a deserialized overlay, so untrusted JSON cannot acquire
/// shadow, runtime, persistence, mutation, or promotion authority.
pub fn validate_serialized_shadow_overlay_integrity(
    candidate: &str,
) -> Result<(), ShadowOverlayError> {
    let value: serde_json::Value = serde_json::from_str(candidate).map_err(|error| {
        ShadowOverlayError::new(
            ShadowFailureKind::SchemaContractFailure,
            format!("invalid_json:{error}"),
        )
    })?;
    if canonical_json_value(&value) != candidate {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::DeterminismFailure,
            "noncanonical_json",
        ));
    }
    let root = value.as_object().ok_or_else(|| {
        ShadowOverlayError::new(ShadowFailureKind::SchemaContractFailure, "root_not_object")
    })?;
    require_exact_keys(
        root,
        &[
            "atomic_units",
            "authority",
            "overlay_id",
            "reconstruction",
            "schema_version",
            "segmentation_contract_version",
            "source_memory_content_sha256",
            "source_memory_id",
            "source_memory_kind",
            "source_memory_sha256",
            "status",
        ],
        "root",
    )?;
    if required_u64(root, "schema_version")? != 1
        || required_str(root, "status")? != "eval_only_shadow_overlay"
        || required_str(root, "segmentation_contract_version")? != SEGMENTATION_CONTRACT_VERSION
    {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::SchemaContractFailure,
            "frozen_root_constant_mismatch",
        ));
    }
    let source_memory_id = required_str(root, "source_memory_id")?;
    let source_memory_sha256 = required_sha256(root, "source_memory_sha256")?;
    required_sha256(root, "source_memory_content_sha256")?;
    ExistingMemoryKind::parse(required_str(root, "source_memory_kind")?)?;
    let expected_overlay_id = format!(
        "aes-v1-{}",
        sha256_hex(
            format!(
                "phase7.4|{source_memory_id}|{source_memory_sha256}|{SEGMENTATION_CONTRACT_VERSION}"
            )
            .as_bytes()
        )
    );
    if required_str(root, "overlay_id")? != expected_overlay_id {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::DeterminismFailure,
            "overlay_id_mismatch",
        ));
    }

    let units = root
        .get("atomic_units")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| {
            ShadowOverlayError::new(
                ShadowFailureKind::SchemaContractFailure,
                "atomic_units_not_array",
            )
        })?;
    if units.is_empty() {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::RepresentationDegeneracy,
            "zero_atomic_units",
        ));
    }
    let mut ordered_claim_ids = Vec::with_capacity(units.len());
    let mut unique_claim_ids = HashSet::with_capacity(units.len());
    for (expected_ordinal, unit) in units.iter().enumerate() {
        let unit = unit.as_object().ok_or_else(|| {
            ShadowOverlayError::new(
                ShadowFailureKind::SchemaContractFailure,
                format!("atomic_unit_{expected_ordinal}_not_object"),
            )
        })?;
        let ordinal = required_u64(unit, "ordinal")?;
        if ordinal != expected_ordinal as u64 {
            return Err(ShadowOverlayError::new(
                ShadowFailureKind::OrdinalFailure,
                format!("expected_ordinal_{expected_ordinal}_observed_{ordinal}"),
            ));
        }
        let claim_text = required_str(unit, "claim_text")?;
        if claim_text.is_empty() {
            return Err(ShadowOverlayError::new(
                ShadowFailureKind::ClaimHashFailure,
                format!("empty_claim_text_at_ordinal_{ordinal}"),
            ));
        }
        let claim_text_sha256 = required_sha256(unit, "claim_text_sha256")?;
        if sha256_hex(claim_text.as_bytes()) != claim_text_sha256 {
            return Err(ShadowOverlayError::new(
                ShadowFailureKind::ClaimHashFailure,
                format!("claim_text_hash_mismatch_at_ordinal_{ordinal}"),
            ));
        }
        let atomic_claim_id = required_str(unit, "atomic_claim_id")?;
        let expected_claim_id = format!(
            "aes-claim-v1-{}",
            sha256_hex(format!("{expected_overlay_id}|{ordinal}|{claim_text_sha256}").as_bytes())
        );
        if atomic_claim_id != expected_claim_id {
            return Err(ShadowOverlayError::new(
                ShadowFailureKind::DeterminismFailure,
                format!("atomic_claim_id_mismatch_at_ordinal_{ordinal}"),
            ));
        }
        if !unique_claim_ids.insert(atomic_claim_id) {
            return Err(ShadowOverlayError::new(
                ShadowFailureKind::OrdinalFailure,
                "duplicate_atomic_claim_id",
            ));
        }
        ordered_claim_ids.push(atomic_claim_id);
    }

    let reconstruction = root
        .get("reconstruction")
        .and_then(serde_json::Value::as_object)
        .ok_or_else(|| {
            ShadowOverlayError::new(
                ShadowFailureKind::SchemaContractFailure,
                "reconstruction_not_object",
            )
        })?;
    if required_str(reconstruction, "source_memory_id")? != source_memory_id {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::InputLineageFailure,
            "reconstruction_source_memory_id_mismatch",
        ));
    }
    let reconstructed_ids = reconstruction
        .get("ordered_atomic_claim_ids")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| {
            ShadowOverlayError::new(
                ShadowFailureKind::SchemaContractFailure,
                "ordered_atomic_claim_ids_not_array",
            )
        })?;
    if reconstructed_ids.len() != ordered_claim_ids.len()
        || reconstructed_ids
            .iter()
            .zip(&ordered_claim_ids)
            .any(|(actual, expected)| actual.as_str() != Some(expected))
    {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::ReconstructionFailure,
            "reconstruction_order_mismatch",
        ));
    }

    let authority = root
        .get("authority")
        .and_then(serde_json::Value::as_object)
        .ok_or_else(|| {
            ShadowOverlayError::new(
                ShadowFailureKind::SchemaContractFailure,
                "authority_not_object",
            )
        })?;
    let expected_authority = HashMap::from([
        ("eval_only", true),
        ("runtime_applied", false),
        ("memory_mutated", false),
        ("store_written", false),
        ("recall_engine_mutated", false),
        ("promotion_authorized", false),
    ]);
    require_exact_keys(
        authority,
        &expected_authority.keys().copied().collect::<Vec<_>>(),
        "authority",
    )?;
    if expected_authority.iter().any(|(field, expected)| {
        authority.get(*field).and_then(serde_json::Value::as_bool) != Some(*expected)
    }) {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::AuthorityBoundaryFailure,
            "runtime_or_mutation_authority_claim",
        ));
    }
    Ok(())
}

pub fn evaluate_prototype_representation(
    overlay: &AtomicEvidenceShadowOverlay,
    memory_chunk_count: usize,
    source_memory_character_count: usize,
) -> PrototypeRepresentationCheck {
    let whole_memory_unit_count = overlay
        .atomic_units
        .iter()
        .filter(|unit| {
            matches!(
                unit.source_locator,
                SourceLocator::SourceMemoryTextSpan {
                    start_char: 0,
                    end_char
                } if end_char == source_memory_character_count
            )
        })
        .count();
    let atomic_unit_count_gt_memory_chunk_count = overlay.atomic_units.len() > memory_chunk_count;
    let whole_memory_single_unit_degeneracy =
        overlay.atomic_units.len() == 1 && whole_memory_unit_count == 1;
    PrototypeRepresentationCheck {
        atomic_unit_count: overlay.atomic_units.len(),
        memory_chunk_count,
        whole_memory_unit_count,
        atomic_unit_count_gt_memory_chunk_count,
        whole_memory_single_unit_degeneracy,
        passed: atomic_unit_count_gt_memory_chunk_count && !whole_memory_single_unit_degeneracy,
    }
}

fn validate_snapshot(snapshot: &FrozenMemorySnapshot) -> Result<(), ShadowOverlayError> {
    if snapshot.source_memory_id.is_empty() || snapshot.source_memory_content.is_empty() {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::InputLineageFailure,
            "empty_source_memory_identity_or_content",
        ));
    }
    let content_hash = sha256_hex(snapshot.source_memory_content.as_bytes());
    if content_hash != snapshot.source_memory_content_sha256 {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::SourceHashFailure,
            "source_memory_content_hash_mismatch",
        ));
    }
    let snapshot_hash = memory_snapshot_sha256(
        &snapshot.source_memory_id,
        snapshot.source_memory_kind,
        &snapshot.source_memory_content_sha256,
        &snapshot.source_evidence_ids,
        &snapshot.source_event_ids,
    );
    if snapshot_hash != snapshot.source_memory_sha256 {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::SourceHashFailure,
            "source_memory_hash_mismatch",
        ));
    }
    Ok(())
}

fn validate_unique_nonempty_ids(ids: &[String], field: &str) -> Result<(), ShadowOverlayError> {
    if ids.is_empty() {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::InputLineageFailure,
            format!("empty_{field}"),
        ));
    }
    validate_unique_ids(ids, field)
}

fn validate_unique_ids(ids: &[String], field: &str) -> Result<(), ShadowOverlayError> {
    if ids.iter().any(String::is_empty) {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::InputLineageFailure,
            format!("blank_id_in_{field}"),
        ));
    }
    let unique: HashSet<&str> = ids.iter().map(String::as_str).collect();
    if unique.len() != ids.len() {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::InputLineageFailure,
            format!("duplicate_id_in_{field}"),
        ));
    }
    Ok(())
}

fn validate_confidence(value: f64, field: &str) -> Result<(), ShadowOverlayError> {
    if !value.is_finite() || !(0.0..=1.0).contains(&value) {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::ConfidenceFailure,
            format!("invalid_{field}"),
        ));
    }
    Ok(())
}

fn validate_provenance(
    unit: &ProspectiveAtomicUnit,
    evidence_ids: &HashSet<&str>,
    event_ids: &HashSet<&str>,
) -> Result<(), ShadowOverlayError> {
    if unit.source_evidence_provenance.is_empty() {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::ProvenanceFailure,
            format!("empty_evidence_provenance_at_ordinal_{}", unit.ordinal),
        ));
    }
    if unit
        .source_evidence_provenance
        .iter()
        .any(|id| !evidence_ids.contains(id.as_str()))
    {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::ProvenanceFailure,
            format!("unknown_evidence_provenance_at_ordinal_{}", unit.ordinal),
        ));
    }
    if unit
        .source_event_provenance
        .iter()
        .any(|id| !event_ids.contains(id.as_str()))
    {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::ProvenanceFailure,
            format!("unknown_event_provenance_at_ordinal_{}", unit.ordinal),
        ));
    }
    validate_unique_ids(
        &unit.source_evidence_provenance,
        "unit_source_evidence_provenance",
    )?;
    validate_unique_ids(
        &unit.source_event_provenance,
        "unit_source_event_provenance",
    )
}

fn validate_contradiction_links(
    unit: &ProspectiveAtomicUnit,
    frozen_target_ids: &HashSet<&str>,
) -> Result<(), ShadowOverlayError> {
    validate_unique_ids(&unit.contradiction_links, "contradiction_links")?;
    if unit
        .contradiction_links
        .iter()
        .any(|id| !frozen_target_ids.contains(id.as_str()))
    {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::ProvenanceFailure,
            format!("unknown_contradiction_target_at_ordinal_{}", unit.ordinal),
        ));
    }
    Ok(())
}

fn validate_reconstruction(input: &ReconstructionInput) -> Result<(), ShadowOverlayError> {
    match input.status {
        ReconstructionStatus::Complete if input.unresolved_gap_count != 0 => {
            Err(ShadowOverlayError::new(
                ShadowFailureKind::ReconstructionFailure,
                "complete_reconstruction_has_unresolved_gaps",
            ))
        }
        ReconstructionStatus::Partial | ReconstructionStatus::NotReconstructable
            if input.unresolved_gap_count == 0 =>
        {
            Err(ShadowOverlayError::new(
                ShadowFailureKind::ReconstructionFailure,
                "noncomplete_reconstruction_missing_explicit_gap",
            ))
        }
        _ => Ok(()),
    }
}

fn validate_text_span_gap_count(
    spans: &[(usize, usize)],
    source_character_count: usize,
    declared_gap_count: usize,
) -> Result<(), ShadowOverlayError> {
    let mut cursor = 0;
    let mut observed_gap_count = 0;
    for (start, end) in spans {
        if *start > cursor {
            observed_gap_count += 1;
        }
        cursor = *end;
    }
    if cursor < source_character_count {
        observed_gap_count += 1;
    }
    if observed_gap_count != declared_gap_count {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::ReconstructionFailure,
            format!("declared_gap_count_{declared_gap_count}_observed_{observed_gap_count}"),
        ));
    }
    Ok(())
}

fn require_exact_keys(
    object: &serde_json::Map<String, serde_json::Value>,
    expected: &[&str],
    location: &str,
) -> Result<(), ShadowOverlayError> {
    let actual: HashSet<&str> = object.keys().map(String::as_str).collect();
    let expected: HashSet<&str> = expected.iter().copied().collect();
    if actual != expected {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::SchemaContractFailure,
            format!("unexpected_keys_at_{location}"),
        ));
    }
    Ok(())
}

fn required_str<'a>(
    object: &'a serde_json::Map<String, serde_json::Value>,
    field: &str,
) -> Result<&'a str, ShadowOverlayError> {
    object
        .get(field)
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| {
            ShadowOverlayError::new(
                ShadowFailureKind::SchemaContractFailure,
                format!("missing_or_nonstring_{field}"),
            )
        })
}

fn required_u64(
    object: &serde_json::Map<String, serde_json::Value>,
    field: &str,
) -> Result<u64, ShadowOverlayError> {
    object
        .get(field)
        .and_then(serde_json::Value::as_u64)
        .ok_or_else(|| {
            ShadowOverlayError::new(
                ShadowFailureKind::SchemaContractFailure,
                format!("missing_or_noninteger_{field}"),
            )
        })
}

fn required_sha256<'a>(
    object: &'a serde_json::Map<String, serde_json::Value>,
    field: &str,
) -> Result<&'a str, ShadowOverlayError> {
    let value = required_str(object, field)?;
    if value.len() != 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
    {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::SchemaContractFailure,
            format!("invalid_sha256_{field}"),
        ));
    }
    Ok(value)
}

fn exact_char_span(
    source: &str,
    start_char: usize,
    end_char: usize,
) -> Result<String, ShadowOverlayError> {
    let character_count = source.chars().count();
    if start_char >= end_char || end_char > character_count {
        return Err(ShadowOverlayError::new(
            ShadowFailureKind::SpanBoundaryFailure,
            format!("invalid_span_{start_char}_{end_char}_for_{character_count}"),
        ));
    }
    Ok(source
        .chars()
        .skip(start_char)
        .take(end_char - start_char)
        .collect())
}

fn memory_snapshot_sha256(
    source_memory_id: &str,
    source_memory_kind: ExistingMemoryKind,
    source_memory_content_sha256: &str,
    source_evidence_ids: &[String],
    source_event_ids: &[String],
) -> String {
    #[derive(Serialize)]
    struct MemoryHashMaterial<'a> {
        source_memory_content_sha256: &'a str,
        source_memory_id: &'a str,
        source_memory_kind: ExistingMemoryKind,
        source_evidence_ids: Vec<&'a str>,
        source_event_ids: Vec<&'a str>,
    }
    let mut evidence: Vec<&str> = source_evidence_ids.iter().map(String::as_str).collect();
    let mut events: Vec<&str> = source_event_ids.iter().map(String::as_str).collect();
    evidence.sort_unstable();
    events.sort_unstable();
    let value = serde_json::to_value(MemoryHashMaterial {
        source_memory_content_sha256,
        source_memory_id,
        source_memory_kind,
        source_evidence_ids: evidence,
        source_event_ids: events,
    })
    .expect("serializing memory hash material cannot fail");
    sha256_hex(canonical_json_value(&value).as_bytes())
}

fn sha256_hex(value: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(value);
    format!("{:x}", hasher.finalize())
}

fn canonical_json_value(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Null => "null".to_string(),
        serde_json::Value::Bool(value) => value.to_string(),
        serde_json::Value::Number(value) => value.to_string(),
        serde_json::Value::String(value) => {
            serde_json::to_string(value).expect("serializing a JSON string cannot fail")
        }
        serde_json::Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(canonical_json_value)
                .collect::<Vec<_>>()
                .join(",")
        ),
        serde_json::Value::Object(values) => {
            let mut keys: Vec<&String> = values.keys().collect();
            keys.sort_unstable();
            let body = keys
                .into_iter()
                .map(|key| {
                    format!(
                        "{}:{}",
                        serde_json::to_string(key)
                            .expect("serializing a JSON object key cannot fail"),
                        canonical_json_value(&values[key])
                    )
                })
                .collect::<Vec<_>>()
                .join(",");
            format!("{{{body}}}")
        }
    }
}
