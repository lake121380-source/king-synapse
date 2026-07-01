//! Adaptive Memory Common Model (RFC-011).
//!
//! This module defines the shared data model consumed by every Phase 5
//! adaptive-memory algorithm. It does not implement any algorithm.
//!
//! v0.5.1 scope: Memory Importance + a minimal `AlgorithmContext` that carries
//! only `now` and `session_id`. Event stream, event types, and the
//! trait-object fields of `AlgorithmContext` (`importance`, `events`) are
//! introduced additively in v0.5.2 under `#[non_exhaustive]`.

pub mod context;
pub mod importance;

pub use context::AlgorithmContext;
pub use importance::{
    ImportanceEstimator, ImportanceSignal, ImportanceSignals, MemoryImportance,
    NoOpImportanceEstimator, UniformImportanceEstimator,
};
