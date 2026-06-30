# ADR-005: Benchmark-first recall development

Status: Accepted

## Context

Recall changes are easy to overfit by intuition and hard to validate by inspection. The project already has a golden set and a bench harness, so the development contract should make measurement the gate for shipping changes.

## Decision

Any recall improvement must be benchmarked before merge. The standard gate is the recall bench against the frozen golden set, with the results captured in JSON so changes can be compared across tags.

## Consequences

Quality changes are tied to concrete numbers instead of anecdotes. The team can tell whether a new branch, reranker, or booster improves recall or only shifts the explanation. This also keeps the freeze tag meaningful as a baseline.

## Enforcement

This is Invariant 6 in `docs/RECALL_PIPELINE.md`. If a change cannot be benchmarked, it does not belong in the freeze line.
