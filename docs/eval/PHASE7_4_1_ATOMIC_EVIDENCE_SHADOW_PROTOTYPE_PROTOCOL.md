# Phase 7.4.1 Atomic Evidence Shadow Prototype Protocol

Status: `frozen_before_shadow_overlay_implementation`

This protocol operationalizes the Phase 7.4 Design Contract without implementing retrieval, competition, reflection, persistence, or runtime behavior.

Its sole purpose is to authorize a bounded eval-only constructor and validator for an Atomic Evidence Shadow Overlay.

## 1. Entry gate

The entry Gate is:

```text
phase7_4_1_design_frozen_shadow_prototype_pending
```

The authoritative design inputs are:

- `docs/PHASE7_4_ATOMIC_EVIDENCE_SUBSTRATE_DESIGN.md`;
- `crates/eval/config/phase7_4_design_contract_v1.json`;
- the frozen Phase 7.3.3-D terminal state, readiness, Final Audit report, and Final Audit receipt referenced by the Design Contract.

Phase 7.3.3-D is a read-only predecessor. Its cases, Candidate content, Evidence content, Gold, effect sizes, and labels are not prototype inputs.

## 2. Authorized prototype

The successor implementation may construct an in-memory, eval-only overlay from a frozen Memory snapshot and prospectively supplied Atomic units.

```text
immutable Memory snapshot
        +
prospective Atomic unit inputs
        ↓
validate IDs, spans, provenance, Support State, and confidence
        ↓
Atomic Evidence Shadow Overlay
        ↓
serialize evaluation artifact only
```

The prototype is a structural substrate. It does not extract claims, call a model, retrieve memories, rank candidates, calculate a competition bonus, or produce reflection lessons.

## 3. Implementation boundary

Implementation is restricted to the `synapse-eval` crate and Phase 7.4 evaluation adapters/tests.

Allowed implementation surfaces are:

```text
crates/eval/src/phase7_4_atomic_evidence_shadow.rs
crates/eval/src/bin/phase7_4_atomic_evidence_shadow.rs
crates/eval/tests/phase7_4_atomic_evidence_shadow_test.rs
scripts/eval/phase7_4_atomic_evidence_shadow_v1.py
crates/eval/datasets/phase7_4/**
crates/eval/reports/phase7_4_*
```

`crates/eval/src/lib.rs` may receive only the minimal module/export wiring required for the eval-only prototype.

Forbidden implementation surfaces include:

```text
crates/core/**
RecallEngine
RecallBooster
Memory / MemoryKind definitions
Store or storage adapters
production write paths
runtime configuration
runtime feature flags
```

No implementation may receive a mutable Memory, mutable `RecallHit`, `Store`, retriever, reranker, writer, or `RecallEngine` handle.

## 4. Input contract

The constructor input consists of two immutable objects.

### 4.1 Frozen Memory snapshot

Required fields:

- source Memory ID;
- existing MemoryKind (`fact`, `preference`, `failure`, `playbook`, or `state`);
- exact Memory content;
- SHA256 of the canonical source Memory snapshot;
- SHA256 of the exact UTF-8 content;
- frozen source evidence IDs;
- frozen source event IDs.

The input vocabulary cannot express `atomic_claim` as a MemoryKind.

### 4.2 Prospective Atomic unit inputs

Each unit supplies:

- exact claim text;
- ordinal position;
- either an exact source-Memory character span or a frozen source evidence ID;
- Support State;
- source evidence and event provenance;
- extraction confidence;
- support confidence;
- confidence calibration status;
- optional contradiction links.

The prototype validates these supplied units. It does not infer or repair them.

## 5. Deterministic identity

The overlay ID is:

```text
aes-v1-<sha256(
  "phase7.4" |
  source_memory_id |
  source_memory_sha256 |
  segmentation_contract_version
)>
```

An Atomic claim ID is:

```text
aes-claim-v1-<sha256(
  overlay_id |
  ordinal |
  claim_text_sha256
)>
```

The separator is the literal ASCII pipe character. Integer ordinals use base-10 ASCII without padding. Text hashes cover exact UTF-8 bytes without normalization.

The same canonical input must produce byte-identical canonical JSON and identical IDs across replays.

## 6. Validation rules

The constructor must reject an overlay when any of the following is true:

- source Memory or content hash mismatch;
- missing or unsupported MemoryKind;
- zero Atomic units;
- duplicate or non-contiguous ordinals;
- duplicate Atomic claim IDs;
- empty claim text;
- claim text hash mismatch;
- invalid or out-of-bounds source span;
- source excerpt does not equal the declared Memory span;
- overlapping source spans;
- evidence locator is not in the frozen source evidence set;
- provenance names an unknown evidence or event ID;
- provenance source Memory differs from the overlay owner;
- extraction or support confidence is non-finite or outside `[0, 1]`;
- Support State is outside the frozen vocabulary;
- reconstruction order differs from Atomic ordinal order;
- an undeclared reconstruction gap or overlap exists;
- an authority field claims runtime application, Memory mutation, Store write, RecallEngine mutation, or promotion.

Validation failure is explicit and deterministic. Inputs are not repaired, truncated, resegmented, relabeled, or silently dropped.

## 7. Output contract

Valid output must conform exactly to:

```text
crates/eval/config/phase7_4_atomic_evidence_shadow_overlay_schema_v1.json
```

The output records:

- owner Memory lineage;
- ordered Atomic units;
- exact locators;
- Support State;
- provenance;
- separately named extraction and support confidence;
- contradiction links;
- reconstruction status and accounting;
- constructor-controlled authority fields.

The authority block is always:

```text
eval_only = true
runtime_applied = false
memory_mutated = false
store_written = false
recall_engine_mutated = false
promotion_authorized = false
```

Input data cannot override these values.

## 8. Reconstruction boundary

Reconstruction maps ordered Atomic units back to their source Memory identity. It does not create a replacement Memory.

The prototype must preserve:

- ordered Atomic claim IDs;
- deterministic source-Memory ownership;
- explicit `complete`, `partial`, or `not_reconstructable` status;
- zero undeclared overlap;
- an explicit count for unresolved gaps.

A partial reconstruction is a valid diagnostic output only when every gap is explicit. It is never silently promoted to complete.

## 9. Prototype fixtures

The implementation successor must freeze fixtures before any Phase 7.4 effect dataset is constructed.

Required positive fixtures:

1. a two-unit Memory with exact non-overlapping spans;
2. an evidence-ID-located Memory with complete provenance;
3. deterministic byte-for-byte replay;
4. explicit partial reconstruction with declared gaps;
5. all five existing MemoryKind values.

Required rejection fixtures:

1. source Memory hash mismatch;
2. claim text hash mismatch;
3. out-of-bounds span;
4. overlapping spans;
5. duplicate or skipped ordinal;
6. unknown provenance ID;
7. confidence outside bounds or non-finite;
8. `atomic_claim` MemoryKind;
9. attempted runtime or mutation authority;
10. whole-Memory single-unit degeneracy in a Representation-Gate fixture.

The whole-Memory case may be structurally serializable for diagnostic accounting, but it must fail the separate prototype Representation Gate and cannot authorize Phase 7.4 effect work.

## 10. Prototype Gate

The implementation Gate requires all of the following:

- schema conformance;
- deterministic IDs and canonical serialization;
- positive fixtures accepted;
- rejection fixtures rejected with frozen reason codes;
- no Store, RecallEngine, runtime, or write-path dependency;
- no new MemoryKind;
- no Provider call;
- no Phase 7.3.3-D effect-data access;
- zero runtime, persistence, mutation, promotion, and learning authority;
- source reconstruction lineage complete;
- version-isolated artifacts and SHA256 manifest;
- deterministic replay and audit receipt PASS.

Failure freezes an authoritative prototype-contract negative result. Same-version semantic repair is prohibited.

## 11. Failure taxonomy

Frozen failure classes are:

- `input_lineage_failure`;
- `source_hash_failure`;
- `claim_hash_failure`;
- `span_boundary_failure`;
- `span_overlap_failure`;
- `ordinal_failure`;
- `provenance_failure`;
- `support_state_failure`;
- `confidence_failure`;
- `reconstruction_failure`;
- `representation_degeneracy`;
- `schema_contract_failure`;
- `authority_boundary_failure`;
- `implementation_dependency_failure`;
- `determinism_failure`;
- `leakage_failure`.

The first deterministic validation outcome is authoritative for the frozen input. Selective fixture removal or relabeling requires a successor version.

## 12. Data and Provider status

At protocol freeze:

```text
Phase 7.4 effect dataset opened = false
Phase 7.4 effect Provider called = false
Phase 7.3.3-D effect data loaded = false
Prototype implementation started = false
Runtime Integration authorized = false
```

The implementation successor uses synthetic contract fixtures only. New effect data remains prohibited until the later inventory, leakage, identifiability, preregistration, and opening Gates pass.

## 13. Exit gate

Protocol Freeze PASS authorizes only:

```text
implement_phase7_4_eval_only_shadow_overlay_v1
```

It does not authorize Atomic retrieval, Evidence Reconstruction evaluation, Atomic competition scoring, reflection evaluation, effect-data opening, Provider execution, `RecallEngine` integration, storage migration, or Runtime Integration.
