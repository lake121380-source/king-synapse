use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase5TraceQualityEvaluator;

#[derive(Parser)]
#[command(
    name = "phase5_trace_quality",
    about = "Synapse Phase 5.2 cognitive trace quality evaluation"
)]
struct Cli {
    /// Write the Phase5TraceQualityReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase5-trace-quality")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase5TraceQualityEvaluator::evaluate(cli.tag)?;

    println!("Phase 5.2 Cognitive Trace Quality Evaluation");
    println!();
    println!("Scenarios: {}", report.scenarios);
    println!(
        "Explanation completeness: {:.4}",
        report.metrics.explanation_completeness
    );
    println!(
        "Factor faithfulness: {:.4}",
        report.metrics.factor_faithfulness
    );
    println!(
        "Trace preference rate: {:.4}",
        report.metrics.trace_preference_rate
    );
    println!("Determinism: {:.4}", report.metrics.determinism);
    println!(
        "Explanation information gain: {:+.4}",
        report.metrics.explanation_information_gain
    );
    println!(
        "Retrieval/trace alignment (diagnostic): {:.4}",
        report.metrics.retrieval_trace_alignment
    );
    println!("Judge mode: {}", report.judge_protocol.mode);
    println!("Status: {}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 5.2 trace quality report to {}",
        cli.json.display()
    );
    Ok(())
}
