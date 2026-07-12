# Phase 7.3.1-F Frozen Judge Diagnostic Calibration

Status: complete against frozen model-adjudicated Silver references.

## Scientific boundary

This is a **diagnostic comparison**, not a human-Gold accuracy claim. The extractor, provider, prompt, parser, repair policy, frozen Judge, and all thresholds remain unchanged. Only the ten design cases are used. Held-out access, Pattern learning, knowledge promotion, memory writes, Hermes, and runtime integration remain unauthorized.

Exact-file lineage is frozen for:

```text
model-adjudicated Silver SHA-256
frozen Judge report SHA-256
```

The calibration declaration explicitly records:

```text
reference_status             model_adjudicated_silver_not_human_gold
human_gold                   false
scope_calibration_authorized false
held_out_accessed            false
```

## Candidate-level reference labels

The conservative Silver aggregation produced:

```text
supported              1
partially_supported    7
unsupported            2
```

The frozen Judge emitted `unsupported_warning=true` for all ten candidates.

## Strict-safety view

Positive reference labels are `partially_supported` and `unsupported`.

```text
TP 9   FP 1   FN 0   TN 0   excluded 0
precision              0.90
recall / sensitivity   1.00
specificity            0.00
false-positive rate    1.00
balanced accuracy      0.50
MCC                     undefined
```

## Strong-error view

Only `unsupported` is positive. `partially_supported` and `not_assessable` are excluded.

```text
TP 2   FP 1   FN 0   TN 0   excluded 7
precision              0.6667
recall / sensitivity   1.00
specificity            0.00
false-positive rate    1.00
balanced accuracy      0.50
MCC                     undefined
```

## Interpretation

The frozen Judge is maximally sensitive on these ten candidates, but it does not demonstrate useful discrimination because it never emits a negative warning. High recall here must not be described as high semantic accuracy. The result identifies an always-positive warning proxy under this design set and supports studying Judge redesign separately from extractor redesign.

Scope calibration remains `null`: the third-model adjudication did not create final scope labels, and raw Reviewer scope labels are not promoted into truth.

## Reproduction

```powershell
python scripts/eval/phase7_artifact_lineage_transition_gate.py
python scripts/eval/phase7_independent_adjudication_calibration.py
cargo test -p synapse-eval --test phase7_artifact_lineage_transition_gate_test --test phase7_independent_adjudication_calibration_test -- --nocapture
```
