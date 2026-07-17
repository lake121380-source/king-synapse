# Phase 7.4 Independent Reference Reviewer Instructions

Use only the assigned blind packet and your reviewer worklist. Do not inspect
source-authoring scripts, segmentation placeholders, another reviewer's work,
Gold, retrieval arms, or Phase 7.3.3-D evaluation content.

For every Atomic claim:

1. Read the query, the owning Memory, the exact Atomic span, source events, and
   source evidence.
2. Assign exactly one support state: `supported`, `partially_supported`,
   `unsupported`, `contradictory`, or `not_assessable`.
3. Mark `query_relevant=true` only when the claim would materially help answer
   or calibrate the query if its support state were known.
4. Add source-Memory spans only when the claim is query-relevant and its state
   is `supported` or `partially_supported`.
5. Use zero-based half-open Unicode-scalar offsets. Spans must remain inside the
   Atomic claim's source span.
6. Leave spans empty for query-irrelevant, unsupported, contradictory, or
   not-assessable claims.

Annotate every assigned claim exactly once. Do not defer, infer an intended
answer from IDs, coordinate with another reviewer, copy prior labels, or add
free-form rationale. Freeze your submission before any agreement result is
computed.
