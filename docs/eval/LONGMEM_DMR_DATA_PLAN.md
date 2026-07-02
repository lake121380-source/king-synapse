# LongMemEval / DMR Data Plan

Date checked: 2026-07-02

Status: smoke runner implemented and run. No LongMemEval or DMR raw dataset
records are committed in this repository.

## Validation Purpose

LongMemEval and DMR are Stage 6 system-validation inputs, not new product
features.

- LongMemEval checks long-horizon memory behavior across sessions, updates,
  temporal questions, and abstention.
- DMR is a smaller fact-retrieval sanity check used by memory-agent literature.
- Neither benchmark replaces the exported cognitive-session fixture, because
  neither directly validates hidden-trace dominance, suppressed alternatives,
  or reinforcement isolation.

## Source And License Check

| Dataset | Source | License / status | Stage 6 decision |
| --- | --- | --- | --- |
| LongMemEval cleaned | <https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned> | Hugging Face dataset card lists `mit`. | Use for first smoke test. Prefer the smallest cleaned split before larger runs. |
| LongMemEval original repo | <https://github.com/xiaowu0162/longmemeval> | Repository includes an MIT license and points to the released Hugging Face data. | Use as implementation reference only; fetch data from Hugging Face cache. |
| LongMemEval-V2 | <https://huggingface.co/datasets/xiaowu0162/longmemeval-v2> | Hugging Face dataset card lists `apache-2.0`; the public package includes multimodal files and is much larger than the first smoke test needs. | Do not use in the first smoke test. Revisit after the cleaned dataset path is stable. |
| DMR candidate data | <https://huggingface.co/datasets/MemGPT/MSC-Self-Instruct> | Hugging Face dataset card lists `apache-2.0`; 500 rows are available in the train split. | Use as the DMR candidate only after recording that the exact original DMR harness has not been reproduced yet. |
| Upstream MSC context | <https://parl.ai/projects/msc/> | Upstream conversational source for MSC-style data. | Do not redistribute mirrored records. Keep only cache instructions and aggregate reports in this repo. |

DMR note: the checked public sources make the MemGPT `MSC-Self-Instruct`
dataset the practical candidate for a DMR smoke test, but this plan should not
claim an official DMR reproduction until the original harness and scoring rules
are pinned.

## Cache Rules

Dataset files must be fetched into a user cache outside the Git worktree.

Default cache roots:

```text
Windows: %LOCALAPPDATA%\king-synapse\eval
Unix:    ${XDG_CACHE_HOME:-$HOME/.cache}/king-synapse/eval
```

Repository paths such as `crates/eval/datasets/longmemeval/` and
`crates/eval/datasets/dmr/` are reserved contract paths, but raw third-party
records should not be checked in there.

Allowed committed artifacts:

- fetch/cache instructions;
- checksums and source URLs;
- small aggregate reports with counts and scores;
- failure notes and schema summaries.

Forbidden committed artifacts:

- raw LongMemEval or DMR examples;
- copied conversations;
- generated answer text containing third-party records;
- API keys, bearer tokens, hosted dataset credentials, or private endpoint
  details.

## Fetch Commands

Install fetch tooling outside the repository:

```powershell
python -m pip install huggingface_hub datasets
```

LongMemEval cleaned smoke cache:

```powershell
$cache = Join-Path $env:LOCALAPPDATA 'king-synapse\eval\longmemeval-cleaned'
New-Item -ItemType Directory -Force $cache | Out-Null
huggingface-cli download xiaowu0162/longmemeval-cleaned `
  --repo-type dataset `
  --local-dir $cache
```

DMR candidate cache:

```powershell
$cache = Join-Path $env:LOCALAPPDATA 'king-synapse\eval\dmr-msc-self-instruct'
New-Item -ItemType Directory -Force $cache | Out-Null
huggingface-cli download MemGPT/MSC-Self-Instruct `
  --repo-type dataset `
  --local-dir $cache
```

After download, record checksums outside the raw-data files:

```powershell
Get-ChildItem $cache -File -Recurse | Get-FileHash -Algorithm SHA256
```

## Smoke Test Design

### LongMemEval Smoke

Initial scope:

- load a deterministic 10-example sample from the smallest cleaned split;
- cover extraction, multi-session reasoning, temporal reasoning, update, and
  abstention if those fields are present;
- fail closed if the dataset schema does not match the loader's expected
  fields;
- report only aggregate scores and anonymized example identifiers.

Minimum report fields:

- source dataset and revision if available;
- local cache path omitted or redacted;
- SHA256 checksums;
- sample size and category counts;
- judge mode: exact match, heuristic, or LLM-as-judge;
- model name if an LLM judge is used;
- pass/fail and per-category aggregate metrics.

### DMR Smoke

Initial scope:

- load a deterministic 20-row sample from `MemGPT/MSC-Self-Instruct`;
- score retrieval sanity first, before adding any LLM judge;
- report whether the expected answer or target fact appears in top-k retrieved
  memory;
- mark the run as `dmr-candidate` until the exact original DMR harness is
  pinned.

Minimum report fields:

- source dataset and revision if available;
- SHA256 checksums;
- sample size;
- top-k setting;
- exact/substring/semantic scoring mode;
- aggregate hit rate;
- unsupported or ambiguous rows count.

## Before Any Full Run

Do not run a full benchmark until these are true:

1. dataset license fields are rechecked from the source pages;
2. raw data is cached outside the repository;
3. the loader records checksums and source revisions;
4. the sample policy is deterministic;
5. no third-party records are committed;
6. any LLM judge records model name, provider mode, and credential names only;
7. the report clearly separates King Synapse cognitive-trace metrics from
   ordinary long-memory retrieval metrics.

## Smoke Run 2026-07-02

Runner:

```powershell
python scripts/eval/longmem_dmr_smoke.py `
  --endpoint https://hf-mirror.com `
  --cleanup-cache
```

Report:

`crates/eval/reports/longmem-dmr-smoke-latest.json`

The runner:

- downloaded raw data to the user cache;
- generated temporary TOML datasets for the existing `kr-eval` binary;
- ran FTS/entity recall only;
- wrote a sanitized aggregate report;
- excluded raw questions, answers, dialogs, and session text;
- removed the raw cache after the run.

| Dataset | Sample | Memory chunks | Recall@5 | Recall@10 | MRR@10 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LongMemEval cleaned | 10/10 | 484 | 0.600 | 0.817 | 0.383 | 0.510 |
| DMR candidate MSC-Self-Instruct | 20/20 | 100 | 0.192 | 0.317 | 0.124 | 0.162 |

Interpretation:

- LongMemEval cleaned smoke is viable as the first long-memory loader path.
- DMR remains a candidate benchmark until the original harness is pinned.
- The low DMR candidate score is a baseline signal, not a product regression:
  the run used only existing FTS/entity recall and no vector branch, reranker,
  LLM judge, or cognitive-trace adaptation.

## Retrieval Branch Check 2026-07-02

Additional reports:

- `crates/eval/reports/longmem-dmr-smoke-vector.json`
- `crates/eval/reports/longmem-dmr-smoke-vector-rerank.json`

The branch check used the same deterministic smoke samples and changed only the
retrieval mode.

| Dataset | Mode | Recall@5 | Recall@10 | MRR@10 | NDCG@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| LongMemEval cleaned | baseline FTS/entity | 0.600 | 0.817 | 0.383 | 0.510 |
| LongMemEval cleaned | vector | 0.800 | 1.000 | 0.611 | 0.717 |
| LongMemEval cleaned | vector + reranker | 0.617 | 0.800 | 0.673 | 0.659 |
| DMR candidate MSC-Self-Instruct | baseline FTS/entity | 0.192 | 0.317 | 0.124 | 0.162 |
| DMR candidate MSC-Self-Instruct | vector | 0.267 | 0.333 | 0.178 | 0.204 |
| DMR candidate MSC-Self-Instruct | vector + reranker | 0.583 | 0.658 | 0.403 | 0.454 |

Failure analysis from anonymized IDs:

- LongMemEval vector-only recovered all sampled misses, but reranker moved
  three previously relevant results out of the top 10.
- DMR vector-only did not change the top-10 miss count: 13/20 rows still had
  zero Recall@10.
- DMR vector + reranker reduced zero Recall@10 rows from 13/20 to 6/20.
- DMR vector + reranker recovered these vector misses:
  `9a43753c58bb6bac`, `fbb4d10243d62605`, `08f41b439a71adf4`,
  `4c4b25f96d26acff`, `531d84aa5ba3fb36`, `268837a04a32ba8e`,
  `6481289551ed1a75`.
- DMR vector + reranker still missed:
  `57b6b989521797c9`, `c46541722e486083`, `776cf885e5ecaeaa`,
  `f854941b0186f8c0`, `80a1b939a7e18a9f`, `f411b444bd9e28b1`.
- One DMR sample, `9fd144e79228209f`, was hurt by reranking versus vector-only.

Decision gate:

| Observed result | Decision |
| --- | --- |
| Vector-only made LongMemEval perfect on the smoke sample. | Keep vector as a serious validation branch. |
| Vector-only barely moved DMR from 0.317 to 0.333. | DMR is not solved by dense recall alone. |
| Vector + reranker moved DMR to 0.658. | Ranking is a real DMR bottleneck for selected valid rows. |
| Vector + reranker reduced LongMemEval from 1.000 to 0.800 and had high latency. | Do not make reranker the default from this smoke result. |
| 112 DMR candidate rows were skipped before selecting 20 valid rows. | Data mapping and candidate quality still need inspection. |

Next step: expand the same three-way comparison to LongMemEval 50 and DMR 50.
Before changing memory schema or chunking, add an anonymized rank-bucket field
so remaining failures can be separated into `top_10`, `top_50`, and `absent`.
