//! Data types for the Edge Hypothesis Pool.

use serde::{Deserialize, Serialize};

/// Cognitive relation types (three categories, v0.1).
///
/// Association: statistical (co_activates, related)
/// Reasoning: semantic (explains, supports, predicts)
/// Evolution: temporal change (conflicts_with, resolves, replaces)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum EdgeRelation {
    // Association
    CoActivates,
    Related,
    // Reasoning
    Explains,
    Supports,
    Predicts,
    // Evolution
    ConflictsWith,
    Resolves,
    Replaces,
}

impl EdgeRelation {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::CoActivates => "co_activates",
            Self::Related => "related",
            Self::Explains => "explains",
            Self::Supports => "supports",
            Self::Predicts => "predicts",
            Self::ConflictsWith => "conflicts_with",
            Self::Resolves => "resolves",
            Self::Replaces => "replaces",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "co_activates" => Some(Self::CoActivates),
            "related" => Some(Self::Related),
            "explains" => Some(Self::Explains),
            "supports" => Some(Self::Supports),
            "predicts" => Some(Self::Predicts),
            "conflicts_with" => Some(Self::ConflictsWith),
            "resolves" => Some(Self::Resolves),
            "replaces" => Some(Self::Replaces),
            _ => None,
        }
    }

    pub fn category(&self) -> &'static str {
        match self {
            Self::CoActivates | Self::Related => "association",
            Self::Explains | Self::Supports | Self::Predicts => "reasoning",
            Self::ConflictsWith | Self::Resolves | Self::Replaces => "evolution",
        }
    }
}

/// Lifecycle states for an edge hypothesis.
///
/// candidate -> observed -> confirmed -> strengthened
///                                    -> disputed -> resolved/forgotten
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum EdgeHypothesisStatus {
    Candidate,
    Observed,
    Confirmed,
    Strengthened,
    Disputed,
    Forgotten,
}

impl EdgeHypothesisStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Candidate => "candidate",
            Self::Observed => "observed",
            Self::Confirmed => "confirmed",
            Self::Strengthened => "strengthened",
            Self::Disputed => "disputed",
            Self::Forgotten => "forgotten",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "candidate" => Some(Self::Candidate),
            "observed" => Some(Self::Observed),
            "confirmed" => Some(Self::Confirmed),
            "strengthened" => Some(Self::Strengthened),
            "disputed" => Some(Self::Disputed),
            "forgotten" => Some(Self::Forgotten),
            _ => None,
        }
    }
}

/// A proposed relation between two memories, pending validation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeHypothesis {
    pub id: String,
    pub source: String,
    pub target: String,
    pub relation: EdgeRelation,
    pub confidence: f32,
    pub observations: usize,
    pub distinct_contexts: usize,
    pub predictive_utility: f32,
    pub first_seen: i64,
    pub last_seen: i64,
    pub status: EdgeHypothesisStatus,
    pub confirmed_at: Option<i64>,
    pub disputed_at: Option<i64>,
    pub decayed_turns: usize,
}

/// Evidence supporting a hypothesis. This is the edge's "memory" —
/// not just an audit log, but the history of why we believe this relation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeEvidence {
    pub id: String,
    pub hypothesis_id: String,
    pub query_context_hash: String,
    pub query_context_tag: String,
    pub supporting_memory_ids: String,
    pub reason_summary: String,
    pub utility_before_rank: Option<i64>,
    pub utility_after_rank: Option<i64>,
    pub observed_at: i64,
}

/// Observed utility of an edge for a single query.
/// Utility is OBSERVED, not predicted.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeUtilityObservation {
    pub query_id: String,
    pub before_rank: usize,
    pub after_rank: usize,
    pub before_recall: bool,
    pub after_recall: bool,
}

impl EdgeUtilityObservation {
    /// Negative = improvement (rank went down = better).
    pub fn rank_delta(&self) -> i32 {
        self.after_rank as i32 - self.before_rank as i32
    }

    pub fn recall_improved(&self) -> bool {
        !self.before_recall && self.after_recall
    }
}

/// Context passed to hypothesis generators after each retrieval.
#[derive(Debug, Clone)]
pub struct RetrievalContext<'a> {
    pub query: &'a str,
    pub query_context_hash: &'a str,
    pub query_context_tag: &'a str,
    pub hit_memory_ids: &'a [String],
    pub hit_scores: &'a [f32],
    pub timestamp: i64,
}

/// Graduation thresholds (defaults from design doc v0.3).
pub const CONFIRM_THRESHOLD: f32 = 0.70;
pub const MIN_OBSERVATIONS: usize = 3;
pub const MIN_DIVERSITY_CONTEXTS: usize = 3;

/// Confidence weights.
pub const W_FREQUENCY: f32 = 0.2;
pub const W_DIVERSITY: f32 = 0.3;
pub const W_UTILITY: f32 = 0.5;

/// Initial confidence for a new hypothesis.
pub const INITIAL_CONFIDENCE: f32 = 0.20;

/// Confidence boost per re-observation in a new context.
pub const REOBSERVATION_BOOST: f32 = 0.15;

/// Confidence decay per turn without re-proposal.
pub const DECAY_PER_TURN: f32 = 0.05;

/// Confidence floor below which a hypothesis is forgotten.
pub const CONFIDENCE_FLOOR: f32 = 0.05;
