//! Session-scoped working memory overlay.
//!
//! Working memory is a transient scratchpad for future activation. It is not
//! persisted, embedded, reranked, or fused into recall.

mod activation;
mod buffer;
mod consolidation;
mod item;
mod session;

pub use activation::{NoOpActivationBooster, WorkingMemoryActivationBooster};
pub use buffer::WorkingMemoryBuffer;
pub use consolidation::{
    ConsolidationEngine, ConsolidationPlan, MergeGroup, MergeStrategy, NoOpConsolidation,
};
pub use item::{MemoryId, WorkingMemoryEdge, WorkingMemoryItem};
pub use session::SessionId;

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration as ChronoDuration, Utc};
    use std::time::Duration;

    #[test]
    fn buffer_isolates_sessions() {
        let session_a = SessionId::new();
        let session_b = SessionId::new();
        let mut buffer = WorkingMemoryBuffer::new();

        buffer.add(
            session_a,
            WorkingMemoryItem::new(session_a, "a", Vec::new(), Duration::from_secs(60)),
        );
        buffer.add(
            session_b,
            WorkingMemoryItem::new(session_b, "b", Vec::new(), Duration::from_secs(60)),
        );

        assert_eq!(buffer.get_session(session_a).len(), 1);
        assert_eq!(buffer.get_session(session_b).len(), 1);
        assert_eq!(buffer.get_session(session_a)[0].content, "a");
        assert_eq!(buffer.get_session(session_b)[0].content, "b");
    }

    #[test]
    fn link_is_session_scoped() {
        let session_a = SessionId::new();
        let session_b = SessionId::new();
        let mut buffer = WorkingMemoryBuffer::new();

        buffer.link(session_a, "mem-a".to_string(), "mem-b".to_string());

        assert_eq!(buffer.get_edges(session_a).len(), 1);
        assert!(buffer.get_edges(session_b).is_empty());
    }

    #[test]
    fn clear_expired_drops_only_expired_items() {
        let session = SessionId::new();
        let mut expired =
            WorkingMemoryItem::new(session, "expired", Vec::new(), Duration::from_secs(1));
        expired.created_at = Utc::now() - ChronoDuration::seconds(2);
        let active = WorkingMemoryItem::new(session, "active", Vec::new(), Duration::from_secs(60));
        let mut buffer = WorkingMemoryBuffer::new();

        buffer.add(session, expired);
        buffer.add(session, active);
        buffer.clear_expired(Utc::now());

        let items = buffer.get_session(session);
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].content, "active");
    }

    #[test]
    fn noop_consolidation_never_emits_memory() {
        let buffer = WorkingMemoryBuffer::new();
        let engine = NoOpConsolidation;
        let plan = engine.consolidate(&buffer);

        assert!(plan.is_empty());
        assert!(plan.promote.is_empty());
        assert!(plan.merge.is_empty());
        assert!(plan.discard.is_empty());
    }

    #[test]
    fn consolidation_plan_can_describe_lifecycle_actions_without_io() {
        let session = SessionId::new();
        let item = WorkingMemoryItem::new(session, "scratch", Vec::new(), Duration::from_secs(60));
        let plan = ConsolidationPlan {
            promote: vec![item.clone()],
            merge: vec![MergeGroup {
                items: vec![item.clone()],
                strategy: MergeStrategy::Deduplicate,
            }],
            discard: vec![item],
        };

        assert!(!plan.is_empty());
        assert_eq!(plan.merge[0].strategy, MergeStrategy::Deduplicate);
    }
}
