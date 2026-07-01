# RFC-009: Store Integration

Status: Accepted

Phase: P4.4 Store Integration

Implementation Tags:

```text
v0.4.30-store-adapter-skeleton
v0.4.31-store-mutation-dispatcher
v0.4.32-store-sink
v0.4.33-persistent-store-executor
v0.4.39-store-integration-freeze
```

## Summary

Store Integration connects frozen Adaptive Memory behavior reports to persistent state through a canonical mutation plan. It is the first Phase 4 area allowed to introduce durable writes, but only after Store mutations are represented as deterministic plans and routed through adapters.

## Motivation

P4.1 through P4.3 froze behavior modules as deterministic, side-effect-free chains:

```text
Behavior Layer
  -> Execution Report
  -> Sink
```

The system now needs a single persistence boundary:

```text
ExecutionReport / ReflectionReport / HebbianExecutionReport
  -> StoreMutationPlan
  -> StoreAdapter
  -> StoreExecutionReport
```

This prevents behavior modules from directly calling Store and keeps persistence replaceable.

## Scope

In scope:

- Define canonical `StoreMutation` variants.
- Convert behavior reports into `StoreMutationPlan` values.
- Dispatch behavior reports into mutation plans deterministically.
- Introduce `StoreAdapter` as the only Store integration entry point.
- Keep P4.4.1 through P4.4.3 deterministic and side-effect free.
- Allow real Store writes only in P4.4.4.
- Execute persistent mutations through `PersistentStoreExecutor`.

Out of scope:

- Recall contract changes.
- Memory Evolution contract changes.
- Direct behavior-module calls to Store.
- LLM behavior.
- Adaptive policy selection.

## Canonical Mutation Form

All upstream behavior must be normalized into `StoreMutation`.

```text
StoreMutation
  InsertMemory
  UpdateMemory
  DeleteMemory
  ArchiveMemory
  UpdateEdge
```

Store must not know whether a mutation came from Consolidation, Reflection, Hebbian, or future policies. Source may be stored as metadata, but it must not change the Store execution path.

## Contract

Store Integration must follow:

```text
ExecutionReport / ReflectionReport / HebbianExecutionReport
  -> StoreAdapter
  -> StoreMutationPlan
  -> StoreMutationReport
  -> StoreMutationSink
  -> StoreExecutor
```

Adapter is the only Store entry point. Code must not bypass it with direct Store writes.

The mutation dispatcher is pure:

```text
ExecutionReport
  -> StoreMutationDispatcher
  -> StoreMutationPlan
```

P4.4.2 starts with `ExecutionReport` and may extend to `ReflectionReport` and `HebbianExecutionReport` without changing Store backends.

Store sinks observe execution reports only:

```text
StoreExecutionReport
  -> StoreSink
```

Sinks must not mutate `StoreExecutionReport`, mutate `StoreMutationPlan`, or perform Store writes.

## P4.4 Milestones

```text
P4.4.1 Store Adapter Skeleton
  -> P4.4.2 Store Mutation Dispatcher
  -> P4.4.3 Store Mutation Sink
  -> P4.4.4 Persistent Executor
  -> P4.4 Freeze
```

P4.4.1 through P4.4.3 must remain pure, deterministic, and side-effect free.

P4.4.4 is the first milestone allowed to perform persistent mutations.

Persistent execution uses one report shape:

```text
StoreMutationPlan
  -> PersistentStoreExecutor
  -> StoreExecutionReport
```

Executors must match on `StoreMutation` only. They must not branch on behavior source such as Reflection, Hebbian, or Consolidation.

## Invariants

1. Store Integration does not change the Recall contract.
2. Store Integration does not change frozen behavior reports.
3. Store Integration must use canonical `StoreMutation` values.
4. Store must not depend on Reflection, Hebbian, Consolidation, Working Memory, or Recall types through the execution path.
5. Store writes must go through `StoreAdapter` or its approved executor path.
6. Store backends must remain replaceable behind adapters.
7. Persistent writes are forbidden before P4.4.4.
8. Benchmark baselines must be preserved before merging Store Integration behavior.
9. Store mutation dispatchers must be deterministic for identical inputs.
10. Store mutation dispatchers must not mutate input reports.
11. Store mutation dispatchers must not access Store, SQLite, Kuzu, or RecallEngine.
12. `StoreExecutionReport` is immutable after adapter execution.
13. `StoreSink` may observe reports, but it must not mutate them.
14. Multiple Store sinks must observe the same immutable report deterministically.
15. Store sink execution must not affect StoreAdapter output.
16. Store sinks must not produce persistent writes.
17. Persistent executors must not introduce backend-specific report types.
18. Persistent executors must not inspect behavior-module sources.
19. SQLite execution must use approved Store APIs instead of bypassing the Store layer with direct SQL.

## Acceptance Criteria

- RFC-009 defines the Store mutation boundary before code implementation.
- P4.4.1 introduces adapter skeleton without database IO.
- P4.4.2 introduces mutation dispatch without database IO.
- P4.4.3 introduces mutation sink without database IO.
- P4.4.4 introduces persistent writes through approved adapters.
- `reference` remains `Recall@10 = 1.000`.
- `multihop` remains `Recall@10 = 0.600`.
