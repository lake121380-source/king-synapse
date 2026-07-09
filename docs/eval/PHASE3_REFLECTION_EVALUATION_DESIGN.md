# Phase 3.0.1 Reflection Learning Evaluation Design

Status: Draft

Baseline:

- [RFC-014 Reflection Learning](../rfc/RFC-014-reflection-learning.md)
- [Phase 3 Reflection Research Questions](PHASE3_REFLECTION_RESEARCH_QUESTIONS.md)
- [Phase 2 Capability Boundary](PHASE2_CAPABILITY_BOUNDARY.md)

This document is evaluation-only. It does not implement reflection algorithms,
change memory schema, modify retrieval, modify activation, modify temporal
lifecycle, modify governance, or change benchmark scoring.

## 1. Motivation

Reflection learning can easily collapse into summarization:

```text
experience
  -> LLM summary
  -> stored note
```

That is not enough for Phase 3.

Phase 3 should test whether an experience-derived lesson changes later behavior
in a scoped, auditable, and reversible way:

```text
experience
  -> reflection
  -> lesson
  -> future influence change
  -> better decision under matching context
```

The evaluation design therefore treats lesson text generation as insufficient.
The core evidence of learning is future influence change.

## 2. Learning Claim

Phase 3 uses a narrow learning claim:

> Synapse learns from experience when an experience-derived lesson changes
> future decision influence in a context where the lesson is grounded,
> scoped, and behaviorally useful.

This excludes broad claims such as consciousness, autonomous goal formation, or
human-equivalent learning.

Learning evidence must show:

- the experience deserved reflection
- the lesson is grounded in source memories
- the lesson scope matches the future task
- future behavior changes compared with a no-reflection baseline
- the behavior change is correct or useful
- later evidence can weaken or supersede the lesson

## 3. Evaluation Questions

### EQ1: What Experiences Deserve Reflection?

Does the system reflect on meaningful experiences while ignoring low-value
noise?

Positive triggers:

- repeated failure
- high-impact failure
- explicit user correction
- repeated manual repair
- governance warning
- expected outcome differs from actual outcome

Negative examples:

- routine success
- low-impact transient error
- unrelated log detail
- ambiguous one-off event with no outcome evidence

### EQ2: Is The Lesson Grounded?

Can the lesson be traced back to source memories and supporting events?

Required evidence:

```text
source episode
outcome
failure or success reason
scope
confidence
contradicting evidence if present
```

### EQ3: Is The Lesson Scoped?

Does the lesson apply only where the evidence applies?

Example:

```text
Good:
For GPU-limited model deployment, check batch size and memory before rollout.

Bad:
Always reduce batch size.
```

### EQ4: Does The Lesson Improve Future Decisions?

The core test compares:

```text
future task without reflection influence
future task with reflection influence
```

The reflection-informed path should change the decision only when the lesson
scope matches the future task.

### EQ5: Does The Lesson Have A Lifecycle?

Lessons should not become permanent unchallengeable rules.

Expected lifecycle:

```text
Lesson Candidate
  -> Strengthened by repeated support
  -> Challenged by contradiction
  -> Superseded when no longer valid
  -> Reactivated under strong later support
```

This reuses the Phase 2 memory lifecycle boundary instead of creating a separate
uncontrolled learning channel.

## 4. Experiment 1: Reflection Trigger Quality

Goal:

Measure whether reflection triggers select meaningful experiences.

Dataset shape:

```text
experience_id
event_sequence
outcome
impact
user_feedback
expected_reflection_action
```

Expected reflection actions:

```text
Reflect
Observe
Ignore
```

Metric:

```text
reflection_trigger_precision
reflection_trigger_recall
noise_reflection_rate
```

Success criteria:

- high-impact failures trigger reflection
- repeated corrections trigger reflection
- routine low-impact events are ignored
- ambiguous one-off events are observed rather than converted into lessons

Failure modes:

- every event becomes a lesson
- important failures are ignored
- observations are treated as hard reflection
- user correction is not recognized as high-signal evidence

## 5. Experiment 2: Lesson Grounding

Goal:

Measure whether generated lessons remain tied to source evidence.

Dataset shape:

```text
episode
source_memories
expected_lesson
required_evidence_ids
forbidden_evidence_ids
```

Metric:

```text
lesson_grounding_score
evidence_coverage
unsupported_claim_rate
```

Scoring intent:

- high score: lesson cites the right source memories and outcome reason
- medium score: lesson is directionally useful but missing evidence
- low score: lesson is plausible but unsupported by the episode

Failure modes:

- lesson invents a cause
- lesson cites irrelevant evidence
- lesson ignores contradiction
- lesson loses the outcome that made reflection necessary

## 6. Experiment 3: Lesson Scope Control

Goal:

Prevent local experience from becoming a global rule.

Example:

```text
Experience:
A Docker deployment failed because the local machine lacked disk space.

Good lesson:
For local Docker deployments, check disk space before image build.

Bad lesson:
Never use Docker.
```

Metric:

```text
lesson_scope_accuracy
overgeneralization_rate
undergeneralization_rate
```

Success criteria:

- lesson scope preserves the relevant environment, task, and failure reason
- lesson does not apply to unrelated contexts
- lesson is not so narrow that it can never help future tasks

Failure modes:

- broad prohibition from narrow failure
- scope ignores environment constraints
- scope ignores user preference
- lesson becomes too narrow to influence future tasks

## 7. Experiment 4: Future Influence

Goal:

Test whether reflected lessons change later behavior in the correct direction.

Comparison:

```text
Mode A:
baseline memory reasoning without lesson influence

Mode B:
memory reasoning + lesson candidate influence
```

Future task example:

```text
Past experience:
Large model deployment failed due to GPU memory pressure.

Lesson:
For GPU-limited deployment, validate memory footprint before rollout.

Future task:
Deploy another large model on a similar GPU-limited host.

Expected influence:
The lesson increases priority of resource validation before rollout.
```

Metrics:

```text
future_influence_delta
behavior_improvement_score
decision_change_correctness
scope_match_precision
```

Success criteria:

- reflection changes the decision only when scope matches
- changed decision is better than baseline
- lesson influence is visible in the trace
- irrelevant lessons are suppressed

Failure modes:

- no future behavior change
- lesson changes unrelated decisions
- lesson bypasses competition
- trace cannot explain the influence change

## 8. Experiment 5: Lesson Lifecycle

Goal:

Test whether lessons can be challenged, weakened, superseded, and reactivated
like other memory influence.

Example:

```text
Lesson:
For small services, manual deployment is safe.

Later evidence:
The service grows and manual deployment causes incident.

Expected:
Lesson becomes challenged or superseded for larger service scope.
```

Metrics:

```text
lesson_lifecycle_consistency
lesson_supersession_accuracy
lesson_reactivation_accuracy
premature_lesson_resurrection_rate
```

Success criteria:

- lessons remain auditable after losing influence
- contradictory evidence can reduce lesson influence
- strong later support can restore limited influence
- weak support does not cause unstable resurrection

Failure modes:

- lessons become permanent rules
- lessons are deleted instead of superseded
- lessons cannot recover when context changes back
- lesson lifecycle bypasses Phase 2 temporal dynamics

## 9. Proposed Report Shape

Phase 3.0.1 should eventually produce a descriptive prebaseline report:

```json
{
  "version": "phase3-reflection-eval-design",
  "implementation_status": "not_started",
  "mechanism_changed": false,
  "experiments": [
    "reflection_trigger_quality",
    "lesson_grounding",
    "lesson_scope_control",
    "future_influence",
    "lesson_lifecycle"
  ],
  "primary_claim": "learning is measured as future influence change, not lesson text generation"
}
```

This report is a future artifact. This document defines the evaluation design
only.

## 10. Non Goals

Phase 3.0.1 does not:

- implement reflection
- implement lesson extraction
- implement playbook formation
- modify memory schema
- modify retrieval
- modify activation
- modify temporal lifecycle
- modify governance
- modify benchmark scoring
- claim autonomous learning
- claim consciousness or AGI

## 11. Success Criteria

Phase 3.0.1 succeeds when:

> Reflection learning is measurable as grounded, scoped, future influence
> change rather than lesson text generation.

Completion criteria:

- learning claim is defined narrowly
- reflection trigger evaluation is specified
- lesson grounding evaluation is specified
- lesson scope evaluation is specified
- future influence evaluation is specified
- lesson lifecycle evaluation is specified
- no core mechanism is changed
- next implementation step is constrained to observation before learning

Recommended next phase:

```text
Phase 3.1 Reflection Observation
```

Phase 3.1 should observe and report reflection traces before creating any
persistent playbook or modifying future influence.
