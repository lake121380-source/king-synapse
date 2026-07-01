use crate::working_memory::{ReflectionEvent, ReflectionEventId, ReflectionSource};
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
    pub executed_actions: Vec<ReflectionAction>,
    pub skipped_actions: Vec<SkippedReflectionAction>,
    pub warnings: Vec<ReflectionWarning>,
    pub statistics: ReflectionStatistics,
}

impl ReflectionReport {
    pub fn is_empty(&self) -> bool {
        self.executed_actions.is_empty() && self.skipped_actions.is_empty()
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReflectionStatistics {
    pub processed: usize,
    pub skipped: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReflectionWarning {
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReflectionAction {
    Record(ReflectionRecord),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum SkippedReflectionAction {
    EmptyPayload(ReflectionRecord),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReflectionRecord {
    pub event_id: ReflectionEventId,
    pub source: ReflectionSource,
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
        let mut report = ReflectionReport::default();

        for event in &plan.events {
            dispatch_event(event, &mut report);
        }

        report
    }
}

fn dispatch_event(event: &ReflectionEvent, report: &mut ReflectionReport) {
    let record = ReflectionRecord {
        event_id: event.id,
        source: event.source,
    };

    if event.payload.is_empty() {
        report
            .skipped_actions
            .push(SkippedReflectionAction::EmptyPayload(record));
        report.warnings.push(ReflectionWarning {
            message: "skipped empty reflection payload".to_string(),
        });
        report.statistics.skipped += 1;
        return;
    }

    report
        .executed_actions
        .push(ReflectionAction::Record(record));
    report.statistics.processed += 1;
}
