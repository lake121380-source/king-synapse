use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use synapse_eval::Phase7ProviderComparisonEvaluator;

fn main() -> Result<()> {
    let report = Phase7ProviderComparisonEvaluator::evaluate("phase7.2.2-protocol-frozen")?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_pattern_provider_comparison.json");
    fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")?;

    println!("Phase: {}", report.phase);
    println!("Prompt: {}", report.canonical_prompt_version);
    for row in &report.capability_matrix {
        println!(
            "Provider: {} status={} completed={}",
            row.provider_name, row.execution_status, row.design_cases_completed
        );
    }
    println!("Preflight: {}", report.preflight_status);
    println!(
        "Held-out cases untouched: {}",
        report.guards.held_out_cases_untouched
    );
    println!("Runtime authorized: {}", report.guards.runtime_authorized);
    println!("Report: {}", output.display());
    Ok(())
}
