# DMR Failure Mode Taxonomy

Date: 2026-07-04

Status: validation evidence, not a runtime change

Machine-readable report:

`crates/eval/reports/dmr-failure-mode-taxonomy.json`

Runner:

`scripts/eval/dmr_failure_mode_taxonomy.py`

## Scope

This audit classifies the DMR 500-request / 323-scored local official-style
view after the `top-context-extractive` candidate was judged on
`deepseek-v4-flash`.

It reads only committed sanitized reports:

- `crates/eval/reports/official-dmr-500.json`
- `crates/eval/reports/official-dmr-500-top-context-judge.json`
- `crates/eval/reports/dmr-mapping-policy-review.json`
- `crates/eval/reports/official-dmr-generator-ablation-dmr-500.json`

It does not read or commit raw questions, answers, dialogs, sessions, memory
content, generated answers, prompts, raw judge responses, or API keys.

## Outcome Taxonomy

The taxonomy is mutually exclusive over the 500 requested DMR rows.

| Outcome | Count | Share of requested | Share of unresolved |
| --- | ---: | ---: | ---: |
| Mapping rejected before scoring | 177 | 35.40% | 39.42% |
| Retrieval top-10 miss | 109 | 21.80% | 24.28% |
| Top-context ranking boundary | 80 | 16.00% | 17.82% |
| Top-1 answer-synthesis failure | 83 | 16.60% | 18.49% |
| Judge-correct success | 51 | 10.20% | n/a |

Read:

- `449/500` requested rows remain unresolved under the current local
  official-style policy.
- The largest unresolved bucket is mapping coverage, not retrieval.
- Among scored rows, retrieval/ranking and answer synthesis are both material.
- Chunk-empty failure is not supported by this audit; the committed mapping
  audits point to answer-to-memory mapping policy as the larger boundary.

## Generator Delta

The top-context generator improves the judged result, but does not solve the
task.

| Metric | Extractive | Top-context |
| --- | ---: | ---: |
| Judge accuracy | 0.050 | 0.158 |
| Gold substring accuracy | 0.046 | 0.121 |
| ROUGE-L F1 | 0.039 | 0.075 |
| Judge-correct rows | 16 | 51 |

Transition read:

- `41` rows are correct only under top-context.
- `6` rows are correct only under extractive.
- Net judge-correct gain is `+35`.
- `266` scored rows remain incorrect under both generators.

## Boundary Interpretation

Mapping rejected before scoring is a scoring-policy boundary: the pinned
punctuation full-answer policy maps `323/500` rows. Relaxed token containment
covers more rows, but remains diagnostic-only and cannot be silently promoted
to the official local policy.

Retrieval top-10 misses are retrieval or ranking failures: the generator cannot
recover rows that never receive a relevant context in the top 10.

Top-context ranking boundary means a relevant context exists in the top 10 but
is not ranked first. Because the top-context generator only reads rank 1, these
rows are primarily ordering failures under the candidate generator policy.

Top-1 answer-synthesis failure means the relevant context is already rank 1,
but the generated answer is still judged incorrect. This is the cleanest
answer-generation optimization surface.

## Decision

The DMR 500 result does not disprove Synapse's core architecture. It narrows
the next work:

- do not change runtime defaults from this audit alone;
- keep the feature freeze;
- use hosted external comparison for the next heavy validation branch;
- use no-model failure analysis to decide whether the next DMR work should
  target mapping policy, ordering, or answer generation.
