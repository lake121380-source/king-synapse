use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use synapse_core::RecallProfile;

#[derive(Debug, Deserialize)]
pub struct Dataset {
    pub memories: Vec<MemorySpec>,
    #[serde(default)]
    pub queries: Vec<QuerySpec>,
}

#[derive(Debug, Deserialize)]
pub struct MemorySpec {
    pub key: String,
    pub kind: String,
    pub scope: String,
    pub content: String,
    #[serde(default)]
    pub importance: Option<f32>,
    #[serde(default)]
    pub confidence: Option<f32>,
}

#[derive(Debug, Deserialize)]
pub struct QuerySpec {
    pub query: String,
    pub relevant: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct QueryResult {
    pub query: String,
    pub relevant: Vec<String>,
    pub returned: Vec<String>,
    pub recall_at_5: f64,
    pub recall_at_10: f64,
    pub rr: f64,
    pub ndcg_at_10: f64,
    pub latency_ms: f64,
    pub profile: RecallProfile,
}

#[derive(Debug, Serialize)]
pub struct Report {
    pub tag: String,
    pub dataset: String,
    pub vectors_enabled: bool,
    pub rerank_enabled: bool,
    pub rerank_pool: usize,
    pub k: usize,
    pub n_memories: usize,
    pub n_queries: usize,
    pub recall_at_5: f64,
    pub recall_at_10: f64,
    pub mrr_at_10: f64,
    pub ndcg_at_10: f64,
    pub p50_latency_ms: f64,
    pub p95_latency_ms: f64,
    pub total_ms: f64,
    pub timing: TimingReport,
    pub per_query: Vec<QueryResult>,
}

#[derive(Debug, Default, Serialize)]
pub struct TimingReport {
    pub dataset_load_ms: f64,
    pub store_write_ms: f64,
    pub embedder_load_ms: Option<f64>,
    pub corpus_embedding_ms: Option<f64>,
    pub embedding_write_ms: Option<f64>,
    pub reranker_load_ms: Option<f64>,
    pub query_wall_ms: f64,
    pub recall_profile_totals: RecallProfile,
    pub recall_profile_mean_ms: RecallProfileMeanMs,
}

#[derive(Debug, Default, Serialize)]
pub struct RecallProfileMeanMs {
    pub total_ms: f64,
    pub fts_ms: f64,
    pub entity_ms: f64,
    pub query_embedding_ms: f64,
    pub vector_search_ms: f64,
    pub memory_hydration_ms: f64,
    pub rrf_fusion_ms: f64,
    pub hit_build_ms: f64,
    pub reranker_ms: f64,
    pub booster_ms: f64,
    pub final_score_ms: f64,
    pub record_access_ms: f64,
}

pub struct BenchOptions {
    pub dataset_path: PathBuf,
    pub k: usize,
    pub vectors: bool,
    pub rerank: bool,
    pub rerank_pool: usize,
    pub tag: String,
}
