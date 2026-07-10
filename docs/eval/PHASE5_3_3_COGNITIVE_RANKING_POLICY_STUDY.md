# Phase 5.3.3 Cognitive Ranking Policy Study

Status: **Frozen as controlled, evaluation-only Phase 5.3 evidence; not runtime-authorized.**

Freeze record: [Phase 5.3 Cognitive Ranking Policy Freeze](PHASE5_3_FREEZE.md).

## Research question

Phase 5.3.2 showed that a bounded cognitive bonus can move candidates, but it
also exposed a scale mismatch and an MRR regression. Phase 5.3.3 therefore asks:

> When should a cognitive signal have ranking authority?

It does not add cognitive factors, tune a production reranker, or connect a
booster to `RecallEngine`.

## Controlled hard benchmark

Dataset:

```text
crates/eval/datasets/cognitive_policy/
```

The benchmark contains 42 deterministic scenarios and 168 candidates across:

- temporal update
- failure override
- reliability conflict
- semantic trap
- preference evolution
- contradiction
- no intervention

Each fixture writes real memories to an in-memory `Store`, recalls real
`RecallHit` values, and maps generated IDs back to stable dataset labels. The
fixture then assigns an explicit deterministic baseline score before generating
the real `CognitiveCompetitionTrace`. This isolates policy behavior from FTS and
ULID tie-breaking. It is a controlled policy benchmark, not an end-to-end
retrieval benchmark.

## Policies

### Absolute Bonus

Reference behavior from Phase 5.3.2:

```text
final = baseline_score + bounded_bonus
```

### Weighted Fusion

The evaluator explicitly normalizes both channels:

```text
baseline_normalized = baseline_score / scenario_max_baseline_score
cognitive_normalized = bounded_bonus / 0.10
final = baseline_normalized * (1 - alpha)
      + cognitive_normalized * alpha
```

Evaluated values: `alpha = 0.05`, `0.10`, and `0.20`.

### Margin Guard

Candidates outside a normalized `0.08` margin from the baseline top candidate
cannot challenge the protected top band. Candidates inside the band use weighted
fusion with `alpha = 0.20`.

This policy studies conditional authority: cognitive evidence can resolve a
close competition but cannot bridge a large semantic gap.

## Metrics

- Recall@3 and MRR
- intervention precision
- intervention recall
- unnecessary intervention rate
- catastrophic regression rate
- regression rate
- changed positions and absolute rank movement
- bounded rate and determinism

A policy intervention is a top-1 change. A successful required intervention
changes top-1 to the fixture's expected candidate. A catastrophic regression
changes a baseline-correct top-1 into an incorrect top-1.

## Local decision table

| Policy | MRR delta | Intervention precision | Intervention recall | Unnecessary intervention | Catastrophic regression |
| --- | ---: | ---: | ---: | ---: | ---: |
| Absolute Bonus | +0.3571 | 0.8571 | 1.0000 | 1.0000 | 1.0000 |
| Weighted Fusion 0.05 | +0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Weighted Fusion 0.10 | +0.2143 | 1.0000 | 0.5000 | 0.0000 | 0.0000 |
| Weighted Fusion 0.20 | +0.3571 | 0.8571 | 1.0000 | 1.0000 | 1.0000 |
| Margin Guard 0.08 / 0.20 | +0.4286 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |

Interpretation:

- absolute bonus is too aggressive
- low-alpha fusion is safe but misses required interventions
- high-alpha fusion recovers required interventions but can override a clearly
  correct baseline
- the current controlled fixture favors conditional, margin-guarded authority

These values are fixture-local and deliberately do not establish production
improvement.

## Ablation

The selected evaluation policy is Margin Guard `0.08 / 0.20`.

| Ablation | MRR | Intervention recall |
| --- | ---: | ---: |
| Full cognitive | 1.0000 | 1.0000 |
| Without temporal | 0.9286 | 0.8333 |
| Without reliability | 0.9286 | 0.8333 |
| Without failure | 0.8571 | 0.6667 |
| Without preference | 0.9286 | 0.8333 |
| Without context | 1.0000 | 1.0000 |

The evaluator removes real trace factors before running the existing bounded v0
booster. It does not synthesize replacement evidence. On this fixture, failure
evidence has the largest measured contribution; context alignment adds no
measured top-1 value and should not be claimed as useful from this study.

## Safety boundary

The report records:

```text
eval_only                    = true
shadow_only                  = true
baseline_authoritative       = true
runtime_applied              = false
policy_memory_written        = false
memory_mutated               = false
ranking_mutated              = false
scores_mutated               = false
activation_changed           = false
candidate_pool_changed       = false
recall_engine_integrated     = false
production_claim_authorized  = false
```

`fixture_setup_writes = true` means the evaluator constructs an in-memory test
corpus. It does not mean the ranking policy writes memory.

## Reproduce

```powershell
$env:CARGO_PROFILE_DEV_DEBUG='0'
$env:CARGO_PROFILE_TEST_DEBUG='0'

cargo test -p synapse-eval --test phase5_cognitive_policy_test
python scripts/eval/phase5_cognitive_policy.py
```

Report:

```text
crates/eval/reports/phase5_cognitive_policy.json
```

## Decision boundary

The local study supports continued research on conditional authority, but it is
not sufficient by itself to freeze Phase 5.3.3 or start runtime A/B testing.
Phase 5.3.4 now challenges the locked policy on a disjoint held-out controlled
fixture. An independent end-to-end retrieval benchmark with ground truth not
constructed from the policy assumptions is still required before runtime work.
