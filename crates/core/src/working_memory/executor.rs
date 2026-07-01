use crate::working_memory::{ConsolidationPlan, MergeGroup, MergeStrategy, WorkingMemoryItem};
use serde::{Deserialize, Serialize};

pub trait ConsolidationExecutor {
    fn execute(&self, plan: &ConsolidationPlan) -> ExecutionReport;
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ExecutionReport {
    pub executed: Vec<ExecutedAction>,
    pub skipped: Vec<SkippedAction>,
}

impl ExecutionReport {
    pub fn is_empty(&self) -> bool {
        self.executed.is_empty() && self.skipped.is_empty()
    }
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
        let mut executed =
            Vec::with_capacity(plan.promote.len() + plan.merge.len() + plan.discard.len());

        for item in &plan.promote {
            executed.push(ExecutedAction::Archive(ArchiveExecution {
                item: item.clone(),
            }));
        }

        for MergeGroup { items, strategy } in &plan.merge {
            executed.push(ExecutedAction::Merge(MergeExecution {
                items: items.clone(),
                strategy: *strategy,
            }));
        }

        for item in &plan.discard {
            executed.push(ExecutedAction::Discard(DiscardExecution {
                item: item.clone(),
            }));
        }

        ExecutionReport {
            executed,
            skipped: Vec::new(),
        }
    }
}
