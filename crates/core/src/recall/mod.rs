//! Recall layer: turns a `RecallQuery` into a ranked list of memories by
//! fusing 1) FTS keyword hits, 2) entity-graph hits, and 3) optional dense
//! vector hits via Reciprocal Rank Fusion.
//!
//! Store is intentionally kept ignorant of queries; this module owns query
//! understanding, optional embedding, fusion, and recency/decay weighting.

mod rrf;

use crate::error::Result;
use crate::model::{Memory, MemoryKind, RecallQuery};
use crate::rerank::Reranker;
use crate::store::Store;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub use rrf::{rrf_fuse, RrfInput, DEFAULT_RRF_K};

/// Default number of candidates a reranker sees before truncating to top-k.
pub const DEFAULT_RERANK_POOL: usize = 50;

/// Anything that can turn a natural-language query into a dense vector.
///
/// `Embedder` from `crate::embed` implements this; tests can supply a stub.
pub trait QueryEmbedder {
    fn embed_query(&mut self, query: &str) -> Result<Vec<f32>>;
}

impl QueryEmbedder for crate::embed::Embedder {
    fn embed_query(&mut self, query: &str) -> Result<Vec<f32>> {
        crate::embed::Embedder::embed_query(self, query)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallHit {
    pub memory: Memory,
    /// Final score after all modifiers (RRF or rerank x importance x decay).
    pub score: f32,
    #[serde(default)]
    pub rrf_score: f32,
    /// Set when a `Reranker` ran over this hit.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rerank_score: Option<f32>,
    #[serde(default)]
    pub entity_hits: u32,
    #[serde(default)]
    pub from_fts: bool,
    #[serde(default)]
    pub from_entity: bool,
    #[serde(default)]
    pub from_vector: bool,
}

/// Hybrid retriever. Owns no state of its own; borrows a Store and an
/// optional embedder/reranker for the duration of a single recall.
pub struct RecallEngine<'a> {
    store: &'a mut Store,
    embedder: Option<&'a mut dyn QueryEmbedder>,
    reranker: Option<&'a mut dyn Reranker>,
    rerank_pool: usize,
}

impl<'a> RecallEngine<'a> {
    pub fn new(store: &'a mut Store) -> Self {
        Self {
            store,
            embedder: None,
            reranker: None,
            rerank_pool: DEFAULT_RERANK_POOL,
        }
    }

    pub fn with_embedder(mut self, embedder: &'a mut dyn QueryEmbedder) -> Self {
        self.embedder = Some(embedder);
        self
    }

    /// Attach a cross-encoder reranker. The engine will fetch up to
    /// `rerank_pool` candidates after RRF and let the reranker reorder them
    /// before truncating to top-k.
    pub fn with_reranker(mut self, reranker: &'a mut dyn Reranker, rerank_pool: usize) -> Self {
        self.reranker = Some(reranker);
        self.rerank_pool = rerank_pool.max(1);
        self
    }

    pub fn recall(&mut self, q: &RecallQuery) -> Result<Vec<RecallHit>> {
        let k = q.k.unwrap_or(8).max(1);
        // If a reranker is attached we want to give it a bigger candidate
        // pool than the caller-requested top-k.
        let pool = if self.reranker.is_some() {
            self.rerank_pool.max(k)
        } else {
            (k * 4).max(20)
        };
        let scope_str = q.scope_filter.as_ref().map(|s| s.to_string());
        let kind_str = q.kind_filter.as_ref().map(|k| k.to_string());

        // 1. FTS branch
        let fts_rows =
            self.store
                .search_fts(&q.query, scope_str.as_deref(), kind_str.as_deref(), pool)?;

        // 2. Entity branch
        let entity_rows =
            self.store
                .search_entity(&q.query, scope_str.as_deref(), kind_str.as_deref(), pool)?;

        // 3. Vector branch (optional; only if an embedder is wired in)
        let vector_rows: Vec<(String, f64)> = match self.embedder.as_mut() {
            Some(emb) => {
                let qv = emb.embed_query(&q.query)?;
                self.store.search_vector(&qv, pool)?
            }
            None => Vec::new(),
        };

        // Memory cache so we can attach metadata to vector-only hits.
        let mut mem_cache: HashMap<String, Memory> = HashMap::new();
        for (m, _) in &fts_rows {
            mem_cache.insert(m.id.clone(), m.clone());
        }
        for (m, _) in &entity_rows {
            mem_cache.entry(m.id.clone()).or_insert_with(|| m.clone());
        }
        for (id, _) in &vector_rows {
            if !mem_cache.contains_key(id) {
                if let Some(m) = self.store.get(id)? {
                    if m.valid_to.is_none() {
                        mem_cache.insert(id.clone(), m);
                    }
                }
            }
        }

        // Build RRF inputs: each branch contributes (id, rank).
        let fts_ids: Vec<String> = fts_rows.iter().map(|(m, _)| m.id.clone()).collect();
        let entity_ids: Vec<String> = entity_rows.iter().map(|(m, _)| m.id.clone()).collect();
        let vec_ids: Vec<String> = vector_rows
            .iter()
            .filter(|(id, _)| mem_cache.contains_key(id))
            .map(|(id, _)| id.clone())
            .collect();

        let entity_hits_by_id: HashMap<String, u32> = entity_rows
            .iter()
            .map(|(m, hits)| (m.id.clone(), *hits))
            .collect();

        let fused = rrf_fuse(
            &[
                RrfInput {
                    name: "fts",
                    ids: &fts_ids,
                },
                RrfInput {
                    name: "entity",
                    ids: &entity_ids,
                },
                RrfInput {
                    name: "vector",
                    ids: &vec_ids,
                },
            ],
            DEFAULT_RRF_K,
        );

        // Build hits in RRF order; `score` starts as RRF and is overwritten
        // below by rerank or modifier passes.
        let mut hits: Vec<RecallHit> = fused
            .into_iter()
            .filter_map(|(id, rrf_score, sources)| {
                let mem = mem_cache.remove(&id)?;
                let entity_hits = entity_hits_by_id.get(&mem.id).copied().unwrap_or(0);
                Some(RecallHit {
                    memory: mem,
                    score: rrf_score as f32,
                    rrf_score: rrf_score as f32,
                    rerank_score: None,
                    entity_hits,
                    from_fts: sources.contains(&"fts"),
                    from_entity: sources.contains(&"entity"),
                    from_vector: sources.contains(&"vector"),
                })
            })
            .collect();

        // Truncate to rerank pool before invoking the cross-encoder.
        if self.reranker.is_some() {
            hits.truncate(self.rerank_pool);
        }

        // Optional reranker pass: rewrites `rerank_score` and resorts.
        if let Some(rr) = self.reranker.as_mut() {
            rr.rerank(&q.query, &mut hits)?;
        }

        // Apply importance/confidence/decay as multiplicative modifiers on top
        // of whichever ranking signal we have (rerank_score if present, else RRF).
        let now = Utc::now().timestamp();
        for h in hits.iter_mut() {
            let base = h.rerank_score.map(sigmoid).unwrap_or(h.rrf_score);
            let age_days = ((now - h.memory.valid_from).max(0) as f32) / 86_400.0;
            let decay = (-decay_lambda(h.memory.kind) * age_days).exp();
            h.score = base * h.memory.importance.max(0.05) * h.memory.confidence.max(0.05) * decay;
        }

        hits.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        hits.truncate(k);

        if !hits.is_empty() {
            let ids: Vec<&str> = hits.iter().map(|h| h.memory.id.as_str()).collect();
            self.store.record_access(&ids, now)?;
        }
        Ok(hits)
    }
}

/// Squash a cross-encoder logit into (0,1) so it composes with the
/// importance/confidence/decay modifiers the same way RRF scores do.
fn sigmoid(x: f32) -> f32 {
    1.0 / (1.0 + (-x).exp())
}

pub(crate) fn decay_lambda(kind: MemoryKind) -> f32 {
    // Half-lives, in days:
    //   STATE      ~1d   -> lambda = ln(2)/1
    //   FAILURE   ~30d
    //   FACT      ~180d
    //   PLAYBOOK  ~180d
    //   PREFERENCE ~365d
    match kind {
        MemoryKind::State => 0.693,
        MemoryKind::Failure => 0.0231,
        MemoryKind::Fact => 0.00385,
        MemoryKind::Playbook => 0.00385,
        MemoryKind::Preference => 0.0019,
    }
}
