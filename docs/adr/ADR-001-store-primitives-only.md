# ADR-001: Store exposes retrieval primitives only

Status: Accepted

## Context

`Store` used to host more of the recall path than it should. As retrieval grew from FTS-only into a hybrid pipeline, the storage layer became the wrong place for branch fusion, reranking, and score shaping. That made the API harder to reason about and made recall changes leak into persistence concerns.

## Decision

`Store` exposes retrieval primitives only. It may offer low-level search and persistence operations such as FTS, entity, and vector lookup, plus state updates like embedding writes and access recording. It does not orchestrate retrieval, fuse branches, rerank candidates, or apply boosters.

## Consequences

The storage API stays narrow and testable. New retrieval behavior belongs in `RecallEngine`, not in the store. Branch-specific logic can evolve without changing persistence semantics.

## Enforcement

This is Invariant 1 in `docs/RECALL_PIPELINE.md`. Any orchestration logic added to `Store` is out of contract.
