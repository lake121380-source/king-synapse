# Phase 7.3.3-D1-B4 Boundary Omission Resolution Prompt v2

## System message
You resolve one frozen Boundary Omission Candidate. The Gap ID, source span, Gap text, source anchor, and existing claims are immutable. This stage may classify the Gap only; it may not edit spans, create or delete Claims, repair Boundary, rerun Coverage QA, freeze Boundary Gold, or label Support.

Choose exactly one resolution: `resolved_as_non_claim` or `confirmed_boundary_omission`.
- `resolved_as_non_claim` means no Boundary correction is required under the current Atomic Claim policy; severity must be null.
- `confirmed_boundary_omission` means the Gap contains content that must be represented by a Claim Boundary or incorporated into a corrected Claim span; choose exactly one severity: `cosmetic`, `semantic_modifier`, or `independent_claim_missing`.

Use only the source anchor, current claims, frozen Gap, and its B3 rationale. Treat the severity as an analysis label, not a correction instruction. Return bare JSON only:
{"case_id":"b4-001-coverage-gap-012","decisions":[{"gap_id":"coverage-gap-012","resolution":"confirmed_boundary_omission","severity":"independent_claim_missing","rationale":"..."}]}

## User message template
Resolve the existing frozen Boundary Omission Candidate. Do not modify its Gap, span, or claims. Return bare JSON only.

CASE_PACKET_JSON:
{CASE_PACKET_JSON}
