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
mod reflection_processing;
mod session;
mod sink;

pub use activation::{NoOpActivationBooster, WorkingMemoryActivationBooster};
pub use buffer::WorkingMemoryBuffer;
pub use consolidation::{
    ConsolidationEngine, ConsolidationPlan, MergeGroup, MergeStrategy, NoOpConsolidation,
};
pub use executor::{
    ArchiveExecution, ConsolidationExecutor, DiscardExecution, ExecutedAction, ExecutionReport,
    ExecutionStatistics, ExecutionWarning, MergeExecution, PlanOnlyConsolidationExecutor,
    SkippedAction,
};
pub use hebbian::{EdgeUpdatePlan, HebbianReinforcementEngine, NoOpHebbianReinforcementEngine};
pub use item::{MemoryId, WorkingMemoryEdge, WorkingMemoryItem};
pub use reflection::{
    InMemoryReflectionEventStream, NoOpReflectionEventRecorder, ReflectionEvent, ReflectionEventId,
    ReflectionEventRecorder, ReflectionPayload, ReflectionSource,
};
pub use reflection_processing::{
    NoOpReflectionEngine, PlanOnlyReflectionExecutor, ReflectionEngine, ReflectionExecutor,
    ReflectionPlan, ReflectionReport,
};
pub use session::SessionId;
pub use sink::{ConsolidationSink, NoOpSink};

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
        assert!(report.executed_actions.is_empty());
        assert!(report.skipped_actions.is_empty());
        assert!(report.warnings.is_empty());
        assert_eq!(report.statistics, ExecutionStatistics::default());
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

        assert_eq!(report.executed_actions.len(), 3);
        assert_eq!(
            report.executed_actions[0],
            ExecutedAction::Archive(ArchiveExecution { item: promote })
        );
        assert_eq!(
            report.executed_actions[1],
            ExecutedAction::Merge(MergeExecution {
                items: vec![merge_a, merge_b],
                strategy: MergeStrategy::Union,
            })
        );
        assert_eq!(
            report.executed_actions[2],
            ExecutedAction::Discard(DiscardExecution { item: discard })
        );
        assert!(report.skipped_actions.is_empty());
        assert_eq!(report.statistics.archived, 1);
        assert_eq!(report.statistics.merged, 1);
        assert_eq!(report.statistics.discarded, 1);
        assert_eq!(report.statistics.skipped, 0);
    }

    #[test]
    fn empty_merge_group_is_skipped_with_warning() {
        let plan = ConsolidationPlan {
            promote: Vec::new(),
            merge: vec![MergeGroup {
                items: Vec::new(),
                strategy: MergeStrategy::Deduplicate,
            }],
            discard: Vec::new(),
        };
        let executor = PlanOnlyConsolidationExecutor;

        let report = executor.execute(&plan);

        assert!(report.executed_actions.is_empty());
        assert_eq!(report.skipped_actions.len(), 1);
        assert_eq!(report.warnings.len(), 1);
        assert_eq!(report.statistics.skipped, 1);
        assert_eq!(
            report.skipped_actions[0],
            SkippedAction::Merge(MergeExecution {
                items: Vec::new(),
                strategy: MergeStrategy::Deduplicate,
            })
        );
    }

    #[test]
    fn noop_sink_consumes_report_without_mutating_it() {
        let session = SessionId::new();
        let item = WorkingMemoryItem::new(session, "archive", Vec::new(), Duration::from_secs(60));
        let plan = ConsolidationPlan {
            promote: vec![item],
            merge: Vec::new(),
            discard: Vec::new(),
        };
        let executor = PlanOnlyConsolidationExecutor;
        let report = executor.execute(&plan);
        let original = report.clone();
        let mut sink = NoOpSink;

        sink.apply(&report).expect("noop sink should accept report");

        assert_eq!(report, original);
    }

    #[test]
    fn noop_reflection_engine_produces_empty_plan() {
        let session = SessionId::new();
        let event = ReflectionEvent::new(
            session,
            ReflectionSource::ConsolidationPlan,
            ReflectionPayload::default(),
        );
        let engine = NoOpReflectionEngine;

        let plan = engine.plan(&[event]);

        assert!(plan.is_empty());
    }

    #[test]
    fn plan_only_reflection_executor_reports_processed_events() {
        let session = SessionId::new();
        let event = ReflectionEvent::new(
            session,
            ReflectionSource::ConsolidationPlan,
            ReflectionPayload::default(),
        );
        let plan = ReflectionPlan {
            events: vec![event.clone()],
        };
        let executor = PlanOnlyReflectionExecutor;

        let report = executor.execute(&plan);

        assert_eq!(report.processed_events, vec![event.id]);
    }
}
