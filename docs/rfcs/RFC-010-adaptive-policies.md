# RFC-010: Adaptive Policies

Status: Draft

Phase: P4.5 Adaptive Policies

Subtitle: Policy Layer for Adaptive Memory Decision Making

## Summary

Adaptive Policies introduce a decision layer above the frozen Adaptive Memory execution chains. Policies decide **whether** existing capabilities should run. They must not perform execution, must not mutate memory, and must not introduce new persistence.

## Motivation

Through P4.4 the system has frozen:

```text
Storage Foundation         Frozen
Recall Platform            Frozen (v0.2.0-recall-api-freeze)
Memory Evolution           Frozen (v0.3.9-memory-evolution-freeze)
Adaptive Memory Foundation Frozen (v0.4.9-adaptive-memory-foundation)
Reflection Processing      Frozen (v0.4.19-reflection-processing-freeze)
Hebbian Execution          Frozen (v0.4.29-hebbian-execution-freeze)
Store Integration          Frozen (v0.4.39-store-integration-freeze)
```

Every execution chain now has the same shape:

```text
Plan -> Execute -> Report -> Sink
```

A new question is now well-defined and previously undefined:

> When should these frozen capabilities be invoked?

RFC-010 answers that question with a dedicated Policy Layer. It does not answer *how well* they should be invoked; concrete strategy algorithms (forgetting curves, reinforcement schedules, LLM-driven decisions) are explicitly deferred.

## Scope

In scope:

- Define the canonical `PolicyDecision` value.
- Define `AdaptivePolicy` as the single Policy entry-point trait.
- Define `AdaptivePolicyEngine` as the deterministic dispatch surface.
- Define the four policy contracts: `ReflectionPolicy`, `HebbianPolicy`, `ForgetPolicy`, `MergePolicy`.
- Define the policy report shape and sink observation model.
- Keep P4.5.1 through P4.5.3 pure, deterministic, and side-effect free.
- Ship `NoOp` implementations for every trait before public use.

Out of scope:

- Concrete policy algorithms (forgetting curves, reinforcement thresholds, LLM decisions, learning-based policies).
- Changes to Recall contracts.
- Changes to Memory Evolution contracts.
- Changes to frozen behavior execution contracts (Consolidation, Reflection, Hebbian).
- Changes to Store Integration contracts.
- Direct memory mutation from policies.
- Persistent writes from policies.
- Cross-policy negotiation or arbitration algorithms.

## Layering

```text
Policy Layer
  ReflectionPolicy
  HebbianPolicy
  ForgetPolicy
  MergePolicy

  |
  v

Execution Layer
  Reflection
  Hebbian
  Consolidation
  Store Integration

  |
  v

Storage Layer
  SQLite
  Kuzu
  Future Backends
```

Policies live strictly above the Execution Layer. Execution modules must not depend on the Policy Layer. Policies may read frozen input types (e.g. `ReflectionEvent`, `EdgeUpdatePlan`, `ConsolidationPlan`, `StoreMutationPlan`) but must not construct them from behavior sources.

## Canonical Decision Form

All policies emit `PolicyDecision`. Policies do not emit mutations, plans, reports, or actions.

```text
PolicyDecision
  Execute
  Skip
  Delay
```

Semantics:

- `Execute` — the upstream capability may run using the same input the policy inspected.
- `Skip` — the upstream capability must not run for this input.
- `Delay` — the upstream capability is deferred; the caller may re-submit later. Delay must not carry side effects or scheduling behavior in P4.5.

A policy must always return exactly one `PolicyDecision` per input. Policies must not return execution artifacts, mutation plans, or reports.

## Contract

The Policy Layer must follow:

```text
PolicyInput
  -> AdaptivePolicy
  -> PolicyDecision
  -> AdaptivePolicyEngine
  -> PolicyDecisionReport
  -> PolicySink
```

`AdaptivePolicyEngine` dispatches to the correct policy based on input type. It must be pure: identical input produces identical decision reports. It must not touch Store, Recall, Working Memory, LLMs, or clocks.

`PolicySink` observes decision reports only. Sinks must not mutate reports, must not call back into policies, and must not produce persistent writes.

## Policy Contracts

### ReflectionPolicy

```text
ReflectionEvent
  -> ReflectionPolicy
  -> PolicyDecision
```

Determines whether a `ReflectionEvent` should be forwarded to `ReflectionEngine`. It must not construct reflection events, must not touch `ReflectionExecutor`, and must not modify the event.

### HebbianPolicy

```text
EdgeUpdatePlan
  -> HebbianPolicy
  -> PolicyDecision
```

Determines whether an `EdgeUpdatePlan` (or individual edge update within it) should proceed to `HebbianExecutor`. It must not modify the plan and must not perform reinforcement.

### ForgetPolicy

```text
MemoryReference
  -> ForgetPolicy
  -> PolicyDecision
```

Recommends whether a memory should be archived, deleted, or kept. `ForgetPolicy` never deletes. Actual archival and deletion remain the responsibility of Store Integration via `StoreMutation::ArchiveMemory` / `DeleteMemory`.

The mapping from `PolicyDecision` to `StoreMutation` is performed downstream, not by the policy.

### MergePolicy

```text
MergeGroup
  -> MergePolicy
  -> PolicyDecision
```

Recommends whether a candidate merge group should be accepted, rejected, or delayed. Merging itself remains the responsibility of Consolidation Execution and Store Integration. `MergePolicy` must not construct merged memories.

## Reporting

```text
PolicyDecisionReport
  policy: PolicyKind
  input_id: opaque identifier
  decision: PolicyDecision
```

`PolicyDecisionReport` is immutable after emission. Sinks may observe reports for telemetry and debugging. Reports must not embed frozen execution reports (`ExecutionReport`, `ReflectionReport`, `HebbianExecutionReport`, `StoreExecutionReport`) or mutation plans.

## P4.5 Milestones

```text
P4.5.1 Policy Skeleton
  -> P4.5.2 Policy Dispatcher
  -> P4.5.3 Policy Sink
  -> P4.5 Freeze
```

- P4.5.1 introduces `AdaptivePolicy`, `PolicyDecision`, per-policy traits, and `NoOp` implementations. No dispatch, no sinks, no algorithms.
- P4.5.2 introduces `AdaptivePolicyEngine` and per-policy dispatch. Deterministic and side-effect free.
- P4.5.3 introduces `PolicyDecisionReport` and `PolicySink`. Observer-only.
- P4.5 Freeze locks the Policy Layer contract before any concrete algorithm work.

Persistent writes remain forbidden across every P4.5 milestone.

## Invariants

1. Policies never mutate memory.
2. Policies never write to Store.
3. Policies never call `ReflectionExecutor`, `HebbianExecutor`, `ConsolidationExecutor`, `PersistentStoreExecutor`, or `StoreAdapter`.
4. Policies never call `RecallEngine`.
5. Policies never call LLMs or non-deterministic sources during P4.5 milestones.
6. Policies never mutate their inputs.
7. Policies always return exactly one `PolicyDecision` per input.
8. Policy Layer does not modify Recall contracts.
9. Policy Layer does not modify Memory Evolution contracts.
10. Policy Layer does not modify frozen Adaptive Memory execution contracts.
11. Policy Layer does not modify Store Integration contracts.
12. `AdaptivePolicyEngine` is deterministic for identical inputs.
13. `PolicyDecisionReport` is immutable after emission.
14. `PolicySink` observes reports only and must not perform persistent writes.
15. `PolicySink` execution must not affect `AdaptivePolicyEngine` output.
16. Execution modules must not depend on the Policy Layer.
17. Every new policy trait ships with a `NoOp` implementation before public use.
18. `PolicyDecision::Delay` carries no side effects and no scheduling logic in P4.5.
19. Concrete policy algorithms are out of scope for RFC-010 and must be introduced through follow-up RFCs.

## Acceptance Criteria

- RFC-010 defines the Policy Layer boundary before code implementation.
- P4.5.1 introduces policy traits and `NoOp` implementations without IO.
- P4.5.2 introduces `AdaptivePolicyEngine` dispatch without IO.
- P4.5.3 introduces `PolicySink` observation without IO.
- P4.5 Freeze records the Policy Layer contract with an annotated release note.
- `reference` remains `Recall@10 = 1.000`.
- `multihop` remains `Recall@10 = 0.600`.

## Non-Goals

- Choosing forgetting curves.
- Choosing reinforcement thresholds.
- Choosing merge similarity thresholds.
- Introducing scheduling or timers.
- Introducing LLM-based decision making.
- Introducing learning or feedback loops.
- Introducing cross-policy arbitration.

These belong to follow-up RFCs after the Policy contract is frozen.
