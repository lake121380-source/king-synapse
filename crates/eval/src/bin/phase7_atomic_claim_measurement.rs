use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::phase7_atomic_claim_measurement::Phase7AtomicClaimMeasurementEvaluator;

fn main() -> Result<()> {
    let report = Phase7AtomicClaimMeasurementEvaluator::evaluate(
        "phase7.3.3-atomic-claim-measurement-protocol-freeze",
    )?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_atomic_claim_measurement.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    println!("Phase: {}", report.phase);
    println!("Status: {}", report.status);
    println!("Decision: {}", report.decision);
    println!(
        "Controls: {} cases / {} claims / balanced={}",
        report.protocol_validation.control_case_count,
        report.protocol_validation.atomic_claim_count,
        report.protocol_validation.balanced_four_class_controls
    );
    println!(
        "Legacy majority baseline: {:.4}",
        report.legacy_design_distribution.majority_class_accuracy
    );
    println!("Report: {}", output.display());
    Ok(())
}
