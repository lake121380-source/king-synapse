# API Surface

This document lists the stable public API of King Synapse as of `v0.5.0-architecture-freeze`.

APIs are classified into three levels:

- **Stable** — SemVer-guaranteed. Breaking changes require a major version bump. See `docs/COMPATIBILITY.md`.
- **Experimental** — Public but subject to change. Documented as such at introduction.
- **Internal** — Not part of the public API. May change at any time. Do not depend on internal items.

Every public API item lives under `synapse-core`'s re-export table in `crates/core/src/lib.rs`. If an item is not re-exported there, it is **Internal**.

## synapse-core

### recall

**Stable**

- `RecallEngine`
- `RecallHit`
- `RecallSource`
- `RecallBooster`
- `BoosterContext`
- `NoOpBooster`
- `QueryEmbedder`
- `Reranker`
- `FastEmbedReranker`
- `DEFAULT_RERANK_POOL`

Frozen by `v0.2.0-recall-api-freeze`. Recall scoring semantics, `RecallHit` schema, and booster extension point are stable. See `docs/RECALL_PIPELINE.md`.

### model

**Stable**

- `Memory`
- `MemoryKind`
- `Scope`
- `Source`
- `RecallQuery`
- `WriteInput`

### storage

**Stable**

- `Store`

**Stable (embedder abstraction)**

- `Embedder`

### working memory (Memory Evolution Contract)

**Stable**

- `WorkingMemoryBuffer`
- `SessionId`
- `WorkingMemoryItem`
- `WorkingMemoryEdge`
- `MemoryId`
- `WorkingMemoryActivationBooster`
- `NoOpActivationBooster`

Frozen by `v0.3.9-memory-evolution-freeze`. See `docs/WORKING_MEMORY.md`.

### consolidation

**Stable**

- `ConsolidationEngine`
- `ConsolidationPlan`
- `MergeGroup`
- `MergeStrategy`
- `NoOpConsolidation`
- `ConsolidationExecutor`
- `PlanOnlyConsolidationExecutor`
- `ExecutionReport`
- `ExecutionStatistics`
- `ExecutionWarning`
- `ExecutedAction`
- `ArchiveExecution`
- `MergeExecution`
- `DiscardExecution`
- `ConsolidationSink`
- `NoOpSink`

Frozen by `v0.4.9-adaptive-memory-foundation`.

### reflection

**Stable**

- `ReflectionEvent`
- `ReflectionEventId`
- `ReflectionSource`
- `ReflectionPayload`
- `ReflectionEventRecorder`
- `NoOpReflectionEventRecorder`
- `ReflectionEngine`
- `NoOpReflectionEngine`
- `ReflectionPlan`
- `ReflectionExecutor`
- `PlanOnlyReflectionExecutor`
- `ReflectionReport`
- `ReflectionRecord`
- `ReflectionAction`
- `ReflectionStatistics`
- `ReflectionWarning`
- `SkippedReflectionAction`
- `ReflectionSink`
- `NoOpReflectionSink`

Frozen by `v0.4.19-reflection-processing-freeze`.

### hebbian

**Stable**

- `HebbianReinforcementEngine`
- `NoOpHebbianReinforcementEngine`
- `EdgeUpdatePlan`
- `HebbianExecutor`
- `NoOpHebbianExecutor`
- `PlanOnlyHebbianExecutor`
- `HebbianExecutionReport`
- `HebbianExecutionStatistics`
- `HebbianExecutionWarning`
- `ExecutedEdgeUpdate`
- `SkippedEdgeUpdate`
- `HebbianSink`
- `NoOpHebbianSink`

Frozen by `v0.4.29-hebbian-execution-freeze`.

### store integration

**Stable**

- `StoreMutation`
- `StoreMutationPlan`
- `StoreAdapter`
- `NoOpStoreAdapter`
- `PlanOnlyStoreAdapter`
- `StoreMutationDispatcher`
- `NoOpStoreMutationDispatcher`
- `DeterministicStoreMutationDispatcher`
- `StoreExecutionReport`
- `StoreExecutionStatistics`
- `StoreExecutionWarning`
- `SkippedStoreMutation`
- `StoreSink`
- `NoOpStoreSink`
- `PersistentStoreExecutor`
- `NoOpPersistentStoreExecutor`
- `SQLitePersistentStoreExecutor`
- `KuzuPersistentStoreExecutor`

Frozen by `v0.4.39-store-integration-freeze`.

### adaptive policies

**Stable**

- `PolicyDecision`
- `AdaptivePolicy`
- `ReflectionPolicy`
- `HebbianPolicy`
- `ForgetPolicy`
- `MergePolicy`
- `NoOpReflectionPolicy`
- `NoOpHebbianPolicy`
- `NoOpForgetPolicy`
- `NoOpMergePolicy`
- `PolicyRequest`
- `PolicyKind`
- `PolicyReport`
- `PolicyStatistics`
- `PolicyWarning`
- `AdaptivePolicyEngine`
- `NoOpAdaptivePolicyEngine`
- `DeterministicAdaptivePolicyEngine`
- `PolicySink`
- `NoOpPolicySink`

Frozen by `v0.4.49-adaptive-policies-freeze`.

### adaptive memory common model (Phase 5)

**Stable**

- `MemoryImportance`
- `ImportanceSignals` (`#[non_exhaustive]`)
- `ImportanceSignal` (`#[non_exhaustive]`; explainability-only)
- `ImportanceEstimator` (trait: `fn estimate(&self, memory: &Memory, ctx: &AlgorithmContext<'_>) -> MemoryImportance`)
- `NoOpImportanceEstimator`
- `UniformImportanceEstimator`
- `MemoryEventId`
- `MemoryEvent`
- `MemoryEventKind` (`#[non_exhaustive]`; 8 kinds: `Recalled`, `Written`, `Updated`, `Invalidated`, `Reflected`, `Reinforced`, `MergeCompleted`, `Forgotten`)
- `MemoryEventPayload` (`#[non_exhaustive]`; `Empty` + typed variants)
- `MemoryEventStream` (trait: `fn record(&self, event: MemoryEvent)` + `fn recent(&self, limit: usize) -> Vec<MemoryEvent>`; append + replay only)
- `NoOpMemoryEventStream`
- `InMemoryMemoryEventStream` (reference implementation only; not production)
- `AlgorithmContext<'a>` (`#[non_exhaustive]`; fields: `now`, `session_id`, `importance: &'a dyn ImportanceEstimator`, `events: &'a dyn MemoryEventStream`; trait-object surface **closed** at v0.5.2)
- `AlgorithmContext::new(now, session_id, importance, events)` — the only supported constructor

Frozen (incrementally): `v0.5.1-memory-importance` (importance kernel), `v0.5.2-memory-event-and-context` (event kernel + context closure). Full RFC-011 freeze at `v0.5.9-adaptive-common-freeze`.

### entity

**Stable**

- `Entity`
- `EntityRef`
- `EntityType`

### error

**Stable**

- `Error`
- `Result`

### config

**Stable**

- `synapse_core::config` module

## synapse-mcp

**Stable (tool surface)**

- `synapse_write`
- `synapse_recall`
- `synapse_list_recent`
- `synapse_forget`

Tool JSON schemas are considered part of the stable public API.

## kr (CLI)

**Stable (command surface)**

- `kr write`
- `kr recall`
- `kr list`
- `kr where`
- `kr forget`

Flag names and output structure are considered part of the stable public API.

## synapse-eval

**Experimental**

- Benchmark harness (`kr-eval` binary), dataset TOML schema, `Recall@k` / `MRR@k` / `NDCG@k` metric outputs.

Metrics and dataset formats may evolve during Phase 5 (Algorithm Implementation).

## Public Guarantees

1. Stable APIs will not change in incompatible ways within a `0.5.x` line.
2. Every stable trait ships with at least one `NoOp` or `PlanOnly` implementation for testing.
3. Reports (`ExecutionReport`, `ReflectionReport`, `HebbianExecutionReport`, `StoreExecutionReport`, `PolicyReport`) are immutable after emission.
4. Sinks are observer-only and must not mutate reports.
5. Behavior modules must not call `Store`, `RecallEngine`, or LLMs directly; they must go through their frozen dispatcher / adapter path.
6. Phase 5 algorithm work must not change stable APIs. Algorithm implementations plug in behind existing traits.

## Item Classification Rules

- If an item is re-exported from `synapse_core::*` and appears above → **Stable**.
- If an item is re-exported from `synapse_core::*` but marked *Experimental* in this document → **Experimental**.
- If an item is not re-exported at the crate root → **Internal**.
- Test-only items (`#[cfg(test)]`, `PlanOnly*` helpers used in tests) may be stable but should be documented as such.
