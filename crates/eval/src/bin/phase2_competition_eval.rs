use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase2CompetitionEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase2-competition-eval",
    about = "Synapse Phase 2.3 memory competition evaluation over cognitive memory benchmark"
)]
struct Cli {
    /// Directory containing cognitive memory benchmark TOML suites.
    #[arg(long, default_value = "crates/eval/datasets/cognitive_memory")]
    dataset_dir: PathBuf,
    /// Write the Phase2CompetitionEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase2-competition-eval")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase2CompetitionEvaluator::evaluate(&cli.dataset_dir, cli.tag)?;

    println!("=== Synapse Phase 2.3 competition evaluation ===");
    println!("tag:                         {}", report.tag);
    println!("dataset_dir:                 {}", report.dataset_dir);
    println!("cases:                       {}", report.case_count);
    println!(
        "baseline:                    {} ({:.4})",
        report.baseline.name, report.baseline.score
    );
    println!(
        "competition:                 {} ({:.4})",
        report.competition.name, report.competition.score
    );
    println!(
        "decision_mismatch_delta:     {:+}",
        report.delta.decision_mismatch
    );
    println!(
        "causal_order_error_delta:    {:+}",
        report.delta.causal_order_error
    );
    println!(
        "suppression_correctness:     {:.4}",
        report.delta.suppression_correctness
    );
    println!(
        "influence_shift:             {:.4}",
        report.delta.influence_shift
    );
    println!("pass:                        {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 2.3 competition report to {}",
        cli.json.display()
    );
    Ok(())
}
