use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceDriftEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-drift-eval",
    about = "Synapse Phase 1c-10 governance longitudinal drift evaluation"
)]
struct Cli {
    /// Path to a governance longitudinal drift TOML dataset.
    #[arg(long, default_value = "crates/eval/datasets/governance_drift.toml")]
    dataset: PathBuf,
    /// Write the independent GovernanceDriftEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-drift")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceDriftEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance longitudinal drift evaluation ===");
    println!("tag:                    {}", report.tag);
    println!("dataset:                {}", report.dataset);
    println!("scenarios:              {}", report.scenario_count);
    println!("steps:                  {}", report.step_count);
    println!(
        "weak_bias_detection:    {:.4}",
        report.weak_bias_detection_rate
    );
    println!(
        "drift_mitigation_gain:  {:.4}",
        report.drift_mitigation_gain
    );
    println!("recovery_score:         {:.4}", report.recovery_score);
    println!("pattern_memory_gain:    {:.4}", report.pattern_memory_gain);
    println!("normal_preservation:    {:.4}", report.normal_preservation);
    println!("over_correction:        {:.4}", report.over_correction_rate);
    println!("stability:              {:.4}", report.stability_score);
    println!("pass:                   {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!("wrote governance drift report to {}", cli.json.display());
    Ok(())
}
