# Architecture

Status: **Stable** since `v0.5.0-architecture-freeze`.

| Phase | Goal | Output |
| --- | --- | --- |
| Phase 1 | Build a reliable capture pipeline. | Capture Engine |
| Phase 2 | Build a stable, explainable recall engine. | Recall API Freeze |
| Phase 3 | Freeze memory evolution contracts without changing the recall contract. | Memory Evolution Contract Freeze |
| Phase 4 | Implement adaptive behavior behind frozen contracts. | Adaptive Memory (7 sub-freezes) |
| Phase 5 | Turn frozen contracts into concrete adaptive behavior. | Algorithm Implementation |

## Final Architecture Rules

Every capability introduced after `v0.5.0-architecture-freeze` must follow all three shapes below.

### Capability Shape

```text
Trait
  -> NoOp
  -> Dispatcher
  -> Report
  -> Sink
```

Every new public trait ships with a `NoOp` implementation. Dispatchers are pure and deterministic. Reports are immutable after emission. Sinks are observer-only.

### Layer Direction

```text
Policy
  -> Execution
  -> Storage
```

Policies decide whether execution runs. Execution modules produce plans and reports. Storage is only reached through `StoreAdapter` or `PersistentStoreExecutor`.

### Subsystem Stack

```text
Recall Platform
  -> Working Memory
  -> Adaptive Memory
  -> Store
```

Recall Platform is stable and query-agnostic. Working Memory is session-scoped and transient. Adaptive Memory drives evolution through frozen behavior chains. Store is the only durable persistence layer.

## Phase 4 Development Rules

1. Behavior modules must be implemented on top of the frozen Recall Platform, Memory Evolution Contract, and Adaptive Memory Foundation.
2. New behavior should follow the established execution model: `Plan -> Execute -> Report -> Sink`.
3. New extension points should reuse the existing plugin pattern: `Trait -> NoOp -> Concrete Implementation`.
4. Changes to frozen contracts require a dedicated ADR and a new architecture milestone.
5. Every new public trait must ship with a NoOp implementation before entering the public API.

## Phase 5 Development Rules

1. Phase 5 must not change any Stable API listed in `docs/API_SURFACE.md`.
2. Algorithm implementations plug in behind existing traits and their `NoOp` slots.
3. Breaking changes to Stable APIs require an ADR and a `0.6.0` release (see `docs/COMPATIBILITY.md`).
4. Frozen benchmark baselines (`reference` = `Recall@10 = 1.000`, `multihop` = `Recall@10 = 1.000` after ADR-006) must be preserved or explicitly renegotiated through ADR.
5. Concrete algorithms must remain replaceable behind their traits; no algorithm becomes a hard dependency of the framework.

## Final Adaptive Memory Architecture (Frozen `v0.5.9`)

The shared foundation every Phase 5 algorithm consumes. This structure is frozen; concrete algorithms attach below `AlgorithmContext`, not above it.

```text
                    ┌────────────────────┐
                    │       Memory       │
                    └──────────┬─────────┘
                               │
                               ▼
                    ┌────────────────────┐
                    │ ImportanceEstimator│──► MemoryImportance
                    └────────────────────┘
                               │
                               │
                    ┌────────────────────┐
                    │ MemoryEventStream  │──► MemoryEvent (append-only)
                    └──────────┬─────────┘
                               │
                               ▼
                    ┌────────────────────┐
                    │  AlgorithmContext  │  (trait-object surface closed at v0.5.2)
                    │  now, session_id,  │
                    │  importance, events│
                    └──────────┬─────────┘
                               │
              ┌────────────────┼────────────────┬──────────────┐
              ▼                ▼                ▼              ▼
       ┌───────────┐    ┌───────────┐    ┌───────────┐   ┌───────────┐
       │Reflection │    │   Merge   │    │  Forget   │   │  Hebbian  │
       └─────┬─────┘    └─────┬─────┘    └─────┬─────┘   └─────┬─────┘
             └──────────┬─────┴──────────┬─────┴───────────────┘
                        ▼                ▼
              ┌──────────────────────────────┐
              │      Store Integration       │  (canonical StoreMutation)
              └──────────────┬───────────────┘
                             ▼
                    ┌────────────────────┐
                    │       Store        │
                    └────────────────────┘

Benchmark plane (parallel, observer-only):
  Each algorithm → BenchmarkReport { benchmark, metrics: BTreeMap<AlgorithmMetric, f64> }
```

**Rule.** Every algorithm consumes `AlgorithmContext`. No algorithm bypasses it. No new engine, graph, recall handle, or LLM client may be added to `AlgorithmContext`.

**Freeze boundary.**

- Everything **above** `AlgorithmContext` (Importance, Event, Event Stream, Context itself, Metric, Report) is **frozen** at `v0.5.9-adaptive-common-freeze`. Changes require an ADR and a `0.6.0` release.
- Everything **below** `AlgorithmContext` (Reflection, Merge, Forget, Hebbian, and their internal data types under `adaptive/<algorithm>/`) is **open**. Concrete algorithm work begins with RFC-012.

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
