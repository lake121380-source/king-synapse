# King Recall Roadmap

Current milestone

✓ Phase 1 — Capture Engine
✓ Phase 2 — Recall Platform (Recall API Freeze)
✓ Phase 3 — Memory Evolution Contract (Architecture Freeze)
✓ P4.1 — Adaptive Memory Foundation (Execution Model Freeze)
✓ P4.2 — Reflection Processing (Contract Freeze)
✓ P4.3 — Hebbian Execution (Contract Freeze)
✓ P4.4 — Store Integration (Contract Freeze)
✓ P4.5 — Adaptive Policies (Contract Freeze)
✓ v0.5.0 — Architecture Freeze (Public API + SemVer Policy)
✓ v0.5.1 — Memory Importance Skeleton
✓ v0.5.2 — Memory Event Kernel + AlgorithmContext Closure
✓ v0.5.3 — Benchmark Harness Contract Freeze
✓ v0.5.9 — Adaptive Common Model Freeze (RFC-011 Implemented)
✓ v0.6.3 — Reflection Yield Benchmark (RFC-012 benchmark milestone)
✓ v0.6.4 — Reflection Processing Adapter
✓ v0.6.5 — Reflection Store Mutation Plan

Status

Architecture: **Stable**

Adaptive Common Model: **Frozen**

Algorithm: **In Progress**

Current focus

▶ RFC-012 — Reflection Algorithm

Phase 5 shifts from shared-contract work to independent algorithm work. RFC-011 (Adaptive Common Model) is now frozen. RFC-012 through RFC-015 (Reflection, Merge, Forget, Hebbian) consume RFC-011 as read-only ground truth and MUST NOT extend it. Algorithm RFCs are also independent of one another — each depends only on RFC-011.

Phase 2 concluded with `v0.2.0-recall-api-freeze`. The Recall contract is now considered stable. Future work extends the platform rather than redesigning it.

Phase 3 concluded with `v0.3.9-memory-evolution-freeze`. The Memory Evolution contract layer is now considered stable. Future work should extend these interfaces instead of changing them.

P4.1 concluded with `v0.4.9-adaptive-memory-foundation`. The Adaptive Memory execution model is now considered stable. Future behavior modules should reuse the Plan -> Execute -> Report -> Sink shape.

P4.2 concluded with `v0.4.19-reflection-processing-freeze`. Reflection Processing is now contract-frozen and remains deterministic and side-effect free.

P4.3 concluded with `v0.4.29-hebbian-execution-freeze`. Hebbian Execution is now contract-frozen and remains deterministic and side-effect free.

P4.4 concluded with `v0.4.39-store-integration-freeze`. Store Integration is now contract-frozen and defines the canonical persistence boundary for Phase 4 behavior modules.

P4.5 concluded with `v0.4.49-adaptive-policies-freeze`. Adaptive Policies is now contract-frozen. Phase 4 is complete.

v0.5.0 concluded with `v0.5.0-architecture-freeze`. The whole-project public API is now stable under the compatibility policy in `docs/COMPATIBILITY.md`. Development mode shifts from **Contract-first** to **Algorithm-first**.

v0.5.9 concluded with `v0.5.9-adaptive-common-freeze`. RFC-011 is Implemented. The Adaptive Common Model (Importance, Event, Event Stream, Context, Metric, Report) is now frozen. Every subsequent algorithm RFC (RFC-012..015) depends only on RFC-011.

## Phase 5 — Algorithm Implementation

Goal

Turn the frozen contracts into concrete adaptive behavior without changing any stable API.

Completed foundations

- v0.5.1 — Memory Importance skeleton (10 tests)
- v0.5.2 — Memory Event kernel + AlgorithmContext closure (20 new tests)
- v0.5.3 — Benchmark harness contract (AlgorithmMetric, BenchmarkReport)
- v0.5.9 — Adaptive Common Model freeze (RFC-011 Implemented)
- v0.6.3 — Reflection yield benchmark (`BenchmarkReport` mapped to `ReflectionYield`)
- v0.6.4 — Reflection output maps into existing Reflection Processing events
- v0.6.5 — Reflection plans map into canonical StoreMutation plans

Focus

- **RFC-012 Reflection Algorithm** — current milestone; replace deterministic reflection heuristics with production-quality signals before freeze.
- RFC-013 Merge Algorithm — concrete `MergePolicy` + `ConsolidationEngine` implementations.
- RFC-014 Forget Algorithm — concrete `ForgetPolicy` implementations.
- RFC-015 Hebbian Algorithm — concrete `HebbianReinforcementEngine` / `HebbianExecutor` implementations.
- Evaluation & benchmarks (DMR, LongMemEval, comparisons against Graphiti / Letta / Mem0).
- Parameter sweeps and ablation studies.

Rules

1. Phase 5 must not change any Stable API. All work plugs in behind existing traits.
2. Frozen benchmark baselines (`reference` `Recall@10 = 1.000`, `multihop` `Recall@10 = 0.600`) must be preserved or explicitly renegotiated through ADR.
3. Every concrete algorithm ships with a benchmark run demonstrating baseline preservation and target-metric improvement.
4. Algorithm parameters are internal by default; promotion to Stable API requires an ADR.
5. Post-freeze rules of RFC-011 apply: uniform call shape `fn method(&self, target, ctx)`, no new top-level shared types under `adaptive/`, algorithm RFCs are independent of one another, `AlgorithmContext` never owns data, benchmarks use only public API, renaming a frozen type is breaking.

## Phase 3 Contract

> **Phase 3 must not modify the Recall contract unless an ADR explicitly approves the change.**

Rules

1. `RecallHit` schema remains frozen.
2. `RecallBoosters` are the only extension point for recall scoring.
3. Every recall-related behavior change must preserve or improve benchmark results.

## Phase 3 — Memory Evolution

Status

Architecture Complete / Contract Frozen

Goal

Enable memories to evolve over time without changing the Recall Platform.

Frozen layers

- Working Memory Buffer
- Activation Booster
- Consolidation Plan
- Reflection Event
- Hebbian Reinforcement Skeleton

Contract tags

```text
v0.3.0  Working Memory Skeleton
v0.3.2  Working Memory Activation
v0.3.3  Consolidation Planning
v0.3.4  Reflection Event
v0.3.5  Hebbian Reinforcement Skeleton
v0.3.9  Memory Evolution Contract Freeze
```

## Phase 4 — Adaptive Memory

Goal

Turn the frozen memory-evolution contracts into adaptive behavior while preserving the Recall and Memory Evolution contracts.

Status: **Complete**. All P4.1–P4.5 milestones are contract-frozen. See the Phase 5 section above for the current focus.

Completed foundation

```text
P4.1 Consolidation Executor
  -> ConsolidationPlan
  -> ConsolidationExecutor
  -> ExecutionReport
  -> ConsolidationSink
```

Completed behavior contracts

```text
P4.2 Reflection Processing
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink

P4.3 Hebbian Execution
  -> EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
  -> HebbianSink

P4.4 Store Integration
  -> StoreMutation
  -> StoreMutationDispatcher
  -> StoreMutationPlan
  -> StoreAdapter / PersistentStoreExecutor
  -> StoreExecutionReport
  -> StoreSink

P4.5 Adaptive Policies
  -> PolicyRequest
  -> AdaptivePolicyEngine
  -> PolicyReport
  -> PolicySink
```

Contract rules

1. Do not change Phase 2 Recall contracts without ADR approval.
2. Do not change Phase 3 Memory Evolution contracts without ADR approval.
3. Prefer strategy implementations over interface changes.
4. Preserve `reference` and `multihop` benchmark baselines before merging behavior changes.
5. Start each Phase 4 implementation from an RFC.

RFC sequence

```text
RFC-006 Consolidation Execution
  -> RFC-007 Reflection Processing
  -> RFC-008 Hebbian Execution
  -> RFC-009 Store Integration
  -> RFC-010 Adaptive Policies
```

## Completed Milestones

v0.2.0-recall-api-freeze

Highlights

• RecallEngine
• Hybrid Retrieval (RRF)
• Pluggable Reranker
• Explainable Recall
• RecallHit Contract
• RecallBooster Extension Point
• Evaluation Harness

v0.3.9-memory-evolution-freeze

Highlights

• WorkingMemoryBuffer
• WorkingMemoryActivationBooster
• ConsolidationPlan
• ReflectionEvent
• HebbianReinforcementEngine
• Memory Evolution Contract

v0.4.9-adaptive-memory-foundation

Highlights

• ConsolidationExecutor
• ExecutionReport
• ConsolidationSink
• NoOpSink
• Plan -> Execute -> Report -> Sink model

v0.4.19-reflection-processing-freeze

Highlights

• ReflectionEngine
• ReflectionPlan
• ReflectionExecutor
• ReflectionReport
• ReflectionSink
• NoOpReflectionSink

v0.4.29-hebbian-execution-freeze

Highlights

• EdgeUpdatePlan
• HebbianExecutor
• HebbianExecutionReport
• HebbianSink
• NoOpHebbianSink

v0.4.39-store-integration-freeze

Highlights

• StoreMutation
• StoreMutationPlan
• StoreMutationDispatcher
• StoreAdapter
• StoreExecutionReport
• StoreSink
• PersistentStoreExecutor
• SQLitePersistentStoreExecutor

v0.4.49-adaptive-policies-freeze

Highlights

• PolicyDecision
• AdaptivePolicy
• ReflectionPolicy / HebbianPolicy / ForgetPolicy / MergePolicy
• PolicyRequest / PolicyReport
• AdaptivePolicyEngine
• DeterministicAdaptivePolicyEngine
• PolicySink
• NoOpPolicySink

v0.5.0-architecture-freeze

Highlights

• Whole-project public API declared stable
• `docs/API_SURFACE.md` (Stable / Experimental / Internal)
• `docs/COMPATIBILITY.md` (SemVer, breaking-change rules, deprecation policy)
• Final Architecture Rules (Trait → NoOp → Dispatcher → Report → Sink)
• Layer direction (Policy → Execution → Storage)
• Subsystem stack (Recall → Working Memory → Adaptive Memory → Store)
• Development mode: Contract-first → Algorithm-first
