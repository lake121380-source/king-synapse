# RFC-015: Hebbian Algorithm

Status: Implemented

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
v0.9.4-hebbian-store-adapter             (implemented)
v0.9.5-sqlite-edge-persistence           (implemented)
v0.9.9-hebbian-algorithm-freeze          (superseded by v0.9.26-cognitive-memory-freeze)
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

## Store Integration

`v0.9.4` connects Hebbian algorithm output into the existing store-mutation
planning boundary without changing any frozen contracts:

```text
HebbianOutput::Plans
  -> EdgeUpdatePlan
  -> HebbianExecutor
  -> HebbianExecutionReport
  -> DeterministicHebbianStoreMutationDispatcher
  -> StoreMutationPlan(UpdateEdge)
```

Only executed `ExecutedEdgeUpdate::Apply` actions become
`StoreMutation::UpdateEdge` values. Skipped invalid or duplicate edge updates
remain in `HebbianExecutionReport` and are not dispatched to Store.

SQLite persistent execution now applies `UpdateEdge` through
`Store::update_edge`, storing directed associative edges in `memory_edges` and
accumulating repeated weight deltas. This is deliberately below the algorithm
and dispatcher layers, so Hebbian stays pure while its approved StoreMutation
output can become durable graph state.

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
- `multihop` Recall@10 remains `1.000` after ADR-006.

## Freeze Disposition

RFC-015 is freeze-reviewed as part of
`docs/releases/v0.9.26-cognitive-memory-freeze.md`.

The rule-based Hebbian heuristic, benchmark, StoreMutation adapter, SQLite edge
persistence path, graph/latent activation consumers, and cognitive trace
reinforcement surfaces are accepted for the cognitive-memory freeze. Future
Hebbian quality work must preserve the post-report reinforcement boundary and
the frozen recall contract.
