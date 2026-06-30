use crate::working_memory::{MemoryId, SessionId, WorkingMemoryEdge, WorkingMemoryItem};
use chrono::{DateTime, Utc};
use std::collections::HashMap;

#[derive(Debug, Default)]
pub struct WorkingMemoryBuffer {
    items: HashMap<SessionId, Vec<WorkingMemoryItem>>,
    edges: HashMap<SessionId, Vec<WorkingMemoryEdge>>,
}

impl WorkingMemoryBuffer {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add(&mut self, session: SessionId, item: WorkingMemoryItem) {
        self.items.entry(session).or_default().push(item);
    }

    pub fn get_session(&self, session: SessionId) -> &[WorkingMemoryItem] {
        self.items.get(&session).map(Vec::as_slice).unwrap_or(&[])
    }

    pub fn link(&mut self, session: SessionId, a: MemoryId, b: MemoryId) {
        self.edges
            .entry(session)
            .or_default()
            .push(WorkingMemoryEdge {
                from: a,
                to: b,
                weight: 1.0,
            });
    }

    pub fn get_edges(&self, session: SessionId) -> &[WorkingMemoryEdge] {
        self.edges.get(&session).map(Vec::as_slice).unwrap_or(&[])
    }

    pub fn clear_expired(&mut self, now: DateTime<Utc>) {
        self.items.retain(|_, items| {
            items.retain(|item| !item.is_expired_at(now));
            !items.is_empty()
        });
    }
}
