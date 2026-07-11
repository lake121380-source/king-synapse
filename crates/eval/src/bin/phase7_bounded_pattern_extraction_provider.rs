use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use synapse_eval::Phase7BoundedPatternExtractionEvaluator;

fn main() -> Result<()> {
    let report = Phase7BoundedPatternExtractionEvaluator::evaluate("phase7.2.1-provider-frozen")?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_bounded_pattern_extraction_provider.json");
    fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")?;

    println!("Phase: {}", report.phase);
    println!("Provider: {}", report.provider_config.provider_id);
    println!("Design cases: {}", report.summary.design_case_count);
    println!(
        "Contract accepted: {}",
        report.summary.contract_accepted_cases
    );
    println!(
        "Quality diagnostics: {}",
        report.summary.cases_with_quality_diagnostics
    );
    println!("Fault injections: {}", report.fault_injections.len());
    println!(
        "Held-out cases untouched: {}",
        report.guards.held_out_cases_untouched
    );
    println!("Runtime authorized: {}", report.guards.runtime_authorized);
    println!("Report: {}", output.display());
    Ok(())
}
