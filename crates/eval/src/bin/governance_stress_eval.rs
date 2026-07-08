use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceStressEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-stress-eval",
    about = "Synapse Phase 1c-7.5 mixed reality governance stress evaluation"
)]
struct Cli {
    /// Path to a mixed governance stress TOML dataset.
    #[arg(long, default_value = "crates/eval/datasets/governance_stress.toml")]
    dataset: PathBuf,
    /// Write the independent GovernanceStressEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-stress")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceStressEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance mixed stress evaluation ===");
    println!("tag:                         {}", report.tag);
    println!("dataset:                     {}", report.dataset);
    println!("cases:                       {}", report.case_count);
    println!("edges:                       {}", report.edge_count);
    println!(
        "harmful_detection_rate:      {:.4}",
        report.harmful_detection_rate
    );
    println!(
        "false_positive_rate:         {:.4}",
        report.false_positive_rate
    );
    println!(
        "ambiguous_calibration_score: {:.4}",
        report.ambiguous_calibration_score
    );
    println!(
        "longitudinal_recovery_score: {:.4}",
        report.longitudinal_recovery_score
    );
    println!(
        "normal_recall_preservation:  {:.4}",
        report.normal_recall_preservation
    );
    println!(
        "over_suppression_rate:       {:.4}",
        report.over_suppression_rate
    );
    println!("pass:                        {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance mixed stress report to {}",
        cli.json.display()
    );
    Ok(())
}
