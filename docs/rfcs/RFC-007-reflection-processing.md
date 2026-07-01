# RFC-007: Reflection Processing

Status: Accepted

Phase: P4.2 Reflection Processor

Implemented by:

- `v0.4.10-reflection-skeleton`
- `v0.4.11-reflection-dispatcher`
- `v0.4.12-reflection-sink`
- `v0.4.19-reflection-processing-freeze`

## Summary

Reflection Processing turns existing `ReflectionEvent` records into deterministic reflection plans and reports. The first version establishes the execution model only; it does not generate free-form reflections or mutate system state.

## Motivation

P4.1 froze the Adaptive Memory execution model:

```text
Plan
  -> Execute
  -> Report
  -> Sink
```

P4.2 applies the same shape to Reflection:

```text
ReflectionEvent
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink
```

The goal is architectural consistency before behavior complexity.

## Scope

In scope:

- Consume existing `ReflectionEvent` values.
- Produce a deterministic `ReflectionPlan`.
- Execute the plan into a semantic `ReflectionReport`.
- Dispatch reflection actions deterministically.
- Provide a `NoOpReflectionSink`.
- Preserve benchmark baselines.

Out of scope:

- Store writes.
- RecallEngine calls.
- LLM calls.
- Memory mutation.
- Consolidation execution.
- Hebbian edge updates.
- Forgetting policy.

## Contract

Reflection Processing must follow:

```text
ReflectionEvent
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink
```

`ReflectionReport` describes semantic reflection outcomes only. Operational metrics belong to observers or sinks.

The report contains:

- Executed actions
- Skipped actions
- Warnings
- Statistics

Sinks consume reports only:

```text
ReflectionReport
  -> ReflectionSink
```

Sinks are observers. They must not generate plans, mutate reports, mutate memory, call Store, or call Recall.

## Invariants

1. Reflection Processing does not change the Recall contract.
2. Reflection Processing does not change the Memory Evolution contract.
3. Reflection Processing does not call Store.
4. Reflection Processing does not call Recall.
5. Reflection Processing does not call an LLM.
6. Reflection Processing does not mutate memory or graph edges.
7. Reflection sinks may consume reports, but they must not mutate them.
8. Multiple sinks must observe the same immutable report deterministically.
9. Sink failures must not affect executor output.

## Acceptance Criteria

- A `NoOpReflectionProcessor` or equivalent NoOp path exists for tests and default wiring.
- Empty or structurally inert reflection input produces an empty report.
- Non-empty reflection input produces deterministic report entries.
- `reference` remains `Recall@10 = 1.000`.
- `multihop` remains `Recall@10 = 0.600`.
