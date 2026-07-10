use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase5CognitivePolicyEvaluator;

#[derive(Parser)]
#[command(
    name = "phase5_cognitive_policy",
    about = "Synapse Phase 5.3.3 cognitive ranking policy study"
)]
struct Cli {
    #[arg(long)]
    json: PathBuf,
    #[arg(long, default_value = "phase5-cognitive-policy")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase5CognitivePolicyEvaluator::evaluate(cli.tag)?;

    println!("Phase 5.3.3 Cognitive Ranking Policy Study");
    println!("Scenarios: {}", report.benchmark.scenarios);
    println!("Candidates: {}", report.benchmark.candidates);
    println!();
    println!("Policy decision table:");
    for policy in &report.policies {
        println!(
            "- {:42} MRR={:.4} delta={:+.4} precision={:.4} recall={:.4} unnecessary={:.4} catastrophic={:.4}",
            policy.policy,
            policy.metrics.policy_mrr,
            policy.metrics.mrr_delta,
            policy.metrics.intervention_precision,
            policy.metrics.intervention_recall,
            policy.metrics.unnecessary_intervention_rate,
            policy.metrics.catastrophic_regression_rate,
        );
    }
    println!();
    println!("Ablation policy: {}", report.ablation_policy);
    for ablation in &report.ablations {
        println!(
            "- {:24} MRR={:.4} intervention_recall={:.4} removed={}",
            ablation.name,
            ablation.metrics.policy_mrr,
            ablation.metrics.intervention_recall,
            ablation.removed_factor_count,
        );
    }
    println!("Runtime applied: {}", report.guards.runtime_applied);
    println!("Status: {}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!("wrote Phase 5.3.3 report to {}", cli.json.display());
    Ok(())
}
