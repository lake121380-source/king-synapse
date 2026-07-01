# RFC-015: Hebbian Algorithm

Status: Draft

Phase: Phase 5 Algorithm Implementation

Depends on:

- `RFC-011: Adaptive Memory Common Model` (Implemented, read-only)
- `RFC-008: Hebbian Execution` (Accepted / contract-frozen)
- `docs/ALGORITHM_GUIDELINES.md`

Implementation Tags:

```text
v0.9.0-hebbian-algorithm-skeleton        (implemented)
v0.9.1-hebbian-algorithm-noop            (implemented)
v0.9.2-hebbian-rule-based-reference      (implemented)
v0.9.3-hebbian-benchmark                 (implemented)
v0.9.9-hebbian-algorithm-freeze          (planned)
```

## Summary

RFC-015 defines the Hebbian Algorithm: a deterministic process that inspects
memory events in an `AlgorithmContext` and produces edge-update plans for
memories that co-occur in meaningful events.

Hebbian is algorithm-local. It consumes the frozen RFC-011 common model and does
not extend `AlgorithmContext`, call Store, call Recall, access a graph backend,
or invoke an LLM.

## Motivation

The v3 cognitive-memory vision needs association learning: memories recalled,
updated, merged, or reflected together should become easier to traverse
together later.

The project already has Hebbian execution contracts:

```text
EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
```

RFC-015 adds the algorithm that decides which edge updates should be produced
without changing those contracts.

## Goals

1. Define a Hebbian algorithm target type wrapping memory events.
2. Follow RFC-011's primary method shape:
   `fn reinforce(&self, target: &HebbianTarget, ctx: &AlgorithmContext<'_>) -> HebbianOutput`.
3. Provide a NoOp implementation.
4. Provide a deterministic rule-based reference implementation.
5. Keep all behavior side-effect free.
6. Define a benchmark path mapped to `AlgorithmMetric::HebbianConsistency`.
7. Preserve frozen recall baselines.

## Non-Goals

- No Store writes.
- No direct Store, Recall, Graph, LLM, or policy engine access.
- No change to `AlgorithmContext`.
- No learned graph model.
- No graph backend dependency.

## Types

All types are local to the Hebbian algorithm module.

```text
HebbianTarget
  events: Vec<MemoryEvent>

HebbianOutput
  Skipped { reason }
  Plans { plans, evidence_count }
```

The output is not a Store mutation. It is a set of existing `EdgeUpdatePlan`
values that later flow through the frozen Hebbian execution layer.

## Algorithm Flow

```text
Collect
  -> Co-occur
  -> Weight
  -> Produce
```

### Collect

The rule-based reference reads memory IDs from RFC-011 `MemoryEvent` values.
Single-memory and memory-less events are not enough evidence.

### Co-occur

For each event with at least two unique memories, the reference emits
bidirectional candidate edges. Duplicate edges are removed deterministically.

### Weight

The initial reference uses deterministic event-kind weights:

- recall/update/write events produce small reinforcement;
- reflection, reinforcement, and merge events produce stronger reinforcement;
- invalidation/forgetting events produce weak reinforcement.

### Produce

The algorithm returns `HebbianOutput::Plans` with existing `EdgeUpdatePlan`
values. It does not execute plans.

## Benchmark Plan

RFC-015 must add a benchmark under:

```text
crates/eval/benches/algorithms/
```

Minimum report:

```rust
BenchmarkReport {
    benchmark: "hebbian-consistency".to_string(),
    metrics: BTreeMap::from([
        (AlgorithmMetric::HebbianConsistency, value),
    ]),
}
```

The first benchmark should use deterministic fixtures with repeated
co-occurrence and expected edge sets.

The initial implementation is exposed as `synapse_eval::hebbian_consistency_report()`
and the `hebbian_consistency` benchmark target. It reports `HebbianConsistency`
as the overlap between produced and expected directed edges in the fixed
fixture, with false-positive and missed edges penalized.

## Acceptance Criteria

- `HebbianAlgorithm` follows the `target + AlgorithmContext` call shape.
- NoOp returns deterministic skipped output.
- Rule-based reference produces bidirectional edge plans for co-occurring memory events.
- Rule-based reference skips empty or single-memory event sets.
- Benchmark emits `BenchmarkReport` mapped to `HebbianConsistency`.
- `cargo test --workspace` passes.
- `cargo clippy --all-targets --all-features -- -D warnings` passes.
- `reference` Recall@10 remains `1.000`.
- `multihop` Recall@10 remains `0.600`.
