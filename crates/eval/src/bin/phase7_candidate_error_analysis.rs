use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::phase7_candidate_error_analysis::Phase7CandidateErrorAnalysisEvaluator;

fn main() -> Result<()> {
    let report =
        Phase7CandidateErrorAnalysisEvaluator::evaluate("phase7.3-candidate-error-analysis")?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_candidate_error_analysis.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    println!("Phase: {}", report.phase);
    println!("Candidates analyzed: {}", report.summary.candidate_count);
    println!(
        "Unsupported warnings: {}",
        report.summary.unsupported_warning_count
    );
    println!("Scope warnings: {}", report.summary.scope_warning_count);
    println!(
        "Confirmed scope expansion labels: {}",
        report.summary.scope_expansion_label_count
    );
    println!(
        "Direct in-scope falsification tests: {}/{}",
        report.summary.falsifiability.direct_in_scope_test_count, report.summary.candidate_count
    );
    println!("Decision: {:?}", report.decision);
    println!("Report: {}", output.display());
    Ok(())
}
