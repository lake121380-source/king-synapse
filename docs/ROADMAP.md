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
✓ v0.6.6 — Rule-Based Reflection Algorithm
✓ v0.7.0 — Merge Algorithm Skeleton
✓ v0.7.1 — NoOp Merge Algorithm
✓ v0.7.2 — Rule-Based Merge Algorithm
✓ v0.7.3 — Merge Precision Benchmark
✓ v0.7.4 — Merge Store Adapter
✓ v0.8.0 — Forget Algorithm Skeleton
✓ v0.8.1 — NoOp Forget Algorithm
✓ v0.8.2 — Rule-Based Forget Algorithm
✓ v0.8.3 — Forget Precision Benchmark
✓ v0.8.4 — Forget Store Adapter
✓ v0.9.0 — Hebbian Algorithm Skeleton
✓ v0.9.1 — NoOp Hebbian Algorithm
✓ v0.9.2 — Rule-Based Hebbian Algorithm
✓ v0.9.3 — Hebbian Consistency Benchmark
✓ v0.9.4 — Hebbian Store Adapter
✓ v0.9.5 — SQLite Edge Persistence
✓ v0.9.6 — Graph Activation Booster
✓ v0.9.7 — Decayed Multi-Step Hidden Activation
✓ v0.9.8 — Edge Inspection Surface
✓ v0.9.9 — Latent Activation Probe
✓ v0.9.10 — Context-Modulated Latent Activation
✓ v0.9.11 — Query-Seeded Latent Activation
✓ v0.9.12 — Auto-Derived Latent Context
✓ v0.9.18 — Cognitive Trace Probe
✓ v0.9.19 — Trace Reinforcement Surface
✓ v0.9.20 — Trace Reinforcement Benchmark
✓ v0.9.21 — Activation Parameter Sweep
✓ v0.9.22 — Long-Horizon Cognitive Memory Benchmark
✓ v0.9.23 — Manual Validation Transcript
✓ v0.9.24 — Cognitive Network Algorithm Model
✓ v0.9.25 — Predictive Trace Continuation
✓ v0.9.26 — Exported Cognitive Session Benchmark
✓ v0.9.26-rc — Cognitive Memory Release Candidate Evidence
✓ v0.9.26-gate — Full Cognitive Memory Gate Validation
✓ v0.9.26-freeze — Cognitive Memory Freeze

Status

Architecture: **Stable**

Adaptive Common Model: **Frozen**

Algorithm: **Frozen**

Current focus

▶ Post-freeze evaluation and product integration

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
- v0.6.6 — Reflection switches from deterministic reference to rule-based heuristic
- v0.7.0 — Merge algorithm trait and target/output shape
- v0.7.1 — NoOp merge implementation
- v0.7.2 — Rule-based merge heuristic
- v0.7.3 — Merge precision benchmark (`BenchmarkReport` mapped to `MergePrecision`)
- v0.7.4 — Merge output maps into existing Consolidation and StoreMutation plans
- v0.8.0 — Forget algorithm trait and target/output shape
- v0.8.1 — NoOp forget implementation
- v0.8.2 — Rule-based forget heuristic
- v0.8.3 — Forget precision benchmark (`BenchmarkReport` mapped to `ForgetPrecision`)
- v0.8.4 — Forget output maps into existing StoreMutation plans
- v0.9.0 — Hebbian algorithm trait and target/output shape
- v0.9.1 — NoOp hebbian implementation
- v0.9.2 — Rule-based hebbian heuristic
- v0.9.3 — Hebbian consistency benchmark (`BenchmarkReport` mapped to `HebbianConsistency`)
- v0.9.4 — Hebbian edge plans map into existing StoreMutation plans
- v0.9.5 — `StoreMutation::UpdateEdge` persists directed edge weights in SQLite
- v0.9.6 — persisted edge weights add recall-time activation through `GraphActivationBooster`
- v0.9.7 — graph activation supports capped, decayed multi-step hidden influence inside the candidate pool
- v0.9.8 — persisted associative edges are inspectable through Store, CLI, and MCP surfaces
- v0.9.9 — latent activation can be probed from seed memories without changing recall candidates or rankings
- v0.9.10 — latent activation can be modulated by explicit state and goal terms while preserving path explanations
- v0.9.11 — natural-language queries can recall visible seed memories and inspect their hidden activation paths as a separate report
- v0.9.12 — query text can derive state and goal terms for latent inspection while keeping recall ranking unchanged
- v0.9.13 — Chinese cognitive-chain benchmark covers visible seed recall into hidden latent influence
- v0.9.14 — optional latent activation booster can add hidden-path bonus to existing recall candidates
- v0.9.15 — deterministic CJK query expansion raises `multihop` Recall@10 to 1.000
- v0.9.16 — CLI and MCP can reinforce co-occurring memories through the Hebbian -> StoreMutation -> SQLite path
- v0.9.17 — recall surfaces can optionally reinforce top-hit co-occurrence after returning results
- v0.9.18 — cognitive trace reports combine visible recall, latent activation, and context into dominant and suppressed candidates
- v0.9.19 — trace surfaces can optionally reinforce visible seeds to the dominant hidden influence after reporting
- v0.9.20 — trace reinforcement benchmark verifies dominant hidden influence can be learned into persisted edges
- v0.9.21 — activation parameter sweep verifies latent, trace, and trace-learning guarantees across multiple settings
- v0.9.22 — long-horizon cognitive-memory benchmark verifies multi-day traces in one shared memory store
- v0.9.23 — manual validation transcript covers normal and empty/error cognitive-memory surfaces
- v0.9.24 — cognitive network algorithm model maps human-network design into visible seeds, latent activation, dominant/suppressed candidates, and post-trace learning
- v0.9.25 — predictive trace continues from the dominant candidate into ranked next hidden influences
- v0.9.26 — exported cognitive-session TOML benchmark verifies visible recall, dominant hidden influence, predictive future continuation, and trace learning in one shared graph
- v0.9.26-rc — release-candidate note records cognitive-memory validation evidence and remaining final tag work
- v0.9.26-gate — full final acceptance command list passed and is recorded in the release validation note
- v0.9.26-freeze — RFC-012 through RFC-015 are freeze-reviewed by the cognitive-memory release note

Focus

- Predictive trace — broaden continuation benchmarks beyond the exported fixture.
- Release process — cut and push the cognitive-memory release/freeze tag.
- Evaluation & benchmarks (DMR, LongMemEval, comparisons against Graphiti / Letta / Mem0).
- Parameter sweeps and ablation studies.

Rules

1. Phase 5 must not change any Stable API. All work plugs in behind existing traits.
2. Frozen benchmark baselines (`reference` `Recall@10 = 1.000`, `multihop` `Recall@10 = 1.000` after ADR-006) must be preserved or explicitly renegotiated through ADR.
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
• `docs/COGNITIVE_MEMORY_FINAL_ACCEPTANCE.md` (final cognitive-memory gates)
• Final Architecture Rules (Trait → NoOp → Dispatcher → Report → Sink)
• Layer direction (Policy → Execution → Storage)
• Subsystem stack (Recall → Working Memory → Adaptive Memory → Store)
• Development mode: Contract-first → Algorithm-first
