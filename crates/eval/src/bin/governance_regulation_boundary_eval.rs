use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceRegulationBoundaryEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-regulation-boundary-eval",
    about = "Synapse Phase 1c-13 governance influence regulation boundary evaluation"
)]
struct Cli {
    /// Path to a governance regulation boundary TOML dataset.
    #[arg(
        long,
        default_value = "crates/eval/datasets/governance_regulation_boundary.toml"
    )]
    dataset: PathBuf,
    /// Write the independent GovernanceRegulationBoundaryEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-regulation-boundary")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceRegulationBoundaryEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance influence regulation boundary ===");
    println!("tag:                          {}", report.tag);
    println!("dataset:                      {}", report.dataset);
    println!("cases:                        {}", report.case_count);
    println!(
        "intervention_cases:           {}",
        report.intervention_case_count
    );
    println!(
        "predicted_interventions:       {}",
        report.predicted_interventions
    );
    println!(
        "intervention_precision:        {:.4}",
        report.intervention_precision
    );
    println!(
        "intervention_recall:           {:.4}",
        report.intervention_recall
    );
    println!(
        "intervention_restraint:        {:.4}",
        report.intervention_restraint
    );
    println!(
        "unnecessary_intervention_rate: {:.4}",
        report.unnecessary_intervention_rate
    );
    println!(
        "exploration_preservation:      {:.4}",
        report.exploration_preservation
    );
    println!(
        "ambiguous_restraint_rate:      {:.4}",
        report.ambiguous_restraint_rate
    );
    println!(
        "regulation_boundary_score:     {:.4}",
        report.regulation_boundary_score
    );
    println!(
        "boundary_miss_rate:            {:.4}",
        report.boundary_miss_rate
    );
    println!(
        "mean_outcome_gain:             {:.4}",
        report.mean_outcome_gain
    );
    println!("pass:                          {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance regulation boundary report to {}",
        cli.json.display()
    );
    Ok(())
}
