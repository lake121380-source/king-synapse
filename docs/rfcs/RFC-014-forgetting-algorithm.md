# RFC-014: Forgetting Algorithm

Status: Draft

Phase: Phase 5 Algorithm Implementation

Depends on:

- `RFC-011: Adaptive Memory Common Model` (Implemented, read-only)
- `docs/ALGORITHM_GUIDELINES.md`

Implementation Tags:

```text
v0.8.0-forget-algorithm-skeleton         (implemented)
v0.8.1-forget-algorithm-noop             (implemented)
v0.8.2-forget-rule-based-reference       (implemented)
v0.8.3-forget-benchmark                  (implemented)
v0.8.4-forget-store-adapter              (implemented)
v0.8.9-forget-algorithm-freeze           (planned)
```

## Summary

RFC-014 defines the Forgetting Algorithm: a deterministic process that inspects
a memory in an `AlgorithmContext` and decides whether that memory should be
forgotten, reviewed as a forget candidate, or retained.

Forget is algorithm-local. It consumes the frozen RFC-011 common model and does
not extend `AlgorithmContext`, call Store, call Recall, access a graph backend,
or invoke an LLM.

## Motivation

A cognitive memory system must not only remember and merge. It also needs a
controlled cleanup path so stale, superseded, expired, or low-quality memories
do not accumulate forever.

The project already has a store-integration boundary:

```text
StoreMutationPlan
  -> StoreAdapter / PersistentStoreExecutor
  -> StoreExecutionReport
```

RFC-014 adds the algorithm that decides when a memory is forgettable without
writing to storage directly.

## Goals

1. Define a Forget algorithm target type wrapping one memory.
2. Follow RFC-011's primary method shape:
   `fn forget(&self, target: &ForgetTarget, ctx: &AlgorithmContext<'_>) -> ForgetOutput`.
3. Provide a NoOp implementation.
4. Provide a deterministic rule-based reference implementation.
5. Keep all behavior side-effect free.
6. Define a benchmark path mapped to `AlgorithmMetric::ForgetPrecision`.
7. Preserve frozen recall baselines.

## Non-Goals

- No Store writes.
- No direct Store, Recall, Graph, LLM, or policy engine access.
- No change to `AlgorithmContext`.
- No learned retention model.
- No deletion of high-importance or recently accessed memories.

## Types

All types are local to the Forget algorithm module.

```text
ForgetTarget
  memory: Memory

ForgetOutput
  Skipped { memory_id, reason }
  Candidate { memory_id, reason, score }
  Forget { memory_id, reason, score }
```

The output is not a Store mutation. Later layers may translate
`ForgetOutput::Forget` into existing archive/delete store mutation plans.

`v0.8.4` adds the first pure adapter:

```text
ForgetOutput::Forget
  -> StoreMutationPlan(ArchiveMemory)
  -> StoreAdapter / PersistentStoreExecutor
```

The adapter preserves the algorithm boundary. `ForgetAlgorithm` still has no
Store access and does not mutate state directly.

## Algorithm Flow

```text
Inspect
  -> Protect
  -> Score
  -> Decide
```

### Inspect

The rule-based reference considers deterministic local signals:

- expiration (`valid_to`);
- supersession (`superseded_by`);
- empty or low-quality content;
- low confidence;
- low importance;
- stale access timestamps.

### Protect

Recently accessed or high-importance memories are skipped even if they are old.
The first production rule should be conservative: forgetting should require
positive evidence.

### Score

The rule-based reference combines low confidence, low importance, stale access,
zero access count, and low-quality content into a finite score.

### Decide

The reference implementation:

- emits `Forget` for expired, superseded, empty, or high-score stale memories;
- emits `Candidate` for medium-score memories that should be reviewed;
- emits `Skipped` for protected or low-signal memories.

## Benchmark Plan

RFC-014 must add a benchmark under:

```text
crates/eval/benches/algorithms/
```

Minimum report:

```rust
BenchmarkReport {
    benchmark: "forget-precision".to_string(),
    metrics: BTreeMap::from([
        (AlgorithmMetric::ForgetPrecision, value),
    ]),
}
```

The first benchmark should use a deterministic fixture with known forgettable
and protected memories.

The initial implementation is exposed as `synapse_eval::forget_precision_report()`
and the `forget_precision` benchmark target. It reports `ForgetPrecision` as the
fraction of emitted `Forget` decisions that are true positives in the fixed
fixture; `Candidate` outputs are review signals and are not counted as forget
predictions.

## Acceptance Criteria

- `ForgetAlgorithm` follows the `target + AlgorithmContext` call shape.
- NoOp returns deterministic skipped output.
- Rule-based reference forgets expired or superseded memories.
- Rule-based reference protects high-importance or recently accessed memories.
- Benchmark emits `BenchmarkReport` mapped to `ForgetPrecision`.
- Forget output maps into the existing store mutation path.
- `cargo test --workspace` passes.
- `cargo clippy --all-targets --all-features -- -D warnings` passes.
- `reference` Recall@10 remains `1.000`.
- `multihop` Recall@10 remains `1.000` after ADR-006.
