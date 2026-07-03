# Official DMR Review

Date checked: 2026-07-02

Status: answer-generation DMR 50 local scoring exists; the DeepSeek judge now
authenticates on `deepseek-v4-flash`, but judge-output stability is still
incomplete.

## Short Answer

The current King Synapse DMR reports are valid as DMR candidate retrieval
baselines, but they are not official DMR benchmark results.

Official DMR-style evaluation asks the system to answer a question from prior
multi-session conversation history, then scores the generated answer against a
gold answer. The current Synapse runner instead checks whether retrieval brings
back answer-bearing memory chunks.

## Sources Checked

| Source | What it says | Impact on this repo |
| --- | --- | --- |
| MemGPT paper, arXiv `2310.08560` | DMR asks a question about an earlier conversation, scores the agent response against the gold answer, and reports accuracy plus ROUGE-L recall. The paper also describes an LLM judge for DMR answer correctness. | Official DMR is answer-generation scoring, not only chunk retrieval scoring. |
| `MemGPT/MSC-Self-Instruct` on Hugging Face | Public Apache-2.0 self-instruct MSC dataset generated while evaluating MemGPT. | This is the practical public candidate dataset used by the Synapse smoke runner. |
| Zep paper, arXiv `2501.13956` | Describes DMR as 500 multi-session conversations with question/answer pairs, then evaluates generated responses with an LLM judge against golden answers. | External published DMR numbers are accuracy-style answer-generation numbers, not Recall@10 retrieval numbers. |

References:

- <https://arxiv.org/abs/2310.08560>
- <https://huggingface.co/datasets/MemGPT/MSC-Self-Instruct>
- <https://arxiv.org/abs/2501.13956>

## What Synapse Measures Today

The current runner:

- downloads `MemGPT/MSC-Self-Instruct` to a user cache;
- converts each accepted row into temporary memory chunks;
- runs three retrieval modes: baseline RRF, vector, and vector + reranker;
- scores whether answer-bearing chunks appear in the returned candidates;
- reports Recall@5, Recall@10, MRR@10, NDCG@10, rank buckets, and skips;
- commits only sanitized aggregate reports.

This is useful because it isolates retrieval, ranking, and mapping quality
without letting answer generation or judge variability hide the retrieval
failure mode.

## Answer-Generation Smoke

`scripts/eval/official_dmr_eval.py` now runs the official-style task shape:

- retrieve candidate memory chunks with `kr-eval`;
- generate an answer from returned chunks;
- score against the gold answer with exact, punctuation-normalized, and
  ROUGE-L metrics;
- optionally call an LLM judge when explicitly configured;
- commit only sanitized metrics and hashes.

Current reports:

- `crates/eval/reports/official-dmr-50.json`
- `crates/eval/reports/official-dmr-200.json`
- `crates/eval/reports/official-dmr-500.json`
- `crates/eval/reports/official-dmr-judge-probe.json`
- `crates/eval/reports/official-dmr-judge-preflight.json`
- `crates/eval/reports/official-dmr-5-extractive.json`
- `docs/eval/OFFICIAL_DMR_RESULT.md`

The 50-query CUDA run completed local answer scoring. Exact accuracy was
`0.000`, punctuation-normalized accuracy was `0.020`, answer-substring accuracy
was `0.060`, and ROUGE-L F1 mean was `0.041`.

The DeepSeek judge path is now live on `deepseek-v4-flash`, but it still
returns malformed JSON on many requests. The 50, 200, and 500 request runs all
have judged samples, so judge-backed scoring is available, but it is not yet
fully stable enough for official DMR claims.

## What Official DMR Still Requires

Before this repo can claim an official DMR result, it needs:

1. fixed official dataset and split policy;
2. conversation ingestion that matches the benchmark's intended setup;
3. successful fixed LLM judge scoring with stable JSON output;
4. 200/500-query answer-generation runs after the DMR 50 path is stable;
5. accuracy and ROUGE-L style reporting that can be compared with MemGPT/Zep
   numbers;
6. raw-data and credential handling that keeps third-party records and secrets
   out of the repository;
7. GPU-first execution for model-heavy embedding, reranking, or generation
   runs.

## Decision

Keep the existing DMR reports as candidate retrieval baselines:

- `crates/eval/reports/dmr-50-validation.json`
- `crates/eval/reports/dmr-50-punctuation-validation.json`
- `docs/eval/VALIDATION_DMR_50.md`
- `docs/eval/VALIDATION_DMR_50_PUNCTUATION.md`

Do not compare their Recall@10 values directly with MemGPT or Zep DMR accuracy
claims. The current conclusion remains narrower: Synapse has a retrieval and
ranking signal on the public DMR candidate data, while official DMR
answer-generation validation has started, but judge-output stability still
needs work before full official reproduction can be claimed.
