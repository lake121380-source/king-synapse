//! Memory Event data model (RFC-011 Part B).
//!
//! Defines `MemoryEventId`, `MemoryEvent`, `MemoryEventKind`, and
//! `MemoryEventPayload`. Events are immutable value types; stream storage
//! and replay live in `event_stream.rs`.

use crate::working_memory::{MemoryId, ReflectionEventId, SessionId};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Opaque identifier for a `MemoryEvent`.
///
/// Newtype around `Uuid` so the backing generator (Uuid v4, ULID, Snowflake,
/// database ID, ...) can be swapped without touching consumers.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct MemoryEventId(pub Uuid);

impl MemoryEventId {
    /// Generate a fresh v4 UUID-backed id.
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }

    /// Nil id (all zeros); useful for tests and placeholder values.
    pub const fn nil() -> Self {
        Self(Uuid::nil())
    }
}

impl Default for MemoryEventId {
    fn default() -> Self {
        Self::new()
    }
}

/// Kind of a memory event.
///
/// All names are past tense — every event describes something that has
/// already happened. `#[non_exhaustive]` so new kinds may be added in
/// future minor versions without breaking downstream `match` arms.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum MemoryEventKind {
    Recalled,
    Written,
    Updated,
    Invalidated,
    Reflected,
    Reinforced,
    MergeCompleted,
    Forgotten,
}

/// Structured payload attached to a `MemoryEvent`.
///
/// Not every `MemoryEventKind` needs a matching variant: `Written`,
/// `Updated`, and `Invalidated` carry no extra data beyond `memory_ids`
/// and use `Empty`. `Empty` is named (not `None`) to avoid visual
/// collision with `Option::None`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub enum MemoryEventPayload {
    Empty,
    Recalled {
        query: String,
        hit_count: usize,
    },
    Reflected {
        reflection_event_id: ReflectionEventId,
    },
    Reinforced {
        edge_key: String,
        delta: f32,
    },
    MergeCompleted {
        into: MemoryId,
    },
    Forgotten {
        reason: String,
    },
}

/// An append-only record of something that happened in the memory system.
///
/// `memory_ids` is a `Vec<MemoryId>`, never `Option`: single-target events
/// use a one-element vector; multi-target events (e.g. `MergeCompleted`)
/// use the full list; events unrelated to any memory use an empty vector.
/// This uniform shape lets consumers iterate `memory_ids` without
/// special-casing kinds.
///
/// `MemoryEvent` is a plain data struct (not `#[non_exhaustive]`) — its
/// field list is closed at v0.5.2. Extensions ride on
/// `MemoryEventPayload`, which is `#[non_exhaustive]`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MemoryEvent {
    pub id: MemoryEventId,
    pub timestamp: DateTime<Utc>,
    pub session_id: Option<SessionId>,
    pub kind: MemoryEventKind,
    pub memory_ids: Vec<MemoryId>,
    pub payload: MemoryEventPayload,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ev(kind: MemoryEventKind) -> MemoryEvent {
        MemoryEvent {
            id: MemoryEventId::nil(),
            timestamp: Utc::now(),
            session_id: None,
            kind,
            memory_ids: Vec::new(),
            payload: MemoryEventPayload::Empty,
        }
    }

    #[test]
    fn event_id_nil_is_zero_uuid() {
        assert_eq!(MemoryEventId::nil().0, Uuid::nil());
    }

    #[test]
    fn event_id_new_is_unique() {
        let a = MemoryEventId::new();
        let b = MemoryEventId::new();
        assert_ne!(a, b);
    }

    #[test]
    fn event_id_default_uses_new() {
        let a: MemoryEventId = Default::default();
        assert_ne!(a, MemoryEventId::nil());
    }

    #[test]
    fn all_eight_kinds_are_distinct() {
        let kinds = [
            MemoryEventKind::Recalled,
            MemoryEventKind::Written,
            MemoryEventKind::Updated,
            MemoryEventKind::Invalidated,
            MemoryEventKind::Reflected,
            MemoryEventKind::Reinforced,
            MemoryEventKind::MergeCompleted,
            MemoryEventKind::Forgotten,
        ];
        assert_eq!(kinds.len(), 8);
        for i in 0..kinds.len() {
            for j in (i + 1)..kinds.len() {
                assert_ne!(kinds[i], kinds[j]);
            }
        }
    }

    #[test]
    fn event_serde_roundtrip_empty_payload() {
        let e = ev(MemoryEventKind::Written);
        let json = serde_json::to_string(&e).unwrap();
        let back: MemoryEvent = serde_json::from_str(&json).unwrap();
        assert_eq!(e, back);
    }

    #[test]
    fn event_serde_roundtrip_merge_payload() {
        let e = MemoryEvent {
            id: MemoryEventId::nil(),
            timestamp: Utc::now(),
            session_id: None,
            kind: MemoryEventKind::MergeCompleted,
            memory_ids: vec!["a".to_string(), "b".to_string()],
            payload: MemoryEventPayload::MergeCompleted {
                into: "c".to_string(),
            },
        };
        let json = serde_json::to_string(&e).unwrap();
        let back: MemoryEvent = serde_json::from_str(&json).unwrap();
        assert_eq!(e, back);
    }

    #[test]
    fn memory_ids_is_vec_not_option() {
        // Single-target
        let single = MemoryEvent {
            memory_ids: vec!["one".to_string()],
            ..ev(MemoryEventKind::Written)
        };
        assert_eq!(single.memory_ids.len(), 1);

        // Multi-target (merge)
        let multi = MemoryEvent {
            memory_ids: vec!["a".to_string(), "b".to_string(), "c".to_string()],
            ..ev(MemoryEventKind::MergeCompleted)
        };
        assert_eq!(multi.memory_ids.len(), 3);

        // Unrelated-to-memory
        let none = ev(MemoryEventKind::Recalled);
        assert!(none.memory_ids.is_empty());
    }

    #[test]
    fn payload_empty_is_a_named_variant() {
        // Empty variant is a value, not Option::None.
        let e = ev(MemoryEventKind::Updated);
        assert!(matches!(e.payload, MemoryEventPayload::Empty));
    }
}
