# API Surface

This document lists the stable public API of King Synapse as of `v0.5.9-adaptive-common-freeze`.

APIs are classified into three levels:

- **Stable** 鈥?SemVer-guaranteed. Breaking changes require a major version bump. See `docs/COMPATIBILITY.md`.
- **Experimental** 鈥?Public but subject to change. Documented as such at introduction.
- **Internal** 鈥?Not part of the public API. May change at any time. Do not depend on internal items.

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

### adaptive cognition

**Experimental**

- `CognitiveCompetitionTrace`
- `CognitiveFactor`
- `CognitiveFactorType`
- `CognitiveTraceEvaluator`
- `CognitiveBooster`
- `CognitiveBoosterConfig`
- `CognitiveBoosterConfigError`
- `CognitiveBoosterInput`
- `CognitiveBoosterMode`
- `CognitiveAdjustedScore`
- `CognitiveBoosterOutput`
- `NoOpCognitiveBooster`
- `DeterministicCognitiveBoosterV0` (Experimental, shadow-only)
- `MAX_COGNITIVE_BOOSTER_BONUS`

The Phase 5.1 trace types are observation-only over already-returned
`RecallHit` candidates. The Phase 5.3.1 booster types are a separate,
OFF-by-default shadow proposal contract and are not the runtime
`RecallBooster` extension point. They receive immutable inputs, enforce bounded
candidate and bonus limits, and expose no `RecallEngine`, retriever, Store, or
memory mutation handle. No cognitive booster is registered with runtime recall.
Phase 5.3.2 adds `DeterministicCognitiveBoosterV0`, which converts trace
factors into bounded report-only score proposals; it is not registered with
`RecallEngine`, does not implement mutable runtime `RecallBooster`, and does not
authorize production ranking changes.

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
- `CognitiveTracePredictionReport`
- `CognitiveTracePredictionStatistics`

`CognitiveTraceProbe` composes visible recall, latent activation, and
state/goal context into a query-facing cognition report. The report identifies
one dominant candidate, suppressed candidates, visible recall hits, latent
activation paths, and the context terms that modulated hidden influence. It is
an inspection surface by default: it does not update graph edges, does not add
fields to `RecallHit`, and does not change recall ranking. Like normal recall,
seed retrieval may stamp access metadata. The CLI/MCP trace surfaces can
optionally run post-report Hebbian reinforcement; that learning is outside the
probe itself and routes through the Store Integration boundary. This surface is
Experimental while the cognitive competition scoring model is evaluated.

`CognitiveTraceProbe::predict_continuation()` is read-only trace continuation:
it starts from the current dominant trace candidate and follows outgoing
Store-owned associative edges to rank likely next hidden influences. The
prediction report carries the seed candidate, continuation candidates, paths,
activation scores, and modulation evidence. It does not mutate Store and does
not affect the current trace ranking.

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
- `AlgorithmContext::new(now, session_id, importance, events)` 鈥?the only supported constructor

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
`state_terms`, `goal_terms`, `auto_context`, `reinforce`, `reinforce_k`,
`predict`, and `prediction_k`.
It returns a cognitive trace report with dominant and suppressed candidates
plus visible and latent evidence. Predictive trace is disabled by default and
adds a read-only continuation report when enabled. Trace reinforcement is
disabled by default and, when enabled, runs only after the trace report is
computed. It learns associations between the top visible seed memories and the
dominant trace candidate for future activation.

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
`--auto-context`, `--predict`, `--prediction-k`, `--reinforce`,
`--reinforce-k`, and `--json` for inspecting the dominant candidate,
suppressed candidates, and hidden paths for a query.
Trace reinforcement is disabled by default and runs only after the report is
produced, so it does not affect the current dominant/suppressed ranking.

## Phase 5.3.3 cognitive policy evaluator

**Experimental; evaluation-only**

- `Phase5CognitivePolicyEvaluator`
- `load_cognitive_policy_benchmark()`
- `Phase5CognitivePolicyReport` and its benchmark, policy, scenario, candidate, metric, ablation, normalization, and safety report types
- `phase5_cognitive_policy` binary

This surface parses the controlled TOML benchmark under
`crates/eval/datasets/cognitive_policy/`, rebuilds real Store-backed candidate
IDs, and emits shadow policy comparisons. It has no `RecallEngine` registration,
no runtime authority, and no stable compatibility guarantee.

## Phase 5.3.4 cognitive generalization evaluator

**Experimental; evaluation-only**

- `Phase5CognitiveGeneralizationEvaluator`
- `Phase5CognitiveGeneralizationReport`
- `GeneralizationSplitReport`, `GeneralizationPolicySummary`, `GeneralizationDecision`, `FactorInteractionReport`, and safety/lock report types
- `phase5_cognitive_generalization` binary

This surface loads the disjoint controlled split under
`crates/eval/datasets/cognitive_policy_generalization/`, verifies split hashes,
applies the locked Margin Guard parameters, compares simple policy controls, and
reports held-out factor interactions. It is shadow-only, has no runtime
registration, and does not authorize end-to-end or production claims.

## Phase 5.4 end-to-end cognitive evaluator

**Experimental; evaluation-only**

- `Phase5EndToEndCognitiveEvaluator`
- `load_phase5_end_to_end_workload()`
- `Phase5EndToEndReport`
- `EndToEndProtocol`, `EndToEndDatasetSummary`, `EndToEndPolicyResult`, `EndToEndMetrics`, `EndToEndDecision`, `EndToEndSafetyGuards`, and scenario/candidate/workload types
- `phase5_end_to_end_cognitive` binary

This surface writes the deterministic Agent-memory workload to isolated Stores,
uses `RecallEngine::recall_profiled` for all candidates and baseline scores,
generates real cognitive traces, and compares shadow-only controls. It does not
register a runtime booster or mutate authoritative recall output. Its `pass`
field validates protocol and safety integrity, not positive gain. The current
report records cognitive parity with the strongest recency/failure controls and
keeps runtime and production authorization false.

## Phase 6.0 memory intelligence benchmark evaluator

**Experimental; evaluation-only**

- `Phase6MemoryIntelligenceBenchmarkEvaluator`
- `load_phase6_memory_intelligence_benchmark()`
- `Phase6MemoryIntelligenceReport`
- `MemoryIntelligenceProtocol`, `MemoryIntelligenceDatasetSummary`, `MemoryIntelligenceRetrievalMetrics`, `MemoryIntelligenceGroupMetrics`, `MemoryIntelligenceGuards`, and scenario/memory specification and report types
- `phase6_memory_intelligence_benchmark` binary

This surface loads the generated 320-scenario workload under
`crates/eval/datasets/memory_intelligence/`, writes each scenario through an
isolated Store, and records real `RecallEngine::recall_profiled` rankings and
scores. It verifies generator/dataset hashes, balanced splits, ground-truth
labels, expected-candidate reachability, repeatable ranking, and no Store
mutation. It performs no algorithm comparison and has no runtime authority or
stable compatibility guarantee. Its `pass` field is a benchmark-integrity gate,
not evidence of cognitive gain.

## Phase 6.1 cognitive baseline comparison evaluator

**Experimental; evaluation-only**

- `Phase6CognitiveBaselineComparisonEvaluator`
- `Phase6CognitiveBaselineComparisonReport`
- `CognitiveBaselineComparisonProtocol`, `CognitiveBaselineDatasetSummary`, `PolicyResult`, `AblationResult`, `ComparisonMetrics`, `CognitiveBaselineDecision`, `FactorContribution`, `CognitiveBaselineComparisonGuards`, and scenario/candidate report types
- `phase6_cognitive_baseline_comparison` binary

This surface reuses the Phase 6.0 dataset and real RecallEngine candidate pools
to compare fixed simple heuristics with the unchanged Margin-Guard Cognitive
policy. Factor ablations remove one trace factor before invoking the same
booster. It is shadow-only and has no Store, schema, retrieval, candidate, or
runtime mutation authority. The current report records policy equality at a
zero-competition-eligibility operating point; independent value and metadata-
aggregation attribution are both unresolved.
## synapse-eval

### benchmark harness contract (Phase 5)

**Stable**

- `AlgorithmMetric` (`#[non_exhaustive]`; 11 IDs: `RecallAt10`, `PrecisionAt10`, `MemoryGrowth`, `CompressionRatio`, `ReflectionYield`, `MergePrecision`, `ForgetPrecision`, `HebbianConsistency`, `CognitiveTraceDominance`, `EventReplayLatency`, `AlgorithmLatency`)
- `BenchmarkReport` (`#[non_exhaustive]`; fields: `benchmark: String` in `lowercase-kebab-case` by convention, `metrics: BTreeMap<AlgorithmMetric, f64>`)

Invariants (RFC-011 Part D):
- `BenchmarkReport` is a deterministic value object: same `(dataset, algorithm, config)` 鈫?identical report. It MUST NOT carry runtime metadata (timestamp, hostname, cpu, random_seed, git_dirty).
- Reports are sparse: only meaningful metrics are included. Missing metrics MUST NOT be interpreted as `0.0`.
- Directory layout under `crates/eval/{datasets,benches,reports}/` is stable per `docs/COMPATIBILITY.md`. Adding a sibling directory is non-breaking; renaming or deleting one is breaking.

Frozen by `v0.5.3-benchmark-harness`. Included in the full Adaptive Common Model freeze at `v0.5.9-adaptive-common-freeze`.

### legacy benchmark runner

**Experimental**

- Benchmark harness (`kr-eval` binary), dataset TOML schema, `Recall@k` / `MRR@k` / `NDCG@k` metric outputs from `crates/eval/src/harness.rs` and `crates/eval/src/metrics.rs`.
- `reflection_yield_report()`, `deterministic_reflection_yield_report()`, `cognitive_chain_recall_report()`, `cognitive_trace_dominance_report()`, `trace_reinforcement_report()`, `predictive_trace_report()`, `activation_parameter_sweep_report()`, `long_horizon_cognitive_memory_report()`, `exported_cognitive_session_report()`, `merge_precision_report()`, `forget_precision_report()`, `hebbian_consistency_report()`, and algorithm benchmark helpers under `crates/eval/src/algorithms.rs`.

The `kr-eval` runner and its `Report` output type predate `BenchmarkReport` and are not part of the v0.5.3 harness contract. They remain Experimental during Phase 5 and may be migrated onto `BenchmarkReport` in a later milestone.

## Public Guarantees

1. Stable APIs will not change in incompatible ways within a `0.5.x` line.
2. Every stable trait ships with at least one `NoOp` or `PlanOnly` implementation for testing.
3. Reports (`ExecutionReport`, `ReflectionReport`, `HebbianExecutionReport`, `StoreExecutionReport`, `PolicyReport`) are immutable after emission.
4. Sinks are observer-only and must not mutate reports.
5. Behavior modules must not call `Store`, `RecallEngine`, or LLMs directly; they must go through their frozen dispatcher / adapter path.
6. Phase 5 algorithm work must not change stable APIs. Algorithm implementations plug in behind existing traits.

## Item Classification Rules

- If an item is re-exported from `synapse_core::*` and appears above 鈫?**Stable**.
- If an item is re-exported from `synapse_core::*` but marked *Experimental* in this document 鈫?**Experimental**.
- If an item is not re-exported at the crate root 鈫?**Internal**.
- Test-only items (`#[cfg(test)]`, `PlanOnly*` helpers used in tests) may be stable but should be documented as such.


## Phase 6.2 recall score distribution evaluator

Eval-only exports from `synapse-eval`:

- `Phase6RecallScoreDistributionEvaluator`
- `Phase6RecallScoreDistributionReport`
- `RecallScoreDistributionProtocol`
- `DistributionSummary`
- `CandidateCountDistribution`
- `ScoreDistributionReport`
- `RankScoreDistribution`
- `AdjacentGapDistribution`
- `MarginCoverage`
- `GroupMarginCoverage`
- `RecallScoreScenarioReport`
- `RecallScoreDistributionDecision`
- `RecallScoreDistributionGuards`
- `phase6_recall_score_distribution` binary

This surface re-runs `Phase6MemoryIntelligenceBenchmarkEvaluator`, observes the returned real `RecallHit.score` values, and produces descriptive score/gap and fixed-margin coverage statistics. It does not execute Cognitive ranking, choose a threshold, modify RecallEngine, register a runtime booster, or authorize Hermes/runtime integration.

## Phase 7.0 cognitive architecture contract

Eval-only exports from `synapse-eval`:

- `Phase7CognitiveArchitectureContractEvaluator`
- `Phase7CognitiveArchitectureContractReport`
- `PatternCandidate`
- `PatternStatus`
- `EvidenceReference`
- `PatternCondition`
- `PatternPrediction`
- `FalsificationCondition`
- `PatternContractValidation`
- `PatternLifecycleTransition`
- `ConfidenceUpdatePolicy`
- `CognitiveArtifactContract`
- `NorthStarContract`
- `Phase7ArchitectureDecision`
- `Phase7ArchitectureGuards`
- `validate_pattern_candidate`
- `phase7_cognitive_architecture_contract` binary

This surface is Experimental and eval-only. It defines the evidence and authority contract for future Pattern research. It does not modify stable `synapse-core` APIs, persist Patterns, change RecallEngine or CognitiveBooster, execute Pattern discovery, connect Hermes, or authorize runtime.

## Phase 7.1 Transfer evaluation surface

Eval-only module:

```text
synapse_eval::phase7_transfer_evaluation_protocol
```

Primary entry points:

```rust
load_phase7_transfer_benchmark()
validate_transfer_scenario(&TransferScenario)
Phase7TransferEvaluationProtocolEvaluator::evaluate(tag)
```

Primary contracts:

```text
TransferBenchmarkDataset
TransferScenario
TransferEvidence
TransferPatternCandidate
EvidenceGraphEdge
ExpectedTransfer
DangerousTransfer
TransferExperimentArm
TransferArmContract
TransferMetricDefinition
TransferFailureTaxonomyEntry
Phase7TransferEvaluationReport
```

Report generator:

```text
cargo run -p synapse-eval --bin phase7_transfer_evaluation_protocol
```

This surface is not exported through `synapse-core`, CLI recall, MCP runtime tools, or the production memory schema. It cannot write memories, promote Patterns, modify rankings, or execute strategies.

## Phase 7.2 Pattern extraction protocol surface

Eval-only module:

```text
synapse_eval::phase7_pattern_extraction_protocol
```

Primary entry points:

```rust
load_phase7_pattern_extraction_design()
validate_pattern_extraction_submission(input, candidate)
validate_pattern_extraction_batch(input, candidates)
Phase7PatternExtractionProtocolEvaluator::evaluate(tag)
```

Provider boundary:

```rust
trait PatternExtractionProvider {
    fn provider_id(&self) -> &str;
    fn extract(&self, input: &PatternExtractionInput) -> Result<Vec<PatternCandidate>>;
}
```

Primary contracts:

```text
PatternExtractionDataset
PatternExtractionCase
PatternExtractionInput
ExtractionExperience
PatternExtractionSubmissionValidation
PatternExtractionBatchValidation
PatternExtractionMetricDefinition
PatternExtractionProtocolGuards
Phase7PatternExtractionReport
```

Report generator:

```text
cargo run -p synapse-eval --bin phase7_pattern_extraction_protocol
```

No provider implementation is present. This surface cannot read held-out transfer cases, write memories, promote Patterns, claim validation outcomes, invoke Hermes, or modify runtime behavior.

## Phase 7.2.1 eval-only extraction API

Module:

```text
synapse_eval::phase7_bounded_pattern_extraction_provider
```

Primary API:

```rust
DeterministicBoundedPatternExtractionProvider::new()
PatternExtractionProvider::extract(&PatternExtractionInput)
Phase7BoundedPatternExtractionEvaluator::evaluate(tag)
evaluate_provider(tag, provider, frozen_provider_config)
```

The module is evaluation-only. It exports frozen provider configuration, per-case contract disposition, deterministic extraction-quality diagnostics, fault-injection results, and a JSON report. It does not expose persistence, knowledge promotion, RecallEngine mutation, Hermes integration, or runtime ranking authority.

## Phase 7.2.2 eval-only provider comparison API

Module:

```text
synapse_eval::phase7_pattern_provider_comparison
```

Primary API:

```rust
Phase7ProviderComparisonEvaluator::evaluate(tag)
load_phase7_provider_manifests()
load_phase7_model_execution()
strict_parse_pattern_candidate_json(raw)
```

Primary contracts:

```text
ProviderComparisonManifestSet
ProviderManifest
StrictParserPolicy
ExtractionScorerPolicy
ModelProviderExecutionArtifact
ModelProviderCaseOutput
ProviderCapabilityRow
ProviderComparisonProtocolGuards
Phase7ProviderComparisonReport
```

The API verifies frozen SHA-256 identities, reports the weak baseline and model provider as separate capability rows, and leaves unavailable model metrics as `None`. It cannot access held-out transfer cases, repair model output, persist Pattern Candidates, promote knowledge, invoke Hermes, or modify runtime behavior.

## Phase 7.2.3 real provider readiness API

Module:

```text
synapse_eval::phase7_real_provider_readiness
```

Primary API:

```rust
Phase7RealProviderReadinessEvaluator::evaluate(tag)
load_phase7_real_provider_execution()
```

Primary contracts:

```text
ProviderReadinessPreflight
ReadinessArtifactHashes
RealProviderCaseReadiness
RealProviderReadinessSummary
RealProviderReadinessGuards
Phase7RealProviderReadinessDecision
Phase7RealProviderReadinessReport
```

The API verifies that a real provider completed all ten design requests exactly once under the frozen Phase 7.2.2 prompt/parser/scorer/dataset identities. It emits per-case deterministic quality diagnostics and explicitly separates `provider_ready` from candidate learning, persistence, knowledge promotion, transfer, Hermes, and runtime authority.

## Phase 7.3 candidate error analysis API

Module:

```text
synapse_eval::phase7_candidate_error_analysis
```

Primary API:

```rust
Phase7CandidateErrorAnalysisEvaluator::evaluate(tag)
load_phase7_candidate_error_annotations()
```

Primary contracts:

```text
CandidateFailureKind
CandidateFailureLabel
MetricConfoundKind
FalsifiabilitySeedAssessment
CandidateErrorSeedCase
CandidateErrorAnnotationDataset
CandidateErrorCaseAnalysis
CandidateErrorAnalysisSummary
CandidateErrorAnalysisGuards
Phase7CandidateErrorAnalysisDecision
Phase7CandidateErrorAnalysisReport
```

The API validates that the seed annotations cover exactly the ten frozen Phase 7.2.3 design outputs and match each output `response_sha256`. It aggregates primary and secondary failure mechanisms, scorer confounds, and falsifiability structure without invoking a provider or changing the frozen prompt, parser, scorer, extraction algorithm, held-out dataset, persistence, Hermes, or runtime authority.

## Phase 7.3.1 independent adjudication and frozen-Judge calibration API

Module:

```text
synapse_eval::phase7_independent_adjudication_calibration
```

Primary API:

```rust
Phase7AdjudicationCalibrationEvaluator::evaluate(tag)
load_phase7_adjudication_measurement_protocol()
load_phase7_reviewer_a_template()
load_phase7_reviewer_b_template()
load_phase7_adjudication_template()
build_phase7_blind_review_packet()
compute_support_agreement(labels)
aggregate_candidate_support_label(claim_labels)
aggregate_candidate_scope_expansion(scope_labels)
compute_confusion_matrix(rows, view)
compute_scope_confusion_matrix(rows)
```

Primary contracts:

```text
Phase7AdjudicationMeasurementProtocol
MeasurementObjectDefinition
ClaimSourceAnchor
BlindReviewCase
BlindReviewPacket
AtomicClaimAnnotation
ReviewerAnnotationSubmission
AdjudicationSubmission
ClaimOrigin
HumanSupportLabel
DisagreementKind
JudgeFailureKind
SupportAgreementMetrics
CandidateJudgeCalibrationRow
ScopeJudgeCalibrationRow
ConfidenceInterval
ConfusionMatrix
Phase7AdjudicationCalibrationGuards
Phase7AdjudicationCalibrationReport
```

The evaluator derives 65 exact hash-bound claim-source anchors from the frozen Phase 7.2.3 Candidate fields. It intentionally emits no agreement or calibration values while both blind reviewer templates and adjudication remain incomplete. The frozen Judge emits Candidate-level warnings rather than atomic-Claim decisions, so adjudicated Claim labels are first aggregated into Candidate-level support and scope labels before confusion-matrix comparison; one Candidate warning is never duplicated across all Claims. Support and scope calibration include Wilson 95% intervals when observations become available. The module cannot call a Provider, modify the Candidate or frozen Judge, access held-out cases, persist knowledge, invoke Hermes, or authorize runtime behavior.


## Phase 7.3.1-B inter-reviewer Agreement Gate API

Module:

```text
synapse_eval::phase7_inter_reviewer_agreement
```

Primary API:

```rust
Phase7InterReviewerAgreementEvaluator::evaluate(tag)
load_phase7_inter_reviewer_agreement_protocol()
compute_inter_reviewer_agreement(reviewer_a, reviewer_b, alignment_policy)
```

Primary contracts:

```text
ClaimSourceSpan
ClaimAlignmentPolicy
ClaimAlignment
SegmentationAgreementMetrics
SemanticAgreementMetrics
InterReviewerAgreementMetrics
InterReviewerAgreementProtocol
InterReviewerAgreementGuards
InterReviewerAgreementDecision
InterReviewerAgreementReport
```

The API aligns independently segmented Claims by frozen Unicode-character spans within the same `case_id + anchor_id`. Matching uses deterministic descending span IoU with a predeclared `0.50` minimum and never uses Claim-text similarity. It reports segmentation, Claim-count, support, provenance, scope, causal, prediction, counterexample, falsifiability, and confidence agreement only after both raw blind submissions are complete. Adjudicated labels and frozen-Judge outputs are forbidden inputs.

## Phase 7.3.1-C artifact lineage transition API

Module: `phase7_artifact_lineage_transition_gate`

Primary entry points:

- `Phase7ArtifactLineageTransitionEvaluator::evaluate`
- `load_phase7_artifact_lineage_protocol`
- `derive_phase7_workflow_state`
- `validate_phase7_workflow_transition`
- `validate_agreement_artifact_lineage`
- `validate_phase7_adjudication_artifact_lineage`
- `exact_file_sha256`

Primary types:

- `Phase731WorkflowState`
- `WorkflowFacts`
- `WorkflowPermissions`
- `IndependentReviewProgress`
- `ArtifactDigest`
- `ArtifactLineageStatus`
- `AgreementArtifactLineage`
- `AdjudicationLineageReference`
- `Phase7ArtifactLineageTransitionReport`

The API authorizes only one-step forward transitions or same-state rechecks. Exact upstream-file hash mismatches derive `ArtifactLineageInvalid` and disable downstream permissions.

## Phase 7.3.1-D model-adjudicated Silver freeze API

Module: `phase7_model_adjudicated_silver_freeze`

Primary entry points:

- `Phase7ModelAdjudicatedSilverFreeze::build`
- `validate_model_adjudicated_silver_freeze`

Primary types:

- `ModelAdjudicatedSilverFreezeArtifact`
- `ModelAdjudicatedSilverClaim`
- `ModelAdjudicatedSilverCandidateLabel`

The API deterministically resolves each adjudicated group back to one design case, freezes 77 claim labels and ten conservative candidate aggregates, and binds the artifact to the exact adjudication SHA-256. The labels are model-adjudicated Silver, never human Gold. Scope calibration is deliberately unavailable because final scope labels were not adjudicated.


### Phase 7.3.1-F diagnostic calibration result

`Phase7AdjudicationCalibrationReport` now includes exact Silver/Judge lineage hashes, ten transparent `candidate_calibration_rows`, strict-safety and strong-error confusion matrices, and a deliberately null `scope_calibration`. Calibration-facing row fields use `silver_support_label`; model Silver is never represented as human Gold.
