//! Recall layer: turns a `RecallQuery` into a ranked list of memories by
//! fusing 1) FTS keyword hits, 2) entity-graph hits, and 3) optional dense
//! vector hits via Reciprocal Rank Fusion.
//!
//! Store is intentionally kept ignorant of queries; this module owns query
//! understanding, optional embedding, fusion, and recency/decay weighting.

mod rrf;

use crate::error::Result;
use crate::model::{Memory, MemoryKind, RecallQuery};
use crate::store::Store;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub use rrf::{rrf_fuse, RrfInput, DEFAULT_RRF_K};

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
    pub score: f32,
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
/// optional embedder for the duration of a single recall.
pub struct RecallEngine<'a> {
    store: &'a mut Store,
    embedder: Option<&'a mut dyn QueryEmbedder>,
}

impl<'a> RecallEngine<'a> {
    pub fn new(store: &'a mut Store) -> Self {
        Self {
            store,
            embedder: None,
        }
    }

    pub fn with_embedder(mut self, embedder: &'a mut dyn QueryEmbedder) -> Self {
        self.embedder = Some(embedder);
        self
    }

    pub fn recall(&mut self, q: &RecallQuery) -> Result<Vec<RecallHit>> {
        let k = q.k.unwrap_or(8).max(1);
        let limit_pool = (k * 4).max(20);
        let scope_str = q.scope_filter.as_ref().map(|s| s.to_string());
        let kind_str = q.kind_filter.as_ref().map(|k| k.to_string());

        // 1. FTS branch
        let fts_rows = self.store.search_fts(
            &q.query,
            scope_str.as_deref(),
            kind_str.as_deref(),
            limit_pool,
        )?;

        // 2. Entity branch
        let entity_rows = self.store.search_entity(
            &q.query,
            scope_str.as_deref(),
            kind_str.as_deref(),
            limit_pool,
        )?;

        // 3. Vector branch (optional; only if an embedder is wired in)
        let vector_rows: Vec<(String, f64)> = match self.embedder.as_mut() {
            Some(emb) => {
                let qv = emb.embed_query(&q.query)?;
                self.store.search_vector(&qv, limit_pool)?
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
        // Filter vector rows to ids we actually have an active memory for.
        let vec_ids: Vec<String> = vector_rows
            .iter()
            .filter(|(id, _)| mem_cache.contains_key(id))
            .map(|(id, _)| id.clone())
            .collect();

        // Entity hit counts, indexed by memory id.
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

        // Apply importance/confidence/decay as multiplicative modifiers,
        // then take top-k.
        let now = Utc::now().timestamp();
        let mut hits: Vec<RecallHit> = fused
            .into_iter()
            .filter_map(|(id, rrf_score, sources)| {
                let mem = mem_cache.remove(&id)?;
                let age_days = ((now - mem.valid_from).max(0) as f32) / 86_400.0;
                let decay = (-decay_lambda(mem.kind) * age_days).exp();
                let score = (rrf_score as f32)
                    * mem.importance.max(0.05)
                    * mem.confidence.max(0.05)
                    * decay;
                let entity_hits = entity_hits_by_id.get(&mem.id).copied().unwrap_or(0);
                Some(RecallHit {
                    memory: mem,
                    score,
                    entity_hits,
                    from_fts: sources.contains(&"fts"),
                    from_entity: sources.contains(&"entity"),
                    from_vector: sources.contains(&"vector"),
                })
            })
            .collect();

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
