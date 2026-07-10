# Phase 5.0 Algorithm Integration Design

Date: 2026-07-10

Status: Design-only

Scope: Algorithm engineering entry point after the Phase 4 cognitive
competition evaluation freeze.

## 1. Purpose

Phase 4 proved, in `crates/eval`, that cognitive candidates can be scored,
contextually weighted, made to compete, and kept stable under repeated runs,
minor context perturbation, and evidence accumulation.

Phase 5 asks a different question:

```text
How can the evaluated cognitive competition mechanisms become maintainable,
runtime-safe algorithms without breaking the frozen recall contract?
```

This document is a design boundary. It does not implement runtime behavior and
does not authorize direct changes to recall ranking, memory schema, activation
runtime, or production defaults.

## 2. Non-Goals

Phase 5.0 does not implement:

```text
runtime cognitive competition
runtime contextual weighting
automatic memory ranking changes
new recall fields
new memory schema fields
online learning
self modification
production default changes
```

It only defines how future Phase 5 implementation work should be staged.

## 3. Inputs From Phase 4

Validated evaluation capabilities:

| Phase | Capability | Runtime status |
| --- | --- | --- |
| 4.1 | Candidate influence scoring | Eval-only |
| 4.2 | Competition and suppression trace | Eval-only |
| 4.3 | Contextual cognitive weighting | Eval-only |
| 4.4 | Context-driven outcome changes | Eval-only |
| 4.5 | Stability and evidence transition | Eval-only |

The evaluated concepts are eligible for Phase 5 design consideration. None is
automatically eligible for production default behavior.

## 4. Runtime Boundary

The recall pipeline is frozen by `docs/RECALL_PIPELINE.md`.

Important constraints:

- `RecallHit` schema remains frozen.
- RRF fuses retrieval signals only.
- Rerankers perform semantic reranking only.
- Boosters cannot create candidates.
- Boosters cannot invoke retrievers.
- Boosters cannot modify RRF.
- Boosters cannot modify `RecallHit` fields except `activation_bonus`.
- Any recall improvement must be benchmarked before merge.

Therefore, Phase 5 cognitive competition cannot start by changing:

```text
RRF
RecallHit schema
memory schema
retriever behavior
reranker contract
candidate creation
production ranking defaults
```

## 5. Candidate Runtime Integration Points

### Option A: Inspection-Only Trace Layer

Location:

```text
CognitiveTraceProbe
```

Behavior:

- run cognitive competition after normal recall
- produce dominant and suppressed candidates in a separate report
- do not feed results back into recall ranking

Pros:

- safest production boundary
- preserves current recall behavior
- useful for debugging, explainability, and manual validation

Cons:

- does not improve Recall@K or MRR directly
- remains observational until a later gated integration

Decision:

```text
Allowed as the first implementation candidate.
```

### Option B: Additive RecallBooster

Location:

```text
RecallBooster
```

Behavior:

- compute bounded competition-derived bonus for already retrieved candidates
- write only to `activation_bonus`
- do not create candidates
- do not call retrievers
- do not modify RRF or reranker scores

Pros:

- fits the frozen booster contract
- can be default-off and A/B tested
- can improve final score without schema changes

Cons:

- must be tightly capped
- can still perturb ranking if bonus is too large
- requires careful regression gates

Decision:

```text
Allowed after inspection-only trace work, default-off only.
```

### Option C: Reranker Replacement Or Post-Reranker Rewrite

Location:

```text
Reranker / final ranking sort
```

Behavior:

- use cognitive competition to reorder candidates directly

Pros:

- strongest behavioral effect

Cons:

- violates current phase boundary
- high regression risk
- conflicts with existing ranking and DMR/LongMemEval validation boundaries

Decision:

```text
Rejected for initial Phase 5.
```

### Option D: Retriever Expansion

Location:

```text
FTS / vector / entity candidate creation
```

Behavior:

- use cognitive competition to add new candidates

Pros:

- could increase recall ceiling

Cons:

- violates booster contract
- changes recall candidate creation
- requires separate retrieval research and benchmark gates

Decision:

```text
Rejected for initial Phase 5.
```

## 6. Recommended Phase 5 Path

Phase 5 should progress in small, reversible steps:

```text
5.0 Algorithm Integration Design
  -> design only, no runtime behavior

5.1 Cognitive Competition Trace Skeleton
  -> public/local algorithm types, NoOp, deterministic reference
  -> inspection-only report

5.2 Cognitive Competition Trace Benchmark
  -> benchmark report over deterministic fixture
  -> trace quality, stability, latency

5.3 Default-Off Cognitive Competition Booster Prototype
  -> bounded activation_bonus only
  -> no candidate creation
  -> no schema change

5.4 A/B Recall Evaluation
  -> compare baseline vs booster-on
  -> Recall@K, MRR, latency, trace quality

5.5 Runtime Decision Gate
  -> keep default-off, promote, or reject
```

## 7. Initial Algorithm Shape

The first algorithm should follow `docs/ALGORITHM_GUIDELINES.md`.

Suggested local module shape:

```text
crates/core/src/recall/cognitive_competition/
  mod.rs
  model.rs
  engine.rs
  noop.rs
```

This is a design suggestion, not an instruction to implement now.

Suggested trait shape:

```rust
pub trait CognitiveCompetitionAlgorithm {
    fn compete(
        &self,
        target: &CognitiveCompetitionTarget,
        ctx: &AlgorithmContext<'_>,
    ) -> CognitiveCompetitionReport;
}
```

Rules:

- consume public/frozen types only
- keep value types local to the algorithm module
- do not extend `AlgorithmContext`
- include a NoOp implementation
- include a deterministic reference implementation
- do not depend on unrelated algorithm RFCs

## 8. Candidate Model Boundary

Runtime candidates should be derived from already retrieved `RecallHit`s or
from trace candidates already produced by inspection tools.

Allowed signals:

- existing `RecallHit.score`
- existing `RecallHit.activation_bonus`
- memory confidence
- memory importance
- decay-adjusted score already present in recall output
- context terms supplied by query/trace caller
- source ranks already present in `RecallHit`

Disallowed signals for initial integration:

- hidden store queries during competition
- new candidate creation
- memory writes
- schema-only fields not present in current models
- LLM-generated relevance labels

## 9. Contextual Weighting Boundary

Contextual weighting may be used only as bounded modulation.

Initial recommendation:

```text
contextual_weight in [0.0, 1.0]
competition_bonus <= configured_cap
default configured_cap = 0.0
experimental configured_cap <= existing activation booster caps
```

The first runtime implementation should prefer trace reporting over score
mutation. If score mutation is introduced, it should be only through
`activation_bonus`.

## 10. Complexity Budget

Initial target:

```text
candidate_count <= recall top-k or rerank pool
time complexity: O(n log n) for ranking, O(n^2) only if explicitly justified
memory overhead: O(n)
external model calls: none
store calls: none during competition
```

Any O(n^2) interaction model must include a benchmark showing that latency stays
within the project budget for normal recall sizes.

## 11. Configuration And Rollback

Initial rollout must be default-off.

Required controls:

- compile-time code path does not change behavior by default
- runtime flag or builder method explicitly enables the algorithm
- NoOp implementation remains available
- disabling the algorithm restores exact baseline behavior
- reports record whether competition was enabled

Rollback rule:

```text
If any baseline recall, latency, or trace-stability gate regresses,
the feature remains default-off or is reverted.
```

## 12. Evaluation Plan

Before runtime integration can be considered successful, compare:

```text
baseline recall
vs
competition trace only
vs
competition booster enabled
```

Minimum metrics:

- Recall@K
- MRR
- latency p50 / p95
- activation bonus distribution
- ranking delta count
- trace quality
- suppression explanation completeness
- deterministic replay stability

Required baseline gates:

- reference Recall@10 remains `1.000`
- multihop Recall@10 remains `1.000`
- no public API break unless an ADR approves it
- no memory schema change
- no runtime default change without A/B evidence

## 13. Phase 5 Entry Decision

Phase 5 may start with algorithm skeleton work only after this design boundary
is accepted:

```text
Allowed first implementation:
  inspection-only cognitive competition trace skeleton

Allowed later:
  default-off bounded booster prototype

Not allowed initially:
  RRF rewrite
  reranker replacement
  candidate expansion
  schema change
  default-on runtime behavior
```

## 14. Summary

Phase 4 proved the cognitive competition concept in evaluation fixtures.

Phase 5 should engineer that concept cautiously:

```text
trace first
default-off
bounded effects
public/frozen types only
benchmark before merge
no runtime default without evidence
```
