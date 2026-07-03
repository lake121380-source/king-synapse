# Official DMR Answer-Generation Result

Date: 2026-07-03

Status: answer-generation harness smoke passed; full official DMR result is not
complete.

Machine-readable report:

`crates/eval/reports/official-dmr-5-extractive.json`

## What Changed

Synapse now has a DMR evaluation path that goes beyond candidate retrieval:

1. retrieve memory chunks with `kr-eval`;
2. generate an answer from returned chunks;
3. score the generated answer against the gold answer;
4. write only sanitized metrics and hashes.

The runner is:

`scripts/eval/official_dmr_eval.py`

## Run

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

## Result

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

This run proves the official DMR task shape can execute locally on CUDA:
retrieval -> answer generation -> gold-answer scoring.

It also shows the next real gap. Candidate retrieval can surface answer-bearing
chunks, but a simple deterministic extractive generator does not reliably turn
those chunks into a clean answer. The current answer-generation score is
therefore low even when retrieval finds relevant context.

## Boundary

This is not a published-comparable official DMR benchmark result.

Reasons:

- only 5 examples were run;
- the generator is a deterministic extractive baseline, not a fixed agent
  answer policy;
- no LLM judge was requested;
- the public DMR candidate mapping still uses the pinned punctuation policy;
- raw questions, answers, dialogs, sessions, and generated answer text are not
  committed.

## Next Step

Run the same harness on 50 examples with the same CUDA settings, then add a
fixed judge configuration. Only after that should the project claim an
official-style DMR 50 result.
