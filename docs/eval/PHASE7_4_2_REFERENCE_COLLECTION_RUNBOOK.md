# Phase 7.4.2 Independent Reference Collection Runbook

Status: collection tooling only; no reviewer identity or annotation supplied

## Required external inputs

Reference collection requires three independent review entities:

- Reviewer A;
- Reviewer B;
- one future adjudicator.

The project coordinator creates one sanitized identity declaration containing
only SHA256 identity commitments and independence assertions. Names, contact
details, credentials, and personal data must remain outside the repository.

Reviewer A and Reviewer B each produce a submission conforming to
`phase7_4_independent_reference_submission_schema_v1.json`. The submissions
must cover all 168 assigned cases and all 3,360 claims in their own frozen
worklist order.

`reviewer_identity_declaration_sha256` is the SHA256 of the declaration's
canonical compact JSON (`sort_keys=true`, UTF-8, no insignificant whitespace).

## Status check

```powershell
python scripts/eval/phase7_4_independent_reference_collection_v1.py --status
```

This command is read-only and reports the exact missing external inputs.

## Validate external files

```powershell
python scripts/eval/phase7_4_independent_reference_collection_v1.py `
  --validate `
  --identity-declaration D:\private\phase7_4_reference_identity_declaration_v1.json `
  --reviewer-a D:\private\phase7_4_reference_reviewer_a_submission_v1.json `
  --reviewer-b D:\private\phase7_4_reference_reviewer_b_submission_v1.json
```

Validation is read-only. It checks identity commitments, independence,
submission Schema, exact packet/worklist lineage, claim coverage, support-state
rules, query relevance, and Unicode-scalar span boundaries.

## Freeze valid submissions

Use `--freeze` with the same three paths only after validation passes. Freeze
copies sanitized canonical JSON into the governed Phase 7.4 dataset namespace,
writes append-only audit/state/receipt artifacts, and authorizes only the
agreement protocol freeze.

The tool refuses to run if:

- any identity commitment is repeated;
- any reviewer is the source author or an arm implementer;
- A or B shared a person/model session or saw the other output;
- a case or claim is missing, duplicated, reordered, or lineage-invalid;
- spans violate the frozen label rules;
- Provider, Gold, arm output, or agreement access is declared;
- governed outputs already exist.

The tool never creates annotations, repairs submissions, substitutes reviewers,
or relaxes the agreement thresholds.
