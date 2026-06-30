//! Cross-encoder rerankers for the recall pipeline.
//!
//! `Reranker` is a trait so we can swap in BGE / Jina / OpenAI / mock impls
//! without touching `RecallEngine`. The recall flow is:
//!   1. RRF fuses FTS + entity + vector hits (rank-only).
//!   2. (optional) Reranker re-scores the top `rerank_pool` hits with a
//!      cross-encoder and reorders them; the rest of the list is dropped.
//!   3. RecallEngine applies importance/confidence/decay and returns top-k.
//!
//! Phase 2 step 5: ship `FastEmbedReranker` (BGE-Reranker-Base, ~300MB).

use crate::error::{Error, Result};
use crate::recall::RecallHit;
use fastembed::{RerankInitOptions, RerankerModel, TextRerank};

/// Anything that can score (query, document) pairs and reorder a candidate
/// list. Implementations may write `rerank_score` into each hit and resort.
pub trait Reranker {
    /// Rerank `hits` in place against `query`. Implementations should also
    /// stamp `hit.rerank_score = Some(score)` so callers can see what the
    /// model thought of each item.
    fn rerank(&mut self, query: &str, hits: &mut Vec<RecallHit>) -> Result<()>;
}

/// Default in-process reranker backed by `fastembed`. Lazy-loaded; first
/// call downloads the ONNX model into `FASTEMBED_CACHE_DIR`.
pub struct FastEmbedReranker {
    inner: TextRerank,
    model_name: String,
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
        let opts = RerankInitOptions::new(model).with_show_download_progress(true);
        let inner = TextRerank::try_new(opts)
            .map_err(|e| Error::Embedder(format!("init reranker {name}: {e}")))?;
        Ok(Self {
            inner,
            model_name: name.to_string(),
        })
    }

    pub fn model_name(&self) -> &str {
        &self.model_name
    }
}

impl Reranker for FastEmbedReranker {
    fn rerank(&mut self, query: &str, hits: &mut Vec<RecallHit>) -> Result<()> {
        if hits.is_empty() {
            return Ok(());
        }
        let docs: Vec<&str> = hits.iter().map(|h| h.memory.content.as_str()).collect();
        let results = self
            .inner
            .rerank(query, &docs, false, None)
            .map_err(|e| Error::Embedder(format!("rerank: {e}")))?;
        let mut scores = vec![f32::NEG_INFINITY; hits.len()];
        for r in &results {
            if let Some(slot) = scores.get_mut(r.index) {
                *slot = r.score;
            }
        }
        for (h, s) in hits.iter_mut().zip(scores.iter()) {
            h.rerank_score = Some(*s);
        }
        hits.sort_by(|a, b| {
            let sa = a.rerank_score.unwrap_or(f32::NEG_INFINITY);
            let sb = b.rerank_score.unwrap_or(f32::NEG_INFINITY);
            sb.partial_cmp(&sa).unwrap_or(std::cmp::Ordering::Equal)
        });
        Ok(())
    }
}
