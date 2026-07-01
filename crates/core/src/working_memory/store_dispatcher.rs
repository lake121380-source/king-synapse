use crate::working_memory::{ExecutedAction, ExecutionReport, StoreMutation, StoreMutationPlan};

pub trait StoreMutationDispatcher {
    fn dispatch(&self) -> StoreMutationPlan;
}

pub struct NoOpStoreMutationDispatcher;

impl StoreMutationDispatcher for NoOpStoreMutationDispatcher {
    fn dispatch(&self) -> StoreMutationPlan {
        StoreMutationPlan::default()
    }
}

pub struct DeterministicStoreMutationDispatcher {
    report: ExecutionReport,
}

impl DeterministicStoreMutationDispatcher {
    pub fn new(report: ExecutionReport) -> Self {
        Self { report }
    }
}

impl StoreMutationDispatcher for DeterministicStoreMutationDispatcher {
    fn dispatch(&self) -> StoreMutationPlan {
        let mutations = self
            .report
            .executed_actions
            .iter()
            .filter_map(dispatch_action)
            .collect();

        StoreMutationPlan { mutations }
    }
}

fn dispatch_action(action: &ExecutedAction) -> Option<StoreMutation> {
    match action {
        ExecutedAction::Archive(action) => Some(StoreMutation::InsertMemory {
            id: action.item.id.to_string(),
            content: action.item.content.clone(),
        }),
        ExecutedAction::Merge(action) => {
            if action.items.is_empty() {
                return None;
            }

            let primary = &action.items[0];
            Some(StoreMutation::UpdateMemory {
                id: primary.id.to_string(),
                content: action
                    .items
                    .iter()
                    .map(|item| item.content.as_str())
                    .collect::<Vec<_>>()
                    .join("\n"),
            })
        }
        ExecutedAction::Discard(action) => Some(StoreMutation::ArchiveMemory {
            id: action.item.id.to_string(),
        }),
    }
}
