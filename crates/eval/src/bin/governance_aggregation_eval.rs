use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::GovernanceAggregationEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-governance-aggregation-eval",
    about = "Synapse Phase 1c-8.5 reliability-calibrated governance aggregation evaluation"
)]
struct Cli {
    /// Path to a detector feedback TOML dataset.
    #[arg(long, default_value = "crates/eval/datasets/governance_feedback.toml")]
    dataset: PathBuf,
    /// Write the independent GovernanceAggregationEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1c-governance-aggregation")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = GovernanceAggregationEvaluator::evaluate(&cli.dataset, cli.tag)?;

    println!("=== Synapse reliability-calibrated governance aggregation ===");
    println!("tag:                    {}", report.tag);
    println!("dataset:                {}", report.dataset);
    println!("detectors:              {}", report.detector_count);
    println!("observations:           {}", report.observation_count);
    println!("best_method:            {}", report.best_method);
    println!(
        "raw:                    calibration={:.4} auc={:.4} stability={:.4}",
        report.raw.calibration_error, report.raw.ranking_auc, report.raw.stability_score
    );
    println!(
        "reliability_scaled:     calibration={:.4} delta_vs_raw={:+.4} auc={:.4} stability={:.4}",
        report.reliability_scaled.calibration_error,
        report.reliability_scaled.calibration_error_delta_vs_raw,
        report.reliability_scaled.ranking_auc,
        report.reliability_scaled.stability_score
    );
    println!(
        "empirical_calibrated:   calibration={:.4} delta_vs_raw={:+.4} auc={:.4} stability={:.4}",
        report.empirical_calibrated.calibration_error,
        report.empirical_calibrated.calibration_error_delta_vs_raw,
        report.empirical_calibrated.ranking_auc,
        report.empirical_calibrated.stability_score
    );
    println!("pass:                   {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance aggregation report to {}",
        cli.json.display()
    );
    Ok(())
}
