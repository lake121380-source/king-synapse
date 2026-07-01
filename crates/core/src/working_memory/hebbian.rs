use crate::working_memory::ReflectionEvent;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

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
    pub executed_actions: Vec<ExecutedEdgeUpdate>,
    pub skipped_actions: Vec<SkippedEdgeUpdate>,
    pub warnings: Vec<HebbianExecutionWarning>,
    pub statistics: HebbianExecutionStatistics,
}

impl HebbianExecutionReport {
    pub fn is_empty(&self) -> bool {
        self.executed_actions.is_empty() && self.skipped_actions.is_empty()
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct HebbianExecutionStatistics {
    pub executed: usize,
    pub skipped: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HebbianExecutionWarning {
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ExecutedEdgeUpdate {
    Apply(EdgeUpdatePlan),
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum SkippedEdgeUpdate {
    Invalid(EdgeUpdatePlan),
    Duplicate(EdgeUpdatePlan),
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
        let mut report = HebbianExecutionReport::default();
        let mut seen_edges = HashSet::new();

        for plan in plans {
            dispatch_edge_update(plan, &mut seen_edges, &mut report);
        }

        report
    }
}

fn dispatch_edge_update(
    plan: &EdgeUpdatePlan,
    seen_edges: &mut HashSet<(String, String)>,
    report: &mut HebbianExecutionReport,
) {
    if plan.source.is_empty() || plan.target.is_empty() || !plan.weight_delta.is_finite() {
        report
            .skipped_actions
            .push(SkippedEdgeUpdate::Invalid(plan.clone()));
        report.warnings.push(HebbianExecutionWarning {
            message: "skipped invalid edge update".to_string(),
        });
        report.statistics.skipped += 1;
        return;
    }

    let edge = (plan.source.clone(), plan.target.clone());
    if !seen_edges.insert(edge) {
        report
            .skipped_actions
            .push(SkippedEdgeUpdate::Duplicate(plan.clone()));
        report.warnings.push(HebbianExecutionWarning {
            message: "skipped duplicate edge update".to_string(),
        });
        report.statistics.skipped += 1;
        return;
    }

    report
        .executed_actions
        .push(ExecutedEdgeUpdate::Apply(plan.clone()));
    report.statistics.executed += 1;
}
