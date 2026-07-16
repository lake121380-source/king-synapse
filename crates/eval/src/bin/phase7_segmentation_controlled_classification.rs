use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use synapse_eval::phase7_segmentation_controlled_classification::build_segmentation_controlled_readiness_report;

fn main() -> Result<()> {
    let report = build_segmentation_controlled_readiness_report()?;
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let output =
        root.join("crates/eval/reports/phase7_3_3_c_segmentation_controlled_readiness.json");
    fs::write(&output, serde_json::to_string_pretty(&report)? + "\n")?;
    println!("Phase: {}", report.phase);
    println!("Status: {}", report.status);
    println!("Decision: {}", report.decision);
    println!(
        "Packets: {} / Claims: {}",
        report.validation.provider_packet_count, report.validation.atomic_claim_count
    );
    println!(
        "Protocol-owned exact spans: {}",
        report.validation.all_protocol_owned_spans_exact
    );
    println!("Real model execution: not started");
    println!("Report: {}", output.display());
    Ok(())
}
