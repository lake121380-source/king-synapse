use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase4ContextualCompetitionIntegrationEvaluator;

#[derive(Parser)]
#[command(
    name = "phase4_contextual_competition_integration",
    about = "Synapse Phase 4.4 contextual competition integration evaluation"
)]
struct Cli {
    /// Write the Phase4ContextualCompetitionIntegrationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase4-contextual-competition-integration")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase4ContextualCompetitionIntegrationEvaluator::evaluate(cli.tag)?;

    println!("Phase 4.4 Contextual Competition Integration");
    println!();
    println!("Scenarios:");
    println!("{}", report.scenarios);
    println!();
    println!("Context flips:");
    println!(
        "{}/{}",
        report.context_flips.changed, report.context_flips.total
    );
    println!();
    println!("Flip rate:");
    println!("{:.4}", report.metric.context_flip_rate);
    println!();
    println!("Dominance consistency:");
    println!("{:.4}", report.metric.dominance_consistency);
    println!();
    println!("Suppression correctness:");
    println!("{:.4}", report.metric.suppression_correctness);
    println!();
    println!("Ranking stability:");
    println!("{:.4}", report.metric.ranking_stability);
    println!();
    println!("core_changed:");
    println!("{}", report.core_changed);
    println!();
    println!("memory_written:");
    println!("{}", report.memory_written);
    println!();
    println!("runtime_weight_changed:");
    println!("{}", report.runtime_weight_changed);
    println!();
    println!("Status:");
    println!("{}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 4.4 contextual competition integration report to {}",
        cli.json.display()
    );
    Ok(())
}
