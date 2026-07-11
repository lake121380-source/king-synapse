use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use synapse_eval::Phase7PatternExtractionProtocolEvaluator;

fn main() -> Result<()> {
    let report = Phase7PatternExtractionProtocolEvaluator::evaluate("phase7.2-protocol-frozen")?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_pattern_extraction_protocol.json");
    fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")?;

    println!("Phase: {}", report.phase);
    println!("Design cases: {}", report.dataset.case_count);
    println!(
        "Supporting experiences: {}",
        report.dataset.supporting_experience_count
    );
    println!("Counterexamples: {}", report.dataset.counterexample_count);
    println!(
        "Reference candidates valid: {}",
        report.dataset.reference_candidates_valid
    );
    println!("Negative cases: {}", report.negative_cases.len());
    println!(
        "Extraction algorithm implemented: {}",
        report.guards.extraction_algorithm_implemented
    );
    println!(
        "Held-out cases untouched: {}",
        report.guards.held_out_cases_untouched
    );
    println!("Runtime authorized: {}", report.guards.runtime_authorized);
    println!("Report: {}", output.display());
    Ok(())
}
