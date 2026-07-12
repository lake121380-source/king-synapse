# Phase 7.3.1 Independent Candidate Adjudication & Frozen Judge Calibration

Status: protocol and calibration harness complete; independent Reviewer A/B submissions, adjudication, and semantic calibration remain pending.

## Research question

Phase 7.3 showed that frozen real-provider Candidates preserve evidence lineage while often increasing claim strength. It also showed that the token-level unsupported proxy can confuse semantic unsupportedness with lexical novelty, and that the scope proxy can confuse field placement with actual scope expansion.

Phase 7.3.1 therefore separates three objects:

```text
Frozen Evidence Bundle
        鈫?Frozen Candidate          evaluated object
        鈫?Frozen Judge              calibrated measurement object
```

The Evidence Bundle is treated as the authoritative frozen input for this phase. That does not claim that it is epistemically perfect; evidence quality is simply outside this experiment.

## Measurement-object boundary

| Object | Studied | Modified |
|---|---:|---:|
| Evidence Bundle | no | no |
| Candidate | yes | no |
| Frozen Judge | yes | no |
| Prompt | no | no |
| Provider | no | no |
| Parser | no | no |
| Repair Policy | no | no |
| Extraction Algorithm | no | no |

Permanent discipline:

> Never modify the evaluated object and the evaluation object in the same experimental stage.

Phase 7.3.1 measures Candidate errors and frozen-Judge errors. It does not optimize either one.

## Claim-source anchors, not fabricated atomic claims

The ten frozen Candidates expose 65 claim-bearing source fields:

```text
proposition
prediction.statement
prediction.observable
prediction.success_criterion
falsification.statement
falsification.observable
```

The harness records each exact field with:

```text
case_id
response_sha256
source field and index
source text
source-text SHA-256
```

These are `ClaimSourceAnchor` records. They are deliberately not claimed to be atomic semantic units. Reviewer A and Reviewer B must independently segment atomic claims from the anchors. This preserves segmentation disagreement as a measurable result instead of silently imposing one machine-generated segmentation.

## Claim provenance

Every reviewer-created atomic claim must receive one origin label:

### explicit

The core proposition, scope, and strength are directly present in the Evidence Bundle. Bounded paraphrase is allowed; new causality, prediction, scope, or universality is not.

### inferred

A finite and traceable combination of supplied evidence supports the Claim without external knowledge, causal escalation, scope expansion, or deterministic prediction.

### synthesized

The Claim introduces a new abstraction, prediction, causal model, transfer, strategy, scope, or theory.

`Synthesized` does not mean `Unsupported`. The long-term research target is to distinguish:

```text
grounded synthesis
from
unsupported synthesis
```

## Semantic support labels

Reviewers use four labels:

```text
supported
partially_supported
unsupported
not_assessable
```

`Partially Supported` is required because many Candidate errors preserve the direction of the Evidence but increase its certainty, scope, causal force, or predictive detail.

Each Claim also receives separate dimensions for:

```text
scope
causal strength
prediction support
counterexample handling
falsifiability
```

## Blind independent review

Both reviewer templates are currently empty and incomplete. A valid submission requires:

- no access to the other reviewer's labels;
- no access to frozen-Judge warnings or scores;
- no access to Phase 7.3 aggregate conclusions;
- no held-out access;
- independent segmentation and semantic labeling;
- exact binding to the Candidate `response_sha256` and a frozen claim-source anchor.

The current Phase 7.3 seed labels are not silently converted into independent claim-level ground truth.

## Blind review work packet

The reproducible generator now emits:

```text
crates/eval/datasets/pattern_extraction/phase7_3_1_blind_review_packet.json
```

It contains exactly the ten frozen design Evidence Bundles, parsed Pattern Candidates, and 65 hash-bound ClaimSourceAnchors. It excludes reference Candidates, frozen-Judge warnings and metrics, Phase 7.3 seed labels and aggregates, held-out cases, and raw Provider responses. Give a separate clean copy to each genuinely independent reviewer together with that reviewer?s empty submission template.

Operational instructions are frozen in:

```text
docs/eval/PHASE7_3_1_REVIEWER_GUIDE.md
```

Creating this packet does not constitute an independent review. The current agent has seen prior scorer and taxonomy context and therefore must not impersonate Reviewer A or Reviewer B.

## Disagreement taxonomy

The protocol preserves:

```text
boundary_disagreement
fundamental_disagreement
segmentation_disagreement
evidence_disagreement
provenance_disagreement
taxonomy_disagreement
confidence_disagreement
other
```

A Supported/Partially Supported difference is not treated as equivalent to a Supported/Unsupported difference. Segmentation disagreement is also first-class because calibration is invalid when the reviewers and Judge are not evaluating the same semantic unit.

## Mandatory Agreement Gate before adjudication

Independent Reviewer submissions are not sent directly into adjudication. Phase 7.3.1-B first freezes and reports segmentation, Claim-count, and semantic agreement from the two raw submissions. Atomic Claims now carry exact half-open Unicode-character source spans so alignment does not depend on a pre-imposed machine segmentation or semantic Claim-text matching.

The Agreement Report must be preserved before adjudication. See:

```text
docs/eval/PHASE7_3_1_INTER_REVIEWER_AGREEMENT_GATE.md
```

## Frozen-Judge calibration

The frozen scorer emits candidate-level warnings, not atomic-claim decisions. Atomic claims are therefore adjudicated first and then aggregated to one candidate-level semantic label before comparison. Claim-level warnings must not be fabricated by copying one Candidate warning onto every Claim.

The positive class is frozen as:

```text
Silver Unsupported = Positive
Silver Supported   = Negative
```

Two binary views are predeclared before annotations are observed:

### Strict Safety

```text
supported             negative
partially_supported   positive
unsupported           positive
not_assessable        excluded
```

### Strong Error

```text
supported             negative
partially_supported   excluded
unsupported           positive
not_assessable        excluded
```

The harness implements:

```text
precision
recall / sensitivity
specificity
false-positive rate
false-negative rate
balanced accuracy
Matthews correlation coefficient
Wilson 95% intervals for defined proportions
raw agreement
linear weighted Cohen-style kappa
boundary disagreement count
fundamental disagreement count
```

Calibration is now emitted only against immutable model-adjudicated Silver references. It is diagnostic and is not a human-Gold accuracy estimate.

## Judge failure taxonomy

Future adjudication can distinguish:

```text
lexical_novelty_false_positive
scope_field_placement_false_positive
paraphrase_entailment_miss
bridging_inference_false_positive
unsupported_prediction_false_negative
causal_leap_false_negative
scope_expansion_false_negative
partial_support_collapsed
claim_boundary_mismatch
other
```

This determines whether Phase 7.4 should constrain extraction or whether the conditional Phase 7.3.2 `Semantic Judge Redesign` must happen first.

## Current result

```text
claim-source anchors      65
Reviewer A completed      true (GPT-4.1, 74 claims)
Reviewer B completed      true (Qwen 3.5 Plus, 77 claims)
adjudication completed    true (Gemini 2.5 Pro, 77/77 groups)
Judge calibration         complete against model Silver
strict safety matrix      TP=9 FP=1 FN=0 TN=0
strong error matrix       TP=2 FP=1 FN=0 TN=0 excluded=7
scope calibration         unavailable
held-out access           false
Prompt/Parser/Judge edits 0
runtime/Hermes            false
```

Decision:

```text
frozen_judge_diagnostic_calibration_complete
```

This is a diagnostic calibration against a three-model, model-adjudicated Silver reference set. It is not human Gold or Candidate semantic truth. The frozen Judge warns on all ten candidates, so high sensitivity coexists with zero observed specificity.

## Next valid action

The exact Silver-plus-frozen-Judge lineage is now declared and diagnostic calibration is complete. The next scientific decision must keep extractor and Judge changes separated; do not optimize either component against these same ten design cases without opening a new controlled phase.

Until then, do not:

- report Candidate semantic error rates;
- report Judge precision or recall;
- change the frozen scorer or its threshold;
- optimize the Prompt or Extractor;
- open held-out cases;
- persist or promote Pattern Candidates;
- connect Hermes or runtime learning.

## Artifact-lineage prerequisite

A completed Adjudication is invalid unless it references the exact SHA-256 values of Reviewer A, Reviewer B, and the preserved Agreement Report. Agreement must precede adjudication; adjudication must precede silver freezing; silver-label and frozen-Judge lineage must be valid before calibration is authorized. See `PHASE7_3_1_ARTIFACT_LINEAGE_TRANSITION_GATE.md`.
