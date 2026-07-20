//! King Synapse core: storage, schema, recall, and entity primitives.
//!
//! Phase 2: SQLite + FTS5 + vec0 (sqlite-vec) storage with a separate
//! RecallEngine that fuses FTS, entity-graph, and vector hits via RRF.
//! Store is now query-agnostic; embedding lives behind a trait so it can
//! be swapped or mocked.

pub(crate) mod accelerator;
pub mod adaptive;
pub mod config;
pub(crate) mod embed;
pub mod enterprise_shadow;
pub(crate) mod entity;
pub(crate) mod error;
pub(crate) mod extract;
pub(crate) mod model;
pub mod recall;
pub(crate) mod rerank;
pub(crate) mod store;
pub mod working_memory;

pub use adaptive::{
    AlgorithmContext, CognitiveAdjustedScore, CognitiveBooster, CognitiveBoosterConfig,
    CognitiveBoosterConfigError, CognitiveBoosterInput, CognitiveBoosterMode,
    CognitiveBoosterOutput, CognitiveCompetitionTrace, CognitiveFactor, CognitiveFactorType,
    CognitiveTraceEvaluator, DeterministicCognitiveBoosterV0, DeterministicReflectionAlgorithm,
    ForgetAlgorithm, ForgetOutput, ForgetReason, ForgetSkipReason, ForgetTarget, HebbianAlgorithm,
    HebbianOutput, HebbianSkipReason, HebbianTarget, ImportanceEstimator, ImportanceSignal,
    ImportanceSignals, InMemoryMemoryEventStream, MemoryEvent, MemoryEventId, MemoryEventKind,
    MemoryEventPayload, MemoryEventStream, MemoryImportance, MergeAlgorithm, MergeOutput,
    MergeSkipReason, MergeTarget, NoOpCognitiveBooster, NoOpForgetAlgorithm, NoOpHebbianAlgorithm,
    NoOpImportanceEstimator, NoOpMemoryEventStream, NoOpMergeAlgorithm, NoOpReflectionAlgorithm,
    ReflectionAlgorithm, ReflectionOutput, ReflectionSkipReason, RuleBasedForgetAlgorithm,
    RuleBasedHebbianAlgorithm, RuleBasedMergeAlgorithm, RuleBasedReflectionAlgorithm,
    UniformImportanceEstimator, MAX_COGNITIVE_BOOSTER_BONUS,
};
pub use embed::Embedder;
pub use enterprise_shadow::{
    EnterpriseCandidateEntry, EnterpriseEvidenceBasis, EnterpriseExcludedEntry, EnterpriseLineage,
    EnterpriseRuntimeTrace, EnterpriseShadowEngine, EnterpriseShadowResponse,
};
pub use entity::{Entity, EntityRef, EntityType};
pub use error::{Error, Result};
pub use model::{Memory, MemoryKind, RecallQuery, Scope, Source, WriteInput};
pub use recall::hypothesis::{
    default_semantic_judge_cache_path, CachedSemanticJudge, DeepSeekSemanticJudge,
    EdgeCandidateEvidence, EdgeEvidence, EdgeHypothesis, EdgeHypothesisGenerator,
    EdgeHypothesisStatus, EdgeJudgeInput, EdgeJudgement, EdgeReasonCategory, EdgeRelation,
    EdgeSemanticJudge, EdgeUtilityObservation, HeuristicSemanticJudge, HypothesisStore,
    JudgedEdgeGeneration, JudgedEdgeGenerator, JudgedEdgeHypothesis, RejectedEdgeCandidate,
    RetrievalContext, RuleBasedEdgeGenerator, SemanticEdgeMode, SemanticJudgeCacheStats,
    SemanticJudgeCacheStatsHandle, SemanticJudgeExecutorConfig,
};
pub use recall::{
    BoosterContext, CognitiveTraceCandidate, CognitiveTraceConfig, CognitiveTracePredictionReport,
    CognitiveTracePredictionStatistics, CognitiveTraceProbe, CognitiveTraceReport,
    CognitiveTraceSource, CognitiveTraceStatistics, GraphActivationBooster,
    LatentActivationBooster, LatentActivationContext, LatentActivationHit, LatentActivationProbe,
    NoOpBooster, ProfiledRecall, QueryEmbedder, QueryLatentActivationProbe,
    QueryLatentActivationReport, RecallBooster, RecallEngine, RecallHit, RecallProfile,
    RecallSource, RrfBranchWeights, DEFAULT_RERANK_POOL, DEFAULT_RRF_K,
};
pub use rerank::{FastEmbedReranker, Reranker};
pub use store::{MemoryEdge, Store};
pub use working_memory::{
    AdaptivePolicy, AdaptivePolicyEngine, ArchiveExecution, ConsolidationEngine,
    ConsolidationExecutor, ConsolidationPlan, ConsolidationSink, DeterministicAdaptivePolicyEngine,
    DeterministicHebbianStoreMutationDispatcher, DeterministicReflectionStoreMutationDispatcher,
    DeterministicStoreMutationDispatcher, DiscardExecution, EdgeUpdatePlan, ExecutedAction,
    ExecutedEdgeUpdate, ExecutionReport, ExecutionStatistics, ExecutionWarning, ForgetPolicy,
    HebbianExecutionReport, HebbianExecutionStatistics, HebbianExecutionWarning, HebbianExecutor,
    HebbianPolicy, HebbianReinforcementEngine, HebbianSink, KuzuPersistentStoreExecutor, MemoryId,
    MergeExecution, MergeGroup, MergePolicy, MergeStrategy, NoOpActivationBooster,
    NoOpAdaptivePolicyEngine, NoOpConsolidation, NoOpForgetPolicy, NoOpHebbianExecutor,
    NoOpHebbianPolicy, NoOpHebbianReinforcementEngine, NoOpHebbianSink, NoOpMergePolicy,
    NoOpPersistentStoreExecutor, NoOpPolicySink, NoOpReflectionEngine, NoOpReflectionEventRecorder,
    NoOpReflectionPolicy, NoOpReflectionSink, NoOpSink, NoOpStoreAdapter,
    NoOpStoreMutationDispatcher, NoOpStoreSink, PersistentStoreExecutor,
    PlanOnlyConsolidationExecutor, PlanOnlyHebbianExecutor, PlanOnlyReflectionExecutor,
    PlanOnlyStoreAdapter, PolicyDecision, PolicyKind, PolicyReport, PolicyRequest, PolicySink,
    PolicyStatistics, PolicyWarning, ReflectionAction, ReflectionEngine, ReflectionEvent,
    ReflectionEventId, ReflectionEventRecorder, ReflectionExecutor, ReflectionPayload,
    ReflectionPlan, ReflectionPolicy, ReflectionRecord, ReflectionReport, ReflectionSink,
    ReflectionSource, ReflectionStatistics, ReflectionWarning, SQLitePersistentStoreExecutor,
    SessionId, SkippedEdgeUpdate, SkippedReflectionAction, SkippedStoreMutation, StoreAdapter,
    StoreExecutionReport, StoreExecutionStatistics, StoreExecutionWarning, StoreMutation,
    StoreMutationDispatcher, StoreMutationPlan, StoreSink, WorkingMemoryActivationBooster,
    WorkingMemoryBuffer, WorkingMemoryEdge, WorkingMemoryItem,
};
