use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase3LessonLifecycleEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase3-lesson-lifecycle",
    about = "Synapse Phase 3.5 lesson lifecycle evaluation"
)]
struct Cli {
    /// Write the Phase3LessonLifecycleReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase3-lesson-lifecycle")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase3LessonLifecycleEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 3.5 lesson lifecycle evaluation ===");
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
        "future_influence_source_count:    {}",
        report.future_influence_source_count
    );
    println!(
        "state_candidate:                  {}",
        report.states.candidate
    );
    println!("state_active:                     {}", report.states.active);
    println!(
        "state_challenged:                 {}",
        report.states.challenged
    );
    println!(
        "state_superseded:                 {}",
        report.states.superseded
    );
    println!(
        "lifecycle_transition_accuracy:    {:.4}",
        report.metrics.lifecycle_transition_accuracy
    );
    println!(
        "contradiction_response_score:     {:.4}",
        report.metrics.contradiction_response_score
    );
    println!(
        "supersession_score:               {:.4}",
        report.metrics.supersession_score
    );
    println!(
        "reinforcement_score:              {:.4}",
        report.metrics.reinforcement_score
    );
    println!(
        "false_lesson_protection_score:    {:.4}",
        report.metrics.false_lesson_protection_score
    );
    println!(
        "lifecycle_safety:                 {:.4}",
        report.metrics.lifecycle_safety
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
        "wrote Phase 3.5 lesson lifecycle report to {}",
        cli.json.display()
    );
    Ok(())
}
