use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::phase7_real_provider_readiness::Phase7RealProviderReadinessEvaluator;

fn main() -> Result<()> {
    let report = Phase7RealProviderReadinessEvaluator::evaluate("phase7.2.3-provider-readiness")?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_real_provider_readiness.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    println!("Phase: {}", report.phase);
    println!(
        "Provider: {} model={} completed={}/{}",
        report.summary.provider_name,
        report.summary.resolved_model,
        report.summary.completed_design_cases,
        report.summary.design_case_count
    );
    println!("Provider ready: {}", report.guards.provider_ready);
    println!(
        "Unsupported claim rate: {:.4}",
        report.summary.unsupported_claim_rate
    );
    println!(
        "Held-out cases untouched: {}",
        report.guards.held_out_cases_untouched
    );
    println!(
        "Knowledge promotion authorized: {}",
        report.guards.knowledge_promotion_authorized
    );
    println!("Report: {}", output.display());
    Ok(())
}
