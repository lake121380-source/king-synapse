use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceRecoveryEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-recovery-eval",
    about = "Synapse Phase 1c-11 governance belief recovery evaluation"
)]
struct Cli {
    /// Path to a governance belief recovery TOML dataset.
    #[arg(long, default_value = "crates/eval/datasets/governance_recovery.toml")]
    dataset: PathBuf,
    /// Write the independent GovernanceRecoveryEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-recovery")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceRecoveryEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse governance belief recovery evaluation ===");
    println!("tag:                    {}", report.tag);
    println!("dataset:                {}", report.dataset);
    println!("scenarios:              {}", report.scenario_count);
    println!("steps:                  {}", report.step_count);
    println!("recovery_scenarios:     {}", report.recovery_scenarios);
    println!(
        "recovery_success_rate:  {:.4}",
        report.recovery_success_rate
    );
    println!("target_recovery_rate:   {:.4}", report.target_recovery_rate);
    println!("recovery_score:         {:.4}", report.recovery_score);
    println!("recovery_gain:          {:.4}", report.recovery_gain);
    println!("latency_improvement:    {:.4}", report.latency_improvement);
    println!("dominant_shift_rate:    {:.4}", report.dominant_shift_rate);
    println!("relapse_rate:           {:.4}", report.relapse_rate);
    println!("normal_preservation:    {:.4}", report.normal_preservation);
    println!("over_correction:        {:.4}", report.over_correction_rate);
    println!("stability:              {:.4}", report.stability_score);
    println!("pass:                   {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!("wrote governance recovery report to {}", cli.json.display());
    Ok(())
}
