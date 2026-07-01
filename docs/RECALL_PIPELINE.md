# Recall Pipeline

Status: **Frozen as of v0.2.0-recall-api-freeze.**

This document is the contract for how King Synapse turns a `RecallQuery` into a ranked list of `RecallHit`s. The shape of the pipeline, the score formula, the `RecallHit` field set, and the six design invariants in Section 6 are stable. Changes require an ADR under `docs/adr/`.

---

## 1. Overview

**Purpose**

RecallEngine is responsible for orchestrating retrieval. It combines multiple retrieval signals into a ranked, explainable set of `RecallHit`s.

Store is responsible for storage only. It never performs retrieval orchestration.

```text
                Query
                  │
                  ▼
            RecallEngine
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
     FTS       Vector      Entity
      └───────────┼───────────┘
                  ▼
                 RRF
                  ▼
           Candidate Pool
                  ▼
             Reranker
                  ▼
            Base Score
                  ▼
          RecallBoosters
                  ▼
            Final RecallHit
```

---

## 2. Recall Pipeline

| Stage | Input | Output | Responsibility |
| --- | --- | --- | --- |
| Retriever | Query | Candidates | Create candidates only |
| RRF | Candidates | Ranked candidates | Fuse retrieval signals only |
| Reranker | Candidates | Ranked candidates | Semantic reranking only |
| Booster | RecallHit | RecallHit | Adjust score only |

Each stage has exactly one responsibility. Cross-stage behavior is prohibited.

---

## 3. Score Formula

```text
base_score =
    sigmoid(rerank_score or rrf_score)

final_score =
    base_score
    × importance
    × confidence
    × decay
    + activation_bonus
```

- `rrf_score` is produced by retrieval fusion.
- `rerank_score` replaces `rrf_score` when available.
- `activation_bonus` is additive only.
- Future boosters may contribute only through `activation_bonus`.

---

## 4. RecallHit Contract

| Field | Meaning | Mutable |
| --- | --- | --- |
| score | Final score | ✓ |
| rrf_score | Retrieval fusion score | ✗ |
| rerank_score | Cross-encoder score | ✗ |
| activation_bonus | Booster contribution | ✓ |
| fts_rank | FTS branch rank | ✗ |
| entity_rank | Entity branch rank | ✗ |
| vector_rank | Vector branch rank | ✗ |
| sources | Retrieval provenance | ✗ |

The RecallHit schema is frozen as of Step 5.5. Future extensions should be introduced through ADRs rather than ad-hoc fields.

---

## 5. RecallBooster Contract

```text
RecallHit
      │
      ▼
 Booster 1
      ▼
 Booster 2
      ▼
 Booster N
      ▼
 Final RecallHit
```

- Boosters never create candidates.
- Boosters never invoke retrievers.
- Boosters never modify RRF.
- Boosters never rerank candidates.
- Boosters modify only `activation_bonus`.

`GraphActivationBooster` is the Store-backed spreading-activation booster. It
reads directed `memory_edges` between the current candidate hits and adds a
capped bonus to existing edge targets only. It does not create candidates,
invoke retrievers, modify RRF, or change any `RecallHit` field except
`activation_bonus`.

---

## 6. Design Invariants

### Invariant 1

> **Store exposes retrieval primitives only.**

### Invariant 2

> **RecallEngine is the only retrieval orchestrator.**

### Invariant 3

> **Retrievers create candidates. Boosters never create candidates.**

### Invariant 4

> **RRF fuses retrieval signals only.**

### Invariant 5

> **Boosters modify score only.**

### Invariant 6

> **Recall improvements must be benchmarked before merge.**
