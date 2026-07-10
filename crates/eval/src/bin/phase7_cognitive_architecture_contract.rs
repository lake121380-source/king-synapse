use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase7CognitiveArchitectureContractEvaluator;

#[derive(Debug, Parser)]
#[command(about = "Run the Phase 7.0 Cognitive Architecture Contract gate")]
struct Cli {
    #[arg(
        long,
        default_value = "crates/eval/reports/phase7_cognitive_architecture_contract.json"
    )]
    json: PathBuf,
    #[arg(long, default_value = "phase7-cognitive-architecture-contract")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase7CognitiveArchitectureContractEvaluator::evaluate(cli.tag)?;

    println!("Phase: {}", report.phase);
    println!("North Star: {}", report.north_star.statement);
    println!(
        "Artifacts: {} contract cases: {}",
        report.artifact_ladder.len(),
        report.invalid_contract_cases.len() + 1
    );
    println!(
        "Experience-to-Pattern mainline authorized: {}",
        report.decision.experience_to_pattern_mainline_authorized
    );
    println!(
        "Pattern discovery algorithm authorized: {}",
        report.decision.pattern_discovery_algorithm_authorized
    );
    println!(
        "Runtime authorized: {}",
        report.decision.runtime_authorization
    );
    println!("Status: {}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!("wrote Phase 7.0 report to {}", cli.json.display());
    Ok(())
}
