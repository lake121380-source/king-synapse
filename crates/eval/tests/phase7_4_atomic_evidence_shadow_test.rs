use synapse_eval::{
    construct_shadow_overlay, evaluate_prototype_representation,
    validate_serialized_shadow_overlay_integrity, ConfidenceCalibrationStatus, ExistingMemoryKind,
    FrozenMemorySnapshot, ProspectiveAtomicUnit, ReconstructionInput, ReconstructionStatus,
    ShadowFailureKind, SourceLocator, SupportState,
};

fn snapshot(kind: ExistingMemoryKind, content: &str) -> FrozenMemorySnapshot {
    FrozenMemorySnapshot::new(
        "memory-001",
        kind,
        content,
        vec!["evidence-001".to_string(), "evidence-002".to_string()],
        vec!["event-001".to_string()],
    )
}

fn span_unit(
    ordinal: usize,
    claim_text: &str,
    start_char: usize,
    end_char: usize,
    evidence_id: &str,
) -> ProspectiveAtomicUnit {
    ProspectiveAtomicUnit {
        ordinal,
        claim_text: claim_text.to_string(),
        source_locator: SourceLocator::SourceMemoryTextSpan {
            start_char,
            end_char,
        },
        support_state: SupportState::Supported,
        source_evidence_provenance: vec![evidence_id.to_string()],
        source_event_provenance: vec!["event-001".to_string()],
        extraction_confidence: 0.9,
        support_confidence: 0.8,
        confidence_calibration_status: ConfidenceCalibrationStatus::UnvalidatedDiagnostic,
        contradiction_links: Vec::new(),
    }
}

fn complete() -> ReconstructionInput {
    ReconstructionInput {
        status: ReconstructionStatus::Complete,
        unresolved_gap_count: 0,
    }
}

fn valid_two_unit_overlay() -> synapse_eval::AtomicEvidenceShadowOverlay {
    construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alphabeta"),
        &[
            span_unit(0, "alpha", 0, 5, "evidence-001"),
            span_unit(1, "beta", 5, 9, "evidence-002"),
        ],
        &complete(),
    )
    .expect("valid overlay")
}

#[test]
fn exact_two_unit_overlay_is_valid_and_eval_only() {
    let overlay = valid_two_unit_overlay();
    assert_eq!(overlay.atomic_units().len(), 2);
    assert_eq!(overlay.atomic_units()[0].claim_text(), "alpha");
    assert_eq!(overlay.atomic_units()[1].claim_text(), "beta");
    assert_eq!(
        overlay.reconstruction().status(),
        ReconstructionStatus::Complete
    );
    assert!(overlay.authority().eval_only());
    assert!(!overlay.authority().runtime_applied());
    assert!(!overlay.authority().memory_mutated());
    assert!(!overlay.authority().store_written());
    assert!(!overlay.authority().recall_engine_mutated());
    assert!(!overlay.authority().promotion_authorized());
}

#[test]
fn identical_input_replays_byte_identically() {
    let first = valid_two_unit_overlay();
    let second = valid_two_unit_overlay();
    assert_eq!(first.overlay_id(), second.overlay_id());
    assert_eq!(
        first.canonical_json().expect("canonical first"),
        second.canonical_json().expect("canonical second")
    );
    assert_eq!(
        first.atomic_units()[0].atomic_claim_id(),
        second.atomic_units()[0].atomic_claim_id()
    );
}

#[test]
fn canonical_json_has_sorted_root_keys_and_schema_shape() {
    let canonical = valid_two_unit_overlay()
        .canonical_json()
        .expect("canonical JSON");
    let parsed: serde_json::Value = serde_json::from_str(&canonical).expect("valid JSON");
    let expected_prefix = "{\"atomic_units\":";
    assert!(canonical.starts_with(expected_prefix));
    assert_eq!(parsed["schema_version"], 1);
    assert_eq!(parsed["status"], "eval_only_shadow_overlay");
    assert_eq!(parsed["authority"]["runtime_applied"], false);
    assert_eq!(parsed["authority"]["memory_mutated"], false);
}

#[test]
fn evidence_id_locator_with_complete_provenance_is_valid() {
    let unit = ProspectiveAtomicUnit {
        ordinal: 0,
        claim_text: "source-specific evidence".to_string(),
        source_locator: SourceLocator::SourceEvidenceId {
            evidence_id: "evidence-001".to_string(),
        },
        support_state: SupportState::PartiallySupported,
        source_evidence_provenance: vec!["evidence-001".to_string()],
        source_event_provenance: vec!["event-001".to_string()],
        extraction_confidence: 0.7,
        support_confidence: 0.6,
        confidence_calibration_status: ConfidenceCalibrationStatus::FrozenCalibrated,
        contradiction_links: vec!["evidence-002".to_string()],
    };
    let overlay = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Preference, "source content"),
        &[unit],
        &complete(),
    )
    .expect("evidence-located overlay");
    assert_eq!(overlay.atomic_units().len(), 1);
    assert_eq!(
        overlay.atomic_units()[0].support_state(),
        SupportState::PartiallySupported
    );
}

#[test]
fn explicit_partial_reconstruction_preserves_gap_count() {
    let overlay = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::State, "alpha---beta"),
        &[
            span_unit(0, "alpha", 0, 5, "evidence-001"),
            span_unit(1, "beta", 8, 12, "evidence-002"),
        ],
        &ReconstructionInput {
            status: ReconstructionStatus::Partial,
            unresolved_gap_count: 1,
        },
    )
    .expect("explicit partial overlay");
    assert_eq!(
        overlay.reconstruction().status(),
        ReconstructionStatus::Partial
    );
    assert_eq!(overlay.reconstruction().unresolved_gap_count(), 1);
}

#[test]
fn all_existing_memory_kinds_are_accepted() {
    for kind in [
        ExistingMemoryKind::Fact,
        ExistingMemoryKind::Preference,
        ExistingMemoryKind::Failure,
        ExistingMemoryKind::Playbook,
        ExistingMemoryKind::State,
    ] {
        construct_shadow_overlay(
            &snapshot(kind, "alpha"),
            &[span_unit(0, "alpha", 0, 5, "evidence-001")],
            &complete(),
        )
        .expect("existing MemoryKind accepted");
    }
}

#[test]
fn atomic_claim_memory_kind_is_rejected() {
    let error = ExistingMemoryKind::parse("atomic_claim").expect_err("must reject new kind");
    assert_eq!(error.kind(), ShadowFailureKind::InputLineageFailure);
}

#[test]
fn claimed_source_hash_mismatch_is_rejected() {
    let valid = snapshot(ExistingMemoryKind::Fact, "alpha");
    let tampered = FrozenMemorySnapshot::from_claimed(
        valid.source_memory_id,
        valid.source_memory_kind,
        valid.source_memory_content,
        "0".repeat(64),
        valid.source_memory_content_sha256,
        valid.source_evidence_ids,
        valid.source_event_ids,
    );
    let error = construct_shadow_overlay(
        &tampered,
        &[span_unit(0, "alpha", 0, 5, "evidence-001")],
        &complete(),
    )
    .expect_err("must reject source hash mismatch");
    assert_eq!(error.kind(), ShadowFailureKind::SourceHashFailure);
}

#[test]
fn source_excerpt_mismatch_is_rejected() {
    let error = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alpha"),
        &[span_unit(0, "wrong", 0, 5, "evidence-001")],
        &complete(),
    )
    .expect_err("must reject excerpt mismatch");
    assert_eq!(error.kind(), ShadowFailureKind::SpanBoundaryFailure);
}

#[test]
fn out_of_bounds_span_is_rejected() {
    let error = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alpha"),
        &[span_unit(0, "alpha", 0, 6, "evidence-001")],
        &complete(),
    )
    .expect_err("must reject out-of-bounds span");
    assert_eq!(error.kind(), ShadowFailureKind::SpanBoundaryFailure);
}

#[test]
fn overlapping_spans_are_rejected() {
    let error = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alphabeta"),
        &[
            span_unit(0, "alpha", 0, 5, "evidence-001"),
            span_unit(1, "abeta", 4, 9, "evidence-002"),
        ],
        &complete(),
    )
    .expect_err("must reject overlap");
    assert_eq!(error.kind(), ShadowFailureKind::SpanOverlapFailure);
}

#[test]
fn skipped_ordinal_is_rejected() {
    let error = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alpha"),
        &[span_unit(1, "alpha", 0, 5, "evidence-001")],
        &complete(),
    )
    .expect_err("must reject skipped ordinal");
    assert_eq!(error.kind(), ShadowFailureKind::OrdinalFailure);
}

#[test]
fn duplicate_ordinal_is_rejected() {
    let error = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alphabeta"),
        &[
            span_unit(0, "alpha", 0, 5, "evidence-001"),
            span_unit(0, "beta", 5, 9, "evidence-002"),
        ],
        &complete(),
    )
    .expect_err("must reject duplicate ordinal");
    assert_eq!(error.kind(), ShadowFailureKind::OrdinalFailure);
}

#[test]
fn unknown_provenance_is_rejected() {
    let mut unit = span_unit(0, "alpha", 0, 5, "evidence-001");
    unit.source_evidence_provenance = vec!["unknown-evidence".to_string()];
    let error = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alpha"),
        &[unit],
        &complete(),
    )
    .expect_err("must reject unknown provenance");
    assert_eq!(error.kind(), ShadowFailureKind::ProvenanceFailure);
}

#[test]
fn nonfinite_or_out_of_bounds_confidence_is_rejected() {
    for value in [f64::NAN, f64::INFINITY, -0.01, 1.01] {
        let mut unit = span_unit(0, "alpha", 0, 5, "evidence-001");
        unit.extraction_confidence = value;
        let error = construct_shadow_overlay(
            &snapshot(ExistingMemoryKind::Fact, "alpha"),
            &[unit],
            &complete(),
        )
        .expect_err("must reject invalid confidence");
        assert_eq!(error.kind(), ShadowFailureKind::ConfidenceFailure);
    }
}

#[test]
fn inconsistent_reconstruction_status_is_rejected() {
    let error = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alpha"),
        &[span_unit(0, "alpha", 0, 5, "evidence-001")],
        &ReconstructionInput {
            status: ReconstructionStatus::Complete,
            unresolved_gap_count: 1,
        },
    )
    .expect_err("must reject undeclared complete gap");
    assert_eq!(error.kind(), ShadowFailureKind::ReconstructionFailure);
}

#[test]
fn undeclared_text_span_gap_is_rejected() {
    let error = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alpha---beta"),
        &[
            span_unit(0, "alpha", 0, 5, "evidence-001"),
            span_unit(1, "beta", 8, 12, "evidence-002"),
        ],
        &complete(),
    )
    .expect_err("must reject undeclared gap");
    assert_eq!(error.kind(), ShadowFailureKind::ReconstructionFailure);
}

#[test]
fn serialized_claim_text_hash_mismatch_is_rejected() {
    let canonical = valid_two_unit_overlay()
        .canonical_json()
        .expect("canonical overlay");
    let tampered = canonical.replacen("\"claim_text\":\"alpha\"", "\"claim_text\":\"wrong\"", 1);
    let error = validate_serialized_shadow_overlay_integrity(&tampered)
        .expect_err("must reject claimed text hash mismatch");
    assert_eq!(error.kind(), ShadowFailureKind::ClaimHashFailure);
}

#[test]
fn serialized_runtime_authority_claim_is_rejected() {
    let canonical = valid_two_unit_overlay()
        .canonical_json()
        .expect("canonical overlay");
    let tampered = canonical.replacen("\"runtime_applied\":false", "\"runtime_applied\":true", 1);
    let error = validate_serialized_shadow_overlay_integrity(&tampered)
        .expect_err("must reject runtime authority claim");
    assert_eq!(error.kind(), ShadowFailureKind::AuthorityBoundaryFailure);
}

#[test]
fn emitted_overlay_passes_serialized_integrity_validation() {
    let canonical = valid_two_unit_overlay()
        .canonical_json()
        .expect("canonical overlay");
    validate_serialized_shadow_overlay_integrity(&canonical)
        .expect("constructor output must pass integrity validation");
}

#[test]
fn whole_memory_single_unit_is_recorded_but_fails_representation_gate() {
    let overlay = construct_shadow_overlay(
        &snapshot(ExistingMemoryKind::Fact, "alpha"),
        &[span_unit(0, "alpha", 0, 5, "evidence-001")],
        &complete(),
    )
    .expect("structurally serializable diagnostic");
    let gate = evaluate_prototype_representation(&overlay, 1, 5);
    assert_eq!(gate.atomic_unit_count, 1);
    assert_eq!(gate.whole_memory_unit_count, 1);
    assert!(gate.whole_memory_single_unit_degeneracy);
    assert!(!gate.passed);
}

#[test]
fn multi_unit_overlay_passes_prototype_representation_gate() {
    let gate = evaluate_prototype_representation(&valid_two_unit_overlay(), 1, 9);
    assert!(gate.atomic_unit_count_gt_memory_chunk_count);
    assert!(!gate.whole_memory_single_unit_degeneracy);
    assert!(gate.passed);
}
