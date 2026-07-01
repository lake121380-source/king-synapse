use crate::working_memory::{
    ExecutedAction, ExecutionReport, MergeGroup, ReflectionEvent, ReflectionPlan, StoreMutation,
    StoreMutationPlan,
};

const REFLECTION_EDGE_DELTA: f32 = 0.1;

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

pub struct DeterministicReflectionStoreMutationDispatcher {
    plan: ReflectionPlan,
}

impl DeterministicReflectionStoreMutationDispatcher {
    pub fn new(plan: ReflectionPlan) -> Self {
        Self { plan }
    }
}

impl StoreMutationDispatcher for DeterministicReflectionStoreMutationDispatcher {
    fn dispatch(&self) -> StoreMutationPlan {
        let mutations = self
            .plan
            .events
            .iter()
            .flat_map(dispatch_reflection_event)
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

fn dispatch_reflection_event(event: &ReflectionEvent) -> Vec<StoreMutation> {
    let reflection_node = format!("reflection:{}", event.id);
    let promoted = event
        .payload
        .promoted
        .iter()
        .map(|target| StoreMutation::UpdateEdge {
            source: reflection_node.clone(),
            target: target.clone(),
            weight_delta: REFLECTION_EDGE_DELTA,
        });
    let merged = event.payload.merged.iter().filter_map(dispatch_merge_group);
    let discarded = event
        .payload
        .discarded
        .iter()
        .map(|id| StoreMutation::ArchiveMemory { id: id.clone() });

    promoted.chain(merged).chain(discarded).collect()
}

fn dispatch_merge_group(group: &MergeGroup) -> Option<StoreMutation> {
    let primary = group.items.first()?;
    Some(StoreMutation::UpdateMemory {
        id: primary.id.to_string(),
        content: group
            .items
            .iter()
            .map(|item| item.content.as_str())
            .collect::<Vec<_>>()
            .join("\n"),
    })
}
