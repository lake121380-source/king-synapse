use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceSoftDominanceEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-soft-dominance-eval",
    about = "Synapse Phase 1c-12.5 governance soft dominance and influence inertia evaluation"
)]
struct Cli {
    /// Path to a governance soft dominance TOML dataset.
    #[arg(
        long,
        default_value = "crates/eval/datasets/governance_soft_dominance.toml"
    )]
    dataset: PathBuf,
    /// Write the independent GovernanceSoftDominanceEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-soft-dominance")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceSoftDominanceEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance soft dominance and influence inertia ===");
    println!("tag:                            {}", report.tag);
    println!("dataset:                        {}", report.dataset);
    println!("scenarios:                      {}", report.scenario_count);
    println!("steps:                          {}", report.step_count);
    println!(
        "dominance_score:                {:.4} -> {:.4} ({:+.4})",
        report.baseline_dominance_score, report.governed_dominance_score, report.dominance_gain
    );
    println!(
        "dominance_flexibility:          {:.4}",
        report.dominance_flexibility
    );
    println!(
        "context_switch_accuracy:        {:.4}",
        report.context_switch_accuracy
    );
    println!(
        "inertia_drag_reduction:         {:.4}",
        report.inertia_drag_reduction
    );
    println!(
        "transition_latency_improvement: {:.4}",
        report.transition_latency_improvement
    );
    println!(
        "near_threshold_accuracy:        {:.4}",
        report.near_threshold_accuracy
    );
    println!(
        "boundary_miss_rate:             {:.4}",
        report.boundary_miss_rate
    );
    println!(
        "over_correction:                {:.4}",
        report.over_correction_rate
    );
    println!(
        "normal_preservation:            {:.4}",
        report.normal_preservation
    );
    println!("pass:                           {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance soft dominance report to {}",
        cli.json.display()
    );
    Ok(())
}
