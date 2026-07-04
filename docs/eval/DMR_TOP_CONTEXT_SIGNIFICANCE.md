# DMR Top-Context Significance

Date: 2026-07-04

Status: validation evidence, not a runtime change

Machine-readable report:

`crates/eval/reports/dmr-top-context-significance.json`

Runner:

`scripts/eval/dmr_top_context_significance.py`

## Scope

This audit checks whether the `top-context-extractive` DMR generator improves
over the pinned `extractive` baseline across the already completed DMR 50, DMR
200, and 500-request / 323-scored views.

It reads only committed sanitized per-query reports:

- `crates/eval/reports/official-dmr-50.json`
- `crates/eval/reports/official-dmr-50-top-context-judge.json`
- `crates/eval/reports/official-dmr-200.json`
- `crates/eval/reports/official-dmr-200-top-context-judge.json`
- `crates/eval/reports/official-dmr-500.json`
- `crates/eval/reports/official-dmr-500-top-context-judge.json`

It does not read or commit raw questions, answers, dialogs, sessions, memory
content, generated answers, prompts, raw judge responses, or API keys.

## Paired Judge Result

The primary statistical read is an exact two-sided McNemar/binomial test over
paired judge-correct discordant rows.

| Scale | Paired rows | Baseline judge acc. | Top-context judge acc. | Delta | Candidate-only | Baseline-only | p-value |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DMR 50 | 50 | 0.080 | 0.260 | +0.180 | 9 | 0 | 0.00390625 |
| DMR 200 | 200 | 0.060 | 0.150 | +0.090 | 23 | 5 | 0.000912234187 |
| DMR 500 request / 323 scored | 323 | 0.050 | 0.158 | +0.108 | 41 | 6 | 1.7717e-07 |

Read:

- The judged direction is positive at all three scale views.
- Candidate-only correct rows outnumber baseline-only correct rows at all
  three scale views.
- The exact paired test is significant at `p < 0.05` for all three scale views.

## Lexical Metrics

| Scale | Substring delta | ROUGE-L F1 delta |
| --- | ---: | ---: |
| DMR 50 | +0.160 | +0.061825 |
| DMR 200 | +0.080 | +0.029701 |
| DMR 500 request / 323 scored | +0.074303 | +0.035191 |

Substring and ROUGE-L move in the same positive direction as the judge signal.

## Available Strata

Committed sanitized reports expose one category only:

`dmr-answer-generation`

So question-subtype consistency cannot be audited from the current committed
reports. The available safe strata are retrieval bucket and answer-length
bucket.

### Retrieval Bucket

| Scale | Bucket | Rows | Baseline correct | Top-context correct | Delta |
| --- | --- | ---: | ---: | ---: | ---: |
| DMR 50 | no relevant top-10 | 12 | 0 | 1 | +0.083 |
| DMR 50 | top-1 relevant | 28 | 4 | 12 | +0.286 |
| DMR 50 | top-10 not top-1 | 10 | 0 | 0 | 0.000 |
| DMR 200 | no relevant top-10 | 61 | 0 | 4 | +0.066 |
| DMR 200 | top-1 relevant | 74 | 8 | 26 | +0.243 |
| DMR 200 | top-10 not top-1 | 65 | 4 | 0 | -0.062 |
| DMR 500 request / 323 scored | no relevant top-10 | 114 | 1 | 5 | +0.035 |
| DMR 500 request / 323 scored | top-1 relevant | 128 | 10 | 45 | +0.273 |
| DMR 500 request / 323 scored | top-10 not top-1 | 81 | 5 | 1 | -0.049 |

Interpretation: the generator direction is strongest when the relevant context
is already ranked first. The `top10_not_top1` bucket remains a ranking boundary
because the top-context generator reads rank 1 only.

## Decision

This strengthens the DMR 500 conclusion: the top-context direction is stable
and statistically supported across the completed local scale views.

It does not finish Phase 6 by itself. The result remains validation-only
because:

- absolute answer quality is still low;
- DMR 500 is still `500 request / 323 scored`, not `500/500`;
- published-comparable mapping/scoring policy is not finalized;
- hosted external comparison is still not configured;
- no runtime generator, ranking, schema, CLI/MCP, or product default should
  change from this report alone.
