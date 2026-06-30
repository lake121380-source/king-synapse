use crate::working_memory::SessionId;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use uuid::Uuid;

pub type MemoryId = String;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WorkingMemoryItem {
    pub id: Uuid,
    pub session_id: SessionId,
    pub content: String,
    pub linked_memory_ids: Vec<MemoryId>,
    pub created_at: DateTime<Utc>,
    pub ttl: Duration,
}

impl WorkingMemoryItem {
    pub fn new(
        session_id: SessionId,
        content: impl Into<String>,
        linked_memory_ids: Vec<MemoryId>,
        ttl: Duration,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            session_id,
            content: content.into(),
            linked_memory_ids,
            created_at: Utc::now(),
            ttl,
        }
    }

    pub fn is_expired_at(&self, now: DateTime<Utc>) -> bool {
        match chrono::Duration::from_std(self.ttl) {
            Ok(ttl) => self.created_at + ttl <= now,
            Err(_) => false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WorkingMemoryEdge {
    pub from: MemoryId,
    pub to: MemoryId,
    pub weight: f32,
}
