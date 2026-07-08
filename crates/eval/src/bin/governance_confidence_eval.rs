use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceConfidenceEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-confidence-eval",
    about = "Synapse Phase 1c-8 adaptive governance confidence evaluation"
)]
struct Cli {
    /// Path to a detector feedback TOML dataset.
    #[arg(long, default_value = "crates/eval/datasets/governance_feedback.toml")]
    dataset: PathBuf,
    /// Write the independent GovernanceConfidenceEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-confidence")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceConfidenceEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse adaptive governance confidence evaluation ===");
    println!("tag:                    {}", report.tag);
    println!("dataset:                {}", report.dataset);
    println!("detectors:              {}", report.detector_count);
    println!("observations:           {}", report.observation_count);
    println!(
        "reliability:            {:.4} -> {:.4} ({:+.4})",
        report.mean_initial_reliability,
        report.mean_final_reliability,
        report.reliability_improvement
    );
    println!(
        "calibration_error:      {:.4}",
        report.mean_calibration_error
    );
    println!(
        "calibration_improvement:{:.4}",
        report.calibration_improvement
    );
    println!(
        "governance_stability:   {:.4}",
        report.governance_stability_score
    );
    println!("pass:                   {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance confidence report to {}",
        cli.json.display()
    );
    Ok(())
}
