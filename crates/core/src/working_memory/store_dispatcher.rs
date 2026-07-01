use crate::working_memory::{
    ExecutedAction, ExecutionReport, MergeGroup, ReflectionEvent, ReflectionPlan, StoreMutation,
    StoreMutationPlan, WorkingMemoryItem,
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
            .flat_map(dispatch_action)
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

fn dispatch_action(action: &ExecutedAction) -> Vec<StoreMutation> {
    match action {
        ExecutedAction::Archive(action) => vec![StoreMutation::InsertMemory {
            id: action.item.id.to_string(),
            content: action.item.content.clone(),
        }],
        ExecutedAction::Merge(action) => dispatch_merge_lifecycle(&action.items),
        ExecutedAction::Discard(action) => vec![StoreMutation::ArchiveMemory {
            id: action.item.id.to_string(),
        }],
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
    let merged = event
        .payload
        .merged
        .iter()
        .flat_map(dispatch_merge_group_lifecycle);
    let discarded = event
        .payload
        .discarded
        .iter()
        .map(|id| StoreMutation::ArchiveMemory { id: id.clone() });

    promoted.chain(merged).chain(discarded).collect()
}

fn dispatch_merge_items(items: &[WorkingMemoryItem]) -> Option<StoreMutation> {
    let primary = primary_merge_memory_id(items)?;
    Some(StoreMutation::UpdateMemory {
        id: primary,
        content: merged_item_content(items),
    })
}

fn primary_merge_memory_id(items: &[WorkingMemoryItem]) -> Option<String> {
    items
        .iter()
        .find_map(|item| item.linked_memory_ids.first().cloned())
        .or_else(|| items.first().map(|item| item.id.to_string()))
}

fn merged_item_content(items: &[WorkingMemoryItem]) -> String {
    items
        .iter()
        .map(|item| item.content.as_str())
        .collect::<Vec<_>>()
        .join("\n")
}

fn dispatch_superseded_merge_items(
    items: &[WorkingMemoryItem],
) -> impl Iterator<Item = StoreMutation> + '_ {
    let primary = primary_merge_memory_id(items);
    items
        .iter()
        .flat_map(|item| item.linked_memory_ids.iter())
        .filter(move |id| Some((*id).as_str()) != primary.as_deref())
        .cloned()
        .map(|id| StoreMutation::ArchiveMemory { id })
}

fn dispatch_merge_lifecycle(items: &[WorkingMemoryItem]) -> Vec<StoreMutation> {
    let Some(update) = dispatch_merge_items(items) else {
        return Vec::new();
    };
    std::iter::once(update)
        .chain(dispatch_superseded_merge_items(items))
        .collect()
}

fn dispatch_merge_group_lifecycle(group: &MergeGroup) -> Vec<StoreMutation> {
    dispatch_merge_lifecycle(&group.items)
}
