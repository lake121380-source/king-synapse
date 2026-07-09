use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase3LessonPromotionEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-phase3-lesson-promotion",
    about = "Synapse Phase 3.3 controlled lesson promotion evaluation"
)]
struct Cli {
    /// Write the Phase3LessonPromotionReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase3-lesson-promotion")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase3LessonPromotionEvaluator::evaluate(cli.tag)?;

    println!("=== Synapse Phase 3.3 controlled lesson promotion ===");
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
    println!(
        "input_candidates:                 {}",
        report.input_candidates
    );
    println!(
        "proposed_lessons:                 {}",
        report.promotion.proposed_lessons
    );
    println!(
        "playbook_candidates:              {}",
        report.promotion.playbook_candidates
    );
    println!(
        "not_promoted:                     {}",
        report.promotion.not_promoted
    );
    println!(
        "promotion_precision:              {:.4}",
        report.metrics.promotion_precision
    );
    println!(
        "promotion_readiness_score:        {:.4}",
        report.metrics.promotion_readiness_score
    );
    println!(
        "evidence_sufficiency_score:       {:.4}",
        report.metrics.evidence_sufficiency_score
    );
    println!(
        "scope_stability_score:            {:.4}",
        report.metrics.scope_stability_score
    );
    println!(
        "contradiction_safety_score:       {:.4}",
        report.metrics.contradiction_safety_score
    );
    println!(
        "promotion_decision_agreement:     {:.4}",
        report.metrics.promotion_decision_agreement
    );
    println!(
        "promotion_safety:                 {:.4}",
        report.metrics.promotion_safety
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
        "wrote Phase 3.3 lesson promotion report to {}",
        cli.json.display()
    );
    Ok(())
}
