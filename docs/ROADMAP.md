# King Recall Roadmap

Current milestone

✓ Phase 1 — Capture Engine
✓ Phase 2 — Recall Platform (Recall API Freeze)

Current focus

▶ Phase 3 — Memory Evolution

Phase 2 concluded with `v0.2.0-recall-api-freeze`. The Recall contract is now considered stable. Future work extends the platform rather than redesigning it.

## Phase 3 Contract

> **Phase 3 must not modify the Recall contract unless an ADR explicitly approves the change.**

Rules

1. `RecallHit` schema remains frozen.
2. `RecallBoosters` are the only extension point for recall scoring.
3. Every recall-related behavior change must preserve or improve benchmark results.

## Phase 3 — Memory Evolution

Goal

Enable memories to evolve over time without changing the Recall Platform.

Epic 1

Working Memory

Session-scoped temporary memory

Consolidation into long-term memory

Epic 2

ActivationBooster

Graph activation

Priming

Hebbian weighting

Epic 3

Reflection Events

LLM-generated reflections

Event log

No direct memory writes

Epic 4

Consolidator

Nightly merge

Deduplication

Decay

Archival

## Phase 4 — Adaptive Recall

Goal

Improve recall quality through learned behavior while preserving the Recall contract.

## Completed Milestones

v0.2.0-recall-api-freeze

Highlights

• RecallEngine
• Hybrid Retrieval (RRF)
• Pluggable Reranker
• Explainable Recall
• RecallHit Contract
• RecallBooster Extension Point
• Evaluation Harness
