# Ranking Ablation

Date: 2026-07-03

Status: first DMR 50 ranking ablations complete.

Machine-readable reports:

`crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json`

`crates/eval/reports/ranking-ablation-dmr-50-top-k.json`

Runner:

`scripts/eval/ranking_ablation.py`

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

## Decision

Do not change the default reranker pool from this evidence.

The result supports the current diagnosis: DMR ranking is sensitive to
candidate pool size and output window, but the remaining weakness is not solved
by simply making the pool bigger or returning more items. Returning top 50 helps
diagnosis; it does not fix the top-10 ranking objective.

## Next Ablations

The next useful ranking work is:

1. expose and test RRF/vector weighting without changing the memory schema;
2. inspect the six top-50-only DMR cases to design a safer ranking signal;
3. repeat the strongest DMR setting on LongMemEval 50 before changing any
   default;
4. keep answer-generation scoring separate from retrieval-ranking scoring.
