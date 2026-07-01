# Algorithm Guidelines

Phase 5 is Algorithm-first. The shared contracts are frozen by `v0.5.9-adaptive-common-freeze`; algorithm work MUST improve behavior without changing the public model.

This is a long-lived engineering guideline for all Algorithm-first work, not a Reflection-only note. Future algorithm families (Reflection, Merge, Forget, Hebbian, Planning, Memory, Routing, and similar work) SHOULD follow the same lifecycle and quality gates unless a later ADR replaces this document.

## Scope

This document governs all Phase 5 algorithm RFCs and implementations:

- RFC-012 Reflection
- RFC-013 Merge
- RFC-014 Forget
- RFC-015 Hebbian

It is an engineering guideline, not a new API contract. Normative API rules remain in `docs/rfcs/RFC-011-adaptive-memory-common-model.md`, `docs/API_SURFACE.md`, and `docs/COMPATIBILITY.md`.

## Required Shape

Every algorithm MUST consume RFC-011 and MUST NOT extend it.

Primary algorithm methods MUST follow the frozen call shape:

```rust
fn method(&self, target: &T, ctx: &AlgorithmContext<'_>) -> Output
```

Rules:

- `target` is the algorithm-specific input.
- `ctx` is the execution environment.
- Multi-input algorithms MUST wrap inputs into one target aggregate.
- Algorithms MUST NOT add fields to `AlgorithmContext`.
- Algorithms MUST NOT define new top-level shared types under `crates/core/src/adaptive/`.
- Algorithm RFCs MUST NOT depend on one another. Each depends only on RFC-011.

## Implementation Ladder

Each algorithm SHOULD ship in this order:

1. **RFC** - objective, inputs, outputs, pipeline, benchmark mapping, non-goals.
2. **Skeleton** - public trait and value types local to the algorithm module.
3. **NoOp** - deterministic placeholder that emits no behavior.
4. **Deterministic Reference** - simple implementation suitable for tests and benchmarks.
5. **Benchmark** - at least one `BenchmarkReport` mapped to at least one `AlgorithmMetric`.
6. **Production Implementation** - optional until the algorithm RFC defines its acceptance criteria.
7. **Freeze** - release note, tag, tests, baselines, and compatibility check.

Algorithms MUST NOT skip the NoOp or deterministic reference step.

## Boundaries

Algorithms MAY consume:

- `Memory`
- `AlgorithmContext<'_>`
- `ImportanceEstimator`
- `MemoryImportance`
- `MemoryEventStream`
- `MemoryEvent`
- Existing frozen behavior contracts from Phase 3 and Phase 4

Algorithms MUST NOT directly access:

- `Store`
- `RecallEngine`
- Graph engines
- LLM clients
- Policy engines outside their frozen policy boundary
- Private modules, `pub(crate)` helpers, debug-only methods, or test-only shortcuts

If an algorithm needs to observe prior behavior, it MUST read `MemoryEventStream`. If it needs to produce persistent effects, it MUST emit existing plans/reports that flow through the frozen execution and store-integration layers.

## Benchmark Rules

Every algorithm RFC MUST define at least one benchmark under `crates/eval/benches/algorithms/`.

Every benchmark MUST emit a `BenchmarkReport`:

```rust
BenchmarkReport {
    benchmark: String,
    metrics: BTreeMap<AlgorithmMetric, f64>,
}
```

Rules:

- `benchmark` MUST use `lowercase-kebab-case`.
- Reports MUST be deterministic value objects: same dataset, same algorithm, same config, same report.
- Reports MUST contain only meaningful metrics. Missing metrics are not zero.
- Benchmarks SHOULD emit finite `f64` values.
- Benchmarks MUST call only public API available to normal users.

Recommended metric mapping:

| Algorithm | Minimum metric |
| --- | --- |
| Reflection | `ReflectionYield` |
| Merge | `MergePrecision` |
| Forget | `ForgetPrecision` |
| Hebbian | `HebbianConsistency` |

Latency-sensitive benchmarks MAY also report `AlgorithmLatency`. Event-heavy benchmarks MAY report `EventReplayLatency`.

## Quality Gates

Before an algorithm freeze, the implementation MUST pass:

1. `cargo test --workspace`
2. `cargo clippy --all-targets -- -D warnings`
3. Frozen baseline check: `reference` `Recall@10 = 1.000`
4. Frozen baseline check: `multihop` `Recall@10 = 1.000` after ADR-006
5. At least one deterministic benchmark producing `BenchmarkReport`
6. At least one normal input manual validation
7. At least one error or empty input manual validation

Benchmark improvements are expected, but baseline regressions MUST require an ADR.

## Freeze Checklist

Each algorithm freeze MUST include:

- RFC status updated to Implemented.
- API surface unchanged unless the RFC explicitly introduced stable algorithm-local items.
- Compatibility review completed.
- Release note added under `docs/releases/`.
- Git tag created for the freeze milestone.
- Tests, clippy, and recall baselines reported.

## Non-Goals

Algorithm RFCs MUST NOT use this guideline as permission to:

- Change RFC-011.
- Add shared top-level adaptive types.
- Expand `AlgorithmContext`.
- Add Store, Recall, Graph, LLM, or Policy handles to algorithm context.
- Couple algorithm RFCs to one another.
- Benchmark internal-only behavior.
