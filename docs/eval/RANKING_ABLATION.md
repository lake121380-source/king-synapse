# Ranking Ablation

Date: 2026-07-03

Status: DMR 50 ranking ablations, DMR 50 chunk-policy/query-expansion
ablations, and DMR 200 ranking-failure expansion complete.

Machine-readable reports:

`crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json`

`crates/eval/reports/ranking-ablation-dmr-50-top-k.json`

`crates/eval/reports/ranking-ablation-dmr-50-chunk-policy.json`

`crates/eval/reports/ranking-ablation-dmr-50-query-expansion.json`

`crates/eval/reports/ranking-failure-audit-dmr-50.json`

`crates/eval/reports/dmr-200-punctuation-validation.json`

`crates/eval/reports/ranking-ablation-dmr-200-top-k.json`

`crates/eval/reports/ranking-failure-audit-dmr-200.json`

`crates/eval/reports/ranking-ablation-longmem-50-reranker-pool.json`

Runner:

`scripts/eval/ranking_ablation.py`

Failure audit runner:

`scripts/eval/ranking_failure_audit.py`

Chunk-policy runner:

`scripts/eval/dmr_chunk_ablation.py`

Query-expansion runner:

`scripts/eval/dmr_query_expansion_ablation.py`

## Reranker Pool Scope

This pass varies one ranking parameter only:

`reranker_pool`

Everything else is fixed:

- dataset: DMR candidate MSC-Self-Instruct;
- sample size: 50;
- answer mapping: punctuation-normalized;
- retrieval mode: RRF + vectors + reranker;
- top-k returned by `kr-eval`: 10;
- accelerator: CUDA device `0`;
- embedding batch `32`, embedding max length `256`;
- reranker batch `32`, reranker max length `256`.

RRF weights, vector weights, chunk size, and query expansion are not exposed by
the current CLI, so they are not varied in this pass.

## Reranker Pool Command

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets dmr `
  --dmr-sample-size 50 `
  --dmr-answer-match punctuation `
  --k 10 `
  --reranker-pools 10,25,50,100 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json `
  --cleanup-cache
```

## Reranker Pool Result

| Reranker pool | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.445 | 0.502 | 169.2 ms | 23 | 8 | 19 |
| 25 | 0.453 | 0.608 | 321.6 ms | 27 | 9 | 14 |
| 50 | 0.468 | 0.618 | 636.9 ms | 28 | 10 | 12 |
| 100 | 0.448 | 0.623 | 1226.1 ms | 28 | 10 | 12 |

## Reranker Pool Read

The current default-style pool `50` remains the best Recall@10 setting in this
DMR 50 pass.

Pool `100` slightly improves MRR (`+0.005`) but lowers Recall@10 and roughly
doubles P50 latency versus pool `50`. That is not a clear default.

Pool `10` is much faster, but it loses five top-1 hits and adds seven retrieval
misses versus pool `50`.

Pool `25` is a possible speed/quality compromise, but it still trails pool `50`
on Recall@10, MRR@10, top-1 hits, and retrieval misses.

## Top-K Scope

This pass varies one ranking parameter only:

`top_k`

Everything else is fixed:

- dataset: DMR candidate MSC-Self-Instruct;
- sample size: 50;
- answer mapping: punctuation-normalized;
- retrieval mode: RRF + vectors + reranker;
- reranker pool: 50;
- accelerator: CUDA device `0`;
- embedding batch `32`, embedding max length `256`;
- reranker batch `32`, reranker max length `256`.

## Top-K Command

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets dmr `
  --dmr-sample-size 50 `
  --dmr-answer-match punctuation `
  --ablation top-k `
  --top-k-values 10,25,50 `
  --fixed-reranker-pool 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-50-top-k.json `
  --cleanup-cache
```

## Top-K Result

| Top-k | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.468 | 0.619 | 630.3 ms | 28 | 10 | 0 | 12 |
| 25 | 0.468 | 0.620 | 633.7 ms | 28 | 10 | 1 | 11 |
| 50 | 0.468 | 0.623 | 672.5 ms | 28 | 10 | 6 | 6 |

## Top-K Read

Increasing top-k does not improve Recall@10, top-1 hits, or top-10 placement.
That means the published candidate metric remains unchanged at the decision
surface.

But increasing top-k does reveal six additional answer-bearing chunks between
rank 11 and rank 50. The DMR 50 miss count drops from `12` at top-k `10` to
`6` at top-k `50`.

This is useful diagnostic evidence: some DMR failures are not pure retrieval
absence. They are late-ranking failures where the relevant memory exists in the
wider candidate list but does not reach the top 10.

## Chunk-Policy Scope

This pass varies one data-mapping parameter only:

`chunk_policy`

Everything else is fixed:

- dataset: DMR candidate MSC-Self-Instruct;
- sample size: 50;
- answer mapping: punctuation-normalized;
- sample selection: same 50 source rows selected by the current dialog chunk
  policy;
- retrieval mode: RRF + vectors + reranker;
- top-k returned by `kr-eval`: 50;
- reranker pool: 50;
- accelerator: CUDA device `0`;
- embedding batch `32`, embedding max length `256`;
- reranker batch `32`, reranker max length `256`.

This is an evaluation-only ablation. It does not change the memory schema,
recall defaults, product CLI, or ranking semantics.

## Chunk-Policy Command

```powershell
python scripts/eval/dmr_chunk_ablation.py `
  --endpoint https://hf-mirror.com `
  --sample-size 50 `
  --k 50 `
  --mode vectors-rerank `
  --reranker-pool 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-50-chunk-policy.json `
  --cleanup-cache
```

## Chunk-Policy Result

| Chunk policy | Memory chunks | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 only | Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dialog | 250 | 0.468 | 0.623 | 689.1 ms | 28 | 10 | 6 | 6 |
| merged-session | 50 | 0.360 | 0.211 | 921.6 ms | 7 | 11 | 32 | 0 |

## Chunk-Policy Read

The merged-session policy removes the six top-50 retrieval misses in this DMR
50 sample, so larger chunks improve broad candidate coverage.

But it sharply hurts ranking quality: Recall@10 drops from `0.468` to `0.360`,
MRR@10 drops from `0.623` to `0.211`, and top-1 hits fall from `28` to `7`.
The missed evidence mostly moves into the top-50-only bucket (`32` cases), not
into the decision surface.

This means the current DMR issue is not solved by simply merging dialogs into
larger memory chunks. Coarse chunks make the answer-bearing memory easier to
include somewhere in the candidate set, but they dilute the ranking signal
needed to place it in top 10.

## Query-Expansion Scope

This pass varies one query-mapping parameter only:

`query_policy`

Everything else is fixed:

- dataset: DMR candidate MSC-Self-Instruct;
- sample size: 50;
- answer mapping: punctuation-normalized;
- sample selection: same 50 source rows selected by the current dialog chunk
  policy;
- chunk policy: dialog chunks;
- retrieval mode: RRF + vectors + reranker;
- top-k returned by `kr-eval`: 50;
- reranker pool: 50;
- accelerator: CUDA device `0`;
- embedding batch `32`, embedding max length `256`;
- reranker batch `32`, reranker max length `256`.

The tested `keyword-boost` policy appends question-derived content keywords
twice. It uses only the question text and does not inspect memory chunks or
gold answers.

## Query-Expansion Command

```powershell
python scripts/eval/dmr_query_expansion_ablation.py `
  --endpoint https://hf-mirror.com `
  --sample-size 50 `
  --k 50 `
  --mode vectors-rerank `
  --reranker-pool 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-50-query-expansion.json `
  --cleanup-cache
```

## Query-Expansion Result

| Query policy | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 only | Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | 0.468 | 0.623 | 638.8 ms | 28 | 10 | 6 | 6 |
| keyword-boost | 0.403 | 0.523 | 663.6 ms | 21 | 15 | 8 | 6 |

`keyword-boost` expanded all 50 queries. It appended a mean of `21.48` tokens
per query from a mean of `10.74` question-derived keywords.

## Query-Expansion Read

The tested keyword-boost expansion does not solve DMR ranking. It keeps the
same six retrieval misses, lowers Recall@10 by `0.065`, lowers MRR@10 by
`0.099`, and loses seven top-1 hits.

This means simple question-keyword repetition is not a safe ranking fix. It
adds more lexical signal, but that signal is too broad: several relevant chunks
move down from top-1 into lower top-10 or top-50 positions.

## Failure Audit

The sanitized failure audit compares:

- baseline RRF;
- RRF + vectors;
- RRF + vectors + reranker;
- top-k `10`, `25`, and `50`.

It does not inspect raw questions, answers, dialogs, sessions, or generated
answer text.

Report:

`crates/eval/reports/ranking-failure-audit-dmr-50.json`

| Bucket | Count |
| --- | ---: |
| Top-1 hit | 28 |
| Top-10 not top-1 | 10 |
| Top-50 only late rank | 6 |
| Top-50 retrieval miss | 6 |

Vector effect:

| Effect | Count |
| --- | ---: |
| Vector recovered to top-10 | 10 |
| Vector suppressed from top-10 | 2 |
| Stable top-1 | 5 |
| Top-10 preserved | 10 |
| No top-10 change | 23 |

Reranker effect:

| Effect | Count |
| --- | ---: |
| Reranker recovered to top-10 | 14 |
| Reranker promoted to top-1 | 12 |
| Reranker suppressed from top-10 | 1 |
| Reranker demoted from top-1 | 1 |
| Stable top-1 | 8 |
| Top-10 preserved | 3 |
| No top-10 change | 11 |

Read:

- Vector retrieval helps, but it is not uniformly safe: it recovers 10 samples
  into top-10 and suppresses 2 from top-10.
- The reranker is doing real work: it recovers 14 samples into top-10 and
  promotes 12 to top-1.
- The reranker also has a small but real downside: 1 sample is suppressed from
  top-10 and 1 top-1 sample is demoted.
- The remaining 12 non-top-10 cases split cleanly into 6 late-ranking failures
  and 6 top-50 retrieval misses.

## DMR 200 Expansion

The DMR 50 failure structure was expanded to 200 punctuation-mapped samples.
This pass keeps the same feature-freeze rule: no memory schema changes, no new
ranking defaults, and one varied top-k parameter in the ablation.

Candidate report:

`crates/eval/reports/dmr-200-punctuation-validation.json`

Top-k report:

`crates/eval/reports/ranking-ablation-dmr-200-top-k.json`

Failure audit:

`crates/eval/reports/ranking-failure-audit-dmr-200.json`

### DMR 200 Candidate Result

| Mode | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 | Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline RRF | 0.145 | 0.129 | 109.9 ms | 14 | 34 | 86 | 66 |
| RRF + vectors | 0.323 | 0.224 | 133.9 ms | 20 | 83 | 46 | 51 |
| RRF + vectors + reranker | 0.411 | 0.476 | 712.4 ms | 74 | 65 | 18 | 43 |

### DMR 200 Top-K Result

| Top-k | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.413 | 0.472 | 676.6 ms | 74 | 66 | 0 | 60 |
| 25 | 0.409 | 0.473 | 687.7 ms | 74 | 64 | 12 | 50 |
| 50 | 0.411 | 0.476 | 731.7 ms | 74 | 65 | 18 | 43 |

### DMR 200 Failure Audit

| Bucket | Count |
| --- | ---: |
| Top-1 hit | 74 |
| Top-10 not top-1 | 66 |
| Top-50 only late rank | 17 |
| Top-50 retrieval miss | 43 |

The standalone top-k `50` run has 18 top-50 bucket cases. The cross-run failure
audit counts 17 top-50-only late-rank cases because one sample is already a
top-10 hit in the top-k `10` run.

Vector effect:

| Effect | Count |
| --- | ---: |
| Vector recovered to top-10 | 60 |
| Vector suppressed from top-10 | 5 |
| Stable top-1 | 9 |
| Top-10 preserved | 34 |
| No top-10 change | 92 |

Reranker effect:

| Effect | Count |
| --- | ---: |
| Reranker recovered to top-10 | 40 |
| Reranker promoted to top-1 | 49 |
| Reranker suppressed from top-10 | 3 |
| Reranker demoted from top-1 | 5 |
| Stable top-1 | 14 |
| Top-10 preserved | 32 |
| No top-10 change | 57 |

Read:

- The 200-sample result confirms that vectors and reranking both help DMR:
  Recall@10 rises from `0.145` to `0.323` with vectors, then to `0.411` with
  the reranker.
- The reranker is valuable but not free of regressions: it recovers 40 samples
  into top-10 and promotes 49 to top-1, while suppressing 3 from top-10 and
  demoting 5 top-1 samples.
- Increasing top-k is diagnostic, not a solution. It reduces apparent misses
  from 60 at top-k `10` to 43 at top-k `50`, but Recall@10 and top-1 hits do
  not improve.
- The remaining DMR 200 non-top-10 cases split into 17 late-ranking cases and
  43 top-50 retrieval misses. Compared with DMR 50, the larger sample shows
  that candidate retrieval remains an active bottleneck alongside ranking.

## LongMemEval Cross-Check

DMR-driven ranking decisions must not be adopted until they are checked against
LongMemEval. This pass varies only `reranker_pool` on the fixed LongMemEval 50
sample.

Report:

`crates/eval/reports/ranking-ablation-longmem-50-reranker-pool.json`

Command:

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets longmem `
  --longmem-sample-size 50 `
  --ablation reranker-pool `
  --reranker-pools 10,25,50,100 `
  --k 10 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-longmem-50-reranker-pool.json `
  --cleanup-cache
```

### LongMemEval 50 Reranker-Pool Result

| Reranker pool | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.600 | 0.473 | 612.9 ms | 18 | 18 | 14 |
| 25 | 0.637 | 0.521 | 829.4 ms | 20 | 18 | 12 |
| 50 | 0.590 | 0.483 | 1261.7 ms | 18 | 18 | 14 |
| 100 | 0.553 | 0.504 | 2098.7 ms | 20 | 15 | 15 |

Reference from `crates/eval/reports/longmem-50-validation.json`:

| Mode | Recall@10 | MRR@10 | Top-1 | Misses |
| --- | ---: | ---: | ---: | ---: |
| RRF + vectors | 0.663 | 0.425 | 13 | 5 |
| RRF + vectors + reranker pool 50 | 0.590 | 0.523 | 21 | 6 |

Read:

- Pool `25` is the best LongMemEval reranker-pool setting in this pass:
  Recall@10 `0.637`, MRR@10 `0.521`, and P50 `829.4 ms`.
- Pool `50`, the current DMR-favored setting, is worse on LongMemEval
  Recall@10 and latency than pool `25`.
- Pool `100` is not justified: it is slowest and has the lowest Recall@10.
- Even the best LongMemEval reranker-pool setting (`25`) still trails
  vector-only Recall@10 (`0.637` vs `0.663`), while improving MRR and top-1.
  This is a quality tradeoff, not a clean default win.

## Decision

Do not change the default reranker pool from this evidence.

The result supports the current diagnosis: DMR ranking is sensitive to
candidate pool size, output window, chunk policy, and query policy, but the
remaining weakness is not solved by simply making the pool bigger, returning
more items, merging all session content into one larger chunk, or repeating
question keywords. Returning top 50 helps diagnosis; merged-session chunks
improve broad top-50 coverage but damage top-10 and top-1 placement; keyword
boosting keeps retrieval misses unchanged and also damages ranking. The DMR
200 expansion adds that true top-50 retrieval misses are material and should
be separated from late-ranking cases before default changes.

The LongMemEval cross-check also argues against a global default change. DMR 50
prefers pool `50` on Recall@10, while LongMemEval 50 prefers pool `25` among
reranker variants and still prefers vector-only for top-10 coverage. Any
ranking change now needs either dataset-specific policy or a broader objective
than Recall@10 alone.

## Next Ablations

The next useful ranking work is:

1. expose and test RRF/vector weighting without changing the memory schema;
2. design a safer ranking signal for the top-50-only DMR cases;
3. test smaller, overlap-aware chunking instead of full-session merging;
4. avoid blunt keyword-boost query expansion unless a future answer-free
   rewrite policy proves it helps on both DMR and LongMemEval;
5. inspect top-50 retrieval misses separately from late-ranking cases;
6. test candidate-retrieval coverage separately from reranker ordering;
7. keep answer-generation scoring separate from retrieval-ranking scoring.
