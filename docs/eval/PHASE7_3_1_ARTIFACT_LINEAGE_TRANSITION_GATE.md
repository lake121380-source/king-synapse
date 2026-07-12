# Phase 7.3.1-C Artifact Lineage & Irreversible Transition Gate

Status: governance protocol, exact-file SHA-256 lineage, transition state machine, report harness, and tests frozen. Scientific review remains at `0/2`.

## Purpose

This stage does not produce Reviewer labels, agreement statistics, adjudication, Gold labels, or Judge calibration. It makes the authorization chain explicit and detectable:

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
                         Gold Labels
                   (adjudication hash)
                              |
                              v
                 Frozen Judge Calibration
                (Gold + Judge exact hashes)
```

An artifact never embeds its own complete-file hash. A downstream artifact references the SHA-256 of the exact upstream file bytes.

## Workflow state machine

Reviewer completion is order-independent:

```text
awaiting_independent_reviews (0/2 or 1/2)
  -> raw_reviews_complete_agreement_required (2/2)
  -> agreement_report_frozen_adjudication_allowed
  -> adjudication_complete_gold_freeze_required
  -> gold_labels_frozen
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
state                         awaiting_independent_reviews
completed                     0/2
artifact lineage broken       false
agreement computation         unauthorized
adjudication                   unauthorized
Gold freeze                    unauthorized
Judge calibration              unauthorized
Gold/Judge hashes              unavailable
```

No fake Reviewer, fake agreement metric, adjudication, Gold label, or calibration artifact was generated.

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
