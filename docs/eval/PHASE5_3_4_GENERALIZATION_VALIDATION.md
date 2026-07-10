# Phase 5.3.4 Generalization Validation

Status: **Frozen as controlled, evaluation-only Phase 5.3 evidence; not runtime-authorized.**

Freeze record: [Phase 5.3 Cognitive Ranking Policy Freeze](PHASE5_3_FREEZE.md).

## Question

Phase 5.3.3 selected a conditional ranking policy on a controlled benchmark:

```text
margin_guard_threshold = 0.08
cognitive_alpha        = 0.20
```

Phase 5.3.4 does not tune those values. It asks whether that locked policy still
behaves safely and usefully on disjoint scenarios that were not part of policy
selection.

## Dataset split

The evaluator uses:

```text
crates/eval/datasets/cognitive_policy_generalization/
├── train/       30 scenarios / 120 candidates
├── validation/  12 scenarios / 48 candidates
└── test/        21 scenarios / 84 candidates
```

The train and validation splits freeze the 42 Phase 5.3.3 scenarios into a
30/12 development partition. The test split adds 21 held-out scenarios with new
queries, entities, wording, score scales, and conflict combinations. Scenario
IDs are disjoint, and each split records a SHA-256 dataset seal in the report.

The test set is "hidden" in the policy-selection sense: the Phase 5.3.3
parameters were locked before it was executed, and no threshold/alpha search is
performed against it. It is checked into the repository for reproducibility, so
this is not a secrecy claim.

All three splits cover:

- temporal update
- failure override
- reliability conflict
- semantic trap
- preference evolution
- contradiction
- no intervention

## Locked policies and controls

Four policies are evaluated without changing runtime recall:

| Policy | Rule |
| --- | --- |
| Retrieval baseline | Preserve the explicit baseline order. |
| Metadata confidence | Normalized baseline/confidence fusion at fixed `alpha = 0.20`. |
| Recency boost | Normalized baseline/temporal-state fusion at fixed `alpha = 0.20`. |
| Margin Guard | Phase 5.3.3 policy at threshold `0.08`, cognitive `alpha = 0.20`. |

The metadata and recency controls answer whether a simple rule explains the
same value as the full cognitive competition signal.

## Results

### Held-out test split

| Policy | MRR | Intervention precision | Intervention recall | Unnecessary intervention | Catastrophic regression |
| --- | ---: | ---: | ---: | ---: | ---: |
| Retrieval baseline | 0.5952 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Metadata confidence | 0.7143 | 1.0000 | 0.2941 | 0.0000 | 0.0000 |
| Recency boost | 0.9048 | 1.0000 | 0.7647 | 0.0000 | 0.0000 |
| **Margin Guard** | **0.9524** | **1.0000** | **0.8824** | **0.0000** | **0.0000** |

The held-out result is deliberately not perfect. Margin Guard misses two of the
17 required interventions, which is stronger evidence than reproducing the
fully templated Phase 5.3.3 score of `1.0000`.

Local controlled conclusion:

```text
Margin Guard > retrieval baseline
Margin Guard > confidence-only reranking
Margin Guard > recency-only reranking
safety regressions = 0
```

This supports controlled generalization of conditional cognitive authority. It
does not prove end-to-end retrieval improvement.

## Factor interaction study

The locked Margin Guard policy is also evaluated on the held-out split with
factor subsets:

| Interaction | MRR | Intervention recall |
| --- | ---: | ---: |
| Full cognitive | 0.9524 | 0.8824 |
| Failure + Temporal | 0.9286 | 0.8235 |
| Failure + Reliability | 0.8333 | 0.5882 |
| Temporal + Preference | 0.7857 | 0.4706 |
| Failure only | 0.7381 | 0.3529 |
| Temporal + Reliability | 0.8333 | 0.5882 |
| Context + Preference | 0.5952 | 0.0000 |

The interaction result refines the Phase 5.3.3 ablation result:

- failure evidence remains important but is not sufficient alone;
- failure plus temporal confidence retains most of the full-policy value;
- recency alone is strong but does not explain all cognitive value;
- context plus preference provides no measured top-1 intervention value in this fixture;
- the full signal performs best, indicating useful factor complementarity.

No factor is removed from runtime code and no new cognitive factor is added.

## Safety boundary

The report records:

```text
eval_only                    = true
shadow_only                  = true
baseline_authoritative       = true
fixed_policy_parameters      = true
policy_locked_before_test    = true
hidden_test_used_for_tuning  = false
runtime_applied              = false
policy_memory_written        = false
memory_mutated               = false
ranking_mutated              = false
scores_mutated               = false
activation_changed           = false
candidate_pool_changed       = false
recall_engine_integrated     = false
production_claim_authorized  = false
end_to_end_claim_authorized  = false
```

Fixture setup writes an isolated in-memory corpus. Policy evaluation never
writes memory and never feeds a proposed ranking back into `RecallEngine`.

## Validation

```bash
cargo test -p synapse-eval --test phase5_cognitive_generalization_test
python scripts/eval/phase5_cognitive_generalization.py
```

The dedicated Rust suite contains 11 tests covering split integrity, dataset
hashes, fixed parameters, required controls, hidden-test comparison, factor
interactions, determinism, boundedness, unchanged state, and explicit claim
boundaries.

## Decision boundary

Phase 5.3.4 establishes only:

> The locked Margin Guard policy retains value over simple controls on a
> disjoint controlled cognitive-conflict fixture.

It does not establish:

- real user-query distribution improvement;
- end-to-end candidate retrieval improvement;
- latency or operational cost acceptability;
- human preference;
- runtime A/B authorization;
- a production default.

Before runtime work, Phase 5 still requires an independent end-to-end benchmark
where candidate generation, retrieval scores, and ground truth are not assigned
by the policy fixture.
