# Ranking Ablation

Date: 2026-07-03

Status: first DMR 50 ranking ablation complete.

Machine-readable report:

`crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json`

Runner:

`scripts/eval/ranking_ablation.py`

## Scope

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

## Command

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

## Result

| Reranker pool | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.445 | 0.502 | 169.2 ms | 23 | 8 | 19 |
| 25 | 0.453 | 0.608 | 321.6 ms | 27 | 9 | 14 |
| 50 | 0.468 | 0.618 | 636.9 ms | 28 | 10 | 12 |
| 100 | 0.448 | 0.623 | 1226.1 ms | 28 | 10 | 12 |

## Read

The current default-style pool `50` remains the best Recall@10 setting in this
DMR 50 pass.

Pool `100` slightly improves MRR (`+0.005`) but lowers Recall@10 and roughly
doubles P50 latency versus pool `50`. That is not a clear default.

Pool `10` is much faster, but it loses five top-1 hits and adds seven retrieval
misses versus pool `50`.

Pool `25` is a possible speed/quality compromise, but it still trails pool `50`
on Recall@10, MRR@10, top-1 hits, and retrieval misses.

## Decision

Do not change the default reranker pool from this evidence.

The result supports the current diagnosis: DMR ranking is sensitive to
candidate pool size, but the remaining weakness is not solved by simply making
the pool bigger or smaller.

## Next Ablations

The next useful ranking work is:

1. expose and test RRF/vector weighting without changing the memory schema;
2. test top-k as a separate one-variable pass;
3. repeat the strongest DMR setting on LongMemEval 50 before changing any
   default;
4. keep answer-generation scoring separate from retrieval-ranking scoring.
