# DMR 50 Punctuation-Normalized Validation

Date: 2026-07-02

Status: completed on local CUDA validation path.

Report:

`crates/eval/reports/dmr-50-punctuation-validation.json`

## Scope

This is the same `MemGPT/MSC-Self-Instruct` DMR candidate validation shape as
`VALIDATION_DMR_50.md`, but it uses the pinned punctuation-normalized answer
mapping policy:

```text
casefold + punctuation-normalized full answer substring in generated memory chunks
```

The original strict-string report is retained as the strict baseline:

`crates/eval/reports/dmr-50-validation.json`

This report is still not an official DMR harness result and uses no LLM judge.
Raw questions, answers, conversations, and generated temporary TOML datasets
are not committed.

## Fixed Configuration

| Field | Value |
| --- | --- |
| Dataset | `MemGPT/MSC-Self-Instruct` |
| Revision | `5138f416f8fa76b75b2e080da87e8a8e346e1500` |
| File | `msc_self_instruct.jsonl` |
| SHA-256 | `d3dbea36848b41dc46c0f1548d0ebf74eeaf6390d6f3fe9318e8480dc984495e` |
| License | `apache-2.0` |
| Answer mapping | `punctuation` |
| Sample | 50 evaluated queries |
| Memory chunks | 250 |
| Top-K | 50 |
| Accelerator | CUDA device `0` |
| Embedding | batch `32`, max length `256` |
| Reranker | batch `32`, max length `256`, pool `50` |

## Data Mapping

| Mapping item | Strict-string baseline | Punctuation-normalized |
| --- | ---: | ---: |
| Evaluated queries | 50 | 50 |
| Skipped before first 50 valid rows | 278 | 31 |

The policy change reduces pre-evaluation skips substantially without using
semantic or LLM scoring.

## Metrics

| Mode | Recall@5 | Recall@10 | MRR@10 | NDCG@10 | P50 latency | P95 latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline RRF | 0.125 | 0.198 | 0.179 | 0.137 | 67.4 ms | 88.1 ms |
| RRF + vectors | 0.217 | 0.280 | 0.303 | 0.224 | 80.8 ms | 106.4 ms |
| RRF + vectors + reranker | 0.408 | 0.468 | 0.623 | 0.441 | 622.3 ms | 659.4 ms |

## Rank Buckets

| Mode | Top 1 | Top 10 not top 1 | Top 50 not top 10 | Absent from top 50 |
| --- | ---: | ---: | ---: | ---: |
| Baseline RRF | 5 | 12 | 19 | 14 |
| RRF + vectors | 9 | 16 | 16 | 9 |
| RRF + vectors + reranker | 28 | 10 | 6 | 6 |

## Read

The punctuation-normalized policy confirms the earlier DMR diagnosis:
pre-evaluation skipping was mostly caused by strict answer-string mapping.

The new candidate set is not directly comparable to the strict-string set,
because it admits different rows. Still, the mode trend stays consistent:

- vectors improve over baseline;
- reranking gives the strongest top-1 behavior;
- remaining failures are still retrieval misses and ranking failures;
- DMR remains a candidate benchmark until the official harness or final
  scoring policy is pinned.

Conclusion: the DMR boundary is now better localized. The system still benefits
from vector retrieval and reranking, while the evaluation layer needs a pinned
official or final answer-matching policy before stronger DMR claims.
