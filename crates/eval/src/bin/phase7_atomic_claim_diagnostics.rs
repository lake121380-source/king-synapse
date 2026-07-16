use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::phase7_atomic_claim_diagnostics::Phase7AtomicClaimDiagnosticsEvaluator;

fn main() -> Result<()> {
    let report =
        Phase7AtomicClaimDiagnosticsEvaluator::evaluate("phase7.3.3-a-diagnostics-readiness")?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_atomic_claim_diagnostics_readiness.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    println!("Phase: {}", report.phase);
    println!("Status: {}", report.status);
    println!("Decision: {}", report.decision);
    println!(
        "Four-label local Claim calibration available: {}",
        report.four_label_local_claim_calibration_available
    );
    println!(
        "Missing Atomic Claim gold labels: {:?}",
        report.missing_gold_atomic_claim_labels
    );
    println!(
        "Supplement Atomic Claim gold labels: {:?}",
        report.supplement_gold_atomic_claim_label_counts
    );
    println!(
        "Candidate collapse gate still uses original controls only: {}",
        report.candidate_collapse_gate_uses_original_balanced_controls_only
    );
    println!("Report: {}", output.display());
    Ok(())
}
