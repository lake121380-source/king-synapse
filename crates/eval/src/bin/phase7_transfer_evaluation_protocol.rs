use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use synapse_eval::Phase7TransferEvaluationProtocolEvaluator;

fn main() -> Result<()> {
    let report = Phase7TransferEvaluationProtocolEvaluator::evaluate("phase7.1-frozen")?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_transfer_evaluation_protocol.json");
    fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")?;

    println!("Phase: {}", report.phase);
    println!("Scenarios: {}", report.dataset.scenario_count);
    println!("Held-out: {}", report.dataset.held_out_count);
    println!("Experiment arms: {}", report.arms.len());
    println!("Metrics: {}", report.metrics.len());
    println!("All scenarios valid: {}", report.all_scenarios_valid);
    println!(
        "Outcome evaluation complete: {}",
        report.guards.outcome_evaluation_complete
    );
    println!("Runtime authorized: {}", report.guards.runtime_authorized);
    println!("Report: {}", output.display());
    Ok(())
}
