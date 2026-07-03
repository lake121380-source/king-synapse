# Official DMR Answer-Generation Result

Date: 2026-07-03

Status: DMR 200 answer-generation scoring passed locally on CUDA; fixed LLM
judge scoring is still unresolved.

Machine-readable report:

Primary report:

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
| Git commit used for the run | `5ce4bef462eaa10fb251f4827d5a2860f91c7d1e` |
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

The mapping-skip number is the count of source rows rejected before building
the scored sample because the answer-to-memory mapping policy did not find the
answer in generated memory chunks. It is not a runtime failure count.

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
completed local pass is now DMR 200, with `200/200` selected samples scored.

The DMR 200 result confirms the DMR 50 trend on a larger local sample:
retrieval remains useful but not enough. Recall@10 moved from `0.468` on DMR
50 to `0.409` on DMR 200. Gold-answer substring accuracy moved from `0.060` to
`0.040`, and ROUGE-L F1 moved from `0.041` to `0.037`.

Research interpretation:

The current evidence does not point to a core architecture failure. It points
to a narrower DMR boundary: candidate retrieval/ranking is imperfect, and the
simple deterministic extractive generator does not reliably turn returned
chunks into clean answers.

The LLM judge path was exercised but did not produce judged samples because the
provider returned `HTTP Error 401: Authorization Required` for every request.
This is a judge authorization/configuration failure, not a retrieval or answer
scoring failure. DMR 200 therefore skipped the judge intentionally and should
be read as lexical / ROUGE-L local scoring only.

## Boundary

This is still not a published-comparable official DMR benchmark result.

Reasons:

- the generator is a deterministic extractive baseline, not a fixed agent
  answer policy;
- the LLM judge did not authenticate successfully;
- the public DMR candidate mapping still uses the pinned punctuation policy;
- raw questions, answers, dialogs, sessions, and generated answer text are not
  committed.

## Next Step

Do not retry the LLM judge until the authorization/configuration is fixed.
After that, run a small judge probe, rerun DMR 50 with a successful fixed
judge, then expand to DMR 500 local scoring.
