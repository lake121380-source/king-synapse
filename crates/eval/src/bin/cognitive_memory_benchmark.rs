use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::CognitiveMemoryBenchmarkEvaluator;

#[derive(Parser)]
#[command(
    name = "kr-cognitive-memory-benchmark",
    about = "Synapse Phase 1 final cognitive memory validation benchmark"
)]
struct Cli {
    /// Directory containing cognitive memory benchmark TOML suites.
    #[arg(long, default_value = "crates/eval/datasets/cognitive_memory")]
    dataset_dir: PathBuf,
    /// Write the CognitiveMemoryBenchmarkReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "phase1-final-validation")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = CognitiveMemoryBenchmarkEvaluator::evaluate(&cli.dataset_dir, cli.tag)?;

    println!("=== Synapse Phase 1 final validation ===");
    println!("tag:                              {}", report.tag);
    println!(
        "stage:                            {}",
        report.validation_stage
    );
    println!("dataset_dir:                      {}", report.dataset_dir);
    println!("suites:                           {}", report.suite_count);
    println!("cases:                            {}", report.case_count);
    println!(
        "challenges:                       {}",
        report.challenge_count
    );
    println!(
        "best_rag:                         {} ({:.4})",
        report.best_rag_method, report.best_rag_score
    );
    println!(
        "full_synapse_score:               {:.4}",
        report.full_synapse_score
    );
    println!(
        "full_over_best_rag_gain:          {:+.4}",
        report.full_over_best_rag_gain
    );
    println!(
        "retrieval_beyond_similarity:      {:.4}",
        report.retrieval_beyond_similarity_score
    );
    println!(
        "longitudinal_influence:           {:.4}",
        report.longitudinal_influence_score
    );
    println!(
        "multi_hop_reasoning:              {:.4}",
        report.multi_hop_reasoning_score
    );
    println!(
        "auditable_trace:                  {:.4}",
        report.auditable_trace_score
    );
    println!(
        "trace_quality:                    {:.4} (coverage={:.4} completeness={:.4} order={:.4} contradiction={:.4})",
        report.trace_quality.score,
        report.trace_quality.evidence_coverage,
        report.trace_quality.trace_completeness,
        report.trace_quality.causal_order,
        report.trace_quality.contradiction_handling
    );
    println!(
        "failed_cases:                     {}",
        report.failed_cases.len()
    );
    println!(
        "error_analysis:                   success={} failed={} retrieval_fail={} reasoning_fail={}",
        report.error_analysis.success_cases,
        report.error_analysis.failed_cases,
        report.error_analysis.retrieval_failure_count,
        report.error_analysis.reasoning_failure_count
    );
    println!(
        "memory_influence:                 full={:.4} best_rag={:.4} gain={:+.4}",
        report
            .memory_influence_attribution
            .mean_full_influence_score,
        report
            .memory_influence_attribution
            .mean_best_rag_influence_score,
        report
            .memory_influence_attribution
            .full_over_best_rag_influence_gain
    );
    println!("pass:                             {}", report.pass);
    println!("-----------------------------------------");
    println!(
        "ablation: rag={:.4} edge={:.4} activation={:.4} governance={:.4} full={:.4}",
        report.ablation.rag_only_score,
        report.ablation.rag_plus_edge_score,
        report.ablation.rag_plus_activation_score,
        report.ablation.rag_plus_governance_score,
        report.ablation.full_synapse_score
    );

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote cognitive memory benchmark report to {}",
        cli.json.display()
    );
    Ok(())
}
