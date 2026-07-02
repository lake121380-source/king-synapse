//! Cross-encoder rerankers for the recall pipeline.
//!
//! `Reranker` is a trait so we can swap in BGE / Jina / OpenAI / mock impls
//! without touching `RecallEngine`.
//!
//! Step 5.5 contract: rerankers do **not** see `RecallHit`. They take the
//! query and a slice of document strings and return one score per slot.
//! The engine writes those scores into hits and resorts. This isolates
//! the trait from `RecallHit`'s frozen field set (ADR-003).

use crate::accelerator::execution_providers_from_env;
use crate::error::{Error, Result};
use fastembed::{RerankInitOptions, RerankerModel, TextRerank};

const RERANK_BATCH_SIZE_ENV: &str = "KING_SYNAPSE_RERANK_BATCH_SIZE";
const RERANK_MAX_LENGTH_ENV: &str = "KING_SYNAPSE_RERANK_MAX_LENGTH";

/// Anything that can score (query, document) pairs.
pub trait Reranker {
    /// Score every document against `query`. Output **must** be the same
    /// length and order as `docs`; entries the model can't score should
    /// be filled with `f32::NEG_INFINITY` so they sort to the bottom.
    fn rerank(&mut self, query: &str, docs: &[&str]) -> Result<Vec<f32>>;
}

/// Default in-process reranker backed by `fastembed`. Lazy-loaded; first
/// call downloads the ONNX model into `FASTEMBED_CACHE_DIR`.
pub struct FastEmbedReranker {
    inner: TextRerank,
    model_name: String,
    batch_size: Option<usize>,
}

impl FastEmbedReranker {
    /// Load the bundled BGE-Reranker-Base model. ~300MB on first run.
    pub fn new() -> Result<Self> {
        Self::with_model(RerankerModel::BGERerankerBase, "bge-reranker-base")
    }

    /// Larger multilingual variant. ~1.1GB on first run; better on CJK.
    pub fn new_bge_v2_m3() -> Result<Self> {
        Self::with_model(RerankerModel::BGERerankerV2M3, "bge-reranker-v2-m3")
    }

    fn with_model(model: RerankerModel, name: &str) -> Result<Self> {
        let mut opts = RerankInitOptions::new(model).with_show_download_progress(true);
        if let Some(max_length) = rerank_max_length_from_env()? {
            opts = opts.with_max_length(max_length);
        }
        let execution_providers = execution_providers_from_env()?;
        if !execution_providers.is_empty() {
            opts = opts.with_execution_providers(execution_providers);
        }
        let inner = TextRerank::try_new(opts)
            .map_err(|e| Error::Embedder(format!("init reranker {name}: {e}")))?;
        Ok(Self {
            inner,
            model_name: name.to_string(),
            batch_size: rerank_batch_size_from_env()?,
        })
    }

    pub fn model_name(&self) -> &str {
        &self.model_name
    }
}

impl Reranker for FastEmbedReranker {
    fn rerank(&mut self, query: &str, docs: &[&str]) -> Result<Vec<f32>> {
        if docs.is_empty() {
            return Ok(Vec::new());
        }
        let results = self
            .inner
            .rerank(query, docs, false, self.batch_size)
            .map_err(|e| Error::Embedder(format!("rerank: {e}")))?;
        let mut scores = vec![f32::NEG_INFINITY; docs.len()];
        for r in &results {
            if let Some(slot) = scores.get_mut(r.index) {
                *slot = r.score;
            }
        }
        Ok(scores)
    }
}

fn rerank_batch_size_from_env() -> Result<Option<usize>> {
    let raw = std::env::var(RERANK_BATCH_SIZE_ENV).unwrap_or_default();
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }
    let batch_size = trimmed.parse::<usize>().map_err(|_| {
        Error::Invalid(format!(
            "{RERANK_BATCH_SIZE_ENV} must be a positive integer"
        ))
    })?;
    if batch_size == 0 {
        return Err(Error::Invalid(format!(
            "{RERANK_BATCH_SIZE_ENV} must be greater than 0"
        )));
    }
    Ok(Some(batch_size))
}

fn rerank_max_length_from_env() -> Result<Option<usize>> {
    let raw = std::env::var(RERANK_MAX_LENGTH_ENV).unwrap_or_default();
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }
    let max_length = trimmed.parse::<usize>().map_err(|_| {
        Error::Invalid(format!(
            "{RERANK_MAX_LENGTH_ENV} must be a positive integer token length"
        ))
    })?;
    if max_length == 0 {
        return Err(Error::Invalid(format!(
            "{RERANK_MAX_LENGTH_ENV} must be greater than 0"
        )));
    }
    Ok(Some(max_length))
}
