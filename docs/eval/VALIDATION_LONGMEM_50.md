# LongMemEval 50 Validation

Date: 2026-07-02

Status: completed on local CUDA validation path.

Report:

`crates/eval/reports/longmem-50-validation.json`

## Scope

This is a 50-query LongMemEval cleaned validation run through the existing
`kr-eval` RecallEngine. It compares the same three retrieval branches:

- baseline RRF: FTS + entity branches;
- RRF + vectors;
- RRF + vectors + BGE reranker.

Raw LongMemEval records are not committed. The checked-in report contains only
aggregate metrics and anonymized per-query buckets.

## Fixed Configuration

| Field | Value |
| --- | --- |
| Dataset | `xiaowu0162/longmemeval-cleaned` |
| Revision | `98d7416c24c778c2fee6e6f3006e7a073259d48f` |
| File | `longmemeval_s_cleaned.json` |
| SHA-256 | `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442` |
| License | `mit` |
| Sample | 50 queries |
| Memory chunks | 2355 |
| Top-K | 50 |
| Accelerator | CUDA device `0` |
| Embedding | batch `32`, max length `256` |
| Reranker | batch `32`, max length `256`, pool `50` |

## Metrics

| Mode | Recall@5 | Recall@10 | MRR@10 | NDCG@10 | P50 latency | P95 latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline RRF | 0.317 | 0.503 | 0.310 | 0.339 | 541.8 ms | 1124.6 ms |
| RRF + vectors | 0.507 | 0.663 | 0.424 | 0.459 | 582.0 ms | 1186.2 ms |
| RRF + vectors + reranker | 0.483 | 0.590 | 0.490 | 0.461 | 1265.1 ms | 1874.2 ms |

## Process Metrics

Sampled around the `cargo run` / `kr-eval` process tree at 100 ms intervals.

| Mode | Peak working set | Peak private bytes | CPU time |
| --- | ---: | ---: | ---: |
| Baseline RRF | 255.6 MiB | 231.2 MiB | 94.9 s |
| RRF + vectors | 3044.3 MiB | 6407.3 MiB | 508.0 s |
| RRF + vectors + reranker | 4690.9 MiB | 8880.6 MiB | 768.2 s |

## Rank Buckets

| Mode | Top 1 | Top 10 not top 1 | Top 50 not top 10 | Absent from top 50 |
| --- | ---: | ---: | ---: | ---: |
| Baseline RRF | 10 | 22 | 9 | 9 |
| RRF + vectors | 13 | 26 | 6 | 5 |
| RRF + vectors + reranker | 18 | 18 | 8 | 6 |

## Read

Vector retrieval improved LongMemEval Recall@10 from `0.503` to `0.663` and
reduced top-50 absence from `9` to `5`.

The reranker improved first-rank quality: top-1 hits increased from `13` to
`18`, and MRR@10 improved from `0.424` to `0.490`. It also reduced top-10
coverage versus vector-only: Recall@10 moved from `0.663` to `0.590`.

Conclusion: LongMemEval benefits from dense vector retrieval. The reranker is
useful for top-1 ordering but is not a safe default for top-10 recall on this
configuration.
