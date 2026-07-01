//! Adaptive Policy Layer skeleton (P4.5.1).
//!
//! Policies decide **whether** frozen Adaptive Memory capabilities should run.
//! They never mutate memory, never touch Store, Recall, or LLMs, and never
//! perform execution. Concrete algorithms are out of scope for this skeleton.

use serde::{Deserialize, Serialize};

use super::consolidation::MergeGroup;
use super::hebbian::EdgeUpdatePlan;
use super::item::MemoryId;
use super::reflection::ReflectionEvent;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PolicyDecision {
    Execute,
    Skip,
    Delay,
}

pub trait AdaptivePolicy<I> {
    fn evaluate(&self, input: &I) -> PolicyDecision;
}

pub trait ReflectionPolicy: AdaptivePolicy<ReflectionEvent> {}

pub trait HebbianPolicy: AdaptivePolicy<EdgeUpdatePlan> {}

pub trait ForgetPolicy: AdaptivePolicy<MemoryId> {}

pub trait MergePolicy: AdaptivePolicy<MergeGroup> {}

pub struct NoOpReflectionPolicy;

impl AdaptivePolicy<ReflectionEvent> for NoOpReflectionPolicy {
    fn evaluate(&self, _input: &ReflectionEvent) -> PolicyDecision {
        PolicyDecision::Execute
    }
}

impl ReflectionPolicy for NoOpReflectionPolicy {}

pub struct NoOpHebbianPolicy;

impl AdaptivePolicy<EdgeUpdatePlan> for NoOpHebbianPolicy {
    fn evaluate(&self, _input: &EdgeUpdatePlan) -> PolicyDecision {
        PolicyDecision::Execute
    }
}

impl HebbianPolicy for NoOpHebbianPolicy {}

pub struct NoOpForgetPolicy;

impl AdaptivePolicy<MemoryId> for NoOpForgetPolicy {
    fn evaluate(&self, _input: &MemoryId) -> PolicyDecision {
        PolicyDecision::Skip
    }
}

impl ForgetPolicy for NoOpForgetPolicy {}

pub struct NoOpMergePolicy;

impl AdaptivePolicy<MergeGroup> for NoOpMergePolicy {
    fn evaluate(&self, _input: &MergeGroup) -> PolicyDecision {
        PolicyDecision::Execute
    }
}

impl MergePolicy for NoOpMergePolicy {}
