# Official DMR Review

Date checked: 2026-07-02

Status: answer-generation harness smoke exists; full official DMR reproduction
is not complete.

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

`scripts/eval/official_dmr_eval.py` now runs the official-style task shape on a
small sample:

- retrieve candidate memory chunks with `kr-eval`;
- generate an answer from returned chunks;
- score against the gold answer with exact, punctuation-normalized, and
  ROUGE-L metrics;
- optionally call an LLM judge when explicitly configured;
- commit only sanitized metrics and hashes.

Current smoke report:

- `crates/eval/reports/official-dmr-5-extractive.json`
- `docs/eval/OFFICIAL_DMR_RESULT.md`

The 5-query CUDA smoke passed, but it is not a published-comparable DMR result.
It used a deterministic extractive generator and no LLM judge.

## What Official DMR Still Requires

Before this repo can claim an official DMR result, it needs:

1. fixed official dataset and split policy;
2. conversation ingestion that matches the benchmark's intended setup;
3. 50/200/500-query answer-generation runs, not only the current 5-query
   smoke;
4. fixed judge model, judge prompt, and provider configuration;
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
answer-generation validation has started, while full official DMR reproduction
remains a Phase 6 gap.
