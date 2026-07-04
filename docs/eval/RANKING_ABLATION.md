# Ranking Ablation

Date: 2026-07-04

Status: DMR 50 ranking ablations, DMR 50 chunk-policy/query-expansion
ablations, DMR 200 ranking-failure expansion, DMR 200 transition audit,
DMR/LongMemEval 50 RRF/vector-weight cross-checks, pool-signal guard audit, and
objective-conflict audit complete.

Machine-readable reports:

`crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json`

`crates/eval/reports/ranking-ablation-dmr-50-top-k.json`

`crates/eval/reports/ranking-ablation-dmr-50-chunk-policy.json`

`crates/eval/reports/ranking-ablation-dmr-50-query-expansion.json`

`crates/eval/reports/ranking-failure-audit-dmr-50.json`

`crates/eval/reports/ranking-transition-audit-dmr-50.json`

`crates/eval/reports/dmr-200-punctuation-validation.json`

`crates/eval/reports/ranking-ablation-dmr-200-top-k.json`

`crates/eval/reports/ranking-ablation-dmr-200-reranker-pool.json`

`crates/eval/reports/ranking-ablation-dmr-200-reranker-pool-signal.json`

`crates/eval/reports/ranking-ablation-dmr-500-reranker-pool-signal.json`

`crates/eval/reports/ranking-ablation-dmr-longmem-50-reranker-pool-signal.json`

`crates/eval/reports/ranking-ablation-longmem-200-reranker-pool-signal.json`

`crates/eval/reports/ranking-ablation-longmem-500-reranker-pool-signal.json`

`crates/eval/reports/ranking-failure-audit-dmr-200.json`

`crates/eval/reports/ranking-transition-audit-dmr-200.json`

`crates/eval/reports/ranking-ablation-longmem-50-reranker-pool.json`

`crates/eval/reports/ranking-ablation-dmr-longmem-50-rrf-k.json`

`crates/eval/reports/ranking-ablation-dmr-longmem-50-vector-weight.json`

`crates/eval/reports/ranking-vector-weight-transition-audit-dmr-longmem-50.json`

`crates/eval/reports/ranking-late-rank-audit-dmr-50-200.json`

`crates/eval/reports/ranking-reranker-pool-transition-audit-dmr-200.json`

`crates/eval/reports/ranking-pool-signal-trigger-audit-dmr-200.json`

`crates/eval/reports/ranking-pool-signal-crosscheck-dmr-longmem-50.json`

`crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json`

`crates/eval/reports/ranking-objective-conflict-audit.json`

Runner:

`scripts/eval/ranking_ablation.py`

Failure audit runner:

`scripts/eval/ranking_failure_audit.py`

Transition audit runner:

`scripts/eval/ranking_transition_audit.py`

Vector-weight transition audit runner:

`scripts/eval/ranking_vector_weight_transition_audit.py`

Late-rank audit runner:

`scripts/eval/ranking_late_rank_audit.py`

Reranker-pool transition audit runner:

`scripts/eval/ranking_reranker_pool_transition_audit.py`

Pool signal trigger audit runner:

`scripts/eval/ranking_pool_signal_trigger_audit.py`

Pool signal cross-check runner:

`scripts/eval/ranking_pool_signal_crosscheck.py`

Pool signal guard audit runner:

`scripts/eval/ranking_pool_signal_guard_audit.py`

Objective-conflict audit runner:

`scripts/eval/ranking_objective_conflict_audit.py`

Chunk-policy runner:

`scripts/eval/dmr_chunk_ablation.py`

Query-expansion runner:

`scripts/eval/dmr_query_expansion_ablation.py`

## Reranker Pool Scope

This pass varies one ranking parameter only:

`reranker_pool`

Everything else is fixed:

- dataset: DMR candidate MSC-Self-Instruct;
- sample size: 50;
- answer mapping: punctuation-normalized;
- retrieval mode: RRF + vectors + reranker;
- top-k returned by `kr-eval`: 10;
- accelerator: CUDA device `0`;
- embedding batch `32`, embedding max length `256`;
- reranker batch `32`, reranker max length `256`.

`kr-eval` now exposes `--rrf-k`, `--fts-weight`, `--entity-weight`, and
`--vector-weight`. This pass still varies only `reranker_pool`; chunk size and
query expansion remain in their own runners.

## Reranker Pool Command

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets dmr `
  --dmr-sample-size 50 `
  --dmr-answer-match punctuation `
  --k 10 `
  --reranker-pools 10,25,50,100 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json `
  --cleanup-cache
```

## Reranker Pool Result

| Reranker pool | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.445 | 0.502 | 169.2 ms | 23 | 8 | 19 |
| 25 | 0.453 | 0.608 | 321.6 ms | 27 | 9 | 14 |
| 50 | 0.468 | 0.618 | 636.9 ms | 28 | 10 | 12 |
| 100 | 0.448 | 0.623 | 1226.1 ms | 28 | 10 | 12 |

## Reranker Pool Read

The current default-style pool `50` remains the best Recall@10 setting in this
DMR 50 pass.

Pool `100` slightly improves MRR (`+0.005`) but lowers Recall@10 and roughly
doubles P50 latency versus pool `50`. That is not a clear default.

Pool `10` is much faster, but it loses five top-1 hits and adds seven retrieval
misses versus pool `50`.

Pool `25` is a possible speed/quality compromise, but it still trails pool `50`
on Recall@10, MRR@10, top-1 hits, and retrieval misses.

## Top-K Scope

This pass varies one ranking parameter only:

`top_k`

Everything else is fixed:

- dataset: DMR candidate MSC-Self-Instruct;
- sample size: 50;
- answer mapping: punctuation-normalized;
- retrieval mode: RRF + vectors + reranker;
- reranker pool: 50;
- accelerator: CUDA device `0`;
- embedding batch `32`, embedding max length `256`;
- reranker batch `32`, reranker max length `256`.

## Top-K Command

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets dmr `
  --dmr-sample-size 50 `
  --dmr-answer-match punctuation `
  --ablation top-k `
  --top-k-values 10,25,50 `
  --fixed-reranker-pool 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-50-top-k.json `
  --cleanup-cache
```

## Top-K Result

| Top-k | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.468 | 0.619 | 630.3 ms | 28 | 10 | 0 | 12 |
| 25 | 0.468 | 0.620 | 633.7 ms | 28 | 10 | 1 | 11 |
| 50 | 0.468 | 0.623 | 672.5 ms | 28 | 10 | 6 | 6 |

## Top-K Read

Increasing top-k does not improve Recall@10, top-1 hits, or top-10 placement.
That means the published candidate metric remains unchanged at the decision
surface.

But increasing top-k does reveal six additional answer-bearing chunks between
rank 11 and rank 50. The DMR 50 miss count drops from `12` at top-k `10` to
`6` at top-k `50`.

This is useful diagnostic evidence: some DMR failures are not pure retrieval
absence. They are late-ranking failures where the relevant memory exists in the
wider candidate list but does not reach the top 10.

## Chunk-Policy Scope

This pass varies one data-mapping parameter only:

`chunk_policy`

Everything else is fixed:

- dataset: DMR candidate MSC-Self-Instruct;
- sample size: 50;
- answer mapping: punctuation-normalized;
- sample selection: same 50 source rows selected by the current dialog chunk
  policy;
- retrieval mode: RRF + vectors + reranker;
- top-k returned by `kr-eval`: 50;
- reranker pool: 50;
- accelerator: CUDA device `0`;
- embedding batch `32`, embedding max length `256`;
- reranker batch `32`, reranker max length `256`.

This is an evaluation-only ablation. It does not change the memory schema,
recall defaults, product CLI, or ranking semantics.

## Chunk-Policy Command

```powershell
python scripts/eval/dmr_chunk_ablation.py `
  --endpoint https://hf-mirror.com `
  --sample-size 50 `
  --k 50 `
  --mode vectors-rerank `
  --reranker-pool 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-50-chunk-policy.json `
  --cleanup-cache
```

## Chunk-Policy Result

| Chunk policy | Memory chunks | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 only | Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dialog | 250 | 0.468 | 0.623 | 689.1 ms | 28 | 10 | 6 | 6 |
| merged-session | 50 | 0.360 | 0.211 | 921.6 ms | 7 | 11 | 32 | 0 |

## Chunk-Policy Read

The merged-session policy removes the six top-50 retrieval misses in this DMR
50 sample, so larger chunks improve broad candidate coverage.

But it sharply hurts ranking quality: Recall@10 drops from `0.468` to `0.360`,
MRR@10 drops from `0.623` to `0.211`, and top-1 hits fall from `28` to `7`.
The missed evidence mostly moves into the top-50-only bucket (`32` cases), not
into the decision surface.

This means the current DMR issue is not solved by simply merging dialogs into
larger memory chunks. Coarse chunks make the answer-bearing memory easier to
include somewhere in the candidate set, but they dilute the ranking signal
needed to place it in top 10.

## Query-Expansion Scope

This pass varies one query-mapping parameter only:

`query_policy`

Everything else is fixed:

- dataset: DMR candidate MSC-Self-Instruct;
- sample size: 50;
- answer mapping: punctuation-normalized;
- sample selection: same 50 source rows selected by the current dialog chunk
  policy;
- chunk policy: dialog chunks;
- retrieval mode: RRF + vectors + reranker;
- top-k returned by `kr-eval`: 50;
- reranker pool: 50;
- accelerator: CUDA device `0`;
- embedding batch `32`, embedding max length `256`;
- reranker batch `32`, reranker max length `256`.

The tested `keyword-boost` policy appends question-derived content keywords
twice. It uses only the question text and does not inspect memory chunks or
gold answers.

## Query-Expansion Command

```powershell
python scripts/eval/dmr_query_expansion_ablation.py `
  --endpoint https://hf-mirror.com `
  --sample-size 50 `
  --k 50 `
  --mode vectors-rerank `
  --reranker-pool 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-50-query-expansion.json `
  --cleanup-cache
```

## Query-Expansion Result

| Query policy | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 only | Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | 0.468 | 0.623 | 638.8 ms | 28 | 10 | 6 | 6 |
| keyword-boost | 0.403 | 0.523 | 663.6 ms | 21 | 15 | 8 | 6 |

`keyword-boost` expanded all 50 queries. It appended a mean of `21.48` tokens
per query from a mean of `10.74` question-derived keywords.

## Query-Expansion Read

The tested keyword-boost expansion does not solve DMR ranking. It keeps the
same six retrieval misses, lowers Recall@10 by `0.065`, lowers MRR@10 by
`0.099`, and loses seven top-1 hits.

This means simple question-keyword repetition is not a safe ranking fix. It
adds more lexical signal, but that signal is too broad: several relevant chunks
move down from top-1 into lower top-10 or top-50 positions.

## DMR 50 Transition Audit

The transition audit reads the existing sanitized DMR 50 reports and compares
rank movement for the same sample IDs. It does not inspect raw questions,
answers, dialogs, sessions, memory content, or generated answer text.

Report:

`crates/eval/reports/ranking-transition-audit-dmr-50.json`

Command:

```powershell
python scripts/eval/ranking_transition_audit.py `
  --output crates/eval/reports/ranking-transition-audit-dmr-50.json
```

### DMR 50 Transition Result

Control outcome:

| Bucket | Count |
| --- | ---: |
| Top-1 hit | 28 |
| Top-10 not top-1 | 10 |
| Top-50 only late rank | 6 |
| Top-50 retrieval miss | 6 |

Baseline RRF -> vector effect:

| Effect | Count |
| --- | ---: |
| Recovered to top-10 | 10 |
| Promoted to top-1 | 4 |
| Stable top-1 | 5 |
| Top-10 preserved | 6 |
| Suppressed from top-10 | 2 |
| Bucket changed outside top-10 | 7 |
| No top-10 change | 16 |

Vector -> reranker effect:

| Effect | Count |
| --- | ---: |
| Recovered to top-10 | 14 |
| Promoted to top-1 | 12 |
| Stable top-1 | 8 |
| Top-10 preserved | 3 |
| Suppressed from top-10 | 1 |
| Demoted from top-1 | 1 |
| Bucket changed outside top-10 | 4 |
| No top-10 change | 7 |

Dialog chunk -> merged-session effect:

| Effect | Count |
| --- | ---: |
| Recovered to top-10 | 1 |
| Promoted to top-1 | 2 |
| Stable top-1 | 4 |
| Top-10 preserved | 2 |
| Suppressed from top-10 | 21 |
| Demoted from top-1 | 9 |
| Bucket changed outside top-10 | 5 |
| No top-10 change | 6 |

Original query -> keyword-boost effect:

| Effect | Count |
| --- | ---: |
| Recovered to top-10 | 2 |
| Stable top-1 | 21 |
| Top-10 preserved | 7 |
| Suppressed from top-10 | 4 |
| Demoted from top-1 | 6 |
| Bucket changed outside top-10 | 1 |
| No top-10 change | 9 |

### DMR 50 Transition Read

The transition audit strengthens the current diagnosis:

- Vector search and reranking are the two productive ranking additions in this
  sample. Vector recovers 10 samples into top-10, while the reranker recovers
  14 into top-10 and promotes 12 to top-1.
- The reranker still has a small risk surface: 1 vector top-10 hit is
  suppressed and 1 vector top-1 hit is demoted.
- Merged-session chunks recover the six control top-50 misses into top-50, but
  only one reaches top-10; meanwhile 21 samples are suppressed from top-10 and
  9 top-1 hits are demoted. This explains why merged-session recall drops even
  though broad coverage improves.
- Keyword boost recovers 2 of the six control top-50 misses into top-10, but
  leaves 4 absent and causes 4 top-10 suppressions plus 6 top-1 demotions. It
  is not a safe default either.

## Failure Audit

The sanitized failure audit compares:

- baseline RRF;
- RRF + vectors;
- RRF + vectors + reranker;
- top-k `10`, `25`, and `50`.

It does not inspect raw questions, answers, dialogs, sessions, or generated
answer text.

Report:

`crates/eval/reports/ranking-failure-audit-dmr-50.json`

| Bucket | Count |
| --- | ---: |
| Top-1 hit | 28 |
| Top-10 not top-1 | 10 |
| Top-50 only late rank | 6 |
| Top-50 retrieval miss | 6 |

Vector effect:

| Effect | Count |
| --- | ---: |
| Vector recovered to top-10 | 10 |
| Vector suppressed from top-10 | 2 |
| Stable top-1 | 5 |
| Top-10 preserved | 10 |
| No top-10 change | 23 |

Reranker effect:

| Effect | Count |
| --- | ---: |
| Reranker recovered to top-10 | 14 |
| Reranker promoted to top-1 | 12 |
| Reranker suppressed from top-10 | 1 |
| Reranker demoted from top-1 | 1 |
| Stable top-1 | 8 |
| Top-10 preserved | 3 |
| No top-10 change | 11 |

Read:

- Vector retrieval helps, but it is not uniformly safe: it recovers 10 samples
  into top-10 and suppresses 2 from top-10.
- The reranker is doing real work: it recovers 14 samples into top-10 and
  promotes 12 to top-1.
- The reranker also has a small but real downside: 1 sample is suppressed from
  top-10 and 1 top-1 sample is demoted.
- The remaining 12 non-top-10 cases split cleanly into 6 late-ranking failures
  and 6 top-50 retrieval misses.

## DMR 200 Expansion

The DMR 50 failure structure was expanded to 200 punctuation-mapped samples.
This pass keeps the same feature-freeze rule: no memory schema changes, no new
ranking defaults, and one varied top-k parameter in the ablation.

Candidate report:

`crates/eval/reports/dmr-200-punctuation-validation.json`

Top-k report:

`crates/eval/reports/ranking-ablation-dmr-200-top-k.json`

Failure audit:

`crates/eval/reports/ranking-failure-audit-dmr-200.json`

Transition audit:

`crates/eval/reports/ranking-transition-audit-dmr-200.json`

### DMR 200 Candidate Result

| Mode | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 | Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline RRF | 0.145 | 0.129 | 109.9 ms | 14 | 34 | 86 | 66 |
| RRF + vectors | 0.323 | 0.224 | 133.9 ms | 20 | 83 | 46 | 51 |
| RRF + vectors + reranker | 0.411 | 0.476 | 712.4 ms | 74 | 65 | 18 | 43 |

### DMR 200 Top-K Result

| Top-k | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Top-50 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.413 | 0.472 | 676.6 ms | 74 | 66 | 0 | 60 |
| 25 | 0.409 | 0.473 | 687.7 ms | 74 | 64 | 12 | 50 |
| 50 | 0.411 | 0.476 | 731.7 ms | 74 | 65 | 18 | 43 |

### DMR 200 Failure Audit

| Bucket | Count |
| --- | ---: |
| Top-1 hit | 74 |
| Top-10 not top-1 | 66 |
| Top-50 only late rank | 17 |
| Top-50 retrieval miss | 43 |

The standalone top-k `50` run has 18 top-50 bucket cases. The cross-run failure
audit counts 17 top-50-only late-rank cases because one sample is already a
top-10 hit in the top-k `10` run.

Vector effect:

| Effect | Count |
| --- | ---: |
| Vector recovered to top-10 | 60 |
| Vector suppressed from top-10 | 5 |
| Stable top-1 | 9 |
| Top-10 preserved | 34 |
| No top-10 change | 92 |

Reranker effect:

| Effect | Count |
| --- | ---: |
| Reranker recovered to top-10 | 40 |
| Reranker promoted to top-1 | 49 |
| Reranker suppressed from top-10 | 3 |
| Reranker demoted from top-1 | 5 |
| Stable top-1 | 14 |
| Top-10 preserved | 32 |
| No top-10 change | 57 |

### DMR 200 Transition Audit

The DMR 200 transition audit reads only sanitized sample IDs and ranks from the
existing DMR 200 candidate and top-k reports. Unlike the DMR 50 transition
audit, it does not include chunk-policy or query-expansion controls because
those controls were only run on the 50-sample set.

Command:

```powershell
python scripts/eval/ranking_transition_audit.py `
  --candidate-report crates/eval/reports/dmr-200-punctuation-validation.json `
  --top-k-report crates/eval/reports/ranking-ablation-dmr-200-top-k.json `
  --skip-cross-ablation-controls `
  --dataset-label "DMR candidate MSC-Self-Instruct, punctuation-normalized 200" `
  --output crates/eval/reports/ranking-transition-audit-dmr-200.json
```

Engineering result:

| Transition | Helpful movement | Harmful movement |
| --- | ---: | ---: |
| Baseline RRF -> vector | 60 recovered to top-10, 9 promoted to top-1 | 5 suppressed from top-10, 5 demoted from top-1 |
| Vector -> reranker | 40 recovered to top-10, 49 promoted to top-1 | 3 suppressed from top-10, 5 demoted from top-1 |
| Top-k 10 -> 25 | 0 recovered to top-10 | 2 suppressed from top-10 |
| Top-k 25 -> 50 | 1 recovered to top-10 | 0 suppressed from top-10 |

Research interpretation:

- The DMR 50 direction repeats at larger sample size: vectors and reranking
  are still the productive ranking signals.
- The reranker has a real positive effect on top-1 placement, but the
  regression surface is no longer negligible at 200 samples: 3 top-10
  suppressions and 5 top-1 demotions must be preserved in future audits.
- Returning more candidates is mainly diagnostic. Top-k `50` exposes more
  answer-bearing chunks, but it does not solve top-10 placement by itself.

Read:

- The 200-sample result confirms that vectors and reranking both help DMR:
  Recall@10 rises from `0.145` to `0.323` with vectors, then to `0.411` with
  the reranker.
- The reranker is valuable but not free of regressions: it recovers 40 samples
  into top-10 and promotes 49 to top-1, while suppressing 3 from top-10 and
  demoting 5 top-1 samples.
- Increasing top-k is diagnostic, not a solution. It reduces apparent misses
  from 60 at top-k `10` to 43 at top-k `50`, but Recall@10 and top-1 hits do
  not improve.
- The remaining DMR 200 non-top-10 cases split into 17 late-ranking cases and
  43 top-50 retrieval misses. Compared with DMR 50, the larger sample shows
  that candidate retrieval remains an active bottleneck alongside ranking.

## LongMemEval Cross-Check

DMR-driven ranking decisions must not be adopted until they are checked against
LongMemEval. This pass varies only `reranker_pool` on the fixed LongMemEval 50
sample.

Report:

`crates/eval/reports/ranking-ablation-longmem-50-reranker-pool.json`

Command:

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets longmem `
  --longmem-sample-size 50 `
  --ablation reranker-pool `
  --reranker-pools 10,25,50,100 `
  --k 10 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-longmem-50-reranker-pool.json `
  --cleanup-cache
```

### LongMemEval 50 Reranker-Pool Result

| Reranker pool | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.600 | 0.473 | 612.9 ms | 18 | 18 | 14 |
| 25 | 0.637 | 0.521 | 829.4 ms | 20 | 18 | 12 |
| 50 | 0.590 | 0.483 | 1261.7 ms | 18 | 18 | 14 |
| 100 | 0.553 | 0.504 | 2098.7 ms | 20 | 15 | 15 |

Reference from `crates/eval/reports/longmem-50-validation.json`:

| Mode | Recall@10 | MRR@10 | Top-1 | Misses |
| --- | ---: | ---: | ---: | ---: |
| RRF + vectors | 0.663 | 0.425 | 13 | 5 |
| RRF + vectors + reranker pool 50 | 0.590 | 0.523 | 21 | 6 |

Read:

- Pool `25` is the best LongMemEval reranker-pool setting in this pass:
  Recall@10 `0.637`, MRR@10 `0.521`, and P50 `829.4 ms`.
- Pool `50`, the current DMR-favored setting, is worse on LongMemEval
  Recall@10 and latency than pool `25`.
- Pool `100` is not justified: it is slowest and has the lowest Recall@10.
- Even the best LongMemEval reranker-pool setting (`25`) still trails
  vector-only Recall@10 (`0.637` vs `0.663`), while improving MRR and top-1.
  This is a quality tradeoff, not a clean default win.

## RRF-K Cross-Check

This pass varies only `rrf_k` on the same DMR 50 and LongMemEval 50 validation
sets. It keeps vectors, reranking, top-k `10`, reranker pool `50`, and the
default branch weights fixed.

Report:

`crates/eval/reports/ranking-ablation-dmr-longmem-50-rrf-k.json`

Command:

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets all `
  --dmr-sample-size 50 `
  --longmem-sample-size 50 `
  --ablation rrf-k `
  --rrf-k-values 20,40,60,80 `
  --fixed-reranker-pool 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-longmem-50-rrf-k.json `
  --cleanup-cache
```

### RRF-K Result

DMR 50:

| RRF k | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 0.468 | 0.618 | 598.4 ms | 28 | 10 | 12 |
| 40 | 0.468 | 0.618 | 598.8 ms | 28 | 10 | 12 |
| 60 | 0.468 | 0.618 | 598.0 ms | 28 | 10 | 12 |
| 80 | 0.468 | 0.618 | 598.9 ms | 28 | 10 | 12 |

LongMemEval 50:

| RRF k | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 0.590 | 0.486 | 1212.2 ms | 18 | 18 | 14 |
| 40 | 0.590 | 0.486 | 1198.6 ms | 18 | 18 | 14 |
| 60 | 0.590 | 0.486 | 1202.9 ms | 18 | 18 | 14 |
| 80 | 0.590 | 0.493 | 1213.3 ms | 19 | 17 | 14 |

Read:

- DMR 50 is insensitive to the tested RRF k range.
- LongMemEval 50 shows only a tiny MRR/top-1 movement at k `80`, with unchanged
  Recall@10 and misses.
- This is not enough evidence to change the default RRF k.

## Vector-Weight Cross-Check

This pass varies only the vector branch weight. It keeps RRF k `60`, FTS and
entity weights `1.0`, vectors, reranking, top-k `10`, and reranker pool `50`
fixed.

Report:

`crates/eval/reports/ranking-ablation-dmr-longmem-50-vector-weight.json`

Command:

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets all `
  --dmr-sample-size 50 `
  --longmem-sample-size 50 `
  --ablation vector-weight `
  --vector-weights 0.5,1.0,1.5,2.0 `
  --fixed-reranker-pool 50 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-longmem-50-vector-weight.json `
  --cleanup-cache
```

### Vector-Weight Result

DMR 50:

| Vector weight | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.5 | 0.432 | 0.603 | 597.8 ms | 28 | 7 | 15 |
| 1.0 | 0.468 | 0.618 | 597.4 ms | 28 | 10 | 12 |
| 1.5 | 0.475 | 0.617 | 593.2 ms | 27 | 12 | 11 |
| 2.0 | 0.465 | 0.597 | 589.9 ms | 26 | 12 | 12 |

LongMemEval 50:

| Vector weight | Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.5 | 0.570 | 0.507 | 1215.5 ms | 20 | 15 | 15 |
| 1.0 | 0.590 | 0.496 | 1203.7 ms | 19 | 17 | 14 |
| 1.5 | 0.607 | 0.486 | 1188.4 ms | 19 | 17 | 14 |
| 2.0 | 0.587 | 0.476 | 1187.1 ms | 19 | 16 | 15 |

Read:

- Vector weight `1.5` improves Recall@10 on both DMR 50 and LongMemEval 50 in
  this pass.
- The improvement is a tradeoff, not a clean default win: DMR top-1 drops from
  `28` to `27`, DMR MRR slightly drops, and LongMemEval MRR drops versus the
  same-run control.
- Vector weight `0.5` improves LongMemEval MRR/top-1 but hurts Recall@10 and
  adds misses on both datasets.
- Vector weight `2.0` is not justified: it lowers DMR MRR/top-1 and does not
  improve LongMemEval Recall@10 versus `1.5`.
- Do not change the global default from this evidence. Treat `vector_weight =
  1.5` as a candidate for a follow-up focused on Recall@10 coverage, not as a
  production setting.

## Vector-Weight Transition Audit

This audit compares the sanitized per-query ranks for `vector_weight = 1.0`
and `vector_weight = 1.5` from the existing DMR / LongMemEval 50 ablation
report. It does not rerun retrieval and does not inspect raw questions,
answers, dialogs, sessions, memory content, or generated text.

Report:

`crates/eval/reports/ranking-vector-weight-transition-audit-dmr-longmem-50.json`

Command:

```powershell
python scripts/eval/ranking_vector_weight_transition_audit.py
```

### Vector-Weight Transition Result

DMR 50, candidate `1.5` minus control `1.0`:

| Metric | Delta |
| --- | ---: |
| Recall@10 | +0.0067 |
| MRR@10 | -0.0018 |
| NDCG@10 | +0.0054 |
| Top-1 | -1 |
| Top-10 not top-1 | +2 |
| Retrieval misses | -1 |

DMR 50 transitions:

| Transition | Count |
| --- | ---: |
| Stable top-1 | 27 |
| Top-10 preserved | 9 |
| Recovered to top-10 | 2 |
| Suppressed from top-10 | 1 |
| Demoted from top-1 | 1 |
| Miss unchanged | 10 |

LongMemEval 50, candidate `1.5` minus control `1.0`:

| Metric | Delta |
| --- | ---: |
| Recall@10 | +0.0167 |
| MRR@10 | -0.0103 |
| NDCG@10 | -0.0009 |
| Top-1 | 0 |
| Top-10 not top-1 | 0 |
| Retrieval misses | 0 |

LongMemEval 50 transitions:

| Transition | Count |
| --- | ---: |
| Stable top-1 | 18 |
| Top-10 preserved | 15 |
| Recovered to top-10 | 2 |
| Suppressed from top-10 | 1 |
| Promoted to top-1 | 1 |
| Demoted from top-1 | 1 |
| Miss unchanged | 12 |

### Vector-Weight Transition Read

The audit confirms that `vector_weight = 1.5` is a coverage candidate, not a
safe default.

On DMR 50, the small Recall@10 gain comes from two recoveries into top-10 and
one fewer retrieval miss, but it also suppresses one previous top-10 hit and
demotes one top-1 hit. That explains why the aggregate result improves
coverage while losing top-1.

On LongMemEval 50, the top-level hit buckets do not improve: top-1, top-10
not top-1, and miss counts are unchanged. The Recall@10 gain is therefore
coming from per-query relevant-evidence coverage inside already measured
samples, while MRR falls because ordering quality gets slightly worse.

This is useful evidence for a future adaptive or query-conditioned policy, but
it is not enough to change the global branch weight.

## Late-Rank Audit

This audit isolates DMR samples where the answer-bearing memory is absent from
the top-10 run but appears within the top-50 run. It is a sanitized
post-processing pass over existing top-k and transition reports; it does not
rerun retrieval and does not inspect raw questions, answers, dialogs,
sessions, memory content, or generated answer text.

Report:

`crates/eval/reports/ranking-late-rank-audit-dmr-50-200.json`

Command:

```powershell
python scripts/eval/ranking_late_rank_audit.py
```

### Late-Rank Result

DMR 50 outcome split:

| Outcome | Count |
| --- | ---: |
| Top-1 hit | 28 |
| Top-10 not top-1 | 10 |
| Top-50 only late rank | 6 |
| Top-50 retrieval miss | 6 |

DMR 50 late-rank distribution:

| Rank band | Count |
| --- | ---: |
| 11-15 | 1 |
| 16-25 | 0 |
| 26-35 | 2 |
| 36-50 | 3 |

Only `1/6` DMR 50 late-rank cases are recoverable by expanding the output
window to top-25. The other `5/6` remain between ranks 26 and 50. The late
rank mean is `33.33` and the median is `36.5`.

DMR 200 outcome split:

| Outcome | Count |
| --- | ---: |
| Top-1 hit | 74 |
| Top-10 not top-1 | 66 |
| Top-50 only late rank | 17 |
| Top-50 retrieval miss | 43 |

DMR 200 late-rank distribution:

| Rank band | Count |
| --- | ---: |
| 11-15 | 2 |
| 16-25 | 8 |
| 26-35 | 5 |
| 36-50 | 2 |

`10/17` DMR 200 late-rank cases are recoverable by top-25, while `7/17`
remain between ranks 26 and 50. The late-rank mean is `25.06` and the median
is `23`.

### Late-Rank Read

Late-rank failures are real, but they are not one uniform class.

DMR 50 is harder at the tail: most late-rank cases sit below rank 25, and the
same cases remain misses under the `vector_weight = 1.5` top-10 audit. That
means simply increasing vector branch weight does not rescue the DMR 50
late-rank set.

DMR 200 has a more actionable middle band: most late-rank cases are between
11 and 25. That suggests a future candidate-ordering experiment can target
reranker ordering or a second-stage selector on the top-25 pool before trying
larger schema or chunking changes.

The key split remains: top-50-only late ranks are ranking/order failures,
while top-50 misses are candidate-retrieval failures. The next experiment
should keep those two buckets separate.

## DMR 200 Reranker-Pool Ordering Check

This pass varies only `reranker_pool` on the DMR 200 punctuation-mapped sample.
It is an ordering/latency check after the late-rank audit showed a larger
rank 11-25 band in DMR 200 than in DMR 50.

Reports:

`crates/eval/reports/ranking-ablation-dmr-200-reranker-pool.json`

`crates/eval/reports/ranking-reranker-pool-transition-audit-dmr-200.json`

Command:

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets dmr `
  --dmr-sample-size 200 `
  --dmr-answer-match punctuation `
  --ablation reranker-pool `
  --reranker-pools 25,50,100 `
  --k 10 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-200-reranker-pool.json `
  --cleanup-cache
```

Transition audit command:

```powershell
python scripts/eval/ranking_reranker_pool_transition_audit.py
```

### DMR 200 Reranker-Pool Result

| Reranker pool | Recall@10 | MRR@10 | P50 latency | P95 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 25 | 0.390 | 0.454 | 346.6 ms | 413.8 ms | 73 | 56 | 71 |
| 50 | 0.411 | 0.472 | 643.8 ms | 709.5 ms | 74 | 65 | 61 |
| 100 | 0.416 | 0.483 | 1205.9 ms | 1262.7 ms | 77 | 67 | 56 |

Pool `100` is best on aggregate ranking quality in this DMR 200 pass, but the
gain is small relative to cost: versus pool `50`, Recall@10 rises by `+0.005`,
MRR rises by `+0.011`, top-1 rises by `+3`, and misses fall by `5`; P50
latency rises by `+562.1 ms`.

### DMR 200 Reranker-Pool Transition Result

Pool `25` versus control pool `50`:

| Transition | Count |
| --- | ---: |
| Recovered to top-10 | 6 |
| Promoted to top-1 | 3 |
| Suppressed from top-10 | 12 |
| Demoted from top-1 | 4 |
| Stable top-1 | 70 |
| Top-10 preserved | 50 |
| Miss unchanged | 55 |

Pool `25` rescues `5/10` DMR 200 rank 11-25 late-rank cases, but it also
causes `12` top-10 suppressions and `4` top-1 demotions overall. It is faster,
but the quality loss is too large for a default.

Pool `100` versus control pool `50`:

| Transition | Count |
| --- | ---: |
| Recovered to top-10 | 7 |
| Promoted to top-1 | 5 |
| Suppressed from top-10 | 7 |
| Demoted from top-1 | 2 |
| Stable top-1 | 72 |
| Top-10 preserved | 58 |
| Miss unchanged | 49 |

Subset movement for pool `100`:

| Subset | Helpful movement | Unchanged misses |
| --- | ---: | ---: |
| Late rank 11-25 | 2 recovered to top-10 | 8 |
| Late rank 26-50 | 1 recovered to top-10, 1 promoted to top-1 | 5 |
| Top-50 retrieval miss | 4 recovered to top-10, 4 promoted to top-1 | 35 |

### DMR 200 Reranker-Pool Read

The experiment separates two effects:

- Pool `25` is a targeted rank 11-25 rescue but has too much collateral
  damage. It recovers half of the DMR 200 rank 11-25 late-rank set, while
  increasing misses and suppressing many existing top-10 hits.
- Pool `100` is a broad candidate expansion, not a focused late-rank fix. It
  improves aggregate Recall@10/MRR/top-1, but most of its helpful movement is
  outside the rank 11-25 late-rank subset and it roughly doubles P50 latency
  versus pool `50`.

This supports the next direction: do not simply change the global reranker
pool. A safer policy needs a second-stage ordering signal that can help the
rank 11-25 cases without suppressing existing top-10/top-1 hits or paying the
full pool `100` latency on every query.

## DMR 200 Pool Signal Trigger Audit

The previous result showed that full pool `100` is too expensive as a global
default. This pass adds evaluation-only ranking diagnostics to the sanitized
report and simulates conditional use of pool `100` from answer-free signals in
the pool `50` control run.

The added diagnostics are rank/score/source summaries only. They do not record
raw questions, answers, dialogs, sessions, memory content, or generated answer
text.

Reports:

`crates/eval/reports/ranking-ablation-dmr-200-reranker-pool-signal.json`

`crates/eval/reports/ranking-pool-signal-trigger-audit-dmr-200.json`

Signal run command:

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets dmr `
  --dmr-sample-size 200 `
  --dmr-answer-match punctuation `
  --ablation reranker-pool `
  --reranker-pools 50,100 `
  --k 10 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-200-reranker-pool-signal.json `
  --cleanup-cache
```

Trigger audit command:

```powershell
python scripts/eval/ranking_pool_signal_trigger_audit.py
```

### Pool Signal Trigger Result

Control pool `50`:

| Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.411 | 0.472 | 644.9 ms | 74 | 65 | 61 |

Full pool `100`:

| Recall@10 | MRR@10 | P50 latency | Top-1 | Top-10 not top-1 | Misses |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.416 | 0.483 | 1203.9 ms | 77 | 67 | 56 |

Best simulated trigger:

`top1_single_source`

This trigger uses pool `100` only when the pool `50` top-1 hit came from
exactly one retrieval branch. It triggered on `43/200` queries.

Projected result versus pool `50`:

| Metric | Delta |
| --- | ---: |
| Recall@10 | +0.0117 |
| MRR@10 | +0.0131 |
| NDCG@10 | +0.0094 |
| P50 latency estimate | +8.5 ms |
| P95 latency estimate | +520.3 ms |
| Top-1 | +3 |
| Top-10 not top-1 | +2 |
| Retrieval misses | -5 |

Triggered transitions:

| Transition | Count |
| --- | ---: |
| Promoted to top-1 | 3 |
| Recovered to top-10 | 2 |
| Stable top-1 | 8 |
| Top-10 preserved | 13 |
| Miss unchanged | 17 |

The important detail: this trigger has no triggered top-10 suppressions or
top-1 demotions in the DMR 200 simulation, while full pool `100` still has
suppression/demotion risk.

### Pool Signal Trigger Read

This is the first ranking result that points to a plausible conditional policy
instead of a global parameter change.

`top1_single_source` is answer-free: it depends only on the control run's
retrieval source composition, not on gold answers or raw text. It captures the
same aggregate miss reduction as full pool `100` in this simulation, while
triggering only `21.5%` of queries and avoiding the harmful pool `100`
transitions that appear outside the triggered set.

But this is not a default yet. It is a DMR 200 offline simulation using
existing pool `50` and pool `100` reports. The next gate is to rerun the same
signal-trigger audit on DMR 50 and LongMemEval 50. If it helps DMR but hurts
LongMemEval, it stays dataset-specific or remains a research finding.

## Pool Signal Cross-Check

This pass cross-checks the DMR 200 `top1_single_source` candidate on the fixed
DMR 50 and LongMemEval 50 samples. It reruns pool `50` and pool `100` with the
same sanitized ranking signal summaries, then simulates the same conditional
trigger.

Reports:

`crates/eval/reports/ranking-ablation-dmr-longmem-50-reranker-pool-signal.json`

`crates/eval/reports/ranking-pool-signal-crosscheck-dmr-longmem-50.json`

Signal run command:

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets all `
  --dmr-sample-size 50 `
  --longmem-sample-size 50 `
  --dmr-answer-match punctuation `
  --ablation reranker-pool `
  --reranker-pools 50,100 `
  --k 10 `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-longmem-50-reranker-pool-signal.json `
  --cleanup-cache
```

Cross-check command:

```powershell
python scripts/eval/ranking_pool_signal_crosscheck.py
```

### Cross-Check Result

Full pool `100` versus pool `50`:

| Dataset | Recall@10 delta | MRR@10 delta | P50 latency delta | Top-1 delta | Miss delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| DMR 50 | -0.020 | +0.0048 | +543.4 ms | 0 | 0 |
| LongMemEval 50 | -0.0367 | +0.0013 | +789.5 ms | 0 | +1 |

The full pool `100` result is not a global fix. It hurts top-10 coverage on
both fixed 50-sample cross-checks and substantially increases latency.

`top1_single_source` simulation:

| Dataset | Triggered | Recall@10 delta | MRR@10 delta | P50 latency estimate delta | Top-1 delta | Miss delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DMR 50 | 8/50 | +0.010 | +0.020 | +2.3 ms | +1 | -1 |
| LongMemEval 50 | 8/50 | -0.020 | -0.0051 | +75.7 ms | 0 | +2 |

Triggered transitions:

| Dataset | Helpful movement | Harmful movement | Unchanged |
| --- | ---: | ---: | ---: |
| DMR 50 | 1 promoted to top-1 | 0 suppressions / 0 demotions | 5 misses unchanged, 2 stable top-1 |
| LongMemEval 50 | 0 recoveries / 0 promotions | 2 suppressed from top-10 | 2 misses unchanged, 1 stable top-1, 3 top-10 preserved |

### Cross-Check Read

The cross-check disqualifies `top1_single_source` as a global default.

It remains interesting for DMR: it helps both DMR 200 and DMR 50 without
triggered suppressions in those two runs. But it hurts LongMemEval 50 by
suppressing two top-10 hits and adding two misses. That violates the Phase 6
ranking rule: if a parameter or policy helps one dataset and hurts another, it
cannot become the default.

The next useful step is not to implement `top1_single_source`; it is to audit
why LongMemEval's single-source top-1 cases behave differently from DMR's. A
safe conditional policy needs a guard that preserves LongMemEval top-10
coverage.

## Pool Signal Guard Audit

This pass audits answer-free guards for the conditional pool `100` trigger
across DMR 200, DMR 500-request / 323-scored, DMR 50, LongMemEval 50, and
LongMemEval 200 / 500. It uses only sanitized rank, metric, source, and score
summaries from existing reports.

Report:

`crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json`

LongMemEval 200 signal report:

`crates/eval/reports/ranking-ablation-longmem-200-reranker-pool-signal.json`

LongMemEval 500 signal report:

`crates/eval/reports/ranking-ablation-longmem-500-reranker-pool-signal.json`

DMR 500-request / 323-scored signal report:

`crates/eval/reports/ranking-ablation-dmr-500-reranker-pool-signal.json`

Command:

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets dmr `
  --dmr-sample-size 500 `
  --dmr-answer-match punctuation `
  --ablation reranker-pool `
  --reranker-pools 50,100 `
  --k 10 `
  --cargo-profile release `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-dmr-500-reranker-pool-signal.json `
  --cleanup-cache
```

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets longmem `
  --longmem-sample-size 500 `
  --ablation reranker-pool `
  --reranker-pools 50,100 `
  --k 10 `
  --cargo-profile release `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-longmem-500-reranker-pool-signal.json `
  --cleanup-cache
```

```powershell
python scripts/eval/ranking_ablation.py `
  --endpoint https://hf-mirror.com `
  --datasets longmem `
  --longmem-sample-size 200 `
  --ablation reranker-pool `
  --reranker-pools 50,100 `
  --k 10 `
  --cargo-profile release `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/ranking-ablation-longmem-200-reranker-pool-signal.json `
  --cleanup-cache
```

```powershell
python scripts/eval/ranking_pool_signal_guard_audit.py
```

### Guard Result

Full LongMemEval 200 pool `100` versus pool `50`:

| Recall@10 delta | MRR@10 delta | P50 latency delta | Top-1 delta | Miss delta |
| ---: | ---: | ---: | ---: | ---: |
| -0.0066 | +0.0016 | +565.9 ms | +1 | +3 |

Full LongMemEval 500 pool `100` versus pool `50`:

| Recall@10 delta | MRR@10 delta | P50 latency delta | Top-1 delta | Miss delta |
| ---: | ---: | ---: | ---: | ---: |
| +0.0088 | +0.0020 | +548.0 ms | -3 | -6 |

Full DMR 500-request / 323-scored pool `100` versus pool `50`:

| Recall@10 delta | MRR@10 delta | P50 latency delta | Top-1 delta | Miss delta |
| ---: | ---: | ---: | ---: | ---: |
| +0.0020 | +0.0042 | +511.2 ms | 0 | -6 |

Guard simulation:

| Guard | DMR 323 Recall@10 delta | DMR 200 Recall@10 delta | DMR 50 Recall@10 delta | LongMem 50 Recall@10 delta | LongMem 200 Recall@10 delta | LongMem 500 Recall@10 delta | Suppression datasets | Read |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `top1_single_source` | +0.0036 | +0.0117 | +0.010 | -0.020 | -0.0062 | +0.0001 | DMR 323, LongMem 50/200/500 | Best DMR gain, blocked globally. |
| `top1_single_source_fts_only` | -0.0008 | +0.0050 | +0.010 | 0.000 | -0.0012 | +0.0006 | DMR 323, LongMem 500 | Source-only guard does not hold at larger samples. |
| `top1_single_source_not_vector_only` | -0.0039 | +0.0050 | +0.010 | 0.000 | -0.0012 | +0.0006 | DMR 323, LongMem 500 | Worse than FTS-only at DMR 323. |
| `top1_single_source_rerank_margin_gt_1` | +0.0057 | +0.0063 | 0.000 | 0.000 | +0.0025 | +0.0004 | LongMem 500 | Last screened guard is now blocked by LongMem 500 suppressions. |

Latency budget for `top1_single_source_rerank_margin_gt_1`:

| Dataset | Triggered | Mean extra / triggered query | Mean extra / all queries | P95 extra / triggered query |
| --- | ---: | ---: | ---: | ---: |
| DMR 50 | 3/50 | +544.2 ms | +32.6 ms | +555.1 ms |
| DMR 200 | 22/200 | +559.3 ms | +61.5 ms | +580.9 ms |
| DMR 500 request / 323 scored | 45/323 | +509.2 ms | +70.9 ms | +527.5 ms |
| LongMemEval 50 | 1/50 | +799.9 ms | +16.0 ms | +799.9 ms |
| LongMemEval 200 | 15/200 | +556.9 ms | +41.8 ms | +584.9 ms |
| LongMemEval 500 | 69/500 | +545.2 ms | +75.2 ms | +642.4 ms |

Across the checked sample sets, this guard adds `63.2 ms` per query on average
when amortized over all queries, with the largest dataset-level mean at
`75.2 ms/query`. Triggered queries themselves still pay the larger pool cost,
usually about `0.5-0.8 s`.

### Guard Read

The LongMemEval 200 and DMR 323 expansions tightened the conclusion, and the
LongMemEval 500 expansion tightens it again. The 50-sample read made
`fts-only` and `not-vector-only` look safe, but LongMemEval 200 shows a small
Recall@10 regression for both, and DMR 323 shows that both source-only guards
can also regress DMR ranking. They cannot become defaults.

Before LongMemEval 500, `top1_single_source_rerank_margin_gt_1` was the only
guard passing the checked quality screen. LongMemEval 500 now blocks it: it
keeps Recall@10 slightly positive (`+0.0004`) but introduces `3`
`suppressed_from_top10` transitions and one top-1 demotion. That violates the
Phase 6 ranking rule. There is currently no pool-signal guard in this audit
that can become a runtime default.

The useful result is negative as much as positive: larger LongMemEval evidence
blocks every tested source/margin guard. The next ranking work should stop
trying to rescue pool `100` with these simple triggers and move to a different
answer-free ordering signal, or separate LongMemEval and DMR objectives more
explicitly.

The latency audit does not adopt a runtime budget. It records the cost surface
for a guard that is now quality-blocked. Before any future implementation, the
project still needs an explicit budget such as maximum amortized latency per
query and maximum triggered-query tail latency.

## Objective Conflict Audit

This pass consolidates the existing DMR / LongMemEval ranking ablations without
running new retrieval. It reads only sanitized aggregate metrics from the
checked reports.

Report:

`crates/eval/reports/ranking-objective-conflict-audit.json`

Command:

```powershell
python scripts/eval/ranking_objective_conflict_audit.py
```

| View | Read | Evidence |
| --- | --- | --- |
| RRF k 20/40/60/80 | Flat | DMR Recall@10 is unchanged at `0.4683`; LongMemEval Recall@10 is unchanged at `0.5900`. |
| Vector weight 0.5/1.0/1.5/2.0 | Tradeoff | `1.5` improves Recall@10 on both DMR (`+0.0067`) and LongMemEval (`+0.0167`) versus `1.0`, but DMR top-1 drops by `1` and MRR drops on both datasets. |
| Reranker pool 10/25/50/100 | Conflict | DMR 50 is best by Recall@10 at pool `50`; LongMemEval 50 is best among reranker variants at pool `25`. |
| Pool 50 vs 100 signal view | Metric tradeoff | Both DMR 50 and LongMemEval 50 keep better Recall@10 at pool `50`, while MRR nudges toward pool `100`; pool `100` is also more expensive. |
| Pool-signal guards | Blocked | The guard audit has `best_safe_guard_id: null`; no checked guard passes the current safety screen. |

Read: the current ranking evidence does not support a new global default. The
active problem is not a broad architecture failure; it is an objective
conflict. DMR wants better late-rank ordering and answer synthesis, while
LongMemEval is more sensitive to top-10 coverage and top-10 suppressions.
`docs/eval/RANKING_OBJECTIVE_SPLIT_DECISION.md` records the follow-up decision:
the DMR / LongMemEval split is now explicit and validation-only. A future
ranking policy still needs either a new answer-free ordering signal that
preserves LongMemEval, or separately validated objective-specific policies. In
both cases, runtime adoption still requires zero LongMemEval top-10
suppressions and an explicit latency budget.

## Decision

Do not change the default reranker pool from this evidence.

The result supports the current diagnosis: DMR ranking is sensitive to
candidate pool size, output window, chunk policy, query policy, and vector
branch weighting, but the remaining weakness is not solved by simply making
the pool bigger, returning more items, merging all session content into one
larger chunk, repeating question keywords, or changing RRF k. Returning top 50
helps diagnosis; merged-session chunks improve broad top-50 coverage but
damage top-10 and top-1 placement; keyword boosting keeps retrieval misses
unchanged and also damages ranking. The DMR 50 transition audit shows why: the
simple fixes recover a few misses while suppressing many stronger hits. The
DMR 200 expansion adds that true top-50 retrieval misses are material and
should be separated from late-ranking cases before default changes. The DMR
200 transition audit repeats the productive direction at larger scale: vector
retrieval recovers 60 samples into top-10, and reranking recovers 40 more
while promoting 49 to top-1. It also records the regression surface: 3
reranker top-10 suppressions and 5 top-1 demotions.

The LongMemEval cross-check also argues against a global default change. DMR 50
prefers pool `50` on Recall@10, while LongMemEval 50 prefers pool `25` among
reranker variants and still prefers vector-only for top-10 coverage. Any
ranking change now needs either dataset-specific policy or a broader objective
than Recall@10 alone. The vector-weight cross-check adds a possible Recall@10
candidate (`1.5`) but the transition audit shows the tradeoff directly:
DMR gains two top-10 recoveries while also taking one top-10 suppression and
one top-1 demotion; LongMemEval keeps the same hit buckets while lowering MRR.
Better coverage alone is not enough when ordering/top-1 tradeoffs appear.

The late-rank audit narrows the next step. DMR 50 late-rank cases mostly sit
below rank 25, while DMR 200 has a larger 11-25 band. A safe ranking fix should
first target ordering inside the existing candidate pool and keep top-50
retrieval misses as a separate coverage problem. The DMR 200 reranker-pool
check adds that pool `25` is too lossy and pool `100` is too expensive for a
global default, even though pool `100` gives a small aggregate quality gain.
The signal-trigger audit gives a better next candidate: conditionally expanding
to pool `100` when the pool `50` top-1 result has only one retrieval source.
That is still an eval-only candidate until DMR 50 and LongMemEval cross-checks
are recorded. The cross-check is now recorded and it blocks a global default:
the signal helps DMR 50 but hurts LongMemEval 50. It can remain a DMR-specific
research candidate, but not a system-wide policy. The LongMemEval 200 guard
audit also blocks the simpler `fts-only` / `not-vector-only` guards. The DMR
323 expansion repeats that block on the DMR side. LongMemEval 500 now blocks
the last screened guard, `top1_single_source_rerank_margin_gt_1`, because it
introduces top-10 suppressions. No tested pool-signal guard should become a
runtime default.

## Next Ablations

The next useful ranking work is:

1. stop pursuing the current source/margin pool-signal guards as defaults;
2. define a runtime latency budget before any future ranking implementation;
3. require zero LongMemEval Recall@10 regression and zero top-10 suppressions
   before any runtime policy;
4. separate top-50 retrieval misses from late-rank ordering failures in the
   next coverage experiment;
5. test smaller, overlap-aware chunking instead of full-session merging;
6. avoid blunt keyword-boost query expansion unless a future answer-free
   rewrite policy proves it helps on both DMR and LongMemEval;
7. keep answer-generation scoring separate from retrieval-ranking scoring.
