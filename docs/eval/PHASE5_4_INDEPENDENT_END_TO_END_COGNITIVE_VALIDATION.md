# Phase 5.4 Independent End-to-End Cognitive Validation

Status: **Local implementation, deterministic protocol gate, and shadow evaluation complete. Independent cognitive value is not established; runtime remains unauthorized.**

## Research question

Phase 5.3 showed that a margin-guarded cognitive policy can work on controlled
assigned-score fixtures. Phase 5.4 asks a stricter question:

> Does the locked cognitive policy add ranking value when candidates and
> baseline scores come from the real `RecallEngine` path?

The experiment does not change runtime recall.

## End-to-end path

```text
query
  -> isolated Store workload
  -> RecallEngine
  -> real RecallHit[] and RecallHit.score
  -> CognitiveTraceEvaluator
  -> shadow policies
  -> baseline/control/cognitive comparison
```

No `baseline_score` field exists in the workload. All baseline ranks and scores
come from `RecallEngine::recall_profiled`.

## Workload and retrieval protocol

Dataset:

```text
crates/eval/datasets/cognitive_end_to_end/agent_workload.toml
```

Coverage:

```text
24 scenarios
144 memories
120 retrieved candidates
6 categories
20 intervention-required scenarios
4 no-intervention scenarios
expected-candidate retrieval rate = 1.0000
```

Categories:

- failure override
- temporal access
- reliability conflict
- preference alignment
- mixed cognitive
- no intervention

Retrieval configuration:

```text
RecallEngine
candidate k = 5
FTS branch active
entity branch enabled by RecallEngine, but workload queries are entity-neutral
vectors disabled
reranker disabled
access recording disabled during recall
```

The entity-neutral query vocabulary is intentional. An earlier workload version
triggered equal-hit entity rankings whose SQL tie order depended on generated
ULIDs. That made fresh Store runs unstable. The final workload removes those
entity matches without assigning scores or changing `RecallEngine`; five fresh
runs reproduced every baseline and policy label ranking and every quality
metric.

Fixture setup may write isolated memories and record selected access metadata.
After setup, recall and all policies are observation-only. Store and `RecallHit`
snapshots are checked after evaluation.

## Locked policies

All non-baseline policies use the same Phase 5.3 authority envelope:

```text
alpha = 0.20
margin threshold = 0.08
candidate limit = 5
```

Policies:

| Policy | Signal |
| --- | --- |
| Retrieval baseline | Real `RecallHit.score`; no shadow change. |
| Confidence boost | Candidate confidence only. |
| Recency boost | Recorded recent-access state only. |
| Failure boost | Failure-memory indicator only. |
| Margin Guard Cognitive | Full deterministic cognitive trace signal. |

This isolates signal value from authority differences.

## Stable result

| Policy | Recall@1 | Recall@3 | MRR@5 | NDCG@5 | Intervention rate | Top-1 regression |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Retrieval baseline | 0.3333 | 1.0000 | 0.6667 | 0.7540 | 0.0000 | 0.0000 |
| Confidence boost | 0.5000 | 1.0000 | 0.7500 | 0.8155 | 0.1667 | 0.0000 |
| Recency boost | 0.6667 | 1.0000 | 0.8333 | 0.8770 | 0.3333 | 0.0000 |
| Failure boost | 0.6667 | 1.0000 | 0.8333 | 0.8770 | 0.3333 | 0.0000 |
| Margin Guard Cognitive | 0.6667 | 1.0000 | 0.8333 | 0.8770 | 0.3333 | 0.0000 |

Cognitive safety metrics:

```text
successful_intervention_rate = 1.0000
unnecessary_intervention_rate = 0.0000
catastrophic_regression_rate  = 0.0000
silent_correctness_rate       = 1.0000
determinism                   = 1.0000
```

## Decision

Observed comparisons:

```text
Cognitive > retrieval baseline
Cognitive > confidence-only control
Cognitive = recency-only control
Cognitive = failure-only control
Cognitive delta vs best simple control = 0.0000
```

Therefore:

```text
protocol_and_safety_gate_pass              = true
independent_end_to_end_value_supported      = false
runtime_authorization                       = false
production_claim_authorized                 = false
```

The correct conclusion is not that the cognitive policy failed. It safely
improved the baseline on this workload. However, the full cognitive signal did
not add measurable value beyond the strongest simple recency/failure controls.
The current workload therefore does not justify the extra cognitive ranking
complexity or a runtime A/B.

## Quality-gate semantics

`PASS` means:

- real `RecallEngine` candidates and scores were used;
- every expected candidate entered the retrieved top five;
- fresh-run rankings are deterministic;
- candidate pools and baseline `RecallHit` values stayed unchanged;
- no memory, activation, runtime ranking, or schema mutation occurred;
- the recorded decision matches the observed metrics.

`PASS` does not mean positive gain, runtime authorization, or production value.
The external evaluation script intentionally accepts a scientifically valid
negative or tied result.

## Limitations

- The workload is deterministic and repository-authored, not an external user distribution.
- DMR and LongMemEval raw datasets are not vendored in this repository.
- Vector retrieval and reranking were not evaluated.
- Entity retrieval produced zero candidates by workload design to preserve fresh-run determinism.
- The workload is small and Recall@3 is saturated.
- Latency values are diagnostic local measurements, not production capacity evidence.

## Validation

```bash
python scripts/eval/phase5_end_to_end_cognitive.py
cargo test -p synapse-eval --test phase5_end_to_end_cognitive_test
```

Report:

```text
crates/eval/reports/phase5_end_to_end_cognitive.json
```

The Rust suite covers real-score provenance, expected-candidate retrieval,
candidate-pool preservation, policy controls, decision consistency, safety,
claim boundaries, and fresh-run ranking determinism.

## Next decision boundary

Do not integrate the booster into runtime from this result.

The next useful research step is an external or independently authored workload
with richer retrieval variation, ideally including vectors/reranking and cases
where recency and failure signals disagree. If full cognitive remains tied with
simple controls, keep Cognitive Trace as an explanation/evaluation layer and
consider a narrower conditional policy rather than a general runtime booster.
