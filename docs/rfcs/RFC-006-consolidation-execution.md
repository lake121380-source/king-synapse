# RFC-006: Consolidation Execution

Status: Draft

Phase: P4.1 Consolidation Executor

## Summary

Consolidation Execution turns a `ConsolidationPlan` into deterministic actions. It is the first Phase 4 behavior implementation because Working Memory currently has planning but no graduation path into durable memory.

## Motivation

Phase 3 froze this planning chain:

```text
WorkingMemoryBuffer
  -> ConsolidationEngine
  -> ConsolidationPlan
```

P4.1 adds the execution step:

```text
ConsolidationPlan
  -> ConsolidationExecutor
  -> deterministic writes and events
```

This closes the lifecycle gap between session-scoped Working Memory and long-term memory.

## Scope

In scope:

- Execute an existing `ConsolidationPlan`.
- Promote selected working-memory items into durable memories.
- Merge or discard plan entries according to deterministic rules.
- Emit reflection events for executed actions.
- Preserve benchmark baselines.

Out of scope:

- LLM-generated consolidation.
- Recall scoring changes.
- Reranker changes.
- Store schema changes without ADR approval.
- Hebbian edge updates.
- Forgetting or archival policy.

## Contract

The executor consumes a completed plan and returns an immutable execution report.

```text
ConsolidationPlan
  -> ConsolidationExecutor
  -> ExecutionReport
```

The executor must be deterministic for the same plan and store state.

`ExecutionReport` is immutable after execution and represents the complete deterministic outcome of a consolidation pass. Sinks may consume the report, but they must not modify it.

The report contains:

- Executed actions
- Skipped actions
- Warnings
- Statistics

`ExecutionReport` describes semantic execution outcomes only. Operational metrics such as latency, database write count, tracing ids, or token usage belong to observers or sinks.

Sinks consume reports only:

```text
ExecutionReport
  -> ConsolidationSink
```

Sinks must not consume `ConsolidationPlan`, `WorkingMemoryBuffer`, or `Store` directly through the executor path.

## Invariants

1. The executor does not change the Recall contract.
2. The executor does not change the `ConsolidationPlan` contract.
3. The executor does not invoke Recall.
4. The executor does not call an LLM.
5. Reflection events are outputs of execution, not inputs that modify the plan.
6. Failed execution must not be hidden as success.
7. Sinks may consume `ExecutionReport`, but they must not mutate it.

## Open Design Points

- Mapping from `WorkingMemoryItem` to `WriteInput`.
- Merge semantics for `MergeStrategy::Deduplicate`, `Union`, and `Compress`.
- Whether execution should be all-or-nothing or best-effort with partial reports.

## Acceptance Criteria

- A `NoOpConsolidationExecutor` exists for tests and default wiring.
- A deterministic executor can execute a plan without using Recall or LLMs.
- Execution emits structured reflection events.
- `reference` remains `Recall@10 = 1.000`.
- `multihop` remains `Recall@10 = 0.600`.
