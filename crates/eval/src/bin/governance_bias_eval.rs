use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceBiasEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-bias-eval",
    about = "Synapse Phase 1c-7 governance positive-control and recovery evaluation"
)]
struct Cli {
    /// Path to a governance positive-control TOML dataset.
    #[arg(long, default_value = "crates/eval/datasets/governance_bias.toml")]
    dataset: PathBuf,
    /// Write the independent GovernanceBiasEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-bias")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceBiasEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance positive-control evaluation ===");
    println!("tag:                         {}", report.tag);
    println!("dataset:                     {}", report.dataset);
    println!("cases:                       {}", report.case_count);
    println!(
        "harmful_edge_detection_rate: {:.4}",
        report.harmful_edge_detection_rate
    );
    println!(
        "suppression_gain:            {:.4}",
        report.suppression_gain
    );
    println!(
        "normal_recall_preservation:  {:.4}",
        report.normal_recall_preservation
    );
    println!(
        "over_suppression_rate:       {:.4}",
        report.over_suppression_rate
    );
    println!("recovery_score:              {:.4}", report.recovery_score);
    println!("pass:                        {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance positive-control report to {}",
        cli.json.display()
    );
    Ok(())
}
