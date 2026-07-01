//! Memory Event Stream trait and reference implementations (RFC-011 Part B).
//!
//! `MemoryEventStream` is a strict append-only log. It exposes exactly two
//! operations: `record` (append) and `recent` (replay-oriented retrieval).
//! It is deliberately NOT a query API — query-shaped methods (`filter`,
//! `search`, `between`, etc.) are out of scope and MUST NOT be added.
//!
//! Included implementations:
//!
//! - [`NoOpMemoryEventStream`] — records nothing, returns empty.
//! - [`InMemoryMemoryEventStream`] — **reference implementation**:
//!   deterministic bounded ring buffer for tests and benchmarks. Not a
//!   default implementation, not a production event store.

use crate::adaptive::event::MemoryEvent;
use std::collections::VecDeque;
use std::sync::Mutex;

/// Append-only event log.
///
/// Invariants (see RFC-011 Part B "Rules"):
///
/// 1. Recorded events are immutable and never reordered by the stream.
/// 2. Past events are immutable once observed by `recent`.
/// 3. Replay is deterministic: identical `record` sequence → identical
///    `recent(n)` output.
/// 4. Event ordering is defined by `record` order, not by `event.timestamp`.
/// 5. Streams are side-effect free with respect to Store / Recall / any
///    executor.
/// 6. Only append and replay are supported. Query-shaped APIs are
///    forbidden.
///
/// Concrete streams may drop the oldest events on buffer overflow, but
/// MUST NOT reorder events relative to insertion order.
pub trait MemoryEventStream {
    /// Append `event` to the log. Recording is infallible and NOT
    /// idempotent — recording the same event twice appends two entries.
    fn record(&self, event: MemoryEvent);

    /// Replay the most recent up-to-`limit` events in insertion order.
    ///
    /// - `recent(0)` returns an empty `Vec`.
    /// - `recent(n)` with `n > len` returns every retained event.
    /// - Ordering follows insertion order, never `event.timestamp`.
    fn recent(&self, limit: usize) -> Vec<MemoryEvent>;
}

/// No-op event stream: `record` drops the event, `recent` returns empty.
///
/// Used as a placeholder when no observation is desired.
#[derive(Debug, Clone, Copy, Default)]
pub struct NoOpMemoryEventStream;

impl MemoryEventStream for NoOpMemoryEventStream {
    fn record(&self, _event: MemoryEvent) {}

    fn recent(&self, _limit: usize) -> Vec<MemoryEvent> {
        Vec::new()
    }
}

/// Reference implementation of `MemoryEventStream`: a bounded, deterministic
/// ring buffer over a `VecDeque<MemoryEvent>` guarded by a `Mutex`.
///
/// This is a **reference implementation** — deterministic, single-process,
/// intended for tests and benchmarks. It is explicitly NOT a default
/// implementation, and NOT a production event store. Persistent event
/// stores (SQLite / Kafka / etc.) are out of RFC-011's scope; they MUST
/// implement `MemoryEventStream` without changing the trait.
///
/// On overflow the **oldest** events are dropped; insertion order among
/// the retained events is preserved.
pub struct InMemoryMemoryEventStream {
    capacity: usize,
    buffer: Mutex<VecDeque<MemoryEvent>>,
}

impl InMemoryMemoryEventStream {
    /// Construct with a fixed retention capacity.
    ///
    /// A capacity of `0` produces a stream that records nothing (all events
    /// are immediately dropped on insert). Prefer `NoOpMemoryEventStream`
    /// for that case; capacity 0 is accepted for uniformity.
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            capacity,
            buffer: Mutex::new(VecDeque::with_capacity(capacity)),
        }
    }

    /// Current retained event count. Reference implementation detail;
    /// not part of the trait.
    pub fn len(&self) -> usize {
        self.buffer
            .lock()
            .expect("event stream mutex poisoned")
            .len()
    }

    /// Whether the stream currently holds no events.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

impl MemoryEventStream for InMemoryMemoryEventStream {
    fn record(&self, event: MemoryEvent) {
        let mut buf = self.buffer.lock().expect("event stream mutex poisoned");
        if self.capacity == 0 {
            return;
        }
        if buf.len() == self.capacity {
            buf.pop_front();
        }
        buf.push_back(event);
    }

    fn recent(&self, limit: usize) -> Vec<MemoryEvent> {
        if limit == 0 {
            return Vec::new();
        }
        let buf = self.buffer.lock().expect("event stream mutex poisoned");
        let take = limit.min(buf.len());
        let start = buf.len() - take;
        buf.iter().skip(start).cloned().collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::event::{MemoryEventId, MemoryEventKind, MemoryEventPayload};
    use chrono::Utc;

    fn make_event(tag: &str) -> MemoryEvent {
        MemoryEvent {
            id: MemoryEventId::new(),
            timestamp: Utc::now(),
            session_id: None,
            kind: MemoryEventKind::Written,
            memory_ids: vec![tag.to_string()],
            payload: MemoryEventPayload::Empty,
        }
    }

    // ---- NoOp ----

    #[test]
    fn noop_recent_is_empty_after_record() {
        let s = NoOpMemoryEventStream;
        s.record(make_event("a"));
        s.record(make_event("b"));
        assert!(s.recent(10).is_empty());
    }

    #[test]
    fn noop_is_zero_sized() {
        assert_eq!(std::mem::size_of::<NoOpMemoryEventStream>(), 0);
    }

    // ---- InMemory: recent(0) / recent(> len) ----

    #[test]
    fn recent_zero_returns_empty() {
        let s = InMemoryMemoryEventStream::with_capacity(8);
        s.record(make_event("a"));
        assert!(s.recent(0).is_empty());
    }

    #[test]
    fn recent_larger_than_len_returns_all() {
        let s = InMemoryMemoryEventStream::with_capacity(8);
        s.record(make_event("a"));
        s.record(make_event("b"));
        let out = s.recent(100);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].memory_ids, vec!["a".to_string()]);
        assert_eq!(out[1].memory_ids, vec!["b".to_string()]);
    }

    // ---- Ordering / determinism ----

    #[test]
    fn record_order_defines_replay_order_not_timestamp() {
        // Deliberately record events whose timestamps are in reverse order
        // of insertion; the stream must NOT sort them by timestamp.
        let s = InMemoryMemoryEventStream::with_capacity(8);
        let mut later = make_event("first");
        later.timestamp = Utc::now() + chrono::Duration::hours(1);
        let mut earlier = make_event("second");
        earlier.timestamp = Utc::now() - chrono::Duration::hours(1);
        s.record(later);
        s.record(earlier);
        let out = s.recent(10);
        assert_eq!(out[0].memory_ids, vec!["first".to_string()]);
        assert_eq!(out[1].memory_ids, vec!["second".to_string()]);
    }

    #[test]
    fn replay_is_deterministic_across_calls() {
        let s = InMemoryMemoryEventStream::with_capacity(8);
        for tag in ["a", "b", "c"] {
            s.record(make_event(tag));
        }
        let first = s.recent(10);
        let second = s.recent(10);
        let third = s.recent(10);
        assert_eq!(first, second);
        assert_eq!(second, third);
    }

    #[test]
    fn recent_only_returns_last_n_in_order() {
        let s = InMemoryMemoryEventStream::with_capacity(8);
        for tag in ["a", "b", "c", "d", "e"] {
            s.record(make_event(tag));
        }
        let out = s.recent(3);
        assert_eq!(out.len(), 3);
        assert_eq!(out[0].memory_ids, vec!["c".to_string()]);
        assert_eq!(out[1].memory_ids, vec!["d".to_string()]);
        assert_eq!(out[2].memory_ids, vec!["e".to_string()]);
    }

    // ---- Capacity / overflow ----

    #[test]
    fn overflow_drops_oldest_preserves_order() {
        let s = InMemoryMemoryEventStream::with_capacity(3);
        for tag in ["a", "b", "c", "d", "e"] {
            s.record(make_event(tag));
        }
        assert_eq!(s.len(), 3);
        let out = s.recent(10);
        assert_eq!(out.len(), 3);
        assert_eq!(out[0].memory_ids, vec!["c".to_string()]);
        assert_eq!(out[1].memory_ids, vec!["d".to_string()]);
        assert_eq!(out[2].memory_ids, vec!["e".to_string()]);
    }

    #[test]
    fn capacity_zero_records_nothing() {
        let s = InMemoryMemoryEventStream::with_capacity(0);
        s.record(make_event("a"));
        s.record(make_event("b"));
        assert!(s.is_empty());
        assert!(s.recent(10).is_empty());
    }

    // ---- Not idempotent ----

    #[test]
    fn record_is_not_idempotent() {
        let s = InMemoryMemoryEventStream::with_capacity(8);
        let e = make_event("dup");
        s.record(e.clone());
        s.record(e.clone());
        assert_eq!(s.len(), 2);
    }

    // ---- Interior mutability via &self ----

    #[test]
    fn record_uses_interior_mutability() {
        // The trait's &self signature must let a shared reference record.
        let s = InMemoryMemoryEventStream::with_capacity(4);
        let stream: &dyn MemoryEventStream = &s;
        stream.record(make_event("x"));
        assert_eq!(stream.recent(10).len(), 1);
    }
}
