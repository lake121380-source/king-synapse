# Working Memory

## Goal

Working Memory is the Phase 3 overlay that lets a session hold temporary state, influence recall through additive activation, plan consolidation without executing it, and emit reflection events without mutating the Recall contract.

## Architecture

```text
SessionId
  ├─ WorkingMemoryBuffer
  │    ├─ WorkingMemoryItem
  │    └─ WorkingMemoryEdge
  ├─ WorkingMemoryActivationBooster
  ├─ ConsolidationEngine -> ConsolidationPlan
  └─ ReflectionEventRecorder -> ReflectionEvent
```

## Session Lifecycle

1. A session gets a `SessionId`.
2. Temporary items live in `WorkingMemoryBuffer` only for that session.
3. Expired items are cleared from the buffer.
4. Recall may read the session id and apply activation bonuses.
5. Consolidation produces a plan for promotion, merge, or discard.
6. Reflection records the plan as events.

## Activation Flow

- `WorkingMemoryActivationBooster` is the only Phase 3 recall extension point.
- It reads `BoosterContext.session_id` and `WorkingMemoryBuffer`.
- It only adds to `RecallHit::activation_bonus`.
- It does not create hits, reorder hits, or change any other `RecallHit` field.
- Bonus application is capped per hit and per linked memory.

## Consolidation Flow

- `ConsolidationEngine` is a planner only.
- It returns `ConsolidationPlan` with `promote`, `merge`, and `discard` buckets.
- It does not write to Store.
- It does not call Recall.
- It does not perform merge or archival execution.

## Reflection Event Flow

- `ReflectionEventRecorder` captures structured lifecycle events.
- `ReflectionEvent` is an audit record, not a state mutation.
- `ReflectionPayload` describes promoted, merged, and discarded memory ids.
- `ReflectionSource` identifies the origin of the event.
- Reflection must not write memory, change recall, or alter store state.

## Design Invariants

1. Recall contract stays frozen unless an ADR explicitly changes it.
2. Working Memory is session-scoped and in-memory only.
3. Activation is additive only.
4. Consolidation is planning only.
5. Reflection is observation only.
6. Phase 3 adds extensions before executors.

## Future Extensions

- P3.5 Hebbian reinforcement is a skeleton contract: it consumes reflection output and returns `EdgeUpdatePlan` without applying graph updates.
- Consolidation execution can be introduced later when there is a real consumer.
- Store schema changes remain outside this contract unless an ADR approves them.
