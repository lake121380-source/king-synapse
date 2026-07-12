use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::phase7_semantic_judge_redesign::Phase7SemanticJudgeRedesignEvaluator;

fn main() -> Result<()> {
    let report = Phase7SemanticJudgeRedesignEvaluator::evaluate(
        "phase7.3.2-semantic-judge-redesign-design-only",
    )?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_semantic_judge_redesign.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    println!("Phase: {}", report.phase);
    println!("Execution: {}", report.execution_status);
    println!("Decision: {:?}", report.decision);
    if let Some(ordinal) = report.ordinal_agreement {
        println!(
            "Ordinal exact agreement: {}/{} ({:.4})",
            ordinal.exact_match_count,
            ordinal.case_count,
            ordinal.exact_agreement.unwrap_or(0.0)
        );
    }
    if let Some(summary) = report.redesigned_semantic_judge {
        println!(
            "Strict safety: precision={:?} recall={:?} specificity={:?} FPR={:?} balanced_accuracy={:?} MCC={:?}",
            summary.strict_safety.precision,
            summary.strict_safety.recall_sensitivity,
            summary.strict_safety.specificity,
            summary.strict_safety.false_positive_rate,
            summary.strict_safety.balanced_accuracy,
            summary.strict_safety.matthews_correlation_coefficient,
        );
    }
    println!("Report: {}", output.display());
    Ok(())
}
