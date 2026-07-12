# Phase 7.3.1-E Resumable Third-Model Adjudication Runner

Status: **infrastructure frozen and locally validated; real adjudication remains blocked by provider quota.**

## Purpose

This stage adds the executable boundary between the frozen two-reviewer Agreement Report and future frozen semantic labels. It does not claim that adjudication has completed.

The runner uses one third model to resolve the 77 frozen adjudication groups:

```text
Reviewer A (GPT-4.1, 74 claims) ----\
                                      -> 74 aligned groups + 3 unmatched groups
Reviewer B (Qwen 3.5 Plus, 77 claims) /
                                                    |
                                                    v
                                      independent third-model adjudicator
                                                    |
                                                    v
                                  model-adjudicated silver candidate labels
```

These labels are **not human Gold**. The third model is an adjudicator over the already frozen grouping; it is not allowed to re-segment the Candidate.

## Frozen inputs

The checkpoint and final manifest bind the exact SHA-256 values of:

- canonical adjudicator prompt;
- blind review packet;
- Reviewer A submission;
- Reviewer B submission;
- frozen Agreement Report;
- adjudication adapter implementation.

A mismatch blocks resume and requires an explicit `--reset-checkpoint`. This prevents decisions produced under one model, protocol, input set, or runner implementation from being silently continued under another.

## Information boundary

The adjudicator sees only:

- the authoritative Evidence Bundle for one design case;
- the frozen Pattern Candidate;
- the Reviewer A/B claims in each frozen alignment group.

It cannot see:

- the frozen Judge or Judge warnings;
- Phase 7.3 seed labels or aggregate error rates;
- reference Candidates;
- held-out cases;
- tools, web, or memory;
- raw historical Provider responses.

`judge_failures` therefore remains empty in the adjudication artifact. Frozen-Judge comparison belongs to the later calibration stage.

## Output contract

For every supplied `group_id`, the model must return exactly:

```json
{
  "group_id": "...",
  "final_support_label": "supported | partially_supported | unsupported | not_assessable",
  "final_claim_origin": "explicit | inferred | synthesized",
  "adjudication_rationale": "..."
}
```

The adapter rejects missing/extra fields, duplicate or missing groups, invalid enums, and empty rationales. A schema failure may retry the same frozen request up to the configured maximum. There is no semantic repair.

## Resume and persistence policy

A full run is isolated by design case. After each fully validated case, only normalized decisions and case metadata are atomically checkpointed under:

```text
target/phase7/phase7_3_1_ai_adjudicator_checkpoint.json
```

Raw Provider responses are never persisted. A failed case does not replace successful checkpointed cases. Resume skips already completed cases only after validating that checkpoint decisions exactly match those cases. Readiness probes executed with `--case` never write checkpoints or final artifacts.

Final artifacts are written only after the runner has exactly:

```text
10 unique completed cases
77 unique adjudicated groups
```

The checkpoint is removed only after both the completed adjudication artifact and Provider manifest have been written.

## Current execution result

Provider probes established that the relay credential is authorized, but complete adjudication could not finish because the relay returned `insufficient_user_quota`. Partial normalized decisions from those pre-checkpoint attempts were not promoted and no final artifact was written.

Current repository state must therefore remain:

```text
adjudication completed    false
silver labels frozen      false
Judge calibration         blocked
held-out                  blocked
runtime/Hermes/memory     blocked
```

Do not replace the missing third-model decisions with deterministic Reviewer consensus. That would silently change the research protocol.

## Reproduction

Set `PHASE7_REVIEW_API_KEY` outside repository files, then run one frozen adjudicator model across all ten cases:

```powershell
python scripts/eval/phase7_ai_independent_adjudicator.py `
  --model gemini-2.5-pro `
  --max-attempts 2
```

A one-case non-persisting readiness probe is available through `--case`. Use one model for the complete run; mixing models case-by-case requires a separately frozen committee protocol.

Local invariant tests:

```powershell
python -m unittest scripts.eval.tests.test_phase7_ai_independent_adjudicator -v
python -m py_compile scripts/eval/phase7_ai_independent_adjudicator.py
```

## Next authorization

After sufficient Provider quota is available, complete one homogeneous third-model run and validate its exact lineage. The resulting labels must be named **model-adjudicated silver candidate labels**. Only after a separate silver-freeze transition may frozen-Judge calibration begin.
