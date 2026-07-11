# Phase 7.3 Failure Taxonomy & Candidate Error Analysis

Status: seed taxonomy and design-set error analysis complete; independent adjudication required; extraction changes and held-out access remain blocked.

## Objective

Phase 7.3 asks a scientific question rather than an engineering question:

> Why do contract-valid real-provider Pattern Candidates still receive high unsupported-claim warnings?

It does not optimize the prompt, rerun DeepSeek, change the parser or scorer, open held-out cases, or authorize learning. It reuses the exact ten frozen Phase 7.2.3 structured outputs.

## Permanent distinction

```text
Contract-valid Candidate
        !=
Semantically grounded Candidate
        !=
Validated knowledge
```

Phase 7.3 adds a second distinction:

```text
Candidate failure
        !=
Scorer warning
```

The frozen `unsupported_claim_rate` is a token-level proxy. It is useful as a review trigger, but it cannot by itself determine semantic entailment. Likewise, the frozen scope proxy can miss scope expressed in `proposition` or `source_domains` because it checks applicability-condition values.

## Frozen analysis conditions

```text
source execution       Phase 7.2.3 DeepSeek design run
candidates             10
provider calls         0
prompt changes         0
parser changes         0
scorer changes         0
algorithm changes      0
held-out access        false
persistence/runtime    false
annotation mode        single_reviewer_model_assisted_seed
independent reviewer   not completed
```

The annotation dataset pins every review to the exact `response_sha256` of the corresponding Phase 7.2.3 output. A changed provider output invalidates the annotations rather than silently reusing them.

## Failure taxonomy

The frozen taxonomy contains all requested classes, including zero-count classes:

```text
unsupported_generalization
scope_expansion
missing_evidence
weak_evidence
prediction_without_support
causal_leap
over_abstraction
counterexample_ignored
ambiguous_pattern
duplicate_pattern
other
```

Every label records severity, affected Candidate components, and a bounded rationale. Multiple labels may apply to one Candidate, but exactly one primary failure is selected for descriptive aggregation.

## Seed results

### Primary failure distribution

| Primary failure | Cases | Rate |
| --- | ---: | ---: |
| Prediction without support | 4 | 40% |
| Unsupported generalization | 3 | 30% |
| Causal leap | 2 | 20% |
| Over-abstraction | 1 | 10% |
| All other taxonomy classes | 0 | 0% |

Across primary and secondary labels:

```text
prediction_without_support  10/10
causal_leap                  9/10
unsupported_generalization  5/10
over_abstraction             1/10
```

This seed review suggests that the observed bottleneck is not evidence-ID handling. It is claim-strength control after evidence has already been read correctly.

### What was not the bottleneck

```text
missing/weak evidence labels       0/10
counterexample-ignored labels      0/10
evidence attribution accuracy      1.0000
evidence coverage                  1.0000
counterexample retention           1.0000
```

The model generally retained the supplied evidence graph. Errors appeared when converting evidence into generalized propositions and future predictions.

## Scorer confound analysis

The report records scorer confounds separately from Candidate failures:

| Confound | Cases | Rate |
| --- | ---: | ---: |
| Lexical novelty confound | 5 | 50% |
| Scope-field placement confound | 6 | 60% |

All ten Candidates exceeded the frozen lexical unsupported-warning threshold. Six received scope warnings. In the single-reviewer seed labels, none of those six scope warnings was confirmed as semantic `scope_expansion`; the source domain was preserved elsewhere in the structured Candidate.

This does not prove that the Candidates have perfect scope. It proves only that:

> The current scope warning is partly a field-placement check and must not be treated as semantic ground truth.

Likewise, `unsupported_claim_rate=0.5129` remains a valid safety alarm but is not a calibrated semantic hallucination probability.

## Falsifiability observation

Phase 7.3 separates structure from epistemic quality:

```text
falsification fields structurally present       10/10
falsification directly tests in-scope prediction 8/10
falsification semantic validity established       0/10
```

Two Candidates used an explicitly excluded counterexample as the falsification condition rather than describing failure inside the claimed scope. This shows why merely requiring a `falsification_conditions` JSON field is insufficient.

## Interpretation

The current evidence supports this provisional mechanism:

```text
Evidence is cited correctly
        ↓
Model compresses and connects observations
        ↓
Associations become guarantees
        ↓
Past outcomes become universal future predictions
        ↓
Scope and causal uncertainty are weakened
```

The dominant problem is therefore not transport, JSON, evidence lookup, or counterexample ID retention. It is epistemic-strength escalation during abstraction.

However, the current annotations are a transparent seed, not final scientific ground truth:

```text
reviewers                 1
independent adjudication  no
inter-rater agreement     unavailable
held-out evidence         unopened
```

## Decision

```text
taxonomy_seeded_independent_review_required
```

Do not optimize the prompt or extraction algorithm from these labels yet. The next valid action is independent adjudication of the ten frozen Candidates, followed by disagreement analysis and taxonomy revision if necessary.

Only after annotation agreement is measured should Phase 7.4 compare extraction strategies such as:

```text
Evidence
  -> Atomic propositions
  -> Evidence clusters
  -> Pattern Candidate
```

## Artifacts

```text
crates/eval/datasets/pattern_extraction/phase7_3_candidate_error_annotations.json
crates/eval/src/phase7_candidate_error_analysis.rs
crates/eval/src/bin/phase7_candidate_error_analysis.rs
crates/eval/tests/phase7_candidate_error_analysis_test.rs
crates/eval/reports/phase7_candidate_error_analysis.json
scripts/eval/phase7_candidate_error_analysis.py
docs/eval/PHASE7_3_FAILURE_TAXONOMY_CANDIDATE_ERROR_ANALYSIS.md
```

## Validation

```powershell
cargo test -p synapse-eval --test phase7_candidate_error_analysis_test -- --nocapture
python scripts/eval/phase7_candidate_error_analysis.py
```

Expected decision:

```text
taxonomy_seeded_independent_review_required
```
