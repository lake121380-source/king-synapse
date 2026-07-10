# Phase 6.1 Cognitive vs Simple Baseline Evaluation

Status: **Implementation complete; deterministic quality gate passes; independent cognitive value remains unresolved; runtime remains unauthorized.**

Phase 6.1 reuses the frozen Phase 6.0 workload to answer one attribution question:

> Does the current Margin-Guarded Cognitive policy provide value beyond simple confidence, recency, and failure heuristics?

It does not introduce a new cognitive algorithm, change any locked parameter, or connect the booster to runtime.

## Scope and fixed protocol

Dataset:

```text
320 scenarios
1,920 memories
10 categories
train / validation / test = 160 / 80 / 80
intervention-required / no-intervention = 224 / 96
```

Every scenario is written to an isolated in-memory `Store` and retrieved through the real `RecallEngine::recall_profiled` path with `k = 5`. The returned `RecallHit` ranking and score remain authoritative.

All non-retrieval comparison policies use the already frozen authority parameters:

```text
alpha     = 0.20
threshold = 0.08
```

The evaluator is:

```text
eval-only
shadow-only
baseline-authoritative
no RecallEngine modification
no candidate-generation modification
no retrieval-score mutation
no memory/schema write
no runtime booster registration
```

## Compared policies

| Policy | Signal |
| --- | --- |
| Retrieval Baseline | unchanged RecallEngine ranking |
| Confidence Only | normalized `memory.confidence` |
| Recency Only | whether `last_accessed_at` is present |
| Failure Only | `MemoryKind::Failure` plus deterministic query/content lexical overlap |
| Simple Combined | `(confidence + recency + failure) / 3` |
| Margin Guard Cognitive | unchanged `DeterministicCognitiveBoosterV0` bounded bonus normalized by `MAX_COGNITIVE_BOOSTER_BONUS` |

Simple policies do not read Cognitive Trace factors. The cognitive policy uses the existing trace evaluator and booster without formula or parameter changes.

## Factor ablation protocol

The following variants are evaluated:

```text
Full Cognitive
without temporal
without failure
without reliability
without preference
without context
```

Ablation does not copy or rewrite the booster formula. It clones the real `CognitiveCompetitionTrace`, removes exactly one `CognitiveFactorType`, and runs the unchanged `DeterministicCognitiveBoosterV0`.

## Stable result

Report:

- `crates/eval/reports/phase6_cognitive_baseline_comparison.json`

| Policy | Recall@1 | Recall@3 | MRR@5 | NDCG@5 | Intervention precision | Intervention recall | Unnecessary intervention | Catastrophic regression |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Retrieval Baseline | `0.3000` | `1.0000` | `0.6500` | `0.7417` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| Confidence Only | `0.3000` | `1.0000` | `0.6500` | `0.7417` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| Recency Only | `0.3000` | `1.0000` | `0.6500` | `0.7417` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| Failure Only | `0.3000` | `1.0000` | `0.6500` | `0.7417` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| Simple Combined | `0.3000` | `1.0000` | `0.6500` | `0.7417` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| Margin Guard Cognitive | `0.3000` | `1.0000` | `0.6500` | `0.7417` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |

Independent-value deltas:

```text
cognitive_gain_vs_best_simple_baseline            = 0.0000 MRR@5
cognitive_recall_at_1_gain_vs_best_simple_baseline = 0.0000
outcome                                             = B_cognitive_matches_best_simple
```

## Critical authority-coverage finding

The equality above must not be overinterpreted as proof that Cognitive is merely metadata aggregation.

With the parameters locked before Phase 6.1, the Phase 6.0 real RecallEngine scores produced:

```text
minimum normalized top-to-second gap = 0.101449
Margin Guard threshold                = 0.080000
scenarios with two eligible candidates = 0 / 320
competition-eligible rate              = 0.0000
```

The locked Margin Guard therefore preserved the retrieval order in every scenario for every comparison policy. Phase 6.1 successfully validates the comparison machinery and safety boundary, but the workload/authority operating point gives no policy enough authority to perform an intervention.

Accurate interpretation:

```text
Cognitive > best simple     not established
Cognitive = best simple     observed at the locked no-intervention operating point
metadata aggregation only  not established
factor attribution          unresolved
```

This is not a reason to retune `threshold` or `alpha` inside Phase 6.1. Changing them after seeing the result would violate the instruction to keep the current Cognitive policy fixed.

## Ablation result

All five removals reproduce the full Cognitive metrics exactly. No factor is reported as independently contributing.

That result is also authority-limited: because no two-candidate competition entered the guarded reranking set, the experiment cannot distinguish temporal, failure, reliability, preference, or context contributions. The report records:

```text
attribution_resolved       = false
zero_intervention_authority = true
contributing_factors       = []
```

## Decision

Phase 6.1 is classified as case B at the observed operating point:

```text
Cognitive = best simple baseline
```

However, the scientific conclusion is narrower than “Cognitive is only metadata aggregation”:

> Independent cognitive value is not demonstrated, and factor attribution is unresolved because the locked 0.08 Margin Guard admitted no two-candidate competitions on the Phase 6.0 score distribution.

Recommendation:

```text
Hermes Shadow Integration   = not recommended
Runtime authorization       = false
Production claim            = false
```

Before any Hermes shadow-integration proposal, a separate review should decide whether the next experiment is intended to validate the locked policy on a naturally near-margin workload or to study authority calibration under a new, explicitly pre-registered protocol. Phase 6.1 itself must remain frozen and must not retroactively change parameters.

## Reproduction

```bash
cargo test -p synapse-eval --test phase6_cognitive_baseline_comparison_test
python scripts/eval/phase6_cognitive_baseline_comparison.py
```

## Quality-gate semantics

A Phase 6.1 `PASS` means:

- all six requested policies ran over the same 320 real-RecallEngine candidate pools;
- all five factor-removal variants used the unchanged cognitive booster;
- rankings and metrics are deterministic;
- gain is computed against the actual best simple baseline;
- Store, RecallHit, candidate pool, schema, and runtime behavior are unchanged;
- the report preserves the no-runtime and no-production-claim boundary.

It does **not** mean:

- Cognitive provides independent value;
- Cognitive has been proven equivalent to simple metadata aggregation;
- the factors have zero value;
- the Margin Guard should be enabled in Hermes or any runtime path.
