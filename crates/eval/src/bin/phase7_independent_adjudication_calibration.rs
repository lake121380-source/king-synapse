use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::phase7_independent_adjudication_calibration::{
    build_phase7_blind_review_packet, Phase7AdjudicationCalibrationEvaluator,
};

fn main() -> Result<()> {
    let report = Phase7AdjudicationCalibrationEvaluator::evaluate(
        "phase7.3.1-independent-adjudication-frozen-judge-calibration",
    )?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_independent_adjudication_calibration.json");
    std::fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;

    let blind_packet = build_phase7_blind_review_packet()?;
    let blind_packet_output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("datasets")
        .join("pattern_extraction")
        .join("phase7_3_1_blind_review_packet.json");
    std::fs::write(
        &blind_packet_output,
        serde_json::to_string_pretty(&blind_packet)? + "\n",
    )
    .with_context(|| format!("write {}", blind_packet_output.display()))?;

    println!("Phase: {}", report.phase);
    println!(
        "Frozen claim-source anchors: {}",
        report.claim_source_anchors.len()
    );
    println!(
        "Reviewer A completed: {}",
        report.guards.reviewer_a_completed
    );
    println!(
        "Reviewer B completed: {}",
        report.guards.reviewer_b_completed
    );
    println!(
        "Adjudication completed: {}",
        report.guards.independent_adjudication_completed
    );
    println!(
        "Judge calibration completed: {}",
        report.guards.scorer_calibration_completed
    );
    println!("Decision: {:?}", report.decision);
    println!("Report: {}", output.display());
    println!(
        "Blind review packet: {} cases / {} anchors",
        blind_packet.cases.len(),
        blind_packet
            .cases
            .iter()
            .map(|case| case.claim_source_anchors.len())
            .sum::<usize>()
    );
    println!("Blind packet: {}", blind_packet_output.display());
    Ok(())
}
