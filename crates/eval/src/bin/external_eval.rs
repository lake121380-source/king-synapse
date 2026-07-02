use anyhow::{bail, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::{
    run_external_comparison, ExternalComparisonOptions, ExternalComparisonReport,
    ExternalSystemKind,
};

#[derive(Parser)]
#[command(
    name = "kr-external-eval",
    about = "Run external memory comparison harness"
)]
struct Cli {
    /// Comma-separated systems: king-synapse, graphiti, mem0, letta, or all.
    #[arg(long, default_value = "all")]
    systems: String,
    /// Optional executable/script that runs a Graphiti adapter.
    ///
    /// The command receives one argument: a JSON adapter-input path. It must
    /// print an ExternalSystemRun JSON object to stdout.
    #[arg(long)]
    graphiti_command: Option<PathBuf>,
    /// Extra argument passed before the adapter-input path.
    ///
    /// On Windows, use this to run a Python adapter:
    /// --graphiti-command python --graphiti-arg scripts/eval/graphiti_adapter.py
    #[arg(long)]
    graphiti_arg: Vec<String>,
    /// Optional executable/script that runs a Mem0 adapter.
    ///
    /// The command receives one argument: a JSON adapter-input path. It must
    /// print an ExternalSystemRun JSON object to stdout.
    #[arg(long)]
    mem0_command: Option<PathBuf>,
    /// Extra argument passed before the adapter-input path.
    ///
    /// On Windows, use this to run a Python adapter:
    /// --mem0-command python --mem0-arg scripts/eval/mem0_adapter.py
    #[arg(long)]
    mem0_arg: Vec<String>,
    /// Optional executable/script that runs a Letta adapter.
    ///
    /// The command receives one argument: a JSON adapter-input path. It must
    /// print an ExternalSystemRun JSON object to stdout.
    #[arg(long)]
    letta_command: Option<PathBuf>,
    /// Extra argument passed before the adapter-input path.
    ///
    /// On Windows, use this to run a Python adapter:
    /// --letta-command python --letta-arg scripts/eval/letta_adapter.py
    #[arg(long)]
    letta_arg: Vec<String>,
    /// Optional path where the adapter input JSON should be written.
    #[arg(long)]
    adapter_input: Option<PathBuf>,
    /// Write the full external comparison report as JSON.
    #[arg(long)]
    json: Option<PathBuf>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = run_external_comparison(ExternalComparisonOptions {
        systems: parse_systems(&cli.systems)?,
        graphiti_command: cli.graphiti_command,
        graphiti_args: cli.graphiti_arg,
        mem0_command: cli.mem0_command,
        mem0_args: cli.mem0_arg,
        letta_command: cli.letta_command,
        letta_args: cli.letta_arg,
        adapter_input_path: cli.adapter_input,
    })?;
    print_external_summary(&report);

    if let Some(out) = cli.json.as_ref() {
        if let Some(parent) = out.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(out, serde_json::to_string_pretty(&report)?)?;
        eprintln!("wrote external comparison report to {}", out.display());
    }

    Ok(())
}

fn parse_systems(raw: &str) -> Result<Vec<ExternalSystemKind>> {
    let mut systems = Vec::new();
    for part in raw.split(',') {
        let part = part.trim().to_ascii_lowercase();
        if part.is_empty() {
            continue;
        }
        match part.as_str() {
            "all" => {
                return Ok(vec![
                    ExternalSystemKind::KingSynapse,
                    ExternalSystemKind::Graphiti,
                    ExternalSystemKind::Mem0,
                    ExternalSystemKind::Letta,
                ]);
            }
            "king-synapse" | "king" | "synapse" => systems.push(ExternalSystemKind::KingSynapse),
            "graphiti" | "zep" | "graphiti-zep" => systems.push(ExternalSystemKind::Graphiti),
            "mem0" | "mem-zero" => systems.push(ExternalSystemKind::Mem0),
            "letta" | "memgpt" => systems.push(ExternalSystemKind::Letta),
            other => bail!("unknown external comparison system: {other}"),
        }
    }

    if systems.is_empty() {
        return Ok(vec![
            ExternalSystemKind::KingSynapse,
            ExternalSystemKind::Graphiti,
            ExternalSystemKind::Mem0,
            ExternalSystemKind::Letta,
        ]);
    }
    systems.dedup();
    Ok(systems)
}

fn print_external_summary(report: &ExternalComparisonReport) {
    println!("=== King Synapse external memory comparison ===");
    println!("schema:          {}", report.schema_version);
    println!("dataset:         {}", report.dataset);
    println!("fixture chains:  {}", report.fixture_chains);
    println!("systems:         {}", report.summary.systems);
    println!("measured:        {}", report.summary.measured_systems);
    println!("not configured:  {}", report.summary.not_configured_systems);
    println!("failed:          {}", report.summary.failed_systems);
    println!();

    for system in &report.systems {
        println!("--- {} ({:?}) ---", system.system, system.status);
        println!("version:         {}", system.version);
        println!("chains:          {}", system.aggregate.chains);
        println!(
            "mean latency:    {:.2} ms",
            system.aggregate.mean_latency_ms
        );
        for metric in [
            "visible_seed_found",
            "hidden_influence_found",
            "hidden_influence_dominant",
            "suppressed_alternatives_visible",
            "evidence_path_available",
            "future_continuation_found",
            "reinforcement_isolated",
        ] {
            if let Some(aggregate) = system.aggregate.metrics.get(metric) {
                println!(
                    "{metric}: hit={} miss={} unsupported={} not_configured={} failed={}",
                    aggregate.hit,
                    aggregate.miss,
                    aggregate.unsupported,
                    aggregate.not_configured,
                    aggregate.failed
                );
            }
        }
        if !system.notes.is_empty() {
            println!("notes:");
            for note in &system.notes {
                println!("  - {note}");
            }
        }
        println!();
    }
}
