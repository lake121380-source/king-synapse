# DMR Mapping Policy Review

Date: 2026-07-03

Status: completed as an anonymized policy-coverage review. This is not a
retrieval benchmark and does not change the Phase 6 feature freeze.

Machine-readable report:

`crates/eval/reports/dmr-mapping-policy-review.json`

Runner:

`scripts/eval/dmr_mapping_policy_review.py`

## Scope

This review explains why the official-style DMR 500-request run scored
`323/500` requested rows instead of `500/500`.

It compares answer-to-memory mapping policies only. It does not run recall,
embeddings, reranking, answer generation, or an LLM judge. The report excludes
raw questions, answers, dialogs, personas, summaries, and memory chunk text.

## Source

| Field | Value |
| --- | --- |
| Dataset | `MemGPT/MSC-Self-Instruct` |
| Revision | `5138f416f8fa76b75b2e080da87e8a8e346e1500` |
| File | `msc_self_instruct.jsonl` |
| SHA-256 | `d3dbea36848b41dc46c0f1548d0ebf74eeaf6390d6f3fe9318e8480dc984495e` |
| Rows reviewed | 500 |
| Rows with question, answer, and generated chunks | 500 |
| Raw cache retained | No |

## Policy Coverage

| Policy | Rows | Coverage |
| --- | ---: | ---: |
| Strict whitespace full-answer substring | 82 | 16.4% |
| Punctuation-normalized full-answer substring | 323 | 64.6% |
| Significant-token containment | 442 | 88.4% |
| Significant-token overlap >= 0.75 | 469 | 93.8% |
| Significant-token overlap >= 0.50 | 487 | 97.4% |
| Any significant answer token present | 494 | 98.8% |

The current official-style DMR reports use the punctuation-normalized
full-answer substring policy. That is why the DMR 500-request run scored 323
rows and skipped 177 rows before selection.

## Punctuation Boundary

| Bucket after punctuation policy | Rows |
| --- | ---: |
| Accepted by punctuation policy | 323 |
| Rejected by punctuation policy | 177 |
| Rejected rows with significant-token containment | 122 |
| Rejected rows with >= 0.75 overlap after token-containment failures | 27 |
| Rejected rows with >= 0.50 overlap after stronger failures | 18 |
| Rejected rows with only weaker token evidence | 7 |
| Rejected rows with no diagnostic token match | 3 |

Answer-token bucket among the 177 punctuation-rejected rows:

| Answer token bucket | Rows |
| --- | ---: |
| 1-3 | 8 |
| 4-8 | 122 |
| 9-16 | 42 |
| 17-32 | 5 |

Significant-token bucket among the 177 punctuation-rejected rows:

| Significant-token bucket | Rows |
| --- | ---: |
| 1-3 | 88 |
| 4-8 | 85 |
| 9-16 | 4 |

## Decision

Keep `punctuation_full_answer` as the pinned official-style local mapping
boundary for now.

Do not claim DMR `500/500` under this policy. The honest claim is
`500 request / 323 scored`.

Do not silently promote `significant_token_containment` to the default DMR
mapping policy. It increases coverage to `442/500`, but it is no longer a
full-answer substring rule. It can over-accept paraphrases, partial evidence,
or generic short answers, so it must be labeled separately if used.

Allowed future option:

- add a separately named `relaxed-token` diagnostic run;
- keep it out of published-comparable official DMR claims;
- require fixed LLM judge scoring or manual spot-checking before using it for
  conclusions about answer correctness.

## Read

This review does not show a Synapse architecture failure. All 500 source rows
produce memory chunks, and 494/500 have at least one significant answer token
present in memory.

The real boundary is scoring-policy validity. A stricter full-answer mapping is
more trustworthy but yields only 323 scored rows after punctuation
normalization. A token-based mapping yields higher coverage but weaker evidence
that the full answer is actually present.

## Next Validation Work

1. Keep the current official-style DMR 50/200/500-request reports labeled with
   punctuation mapping.
2. Fix LLM judge authorization before making answer-correctness claims beyond
   lexical / ROUGE-L local scoring.
3. If larger DMR coverage is needed, add a separately labeled relaxed-token
   run and validate it with judge/manual checks.
4. Continue ranking failure localization on the current pinned punctuation
   dataset before changing any retrieval default.
