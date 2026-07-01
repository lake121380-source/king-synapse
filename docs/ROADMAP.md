# King Recall Roadmap

Current milestone

✓ Phase 1 — Capture Engine
✓ Phase 2 — Recall Platform (Recall API Freeze)
✓ Phase 3 — Memory Evolution Contract (Architecture Freeze)
✓ P4.1 — Adaptive Memory Foundation (Execution Model Freeze)
✓ P4.2 — Reflection Processing (Contract Freeze)
✓ P4.3 — Hebbian Execution (Contract Freeze)

Status

Architecture Complete

Contract Frozen

Current focus

▶ Phase 4 — Adaptive Memory

Phase 2 concluded with `v0.2.0-recall-api-freeze`. The Recall contract is now considered stable. Future work extends the platform rather than redesigning it.

Phase 3 concluded with `v0.3.9-memory-evolution-freeze`. The Memory Evolution contract layer is now considered stable. Future work should extend these interfaces instead of changing them.

P4.1 concluded with `v0.4.9-adaptive-memory-foundation`. The Adaptive Memory execution model is now considered stable. Future behavior modules should reuse the Plan -> Execute -> Report -> Sink shape.

P4.2 concluded with `v0.4.19-reflection-processing-freeze`. Reflection Processing is now contract-frozen and remains deterministic and side-effect free.

P4.3 concluded with `v0.4.29-hebbian-execution-freeze`. Hebbian Execution is now contract-frozen and remains deterministic and side-effect free.

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

Focus

- P4.4 Store Integration
- P4.5 Adaptive Policies

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
