use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase3FutureInfluenceEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase3-future-influence",
    about = "Synapse Phase 3.4 future influence evaluation"
)]
struct Cli {
    /// Write the Phase3FutureInfluenceReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase3-future-influence")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase3FutureInfluenceEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 3.4 future influence experiment ===");
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
        "promoted_lesson_source_count:     {}",
        report.promoted_lesson_source_count
    );
    println!(
        "helpful_lessons:                  {}",
        report.results.helpful_lessons
    );
    println!(
        "neutral_lessons:                  {}",
        report.results.neutral_lessons
    );
    println!(
        "rejected_influence:               {}",
        report.results.rejected_influence
    );
    println!(
        "influence_gain_score:             {:.4}",
        report.metrics.influence_gain_score
    );
    println!(
        "decision_improvement_score:       {:.4}",
        report.metrics.decision_improvement_score
    );
    println!(
        "failure_reduction_score:          {:.4}",
        report.metrics.failure_reduction_score
    );
    println!(
        "lesson_usefulness_score:          {:.4}",
        report.metrics.lesson_usefulness_score
    );
    println!(
        "no_write_safety:                  {:.4}",
        report.metrics.no_write_safety
    );
    println!(
        "memory_written:                   {}",
        report.safety.memory_written
    );
    println!(
        "playbook_created:                 {}",
        report.safety.playbook_created
    );
    println!(
        "future_influence_changed:         {}",
        report.safety.future_influence_changed
    );
    println!("pass:                             {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 3.4 future influence report to {}",
        cli.json.display()
    );
    Ok(())
}
