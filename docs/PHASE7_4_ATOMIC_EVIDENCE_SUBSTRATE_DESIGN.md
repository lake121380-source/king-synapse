# Phase 7.4 Atomic Evidence Substrate Design

Status: `phase7_4_1_design_frozen_shadow_prototype_pending`

Phase 7.4 evaluates whether Atomic Evidence Substrate, validated in Support Localization tasks, provides measurable improvements when applied as an evidence representation layer inside King Recall memory evaluation workflows.

Phase 7.4 is a new capability-transfer validation stage. It is not a continuation, rerun, or extension of Phase 7.3.3-D. The predecessor remains frozen at:

```text
confirmatory_success_frozen_runtime_integration_not_authorized
```

The established result and the open question are deliberately separated:

```text
Established:
Atomic representation
        ↓
Support Localization task
        ↓
confirmed improvement

Unknown:
Atomic representation
        ↓
Memory Retrieval / Competition / Reflection
        ↓
system-level value?
```

Phase 7.4 therefore asks whether a validated evaluation capability can transfer into a useful, offline cognitive-system capability. It does not assume that transfer will occur.

## 1. Scope and non-goals

Phase 7.4 observes possible value before changing system behavior.

Permitted work is limited to:

- an eval-only shadow overlay;
- deterministic offline comparisons;
- new, independently frozen Phase 7.4 evaluation datasets;
- new evaluation metrics and audit artifacts;
- read-only reuse of existing retrieval, competition, and reflection evaluation interfaces;
- bounded prototype code that cannot enter a production path.

The following are prohibited throughout Phase 7.4:

- adding `MemoryKind::AtomicClaim` or any equivalent memory kind;
- modifying existing `MemoryKind` semantics;
- migrating or extending the persistent storage schema;
- modifying `RecallEngine` ranking, filtering, or retrieval behavior;
- modifying the production memory write path;
- persisting shadow claims as first-class memories;
- activating an Atomic score in runtime ranking;
- granting runtime, storage, learning, promotion, or autonomous-write authority;
- modifying any frozen Phase 7.3.3-D artifact;
- using Phase 7.3.3-D Confirmatory cases or Gold as Phase 7.4 effect data.

The only current authority is to freeze this design and subsequently construct an eval-only shadow prototype under a successor protocol.

## 2. Architecture position

Atomic Evidence is an explanatory evidence substrate owned by an existing Memory object. It is not a Memory replacement and does not independently participate in production recall.

```text
Existing Memory Object
│
├── existing content
├── existing MemoryKind
├── existing provenance
└── eval-only Evidence Substrate Overlay
    ├── Atomic Claim
    ├── Support State
    ├── Claim Provenance
    ├── Confidence
    └── Contradiction / obsolescence links
```

The ownership rule is:

```text
Memory owns content and runtime identity.
Atomic Evidence explains support structure in offline evaluation.
```

It is explicitly not:

```text
Atomic Evidence replaces Memory.
Atomic Claim becomes a production MemoryKind.
Atomic Evidence mutates RecallEngine output.
```

### 2.1 Shadow overlay contract

The prototype overlay must be derivable from a frozen Memory snapshot and must contain, at minimum:

- `overlay_id`;
- `source_memory_id`;
- `source_memory_sha256`;
- `segmentation_contract_version`;
- one or more ordered Atomic units;
- an exact source span or an explicit non-textual evidence locator for every unit;
- a Support State for every unit;
- provenance links restricted to the frozen source evidence set;
- separately named extraction and support confidence values;
- optional contradiction or obsolescence links whose targets are frozen source IDs.

Every overlay must be reproducible from the same inputs and configuration. An overlay has no storage authority, no promotion authority, and no runtime identity.

### 2.2 Support State

The Phase 7.4 shadow layer may use the frozen Support State vocabulary:

- `supported`;
- `partially_supported`;
- `unsupported`;
- `not_assessable`.

These values remain evidence diagnostics. They do not rewrite Memory content, confidence, kind, or persistence status.

### 2.3 Shadow scoring boundary

Any Atomic retrieval or competition score is diagnostic-only. A successor protocol must freeze its formula and bounds before outcome access. The score may be compared with an existing score but may not alter the base ranking.

The intended observation shape is:

```text
base ranking
    +
bounded Atomic Evidence shadow score
    =
shadow ranking for offline comparison only
```

## 3. Preregistered research questions

Phase 7.4 has three research questions. Each must be answered with a new Phase 7.4 dataset and a paired, deterministic offline comparison.

### RQ1 — Evidence Localization

Question:

> Does Atomic Evidence improve the ability to retrieve and localize the correct supporting evidence?

Comparison:

```text
Arm A: Chunk Retrieval
Arm B: Atomic Retrieval + Evidence Reconstruction
```

The RQ1 primary estimand is the paired difference in evidence-localization F1 at the frozen retrieval cutoff, `Arm B − Arm A`.

Required secondary metrics are:

- Recall@K;
- Precision@K;
- MRR;
- exact or span-IoU evidence localization accuracy;
- reconstruction completeness;
- query-level missingness and failure counts.

The cutoff K, span matching rule, sample size, uncertainty method, minimum detectable effect, and regression thresholds must be frozen in the Phase 7.4.2 protocol before selected effect content is opened.

### RQ2 — Unsupported or Contradictory Activation

Question:

> Does Atomic Evidence reduce activation of unsupported, contradictory, or obsolete memory evidence?

Comparison:

```text
Arm A: Chunk Retrieval
Arm B: Atomic Retrieval + Evidence Reconstruction
```

The RQ2 primary estimand is the paired reduction in unsupported activation rate, `Arm A − Arm B`, so a positive value favors Atomic Evidence.

Required secondary metrics are:

- contradiction exposure rate;
- obsolete evidence activation rate;
- false-confidence rate;
- supported-evidence retention;
- unsupported masking rate;
- query-level missingness and failure counts.

RQ2 must distinguish avoidance of bad evidence from accidental suppression of useful evidence. A reduction in unsupported activation cannot pass if supported-evidence recall violates its frozen non-inferiority bound.

### RQ3 — Cognitive Improvement

Question:

> Does Atomic Evidence improve memory competition and downstream reflection diagnostics?

Comparison:

```text
Arm C: existing Memory Competition
Arm D: existing Memory Competition + bounded Atomic Evidence shadow score
```

The RQ3 competition primary estimand is the paired difference in winner correctness, `Arm D − Arm C`.

Required competition metrics are:

- winner correctness;
- conflict-resolution accuracy;
- harmful winner rate;
- ranking stability;
- unsupported winner activation;
- score-bound compliance.

Required reflection diagnostics are:

- lesson quality;
- failure avoidance;
- future-influence accuracy;
- unsupported lesson rate;
- provenance completeness.

Reflection remains downstream and eval-only. It cannot write, promote, consolidate, or modify a Memory. A successor protocol must freeze whether reflection is a powered endpoint or a diagnostic endpoint before outcome access.

## 4. Frozen experimental arms

### Arm A — Chunk Retrieval

Arm A is the existing offline retrieval baseline over complete Memory chunks. Its implementation and configuration hashes must be frozen before Phase 7.4 effect data is opened.

### Arm B — Atomic Retrieval plus Evidence Reconstruction

Arm B retrieves Atomic units from the shadow overlay and reconstructs source Memory evidence without modifying the source Memory or base retrieval result.

Arm B must report both Atomic hits and reconstructed Memory hits. Reconstruction failure is an explicit failure class and cannot be silently dropped.

### Arm C — Existing Memory Competition

Arm C is the existing offline Memory Competition baseline. It must use the same candidate pool, source memories, and base scores as Arm D.

### Arm D — Memory plus Atomic Evidence Competition

Arm D adds a bounded Atomic Evidence shadow score for offline comparison. The existing Competition Engine output remains unchanged.

The score may use only prospectively frozen components such as:

- Support strength;
- evidence consistency;
- contradiction density;
- claim reliability;
- provenance completeness;
- obsolescence pressure.

Arm D must emit a separate shadow ranking and an exact score breakdown. It may not overwrite base scores or production winners.

### 4.1 Equality requirements

Paired arms must share:

- the same query and source Memory snapshot;
- the same candidate pool;
- the same retrieval cutoff where applicable;
- the same evaluation labels;
- the same missingness denominator;
- equivalent resource accounting;
- frozen deterministic seeds;
- identical visibility of all non-arm-specific inputs.

Outcome-dependent case replacement, silent dropping, semantic retry, and selective rerun are prohibited.

## 5. Phase 7.4 identifiability and opening gates

No effect conclusion is permitted until every applicable pre-effect Gate passes.

### 5.1 Representation Gate

The shadow representation must not degenerate into one whole-Memory unit per Memory.

The successor protocol must freeze and check at least:

- Atomic unit count greater than Memory chunk count;
- a minimum multi-unit Memory rate;
- a maximum whole-Memory span rate;
- unique, ordered, non-duplicated claim spans;
- deterministic reconstruction from Atomic units to source Memory IDs;
- zero unexplained span overlap or coverage gaps under the frozen boundary policy.

Failure is an authoritative structural negative result and blocks effect scoring.

### 5.2 Evidence Coverage Gate

Every scored Atomic unit must contain:

- a claim span or explicit locator;
- a Support State;
- source provenance;
- source Memory lineage;
- a frozen confidence interpretation;
- a reconstruction disposition.

Missing provenance or Support State cannot be imputed after arm execution.

### 5.3 Leakage Gate

Phase 7.3.3-D Confirmatory Gold is not Phase 7.4 effect data.

Permitted upstream use is limited to:

- parser and schema fixtures;
- protocol vocabulary;
- boundary and Support State contract tests;
- frozen rationale for choosing Atomic representation.

Prohibited upstream use includes:

- effect-size estimation for Phase 7.4;
- sample selection;
- model tuning;
- threshold tuning;
- retrieval or competition labels;
- Phase 7.4 power estimates unless explicitly justified by an independent non-effect pilot;
- any reuse of Confirmatory Candidate, Evidence, or Gold hashes in the effect dataset.

The Phase 7.4 dataset must use independent case IDs, source identities, Candidate hashes, Evidence hashes, and labels. Overlap is checked before content opening.

### 5.4 Dataset Opening Gate

Selected Phase 7.4 effect content may be opened only after all of the following are frozen:

- source inventory and eligibility policy;
- overlap audit corpus;
- selected IDs and hashes;
- all primary estimands and metric directions;
- sample size and power method;
- arm implementations and configurations;
- missingness and failure handling;
- cost accounting;
- analysis seeds and uncertainty method.

If inventory, representation, coverage, or leakage requirements fail, the dataset remains closed and no manual backfill is permitted in the same version.

### 5.5 Realized Identifiability Gate

After arm execution and before effect scoring, an offline Gate must confirm that:

- Arm A and B produced the required paired retrieval representations;
- Arm C and D used equal candidate pools;
- Atomic decisions remained local rather than whole-Memory fallbacks;
- source reconstruction remained deterministic;
- no pair was silently dropped;
- Gold and outcome labels were invisible during arm execution.

Failure blocks the affected estimand and is preserved as an authoritative negative result.

## 6. Statistical and decision discipline

RQ1 and RQ2 are the Phase 7.5 capability-entry family. Their family-wise one-sided alpha is `0.05`; the Phase 7.4.2 preregistration must freeze a valid multiplicity procedure before content opening. Holm-Bonferroni is the default unless a prospective successor contract provides a stronger justification.

RQ3 does not compensate for failure of both RQ1 and RQ2. It is evaluated only after its own identifiability and equality Gates pass.

Every primary result must report:

- paired effect estimate;
- preregistered uncertainty interval;
- preregistered p-value or decision statistic;
- all missing and failed pairs;
- arm-level resource use;
- exact dataset and implementation lineage;
- the outcome scope and prohibited generalizations.

Observed effect sizes may not be used to change the same-version sample size, threshold, metric, or case set.

## 7. Negative-result discipline

Phase 7.4 is designed to determine whether Atomic Evidence has system-level value, not to prove that it does.

### Positive result

At least one capability Gate passes under the frozen multiplicity rule, all regression and cost Gates pass, and Final Audit passes. This permits a separate Phase 7.5 design decision; it does not itself activate Runtime Integration.

### Neutral result

Atomic Evidence improves localization, provenance visibility, or explanation quality but does not improve a powered retrieval or activation endpoint. The layer may remain a diagnostic-only tool. Runtime Integration remains unauthorized.

### Negative result

Atomic Evidence adds complexity, cost, harmful suppression, instability, or unsupported activation without a measurable capability gain. The negative result is frozen. Runtime Integration remains unauthorized.

### Invalid or unidentifiable result

Representation, coverage, leakage, equality, or realized-identifiability requirements fail. Effect claims are blocked, the failure is classified, and same-version semantic retry is prohibited.

Transport failures before receipt of Provider content may resume only under the identical frozen manifest. The first received Provider content is authoritative. Repair, cherry-picking, selective rerun, and outcome-driven successor construction are prohibited.

## 8. Phase 7.5 entry conditions

Phase 7.5 Runtime Integration design may be considered only when every mandatory Gate below passes.

### Gate A — Capability benefit

At least one of RQ1 or RQ2 passes under the frozen family-wise error procedure. RQ3 alone is insufficient.

### Gate B — No severe regression

All prospectively frozen safety and non-inferiority bounds pass, including supported-evidence retention, harmful winner rate, ranking stability, and failure/missingness limits.

### Gate C — Acceptable cost

Latency, storage footprint, compute, reconstruction failure, and operational complexity remain within thresholds frozen before arm execution. USD cost may be reported only when Provider pricing was prospectively frozen.

### Gate D — Final Audit

Lineage, deterministic replay, data isolation, failure handling, arm equality, statistical procedure, and policy-boundary audits all pass.

Even when Gates A–D pass, Phase 7.4 authorizes only a Phase 7.5 design review. It does not authorize runtime code, storage migration, production writes, or rollout.

If any mandatory Gate fails, the terminal disposition remains:

```text
runtime_integration_not_authorized
```

## 9. Governance, versioning, and lineage

Phase 7.4 artifacts must be version-isolated and write-once. Frozen artifacts may be verified but not edited. Any semantic change requires a successor version that preserves the earlier result.

Every stage must provide:

- SHA256 lineage for all frozen inputs and outputs;
- deterministic replay fixtures;
- append-only, hash-chained audit events for execution attempts;
- explicit Provider visibility and call counts;
- explicit Runtime Integration, storage, and write-authority fields;
- failure classification and same-version retry disposition;
- a state and readiness transition whose next Gate is explicit.

The Phase 7.3.3-D predecessor is read-only and pinned by the machine-readable Design Contract. Its Confirmatory result is evidence for the motivation of Phase 7.4, not evidence for any Phase 7.4 effect conclusion.

## 10. Frozen Phase 7.4.1 disposition

This Design Freeze authorizes only the next bounded activity:

```text
construct_phase7_4_eval_only_shadow_prototype_protocol_v1
```

It does not authorize implementation in `RecallEngine`, modification of Memory Schema or `MemoryKind`, production persistence, production memory writes, or Runtime Integration.

Current Phase 7.4 state:

```text
phase7_4_1_design_frozen_shadow_prototype_pending
```

Current runtime disposition:

```text
runtime_integration_not_authorized
```
