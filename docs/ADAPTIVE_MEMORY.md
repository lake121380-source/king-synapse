# Adaptive Memory

## Purpose

Adaptive Memory is the Phase 4 layer that turns frozen memory-evolution contracts into deterministic behavior chains.

It exists to connect session behavior, reflection, reinforcement, and future persistence without changing the Recall Platform or Memory Evolution contracts.

## Architecture

```text
WorkingMemoryBuffer
  -> WorkingMemoryActivationBooster
  -> ConsolidationPlan
  -> ConsolidationExecutor
  -> ExecutionReport
  -> ConsolidationSink
  -> ReflectionEvent
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink
  -> HebbianReinforcementEngine
  -> EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
  -> HebbianSink
  -> Store Integration
```

## Frozen Behavior Modules

### Consolidation

```text
ConsolidationPlan
  -> ConsolidationExecutor
  -> ExecutionReport
  -> ConsolidationSink
```

Status: frozen by `v0.4.9-adaptive-memory-foundation`.

### Reflection

```text
ReflectionEvent
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink
```

Status: frozen by `v0.4.19-reflection-processing-freeze`.

### Hebbian

```text
EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
  -> HebbianSink
```

Status: frozen by `v0.4.29-hebbian-execution-freeze`.

### Store Integration

```text
ExecutionReport / ReflectionReport / HebbianExecutionReport
  -> StoreMutationDispatcher
  -> StoreMutationPlan
  -> StoreAdapter / PersistentStoreExecutor
  -> StoreExecutionReport
  -> StoreSink
```

Status: frozen by `v0.4.39-store-integration-freeze`.

### Adaptive Policies

```text
PolicyRequest
  -> AdaptivePolicyEngine
  -> PolicyReport
  -> PolicySink
```

Status: frozen by `v0.4.49-adaptive-policies-freeze`. Policies emit `PolicyDecision::{Execute, Skip, Delay}` only. Policies never mutate memory, never call executors, and never touch Store or Recall.

## Current Boundary

Adaptive Memory is deterministic and side-effect free through P4.3. P4.4 introduced the first Phase 4 milestone allowed to perform durable writes, and only through `StoreAdapter` or `PersistentStoreExecutor`. P4.5 introduced the Policy Layer above the frozen execution chains.

Frozen behavior modules may produce reports, but they must not directly mutate Store, graph edges, Recall scoring, or Working Memory. All persistence is routed through the frozen Store Integration boundary. All decision making about whether frozen capabilities should run is routed through the frozen Policy Layer.

The user-facing reinforcement surfaces (`kr reinforce` and
`synapse_reinforce`) are consumers of that boundary. They build a
`MemoryEvent` from co-occurring memory ids, run the rule-based Hebbian
algorithm, execute the resulting `EdgeUpdatePlan`s, dispatch them into
`StoreMutation::UpdateEdge`, and persist through `SQLitePersistentStoreExecutor`.
The Hebbian algorithm still has no direct Store access.

Recall surfaces may opt into the same learning path after results are already
computed (`kr recall --reinforce`, `synapse_recall` with `reinforce: true`).
This records "these memories were recalled together" for future activation,
but it does not change the current recall ranking.

## P4.5 Adaptive Policies

P4.5 should add policies after Store Integration exists.

Examples:

- `ReflectionPolicy`
- `HebbianPolicy`
- `ForgetPolicy`
- `MergePolicy`

Policies should select or parameterize behavior. They should not redefine the frozen execution model.
