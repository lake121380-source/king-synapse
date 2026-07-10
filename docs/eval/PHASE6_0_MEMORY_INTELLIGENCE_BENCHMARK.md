# Phase 6.0 Memory Intelligence Benchmark

Status: **Benchmark foundation complete; algorithm comparison and runtime authorization are explicitly out of scope**.

Date: 2026-07-10

## Objective

Phase 6.0 establishes a larger deterministic Agent-memory workload before any
new cognitive-ranking work. It asks whether the real retrieval pipeline can
consistently expose the relevant candidate in memory-conflict scenarios and
whether later policies can be evaluated against stable labels without manual
retrieval scores.

It does **not** compare cognitive, recency, failure, confidence, graph, or other
ranking policies. It does not modify `RecallEngine`, register a runtime booster,
or authorize a production claim.

## Frozen workload

The checked-in generator and dataset are:

- `scripts/eval/generate_phase6_memory_intelligence_benchmark.py`
- `crates/eval/datasets/memory_intelligence/agent_memory_benchmark.toml`

The workload contains:

```text
scenarios          = 320
memories           = 1920
memories/scenario  = 6
unique queries     = 320
categories         = 10
template variants  = 4
train/validation/test = 160/80/80
```

Each category contains 32 scenarios with a fixed `16/8/8` split:

1. `temporal_update`
2. `failure_override`
3. `reliability_conflict`
4. `preference_evolution`
5. `contextual_constraint`
6. `failure_vs_recency_failure_wins`
7. `failure_vs_recency_recency_wins`
8. `reliability_vs_recency_reliability_wins`
9. `reliability_vs_recency_recency_wins`
10. `no_intervention`

The final label mix is:

```text
intervention_required = 224
no_intervention       = 96
```

Every scenario carries an explicit timeline, one ground-truth memory, a reason
for that label, and at least two conflicting signals. The dataset contains no
`baseline_score` field.

## Real retrieval protocol

For each scenario, the evaluator:

1. creates an isolated in-memory `Store`;
2. writes all six memories through the public Store API;
3. executes `RecallEngine::recall_profiled` with `k = 5`;
4. uses the returned `RecallHit.score` values and ranking as the baseline;
5. repeats recall against the same Store with access recording disabled;
6. verifies the Store snapshot is unchanged;
7. records reachability and ranking metrics without applying any policy.

The protocol uses real FTS retrieval. The entity branch remains enabled but the
current workload produces zero entity candidates. Vectors and the reranker are
disabled so Phase 6.0 freezes one clearly identified retrieval lane rather than
mixing algorithm changes into benchmark construction.

`RecallEngine` applies wall-clock temporal decay at second resolution. Ranking
repeatability remains exact; score repeatability uses a `1e-6` tolerance so a
pair of otherwise identical recalls that straddles a one-second boundary does
not create a false determinism failure.

## Label-alignment correction

The first 320-scenario draft produced:

```text
Recall@1               = 0.9000
label_intent_alignment = 0.2000
status                  = FAIL
```

The failure was not repaired by changing policy parameters or inserting manual
scores. Inspection showed that real `RecallEngine` scoring already multiplies
retrieval evidence by memory importance, confidence, and temporal decay. Several
initial reliability/high-confidence cases had therefore been labeled as if the
baseline needed intervention even though the baseline already ranked the
intended memory first.

The workload was corrected to reflect observed baseline semantics:

- reliability cases already resolved by confidence/importance are labeled
  no-intervention;
- temporal, failure, preference, context, and signal-disagreement cases not
  directly resolved by the baseline remain intervention-required;
- the expected memory must still be present in the real top-5 candidate pool.

This correction is part of the benchmark design evidence: it prevents Phase 6
from counting capability already present in the baseline as new cognitive gain.

## Stable result

Report:

- `crates/eval/reports/phase6_memory_intelligence_benchmark.json`

Current deterministic result:

| Metric | Value |
| --- | ---: |
| Expected-candidate retrieval rate | `1.0000` |
| Recall@1 | `0.3000` |
| Recall@3 | `1.0000` |
| Recall@5 | `1.0000` |
| MRR@5 | `0.6500` |
| NDCG@5 | `0.7417` |
| Determinism | `1.0000` |
| Store unchanged rate | `1.0000` |
| Label-intent alignment | `1.0000` |
| Entity candidates | `0` |

The expected-rank distribution is intentionally diagnostic:

```text
rank 1 = 96 scenarios
rank 2 = 224 scenarios
```

It provides both silent-correctness cases and cases in which a later evaluation
policy has an opportunity to intervene. Phase 6.0 itself makes no judgment
about which intervention policy should win.

## Quality-gate semantics

A Phase 6.0 `PASS` means only:

- the generated dataset matches the checked-in source;
- split, category, timeline, label, and provenance constraints are valid;
- all expected memories are reachable through the real RecallEngine top-5;
- repeated rankings and aggregate metrics are deterministic;
- recall does not mutate the Store;
- no algorithm comparison or runtime path was activated.

A Phase 6.0 `PASS` does **not** mean:

- cognitive ranking beats retrieval or a simple metadata rule;
- independent cognitive value has been established;
- the workload represents an external or real-user query distribution;
- vector/reranker behavior has been validated;
- runtime or production use is authorized.

This is a repository-authored deterministic synthetic workload. Its purpose is
to provide a reproducible experimental foundation, not external validity.

## Reproduction

```bash
python scripts/eval/generate_phase6_memory_intelligence_benchmark.py --check
cargo test -p synapse-eval --test phase6_memory_intelligence_benchmark_test
python scripts/eval/phase6_memory_intelligence_benchmark.py
```

## Safety boundary

The checked-in report must preserve:

```text
benchmark_only                    = true
real_recall_engine_used           = true
artificial_baseline_scores_used   = false
algorithm_comparison_performed    = false
independent_cognitive_value_claimed = false
runtime_applied                   = false
runtime_authorization             = false
production_claim_authorized       = false
```

## Next decision

Phase 6.1 may compare cognitive ranking with simple baselines over the frozen
workload, while preserving the candidate pool and real baseline scores. Phase
6.0 itself remains benchmark-only and must not be retroactively interpreted as
an algorithm win.
