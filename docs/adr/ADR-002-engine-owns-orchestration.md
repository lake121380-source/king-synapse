# ADR-002: RecallEngine owns retrieval orchestration

Status: Accepted

## Context

Hybrid recall needs one place that owns the execution order and the score composition. Once FTS, entity, vector, reranking, and boosters all exist, scattering the control flow across multiple modules makes the behavior impossible to explain or benchmark.

## Decision

`RecallEngine` owns orchestration. It chooses which retrievers run, how candidates are fused, when reranking is applied, how booster passes are invoked, and how the final score is computed. The engine is the only layer allowed to combine signals across stages.

## Consequences

The recall path stays explainable from one entry point. Score drift is easier to detect because the composition is centralized. Adding a new branch or booster requires engine updates, but the rest of the system can remain stable.

## Enforcement

This is Invariant 2 in `docs/RECALL_PIPELINE.md`. Cross-stage orchestration elsewhere is a contract violation.
