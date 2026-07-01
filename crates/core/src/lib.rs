//! King Synapse core: storage, schema, recall, and entity primitives.
//!
//! Phase 2: SQLite + FTS5 + vec0 (sqlite-vec) storage with a separate
//! RecallEngine that fuses FTS, entity-graph, and vector hits via RRF.
//! Store is now query-agnostic; embedding lives behind a trait so it can
//! be swapped or mocked.

pub mod adaptive;
pub mod config;
pub(crate) mod embed;
pub(crate) mod entity;
pub(crate) mod error;
pub(crate) mod extract;
pub(crate) mod model;
pub(crate) mod recall;
pub(crate) mod rerank;
pub(crate) mod store;
pub mod working_memory;

pub use adaptive::{
    AlgorithmContext, DeterministicReflectionAlgorithm, ForgetAlgorithm, ForgetOutput,
    ForgetReason, ForgetSkipReason, ForgetTarget, ImportanceEstimator, ImportanceSignal,
    ImportanceSignals, InMemoryMemoryEventStream, MemoryEvent, MemoryEventId, MemoryEventKind,
    MemoryEventPayload, MemoryEventStream, MemoryImportance, MergeAlgorithm, MergeOutput,
    MergeSkipReason, MergeTarget, NoOpForgetAlgorithm, NoOpImportanceEstimator,
    NoOpMemoryEventStream, NoOpMergeAlgorithm, NoOpReflectionAlgorithm, ReflectionAlgorithm,
    ReflectionOutput, ReflectionSkipReason, RuleBasedForgetAlgorithm, RuleBasedMergeAlgorithm,
    RuleBasedReflectionAlgorithm, UniformImportanceEstimator,
};
pub use embed::Embedder;
pub use entity::{Entity, EntityRef, EntityType};
pub use error::{Error, Result};
pub use model::{Memory, MemoryKind, RecallQuery, Scope, Source, WriteInput};
pub use recall::{
    BoosterContext, NoOpBooster, QueryEmbedder, RecallBooster, RecallEngine, RecallHit,
    RecallSource, DEFAULT_RERANK_POOL,
};
pub use rerank::{FastEmbedReranker, Reranker};
pub use store::Store;
pub use working_memory::{
    AdaptivePolicy, AdaptivePolicyEngine, ArchiveExecution, ConsolidationEngine,
    ConsolidationExecutor, ConsolidationPlan, ConsolidationSink, DeterministicAdaptivePolicyEngine,
    DeterministicReflectionStoreMutationDispatcher, DeterministicStoreMutationDispatcher,
    DiscardExecution, EdgeUpdatePlan, ExecutedAction, ExecutedEdgeUpdate, ExecutionReport,
    ExecutionStatistics, ExecutionWarning, ForgetPolicy, HebbianExecutionReport,
    HebbianExecutionStatistics, HebbianExecutionWarning, HebbianExecutor, HebbianPolicy,
    HebbianReinforcementEngine, HebbianSink, KuzuPersistentStoreExecutor, MemoryId, MergeExecution,
    MergeGroup, MergePolicy, MergeStrategy, NoOpActivationBooster, NoOpAdaptivePolicyEngine,
    NoOpConsolidation, NoOpForgetPolicy, NoOpHebbianExecutor, NoOpHebbianPolicy,
    NoOpHebbianReinforcementEngine, NoOpHebbianSink, NoOpMergePolicy, NoOpPersistentStoreExecutor,
    NoOpPolicySink, NoOpReflectionEngine, NoOpReflectionEventRecorder, NoOpReflectionPolicy,
    NoOpReflectionSink, NoOpSink, NoOpStoreAdapter, NoOpStoreMutationDispatcher, NoOpStoreSink,
    PersistentStoreExecutor, PlanOnlyConsolidationExecutor, PlanOnlyHebbianExecutor,
    PlanOnlyReflectionExecutor, PlanOnlyStoreAdapter, PolicyDecision, PolicyKind, PolicyReport,
    PolicyRequest, PolicySink, PolicyStatistics, PolicyWarning, ReflectionAction, ReflectionEngine,
    ReflectionEvent, ReflectionEventId, ReflectionEventRecorder, ReflectionExecutor,
    ReflectionPayload, ReflectionPlan, ReflectionPolicy, ReflectionRecord, ReflectionReport,
    ReflectionSink, ReflectionSource, ReflectionStatistics, ReflectionWarning,
    SQLitePersistentStoreExecutor, SessionId, SkippedEdgeUpdate, SkippedReflectionAction,
    SkippedStoreMutation, StoreAdapter, StoreExecutionReport, StoreExecutionStatistics,
    StoreExecutionWarning, StoreMutation, StoreMutationDispatcher, StoreMutationPlan, StoreSink,
    WorkingMemoryActivationBooster, WorkingMemoryBuffer, WorkingMemoryEdge, WorkingMemoryItem,
};
