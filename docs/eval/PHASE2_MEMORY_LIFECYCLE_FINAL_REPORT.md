# Phase 2 Memory Lifecycle Final Report

Status: Frozen

Baseline:

- `v0.6.0-cognitive-validation`
- Phase 1.2 cognitive memory benchmark v1.2
- 200 cognitive-memory cases

Phase 2 scope:

> How should memories compete, evolve, lose influence, and regain limited
> influence over time?

Phase 2 does not claim autonomous learning, goal formation, consciousness, AGI,
or production readiness. It freezes a narrower research result: Synapse now has
a minimal memory lifecycle engine that can regulate memory influence without
deleting historical memory.

## 1. Motivation

Phase 1 showed that Synapse can perform auditable memory reasoning beyond
retrieval-only RAG. The remaining bottleneck was not whether relevant memories
could be found. Phase 1.2 recorded zero retrieval failures and four reasoning
failures.

Phase 2 therefore shifted the research question from retrieval to influence:

```text
Which memories should influence the current decision?
Which memories should be suppressed?
When should old influence become historical?
When should historical influence re-enter competition?
```

The goal was to make memory dynamic without turning memory into an opaque
rewriting system. Old memories must remain auditable even when their current
influence changes.

## 2. Architecture

Phase 2 freezes this lifecycle shape:

```text
Memory
  -> Activation
  -> Competition
  -> Temporal State
  -> Supersession / Reactivation
  -> Auditable Influence Trace
```

The lifecycle states remain intentionally minimal:

```text
Active
  -> Challenged
  -> Superseded
  -> Challenged
```

State meaning:

- `Active`: historically valid and currently influential.
- `Challenged`: still available, but later evidence has reduced confidence in
  its current influence.
- `Superseded`: preserved as history, but no longer dominant for matching future
  decisions.
- `Superseded -> Challenged`: repeated support can restore limited influence,
  but not full active dominance.

The current model tracks two pressures:

```text
supersession_pressure
  = evidence that the current world is displacing the memory

reactivation_pressure
  = evidence that the current world is supporting a superseded memory again
```

## 3. Implemented Components

### Phase 2.2 Memory Competition

Introduced candidate competition over activated memories:

```text
Dominant
Suppressed
Rejected
```

Competition regulates influence with activation, confidence, temporal, and
consistency factors. It preserves losing candidates in the decision path.

### Phase 2.3 Competition Evaluation

Evaluated competition on the unchanged 200-case benchmark:

```text
synapse:              0.9400
synapse+competition:  0.9431
suppression_correctness: 1.0000
influence_shift:          0.3991
```

The aggregate score moved only slightly because the benchmark had few remaining
conflict-heavy cases, but the known conflict subset showed correct influence
suppression.

### Phase 2.5 Temporal Transition

Introduced temporal state for memory influence:

```text
Active -> Challenged -> Superseded
```

The memory remains stored. Only future influence changes.

### Phase 2.6 Temporal Influence Evaluation

Connected temporal transition to evaluation:

```text
synapse+competition:           0.9431
synapse+temporal+competition:  0.9508
temporal_update_accuracy:      1.0000
historical_preservation:       1.0000
causal_transition_accuracy:    1.0000
obsolete_memory_detection:     0.5686
```

The result exposed a clear gap: memories entered `Challenged`, but many did not
advance into `Superseded`.

### Phase 2.7 Temporal Supersession

Added displacement pressure for `Challenged -> Superseded`.

Updated evaluation:

```text
synapse+temporal+competition: 0.9509
obsolete_memory_detection:    0.9216
obsolete errors:              51 -> 4
pass:                         true
```

This made old-but-invalid influence exit current dominance without deleting the
old memory.

### Phase 2.8 Temporal Stress Evaluation

Stress-tested the supersession mechanism:

```text
oscillation_resistance:         1.0000
delayed_contradiction_handling: 1.0000
false_contradiction_restraint:  1.0000
memory_recovery_signal:         1.0000
historical_preservation:        1.0000
stability_score:                1.0000
state_recovery:                 0.0000
```

Interpretation:

- weak recovery evidence produces a recovery signal
- weak recovery evidence does not trigger state recovery
- no oscillation, premature forgetting, or historical deletion was observed

### Phase 2.9 Temporal Reactivation

Added `reactivation_pressure` so repeated supporting evidence can restore a
superseded memory to limited influence:

```text
Superseded -> Challenged
```

Unit validation:

```text
weak support does not resurrect
strong support reactivates to Challenged
reactivated influence remains partial
counterevidence decays reactivation pressure
```

## 4. Evaluation Results

Primary benchmark and stress outputs:

- `crates/eval/reports/phase2-competition-eval.json`
- `crates/eval/reports/phase2-temporal-influence-eval.json`
- `crates/eval/reports/phase2-temporal-stress-eval.json`

Targeted validation used:

```text
cargo test -p synapse-core --test temporal_memory_transition_test -j 1
cargo test -p synapse-core --test temporal_supersession_test -j 1
cargo test -p synapse-core --test temporal_reactivation_test -j 1
cargo test -p synapse-eval --test phase2_temporal_stress_eval_test -j 1
python scripts/eval/phase2_temporal_stress_eval.py
```

The important Phase 2 result is not a large aggregate score increase. It is the
existence of a tested lifecycle path:

```text
memory can compete
memory can lose current influence
memory remains stored after losing influence
memory can regain limited influence under strong support
weak recovery evidence does not create instability
```

## 5. Key Findings

### Retrieval Was Not The Bottleneck

Phase 1.2 found zero retrieval failures in the synthetic cognitive-memory
benchmark. Phase 2 improvements therefore focused on influence regulation.

### Influence Can Change Without Deletion

Superseded memory remains stored. This is the core distinction from deletion or
naive overwrite.

### Supersession And Reactivation Are Different Pressures

A memory can be displaced by contradiction and later supported again. Treating
these as separate pressures avoids a single confidence score that destroys
historical nuance.

### Stability Matters More Than Immediate Recovery

Phase 2.8 preserving `state_recovery = 0.0000` is intentional for weak recovery
stress. Strong recovery is validated separately in Phase 2.9 so that the system
does not oscillate from minor evidence.

## 6. Limitations

Phase 2 does not implement:

- autonomous reflection
- lesson extraction
- playbook synthesis
- self-directed goal formation
- unrestricted self modification
- neural temporal models
- production online learning

Current limitations:

- Reactivation returns to `Challenged`, not full `Active`.
- Reactivation thresholds are deterministic and rule-based.
- Temporal dynamics are evaluated with synthetic and deterministic cases.
- Memory lifecycle changes do not yet create new semantic strategies.
- Phase 3 must define how experience becomes reusable knowledge.

## 7. Future Research

Phase 2 answers:

> How does memory evolve?

Phase 3 should answer:

> How does experience become reusable knowledge?

The next phase should study the path:

```text
Experience
  -> Reflection
  -> Lesson
  -> Playbook Candidate
  -> Future Influence
```

Phase 3 should begin with design and evaluation planning before algorithm work.
The first research goal is not broad "learning"; it is the narrower question of
how episodic experience can produce auditable, reusable strategy.
