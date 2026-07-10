use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase5ShadowRankingEvaluator;

#[derive(Parser)]
#[command(
    name = "phase5_shadow_ranking",
    about = "Synapse Phase 5.3.2 deterministic cognitive booster shadow ranking evaluation"
)]
struct Cli {
    /// Write the Phase5ShadowRankingReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase5-shadow-ranking")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase5ShadowRankingEvaluator::evaluate(cli.tag)?;

    println!("Phase 5.3.2 Shadow Ranking Experiment");
    println!();
    println!("Algorithm: {}", report.algorithm);
    println!("Scenarios: {}", report.scenarios);
    println!("Proposal coverage: {:.4}", report.metrics.proposal_coverage);
    println!("Changed positions: {}", report.metrics.changed_positions);
    println!(
        "Average absolute rank delta: {:.4}",
        report.metrics.avg_abs_rank_delta
    );
    println!(
        "Maximum absolute rank delta: {}",
        report.metrics.max_abs_rank_delta
    );
    println!(
        "Maximum proposed bonus: {:.4}",
        report.metrics.max_proposed_bonus
    );
    println!("Bounded rate: {:.4}", report.metrics.bounded_rate);
    println!("Determinism: {:.4}", report.metrics.determinism);
    println!(
        "Recall@{} baseline/shadow/delta: {:.4} / {:.4} / {:+.4}",
        report.metric_cutoff,
        report.metrics.baseline_recall_at_k,
        report.metrics.shadow_recall_at_k,
        report.metrics.shadow_recall_delta
    );
    println!(
        "MRR baseline/shadow/delta: {:.4} / {:.4} / {:+.4}",
        report.metrics.baseline_mrr, report.metrics.shadow_mrr, report.metrics.shadow_mrr_delta
    );
    println!("Runtime applied: {}", report.guards.runtime_applied);
    println!("Status: {}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 5.3.2 shadow ranking report to {}",
        cli.json.display()
    );
    Ok(())
}
