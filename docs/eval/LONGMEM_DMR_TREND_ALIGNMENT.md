# LongMemEval / DMR Trend Alignment

Date: 2026-07-04

Status: validation evidence, not a runtime change

Machine-readable report:

`crates/eval/reports/longmem-dmr-trend-alignment.json`

Runner:

`scripts/eval/longmem_dmr_trend_alignment.py`

## Scope

This audit checks the Phase 6 exit-condition question:

`Do LongMemEval and DMR trends stay consistent as sample size expands?`

It reads only committed sanitized reports:

- `crates/eval/reports/dmr-top-context-significance.json`
- `crates/eval/reports/ranking-objective-conflict-audit.json`
- `crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json`
- `crates/eval/reports/ranking-task-gate.json`
- `crates/eval/reports/long-horizon-task-gate.json`

It does not run retrieval, ranking, answer generation, hosted adapters, LLM
judges, product code, or raw benchmark data.

## Result

The answer is mixed:

- DMR top-context answer generation is stable and paired-significant across
  DMR 50, 200, and the 500-request / 323-scored view.
- Ranking trends are not aligned enough across DMR and LongMemEval to support a
  global runtime ranking default.

So this Phase 6 exit condition is **not complete**.

## Aligned Surfaces

| Surface | Read |
| --- | --- |
| DMR top-context generation | Positive judge deltas on DMR 50, 200, and 500-request / 323-scored; paired McNemar tests are significant. |
| RRF k | Mostly flat in the checked range. |
| Vector weight | `1.5` improves Recall@10 on both DMR 50 and LongMemEval 50, but with MRR/top-1 tradeoffs. |

## Conflict Surfaces

| Surface | Read |
| --- | --- |
| Reranker pool exhaustive 50-sample view | DMR and LongMemEval choose different best Recall@10 values. |
| Pool-50 -> pool-100 expanded view | DMR 200/500 improve Recall@10, DMR 50 regresses; LongMemEval 50/200 regress, LongMemEval 500 improves but top-1 falls. |
| Pool-signal guards | No screened guard is ready for implementation. |

## Expanded Pool-50 -> Pool-100 View

| Dataset | Sample size | Recall@10 delta | MRR@10 delta | Top-1 delta | Retrieval-miss delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| DMR | 50 | -0.020000 | +0.004833 | 0 | 0 |
| DMR | 200 | +0.005167 | +0.011369 | +3 | -5 |
| DMR | 323 | +0.001961 | +0.004180 | 0 | -6 |
| LongMemEval | 50 | -0.036667 | +0.001278 | 0 | +1 |
| LongMemEval | 200 | -0.006583 | +0.001621 | +1 | +3 |
| LongMemEval | 500 | +0.008800 | +0.002024 | -3 | -6 |

Read:

- DMR has two positive Recall@10 expanded views and one negative view.
- LongMemEval has one positive Recall@10 expanded view and two negative views.
- MRR often moves positive while Recall@10 or top-1 can move the wrong way.

That is a ranking objective conflict, not a system-collapse signal.

## Decision

Do not change runtime ranking defaults.

The correct Phase 6 decision is:

- keep feature freeze;
- keep DMR top-context as validation evidence only;
- either define an explicit DMR/LongMemEval objective split, or find a new
  answer-free ordering signal;
- continue hosted external comparison when credentials/endpoints are
  configured.

This does not start Phase 7.
