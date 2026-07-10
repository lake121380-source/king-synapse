# Phase 6.2 Recall Score Distribution Study

Status: **Implementation complete; deterministic distribution gate passes; no threshold was selected or changed; Hermes and runtime remain unauthorized.**

Phase 6.1 found that the locked Margin Guard never opened on the frozen Phase 6.0 workload. Phase 6.2 therefore stops policy comparison and asks a narrower descriptive question:

> What does the real RecallEngine score and score-gap distribution look like, and how much natural competition coverage do fixed candidate margins provide?

This phase does not attempt to improve retrieval or prove Cognitive value.

## Fixed scope

Phase 6.2 re-runs the frozen Phase 6.0 workload through the existing evaluator:

```text
320 real RecallEngine queries
1,920 written memories
1,600 returned candidates (k = 5)
10 balanced categories
train / validation / test = 160 / 80 / 80
```

Locked inputs remain unchanged:

```text
Margin Guard threshold = 0.08
policy alpha           = 0.20
RecallEngine           = unchanged
CognitiveBooster       = unchanged and not executed
candidate generation   = unchanged
ranking                = unchanged
```

The Phase 6.2 evaluator consumes the `RecallHit.score` values produced by `Phase6MemoryIntelligenceBenchmarkEvaluator`. It does not reproduce retrieval logic and does not supply artificial scores.

## Gap definitions

The report keeps raw and normalized quantities separate:

```text
raw adjacent gap
    = score(rank_i) - score(rank_i+1)

adjacent normalized gap
    = 1 - score(rank_i+1) / score(rank_i)

top-relative gap
    = 1 - score(candidate) / score(top1)
```

The existing Margin Guard uses the top-relative scale. A scenario is competition-eligible only when at least two candidates have a top-relative gap less than or equal to the observed threshold.

## Candidate and score distribution

Every query returned exactly five candidates:

```text
candidate-count histogram = { 5: 320 }
mean candidate count      = 5.0
```

Across all 1,600 returned candidates:

| Statistic | Recall score |
| --- | ---: |
| Minimum | `0.007624` |
| Mean | `0.011187` |
| Median / P50 | `0.010413` |
| P90 | `0.014470` |
| P95 | `0.015744` |
| P99 | `0.015905` |
| Maximum | `0.015905` |

These raw scores are descriptive only. Margin coverage is calculated on the existing top-relative normalized scale, not by comparing `0.08` directly with raw score differences.

## Top-1 to Top-2 distribution

| Statistic | Raw gap | Top-relative normalized gap |
| --- | ---: | ---: |
| Minimum | `0.001460` | `0.101449` |
| Mean | `0.003020` | `0.197452` |
| Median / P50 | `0.001989` | `0.134464` |
| P90 | `0.005492` | `0.345316` |
| P95 | `0.005492` | `0.345316` |
| P99 | `0.005492` | `0.345316` |
| Maximum | `0.005492` | `0.345316` |

The central Phase 6.1 observation is now explained by the distribution baseline:

```text
locked threshold                       = 0.080000
minimum observed Top1-Top2 normalized gap = 0.101449
0.080000 < 0.101449
```

Therefore the fixed guard is below every observed natural Top1/Top2 competition gap in this workload.

## Adjacent candidate gaps

| Pair | Raw gap mean | Adjacent normalized median | Top-relative median of lower rank |
| --- | ---: | ---: | ---: |
| Top1?Top2 | `0.003020` | `0.134464` | `0.134464` |
| Top2?Top3 | `0.001511` | `0.155800` | `0.284537` |
| Top3?Top4 | `0.000659` | `0.070696` | `0.313496` |
| Top4?Top5 | `0.001070` | `0.099129` | `0.391212` |

This shows why raw absolute gaps alone are not sufficient for guard design: later adjacent candidates can have small raw differences while remaining far outside a top-relative authority window.

## Descriptive margin coverage

The requested thresholds were evaluated without selecting or authorizing any of them:

| Top-relative threshold | Eligible scenarios | Eligible rate |
| ---: | ---: | ---: |
| `0.01` | `0 / 320` | `0.0000` |
| `0.02` | `0 / 320` | `0.0000` |
| `0.05` | `0 / 320` | `0.0000` |
| `0.08` | `0 / 320` | `0.0000` |
| `0.10` | `0 / 320` | `0.0000` |
| `0.15` | `192 / 320` | `0.6000` |
| `0.20` | `192 / 320` | `0.6000` |

The jump at `0.15` is an observed property of this controlled benchmark. It is **not** authorization to change the production or experimental threshold to `0.15`. Selecting a value after observing this table would turn the same dataset into a tuning set.

## What Phase 6.2 proves

Phase 6.2 establishes that:

1. the Phase 6.1 zero-intervention result is caused by authority coverage, not by an executed Cognitive policy losing to simple baselines;
2. the locked `0.08` threshold is below the minimum observed Top1/Top2 normalized gap on this frozen workload;
3. candidate-score and margin-coverage statistics can be reproduced without changing retrieval or ranking;
4. a future Margin Guard study must pre-register its authority target and validate it on a separate holdout or real shadow distribution.

Phase 6.2 does **not** prove that:

```text
Cognitive works
Cognitive fails
0.15 is the correct threshold
60% intervention is desirable
Hermes integration is ready
runtime ranking should change
```

## Safety boundary

The report records:

```text
eval_only                    = true
distribution_study_only      = true
real_recall_engine_used      = true
recall_engine_modified       = false
cognitive_booster_modified   = false
cognitive_algorithm_executed = false
threshold_modified           = false
alpha_modified               = false
threshold_selected_from_results = false
ranking_modified             = false
retrieval_scores_mutated     = false
memory_written               = false
memory_mutated               = false
runtime_applied              = false
hermes_integration_performed = false
runtime_authorization        = false
production_claim_authorized  = false
```

`PASS` means that the statistics, dataset shape, score ordering, determinism, threshold coverage, and isolation checks passed. It is not an algorithm-quality gate.

## Artifacts

```text
crates/eval/src/phase6_recall_score_distribution.rs
crates/eval/src/bin/phase6_recall_score_distribution.rs
crates/eval/tests/phase6_recall_score_distribution_test.rs
scripts/eval/phase6_recall_score_distribution.py
crates/eval/reports/phase6_recall_score_distribution.json
```

Run:

```bash
python scripts/eval/phase6_recall_score_distribution.py
```

## Decision

```text
Recall Score Distribution Baseline      established
locked Margin Guard authority           0 / 320
threshold selection                     not performed
Margin Guard redesign                   not authorized by this phase
Cognitive value evaluation              not performed
Hermes Shadow Integration               not recommended
runtime authorization                   false
```

The next valid experiment, if pursued, is a separately specified authority-policy study with a pre-registered coverage objective and independent validation data. Phase 6.2 itself must remain a descriptive baseline.
