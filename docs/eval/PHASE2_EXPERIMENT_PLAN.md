# Phase 2 Experiment Plan

Status: Draft

Baseline:

- `v0.6.0-cognitive-validation`
- Phase 1 Cognitive Memory Foundation
- Phase 1.2 Benchmark Scaling
- [RFC-013 Adaptive Memory Dynamics](../rfc/RFC-013-adaptive-memory-dynamics.md)

This document is design-only. It defines falsifiable experiments for Phase 2
Adaptive Memory Dynamics. It does not implement algorithms, change `crates/core`,
modify retrieval, modify activation, or change the Phase 1 benchmark.

## 1. Objective

Phase 1 proved the narrow claim:

> Synapse can perform auditable memory reasoning beyond retrieval-only RAG.

Phase 2 must test a harder claim:

> Synapse can regulate which memories influence decisions.

The goal of Phase 2.1 is to turn RFC-013 into small experiments that can fail in
clear ways. The first implementation should not attempt a full adaptive
cognitive architecture. It should choose one minimal regulation problem and
prove whether the approach improves memory influence without damaging the
Phase 1 baseline.

## 2. Phase 1.2 Starting Point

Current benchmark result:

```text
cases:              200
suites:             15
full_synapse_score: 0.9400
hybrid_rag:         0.5550
gain:               +0.3850
retrieval_failure:  0
reasoning_failure:  4
```

Remaining failure types:

- decision mismatch
- causal order error

Interpretation:

Retrieval is not the current bottleneck in the synthetic cognitive-memory
benchmark. The next bottleneck is memory influence regulation: which activated
memories should dominate, which should be suppressed, and when the system should
abstain because the memory evidence is insufficient.

## 3. Experiment 1: Memory Conflict Resolution

Research question:

> When two relevant memories conflict, can Synapse choose the memory that should
> influence the current decision?

Example:

```text
Memory A:
User prefers fast development.

Memory B:
Fast development caused previous failure.

Question:
Recommend an architecture for the next project.
```

Current-system observation:

- Which memory becomes dominant?
- Does the trace preserve both memories?
- Does the decision over-follow the old preference?

Future-mechanism target:

- Memory A remains visible as preference context.
- Memory B increases influence when the current context matches the failure
  scope.
- The final trace explains why speed preference was reweighted rather than
  deleted.

Metric:

```text
conflict_resolution_score
```

Scoring intent:

- high score: conflicting memories are both represented and correctly weighted
- medium score: both memories are recalled, but influence is not clearly
  regulated
- low score: the system follows one memory by similarity or recency alone

Failure modes:

- old preference dominates despite stronger failure evidence
- newer evidence always dominates even when scope does not match
- trace hides the losing memory, making regulation unauditable

## 4. Experiment 2: Temporal Influence

Research question:

> Does temporal order change memory influence correctly?

This experiment directly targets the Phase 1.2 `causal_order_error` failures.

Example:

```text
A:
User likes solution X.

B:
Solution X fails under real use.

C:
User chooses a safer strategy.

Question:
What should guide the next similar decision?
```

Expected influence movement:

```text
A influence decreases
B influence increases
C becomes current strategy evidence
```

Current-system observation:

- Does Synapse collapse the chain into the latest memory?
- Does it preserve causal order?
- Does it distinguish delayed feedback from initial preference?

Future-mechanism target:

- Old preference remains available but no longer dominates.
- Failure evidence is applied only when the current context matches.
- Strategy update is treated as a state transition, not just another memory.

Metric:

```text
temporal_reasoning_score
```

Scoring intent:

- high score: trace preserves order and influence changes in the expected
  direction
- medium score: final decision is right but temporal explanation is incomplete
- low score: order is collapsed into latest-memory or keyword matching behavior

Failure modes:

- latest memory always wins
- oldest preference remains dominant after later failure
- delayed feedback is treated as unrelated context
- partial ordering is flattened into a false linear chain

## 5. Experiment 3: Memory Suppression

Research question:

> Can Synapse suppress an incorrect or outdated memory without deleting it?

This is the highest-priority Phase 2 experiment because it directly tests
candidate thought competition.

Example:

```text
Old memory:
Solution A worked well.

New memory:
Solution A caused an incident in the current scope.

Correct behavior:
Solution A remains stored, but its current influence is suppressed.
```

Current-system observation:

- Does the old success remain dominant because it is semantically similar?
- Does governance observe the risk but fail to reduce influence?
- Is the suppressed candidate visible in the trace?

Future-mechanism target:

```text
candidate_old_success:
  state: suppressed
  reason: contradicted by scoped incident evidence

candidate_failure_memory:
  state: dominant
  reason: current context matches incident scope
```

Metric:

```text
suppression_accuracy
```

Scoring intent:

- high score: harmful/outdated memory is suppressed while still auditable
- medium score: final decision is right but suppression reason is not visible
- low score: old memory is either deleted conceptually or still dominates

Failure modes:

- suppression acts like memory deletion
- suppression blocks all exploration
- suppression is applied globally instead of scope-locally
- the trace cannot explain why a memory lost the competition

## 6. Experiment 4: Uncertainty Boundary

Research question:

> Can Synapse know when memory evidence is insufficient?

Example:

```text
Memory:
A similar project exists.

Missing:
No outcome, no root cause, no current scope match.

Correct behavior:
insufficient evidence
```

Current-system observation:

- Does Synapse force a causal trace from weak memory?
- Does keyword similarity create false confidence?
- Does the answer distinguish "relevant" from "sufficient"?

Future-mechanism target:

- The system returns an observe or insufficient-evidence state.
- Activated memories are still shown, but not promoted to decisive influence.
- The trace explains which evidence is missing.

Metric:

```text
abstention_score
```

Scoring intent:

- high score: system abstains or observes when evidence is incomplete
- medium score: system gives a cautious answer but without explicit missing
  evidence
- low score: system invents a strong trace from weak or irrelevant memory

Failure modes:

- false confidence from keyword overlap
- unsupported causal bridge
- ambiguous evidence converted into a hard recommendation
- abstention used too aggressively, suppressing valid decisions

## 7. Phase 2 Prebaseline Output

The Phase 2.1 design validation should produce a prebaseline report with this
shape before any algorithm implementation begins:

```json
{
  "version": "phase2-prebaseline",
  "phase1_baseline": "v0.6.0-cognitive-validation",
  "phase1_2_cases": 200,
  "experiments": [
    "conflict_resolution",
    "temporal_influence",
    "suppression",
    "uncertainty"
  ],
  "primary_implementation_candidate": "memory_suppression_competition",
  "implementation_status": "not_started",
  "core_mechanism_changed": false
}
```

This report should be descriptive at first. It should document existing
behavior and failure modes before introducing a new mechanism.

## 8. Recommended Phase 2 Sequence

```text
RFC-013 Adaptive Memory Dynamics
  -> Phase 2 Experiment Plan
  -> Phase 2 Prebaseline
  -> Adaptive Competition Prototype
  -> Benchmark Validation
```

The first implementation target should be:

```text
Memory Suppression / Competition
```

Reason:

Synapse's core distinction from retrieval-only RAG is not that it can store more
memories. It is that multiple activated memories can compete for influence over
the current decision. The first Phase 2 mechanism should therefore answer the
smallest useful question:

> When multiple memories are activated, which one should become dominant, which
> should be suppressed, and why?

## 9. Success Criteria

Phase 2.1 succeeds when:

- RFC-013 is decomposed into falsifiable experiments
- each experiment has a clear target metric
- each experiment has known failure modes
- no core mechanism is changed
- no benchmark is modified
- the first implementation candidate is narrowed to memory suppression and
  competition

Phase 2 implementation should not start until this experiment plan is accepted.
