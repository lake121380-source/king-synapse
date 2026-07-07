# Edge Hypothesis Pool — Design Document (v0.3 — FROZEN)

## First Principle

> Memory should not only remember the past—it should reorganize itself through experience.

> Edge is not the result of reasoning. Edge is the sediment of experience.

Edge is not a static property of the graph. Edge is a first-class citizen of
the memory ecology, with its own lifecycle: candidate -> observed -> confirmed
-> strengthened -> disputed -> resolved/forgotten.

## What This Is

An immune system for edges. Its job is not to generate more connections,
but to ensure only trustworthy connections survive into long-term memory.

The core question: "how do we keep only the connections worth believing?"

## Problem This Solves

Phase 1 proved that entity-shared edges produce a 96.7% dense graph with zero
discrimination. The fix is not better entity extraction — it is a fundamentally
different edge creation mechanism: **reasoning proposes, experience disposes.**

## Core Mechanism

```
Retrieval returns top-K memories
        |
        v
EdgeHypothesisGenerator::generate(context) -> Vec<EdgeHypothesis>
        |
        v
Hypotheses enter Pool with initial confidence + evidence
        |
        v
... more queries arrive, same hypothesis re-proposed in DIFFERENT contexts ...
        |
        v  confidence = f(frequency, diversity, observed_utility)
... repeated across N independent interactions ...
        |
        v
confidence >= threshold AND diversity >= min AND observations >= min
        |
        v
Hypothesis graduates to Confirmed Edge in memory_edges
        |
        v
GraphActivationBooster propagates along meaningful edges
        |
        v
Utility observed: did the edge improve retrieval rank? (before vs after)
        |
        v
Confirmed -> Strengthened (if utility positive) or -> Disputed (if conflict found)
```

## Confidence Model

Confidence is NOT a counter. It is a composite of three observed signals:

### 1. Frequency (w=0.2)

How many times has this hypothesis been re-proposed across independent
retrieval events? Necessary but not sufficient. Alone, frequency produces
spurious correlations.

### 2. Context Diversity (w=0.3)

Are re-proposals from genuinely different query contexts?

- 3 different query contexts producing same hypothesis = strong signal
- Same query repeated 3 times = weak signal (artifact)

Implementation: hash query context. Hypothesis needs observations from at
least MIN_DIVERSITY_CONTEXTS (default 3) distinct hashes to graduate.

### 3. Predictive Utility (w=0.5) — OBSERVED, NOT PREDICTED

Does the edge improve future retrieval? We do not predict this — we observe it.

When a hypothesis exists (A-B connected), track for subsequent queries:

```rust
struct EdgeUtilityObservation {
    query_id: String,
    before_rank: usize,    // rank of B when edge absent
    after_rank: usize,     // rank of B when edge present
    before_recall: bool,   // was B in top-K without edge?
    after_recall: bool,    // is B in top-K with edge?
    rank_delta: i32,       // after_rank - before_rank (negative = improvement)
}
```

Utility score = normalized rank improvement + recall improvement.

A relation that appears often but never helps retrieval is noise.
A relation that appears rarely but consistently improves retrieval is gold.

### Composite Formula

```
confidence = 0.2 * normalized_frequency
           + 0.3 * context_diversity_score
           + 0.5 * predictive_utility_score
```

## Edge Lifecycle States (Revised — Added `disputed`)

```
candidate
    |  (first proposal)
    v
observed
    |  (re-proposed in different context, confidence rising)
    v
confirmed
    |  (confidence >= 0.70, diversity >= 3, observations >= 3)
    v
strengthened
    |  (consistently positive utility)
    |
    |  (conflict found — new evidence contradicts)
    v
disputed
    |  (re-evaluation)
    +-------> resolved (conflict resolved, edge updated or type changed)
    |
    +-------> forgotten (conflict unresolved, confidence decays below floor)
```

Why `disputed` exists: real memory is not "believe -> forget." It is
"believe -> discover conflict -> re-evaluate." When new evidence contradicts
a confirmed edge (e.g., "likes Python" -> "switched to Rust"), the edge
enters `disputed`, is re-evaluated, and either resolves (edge type changes
to `replaces` or `conflicts_with`) or is forgotten.

## Relation Types (Three Categories)

### A. Association (weak, statistical)

| Relation | Meaning | Source |
|----------|---------|--------|
| co_activates | A and B frequently retrieved together | co-retrieval |
| related | A and B share topical proximity | temporal / session |

### B. Reasoning (inferred, semantic)

| Relation | Meaning | Source |
|----------|---------|--------|
| explains | A provides context making B understandable | LLM hypothesis |
| supports | A and B independently support same conclusion | LLM hypothesis |
| predicts | A occurring makes B more likely relevant | LLM hypothesis |

### C. Evolution (change over time)

| Relation | Meaning | Source |
|----------|---------|--------|
| conflicts_with | A and B contain contradictory information | memory update / LLM |
| resolves | A resolves a conflict involving B | memory update |
| replaces | A supersedes B (B is outdated) | memory supersession |

## Edge Evidence — Not a Log, But Edge's Own Memory

Evidence is not just an audit trail. It is the edge's memory — the history of
why we believe this relation, and what has happened to it over time.

A confirmed edge can be overturned later (A supports B -> later A conflicts_with B).
If we only keep the final edge, we lose the cognitive evolution.

- `memory_edges` = what we currently believe
- `edge_evidence` = why we believe it, and what happened before

### Schema: `edge_evidence`

```sql
CREATE TABLE IF NOT EXISTS edge_evidence (
    id              TEXT PRIMARY KEY,
    hypothesis_id   TEXT NOT NULL REFERENCES edge_hypotheses(id),
    query_context_hash TEXT NOT NULL,
    query_context_tag   TEXT NOT NULL,     -- category, not raw query
    supporting_memory_ids TEXT NOT NULL,   -- comma-separated IDs
    reason_summary  TEXT NOT NULL,         -- rule or LLM reason (no raw content)
    utility_before_rank INTEGER,           -- rank before edge effect (NULL if N/A)
    utility_after_rank  INTEGER,           -- rank after edge effect
    observed_at     INTEGER NOT NULL
);
```

## Schema: `edge_hypotheses` (Revised)

```sql
CREATE TABLE IF NOT EXISTS edge_hypotheses (
    id                  TEXT PRIMARY KEY,
    source              TEXT NOT NULL REFERENCES memories(id),
    target              TEXT NOT NULL REFERENCES memories(id),
    relation            TEXT NOT NULL,
    confidence          REAL NOT NULL DEFAULT 0.0,
    observations        INTEGER NOT NULL DEFAULT 0,
    distinct_contexts   INTEGER NOT NULL DEFAULT 0,
    predictive_utility  REAL NOT NULL DEFAULT 0.0,
    first_seen          INTEGER NOT NULL,
    last_seen           INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'candidate',
    -- candidate | observed | confirmed | strengthened | disputed | forgotten
    confirmed_at        INTEGER,
    disputed_at         INTEGER,
    decayed_turns       INTEGER NOT NULL DEFAULT 0
);
```

## Proposer Abstraction

```rust
trait EdgeHypothesisGenerator {
    fn generate(&self, context: &RetrievalContext) -> Vec<EdgeHypothesis>;
}
```

Implementations (in order):
1. `RuleBasedEdgeGenerator` — co-retrieval, temporal proximity, session shared
2. `LLMEdgeGenerator` — DeepSeek-backed cognitive relation detection
3. `HybridEdgeGenerator` — combines rule + LLM, weighted by source reliability

## Implementation Phases

### Phase 1a: Minimum Closed Loop (Rule-Based, No LLM)

Goal: prove that edges can be learned like memories. NOT to prove Recall improvement.

Complete the full loop:
```
Memory -> Retrieval -> Generate hypothesis -> Store -> Update confidence
-> Graduate -> Activation uses edge -> Observe utility
```

RuleBasedEdgeGenerator rules:
- Co-retrieval: A and B both in top-K for same query -> propose `co_activates`
- Temporal proximity: A and B written within T seconds -> propose `related`

Run 1000 queries on DMR. Observe lifecycle transitions.

### Phase 1a Success Metrics (Graph Quality, NOT Recall)

1. **Edge density** — target < 5% (vs Phase 1's 96.7%)
2. **Edge diversity** — multiple relation types present, not all `co_activates`
3. **Survival curve** — what % of candidates reach confirmed?
4. **Activation differentiation** — non-uniform bonuses (A=0.8, B=0.2, C=0)
   vs Phase 1's all-saturated-to-cap

Only after these succeed do we look at Recall.

### Phase 1b: LLM Hypothesis Generator

- LLMEdgeGenerator with DeepSeek
- A/B: rule-based vs LLM — which produces more useful graduated edges?

### Phase 1c: Hebbian Reinforcement + Utility Tracking

- Re-proposal in diverse context -> confidence boost
- Utility observation: before_rank vs after_rank
- Decay: unobserved hypotheses lose confidence

### Phase 1d: Dispute Resolution + End-to-End

- Conflict detection: new evidence contradicting confirmed edge
- Dispute -> resolve or forget
- Full evaluation with all lifecycle states active

## Design Principles

1. **Reasoning proposes, experience disposes.**
2. **Frequency alone is not trust.**
3. **Utility is observed, not predicted.**
4. **Every edge must be explainable.** Evidence stream, not black-box score.
5. **The pool is an immune system, not a generator.**
6. **Edges learn like memories.** They have lifecycles, evidence, and can be overturned.
