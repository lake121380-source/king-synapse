//! Core `RecallEngine` implementation: the function that turns one
//! `RecallQuery` into a ranked `Vec<RecallHit>` by walking the pipeline
//! defined in `docs/RECALL_PIPELINE.md`.

use crate::error::{Error, Result};
use crate::model::{Memory, MemoryKind, RecallQuery};
use crate::recall::booster::{BoosterContext, RecallBooster};
use crate::recall::hit::{RecallHit, RecallHitBuilder, RecallSource};
use crate::recall::rrf::{rrf_fuse, RrfInput, DEFAULT_RRF_K};
use crate::recall::{QueryEmbedder, DEFAULT_RERANK_POOL};
use crate::rerank::Reranker;
use crate::store::Store;
use chrono::Utc;
use std::collections::HashMap;

pub struct RecallEngine<'a> {
    pub(crate) store: &'a mut Store,
    pub(crate) embedder: Option<&'a mut dyn QueryEmbedder>,
    pub(crate) reranker: Option<&'a mut dyn Reranker>,
    pub(crate) boosters: Vec<&'a dyn RecallBooster>,
    pub(crate) rerank_pool: usize,
}

impl<'a> RecallEngine<'a> {
    pub fn new(store: &'a mut Store) -> Self {
        Self {
            store,
            embedder: None,
            reranker: None,
            boosters: Vec::new(),
            rerank_pool: DEFAULT_RERANK_POOL,
        }
    }

    pub fn with_embedder(mut self, embedder: &'a mut dyn QueryEmbedder) -> Self {
        self.embedder = Some(embedder);
        self
    }

    pub fn with_reranker(mut self, reranker: &'a mut dyn Reranker, rerank_pool: usize) -> Self {
        self.reranker = Some(reranker);
        self.rerank_pool = rerank_pool.max(1);
        self
    }

    pub fn with_booster(mut self, booster: &'a dyn RecallBooster) -> Self {
        self.boosters.push(booster);
        self
    }

    pub fn recall(&mut self, q: &RecallQuery) -> Result<Vec<RecallHit>> {
        let k = q.k.unwrap_or(8).max(1);
        let pool = if self.reranker.is_some() {
            self.rerank_pool.max(k)
        } else {
            (k * 4).max(20)
        };
        let scope_str = q.scope_filter.as_ref().map(|s| s.to_string());
        let kind_str = q.kind_filter.as_ref().map(|k| k.to_string());

        let fts_rows =
            self.store
                .search_fts(&q.query, scope_str.as_deref(), kind_str.as_deref(), pool)?;
        let entity_rows =
            self.store
                .search_entity(&q.query, scope_str.as_deref(), kind_str.as_deref(), pool)?;
        let vector_rows: Vec<(String, f64)> = match self.embedder.as_mut() {
            Some(emb) => {
                let qv = emb.embed_query(&q.query)?;
                self.store.search_vector(&qv, pool)?
            }
            None => Vec::new(),
        };

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

        let fts_ranks = rank_map(fts_rows.iter().map(|(m, _)| m.id.clone()));
        let entity_ranks = rank_map(entity_rows.iter().map(|(m, _)| m.id.clone()));
        let vector_ranks = rank_map(
            vector_rows
                .iter()
                .filter(|(id, _)| mem_cache.contains_key(id))
                .map(|(id, _)| id.clone()),
        );

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

        let mut hits: Vec<RecallHit> = fused
            .into_iter()
            .filter_map(|(id, rrf_score, sources)| {
                let mem = mem_cache.remove(&id)?;
                let mem_id = mem.id.clone();
                let entity_hits = entity_hits_by_id.get(&mem_id).copied().unwrap_or(0);
                let mut srcs = Vec::with_capacity(sources.len());
                if sources.contains(&"fts") {
                    srcs.push(RecallSource::Fts);
                }
                if sources.contains(&"entity") {
                    srcs.push(RecallSource::Entity);
                }
                if sources.contains(&"vector") {
                    srcs.push(RecallSource::Vector);
                }
                Some(
                    RecallHitBuilder::new(mem)
                        .rrf_score(rrf_score as f32)
                        .fts_rank(fts_ranks.get(&mem_id).copied())
                        .entity_rank(entity_ranks.get(&mem_id).copied())
                        .vector_rank(vector_ranks.get(&mem_id).copied())
                        .entity_hits(entity_hits)
                        .sources(srcs)
                        .build(),
                )
            })
            .collect();

        if self.reranker.is_some() {
            hits.truncate(self.rerank_pool);
        }

        if let Some(rr) = self.reranker.as_mut() {
            let docs: Vec<&str> = hits.iter().map(|h| h.memory.content.as_str()).collect();
            let scores = rr.rerank(&q.query, &docs)?;
            if scores.len() != hits.len() {
                return Err(Error::Invalid(format!(
                    "reranker returned {} scores for {} docs",
                    scores.len(),
                    hits.len()
                )));
            }
            for (h, s) in hits.iter_mut().zip(scores.iter()) {
                h.rerank_score = Some(*s);
            }
            hits.sort_by(|a, b| {
                let sa = a.rerank_score.unwrap_or(f32::NEG_INFINITY);
                let sb = b.rerank_score.unwrap_or(f32::NEG_INFINITY);
                sb.partial_cmp(&sa).unwrap_or(std::cmp::Ordering::Equal)
            });
        }

        if !self.boosters.is_empty() {
            let ctx = BoosterContext::new(q, self.store);
            for booster in &self.boosters {
                booster.apply(&ctx, hits.as_mut_slice())?;
            }
        }

        let now = Utc::now().timestamp();
        for h in hits.iter_mut() {
            let base = h.rerank_score.map(sigmoid).unwrap_or(h.rrf_score);
            let age_days = ((now - h.memory.valid_from).max(0) as f32) / 86_400.0;
            let decay = (-decay_lambda(h.memory.kind) * age_days).exp();
            let weighted =
                base * h.memory.importance.max(0.05) * h.memory.confidence.max(0.05) * decay;
            h.score = weighted + h.activation_bonus;
            if h.activation_bonus > 0.0 && !h.sources.contains(&RecallSource::Activation) {
                h.sources.push(RecallSource::Activation);
            }
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

fn rank_map<I: IntoIterator<Item = String>>(ids: I) -> HashMap<String, u32> {
    let mut out = HashMap::new();
    for (i, id) in ids.into_iter().enumerate() {
        out.entry(id).or_insert((i + 1) as u32);
    }
    out
}

fn sigmoid(x: f32) -> f32 {
    1.0 / (1.0 + (-x).exp())
}

pub(crate) fn decay_lambda(kind: MemoryKind) -> f32 {
    match kind {
        MemoryKind::State => 0.693,
        MemoryKind::Failure => 0.0231,
        MemoryKind::Fact => 0.00385,
        MemoryKind::Playbook => 0.00385,
        MemoryKind::Preference => 0.0019,
    }
}
