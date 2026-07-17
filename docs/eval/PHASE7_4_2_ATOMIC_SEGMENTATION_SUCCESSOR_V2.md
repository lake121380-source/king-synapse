# Phase 7.4.2 Atomic Segmentation Successor v2

Status: bounded compatibility successor after v1 input-lineage failure

## Retained v1 failure

The v1 execution adapters passed protocol, query-blindness, environment, and
unit-test preflight. Execution stopped before the first overlay was constructed
because the Phase 7.4.1 prototype constructor and the frozen Phase 7.4 source
dataset use different canonical field names in the source-Memory hash material.

The source authoring contract uses:

```text
source_evidence_ids_sorted
source_event_ids_sorted
```

The prototype constructor uses:

```text
source_evidence_ids
source_event_ids
```

The sorted values are otherwise the same. The failure is classified as:

```text
input_lineage_failure / source_memory_hash_contract_mismatch
```

No v1 overlay, Atomic claim, Reference, Gold, arm output, state, receipt, or
effect score was written. The source dataset, query-blind projection, prototype
constructor, v1 Python adapter, v1 Rust adapter, and append-only failed attempt
remain immutable.

## Bounded v2 authority

v2 may introduce a new eval-only formal overlay compatibility contract that
validates the already frozen authoring source-Memory hash. It may not rewrite
the prototype or source data.

The formal contract version is:

```text
phase7.4-query-blind-sentence-segmentation-overlay-v2
```

Allowed changes are limited to:

- a new overlay JSON Schema v2 whose structure matches v1 except for the formal
  segmentation contract constant;
- a new Rust v2 constructor/validator owned by the eval crate;
- validation of the frozen authoring hash projection using the original sorted
  field names;
- overlay and claim IDs derived from the new contract constant;
- v2 dataset and audit namespaces.

The existing `aes-v1-` and `aes-claim-v1-` identity prefixes remain for
compatibility with the preregistered Gold schema. The digest material includes
the new formal contract version, so v1 and v2 identities cannot collide.

v2 may not change:

- source bytes, source Memory IDs, source Memory hashes, evidence IDs, event
  IDs, case selection, strata, or pool order;
- the query-blind projection;
- the sentence-boundary algorithm or two-unit expectation;
- Atomic spans, support placeholders, provenance, reconstruction, or authority
  flags;
- representation/evidence-coverage thresholds;
- query, Gold, Reference, or arm access;
- Provider, Runtime, Store, RecallEngine, or production-write authority.

## Disposition

A passing successor freeze authorizes only:

```text
execute_phase7_4_query_blind_atomic_segmentation_v2
```

v2 must still pass byte-identical replay, 1,680-overlay/3,360-unit counts, exact
span coverage, Schema, identity, provenance, placeholder, and authority Gates.
Another failure requires another recorded successor. Reference, Gold, arm
execution, effect scoring, Runtime Integration, productization, and release
remain unauthorized.
