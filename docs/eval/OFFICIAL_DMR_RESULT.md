# Official DMR Answer-Generation Result

Date: 2026-07-03

Status: DMR 500-request answer-generation scoring passed locally on CUDA with
323 mappable samples; fixed LLM judge scoring is still unresolved.

Machine-readable report:

Primary report:

`crates/eval/reports/official-dmr-500.json`

Pinned DMR 200 report:

`crates/eval/reports/official-dmr-200.json`

Pinned DMR 50 report:

`crates/eval/reports/official-dmr-50.json`

Smoke report:

`crates/eval/reports/official-dmr-5-extractive.json`

## What Changed

Synapse now has a DMR evaluation path that goes beyond candidate retrieval:

1. retrieve memory chunks with `kr-eval`;
2. generate an answer from returned chunks;
3. score the generated answer against the gold answer;
4. write only sanitized metrics and hashes.

The runner is:

`scripts/eval/official_dmr_eval.py`

## Experiment Version

| Field | Value |
| --- | --- |
| Git commit used for the DMR 500 run | `eb95b6d20a7fe97bb615d055d3a1cf0eb2759bc6` |
| Report schema | `king-synapse.official-dmr-answer-eval.v1` |
| Dataset | `MemGPT/MSC-Self-Instruct`, `msc_self_instruct.jsonl` |
| Dataset revision | `5138f416f8fa76b75b2e080da87e8a8e346e1500` |
| Dataset SHA-256 | `d3dbea36848b41dc46c0f1548d0ebf74eeaf6390d6f3fe9318e8480dc984495e` |
| Accelerator | CUDA device `0` |
| Embedder / reranker | `fastembed 5.17.2`, `multilingual-e5-base`, `bge-reranker-base` |
| Raw data policy | Raw records, raw answers, and generated answers are not committed. |

## Run Coverage

| Run | Requested | Scored | Mapping skips before selection | Judge status |
| --- | ---: | ---: | ---: | --- |
| DMR 5 smoke | 5 | 5 | 1 | not requested |
| DMR 50 | 50 | 50 | 31 | 50 authorization errors |
| DMR 200 | 200 | 200 | 111 | not requested |
| DMR 500 request | 500 | 323 | 177 | not requested |

The mapping-skip number is the count of source rows rejected before building
the scored sample because the answer-to-memory mapping policy did not find the
answer in generated memory chunks. It is not a runtime failure count.

The DMR 500-request run exhausted the mappable rows available under the pinned
punctuation policy before reaching 500 scored samples. It should be read as a
500-request / 323-scored report, not as a 500/500 report.

## DMR 500-Request Run

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 500 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator extractive `
  --llm-judge none `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-500.json `
  --cleanup-cache
```

## DMR 500-Request Result

| Metric | Value |
| --- | ---: |
| Requested sample size | 500 |
| Scored samples | 323/500 |
| Mapping skips before selection | 177 |
| Retrieval mode | vectors + reranker |
| Retrieval Recall@10 | 0.380 |
| Retrieval MRR@10 | 0.469 |
| Generator | extractive |
| Exact accuracy | 0.000 |
| Punctuation-normalized accuracy | 0.000 |
| Gold-answer substring accuracy | 0.046 |
| ROUGE-L precision mean | 0.027 |
| ROUGE-L recall mean | 0.103 |
| ROUGE-L F1 mean | 0.039 |
| LLM judge status | 323/323 not requested |
| LLM judge accuracy | not available |
| P50 query latency | 753.8 ms |
| P95 query latency | 1043.3 ms |
| Query wall time | 253.7 s |
| Peak GPU total memory | 3899.5 MiB |

## DMR 200 Run

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 200 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator extractive `
  --llm-judge none `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-200.json `
  --cleanup-cache
```

## DMR 200 Result

| Metric | Value |
| --- | ---: |
| Sample size | 200 |
| Scored samples | 200/200 |
| Retrieval mode | vectors + reranker |
| Retrieval Recall@10 | 0.409 |
| Retrieval MRR@10 | 0.469 |
| Generator | extractive |
| Exact accuracy | 0.000 |
| Punctuation-normalized accuracy | 0.000 |
| Gold-answer substring accuracy | 0.040 |
| ROUGE-L precision mean | 0.024 |
| ROUGE-L recall mean | 0.097 |
| ROUGE-L F1 mean | 0.037 |
| LLM judge status | 200/200 not requested |
| LLM judge accuracy | not available |
| P50 query latency | 667.3 ms |
| P95 query latency | 749.0 ms |
| Query wall time | 135.1 s |
| Peak GPU total memory | 4279.5 MiB |

## DMR 50 Run

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 50 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator extractive `
  --llm-judge deepseek `
  --judge-model deepseek-chat `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-50.json `
  --cleanup-cache
```

## DMR 50 Result

| Metric | Value |
| --- | ---: |
| Sample size | 50 |
| Retrieval mode | vectors + reranker |
| Retrieval Recall@10 | 0.468 |
| Retrieval MRR@10 | 0.619 |
| Generator | extractive |
| Exact accuracy | 0.000 |
| Punctuation-normalized accuracy | 0.020 |
| Gold-answer substring accuracy | 0.060 |
| ROUGE-L precision mean | 0.033 |
| ROUGE-L recall mean | 0.102 |
| ROUGE-L F1 mean | 0.041 |
| LLM judge status | 50/50 authorization errors |
| LLM judge accuracy | not available |
| Peak GPU total memory | 5304.2 MiB |

## Smoke Run

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 5 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator extractive `
  --llm-judge none `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-5-extractive.json `
  --cleanup-cache
```

## Smoke Result

| Metric | Value |
| --- | ---: |
| Sample size | 5 |
| Retrieval mode | vectors + reranker |
| Generator | extractive |
| LLM judge | not requested |
| Exact accuracy | 0.000 |
| Punctuation-normalized accuracy | 0.000 |
| Gold-answer substring accuracy | 0.200 |
| ROUGE-L precision mean | 0.050 |
| ROUGE-L recall mean | 0.322 |
| ROUGE-L F1 mean | 0.082 |
| Peak GPU total memory | 4031.5 MiB |

## Read

Engineering result:

These runs prove the official-style DMR task shape can execute locally on
CUDA: retrieval -> answer generation -> gold-answer scoring. The largest
completed local pass is now the DMR 500-request run, with `323/500` requested
samples scored under the pinned punctuation mapping policy.

The larger runs confirm the DMR 50 trend: retrieval remains useful but not
enough. Recall@10 moved from `0.468` on DMR 50 to `0.409` on DMR 200 and
`0.380` on the DMR 500-request run. Gold-answer substring accuracy stayed low:
`0.060`, `0.040`, then `0.046`. ROUGE-L F1 also stayed low: `0.041`, `0.037`,
then `0.039`.

Research interpretation:

The current evidence does not point to a core architecture failure. It points
to a narrower DMR boundary: candidate retrieval/ranking is imperfect, and the
simple deterministic extractive generator does not reliably turn returned
chunks into clean answers. The DMR 500-request run adds a third boundary:
under the current punctuation mapping policy, the public candidate file does
not yield 500 scored official-style examples.

The LLM judge path was exercised but did not produce judged samples because the
provider returned `HTTP Error 401: Authorization Required` for every request.
This is a judge authorization/configuration failure, not a retrieval or answer
scoring failure. DMR 200 and the DMR 500-request run therefore skipped the
judge intentionally and should be read as lexical / ROUGE-L local scoring only.

## Boundary

This is still not a published-comparable official DMR benchmark result.

Reasons:

- the generator is a deterministic extractive baseline, not a fixed agent
  answer policy;
- the LLM judge did not authenticate successfully;
- the DMR 500-request run scored 323/500 requested samples because the pinned
  answer-to-memory mapping policy exhausted mappable rows;
- the public DMR candidate mapping still uses the pinned punctuation policy;
- raw questions, answers, dialogs, sessions, and generated answer text are not
  committed.

## Next Step

Do not retry the LLM judge until the authorization/configuration is fixed.
After that, run a small judge probe, rerun DMR 50 with a successful fixed
judge, and decide whether the DMR mapping policy should remain punctuation
only or gain a separately labeled relaxed policy for larger official-style
coverage.
