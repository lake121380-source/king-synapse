use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
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
    /// Write the full report as JSON to this path (in addition to the table).
    #[arg(long)]
    json: Option<PathBuf>,
    /// Tag to embed in the JSON report (e.g. "baseline-rrf", "with-reranker").
    #[arg(long, default_value = "unnamed")]
    tag: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let opts = BenchOptions {
        dataset_path: cli.dataset.unwrap_or_else(default_dataset_path),
        k: cli.k,
        vectors: cli.vectors,
        rerank: cli.rerank,
        rerank_pool: cli.rerank_pool,
        tag: cli.tag,
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
