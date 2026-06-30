# ADR-003: RecallHit schema is frozen

Status: Accepted

## Context

`RecallHit` is the public shape that downstream callers inspect, render, and serialize. If the field set changes ad hoc, explainability and benchmark diffs both become noisy. The frozen contract also keeps the API aligned with the engine and booster rules.

## Decision

The `RecallHit` field set is frozen as of Step 5.5. The current fields are the complete contract: `score`, `rrf_score`, `rerank_score`, `activation_bonus`, branch ranks, `entity_hits`, and `sources`. Future additions require an ADR instead of a local patch.

## Consequences

Consumers can rely on stable serialization and explainability output. Internal changes must flow through the builder or through new optional fields approved by ADR. The freeze also makes the evaluation JSON stable enough to compare across releases.

## Enforcement

This is the contract cited by `crates/core/src/recall/hit.rs:1`. Additions to the struct need an ADR.
