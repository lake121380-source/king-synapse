# RFC-011: Adaptive Memory Common Model

Status: Implemented

Phase: Phase 5 Algorithm Implementation

Implementation Tags:

```text
v0.5.1-memory-importance          (implemented)
v0.5.2-memory-event-and-context   (implemented)
v0.5.3-benchmark-harness          (implemented)
v0.5.9-adaptive-common-freeze     (implemented)
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

**`overall` is NOT the arithmetic mean of `signals`.** It is the estimator's final judgement. Concrete estimators MAY combine signals non-linearly, apply weights, clip, or normalize. `overall < max(signal)` is a legal outcome. Consumers MUST NOT assume any algebraic relationship between `overall` and individual `signals` fields.

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

`ImportanceSignal` is for explainability, diagnostics, and metric mapping only. It MUST NOT appear as an input parameter to estimators or as a strategy selector (`estimate(signal: ImportanceSignal)` is forbidden).

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
MemoryEventId(Uuid)

MemoryEvent
  id: MemoryEventId
  timestamp: DateTime<Utc>
  session_id: Option<SessionId>
  kind: MemoryEventKind
  memory_ids: Vec<MemoryId>
  payload: MemoryEventPayload
```

Events are append-only. They carry no algorithm output. Algorithms produce their own reports (already frozen in Phase 4).

`memory_ids` is a `Vec<MemoryId>`, never `Option<MemoryId>`. Single-target events use a one-element vector; multi-target events (e.g. `MergeCompleted`) use the full list. Events unrelated to a specific memory use an empty vector. This uniform shape lets every downstream algorithm iterate `memory_ids` without special-casing kinds.

`MemoryEventId` is a newtype around `Uuid` so future implementations may swap the backing generator (ULID, Snowflake, database ID) without touching the event surface.

### Event Kinds

```text
#[non_exhaustive]
MemoryEventKind
  Recalled
  Written
  Updated
  Invalidated
  Reflected
  Reinforced
  MergeCompleted
  Forgotten
```

All kind names are **past tense** — every event describes something that has already happened. `Written`, `Updated`, and `Invalidated` mirror the frozen `Store::write` / `Store::invalidate` API surface; renaming to `Created` / `TombStoned` etc. is intentionally rejected.

`MergeCompleted` and `Forgotten` are included at freeze time not because RFC-011 defines merging or forgetting, but because the event stream must be replayable across the future algorithms that produce them.

Adding a new kind is not a breaking change because the enum is `#[non_exhaustive]`.

### Payload

```text
#[non_exhaustive]
MemoryEventPayload
  Empty
  Recalled { query: String, hit_count: usize }
  Reflected { reflection_event_id: ReflectionEventId }
  Reinforced { edge_key: String, delta: f32 }
  MergeCompleted { into: MemoryId }
  Forgotten { reason: String }
```

Payloads stay minimal at freeze time.

- The `Empty` variant name is chosen (not `None`) to avoid visual collision with `Option::None`.
- Not every `MemoryEventKind` has a matching payload variant. `Written`, `Updated`, `Invalidated` carry no extra data beyond `memory_ids` and use `Empty`.
- `MergeCompleted.into` is the surviving memory; the merged source ids live in `event.memory_ids` per the Value Type rule.
- Algorithm RFCs may introduce new payload variants; `#[non_exhaustive]` guarantees additivity.

### Stream Trait

```text
MemoryEventStream
  fn record(&self, event: MemoryEvent)
  fn recent(&self, limit: usize) -> Vec<MemoryEvent>
```

- `record` takes `&self`; concrete implementations use interior mutability. This lets `AlgorithmContext` hold `&dyn MemoryEventStream` and share it across algorithm calls.
- `recent(0)` MUST return an empty `Vec`.
- `recent(n)` where `n > len` MUST return every retained event.
- Neither method returns `Result`; both are infallible.
- `record` is NOT idempotent — recording the same event twice appends two entries. Deduplication is the caller's responsibility.

Included implementations:

- `NoOpMemoryEventStream` — records nothing, returns empty.
- `InMemoryMemoryEventStream` — **reference implementation**: bounded ring buffer, deterministic, intended for tests and benchmarks. It is explicitly NOT a default implementation nor a production event store. Persistent event stores (SQLite / Kafka / etc.) are out of scope for RFC-011 and, when introduced, MUST implement the same `MemoryEventStream` contract without changing it.

### Rules

1. `MemoryEvent` is immutable after construction.
2. `MemoryEventStream` is **append-only**. Recorded events cannot be modified, deleted, or reordered by any consumer.
3. **Past events are immutable.** Once an event has been observed by `recent(...)`, its fields are fixed for the lifetime of the stream.
4. **Replay is deterministic.** Given the same sequence of `record(...)` calls, `recent(N)` MUST return events in the same order across every call. Concrete streams may drop the oldest events when the buffer overflows, but MUST NOT reorder events relative to insertion order.
5. **Event ordering is defined by `record` order, not by `event.timestamp`.** Two events with identical timestamps MUST NOT be reordered. Streams MUST NOT sort, reorder, or de-duplicate by timestamp. `timestamp` is metadata for observers; insertion order is the sole ordering invariant.
6. Streams must be side-effect free with respect to Store, Recall, and any executor.
7. Filtering, transformation, and reordering are the responsibility of consumers over the returned `Vec<MemoryEvent>`; they MUST NOT be performed by the stream itself.
8. **`recent(n)` is not a query API.** It is a replay convenience over an append-only log. `MemoryEventStream` supports only append (`record`) and replay-oriented retrieval (`recent`). Query-shaped APIs (`query`, `filter`, `search`, `between`, tag lookups, aggregation) are explicitly out of scope and MUST NOT be added to the trait. Consumers that need such capabilities own their own indexes over `recent(n)` output.

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
3. **`AlgorithmContext` trait-object surface is closed at v0.5.2.** The two allowed trait-object fields are `importance: &'a dyn ImportanceEstimator` (added in v0.5.2) and `events: &'a dyn MemoryEventStream` (added in v0.5.2). No new trait-object fields may ever be added: no `&dyn Store`, no `&dyn RecallEngine`, no `&dyn PolicyEngine`, no `&dyn Graph`, no `&dyn LlmClient`, no other service dependency.
4. `AlgorithmContext` MAY gain additional **plain-data** fields in future minor versions when they are optional or backward-compatible (`Option<...>`, `Default`-able, or gated behind a new constructor while preserving the old one). This is subject to the `#[non_exhaustive]` marker on the struct.
5. Removing or renaming any existing field is a breaking change under `docs/COMPATIBILITY.md` and requires an ADR.
6. Fields introduced later that are optional must be represented as `Option<...>` or provided via a builder that preserves existing constructors.
7. `now` is provided by the caller. Algorithms MUST NOT read the system clock directly.
8. `session_id` is optional to allow global (non-session) algorithm invocations.
9. The context is a borrow. Algorithm implementations MUST NOT store the context beyond the current call.
10. **No `Send + Sync` bound is imposed on `ImportanceEstimator` or `MemoryEventStream`.** The reference algorithm layer is single-threaded and deterministic. Concurrent executors that need thread-safety MUST add the bound at their own layer, not on the shared traits.

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

## Part D — Shared Metrics and Benchmark Report

Benchmark identifiers and the unified benchmark output shape used by `crates/eval` and every future algorithm benchmark.

### AlgorithmMetric

```text
#[non_exhaustive]
AlgorithmMetric
  RecallAt10
  PrecisionAt10
  MemoryGrowth
  CompressionRatio
  ReflectionYield
  MergePrecision
  ForgetPrecision
  HebbianConsistency
  EventReplayLatency
  AlgorithmLatency
```

- Metric variants are stable IDs. Their **exact numerical definition** is fixed by the benchmark implementation, not by RFC-011. Algorithms MUST NOT read metric outputs; benchmarks MUST NOT feed back into algorithm decisions.
- The enum is `#[non_exhaustive]`. Adding a new variant is not a breaking change.
- `RecallAt10` is a naming convention only. Its presence in the enum does not imply the v0.5.3 skeleton produces any value.
- `EventReplayLatency` (cost of `MemoryEventStream::recent`) and `AlgorithmLatency` (cost of one `algorithm.run(target, ctx)` call) are intentionally distinct — they MUST NOT be collapsed into a single "latency" number.

### BenchmarkReport

```text
#[non_exhaustive]
BenchmarkReport
  benchmark: String                              // lowercase-kebab-case, e.g. "reference-recall"
  metrics: BTreeMap<AlgorithmMetric, f64>        // deterministic order
```

- All metric values are `f64`. Typed metric values (`Ratio`, `Duration`, etc.) are out of scope for v0.5.3.
- `BTreeMap` (not `HashMap`) is mandatory: the resulting serialization order is deterministic, which is required for CI diffs.
- The `benchmark` field is a free-form `String`. By convention it MUST be `lowercase-kebab-case` (e.g. `reference-recall`, `multihop-recall`, `reflection-yield`). This convention is documented, not enforced by the type.
- The struct is `#[non_exhaustive]`.

### Rules

1. **Deterministic value object (D8).** `BenchmarkReport` is a deterministic value object. Given the same dataset, the same algorithm implementation, and the same configuration, benchmarks MUST produce identical `BenchmarkReport` values. Runtime-specific metadata (`timestamp`, `hostname`, `cpu`, `random_seed`, `git_dirty`, wall-clock start time, etc.) is out of scope for `BenchmarkReport` and belongs to a future exporter layer.
2. **Sparse by design (D9).** A `BenchmarkReport` includes only the metrics that are meaningful for that benchmark. Missing metrics MUST NOT be interpreted as `0.0`. A recall benchmark may report only `RecallAt10`; a reflection benchmark may report only `ReflectionYield` and `AlgorithmLatency`.
3. **Finite values.** Benchmark producers SHOULD emit finite `f64` values. `NaN` and `Inf` are neither validated nor forbidden by the harness; consumers of `BenchmarkReport` decide how to handle them.
4. **Metrics are IDs, not fixed fields.** `AlgorithmMetric` variants are never inlined as `BenchmarkReport` struct fields. They flow only through `metrics`.

### Algorithm → Benchmark → Metric Discipline (D7)

Every algorithm RFC (RFC-012..015, and any future algorithm RFC) MUST:

1. Define at least one benchmark under `crates/eval/benches/algorithms/`.
2. Map its benchmark to at least one `AlgorithmMetric` variant. If no existing variant fits, the RFC MUST propose a new variant as an additive change to `AlgorithmMetric` (non-breaking under `#[non_exhaustive]`).
3. Emit its result as a `BenchmarkReport` value obeying the D8 determinism invariant.

This binds every algorithm to a measurable output shape and prevents "algorithm shipped without any way to compare it against the previous version".

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

- v0.5.1 ships `MemoryImportance`, `ImportanceSignals`, `ImportanceSignal`, `ImportanceEstimator`, `NoOpImportanceEstimator`, `UniformImportanceEstimator`, and a minimal `AlgorithmContext { now, session_id }`. The context intentionally excludes `importance` and `events` trait fields at this milestone — they are added additively in v0.5.2 under `#[non_exhaustive]`. `ImportanceEstimator::estimate(memory, ctx)` signature is frozen from v0.5.1 onward.
- v0.5.2 ships `MemoryEventId`, `MemoryEvent`, `MemoryEventKind`, `MemoryEventPayload`, `MemoryEventStream`, `NoOpMemoryEventStream`, `InMemoryMemoryEventStream`. `AlgorithmContext` gains a lifetime `'a` and two trait-object fields `importance: &'a dyn ImportanceEstimator` and `events: &'a dyn MemoryEventStream`. The v0.5.1 constructor `AlgorithmContext::new(now, session_id)` is replaced by `AlgorithmContext::new(now, session_id, importance, events)`; this is the only allowed shape and there is no builder variant. After v0.5.2 the `AlgorithmContext` trait-object surface is permanently closed per Part C rule 3.
- v0.5.3 freezes the benchmark harness contract: `AlgorithmMetric` (10 IDs, `#[non_exhaustive]`), `BenchmarkReport` (`#[non_exhaustive]`, `benchmark: String` + `metrics: BTreeMap<AlgorithmMetric, f64>`), and the directory layout under `crates/eval/{datasets,benches,reports}/`. This milestone ships **contract only** — no dataset loader, no benchmark runner, no CLI, no exporter. The Algorithm → Benchmark → Metric discipline (Part D "Discipline" section) becomes binding on every subsequent algorithm RFC.
- v0.5.9 freezes the model: RFC-011 → Implemented, `docs/API_SURFACE.md` updated with the new Stable items, release note added.

Benchmark baselines must be preserved across every milestone:

- `reference` `Recall@10 = 1.000`
- `multihop` `Recall@10 = 0.600`

## Post-Freeze Rules

Effective at `v0.5.9-adaptive-common-freeze`. These rules govern every subsequent RFC that consumes the Adaptive Common Model.

### PF1. No new top-level shared types after v0.5.9

No new top-level type (struct / enum / trait) may be added under `crates/core/src/adaptive/` after v0.5.9. Algorithm-specific data types belong to their own subtrees:

```
adaptive/reflection/
adaptive/merge/
adaptive/forget/
adaptive/hebbian/
```

Types like `ReflectionScore`, `MergeCandidate`, `ForgetReason`, or `HebbianEdge` MUST live inside their own algorithm module, not in the shared `adaptive/` root.

Additive extension of the frozen `#[non_exhaustive]` enums (`ImportanceSignal`, `MemoryEventKind`, `MemoryEventPayload`, `AlgorithmMetric`) via new variants remains allowed. What is frozen is the set of top-level types, not the set of variants.

### PF2. Uniform algorithm call shape (MUST)

Every Phase 5 algorithm's primary method MUST have the shape:

```rust
fn method(&self, target: &T, ctx: &AlgorithmContext<'_>) -> Output
```

Deviations such as `(ctx)` alone, `(graph, ctx)`, `(policy, ctx)`, or `(memory, edge, ctx)` are forbidden. Multi-input algorithms MUST wrap their inputs into a single target aggregate (`MergeGroup`, `EdgeInput`, ...) so the first argument is always exactly one value. Any deviation requires an ADR, not an RFC.

### PF3. Downstream RFCs consume, never extend

RFC-012 through RFC-015 (and any future algorithm RFC) MUST reference RFC-011 for `Importance`, `Event`, `Context`, and `Metric`. They MUST NOT redefine these types, fork them locally, or shadow them under a different name.

### PF4. Algorithm RFCs MUST NOT depend on one another

Every algorithm RFC depends only on RFC-011. Direct dependencies between algorithm RFCs are forbidden:

```
    RFC-011  (Adaptive Common Model, frozen)
       ▲
       │
 ┌─────┼──────┬──────┬──────┐
 │     │      │      │      │
RFC-012 RFC-013 RFC-014 RFC-015
Reflection Merge Forget Hebbian
```

Reflection MUST NOT import Merge types. Merge MUST NOT import Forget types. Cross-algorithm interaction (if ever needed) happens through `MemoryEvent` on the shared `MemoryEventStream`, never through direct type dependencies.

### PF5. AlgorithmContext never owns data

`AlgorithmContext` carries only borrows and small `Copy` values (`DateTime<Utc>`, `Option<SessionId>`, `&dyn ImportanceEstimator`, `&dyn MemoryEventStream`). It MUST NOT gain fields of the following shapes:

- Owned collections: `Vec<Memory>`, `HashMap<...>`, `BTreeMap<...>`, `Arc<...>`, `Box<...>`.
- Service handles: any `&dyn Store`, `&dyn RecallEngine`, `&dyn PolicyEngine`, `&dyn Graph`, `&dyn LlmClient`, or their owned equivalents.
- Configuration bags, caches, or working buffers.

`AlgorithmContext` is a borrow of environment, not a service locator.

### PF6. Benchmarks use only public API

Benchmarks under `crates/eval/benches/algorithms/` MUST call the same public API surface that end users call. Benchmarks MUST NOT invoke internal helpers, private modules, `pub(crate)` shortcuts, or "debug" variants of algorithm methods. If a benchmark cannot express the measurement using the public API, either the measurement is invalid or the public API is incomplete — in either case the fix is not to widen the benchmark's access.

### PF7. Renaming a frozen type is breaking

Renaming any frozen type introduced by RFC-011 is a breaking change under `docs/COMPATIBILITY.md`, regardless of behavioral equivalence:

- `MemoryImportance` → `Importance`: breaking.
- `AlgorithmContext` → `ExecutionContext`: breaking.
- `MemoryEventStream` → `EventStream`: breaking.
- `BenchmarkReport` → `Report`: breaking.

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
