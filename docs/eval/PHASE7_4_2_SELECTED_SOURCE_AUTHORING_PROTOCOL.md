# Phase 7.4.2 Selected Source Authoring Protocol

Status: authoring contract frozen before selected source content exists

## Purpose

This protocol governs creation of the 168 selected Phase 7.4 source cases after
the content-blind inventory and sampling frame have been frozen. It fixes the
case structure, domain balance, identity namespaces, candidate-pool ordering,
content boundaries, and authoring validation rules before any query, source
event, evidence text, or Memory text is written.

The entry Gate is:

```text
freeze_phase7_4_selected_source_authoring_contract_v1
```

Passing this Gate authorizes only:

```text
author_phase7_4_selected_source_cases_v1
```

## Frozen authoring plan

The selected worklist remains exactly 168 cases, with 21 cases in each of the
eight preregistered strata. Selection cannot be changed by content.

Within every stratum, the frozen selection rank assigns one of seven synthetic
domains and one of three scenario variants:

| Domain | Role |
| --- | --- |
| `software_delivery` | releases, incidents, and implementation decisions |
| `data_operations` | pipelines, quality checks, and data handling |
| `customer_support` | service observations and response decisions |
| `procurement` | vendor, cost, and contract evidence |
| `team_process` | staffing, workflow, and coordination evidence |
| `research_planning` | experiments, observations, and planning decisions |
| `personal_workflow` | local productivity preferences and outcomes |

For selection rank `r` from 1 through 21:

```text
domain = domains[(r - 1) mod 7]
scenario_variant = floor((r - 1) / 7) + 1
```

Every stratum therefore contains exactly three cases from every domain and one
case for every domain/variant pair. Domain and variant are design controls, not
Gold labels.

Each case receives content-blind identity slots for:

- one query;
- four synthetic entities;
- six source events;
- eight source-evidence records;
- ten candidate Memory snapshots.

The ten Memory slots contain exactly two instances of every existing
`MemoryKind`: `fact`, `preference`, `failure`, `playbook`, and `state`. Kind
assignment rotates by frozen selection rank. It does not add a MemoryKind or
change the production schema.

Candidate pool order is independent of authored content. For every Memory slot,
compute:

```text
sha256("phase7.4|7402201|" + case_id + "|" + source_memory_id)
```

Sort by this digest and then by `source_memory_id`; assign zero-based pool
ordinals. Pool order cannot be repaired after content is observed.

## Source-case content

Every authored case must conform to
`phase7_4_source_authoring_case_schema_v1.json` and must contain only synthetic,
repository-owned text.

Required content includes:

- a non-empty English query;
- four case-local synthetic entities;
- six logically ordered source events;
- eight evidence records with provenance kind and stable locator;
- ten Memory snapshots linked to one or more frozen evidence and event IDs;
- exact UTF-8 SHA256 values for every authored text field;
- a canonical source-Memory hash over identity, kind, content, evidence IDs,
  and event IDs.

The authored source package must not contain:

- relevant-Memory labels;
- support-state labels;
- query-relevance labels;
- evidence-span Gold;
- expected answers;
- Atomic claim boundaries or Atomic overlay IDs;
- arm scores, rankings, outputs, or analysis fields;
- author rationale that reveals the intended answer;
- Phase 7.3.3-D content, IDs, labels, Gold, or adjudication lineage.

## Stratum construction constraints

These constraints govern scenario construction but do not encode per-case Gold:

- `temporal_update` includes multiple logical times and plausible stale
  information without marking which Memory is current.
- `contradiction` includes provenance-bearing statements that cannot all be
  accepted simultaneously.
- `preference_evolution` includes a preference before and after an outcome or
  decision event.
- `failure_learning` includes an attempted action, observed outcome, and
  contextual alternatives without an authored lesson label.
- `causal_reasoning` separates temporal association, intervention, and outcome
  evidence.
- `multi_entity_reasoning` includes at least three active entities and plausible
  cross-entity attribution distractors.
- `uncertainty_boundary` includes evidence that supports calibrated uncertainty
  and plausible overstatement.
- `adversarial_lexical_overlap` includes high-overlap irrelevant material and
  lower-overlap relevant evidence without storing either role.

Every case must be semantically answerable from its frozen source records, but
the source author may not emit the answer or any support/relevance label. The
independent Reference stage determines those labels.

## Blindness and separation

The authoring lane may read only:

- the Phase 7.4 authoring contract, schema, and blank authoring plan;
- the selected case IDs, strata, domain/variant assignments, and blank slots;
- the preregistered public protocol constraints needed to author valid cases.

It may not read or load:

- any Phase 7.3.3-D effect dataset or evaluation result;
- future reviewer submissions, agreement reports, adjudication, or Gold;
- Atomic segmentation output;
- Arm A or Arm B output;
- paired statistics or Gate decisions.

Query and source content may be authored together, but future Atomic
segmentation receives a memory-only projection with query bytes removed. Gold
and arm execution remain closed throughout authoring.

## Mechanical authoring validation

Before authored cases can be frozen, a successor validator must establish:

- exact selected-worklist coverage and no reserve case use;
- exact domain, variant, entity, event, evidence, Memory identity, kind, and
  pool-order agreement with the frozen blank plan;
- JSON Schema validity and exact SHA256 replay;
- unique case-local and dataset-wide IDs where required;
- all evidence/event references resolve within the same case;
- every source evidence record is referenced by at least one Memory;
- all Memory contents and queries are non-empty and within frozen size bounds;
- no forbidden label, Gold, Atomic, arm-output, analysis, or rationale fields;
- no exact duplicate normalized query, Memory, event, or evidence text across
  cases;
- no unresolved normalized five-gram Jaccard pair at or above `0.85` across
  different cases;
- no exact ID, normalized text hash, Candidate hash, or Evidence hash overlap
  with Phase 7.3.3-D;
- Provider, network, Runtime, Store, and RecallEngine handles were not used.

The Phase 7.3.3-D comparison is performed only by a dedicated leakage auditor
after Phase 7.4 source content has been frozen. The authoring lane itself does
not load Phase 7.3.3-D content.

## Failure policy

Authoring failures are classified as one of:

- `input_lineage_failure`;
- `authoring_plan_mismatch`;
- `case_schema_failure`;
- `identity_or_hash_failure`;
- `content_completeness_failure`;
- `reference_resolution_failure`;
- `forbidden_label_or_rationale_failure`;
- `duplicate_or_similarity_failure`;
- `stratum_construction_failure`;
- `leakage_boundary_failure`;
- `provider_or_environment_failure`;
- `authority_boundary_failure`;
- `audit_failure`.

Failures are append-only. A failed selected case cannot be silently deleted,
replaced by a reserve case, or repaired after Reference or arm output is seen.
Semantic repair requires an explicitly authorized successor version. Same-
version content-driven reselection is prohibited.

## Disposition

Freezing this contract does not itself author or open source content. A passing
contract Gate authorizes the bounded authoring lane only. It does not authorize
Atomic segmentation, Reference review, Gold freeze, leakage clearance, dataset
opening for arms, effect scoring, Provider access, Runtime Integration,
productization, or release.

