# System Validation Plan

Status: Active validation phase

Date: 2026-07-03

## Phase Decision

King Synapse is now in **Phase 6: Full System Evaluation**.

The question for this phase is no longer "can we add another memory feature?"
The question is:

> Does the whole system hold together under repeatable, comparable tests?

Feature growth is frozen by default until this question has a clear answer.

## Feature Freeze Rules

During system validation, do not expand the product surface unless the change is
needed to make validation possible or to fix a bug found by validation.

Frozen by default:

- no new memory schema;
- no new CLI command families;
- no new MCP tool families;
- no new reflection, trace, prediction, or reinforcement semantics;
- no changes to frozen benchmark contracts;
- no tuning that changes baseline behavior without a recorded validation reason.

Allowed work:

- bug fixes found by validation;
- adapter configuration fixes;
- reproducibility improvements;
- evaluation manifests and reports;
- dataset fetch/cache instructions;
- documentation that clarifies the validation state.

## Experiment Report Discipline

Every Phase 6 experiment that can influence a project decision should record:

- Git commit used for the run;
- dataset name, source revision, checksum, and license when available;
- configuration version or report schema;
- accelerator, device, batch sizes, and max-length limits;
- model names and dependency versions when embeddings, rerankers, or judges are
  involved;
- date, requested sample size, scored sample size, and skipped count by reason;
- whether raw records, gold answers, generated answers, or temporary datasets
  were committed.

Readable reports should separate:

- engineering result: the measured numbers and whether the run completed;
- research interpretation: the narrower hypothesis supported by those numbers.

Do not turn one experiment into a universal claim. Treat it as current evidence
until the trend repeats across larger samples, a second dataset, or an external
comparison.

## Validation Questions

System validation answers three questions.

| Question | Meaning |
| --- | --- |
| Stability | Same input, same fixture, same configuration should produce the same scored behavior. |
| Consistency | Recall, trace, prediction, and reinforcement should not contradict each other. |
| Comparative value | King Synapse should expose useful memory behavior that competing systems do not expose under the same fixture. |

## Test Order

### 1. Internal Deterministic Gates

These tests protect the system from regressing while the external comparison
continues.

```bash
cargo fmt --all -- --check
cargo test -p synapse-eval
cargo bench -p synapse-eval --bench exported_cognitive_session
cargo bench -p synapse-eval --bench expanded_cognitive_replay
cargo bench -p synapse-eval --bench long_horizon_cognitive_memory
```

Required result:

- formatting passes;
- `synapse-eval` tests pass;
- exported cognitive session keeps visible recall, hidden influence, dominant
  trace, suppressed alternatives, prediction, and reinforcement checks intact.
- expanded cognitive replay keeps 20 cognitive trace checks and 20 prediction
  checks intact.
- long-horizon cognitive memory keeps visible recall, hidden influence
  dominance, and Hebbian reinforcement intact in one shared long-session
  store.

### 2. Current External Comparison

Run the checked-in external harness:

```bash
cargo run -p synapse-eval --bin kr-external-eval -- \
  --graphiti-command python \
  --graphiti-arg scripts/eval/graphiti_adapter.py \
  --mem0-command python \
  --mem0-arg scripts/eval/mem0_adapter.py \
  --letta-command python \
  --letta-arg scripts/eval/letta_adapter.py \
  --json crates/eval/reports/external-comparison-latest.json
```

Current known status:

| System | Status |
| --- | --- |
| King Synapse | measured |
| Graphiti/Zep | measured through local Kuzu mode |
| Mem0 | measured through OSS SDK + DeepSeek + local Qdrant |
| Letta | adapter present, not configured |

This stage should not force unsupported competitor behavior into fake scores.
Unsupported surfaces remain `unsupported`.

### 3. Letta Configuration

Goal:

- measure Letta with either a disposable hosted project or a local endpoint;
- keep memory-block behavior separate from autonomous agent-loop behavior;
- record missing semantics as unsupported instead of failed.

Required before acceptance:

- `letta-client` version recorded;
- endpoint mode recorded;
- no production agent state mutated;
- raw memory block evidence captured.

### 4. Long-Horizon And Public Dataset Tests

LongMemEval and DMR now have a small smoke runner and sanitized aggregate
report. The current 50-sample validation baseline is fixed, but official DMR
and larger public benchmark claims are not complete.

Before importing or mirroring data:

- confirm license and redistribution terms;
- add fetch/cache instructions;
- record dataset checksum or source commit;
- keep third-party dataset files out of the repository unless redistribution is
  clearly allowed.

Validation purpose:

- LongMemEval checks long-memory behavior over time;
- DMR checks fact-retrieval sanity;
- neither replaces the cognitive-trace fixture.

### 5. Hosted-Mode Reruns

When credentials are available, rerun:

- Graphiti with full Neo4j/OpenAI extraction mode;
- Mem0 with an official embedding path.

Keep local deterministic modes as reproducible baselines. Hosted-mode results
must be marked separately from local deterministic results.

Current hosted/official probe:

- `crates/eval/reports/external-comparison-hosted.json`
- King Synapse: measured as the same local baseline on the fixture.
- Graphiti/Zep Neo4j/OpenAI path: `not_configured`.
- Mem0 official/custom configuration path without the DeepSeek fallback:
  `not_configured`.
- Letta hosted/local endpoint path: `not_configured`.

This records the current environment boundary. It is not a hosted measurement
of the competitor systems.

### 6. Benchmark And Golden Replay Baselines

The current Phase 6 replay baseline is fixed in:

- `docs/eval/BENCHMARK_BASELINE.md`
- `docs/eval/GOLDEN_DATASET.md`
- `crates/eval/reports/phase6-benchmark-baseline.json`
- `crates/eval/datasets/regression/golden-manifest.json`

Ordinary PRs should preserve the lightweight committed replay baselines.
Retrieval-strategy changes must compare against the LongMemEval / DMR
50-sample CUDA reports before changing defaults.

### 7. Performance Analysis

The current performance pass is recorded in:

- `docs/eval/PERFORMANCE_ANALYSIS.md`
- `crates/eval/reports/phase6-performance-profile.json`

It records end-to-end latency and branch deltas from existing reports. A later
small CUDA probe added direct embedding, vector-search, FTS/entity/RRF,
reranker, process memory, process CPU, and GPU memory metrics. The 50-sample
LongMemEval / DMR reports now include process-level memory and CPU metrics;
GPU memory accounting is verified on the small CUDA DMR probe and should be
repeated on 50-sample runs only after retrieval or model-configuration changes.

## Failure Modes To Watch

| Failure mode | What it means |
| --- | --- |
| Drift | Repeated runs change scored behavior without a fixture or config change. |
| Contradiction | Recall returns one story while trace or prediction explains another. |
| Hidden answer injection | Adapter input accidentally gives the target answer to a competitor system. |
| Unsupported-as-failure | A competitor is scored as wrong for a surface it does not expose. |
| Reinforcement leakage | Post-report learning mutates the report that was supposed to describe the pre-learning state. |
| External contamination | Default user databases, production agents, or persistent external accounts are mutated. |

## What Counts As A Win

King Synapse does not need to beat every external system on every long-memory
task. The validation win condition is narrower and more important:

1. internal cognitive-memory gates remain stable;
2. external comparison is reproducible and honest about unsupported surfaces;
3. King Synapse consistently exposes trace evidence, dominant/suppressed
   candidates, prediction, and reinforcement isolation where competitors do not;
4. long-horizon tests do not reveal contradiction or uncontrolled drift;
5. every claim in README can be traced to a local report, benchmark, or source
   note.

## Immediate Execution Plan

This is the current order of work. Do not reorder it unless a validation run
finds a blocking bug.

| Step | Work | Exit condition |
| --- | --- | --- |
| 1 | Close the DMR 200 documentation pass and sync it to GitHub. | `official-dmr-200.json` is documented, checked for raw data / secrets, committed, and pushed. |
| 2 | Fix LLM judge authorization/configuration outside the repository. | A 5-10 sample judge probe succeeds without writing an API key or raw answer text. |
| 3 | Rerun DMR 50 with the fixed judge. | Judge status has successful scored samples, skipped/error counts are explicit, and lexical metrics still match the local scoring path. |
| 4 | Run DMR 500-request local scoring on CUDA. | Done as `official-dmr-500.json`: requested 500, scored 323, mapping skips 177, raw data not committed. |
| 5 | Review DMR mapping policy before claiming 500/500 coverage. | Done in `DMR_MAPPING_POLICY_REVIEW.md`: keep punctuation-only mapping as the pinned local boundary; relaxed-token coverage must be separately labeled. |
| 6 | Expand ranking failure localization beyond DMR 50. | Done for DMR 200: 17 top-50-only late-ranking cases and 43 top-50 retrieval misses are split before changing reranker defaults. |
| 7 | Repeat the strongest retrieval/ranking setting on LongMemEval. | Done for reranker-pool cross-check: LongMemEval prefers pool `25` among reranker variants and vector-only for Recall@10, so no global default change is justified. |
| 8 | Record deterministic long-horizon cognitive validation. | Done in `LONG_HORIZON_VALIDATION.md`: Recall@10, HebbianConsistency, and CognitiveTraceDominance are all `1.000` on the fixed fixture. |
| 9 | Complete fair external comparison gaps. | Current environment probe is done: Letta endpoint, hosted Graphiti, and official-embedding Mem0 are explicitly marked `not_configured`; real hosted measurement still waits on credentials/endpoints. |
| 10 | Make the productization decision. | README claims, validation reports, external comparison, and long-horizon evidence agree. |

## Current Open Items

- Stage 1 internal baseline: passed in `docs/eval/VALIDATION_RUN_2026-07-02.md`.
- Stage 2 repeatability check: stable for five King Synapse runs in
  `docs/eval/VALIDATION_RUN_2026-07-02.md`.
- Stage 3 external comparison rerun: completed in
  `docs/eval/EXTERNAL_VALIDATION.md`.
- Stage 4 external-run manifest: refreshed at
  `crates/eval/reports/external-comparison-manifest.json`.
- Letta measured run: `letta-client 1.12.1` is installed, but Letta is still
  not measured because no hosted or local endpoint is configured.
- LongMemEval / DMR smoke path: implemented in
  `scripts/eval/longmem_dmr_smoke.py`; latest sanitized report is
  `crates/eval/reports/longmem-dmr-smoke-latest.json`.
- GPU validation path: passed after installing CUDA 12 runtime DLLs into a
  user cache outside the repository; see
  `docs/eval/GPU_VALIDATION_2026-07-02.md`.
- Stage 7 system validation report: added at
  `docs/eval/SYSTEM_VALIDATION_REPORT.md`.
- 50-sample LongMemEval / DMR validation: completed on CUDA; see
  `docs/eval/VALIDATION_LONGMEM_50.md`,
  `docs/eval/VALIDATION_DMR_50.md`, and
  `docs/eval/FAILURE_ANALYSIS.md`.
- Failure-analysis follow-up: focus on DMR mapping/chunk skips and final
  candidate ranking.
- Benchmark baseline fixation: completed for the current Phase 6 scope; see
  `docs/eval/BENCHMARK_BASELINE.md`.
- Golden Dataset / regression baseline: current registry added at
  `crates/eval/datasets/regression/golden-manifest.json`; the expanded
  `expanded-cognitive-replay` benchmark now covers 20 cognitive trace replays
  and 20 prediction replays.
- Performance analysis: first pass added at
  `docs/eval/PERFORMANCE_ANALYSIS.md`; sub-stage timing and process metrics
  probe added at `crates/eval/reports/phase6-substage-timing-probe.json`;
  process memory and CPU instrumentation has been promoted to the 50-sample
  LongMemEval / DMR reports, and GPU memory accounting is verified on the
  small CUDA DMR probe.
- DMR mapping audit: added at `docs/eval/DMR_MAPPING_AUDIT.md`; the 278
  pre-eval skipped rows are now localized to strict answer-string mapping, not
  empty chunk generation. A punctuation-normalized candidate rerun is pinned at
  `docs/eval/VALIDATION_DMR_50_PUNCTUATION.md`.
- DMR mapping policy review: added at
  `docs/eval/DMR_MAPPING_POLICY_REVIEW.md` and
  `crates/eval/reports/dmr-mapping-policy-review.json`. It confirms
  punctuation full-answer mapping covers `323/500` rows, significant-token
  containment covers `442/500`, and the current decision is to keep punctuation
  as the pinned local boundary while treating relaxed-token mapping as a
  separately labeled diagnostic option.
- Official-style DMR answer generation: 5-query smoke, 50-query CUDA scoring,
  200-query CUDA local scoring, and a 500-request CUDA local scoring pass are
  recorded at
  `docs/eval/OFFICIAL_DMR_RESULT.md`,
  `crates/eval/reports/official-dmr-5-extractive.json`,
  `crates/eval/reports/official-dmr-50.json`, and
  `crates/eval/reports/official-dmr-200.json`, and
  `crates/eval/reports/official-dmr-500.json`; fixed LLM judge authorization
  is still unresolved. The DMR 500-request pass scored `323/500` requested
  samples because the pinned punctuation mapping skipped 177 source rows before
  selection.
- Ranking ablation: first DMR 50 reranker-pool pass is recorded at
  `docs/eval/RANKING_ABLATION.md` and
  `crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json`; pool `50`
  remains the best Recall@10 setting in that pass, so no default change is
  justified yet.
- DMR 50 top-k ablation is recorded at
  `crates/eval/reports/ranking-ablation-dmr-50-top-k.json`; top-k `50`
  reveals six answer-bearing chunks between rank 11 and 50 but does not improve
  Recall@10 or top-1 hits, so it is diagnostic evidence rather than a default
  change.
- DMR 50 ranking failure audit is recorded at
  `crates/eval/reports/ranking-failure-audit-dmr-50.json`; it confirms 6
  top-50-only late-ranking cases, 6 top-50 retrieval misses, 14 reranker
  recoveries into top-10, and 1 reranker suppression from top-10.
- DMR 50 chunk-policy ablation is recorded at
  `crates/eval/reports/ranking-ablation-dmr-50-chunk-policy.json`; merging
  each source row into one session chunk removes the 6 top-50 retrieval misses
  but drops Recall@10 from `0.468` to `0.360` and top-1 hits from `28` to `7`,
  so full-session merging is not a safe default fix.
- DMR 50 query-expansion ablation is recorded at
  `crates/eval/reports/ranking-ablation-dmr-50-query-expansion.json`;
  question-derived keyword boosting keeps the 6 retrieval misses unchanged,
  drops Recall@10 from `0.468` to `0.403`, and drops top-1 hits from `28` to
  `21`, so blunt query expansion is not a safe default fix.
- DMR 200 ranking failure expansion is recorded at
  `crates/eval/reports/dmr-200-punctuation-validation.json`,
  `crates/eval/reports/ranking-ablation-dmr-200-top-k.json`, and
  `crates/eval/reports/ranking-failure-audit-dmr-200.json`; it confirms 17
  top-50-only late-ranking cases, 43 top-50 retrieval misses, 40 reranker
  recoveries into top-10, 49 reranker promotions to top-1, 3 reranker
  suppressions from top-10, and 5 reranker demotions from top-1.
- LongMemEval 50 reranker-pool cross-check is recorded at
  `crates/eval/reports/ranking-ablation-longmem-50-reranker-pool.json`; pool
  `25` is best among reranker variants, but vector-only remains the strongest
  Recall@10 baseline. This blocks a global reranker-pool default change from
  the current DMR evidence.
- Long-horizon cognitive-memory validation is recorded at
  `docs/eval/LONG_HORIZON_VALIDATION.md` and
  `crates/eval/reports/long-horizon-cognitive-memory.json`; the fixed
  deterministic fixture passes Recall@10, HebbianConsistency, and
  CognitiveTraceDominance at `1.000`.
- Hosted/official external comparison probe is recorded at
  `crates/eval/reports/external-comparison-hosted.json`; Graphiti/Zep
  Neo4j/OpenAI, Mem0 official/custom configuration, and Letta endpoint paths
  are all `not_configured` in the current environment, with zero adapter
  failures. Real hosted measurements remain open until credentials/endpoints
  are available.
