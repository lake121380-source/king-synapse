//! Forget Algorithm skeleton and rule-based reference (RFC-014).
//!
//! This module is algorithm-local. It consumes `Memory + AlgorithmContext`
//! from RFC-011 and does not extend the shared adaptive model.

use crate::adaptive::AlgorithmContext;
use crate::model::Memory;
use crate::working_memory::{StoreMutation, StoreMutationPlan};
use serde::{Deserialize, Serialize};

const DEFAULT_FORGET_THRESHOLD: f32 = 1.2;
const DEFAULT_CANDIDATE_THRESHOLD: f32 = 0.7;
const STALE_AFTER_SECONDS: i64 = 90 * 24 * 60 * 60;
const RECENT_AFTER_SECONDS: i64 = 7 * 24 * 60 * 60;

pub trait ForgetAlgorithm {
    fn forget(&self, target: &ForgetTarget, ctx: &AlgorithmContext<'_>) -> ForgetOutput;
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[non_exhaustive]
pub struct ForgetTarget {
    pub memory: Memory,
}

impl ForgetTarget {
    pub fn new(memory: Memory) -> Self {
        Self { memory }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub enum ForgetOutput {
    Skipped {
        memory_id: String,
        reason: ForgetSkipReason,
    },
    Candidate {
        memory_id: String,
        reason: ForgetReason,
        score: f32,
    },
    Forget {
        memory_id: String,
        reason: ForgetReason,
        score: f32,
    },
}

impl ForgetOutput {
    pub fn empty(target: &ForgetTarget) -> Self {
        Self::Skipped {
            memory_id: target.memory.id.clone(),
            reason: ForgetSkipReason::NoOp,
        }
    }

    pub fn is_empty(&self) -> bool {
        matches!(
            self,
            Self::Skipped {
                reason: ForgetSkipReason::NoOp,
                ..
            }
        )
    }

    pub fn memory_id(&self) -> &str {
        match self {
            Self::Skipped { memory_id, .. }
            | Self::Candidate { memory_id, .. }
            | Self::Forget { memory_id, .. } => memory_id,
        }
    }

    /// Convert a positive forget decision into the existing store mutation
    /// plan shape.
    ///
    /// This is a pure adapter. It does not write to storage. `Candidate` and
    /// `Skipped` outputs do not produce a plan because they either require
    /// review or intentionally carry no work.
    pub fn to_store_mutation_plan(&self) -> Option<StoreMutationPlan> {
        let memory_id = match self {
            Self::Forget { memory_id, .. } => memory_id,
            Self::Candidate { .. } | Self::Skipped { .. } => return None,
        };

        Some(StoreMutationPlan {
            mutations: vec![StoreMutation::ArchiveMemory {
                id: memory_id.clone(),
            }],
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum ForgetReason {
    Expired,
    Superseded,
    EmptyContent,
    LowQualityStale,
    LowUseLowImportance,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum ForgetSkipReason {
    NoOp,
    ProtectedRecentAccess,
    HighImportance,
    InsufficientSignal,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NoOpForgetAlgorithm;

impl ForgetAlgorithm for NoOpForgetAlgorithm {
    fn forget(&self, target: &ForgetTarget, _ctx: &AlgorithmContext<'_>) -> ForgetOutput {
        ForgetOutput::empty(target)
    }
}

#[derive(Debug, Clone, Copy)]
pub struct RuleBasedForgetAlgorithm {
    forget_threshold: f32,
    candidate_threshold: f32,
}

impl RuleBasedForgetAlgorithm {
    pub fn new(forget_threshold: f32, candidate_threshold: f32) -> Self {
        let forget_threshold = sanitize_score(forget_threshold, DEFAULT_FORGET_THRESHOLD);
        let candidate_threshold = sanitize_score(candidate_threshold, DEFAULT_CANDIDATE_THRESHOLD);
        let (forget_threshold, candidate_threshold) = if candidate_threshold > forget_threshold {
            (candidate_threshold, forget_threshold)
        } else {
            (forget_threshold, candidate_threshold)
        };
        Self {
            forget_threshold,
            candidate_threshold,
        }
    }

    pub fn forget_threshold(&self) -> f32 {
        self.forget_threshold
    }

    pub fn candidate_threshold(&self) -> f32 {
        self.candidate_threshold
    }
}

impl Default for RuleBasedForgetAlgorithm {
    fn default() -> Self {
        Self::new(DEFAULT_FORGET_THRESHOLD, DEFAULT_CANDIDATE_THRESHOLD)
    }
}

impl ForgetAlgorithm for RuleBasedForgetAlgorithm {
    fn forget(&self, target: &ForgetTarget, ctx: &AlgorithmContext<'_>) -> ForgetOutput {
        let memory = &target.memory;
        let now = ctx.now.timestamp();

        if memory
            .last_accessed_at
            .is_some_and(|last_access| now.saturating_sub(last_access) <= RECENT_AFTER_SECONDS)
        {
            return ForgetOutput::Skipped {
                memory_id: memory.id.clone(),
                reason: ForgetSkipReason::ProtectedRecentAccess,
            };
        }

        if memory.valid_to.is_some_and(|valid_to| valid_to <= now) {
            return ForgetOutput::Forget {
                memory_id: memory.id.clone(),
                reason: ForgetReason::Expired,
                score: 1.0,
            };
        }

        if memory.superseded_by.is_some() {
            return ForgetOutput::Forget {
                memory_id: memory.id.clone(),
                reason: ForgetReason::Superseded,
                score: 1.0,
            };
        }

        if memory.content.trim().is_empty() {
            return ForgetOutput::Forget {
                memory_id: memory.id.clone(),
                reason: ForgetReason::EmptyContent,
                score: 1.0,
            };
        }

        let importance = ctx.importance.estimate(memory, ctx).overall.clamp(0.0, 1.0);
        if importance >= 0.8 || memory.importance >= 0.8 {
            return ForgetOutput::Skipped {
                memory_id: memory.id.clone(),
                reason: ForgetSkipReason::HighImportance,
            };
        }

        let score = forget_score(memory, importance, now);
        let reason = forget_reason(memory);

        if score >= self.forget_threshold {
            return ForgetOutput::Forget {
                memory_id: memory.id.clone(),
                reason,
                score,
            };
        }

        if score >= self.candidate_threshold {
            return ForgetOutput::Candidate {
                memory_id: memory.id.clone(),
                reason,
                score,
            };
        }

        ForgetOutput::Skipped {
            memory_id: memory.id.clone(),
            reason: ForgetSkipReason::InsufficientSignal,
        }
    }
}

fn sanitize_score(value: f32, fallback: f32) -> f32 {
    if value.is_finite() {
        value.max(0.0)
    } else {
        fallback
    }
}

fn forget_score(memory: &Memory, estimated_importance: f32, now: i64) -> f32 {
    let mut score = 0.0;
    let effective_importance = memory.importance.max(estimated_importance).clamp(0.0, 1.0);
    score += (1.0 - effective_importance) * 0.5;
    score += (1.0 - memory.confidence.clamp(0.0, 1.0)) * 0.35;

    if memory.access_count <= 0 {
        score += 0.2;
    }

    if is_stale(memory, now) {
        score += 0.4;
    }

    if has_low_quality_content(&memory.content) {
        score += 0.35;
    }

    score
}

fn forget_reason(memory: &Memory) -> ForgetReason {
    if has_low_quality_content(&memory.content) {
        ForgetReason::LowQualityStale
    } else {
        ForgetReason::LowUseLowImportance
    }
}

fn is_stale(memory: &Memory, now: i64) -> bool {
    let timestamp = memory.last_accessed_at.unwrap_or(memory.valid_from);
    now.saturating_sub(timestamp) >= STALE_AFTER_SECONDS
}

fn has_low_quality_content(content: &str) -> bool {
    let trimmed = content.trim();
    trimmed.len() < 8
        || ["todo", "temp", "temporary", "scratch", "???"]
            .iter()
            .any(|signal| trimmed.eq_ignore_ascii_case(signal))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::{NoOpImportanceEstimator, NoOpMemoryEventStream};
    use crate::model::{MemoryKind, Scope, Source};
    use chrono::{TimeZone, Utc};

    fn memory(id: &str, content: &str) -> Memory {
        Memory {
            id: id.to_string(),
            kind: MemoryKind::Fact,
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
        AlgorithmContext::new(
            Utc.timestamp_opt(1_700_000_000, 0).unwrap(),
            None,
            importance,
            events,
        )
    }

    #[test]
    fn noop_forget_algorithm_returns_empty_output() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let target = ForgetTarget::new(memory("m1", "keep me"));
        let algorithm = NoOpForgetAlgorithm;

        let output = algorithm.forget(&target, &ctx(&importance, &events));

        assert_eq!(
            output,
            ForgetOutput::Skipped {
                memory_id: "m1".to_string(),
                reason: ForgetSkipReason::NoOp,
            }
        );
        assert!(output.is_empty());
    }

    #[test]
    fn rule_based_forget_forgets_expired_memory() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let mut target = memory("expired", "expired memory");
        target.valid_to = Some(1);
        let algorithm = RuleBasedForgetAlgorithm::default();

        let output = algorithm.forget(&ForgetTarget::new(target), &ctx(&importance, &events));

        assert_eq!(
            output,
            ForgetOutput::Forget {
                memory_id: "expired".to_string(),
                reason: ForgetReason::Expired,
                score: 1.0,
            }
        );
    }

    #[test]
    fn forget_output_maps_to_store_mutation_plan() {
        let output = ForgetOutput::Forget {
            memory_id: "forget-me".to_string(),
            reason: ForgetReason::Expired,
            score: 1.0,
        };

        let plan = output
            .to_store_mutation_plan()
            .expect("forget output should produce a store mutation plan");

        assert_eq!(
            plan.mutations,
            vec![StoreMutation::ArchiveMemory {
                id: "forget-me".to_string(),
            }]
        );
    }

    #[test]
    fn non_forget_outputs_do_not_create_store_mutation_plans() {
        let candidate = ForgetOutput::Candidate {
            memory_id: "candidate".to_string(),
            reason: ForgetReason::LowUseLowImportance,
            score: 0.8,
        };
        let skipped = ForgetOutput::Skipped {
            memory_id: "skipped".to_string(),
            reason: ForgetSkipReason::HighImportance,
        };

        assert!(candidate.to_store_mutation_plan().is_none());
        assert!(skipped.to_store_mutation_plan().is_none());
    }

    #[test]
    fn rule_based_forget_forgets_superseded_memory() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let mut target = memory("superseded", "old value");
        target.superseded_by = Some("newer".to_string());
        let algorithm = RuleBasedForgetAlgorithm::default();

        let output = algorithm.forget(&ForgetTarget::new(target), &ctx(&importance, &events));

        assert_eq!(
            output,
            ForgetOutput::Forget {
                memory_id: "superseded".to_string(),
                reason: ForgetReason::Superseded,
                score: 1.0,
            }
        );
    }

    #[test]
    fn rule_based_forget_marks_low_quality_stale_memory() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let mut target = memory("scratch", "todo");
        target.confidence = 0.2;
        target.importance = 0.1;
        target.valid_from = 1_600_000_000;
        let algorithm = RuleBasedForgetAlgorithm::default();

        let output = algorithm.forget(&ForgetTarget::new(target), &ctx(&importance, &events));

        assert!(matches!(
            output,
            ForgetOutput::Forget {
                memory_id,
                reason: ForgetReason::LowQualityStale,
                score,
            } if memory_id == "scratch" && score >= algorithm.forget_threshold()
        ));
    }

    #[test]
    fn rule_based_forget_marks_medium_signal_memory_candidate() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let mut target = memory("candidate", "old rarely used fact");
        target.confidence = 0.7;
        target.importance = 0.4;
        target.valid_from = 1_600_000_000;
        target.access_count = 0;
        let algorithm = RuleBasedForgetAlgorithm::default();

        let output = algorithm.forget(&ForgetTarget::new(target), &ctx(&importance, &events));

        assert!(matches!(
            output,
            ForgetOutput::Candidate {
                memory_id,
                reason: ForgetReason::LowUseLowImportance,
                score,
            } if memory_id == "candidate"
                && score >= algorithm.candidate_threshold()
                && score < algorithm.forget_threshold()
        ));
    }

    #[test]
    fn rule_based_forget_skips_high_importance_memory() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let mut target = memory("important", "critical production invariant");
        target.importance = 0.95;
        target.valid_from = 1_600_000_000;
        let algorithm = RuleBasedForgetAlgorithm::default();

        let output = algorithm.forget(&ForgetTarget::new(target), &ctx(&importance, &events));

        assert_eq!(
            output,
            ForgetOutput::Skipped {
                memory_id: "important".to_string(),
                reason: ForgetSkipReason::HighImportance,
            }
        );
    }

    #[test]
    fn rule_based_forget_skips_recently_accessed_memory() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let mut target = memory("recent", "recently used note");
        target.importance = 0.1;
        target.confidence = 0.1;
        target.last_accessed_at = Some(1_700_000_000 - 60);
        let algorithm = RuleBasedForgetAlgorithm::default();

        let output = algorithm.forget(&ForgetTarget::new(target), &ctx(&importance, &events));

        assert_eq!(
            output,
            ForgetOutput::Skipped {
                memory_id: "recent".to_string(),
                reason: ForgetSkipReason::ProtectedRecentAccess,
            }
        );
    }

    #[test]
    fn rule_based_forget_config_is_sanitized_and_ordered() {
        let algorithm = RuleBasedForgetAlgorithm::new(f32::NAN, 2.0);

        assert_eq!(algorithm.forget_threshold(), 2.0);
        assert_eq!(algorithm.candidate_threshold(), 1.2);
    }
}
