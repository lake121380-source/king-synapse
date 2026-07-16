# Phase 7.4.2 Offline Retrieval Evaluation Protocol

Status: frozen before independent source inventory and before effect content

## 1. Purpose

This protocol evaluates whether the Phase 7.4 Atomic Evidence representation
improves offline memory-evidence retrieval and reduces unsupported or
contradictory activation relative to whole-chunk retrieval.

It preregisters RQ1 and RQ2. It does not open, select, label, score, or inspect
Phase 7.4 effect cases. It does not authorize Provider calls, Runtime
Integration, Store writes, Memory schema changes, RecallEngine changes, ranking
changes, learning, promotion, or autonomous behavior.

The entry state is:

```text
m0_governance_baseline_frozen_phase7_4_2_protocol_freeze_authorized
```

The Phase 7.3.3-D predecessor remains immutable and is not effect evidence for
this protocol.

## 2. Research questions

### RQ1 — Evidence Localization

Does Atomic Retrieval plus Evidence Reconstruction improve localization of the
supporting evidence span relative to Chunk Retrieval?

Primary estimand:

```text
mean(case_localization_f1_arm_b - case_localization_f1_arm_a)
```

The minimum practically relevant effect is `+0.05` absolute paired F1.

### RQ2 — Unsupported or Contradictory Activation

Does Atomic Retrieval plus Evidence Reconstruction reduce activation of claims
that the frozen Gold classifies as unsupported or contradictory, while
preserving supported-evidence recall?

Primary estimand:

```text
mean(case_unsupported_activation_rate_arm_a
     - case_unsupported_activation_rate_arm_b)
```

The minimum practically relevant reduction is `+0.03` absolute. Supported
evidence recall uses a non-inferiority margin of `-0.02` for `Arm B - Arm A`.

RQ1 and RQ2 are one confirmatory family. RQ3 is not part of this execution and
cannot compensate for failure of this family.

## 3. Experimental units and sampling

The paired experimental unit is one independently authored Phase 7.4 case.
Each case contains:

- one query;
- exactly ten candidate Memory snapshots;
- the same candidate pool for both arms;
- frozen Atomic overlays constructed from source Memory content without access
  to the query, effect labels, or arm outcomes;
- independent claim-level Gold support and contradiction annotations;
- at least one Gold-supported memory and at least one hard distractor.

Target selected sample size: `168` cases.

Minimum analyzable paired sample size: `160` cases.

There are eight preregistered strata with a target of 21 selected cases and a
minimum of 20 analyzable cases per stratum:

1. temporal update;
2. contradiction;
3. preference evolution;
4. failure learning;
5. causal reasoning;
6. multi-entity reasoning;
7. uncertainty boundary;
8. adversarial lexical overlap.

No stratum may be removed, merged, renamed, or reweighted after effect content
is opened. The primary estimand is the equal-weight case mean. Stratum results
are mandatory diagnostics and do not form additional confirmatory hypotheses.

## 4. Design power and MDE

The design assumes a paired-difference standard deviation no larger than
`0.20`. With `n = 160`, a conservative one-sided per-hypothesis alpha of `0.025`
and power `0.80`, the normal-approximation MDE is approximately `0.0443`:

```text
(z_0.975 + z_0.80) * 0.20 / sqrt(160)
```

The protocol rounds the practical RQ1 threshold upward to `0.05`. RQ2 uses a
`0.03` practical threshold because unsupported activation is a directly bounded
rate and additionally must pass supported-recall non-inferiority.

This is a design calculation, not an effect estimate. Phase 7.3.3-D effect data
was not used for MDE or power selection.

## 5. Arm definitions

### Arm A — Chunk Retrieval

Arm A scores each of the ten complete candidate Memory texts and returns the top
five Memory identities. A retrieved chunk exposes all Gold claims contained by
that Memory for activation accounting. For localization accounting, its
retrieved evidence interval is the complete source Memory span.

### Arm B — Atomic Retrieval plus Evidence Reconstruction

Arm B scores frozen Atomic units belonging to the same ten candidate Memories.
It reconstructs Memory results by:

1. ordering Atomic units by the frozen retrieval score;
2. grouping units by source Memory identity;
3. assigning a Memory the maximum score of its retrieved Atomic units;
4. breaking Memory-score ties by frozen candidate-pool ordinal;
5. returning the top five reconstructed Memory identities;
6. exposing only the selected Atomic spans for localization and activation
   accounting.

Arm B cannot infer, repair, drop, relabel, merge, or resegment Atomic units.
Overlay validation failure is an explicit execution failure.

## 6. Equality and isolation requirements

Both arms use identical:

- case and query bytes;
- candidate Memory identities and source hashes;
- candidate-pool order;
- tokenizer and query normalization;
- retrieval scoring formula and numeric precision;
- cutoff `K = 5` reconstructed Memory results;
- hardware process, timeout, and measurement clock;
- tie-breaking policy;
- failure logging and output schema.

Arm B necessarily scores more representation units. That extra work is the
treatment cost and is measured; it is not hidden by truncating the Atomic unit
pool. Equal-resource means equal source pool, environment, timeout, and result
budget, not equal internal operation count.

The evaluation implementation and every scoring parameter must be hash-frozen
before selected effect content is opened.

## 7. Frozen retrieval semantics

The primary lane is deterministic, offline, local, and Provider-free.

Before the Dataset Opening Gate, the implementation freeze must define:

- Unicode normalization: none;
- case folding: Unicode lowercase;
- token boundary rule;
- punctuation handling;
- CJK token handling;
- document-frequency calculation over the ten-case candidate pool;
- the exact deterministic scoring formula;
- score precision and rounding;
- candidate and Atomic tie-breaking;
- empty-query and zero-token behavior.

No embedding model, reranker, network service, LLM, or external Provider is
authorized by this v1 protocol. Adding one requires a successor protocol frozen
before effect content is opened.

## 8. Gold and metric definitions

### 8.1 Claim labels

Each Gold claim has one frozen state:

- `supported`;
- `partially_supported`;
- `unsupported`;
- `contradictory`;
- `not_assessable`.

The first two are supported for supported-recall accounting. `unsupported` and
`contradictory` count as harmful exposure. `not_assessable` is reported
separately and is not silently mapped to either class.

### 8.2 Evidence localization F1

For each case, the predicted character set is the union of source-character
intervals exposed by the top-five results. The Gold character set is the union
of Gold-supported or partially-supported evidence intervals for the query.

```text
precision = |predicted ∩ gold| / |predicted|
recall    = |predicted ∩ gold| / |gold|
f1        = 2 * precision * recall / (precision + recall)
```

Empty-set rules:

- Gold cannot be empty by sampling contract;
- an empty prediction has precision `0`, recall `0`, and F1 `0`;
- character positions are Unicode scalar-value ordinals, not UTF-8 byte offsets.

### 8.3 Unsupported activation rate

For each case:

```text
unsupported_activation_rate =
  activated unsupported-or-contradictory Gold claims
  / all activated assessable Gold claims
```

For Arm A, retrieving a chunk activates every assessable Gold claim in that
chunk. For Arm B, only Atomic units selected into the reconstructed top-five
evidence set are activated. Duplicate claim exposure counts once per case.

### 8.4 Supported-evidence recall

```text
supported_evidence_recall =
  activated supported-or-partially-supported Gold claims
  / all Gold supported-or-partially-supported claims
```

### 8.5 Secondary metrics

- Memory Recall@1, Recall@3, and Recall@5;
- Memory MRR@5;
- evidence Precision@5 and Recall@5;
- contradiction exposure rate;
- not-assessable exposure rate;
- reconstruction failure rate;
- deterministic replay rate;
- per-case and aggregate latency;
- scored representation-unit count;
- peak process memory delta;
- serialized overlay-to-source byte ratio.

Secondary metrics cannot rescue a failed primary Gate.

## 9. Statistical analysis

### 9.1 Hypothesis tests

RQ1 and RQ2 use one-sided paired sign-flip permutation tests.

- exact enumeration is used when feasible;
- otherwise 100,000 Monte Carlo sign flips are used;
- seed: `7402001`;
- the observed assignment is included;
- p-values use the plus-one correction;
- calculations use IEEE-754 binary64;
- no intermediate rounding is permitted.

### 9.2 Multiplicity

Holm-Bonferroni controls family-wise one-sided alpha at `0.05` across RQ1 and
RQ2. Hypotheses are ordered by raw p-value, with `RQ1` before `RQ2` as the
deterministic tie-breaker.

### 9.3 Confidence intervals

Paired percentile bootstrap intervals use:

- 20,000 resamples;
- seed `7402002`;
- case-level paired resampling;
- equal-weight case means;
- a two-sided 95% interval for effect reporting;
- one-sided 95% lower bounds for practical-effect and non-inferiority Gates.

Bootstrap results are descriptive uncertainty evidence; the frozen permutation
tests plus practical thresholds determine confirmatory capability passage.

### 9.4 Passage rules

RQ1 passes only when:

- its Holm-adjusted one-sided p-value is at most `0.05`;
- mean paired localization F1 improvement is at least `0.05`;
- its one-sided 95% lower bound is greater than `0`.

RQ2 passes only when:

- its Holm-adjusted one-sided p-value is at most `0.05`;
- mean unsupported-activation reduction is at least `0.03`;
- its one-sided 95% lower bound is greater than `0`;
- the one-sided 95% lower bound for `Arm B - Arm A` supported-evidence recall is
  greater than `-0.02`.

At least one of RQ1 or RQ2 must pass for the Phase 7.4 capability-entry family.

## 10. Missing data and execution failures

All selected cases remain in accounting.

- zero selective reruns;
- zero selective case deletion;
- zero silent parser or reconstruction repair;
- maximum total unpaired or structurally unusable case rate: `5%`;
- minimum analyzable cases: `160`;
- minimum analyzable cases per stratum: `20`.

If any minimum is missed, the Realized Identifiability Gate fails and primary
effect scoring is not authoritative.

Arm-specific failure sensitivity is conservative:

- an Arm B-only localization failure receives Arm B localization F1 `0`;
- an Arm B-only activation failure receives Arm B unsupported rate `1` and
  supported recall `0`;
- an Arm A-only failure is classified as pair unidentifiable and cannot be
  removed from failure-rate accounting;
- a shared infrastructure failure is classified separately and cannot be
  silently replaced.

Complete-pair analysis is reported only as sensitivity evidence.

## 11. Pre-effect Gates

### 11.1 Representation Gate

- aggregate Atomic unit count must exceed Memory chunk count;
- no selected case may consist solely of one whole-Memory Atomic unit;
- query and Gold labels were not used during Atomic segmentation;
- overlay IDs and claim IDs replay exactly.

### 11.2 Evidence Coverage Gate

- every selected Memory has exact content SHA-256;
- every Atomic unit has a valid source locator and source provenance;
- all Gold evidence intervals are in bounds;
- all support labels are within the frozen vocabulary;
- all selected cases have supported Gold evidence;
- no undeclared span overlap or reconstruction gap exists.

### 11.3 Reference Gate

Two blind reviewers are required.

- aggregate span F1 agreement must be at least `0.80`;
- aggregate support-state Cohen kappa must be at least `0.70`;
- no stratum kappa may be below `0.60`;
- every disagreement is adjudicated or explicitly deferred;
- Gold cannot freeze with a deferred item.

### 11.4 Leakage Gate

The new source inventory is compared with all Phase 7.3.3-D selected,
confirmatory, worklist, and Gold inventories.

- exact case-ID overlap: `0`;
- exact source-ID overlap: `0`;
- exact normalized source-text hash overlap: `0`;
- exact Candidate hash overlap: `0`;
- exact Evidence hash overlap: `0`;
- label or adjudication lineage reuse: `0`;
- normalized five-gram Jaccard above `0.85` is manually adjudicated before
  selection and cannot remain unresolved.

### 11.5 Dataset Opening Gate

Effect content may be opened only after all of the following are frozen:

- source inventory and sampling frame;
- selection algorithm and seed;
- case/worklist and Gold schemas;
- Atomic segmentation implementation;
- Arm A and Arm B implementation hashes;
- metrics and statistical implementation hashes;
- execution environment and cost accounting;
- all pre-effect Gate reports and receipts.

## 12. Realized Identifiability Gate

This Gate runs after both arms complete and before effect scoring.

It requires:

- the same case IDs, query hashes, candidate-pool hashes, and cutoffs;
- no Gold or arm-output access by segmentation;
- both arms used their frozen implementation and environment hashes;
- Arm B produced non-degenerate Atomic exposure;
- at least 160 analyzable pairs and 20 per stratum;
- total unusable rate at most 5%;
- no systematic arm-specific timeout or parse-failure imbalance;
- all failure classes and resource counts are complete;
- the canonical semantic projection replays byte-identically. Timing and memory
  telemetry are excluded from the semantic projection and are tolerance-audited
  separately.

Failure blocks the affected estimand and freezes an authoritative invalid or
unidentifiable result.

## 13. Regression and cost Gates

### Regression limits

- the one-sided 95% lower bound for Memory Recall@5 `Arm B - Arm A` must be
  greater than `-0.02`;
- mean MRR@5 regression may not be worse than `-0.03`;
- harmful unsupported activation may not increase by more than `0.01` in any
  stratum;
- deterministic replay rate must be `1.00`;
- lineage failure count must be `0`;
- reconstruction failure rate must be at most `0.01`.

### Cost limits

- p95 Arm B latency divided by p95 Arm A latency must be at most `2.0`;
- p95 absolute latency increase must be at most `20 ms` in the frozen local
  deterministic lane;
- peak process memory delta must be at most `256 MiB` and at most `2.0x` Arm A;
- mean scored Atomic units divided by scored chunks must be reported and must
  not exceed `8.0`;
- serialized Atomic overlay bytes divided by source Memory bytes must not exceed
  `6.0` for the frozen evaluation artifact;
- Provider cost is exactly zero in v1.

Passing a cost Gate does not authorize Runtime behavior.

## 14. Failure taxonomy

Every failure uses one frozen class:

- `input_lineage_failure`;
- `selection_failure`;
- `leakage_failure`;
- `reference_failure`;
- `representation_failure`;
- `evidence_coverage_failure`;
- `structural_identifiability_failure`;
- `environment_failure`;
- `arm_equality_failure`;
- `timeout_failure`;
- `retrieval_failure`;
- `reconstruction_failure`;
- `unsupported_activation_accounting_failure`;
- `metric_failure`;
- `determinism_failure`;
- `realized_identifiability_failure`;
- `power_failure`;
- `regression_failure`;
- `cost_failure`;
- `audit_failure`.

## 15. Output, privacy, and audit

Only sanitized protocol, schema, manifest, aggregate, state, readiness, audit,
and receipt artifacts may be committed.

Each case output carries `output_sha256` over the canonical semantic projection:
case identity, query and candidate-pool hashes, status, failure class, ranked
memories, activated claims and spans, scores, and scored-unit count. `latency_ns`
and aggregate resource telemetry are excluded from this semantic hash because
wall-clock measurements are observational rather than deterministic. They
remain mandatory cost evidence.

The following remain prohibited:

- credentials;
- raw Provider requests or responses;
- private source data;
- unlicensed third-party content;
- local absolute paths in portable artifacts;
- timestamps or nondeterministic identifiers in canonical result hashes;
- overwritten attempt logs;
- omitted failures.

## 16. M1 disposition

Freezing this protocol authorizes only:

```text
construct_phase7_4_independent_source_inventory_and_sampling_frame_v1
```

It does not authorize selected effect-content opening, Reference review,
retrieval execution, effect scoring, Provider calls, Runtime Integration,
storage migration, production writes, productization, or release.
