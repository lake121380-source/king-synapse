//! `RecallHit`: a single ranked memory plus all the evidence the recall
//! pipeline produced for it. Field set is **frozen** as of Phase 2 step 5.5;
//! see `docs/adr/ADR-003-recall-hit-freeze.md`.
//!
//! Outside this crate the struct is read-only. Construct via
//! `RecallHitBuilder`; mutate `activation_bonus` only via the booster
//! contract (Invariant 3 in `docs/RECALL_PIPELINE.md`).

use crate::model::Memory;
use serde::{Deserialize, Serialize};
use std::fmt;

/// Which retrieval branch (or post-retrieval layer) contributed to a hit.
///
/// Stored as enum so renames are typechecker problems instead of silent
/// string mismatches; CLI renderers map back to short glyphs.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RecallSource {
    Fts,
    Entity,
    Vector,
    /// Reserved for the spreading-activation booster (Phase 2 step 6).
    Activation,
    /// Reserved for the working-memory booster (Phase 3).
    WorkingMemory,
}

impl RecallSource {
    pub fn glyph(self) -> char {
        match self {
            RecallSource::Fts => 'F',
            RecallSource::Entity => 'E',
            RecallSource::Vector => 'V',
            RecallSource::Activation => 'A',
            RecallSource::WorkingMemory => 'W',
        }
    }
}

impl fmt::Display for RecallSource {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            RecallSource::Fts => "fts",
            RecallSource::Entity => "entity",
            RecallSource::Vector => "vector",
            RecallSource::Activation => "activation",
            RecallSource::WorkingMemory => "working_memory",
        };
        f.write_str(s)
    }
}

/// One ranked memory with its full provenance.
///
/// **Field set is frozen.** Adding a field requires an ADR. External
/// crates must construct via `RecallHitBuilder` and read fields via the
/// accessor methods. The struct is `#[non_exhaustive]` so adding fields
/// is not a breaking change internally, but downstream code must treat
/// the field list as a stable contract.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[non_exhaustive]
pub struct RecallHit {
    pub memory: Memory,
    /// Final score after RRF/rerank + decay/importance + activation bonus.
    /// This is the value the engine sorted by.
    pub score: f32,
    /// Raw RRF score before any modifiers.
    pub rrf_score: f32,
    /// Cross-encoder logit when a reranker ran; `None` otherwise.
    pub rerank_score: Option<f32>,
    /// Additive bonus from `RecallBooster`s. Set to `0.0` when no booster ran.
    pub activation_bonus: f32,
    /// 1-indexed rank in the FTS branch, if it returned this id.
    pub fts_rank: Option<u32>,
    /// 1-indexed rank in the entity branch, if it returned this id.
    pub entity_rank: Option<u32>,
    /// 1-indexed rank in the vector branch, if it returned this id.
    pub vector_rank: Option<u32>,
    /// Number of query entities also referenced by this memory.
    pub entity_hits: u32,
    /// Every branch / layer that contributed to this hit.
    pub sources: Vec<RecallSource>,
}

impl RecallHit {
    pub fn from_fts(&self) -> bool {
        self.sources.contains(&RecallSource::Fts)
    }

    pub fn from_entity(&self) -> bool {
        self.sources.contains(&RecallSource::Entity)
    }

    pub fn from_vector(&self) -> bool {
        self.sources.contains(&RecallSource::Vector)
    }

    pub fn from_activation(&self) -> bool {
        self.sources.contains(&RecallSource::Activation)
    }
}

/// Builder for `RecallHit`. Public construction goes through here so the
/// hit struct's field list stays frozen and consumers don't break when
/// new optional fields land.
pub struct RecallHitBuilder {
    memory: Memory,
    rrf_score: f32,
    rerank_score: Option<f32>,
    activation_bonus: f32,
    fts_rank: Option<u32>,
    entity_rank: Option<u32>,
    vector_rank: Option<u32>,
    entity_hits: u32,
    sources: Vec<RecallSource>,
}

impl RecallHitBuilder {
    pub fn new(memory: Memory) -> Self {
        Self {
            memory,
            rrf_score: 0.0,
            rerank_score: None,
            activation_bonus: 0.0,
            fts_rank: None,
            entity_rank: None,
            vector_rank: None,
            entity_hits: 0,
            sources: Vec::new(),
        }
    }

    pub fn rrf_score(mut self, s: f32) -> Self {
        self.rrf_score = s;
        self
    }

    pub fn fts_rank(mut self, r: Option<u32>) -> Self {
        self.fts_rank = r;
        self
    }

    pub fn entity_rank(mut self, r: Option<u32>) -> Self {
        self.entity_rank = r;
        self
    }

    pub fn vector_rank(mut self, r: Option<u32>) -> Self {
        self.vector_rank = r;
        self
    }

    pub fn entity_hits(mut self, n: u32) -> Self {
        self.entity_hits = n;
        self
    }

    pub fn sources(mut self, s: Vec<RecallSource>) -> Self {
        self.sources = s;
        self
    }

    /// Finalize with `score` left equal to `rrf_score`. The engine will
    /// overwrite `score` after rerank + decay + booster passes.
    pub fn build(self) -> RecallHit {
        RecallHit {
            memory: self.memory,
            score: self.rrf_score,
            rrf_score: self.rrf_score,
            rerank_score: self.rerank_score,
            activation_bonus: self.activation_bonus,
            fts_rank: self.fts_rank,
            entity_rank: self.entity_rank,
            vector_rank: self.vector_rank,
            entity_hits: self.entity_hits,
            sources: self.sources,
        }
    }
}
