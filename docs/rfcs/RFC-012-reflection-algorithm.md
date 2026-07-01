# RFC-012: Reflection Algorithm

Status: Draft

Phase: Phase 5 Algorithm Implementation

Depends on:

- `RFC-011: Adaptive Memory Common Model` (Implemented, read-only)
- `RFC-007: Reflection Processing` (Accepted, contract-frozen)
- `docs/ALGORITHM_GUIDELINES.md`

Implementation Tags:

```text
v0.6.0-reflection-algorithm-skeleton        (planned)
v0.6.1-reflection-algorithm-noop            (planned)
v0.6.2-reflection-deterministic-reference   (planned)
v0.6.3-reflection-benchmark                 (planned)
v0.6.9-reflection-algorithm-freeze          (planned)
```

Subtitle: First concrete Adaptive Memory algorithm built on RFC-011

## Summary

RFC-012 defines the Reflection Algorithm: a deterministic process that inspects a target memory in an `AlgorithmContext`, decides whether that memory should produce reflection work, and emits reflection outputs through the already frozen Reflection Processing contract.

This RFC is specification-only. It does not implement code, change any public API, add shared adaptive types, modify `AlgorithmContext`, or alter RFC-011.

## Motivation

Phase 4 froze the Reflection Processing execution shape:

```text
ReflectionEvent
  -> ReflectionEngine
  -> ReflectionPlan
  -> ReflectionExecutor
  -> ReflectionReport
  -> ReflectionSink
```

RFC-011 froze the shared model all algorithms consume:

```text
Memory + AlgorithmContext
  -> Importance
  -> Event Stream
  -> BenchmarkReport
```

The project now needs the first concrete algorithm that uses these frozen contracts without changing them. Reflection is the natural first algorithm because it can improve memory quality while remaining side-effect free until execution.

## Goals

1. Define Reflection's objective and algorithm boundary.
2. Define the input and output shape using RFC-011's uniform call pattern.
3. Define a deterministic pipeline that can be implemented in skeleton, NoOp, deterministic reference, benchmark, and production milestones.
4. Define how Reflection consumes `AlgorithmContext` without adding new shared model fields.
5. Define failure behavior for empty input, inert memory, malformed context, and event replay edge cases.
6. Define a benchmark mapping to `BenchmarkReport` and `AlgorithmMetric::ReflectionYield`.
7. Preserve frozen Recall baselines.

## Non-Goals

- No change to RFC-011, `AlgorithmContext`, `MemoryEventStream`, `MemoryImportance`, or `BenchmarkReport`.
- No new top-level shared types under `crates/core/src/adaptive/`.
- No direct Store access.
- No direct RecallEngine access.
- No graph engine access.
- No LLM client or prompt design.
- No prompt tuning, learned strategy, or parameter sweep.
- No Merge, Forget, or Hebbian algorithm design.
- No production-quality semantic reflection implementation in this RFC.

## Architecture

Reflection sits below `AlgorithmContext` and above the already frozen Reflection Processing pipeline:

```text
Memory
  + AlgorithmContext<'_>
      ├─ importance: &dyn ImportanceEstimator
      └─ events:     &dyn MemoryEventStream
        │
        ▼
Reflection Algorithm
  -> ReflectionCandidate
  -> ReflectionDecision
  -> ReflectionOutput
        │
        ▼
Reflection Processing (RFC-007)
  -> ReflectionEvent / ReflectionPlan / ReflectionReport
```

`ReflectionCandidate`, `ReflectionDecision`, and `ReflectionOutput` are algorithm-local types. They must live under the Reflection algorithm module, not in the shared `adaptive/` root.

## Algorithm Objective

Reflection answers one question:

> Given a memory and the current algorithm environment, should this memory produce reflection work now, and if yes, what deterministic reflection output should be passed to the frozen Reflection Processing layer?

Reflection does not mutate memory directly. It produces algorithm-local output that later milestones translate into the existing Phase 4 Reflection Processing contracts.

Reflection Algorithm MUST be side-effect free. It must not modify Store, write recall indexes, update graph state, call external services, persist diagnostic state, or perform external IO. Its only algorithm-level output is `ReflectionOutput`; a higher layer decides whether and how that output enters the frozen Reflection Processing and Store Integration pipelines.

## Primary Call Shape

Reflection MUST follow RFC-011 PF2 and `docs/ALGORITHM_GUIDELINES.md`:

```rust
fn reflect(&self, target: &Memory, ctx: &AlgorithmContext<'_>) -> ReflectionOutput
```

The exact trait and type names are implemented by the skeleton milestone, but the primary method shape is fixed:

- first argument: exactly one target (`&Memory`),
- second argument: `&AlgorithmContext<'_>`,
- no additional shared context parameters,
- no direct Store / Recall / Graph / LLM handles.

## Inputs

Required input:

- `target: &Memory` - the memory being considered for reflection.
- `ctx: &AlgorithmContext<'_>` - execution environment.

Context fields used:

- `ctx.now` - deterministic caller-provided time.
- `ctx.session_id` - optional session scope.
- `ctx.importance` - estimates `MemoryImportance` for `target`.
- `ctx.events` - provides replay-oriented recent events.

Context fields not allowed:

- no target memory embedded in context,
- no Store handle,
- no RecallEngine handle,
- no policy engine handle,
- no graph engine handle,
- no LLM client,
- no owned collections or caches.

## Outputs

Reflection output is algorithm-local and must include enough information for later milestones to map into RFC-007 Reflection Processing.

Minimum conceptual output variants:

```text
ReflectionOutput
  Skipped { reason }
  Candidate { target_memory_id, importance, evidence }
  Produced { target_memory_id, reflection_payload }
```

This RFC does not freeze exact Rust names or field lists. Skeleton implementation defines algorithm-local concrete types under the Reflection module. Those types must not be added to RFC-011 or the shared `adaptive/` root.

## Algorithm Flow

The deterministic reference implementation SHOULD follow this stage order:

```text
Select
  -> Analyze
  -> Decide
  -> Produce
```

### Stage 1: Select

Select determines whether `target` is structurally eligible for reflection.

Rules:

- Empty content is skipped.
- Superseded or invalid memories are skipped if the `Memory` model indicates that state.
- Session-scoped behavior must use `ctx.session_id` only as scope information, not as hidden state.
- Selection must not query Store or Recall.

### Stage 2: Analyze

Analyze computes the signals Reflection is allowed to observe:

- `ctx.importance.estimate(target, ctx)` for `MemoryImportance`.
- `ctx.events.recent(N)` for deterministic event replay.

Rules:

- `overall` is algorithm-facing.
- Individual `ImportanceSignals` are explainability and diagnostics only; the algorithm must not branch on a single signal unless a later RFC explicitly justifies it.
- Event replay order is record order, not timestamp order.
- Reflection must treat missing events as empty context, not an error.

### Stage 3: Decide

Decide turns analysis into one of:

```text
Skip
ProduceReflection
Defer
```

Reference implementation expectations:

- deterministic for the same `(target, ctx)` inputs,
- no random number generation,
- no system clock reads,
- no IO,
- no mutation.

### Stage 4: Produce

Produce converts a positive decision into algorithm-local reflection output suitable for later mapping to RFC-007 types.

Rules:

- Output must be deterministic.
- Output must not write Store.
- Output must not call Recall.
- Output must not call an LLM.
- Output must be serializable if the skeleton chooses to expose it across reports.

## Failure Handling

Failure behavior must be deterministic and explicit.

| Scenario | Required behavior |
| --- | --- |
| Empty memory content | Return `Skipped` with an empty-content reason. |
| Structurally inert memory | Return `Skipped` with a structural reason. |
| No recent events | Continue with empty evidence. |
| `recent(N)` returns fewer than `N` events | Use all returned events. |
| `ImportanceEstimator` returns zero importance | Deterministically skip or defer according to the algorithm-local threshold. |
| Invalid algorithm-local threshold/config | Use safe default or fail at construction; do not fail during `reflect`. |
| Sink or executor failure | Out of scope for Reflection Algorithm; handled by RFC-007 processing/execution contracts. |

Reflection must not hide errors by converting them into successful produced output. If construction or configuration can fail in production implementations, that failure belongs at construction time, not inside the primary method.

## Deterministic Reference Expectations

The deterministic reference implementation is not a production-quality semantic algorithm. It exists to validate the pipeline shape, edge cases, and benchmarks.

Its goal is reproducibility, not quality. Given the same input memory, the same `AlgorithmContext`, and the same configuration, it must produce the same output so benchmark comparisons are meaningful.

It MUST satisfy:

1. Same `(Memory, AlgorithmContext)` -> identical `ReflectionOutput`.
2. Empty memory -> deterministic `Skipped`.
3. No events -> deterministic output.
4. Event replay order affects evidence only according to record order.
5. No direct Store, Recall, Graph, Policy, or LLM access.
6. No system clock reads; use `ctx.now` only.
7. Produces at least one positive output for a controlled synthetic eligible memory.
8. Produces no output for structurally inert memory.

## Benchmark Plan

RFC-012 must add at least one benchmark under:

```text
crates/eval/benches/algorithms/
```

Minimum report:

```rust
BenchmarkReport {
    benchmark: "reflection-yield".to_string(),
    metrics: BTreeMap::from([
        (AlgorithmMetric::ReflectionYield, value),
    ]),
}
```

Recommended additional metrics:

- `AlgorithmMetric::AlgorithmLatency`
- `AlgorithmMetric::EventReplayLatency` if the benchmark stresses event replay
- `AlgorithmMetric::MemoryGrowth` only if the implementation produces measurable downstream memory growth through existing frozen execution layers

Benchmark rules:

- Reports must be deterministic value objects.
- Missing metrics are not zero.
- Benchmarks must use only public API.
- Benchmark names use lowercase-kebab-case.
- Benchmarks must not call reflection-internal debug helpers.

## Acceptance Criteria

The Reflection Algorithm RFC is complete when:

- It defines algorithm-local input/output types without adding shared types to RFC-011.
- It defines a skeleton trait whose primary method follows `target + AlgorithmContext`.
- It provides a NoOp implementation.
- It provides a deterministic reference implementation.
- It adds at least one `BenchmarkReport`-producing benchmark mapped to `ReflectionYield`.
- Production implementations are compared against the deterministic reference implementation before freeze.
- It preserves `reference` `Recall@10 = 1.000`.
- It preserves `multihop` `Recall@10 = 0.600`.
- `cargo test --workspace` passes.
- `cargo clippy --all-targets -- -D warnings` passes.
- Empty input and normal input are manually validated.

## Milestones

```text
v0.6.0-reflection-algorithm-skeleton
  -> v0.6.1-reflection-algorithm-noop
  -> v0.6.2-reflection-deterministic-reference
  -> v0.6.3-reflection-benchmark
  -> v0.6.9-reflection-algorithm-freeze
```

Milestone constraints:

- Skeleton defines algorithm-local types and the primary trait shape only.
- NoOp emits deterministic skipped/empty output.
- Deterministic reference adds simple positive/negative behavior without IO.
- Benchmark milestone emits `BenchmarkReport` and does not introduce a runner/exporter.
- Freeze updates API docs only for algorithm-local stable items, not RFC-011.

## Open Questions

1. Should the first deterministic reference use a fixed importance threshold, or only structural eligibility?
2. Should event evidence in the deterministic reference include all recent events, or only events whose `memory_ids` mention the target memory?
3. Should Reflection output map immediately to existing `ReflectionPayload`, or should that mapping wait until the skeleton milestone?
4. Should the first benchmark dataset be synthetic only, or should it derive from existing `reference` / `multihop` memories?
