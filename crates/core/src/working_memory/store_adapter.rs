use serde::{Deserialize, Serialize};

pub trait StoreAdapter {
    fn execute(&self, plan: &StoreMutationPlan) -> StoreExecutionReport;
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct StoreMutationPlan {
    pub mutations: Vec<StoreMutation>,
}

impl StoreMutationPlan {
    pub fn is_empty(&self) -> bool {
        self.mutations.is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum StoreMutation {
    InsertMemory {
        id: String,
        content: String,
    },
    UpdateMemory {
        id: String,
        content: String,
    },
    DeleteMemory {
        id: String,
    },
    ArchiveMemory {
        id: String,
    },
    UpdateEdge {
        source: String,
        target: String,
        weight_delta: f32,
    },
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct StoreExecutionReport {
    pub executed: Vec<StoreMutation>,
}

impl StoreExecutionReport {
    pub fn is_empty(&self) -> bool {
        self.executed.is_empty()
    }
}

pub struct NoOpStoreAdapter;

impl StoreAdapter for NoOpStoreAdapter {
    fn execute(&self, _plan: &StoreMutationPlan) -> StoreExecutionReport {
        StoreExecutionReport::default()
    }
}

pub struct PlanOnlyStoreAdapter;

impl StoreAdapter for PlanOnlyStoreAdapter {
    fn execute(&self, plan: &StoreMutationPlan) -> StoreExecutionReport {
        StoreExecutionReport {
            executed: plan.mutations.clone(),
        }
    }
}
