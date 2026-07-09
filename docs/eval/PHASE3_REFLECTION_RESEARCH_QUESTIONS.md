# Phase 3 Reflection Learning Research Questions

Status: Draft

Phase 2 freeze handoff:

- [Phase 2 Memory Lifecycle Final Report](PHASE2_MEMORY_LIFECYCLE_FINAL_REPORT.md)
- [Phase 2 Capability Boundary](PHASE2_CAPABILITY_BOUNDARY.md)

Phase 3 should not begin with implementation. It should begin by defining how
experience can become reusable knowledge without mixing that problem with the
completed Phase 2 memory lifecycle work.

## 1. Motivation

Phase 2 answers:

> How does memory evolve over time?

Phase 3 should answer:

> How does experience become reusable knowledge?

The target abstraction is:

```text
Experience
  -> Reflection
  -> Lesson
  -> Playbook Candidate
  -> Future Influence
```

The research question is not broad "learning." The narrower question is whether
Synapse can transform episodic evidence into auditable strategy candidates that
can influence future decisions.

## 2. Phase 3 Scope

Phase 3 should study reflection learning:

```text
episodic memory -> semantic strategy
```

Example:

```text
Experience:
Deployment failed because database permissions were missing.

Reflection:
The failure happened before runtime debugging began.

Lesson:
Permission checks should happen before deployment attempts.

Playbook candidate:
Deployment safety checklist includes database permission verification.
```

The playbook candidate should not silently overwrite memory. It should become an
auditable candidate that can compete with other memories and strategies.

## 3. Research Questions

### RQ1: What Experiences Deserve Reflection?

Not every event should create a lesson.

Candidate reflection triggers:

- repeated failure
- high impact outcome
- user correction
- contradiction between expected and actual result
- recurring manual fix
- governance warning

Failure risks:

- reflecting on low-value noise
- generating too many weak lessons
- treating one-off events as universal rules

### RQ2: How Are Facts Separated From Lessons?

Fact:

```text
Database connection failed during deployment.
```

Lesson:

```text
Check database permissions before deployment.
```

Phase 3 must avoid collapsing facts and lessons into the same memory type.
Facts describe what happened. Lessons describe reusable implications.

Failure risks:

- turning every fact into a rule
- losing the evidence behind a lesson
- making a lesson unauditable

### RQ3: When Should A Playbook Candidate Be Created?

A playbook candidate should require stronger evidence than a single weak event.

Candidate criteria:

```text
repeated pattern
+ high impact
+ confidence
+ scoped applicability
```

Failure risks:

- one failure creates a permanent rule
- playbooks become too broad
- playbooks conflict with existing user preferences
- playbooks bypass memory competition

### RQ4: How Should Strategy Influence Future Decisions?

Phase 3 output must connect back to Phase 2:

```text
new situation
  -> memory candidates
  -> playbook candidates
  -> competition
  -> decision influence
```

A playbook should influence future behavior only when scope matches. It should
remain suppressible and auditable.

Failure risks:

- playbooks dominate all similar tasks too aggressively
- old lessons are never superseded
- lessons cannot be challenged by later evidence
- strategy influence bypasses governance

## 4. Proposed Evaluation Direction

Phase 3.1 should define an evaluation plan before any algorithm work.

Candidate experiments:

### Reflection Trigger Precision

Does the system reflect on important experiences and ignore low-value noise?

Metric:

```text
reflection_trigger_precision
```

### Lesson Extraction Accuracy

Does the lesson preserve the causal reason from the episode?

Metric:

```text
lesson_extraction_accuracy
```

### Playbook Formation Quality

Does a playbook candidate require repeated or high-impact evidence?

Metric:

```text
playbook_candidate_quality
```

### Future Strategy Influence

Does the lesson influence a later matching decision without overriding unrelated
contexts?

Metric:

```text
future_strategy_influence
```

## 5. Non Goals

Phase 3 design should not claim:

- autonomous goal formation
- unrestricted self modification
- neural reinforcement learning
- consciousness
- general intelligence
- production online learning

Phase 3 should also avoid changing retrieval, activation, temporal lifecycle, or
governance unless an evaluation exposes a specific bug.

## 6. Recommended Sequence

```text
Phase 2.10
Memory Lifecycle Freeze
  -> Phase 3.0
     Reflection Learning RFC
  -> Phase 3.1
     Reflection Evaluation Design
  -> Phase 3.2
     Minimal Reflection Prototype
```

Phase 3.0 should be design-only. The first implementation should wait until the
evaluation plan defines what a successful reflection outcome looks like.
