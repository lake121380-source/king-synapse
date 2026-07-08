use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceCompetitionEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-competition-eval",
    about = "Synapse Phase 1c-12 governance competing influence dynamics evaluation"
)]
struct Cli {
    /// Path to a governance competing influence TOML dataset.
    #[arg(
        long,
        default_value = "crates/eval/datasets/governance_competition.toml"
    )]
    dataset: PathBuf,
    /// Write the independent GovernanceCompetitionEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-competition")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceCompetitionEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance competing influence dynamics ===");
    println!("tag:                    {}", report.tag);
    println!("dataset:                {}", report.dataset);
    println!("scenarios:              {}", report.scenario_count);
    println!("steps:                  {}", report.step_count);
    println!(
        "competition_score:      {:.4} -> {:.4} ({:+.4})",
        report.baseline_competition_score,
        report.governed_competition_score,
        report.competition_gain
    );
    println!(
        "transition_accuracy:    {:.4}",
        report.dominant_transition_accuracy
    );
    println!(
        "evidence_response_gain: {:.4}",
        report.evidence_response_gain
    );
    println!(
        "balance_stability:      {:.4}",
        report.influence_balance_stability
    );
    println!(
        "suppression_precision:  {:.4}",
        report.suppression_precision
    );
    println!(
        "over_suppression:       {:.4}",
        report.over_suppression_rate
    );
    println!("normal_preservation:    {:.4}", report.normal_preservation);
    println!("pass:                   {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance competition report to {}",
        cli.json.display()
    );
    Ok(())
}
