# Edge Hypothesis Pool — Design Document

## First Principle

> Memory should not only remember the past—it should reorganize itself through experience.

Edge is not a static property of the graph. Edge is a first-class citizen of
the memory ecology, with its own lifecycle: candidate → observed → confirmed →
strengthened → forgotten.

## Problem This Solves

Phase 1 proved that entity-shared edges produce a 96.7% dense graph with zero
discrimination. The root cause is not "entity extraction is too coarse" — it is
that **edges created from surface-level feature matching have no semantic
meaning**.

The fix is not better entity extraction. The fix is a fundamentally different
edge creation mechanism: **reasoning proposes, experience disposes.**

## Core Mechanism

```
Retrieval returns top-K memories
        ↓
LLM examines (query, top-K) and proposes hypotheses:
  "Memory A explains Memory B in the context of this query"
  "Memory C conflicts_with Memory D"
        ↓
Hypotheses enter Edge Hypothesis Pool with confidence = initial (e.g. 0.3)
        ↓
... time passes, more queries arrive ...
        ↓
Same hypothesis re-proposed in different context
        ↓ confidence += delta (Hebbian reinforcement)
... repeated across N independent interactions ...
        ↓
confidence crosses threshold (e.g. 0.85)
        ↓
Hypothesis graduates to Confirmed Edge in memory_edges
        ↓
GraphActivationBooster now propagates along meaningful edges
```

## What Makes This Different From LLM Graph Construction

| Aspect | Naive LLM Graph | Edge Hypothesis Pool |
|--------|----------------|---------------------|
| Who creates edges | LLM, immediately | Experience, over time |
| Trust model | Trust first observation | Trust only repeated observations |
| Failure mode | Hallucinated graph (too dense, too fake) | Sparse but trustworthy graph |
| Analogy | Knowledge graph | Memory ecology |

## Edge Lifecycle States

```
candidate     — proposed by LLM, not yet observed twice
observed      — re-proposed at least once in different context
confirmed     — confidence crossed threshold, written to memory_edges
strengthened  — confirmed and repeatedly co-activated in retrieval
forgotten     — not re-proposed for N turns, confidence decays below floor
```

## Relation Types (Cognitive, Not Ontological)

These describe cognitive processes between memories, not factual relationships:

- `explains` — A provides context that makes B understandable
- `predicts` — A occurring makes B more likely to be relevant
- `conflicts_with` — A and B contain contradictory information
- `resolves` — A resolves a conflict involving B
- `reinforces` — A and B independently support the same conclusion
- `co_activates` — A and B are frequently retrieved together (statistical, Hebbian)

## Schema Extension

### New table: `edge_hypotheses`

```sql
CREATE TABLE IF NOT EXISTS edge_hypotheses (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL REFERENCES memories(id),
    target      TEXT NOT NULL REFERENCES memories(id),
    relation    TEXT NOT NULL,          -- explains, predicts, conflicts_with, ...
    confidence  REAL NOT NULL DEFAULT 0.0,
    observations INTEGER NOT NULL DEFAULT 0,
    first_seen  INTEGER NOT NULL,
    last_seen   INTEGER NOT NULL,
    context_hashes TEXT NOT NULL DEFAULT '',  -- hash of query contexts that re-proposed this
    status      TEXT NOT NULL DEFAULT 'candidate'  -- candidate|observed|confirmed|strengthened|forgotten
);
```

### Existing table: `memory_edges` (unchanged schema)

Confirmed hypotheses graduate here. The `edge` field already supports
arbitrary TEXT, so `explains`, `predicts`, etc. can be stored directly.

## Integration Points

### 1. Post-Retrieval Hook (new)

After `RecallEngine.recall()` returns top-K, a new `EdgeHypothesisProposer`
examines the results and generates hypotheses. This is the "reasoning proposes"
step.

```
RecallEngine.recall() → top-K hits
                          ↓
              EdgeHypothesisProposer::propose(query, hits, store)
                          ↓
              Vec<EdgeHypothesis> → upsert into edge_hypotheses
```

### 2. Hebbian Reinforcement (existing, extended)

`HebbianReinforcementEngine` already produces `EdgeUpdatePlan` from
co-occurrence events. Extend it to also reinforce matching hypotheses:

- If a hypothesis (A, B, relation) is re-proposed, increment `observations`
  and increase `confidence`
- If A and B co-activate in retrieval (both in top-K) without being
  re-proposed, small confidence nudge (statistical signal)

### 3. Graduation (new)

When `confidence >= CONFIRM_THRESHOLD` (default 0.85) and
`observations >= MIN_OBSERVATIONS` (default 3):

- Write to `memory_edges` with the cognitive relation type
- Mark hypothesis as `confirmed`

### 4. GraphActivationBooster (existing, unchanged)

Already reads `memory_edges` via `edge_weights_between`. Once confirmed
hypotheses are written, the booster automatically propagates activation
along meaningful edges. No code change needed in the booster itself.

### 5. Decay (existing Forget algorithm, extended)

Hypotheses not re-proposed for N turns decay:
- `confidence -= decay_rate` per turn
- If `confidence < FLOOR` (default 0.1), mark as `forgotten`

## Implementation Phases

### Phase 1a: Schema + Hypothesis Storage
- Add `edge_hypotheses` table to schema
- Add Store methods: `upsert_hypothesis`, `get_hypotheses`, `confirm_hypothesis`
- Unit tests for lifecycle transitions

### Phase 1b: LLM Hypothesis Proposer
- Implement `EdgeHypothesisProposer` trait
- DeepSeek-backed implementation: given (query, top-K memories), ask LLM to
  identify cognitive relations
- Output: `Vec<EdgeHypothesis>` with initial confidence

### Phase 1c: Hebbian Reinforcement Integration
- Wire hypothesis reinforcement into existing Hebbian engine
- Re-proposal → confidence boost
- Co-activation without re-proposal → small nudge

### Phase 1d: Graduation + Activation Loop
- Graduation logic: hypothesis → memory_edges
- End-to-end test: run N queries, observe hypothesis evolution, verify
  confirmed edges appear and affect retrieval ranking

## What Success Looks Like

1. After N queries on DMR data, `edge_hypotheses` table has entries with
   varying confidence levels (not all 0.15 like Phase 1)
2. Some hypotheses graduate to `memory_edges` with cognitive relation types
3. GraphActivationBooster, when run with graduated edges, produces **non-uniform**
   activation bonuses (different hits get different bonuses)
4. Recall@10 on graduated-edge runs shows measurable difference from baseline
   (direction TBD — even a small negative result is informative)

## What Failure Looks Like (And Why That's OK)

- LLM proposes too many hypotheses → pool floods, nothing graduates
  → fix: stricter proposal prompt, higher initial bar
- LLM never re-proposes same hypothesis → nothing confirms
  → fix: lower MIN_OBSERVATIONS, or add co-activation nudge
- Graduated edges don't change recall → edges are real but irrelevant to
  retrieval task → this is a valid research finding, not a bug

## Design Principle (From Discussion)

> Edge is not the result of reasoning. Edge is the sediment of experience.

The LLM does not decide what the graph looks like. The LLM proposes.
Experience decides.
