use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::phase7_inter_reviewer_agreement::Phase7InterReviewerAgreementEvaluator;

fn main() -> Result<()> {
    let report = Phase7InterReviewerAgreementEvaluator::evaluate(
        "phase7.3.1-inter-reviewer-agreement-gate",
    )?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_inter_reviewer_agreement.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    println!("Phase: {}", report.phase);
    println!(
        "Reviewer A completed: {}",
        report.guards.reviewer_a_completed
    );
    println!(
        "Reviewer B completed: {}",
        report.guards.reviewer_b_completed
    );
    println!("Agreement available: {}", report.metrics.is_some());
    println!("Decision: {:?}", report.decision);
    println!("Report: {}", output.display());
    Ok(())
}
