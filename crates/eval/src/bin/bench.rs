use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use synapse_core::RrfBranchWeights;
use synapse_eval::{default_dataset_path, print_table, run, BenchOptions};

#[derive(Parser)]
#[command(name = "kr-eval", about = "King Synapse recall benchmark")]
struct Cli {
    /// Path to a dataset TOML file (defaults to the bundled coding_mem set).
    #[arg(long)]
    dataset: Option<PathBuf>,
    /// Top-K used by the recall engine for each query.
    #[arg(long, default_value = "10")]
    k: usize,
    /// Also run the dense vector branch (loads the embedder + downloads model on first run).
    #[arg(long)]
    vectors: bool,
    /// Attach the cross-encoder reranker (BGE-Reranker-Base, ~300MB on first run).
    #[arg(long)]
    rerank: bool,
    /// Candidate pool size passed to the reranker before truncating to top-k.
    #[arg(long, default_value = "50")]
    rerank_pool: usize,
    /// Reciprocal Rank Fusion k constant. Lower values emphasize the top ranks more.
    #[arg(long, default_value = "60.0")]
    rrf_k: f64,
    /// Weight applied to the FTS branch during RRF.
    #[arg(long, default_value = "1.0")]
    fts_weight: f64,
    /// Weight applied to the entity branch during RRF.
    #[arg(long, default_value = "1.0")]
    entity_weight: f64,
    /// Weight applied to the vector branch during RRF.
    #[arg(long, default_value = "1.0")]
    vector_weight: f64,
    /// Write the full report as JSON to this path (in addition to the table).
    #[arg(long)]
    json: Option<PathBuf>,
    /// Tag to embed in the JSON report (e.g. "baseline-rrf", "with-reranker").
    #[arg(long, default_value = "unnamed")]
    tag: String,
    /// Enable graph activation booster (requires entity-based edges).
    #[arg(long)]
    graph_activation: bool,
    #[arg(long)]
    hypothesis_generation: bool,
    #[arg(long)]
    hypothesis_graduation: bool,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let opts = BenchOptions {
        dataset_path: cli.dataset.unwrap_or_else(default_dataset_path),
        k: cli.k,
        vectors: cli.vectors,
        rerank: cli.rerank,
        rerank_pool: cli.rerank_pool,
        rrf_k: cli.rrf_k,
        rrf_weights: RrfBranchWeights::new(cli.fts_weight, cli.entity_weight, cli.vector_weight),
        tag: cli.tag,
        graph_activation: cli.graph_activation,
        hypothesis_generation: cli.hypothesis_generation,
        hypothesis_graduation: cli.hypothesis_graduation,
    };
    let report = run(opts)?;
    print_table(&report);
    if let Some(out) = cli.json.as_ref() {
        std::fs::write(out, serde_json::to_string_pretty(&report)?)
            .with_context(|| format!("writing JSON to {}", out.display()))?;
        eprintln!("wrote JSON report to {}", out.display());
    }
    Ok(())
}
