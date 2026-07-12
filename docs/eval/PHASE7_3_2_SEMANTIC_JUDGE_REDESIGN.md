# Phase 7.3.2 Semantic Judge Redesign

## Status

`COMPLETE_DESIGN_ONLY_NEGATIVE_RESULT`

Phase 7.3.2 changes exactly one experimental object: the Judge. Evidence bundles, the ten Phase 7.2.3 Candidates, Extractor, Provider, Prompt/Parser/Repair policy, model-adjudicated Silver references, and the old frozen Judge remain immutable controls. Held-out data, runtime, memory writes, Pattern promotion, and Hermes remain unauthorized.

## Question

Can a semantic, evidence-constrained ordinal Judge distinguish `supported`, `partially_supported`, `unsupported`, and `not_assessable` better than the old lexical novelty proxy?

## Execution

The frozen `PatternSemanticJudgePrompt-v1` was executed case-by-case through `gpt-5.4-2026-03-05` on exactly ten design Candidates. The adapter loaded only each Evidence bundle and Candidate. It did not load Silver labels, reviewer annotations, adjudication rationales, old-Judge warnings, reference Candidates, or held-out data. Temperature was `0`, top-p was `1`, parsing was strict JSON, repair and selective retry were disabled, raw Provider responses and credentials were not stored.

## Result

The semantic Judge returned:

```text
partially_supported  10/10
supported             0/10
unsupported           0/10
not_assessable        0/10
```

Against the frozen model-adjudicated Silver candidate aggregates:

```text
ordinal exact agreement  7/10 = 0.70
```

The apparent `0.70` is not evidence of discrimination: seven of ten Silver Candidates are themselves `partially_supported`, so the Judge matched the majority class while missing the one `supported` and both `unsupported` Candidates.

### Strict-safety view

Positive means `partially_supported | unsupported`.

```text
Old frozen Judge: TP=9 FP=1 FN=0 TN=0
New semantic Judge: TP=9 FP=1 FN=0 TN=0

precision          0.90
recall             1.00
specificity        0.00
false-positive     1.00
balanced accuracy  0.50
MCC                null
```

There is no improvement.

### Strong-error view

Positive means `unsupported`; partially-supported cases are excluded.

```text
Old frozen Judge: TP=2 FP=1 FN=0 TN=0
New semantic Judge: TP=0 FP=0 FN=2 TN=1

new recall          0.00
new specificity     1.00
new balanced acc.   0.50
new MCC              null
```

The new Judge eliminated strong-error false positives only by never predicting strong error. This is a sensitivity collapse, not useful discrimination.

## Conclusion

The first semantic redesign replaced an **always-positive binary warning collapse** with an **always-partially-supported ordinal collapse**. It did not improve balanced accuracy or demonstrate independent semantic discrimination.

This is a valid negative scientific result. It suggests that whole-Candidate, single-label judging is too coarse: one overcommitted prediction can make an otherwise grounded Candidate partially supported, while a truly unsupported central proposition is not separated reliably.

## Next allowed step

Do not tune `PatternSemanticJudgePrompt-v1` on these same ten outputs and do not open held-out data. A separate future phase should pre-register an atomic-claim semantic Judge that:

1. judges proposition, prediction, falsification, scope, and exclusions separately;
2. aggregates claim-level labels with an explicit frozen rule;
3. includes contradiction and supported controls before execution;
4. preserves the current Phase 7.3.2 result unchanged as the whole-Candidate baseline.

Scope calibration remains unavailable because final scope labels were not independently adjudicated.

## Reproduction

```powershell
python scripts/eval/phase7_semantic_judge_redesign.py
cargo test -p synapse-eval --test phase7_semantic_judge_redesign_test -- --nocapture
```

The Provider execution adapter is `scripts/eval/phase7_semantic_judge_execution.py`. It requires a credential only when creating a new execution artifact; the checked-in normalized execution and report contain no credential or raw response.
