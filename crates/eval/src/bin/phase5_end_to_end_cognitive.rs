use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase5EndToEndCognitiveEvaluator;

#[derive(Debug, Parser)]
#[command(about = "Run Phase 5.4 independent end-to-end cognitive validation")]
struct Cli {
    #[arg(
        long,
        default_value = "crates/eval/reports/phase5_end_to_end_cognitive.json"
    )]
    json: PathBuf,
    #[arg(long, default_value = "phase5-end-to-end-cognitive")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase5EndToEndCognitiveEvaluator::evaluate(cli.tag)?;

    println!("Phase: {}", report.phase);
    println!(
        "Dataset: scenarios={} memories={} expected-retrieved={:.4}",
        report.dataset.scenarios,
        report.dataset.memories,
        report.dataset.expected_candidate_retrieval_rate
    );
    for policy in &report.policies {
        println!(
            "  {:36} R@1={:.4} R@3={:.4} MRR@5={:.4} NDCG@5={:.4} intervention={:.4} regression={:.4}",
            policy.policy,
            policy.metrics.recall_at_1,
            policy.metrics.recall_at_3,
            policy.metrics.mrr_at_5,
            policy.metrics.ndcg_at_5,
            policy.metrics.cognitive_intervention_rate,
            policy.metrics.top1_regression_rate,
        );
    }
    println!(
        "Independent end-to-end value supported: {}",
        report.decision.independent_end_to_end_value_supported
    );
    println!(
        "Runtime authorized: {}",
        report.decision.runtime_authorization
    );
    println!("Status: {}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!("wrote Phase 5.4 report to {}", cli.json.display());
    Ok(())
}
