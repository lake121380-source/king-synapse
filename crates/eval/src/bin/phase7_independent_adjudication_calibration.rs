use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::phase7_independent_adjudication_calibration::Phase7AdjudicationCalibrationEvaluator;

fn main() -> Result<()> {
    let report = Phase7AdjudicationCalibrationEvaluator::evaluate(
        "phase7.3.1-independent-adjudication-frozen-judge-calibration",
    )?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_independent_adjudication_calibration.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    println!("Phase: {}", report.phase);
    println!(
        "Frozen claim-source anchors: {}",
        report.claim_source_anchors.len()
    );
    println!(
        "Reviewer A completed: {}",
        report.guards.reviewer_a_completed
    );
    println!(
        "Reviewer B completed: {}",
        report.guards.reviewer_b_completed
    );
    println!(
        "Adjudication completed: {}",
        report.guards.independent_adjudication_completed
    );
    println!(
        "Judge calibration completed: {}",
        report.guards.scorer_calibration_completed
    );
    println!("Decision: {:?}", report.decision);
    println!("Report: {}", output.display());
    Ok(())
}
