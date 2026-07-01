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

## Current Boundary

Adaptive Memory is deterministic and side-effect free through P4.3.

Frozen behavior modules may produce reports, but they must not directly mutate Store, graph edges, Recall scoring, or Working Memory.

## P4.4 Store Integration

P4.4 introduces persistence through adapters after reports already exist.

Planned shape:

```text
ExecutionReport / ReflectionReport / HebbianExecutionReport
  -> StoreAdapter
  -> StoreMutationPlan
  -> StoreMutationReport
  -> StoreMutationSink
  -> StoreExecutor
```

P4.4 must preserve these rules:

1. Frozen behavior reports remain immutable.
2. Store integration must be adapter-based.
3. Store writes must not change Recall contracts.
4. Store writes must preserve benchmark baselines.
5. Real persistence is introduced only after mutation plans and reports are deterministic.

## P4.5 Adaptive Policies

P4.5 should add policies after Store Integration exists.

Examples:

- `ReflectionPolicy`
- `HebbianPolicy`
- `ForgetPolicy`
- `MergePolicy`

Policies should select or parameterize behavior. They should not redefine the frozen execution model.
