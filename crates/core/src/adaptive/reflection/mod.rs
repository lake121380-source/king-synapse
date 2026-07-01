//! Reflection Algorithm skeleton (RFC-012).
//!
//! This module is algorithm-local. It consumes the frozen Adaptive Common
//! Model (`Memory` + `AlgorithmContext`) and does not extend RFC-011.
//!
//! v0.6.0-v0.6.2 scope: skeleton + NoOp + deterministic reference. No
//! production logic, no Store access, no Recall access, no graph access, no
//! LLM access, and no side effects.

use crate::adaptive::{AlgorithmContext, MemoryImportance};
use crate::model::{Memory, MemoryKind};
use crate::working_memory::{
    ReflectionEvent, ReflectionEventId, ReflectionPayload, ReflectionSource, SessionId,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

const DEFAULT_MIN_IMPORTANCE: f32 = 0.5;
const DEFAULT_RECENT_EVENT_LIMIT: usize = 32;
const DEFAULT_RULE_PRODUCE_SCORE: f32 = 1.5;
const DEFAULT_RULE_CANDIDATE_SCORE: f32 = 0.8;

/// Reflection algorithm entry point.
///
/// The method shape is fixed by RFC-011 PF2: one target argument plus
/// `&AlgorithmContext`. Implementations must be side-effect free.
pub trait ReflectionAlgorithm {
    fn reflect(&self, target: &Memory, ctx: &AlgorithmContext<'_>) -> ReflectionOutput;
}

/// Algorithm-local output produced by a `ReflectionAlgorithm`.
///
/// RFC-012 deterministic reference scope includes deterministic skipped and
/// candidate output. Future production milestones may use `Produced` without
/// changing RFC-011.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub enum ReflectionOutput {
    Skipped {
        target_memory_id: String,
        reason: ReflectionSkipReason,
    },
    Candidate {
        target_memory_id: String,
        importance: MemoryImportance,
        evidence_count: usize,
    },
    Produced {
        target_memory_id: String,
        payload_summary: String,
    },
}

impl ReflectionOutput {
    pub fn empty(target: &Memory) -> Self {
        Self::Skipped {
            target_memory_id: target.id.clone(),
            reason: ReflectionSkipReason::NoOp,
        }
    }

    pub fn is_empty(&self) -> bool {
        matches!(
            self,
            Self::Skipped {
                reason: ReflectionSkipReason::NoOp,
                ..
            }
        )
    }

    /// Convert algorithm output into the frozen Reflection Processing event
    /// shape.
    ///
    /// This is a pure adapter: skipped outputs do not create events, and
    /// positive outputs become a non-empty `ReflectionPayload` that the
    /// existing `PlanOnlyReflectionExecutor` can process. The caller supplies
    /// `now` so this method does not read the system clock.
    pub fn to_reflection_event_with_id(
        &self,
        event_id: ReflectionEventId,
        session_id: SessionId,
        source: ReflectionSource,
        now: DateTime<Utc>,
    ) -> Option<ReflectionEvent> {
        let target_memory_id = match self {
            Self::Candidate {
                target_memory_id, ..
            }
            | Self::Produced {
                target_memory_id, ..
            } => target_memory_id.clone(),
            Self::Skipped { .. } => return None,
        };

        Some(ReflectionEvent {
            id: event_id,
            session_id,
            timestamp: now,
            source,
            payload: ReflectionPayload {
                promoted: vec![target_memory_id],
                merged: Vec::new(),
                discarded: Vec::new(),
            },
        })
    }
}

/// Reason a reflection invocation did not produce reflection work.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum ReflectionSkipReason {
    NoOp,
    EmptyContent,
    StructurallyInert,
    LowImportance,
}

/// Deterministic empty implementation for default wiring and tests.
#[derive(Debug, Clone, Copy, Default)]
pub struct NoOpReflectionAlgorithm;

impl ReflectionAlgorithm for NoOpReflectionAlgorithm {
    fn reflect(&self, target: &Memory, _ctx: &AlgorithmContext<'_>) -> ReflectionOutput {
        ReflectionOutput::empty(target)
    }
}

/// Deterministic reference implementation for RFC-012.
///
/// This is not a production-quality semantic algorithm. Its purpose is to
/// provide a reproducible baseline for tests and future production
/// comparisons.
#[derive(Debug, Clone, Copy)]
pub struct DeterministicReflectionAlgorithm {
    min_importance: f32,
    recent_event_limit: usize,
}

impl DeterministicReflectionAlgorithm {
    pub fn new(min_importance: f32, recent_event_limit: usize) -> Self {
        let min_importance = if min_importance.is_finite() {
            min_importance.clamp(0.0, 1.0)
        } else {
            DEFAULT_MIN_IMPORTANCE
        };
        Self {
            min_importance,
            recent_event_limit,
        }
    }

    pub fn min_importance(&self) -> f32 {
        self.min_importance
    }

    pub fn recent_event_limit(&self) -> usize {
        self.recent_event_limit
    }
}

impl Default for DeterministicReflectionAlgorithm {
    fn default() -> Self {
        Self::new(DEFAULT_MIN_IMPORTANCE, DEFAULT_RECENT_EVENT_LIMIT)
    }
}

impl ReflectionAlgorithm for DeterministicReflectionAlgorithm {
    fn reflect(&self, target: &Memory, ctx: &AlgorithmContext<'_>) -> ReflectionOutput {
        if target.content.trim().is_empty() {
            return ReflectionOutput::Skipped {
                target_memory_id: target.id.clone(),
                reason: ReflectionSkipReason::EmptyContent,
            };
        }

        if target.superseded_by.is_some()
            || target.valid_to.is_some_and(|v| v <= ctx.now.timestamp())
        {
            return ReflectionOutput::Skipped {
                target_memory_id: target.id.clone(),
                reason: ReflectionSkipReason::StructurallyInert,
            };
        }

        let importance = ctx.importance.estimate(target, ctx);
        if importance.overall < self.min_importance {
            return ReflectionOutput::Skipped {
                target_memory_id: target.id.clone(),
                reason: ReflectionSkipReason::LowImportance,
            };
        }

        let evidence_count = ctx
            .events
            .recent(self.recent_event_limit)
            .iter()
            .filter(|event| event.memory_ids.iter().any(|id| id == &target.id))
            .count();

        ReflectionOutput::Candidate {
            target_memory_id: target.id.clone(),
            importance,
            evidence_count,
        }
    }
}

/// Rule-based Reflection implementation for v0.6.6.
///
/// This remains deterministic and side-effect free, but it is closer to a
/// production heuristic than the deterministic reference: it combines
/// importance, target-specific event evidence, memory kind, and lightweight
/// content signals to decide whether to produce a reflection payload or only
/// mark the target as a candidate.
#[derive(Debug, Clone, Copy)]
pub struct RuleBasedReflectionAlgorithm {
    produce_score: f32,
    candidate_score: f32,
    recent_event_limit: usize,
}

impl RuleBasedReflectionAlgorithm {
    pub fn new(produce_score: f32, candidate_score: f32, recent_event_limit: usize) -> Self {
        let produce_score = sanitize_score(produce_score, DEFAULT_RULE_PRODUCE_SCORE);
        let candidate_score = sanitize_score(candidate_score, DEFAULT_RULE_CANDIDATE_SCORE);
        let (produce_score, candidate_score) = if candidate_score > produce_score {
            (candidate_score, produce_score)
        } else {
            (produce_score, candidate_score)
        };
        Self {
            produce_score,
            candidate_score,
            recent_event_limit,
        }
    }

    pub fn produce_score(&self) -> f32 {
        self.produce_score
    }

    pub fn candidate_score(&self) -> f32 {
        self.candidate_score
    }

    pub fn recent_event_limit(&self) -> usize {
        self.recent_event_limit
    }
}

impl Default for RuleBasedReflectionAlgorithm {
    fn default() -> Self {
        Self::new(
            DEFAULT_RULE_PRODUCE_SCORE,
            DEFAULT_RULE_CANDIDATE_SCORE,
            DEFAULT_RECENT_EVENT_LIMIT,
        )
    }
}

impl ReflectionAlgorithm for RuleBasedReflectionAlgorithm {
    fn reflect(&self, target: &Memory, ctx: &AlgorithmContext<'_>) -> ReflectionOutput {
        if target.content.trim().is_empty() {
            return ReflectionOutput::Skipped {
                target_memory_id: target.id.clone(),
                reason: ReflectionSkipReason::EmptyContent,
            };
        }

        if target.superseded_by.is_some()
            || target.valid_to.is_some_and(|v| v <= ctx.now.timestamp())
        {
            return ReflectionOutput::Skipped {
                target_memory_id: target.id.clone(),
                reason: ReflectionSkipReason::StructurallyInert,
            };
        }

        let importance = ctx.importance.estimate(target, ctx);
        let evidence_count = ctx
            .events
            .recent(self.recent_event_limit)
            .iter()
            .filter(|event| event.memory_ids.iter().any(|id| id == &target.id))
            .count();
        let score = reflection_rule_score(target, importance, evidence_count);

        if score >= self.produce_score {
            return ReflectionOutput::Produced {
                target_memory_id: target.id.clone(),
                payload_summary: reflection_summary(target, evidence_count),
            };
        }

        if score >= self.candidate_score {
            return ReflectionOutput::Candidate {
                target_memory_id: target.id.clone(),
                importance,
                evidence_count,
            };
        }

        ReflectionOutput::Skipped {
            target_memory_id: target.id.clone(),
            reason: ReflectionSkipReason::LowImportance,
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

fn reflection_rule_score(
    target: &Memory,
    importance: MemoryImportance,
    evidence_count: usize,
) -> f32 {
    let mut score = importance.overall.clamp(0.0, 1.0);
    score += (evidence_count.min(3) as f32) * 0.35;
    score += kind_weight(target.kind);
    score += content_signal_weight(&target.content);
    score
}

fn kind_weight(kind: MemoryKind) -> f32 {
    match kind {
        MemoryKind::Failure => 0.45,
        MemoryKind::Preference => 0.35,
        MemoryKind::Playbook => 0.30,
        MemoryKind::State => 0.20,
        MemoryKind::Fact => 0.10,
    }
}

fn content_signal_weight(content: &str) -> f32 {
    let normalized = content.to_ascii_lowercase();
    let signals = [
        "fail",
        "failure",
        "error",
        "fix",
        "avoid",
        "prefer",
        "preference",
        "should",
        "must",
        "remember",
        "next time",
    ];
    let hits = signals
        .iter()
        .filter(|signal| normalized.contains(**signal))
        .count();
    (hits.min(3) as f32) * 0.15
}

fn reflection_summary(target: &Memory, evidence_count: usize) -> String {
    let kind = target.kind.to_string();
    let content = truncate_chars(target.content.trim(), 96);
    format!("reflect {kind} memory after {evidence_count} supporting events: {content}")
}

fn truncate_chars(value: &str, max_chars: usize) -> String {
    if value.chars().count() <= max_chars {
        return value.to_string();
    }
    let mut out: String = value.chars().take(max_chars).collect();
    out.push_str("...");
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::{
        InMemoryMemoryEventStream, MemoryEvent, MemoryEventId, MemoryEventKind, MemoryEventPayload,
        MemoryEventStream, NoOpImportanceEstimator, NoOpMemoryEventStream,
        UniformImportanceEstimator,
    };
    use crate::model::{MemoryKind, Scope, Source};
    use crate::working_memory::{PlanOnlyReflectionExecutor, ReflectionExecutor, ReflectionPlan};
    use chrono::Utc;
    use uuid::Uuid;

    fn memory(id: &str, content: &str) -> Memory {
        Memory {
            id: id.to_string(),
            kind: MemoryKind::Fact,
            scope: Scope::Global,
            content: content.to_string(),
            source: Source::ExplicitUser,
            confidence: 1.0,
            importance: 0.0,
            valid_from: 0,
            valid_to: None,
            superseded_by: None,
            access_count: 0,
            last_accessed_at: None,
        }
    }

    #[test]
    fn noop_reflection_returns_empty_output() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = NoOpReflectionAlgorithm;
        let output = algorithm.reflect(&memory("m1", "hello"), &ctx);

        assert_eq!(
            output,
            ReflectionOutput::Skipped {
                target_memory_id: "m1".to_string(),
                reason: ReflectionSkipReason::NoOp,
            }
        );
        assert!(output.is_empty());
    }

    #[test]
    fn noop_reflection_is_deterministic() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = NoOpReflectionAlgorithm;
        let target = memory("m2", "same");

        let a = algorithm.reflect(&target, &ctx);
        let b = algorithm.reflect(&target, &ctx);

        assert_eq!(a, b);
    }

    #[test]
    fn noop_reflection_handles_empty_content() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = NoOpReflectionAlgorithm;
        let output = algorithm.reflect(&memory("empty", ""), &ctx);

        assert_eq!(
            output,
            ReflectionOutput::Skipped {
                target_memory_id: "empty".to_string(),
                reason: ReflectionSkipReason::NoOp,
            }
        );
    }

    #[test]
    fn noop_reflection_does_not_record_events() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = NoOpReflectionAlgorithm;

        let _ = algorithm.reflect(&memory("m3", "no side effects"), &ctx);

        assert!(ctx.events.recent(10).is_empty());
    }

    #[test]
    fn noop_reflection_algorithm_is_zero_sized() {
        assert_eq!(std::mem::size_of::<NoOpReflectionAlgorithm>(), 0);
    }

    #[test]
    fn reflection_output_serde_roundtrip() {
        let output = ReflectionOutput::Skipped {
            target_memory_id: "m4".to_string(),
            reason: ReflectionSkipReason::NoOp,
        };
        let json = serde_json::to_string(&output).unwrap();
        let decoded: ReflectionOutput = serde_json::from_str(&json).unwrap();
        assert_eq!(decoded, output);
    }

    #[test]
    fn deterministic_reference_produces_candidate_for_eligible_memory() {
        let importance = UniformImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = DeterministicReflectionAlgorithm::default();
        let output = algorithm.reflect(&memory("m5", "eligible"), &ctx);

        assert_eq!(
            output,
            ReflectionOutput::Candidate {
                target_memory_id: "m5".to_string(),
                importance: MemoryImportance {
                    overall: 0.5,
                    signals: crate::adaptive::ImportanceSignals::uniform(0.5),
                },
                evidence_count: 0,
            }
        );
    }

    #[test]
    fn deterministic_reference_skips_empty_content() {
        let importance = UniformImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = DeterministicReflectionAlgorithm::default();
        let output = algorithm.reflect(&memory("empty-reference", "  "), &ctx);

        assert_eq!(
            output,
            ReflectionOutput::Skipped {
                target_memory_id: "empty-reference".to_string(),
                reason: ReflectionSkipReason::EmptyContent,
            }
        );
    }

    #[test]
    fn deterministic_reference_skips_structurally_inert_memory() {
        let importance = UniformImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = DeterministicReflectionAlgorithm::default();
        let mut target = memory("m6", "superseded");
        target.superseded_by = Some("newer".to_string());

        assert_eq!(
            algorithm.reflect(&target, &ctx),
            ReflectionOutput::Skipped {
                target_memory_id: "m6".to_string(),
                reason: ReflectionSkipReason::StructurallyInert,
            }
        );
    }

    #[test]
    fn deterministic_reference_skips_low_importance() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = DeterministicReflectionAlgorithm::default();

        assert_eq!(
            algorithm.reflect(&memory("m7", "low importance"), &ctx),
            ReflectionOutput::Skipped {
                target_memory_id: "m7".to_string(),
                reason: ReflectionSkipReason::LowImportance,
            }
        );
    }

    #[test]
    fn deterministic_reference_counts_only_target_event_evidence() {
        let importance = UniformImportanceEstimator;
        let events = InMemoryMemoryEventStream::with_capacity(8);
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = DeterministicReflectionAlgorithm::default();

        events.record(MemoryEvent {
            id: MemoryEventId::nil(),
            timestamp: Utc::now(),
            session_id: None,
            kind: MemoryEventKind::Written,
            memory_ids: vec!["target".to_string()],
            payload: MemoryEventPayload::Empty,
        });
        events.record(MemoryEvent {
            id: MemoryEventId::nil(),
            timestamp: Utc::now(),
            session_id: None,
            kind: MemoryEventKind::Written,
            memory_ids: vec!["other".to_string()],
            payload: MemoryEventPayload::Empty,
        });
        events.record(MemoryEvent {
            id: MemoryEventId::nil(),
            timestamp: Utc::now(),
            session_id: None,
            kind: MemoryEventKind::Updated,
            memory_ids: vec!["target".to_string(), "related".to_string()],
            payload: MemoryEventPayload::Empty,
        });

        assert_eq!(
            algorithm.reflect(&memory("target", "has evidence"), &ctx),
            ReflectionOutput::Candidate {
                target_memory_id: "target".to_string(),
                importance: MemoryImportance {
                    overall: 0.5,
                    signals: crate::adaptive::ImportanceSignals::uniform(0.5),
                },
                evidence_count: 2,
            }
        );
    }

    #[test]
    fn deterministic_reference_is_reproducible() {
        let importance = UniformImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = DeterministicReflectionAlgorithm::default();
        let target = memory("m8", "same input");

        let a = algorithm.reflect(&target, &ctx);
        let b = algorithm.reflect(&target, &ctx);

        assert_eq!(a, b);
    }

    #[test]
    fn deterministic_reference_does_not_record_events() {
        let importance = UniformImportanceEstimator;
        let events = InMemoryMemoryEventStream::with_capacity(8);
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = DeterministicReflectionAlgorithm::default();

        let _ = algorithm.reflect(&memory("m9", "side effect check"), &ctx);

        assert!(ctx.events.recent(10).is_empty());
    }

    #[test]
    fn deterministic_reference_config_is_sanitized() {
        let algorithm = DeterministicReflectionAlgorithm::new(f32::NAN, 7);

        assert_eq!(algorithm.min_importance(), 0.5);
        assert_eq!(algorithm.recent_event_limit(), 7);
    }

    #[test]
    fn rule_based_reflection_produces_for_high_signal_failure() {
        let importance = UniformImportanceEstimator;
        let events = InMemoryMemoryEventStream::with_capacity(8);
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = RuleBasedReflectionAlgorithm::default();
        let mut target = memory("rule-failure", "Fix recurring JWT refresh error next time.");
        target.kind = MemoryKind::Failure;
        events.record(MemoryEvent {
            id: MemoryEventId::nil(),
            timestamp: Utc::now(),
            session_id: None,
            kind: MemoryEventKind::Updated,
            memory_ids: vec![target.id.clone()],
            payload: MemoryEventPayload::Empty,
        });

        let output = algorithm.reflect(&target, &ctx);

        assert!(matches!(
            output,
            ReflectionOutput::Produced {
                target_memory_id,
                payload_summary,
            } if target_memory_id == "rule-failure" && payload_summary.contains("failure")
        ));
    }

    #[test]
    fn rule_based_reflection_marks_medium_signal_memory_candidate() {
        let importance = UniformImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = RuleBasedReflectionAlgorithm::default();
        let mut target = memory("rule-pref", "User prefers concise handoff notes.");
        target.kind = MemoryKind::Preference;

        let output = algorithm.reflect(&target, &ctx);

        assert!(matches!(
            output,
            ReflectionOutput::Candidate {
                target_memory_id,
                evidence_count: 0,
                ..
            } if target_memory_id == "rule-pref"
        ));
    }

    #[test]
    fn rule_based_reflection_skips_low_signal_fact() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &importance, &events);
        let algorithm = RuleBasedReflectionAlgorithm::default();
        let target = memory("rule-low", "Plain static note.");

        assert_eq!(
            algorithm.reflect(&target, &ctx),
            ReflectionOutput::Skipped {
                target_memory_id: "rule-low".to_string(),
                reason: ReflectionSkipReason::LowImportance,
            }
        );
    }

    #[test]
    fn rule_based_reflection_config_is_sanitized_and_ordered() {
        let algorithm = RuleBasedReflectionAlgorithm::new(f32::NAN, 2.0, 9);

        assert_eq!(algorithm.produce_score(), 2.0);
        assert_eq!(algorithm.candidate_score(), 1.5);
        assert_eq!(algorithm.recent_event_limit(), 9);
    }

    #[test]
    fn candidate_output_maps_to_reflection_processing_event() {
        let now = Utc::now();
        let session_id = crate::working_memory::SessionId::new();
        let event_id = Uuid::nil();
        let output = ReflectionOutput::Candidate {
            target_memory_id: "target-memory".to_string(),
            importance: MemoryImportance {
                overall: 0.5,
                signals: crate::adaptive::ImportanceSignals::uniform(0.5),
            },
            evidence_count: 2,
        };

        let event = output
            .to_reflection_event_with_id(event_id, session_id, ReflectionSource::SystemSignal, now)
            .expect("candidate output should produce a reflection event");

        assert_eq!(event.id, event_id);
        assert_eq!(event.session_id, session_id);
        assert_eq!(event.timestamp, now);
        assert_eq!(event.source, ReflectionSource::SystemSignal);
        assert_eq!(event.payload.promoted, vec!["target-memory".to_string()]);
        assert!(event.payload.merged.is_empty());
        assert!(event.payload.discarded.is_empty());

        let report = PlanOnlyReflectionExecutor.execute(&ReflectionPlan {
            events: vec![event],
        });
        assert_eq!(report.statistics.processed, 1);
        assert_eq!(report.statistics.skipped, 0);
    }

    #[test]
    fn skipped_output_does_not_create_reflection_processing_event() {
        let now = Utc::now();
        let session_id = crate::working_memory::SessionId::new();
        let output = ReflectionOutput::Skipped {
            target_memory_id: "target-memory".to_string(),
            reason: ReflectionSkipReason::LowImportance,
        };

        assert!(output
            .to_reflection_event_with_id(
                Uuid::nil(),
                session_id,
                ReflectionSource::SystemSignal,
                now,
            )
            .is_none());
    }
}
