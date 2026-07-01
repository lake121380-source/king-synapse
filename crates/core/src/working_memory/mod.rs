//! Session-scoped working memory overlay.
//!
//! Working memory is a transient scratchpad for future activation. It is not
//! persisted, embedded, reranked, or fused into recall.

mod activation;
mod buffer;
mod consolidation;
mod executor;
mod hebbian;
mod hebbian_sink;
mod item;
mod persistent_store;
mod policy;
mod policy_dispatcher;
mod policy_sink;
mod reflection;
mod reflection_processing;
mod reflection_sink;
mod session;
mod sink;
mod store_adapter;
mod store_dispatcher;
mod store_sink;

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
pub use hebbian::{
    EdgeUpdatePlan, ExecutedEdgeUpdate, HebbianExecutionReport, HebbianExecutionStatistics,
    HebbianExecutionWarning, HebbianExecutor, HebbianReinforcementEngine, NoOpHebbianExecutor,
    NoOpHebbianReinforcementEngine, PlanOnlyHebbianExecutor, SkippedEdgeUpdate,
};
pub use hebbian_sink::{HebbianSink, NoOpHebbianSink};
pub use item::{MemoryId, WorkingMemoryEdge, WorkingMemoryItem};
pub use persistent_store::{
    KuzuPersistentStoreExecutor, NoOpPersistentStoreExecutor, PersistentStoreExecutor,
    SQLitePersistentStoreExecutor,
};
pub use policy::{
    AdaptivePolicy, ForgetPolicy, HebbianPolicy, MergePolicy, NoOpForgetPolicy, NoOpHebbianPolicy,
    NoOpMergePolicy, NoOpReflectionPolicy, PolicyDecision, ReflectionPolicy,
};
pub use policy_dispatcher::{
    AdaptivePolicyEngine, DeterministicAdaptivePolicyEngine, NoOpAdaptivePolicyEngine, PolicyKind,
    PolicyReport, PolicyRequest, PolicyStatistics, PolicyWarning,
};
pub use policy_sink::{NoOpPolicySink, PolicySink};
pub use reflection::{
    InMemoryReflectionEventStream, NoOpReflectionEventRecorder, ReflectionEvent, ReflectionEventId,
    ReflectionEventRecorder, ReflectionPayload, ReflectionSource,
};
pub use reflection_processing::{
    NoOpReflectionEngine, PlanOnlyReflectionExecutor, ReflectionAction, ReflectionEngine,
    ReflectionExecutor, ReflectionPlan, ReflectionRecord, ReflectionReport, ReflectionStatistics,
    ReflectionWarning, SkippedReflectionAction,
};
pub use reflection_sink::{NoOpReflectionSink, ReflectionSink};
pub use session::SessionId;
pub use sink::{ConsolidationSink, NoOpSink};
pub use store_adapter::{
    NoOpStoreAdapter, PlanOnlyStoreAdapter, SkippedStoreMutation, StoreAdapter,
    StoreExecutionReport, StoreExecutionStatistics, StoreExecutionWarning, StoreMutation,
    StoreMutationPlan,
};
pub use store_dispatcher::{
    DeterministicHebbianStoreMutationDispatcher, DeterministicReflectionStoreMutationDispatcher,
    DeterministicStoreMutationDispatcher, NoOpStoreMutationDispatcher, StoreMutationDispatcher,
};
pub use store_sink::{NoOpStoreSink, StoreSink};

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::{
        ForgetOutput, ForgetReason, ImportanceSignals, MemoryImportance, ReflectionOutput,
    };
    use crate::Store;
    use chrono::{Duration as ChronoDuration, Utc};
    use std::time::Duration;
    use uuid::Uuid;

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
    fn noop_hebbian_executor_emits_empty_report() {
        let plans = vec![EdgeUpdatePlan {
            source: "mem-a".to_string(),
            target: "mem-b".to_string(),
            weight_delta: 0.1,
        }];
        let executor = NoOpHebbianExecutor;

        let report = executor.execute(&plans);

        assert!(report.is_empty());
        assert_eq!(report.statistics, HebbianExecutionStatistics::default());
    }

    #[test]
    fn plan_only_hebbian_executor_reports_input_plans() {
        let plans = vec![EdgeUpdatePlan {
            source: "mem-a".to_string(),
            target: "mem-b".to_string(),
            weight_delta: 0.1,
        }];
        let executor = PlanOnlyHebbianExecutor;

        let report = executor.execute(&plans);

        assert_eq!(
            report.executed_actions,
            vec![ExecutedEdgeUpdate::Apply(plans[0].clone())]
        );
        assert!(report.skipped_actions.is_empty());
        assert!(report.warnings.is_empty());
        assert_eq!(report.statistics.executed, 1);
        assert_eq!(report.statistics.skipped, 0);
    }

    #[test]
    fn invalid_hebbian_update_is_skipped_with_warning() {
        let plans = vec![EdgeUpdatePlan {
            source: String::new(),
            target: "mem-b".to_string(),
            weight_delta: f32::INFINITY,
        }];
        let executor = PlanOnlyHebbianExecutor;

        let report = executor.execute(&plans);

        assert!(report.executed_actions.is_empty());
        assert_eq!(
            report.skipped_actions,
            vec![SkippedEdgeUpdate::Invalid(plans[0].clone())]
        );
        assert_eq!(report.warnings.len(), 1);
        assert_eq!(report.statistics.executed, 0);
        assert_eq!(report.statistics.skipped, 1);
    }

    #[test]
    fn duplicate_hebbian_update_is_skipped_deterministically() {
        let plans = vec![
            EdgeUpdatePlan {
                source: "mem-a".to_string(),
                target: "mem-b".to_string(),
                weight_delta: 0.1,
            },
            EdgeUpdatePlan {
                source: "mem-a".to_string(),
                target: "mem-b".to_string(),
                weight_delta: 0.2,
            },
        ];
        let executor = PlanOnlyHebbianExecutor;

        let report_a = executor.execute(&plans);
        let report_b = executor.execute(&plans);

        assert_eq!(report_a, report_b);
        assert_eq!(
            report_a.executed_actions,
            vec![ExecutedEdgeUpdate::Apply(plans[0].clone())]
        );
        assert_eq!(
            report_a.skipped_actions,
            vec![SkippedEdgeUpdate::Duplicate(plans[1].clone())]
        );
        assert_eq!(report_a.warnings.len(), 1);
        assert_eq!(report_a.statistics.executed, 1);
        assert_eq!(report_a.statistics.skipped, 1);
    }

    #[test]
    fn noop_hebbian_sink_consumes_report_without_mutating_it() {
        let plans = vec![EdgeUpdatePlan {
            source: "mem-a".to_string(),
            target: "mem-b".to_string(),
            weight_delta: 0.1,
        }];
        let executor = PlanOnlyHebbianExecutor;
        let report = executor.execute(&plans);
        let original = report.clone();
        let mut sink = NoOpHebbianSink;

        sink.consume(&report);

        assert_eq!(report, original);
    }

    #[test]
    fn multiple_hebbian_sinks_observe_same_report() {
        #[derive(Default)]
        struct CountingSink {
            observed_actions: usize,
        }

        impl HebbianSink for CountingSink {
            fn consume(&mut self, report: &HebbianExecutionReport) {
                self.observed_actions = report.executed_actions.len();
            }
        }

        let plans = vec![EdgeUpdatePlan {
            source: "mem-a".to_string(),
            target: "mem-b".to_string(),
            weight_delta: 0.1,
        }];
        let executor = PlanOnlyHebbianExecutor;
        let report = executor.execute(&plans);
        let report_after_dispatch = executor.execute(&plans);
        let mut sink_a = CountingSink::default();
        let mut sink_b = CountingSink::default();

        sink_a.consume(&report);
        sink_b.consume(&report);

        assert_eq!(report, report_after_dispatch);
        assert_eq!(sink_a.observed_actions, 1);
        assert_eq!(sink_b.observed_actions, 1);
    }

    #[test]
    fn noop_store_adapter_emits_empty_report() {
        let plan = StoreMutationPlan {
            mutations: vec![StoreMutation::InsertMemory {
                id: "mem-a".to_string(),
                content: "hello".to_string(),
            }],
        };
        let adapter = NoOpStoreAdapter;

        let report = adapter.execute(&plan);

        assert!(report.is_empty());
        assert_eq!(report.statistics, StoreExecutionStatistics::default());
    }

    #[test]
    fn plan_only_store_adapter_reports_input_mutations() {
        let plan = StoreMutationPlan {
            mutations: vec![
                StoreMutation::InsertMemory {
                    id: "mem-a".to_string(),
                    content: "hello".to_string(),
                },
                StoreMutation::UpdateEdge {
                    source: "mem-a".to_string(),
                    target: "mem-b".to_string(),
                    weight_delta: 0.1,
                },
            ],
        };
        let adapter = PlanOnlyStoreAdapter;

        let report = adapter.execute(&plan);

        assert_eq!(report.executed, plan.mutations);
        assert!(report.skipped.is_empty());
        assert!(report.warnings.is_empty());
        assert_eq!(report.statistics.executed, 2);
        assert_eq!(report.statistics.skipped, 0);
    }

    #[test]
    fn store_adapter_execution_is_deterministic_and_preserves_plan() {
        let plan = StoreMutationPlan {
            mutations: vec![StoreMutation::ArchiveMemory {
                id: "mem-a".to_string(),
            }],
        };
        let original = plan.clone();
        let adapter = PlanOnlyStoreAdapter;

        let report_a = adapter.execute(&plan);
        let report_b = adapter.execute(&plan);

        assert_eq!(report_a, report_b);
        assert_eq!(plan, original);
    }

    #[test]
    fn noop_store_mutation_dispatcher_emits_empty_plan() {
        let dispatcher = NoOpStoreMutationDispatcher;

        let plan = dispatcher.dispatch();

        assert!(plan.is_empty());
    }

    #[test]
    fn store_mutation_dispatcher_maps_archive_action_to_insert_memory() {
        let session = SessionId::new();
        let item =
            WorkingMemoryItem::new(session, "archive me", Vec::new(), Duration::from_secs(60));
        let plan = ConsolidationPlan {
            promote: vec![item.clone()],
            merge: Vec::new(),
            discard: Vec::new(),
        };
        let executor = PlanOnlyConsolidationExecutor;
        let report = executor.execute(&plan);
        let original = report.clone();
        let dispatcher = DeterministicStoreMutationDispatcher::new(report.clone());

        let mutation_plan = dispatcher.dispatch();

        assert_eq!(report, original);
        assert_eq!(
            mutation_plan.mutations,
            vec![StoreMutation::InsertMemory {
                id: item.id.to_string(),
                content: item.content,
            }]
        );
    }

    #[test]
    fn store_mutation_dispatcher_is_deterministic() {
        let session = SessionId::new();
        let item =
            WorkingMemoryItem::new(session, "discard me", Vec::new(), Duration::from_secs(60));
        let plan = ConsolidationPlan {
            promote: Vec::new(),
            merge: Vec::new(),
            discard: vec![item],
        };
        let executor = PlanOnlyConsolidationExecutor;
        let report = executor.execute(&plan);
        let dispatcher = DeterministicStoreMutationDispatcher::new(report);

        let plan_a = dispatcher.dispatch();
        let plan_b = dispatcher.dispatch();

        assert_eq!(plan_a, plan_b);
    }

    #[test]
    fn reflection_store_dispatcher_maps_candidate_to_edge_update() {
        let session = SessionId::new();
        let now = Utc::now();
        let event_id = Uuid::nil();
        let output = ReflectionOutput::Candidate {
            target_memory_id: "mem-reflected".to_string(),
            importance: MemoryImportance {
                overall: 0.5,
                signals: ImportanceSignals::uniform(0.5),
            },
            evidence_count: 1,
        };
        let event = output
            .to_reflection_event_with_id(event_id, session, ReflectionSource::SystemSignal, now)
            .expect("candidate should map to a reflection event");
        let dispatcher = DeterministicReflectionStoreMutationDispatcher::new(ReflectionPlan {
            events: vec![event],
        });

        let plan = dispatcher.dispatch();

        assert_eq!(
            plan.mutations,
            vec![StoreMutation::UpdateEdge {
                source: format!("reflection:{}", event_id),
                target: "mem-reflected".to_string(),
                weight_delta: 0.1,
            }]
        );
    }

    #[test]
    fn reflection_store_dispatcher_maps_payload_lifecycle_actions() {
        let session = SessionId::new();
        let merge_a =
            WorkingMemoryItem::new(session, "merge-a", Vec::new(), Duration::from_secs(60));
        let merge_b =
            WorkingMemoryItem::new(session, "merge-b", Vec::new(), Duration::from_secs(60));
        let event = ReflectionEvent {
            id: Uuid::nil(),
            session_id: session,
            timestamp: Utc::now(),
            source: ReflectionSource::SystemSignal,
            payload: ReflectionPayload {
                promoted: Vec::new(),
                merged: vec![MergeGroup {
                    items: vec![merge_a.clone(), merge_b.clone()],
                    strategy: MergeStrategy::Union,
                }],
                discarded: vec!["mem-discarded".to_string()],
            },
        };
        let dispatcher = DeterministicReflectionStoreMutationDispatcher::new(ReflectionPlan {
            events: vec![event],
        });

        let plan = dispatcher.dispatch();

        assert_eq!(
            plan.mutations,
            vec![
                StoreMutation::UpdateMemory {
                    id: merge_a.id.to_string(),
                    content: "merge-a\nmerge-b".to_string(),
                },
                StoreMutation::ArchiveMemory {
                    id: "mem-discarded".to_string(),
                },
            ]
        );
    }

    #[test]
    fn hebbian_store_dispatcher_maps_edge_updates_to_store_mutations() {
        let plans = vec![
            EdgeUpdatePlan {
                source: "mem-a".to_string(),
                target: "mem-b".to_string(),
                weight_delta: 0.2,
            },
            EdgeUpdatePlan {
                source: "mem-b".to_string(),
                target: "mem-a".to_string(),
                weight_delta: 0.2,
            },
        ];
        let executor = PlanOnlyHebbianExecutor;
        let report = executor.execute(&plans);
        let original = report.clone();
        let dispatcher = DeterministicHebbianStoreMutationDispatcher::new(report.clone());

        let mutation_plan = dispatcher.dispatch();

        assert_eq!(report, original);
        assert_eq!(
            mutation_plan.mutations,
            vec![
                StoreMutation::UpdateEdge {
                    source: "mem-a".to_string(),
                    target: "mem-b".to_string(),
                    weight_delta: 0.2,
                },
                StoreMutation::UpdateEdge {
                    source: "mem-b".to_string(),
                    target: "mem-a".to_string(),
                    weight_delta: 0.2,
                },
            ]
        );
    }

    #[test]
    fn hebbian_store_dispatcher_ignores_skipped_edge_updates() {
        let plans = vec![
            EdgeUpdatePlan {
                source: "mem-a".to_string(),
                target: "mem-b".to_string(),
                weight_delta: 0.2,
            },
            EdgeUpdatePlan {
                source: "mem-a".to_string(),
                target: "mem-b".to_string(),
                weight_delta: 0.4,
            },
            EdgeUpdatePlan {
                source: String::new(),
                target: "mem-c".to_string(),
                weight_delta: 0.6,
            },
        ];
        let executor = PlanOnlyHebbianExecutor;
        let report = executor.execute(&plans);
        let dispatcher = DeterministicHebbianStoreMutationDispatcher::new(report);

        let mutation_plan_a = dispatcher.dispatch();
        let mutation_plan_b = dispatcher.dispatch();

        assert_eq!(mutation_plan_a, mutation_plan_b);
        assert_eq!(
            mutation_plan_a.mutations,
            vec![StoreMutation::UpdateEdge {
                source: "mem-a".to_string(),
                target: "mem-b".to_string(),
                weight_delta: 0.2,
            }]
        );
    }

    #[test]
    fn store_mutation_dispatcher_maps_linked_merge_to_update_and_archives() {
        let session = SessionId::new();
        let item = WorkingMemoryItem::new(
            session,
            "merged memory",
            vec!["mem-primary".to_string(), "mem-duplicate".to_string()],
            Duration::from_secs(60),
        );
        let plan = ConsolidationPlan {
            promote: Vec::new(),
            merge: vec![MergeGroup {
                items: vec![item],
                strategy: MergeStrategy::Deduplicate,
            }],
            discard: Vec::new(),
        };
        let executor = PlanOnlyConsolidationExecutor;
        let report = executor.execute(&plan);
        let dispatcher = DeterministicStoreMutationDispatcher::new(report);

        let mutation_plan = dispatcher.dispatch();

        assert_eq!(
            mutation_plan.mutations,
            vec![
                StoreMutation::UpdateMemory {
                    id: "mem-primary".to_string(),
                    content: "merged memory".to_string(),
                },
                StoreMutation::ArchiveMemory {
                    id: "mem-duplicate".to_string(),
                },
            ]
        );
    }

    #[test]
    fn noop_store_sink_consumes_report_without_mutating_it() {
        let plan = StoreMutationPlan {
            mutations: vec![StoreMutation::InsertMemory {
                id: "mem-a".to_string(),
                content: "hello".to_string(),
            }],
        };
        let adapter = PlanOnlyStoreAdapter;
        let report = adapter.execute(&plan);
        let original = report.clone();
        let sink = NoOpStoreSink;

        sink.consume(&report);

        assert_eq!(report, original);
    }

    #[test]
    fn multiple_store_sinks_observe_same_report_without_affecting_adapter_output() {
        #[derive(Default)]
        struct CountingSink {
            observed: std::cell::Cell<usize>,
        }

        impl StoreSink for CountingSink {
            fn consume(&self, report: &StoreExecutionReport) {
                self.observed.set(report.executed.len());
            }
        }

        let plan = StoreMutationPlan {
            mutations: vec![StoreMutation::ArchiveMemory {
                id: "mem-a".to_string(),
            }],
        };
        let adapter = PlanOnlyStoreAdapter;
        let report = adapter.execute(&plan);
        let report_after_sink = adapter.execute(&plan);
        let sink_a = CountingSink::default();
        let sink_b = CountingSink::default();

        sink_a.consume(&report);
        sink_b.consume(&report);

        assert_eq!(report, report_after_sink);
        assert_eq!(sink_a.observed.get(), 1);
        assert_eq!(sink_b.observed.get(), 1);
    }

    #[test]
    fn noop_persistent_store_executor_returns_empty_report() {
        let plan = StoreMutationPlan {
            mutations: vec![StoreMutation::InsertMemory {
                id: "mem-a".to_string(),
                content: "hello".to_string(),
            }],
        };
        let mut executor = NoOpPersistentStoreExecutor;

        let report = executor.execute(&plan);

        assert!(report.is_empty());
    }

    #[test]
    fn sqlite_persistent_store_executor_inserts_memory() {
        let mut store = Store::open_in_memory().unwrap();
        let plan = StoreMutationPlan {
            mutations: vec![StoreMutation::InsertMemory {
                id: "mem-a".to_string(),
                content: "persistent hello".to_string(),
            }],
        };
        let original = plan.clone();
        let mut executor = SQLitePersistentStoreExecutor::new(&mut store);

        let report = executor.execute(&plan);

        assert_eq!(plan, original);
        assert_eq!(report.executed, plan.mutations);
        assert!(report.skipped.is_empty());
        assert_eq!(report.statistics.executed, 1);
        assert_eq!(store.count().unwrap(), 1);
    }

    #[test]
    fn sqlite_persistent_store_executor_handles_empty_plan() {
        let mut store = Store::open_in_memory().unwrap();
        let plan = StoreMutationPlan::default();
        let mut executor = SQLitePersistentStoreExecutor::new(&mut store);

        let report = executor.execute(&plan);

        assert!(report.is_empty());
        assert_eq!(store.count().unwrap(), 0);
    }

    #[test]
    fn sqlite_persistent_store_executor_updates_edge_weight() {
        let mut store = Store::open_in_memory().unwrap();
        let source = store
            .write(crate::WriteInput {
                content: "source memory".to_string(),
                kind: crate::MemoryKind::Fact,
                scope: crate::Scope::Global,
                source: crate::Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let target = store
            .write(crate::WriteInput {
                content: "target memory".to_string(),
                kind: crate::MemoryKind::Fact,
                scope: crate::Scope::Global,
                source: crate::Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let plan = StoreMutationPlan {
            mutations: vec![
                StoreMutation::UpdateEdge {
                    source: source.id.clone(),
                    target: target.id.clone(),
                    weight_delta: 0.1,
                },
                StoreMutation::UpdateEdge {
                    source: source.id.clone(),
                    target: target.id.clone(),
                    weight_delta: 0.4,
                },
            ],
        };
        let mut executor = SQLitePersistentStoreExecutor::new(&mut store);

        let report = executor.execute(&plan);

        assert_eq!(report.executed, plan.mutations);
        assert!(report.skipped.is_empty());
        assert_eq!(report.statistics.executed, 2);
        assert_eq!(report.statistics.skipped, 0);
        assert_eq!(
            store.edge_weight(&source.id, &target.id).unwrap(),
            Some(0.5)
        );
    }

    #[test]
    fn sqlite_persistent_store_executor_reports_failed_edge_updates() {
        let mut store = Store::open_in_memory().unwrap();
        let plan = StoreMutationPlan {
            mutations: vec![StoreMutation::UpdateEdge {
                source: "missing-source".to_string(),
                target: "missing-target".to_string(),
                weight_delta: 0.1,
            }],
        };
        let mut executor = SQLitePersistentStoreExecutor::new(&mut store);

        let report = executor.execute(&plan);

        assert!(report.executed.is_empty());
        assert_eq!(
            report.skipped,
            vec![SkippedStoreMutation::Failed(plan.mutations[0].clone())]
        );
        assert_eq!(report.statistics.executed, 0);
        assert_eq!(report.statistics.skipped, 1);
    }

    #[test]
    fn sqlite_persistent_store_executor_updates_memory_content() {
        let mut store = Store::open_in_memory().unwrap();
        let first = store
            .write(crate::WriteInput {
                content: "old duplicate memory".to_string(),
                kind: crate::MemoryKind::Fact,
                scope: crate::Scope::Global,
                source: crate::Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let second = store
            .write(crate::WriteInput {
                content: "duplicate to archive".to_string(),
                kind: crate::MemoryKind::Fact,
                scope: crate::Scope::Global,
                source: crate::Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let plan = StoreMutationPlan {
            mutations: vec![
                StoreMutation::UpdateMemory {
                    id: first.id.clone(),
                    content: "merged duplicate memory".to_string(),
                },
                StoreMutation::ArchiveMemory {
                    id: second.id.clone(),
                },
            ],
        };
        let mut executor = SQLitePersistentStoreExecutor::new(&mut store);

        let report = executor.execute(&plan);

        assert_eq!(report.executed, plan.mutations);
        assert!(report.skipped.is_empty());
        assert_eq!(report.statistics.executed, 2);
        assert_eq!(report.statistics.skipped, 0);
        assert_eq!(
            store.get(&first.id).unwrap().unwrap().content,
            "merged duplicate memory"
        );
        assert!(store.get(&second.id).unwrap().unwrap().valid_to.is_some());
        let pending = store.pending_embeddings(10).unwrap();
        assert!(pending
            .iter()
            .any(|(id, content)| { id == &first.id && content == "merged duplicate memory" }));
    }

    #[test]
    fn forget_output_store_plan_archives_memory_in_sqlite() {
        let mut store = Store::open_in_memory().unwrap();
        let memory = store
            .write(crate::WriteInput {
                content: "forgettable memory".to_string(),
                kind: crate::MemoryKind::Fact,
                scope: crate::Scope::Global,
                source: crate::Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let output = ForgetOutput::Forget {
            memory_id: memory.id.clone(),
            reason: ForgetReason::LowUseLowImportance,
            score: 1.3,
        };
        let plan = output
            .to_store_mutation_plan()
            .expect("forget output should map to a store mutation plan");
        let mut executor = SQLitePersistentStoreExecutor::new(&mut store);

        let report = executor.execute(&plan);

        assert_eq!(report.executed, plan.mutations);
        assert!(report.skipped.is_empty());
        assert_eq!(report.statistics.executed, 1);
        assert!(store.get(&memory.id).unwrap().unwrap().valid_to.is_some());
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
            ReflectionPayload {
                promoted: vec!["mem-a".to_string()],
                merged: Vec::new(),
                discarded: Vec::new(),
            },
        );
        let plan = ReflectionPlan {
            events: vec![event.clone()],
        };
        let executor = PlanOnlyReflectionExecutor;

        let report = executor.execute(&plan);

        assert_eq!(report.executed_actions.len(), 1);
        assert_eq!(
            report.executed_actions[0],
            ReflectionAction::Record(ReflectionRecord {
                event_id: event.id,
                source: ReflectionSource::ConsolidationPlan,
            })
        );
        assert!(report.skipped_actions.is_empty());
        assert!(report.warnings.is_empty());
        assert_eq!(report.statistics.processed, 1);
        assert_eq!(report.statistics.skipped, 0);
    }

    #[test]
    fn empty_reflection_payload_is_skipped_with_warning() {
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

        assert!(report.executed_actions.is_empty());
        assert_eq!(report.skipped_actions.len(), 1);
        assert_eq!(report.warnings.len(), 1);
        assert_eq!(report.statistics.processed, 0);
        assert_eq!(report.statistics.skipped, 1);
        assert_eq!(
            report.skipped_actions[0],
            SkippedReflectionAction::EmptyPayload(ReflectionRecord {
                event_id: event.id,
                source: ReflectionSource::ConsolidationPlan,
            })
        );
    }

    #[test]
    fn noop_reflection_sink_consumes_report_without_mutating_it() {
        let session = SessionId::new();
        let event = ReflectionEvent::new(
            session,
            ReflectionSource::ConsolidationPlan,
            ReflectionPayload {
                promoted: vec!["mem-a".to_string()],
                merged: Vec::new(),
                discarded: Vec::new(),
            },
        );
        let plan = ReflectionPlan {
            events: vec![event],
        };
        let executor = PlanOnlyReflectionExecutor;
        let report = executor.execute(&plan);
        let original = report.clone();
        let mut sink = NoOpReflectionSink;

        sink.consume(&report);

        assert_eq!(report, original);
    }

    #[test]
    fn multiple_reflection_sinks_observe_same_report() {
        #[derive(Default)]
        struct CountingSink {
            observed_actions: usize,
        }

        impl ReflectionSink for CountingSink {
            fn consume(&mut self, report: &ReflectionReport) {
                self.observed_actions = report.executed_actions.len();
            }
        }

        let session = SessionId::new();
        let event = ReflectionEvent::new(
            session,
            ReflectionSource::ConsolidationPlan,
            ReflectionPayload {
                promoted: vec!["mem-a".to_string()],
                merged: Vec::new(),
                discarded: Vec::new(),
            },
        );
        let plan = ReflectionPlan {
            events: vec![event],
        };
        let executor = PlanOnlyReflectionExecutor;
        let report = executor.execute(&plan);
        let mut sink_a = CountingSink::default();
        let mut sink_b = CountingSink::default();

        sink_a.consume(&report);
        sink_b.consume(&report);

        assert_eq!(sink_a.observed_actions, 1);
        assert_eq!(sink_b.observed_actions, 1);
    }

    #[test]
    fn noop_reflection_policy_is_deterministic() {
        let policy = NoOpReflectionPolicy;
        let event = ReflectionEvent::new(
            SessionId::new(),
            ReflectionSource::ConsolidationPlan,
            ReflectionPayload {
                promoted: vec!["mem-a".to_string()],
                merged: Vec::new(),
                discarded: Vec::new(),
            },
        );
        assert_eq!(policy.evaluate(&event), PolicyDecision::Execute);
        assert_eq!(policy.evaluate(&event), PolicyDecision::Execute);
    }

    #[test]
    fn noop_hebbian_policy_is_deterministic() {
        let policy = NoOpHebbianPolicy;
        let plan = EdgeUpdatePlan {
            source: "a".to_string(),
            target: "b".to_string(),
            weight_delta: 0.1,
        };
        assert_eq!(policy.evaluate(&plan), PolicyDecision::Execute);
        assert_eq!(policy.evaluate(&plan), PolicyDecision::Execute);
    }

    #[test]
    fn noop_forget_policy_is_deterministic() {
        let policy = NoOpForgetPolicy;
        let id: MemoryId = "mem-a".to_string();
        assert_eq!(policy.evaluate(&id), PolicyDecision::Skip);
        assert_eq!(policy.evaluate(&id), PolicyDecision::Skip);
    }

    #[test]
    fn noop_merge_policy_is_deterministic() {
        let policy = NoOpMergePolicy;
        let group = MergeGroup {
            items: Vec::new(),
            strategy: MergeStrategy::Deduplicate,
        };
        assert_eq!(policy.evaluate(&group), PolicyDecision::Execute);
        assert_eq!(policy.evaluate(&group), PolicyDecision::Execute);
    }

    #[test]
    fn policy_decision_equality_and_serialization() {
        assert_eq!(PolicyDecision::Execute, PolicyDecision::Execute);
        assert_ne!(PolicyDecision::Execute, PolicyDecision::Skip);
        assert_ne!(PolicyDecision::Skip, PolicyDecision::Delay);

        let encoded = serde_json::to_string(&PolicyDecision::Delay).unwrap();
        let decoded: PolicyDecision = serde_json::from_str(&encoded).unwrap();
        assert_eq!(decoded, PolicyDecision::Delay);
    }

    #[test]
    fn noop_policies_are_zero_sized() {
        assert_eq!(std::mem::size_of::<NoOpReflectionPolicy>(), 0);
        assert_eq!(std::mem::size_of::<NoOpHebbianPolicy>(), 0);
        assert_eq!(std::mem::size_of::<NoOpForgetPolicy>(), 0);
        assert_eq!(std::mem::size_of::<NoOpMergePolicy>(), 0);
    }

    fn sample_reflection_event() -> ReflectionEvent {
        ReflectionEvent::new(
            SessionId::new(),
            ReflectionSource::ConsolidationPlan,
            ReflectionPayload {
                promoted: vec!["mem-a".to_string()],
                merged: Vec::new(),
                discarded: Vec::new(),
            },
        )
    }

    fn sample_edge_plan() -> EdgeUpdatePlan {
        EdgeUpdatePlan {
            source: "a".to_string(),
            target: "b".to_string(),
            weight_delta: 0.1,
        }
    }

    fn sample_merge_group() -> MergeGroup {
        MergeGroup {
            items: Vec::new(),
            strategy: MergeStrategy::Deduplicate,
        }
    }

    #[test]
    fn noop_policy_engine_returns_skip_for_all_requests() {
        let engine = NoOpAdaptivePolicyEngine;

        let reflection = engine.evaluate(&PolicyRequest::Reflection(sample_reflection_event()));
        assert_eq!(reflection.policy, PolicyKind::Reflection);
        assert_eq!(reflection.decision, PolicyDecision::Skip);
        assert_eq!(reflection.statistics.evaluated, 1);
        assert_eq!(reflection.statistics.skipped, 1);

        let hebbian = engine.evaluate(&PolicyRequest::Hebbian(sample_edge_plan()));
        assert_eq!(hebbian.policy, PolicyKind::Hebbian);
        assert_eq!(hebbian.decision, PolicyDecision::Skip);

        let forget = engine.evaluate(&PolicyRequest::Forget("mem-x".to_string()));
        assert_eq!(forget.policy, PolicyKind::Forget);
        assert_eq!(forget.decision, PolicyDecision::Skip);

        let merge = engine.evaluate(&PolicyRequest::Merge(sample_merge_group()));
        assert_eq!(merge.policy, PolicyKind::Merge);
        assert_eq!(merge.decision, PolicyDecision::Skip);
    }

    #[test]
    fn deterministic_policy_engine_routes_to_matching_policy() {
        let engine = DeterministicAdaptivePolicyEngine::default();

        let reflection = engine.evaluate(&PolicyRequest::Reflection(sample_reflection_event()));
        assert_eq!(reflection.policy, PolicyKind::Reflection);
        assert_eq!(reflection.decision, PolicyDecision::Execute);
        assert_eq!(reflection.statistics.executed, 1);

        let hebbian = engine.evaluate(&PolicyRequest::Hebbian(sample_edge_plan()));
        assert_eq!(hebbian.policy, PolicyKind::Hebbian);
        assert_eq!(hebbian.decision, PolicyDecision::Execute);

        let forget = engine.evaluate(&PolicyRequest::Forget("mem-x".to_string()));
        assert_eq!(forget.policy, PolicyKind::Forget);
        assert_eq!(forget.decision, PolicyDecision::Skip);
        assert_eq!(forget.statistics.skipped, 1);

        let merge = engine.evaluate(&PolicyRequest::Merge(sample_merge_group()));
        assert_eq!(merge.policy, PolicyKind::Merge);
        assert_eq!(merge.decision, PolicyDecision::Execute);
    }

    #[test]
    fn deterministic_policy_engine_is_stable_for_identical_input() {
        let engine = DeterministicAdaptivePolicyEngine::default();
        let request = PolicyRequest::Hebbian(sample_edge_plan());

        let first = engine.evaluate(&request);
        let second = engine.evaluate(&request);
        assert_eq!(first, second);
    }

    #[test]
    fn policy_request_kind_matches_variant() {
        assert_eq!(
            PolicyRequest::Reflection(sample_reflection_event()).kind(),
            PolicyKind::Reflection,
        );
        assert_eq!(
            PolicyRequest::Hebbian(sample_edge_plan()).kind(),
            PolicyKind::Hebbian,
        );
        assert_eq!(
            PolicyRequest::Forget("mem-a".to_string()).kind(),
            PolicyKind::Forget,
        );
        assert_eq!(
            PolicyRequest::Merge(sample_merge_group()).kind(),
            PolicyKind::Merge,
        );
    }

    #[test]
    fn policy_report_serializes_round_trip() {
        let engine = NoOpAdaptivePolicyEngine;
        let report = engine.evaluate(&PolicyRequest::Forget("mem-a".to_string()));
        let encoded = serde_json::to_string(&report).unwrap();
        let decoded: PolicyReport = serde_json::from_str(&encoded).unwrap();
        assert_eq!(decoded, report);
    }

    #[test]
    fn noop_policy_sink_consumes_report_without_mutating_it() {
        let engine = DeterministicAdaptivePolicyEngine::default();
        let request = PolicyRequest::Hebbian(sample_edge_plan());
        let report = engine.evaluate(&request);
        let sink = NoOpPolicySink;

        sink.consume(&report);

        assert_eq!(engine.evaluate(&request), report);
    }

    #[test]
    fn multiple_policy_sinks_observe_same_report_without_affecting_dispatcher() {
        #[derive(Default)]
        struct CountingPolicySink {
            observed: std::cell::Cell<usize>,
        }

        impl PolicySink for CountingPolicySink {
            fn consume(&self, _report: &PolicyReport) {
                self.observed.set(self.observed.get() + 1);
            }
        }

        let engine = DeterministicAdaptivePolicyEngine::default();
        let request = PolicyRequest::Reflection(sample_reflection_event());
        let report_before = engine.evaluate(&request);
        let sink_a = CountingPolicySink::default();
        let sink_b = CountingPolicySink::default();

        sink_a.consume(&report_before);
        sink_b.consume(&report_before);

        let report_after = engine.evaluate(&request);
        assert_eq!(report_before, report_after);
        assert_eq!(sink_a.observed.get(), 1);
        assert_eq!(sink_b.observed.get(), 1);
    }
}
