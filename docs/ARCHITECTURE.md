# Architecture

| Phase | Goal | Output |
| --- | --- | --- |
| Phase 1 | Build a reliable capture pipeline. | Capture Engine |
| Phase 2 | Build a stable, explainable recall engine. | Recall API Freeze |
| Phase 3 | Freeze memory evolution contracts without changing the recall contract. | Memory Evolution Contract Freeze |
| Phase 4 | Implement adaptive behavior behind frozen contracts. | Adaptive Memory Foundation |

## Phase 4 Development Rules

1. Behavior modules must be implemented on top of the frozen Recall Platform, Memory Evolution Contract, and Adaptive Memory Foundation.
2. New behavior should follow the established execution model: `Plan -> Execute -> Report -> Sink`.
3. New extension points should reuse the existing plugin pattern: `Trait -> NoOp -> Concrete Implementation`.
4. Changes to frozen contracts require a dedicated ADR and a new architecture milestone.
5. Every new public trait must ship with a NoOp implementation before entering the public API.

## Reflection

```text
ReflectionEvent
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink
```

Reflection remains deterministic and side-effect free until later execution phases.

## Hebbian

```text
EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
  -> HebbianSink
```

Hebbian Execution remains deterministic and side-effect free until Store integration introduces explicit persistence adapters.

## Store Integration

```text
ExecutionReport / ReflectionReport / HebbianExecutionReport
  -> StoreMutationDispatcher
  -> StoreMutationPlan
  -> StoreAdapter / PersistentStoreExecutor
  -> StoreExecutionReport
  -> StoreSink
```

Store Integration is the first Phase 4 area allowed to perform durable writes. All persistence flows through `StoreAdapter` or `PersistentStoreExecutor`; behavior modules must not call Store directly. Frozen by `v0.4.39-store-integration-freeze`.

## Adaptive Policies

```text
PolicyRequest
  -> AdaptivePolicyEngine
  -> PolicyReport
  -> PolicySink
```

Adaptive Policies sit above the frozen Adaptive Memory execution chains and decide whether existing capabilities should run. Policies emit only `PolicyDecision::{Execute, Skip, Delay}`; they never mutate memory and never call executors or Store. Frozen by `v0.4.49-adaptive-policies-freeze`.
