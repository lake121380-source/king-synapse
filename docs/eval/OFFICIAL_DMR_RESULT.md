# Official DMR Answer-Generation Result

Date: 2026-07-03

Status: DMR 50 answer-generation scoring passed locally; LLM judge was
attempted but not authorized.

Machine-readable report:

Primary report:

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

These runs prove the official DMR task shape can execute locally on CUDA:
retrieval -> answer generation -> gold-answer scoring.

They also show the next real gap. Candidate retrieval can surface
answer-bearing chunks, but a simple deterministic extractive generator does not
reliably turn those chunks into a clean answer. On DMR 50, retrieval Recall@10
is `0.468`, while answer substring accuracy is only `0.060` and ROUGE-L F1 is
only `0.041`.

The LLM judge path was exercised but did not produce judged samples because the
provider returned `HTTP Error 401: Authorization Required` for every request.
This is a judge authorization/configuration failure, not a retrieval or answer
scoring failure.

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

Fix the judge authorization/configuration, rerun DMR 50 with a successful fixed
judge, then expand to DMR 200 / 500.
