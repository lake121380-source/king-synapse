use serde_json::json;
use sha2::{Digest, Sha256};
use synapse_eval::{
    construct_shadow_overlay, evaluate_prototype_representation,
    validate_serialized_shadow_overlay_integrity, ConfidenceCalibrationStatus, ExistingMemoryKind,
    FrozenMemorySnapshot, ProspectiveAtomicUnit, ReconstructionInput, ReconstructionStatus,
    SourceLocator, SupportState,
};

fn sha256_hex(value: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(value);
    format!("{:x}", hasher.finalize())
}

fn build_overlay() -> synapse_eval::AtomicEvidenceShadowOverlay {
    let snapshot = FrozenMemorySnapshot::new(
        "synthetic-memory-001",
        ExistingMemoryKind::Fact,
        "alphabeta",
        vec!["synthetic-evidence-001".to_string()],
        vec!["synthetic-event-001".to_string()],
    );
    let unit = |ordinal, claim_text: &str, start_char, end_char| ProspectiveAtomicUnit {
        ordinal,
        claim_text: claim_text.to_string(),
        source_locator: SourceLocator::SourceMemoryTextSpan {
            start_char,
            end_char,
        },
        support_state: SupportState::Supported,
        source_evidence_provenance: vec!["synthetic-evidence-001".to_string()],
        source_event_provenance: vec!["synthetic-event-001".to_string()],
        extraction_confidence: 0.9,
        support_confidence: 0.8,
        confidence_calibration_status: ConfidenceCalibrationStatus::UnvalidatedDiagnostic,
        contradiction_links: Vec::new(),
    };
    construct_shadow_overlay(
        &snapshot,
        &[unit(0, "alpha", 0, 5), unit(1, "beta", 5, 9)],
        &ReconstructionInput {
            status: ReconstructionStatus::Complete,
            unresolved_gap_count: 0,
        },
    )
    .expect("frozen synthetic fixture must remain valid")
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args != ["--emit-fixture"] {
        eprintln!("usage: phase7_4_atomic_evidence_shadow --emit-fixture");
        std::process::exit(2);
    }
    let first = build_overlay();
    let second = build_overlay();
    let canonical = first
        .canonical_json()
        .expect("synthetic overlay serialization must succeed");
    let replay = second
        .canonical_json()
        .expect("synthetic replay serialization must succeed");
    validate_serialized_shadow_overlay_integrity(&canonical)
        .expect("synthetic overlay integrity must pass");
    let representation = evaluate_prototype_representation(&first, 1, 9);
    let overlay: serde_json::Value =
        serde_json::from_str(&canonical).expect("canonical overlay must parse");
    let output = json!({
        "schema_version": 1,
        "fixture_run_id": "phase7.4.1-atomic-evidence-shadow-synthetic-run-v1",
        "status": "PASS",
        "synthetic_only": true,
        "effect_dataset_opened": false,
        "provider_called": false,
        "runtime_integration_authorized": false,
        "canonical_overlay_json_sha256": sha256_hex(canonical.as_bytes()),
        "replay_byte_identical": canonical == replay,
        "representation": representation,
        "overlay": overlay,
    });
    println!(
        "{}",
        serde_json::to_string(&output).expect("fixture output serialization must succeed")
    );
}
