//! Adaptive Policy Dispatcher (P4.5.2).
//!
//! The dispatcher is a pure routing surface over frozen Policy traits.
//! It converts a `PolicyRequest` into a single `PolicyReport` deterministically,
//! without performing any execution, mutation, IO, or algorithmic decisions.

use serde::{Deserialize, Serialize};

use super::consolidation::MergeGroup;
use super::hebbian::EdgeUpdatePlan;
use super::item::MemoryId;
use super::policy::{
    AdaptivePolicy, ForgetPolicy, HebbianPolicy, MergePolicy, NoOpForgetPolicy, NoOpHebbianPolicy,
    NoOpMergePolicy, NoOpReflectionPolicy, PolicyDecision, ReflectionPolicy,
};
use super::reflection::ReflectionEvent;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum PolicyRequest {
    Reflection(ReflectionEvent),
    Hebbian(EdgeUpdatePlan),
    Forget(MemoryId),
    Merge(MergeGroup),
}

impl PolicyRequest {
    pub fn kind(&self) -> PolicyKind {
        match self {
            PolicyRequest::Reflection(_) => PolicyKind::Reflection,
            PolicyRequest::Hebbian(_) => PolicyKind::Hebbian,
            PolicyRequest::Forget(_) => PolicyKind::Forget,
            PolicyRequest::Merge(_) => PolicyKind::Merge,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PolicyKind {
    Reflection,
    Hebbian,
    Forget,
    Merge,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PolicyReport {
    pub policy: PolicyKind,
    pub decision: PolicyDecision,
    pub warnings: Vec<PolicyWarning>,
    pub statistics: PolicyStatistics,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyStatistics {
    pub evaluated: usize,
    pub executed: usize,
    pub skipped: usize,
    pub delayed: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyWarning {
    pub message: String,
}

pub trait AdaptivePolicyEngine {
    fn evaluate(&self, request: &PolicyRequest) -> PolicyReport;
}

pub struct NoOpAdaptivePolicyEngine;

impl AdaptivePolicyEngine for NoOpAdaptivePolicyEngine {
    fn evaluate(&self, request: &PolicyRequest) -> PolicyReport {
        report_from(request.kind(), PolicyDecision::Skip)
    }
}

pub struct DeterministicAdaptivePolicyEngine<R, H, F, M>
where
    R: ReflectionPolicy,
    H: HebbianPolicy,
    F: ForgetPolicy,
    M: MergePolicy,
{
    reflection: R,
    hebbian: H,
    forget: F,
    merge: M,
}

impl<R, H, F, M> DeterministicAdaptivePolicyEngine<R, H, F, M>
where
    R: ReflectionPolicy,
    H: HebbianPolicy,
    F: ForgetPolicy,
    M: MergePolicy,
{
    pub fn new(reflection: R, hebbian: H, forget: F, merge: M) -> Self {
        Self {
            reflection,
            hebbian,
            forget,
            merge,
        }
    }
}

impl<R, H, F, M> AdaptivePolicyEngine for DeterministicAdaptivePolicyEngine<R, H, F, M>
where
    R: ReflectionPolicy,
    H: HebbianPolicy,
    F: ForgetPolicy,
    M: MergePolicy,
{
    fn evaluate(&self, request: &PolicyRequest) -> PolicyReport {
        let (kind, decision) = match request {
            PolicyRequest::Reflection(event) => (
                PolicyKind::Reflection,
                <R as AdaptivePolicy<ReflectionEvent>>::evaluate(&self.reflection, event),
            ),
            PolicyRequest::Hebbian(plan) => (
                PolicyKind::Hebbian,
                <H as AdaptivePolicy<EdgeUpdatePlan>>::evaluate(&self.hebbian, plan),
            ),
            PolicyRequest::Forget(id) => (
                PolicyKind::Forget,
                <F as AdaptivePolicy<MemoryId>>::evaluate(&self.forget, id),
            ),
            PolicyRequest::Merge(group) => (
                PolicyKind::Merge,
                <M as AdaptivePolicy<MergeGroup>>::evaluate(&self.merge, group),
            ),
        };
        report_from(kind, decision)
    }
}

impl Default
    for DeterministicAdaptivePolicyEngine<
        NoOpReflectionPolicy,
        NoOpHebbianPolicy,
        NoOpForgetPolicy,
        NoOpMergePolicy,
    >
{
    fn default() -> Self {
        Self::new(
            NoOpReflectionPolicy,
            NoOpHebbianPolicy,
            NoOpForgetPolicy,
            NoOpMergePolicy,
        )
    }
}

fn report_from(policy: PolicyKind, decision: PolicyDecision) -> PolicyReport {
    let mut statistics = PolicyStatistics {
        evaluated: 1,
        ..PolicyStatistics::default()
    };
    match decision {
        PolicyDecision::Execute => statistics.executed = 1,
        PolicyDecision::Skip => statistics.skipped = 1,
        PolicyDecision::Delay => statistics.delayed = 1,
    }
    PolicyReport {
        policy,
        decision,
        warnings: Vec::new(),
        statistics,
    }
}
