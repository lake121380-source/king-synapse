# Performance Analysis

Date: 2026-07-02

Status: Phase 6 performance pass with sub-stage and process metrics probe.

Machine-readable profile:

`crates/eval/reports/phase6-performance-profile.json`

## Scope

This is not an optimization plan. It records where time is currently going
based on checked-in validation reports.

No LongMemEval / DMR heavy rerun was started for this pass. The analysis uses
the existing CUDA 50-sample reports, lightweight replay baselines, and one
small CUDA sub-stage / process metrics probe.

## Measurement Coverage

| Item | Current status |
| --- | --- |
| Latency | Measured end-to-end per query and per run. |
| Memory | Instrumented in the 50-sample LongMemEval / DMR reports and in `phase6-substage-timing-probe.json`. |
| CPU | Instrumented in the 50-sample LongMemEval / DMR reports and in `phase6-substage-timing-probe.json`. |
| Embedding time | Instrumented in the 50-sample reports and summarized in `phase6-substage-timing-probe.json`. |
| Vector search time | Instrumented in the 50-sample reports and summarized in `phase6-substage-timing-probe.json`. |
| Reranker time | Instrumented in the 50-sample reports and summarized in `phase6-substage-timing-probe.json`. |
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
| LongMemEval 50 | Baseline RRF | 2355 | 0.503 | 0.310 | 541.8 ms | 1124.6 ms | 29193.9 ms |
| LongMemEval 50 | RRF + vectors | 2355 | 0.663 | 0.424 | 582.0 ms | 1186.2 ms | 31064.6 ms |
| LongMemEval 50 | RRF + vectors + reranker | 2355 | 0.590 | 0.490 | 1265.1 ms | 1874.2 ms | 65754.1 ms |
| DMR 50 | Baseline RRF | 250 | 0.188 | 0.155 | 64.3 ms | 84.1 ms | 3297.4 ms |
| DMR 50 | RRF + vectors | 250 | 0.438 | 0.217 | 78.1 ms | 102.9 ms | 3978.0 ms |
| DMR 50 | RRF + vectors + reranker | 250 | 0.584 | 0.445 | 618.7 ms | 651.8 ms | 31111.4 ms |

## Long-Memory Process Metrics

These metrics were sampled around the `cargo run` / `kr-eval` process tree at
100 ms intervals during the CUDA 50-sample reruns.

| Dataset | Mode | Peak working set | Peak private bytes | CPU time |
| --- | --- | ---: | ---: | ---: |
| LongMemEval 50 | Baseline RRF | 255.6 MiB | 231.2 MiB | 94.9 s |
| LongMemEval 50 | RRF + vectors | 3044.3 MiB | 6407.3 MiB | 508.0 s |
| LongMemEval 50 | RRF + vectors + reranker | 4690.9 MiB | 8880.6 MiB | 768.2 s |
| DMR 50 | Baseline RRF | 92.3 MiB | 72.1 MiB | 6.1 s |
| DMR 50 | RRF + vectors | 1935.9 MiB | 4277.9 MiB | 35.2 s |
| DMR 50 | RRF + vectors + reranker | 2741.1 MiB | 7236.5 MiB | 112.2 s |

## Branch Delta

| Dataset | Vector P50 delta | Reranker P50 delta | Vector total delta | Reranker total delta |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval 50 | +40.2 ms | +683.1 ms | +1870.8 ms | +34689.4 ms |
| DMR 50 | +13.7 ms | +540.7 ms | +680.6 ms | +27133.4 ms |

Read:

- Vector retrieval is not the dominant latency cost in the 50-sample runs, but
  it does account for most of the jump in process memory.
- Reranking is the dominant added query latency cost and the peak memory point
  in both 50-sample runs.
- DMR benefits from reranking enough to justify the cost during validation.
- LongMemEval reranking improves MRR/top-1 but reduces Recall@10 versus
  vector-only, so it is not a clear default without more ranking work.

## Sub-Stage Timing Probe

Report:

`crates/eval/reports/phase6-substage-timing-probe.json`

Scope: DMR candidate, punctuation-normalized mapping, 5 queries, 25 chunks,
`RRF + vectors + reranker`, CUDA device `0`.

This probe is intentionally small. It proves the instrumentation path and
locates sub-stage cost without replacing the 50-sample validation reports.

Setup timing:

| Stage | Time |
| --- | ---: |
| Dataset load | 11.3 ms |
| Store write | 176.3 ms |
| Embedder load | 6425.4 ms |
| Corpus embedding | 1584.6 ms |
| Embedding write | 8.8 ms |
| Reranker load | 6013.0 ms |

Mean query sub-stage timing:

| Stage | Mean per query |
| --- | ---: |
| Total recall | 308.0 ms |
| FTS | 4.6 ms |
| Entity | 1.0 ms |
| Query embedding | 13.0 ms |
| Vector search | 2.2 ms |
| Memory hydration | 0.1 ms |
| RRF fusion | 0.4 ms |
| Hit build | 0.1 ms |
| Reranker inference | 280.8 ms |
| Final scoring | 0.0 ms |
| Record access | 5.7 ms |

Read: on this CUDA probe, reranker inference dominates query-time cost.
Query embedding and vector search are visible but much smaller. The original
branch-delta conclusion is therefore supported by direct sub-stage timing.

Process metrics from the same probe:

| Metric | Value |
| --- | ---: |
| Sample interval | 100 ms |
| Samples | 156 |
| Max process count | 3 |
| Peak working set | 2495.7 MiB |
| Peak private bytes | 6173.5 MiB |
| CPU time | 20.8 s |
| Process wall time | 17.9 s |

Read: process metrics now exist for the small CUDA probe. They include the
`cargo run` wrapper plus the `kr-eval` process tree, so they should be treated
as run-level validation evidence rather than isolated engine-only memory
usage.

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

1. GPU memory accounting if the execution provider exposes it;
2. repeat 50-sample process metrics after retrieval or model-configuration
   changes.

Memory, CPU, embedding, vector search, FTS/entity/RRF, and reranker inference
now have direct validation evidence. GPU memory is still not independently
measured.
