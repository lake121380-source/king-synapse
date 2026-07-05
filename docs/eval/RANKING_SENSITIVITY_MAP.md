# Ranking Sensitivity Map

Date: 2026-07-05

Status: **Ranking sensitivity analysis complete. System is in saturation zone.**

## Purpose

Map which ranking parameters break system stability and which are inert.
Fixed pool=100, tested one variable at a time on 200-sample LongMemEval.

## Setup

| Item | Value |
| --- | --- |
| Dataset | LongMemEval cleaned, 200 samples |
| Base config | vectors-rerank, pool=100, vw=1.0, fts=1.0, entity=1.0, rrf_k=60 |
| Accelerator | CUDA GPU |
| Cargo profile | release |

## Results

### vector_weight sensitivity

| vw | Recall@10 | MRR@10 | miss | delta vs baseline |
| ---: | ---: | ---: | ---: | ---: |
| 0.5 | 0.4616 | 0.3938 | 83 | -0.0056 |
| **0.8** | **0.4760** | 0.3998 | **77** | **+0.0088** |
| 1.0 (default) | 0.4672 | 0.3977 | 81 | baseline |
| 1.2 | 0.4618 | 0.3928 | 83 | -0.0054 |

**Shape: Inverted U, peak at vw=0.8.** Both sides degrade symmetrically.

### fts_weight sensitivity

| fts | Recall@10 | MRR@10 | miss | delta vs baseline |
| ---: | ---: | ---: | ---: | ---: |
| 0.5 | 0.4327 | 0.3811 | 89 | -0.0345 |
| 1.0 (default) | 0.4672 | 0.3977 | 81 | baseline |
| 1.5 | 0.4747 | 0.4001 | 79 | +0.0075 |

**Shape: Monotonic increasing, but converging.** fts=0.5 is destructive.

### rrf_k sensitivity

| rrf_k | Recall@10 | MRR@10 | miss |
| ---: | ---: | ---: | ---: |
| 40 | 0.4672 | 0.4002 | 81 |
| 60 (default) | 0.4672 | 0.3977 | 81 |
| 80 | 0.4672 | 0.4001 | 81 |

**Shape: Completely flat.** rrf_k is not a sensitive variable in this range.

### Combination test

| config | Recall@10 | MRR@10 | miss |
| --- | ---: | ---: | ---: |
| vw=1.0 fts=1.0 (baseline) | 0.4672 | 0.3977 | 81 |
| vw=0.8 fts=1.0 | 0.4760 | 0.3998 | 77 |
| vw=1.0 fts=1.5 | 0.4747 | 0.4001 | 79 |
| vw=0.8 fts=1.5 | 0.4747 | 0.3961 | 78 |

**Gains do not stack.** vw=0.8 and fts=1.5 affect overlapping query sets.

## Key findings

1. **System is in saturation zone.** Best single-variable gain is +0.0088 Recall@10
   (vw=0.8). Combination of two best variables does not improve over either alone.

2. **vector_weight is the most sensitive variable** (inverted-U, peak at 0.8).

3. **fts_weight is mildly sensitive** (monotonic but converging, 1.5 slightly better).

4. **rrf_k is completely inert** in the 40-80 range.

5. **The ranking function has a stable point** near vw=0.8, fts=1.0-1.5, rrf_k=40-80.
   Parameter perturbation beyond this point degrades performance.

6. **No runtime default change is warranted.** The gains are within noise range
   and do not justify changing the production default (vw=1.0, fts=1.0, rrf_k=60).

## Conclusion

Synapse has completed the ranking sensitivity map. The system is in the
"ranking saturation" phase identified in the convergence analysis: the reranker
determines the performance ceiling, parameter perturbation yields diminishing
returns, and the ranking function has a stable point.

The primary bottleneck remains retrieval recall (miss rate ~40% at 200 samples),
not ranking quality. Further gains require improving retrieval, not tuning
ranking parameters.

## Reports

| Config | Path |
| --- | --- |
| vw=0.5 | `crates/eval/reports/longmem-200-sens-vw0.5.json` |
| vw=0.8 | `crates/eval/reports/longmem-200-sens-vw0.8.json` |
| vw=1.0 | `crates/eval/reports/longmem-200-sens-vw1.0.json` |
| vw=1.2 | `crates/eval/reports/longmem-200-sens-vw1.2.json` |
| fts=0.5 | `crates/eval/reports/longmem-200-sens-fts0.5.json` |
| fts=1.5 | `crates/eval/reports/longmem-200-sens-fts1.5.json` |
| rrf_k=40 | `crates/eval/reports/longmem-200-sens-rrf40.json` |
| rrf_k=80 | `crates/eval/reports/longmem-200-sens-rrf80.json` |
| vw=0.8 fts=1.5 | `crates/eval/reports/longmem-200-sens-vw0.8-fts1.5.json` |
