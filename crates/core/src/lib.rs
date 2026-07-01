//! King Synapse core: storage, schema, recall, and entity primitives.
//!
//! Phase 2: SQLite + FTS5 + vec0 (sqlite-vec) storage with a separate
//! RecallEngine that fuses FTS, entity-graph, and vector hits via RRF.
//! Store is now query-agnostic; embedding lives behind a trait so it can
//! be swapped or mocked.

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
    ArchiveExecution, ConsolidationEngine, ConsolidationExecutor, ConsolidationPlan,
    ConsolidationSink, DeterministicStoreMutationDispatcher, DiscardExecution, EdgeUpdatePlan,
    ExecutedAction, ExecutedEdgeUpdate, ExecutionReport, ExecutionStatistics, ExecutionWarning,
    HebbianExecutionReport, HebbianExecutionStatistics, HebbianExecutionWarning, HebbianExecutor,
    HebbianReinforcementEngine, HebbianSink, MemoryId, MergeExecution, MergeGroup, MergeStrategy,
    NoOpActivationBooster, NoOpConsolidation, NoOpHebbianExecutor, NoOpHebbianReinforcementEngine,
    NoOpHebbianSink, NoOpReflectionEngine, NoOpReflectionEventRecorder, NoOpReflectionSink,
    NoOpSink, NoOpStoreAdapter, NoOpStoreMutationDispatcher, PlanOnlyConsolidationExecutor,
    PlanOnlyHebbianExecutor, PlanOnlyReflectionExecutor, PlanOnlyStoreAdapter, ReflectionAction,
    ReflectionEngine, ReflectionEvent, ReflectionEventId, ReflectionEventRecorder,
    ReflectionExecutor, ReflectionPayload, ReflectionPlan, ReflectionRecord, ReflectionReport,
    ReflectionSink, ReflectionSource, ReflectionStatistics, ReflectionWarning, SessionId,
    SkippedEdgeUpdate, SkippedReflectionAction, StoreAdapter, StoreExecutionReport, StoreMutation,
    StoreMutationDispatcher, StoreMutationPlan, WorkingMemoryActivationBooster,
    WorkingMemoryBuffer, WorkingMemoryEdge, WorkingMemoryItem,
};
