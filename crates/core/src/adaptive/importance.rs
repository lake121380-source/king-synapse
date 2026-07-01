//! Memory Importance (RFC-011 Part A).
//!
//! Defines the shared importance data model consumed by every Phase 5
//! adaptive-memory algorithm. This module contains no algorithm logic; two
//! placeholder estimators (`NoOpImportanceEstimator`, `UniformImportanceEstimator`)
//! are provided to exercise the trait shape.
//!
//! Key invariants (see RFC-011 Part A):
//!
//! - `MemoryImportance::overall` is **not** the arithmetic mean of
//!   `signals`. It is the estimator's final judgement. Concrete estimators
//!   may combine signals non-linearly, apply weights, clip, or normalize.
//! - `ImportanceSignal` is for explainability, diagnostics, and metric
//!   mapping only. It MUST NOT appear as an input parameter to estimators.

use crate::adaptive::context::AlgorithmContext;
use crate::model::Memory;
use serde::{Deserialize, Serialize};

/// Individual importance signals, each normalized to `0.0 ..= 1.0`.
///
/// Marked `#[non_exhaustive]` so additional signals may be added in future
/// minor versions without a breaking change.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct ImportanceSignals {
    pub access_frequency: f32,
    pub recency: f32,
    pub reflection_score: f32,
    pub user_priority: f32,
    pub semantic_uniqueness: f32,
}

impl ImportanceSignals {
    /// All signals set to zero.
    pub const fn zero() -> Self {
        Self {
            access_frequency: 0.0,
            recency: 0.0,
            reflection_score: 0.0,
            user_priority: 0.0,
            semantic_uniqueness: 0.0,
        }
    }

    /// All signals set to the same value.
    pub const fn uniform(v: f32) -> Self {
        Self {
            access_frequency: v,
            recency: v,
            reflection_score: v,
            user_priority: v,
            semantic_uniqueness: v,
        }
    }
}

/// Composite importance value returned by an [`ImportanceEstimator`].
///
/// `overall` is the estimator's final judgement, `signals` is the breakdown
/// used for explainability. There is no required algebraic relationship
/// between `overall` and any function of `signals`.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct MemoryImportance {
    pub overall: f32,
    pub signals: ImportanceSignals,
}

impl MemoryImportance {
    /// Importance with `overall = 0.0` and all signals zero.
    pub const fn zero() -> Self {
        Self {
            overall: 0.0,
            signals: ImportanceSignals::zero(),
        }
    }
}

/// Identifier for an individual importance signal.
///
/// Used for explainability, diagnostics, and metric mapping only. It MUST
/// NOT be used as an input parameter to estimators or as a strategy
/// selector.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum ImportanceSignal {
    AccessFrequency,
    Recency,
    ReflectionScore,
    UserPriority,
    SemanticUniqueness,
}

/// Estimates the importance of a memory in an execution context.
///
/// Signature is closed at v0.5.1: `memory` is the evaluation target,
/// `ctx` is the environment. Future shared inputs are added to
/// `AlgorithmContext` under the Part C additive-data rule, never to this
/// trait.
pub trait ImportanceEstimator {
    fn estimate(&self, memory: &Memory, ctx: &AlgorithmContext<'_>) -> MemoryImportance;
}

/// Placeholder estimator that returns `MemoryImportance::zero()` for every
/// input.
#[derive(Debug, Clone, Copy, Default)]
pub struct NoOpImportanceEstimator;

impl ImportanceEstimator for NoOpImportanceEstimator {
    fn estimate(&self, _memory: &Memory, _ctx: &AlgorithmContext<'_>) -> MemoryImportance {
        MemoryImportance::zero()
    }
}

/// Placeholder estimator that returns `overall = 0.5` with every signal set
/// to `0.5`, independent of the memory content or context.
#[derive(Debug, Clone, Copy, Default)]
pub struct UniformImportanceEstimator;

impl ImportanceEstimator for UniformImportanceEstimator {
    fn estimate(&self, _memory: &Memory, _ctx: &AlgorithmContext<'_>) -> MemoryImportance {
        MemoryImportance {
            overall: 0.5,
            signals: ImportanceSignals::uniform(0.5),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::event_stream::NoOpMemoryEventStream;
    use crate::model::{Memory, MemoryKind, Scope, Source};
    use chrono::Utc;
    use std::mem::size_of;

    fn mem(text: &str) -> Memory {
        Memory {
            id: "test-id".to_string(),
            kind: MemoryKind::Fact,
            scope: Scope::Global,
            content: text.to_string(),
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
    fn noop_returns_zero() {
        let ctx_est = NoOpImportanceEstimator;
        let ctx_evs = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &ctx_est, &ctx_evs);
        let est = NoOpImportanceEstimator;
        let out = est.estimate(&mem("hello"), &ctx);
        assert_eq!(out, MemoryImportance::zero());
        assert_eq!(out.overall, 0.0);
        assert_eq!(out.signals.access_frequency, 0.0);
        assert_eq!(out.signals.recency, 0.0);
        assert_eq!(out.signals.reflection_score, 0.0);
        assert_eq!(out.signals.user_priority, 0.0);
        assert_eq!(out.signals.semantic_uniqueness, 0.0);
    }

    #[test]
    fn uniform_returns_half() {
        let ctx_est = NoOpImportanceEstimator;
        let ctx_evs = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &ctx_est, &ctx_evs);
        let est = UniformImportanceEstimator;
        let out = est.estimate(&mem("hello"), &ctx);
        assert_eq!(out.overall, 0.5);
        assert_eq!(out.signals, ImportanceSignals::uniform(0.5));
    }

    #[test]
    fn deterministic_for_same_inputs() {
        let ctx_est = NoOpImportanceEstimator;
        let ctx_evs = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &ctx_est, &ctx_evs);
        let est = UniformImportanceEstimator;
        let m = mem("same");
        let a = est.estimate(&m, &ctx);
        let b = est.estimate(&m, &ctx);
        assert_eq!(a, b);
    }

    #[test]
    fn uniform_independent_of_memory_content() {
        let ctx_est = NoOpImportanceEstimator;
        let ctx_evs = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &ctx_est, &ctx_evs);
        let est = UniformImportanceEstimator;
        let a = est.estimate(&mem("foo"), &ctx);
        let b = est.estimate(&mem("something completely different"), &ctx);
        assert_eq!(a, b);
    }

    #[test]
    fn memory_importance_serde_roundtrip() {
        let original = MemoryImportance {
            overall: 0.42,
            signals: ImportanceSignals {
                access_frequency: 0.1,
                recency: 0.2,
                reflection_score: 0.3,
                user_priority: 0.4,
                semantic_uniqueness: 0.5,
            },
        };
        let json = serde_json::to_string(&original).unwrap();
        let decoded: MemoryImportance = serde_json::from_str(&json).unwrap();
        assert_eq!(original, decoded);
    }

    #[test]
    fn signal_enum_covers_all_signal_fields() {
        // ImportanceSignal variants map 1:1 to ImportanceSignals numeric
        // fields. If a field is added to ImportanceSignals, a corresponding
        // variant must be added here.
        let variants = [
            ImportanceSignal::AccessFrequency,
            ImportanceSignal::Recency,
            ImportanceSignal::ReflectionScore,
            ImportanceSignal::UserPriority,
            ImportanceSignal::SemanticUniqueness,
        ];
        assert_eq!(variants.len(), 5);
    }

    #[test]
    fn estimators_are_zero_sized() {
        assert_eq!(size_of::<NoOpImportanceEstimator>(), 0);
        assert_eq!(size_of::<UniformImportanceEstimator>(), 0);
    }
}
