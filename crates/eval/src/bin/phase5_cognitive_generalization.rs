use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase5CognitiveGeneralizationEvaluator;

#[derive(Debug, Parser)]
#[command(about = "Run Phase 5.3.4 cognitive policy generalization validation")]
struct Cli {
    #[arg(
        long,
        default_value = "crates/eval/reports/phase5_cognitive_generalization.json"
    )]
    json: PathBuf,
    #[arg(long, default_value = "phase5-cognitive-generalization")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase5CognitiveGeneralizationEvaluator::evaluate(cli.tag)?;

    println!("Phase: {}", report.phase);
    for split in &report.splits {
        println!(
            "{}: scenarios={} candidates={} sha256={}",
            split.split,
            split.benchmark.scenarios,
            split.benchmark.candidates,
            split.dataset_sha256
        );
        for policy in &split.policies {
            println!(
                "  {:42} MRR={:.4} precision={:.4} recall={:.4} unnecessary={:.4} catastrophic={:.4}",
                policy.policy,
                policy.metrics.policy_mrr,
                policy.metrics.intervention_precision,
                policy.metrics.intervention_recall,
                policy.metrics.unnecessary_intervention_rate,
                policy.metrics.catastrophic_regression_rate,
            );
        }
    }
    println!(
        "Hidden controlled generalization supported: {}",
        report
            .hidden_test_decision
            .controlled_generalization_supported
    );
    println!(
        "Runtime authorized: {}",
        report.hidden_test_decision.runtime_authorization
    );
    println!("Status: {}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!("wrote Phase 5.3.4 report to {}", cli.json.display());
    Ok(())
}
