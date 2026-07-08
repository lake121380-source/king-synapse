use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceSelfConsistencyEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-self-consistency-eval",
    about = "Synapse Phase 1c-14 governance self-consistency evaluation"
)]
struct Cli {
    /// Path to a governance self-consistency TOML dataset.
    #[arg(
        long,
        default_value = "crates/eval/datasets/governance_self_consistency.toml"
    )]
    dataset: PathBuf,
    /// Write the independent GovernanceSelfConsistencyEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-self-consistency")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceSelfConsistencyEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance self-consistency ===");
    println!("tag:                                  {}", report.tag);
    println!("dataset:                              {}", report.dataset);
    println!(
        "cases:                                {}",
        report.case_count
    );
    println!(
        "governance_consistency_score:         {:.4}",
        report.governance_consistency_score
    );
    println!(
        "decision_path_agreement:              {:.4}",
        report.decision_path_agreement
    );
    println!(
        "uncertainty_alignment:                {:.4}",
        report.uncertainty_alignment
    );
    println!(
        "contradiction_rate:                   {:.4}",
        report.contradiction_rate
    );
    println!(
        "disagreement_rate:                    {:.4}",
        report.disagreement_rate
    );
    println!(
        "high_uncertainty_disagreement_rate:   {:.4}",
        report.high_uncertainty_disagreement_rate
    );
    println!(
        "majority_expected_alignment:          {:.4}",
        report.majority_expected_alignment
    );
    println!(
        "abstention_consistency:               {:.4}",
        report.abstention_consistency
    );
    println!("pass:                                 {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance self-consistency report to {}",
        cli.json.display()
    );
    Ok(())
}
