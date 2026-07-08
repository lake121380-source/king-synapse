# Cognitive Memory Benchmark

Phase 1 final validation is a synthetic benchmark for testing whether Synapse
can use past experience as decision influence instead of only retrieving
similar text.

## Claim Boundary

This benchmark supports the cautious claim:

> On synthetic cognitive-memory cases, Synapse shows stronger auditable memory
> reasoning than retrieval-only baselines.

It does not support the broad claim that Synapse is generally better than RAG.
The current case count is intentionally small and should be treated as
directional evidence until Phase 1.1 expands the suite.

## Current Suites

- `consistency.toml`: longitudinal preference and preference revision.
- `causal.toml`: retrieval-vs-reasoning and multi-hop causal memory.
- `evolution.toml`: strategy evolution after failures and retrospectives.
- `governance.toml`: governance boundary and exploration preservation traces.
- `preference.toml`: preference changes after later feedback or incidents.
- `failure_learning.toml`: failures turning into strategy updates.
- `contradiction.toml`: old beliefs competing with newer evidence.
- `temporal.toml`: time order, recency, and partial temporal ambiguity.
- `adversarial.toml`: keyword overlap, spurious causality, and over-inference.

## Baselines

Every case must include the same method set:

- `vector_rag`
- `bm25_rag`
- `hybrid_rag`
- `rag_plus_edge`
- `rag_plus_activation`
- `rag_plus_governance`
- `full_synapse`

This makes ablation stable across reports and prevents the final score from
hiding which layer contributes the gain.

## Scoring Axes

- `evidence_coverage`: whether required memories are surfaced.
- `trace_completeness`: whether the expected reasoning chain appears.
- `causal_order`: whether the trace preserves temporal or causal order.
- `memory_influence_score`: whether past experience changes the decision.
- `governance_trace_score`: whether governance action is justified and visible.
- `contradiction_handling`: whether revised or conflicting memories are resolved.

## Phase 1.1 Expansion Status

The first Phase 1.1 suite expands the benchmark from 8 cases to 50 cases across
at least these categories:

- causal
- preference
- failure_learning
- strategy_evolution
- contradiction
- temporal_reasoning
- governance_boundary
- adversarial

The report intentionally includes failed cases. A credible research benchmark
should preserve visible misses rather than only reporting aggregate pass/fail.

## Phase 1.1.1 Error Analysis

The report now separates:

- retrieval failures: relevant evidence is not sufficiently covered.
- reasoning failures: evidence is present, but decision, causal order, or
  governance interpretation fails.
- decision mismatches.
- causal ordering errors.
- governance boundary misses.

This is intended to answer whether remaining misses come from retrieval or from
memory reasoning.

## Memory Influence Attribution

`memory_influence_attribution` is an evaluation proxy over expected trace nodes.
It estimates which historical factors drove the benchmark decision by assigning
activation deltas over the expected trace. It is not a persisted memory edge
weight and does not mutate memory state.

The next externalized target is 200 cases with a stable scorer, frozen dataset
schema, and broader adversarial coverage.

## Version Freeze Target

`v0.6.0-cognitive-validation` should freeze:

- dataset schema
- method names
- ablation protocol
- trace quality metrics
- report field names
- claim boundary language
