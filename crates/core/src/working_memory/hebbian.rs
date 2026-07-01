use crate::working_memory::ReflectionEvent;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EdgeUpdatePlan {
    pub source: String,
    pub target: String,
    pub weight_delta: f32,
}

pub trait HebbianExecutor {
    fn execute(&self, plans: &[EdgeUpdatePlan]) -> HebbianExecutionReport;
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct HebbianExecutionReport {
    pub planned_updates: Vec<EdgeUpdatePlan>,
}

impl HebbianExecutionReport {
    pub fn is_empty(&self) -> bool {
        self.planned_updates.is_empty()
    }
}

pub trait HebbianReinforcementEngine {
    fn reinforce(&self, event: &ReflectionEvent) -> Vec<EdgeUpdatePlan>;
}

pub struct NoOpHebbianReinforcementEngine;

impl HebbianReinforcementEngine for NoOpHebbianReinforcementEngine {
    fn reinforce(&self, _event: &ReflectionEvent) -> Vec<EdgeUpdatePlan> {
        Vec::new()
    }
}

pub struct NoOpHebbianExecutor;

impl HebbianExecutor for NoOpHebbianExecutor {
    fn execute(&self, _plans: &[EdgeUpdatePlan]) -> HebbianExecutionReport {
        HebbianExecutionReport::default()
    }
}

pub struct PlanOnlyHebbianExecutor;

impl HebbianExecutor for PlanOnlyHebbianExecutor {
    fn execute(&self, plans: &[EdgeUpdatePlan]) -> HebbianExecutionReport {
        HebbianExecutionReport {
            planned_updates: plans.to_vec(),
        }
    }
}
