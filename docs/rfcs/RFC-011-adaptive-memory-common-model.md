# RFC-011: Adaptive Memory Common Model

Status: Accepted

Phase: Phase 5 Algorithm Implementation

Implementation Tags:

```text
v0.5.1-memory-importance          (planned)
v0.5.2-memory-event-and-context   (planned)
v0.5.3-benchmark-harness          (planned)
v0.5.9-adaptive-common-freeze     (planned)
```

Subtitle: Shared Data Model for All Adaptive Memory Algorithms

## Summary

RFC-011 defines the data model that every Phase 5 adaptive-memory algorithm consumes: memory importance, memory events, and algorithm context. It does **not** define any algorithm. Reflection, Merge, Forgetting, and Hebbian each get their own RFC and each must consume the model defined here without extending it locally.

## Motivation

At the close of Phase 4, all architectural contracts are frozen. Phase 5 begins concrete algorithm work. If each algorithm is allowed to invent its own notion of "how important is this memory", "what happened recently", or "what state is the system in", the project will end up with:

- multiple incompatible `Importance` values,
- forked event streams that cannot be replayed together,
- trait signatures that grow parameters release after release.

RFC-011 eliminates that failure mode by freezing the shared data model **before** any algorithm RFC is drafted. RFC-012 through RFC-015 will reference this document and MUST NOT redefine any type introduced here.

## Scope

In scope:

- `MemoryImportance` value type with an `overall` score and structured `ImportanceSignals`.
- `ImportanceEstimator` trait.
- `MemoryEvent` and `MemoryEventKind` value types.
- `MemoryEventStream` trait for producing events.
- `AlgorithmContext` value type: the single argument every Phase 5 algorithm accepts alongside its own input.
- Shared metric identifiers used by the benchmark harness.
- Extension rules for adding new signals, event kinds, and metrics without breaking stable APIs.

Out of scope:

- Reflection, Merge, Forgetting, or Hebbian algorithm design (deferred to RFC-012..015).
- Concrete `ImportanceEstimator` implementations beyond `NoOp` / `Uniform` placeholders.
- Concrete `MemoryEventStream` implementations beyond `NoOp` / `InMemory`.
- Weight tuning for importance signals.
- Any change to the Recall contract, Memory Evolution contract, Adaptive Memory execution contracts, Store Integration contract, or Adaptive Policies contract.
- Any change to `docs/API_SURFACE.md` classifications; new items introduced by RFC-011 are Stable at freeze time.

## Guiding Principles

1. **One Importance.** Reflection, Merge, Forgetting, and Hebbian all consume the same `MemoryImportance`. No algorithm computes a private importance value.
2. **One Event Stream.** All observable adaptive-memory activity is emitted as `MemoryEvent`. Algorithms consume the same stream. The stream is replayable.
3. **One Context.** Every Phase 5 algorithm takes `&AlgorithmContext` as its second argument. New shared inputs are added to the context, not to trait signatures.
4. **Extensible by default.** Every enum introduced by RFC-011 is `#[non_exhaustive]`. New signals, event kinds, and metrics can be added without a major version bump.
5. **Explainability preserved.** `MemoryImportance` exposes both the aggregate `overall` and the structured `signals`. Debug tooling reads signals; algorithms read `overall`.
6. **No IO in the model.** Types are plain data. Estimators and streams have traits, but the model itself does not touch Store, Recall, LLMs, or clocks.

## Part A — Memory Importance

### Value Type

```text
MemoryImportance
  overall: f32                (0.0 ..= 1.0, algorithm-facing)
  signals: ImportanceSignals  (introspection-only)
```

`overall` is the single value every algorithm should consume. `signals` exists for debug tooling, benchmarks, and explainability. Algorithms MUST NOT branch on individual signals.

```text
ImportanceSignals
  access_frequency: f32       (normalized 0.0 ..= 1.0)
  recency: f32                (normalized 0.0 ..= 1.0)
  reflection_score: f32       (normalized 0.0 ..= 1.0)
  user_priority: f32          (normalized 0.0 ..= 1.0)
  semantic_uniqueness: f32    (normalized 0.0 ..= 1.0)
```

All fields are normalized to `[0.0, 1.0]` at the model boundary. Estimators are responsible for normalization; consumers must not renormalize.

### Signal Enumeration

For introspection tooling and future signal additions:

```text
#[non_exhaustive]
ImportanceSignal
  AccessFrequency
  Recency
  ReflectionScore
  UserPriority
  SemanticUniqueness
```

Adding a new variant is not a breaking change.

### Estimator Trait

```text
ImportanceEstimator
  fn estimate(&self, memory: &Memory, ctx: &AlgorithmContext) -> MemoryImportance
```

Signature rules:

- `memory` is the evaluation **target**. It is passed as an explicit method parameter, not embedded into the context.
- `ctx` is the evaluation **environment**. Shared inputs live here.
- The trait signature is closed at v0.5.1. Future shared inputs are added to `AlgorithmContext` (subject to the Part C rules), never to this trait.

Included implementations at freeze time:

- `NoOpImportanceEstimator` — returns `overall = 0.0`, all signals zero. Default for tests and benchmarks that do not exercise importance.
- `UniformImportanceEstimator` — returns `overall = 0.5`, all signals `0.5`. Default when a caller needs a non-zero baseline without wiring signals.

Both are placeholders. Concrete weighted estimators arrive with RFC-012 and later, behind this trait.

### Rules

1. `MemoryImportance` is immutable after construction.
2. Estimators are pure with respect to the model. They may read from Store or event streams only through explicit parameters passed via `AlgorithmContext`.
3. Signal weights are internal to estimator implementations. Weights are never stable API.
4. Adding a new field to `ImportanceSignals` requires the field to be `Default`-able and gated behind `#[non_exhaustive]` on the struct. Otherwise it is a breaking change under `docs/COMPATIBILITY.md`.

## Part B — Memory Event

### Value Type

```text
MemoryEvent
  id: MemoryEventId          (uuid)
  timestamp: DateTime<Utc>
  session_id: Option<SessionId>
  kind: MemoryEventKind
  payload: MemoryEventPayload
```

Events are append-only. They carry no algorithm output. Algorithms produce their own reports (already frozen in Phase 4).

### Event Kinds

```text
#[non_exhaustive]
MemoryEventKind
  Recall
  Write
  Reflection
  Failure
  UserCorrection
  GoalCompleted
  MergeCompleted
  Forgotten
```

`MergeCompleted` and `Forgotten` are included at freeze time not because RFC-011 defines merging or forgetting, but because the event stream must be replayable across the future algorithms that produce them.

Adding a new kind is not a breaking change because the enum is `#[non_exhaustive]`.

### Payload

```text
#[non_exhaustive]
MemoryEventPayload
  Empty
  MemoryRef { memory_id: MemoryId }
  MemoryRefs { memory_ids: Vec<MemoryId> }
  Text { message: String }
```

Payloads stay minimal at freeze time. Algorithm RFCs may introduce new payload variants; `#[non_exhaustive]` guarantees additivity.

### Stream Trait

```text
MemoryEventStream
  fn record(&self, event: MemoryEvent)
  fn recent(&self, limit: usize) -> Vec<MemoryEvent>
```

Included implementations:

- `NoOpMemoryEventStream` — records nothing, returns empty.
- `InMemoryMemoryEventStream` — bounded ring buffer, deterministic for tests and benchmarks.

### Rules

1. `MemoryEvent` is immutable after construction.
2. `MemoryEventStream` is **append-only**. Recorded events cannot be modified, deleted, or reordered by any consumer.
3. **Past events are immutable.** Once an event has been observed by `recent(...)`, its fields are fixed for the lifetime of the stream.
4. **Replay is deterministic.** Given the same sequence of `record(...)` calls, `recent(N)` MUST return events in the same order across every call. Concrete streams may drop the oldest events when the buffer overflows, but MUST NOT reorder events relative to insertion order.
5. Streams must be side-effect free with respect to Store, Recall, and any executor.
6. Filtering, transformation, and reordering are the responsibility of consumers over the returned `Vec<MemoryEvent>`; they MUST NOT be performed by the stream itself.

## Part C — Algorithm Context

Every Phase 5 algorithm accepts `&AlgorithmContext` alongside its algorithm-specific input. New shared inputs go here.

```text
AlgorithmContext<'a>
  now: DateTime<Utc>
  session_id: Option<SessionId>
  importance: &'a dyn ImportanceEstimator
  events: &'a dyn MemoryEventStream
```

The context is a borrow. It carries no owned state. Algorithm implementations must not store the context beyond the current call.

### Rules

1. Algorithms MUST take `&AlgorithmContext` rather than adding new parameters to their trait methods.
2. **`AlgorithmContext` represents execution environment only.** The primary evaluation target MUST be passed as an explicit method parameter (`memory`, `group`, `event`, etc.) rather than embedded into the context. Fields such as `target_memory`, `target_edge`, or `target_event` MUST NOT appear on `AlgorithmContext`.
3. **`AlgorithmContext` MUST NOT acquire new service dependencies after v0.5.1.** No new trait objects, engines, stores, recall systems, LLM clients, policy engines, or graph handles may be added. The trait-object surface is closed at freeze time (`importance`, `events`).
4. `AlgorithmContext` MAY gain additional **plain-data** fields in future minor versions when they are optional or backward-compatible (`Option<...>`, `Default`-able, or gated behind a new constructor while preserving the old one). This is subject to the `#[non_exhaustive]` marker on the struct.
5. Removing or renaming any existing field is a breaking change under `docs/COMPATIBILITY.md` and requires an ADR.
6. Fields introduced later that are optional must be represented as `Option<...>` or provided via a builder that preserves existing constructors.
7. `now` is provided by the caller. Algorithms MUST NOT read the system clock directly.
8. `session_id` is optional to allow global (non-session) algorithm invocations.
9. The context is a borrow. Algorithm implementations MUST NOT store the context beyond the current call.

### Uniform Call Shape

Every Phase 5 algorithm MUST expose its primary method in the form `fn method(target, ctx)` where `ctx: &AlgorithmContext` and `target` is the algorithm-specific input. Illustrative expected shapes (defined by later RFCs):

```text
importance.estimate(memory, ctx)
reflection.process(memory, ctx)
merge.score(group, ctx)
forget.should_forget(memory, ctx)
hebbian.reinforce(edge, ctx)
```

This is a convention, not a trait: each algorithm's exact trait method is defined by its own RFC (RFC-012..015). RFC-011 fixes only the argument shape.

## Part D — Shared Metrics

Benchmark identifiers used by `crates/eval` and future algorithm benchmarks.

```text
#[non_exhaustive]
AlgorithmMetric
  Recall
  Mrr
  Ndcg
  LatencyP50
  LatencyP95
  MemoryGrowth
  CompressionRatio
  ImportanceStability
  ReflectionLatency
  ForgettingQuality
```

Metric IDs are stable strings. Metric values are produced by benchmarks, not by algorithm implementations. Algorithms MUST NOT read metric outputs; benchmarks MUST NOT feed back into algorithm decisions.

Adding a new variant is not a breaking change.

## Appendix — Extension Rules

All types introduced by RFC-011 follow these rules for Phase 5 and beyond:

1. Every public enum is `#[non_exhaustive]`. Adding a variant is additive.
2. Every public struct listed in `docs/API_SURFACE.md` accepts new fields only if the struct is marked `#[non_exhaustive]` and the change ships with a new constructor while the old constructor is preserved.
3. Trait method signatures never grow. Shared inputs go into `AlgorithmContext`.
4. `NoOp*` and at least one deterministic placeholder implementation must ship with each new trait at freeze time.
5. Serialized (`serde`) shapes are stable. Removing a field or renaming a variant is a breaking change under `docs/COMPATIBILITY.md`.
6. RFC-012 through RFC-015 must reference RFC-011 for shared types. They must not fork Importance, Event, or Context.

## Milestones

```text
v0.5.1  Memory Importance Skeleton
  -> v0.5.2  Memory Event Skeleton (includes AlgorithmContext)
  -> v0.5.3  Benchmark Harness Scaffold (includes AlgorithmMetric)
  -> v0.5.9  Adaptive Memory Common Model Freeze (RFC-011 Accepted)
```

Each milestone follows the frozen pattern: `Trait -> NoOp -> (optional Deterministic placeholder) -> Freeze`.

Milestone constraints:

- v0.5.1 ships `MemoryImportance`, `ImportanceSignals`, `ImportanceSignal`, `ImportanceEstimator`, `NoOpImportanceEstimator`, `UniformImportanceEstimator`.
- v0.5.2 ships `MemoryEvent`, `MemoryEventId`, `MemoryEventKind`, `MemoryEventPayload`, `MemoryEventStream`, `NoOpMemoryEventStream`, `InMemoryMemoryEventStream`, plus `AlgorithmContext`.
- v0.5.3 scaffolds benchmark directories (`datasets/{regression,synthetic,dmr,longmemeval}`, `benches/{recall,memory,algorithms}`, `reports/`) plus `AlgorithmMetric`. No new datasets are populated at this milestone; scaffolding only.
- v0.5.9 freezes the model: RFC-011 → Accepted, `docs/API_SURFACE.md` updated with the new Stable items, release note added.

Benchmark baselines must be preserved across every milestone:

- `reference` `Recall@10 = 1.000`
- `multihop` `Recall@10 = 0.600`

## Non-Goals

- Reflection algorithm design (RFC-012).
- Merge algorithm design (RFC-013).
- Forgetting algorithm design (RFC-014).
- Hebbian algorithm design (RFC-015).
- Signal weight tuning.
- Learned importance.
- LLM-driven importance.
- Persistent event storage (streams stay in-memory until an algorithm RFC needs otherwise).
- Cross-session event correlation.

These are deferred to follow-up RFCs, each of which will reference RFC-011.

## Acceptance Criteria

- RFC-011 defines the Adaptive Memory Common Model before any algorithm RFC is drafted.
- v0.5.1 introduces the Importance types with `NoOp` and `Uniform` placeholders.
- v0.5.2 introduces the Event types, `AlgorithmContext`, and `NoOp` / `InMemory` stream implementations.
- v0.5.3 scaffolds the benchmark harness and introduces `AlgorithmMetric` without changing baselines.
- v0.5.9 freezes RFC-011 as Accepted.
- `reference` remains `Recall@10 = 1.000`.
- `multihop` remains `Recall@10 = 0.600`.
- No stable Phase 1–4 API is modified by RFC-011 milestones.
