# Phase 7.4.2 Independent Reference Protocol

Status: frozen before reviewer assignment or Reference execution

## Purpose

This protocol governs independent annotation of the 168 frozen Phase 7.4 cases
and 3,360 formal Atomic claims. It produces Reference judgments for query
relevance, support state, and localized source-Memory spans without exposing arm
outputs, retrieval scores, authoring roles, segmentation placeholders, or Phase
7.3.3-D effect data.

The entry Gate is:

```text
freeze_phase7_4_independent_reference_protocol_v1
```

A passing freeze authorizes only:

```text
collect_phase7_4_independent_reference_submissions_v1
```

## Reviewer independence

Reviewer A and Reviewer B must be distinct reviewers who did not author the
source cases, segmentation implementation, or evaluation arms. They must work
independently and must not see each other's assignments or outputs before both
submissions are frozen.

The adjudicator must be a third distinct reviewer. The adjudicator sees only
frozen disagreement items and the same blind evidence packet after A and B have
submitted. The adjudicator cannot be the source author, either reviewer, or an
arm implementer.

One person, one model session, copied submissions, coordinated annotation, or a
single output presented under multiple reviewer IDs does not satisfy
independence.

## Blind packet

The canonical packet includes, for every case:

- query text and exact query hash;
- source events and source evidence with provenance;
- ten frozen candidate Memory snapshots in pool order;
- two formal Atomic units per Memory with claim ID, exact text/hash, source
  span, and provenance.

The packet excludes:

- source-authoring domain and scenario-variant fields;
- author rationale or intended answer;
- segmentation `not_assessable` placeholder state and confidence;
- Reference, Gold, agreement, or adjudication labels;
- Arm A/B score, rank, output, failure, latency, or analysis;
- Phase 7.3.3-D content or labels;
- Runtime or productization data.

Case order is independently randomized for A and B using SHA256 order with
seeds `7402301` and `7402302`. Candidate Memories remain in frozen pool order,
and Atomic units remain in ordinal order.

## Annotation unit

Every one of the 3,360 Atomic claims must receive exactly one annotation:

- `support_state`;
- `query_relevant`;
- zero or more `evidence_spans` in the owning source Memory.

No claim may be omitted or deferred.

### Support states

- `supported`: the frozen source evidence entails the essential content of the
  claim in the stated scope and time.
- `partially_supported`: source evidence supports a material part but not every
  essential part or scope qualifier.
- `unsupported`: adequate source evidence for the claim is absent, without a
  credible direct conflict.
- `contradictory`: credible source evidence directly conflicts with an
  essential part of the claim.
- `not_assessable`: the evidence is incomplete, ambiguous, or incomparable so
  support versus contradiction cannot be determined.

Reviewers must ignore the segmentation placeholder as a judgment; it is not
included in the packet.

### Query relevance

`query_relevant=true` means the claim would materially help answer or calibrate
the frozen query if its support state were known. Relevance is judged separately
from truth: unsupported, contradictory, and not-assessable claims can still be
query-relevant.

### Evidence spans

Spans use zero-based half-open Unicode-scalar offsets into the owning
`source_memory_content`.

- For query-relevant `supported` or `partially_supported` claims, at least one
  non-empty in-bounds span is required.
- Those spans mark the exact source-Memory text that supplies localized useful
  evidence for the query.
- For query-irrelevant claims, spans must be empty.
- For `unsupported`, `contradictory`, or `not_assessable`, spans must be empty.
- Spans must be ordered, non-overlapping, unique, and contained within the
  Atomic claim's frozen source span.

Relevant Memory IDs are derived mechanically as Memory IDs containing at least
one query-relevant `supported` or `partially_supported` claim. Reviewers do not
enter a separate relevant-Memory list.

## Submission and freeze

Each submission must:

- contain all 168 cases and all 3,360 claims exactly once;
- match the reviewer's frozen case order;
- replay packet, worklist, claim, Memory, and span identities;
- contain no free-form rationale, Gold, arm output, or deferred item;
- be signed by a distinct reviewer identity declaration;
- be immutable after submission freeze.

Reviewer identities may be pseudonymous in public artifacts, but the local
assignment receipt must establish that A, B, and adjudicator are distinct and
not the source author. Credentials or personal data must not be committed.

## Agreement Gate

After both submissions are frozen, agreement is computed before adjudication:

- aggregate support-state Cohen's kappa at least `0.70`;
- support-state Cohen's kappa at least `0.60` in every stratum;
- aggregate span F1 at least `0.80` over claims where either reviewer supplies
  a span;
- exact query-relevance agreement is reported and all disagreements are routed
  to adjudication;
- no missing, duplicate, deferred, or lineage-invalid annotation.

If any threshold fails, Gold freeze is not authorized. The failure is retained
as an authoritative Reference failure; thresholds cannot be relaxed after
viewing agreement.

## Adjudication and Gold

Only disagreement items are adjudicated. The adjudicator selects or supplies a
valid final support state, query-relevance flag, and span set using the frozen
packet. All disagreements must be resolved and `deferred_count` must equal zero.

Gold is then constructed mechanically from adjudicated annotations and exact
agreements. Gold cannot be edited to improve retrieval or statistical results.
The dedicated Gold-freeze Gate remains separate from this protocol.

## Failure taxonomy

- `reviewer_independence_failure`;
- `reviewer_assignment_failure`;
- `packet_lineage_failure`;
- `submission_schema_failure`;
- `annotation_coverage_failure`;
- `claim_identity_failure`;
- `span_boundary_failure`;
- `label_rule_failure`;
- `missing_or_duplicate_annotation_failure`;
- `agreement_threshold_failure`;
- `adjudication_failure`;
- `deferred_item_failure`;
- `blindness_failure`;
- `provider_or_environment_failure`;
- `authority_boundary_failure`;
- `audit_failure`.

All attempts are append-only. Reviewer substitution after seeing agreement,
copied submissions, selective claim deletion, threshold relaxation, and
same-version relabeling are forbidden.

## Disposition

Protocol freeze and packet construction do not constitute Reference execution.
Until two genuinely independent submissions and a third-party adjudication are
available, Reference and Gold remain incomplete. This stage does not authorize
dataset opening for arms, retrieval execution, effect scoring, Runtime
Integration, productization, or release.
