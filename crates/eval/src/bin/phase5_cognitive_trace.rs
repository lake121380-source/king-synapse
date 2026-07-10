use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase5CognitiveTraceEvaluator;

#[derive(Parser)]
#[command(
    name = "phase5_cognitive_trace",
    about = "Synapse Phase 5.1 cognitive competition trace integration evaluation"
)]
struct Cli {
    /// Write the Phase5CognitiveTraceReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase5-cognitive-trace")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase5CognitiveTraceEvaluator::evaluate(cli.tag)?;

    println!("Phase 5.1 Cognitive Competition Trace Integration");
    println!();
    println!("Scenarios:");
    println!("{}", report.scenarios);
    println!();
    println!("Trace generation rate:");
    println!("{:.4}", report.metrics.trace_generation_rate);
    println!();
    println!("Dominant validity:");
    println!("{:.4}", report.metrics.dominant_validity);
    println!();
    println!("Factor explanation rate:");
    println!("{:.4}", report.metrics.factor_explanation_rate);
    println!();
    println!("Trace determinism:");
    println!("{:.4}", report.metrics.trace_determinism);
    println!();
    println!("Recall regression:");
    println!("{:.4}", report.metrics.recall_regression);
    println!();
    println!("Latency P50 before/after:");
    println!(
        "{:.4} / {:.4} ms",
        report.latency.before.p50_ms, report.latency.after.p50_ms
    );
    println!();
    println!("Status:");
    println!("{}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 5.1 cognitive trace report to {}",
        cli.json.display()
    );
    Ok(())
}
