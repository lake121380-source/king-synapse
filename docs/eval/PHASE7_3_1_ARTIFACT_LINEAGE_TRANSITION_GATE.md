# Phase 7.3.1-C Artifact Lineage & Irreversible Transition Gate

Status: two heterogeneous blind AI reviews, the Agreement Report, the 77-group third-model adjudication, and the model-adjudicated Silver artifact are frozen. Workflow is at `silver_labels_frozen`.

## Purpose

This stage does not produce Reviewer labels, agreement statistics, adjudication, or Judge calibration. It now verifies the separately generated immutable Silver artifact. It makes the authorization chain explicit and detectable:

```text
Source execution + blind packet + Reviewer A/B files + agreement protocol
                              |
                              v
                    Agreement Report
                   (upstream hashes)
                              |
                              v
                       Adjudication
                (Agreement Report hash)
                              |
                              v
                         Silver Labels
                   (adjudication hash)
                              |
                              v
                 Frozen Judge Calibration
                (Silver + Judge exact hashes)
```

An artifact never embeds its own complete-file hash. A downstream artifact references the SHA-256 of the exact upstream file bytes.

## Workflow state machine

Reviewer completion is order-independent:

```text
awaiting_independent_reviews (0/2 or 1/2)
  -> raw_reviews_complete_agreement_required (2/2)
  -> agreement_report_frozen_adjudication_allowed
  -> adjudication_complete_silver_freeze_required
  -> silver_labels_frozen
  -> judge_calibration_allowed
```

Same-state rechecks are allowed. Backward and skipped transitions are rejected. `Reviewer B` may complete before `Reviewer A`; only the completed count and the two independent completion flags matter.

## Detectable invalidation

?Irreversible? is a governance invariant, not a filesystem claim. Files can technically be edited, but any upstream byte change causes:

```text
current SHA-256 != referenced SHA-256
  -> artifact_lineage_invalid
  -> every downstream permission false
```

Generated metadata, including timestamps, is included in the exact-file hash. Regenerating an Agreement Report after adjudication therefore invalidates the adjudication reference unless the downstream experiment is deliberately restarted.

## Current result

```text
state                         silver_labels_frozen
completed reviews             2/2
adjudicated groups            77/77
artifact lineage broken       false
agreement computation         complete and frozen
adjudication                  complete and lineage-valid
Silver freeze                 complete and lineage-valid
Judge calibration             unauthorized pending exact calibration lineage
Silver hash                   available
Frozen-Judge hash             unavailable
```

No fake Reviewer, fake agreement metric, human Gold claim, or calibration artifact was generated. The Silver artifact is deterministic, immutable, and explicitly model-adjudicated rather than human Gold.

## Frozen boundaries

The stage does not modify or authorize:

- Prompt, Provider, Parser, Repair Policy, Extractor, scorer, or frozen Judge;
- held-out access;
- memory writes;
- Hermes or runtime integration.

## Reproduction

```powershell
python scripts/eval/phase7_artifact_lineage_transition_gate.py
cargo test -p synapse-eval --test phase7_artifact_lineage_transition_gate_test -- --nocapture
```
