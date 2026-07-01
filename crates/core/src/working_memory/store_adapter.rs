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
    pub skipped: Vec<SkippedStoreMutation>,
    pub warnings: Vec<StoreExecutionWarning>,
    pub statistics: StoreExecutionStatistics,
}

impl StoreExecutionReport {
    pub fn is_empty(&self) -> bool {
        self.executed.is_empty() && self.skipped.is_empty()
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct StoreExecutionStatistics {
    pub executed: usize,
    pub skipped: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StoreExecutionWarning {
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum SkippedStoreMutation {
    Failed(StoreMutation),
    Unsupported(StoreMutation),
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
        let mut report = StoreExecutionReport {
            executed: plan.mutations.clone(),
            skipped: Vec::new(),
            warnings: Vec::new(),
            statistics: StoreExecutionStatistics::default(),
        };
        report.statistics.executed = report.executed.len();
        report
    }
}
