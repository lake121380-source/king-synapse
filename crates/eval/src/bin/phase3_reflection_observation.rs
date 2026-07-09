use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase3ReflectionObservationEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase3-reflection-observation",
    about = "Synapse Phase 3.1 reflection observation trace evaluation"
)]
struct Cli {
    /// Write the Phase3ReflectionObservationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase3-reflection-observation")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase3ReflectionObservationEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 3.1 reflection observation ===");
    println!("tag:                          {}", report.tag);
    println!(
        "evaluation_version:           {}",
        report.evaluation_version
    );
    println!("baseline_version:             {}", report.baseline_version);
    println!("traces:                       {}", report.trace_count);
    println!("reflected:                    {}", report.reflected);
    println!("observed:                     {}", report.observed);
    println!("ignored:                      {}", report.ignored);
    println!(
        "reflection_trigger_precision: {:.4}",
        report.metrics.reflection_trigger_precision
    );
    println!(
        "reflection_trigger_recall:    {:.4}",
        report.metrics.reflection_trigger_recall
    );
    println!(
        "action_agreement:             {:.4}",
        report.metrics.action_agreement
    );
    println!(
        "lesson_grounding_readiness:   {:.4}",
        report.metrics.lesson_grounding_readiness
    );
    println!(
        "lesson_scope_readiness:       {:.4}",
        report.metrics.lesson_scope_readiness
    );
    println!(
        "observation_safety:           {:.4}",
        report.metrics.observation_safety
    );
    println!("playbook_created:             {}", report.playbook_created);
    println!(
        "future_influence_changed:     {}",
        report.future_influence_changed
    );
    println!("pass:                         {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 3.1 reflection observation report to {}",
        cli.json.display()
    );
    Ok(())
}
