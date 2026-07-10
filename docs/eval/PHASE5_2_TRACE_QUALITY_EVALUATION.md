# Phase 5.2 Cognitive Trace Quality Evaluation

Status: **Frozen - local deterministic proof complete; external validation pending**.

## 1. Purpose

Phase 5.1 connected cognitive competition tracing to real `RecallHit` candidates
without changing retrieval behavior. Phase 5.2 asks whether the resulting trace
contains more useful and faithful explanation information than ordinary recall
metadata.

This phase remains evaluation-only:

```text
RecallHit candidates
        |
        +--> existing ranking (unchanged)
        |
        +--> CognitiveCompetitionTrace
                  |
                  +--> quality audit only
```

No trace score is fed back into recall, activation, storage, working memory, or
candidate generation.

## 2. Compared Explanations

The baseline explanation contains only retrieval metadata:

- candidate id
- rank
- score
- retrieval sources
- memory timestamp

The cognitive explanation contains:

- dominant candidate
- suppressed candidates
- candidate-level factors
- factor contributions
- competition confidence

## 3. Experiments

### 3.1 Explanation completeness

Each scenario checks five components:

1. a valid dominant candidate is identified
2. all non-dominant candidates are reported as suppressed
3. every candidate has factor coverage
4. all factors required by the source `RecallHit` data are present
5. confidence and candidate count are valid

Metric:

```text
explanation_completeness
```

Gate:

```text
>= 0.90
```

### 3.2 Factor faithfulness

The evaluator independently reconstructs the expected factors from the frozen
`RecallHit` contract and compares candidate id, factor type, and rounded
contribution against the emitted trace.

The audit records:

- expected factors
- actual factors
- faithful factors
- hallucinated factors
- missing factors

Metric:

```text
factor_faithfulness
```

Gate:

```text
= 1.00
```

### 3.3 Pairwise explanation preference

For deterministic CI, the report applies a transparent five-part pairwise
rubric to baseline metadata and the cognitive explanation:

- outcome identification
- alternative explanation
- evidence attribution
- confidence reporting
- candidate coverage

Metric:

```text
trace_preference_rate
```

Gate:

```text
>= 0.80
```

This is a local deterministic proxy. It is not presented as completed human or
LLM evidence. Every report includes:

```json
{
  "external_judge_ready": true,
  "human_or_llm_judge_completed": false
}
```

The scenario reports contain both explanation forms and can be converted into
blind A/B judge inputs without changing runtime code.

### 3.4 Determinism

The same query and same candidate state are evaluated repeatedly. The complete
`CognitiveCompetitionTrace` must remain identical.

Metric and gate:

```text
determinism = 1.00
```

## 4. Fixture Boundary

The six fixtures exercise the real public `RecallHit` contract through the
existing local `Store` and `RecallEngine`. They cover:

- failure evidence
- preference alignment
- reliability competition
- context alignment
- suppressed alternatives
- mixed memory kinds

The trace evaluator receives the returned candidates only. It performs no
hidden store query.

## 5. Results

Committed report:

```text
crates/eval/reports/phase5_trace_quality.json
```

Current local deterministic result:

```json
{
  "explanation_completeness": 1.0,
  "factor_faithfulness": 1.0,
  "trace_preference_rate": 1.0,
  "determinism": 1.0,
  "baseline_explanation_completeness": 0.4,
  "cognitive_explanation_completeness": 1.0,
  "explanation_information_gain": 0.6,
  "retrieval_trace_alignment": 0.8333333333333334
}
```

The retrieval/trace alignment value is diagnostic. A cognitive dominant
candidate is an observation-layer result and does not replace retrieval top-1.
The mismatch is intentionally visible before any booster experiment.

## 6. Safety Result

The report records:

```text
eval_only = true
core_behavior_changed = false
recall_ranking_changed = false
recall_scores_changed = false
memory_written = false
activation_changed = false
booster_enabled = false
external_model_called = false
```

## 7. Decision

The local deterministic Phase 5.2 quality gate passes:

```text
PASS_LOCAL_DETERMINISTIC_QUALITY_GATE
```

This establishes that the trace is structurally complete, source-faithful,
deterministic, and richer than baseline metadata under the declared rubric.

It does not close the external preference-evidence lane. Before interpreting
`trace_preference_rate` as a human-quality claim, run blinded human or LLM pairwise
judging over the exported scenario explanations.

Phase 5.3 remains separate and default-off. No booster activation is authorized
by this report alone.

## 8. Freeze Declaration

Phase 5.2 is frozen with the following evidence boundary:

```text
Implementation: complete
Local deterministic quality gate: passed
External human/LLM judge: pending
Runtime decision authority: unchanged
Booster authorization: not granted by Phase 5.2
```

The frozen conclusion is that cognitive trace output is complete, faithful,
deterministic, and more informative than baseline retrieval metadata under the
declared local rubric. It is not a human-preference or LLM-preference claim.

Entry into Phase 5.3 is limited to an OFF-by-default bounded booster prototype.
It must preserve the baseline path, provide A/B comparison and rollback, avoid
memory or schema mutation, and remain separate from production defaults.

## 9. Commands

```bash
cargo test -p synapse-eval --test phase5_trace_quality_test
python scripts/eval/phase5_trace_quality.py
```
