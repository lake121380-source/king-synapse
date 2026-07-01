use crate::working_memory::{ConsolidationPlan, MergeGroup, MergeStrategy, WorkingMemoryItem};
use serde::{Deserialize, Serialize};

pub trait ConsolidationExecutor {
    fn execute(&self, plan: &ConsolidationPlan) -> ExecutionReport;
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ExecutionReport {
    pub executed_actions: Vec<ExecutedAction>,
    pub skipped_actions: Vec<SkippedAction>,
    pub warnings: Vec<ExecutionWarning>,
    pub statistics: ExecutionStatistics,
}

impl ExecutionReport {
    pub fn is_empty(&self) -> bool {
        self.executed_actions.is_empty() && self.skipped_actions.is_empty()
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionStatistics {
    pub merged: usize,
    pub archived: usize,
    pub discarded: usize,
    pub skipped: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionWarning {
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ExecutedAction {
    Archive(ArchiveExecution),
    Merge(MergeExecution),
    Discard(DiscardExecution),
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum SkippedAction {
    Archive(ArchiveExecution),
    Merge(MergeExecution),
    Discard(DiscardExecution),
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ArchiveExecution {
    pub item: WorkingMemoryItem,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MergeExecution {
    pub items: Vec<WorkingMemoryItem>,
    pub strategy: MergeStrategy,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DiscardExecution {
    pub item: WorkingMemoryItem,
}

pub struct PlanOnlyConsolidationExecutor;

impl ConsolidationExecutor for PlanOnlyConsolidationExecutor {
    fn execute(&self, plan: &ConsolidationPlan) -> ExecutionReport {
        let mut report = ExecutionReport {
            executed_actions: Vec::with_capacity(
                plan.promote.len() + plan.merge.len() + plan.discard.len(),
            ),
            skipped_actions: Vec::new(),
            warnings: Vec::new(),
            statistics: ExecutionStatistics::default(),
        };

        for item in &plan.promote {
            dispatch_archive(item, &mut report);
        }

        for group in &plan.merge {
            dispatch_merge(group, &mut report);
        }

        for item in &plan.discard {
            dispatch_discard(item, &mut report);
        }

        report
    }
}

fn dispatch_archive(item: &WorkingMemoryItem, report: &mut ExecutionReport) {
    report
        .executed_actions
        .push(ExecutedAction::Archive(ArchiveExecution {
            item: item.clone(),
        }));
    report.statistics.archived += 1;
}

fn dispatch_merge(group: &MergeGroup, report: &mut ExecutionReport) {
    if group.items.is_empty() {
        let action = MergeExecution {
            items: Vec::new(),
            strategy: group.strategy,
        };
        report.skipped_actions.push(SkippedAction::Merge(action));
        report.warnings.push(ExecutionWarning {
            message: "skipped empty merge group".to_string(),
        });
        report.statistics.skipped += 1;
        return;
    }

    report
        .executed_actions
        .push(ExecutedAction::Merge(MergeExecution {
            items: group.items.clone(),
            strategy: group.strategy,
        }));
    report.statistics.merged += 1;
}

fn dispatch_discard(item: &WorkingMemoryItem, report: &mut ExecutionReport) {
    report
        .executed_actions
        .push(ExecutedAction::Discard(DiscardExecution {
            item: item.clone(),
        }));
    report.statistics.discarded += 1;
}
