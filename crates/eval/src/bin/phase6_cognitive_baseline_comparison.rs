use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase6CognitiveBaselineComparisonEvaluator;

#[derive(Debug, Parser)]
#[command(about = "Run the Phase 6.1 Cognitive vs Simple Baseline evaluation")]
struct Cli {
    #[arg(
        long,
        default_value = "crates/eval/reports/phase6_cognitive_baseline_comparison.json"
    )]
    json: PathBuf,
    #[arg(long, default_value = "phase6-cognitive-baseline-comparison")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase6CognitiveBaselineComparisonEvaluator::evaluate(cli.tag)?;

    println!("Phase: {}", report.phase);
    println!(
        "Dataset: scenarios={} memories={} categories={}",
        report.dataset.scenarios, report.dataset.memories, report.dataset.categories
    );
    for policy in &report.policies {
        println!(
            "{:<36} R@1={:.4} R@3={:.4} MRR@5={:.4} NDCG@5={:.4} IP={:.4} IR={:.4} UIR={:.4} CR={:.4}",
            policy.policy,
            policy.metrics.recall_at_1,
            policy.metrics.recall_at_3,
            policy.metrics.mrr_at_5,
            policy.metrics.ndcg_at_5,
            policy.metrics.intervention_precision,
            policy.metrics.intervention_recall,
            policy.metrics.unnecessary_intervention_rate,
            policy.metrics.catastrophic_regression_rate,
        );
    }
    println!("Best simple: {}", report.decision.best_simple_baseline);
    println!(
        "Cognitive gain: MRR@5={:+.4} Recall@1={:+.4}",
        report.decision.cognitive_gain_vs_best_simple_baseline,
        report
            .decision
            .cognitive_recall_at_1_gain_vs_best_simple_baseline,
    );
    println!("Outcome: {}", report.decision.outcome);
    println!(
        "Hermes shadow integration recommended: {}",
        report.decision.hermes_shadow_integration_recommended
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
    eprintln!("wrote Phase 6.1 report to {}", cli.json.display());
    Ok(())
}
