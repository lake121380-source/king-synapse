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

The FTS retriever still receives a deterministic Store-level `MATCH`
expression, not an interpreted semantic query. As of ADR-006, `RecallEngine`
may add a small CJK technical query-expansion dictionary before calling Store
FTS so Chinese phrases such as "维度约束" and "前缀记忆" can bridge to
existing English/code tokens like `VEC_DIM`, `embedding`, `prefix`, `query`,
and `passage`.

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
capped bonus to existing edge targets only. It can spread activation for
multiple decayed steps inside the already retrieved candidate pool, modeling
low-strength hidden influence without surfacing new memories by itself. It does
not create candidates, invoke retrievers, modify RRF, or change any `RecallHit`
field except `activation_bonus`.

`LatentActivationProbe` is a read-only inspection tool, not a booster. It starts
from one or more memory ids, walks directed `memory_edges`, and returns hidden
multi-step activations with path explanations. Optional state and goal terms
act as capped modulation, making matches to the current human/agent context
slightly stronger while preserving the explanation trail. Because it does not
produce `RecallHit`s or run inside `RecallEngine`, it can inspect
candidate-set-external background influence without changing recall rankings.

`QueryLatentActivationProbe` composes the frozen recall pipeline with latent
inspection: it recalls visible seed memories for a query, then probes hidden
activation from those seed ids. It returns a separate report containing
`seeds`, `activations`, and the final latent context. Optional auto-context
derives extra state and goal terms from the query text. It does not add fields
to `RecallHit`, change `RecallEngine` scoring, or feed latent activations back
into recall.

`LatentActivationBooster` is the optional recall-time version of the same
latent activation model. When explicitly enabled, it takes the top visible
recall hits as seed memories, walks directed edges that may pass through
candidate-set-external memories, and adds the resulting activation only to
memories already present in the candidate list. It still obeys the booster
contract: no new `RecallHit`s, no retriever calls, no RRF changes, and no field
mutation except `activation_bonus`.

`synapse_eval::cognitive_chain_recall_report()` provides the first regression
benchmark for this inspection path. It models Chinese cognitive chains where
visible query text finds a seed memory and latent activation should surface a
connected hidden influence, such as "forgot water -> bad mood -> commute
attention risk". The benchmark is deliberately separate from `RecallEngine`
ranking metrics because latent hits are explanations, not `RecallHit`s.

`CognitiveTraceProbe` builds on the same separation. It combines visible recall,
latent activation, and state/goal context into a report that names the dominant
candidate and suppressed alternatives. The probe itself is inspection-only and
does not change recall ranking or `RecallHit`; the CLI/MCP trace surfaces may
explicitly run post-report Hebbian reinforcement to learn visible seed ->
dominant hidden influence edges for future activation.

`synapse_eval::cognitive_trace_dominance_report()` verifies that the expected
hidden influence becomes the dominant trace candidate. `trace_reinforcement`
then verifies that explicit post-trace reinforcement persists the expected
visible-to-hidden associative edges through the Hebbian -> StoreMutation ->
SQLite path.

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
