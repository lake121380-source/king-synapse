# ADR-004: RecallBoosters are additive

Status: Accepted

## Context

The system needs a plugin point for memory evolution features without reopening the recall pipeline. A booster must be able to bias results using extra context, but it must not turn into a hidden retriever or a second ranker.

## Decision

`RecallBooster` is additive only. A booster may inspect the query and read-only store context, then add to `RecallHit::activation_bonus`. It may not create new candidates, call retrievers, rerank documents, or modify any other field.

## Consequences

New recall features can ship as plugins without destabilizing the core pipeline. The engine can apply boosters in sequence and then recompute the final order from the additive contribution. Explainability stays intact because the booster effect is explicit and isolated.

## Enforcement

This is Invariant 5 in `docs/RECALL_PIPELINE.md`. Non-additive booster behavior is out of contract.
