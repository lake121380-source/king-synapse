# Phase 5.3.2 Deterministic Cognitive Booster v0 Shadow Ranking Experiment

Status: **Frozen — local shadow experiment complete; runtime authorization withheld**

Date: 2026-07-10

## Purpose

Phase 5.3.2 asks a narrower question than production reranking:

> Can the cognitive factors already present in the Phase 5.1 trace produce a deterministic, bounded ranking proposal over real `RecallHit` candidates?

The experiment does not replace or mutate recall ranking. It computes a second, report-only ordering and compares it with the authoritative baseline.

```text
RecallHit candidates (immutable)
        |                       |
        v                       v
baseline order          CognitiveTraceEvaluator
        |                       |
        |              DeterministicCognitiveBoosterV0
        |                       |
        +-------- compare ------+
                    |
                    v
             shadow report only
```

## Algorithm v0

Implementation:

- `crates/core/src/adaptive/cognitive_booster/deterministic_v0.rs`
- public type: `DeterministicCognitiveBoosterV0`
- stable diagnostic name: `deterministic_cognitive_booster_v0`

The v0 bonus uses only factors emitted by the real cognitive trace:

| Trace factor | Normalization ceiling | Maximum v0 budget |
| --- | ---: | ---: |
| `TemporalConfidence` | `0.15` | `0.02` |
| `Reliability` | `0.20` | `0.02` |
| `ContextAlignment` | `0.15` | `0.02` |
| `PreferenceAlignment` | `0.10` | `0.01` |
| `FailureEvidence` | `0.15` | `0.03` |
| Total | - | `0.10` |

`SemanticMatch` is intentionally excluded. Baseline recall already contains semantic retrieval evidence; Phase 5.3.2 tests whether additional cognitive factors contribute independent ranking information.

The current trace has no contradiction factor. v0 therefore does not invent a contradiction penalty or any other unsupported signal. All proposals are additive and non-negative.

## Shadow ranking contract

For reporting only:

```text
shadow_score = baseline_score + bounded_bonus
```

A copied candidate report is sorted by:

1. descending `shadow_score`
2. ascending baseline rank as the deterministic tie-breaker

The original `Vec<RecallHit>` is not sorted or modified. Positive `position_delta` means upward movement:

```text
position_delta = baseline_rank - shadow_rank
```

## Evaluation

Runner:

```bash
python scripts/eval/phase5_shadow_ranking.py
```

Report:

```text
crates/eval/reports/phase5_shadow_ranking.json
```

The four deterministic local fixtures cover failure evidence, preference alignment, playbook context, and a reliability tradeoff. Ground-truth memory IDs are captured from real `Store::write` results, candidates are produced by the real `RecallEngine`, and traces are produced by `CognitiveTraceEvaluator`.

## Local result

```text
proposal_coverage       = 1.0000
changed_positions       = 13
avg_abs_rank_delta      = 0.9474
max_abs_rank_delta      = 3
max_proposed_bonus      = 0.0848
bounded_rate            = 1.0000
determinism             = 1.0000
baseline Recall@3       = 1.0000
shadow Recall@3         = 1.0000
shadow Recall@3 delta   = +0.0000
baseline MRR            = 0.8750
shadow MRR              = 0.7500
shadow MRR delta        = -0.1250
```

The quality result is intentionally not converted into an improvement claim. On this small deterministic fixture, v0 preserves Recall@3 but reduces MRR. The experiment therefore shows that the signal can move ranking deterministically, but **does not show that the current weighting has positive ranking value**.

The high proposal coverage and observed rank movement are useful diagnostics: the absolute `0.10` interface cap is enforced, but v0 bonuses can still be large relative to the current baseline score scale. Any later calibration must address this before runtime authorization.

## Safety result

The report and tests require:

```json
{
  "runtime_applied": false,
  "memory_written": false,
  "memory_mutated": false,
  "ranking_mutated": false,
  "scores_mutated": false,
  "activation_changed": false,
  "candidate_pool_changed": false,
  "recall_engine_integrated": false,
  "production_claim_authorized": false
}
```

Additional guarantees:

- default configuration remains disabled
- only the configured candidate prefix is eligible
- every bonus is capped by configuration and the absolute `0.10` interface limit
- unknown candidates cannot enter the shadow pool
- replay produces identical proposals and shadow order
- baseline IDs, score bits, activation bits, and serialized memory remain unchanged

## Non-claims

Phase 5.3.2 does not claim:

- runtime integration
- production ranking improvement
- recall improvement
- MRR improvement
- human or LLM preference
- learned weights
- candidate generation
- memory or schema mutation
- booster authorization

## Freeze decision

Phase 5.3.2 is frozen with the following conclusions:

```text
Shadow experiment complete.
Cognitive signal affects ranking.
Positive retrieval improvement not established.
MRR regression observed.
Calibration required before further authorization.
```

The shadow experiment mechanism and its safety boundaries are valid. The negative MRR delta is retained as an algorithm result rather than hidden or optimized away. Baseline recall remains authoritative, and runtime authorization is withheld.

## Next stage boundary

Phase 5.3.3 is a **Cognitive Score Calibration Study**, not runtime A/B activation. It may compare proportional bonuses, normalized score blending, tie-break-only policies, and bounded cognitive weights such as `0.01`, `0.02`, `0.05`, `0.10`, and `0.20`.

It must continue to report Recall@K, MRR, rank movement, and regression rate in shadow mode. It may not activate the booster in runtime without a separate authorization decision.

