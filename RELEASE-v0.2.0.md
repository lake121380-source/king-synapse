# King Recall v0.2.0 - Recall API Freeze

## Status

Recall Platform is now considered **stable**.

This release concludes **Phase 2** and establishes the platform contract for future Memory Evolution work.

## Highlights

- RecallEngine orchestrates retrieval
- Hybrid retrieval (FTS + Vector + Entity + RRF)
- Pluggable Reranker
- Frozen RecallHit contract
- RecallBooster extension point
- Explainable recall (`kr recall --explain`)
- Evaluation harness and benchmark baseline
- Architecture contract (`RECALL_PIPELINE.md` + ADRs)

## Frozen Contract

The following interfaces are now treated as stable:

- RecallEngine
- RecallHit
- RecallBooster
- Reranker
- Recall Pipeline
- Public Recall API

Changes to these contracts require an approved ADR.

## Benchmark Baseline

```text
Recall@10  0.950
MRR@10     0.933
NDCG@10    0.929
```

Reference baseline:

```text
crates/eval/results/recall-api-freeze.json
```

## Next

**Phase 3 - Memory Evolution**

Focus:

- Working Memory
- ActivationBooster
- Reflection Events
- Consolidator

Guiding principle:

> Evolve memory, not the Recall contract.

Stable platforms evolve through extensions first, and platform changes only through explicit architectural decisions (ADRs).
