//! Session-scoped working memory overlay.
//!
//! Working memory is a transient scratchpad for future activation. It is not
//! persisted, embedded, reranked, or fused into recall.

mod activation;
mod buffer;
mod consolidation;
mod executor;
mod hebbian;
mod item;
mod reflection;
mod session;

pub use activation::{NoOpActivationBooster, WorkingMemoryActivationBooster};
pub use buffer::WorkingMemoryBuffer;
pub use consolidation::{
    ConsolidationEngine, ConsolidationPlan, MergeGroup, MergeStrategy, NoOpConsolidation,
};
pub use executor::{
    ArchiveExecution, ConsolidationExecutor, DiscardExecution, ExecutedAction, ExecutionReport,
    MergeExecution, PlanOnlyConsolidationExecutor, SkippedAction,
};
pub use hebbian::{EdgeUpdatePlan, HebbianReinforcementEngine, NoOpHebbianReinforcementEngine};
pub use item::{MemoryId, WorkingMemoryEdge, WorkingMemoryItem};
pub use reflection::{
    InMemoryReflectionEventStream, NoOpReflectionEventRecorder, ReflectionEvent, ReflectionEventId,
    ReflectionEventRecorder, ReflectionPayload, ReflectionSource,
};
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

    #[test]
    fn noop_reflection_recorder_drops_events() {
        let session = SessionId::new();
        let event = ReflectionEvent::new(
            session,
            ReflectionSource::ConsolidationPlan,
            ReflectionPayload::default(),
        );
        let mut recorder = NoOpReflectionEventRecorder;

        recorder.record(event);

        assert!(recorder.events().is_empty());
    }

    #[test]
    fn in_memory_reflection_stream_records_events() {
        let session = SessionId::new();
        let payload = ReflectionPayload {
            promoted: vec!["mem-a".to_string()],
            merged: Vec::new(),
            discarded: vec!["mem-b".to_string()],
        };
        let event = ReflectionEvent::new(session, ReflectionSource::ConsolidationPlan, payload);
        let mut stream = InMemoryReflectionEventStream::new();

        stream.record(event);

        assert_eq!(stream.events().len(), 1);
        assert_eq!(stream.events()[0].session_id, session);
        assert_eq!(
            stream.events()[0].source,
            ReflectionSource::ConsolidationPlan
        );
        assert_eq!(stream.events()[0].payload.promoted, vec!["mem-a"]);
        assert_eq!(stream.events()[0].payload.discarded, vec!["mem-b"]);
    }

    #[test]
    fn reflection_payload_empty_reports_structural_noop() {
        let empty = ReflectionPayload::default();
        let non_empty = ReflectionPayload {
            promoted: vec!["mem-a".to_string()],
            merged: Vec::new(),
            discarded: Vec::new(),
        };

        assert!(empty.is_empty());
        assert!(!non_empty.is_empty());
    }

    #[test]
    fn noop_hebbian_engine_emits_no_updates() {
        let session = SessionId::new();
        let event = ReflectionEvent::new(
            session,
            ReflectionSource::ConsolidationPlan,
            ReflectionPayload::default(),
        );
        let engine = NoOpHebbianReinforcementEngine;

        assert!(engine.reinforce(&event).is_empty());
    }

    #[test]
    fn empty_plan_executes_to_empty_report() {
        let plan = ConsolidationPlan::default();
        let executor = PlanOnlyConsolidationExecutor;

        let report = executor.execute(&plan);

        assert!(report.is_empty());
        assert!(report.executed.is_empty());
        assert!(report.skipped.is_empty());
    }

    #[test]
    fn promote_merge_and_discard_translate_to_report_actions() {
        let session = SessionId::new();
        let promote =
            WorkingMemoryItem::new(session, "promote", Vec::new(), Duration::from_secs(60));
        let merge_a =
            WorkingMemoryItem::new(session, "merge-a", Vec::new(), Duration::from_secs(60));
        let merge_b =
            WorkingMemoryItem::new(session, "merge-b", Vec::new(), Duration::from_secs(60));
        let discard =
            WorkingMemoryItem::new(session, "discard", Vec::new(), Duration::from_secs(60));
        let plan = ConsolidationPlan {
            promote: vec![promote.clone()],
            merge: vec![MergeGroup {
                items: vec![merge_a.clone(), merge_b.clone()],
                strategy: MergeStrategy::Union,
            }],
            discard: vec![discard.clone()],
        };
        let executor = PlanOnlyConsolidationExecutor;

        let report = executor.execute(&plan);

        assert_eq!(report.executed.len(), 3);
        assert_eq!(
            report.executed[0],
            ExecutedAction::Archive(ArchiveExecution { item: promote })
        );
        assert_eq!(
            report.executed[1],
            ExecutedAction::Merge(MergeExecution {
                items: vec![merge_a, merge_b],
                strategy: MergeStrategy::Union,
            })
        );
        assert_eq!(
            report.executed[2],
            ExecutedAction::Discard(DiscardExecution { item: discard })
        );
        assert!(report.skipped.is_empty());
    }
}
