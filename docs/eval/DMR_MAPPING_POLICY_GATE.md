# DMR Mapping Policy Gate

Date: 2026-07-04

> **NOTE (2026-07-05):** This gate was written under the `punctuation` mapping
> policy. A 30-sample human audit proved that policy rejects samples that
> contain the gold answer in memory. The corrected `significant_token_containment`
> policy scores 433/500 (vs 323). See `DMR_MAPPING_POLICY_CORRECTION.md` for
> the corrected results. Gate conclusions referencing the 323-sample set should
> be re-evaluated under the new mapping.

Status: validation evidence, not a runtime change

Machine-readable report:

`crates/eval/reports/dmr-mapping-policy-gate.json`

Runner:

`scripts/eval/dmr_mapping_policy_gate.py`

## Question

Should the DMR mapping policy be changed from punctuation-normalized
full-answer matching to a relaxed policy?

## Decision

`No.`

Keep `punctuation_full_answer` as the runtime default. Do not silently promote
relaxed diagnostic policies to official DMR scores.

The gate passes because the policy decision is evidence-backed, not because
mapping performance is good.

## Coverage Comparison

| Policy | Coverage | Share | Additional over current |
| --- | ---: | ---: | ---: |
| punctuation_full_answer (current) | 323 | 64.6% | 0 |
| significant_token_containment | 442 | 88.4% | +119 |
| significant_token_overlap_75 | 469 | 93.8% | +146 |
| significant_token_overlap_50 | 487 | 97.4% | +164 |
| any_significant_token | 494 | 98.8% | +171 |

## Rationale

177/500 requested rows are rejected by the pinned punctuation policy. Of those:

- 122 have full significant-token containment in a single chunk.
- 27 have 75% token overlap.
- 18 have 50% token overlap.
- 7 have at least one significant token.
- 3 have no diagnostic match.

174/177 rejected rows have diagnostic token matches, so the answer is likely in
memory but missed by strict matching. A relaxed policy could recover up to 119
rows (significant_token_containment), but it must be judge-validated before
promotion. Silently switching would inflate scores without proving the
recovered rows are correct.

## Validation-Only Relaxed Path

Run DMR 500 with `significant_token_containment` mapping + DeepSeek judge
scoring, then compare judge accuracy against the pinned punctuation baseline.
Only promote if judge accuracy improves and no false positives are introduced.

This is a separate labeled experiment, not a runtime default change.

## Gate Status

- `dmr_mapping_policy_gate_passed`: true
- `runtime_mapping_policy_change_allowed`: false
- `current_policy`: punctuation_full_answer
- `relaxed_policy_candidate`: significant_token_containment
- `relaxed_policy_additional_coverage`: 119
- `mapping_rejected_count`: 177
- `mapping_rejected_with_token_match`: 174
- `mapping_rejected_no_match`: 3
- `productization_allowed`: false

## Next Action

Keep feature freeze. Do not change runtime mapping default. The next useful
step is a labeled relaxed-mapping judge experiment, or continue to LongMemEval
/ DMR trend alignment.
