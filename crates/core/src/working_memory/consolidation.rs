use crate::working_memory::{WorkingMemoryBuffer, WorkingMemoryItem};
use serde::{Deserialize, Serialize};

pub trait ConsolidationEngine {
    fn consolidate(&self, session: &WorkingMemoryBuffer) -> ConsolidationPlan;
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ConsolidationPlan {
    pub promote: Vec<WorkingMemoryItem>,
    pub merge: Vec<MergeGroup>,
    pub discard: Vec<WorkingMemoryItem>,
}

impl ConsolidationPlan {
    pub fn is_empty(&self) -> bool {
        self.promote.is_empty() && self.merge.is_empty() && self.discard.is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MergeGroup {
    pub items: Vec<WorkingMemoryItem>,
    pub strategy: MergeStrategy,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MergeStrategy {
    Deduplicate,
    Union,
    Compress,
}

pub struct NoOpConsolidation;

impl ConsolidationEngine for NoOpConsolidation {
    fn consolidate(&self, _session: &WorkingMemoryBuffer) -> ConsolidationPlan {
        ConsolidationPlan::default()
    }
}
