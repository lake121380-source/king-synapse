use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase4CognitiveInfluenceEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase4-cognitive-influence",
    about = "Synapse Phase 4.1 cognitive influence evaluation"
)]
struct Cli {
    /// Write the Phase4CognitiveInfluenceReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase4-cognitive-influence")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase4CognitiveInfluenceEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 4.1 cognitive influence evaluation ===");
    println!("tag:                              {}", report.tag);
    println!("phase:                            {}", report.phase);
    println!("mode:                             {}", report.mode);
    println!(
        "evaluation_version:               {}",
        report.evaluation_version
    );
    println!(
        "baseline_version:                 {}",
        report.baseline_version
    );
    println!("scenarios:                        {}", report.scenarios);
    println!(
        "weight_history:                   {:.4}",
        report.weights.historical_strength
    );
    println!(
        "weight_temporal:                  {:.4}",
        report.weights.temporal_confidence
    );
    println!(
        "weight_context:                   {:.4}",
        report.weights.context_alignment
    );
    println!(
        "weight_reliability:               {:.4}",
        report.weights.reliability_score
    );
    println!(
        "influence_accuracy:               {:.4}",
        report.metrics.influence_accuracy
    );
    println!(
        "context_alignment_score:          {:.4}",
        report.metrics.context_alignment_score
    );
    println!(
        "competition_stability:            {:.4}",
        report.metrics.competition_stability
    );
    println!(
        "explanation_quality:              {:.4}",
        report.metrics.explanation_quality
    );
    println!(
        "core_changed:                     {}",
        report.safety.core_changed
    );
    println!(
        "memory_written:                   {}",
        report.safety.memory_written
    );
    println!(
        "runtime_influence_changed:        {}",
        report.safety.runtime_influence_changed
    );
    println!("pass:                             {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 4.1 cognitive influence report to {}",
        cli.json.display()
    );
    Ok(())
}
