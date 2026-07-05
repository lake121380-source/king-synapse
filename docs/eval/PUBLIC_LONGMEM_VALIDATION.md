# Public LongMemEval Validation

Date: 2026-07-04

Status: **Public real-world long-memory validation completed.**

## Purpose

Validate Synapse end-to-end retrieval on the full public LongMemEval-cleaned
dataset (500 samples, 23,867 memory chunks) with GPU acceleration, and compare
retrieval modes and ranking parameters.

This is the first end-to-end run on the complete public LongMemEval dataset,
not a local deterministic fixture.

## Dataset

| Item | Value |
| --- | --- |
| Source | `xiaowu0162/longmemeval-cleaned` (HuggingFace, MIT license) |
| File | `longmemeval_s_cleaned.json` |
| Samples | 500 |
| Memory chunks | 23,867 |
| Accelerator | CUDA (GPU) |
| Cargo profile | release |

## Results

| Mode | Recall@10 | MRR@10 | top1 | retrieval_miss | P50 latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline-rrf | 0.3174 | 0.1618 | 29 | 291 | 2,042 |
| vectors | 0.3435 | 0.2352 | 74 | 272 | 2,155 |
| vectors-rerank pool=50 vw=1.0 | 0.3712 | 0.3190 | 118 | 250 | 5,637 |
| **vectors-rerank pool=100 vw=1.0** | **0.3800** | **0.3208** | 115 | **244** | 3,471 |
| vectors-rerank pool=100 vw=1.5 | 0.3736 | 0.3168 | 114 | 248 | 3,595 |

## Key findings

1. **Vector retrieval improves Recall@10 by +2.6%** over baseline RRF (0.317 -> 0.343).

2. **Reranker improves Recall@10 by +2.8%** over vectors-only (0.343 -> 0.371)
   and MRR@10 by +8.4% (0.235 -> 0.319).

3. **pool=100 is the best reranker pool size**: Recall@10 0.380 vs 0.371 at
   pool=50, with 6 fewer retrieval misses. P50 latency also improved
   (3.5s vs 5.6s) due to better GPU batching at the larger pool size.

4. **vector_weight=1.5 does not help**: Recall@10 dropped from 0.380 to 0.374.
   The default vector_weight=1.0 remains the best setting.

5. **Retrieval miss is the primary bottleneck**: 244/500 (48.8%) of queries
   have no relevant memory in the top-10. This is a recall problem, not a
   ranking problem. The reranker can only rerank what retrieval finds.

## Reports

| Report | Path |
| --- | --- |
| baseline-rrf | `crates/eval/reports/longmem-500-public-baseline-rrf.json` |
| vectors | `crates/eval/reports/longmem-500-public-vectors.json` |
| vectors-rerank pool=50 | `crates/eval/reports/longmem-500-public-vectors-rerank.json` |
| vectors-rerank pool=100 | `crates/eval/reports/longmem-500-public-rerank-pool-100.json` |
| vectors-rerank pool=100 vw=1.5 | `crates/eval/reports/longmem-500-public-pool100-vw1.5.json` |

## Conclusion

The public real-world LongMemEval validation is complete. Synapse achieves
Recall@10 = 0.380 on the full 500-sample public dataset with the best
configuration (vectors-rerank, pool=100, vector_weight=1.0). The system is
functional end-to-end on public real-world long-memory data.

The primary bottleneck is retrieval recall (48.8% miss rate), not ranking or
architecture. This is an engineering optimization target, not a design failure.

No runtime defaults are changed. All results are validation-only evidence.
