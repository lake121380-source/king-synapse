# Phase 7.3.1 Independent Reviewer Guide

## Purpose

This guide is for a genuinely independent semantic reviewer evaluating frozen Pattern Candidates against frozen Evidence Bundles. The reviewer is not evaluating writing quality and must not optimize or rewrite the Candidate.

## Required blindness

A reviewer is eligible only if they have not seen:

- the other reviewer submission;
- frozen-Judge warnings, scores, or thresholds;
- Phase 7.3 seed labels or aggregate failure conclusions;
- reference Candidates;
- held-out cases;
- raw Provider responses outside the frozen parsed Candidate.

If any item was seen, do not mark the submission as blind.

## Files supplied to each reviewer

Give each reviewer a separate clean copy of:

```text
crates/eval/datasets/pattern_extraction/phase7_3_1_blind_review_packet.json
```

Give Reviewer A a separate writable copy of:

```text
crates/eval/datasets/pattern_extraction/phase7_3_1_reviewer_a_template.json
```

Give Reviewer B a separate writable copy of:

```text
crates/eval/datasets/pattern_extraction/phase7_3_1_reviewer_b_template.json
```

Do not place the two completed submissions in a shared location until both are frozen.

## Review unit

`ClaimSourceAnchor` identifies a claim-bearing Candidate field; it is not an atomic semantic truth. Independently split each anchor into the smallest claims that can receive stable evidence, provenance, scope, causal-strength, prediction, counterexample, and falsifiability judgments.

Do not copy another segmentation. Segmentation disagreement is a measured result.

Each atomic Claim must identify a half-open Unicode-character span `[start_char, end_char)` inside its ClaimSourceAnchor. `source_excerpt` must exactly equal that span. Byte offsets and token offsets are not allowed. If one source field contains multiple atomic Claims, give each Claim its own span; do not force identical boundaries merely to simplify agreement.

## Required annotation per atomic Claim

Each Claim must include:

```text
claim_id
case_id
response_sha256
anchor_id
source_span.start_char
source_span.end_char
source_span.source_excerpt
claim_text
claim_origin
claimed_evidence_ids
human_support_label
dimension_labels
failure_kinds
reviewer_rationale
annotation_confidence
```

`claim_origin` is one of:

```text
explicit
inferred
synthesized
```

`human_support_label` is one of:

```text
supported
partially_supported
unsupported
not_assessable
```

`partially_supported` should be used when the Evidence supports the direction but not the Candidate's full certainty, scope, causal force, prediction, or detail.

`synthetized` is not a valid value. Use `synthesized`. A synthesized Claim is not automatically unsupported; judge whether the supplied Evidence grounds the synthesis.

## Completion declaration

Only after all ten design cases are independently segmented and labeled:

```text
completed = true
held_out_accessed = false
blind_to_other_reviewer = true
blind_to_frozen_judge = true
blind_to_phase7_3_aggregates = true
```

Use a real reviewer identifier and a unique submission identifier. Do not modify the protocol ID or source execution ID.

## Handoff

After both submissions are frozen:

1. validate both files against the Phase 7.3.1 harness;
2. preserve all segmentation and semantic disagreements;
3. give both submissions to an adjudicator;
4. complete the adjudication template;
5. only then calculate Candidate-level frozen-Judge calibration.

No Candidate may be promoted to knowledge during this process.
