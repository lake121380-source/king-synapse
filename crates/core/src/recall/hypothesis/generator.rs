//! Edge hypothesis generators.
//!
//! Phase 1a: RuleBasedEdgeGenerator (deterministic, no LLM).
//! Phase 1b: LLMEdgeGenerator (DeepSeek-backed).
//! Phase 1c: HybridEdgeGenerator.

use super::model::{EdgeHypothesis, EdgeRelation, RetrievalContext, INITIAL_CONFIDENCE};
use std::collections::HashSet;

/// Anything that can propose edge hypotheses from a retrieval context.
pub trait EdgeHypothesisGenerator: Send + Sync {
    fn generate(&self, context: &RetrievalContext<'_>) -> Vec<EdgeHypothesis>;
    fn name(&self) -> &'static str;
}

/// Rule-based generator using co-retrieval and temporal proximity.
///
/// Phase 1a: deterministic, no LLM. Validates the lifecycle mechanism.
/// Rules:
///   - Co-retrieval: A and B both in top-K -> propose co_activates
///   - Temporal proximity: handled by store (same session -> related)
pub struct RuleBasedEdgeGenerator {
    /// Minimum score for a hit to be considered for hypothesis generation.
    min_hit_score: f32,
}

impl RuleBasedEdgeGenerator {
    pub fn new() -> Self {
        Self {
            min_hit_score: f32::NEG_INFINITY,
        }
    }

    pub fn with_min_hit_score(mut self, score: f32) -> Self {
        self.min_hit_score = score;
        self
    }
}

impl Default for RuleBasedEdgeGenerator {
    fn default() -> Self {
        Self::new()
    }
}

impl EdgeHypothesisGenerator for RuleBasedEdgeGenerator {
    fn name(&self) -> &'static str {
        "rule_based"
    }

    fn generate(&self, ctx: &RetrievalContext<'_>) -> Vec<EdgeHypothesis> {
        let mut hypotheses = Vec::new();
        let ids: Vec<&str> = ctx
            .hit_memory_ids
            .iter()
            .zip(ctx.hit_scores.iter())
            .filter(|(_, score)| **score >= self.min_hit_score)
            .map(|(id, _)| id.as_str())
            .collect();

        // Co-retrieval: propose co_activates for all pairs in top-K.
        // This is intentionally simple — Phase 1a validates lifecycle, not quality.
        for i in 0..ids.len() {
            for j in (i + 1)..ids.len() {
                let source = ids[i];
                let target = ids[j];
                let hyp_id = hypothesis_id(source, target, EdgeRelation::CoActivates);
                hypotheses.push(EdgeHypothesis {
                    id: hyp_id,
                    source: source.to_string(),
                    target: target.to_string(),
                    relation: EdgeRelation::CoActivates,
                    confidence: INITIAL_CONFIDENCE,
                    observations: 1,
                    distinct_contexts: 1, // will be updated by store on upsert
                    predictive_utility: 0.0,
                    first_seen: ctx.timestamp,
                    last_seen: ctx.timestamp,
                    status: super::model::EdgeHypothesisStatus::Candidate,
                    confirmed_at: None,
                    disputed_at: None,
                    decayed_turns: 0,
                });
            }
        }

        hypotheses
    }
}

/// Generate a deterministic hypothesis ID from (source, target, relation).
pub fn hypothesis_id(source: &str, target: &str, relation: EdgeRelation) -> String {
    // Deterministic ordering so (A,B) and (B,A) produce the same ID
    // for symmetric relations.
    let (a, b) = if source <= target {
        (source, target)
    } else {
        (target, source)
    };
    format!("hyp_{}_{}_{}", a, b, relation.as_str())
}

/// Track distinct context hashes seen for a hypothesis.
#[derive(Debug, Clone, Default)]
pub struct ContextTracker {
    seen: HashSet<String>,
}

impl ContextTracker {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add(&mut self, hash: &str) -> bool {
        self.seen.insert(hash.to_string())
    }

    pub fn count(&self) -> usize {
        self.seen.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rule_based_generates_co_activates_for_pairs() {
        let gen = RuleBasedEdgeGenerator::new();
        let ids = vec!["m1".to_string(), "m2".to_string(), "m3".to_string()];
        let scores = vec![0.9, 0.8, 0.7];
        let ctx = RetrievalContext {
            query: "test",
            query_context_hash: "hash1",
            query_context_tag: "test",
            hit_memory_ids: &ids,
            hit_scores: &scores,
            timestamp: 1000,
        };
        let hyps = gen.generate(&ctx);
        // 3 choose 2 = 3 pairs
        assert_eq!(hyps.len(), 3);
        assert!(hyps.iter().all(|h| h.relation == EdgeRelation::CoActivates));
    }

    #[test]
    fn hypothesis_id_is_deterministic_and_symmetric() {
        let id1 = hypothesis_id("m1", "m2", EdgeRelation::CoActivates);
        let id2 = hypothesis_id("m2", "m1", EdgeRelation::CoActivates);
        assert_eq!(id1, id2);
    }
}
