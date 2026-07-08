use anyhow::{Context, Result};
use clap::{Parser, ValueEnum};
use std::path::PathBuf;
use synapse_core::{RrfBranchWeights, SemanticEdgeMode};
use synapse_eval::{default_dataset_path, BenchOptions, GovernanceEvaluator, SemanticJudgeKind};

#[derive(Parser)]
#[command(
    name = "kr-governance-eval",
    about = "Synapse semantic edge governance validation"
)]
struct Cli {
    /// Path to a dataset TOML file.
    #[arg(long)]
    dataset: Option<PathBuf>,
    /// Top-K used by the recall engine for each query.
    #[arg(long, default_value = "10")]
    k: usize,
    /// Enable dense vector retrieval during trace collection.
    #[arg(long)]
    vectors: bool,
    /// Enable cross-encoder reranking during trace collection.
    #[arg(long)]
    rerank: bool,
    /// Candidate pool size passed to the reranker.
    #[arg(long, default_value = "50")]
    rerank_pool: usize,
    /// Reciprocal Rank Fusion k constant.
    #[arg(long, default_value = "60.0")]
    rrf_k: f64,
    #[arg(long, default_value = "1.0")]
    fts_weight: f64,
    #[arg(long, default_value = "1.0")]
    entity_weight: f64,
    #[arg(long, default_value = "1.0")]
    vector_weight: f64,
    /// Write the independent GovernanceEvaluationReport JSON to this path.
    #[arg(long)]
    json: PathBuf,
    /// Tag to embed in the report.
    #[arg(long, default_value = "governance-eval")]
    tag: String,
    /// Semantic judge mode used to collect governance evidence.
    #[arg(long, value_enum, default_value = "classify")]
    semantic_edge_mode: SemanticEdgeModeArg,
    /// Semantic judge implementation.
    #[arg(long, value_enum, default_value = "heuristic")]
    semantic_judge: SemanticJudgeKindArg,
    /// Disable persistent semantic judge cache for model-backed judges.
    #[arg(long)]
    no_semantic_judge_cache: bool,
    /// Override persistent semantic judge cache SQLite path.
    #[arg(long)]
    semantic_judge_cache_path: Option<PathBuf>,
}

#[derive(Clone, Debug, ValueEnum)]
#[clap(rename_all = "kebab-case")]
enum SemanticEdgeModeArg {
    Filter,
    Classify,
}

#[derive(Clone, Debug, ValueEnum)]
#[clap(rename_all = "lower")]
enum SemanticJudgeKindArg {
    Heuristic,
    DeepSeek,
}

impl From<SemanticEdgeModeArg> for SemanticEdgeMode {
    fn from(value: SemanticEdgeModeArg) -> Self {
        match value {
            SemanticEdgeModeArg::Filter => SemanticEdgeMode::Filter,
            SemanticEdgeModeArg::Classify => SemanticEdgeMode::Classify,
        }
    }
}

impl From<SemanticJudgeKindArg> for SemanticJudgeKind {
    fn from(value: SemanticJudgeKindArg) -> Self {
        match value {
            SemanticJudgeKindArg::Heuristic => SemanticJudgeKind::Heuristic,
            SemanticJudgeKindArg::DeepSeek => SemanticJudgeKind::DeepSeek,
        }
    }
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
        graph_activation: true,
        hypothesis_generation: true,
        hypothesis_graduation: true,
        semantic_edge_mode: cli.semantic_edge_mode.into(),
        semantic_judge: cli.semantic_judge.into(),
        semantic_judge_cache_path: if cli.no_semantic_judge_cache {
            None
        } else {
            Some(
                cli.semantic_judge_cache_path
                    .unwrap_or_else(|| synapse_core::default_semantic_judge_cache_path()),
            )
        },
    };

    let report = GovernanceEvaluator::evaluate(opts)?;
    println!("=== Synapse governance evaluation ===");
    println!("tag:               {}", report.tag);
    println!("dataset:           {}", report.dataset);
    println!("detection_score:   {:.4}", report.detection_score);
    println!("intervention_gain: {:.4}", report.intervention_gain);
    println!("regression_rate:   {:.4}", report.regression_rate);
    println!("stability_score:   {:.4}", report.stability_score);
    println!(
        "suspect detection: tp={} fp={} fn={} precision={:.3} recall={:.3}",
        report.suspect_detection.true_positive,
        report.suspect_detection.false_positive,
        report.suspect_detection.false_negative,
        report.suspect_detection.precision,
        report.suspect_detection.recall
    );
    println!(
        "intervention:      changed={} improved={} harmed={} safe={}",
        report.intervention_safety.changed_queries,
        report.intervention_safety.improved_queries,
        report.intervention_safety.harmed_queries,
        report.intervention_safety.safety_passed
    );

    if let Some(parent) = cli.json.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&cli.json, serde_json::to_string_pretty(&report)?)
        .with_context(|| format!("writing JSON to {}", cli.json.display()))?;
    eprintln!(
        "wrote governance evaluation report to {}",
        cli.json.display()
    );
    Ok(())
}
