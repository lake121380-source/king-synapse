use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase3LessonCandidateEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase3-lesson-candidate-eval",
    about = "Synapse Phase 3.2 lesson candidate evaluation"
)]
struct Cli {
    /// Write the Phase3LessonCandidateEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase3-lesson-candidate-eval")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase3LessonCandidateEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 3.2 lesson candidate evaluation ===");
    println!("tag:                              {}", report.tag);
    println!(
        "evaluation_version:               {}",
        report.evaluation_version
    );
    println!(
        "baseline_version:                 {}",
        report.baseline_version
    );
    println!(
        "source_traces:                    {}",
        report.source_trace_count
    );
    println!(
        "candidates:                       {}",
        report.candidate_count
    );
    println!("accepted:                         {}", report.accepted);
    println!("observe_more:                     {}", report.observe_more);
    println!("rejected:                         {}", report.rejected);
    println!(
        "lesson_grounding_score:           {:.4}",
        report.metrics.lesson_grounding_score
    );
    println!(
        "lesson_scope_score:               {:.4}",
        report.metrics.lesson_scope_score
    );
    println!(
        "contradiction_resistance_score:   {:.4}",
        report.metrics.contradiction_resistance_score
    );
    println!(
        "overgeneralization_guard_score:   {:.4}",
        report.metrics.overgeneralization_guard_score
    );
    println!(
        "candidate_accept_precision:       {:.4}",
        report.metrics.candidate_accept_precision
    );
    println!(
        "candidate_decision_agreement:     {:.4}",
        report.metrics.candidate_decision_agreement
    );
    println!(
        "promotion_safety:                 {:.4}",
        report.metrics.promotion_safety
    );
    println!(
        "lesson_persisted:                 {}",
        report.lesson_persisted
    );
    println!(
        "playbook_created:                 {}",
        report.playbook_created
    );
    println!(
        "future_influence_changed:         {}",
        report.future_influence_changed
    );
    println!("pass:                             {}", report.pass);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote Phase 3.2 lesson candidate report to {}",
        cli.json.display()
    );
    Ok(())
}
