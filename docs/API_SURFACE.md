# API Surface

This document lists the stable public API of King Synapse as of `v0.5.9-adaptive-common-freeze`.

APIs are classified into three levels:

- **Stable** — SemVer-guaranteed. Breaking changes require a major version bump. See `docs/COMPATIBILITY.md`.
- **Experimental** — Public but subject to change. Documented as such at introduction.
- **Internal** — Not part of the public API. May change at any time. Do not depend on internal items.

Stable items in `synapse-core` live under the crate's re-export table in `crates/core/src/lib.rs`. Stable items in other crates live in their crate's `src/lib.rs` re-exports. If an item is not re-exported there, it is **Internal**.

## Adaptive Common Model (Frozen Reference)

**Frozen at `v0.5.9-adaptive-common-freeze`.** This is the shared foundation every Phase 5 adaptive-memory algorithm consumes. New algorithm RFCs (RFC-012..015) reference these types read-only and MUST NOT redefine, fork, or shadow them.

| Concept | Type | Crate | Frozen since |
| --- | --- | --- | --- |
| Importance | `MemoryImportance`, `ImportanceSignals`, `ImportanceSignal`, `ImportanceEstimator`, `NoOpImportanceEstimator`, `UniformImportanceEstimator` | `synapse-core::adaptive::importance` | `v0.5.1` |
| Event | `MemoryEventId`, `MemoryEvent`, `MemoryEventKind`, `MemoryEventPayload` | `synapse-core::adaptive::event` | `v0.5.2` |
| Event Stream | `MemoryEventStream`, `NoOpMemoryEventStream`, `InMemoryMemoryEventStream` | `synapse-core::adaptive::event_stream` | `v0.5.2` |
| Context | `AlgorithmContext<'a>` (trait-object surface: `importance`, `events`; **closed** at `v0.5.2`) | `synapse-core::adaptive::context` | `v0.5.2` |
| Metric | `AlgorithmMetric` (10 IDs, `#[non_exhaustive]`) | `synapse-eval::contract` | `v0.5.3` |
| Report | `BenchmarkReport` (`#[non_exhaustive]`, `benchmark: String` + `metrics: BTreeMap<AlgorithmMetric, f64>`) | `synapse-eval::contract` | `v0.5.3` |

Post-Freeze rules (`docs/rfcs/RFC-011-adaptive-memory-common-model.md#post-freeze-rules`):

- **PF1** No new top-level shared types under `crates/core/src/adaptive/`. Additive `#[non_exhaustive]` variant extension remains allowed.
- **PF2** Every algorithm's primary method is `fn method(&self, target: &T, ctx: &AlgorithmContext<'_>) -> Output`. Any deviation requires an ADR.
- **PF3** Downstream RFCs consume, never extend.
- **PF4** Algorithm RFCs MUST NOT depend on one another. All algorithms depend only on RFC-011.
- **PF5** `AlgorithmContext` never owns data; no new service handles.
- **PF6** Benchmarks call only public API.
- **PF7** Renaming any frozen type is breaking.

Detailed per-crate listings follow below.

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
- `DeterministicReflectionStoreMutationDispatcher`
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

Frozen (incrementally): `v0.5.1-memory-importance` (importance kernel), `v0.5.2-memory-event-and-context` (event kernel + context closure). Full RFC-011 model frozen at `v0.5.9-adaptive-common-freeze`.

### adaptive algorithms (Phase 5)

**Stable (algorithm-local skeleton)**

- `ReflectionAlgorithm` (trait: `fn reflect(&self, target: &Memory, ctx: &AlgorithmContext<'_>) -> ReflectionOutput`)
- `ReflectionOutput` (`#[non_exhaustive]`; algorithm-local output)
- `ReflectionOutput::to_reflection_event_with_id(event_id, session_id, source, now)` (adapter into frozen Reflection Processing events)
- `ReflectionSkipReason` (`#[non_exhaustive]`; algorithm-local skip reason)
- `NoOpReflectionAlgorithm`
- `DeterministicReflectionAlgorithm` (reference implementation; reproducible baseline, not production)
- `RuleBasedReflectionAlgorithm` (deterministic heuristic implementation; closer to production than the reference)
- `MergeAlgorithm` (trait: `fn merge(&self, target: &MergeTarget, ctx: &AlgorithmContext<'_>) -> MergeOutput`)
- `MergeTarget` (`#[non_exhaustive]`; algorithm-local aggregate of candidate memories)
- `MergeOutput` (`#[non_exhaustive]`; `Skipped`, `Candidate`, or `Merge`)
- `MergeOutput::to_consolidation_plan_with_item_id(item_id, session_id, created_at, ttl)` (adapter into frozen Consolidation plans)
- `MergeSkipReason` (`#[non_exhaustive]`; algorithm-local skip reason)
- `NoOpMergeAlgorithm`
- `RuleBasedMergeAlgorithm` (deterministic heuristic implementation; emits merge, candidate, or skip decisions)

Introduced by `v0.6.0-reflection-algorithm-skeleton`, `v0.6.2-reflection-deterministic-reference`, `v0.6.4-reflection-processing-adapter`, `v0.7.0-merge-algorithm-skeleton`, `v0.7.2-merge-rule-based-reference`, `v0.7.3-merge-benchmark`, and `v0.7.4-merge-store-adapter`. These items are algorithm-local; they do not extend RFC-011 and do not add new shared top-level adaptive types.

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

### benchmark harness contract (Phase 5)

**Stable**

- `AlgorithmMetric` (`#[non_exhaustive]`; 10 IDs: `RecallAt10`, `PrecisionAt10`, `MemoryGrowth`, `CompressionRatio`, `ReflectionYield`, `MergePrecision`, `ForgetPrecision`, `HebbianConsistency`, `EventReplayLatency`, `AlgorithmLatency`)
- `BenchmarkReport` (`#[non_exhaustive]`; fields: `benchmark: String` in `lowercase-kebab-case` by convention, `metrics: BTreeMap<AlgorithmMetric, f64>`)

Invariants (RFC-011 Part D):
- `BenchmarkReport` is a deterministic value object: same `(dataset, algorithm, config)` → identical report. It MUST NOT carry runtime metadata (timestamp, hostname, cpu, random_seed, git_dirty).
- Reports are sparse: only meaningful metrics are included. Missing metrics MUST NOT be interpreted as `0.0`.
- Directory layout under `crates/eval/{datasets,benches,reports}/` is stable per `docs/COMPATIBILITY.md`. Adding a sibling directory is non-breaking; renaming or deleting one is breaking.

Frozen by `v0.5.3-benchmark-harness`. Included in the full Adaptive Common Model freeze at `v0.5.9-adaptive-common-freeze`.

### legacy benchmark runner

**Experimental**

- Benchmark harness (`kr-eval` binary), dataset TOML schema, `Recall@k` / `MRR@k` / `NDCG@k` metric outputs from `crates/eval/src/harness.rs` and `crates/eval/src/metrics.rs`.
- `reflection_yield_report()`, `rule_based_reflection_yield_report()`, `merge_precision_report()`, and algorithm benchmark helpers under `crates/eval/src/algorithms.rs`.

The `kr-eval` runner and its `Report` output type predate `BenchmarkReport` and are not part of the v0.5.3 harness contract. They remain Experimental during Phase 5 and may be migrated onto `BenchmarkReport` in a later milestone.

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
