use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::Phase7ArtifactLineageTransitionEvaluator;

fn main() -> Result<()> {
    let report = Phase7ArtifactLineageTransitionEvaluator::evaluate(
        "phase7.3.1-artifact-lineage-transition-gate",
    )?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_artifact_lineage_transition_gate.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    println!("Phase: {}", report.phase);
    println!("State: {:?}", report.state);
    println!(
        "Independent reviews completed: {}/{}",
        report.review_progress.completed_count, report.review_progress.required_count
    );
    println!(
        "Artifact lineage broken: {}",
        report.lineage.artifact_lineage_broken
    );
    println!(
        "Adjudication allowed: {}",
        report.permissions.adjudication_allowed
    );
    println!(
        "Judge calibration allowed: {}",
        report.permissions.judge_calibration_allowed
    );
    println!("Report: {}", output.display());
    Ok(())
}
