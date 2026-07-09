# RFC-014 Reflection Learning

Status: Draft

Phase: Phase 3.0 - Reflection Learning Design

Baseline:

- Phase 1 Cognitive Memory Foundation
- Phase 1.2 Cognitive Memory Benchmark Scaling
- Phase 2.10 Memory Lifecycle Freeze
- [Phase 2 Memory Lifecycle Final Report](../eval/PHASE2_MEMORY_LIFECYCLE_FINAL_REPORT.md)
- [Phase 2 Capability Boundary](../eval/PHASE2_CAPABILITY_BOUNDARY.md)
- [Phase 3 Reflection Research Questions](../eval/PHASE3_REFLECTION_RESEARCH_QUESTIONS.md)

This RFC is design-only. It does not implement a core algorithm, modify memory
schema, modify retrieval, modify activation, modify governance, or change
benchmark scoring.

## 1. Motivation

Phase 2 froze a memory lifecycle engine:

```text
Memory
  -> Competition
  -> Temporal Update
  -> Supersession
  -> Reactivation
```

That answers:

> How does memory evolve?

Phase 3 begins a different question:

> How does experience become reusable knowledge?

The difference matters. An episodic memory records what happened. Reflection
learning tries to extract what should be reused later.

Example:

```text
Experience:
Deployment failed because database permissions were missing.

Potential lesson:
Check database permissions before deployment.

Potential playbook:
Deployment safety checklist includes database permission verification.
```

The goal is not to make Synapse generate arbitrary rules. The goal is to
produce auditable strategy candidates only when evidence justifies them, and to
make those candidates compete with ordinary memories rather than bypassing the
memory lifecycle.

## 2. Research Questions

### RQ1: What Experiences Deserve Reflection?

Not every event should become a lesson.

Candidate reflection triggers:

- repeated failure
- high-impact outcome
- explicit user correction
- mismatch between expected and actual result
- repeated manual fix
- governance warning
- recurring contradiction across similar tasks

Open problem:

> How can Synapse avoid reflecting on noise while still catching important
> failure patterns early?

### RQ2: How Are Facts Separated From Lessons?

Fact:

```text
The deployment failed because the database user lacked write permission.
```

Lesson:

```text
Before deployment, verify database write permissions.
```

Facts preserve evidence. Lessons summarize future-use implications.

Open problem:

> How can a lesson remain grounded in source memories so that it is auditable
> and reversible?

### RQ3: When Should A Playbook Candidate Be Created?

A playbook candidate is stronger than a lesson. It suggests a reusable action
pattern.

Candidate criteria:

```text
repeated pattern
+ high impact
+ scoped applicability
+ evidence confidence
+ no unresolved contradiction
```

Open problem:

> How much evidence is enough before a lesson becomes a playbook candidate?

### RQ4: How Should Reflected Strategy Influence Future Decisions?

Phase 3 output must connect back to Phase 2:

```text
new situation
  -> memory candidates
  -> lesson candidates
  -> playbook candidates
  -> competition
  -> decision influence
```

A strategy candidate should be suppressible, supersedable, and reactivatable
like other memory influence.

Open problem:

> How can reflected strategy affect future behavior without becoming an
> unchallengeable rule?

## 3. Current Architecture

The current cognitive memory path is:

```text
Memory Storage
  -> Retrieval
  -> Activation
  -> Competition
  -> Temporal Lifecycle
  -> Governance
  -> Trace
```

Phase 3 should add reflection after experience, not inside retrieval:

```text
Experience
  -> Reflection Candidate
  -> Lesson Candidate
  -> Playbook Candidate
  -> Future Influence Candidate
```

The output of reflection should enter future competition. It should not bypass
competition, governance, or temporal lifecycle rules.

## 4. Proposed Direction

### A. Reflection Trigger

Goal:

Determine whether an experience is worth reflection.

Candidate inputs:

- outcome severity
- failure repetition
- user correction
- confidence mismatch
- governance warning
- similarity to prior incidents
- current uncertainty

Candidate output:

```text
Reflect
Observe
Ignore
```

Interpretation:

- `Reflect`: enough signal exists to produce a lesson candidate.
- `Observe`: event is notable but evidence is not yet sufficient.
- `Ignore`: low-value noise.

### B. Lesson Candidate

Goal:

Extract a scoped implication from one or more episodes.

A lesson candidate should include:

```text
lesson_id
source_memory_ids
claim
scope
confidence
evidence_summary
contradictions
```

The lesson is not a fact replacement. It is a future-use hypothesis grounded in
episodes.

### C. Playbook Candidate

Goal:

Promote stable lessons into reusable strategy candidates.

Promotion should require:

- repeated evidence or high-impact evidence
- clear scope
- no unresolved contradiction
- enough confidence to influence future decisions

Example:

```text
lesson:
Check database write permission before deployment.

playbook candidate:
Deployment safety checklist:
1. verify database permissions
2. verify migration user scope
3. verify rollback path
```

### D. Future Influence Integration

Goal:

Make lessons and playbooks influence future decisions through existing
competition and lifecycle surfaces.

Expected flow:

```text
query / task
  -> ordinary memory candidates
  -> lesson candidates
  -> playbook candidates
  -> competition
  -> dominant / suppressed / rejected
```

The trace should show:

- which experience produced the lesson
- why the lesson applies to the current context
- why other strategies were suppressed or rejected
- whether governance considered the strategy too strong

## 5. Non Goals

Phase 3.0 does not attempt:

- autonomous goal formation
- unrestricted self modification
- consciousness
- AGI
- neural reinforcement learning
- production online learning
- replacing retrieval
- replacing temporal lifecycle
- replacing governance
- generating permanent rules from single low-impact events

Phase 3.0 also does not implement the mechanism. It defines the research
surface and the minimum design boundary for later evaluation.

## 6. Evaluation Plan

Phase 3 should be evaluated as reflection quality, not as retrieval recall.

### Reflection Trigger Precision

Question:

> Did Synapse reflect on experiences that deserved reflection while ignoring
> low-value noise?

Metric:

```text
reflection_trigger_precision
```

### Lesson Extraction Accuracy

Question:

> Did the lesson preserve the causal reason from the source episode?

Metric:

```text
lesson_extraction_accuracy
```

### Evidence Grounding Score

Question:

> Can the lesson be traced back to the source memories that justify it?

Metric:

```text
lesson_grounding_score
```

### Playbook Candidate Quality

Question:

> Did playbook formation require enough evidence, scope, and confidence?

Metric:

```text
playbook_candidate_quality
```

### Future Strategy Influence

Question:

> Did the reflected strategy influence later matching decisions without
> overgeneralizing to unrelated contexts?

Metric:

```text
future_strategy_influence
```

### Overgeneralization Rate

Question:

> Did the system turn narrow lessons into broad rules?

Metric:

```text
overgeneralization_rate
```

## 7. Phase 3 Success Criteria

Phase 3 succeeds when:

> Synapse can transform selected experiences into auditable lesson and playbook
> candidates that influence future decisions through the existing competition
> and lifecycle architecture.

Minimum success criteria:

- important experiences trigger reflection
- low-value events do not create lessons
- lessons remain grounded in source memories
- playbooks require repeated or high-impact evidence
- reflected strategy is scoped and suppressible
- future influence is auditable
- Phase 2 memory lifecycle guarantees remain stable

Phase 3 implementation should not begin until a separate experiment plan defines
datasets, failure modes, metrics, and acceptance gates.
