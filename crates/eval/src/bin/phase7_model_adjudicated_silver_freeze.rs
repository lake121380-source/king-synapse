use anyhow::{Context, Result};
use std::path::PathBuf;
use synapse_eval::Phase7ModelAdjudicatedSilverFreeze;

fn main() -> Result<()> {
    let artifact = Phase7ModelAdjudicatedSilverFreeze::build()?;
    let output = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("datasets")
        .join("pattern_extraction")
        .join("phase7_3_1_model_adjudicated_silver_labels.json");
    std::fs::write(&output, serde_json::to_string_pretty(&artifact)? + "\n")
        .with_context(|| format!("write {}", output.display()))?;
    println!("Phase: {}", artifact.phase);
    println!("Frozen claims: {}", artifact.claim_count);
    println!("Frozen candidates: {}", artifact.candidate_count);
    println!("Label status: {}", artifact.label_status);
    println!("Human Gold: {}", artifact.human_gold);
    println!(
        "Scope calibration available: {}",
        artifact.scope_calibration_available
    );
    println!("Artifact: {}", output.display());
    Ok(())
}
