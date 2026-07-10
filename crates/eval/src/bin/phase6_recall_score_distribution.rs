use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase6RecallScoreDistributionEvaluator;

#[derive(Debug, Parser)]
#[command(about = "Run the Phase 6.2 Recall Score Distribution Study")]
struct Cli {
    #[arg(
        long,
        default_value = "crates/eval/reports/phase6_recall_score_distribution.json"
    )]
    json: PathBuf,
    #[arg(long, default_value = "phase6-recall-score-distribution")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase6RecallScoreDistributionEvaluator::evaluate(cli.tag)?;
    let top1_top2 = report
        .adjacent_gaps
        .iter()
        .find(|gap| gap.left_rank == 1 && gap.right_rank == 2)
        .context("missing top1-top2 distribution")?;

    println!("Phase: {}", report.phase);
    println!(
        "Dataset: queries={} memories={} candidate_count_mean={:.2}",
        report.dataset.scenarios, report.dataset.memories, report.candidate_count.summary.mean,
    );
    println!(
        "Top1-Top2 normalized gap: mean={:.6} median={:.6} P90={:.6} P95={:.6} P99={:.6} min={:.6}",
        top1_top2.top_relative_gap.mean,
        top1_top2.top_relative_gap.median,
        top1_top2.top_relative_gap.p90,
        top1_top2.top_relative_gap.p95,
        top1_top2.top_relative_gap.p99,
        top1_top2.top_relative_gap.min,
    );
    println!("Margin coverage:");
    for coverage in &report.margin_coverage {
        println!(
            "  threshold={:.2} eligible={:>3}/{} rate={:.4} mean_candidates={:.4}",
            coverage.threshold,
            coverage.eligible_scenarios,
            coverage.scenarios,
            coverage.eligible_rate,
            coverage.mean_candidates_inside_margin,
        );
    }
    println!(
        "Locked threshold {:.2}: eligible={}/{} rate={:.4}",
        report.decision.locked_margin_threshold,
        report.decision.locked_margin_eligible_scenarios,
        report.dataset.scenarios,
        report.decision.locked_margin_eligible_rate,
    );
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
    eprintln!("wrote Phase 6.2 report to {}", cli.json.display());
    Ok(())
}
