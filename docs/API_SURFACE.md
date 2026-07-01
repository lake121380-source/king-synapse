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
| Metric | `AlgorithmMetric` (11 IDs, `#[non_exhaustive]`) | `synapse-eval::contract` | `v0.5.3` |
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
- `GraphActivationBooster`
- `LatentActivationContext`
- `LatentActivationProbe`
- `LatentActivationHit`
- `QueryLatentActivationProbe`
- `QueryLatentActivationReport`
- `QueryEmbedder`
- `Reranker`
- `FastEmbedReranker`
- `DEFAULT_RERANK_POOL`

Frozen by `v0.2.0-recall-api-freeze`. Recall scoring semantics, `RecallHit` schema, and booster extension point are stable. See `docs/RECALL_PIPELINE.md`.

`GraphActivationBooster` is additive only: it reads Store-owned `memory_edges`
among existing candidate hits and contributes capped, decayed activation bonus
without creating new candidates or changing retrieval provenance fields.

`LatentActivationProbe` is read-only inspection, not a recall booster. It walks
Store-owned `memory_edges` from one or more seed memories and returns hidden
multi-step activation candidates with activation strength, depth, path,
modulation factor, and matched context terms. Optional
`LatentActivationContext` state/goal terms can increase matching hidden
activations while remaining capped and explainable. It does not create
`RecallHit`s, mutate Store, invoke retrievers, or alter recall rankings.

`QueryLatentActivationProbe` is a read-only inspection orchestrator. It first
uses `RecallEngine` to find visible seed memories for a `RecallQuery`, then
runs `LatentActivationProbe` from those seed ids. The report separates
`seeds` from `activations` and includes the final latent context. Optional
auto-context derives additional state/goal terms from the query text so
query-facing inspection remains outside `RecallHit` and does not alter recall
rankings.

**Experimental**

- `CognitiveTraceConfig`
- `CognitiveTraceProbe`
- `CognitiveTraceReport`
- `CognitiveTraceCandidate`
- `CognitiveTraceSource`
- `CognitiveTraceStatistics`

`CognitiveTraceProbe` composes visible recall, latent activation, and
state/goal context into a query-facing cognition report. The report identifies
one dominant candidate, suppressed candidates, visible recall hits, latent
activation paths, and the context terms that modulated hidden influence. It is
an inspection surface: it does not update graph edges, does not add fields to
`RecallHit`, and does not change recall ranking. Like normal recall, seed
retrieval may stamp access metadata. This surface is Experimental while the
cognitive competition scoring model is evaluated.

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
- `MemoryEdge`

`Store` exposes additive edge-inspection reads:
`outgoing_edges(memory_id, limit)`, `incoming_edges(memory_id, limit)`, and
`memory_edges(memory_id, limit)`. They return Store-owned directed
`associates` edges for active memories only.

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
- `DeterministicHebbianStoreMutationDispatcher`
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
- `ForgetAlgorithm` (trait: `fn forget(&self, target: &ForgetTarget, ctx: &AlgorithmContext<'_>) -> ForgetOutput`)
- `ForgetTarget` (`#[non_exhaustive]`; algorithm-local wrapper for one memory)
- `ForgetOutput` (`#[non_exhaustive]`; `Skipped`, `Candidate`, or `Forget`)
- `ForgetOutput::to_store_mutation_plan()` (adapter into frozen StoreMutation plans)
- `ForgetReason` (`#[non_exhaustive]`; algorithm-local forget reason)
- `ForgetSkipReason` (`#[non_exhaustive]`; algorithm-local skip reason)
- `NoOpForgetAlgorithm`
- `RuleBasedForgetAlgorithm` (deterministic heuristic implementation; emits forget, candidate, or skip decisions)
- `HebbianAlgorithm` (trait: `fn reinforce(&self, target: &HebbianTarget, ctx: &AlgorithmContext<'_>) -> HebbianOutput`)
- `HebbianTarget` (`#[non_exhaustive]`; algorithm-local aggregate of memory events)
- `HebbianOutput` (`#[non_exhaustive]`; `Skipped` or `Plans`)
- `HebbianSkipReason` (`#[non_exhaustive]`; algorithm-local skip reason)
- `NoOpHebbianAlgorithm`
- `RuleBasedHebbianAlgorithm` (deterministic heuristic implementation; emits edge-update plans)

Introduced by `v0.6.0-reflection-algorithm-skeleton`, `v0.6.2-reflection-deterministic-reference`, `v0.6.4-reflection-processing-adapter`, `v0.7.0-merge-algorithm-skeleton`, `v0.7.2-merge-rule-based-reference`, `v0.7.3-merge-benchmark`, `v0.7.4-merge-store-adapter`, `v0.8.0-forget-algorithm-skeleton`, `v0.8.2-forget-rule-based-reference`, `v0.8.3-forget-benchmark`, `v0.8.4-forget-store-adapter`, `v0.9.0-hebbian-algorithm-skeleton`, `v0.9.2-hebbian-rule-based-reference`, `v0.9.3-hebbian-benchmark`, and `v0.9.4-hebbian-store-adapter`. These items are algorithm-local; they do not extend RFC-011 and do not add new shared top-level adaptive types.

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
- `synapse_entities`
- `synapse_neighbors`
- `synapse_edges`
- `synapse_reinforce`
- `synapse_latent_activation`
- `synapse_latent_query`
- `synapse_trace` (Experimental)

Tool JSON schemas are considered part of the stable public API except entries
explicitly marked Experimental.
`synapse_recall` accepts optional graph activation fields:
`graph_activation`, `graph_scale`, `graph_cap`, `graph_steps`, and
`graph_decay`. They are disabled by default.
`synapse_recall` also accepts optional post-recall Hebbian learning fields:
`reinforce` and `reinforce_k`. They are disabled by default and run only after
hits are computed.
`synapse_edges` accepts `id`, optional `direction` (`outgoing`, `incoming`,
or `both`), and optional `k`.
`synapse_reinforce` accepts `ids`, optional `event` (`recalled`, `written`,
`updated`, `reflected`, `reinforced`, or `merge_completed`), and optional
`query`. It routes co-occurrence through the rule-based Hebbian algorithm,
Hebbian executor, StoreMutation dispatcher, and SQLite persistent executor.
`synapse_latent_activation` accepts `id`, optional `k`, `scale`, `cap`,
`steps`, `decay`, `fanout`, `state_terms`, and `goal_terms`.
`synapse_latent_query` accepts `query`, optional `k`, `seed_k`, `scope`,
`kind`, `scale`, `cap`, `steps`, `decay`, `fanout`, `state_terms`, and
`goal_terms`, and `auto_context`.
`synapse_trace` accepts `query`, optional `k`, `latent_k`, `seed_k`,
`suppressed_k`, `scope`, `kind`, `scale`, `cap`, `steps`, `decay`, `fanout`,
`state_terms`, `goal_terms`, `auto_context`, `reinforce`, and `reinforce_k`.
It returns a cognitive trace report with dominant and suppressed candidates
plus visible and latent evidence. Trace reinforcement is disabled by default
and, when enabled, runs only after the trace report is computed. It learns
associations between the top visible seed memories and the dominant trace
candidate for future activation.

## kr (CLI)

**Stable (command surface)**

- `kr write`
- `kr recall`
- `kr list`
- `kr where`
- `kr forget`
- `kr entities`
- `kr neighbors`
- `kr edges`
- `kr reinforce`
- `kr latent`
- `kr latent-query`
- `kr trace` (Experimental)

Flag names and output structure are considered part of the stable public API
except entries explicitly marked Experimental.
`kr recall` supports optional graph activation flags:
`--graph-activation`, `--graph-scale`, `--graph-cap`, `--graph-steps`, and
`--graph-decay`. They are disabled by default.
`kr recall` also supports optional latent activation flags:
`--latent-activation`, `--latent-seed-k`, `--latent-scale`, `--latent-cap`,
`--latent-steps`, `--latent-decay`, `--latent-fanout`, repeated
`--latent-state`, repeated `--latent-goal`, and `--latent-auto-context`.
They are disabled by default and only add bonus to existing recall candidates.
`kr recall` also supports optional post-recall Hebbian learning flags:
`--reinforce` and `--reinforce-k`. They are disabled by default and run only
after recall results have been produced, so they do not affect the current
ranking.
`kr edges <id>` supports `--direction outgoing|incoming|both`, `-k`, and
`--json` for inspecting persisted associative edge weights.
`kr reinforce <id> <id>...` supports `--event`, `--query`, and `--json` for
learning associative edges from memories that co-occurred in one event.
`kr latent <id>` supports `--steps`, `--decay`, `--scale`, `--cap`,
`--fanout`, repeated `--state`, repeated `--goal`, `-k`, and `--json` for
inspecting hidden multi-step activation.
`kr latent-query <query>` supports `--seed-k`, `--scope`, `--kind`,
`--steps`, `--decay`, `--scale`, `--cap`, `--fanout`, repeated `--state`,
repeated `--goal`, `--auto-context`, `-k`, and `--json` for inspecting
query-triggered visible seed memories plus their hidden activation paths.
`kr trace <query>` supports `-k`, `--latent-k`, `--seed-k`,
`--suppressed-k`, `--scope`, `--kind`, `--steps`, `--decay`, `--scale`,
`--cap`, `--fanout`, repeated `--state`, repeated `--goal`,
`--auto-context`, `--reinforce`, `--reinforce-k`, and `--json` for inspecting
the dominant candidate, suppressed candidates, and hidden paths for a query.
Trace reinforcement is disabled by default and runs only after the report is
produced, so it does not affect the current dominant/suppressed ranking.

## synapse-eval

### benchmark harness contract (Phase 5)

**Stable**

- `AlgorithmMetric` (`#[non_exhaustive]`; 11 IDs: `RecallAt10`, `PrecisionAt10`, `MemoryGrowth`, `CompressionRatio`, `ReflectionYield`, `MergePrecision`, `ForgetPrecision`, `HebbianConsistency`, `CognitiveTraceDominance`, `EventReplayLatency`, `AlgorithmLatency`)
- `BenchmarkReport` (`#[non_exhaustive]`; fields: `benchmark: String` in `lowercase-kebab-case` by convention, `metrics: BTreeMap<AlgorithmMetric, f64>`)

Invariants (RFC-011 Part D):
- `BenchmarkReport` is a deterministic value object: same `(dataset, algorithm, config)` → identical report. It MUST NOT carry runtime metadata (timestamp, hostname, cpu, random_seed, git_dirty).
- Reports are sparse: only meaningful metrics are included. Missing metrics MUST NOT be interpreted as `0.0`.
- Directory layout under `crates/eval/{datasets,benches,reports}/` is stable per `docs/COMPATIBILITY.md`. Adding a sibling directory is non-breaking; renaming or deleting one is breaking.

Frozen by `v0.5.3-benchmark-harness`. Included in the full Adaptive Common Model freeze at `v0.5.9-adaptive-common-freeze`.

### legacy benchmark runner

**Experimental**

- Benchmark harness (`kr-eval` binary), dataset TOML schema, `Recall@k` / `MRR@k` / `NDCG@k` metric outputs from `crates/eval/src/harness.rs` and `crates/eval/src/metrics.rs`.
- `reflection_yield_report()`, `deterministic_reflection_yield_report()`, `cognitive_chain_recall_report()`, `cognitive_trace_dominance_report()`, `merge_precision_report()`, `forget_precision_report()`, `hebbian_consistency_report()`, and algorithm benchmark helpers under `crates/eval/src/algorithms.rs`.

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
