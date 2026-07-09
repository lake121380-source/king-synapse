use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase4CognitiveCompetitionEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase4-cognitive-competition",
    about = "Synapse Phase 4.2 cognitive competition evaluation"
)]
struct Cli {
    /// Write the Phase4CognitiveCompetitionReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase4-cognitive-competition")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase4CognitiveCompetitionEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 4.2 cognitive competition model ===");
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
        "dominant_selection_accuracy:      {:.4}",
        report.metrics.dominant_selection_accuracy
    );
    println!(
        "competition_convergence:          {:.4}",
        report.metrics.competition_convergence
    );
    println!(
        "suppression_quality:              {:.4}",
        report.metrics.suppression_quality
    );
    println!(
        "activation_stability:             {:.4}",
        report.metrics.activation_stability
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
        "runtime_activation_changed:       {}",
        report.safety.runtime_activation_changed
    );
    println!("pass:                             {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 4.2 cognitive competition report to {}",
        cli.json.display()
    );
    Ok(())
}
