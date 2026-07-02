# Performance Analysis

Date: 2026-07-02

Status: first Phase 6 performance pass.

Machine-readable profile:

`crates/eval/reports/phase6-performance-profile.json`

## Scope

This is not an optimization plan. It records where time is currently going
based on checked-in validation reports.

No LongMemEval / DMR heavy rerun was started for this pass. The analysis uses
the existing CUDA 50-sample reports and lightweight replay baselines.

## Measurement Coverage

| Item | Current status |
| --- | --- |
| Latency | Measured end-to-end per query and per run. |
| Memory | Not instrumented yet. |
| CPU | Not instrumented yet. |
| Embedding time | Not independently instrumented; only vector-branch delta is available. |
| Vector search time | Not independently instrumented; included in vector-branch delta. |
| Reranker time | Not independently instrumented; reranker-branch delta is available. |
| GPU path | CUDA validated for LongMemEval / DMR vector and reranker runs. |

## Lightweight Replay Latency

These runs are local, no-model-download replay checks.

| Dataset | Memories | Queries | Recall@10 | P50 latency | P95 latency | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `coding_mem` | 20 | 30 | 0.950 | 2.21 ms | 3.77 ms | 71.08 ms |
| `reference` | 20 | 5 | 1.000 | 1.16 ms | 1.67 ms | 5.84 ms |
| `multihop` | 20 | 5 | 1.000 | 2.14 ms | 4.16 ms | 12.79 ms |

Read: the committed local replay gates are not the performance concern.

## Long-Memory Latency

| Dataset | Mode | Chunks | Recall@10 | MRR@10 | P50 latency | P95 latency | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LongMemEval 50 | Baseline RRF | 2355 | 0.503 | 0.310 | 538.1 ms | 1115.2 ms | 29121.1 ms |
| LongMemEval 50 | RRF + vectors | 2355 | 0.663 | 0.424 | 576.4 ms | 1190.3 ms | 30971.6 ms |
| LongMemEval 50 | RRF + vectors + reranker | 2355 | 0.590 | 0.490 | 1274.6 ms | 1861.5 ms | 65862.0 ms |
| DMR 50 | Baseline RRF | 250 | 0.188 | 0.155 | 64.4 ms | 83.4 ms | 3300.3 ms |
| DMR 50 | RRF + vectors | 250 | 0.438 | 0.217 | 78.1 ms | 102.9 ms | 3986.5 ms |
| DMR 50 | RRF + vectors + reranker | 250 | 0.584 | 0.445 | 619.0 ms | 648.6 ms | 31133.9 ms |

## Branch Delta

| Dataset | Vector P50 delta | Reranker P50 delta | Vector total delta | Reranker total delta |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval 50 | +38.3 ms | +698.1 ms | +1850.4 ms | +34890.4 ms |
| DMR 50 | +13.7 ms | +540.9 ms | +686.2 ms | +27147.4 ms |

Read:

- Vector retrieval is not the dominant latency cost in the 50-sample runs.
- Reranking is the dominant added cost.
- DMR benefits from reranking enough to justify the cost during validation.
- LongMemEval reranking improves MRR/top-1 but reduces Recall@10 versus
  vector-only, so it is not a clear default without more ranking work.

## External Adapter Latency

| System | Status | Chains | Mean latency |
| --- | --- | ---: | ---: |
| King Synapse | measured | 8 | 4.51 ms |
| Graphiti/Zep local | measured | 8 | 136.55 ms |
| Mem0 OSS | measured | 8 | 2995.50 ms |
| Letta | not configured | 8 | 0.00 ms |

Read: the local Synapse cognitive fixture is very fast; Mem0's measured path is
API/SDK bound and not comparable as a local-only latency number.

## Current Bottleneck Read

The current performance boundary is mostly reranker cost, not vector search.
The current quality boundary is still ranking and DMR mapping/chunking, not
raw latency.

The next useful instrumentation is:

1. process peak memory and CPU around `kr-eval` subprocesses;
2. corpus embedding time separated from query-time vector search;
3. FTS/entity/RRF/vector branch timing separated inside `RecallEngine`;
4. reranker candidate collection time separated from reranker model inference.

Until those are available, memory, CPU, embedding time, vector search time, and
reranker time should be treated as unresolved sub-stage metrics, not inferred
from end-to-end latency alone.
