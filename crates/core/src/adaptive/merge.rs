//! Merge Algorithm skeleton and rule-based reference (RFC-013).
//!
//! This module is algorithm-local. It consumes `Memory + AlgorithmContext`
//! from RFC-011 and does not extend the shared adaptive model.

use crate::adaptive::AlgorithmContext;
use crate::model::Memory;
use crate::working_memory::{
    ConsolidationPlan, MergeGroup, MergeStrategy, SessionId, WorkingMemoryItem,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::time::Duration;
use uuid::Uuid;

const DEFAULT_MERGE_THRESHOLD: f32 = 0.72;
const DEFAULT_CANDIDATE_THRESHOLD: f32 = 0.45;

pub trait MergeAlgorithm {
    fn merge(&self, target: &MergeTarget, ctx: &AlgorithmContext<'_>) -> MergeOutput;
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[non_exhaustive]
pub struct MergeTarget {
    pub memories: Vec<Memory>,
}

impl MergeTarget {
    pub fn new(memories: Vec<Memory>) -> Self {
        Self { memories }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub enum MergeOutput {
    Skipped {
        reason: MergeSkipReason,
    },
    Candidate {
        memory_ids: Vec<String>,
        strategy: MergeStrategy,
        score: f32,
    },
    Merge {
        memory_ids: Vec<String>,
        strategy: MergeStrategy,
        merged_content: String,
        score: f32,
    },
}

impl MergeOutput {
    pub fn is_empty(&self) -> bool {
        matches!(
            self,
            Self::Skipped {
                reason: MergeSkipReason::NoOp
            }
        )
    }

    /// Convert a positive merge decision into the existing consolidation plan
    /// shape.
    ///
    /// This is a pure adapter. It does not write to storage; later execution
    /// and store-dispatch layers translate the returned `MergeGroup` into
    /// canonical store mutations. `Candidate` and `Skipped` outputs do not
    /// produce a plan because they still require review or intentionally carry
    /// no work.
    pub fn to_consolidation_plan_with_item_id(
        &self,
        item_id: Uuid,
        session_id: SessionId,
        created_at: DateTime<Utc>,
        ttl: Duration,
    ) -> Option<ConsolidationPlan> {
        let (memory_ids, strategy, merged_content) = match self {
            Self::Merge {
                memory_ids,
                strategy,
                merged_content,
                ..
            } => (memory_ids, *strategy, merged_content),
            Self::Candidate { .. } | Self::Skipped { .. } => return None,
        };

        Some(ConsolidationPlan {
            promote: Vec::new(),
            merge: vec![MergeGroup {
                items: vec![WorkingMemoryItem {
                    id: item_id,
                    session_id,
                    content: merged_content.clone(),
                    linked_memory_ids: memory_ids.clone(),
                    created_at,
                    ttl,
                }],
                strategy,
            }],
            discard: Vec::new(),
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum MergeSkipReason {
    NoOp,
    TooFewMemories,
    EmptyContent,
    StructurallyInert,
    LowSimilarity,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NoOpMergeAlgorithm;

impl MergeAlgorithm for NoOpMergeAlgorithm {
    fn merge(&self, _target: &MergeTarget, _ctx: &AlgorithmContext<'_>) -> MergeOutput {
        MergeOutput::Skipped {
            reason: MergeSkipReason::NoOp,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct RuleBasedMergeAlgorithm {
    merge_threshold: f32,
    candidate_threshold: f32,
}

impl RuleBasedMergeAlgorithm {
    pub fn new(merge_threshold: f32, candidate_threshold: f32) -> Self {
        let merge_threshold = sanitize_threshold(merge_threshold, DEFAULT_MERGE_THRESHOLD);
        let candidate_threshold =
            sanitize_threshold(candidate_threshold, DEFAULT_CANDIDATE_THRESHOLD);
        let (merge_threshold, candidate_threshold) = if candidate_threshold > merge_threshold {
            (candidate_threshold, merge_threshold)
        } else {
            (merge_threshold, candidate_threshold)
        };
        Self {
            merge_threshold,
            candidate_threshold,
        }
    }

    pub fn merge_threshold(&self) -> f32 {
        self.merge_threshold
    }

    pub fn candidate_threshold(&self) -> f32 {
        self.candidate_threshold
    }
}

impl Default for RuleBasedMergeAlgorithm {
    fn default() -> Self {
        Self::new(DEFAULT_MERGE_THRESHOLD, DEFAULT_CANDIDATE_THRESHOLD)
    }
}

impl MergeAlgorithm for RuleBasedMergeAlgorithm {
    fn merge(&self, target: &MergeTarget, ctx: &AlgorithmContext<'_>) -> MergeOutput {
        if target.memories.len() < 2 {
            return MergeOutput::Skipped {
                reason: MergeSkipReason::TooFewMemories,
            };
        }

        if target
            .memories
            .iter()
            .any(|memory| memory.content.trim().is_empty())
        {
            return MergeOutput::Skipped {
                reason: MergeSkipReason::EmptyContent,
            };
        }

        if target.memories.iter().any(|memory| {
            memory.superseded_by.is_some()
                || memory
                    .valid_to
                    .is_some_and(|valid_to| valid_to <= ctx.now.timestamp())
        }) {
            return MergeOutput::Skipped {
                reason: MergeSkipReason::StructurallyInert,
            };
        }

        let score = merge_score(&target.memories);
        let memory_ids = target
            .memories
            .iter()
            .map(|memory| memory.id.clone())
            .collect::<Vec<_>>();
        let strategy = merge_strategy(&target.memories);

        if score >= self.merge_threshold {
            return MergeOutput::Merge {
                memory_ids,
                strategy,
                merged_content: merged_content(&target.memories),
                score,
            };
        }

        if score >= self.candidate_threshold {
            return MergeOutput::Candidate {
                memory_ids,
                strategy,
                score,
            };
        }

        MergeOutput::Skipped {
            reason: MergeSkipReason::LowSimilarity,
        }
    }
}

fn sanitize_threshold(value: f32, fallback: f32) -> f32 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        fallback
    }
}

fn merge_score(memories: &[Memory]) -> f32 {
    let mut pairs = Vec::new();
    for left in 0..memories.len() {
        for right in (left + 1)..memories.len() {
            pairs.push(pair_score(&memories[left], &memories[right]));
        }
    }
    if pairs.is_empty() {
        0.0
    } else {
        pairs.iter().sum::<f32>() / pairs.len() as f32
    }
}

fn pair_score(left: &Memory, right: &Memory) -> f32 {
    let mut score = token_overlap(&left.content, &right.content) * 0.65;
    if left.kind == right.kind {
        score += 0.15;
    }
    if left.scope == right.scope {
        score += 0.10;
    }
    if shared_signal_count(&left.content, &right.content) > 0 {
        score += 0.10;
    }
    score.clamp(0.0, 1.0)
}

fn token_overlap(left: &str, right: &str) -> f32 {
    let left_tokens = tokens(left);
    let right_tokens = tokens(right);
    if left_tokens.is_empty() || right_tokens.is_empty() {
        return 0.0;
    }
    let intersection = left_tokens.intersection(&right_tokens).count() as f32;
    let union = left_tokens.union(&right_tokens).count() as f32;
    if union == 0.0 {
        0.0
    } else {
        intersection / union
    }
}

fn tokens(value: &str) -> BTreeSet<String> {
    value
        .split(|ch: char| !ch.is_alphanumeric())
        .filter_map(|raw| {
            let token = raw.trim().to_ascii_lowercase();
            if token.len() >= 3 {
                Some(token)
            } else {
                None
            }
        })
        .collect()
}

fn shared_signal_count(left: &str, right: &str) -> usize {
    let left = left.to_ascii_lowercase();
    let right = right.to_ascii_lowercase();
    [
        "fix", "error", "prefer", "must", "should", "avoid", "failure",
    ]
    .iter()
    .filter(|signal| left.contains(**signal) && right.contains(**signal))
    .count()
}

fn merge_strategy(memories: &[Memory]) -> MergeStrategy {
    let unique_content = memories
        .iter()
        .map(|memory| normalize_content(&memory.content))
        .collect::<BTreeSet<_>>();
    if unique_content.len() == 1 {
        MergeStrategy::Deduplicate
    } else if memories.len() > 2 {
        MergeStrategy::Compress
    } else {
        MergeStrategy::Union
    }
}

fn merged_content(memories: &[Memory]) -> String {
    let mut seen = BTreeSet::new();
    let mut lines = Vec::new();
    for memory in memories {
        let normalized = normalize_content(&memory.content);
        if seen.insert(normalized) {
            lines.push(memory.content.trim().to_string());
        }
    }
    lines.join("\n")
}

fn normalize_content(value: &str) -> String {
    value
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_ascii_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::{NoOpImportanceEstimator, NoOpMemoryEventStream};
    use crate::model::{MemoryKind, Scope, Source};
    use chrono::Utc;
    use std::time::Duration;
    use uuid::Uuid;

    fn memory(id: &str, content: &str) -> Memory {
        Memory {
            id: id.to_string(),
            kind: MemoryKind::Failure,
            scope: Scope::Global,
            content: content.to_string(),
            source: Source::ExplicitUser,
            confidence: 1.0,
            importance: 0.5,
            valid_from: 0,
            valid_to: None,
            superseded_by: None,
            access_count: 0,
            last_accessed_at: None,
        }
    }

    fn ctx<'a>(
        importance: &'a NoOpImportanceEstimator,
        events: &'a NoOpMemoryEventStream,
    ) -> AlgorithmContext<'a> {
        AlgorithmContext::new(Utc::now(), None, importance, events)
    }

    #[test]
    fn noop_merge_algorithm_returns_empty_output() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = NoOpMergeAlgorithm;

        let output = algorithm.merge(&MergeTarget::default(), &ctx(&importance, &events));

        assert_eq!(
            output,
            MergeOutput::Skipped {
                reason: MergeSkipReason::NoOp,
            }
        );
        assert!(output.is_empty());
    }

    #[test]
    fn rule_based_merge_merges_duplicate_failures() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedMergeAlgorithm::default();
        let target = MergeTarget::new(vec![
            memory("a", "Fix JWT refresh error by rotating token cache."),
            memory("b", "Fix JWT refresh error by rotating token cache."),
        ]);

        let output = algorithm.merge(&target, &ctx(&importance, &events));

        assert!(matches!(
            output,
            MergeOutput::Merge {
                memory_ids,
                strategy: MergeStrategy::Deduplicate,
                merged_content,
                ..
            } if memory_ids == vec!["a".to_string(), "b".to_string()]
                && merged_content == "Fix JWT refresh error by rotating token cache."
        ));
    }

    #[test]
    fn merge_output_maps_to_consolidation_plan() {
        let item_id = Uuid::nil();
        let session_id = SessionId::new();
        let created_at = Utc::now();
        let ttl = Duration::from_secs(60);
        let output = MergeOutput::Merge {
            memory_ids: vec!["a".to_string(), "b".to_string()],
            strategy: MergeStrategy::Deduplicate,
            merged_content: "merged content".to_string(),
            score: 1.0,
        };

        let plan = output
            .to_consolidation_plan_with_item_id(item_id, session_id, created_at, ttl)
            .expect("merge output should produce a consolidation plan");

        assert!(plan.promote.is_empty());
        assert!(plan.discard.is_empty());
        assert_eq!(plan.merge.len(), 1);
        assert_eq!(plan.merge[0].strategy, MergeStrategy::Deduplicate);
        assert_eq!(plan.merge[0].items.len(), 1);
        assert_eq!(plan.merge[0].items[0].id, item_id);
        assert_eq!(plan.merge[0].items[0].session_id, session_id);
        assert_eq!(plan.merge[0].items[0].content, "merged content");
        assert_eq!(
            plan.merge[0].items[0].linked_memory_ids,
            vec!["a".to_string(), "b".to_string()]
        );
        assert_eq!(plan.merge[0].items[0].created_at, created_at);
        assert_eq!(plan.merge[0].items[0].ttl, ttl);
    }

    #[test]
    fn non_merge_outputs_do_not_create_consolidation_plans() {
        let item_id = Uuid::nil();
        let session_id = SessionId::new();
        let created_at = Utc::now();
        let ttl = Duration::from_secs(60);

        let candidate = MergeOutput::Candidate {
            memory_ids: vec!["a".to_string(), "b".to_string()],
            strategy: MergeStrategy::Union,
            score: 0.5,
        };
        let skipped = MergeOutput::Skipped {
            reason: MergeSkipReason::LowSimilarity,
        };

        assert!(candidate
            .to_consolidation_plan_with_item_id(item_id, session_id, created_at, ttl)
            .is_none());
        assert!(skipped
            .to_consolidation_plan_with_item_id(item_id, session_id, created_at, ttl)
            .is_none());
    }

    #[test]
    fn rule_based_merge_marks_related_memories_candidate() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedMergeAlgorithm::default();
        let target = MergeTarget::new(vec![
            memory("a", "Fix JWT refresh error in auth middleware."),
            memory("b", "Avoid JWT refresh failure in auth handler."),
        ]);

        let output = algorithm.merge(&target, &ctx(&importance, &events));

        assert!(matches!(
            output,
            MergeOutput::Candidate {
                memory_ids,
                strategy: MergeStrategy::Union,
                ..
            } if memory_ids == vec!["a".to_string(), "b".to_string()]
        ));
    }

    #[test]
    fn rule_based_merge_skips_unrelated_memories() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedMergeAlgorithm::default();
        let mut other = memory("b", "Prefer concise Chinese summaries.");
        other.kind = MemoryKind::Preference;
        other.scope = Scope::User;
        let target = MergeTarget::new(vec![memory("a", "Fix JWT refresh error."), other]);

        let output = algorithm.merge(&target, &ctx(&importance, &events));

        assert_eq!(
            output,
            MergeOutput::Skipped {
                reason: MergeSkipReason::LowSimilarity,
            }
        );
    }

    #[test]
    fn rule_based_merge_rejects_structurally_inert_memory() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedMergeAlgorithm::default();
        let mut inert = memory("b", "Fix JWT refresh error.");
        inert.superseded_by = Some("newer".to_string());
        let target = MergeTarget::new(vec![memory("a", "Fix JWT refresh error."), inert]);

        let output = algorithm.merge(&target, &ctx(&importance, &events));

        assert_eq!(
            output,
            MergeOutput::Skipped {
                reason: MergeSkipReason::StructurallyInert,
            }
        );
    }
}
