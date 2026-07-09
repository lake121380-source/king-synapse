# Phase 2.4 Temporal Memory Dynamics Plan

## 1. Motivation

Phase 1 showed that memory can influence decisions. Phase 2.2 introduced a
minimal competition layer, and Phase 2.3 showed that competition can regulate
which memory influence wins in known conflict cases.

The remaining problem is temporal meaning. Current benchmark cases still expose
`causal_order_error`, which suggests that treating memory as static evidence is
not enough. A memory may remain historically true while its future influence
should change after later evidence arrives.

Phase 2.4 therefore studies memory as a dynamic influence state:

```text
static evidence
  -> dynamic influence state
```

The goal is not to delete old memory or rewrite history. The goal is to preserve
historical facts while allowing later events to update how much those facts
should guide future decisions.

## 2. Current Limitation

Phase 2.3 addressed competition:

```text
memory candidates
  -> competition
  -> dominant / suppressed / rejected
```

This helps answer:

> Which memory should matter more right now?

It does not fully answer:

> How did later evidence change the meaning and future influence of an earlier
> memory?

For example, an old preference can be true as a historical record while becoming
less useful as a guide after repeated failures. A past strategy can have been
successful under one environment and become obsolete after conditions change.

Phase 2.4 focuses on temporal meaning update rather than stronger ranking.

## 3. Research Experiments

### Experiment 1: Preference Revision

Test whether a past preference is preserved while its future influence is
reduced by later failure evidence.

Example:

```text
Day 1:
User prefers fast solution.

Day 30:
Fast solution caused repeated failures.

Day 60:
Ask for an architecture recommendation.
```

Expected behavior:

- The old preference remains stored and auditable.
- The repeated failure evidence reduces the old preference's decision influence.
- The final recommendation reflects the revised influence balance.

Metric:

```text
temporal_update_accuracy
```

### Experiment 2: Successful Past Strategy Expiration

Test whether a strategy that worked in the past can become less influential
after the environment changes.

Example:

```text
Day 1:
Small-team manual deployment worked well.

Day 20:
The project moved to a multi-team release process.

Day 45:
Ask for a deployment recommendation.
```

Expected behavior:

- The old success memory remains available as historical evidence.
- The system recognizes that the prior context no longer fully applies.
- The recommendation changes when the strategy is no longer valid for the new
  environment.

Metric:

```text
obsolete_memory_detection
```

### Experiment 3: Delayed Feedback Chain

Test whether the system can interpret a delayed outcome as feedback on an
earlier decision.

Example:

```text
decision
  -> outcome
  -> delayed feedback
  -> strategy update
```

Expected behavior:

- The system links feedback to the earlier decision even when intermediate
  events exist.
- The strategy update modifies future influence rather than simply adding one
  more retrieved fact.
- Future decisions reflect the causal transition.

Metric:

```text
causal_transition_accuracy
```

### Experiment 4: Contradictory Timeline

Test whether the system can handle opposite information about the same entity at
different times.

Example:

```text
Day 1:
Service A is reliable for batch jobs.

Day 30:
Service A repeatedly failed under new load.

Day 60:
Choose a service for a high-load batch pipeline.
```

Expected behavior:

- New evidence dominates when the current context matches the newer condition.
- Old evidence is suppressed but remains visible in the trace.
- The system avoids flattening the timeline into a contradiction-free summary.

Metric:

```text
temporal_conflict_resolution
```

## 4. Proposed Minimal Mechanism

This section is conceptual only. Phase 2.4 design does not implement the
mechanism.

Proposed memory state transition:

```text
Active
  -> Challenged
  -> Updated
  -> Superseded
```

State meanings:

- `Active`: memory is historically valid and currently influential.
- `Challenged`: later evidence questions whether the memory should still guide
  decisions.
- `Updated`: later evidence has changed the memory's future influence while the
  original memory remains historically valid.
- `Superseded`: later evidence should dominate future decisions in matching
  contexts.

The memory is not deleted. The historical record remains intact; only the
influence state changes.

## 5. Evaluation Plan

Phase 2.4 should be evaluated without changing the existing Phase 1 benchmark
scoring formula. New experiments can report additional temporal metrics beside
the existing benchmark results.

Proposed metrics:

```text
temporal_update_accuracy
obsolete_memory_detection
causal_transition_accuracy
temporal_conflict_resolution
```

Metric intent:

- `temporal_update_accuracy`: measures whether new evidence correctly modifies
  the influence of old memories.
- `obsolete_memory_detection`: measures whether old-but-invalid strategies are
  recognized without deleting their history.
- `causal_transition_accuracy`: measures whether delayed feedback is attached
  to the decision it updates.
- `temporal_conflict_resolution`: measures whether newer contradictory evidence
  dominates only when the current context justifies it.

## 6. Non Goals

Phase 2.4 does not attempt:

- neural temporal model
- reinforcement learning
- self modification
- consciousness
- memory deletion
- replacement of retrieval, activation, competition, or governance

## 7. Success Criteria

Phase 2.4 succeeds when:

> Synapse can preserve historical memories while dynamically updating their
> future influence.

The expected research claim is narrow:

```text
old memories remain auditable
later evidence changes future influence
future decisions reflect temporal transitions
```

