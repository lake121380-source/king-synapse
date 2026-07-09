use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase4ContextualWeightingEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase4-contextual-weighting",
    about = "Synapse Phase 4.3 contextual cognitive weighting evaluation"
)]
struct Cli {
    /// Write the Phase4ContextualWeightingReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase4-contextual-weighting")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase4ContextualWeightingEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 4.3 contextual cognitive weighting ===");
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
        "context_weight_accuracy:          {:.4}",
        report.metrics.context_weight_accuracy
    );
    println!(
        "adaptive_weight_shift:            {:.4}",
        report.metrics.adaptive_weight_shift
    );
    println!(
        "cross_context_consistency:        {:.4}",
        report.metrics.cross_context_consistency
    );
    println!(
        "importance_explanation:           {:.4}",
        report.metrics.importance_explanation
    );
    println!(
        "conflict_resolution:              {:.4}",
        report.metrics.conflict_resolution
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
        "runtime_weight_changed:           {}",
        report.safety.runtime_weight_changed
    );
    println!("pass:                             {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 4.3 contextual cognitive weighting report to {}",
        cli.json.display()
    );
    Ok(())
}
