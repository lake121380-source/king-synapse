use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase4CognitiveCompetitionStabilityEvaluator;

#[derive(Parser)]
#[command(
    name = "phase4_cognitive_competition_stability",
    about = "Synapse Phase 4.5 cognitive competition stability evaluation"
)]
struct Cli {
    /// Write the Phase4CognitiveCompetitionStabilityReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase4-cognitive-competition-stability")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase4CognitiveCompetitionStabilityEvaluator::evaluate(cli.tag)?;

    println!("Phase 4.5 Cognitive Competition Stability Evaluation");
    println!();
    println!("Experiment 1:");
    println!("Dominance Stability");
    println!();
    println!("Runs:");
    println!("{}", report.deterministic.runs);
    println!();
    println!("Score:");
    println!("{:.4}", report.metrics.dominance_stability);
    println!();
    println!("Experiment 2:");
    println!("Context Noise Resistance");
    println!();
    println!("Cases:");
    println!("{}/{}", report.noise.unchanged_cases, report.noise.cases);
    println!();
    println!("Score:");
    println!("{:.4}", report.metrics.noise_resistance);
    println!();
    println!("Experiment 3:");
    println!("Evidence Transition");
    println!();
    println!("Transition:");
    println!(
        "{}",
        report
            .transition
            .result
            .dominant_sequence
            .windows(2)
            .find(|window| window[0] != window[1])
            .map(|window| format!("{} -> {}", window[0], window[1]))
            .unwrap_or_else(|| "none".to_string())
    );
    println!();
    println!("Oscillation:");
    println!("{}", report.transition.result.oscillation_events);
    println!();
    println!("--------------------------------");
    println!();
    println!("Phase 4.5 {}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 4.5 cognitive competition stability report to {}",
        cli.json.display()
    );
    Ok(())
}
