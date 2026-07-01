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
    ConsolidationSink, DiscardExecution, EdgeUpdatePlan, ExecutedAction, ExecutionReport,
    ExecutionStatistics, ExecutionWarning, HebbianReinforcementEngine, MemoryId, MergeExecution,
    MergeGroup, MergeStrategy, NoOpActivationBooster, NoOpConsolidation,
    NoOpHebbianReinforcementEngine, NoOpReflectionEventRecorder, NoOpSink,
    PlanOnlyConsolidationExecutor, ReflectionEvent, ReflectionEventId, ReflectionEventRecorder,
    ReflectionPayload, ReflectionSource, SessionId, WorkingMemoryActivationBooster,
    WorkingMemoryBuffer, WorkingMemoryEdge, WorkingMemoryItem,
};
