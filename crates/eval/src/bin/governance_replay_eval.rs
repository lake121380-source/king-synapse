use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceReplayEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-replay-eval",
    about = "Synapse Phase 1c-9 governance counterfactual replay evaluation"
)]
struct Cli {
    /// Path to a governance replay TOML dataset.
    #[arg(long, default_value = "crates/eval/datasets/governance_replay.toml")]
    dataset: PathBuf,
    /// Path to detector feedback observations used for reliability-calibrated risk.
    #[arg(long, default_value = "crates/eval/datasets/governance_feedback.toml")]
    feedback_dataset: PathBuf,
    /// Write the independent GovernanceReplayEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-replay")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceReplayEvaluator::evaluate(&cli.dataset, &cli.feedback_dataset, cli.tag)?;

    println!("=== Synapse governance counterfactual replay ===");
    println!("tag:                    {}", report.tag);
    println!("dataset:                {}", report.dataset);
    println!("feedback_dataset:       {}", report.feedback_dataset);
    println!("detectors:              {}", report.detector_count);
    println!("cases:                  {}", report.case_count);
    println!("events:                 {}", report.event_count);
    println!(
        "accuracy:               {:.4} -> {:.4} ({:+.4})",
        report.baseline_accuracy, report.governed_accuracy, report.counterfactual_gain
    );
    println!(
        "regret:                 {:.4} -> {:.4} ({:+.4}, rate={:.4})",
        report.baseline_regret,
        report.governed_regret,
        report.regret_reduction,
        report.regret_reduction_rate
    );
    println!("normal_preservation:    {:.4}", report.normal_preservation);
    println!(
        "over_conservatism:      {:.4}",
        report.over_conservatism_rate
    );
    println!("stability:              {:.4}", report.stability_score);
    println!("pass:                   {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!("wrote governance replay report to {}", cli.json.display());
    Ok(())
}
