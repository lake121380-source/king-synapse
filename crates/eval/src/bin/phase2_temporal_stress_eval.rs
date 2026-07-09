use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase2TemporalStressEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase2-temporal-stress-eval",
    about = "Synapse Phase 2.8 temporal stress evaluation over temporal supersession dynamics"
)]
struct Cli {
    /// Write the Phase2TemporalStressEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase2-temporal-stress-eval")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase2TemporalStressEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 2.8 temporal stress evaluation ===");
    println!("tag:                             {}", report.tag);
    println!(
        "baseline_version:                {}",
        report.baseline_version
    );
    println!("scenarios:                       {}", report.scenario_count);
    println!(
        "oscillation_resistance:          {:.4}",
        report.metrics.oscillation_resistance
    );
    println!(
        "delayed_contradiction_handling:  {:.4}",
        report.metrics.delayed_contradiction_handling
    );
    println!(
        "false_contradiction_restraint:   {:.4}",
        report.metrics.false_contradiction_restraint
    );
    println!(
        "memory_recovery_signal:          {:.4}",
        report.metrics.memory_recovery_signal
    );
    println!(
        "state_recovery:                  {:.4}",
        report.metrics.state_recovery
    );
    println!(
        "historical_preservation:         {:.4}",
        report.metrics.historical_preservation
    );
    println!(
        "stability_score:                 {:.4}",
        report.metrics.stability_score
    );
    println!("pass:                            {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 2.8 temporal stress report to {}",
        cli.json.display()
    );
    Ok(())
}
