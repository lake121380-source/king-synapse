# Living Cognitive Network v0.1 — Runtime Shadow E3–E5

Status: **E3 packet-only isolation PASS; E4 read-only execution PASS; E5 trace regression PASS**

## Scope

This stage proves that the existing Canonical Company Profile packet can be
consumed by a small, read-only execution path. It does not enable production
runtime retrieval, memory writes, learning, reflection, admission, provider
calls, or Living Cognitive Network modification.

The frozen Profile v3 and the earlier E1 retrieval packet are not rewritten.
The execution input creates a backward-compatible runtime projection that adds
`status`, `retrieval_eligible`, and `evidence_basis` to each selected entry.
This preserves the existing E1 hash lineage while making the product-facing
governance fields observable.

## E3 — Fresh Isolated Packet-only Proof

The generation child receives only a serialized task and runtime packet through
stdin. It runs with Python isolated mode and reads no repository file. The
parent process performs artifact hashing and replay validation after the child
returns.

The proof passed:

- packet contains no source documents or unadjudicated assertions;
- 14 candidates are observable: 12 eligible entries and 2 blockers;
- 12 selected entries are traced to output paragraphs;
- suspended and unknown blockers remain excluded with explicit reasons;
- all five output guards pass;
- output is 724 Chinese characters;
- the isolated child replay reproduces output and trace exactly;
- `runtime_write = false` and `candidate_or_network_modified = false`.

## E4 — Read-only Runtime Shadow

The first Runtime Shadow uses a deterministic keyword retrieval probe. This is
an execution harness, not a semantic retrieval-quality claim. It executes the
following path:

```text
question
  -> candidate_entries
  -> selected_entries / excluded_entries
  -> applied_guards
  -> shadow_draft or withheld
  -> runtime trace
```

The trace is a formal output surface and includes:

- `candidate_entries` with rank, score, eligibility, and exclusion reason;
- `selected_entries`;
- `excluded_entries`;
- `applied_guards`;
- per-entry `evidence_basis`;
- `answer_mode`;
- read-only authority flags.

## E5 — Governance Trace Regression

The frozen suite contains 20 enterprise questions covering identity,
positioning, prices, trial terms, 7×24 conditions, integrations, roles,
capabilities, case publication, suspended statistics, unknown delivery time,
company introduction, mixed retrieval, and adversarial quote requests.

The regression checks both answer mode and trace semantics. A case fails when
the answer happens to remain similar but the candidate pool, selected entries,
excluded reasons, or mandatory guards change unexpectedly.

Current result: **20/20 cases pass; replay pass**.

## Claim boundary and next stage

This stage proves packet portability, read-only governance execution, and trace
regression stability. It does **not** prove that the deterministic keyword
probe is a production-grade semantic retriever, and it does not authorize
Runtime integration.

The next allowed work is to compare or replace the retrieval probe while
keeping the Runtime Trace v1 and the 20-case governance expectations frozen.
