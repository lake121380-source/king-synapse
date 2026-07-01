# RFC-013: Merge Algorithm

Status: Draft

Phase: Phase 5 Algorithm Implementation

Depends on:

- `RFC-011: Adaptive Memory Common Model` (Implemented, read-only)
- `RFC-006: Consolidation Execution` (Draft / contract-aligned)
- `docs/ALGORITHM_GUIDELINES.md`

Implementation Tags:

```text
v0.7.0-merge-algorithm-skeleton          (implemented)
v0.7.1-merge-algorithm-noop              (implemented)
v0.7.2-merge-rule-based-reference        (implemented)
v0.7.3-merge-benchmark                   (implemented)
v0.7.4-merge-store-adapter               (implemented)
v0.7.9-merge-algorithm-freeze            (planned)
```

## Summary

RFC-013 defines the Merge Algorithm: a deterministic process that inspects a
candidate set of memories in an `AlgorithmContext` and decides whether those
memories should be merged, skipped, or left as candidates for later review.

Merge is algorithm-local. It consumes the frozen RFC-011 common model and does
not extend `AlgorithmContext`, call Store, call Recall, access a graph backend,
or invoke an LLM.

## Motivation

The v3 cognitive-memory vision requires long-term memory cleanup: duplicate
facts, repeated failures, and overlapping playbooks should not grow forever as
flat independent memories.

The project already has consolidation contracts:

```text
ConsolidationPlan
  -> ConsolidationExecutor
  -> ExecutionReport
  -> StoreMutationPlan
```

RFC-013 adds the algorithm that decides when a candidate memory set is mergeable
without changing those contracts.

## Goals

1. Define a Merge algorithm target type that wraps multiple memories.
2. Follow RFC-011's primary method shape:
   `fn merge(&self, target: &MergeTarget, ctx: &AlgorithmContext<'_>) -> MergeOutput`.
3. Provide a NoOp implementation.
4. Provide a deterministic rule-based reference implementation.
5. Keep all behavior side-effect free.
6. Define a benchmark path mapped to `AlgorithmMetric::MergePrecision`.
7. Preserve frozen recall baselines.

## Non-Goals

- No Store writes.
- No direct Store, Recall, Graph, LLM, or policy engine access.
- No change to `AlgorithmContext`.
- No change to `Memory`, `ConsolidationPlan`, `MergeGroup`, or `MergeStrategy`.
- No learned deduplication model.
- No semantic embedding comparison in this RFC.

## Types

All types are local to the Merge algorithm module.

```text
MergeTarget
  memories: Vec<Memory>

MergeOutput
  Skipped { reason }
  Candidate { memory_ids, strategy }
  Merge { memory_ids, strategy, merged_content }
```

The output is not a Store mutation. Later layers translate merge output into
existing consolidation/store plans.

`v0.7.4` adds the first pure adapter:

```text
MergeOutput::Merge
  -> ConsolidationPlan.merge
  -> ExecutionReport::Merge
  -> StoreMutationPlan(UpdateMemory + ArchiveMemory...)
```

The adapter preserves the algorithm boundary. `MergeAlgorithm` still has no
Store access and does not mutate state directly.

## Algorithm Flow

```text
Select
  -> Compare
  -> Decide
  -> Produce
```

### Select

Reject structurally invalid input:

- fewer than two memories;
- empty content after trimming;
- expired or superseded memories.

### Compare

The rule-based reference compares only deterministic local signals:

- normalized token overlap;
- same memory kind;
- same scope;
- repeated explicit key phrases such as "fix", "prefer", "error", "must".

It does not call embeddings or external services.

### Decide

The reference implementation:

- emits `Merge` for high overlap and compatible memory kinds;
- emits `Candidate` for medium overlap;
- emits `Skipped` for low overlap or incompatible structure.

### Produce

`Merge` output concatenates unique normalized content lines in input order.
This is intentionally conservative; production implementations may use better
summarization later, but only behind the same trait.

## Benchmark Plan

RFC-013 must add a benchmark under:

```text
crates/eval/benches/algorithms/
```

Minimum report:

```rust
BenchmarkReport {
    benchmark: "merge-precision".to_string(),
    metrics: BTreeMap::from([
        (AlgorithmMetric::MergePrecision, value),
    ]),
}
```

The first benchmark should use a deterministic fixture with known mergeable and
non-mergeable groups.

The initial implementation is exposed as `synapse_eval::merge_precision_report()`
and the `merge_precision` benchmark target. It reports `MergePrecision` as the
fraction of emitted `Merge` decisions that are true positives in the fixed
fixture; `Candidate` outputs are review signals and are not counted as merge
predictions.

## Acceptance Criteria

- `MergeAlgorithm` follows the `target + AlgorithmContext` call shape.
- NoOp returns deterministic skipped output.
- Rule-based reference produces a merge for controlled duplicate memories.
- Rule-based reference skips incompatible groups.
- Benchmark emits `BenchmarkReport` mapped to `MergePrecision`.
- Merge output maps into the existing consolidation/store mutation path.
- `cargo test --workspace` passes.
- `cargo clippy --all-targets --all-features -- -D warnings` passes.
- `reference` Recall@10 remains `1.000`.
- `multihop` Recall@10 remains `0.600`.
