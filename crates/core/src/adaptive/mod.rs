//! Adaptive Memory Common Model (RFC-011).
//!
//! This module defines the shared data model consumed by every Phase 5
//! adaptive-memory algorithm. It does not implement any algorithm.
//!
//! v0.5.1 shipped Memory Importance and a minimal `AlgorithmContext`.
//! v0.5.2 closes the trait-object surface by adding `MemoryEvent`,
//! `MemoryEventStream`, and the `importance` / `events` fields on
//! `AlgorithmContext<'a>`. Per RFC-011 Part C rule 3, no further service
//! dependencies may be added to `AlgorithmContext` after v0.5.2.

pub mod cognitive_booster;
pub mod cognitive_trace;
pub mod competition;
pub mod context;
pub mod event;
pub mod event_stream;
pub mod forget;
pub mod hebbian;
pub mod importance;
pub mod merge;
pub mod reflection;
pub mod temporal;

pub use cognitive_booster::{
    CognitiveAdjustedScore, CognitiveBooster, CognitiveBoosterConfig, CognitiveBoosterConfigError,
    CognitiveBoosterInput, CognitiveBoosterMode, CognitiveBoosterOutput,
    DeterministicCognitiveBoosterV0, NoOpCognitiveBooster, MAX_COGNITIVE_BOOSTER_BONUS,
};
pub use cognitive_trace::{
    CognitiveCompetitionTrace, CognitiveFactor, CognitiveFactorType, CognitiveTraceEvaluator,
};
pub use competition::{
    MemoryCandidate, MemoryCompetition, MemoryCompetitionReport, MemoryCompetitionState,
    MemoryCompetitionTraceStep, RuleBasedMemoryCompetition,
};
pub use context::AlgorithmContext;
pub use event::{MemoryEvent, MemoryEventId, MemoryEventKind, MemoryEventPayload};
pub use event_stream::{InMemoryMemoryEventStream, MemoryEventStream, NoOpMemoryEventStream};
pub use forget::{
    ForgetAlgorithm, ForgetOutput, ForgetReason, ForgetSkipReason, ForgetTarget,
    NoOpForgetAlgorithm, RuleBasedForgetAlgorithm,
};
pub use hebbian::{
    HebbianAlgorithm, HebbianOutput, HebbianSkipReason, HebbianTarget, NoOpHebbianAlgorithm,
    RuleBasedHebbianAlgorithm,
};
pub use importance::{
    ImportanceEstimator, ImportanceSignal, ImportanceSignals, MemoryImportance,
    NoOpImportanceEstimator, UniformImportanceEstimator,
};
pub use merge::{
    MergeAlgorithm, MergeOutput, MergeSkipReason, MergeTarget, NoOpMergeAlgorithm,
    RuleBasedMergeAlgorithm,
};
pub use reflection::{
    DeterministicReflectionAlgorithm, NoOpReflectionAlgorithm, ReflectionAlgorithm,
    ReflectionOutput, ReflectionSkipReason, RuleBasedReflectionAlgorithm,
};
pub use temporal::{
    MemoryInfluenceState, ReactivationDecision, RuleBasedTemporalReactivationPolicy,
    RuleBasedTemporalSupersessionPolicy, RuleBasedTemporalTransitionEngine, SupersessionDecision,
    TemporalEvent, TemporalMemoryProfile, TemporalReactivationPolicy, TemporalSupersessionPolicy,
    TemporalTransitionEngine, TemporalTransitionReport, TemporalTransitionStep,
};
