# Edge Hypothesis Pool — Design Document (v0.2)

## First Principle

> Memory should not only remember the past—it should reorganize itself through experience.

> Edge is not the result of reasoning. Edge is the sediment of experience.

Edge is not a static property of the graph. Edge is a first-class citizen of
the memory ecology, with its own lifecycle: candidate -> observed -> confirmed
-> strengthened -> forgotten.

## What This Is

An "immune system for edges." Its job is not to generate more connections,
but to ensure only trustworthy connections survive into long-term memory.

The core question has shifted from "how do we connect more memories?" to
"how do we keep only the connections worth believing?"

## Problem This Solves

Phase 1 proved that entity-shared edges produce a 96.7% dense graph with zero
discrimination. The root cause is not "entity extraction is too coarse" — it is
that edges created from surface-level feature matching have no semantic
meaning and no validation mechanism.

The fix is not better entity extraction. The fix is a fundamentally different
edge creation mechanism: **reasoning proposes, experience disposes.**

## Core Mechanism

```
Retrieval returns top-K memories
        |
        v
Proposer examines (query, top-K) and proposes hypotheses:
  "Memory A explains Memory B in the context of this query"
  "Memory C conflicts_with Memory D"
        |
        v
Hypotheses enter Edge Hypothesis Pool with initial confidence
        |
        v
... time passes, more queries arrive ...
        |
        v
Same hypothesis re-proposed in DIFFERENT context (diversity check)
        |
        v  confidence += f(frequency, diversity, utility)
... repeated across N independent interactions ...
        |
        v
confidence crosses threshold AND diversity >= minimum AND utility validated
        |
        v
Hypothesis graduates to Confirmed Edge in memory_edges
        |
        v
GraphActivationBooster propagates along meaningful edges
```

## Confidence Model (Revised — Not Just Frequency)

A hypothesis's confidence is NOT a counter. It is a composite of three signals:

### 1. Frequency

How many times has this hypothesis been (re-)proposed across independent
retrieval events?

- Necessary but not sufficient.
- Alone, frequency produces spurious correlations (e.g., "likes Rust" and
  "bought keyboard" co-activate every day just because the user opens the
  app every day).

### 2. Context Diversity

Are the re-proposals coming from genuinely different query contexts?

```
query1: "learning path"      -> proposes A predicts B
query2: "tool recommendation" -> proposes A predicts B
query3: "career planning"     -> proposes A predicts B
```

Three different contexts all producing the same hypothesis = strong signal.

```
query1: "Rust"  -> proposes A co_activates B
query2: "Rust"  -> proposes A co_activates B
query3: "Rust"  -> proposes A co_activates B
```

Same query repeated 3 times = weak signal (could be artifact).

Implementation: hash the query context (query text + retrieved context hash).
A hypothesis needs observations from at least MIN_DIVERSITY_CONTEXTS (default 3)
distinct context hashes to graduate.

### 3. Predictive Utility (Future-Looking)

Does the presence of this edge improve future retrieval?

When a hypothesis is present (A-B connected in the pool), track whether
queries that should benefit from A-B connection actually retrieve both A and
B in top-K more often than baseline.

If edge (A, B) exists as hypothesis, and subsequent queries that retrieve A
also retrieve B at a rate higher than random chance, the edge has predictive
utility.

### Composite Formula

```
confidence = w_f * normalized_frequency
           + w_d * context_diversity_score
           + w_u * predictive_utility_score
```

Default weights: w_f=0.2, w_d=0.3, w_u=0.5

Utility weighted highest because: a relation that appears often but never
helps retrieval is noise; a relation that appears rarely but consistently
improves retrieval is gold.

## Graduation Criteria

A hypothesis graduates to confirmed edge when ALL of:

- confidence >= CONFIRM_THRESHOLD (default 0.70)
- observations >= MIN_OBSERVATIONS (default 3)
- distinct_contexts >= MIN_DIVERSITY_CONTEXTS (default 3)

## Edge Lifecycle States

```
candidate     — proposed, not yet observed in different context
observed      — re-proposed in at least one different context
confirmed     — graduated to memory_edges, affects retrieval
strengthened  — confirmed and consistently showing predictive utility
forgotten     — not re-proposed for N turns, confidence decayed below floor
```

## Relation Types (Three Categories, v0.1)

Do not over-specify the cognitive language yet. Start with three categories:

### A. Association (weak, statistical)

| Relation | Meaning | Source |
|----------|---------|--------|
| co_activates | A and B frequently retrieved together | Hebbian / co-retrieval |
| related | A and B share topical similarity but no deeper relation | temporal proximity, shared context |

### B. Reasoning (inferred, semantic)

| Relation | Meaning | Source |
|----------|---------|--------|
| explains | A provides context that makes B understandable | LLM hypothesis |
| supports | A and B independently support the same conclusion | LLM hypothesis |
| predicts | A occurring makes B more likely to be relevant | LLM hypothesis |

### C. Evolution (change over time)

| Relation | Meaning | Source |
|----------|---------|--------|
| conflicts_with | A and B contain contradictory information | memory update / LLM |
| resolves | A resolves a conflict involving B | memory update |
| replaces | A supersedes B (B is outdated) | memory supersession |

## Edge Evidence Layer (New)

Every hypothesis stores not just a confidence number, but the evidence behind
it. This preserves MindMesh's explainability advantage.

### Schema: `edge_evidence`

```sql
CREATE TABLE IF NOT EXISTS edge_evidence (
    id              TEXT PRIMARY KEY,
    hypothesis_id   TEXT NOT NULL REFERENCES edge_hypotheses(id),
    query_hash      TEXT NOT NULL,         -- hash of query that produced this evidence
    query_context   TEXT NOT NULL,         -- category/tag of query context (not raw query)
    supporting_memory_ids TEXT NOT NULL,   -- comma-separated memory IDs that supported the hypothesis
    reason_summary  TEXT NOT NULL,         -- LLM or rule-generated reason (no raw content)
    observed_at     INTEGER NOT NULL
);
```

When someone asks "why does the system think A and B are related?", the system
can answer: "Because across 3 different query contexts (tool recommendation,
career planning, learning path), A and B were consistently co-retrieved and
the reasoning engine identified that A explains B."

## Schema: `edge_hypotheses` (Revised)

```sql
CREATE TABLE IF NOT EXISTS edge_hypotheses (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL REFERENCES memories(id),
    target          TEXT NOT NULL REFERENCES memories(id),
    relation        TEXT NOT NULL,          -- co_activates, explains, predicts, ...
    confidence      REAL NOT NULL DEFAULT 0.0,
    observations    INTEGER NOT NULL DEFAULT 0,
    distinct_contexts INTEGER NOT NULL DEFAULT 0,
    predictive_utility REAL NOT NULL DEFAULT 0.0,
    first_seen      INTEGER NOT NULL,
    last_seen       INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'candidate',
    -- candidate | observed | confirmed | strengthened | forgotten
    confirmed_at    INTEGER,                -- NULL until confirmed
    decayed_turns   INTEGER NOT NULL DEFAULT 0  -- turns since last re-proposal
);
```

## Implementation Phases (Revised — Rule-Based First)

### Phase 1a: Schema + Rule-Based Proposer (No LLM)

Goal: validate the lifecycle mechanism without LLM noise.

- Add `edge_hypotheses` and `edge_evidence` tables to schema
- Add Store methods: `upsert_hypothesis`, `get_hypotheses`, `confirm_hypothesis`,
  `add_evidence`, `decay_hypotheses`
- Implement `RuleBasedHypothesisProposer`:
  - Co-retrieval: if A and B both appear in top-K, propose `co_activates`
  - Temporal proximity: if A and B were written within T seconds, propose `related`
  - Same session: if A and B share a session tag, propose `related`
- Confidence starts low (0.2), boosted by re-observation in diverse contexts
- Unit tests for lifecycle transitions: candidate -> observed -> confirmed -> forgotten

Why no LLM first: if the lifecycle mechanism is broken, we need to know it's
the mechanism, not the LLM. Rule-based proposers are deterministic and
debuggable.

### Phase 1b: LLM Hypothesis Proposer

- Implement `LlmHypothesisProposer` trait
- DeepSeek-backed: given (query, top-K memories), identify cognitive relations
  (explains, supports, predicts, conflicts_with)
- Output: `Vec<EdgeHypothesis>` with initial confidence and evidence
- A/B compare: rule-based proposer vs LLM proposer — which produces more
  useful graduated edges?

### Phase 1c: Hebbian Reinforcement + Predictive Utility

- Wire hypothesis reinforcement into existing Hebbian engine
- Re-proposal in diverse context -> confidence boost (diversity-weighted)
- Co-activation without re-proposal -> small nudge
- Implement predictive utility tracking: does edge presence improve future
  retrieval of the connected memories?
- Decay: hypotheses not re-proposed for N turns lose confidence

### Phase 1d: Graduation + End-to-End Evaluation

- Graduation logic: hypothesis -> memory_edges (with cognitive relation type)
- End-to-end test: run N queries on DMR, observe:
  - How many hypotheses are proposed?
  - How many graduate?
  - Do graduated edges produce non-uniform activation bonuses?
  - Does Recall@10 change vs baseline?
  - Can the system explain why each confirmed edge exists (evidence query)?

## What Success Looks Like

1. `edge_hypotheses` has entries with varying confidence (not all saturated)
2. Context diversity filtering prevents spurious edges from graduating
3. Some hypotheses graduate with evidence-backed reasoning
4. Graduated edges produce non-uniform activation in GraphActivationBooster
5. System can answer "why does A connect to B?" with specific evidence
6. Recall impact measurable (positive or negative — both are findings)

## Design Principles

1. **Reasoning proposes, experience disposes.** LLM does not decide the graph.
   LLM proposes. Experience decides.
2. **Frequency alone is not trust.** A relation seen 10 times in the same
   context is weaker than one seen 3 times in different contexts.
3. **Every edge must be explainable.** No black-box confidence. Every
   confirmed edge has traceable evidence.
4. **The pool is an immune system, not a generator.** Its primary function is
   to prevent bad edges from entering long-term memory, not to create as many
   edges as possible.
