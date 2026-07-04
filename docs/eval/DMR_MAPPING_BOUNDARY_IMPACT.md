# DMR Mapping Boundary Impact

Date: 2026-07-04

Status: validation evidence, not a runtime change

Machine-readable report:

`crates/eval/reports/dmr-mapping-boundary-impact.json`

Runner:

`scripts/eval/dmr_mapping_boundary_impact.py`

## Scope

This audit explains the `177/500` DMR rows that are rejected before scoring
under the pinned local punctuation-normalized full-answer mapping policy.

It reads only committed sanitized reports:

- `crates/eval/reports/dmr-mapping-policy-review.json`
- `crates/eval/reports/dmr-failure-mode-taxonomy.json`

It does not read or commit raw questions, answers, dialogs, sessions, memory
content, generated answers, prompts, raw judge responses, or API keys.

## Policy Ladder

| Mapping view | Rows covered | Share |
| --- | ---: | ---: |
| Strict whitespace full answer | 82 | 16.40% |
| Punctuation full answer | 323 | 64.60% |
| Significant-token containment | 442 | 88.40% |
| Significant-token overlap >= 75% | 469 | 93.80% |
| Significant-token overlap >= 50% | 487 | 97.40% |
| Any significant token | 494 | 98.80% |

The official local view remains punctuation full-answer matching. The relaxed
views are diagnostic only.

## Punctuation-Rejected Rows

The `177` punctuation-rejected rows split as follows:

| Boundary class | Count | Share of rejected |
| --- | ---: | ---: |
| All significant answer tokens present in one chunk | 122 | 68.93% |
| 75-99% significant-token overlap | 27 | 15.25% |
| 50-74% significant-token overlap | 18 | 10.17% |
| Any significant token only | 7 | 3.95% |
| No diagnostic significant-token match | 3 | 1.69% |

Read:

- `0/500` rows have empty memory chunks.
- `122/177` punctuation-rejected rows contain all significant answer tokens in
  one memory chunk.
- `174/177` punctuation-rejected rows have at least one diagnostic
  significant-token match.
- `3/177` punctuation-rejected rows have no diagnostic token match.

## Interpretation

This narrows the biggest unresolved DMR bucket. The mapping failures are mostly
not evidence that Synapse failed to create memory chunks. They are mostly a
boundary between a strict official-style answer-string policy and looser
diagnostic evidence inside the generated memory chunks.

That does not mean the relaxed rows should be counted as official hits. Token
containment and overlap can over-accept paraphrases, generic answers, or
partially supported answers. They need a separately labeled judge/manual
validation before they can support stronger DMR claims.

## Decision

This audit does not disprove Synapse's core memory architecture. It moves the
next DMR proof question from:

`Are the memory chunks empty or useless?`

to:

`Which mapping/scoring policy can be defended as published-comparable?`

Keep the feature freeze. Do not change memory schema, cognitive layers,
runtime defaults, ranking defaults, CLI/MCP, or product surfaces from this
audit alone.
