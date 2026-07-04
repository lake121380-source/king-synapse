# Official DMR Answer-Generation Result

Date: 2026-07-04

Status: DMR 500-request answer-generation scoring passed locally on CUDA with
323 mappable samples; DeepSeek judge preflight and judge probe now return
`judged` on `deepseek-v4-flash`, and the pinned 5 / 50 / 200 / 500-request
runs plus the DMR 50 / 200 / 500-request top-context candidates are now judged locally. A sanitized
bottleneck taxonomy now separates mapping coverage, retrieval/ranking, and
answer-synthesis limits.

Machine-readable report:

Primary report:

`crates/eval/reports/official-dmr-500.json`

DMR 500-request generator ablation report:

`crates/eval/reports/official-dmr-500-top-context-extractive.json`

DMR 500-request top-context judge report:

`crates/eval/reports/official-dmr-500-top-context-judge.json`

DMR 500-request generator ablation audit:

`crates/eval/reports/official-dmr-generator-ablation-dmr-500.json`

Pinned DMR 200 report:

`crates/eval/reports/official-dmr-200.json`

DMR 200 generator ablation report:

`crates/eval/reports/official-dmr-200-top-context-extractive.json`

DMR 200 generator ablation audit:

`crates/eval/reports/official-dmr-generator-ablation-dmr-200.json`

DMR 200 top-context judge report:

`crates/eval/reports/official-dmr-200-top-context-judge.json`

Pinned DMR 50 report:

`crates/eval/reports/official-dmr-50.json`

DMR 50 generator ablation report:

`crates/eval/reports/official-dmr-50-top-context-extractive.json`

DMR 50 generator ablation audit:

`crates/eval/reports/official-dmr-generator-ablation-dmr-50.json`

DMR 50 top-context judge report:

`crates/eval/reports/official-dmr-50-top-context-judge.json`

Consolidated generator ablation summary:

`crates/eval/reports/official-dmr-generator-ablation-summary.json`

Smoke report:

`crates/eval/reports/official-dmr-5-extractive.json`

Judge probe:

`crates/eval/reports/official-dmr-judge-probe.json`

Judge preflight:

`crates/eval/reports/official-dmr-judge-preflight.json`

Top-context candidate judge preflight:

`crates/eval/reports/official-dmr-top-context-judge-preflight.json`

Answer-synthesis audit:

`crates/eval/reports/official-dmr-answer-synthesis-audit.json`

Bottleneck taxonomy:

`crates/eval/reports/official-dmr-bottleneck-taxonomy.json`

DMR failure-mode taxonomy:

`crates/eval/reports/dmr-failure-mode-taxonomy.json`

DMR mapping-boundary impact:

`crates/eval/reports/dmr-mapping-boundary-impact.json`

DMR top-context significance:

`crates/eval/reports/dmr-top-context-significance.json`

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
| Git commit used for the DMR 500 run | `5ac1b69d052f9e5edd79fedb5e1b503a0d6e912f` |
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
| DMR 50 | 50 | 50 | 31 | 50 judged / 0 error |
| DMR 50 top-context generator | 50 | 50 | 31 | 50 judged / 0 error |
| DMR 200 | 200 | 200 | 111 | 200 judged / 0 error |
| DMR 200 top-context generator | 200 | 200 | 111 | 200 judged / 0 error |
| DMR 500 request | 500 | 323 | 177 | 323 judged / 0 error |
| DMR 500-request top-context generator | 500 | 323 | 177 | 323 judged / 0 error |
| Judge probe | 5 | 5 | 1 | 5 judged / 0 error |
| Judge preflight | 1 synthetic request | 0 DMR samples | 0 | judged / HTTP 200 |

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
  --llm-judge deepseek `
  --judge-model deepseek-v4-flash `
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
| Retrieval Recall@10 | 0.381 |
| Retrieval MRR@10 | 0.469 |
| Generator | extractive |
| Exact accuracy | 0.000 |
| Punctuation-normalized accuracy | 0.000 |
| Gold-answer substring accuracy | 0.046 |
| ROUGE-L precision mean | 0.027 |
| ROUGE-L recall mean | 0.103 |
| ROUGE-L F1 mean | 0.039 |
| LLM judge status | 323 judged / 0 error |
| LLM judge accuracy | 0.04953560371517028 |
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
  --llm-judge deepseek `
  --judge-model deepseek-v4-flash `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-500-top-context-judge.json `
  --cleanup-cache
```

| Generator | Retrieval Recall@10 | Exact | Punctuation | Gold substring | ROUGE-L F1 | Judge | Top-1 without substring |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| extractive | 0.381 | 0.000 | 0.000 | 0.046 | 0.039 | 323 judged / acc 0.050 | 118/128 |
| top-context-extractive | 0.381 | 0.000 | 0.000 | 0.121 | 0.075 | 323 judged / acc 0.158 | 91/128 |

The largest local cross-check repeats the same answer-synthesis direction:
substring, ROUGE-L, and judge accuracy improve, but the absolute answer score
remains low.

## DMR 200 Run

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 200 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator extractive `
  --llm-judge deepseek `
  --judge-model deepseek-v4-flash `
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
| Retrieval Recall@10 | 0.411 |
| Retrieval MRR@10 | 0.472 |
| Generator | extractive |
| Exact accuracy | 0.000 |
| Punctuation-normalized accuracy | 0.000 |
| Gold-answer substring accuracy | 0.040 |
| ROUGE-L precision mean | 0.024 |
| ROUGE-L recall mean | 0.097 |
| ROUGE-L F1 mean | 0.037 |
| LLM judge status | 200 judged / 0 error |
| LLM judge accuracy | 0.06 |
| P50 query latency | 667.3 ms |
| P95 query latency | 749.0 ms |
| Query wall time | 135.1 s |
| Peak GPU total memory | 4279.5 MiB |

## DMR 200 Generator Cross-Check

This repeats the `top-context-extractive` generator ablation on the 200-sample
DMR run. It is still evaluation-only: same sample size, mapping policy,
retrieval mode, top-k, and CUDA settings. It is now also judge-scored on
`deepseek-v4-flash`.

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 200 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator top-context-extractive `
  --llm-judge deepseek `
  --judge-model deepseek-v4-flash `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-200-top-context-judge.json `
  --cleanup-cache
```

| Generator | Retrieval Recall@10 | Exact | Punctuation | Gold substring | ROUGE-L F1 | Judge |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| extractive | 0.411 | 0.000 | 0.000 | 0.040 | 0.037 | 200 judged / acc 0.06 |
| top-context-extractive | 0.411 | 0.000 | 0.000 | 0.120 | 0.066 | 200 judged / acc 0.15 |

The retrieval numbers are from separate CUDA runs with the same configuration,
so they are aligned but not bit-identical. The answer-generation direction
repeats: restricting extraction to the top returned context improves substring
accuracy and ROUGE-L on the 200-sample run, but the absolute answer score is
still low. The judged result repeats the DMR 50 direction with a smaller
absolute judge gain: DMR 200 judge accuracy rises from `0.06` to `0.15`.


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
  --judge-model deepseek-v4-flash `
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
| LLM judge status | 50 judged / 0 error |
| LLM judge accuracy | 0.08 |
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

## DMR 50 Top-Context Judge Run

This repeats the DMR 50 top-context generator with the DeepSeek judge enabled.
It is still evaluation-only: it does not change runtime defaults, memory
schema, CLI behavior, or the pinned extractive baseline reports.

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 50 `
  --mode vectors-rerank `
  --generator top-context-extractive `
  --llm-judge deepseek `
  --judge-model deepseek-v4-flash `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-50-top-context-judge.json `
  --cleanup-cache
```

| Metric | Value |
| --- | ---: |
| Sample size | 50 |
| Retrieval mode | vectors + reranker |
| Retrieval Recall@10 | 0.468 |
| Retrieval MRR@10 | 0.618 |
| Generator | top-context-extractive |
| Exact accuracy | 0.000 |
| Punctuation-normalized accuracy | 0.020 |
| Gold-answer substring accuracy | 0.220 |
| ROUGE-L precision mean | 0.073 |
| ROUGE-L recall mean | 0.288 |
| ROUGE-L F1 mean | 0.103 |
| LLM judge status | 50 judged / 0 error |
| LLM judge accuracy | 0.26 |
| P50 query latency | 607.1 ms |
| P95 query latency | 671.1 ms |
| Peak GPU total memory | 4855.7 MiB |

Read: DMR 50 top-context is now judge-scored. Compared with the pinned
extractive DMR 50 run, judge accuracy rises from `0.08` to `0.26`, substring
accuracy rises from `0.060` to `0.220`, and ROUGE-L F1 rises from `0.041` to
`0.103`, while retrieval Recall@10 stays `0.468`. This supports answer
synthesis as a real optimization surface, but it remains a small local
candidate result until DMR 200 / 500 top-context judge scoring and
published-comparable policy work are complete.

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
after judge authorization was fixed on `deepseek-v4-flash`. It uses CUDA
retrieval and the same sanitized answer-generation report shape. It does not
commit raw questions, answers, dialogs, sessions, generated answers, or the API
key.

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 5 `
  --dmr-answer-match punctuation `
  --mode vectors-rerank `
  --k 10 `
  --generator extractive `
  --llm-judge deepseek `
  --judge-model deepseek-v4-flash `
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
| LLM judge status | 5 judged / 0 error |
| HTTP status | 200 |
| LLM judge accuracy | 0.2 |

## Judge Preflight

This preflight isolates the DeepSeek judge configuration from DMR retrieval,
answer generation, CUDA, and dataset mapping. It sends one synthetic judgement
request and commits only sanitized status metadata.

```powershell
python scripts/eval/deepseek_judge_preflight.py `
  --output crates/eval/reports/official-dmr-judge-preflight.json
```

| Field | Value |
| --- | --- |
| API key present | true |
| API key committed | false |
| Prompt text recorded | false |
| Raw response committed | false |
| Status | judged |
| HTTP status | 200 |
| Decision | ready_for_official_dmr_judge_rerun |

Read: this preflight opened the path for the pinned extractive official runs,
and those runs now serialize cleanly through it.

## Top-Context Candidate Judge Preflight

After the extractive baseline became judge-backed, the next evidence gap was
the `top-context-extractive` candidate. The latest isolated preflight confirms
that `deepseek-v4-flash` can judge through the current environment without
committing prompt text, raw response text, raw DMR records, answers, generated
answers, or API keys.

```powershell
python scripts/eval/deepseek_judge_preflight.py `
  --judge-model deepseek-v4-flash `
  --output crates/eval/reports/official-dmr-top-context-judge-preflight.json
```

| Field | Value |
| --- | --- |
| API key present | true |
| API key committed | false |
| Prompt text recorded | false |
| Raw response committed | false |
| Model | deepseek-v4-flash |
| Status | judged |
| HTTP status | 200 |
| Decision | ready_for_official_dmr_judge_rerun |

Read: the pinned extractive reports remain judge-backed evidence, and DMR 50 /
200 / 500-request top-context are now judge-backed evidence too.

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
            crates/eval/reports/official-dmr-50-top-context-judge.json `
  --output crates/eval/reports/official-dmr-generator-ablation-dmr-50.json
```

And the DMR 200 generator ablation:

```powershell
python scripts/eval/official_dmr_answer_audit.py `
  --reports crates/eval/reports/official-dmr-200.json `
            crates/eval/reports/official-dmr-200-top-context-judge.json `
  --output crates/eval/reports/official-dmr-generator-ablation-dmr-200.json
```

And the DMR 500-request generator ablation:

```powershell
python scripts/eval/official_dmr_answer_audit.py `
  --reports crates/eval/reports/official-dmr-500.json `
            crates/eval/reports/official-dmr-500-top-context-judge.json `
  --output crates/eval/reports/official-dmr-generator-ablation-dmr-500.json
```

The consolidated generator ablation summary is generated from those three
sanitized audit files:

```powershell
python scripts/eval/dmr_generator_ablation_summary.py
```

The bottleneck taxonomy consolidates mapping, retrieval/ranking, and generator
opportunity loss:

```powershell
python scripts/eval/official_dmr_bottleneck_taxonomy.py
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

Generator delta summary:

| Run | Substring delta | ROUGE-L F1 delta | Top-1 without substring delta |
| --- | ---: | ---: | ---: |
| DMR 50 | +0.160 | +0.062 | -8 |
| DMR 200 | +0.080 | +0.030 | -16 |
| DMR 500 request / 323 scored | +0.074 | +0.035 | -27 |

## Bottleneck Taxonomy

The taxonomy report makes the current DMR boundary explicit:

| Boundary | Largest local view | Read |
| --- | ---: | --- |
| Mapping coverage | 177 punctuation-mapping rejections before scoring | The 500-request view honestly scores `323/500`; relaxed token containment is diagnostic only. |
| Retrieval / ranking | 114/323 scored samples without a relevant top-10 retrieval | Generator work cannot recover samples without a relevant top-10 context. |
| Answer synthesis after top-1 retrieval | 118/128 top-1 hits still miss the gold substring | Retrieval can find a relevant top chunk while the extractive generator still fails to answer. |
| Top-context residual | 91 top-1 hits still miss after top-context extraction | The candidate generator improves the direction but is not enough for official claims. |

Read: DMR is not blocked by one single defect. The current evidence separates
three bottlenecks: mapping coverage, retrieval/ranking, and answer synthesis.
Top-context extraction is the clearest generator direction, but it remains
eval-only and still leaves substantial residual loss.

## Failure Mode Taxonomy

The DMR 500 failure-mode taxonomy is recorded in
`docs/eval/DMR_FAILURE_MODE_TAXONOMY.md` and
`crates/eval/reports/dmr-failure-mode-taxonomy.json`.

| Outcome | Count | Share of requested | Share of unresolved |
| --- | ---: | ---: | ---: |
| Mapping rejected before scoring | 177 | 35.40% | 39.42% |
| Retrieval top-10 miss | 109 | 21.80% | 24.28% |
| Top-context ranking boundary | 80 | 16.00% | 17.82% |
| Top-1 answer-synthesis failure | 83 | 16.60% | 18.49% |
| Judge-correct success | 51 | 10.20% | n/a |

Read: the largest unresolved bucket is mapping coverage under the pinned
punctuation policy. Among scored rows, retrieval/ranking and answer synthesis
are both material. This supports failure-directed validation work, not a
runtime default change.

## Mapping Boundary Impact

The DMR mapping-boundary impact audit is recorded in
`docs/eval/DMR_MAPPING_BOUNDARY_IMPACT.md` and
`crates/eval/reports/dmr-mapping-boundary-impact.json`.

| Punctuation-rejected boundary class | Count | Share of rejected |
| --- | ---: | ---: |
| All significant answer tokens present in one chunk | 122 | 68.93% |
| 75-99% significant-token overlap | 27 | 15.25% |
| 50-74% significant-token overlap | 18 | 10.17% |
| Any significant token only | 7 | 3.95% |
| No diagnostic significant-token match | 3 | 1.69% |

Read: `0/500` rows have empty memory chunks. Of the `177` rows rejected by
the pinned punctuation policy, `174` still have some diagnostic token match and
`122` contain all significant answer tokens in one chunk. This moves the main
mapping question to defensible scoring policy, not empty memory construction.

## Top-Context Significance

The DMR top-context significance audit is recorded in
`docs/eval/DMR_TOP_CONTEXT_SIGNIFICANCE.md` and
`crates/eval/reports/dmr-top-context-significance.json`.

| Scale | Judge delta | Candidate-only | Baseline-only | McNemar p-value |
| --- | ---: | ---: | ---: | ---: |
| DMR 50 | +0.180 | 9 | 0 | 0.00390625 |
| DMR 200 | +0.090 | 23 | 5 | 0.000912234187 |
| DMR 500 request / 323 scored | +0.108 | 41 | 6 | 1.7717e-07 |

Read: the top-context direction is positive and statistically supported across
all completed local scale views. The result is strongest when the relevant
context is already ranked first; `top10_not_top1` remains a ranking boundary
because the top-context generator reads rank 1 only.

## Read

Engineering result:

These runs prove the official-style DMR task shape can execute locally on
CUDA: retrieval -> answer generation -> gold-answer scoring. The largest
completed local pass is now the DMR 500-request run, with `323/500` requested
samples scored under the pinned punctuation mapping policy.

The larger runs confirm the DMR 50 trend: retrieval remains useful but not
enough. Recall@10 moved from `0.468` on DMR 50 to `0.411` on DMR 200 and
`0.381` on the DMR 500-request run. Gold-answer substring accuracy stayed low:
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
from `118/128` to `91/128`. Judge accuracy rises from `0.050` to `0.158`.
This makes the generator direction repeat across DMR 50, 200, and the largest
pinned local run. The consolidated
machine-readable summary is
`crates/eval/reports/official-dmr-generator-ablation-summary.json`; it also
records that the extractive baseline reports are judge-backed on all pinned
runs while the top-context generator ablation is judge-backed on DMR 50,
DMR 200, and the 500-request / 323-scored view.

Research interpretation:

The current evidence does not point to a core architecture failure. It points
to a narrower DMR boundary: candidate retrieval/ranking is imperfect, and the
simple deterministic extractive generator does not reliably turn returned
chunks into clean answers. The DMR 500-request run adds a third boundary:
under the current punctuation mapping policy, the public candidate file does
not yield 500 scored official-style examples. The mapping policy review keeps
punctuation full-answer mapping as the pinned local boundary and treats
relaxed-token mapping as a separate diagnostic option.

The LLM judge path now produces judged samples on `deepseek-v4-flash` for the
pinned official runs and the DMR 50 / 200 / 500-request top-context candidates.
The DMR 50 run returned `50` judged samples; the DMR 200 run returned `200`
judged samples; the 500-request run returned `323` judged samples on the
mappable subset; the DMR 50 top-context candidate returned `50` judged
samples; the DMR 200 top-context candidate returned `200` judged samples; and
the DMR 500-request top-context candidate returned `323` judged samples. The
5-sample probe also returned `5/5` judged samples, and the isolated DeepSeek
preflight confirms HTTP `200` with an API key present before any DMR retrieval
or answer generation runs. Judge output is now stable on the pinned runs and
all top-context scale views, so the remaining evidence boundaries are
retrieval/ranking quality, answer synthesis, and answer-to-memory mapping
coverage.

## Boundary

This is still not a published-comparable official DMR benchmark result.

Reasons:

- the generator is a deterministic extractive baseline, not a fixed agent
  answer policy;
- the better DMR 50/200/500-request generator ablation is eval-only evidence;
  DMR 50, DMR 200, and the 500-request / 323-scored view are judge-scored, but
  the candidate has not been adopted as a runtime default, validated by
  LongMemEval, or evaluated under a published-comparable official DMR protocol;
- the LLM judge path is now stable on the pinned extractive runs; the remaining
  evidence boundaries are answer-generation quality and answer-to-memory
  mapping coverage;
- the DMR 500-request run scored 323/500 requested samples because the pinned
  answer-to-memory mapping policy exhausted mappable rows;
- the public DMR candidate mapping still uses the pinned punctuation policy;
- raw questions, answers, dialogs, sessions, and generated answer text are not
  committed.

## Next Step

Keep feature growth frozen, keep the judge path on `deepseek-v4-flash`, and do
not rerun DMR 50/200/500 top-context unless the gate asks for a reproducibility
check. The DMR top-context judge-scaling branch is complete. The next heavy
validation branch should be hosted external comparison once credentials or
endpoints are configured; meanwhile, no-model failure analysis can continue.
Any relaxed-token coverage run must be separately labeled and validated before
it is used for conclusions.
