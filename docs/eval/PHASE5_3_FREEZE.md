# Phase 5.3 Cognitive Ranking Policy Freeze

Status: **Frozen as an evaluation-only shadow policy track. Runtime authority remains withheld.**

## Frozen scope

Phase 5.3 established the safe proposal and policy boundary for cognitive ranking:

| Stage | Frozen result |
| --- | --- |
| Phase 5.3.1 | Immutable, OFF-by-default `CognitiveBooster` proposal interface. |
| Phase 5.3.2 | Deterministic shadow ranking mechanism; absolute bonus exposed score-scale regression. |
| Phase 5.3.3 | Controlled policy study favored margin-guarded conditional authority over fixed absolute bonus or unconstrained fusion. |
| Phase 5.3.4 | Locked `threshold = 0.08` and `alpha = 0.20` retained value on a disjoint controlled held-out split. |

The frozen policy hypothesis is:

> Cognitive competition may receive bounded ranking authority only when the
> baseline margin indicates candidate uncertainty.

This is not a production ranking guarantee.

## Evidence frozen with the phase

Phase 5.3.3 used 42 controlled scenarios / 168 candidates. Phase 5.3.4 used a
disjoint 30/12/21 train-validation-test split and locked parameters before the
held-out execution.

Held-out Phase 5.3.4 result:

| Policy | MRR | Intervention recall | Top-1 regression |
| --- | ---: | ---: | ---: |
| Retrieval | 0.5952 | 0.0000 | 0.0000 |
| Confidence-only | 0.7143 | 0.2941 | 0.0000 |
| Recency-only | 0.9048 | 0.7647 | 0.0000 |
| Margin Guard Cognitive | 0.9524 | 0.8824 | 0.0000 |

This supports controlled policy generalization only. The fixtures assign the
policy-study baseline scores and therefore do not establish end-to-end recall
value.

## Frozen safety boundary

The following remain invariant:

```text
baseline recall remains authoritative
runtime_applied = false
memory_written = false
memory_mutated = false
ranking_mutated = false
scores_mutated = false
activation_changed = false
candidate_pool_changed = false
RecallEngine integration = absent
runtime booster registration = absent
production claim authorization = false
```

## What the freeze does not authorize

The freeze does not authorize:

- changing `RecallEngine` default ordering;
- registering a cognitive runtime booster;
- modifying candidate generation, storage, schema, activation, or working memory;
- claiming improvement on real user-query distributions;
- treating controlled benchmark MRR as production evidence;
- further tuning `threshold` or `alpha` against Phase 5.4 outcomes.

## Exit condition

Any future runtime experiment requires independent end-to-end evidence over
real `RecallEngine` candidates and scores, comparison with simple controls, a
stable cross-run protocol, and explicit top-1 regression protection.

Phase 5.4 is the first such independent validation step. It remains shadow-only
and cannot retroactively change the frozen Phase 5.3 parameters.
