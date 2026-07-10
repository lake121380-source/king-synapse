use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_eval::Phase6MemoryIntelligenceBenchmarkEvaluator;

#[derive(Debug, Parser)]
#[command(about = "Run the Phase 6.0 Memory Intelligence Benchmark quality gate")]
struct Cli {
    #[arg(
        long,
        default_value = "crates/eval/reports/phase6_memory_intelligence_benchmark.json"
    )]
    json: PathBuf,
    #[arg(long, default_value = "phase6-memory-intelligence-benchmark")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = Phase6MemoryIntelligenceBenchmarkEvaluator::evaluate(cli.tag)?;

    println!("Phase: {}", report.phase);
    println!(
        "Dataset: scenarios={} memories={} categories={} splits={:?}",
        report.dataset.scenarios,
        report.dataset.memories,
        report.dataset.categories,
        report.dataset.split_counts
    );
    println!(
        "Retrieval: R@1={:.4} R@3={:.4} R@5={:.4} MRR@5={:.4} NDCG@5={:.4}",
        report.retrieval.recall_at_1,
        report.retrieval.recall_at_3,
        report.retrieval.recall_at_5,
        report.retrieval.mrr_at_5,
        report.retrieval.ndcg_at_5,
    );
    println!(
        "Integrity: expected-retrieved={:.4} deterministic={:.4} label-alignment={:.4} entity-candidates={}",
        report.retrieval.expected_candidate_retrieval_rate,
        report.retrieval.determinism,
        report.retrieval.label_intent_alignment,
        report.retrieval.entity_candidates,
    );
    println!(
        "Algorithm comparison performed: {}",
        report.guards.algorithm_comparison_performed
    );
    println!(
        "Runtime authorized: {}",
        report.guards.runtime_authorization
    );
    println!("Status: {}", report.status);

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!("wrote Phase 6.0 report to {}", cli.json.display());
    Ok(())
}
