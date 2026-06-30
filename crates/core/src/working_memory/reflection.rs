use crate::working_memory::{MemoryId, MergeGroup, SessionId};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub type ReflectionEventId = Uuid;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReflectionEvent {
    pub id: ReflectionEventId,
    pub session_id: SessionId,
    pub timestamp: DateTime<Utc>,
    pub source: ReflectionSource,
    pub payload: ReflectionPayload,
}

impl ReflectionEvent {
    pub fn new(
        session_id: SessionId,
        source: ReflectionSource,
        payload: ReflectionPayload,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            session_id,
            timestamp: Utc::now(),
            source,
            payload,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReflectionSource {
    ConsolidationPlan,
    WorkingMemorySnapshot,
    SystemSignal,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ReflectionPayload {
    pub promoted: Vec<MemoryId>,
    pub merged: Vec<MergeGroup>,
    pub discarded: Vec<MemoryId>,
}

impl ReflectionPayload {
    pub fn is_empty(&self) -> bool {
        self.promoted.is_empty() && self.merged.is_empty() && self.discarded.is_empty()
    }
}

pub trait ReflectionEventRecorder {
    fn record(&mut self, event: ReflectionEvent);

    fn events(&self) -> &[ReflectionEvent];
}

#[derive(Debug, Default)]
pub struct NoOpReflectionEventRecorder;

impl ReflectionEventRecorder for NoOpReflectionEventRecorder {
    fn record(&mut self, _event: ReflectionEvent) {}

    fn events(&self) -> &[ReflectionEvent] {
        &[]
    }
}

#[derive(Debug, Default)]
pub struct InMemoryReflectionEventStream {
    events: Vec<ReflectionEvent>,
}

impl InMemoryReflectionEventStream {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn clear(&mut self) {
        self.events.clear();
    }
}

impl ReflectionEventRecorder for InMemoryReflectionEventStream {
    fn record(&mut self, event: ReflectionEvent) {
        self.events.push(event);
    }

    fn events(&self) -> &[ReflectionEvent] {
        &self.events
    }
}
