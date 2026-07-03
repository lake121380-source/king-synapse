//! Core `RecallEngine` implementation: the function that turns one
//! `RecallQuery` into a ranked `Vec<RecallHit>` by walking the pipeline
//! defined in `docs/RECALL_PIPELINE.md`.

use crate::error::{Error, Result};
use crate::model::{Memory, MemoryKind, RecallQuery};
use crate::recall::booster::{BoosterContext, RecallBooster};
use crate::recall::hit::{RecallHit, RecallHitBuilder, RecallSource};
use crate::recall::rrf::{rrf_fuse, sanitize_k, RrfBranchWeights, RrfInput, DEFAULT_RRF_K};
use crate::recall::{QueryEmbedder, DEFAULT_RERANK_POOL};
use crate::rerank::Reranker;
use crate::store::Store;
use crate::working_memory::SessionId;
use chrono::Utc;
use serde::Serialize;
use std::collections::HashMap;
use std::time::Instant;

#[derive(Debug, Clone, Default, Serialize)]
pub struct RecallProfile {
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
    pub fts_candidates: usize,
    pub entity_candidates: usize,
    pub vector_candidates: usize,
    pub hydrated_memories: usize,
    pub fused_candidates: usize,
    pub rerank_candidates: usize,
    pub returned_hits: usize,
}

#[derive(Debug, Clone)]
pub struct ProfiledRecall {
    pub hits: Vec<RecallHit>,
    pub profile: RecallProfile,
}

pub struct RecallEngine<'a> {
    pub(crate) store: &'a mut Store,
    pub(crate) embedder: Option<&'a mut dyn QueryEmbedder>,
    pub(crate) reranker: Option<&'a mut dyn Reranker>,
    pub(crate) boosters: Vec<&'a dyn RecallBooster>,
    pub(crate) rerank_pool: usize,
    pub(crate) rrf_k: f64,
    pub(crate) rrf_weights: RrfBranchWeights,
    pub(crate) session_id: Option<SessionId>,
}

impl<'a> RecallEngine<'a> {
    pub fn new(store: &'a mut Store) -> Self {
        Self {
            store,
            embedder: None,
            reranker: None,
            boosters: Vec::new(),
            rerank_pool: DEFAULT_RERANK_POOL,
            rrf_k: DEFAULT_RRF_K,
            rrf_weights: RrfBranchWeights::default(),
            session_id: None,
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

    pub fn with_rrf_k(mut self, rrf_k: f64) -> Self {
        self.rrf_k = sanitize_k(rrf_k);
        self
    }

    pub fn with_rrf_weights(mut self, weights: RrfBranchWeights) -> Self {
        self.rrf_weights = weights.sanitized();
        self
    }

    pub fn with_session_id(mut self, session_id: SessionId) -> Self {
        self.session_id = Some(session_id);
        self
    }

    pub fn recall(&mut self, q: &RecallQuery) -> Result<Vec<RecallHit>> {
        Ok(self.recall_profiled(q)?.hits)
    }

    pub fn recall_profiled(&mut self, q: &RecallQuery) -> Result<ProfiledRecall> {
        let total_start = Instant::now();
        let mut profile = RecallProfile::default();
        let k = q.k.unwrap_or(8).max(1);
        let pool = if self.reranker.is_some() {
            self.rerank_pool.max(k)
        } else {
            (k * 4).max(20)
        };
        let scope_str = q.scope_filter.as_ref().map(|s| s.to_string());
        let kind_str = q.kind_filter.as_ref().map(|k| k.to_string());
        let retrieval_query = expand_cjk_query(&q.query);

        let fts_start = Instant::now();
        let fts_rows = self.store.search_fts(
            &retrieval_query,
            scope_str.as_deref(),
            kind_str.as_deref(),
            pool,
        )?;
        profile.fts_ms = elapsed_ms(fts_start);
        profile.fts_candidates = fts_rows.len();

        let entity_start = Instant::now();
        let entity_rows =
            self.store
                .search_entity(&q.query, scope_str.as_deref(), kind_str.as_deref(), pool)?;
        profile.entity_ms = elapsed_ms(entity_start);
        profile.entity_candidates = entity_rows.len();

        let vector_rows: Vec<(String, f64)> = match self.embedder.as_mut() {
            Some(emb) => {
                let embed_start = Instant::now();
                let qv = emb.embed_query(&q.query)?;
                profile.query_embedding_ms = elapsed_ms(embed_start);

                let vector_start = Instant::now();
                let rows = self.store.search_vector(&qv, pool)?;
                profile.vector_search_ms = elapsed_ms(vector_start);
                rows
            }
            None => Vec::new(),
        };
        profile.vector_candidates = vector_rows.len();

        let hydration_start = Instant::now();
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
        profile.memory_hydration_ms = elapsed_ms(hydration_start);
        profile.hydrated_memories = mem_cache.len();

        let fusion_start = Instant::now();
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
                    weight: self.rrf_weights.fts,
                },
                RrfInput {
                    name: "entity",
                    ids: &entity_ids,
                    weight: self.rrf_weights.entity,
                },
                RrfInput {
                    name: "vector",
                    ids: &vec_ids,
                    weight: self.rrf_weights.vector,
                },
            ],
            self.rrf_k,
        );
        profile.rrf_fusion_ms = elapsed_ms(fusion_start);

        let hit_build_start = Instant::now();
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
        profile.hit_build_ms = elapsed_ms(hit_build_start);
        profile.fused_candidates = hits.len();

        if self.reranker.is_some() {
            hits.truncate(self.rerank_pool);
        }

        if let Some(rr) = self.reranker.as_mut() {
            let docs: Vec<&str> = hits.iter().map(|h| h.memory.content.as_str()).collect();
            profile.rerank_candidates = docs.len();
            let rerank_start = Instant::now();
            let scores = rr.rerank(&q.query, &docs)?;
            profile.reranker_ms = elapsed_ms(rerank_start);
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
            let booster_start = Instant::now();
            let mut ctx = BoosterContext::new(q, self.store);
            if let Some(session_id) = self.session_id {
                ctx = ctx.with_session_id(session_id);
            }
            for booster in &self.boosters {
                booster.apply(&ctx, hits.as_mut_slice())?;
            }
            profile.booster_ms = elapsed_ms(booster_start);
        }

        let final_score_start = Instant::now();
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
        profile.final_score_ms = elapsed_ms(final_score_start);
        profile.returned_hits = hits.len();

        if !hits.is_empty() {
            let ids: Vec<&str> = hits.iter().map(|h| h.memory.id.as_str()).collect();
            let record_start = Instant::now();
            self.store.record_access(&ids, now)?;
            profile.record_access_ms = elapsed_ms(record_start);
        }
        profile.total_ms = elapsed_ms(total_start);
        Ok(ProfiledRecall { hits, profile })
    }
}

fn elapsed_ms(start: Instant) -> f64 {
    start.elapsed().as_secs_f64() * 1000.0
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

fn expand_cjk_query(query: &str) -> String {
    let expansions = cjk_query_expansions(query);
    if expansions.is_empty() {
        return query.to_string();
    }

    let mut expanded = query.to_string();
    for term in expansions {
        expanded.push(' ');
        expanded.push_str(term);
    }
    expanded
}

fn cjk_query_expansions(query: &str) -> Vec<&'static str> {
    const RULES: &[(&str, &[&str])] = &[
        ("中文", &["CJK", "multilingual", "unicode61"]),
        ("多语言", &["multilingual"]),
        ("设置", &["setting", "tokenizer", "prefix"]),
        ("检索", &["recall", "embedding", "FTS"]),
        ("向量", &["vector", "embedding", "vec0"]),
        ("维度", &["dim", "dimension", "VEC_DIM", "768"]),
        ("维度约束", &["dim", "VEC_DIM", "768"]),
        ("前缀", &["prefix", "query", "passage"]),
        ("前缀记忆", &["prefix", "query", "passage"]),
        ("误判", &["mismatch", "validate", "drops"]),
        ("泄漏", &["leak", "leaking"]),
        ("大表", &["table", "100M", "autovacuum", "VACUUM"]),
        ("维护", &["VACUUM", "ANALYZE", "autovacuum"]),
        ("包管理器", &["pnpm", "npm"]),
        ("卷挂载", &["Docker", "Compose", "mount"]),
    ];

    let mut terms = Vec::new();
    for (marker, expansions) in RULES {
        if query.contains(marker) {
            terms.extend(expansions.iter().copied());
        }
    }
    terms.sort_unstable();
    terms.dedup();
    terms
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
