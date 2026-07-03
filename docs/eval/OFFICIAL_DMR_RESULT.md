# Official DMR Answer-Generation Result

Date: 2026-07-03

Status: DMR 500-request answer-generation scoring passed locally on CUDA with
323 mappable samples; the latest 5-sample DeepSeek judge probe still returns
authorization errors, so fixed LLM judge scoring is unresolved.

Machine-readable report:

Primary report:

`crates/eval/reports/official-dmr-500.json`

DMR 500-request generator ablation report:

`crates/eval/reports/official-dmr-500-top-context-extractive.json`

DMR 500-request generator ablation audit:

`crates/eval/reports/official-dmr-generator-ablation-dmr-500.json`

Pinned DMR 200 report:

`crates/eval/reports/official-dmr-200.json`

DMR 200 generator ablation report:

`crates/eval/reports/official-dmr-200-top-context-extractive.json`

DMR 200 generator ablation audit:

`crates/eval/reports/official-dmr-generator-ablation-dmr-200.json`

Pinned DMR 50 report:

`crates/eval/reports/official-dmr-50.json`

DMR 50 generator ablation report:

`crates/eval/reports/official-dmr-50-top-context-extractive.json`

DMR 50 generator ablation audit:

`crates/eval/reports/official-dmr-generator-ablation-dmr-50.json`

Smoke report:

`crates/eval/reports/official-dmr-5-extractive.json`

Judge probe:

`crates/eval/reports/official-dmr-judge-probe.json`

Answer-synthesis audit:

`crates/eval/reports/official-dmr-answer-synthesis-audit.json`

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
| DMR 50 top-context generator | 50 | 50 | 31 | not requested |
| DMR 200 | 200 | 200 | 111 | not requested |
| DMR 200 top-context generator | 200 | 200 | 111 | not requested |
| DMR 500 request | 500 | 323 | 177 | not requested |
| DMR 500-request top-context generator | 500 | 323 | 177 | not requested |
| Judge probe | 5 | 5 | 1 | 5 authorization errors |

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

## DMR 500-Request Generator Cross-Check

This repeats the `top-context-extractive` generator ablation on the largest
local DMR request. Under the pinned punctuation mapping policy, the 500-request
run still scores `323/500` requested samples.

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 500 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator top-context-extractive `
  --llm-judge none `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-500-top-context-extractive.json `
  --cleanup-cache
```

| Generator | Retrieval Recall@10 | Exact | Punctuation | Gold substring | ROUGE-L F1 | Top-1 without substring |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| extractive | 0.380 | 0.000 | 0.000 | 0.046 | 0.039 | 118/128 |
| top-context-extractive | 0.380 | 0.000 | 0.000 | 0.121 | 0.075 | 90/127 |

The largest local cross-check repeats the same answer-synthesis direction:
substring and ROUGE-L improve, but the absolute answer score remains low.

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

## DMR 200 Generator Cross-Check

This repeats the `top-context-extractive` generator ablation on the 200-sample
DMR run. It is still evaluation-only: same sample size, mapping policy,
retrieval mode, top-k, CUDA settings, and no LLM judge.

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 200 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator top-context-extractive `
  --llm-judge none `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-200-top-context-extractive.json `
  --cleanup-cache
```

| Generator | Retrieval Recall@10 | Exact | Punctuation | Gold substring | ROUGE-L F1 | Top-1 without substring |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| extractive | 0.409 | 0.000 | 0.000 | 0.040 | 0.037 | 68/74 |
| top-context-extractive | 0.411 | 0.000 | 0.000 | 0.120 | 0.067 | 52/74 |

The retrieval numbers are from separate CUDA runs with the same configuration,
so they are aligned but not bit-identical. The answer-generation direction
repeats: restricting extraction to the top returned context improves substring
accuracy and ROUGE-L on the 200-sample run, but the absolute answer score is
still low.


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

## DMR 50 Generator Ablation

This is an evaluation-only answer-synthesis ablation. It changes only the
deterministic generator policy from `extractive` to `top-context-extractive`.
Retrieval mode, sample selection, mapping policy, CUDA settings, and top-k stay
fixed. The policy does not inspect gold answers; it restricts sentence
selection to the top returned memory chunk.

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 50 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator top-context-extractive `
  --llm-judge none `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-50-top-context-extractive.json `
  --cleanup-cache
```

| Generator | Retrieval Recall@10 | Exact | Punctuation | Gold substring | ROUGE-L F1 | Top-1 without substring |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| extractive | 0.468 | 0.000 | 0.020 | 0.060 | 0.041 | 25/28 |
| top-context-extractive | 0.468 | 0.000 | 0.020 | 0.220 | 0.103 | 17/28 |

Read: keeping the highest-ranked returned chunk as the generator search scope
improves substring accuracy and ROUGE-L on DMR 50. This does not make the
answer generator strong enough for official DMR claims, but it proves the low
answer score is not only a retrieval/ranking problem.

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

## Judge Probe

This probe re-ran the official-style 5-sample path with `--llm-judge deepseek`
after the previous DMR 50 judge failure. It uses CUDA retrieval and the same
sanitized answer-generation report shape. It does not commit raw questions,
answers, dialogs, sessions, generated answers, or the API key.

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 5 `
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
  --output crates/eval/reports/official-dmr-judge-probe.json `
  --cleanup-cache
```

| Metric | Value |
| --- | ---: |
| Sample size | 5 |
| Scored samples | 5/5 |
| Mapping skips before selection | 1 |
| Retrieval Recall@10 | 0.667 |
| Retrieval MRR@10 | 0.700 |
| Exact accuracy | 0.000 |
| Punctuation-normalized accuracy | 0.000 |
| Gold-answer substring accuracy | 0.200 |
| ROUGE-L F1 mean | 0.082 |
| LLM judge status | 5/5 authorization errors |
| HTTP status | 401 |
| LLM judge accuracy | not available |

## Answer-Synthesis Audit

The answer-synthesis audit reads the existing sanitized official-style reports
and separates retrieval misses from generator opportunity loss. It uses only
sample IDs, ranks, lengths, hashes, generation trace metadata, and scores.

The 50, 200, and 500-request reports are deterministic expansions of the same
source order, so the rows overlap. Treat the table below as three scale views,
not as independent samples to sum.

```powershell
python scripts/eval/official_dmr_answer_audit.py `
  --output crates/eval/reports/official-dmr-answer-synthesis-audit.json
```

The same audit runner also records the DMR 50 generator ablation:

```powershell
python scripts/eval/official_dmr_answer_audit.py `
  --reports crates/eval/reports/official-dmr-50.json `
            crates/eval/reports/official-dmr-50-top-context-extractive.json `
  --output crates/eval/reports/official-dmr-generator-ablation-dmr-50.json
```

And the DMR 200 generator ablation:

```powershell
python scripts/eval/official_dmr_answer_audit.py `
  --reports crates/eval/reports/official-dmr-200.json `
            crates/eval/reports/official-dmr-200-top-context-extractive.json `
  --output crates/eval/reports/official-dmr-generator-ablation-dmr-200.json
```

And the DMR 500-request generator ablation:

```powershell
python scripts/eval/official_dmr_answer_audit.py `
  --reports crates/eval/reports/official-dmr-500.json `
            crates/eval/reports/official-dmr-500-top-context-extractive.json `
  --output crates/eval/reports/official-dmr-generator-ablation-dmr-500.json
```

| Run | Top-1 hits | Top-1 without gold substring | Top-10 hits without gold substring | Not retrieved in top-10 | Top-1 selected non-first context |
| --- | ---: | ---: | ---: | ---: | ---: |
| DMR 50 | 28 | 25 | 35 | 12 | 23 |
| DMR 200 | 74 | 68 | 130 | 62 | 57 |
| DMR 500 request / 323 scored | 128 | 118 | 195 | 115 | 98 |

Bucket-level substring accuracy:

| Run | Top-1 bucket | Top-10 not top-1 bucket | Not retrieved top-10 bucket |
| --- | ---: | ---: | ---: |
| DMR 50 | 0.107 | 0.000 | 0.000 |
| DMR 200 | 0.081 | 0.031 | 0.000 |
| DMR 500 request / 323 scored | 0.078 | 0.038 | 0.017 |

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

The answer-synthesis audit sharpens that diagnosis. Even when retrieval returns
a relevant chunk at rank 1, the deterministic extractive generator usually does
not place the gold answer in the final generated answer: `25/28` top-1 DMR 50
hits, `68/74` top-1 DMR 200 hits, and `118/128` top-1 hits in the 323-scored
DMR 500-request run still miss the gold substring. This makes answer synthesis
a separate bottleneck from retrieval/ranking.

The DMR 50 generator ablation confirms the bottleneck is actionable. With
retrieval unchanged, `top-context-extractive` raises gold-answer substring
accuracy from `0.060` to `0.220` and ROUGE-L F1 from `0.041` to `0.103`.
It also reduces top-1 retrieval hits without a gold substring from `25/28` to
`17/28`.

The DMR 200 cross-check repeats the same direction at larger sample size:
substring accuracy rises from `0.040` to `0.120`, ROUGE-L F1 rises from
`0.037` to `0.067`, and top-1 hits without the gold substring fall from
`68/74` to `52/74`. The improvement is smaller than DMR 50 and still not
enough for official DMR claims, but it confirms answer synthesis is a real
optimization surface.

The DMR 500-request cross-check completes the local scale check. On the
323-scored sample, substring accuracy rises from `0.046` to `0.121`, ROUGE-L F1
rises from `0.039` to `0.075`, and top-1 hits without the gold substring fall
from `118/128` to `90/127`. This makes the generator direction repeat across
DMR 50, 200, and the largest pinned local run.

Research interpretation:

The current evidence does not point to a core architecture failure. It points
to a narrower DMR boundary: candidate retrieval/ranking is imperfect, and the
simple deterministic extractive generator does not reliably turn returned
chunks into clean answers. The DMR 500-request run adds a third boundary:
under the current punctuation mapping policy, the public candidate file does
not yield 500 scored official-style examples. The mapping policy review keeps
punctuation full-answer mapping as the pinned local boundary and treats
relaxed-token mapping as a separate diagnostic option.

The LLM judge path was exercised twice and did not produce judged samples. The
DMR 50 run returned authorization errors for all 50 requests. The later
5-sample judge probe also returned `authorization_error` for all 5 requests,
with HTTP status `401`. This is a judge authorization/configuration failure,
not a retrieval or answer scoring failure. DMR 200 and the DMR 500-request run
therefore skipped the judge intentionally and should be read as lexical /
ROUGE-L local scoring only.

## Boundary

This is still not a published-comparable official DMR benchmark result.

Reasons:

- the generator is a deterministic extractive baseline, not a fixed agent
  answer policy;
- the better DMR 50/200/500-request generator ablation is eval-only evidence
  and has not been validated by LongMemEval or an LLM judge;
- the LLM judge did not authenticate successfully;
- the DMR 500-request run scored 323/500 requested samples because the pinned
  answer-to-memory mapping policy exhausted mappable rows;
- the public DMR candidate mapping still uses the pinned punctuation policy;
- raw questions, answers, dialogs, sessions, and generated answer text are not
  committed.

## Next Step

Do not rerun the DMR 50 judge path until the authorization/configuration is
fixed outside the repository. The next judge gate is a small probe with at
least one successful `judged` sample. After that, rerun DMR 50 with the fixed
judge. Ranking work should continue on the pinned punctuation-mapped dataset;
any relaxed-token coverage run must be separately labeled and validated before
it is used for conclusions.
