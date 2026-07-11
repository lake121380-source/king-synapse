# Phase 7.3.1-B Inter-reviewer Agreement Gate

Status: protocol, span contract, alignment algorithm, report harness, and tests frozen; real statistics remain unavailable until Reviewer A and Reviewer B independently complete all design cases.

## Research purpose

Frozen-Judge calibration is only meaningful if the semantic labels used as Gold have a documented independent-review history. This gate therefore measures the two raw blind submissions before adjudication.

```text
Reviewer A raw submission
Reviewer B raw submission
          ↓
Inter-reviewer Agreement Report
          ↓
Disagreement-preserving adjudication
          ↓
Frozen Gold Labels
          ↓
Candidate-level frozen-Judge calibration
```

Agreement never consumes adjudicated labels, Judge warnings, Phase 7.3 seed labels, reference Candidates, held-out cases, or runtime outcomes.

## Span contract

Claim count equality is not segmentation agreement. Every Reviewer-created Atomic Claim must bind to a half-open Unicode-character span:

```json
{
  "start_char": 0,
  "end_char": 12,
  "source_excerpt": "exact source text"
}
```

The excerpt must exactly equal the corresponding range inside the frozen ClaimSourceAnchor. This contract was frozen before any independent annotation began.

## Alignment policy

Claims are grouped by:

```text
case_id + anchor_id
```

Pair score:

```text
character span intersection over union
```

Matching is deterministic greedy descending IoU with Claim IDs as tie-breakers. The predeclared minimum IoU is:

```text
0.50
```

Claim-text similarity is forbidden during alignment because semantic similarity could hide segmentation disagreement.

## Segmentation metrics

```text
exact_boundary_agreement_rate
matched_span_mean_iou
overlap_alignment_rate
unmatched_claim_rate
split_disagreement_count
merge_disagreement_count
```

Exact-boundary rate uses the larger Reviewer Claim count as its denominator so unmatched Claims are not silently rewarded. Overlap alignment uses the symmetric `2 * aligned_pairs / total_claims` rate.

## Claim-count diagnostics

```text
reviewer_a_claim_count
reviewer_b_claim_count
absolute_claim_count_difference
per_case_claim_count_pearson_correlation
```

Claim-count agreement is diagnostic only and never substitutes for span agreement.

## Semantic agreement

Semantic agreement is calculated only over deterministically aligned Claim pairs:

```text
support raw agreement
support linear weighted kappa
support ordinal Krippendorff alpha
provenance agreement
scope agreement
causal-strength agreement
prediction-support agreement
counterexample-handling agreement
falsifiability agreement
annotation-confidence agreement
```

`not_assessable` is excluded from ordinal support reliability. Krippendorff alpha is secondary for the current two-Reviewer design; weighted kappa remains the primary chance-corrected statistic. Alpha becomes more useful if future protocols introduce missing ratings or more than two Reviewers.

## Current result

```text
Reviewer A completed  false
Reviewer B completed  false
Agreement metrics      unavailable
Adjudication used      false
Frozen Judge visible   false
Held-out accessed      false
Runtime/Hermes         false
```

Decision:

```text
waiting_for_two_independent_submissions
```

No semantic reliability, Candidate error rate, Gold label, or Judge-calibration claim is made by this readiness result.
