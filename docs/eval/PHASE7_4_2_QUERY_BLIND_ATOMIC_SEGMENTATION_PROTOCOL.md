# Phase 7.4.2 Query-Blind Atomic Segmentation Protocol

Status: frozen before Atomic segmentation execution

## Purpose

This protocol freezes the deterministic, query-blind transformation from the
168 frozen Phase 7.4 source cases into eval-only Atomic Evidence Shadow
Overlays. It reuses the validated Phase 7.4.1 overlay constructor contract and
does not modify Memory, Store, RecallEngine, Runtime, or the production write
path.

The entry Gate is:

```text
freeze_phase7_4_query_blind_atomic_segmentation_protocol_v1
```

A passing protocol freeze authorizes only:

```text
execute_phase7_4_query_blind_atomic_segmentation_v1
```

## Frozen source

The only source dataset is:

```text
crates/eval/datasets/phase7_4/phase7_4_selected_source_cases_v2.json
sha256 b06ff2ceb1d300561df937f73a1e9de9d8f5c9d6ca19cb57069b63acc834256d
```

The v1 authoring draft remains a retained failed attempt and is not an input.
No reserve case, Phase 7.3.3-D content, reviewer submission, Gold, arm output,
or analysis artifact may be read.

## Query-blind projection

Protocol freeze creates a deterministic memory-only projection containing:

- case ID and stratum;
- source Memory ID, frozen MemoryKind, pool ordinal, content, content SHA, and
  Memory SHA;
- source evidence IDs and event IDs;
- the frozen source-dataset and authoring-manifest hashes.

The projection contains no query ID, query text, expected answer, relevance
label, support state, Gold span, Atomic output, arm score, or analysis field.
Segmentation execution may read only this projection plus the frozen protocol,
schema, and eval-only constructor implementation.

## Segmentation algorithm

The formal algorithm ID is:

```text
phase7.4-query-blind-sentence-segmentation-v1
```

For every source Memory, operate on Unicode scalar values without Unicode
normalization:

1. Scan from the first scalar to the last.
2. Treat `.`, `?`, and `!` as sentence terminators.
3. A terminator closes a unit only when followed by whitespace or end of text.
4. Include the terminator and all immediately following whitespace in the
   closing unit.
5. The next unit begins at the first non-whitespace scalar.
6. The final unit must end at the source Memory's scalar count.
7. Empty units, overlapping spans, uncovered characters, and reordered spans
   are failures.
8. No abbreviation, language-model, query-aware, Gold-aware, or semantic merge
   heuristic is allowed.

The frozen source corpus is expected to produce exactly two units per Memory.
This expectation is a Gate, not a repair instruction. A different count fails
the same version.

## Overlay compatibility contract

Every segmented Memory is passed through the already validated Phase 7.4.1
eval-only overlay contract:

```text
phase7.4-atomic-evidence-shadow-prototype-v1
```

The existing overlay and Atomic claim identities remain:

```text
overlay_id = aes-v1-sha256(
  "phase7.4|" + source_memory_id + "|" + source_memory_sha256 + "|" +
  "phase7.4-atomic-evidence-shadow-prototype-v1"
)

atomic_claim_id = aes-claim-v1-sha256(
  overlay_id + "|" + ordinal + "|" + claim_text_sha256
)
```

The formal sentence algorithm is recorded in the dataset manifest and receipt;
it does not rewrite the already frozen constructor constant or identity scheme.

## Non-label placeholder fields

Segmentation does not decide support. Every prospective unit uses:

- `support_state = not_assessable`;
- `support_confidence = 0.0`;
- `confidence_calibration_status = not_assessable`;
- `extraction_confidence = 1.0` for exact deterministic spans;
- empty contradiction links;
- the owning Memory's frozen evidence and event IDs as provenance.

These fields are segmentation placeholders, not Gold and not effect data.
Independent Reference later assigns the five preregistered Gold support states,
including `contradictory`, without reading the placeholder as a judgment.

## Representation and coverage Gate

Execution must establish all of the following before Reference is authorized:

- 168 cases and 1,680 source Memory snapshots are covered exactly once;
- exactly 3,360 Atomic units are emitted;
- every Memory emits exactly two units;
- total Atomic units exceed total Memory chunks;
- no Memory is represented as a single whole-Memory Atomic unit;
- source spans are in bounds, ordered, non-overlapping, and cover every Unicode
  scalar exactly once;
- reconstruction is `complete`, deterministic, and has zero unresolved gaps;
- every overlay, claim ID, claim hash, Memory hash, and canonical JSON byte
  projection replays exactly;
- every provenance evidence/event ID belongs to the owning Memory;
- every overlay passes the frozen JSON Schema and Rust integrity validator;
- query, Gold, Reference, arm output, and Phase 7.3.3-D content access counts are
  zero;
- Provider, network, Runtime, Store, RecallEngine, and write access counts are
  zero.

Failure freezes an authoritative segmentation or representation negative result
for that version. Units cannot be merged, split, dropped, or relabeled after a
failure.

## Execution environment

Execution is local, offline, deterministic, CPU-only, and Provider-free. The
Rust toolchain, Python toolchain, OS build, and hardware remain those frozen by
the Phase 7.4 offline retrieval protocol. Environment drift requires a
successor; it cannot be repaired in place.

## Failure taxonomy

- `input_lineage_failure`;
- `query_blindness_failure`;
- `sentence_boundary_failure`;
- `span_boundary_failure`;
- `span_overlap_or_gap_failure`;
- `unit_count_failure`;
- `claim_hash_or_identity_failure`;
- `provenance_failure`;
- `overlay_schema_failure`;
- `overlay_integrity_failure`;
- `reconstruction_failure`;
- `representation_failure`;
- `determinism_failure`;
- `environment_failure`;
- `authority_boundary_failure`;
- `audit_failure`.

All attempts and failures are append-only. Silent resegmentation, selective
case deletion, reserve substitution, and same-version semantic retry are
forbidden.

## Disposition

Protocol freeze does not construct Atomic overlays. Passing the later execution
Gate may authorize only the independent Reference protocol freeze. It does not
authorize Reference execution, Gold, dataset opening for arms, retrieval
execution, effect scoring, Runtime Integration, productization, or release.

