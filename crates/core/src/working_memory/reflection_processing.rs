use crate::working_memory::{ReflectionEvent, ReflectionEventId};
use serde::{Deserialize, Serialize};

pub trait ReflectionEngine {
    fn plan(&self, events: &[ReflectionEvent]) -> ReflectionPlan;
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ReflectionPlan {
    pub events: Vec<ReflectionEvent>,
}

impl ReflectionPlan {
    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }
}

pub trait ReflectionExecutor {
    fn execute(&self, plan: &ReflectionPlan) -> ReflectionReport;
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ReflectionReport {
    pub processed_events: Vec<ReflectionEventId>,
}

impl ReflectionReport {
    pub fn is_empty(&self) -> bool {
        self.processed_events.is_empty()
    }
}

pub struct NoOpReflectionEngine;

impl ReflectionEngine for NoOpReflectionEngine {
    fn plan(&self, _events: &[ReflectionEvent]) -> ReflectionPlan {
        ReflectionPlan::default()
    }
}

pub struct PlanOnlyReflectionExecutor;

impl ReflectionExecutor for PlanOnlyReflectionExecutor {
    fn execute(&self, plan: &ReflectionPlan) -> ReflectionReport {
        ReflectionReport {
            processed_events: plan.events.iter().map(|event| event.id).collect(),
        }
    }
}
