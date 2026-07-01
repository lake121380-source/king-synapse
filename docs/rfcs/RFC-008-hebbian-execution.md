# RFC-008: Hebbian Execution

Status: Draft

Phase: P4.3 Hebbian Execution

## Summary

Hebbian Execution turns `EdgeUpdatePlan` values into deterministic execution reports. The first version establishes the execution model only; it does not update Store, graph edges, or Recall scoring.

## Motivation

P4.1 and P4.2 froze the Adaptive Memory behavior shape:

```text
Plan
  -> Execute / Dispatch
  -> Report
  -> Sink
```

P4.3 applies the same shape to Hebbian reinforcement:

```text
EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
  -> HebbianSink
```

The goal is to complete the behavior contract before real edge-weight execution exists.

## Scope

In scope:

- Consume existing `EdgeUpdatePlan` values.
- Execute plans into a deterministic `HebbianExecutionReport`.
- Dispatch edge update actions deterministically.
- Provide NoOp executor behavior for default wiring.
- Preserve benchmark baselines.

Out of scope:

- Store writes.
- Graph mutation.
- RecallEngine changes.
- LLM calls.
- Reflection execution.
- Consolidation execution.

## Contract

Hebbian Execution must follow:

```text
EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
```

`HebbianExecutionReport` describes semantic execution outcomes only. Operational metrics belong to observers or future sinks.

The report contains:

- Executed actions
- Skipped actions
- Warnings
- Statistics

## Invariants

1. Hebbian Execution does not change the Recall contract.
2. Hebbian Execution does not change the Memory Evolution contract.
3. Hebbian Execution does not call Store.
4. Hebbian Execution does not mutate graph edges.
5. Hebbian Execution does not call an LLM.
6. Executor output is deterministic for the same input plans.
7. Dispatcher must not modify `EdgeUpdatePlan` input values.
8. Executor must only generate execution reports, not apply edge updates.

## Acceptance Criteria

- A `NoOpHebbianExecutor` exists for default wiring.
- Empty input produces an empty report.
- Non-empty input produces deterministic report entries.
- Invalid input produces skipped actions and warnings.
- `reference` remains `Recall@10 = 1.000`.
- `multihop` remains `Recall@10 = 0.600`.
