use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceCalibrationEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-calibration-eval",
    about = "Synapse Phase 1c-7.6 governance risk calibration sweep"
)]
struct Cli {
    /// Path to a mixed governance stress TOML dataset.
    #[arg(long, default_value = "crates/eval/datasets/governance_stress.toml")]
    dataset: PathBuf,
    /// Write the independent GovernanceCalibrationSweepReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-calibration")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceCalibrationEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance risk calibration sweep ===");
    println!("tag:                  {}", report.tag);
    println!("dataset:              {}", report.dataset);
    println!("candidates:           {}", report.candidate_count);
    println!(
        "baseline:             detection={:.4} fp={:.4} preservation={:.4} over={:.4}",
        report.baseline.harmful_detection_rate,
        report.baseline.false_positive_rate,
        report.baseline.normal_recall_preservation,
        report.baseline.over_suppression_rate
    );
    if let Some(best) = report.best_candidate.as_ref() {
        println!(
            "best:                 {} detection={:.4} fp={:.4} preservation={:.4} over={:.4}",
            best.name,
            best.harmful_detection_rate,
            best.false_positive_rate,
            best.normal_recall_preservation,
            best.over_suppression_rate
        );
    } else {
        println!("best:                 <none passed safety gates>");
    }
    println!("pareto_frontier:      {}", report.pareto_frontier.len());

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance calibration report to {}",
        cli.json.display()
    );
    Ok(())
}
