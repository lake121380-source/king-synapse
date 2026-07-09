use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase2TemporalInfluenceEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase2-temporal-influence-eval",
    about = "Synapse Phase 2.6 temporal influence evaluation over cognitive memory benchmark"
)]
struct Cli {
    /// Directory containing cognitive memory benchmark TOML suites.
    #[arg(long, default_value = "crates/eval/datasets/cognitive_memory")]
    dataset_dir: PathBuf,
    /// Write the Phase2TemporalInfluenceEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase2-temporal-influence-eval")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase2TemporalInfluenceEvaluator::evaluate(&cli.dataset_dir, cli.tag)?;

    println!("=== Synapse Phase 2.6 temporal influence evaluation ===");
    println!("tag:                         {}", report.tag);
    println!("dataset_dir:                 {}", report.dataset_dir);
    println!("cases:                       {}", report.case_count);
    println!(
        "baseline:                    {} ({:.4})",
        report.baseline.name, report.baseline.score
    );
    println!(
        "temporal:                    {} ({:.4})",
        report.temporal.name, report.temporal.score
    );
    println!(
        "temporal_update_accuracy:    {:.4}",
        report.metrics.temporal_update_accuracy
    );
    println!(
        "obsolete_memory_detection:   {:.4}",
        report.metrics.obsolete_memory_detection
    );
    println!(
        "historical_preservation:     {:.4}",
        report.metrics.historical_preservation
    );
    println!(
        "causal_transition_accuracy:  {:.4}",
        report.metrics.causal_transition_accuracy
    );
    println!(
        "obsolete_memory_error:       {} -> {} (+{})",
        report.temporal_errors.obsolete_memory_error.before,
        report.temporal_errors.obsolete_memory_error.after,
        report.temporal_errors.obsolete_memory_error.improvement
    );
    println!("pass:                        {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 2.6 temporal influence report to {}",
        cli.json.display()
    );
    Ok(())
}
