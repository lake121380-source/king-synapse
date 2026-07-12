# Phase 7.3.1-D Model-Adjudicated Silver Label Freeze

Status: complete. The 77 third-model adjudication decisions are frozen into ten candidate-level diagnostic aggregates.

## Purpose

This stage converts the completed adjudication into an immutable, hash-bound reference artifact. It does **not** convert AI labels into human Gold and does not establish semantic truth.

```text
Reviewer A + Reviewer B + frozen Agreement Report
                    |
                    v
        third-model adjudication (77/77)
                    |
                    v
 model-adjudicated Silver freeze (77 claims / 10 candidates)
```

The artifact references the exact SHA-256 of `phase7_3_1_adjudication_template.json`. Any upstream byte change invalidates the Silver lineage.

## Result

```text
frozen claims                  77
candidate aggregates           10
label status                   model_adjudicated_silver_not_human_gold
human Gold                     false
held-out accessed              false
scope labels adjudicated       false
scope calibration available    false
workflow state                 silver_labels_frozen
Judge calibration authorized   false
```

Candidate aggregation is conservative: `unsupported` dominates `partially_supported`, which dominates `supported`; `not_assessable` is used only when no assessable claim exists.

Scope calibration remains unavailable because the adjudicator did not produce final scope labels. Reviewer scope labels are not silently promoted into adjudicated truth.

## Boundaries

No Prompt, Provider, Parser, Repair Policy, Extractor, frozen Judge, or threshold changed. No held-out case, memory write, knowledge promotion, Hermes connection, or runtime behavior is authorized.

## Reproduction

```powershell
python scripts/eval/phase7_model_adjudicated_silver_freeze.py
python scripts/eval/phase7_artifact_lineage_transition_gate.py
cargo test -p synapse-eval --test phase7_model_adjudicated_silver_freeze_test -- --nocapture
```
