# DMR 50 Validation

Date: 2026-07-02

Status: completed on local CUDA validation path.

Report:

`crates/eval/reports/dmr-50-validation.json`

## Scope

This is a 50-query DMR candidate validation run built from
`MemGPT/MSC-Self-Instruct`. It is not an official DMR harness result. It uses
the existing sanitized smoke runner to test whether King Synapse can retrieve
the expected answer-bearing memory chunks under the same three retrieval
branches:

- baseline RRF: FTS + entity branches;
- RRF + vectors;
- RRF + vectors + BGE reranker.

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
| Sample | 50 evaluated queries |
| Memory chunks | 250 |
| Top-K | 50 |
| Accelerator | CUDA device `0` |
| Embedding | batch `32`, max length `256` |
| Reranker | batch `32`, max length `256`, pool `50` |

## Data Mapping

| Mapping item | Count |
| --- | ---: |
| Evaluated queries | 50 |
| Skipped because answer was not found in generated chunks | 278 |

The skipped count is important: it means a large part of the candidate source
cannot yet participate in this harness without improving the DMR mapping and
chunking logic.

Follow-up audit:

- `docs/eval/DMR_MAPPING_AUDIT.md`
- `crates/eval/reports/dmr-mapping-audit.json`

The audit checked all 500 candidate rows. Every row produced five memory
chunks, but the current exact answer-string selection rule accepted only 82
rows and skipped 418. Among skipped rows, 241 matched after punctuation
normalization and 362 had all significant answer tokens in one chunk. This
localizes the DMR skipped-row issue to the mapping/scoring rule rather than
empty chunk generation.

## Metrics

| Mode | Recall@5 | Recall@10 | MRR@10 | NDCG@10 | P50 latency | P95 latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline RRF | 0.145 | 0.188 | 0.155 | 0.135 | 64.4 ms | 83.4 ms |
| RRF + vectors | 0.238 | 0.438 | 0.217 | 0.238 | 78.1 ms | 102.9 ms |
| RRF + vectors + reranker | 0.524 | 0.584 | 0.445 | 0.451 | 619.0 ms | 648.6 ms |

## Rank Buckets

| Mode | Top 1 | Top 10 not top 1 | Top 50 not top 10 | Absent from top 50 |
| --- | ---: | ---: | ---: | ---: |
| Baseline RRF | 5 | 7 | 26 | 12 |
| RRF + vectors | 6 | 19 | 18 | 7 |
| RRF + vectors + reranker | 16 | 18 | 11 | 5 |

## Read

DMR is still the harder path. Dense vectors improved Recall@10 from `0.188` to
`0.438`, and the reranker improved it further to `0.584`.

The biggest reranker gain is rank quality: top-1 hits increased from `6` in
vector-only mode to `16` after reranking. Top-50 absence also dropped from `7`
to `5`, but most remaining failures are ranking failures rather than pure
retrieval misses.

Conclusion: the DMR bottleneck is mainly retrieval-ranking plus data mapping,
not a reason to change the whole Synapse architecture.
