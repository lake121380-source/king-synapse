# King Synapse Technical Whitepaper

## Summary

King Synapse is a local-first memory runtime for coding agents. It treats memory as an inspectable associative network rather than a hidden text cache or opaque embedding store.

The system is organized around three stable layers:

1. Storage Foundation captures durable memories and provenance.
2. Recall Platform retrieves explainable ranked memories through a frozen API.
3. Memory Evolution Contract defines how temporary session state can influence, plan, and learn from memory without mutating the recall contract.

## Problem

Coding agents repeatedly lose context between sessions. Existing approaches usually rely on flat notes, hidden vector stores, or manual prompt files. These systems make it difficult to inspect why a memory was recalled, how it changed, and whether future behavior is learning from past work.

King Synapse separates storage, recall, and evolution so each layer can be tested and frozen independently.

## Storage Foundation

The storage layer records durable memories with explicit scope, kind, source, confidence, importance, and validity timestamps.

Core principles:

- Memories are append-only and time-stamped.
- Provenance is part of the model.
- Scopes are explicit.
- Memory kinds have different decay behavior.
- The hot path remains local-first.

This layer provides primitives, not recall orchestration.

## Recall Platform

The Recall Platform is frozen at `v0.2.0-recall-api-freeze`.

Its responsibility is to turn one query into ranked `RecallHit` results.

```text
Query
  -> RecallEngine
  -> FTS / Vector / Entity retrieval
  -> RRF fusion
  -> optional Reranker
  -> additive RecallBoosters
  -> RecallHit
```

Frozen contracts:

- `RecallEngine` owns orchestration.
- `RecallHit` owns explainable result fields.
- `RecallBooster` can only add `activation_bonus`.
- RRF fuses retrieval signals only.
- Reranker reorders candidates only.
- Benchmark results gate recall changes.

The key rule is: evolve memory, not the Recall contract.

## Memory Evolution Contract

The Memory Evolution Contract is frozen at `v0.3.9-memory-evolution-freeze`.

It defines a five-layer architecture:

```text
WorkingMemoryBuffer
  -> WorkingMemoryActivationBooster
  -> ConsolidationPlan
  -> ReflectionEvent
  -> HebbianReinforcementEngine
```

Each layer is intentionally narrow.

### Working Memory

`WorkingMemoryBuffer` is an in-memory, session-scoped overlay. It stores temporary `WorkingMemoryItem` values and links to durable memory ids. It is not persisted, embedded, reranked, or fused into recall.

### Activation

`WorkingMemoryActivationBooster` is the only recall-facing extension from Working Memory. It reads `BoosterContext.session_id`, inspects linked memory ids, and adds capped `activation_bonus` values to existing hits.

It never creates candidates and never changes the Recall schema.

### Consolidation

`ConsolidationEngine` returns `ConsolidationPlan` with `promote`, `merge`, and `discard` buckets. It is planning only. It does not execute writes, call Store, or call Recall.

### Reflection

`ReflectionEvent` records structured lifecycle observations. Reflection is audit-only. It does not write memory, update graphs, or alter recall scoring.

### Hebbian Reinforcement

`HebbianReinforcementEngine` consumes reflection output and returns `EdgeUpdatePlan` values. The skeleton is planning only. It does not directly update a graph or database.

## Contract Boundaries

The architecture uses contracts to avoid accidental coupling:

- Store exposes primitives only.
- RecallEngine owns retrieval orchestration.
- Boosters are additive only.
- Working Memory is session-scoped only.
- Consolidation plans but does not execute.
- Reflection records but does not mutate.
- Hebbian reinforcement plans updates but does not apply them.

Breaking these boundaries requires ADR approval.

## Extension Pattern

King Synapse uses two recurring extension patterns:

- Trait -> NoOp -> concrete implementation
- Plan -> Execute -> Report -> Sink

Recall, Working Memory, Consolidation, Reflection, Hebbian reinforcement, Forgetting, and Sleep Cycle extensions should preserve these patterns unless an ADR approves a different shape.

Phase 4 code review should check every new behavior module against these rules:

1. Build on frozen Recall Platform, Memory Evolution Contract, and Adaptive Memory Foundation layers.
2. Preserve the `Plan -> Execute -> Report -> Sink` lifecycle.
3. Reuse `Trait -> NoOp -> Concrete Implementation` for new extension points.
4. Require ADR approval and a new architecture milestone for frozen-contract changes.
5. Require every new public trait to ship with a NoOp implementation.

## Behavior Modules

Consolidation, Reflection, and Hebbian Execution now share the same Adaptive Memory behavior shape:

```text
Trait
  -> NoOp
  -> Concrete

Plan
  -> Execute / Dispatch
  -> Report
  -> Sink
```

Store Integration, LLM Integration, and future behavior work should preserve this architecture unless an ADR approves a different shape.

See `docs/ADAPTIVE_MEMORY.md` for the Phase 4 data flow and Store Integration boundary.

## Evaluation

Behavior changes must preserve the frozen baselines:

```text
reference Recall@10 = 1.000
multihop  Recall@10 = 0.600
```

The `reference` dataset protects baseline recall behavior. The `multihop` dataset captures the starting line for future adaptive memory algorithms.

## Phase 4 Direction

Phase 4 is Adaptive Memory. It should implement strategies behind the frozen contracts instead of changing them.

The P4.1 Adaptive Memory Foundation is frozen at `v0.4.9-adaptive-memory-foundation`. Future adaptive behavior modules should reuse the `Plan -> Execute -> Report -> Sink` execution model.

P4.2 Reflection Processing is frozen at `v0.4.19-reflection-processing-freeze` and remains deterministic and side-effect free.

P4.3 Hebbian Execution is frozen at `v0.4.29-hebbian-execution-freeze` and remains deterministic and side-effect free.

P4.4 Store Integration is frozen at `v0.4.39-store-integration-freeze`. It defines the canonical persistence boundary for Phase 4 behavior modules and is the first Phase 4 milestone allowed to perform durable writes.

Planned work follows the RFC sequence:

- P4.5 Adaptive Policies

The development mode changes from defining interfaces to validating algorithms.
