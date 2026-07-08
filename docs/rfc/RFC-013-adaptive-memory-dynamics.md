# RFC-013 Adaptive Memory Dynamics

Status: Draft

Phase: Phase 2 Preparation - Adaptive Cognitive Architecture

Baseline:

- `v0.6.0-cognitive-validation`
- Phase 1 Cognitive Memory Foundation
- Phase 1.2 Benchmark Scaling

This RFC is design-only. It does not implement a core algorithm, change memory
schema, modify activation, modify retrieval, or change benchmark scoring.

## 1. Motivation

Phase 1 and Phase 1.2 established that Synapse can perform auditable memory
reasoning beyond retrieval-only RAG on the Cognitive Memory Benchmark.

Current Phase 1.2 result:

```text
cases:              200
full_synapse_score: 0.9400
hybrid_rag:         0.5550
gain:               +0.3850
retrieval_failure:  0
reasoning_failure:  4
failure_types:
  - decision mismatch
  - causal order error
```

The key finding is that retrieval is no longer the bottleneck in this benchmark.
The remaining failures are about how recalled memories influence the current
decision:

- over influence from plausible but unsupported memories
- temporal ordering errors when evidence arrives in complex order
- outdated memory interference when old evidence competes with newer context

The current flow is:

```text
memory
  -> activation
  -> decision
```

That flow is useful, but it is still too static. Phase 2 should make memory
influence adaptive so that memories do not merely appear in context, but compete,
decay, reinforce, abstain, and influence decisions according to evidence quality
and temporal state.

## 2. Research Questions

RQ1: How should conflicting memories compete?

Synapse needs a principled way to compare memories that support different
decisions. Competition should consider evidence coverage, confidence, recency,
history of success or failure, and contradiction with newer memories.

RQ2: How should old and new memories interact?

New evidence should not automatically erase old memory. Instead, old memory
should remain available while its influence changes when newer evidence revises
the relevant belief state.

RQ3: How should failed experiences modify future decisions?

Failure memories should not become global prohibitions. They should modify
future influence according to root cause, scope, repetition, recovery evidence,
and whether the current context matches the failed context.

RQ4: How should the system know when memory evidence is insufficient?

Synapse needs an abstention path when the memory trace is incomplete, stale,
contradictory, or only keyword-similar. The correct behavior may be to observe,
ask for evidence, or keep competing candidates unresolved instead of producing
a confident decision.

## 3. Current Architecture

Phase 1 uses the following cognitive memory path:

```text
Memory
  |
  v
Semantic Edge
  |
  v
Activation
  |
  v
Dominant Candidate
  |
  v
Governance
  |
  v
Trace
```

Phase 2 does not replace this architecture. The Recall contract, memory schema,
activation behavior, retrieval pipeline, and Phase 1 benchmark protocol remain
unchanged unless a later implementation RFC explicitly proposes a compatible
extension.

Phase 2 focuses on the influence layer between activation and decision:

```text
Activation
  |
  v
Influence Regulation
  |
  v
Dominant / Suppressed / Rejected Candidates
```

The purpose is to regulate which activated memories should affect current
decisions and how strongly they should do so.

## 4. Proposed Direction

### A. Adaptive Memory Weight

Goal: dynamically adjust memory influence without changing the stored memory
itself.

Adaptive memory weight should consider:

- recency
- confidence
- success history
- failure history
- contradiction
- scope match
- evidence completeness
- governance uncertainty

Conceptually:

```text
memory influence =
    semantic activation
  + contextual fit
  + success reinforcement
  - failure penalty when scope matches
  - contradiction pressure
  - uncertainty pressure
```

The weight is not a memory rewrite. It is a decision-time influence estimate
that can be audited in traces.

### B. Temporal Memory Dynamics

Goal: reduce causal ordering errors by representing memory influence as a state
transition rather than a flat collection of recalled facts.

Example:

```text
old belief
  |
  v
new evidence
  |
  v
belief update
```

Temporal dynamics should model:

- old evidence that remains valid
- old evidence superseded by newer evidence
- delayed feedback that arrives after an apparent success
- partial ordering where multiple events overlap
- multiple outcomes where one action has mixed effects

This is intended to address the Phase 1.2 `causal_order_error` failures without
changing retrieval or benchmark scoring.

### C. Memory Competition and Suppression

Goal: model candidate thought competition instead of treating the strongest
retrieved memory as the automatic decision driver.

Candidate memories:

```text
A
B
C
```

Competition produces:

- dominant: currently controls the decision trace
- suppressed: relevant but lower priority or lower confidence
- rejected: misleading, outdated, unsupported, or out of scope

The design should preserve traceability:

```text
candidate A -> dominant because current context and evidence support it
candidate B -> suppressed because it is older but still relevant
candidate C -> rejected because similarity is lexical rather than causal
```

This makes the system auditable: the user should be able to see not only what
memory won, but why other plausible memories did not.

## 5. Non Goals

Phase 2 does not attempt to build:

- consciousness
- AGI
- unrestricted self modification
- memory deletion as a default regulation strategy
- replacement of the LLM
- replacement of the existing retrieval pipeline
- a new benchmark scoring formula

Phase 2 also does not grant the system open-ended authority to rewrite memory
state. Any future persistent influence mutation requires a separate RFC, tests,
rollback model, and governance boundary.

## 6. Evaluation Plan

Phase 2 should be evaluated as adaptive influence regulation, not as retrieval
improvement.

### Memory Influence Accuracy

Measures whether the memories that influence the final decision are the correct
ones for the current context.

Question:

> Did the right historical factors change the decision?

### Conflict Resolution Score

Measures whether old and new memories, contradictory preferences, policy
changes, and mixed evidence are resolved correctly.

Question:

> Did the system preserve old memory while correctly reweighting it against new
> evidence?

### Temporal Reasoning Score

Measures whether causal order, delayed feedback, partial ordering, and multiple
outcomes are represented correctly in the trace.

Question:

> Did the system avoid collapsing time into "latest memory wins" or "oldest
> memory wins"?

### Abstention Score

Measures whether Synapse avoids false confidence when memory evidence is
insufficient.

Question:

> Did the system know when to observe, ask for more evidence, or keep candidates
> unresolved?

## 7. Phase 2 Success Criteria

Phase 2 succeeds when:

> Synapse can not only retrieve memories, but adaptively regulate which memories
> influence decisions.

Minimum success criteria:

- conflict memories compete with auditable outcomes
- old and new memories interact through explicit state transitions
- failure memories influence future choices without becoming global bans
- insufficient memory evidence leads to abstention or observe states
- Phase 1 retrieval and benchmark baselines remain stable
- no unrestricted self-modification is introduced

Phase 2 implementation should begin only after this design is accepted and a
separate implementation RFC defines concrete interfaces, rollback behavior, and
evaluation gates.
