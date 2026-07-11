# synapse-eval

Recall benchmark harness for King Synapse.

## Quick start

```bash
# baseline: RRF only (FTS + entity branches), no model downloads
cargo run --release -p synapse-eval --bin kr-eval -- --tag baseline-rrf --json crates/eval/reports/baseline-rrf.json

# add the dense vector branch (downloads multilingual-e5-base ~470MB on first run)
cargo run --release -p synapse-eval --bin kr-eval -- --vectors --tag rrf-with-vectors --json crates/eval/reports/rrf-with-vectors.json

# add the cross-encoder reranker (downloads bge-reranker-base ~300MB on first run)
cargo run --release -p synapse-eval --bin kr-eval -- --vectors --rerank --tag rrf-vec-rerank --json crates/eval/reports/rrf-vec-rerank.json
```

These commands use the real workspace package and binary names directly. If
you add a local Cargo alias later, keep it as a shortcut for this command
shape.

`kr-eval` also exposes `--rrf-k`, `--fts-weight`, `--entity-weight`, and
`--vector-weight` for ranking sweeps. The defaults keep the current behavior.

## External Comparison Harness

```bash
# Run the post-freeze external comparison harness.
# This measures King Synapse locally. Pass adapter commands below to include
# external systems in the same report.
cargo run -p synapse-eval --bin kr-external-eval -- --json crates/eval/reports/external-comparison-latest.json

# Run only the local King Synapse cognitive fixture.
cargo run -p synapse-eval --bin kr-external-eval -- --systems king-synapse

# Run with an external Graphiti adapter script.
# The command receives one argument: an adapter-input JSON path.
# It must print an ExternalSystemRun JSON object to stdout.
cargo run -p synapse-eval --bin kr-external-eval -- \
  --systems graphiti \
  --graphiti-command python \
  --graphiti-arg scripts/eval/graphiti_adapter.py \
  --json crates/eval/reports/graphiti-external-comparison.json

# Run with the included Mem0 adapter script.
cargo run -p synapse-eval --bin kr-external-eval -- \
  --systems mem0 \
  --mem0-command python \
  --mem0-arg scripts/eval/mem0_adapter.py \
  --json crates/eval/reports/mem0-external-comparison.json

# Run with the included Letta adapter script.
cargo run -p synapse-eval --bin kr-external-eval -- \
  --systems letta \
  --letta-command python \
  --letta-arg scripts/eval/letta_adapter.py \
  --json crates/eval/reports/letta-external-comparison.json
```

The harness uses `crates/eval/datasets/exported_cognitive_session.toml` and
emits a runtime report, not a frozen `BenchmarkReport`. Runtime metadata,
raw evidence, configured external systems, unsupported capabilities, and
adapter failures belong in this external report format.

The checked-in latest report is
`crates/eval/reports/external-comparison-latest.json`. It records King Synapse
as a measured local run, Graphiti/Zep measured through
`scripts/eval/graphiti_adapter.py`, Mem0 measured through
`scripts/eval/mem0_adapter.py`, and Letta through
`scripts/eval/letta_adapter.py` as `not_configured` until a Letta client and
endpoint are available. If `graphiti-core` and `kuzu` are installed but
Neo4j/OpenAI credentials are absent, the Graphiti adapter uses a local Kuzu
graph backend with deterministic embeddings and explicit fixture triplets. The
Mem0 adapter uses the Mem0 OSS Python SDK when `mem0ai` and either
`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, or `MEM0_CONFIG_JSON` /
`MEM0_CONFIG_PATH` are available. With DeepSeek, the adapter generates a
DeepSeek + deterministic local embedder + local Qdrant config automatically.
The Letta adapter uses the official `letta-client` SDK to create and inspect
agent memory blocks when `LETTA_API_KEY`, `LETTA_BASE_URL`, or
`LETTA_ENVIRONMENT=local` is configured. If dependencies or credentials are
missing, adapters report `not_configured` with the missing names.

The checked-in hosted/official configuration probe is
`crates/eval/reports/external-comparison-hosted.json`. It forces Graphiti onto
the Neo4j/OpenAI path, disables the Mem0 DeepSeek fallback, and checks Letta for
a real endpoint. In the current environment it records King Synapse as
measured and Graphiti/Zep, Mem0, and Letta as `not_configured`, with zero
adapter failures.

The separate DeepSeek-first protocol gate is
`crates/eval/reports/deepseek-external-protocol-gate.json`. It treats Mem0 OSS
with DeepSeek, local Graphiti/Zep Kuzu, and King Synapse as the domestic/local
design-validation lane. It is valid Phase 6 evidence for Synapse's own
cognitive-trace design claim, but it is not an OpenAI/Neo4j hosted official
competitor claim.

## LongMemEval / DMR Harness

```bash
python scripts/eval/longmem_dmr_smoke.py --endpoint https://hf-mirror.com --datasets longmem --modes all --longmem-sample-size 50 --k 50 --accelerator cuda --cuda-device-id 0 --embed-batch-size 32 --embed-max-length 256 --rerank-batch-size 32 --rerank-max-length 256 --output crates/eval/reports/longmem-50-validation.json --cleanup-cache
python scripts/eval/longmem_dmr_smoke.py --endpoint https://hf-mirror.com --datasets dmr --modes all --dmr-sample-size 50 --k 50 --accelerator cuda --cuda-device-id 0 --embed-batch-size 32 --embed-max-length 256 --rerank-batch-size 32 --rerank-max-length 256 --output crates/eval/reports/dmr-50-validation.json --cleanup-cache
```

The runner downloads LongMemEval cleaned and the DMR candidate MSC-Self-Instruct
data to a user cache outside the repository, generates temporary TOML datasets
for the existing `kr-eval` binary, and writes only sanitized aggregate reports.
The checked-in 50-sample reports are
`crates/eval/reports/longmem-50-validation.json` and
`crates/eval/reports/dmr-50-validation.json`.

Use `--modes` to isolate branch checks without overwriting the baseline report:
`baseline`, `vector`, `vector-rerank`, or `all`.

Use `--datasets` to isolate a long run:
`longmem`, `dmr`, or `all`.

Use `--accelerator cuda --cuda-device-id 0` for vector/reranker runs. The
runner records accelerator, embedding, and reranker settings in the sanitized
report. On Windows, CUDA mode requires ONNX Runtime's CUDA provider
dependencies such as `cublasLt64_12.dll` and cuDNN DLLs to be visible on PATH.
The 2026-07-02 local GPU setup is recorded in
`docs/eval/GPU_VALIDATION_2026-07-02.md`.

The checked-in reports exclude raw questions, answers, dialogs, and session
text. The DMR path is still a candidate harness, not the official DMR harness.

## Phase 6 Baseline Registry

The current Phase 6 replay baseline is fixed in:

- `reports/phase6-benchmark-baseline.json`
- `datasets/regression/golden-manifest.json`
- `reports/phase6-coding-mem-baseline.json`
- `reports/phase6-reference-baseline.json`
- `reports/phase6-multihop-baseline.json`

Readable summaries live in `docs/eval/BENCHMARK_BASELINE.md` and
`docs/eval/GOLDEN_DATASET.md`.

The current deterministic long-horizon cognitive gate is fixed in:

- `reports/long-horizon-cognitive-memory.json`

Readable summary: `docs/eval/LONG_HORIZON_VALIDATION.md`.

The current Phase 6 performance profile is fixed in:

- `reports/phase6-performance-profile.json`
- `reports/phase6-substage-timing-probe.json`

The sub-stage probe also records process-tree CPU, process memory, and Windows
GPU Process Memory counter samples around the `cargo run` / `kr-eval`
validation command.

Readable summary: `docs/eval/PERFORMANCE_ANALYSIS.md`.

The current DMR mapping audit is fixed in:

- `reports/dmr-mapping-audit.json`
- `reports/dmr-mapping-policy-review.json`

Readable summary: `docs/eval/DMR_MAPPING_AUDIT.md`.

Policy review: `docs/eval/DMR_MAPPING_POLICY_REVIEW.md`.

The current punctuation-normalized DMR candidate rerun is fixed in:

- `reports/dmr-50-punctuation-validation.json`
- `reports/dmr-200-punctuation-validation.json`

Readable summary: `docs/eval/VALIDATION_DMR_50_PUNCTUATION.md`.

The official-style DMR answer-generation reports are fixed in:

- `reports/official-dmr-500.json`
- `reports/official-dmr-500-top-context-extractive.json`
- `reports/official-dmr-200.json`
- `reports/official-dmr-200-top-context-extractive.json`
- `reports/official-dmr-50.json`
- `reports/official-dmr-50-top-context-extractive.json`
- `reports/official-dmr-judge-probe.json`
- `reports/official-dmr-answer-synthesis-audit.json`
- `reports/official-dmr-generator-ablation-dmr-500.json`
- `reports/official-dmr-generator-ablation-dmr-200.json`
- `reports/official-dmr-generator-ablation-dmr-50.json`
- `reports/official-dmr-5-extractive.json`

Readable summary: `docs/eval/OFFICIAL_DMR_RESULT.md`.

The first ranking ablation report is fixed in:

- `reports/ranking-ablation-dmr-50-reranker-pool.json`
- `reports/ranking-ablation-dmr-50-top-k.json`
- `reports/ranking-ablation-dmr-50-chunk-policy.json`
- `reports/ranking-ablation-dmr-50-query-expansion.json`
- `reports/ranking-failure-audit-dmr-50.json`
- `reports/ranking-transition-audit-dmr-50.json`
- `reports/ranking-ablation-dmr-200-top-k.json`
- `reports/ranking-failure-audit-dmr-200.json`
- `reports/ranking-transition-audit-dmr-200.json`
- `reports/ranking-ablation-longmem-50-reranker-pool.json`

Readable summary: `docs/eval/RANKING_ABLATION.md`.

## Algorithm Benchmarks

```bash
# RFC-012 reflection benchmark suite (deterministic + rule-based)
cargo bench -p synapse-eval --bench reflection_yield

# RFC-013 merge benchmark suite (rule-based)
cargo bench -p synapse-eval --bench merge_precision

# RFC-014 forget benchmark suite (rule-based)
cargo bench -p synapse-eval --bench forget_precision

# RFC-015 hebbian benchmark suite (rule-based)
cargo bench -p synapse-eval --bench hebbian_consistency

# Latent cognitive-chain benchmark (visible seed -> hidden influence)
cargo bench -p synapse-eval --bench cognitive_chain_recall

# Cognitive trace dominance benchmark (visible seed + hidden influence -> dominant candidate)
cargo bench -p synapse-eval --bench cognitive_trace_dominance

# Predictive trace benchmark (dominant candidate -> next hidden influence)
cargo bench -p synapse-eval --bench predictive_trace

# Exported cognitive-session benchmark (shared long-session TOML fixture)
cargo bench -p synapse-eval --bench exported_cognitive_session

# Expanded Phase 6 cognitive/prediction replay benchmark
cargo bench -p synapse-eval --bench expanded_cognitive_replay
```

The benchmark emits two `BenchmarkReport` values:

- `benchmark = "reflection-yield"` for the current v0.6.6 rule-based algorithm
- `benchmark = "reflection-yield-deterministic"` for the deterministic reference baseline

Both reports use `AlgorithmMetric::ReflectionYield`.

The merge benchmark emits one `BenchmarkReport` value:

- `benchmark = "merge-precision"` for the v0.7.3 rule-based merge algorithm

The report uses `AlgorithmMetric::MergePrecision`.

The forget benchmark emits one `BenchmarkReport` value:

- `benchmark = "forget-precision"` for the v0.8.3 rule-based forget algorithm

The report uses `AlgorithmMetric::ForgetPrecision`.

The hebbian benchmark emits one `BenchmarkReport` value:

- `benchmark = "hebbian-consistency"` for the v0.9.3 rule-based hebbian algorithm

The report uses `AlgorithmMetric::HebbianConsistency`.

The cognitive-chain benchmark emits one `BenchmarkReport` value:

- `benchmark = "cognitive-chain-recall"` for Chinese latent-chain inspection

The report uses `AlgorithmMetric::RecallAt10`. It measures whether a visible
seed memory recalled from Chinese query text can activate the expected hidden
downstream memory through `QueryLatentActivationProbe` and auto-derived
state/goal context.

The cognitive-trace benchmark emits one `BenchmarkReport` value:

- `benchmark = "cognitive-trace-dominance"` for trace competition behavior

The report uses `AlgorithmMetric::CognitiveTraceDominance`. It measures
whether `CognitiveTraceProbe` makes the expected hidden/downstream influence
the dominant candidate after visible recall supplies seed memories and
state/goal context modulates latent activation. The fixture covers six chain
families: body state to commute attention, social pressure to work goals, past
failure to future decision, object/tool use to task risk, social memory to
emotion, and subconscious avoidance to error review.

The predictive-trace benchmark emits one `BenchmarkReport` value:

- `benchmark = "predictive-trace"` for dominant-candidate continuation

The report uses `AlgorithmMetric::RecallAt10`. It measures whether
`CognitiveTraceProbe::predict_continuation()` can start from the current
dominant candidate and surface the expected next hidden influence through
outgoing associative edges.

The activation-parameter-sweep benchmark emits one `BenchmarkReport` value:

- `benchmark = "activation-parameter-sweep"` for final cognitive-memory parameter coverage

The report reuses existing metric IDs. `RecallAt10` measures the fraction of
latent-chain parameter settings that preserve visible seed -> hidden influence
activation. `CognitiveTraceDominance` measures the fraction of trace settings
that still choose the expected hidden influence as dominant.
`HebbianConsistency` measures the fraction of trace-learning settings that
still persist the expected visible <-> hidden edges after reinforcement.
The final sweep covers seven cognitive-chain families and five parameter
settings, including deeper multi-step activation, wider fanout, broader trace
limits, and higher cap/decay settings used to approximate production-range
behavior without changing public contracts.

The long-horizon cognitive-memory benchmark emits one `BenchmarkReport` value:

- `benchmark = "long-horizon-cognitive-memory"` for multi-day cognitive-memory behavior

It writes several day-stamped cognitive chains into one shared in-memory store,
including visible distractors and hidden distractors. It then verifies ordinary
recall, cognitive trace dominance, and post-trace reinforcement in that shared
long-session memory graph. The checked report records Recall@10 `1.000`,
CognitiveTraceDominance `1.000`, and HebbianConsistency `1.000` for the fixed
fixture.

The exported cognitive-session benchmark emits one `BenchmarkReport` value:

- `benchmark = "exported-cognitive-session"` for the TOML-backed long-session fixture

It loads `crates/eval/datasets/exported_cognitive_session.toml`, seeds one
shared memory graph, and verifies visible seed recall, dominant hidden
influence, predictive future continuation, and post-trace reinforcement.

The expanded cognitive replay benchmark emits one `BenchmarkReport` value:

- `benchmark = "expanded-cognitive-replay"` for the Phase 6 20-chain replay fixture

It loads `crates/eval/datasets/regression/expanded_cognitive_replay.toml`.
The fixture keeps the external-comparison dataset stable while fixing 20
cognitive trace replays and 20 prediction replays for regression checks.

## Metrics

Per run the harness reports:

- **Recall@5 / Recall@10**: fraction of relevant memories surfaced in top-K
- **MRR@10**: mean reciprocal rank of the first relevant hit
- **NDCG@10**: normalized discounted cumulative gain
- **P50 / P95 latency**: per-query wall-clock latency
- A `--json` dump containing every per-query miss for offline diffing

## Dataset

`datasets/coding_mem.toml` is the bundled golden set: 20 memories spread
across factual / preference / failure / playbook / state, plus 30 queries
covering FTS-only, entity-only, vector-only, and cross-lingual paraphrases.
Each query lists the keys of memories that count as relevant.

To add a new entry: write a `[[memories]]` block with a unique `key`, then
add `[[queries]]` blocks referencing that key in `relevant`.

## Network requirement

`--vectors` and `--rerank` download ONNX weights from HuggingFace on first
run into `FASTEMBED_CACHE_DIR` (or `./.fastembed_cache`). If `huggingface.co`
is unreachable from your network, set `HF_ENDPOINT=https://hf-mirror.com`
before running. The baseline RRF bench needs no network access.

## Model Accelerator

The vector and reranker paths can request an ONNX Runtime execution provider
through `KING_SYNAPSE_ACCELERATOR`:

| Value | Behavior |
| --- | --- |
| unset / `cpu` / `none` / `off` | Previous CPU behavior. |
| `cuda` | Use CUDA provider on Windows validation builds. |
| `directml` / `dml` / `gpu` | Use DirectML provider on Windows. |

The LongMemEval / DMR runner can set this for a validation run:

```bash
python scripts/eval/longmem_dmr_smoke.py --endpoint https://hf-mirror.com --datasets dmr --modes all --dmr-sample-size 50 --k 50 --accelerator cuda --cuda-device-id 0 --embed-batch-size 32 --embed-max-length 256 --rerank-batch-size 32 --rerank-max-length 256 --output crates/eval/reports/dmr-50-validation.json --cleanup-cache
```

GPU mode is infrastructure for validation speed. It does not change the memory
schema or the scoring contract.

## Baseline

```
tag:        baseline-rrf
corpus:     20 memories / 30 queries / top-10
Recall@5:   0.950
Recall@10:  0.950
MRR@10:     0.950
NDCG@10:    0.941
P50 lat:    1.17 ms
P95 lat:    1.89 ms
```

Two queries miss:
- "What dimension are our memory embeddings?" 鈥?paraphrase, vector branch should fix.
- "user language preference for commits" 鈥?CN-EN cross-lingual, vector branch should fix.

Both are exactly the kind of miss the dense + rerank branches are designed
to recover, so the harness gives us a real signal to optimize against.

## Phase 5.4 end-to-end cognitive shadow evaluator

Run:

```bash
python scripts/eval/phase5_end_to_end_cognitive.py
```

The evaluator builds an isolated Agent-memory workload through `Store`, obtains
all candidate ranks and scores from the real `RecallEngine`, and compares the
retrieval baseline with margin-guarded confidence, recency, failure, and full
cognitive policies. It is shadow-only. A protocol `PASS` validates provenance,
determinism, candidate-pool preservation, and safety; it does not require or
claim positive cognitive gain.

Current stable workload result: cognitive MRR@5 is `0.8333` versus retrieval
`0.6667`, but equals the best recency/failure control. Runtime authorization is
false.

## Phase 6.0 Memory Intelligence Benchmark

Run:

```bash
python scripts/eval/phase6_memory_intelligence_benchmark.py
```

This benchmark freezes 320 repository-authored Agent-memory scenarios / 1,920
memories across 10 categories and a fixed 160/80/80 split. Each scenario is
written through a real isolated `Store`, and candidate ranks/scores come from
`RecallEngine::recall_profiled`; the dataset contains no manual
`baseline_score` field.

The current foundation result is `Recall@1 = 0.3000`, `Recall@3/5 = 1.0000`,
`MRR@5 = 0.6500`, expected-candidate retrieval `1.0000`, determinism `1.0000`,
and Store-unchanged rate `1.0000`. `PASS` validates workload integrity,
provenance, reachability, determinism, and safety only. No cognitive policy or
simple baseline is compared, and runtime authorization remains false. See
`docs/eval/PHASE6_0_MEMORY_INTELLIGENCE_BENCHMARK.md`.

## Phase 6.1 Cognitive vs Simple Baseline Evaluation

Run:

```bash
python scripts/eval/phase6_cognitive_baseline_comparison.py
```

The evaluator reuses all 320 Phase 6.0 real-RecallEngine scenarios and compares
retrieval, confidence-only, recency-only, failure-only, simple-combined, and the
unchanged Margin-Guard Cognitive policy. It also runs five single-factor
removals by deleting one factor from a cloned Cognitive Trace and invoking the
same booster.

The current result is equality at Recall@1 `0.3000` / MRR@5 `0.6500` for every
policy. This does not prove metadata aggregation: with the locked
`threshold = 0.08`, no scenario has two candidates inside the guarded margin,
so the competition-eligible and top-1-change rates are both `0.0000`.
Attribution is therefore unresolved, Hermes shadow integration is not
recommended, and runtime authorization remains false. See
`docs/eval/PHASE6_1_COGNITIVE_BASELINE_COMPARISON.md`.
## Layout (v0.5.3 harness contract)

The `crates/eval` layout is frozen by `v0.5.3-benchmark-harness`. Existing
dataset files and reserved benchmark/report paths have fixed roles. Renaming
or deleting an existing path is a breaking change under
`docs/COMPATIBILITY.md`. Adding a sibling dataset or benchmark path is
non-breaking.

| Path | Role |
| --- | --- |
| `datasets/reference.toml` | Recall Platform baseline. `Recall@10 = 1.000` 鈥?must not regress. |
| `datasets/multihop.toml` | Multi-hop and mixed Chinese/English technical recall baseline. `Recall@10 = 1.000` after ADR-006 CJK query expansion 鈥?must not regress. |
| `datasets/coding_mem.toml` | Bundled 20-memory / 30-query golden set for `cargo bench-recall`. |
| `datasets/regression/` | Frozen regression datasets. Add here to lock in a known corpus + queries and detect future retrieval / algorithm regressions. |
| `datasets/synthetic/` | Synthetic datasets for scale and stress testing (controlled size and distribution). |
| `datasets/cognitive_policy/` | Phase 5.3.3 controlled policy-authority scenarios with stable labels and explicit baseline scores; evaluation-only and not an end-to-end recall benchmark. |
| `datasets/cognitive_policy_generalization/` | Phase 5.3.4 disjoint 30/12/21 train-validation-held-out policy split with fixed parameters and SHA-256 seals; controlled shadow evidence only. |
| `datasets/cognitive_end_to_end/` | Phase 5.4 deterministic Agent-memory workload. Candidate ranks and scores come from real `Store + RecallEngine`; no manual `baseline_score` field is allowed. |
| `datasets/memory_intelligence/` | Phase 6.0 generated 320-scenario / 1,920-memory benchmark foundation with balanced splits, explicit timelines and labels, real RecallEngine scores, and no policy comparison. |
| `datasets/dmr/` | Deep Memory Retrieval external dataset mirrors. |
| `datasets/longmemeval/` | LongMemEval external dataset mirrors. |
| `benches/recall/` | Recall-pipeline benchmark source (RRF, vector, rerank). |
| `benches/memory/` | Memory-growth / compression / churn benchmark source. |
| `benches/algorithms/` | Per-algorithm benchmarks (Reflection / Merge / Forget / Hebbian). Each algorithm RFC ships at least one benchmark here. |
| `reports/` | Serialized `BenchmarkReport` outputs. |

## Benchmark Contract

Every Phase 5 benchmark returns a `synapse_eval::BenchmarkReport`:

```rust
BenchmarkReport {
    benchmark: String,                              // lowercase-kebab-case
    metrics: BTreeMap<AlgorithmMetric, f64>,        // deterministic order
}
```

Rules (RFC-011 Part D):

1. **Deterministic value object.** Same `(dataset, algorithm, config)` 鈫?identical `BenchmarkReport`. No `timestamp`, `hostname`, `cpu`, `random_seed`, or `git_dirty` fields.
2. **Sparse by design.** A report contains only the metrics that are meaningful for that benchmark. Missing metrics MUST NOT be treated as `0.0`.
3. **Finite values (SHOULD).** Producers should emit finite `f64` values; `NaN` / `Inf` are neither validated nor forbidden.
4. **Benchmark naming.** `benchmark` field uses `lowercase-kebab-case`: `reference-recall`, `multihop-recall`, `reflection-yield`, `merge-precision`, `hebbian-consistency`.

`AlgorithmMetric` is `#[non_exhaustive]`. Adding a new variant is non-breaking; removing or renaming one is breaking.

## Algorithm 鈫?Benchmark 鈫?Metric Discipline

Every algorithm RFC (RFC-012 onward) MUST:

1. Ship at least one benchmark under `benches/algorithms/`.
2. Map that benchmark to at least one `AlgorithmMetric` variant. If no existing variant fits, the RFC proposes a new variant as an additive change to `AlgorithmMetric`.
3. Emit results as `BenchmarkReport` values that satisfy the determinism invariant.

An algorithm that ships without a benchmark cannot be compared against previous versions, so it does not ship.


## Phase 6.2 Recall Score Distribution Study

Phase 6.2 stops booster development and measures the real RecallEngine score operating point:

```bash
python scripts/eval/phase6_recall_score_distribution.py
```

It re-runs the frozen 320-query / 1,920-memory Phase 6.0 workload and reports:

- candidate-count and per-rank score distributions;
- raw and normalized Top1-Top2, Top2-Top3, Top3-Top4, and Top4-Top5 gaps;
- mean, median/P50, P90, P95, and P99;
- descriptive coverage for `0.01`, `0.02`, `0.05`, `0.08`, `0.10`, `0.15`, and `0.20` top-relative margins;
- category/split diagnostics and all 320 scenario score records.

Observed on the frozen workload:

```text
minimum Top1-Top2 normalized gap = 0.101449
locked threshold                 = 0.080000
locked eligible scenarios        = 0 / 320
0.15 descriptive coverage        = 192 / 320
0.20 descriptive coverage        = 192 / 320
```

The `0.15`/`0.20` observations are not threshold recommendations. The evaluator does not execute Cognitive ranking, modify RecallEngine, mutate scores, select a threshold, connect Hermes, or authorize runtime.

Artifacts:

- `src/phase6_recall_score_distribution.rs`
- `src/bin/phase6_recall_score_distribution.rs`
- `tests/phase6_recall_score_distribution_test.rs`
- `reports/phase6_recall_score_distribution.json`
- `../../scripts/eval/phase6_recall_score_distribution.py`
- `../../docs/eval/PHASE6_2_RECALL_SCORE_DISTRIBUTION_STUDY.md`

## Phase 7.0 Cognitive Architecture Contract

Phase 7.0 moves the research mainline from retrieval-score intervention to evidence-grounded Experience-to-Pattern learning. The eval-only contract defines `PatternCandidate`, evidence provenance, scope and exclusions, counterexample search, testable predictions, falsification conditions, confidence boundaries, and a non-autonomous lifecycle.

The contract gate rejects missing evidence, missing scope, missing falsification, skipped counterexample search, invalid confidence, and premature `Active` status. It does not implement Pattern discovery, persist Patterns, change RecallEngine or CognitiveBooster, connect Hermes, execute a strategy, or authorize runtime.

Artifacts:

- `src/phase7_cognitive_architecture_contract.rs`
- `src/bin/phase7_cognitive_architecture_contract.rs`
- `tests/phase7_cognitive_architecture_contract_test.rs`
- `reports/phase7_cognitive_architecture_contract.json`
- `../../scripts/eval/phase7_cognitive_architecture_contract.py`
- `../../docs/COGNITIVE_ARCHITECTURE_NORTH_STAR.md`
- `../../docs/eval/PHASE7_0_COGNITIVE_ARCHITECTURE_REORIENTATION.md`

## Phase 7.1 Transfer Evaluation Protocol

The eval crate contains a frozen 30-scenario transfer benchmark with 20 held-out cases, six comparison arms, 13 transfer/safety metrics, and a deterministic failure taxonomy.

```powershell
cargo run -p synapse-eval --bin phase7_transfer_evaluation_protocol
python scripts/eval/phase7_transfer_evaluation_protocol.py
```

Outputs:

```text
crates/eval/reports/phase7_transfer_evaluation_protocol.json
```

The report intentionally keeps `outcome_evaluation_complete=false`. It validates the benchmark and experimental protocol; it does not run Pattern Mining or claim transfer improvement.

## Phase 7.2 Pattern Extraction Protocol

The eval crate now defines a design-only `PatternExtractionProvider` boundary and deterministic validation for grounded Pattern Candidate output.

```powershell
cargo run -p synapse-eval --bin phase7_pattern_extraction_protocol
python scripts/eval/phase7_pattern_extraction_protocol.py
```

Dataset and report:

```text
crates/eval/datasets/pattern_extraction/phase7_2_pattern_extraction_design.json
crates/eval/reports/phase7_pattern_extraction_protocol.json
```

The ten inputs contain 20 supporting experiences and 10 counterexamples. They exclude target transfer answers and all held-out cases. No model provider or extraction performance is included.

## Phase 7.2.1 Bounded Pattern Extraction Provider

```powershell
cargo test -p synapse-eval --test phase7_bounded_pattern_extraction_provider_test --jobs 1 -- --test-threads=1
python scripts/eval/phase7_bounded_pattern_extraction_provider.py
```

Artifacts:

```text
src/phase7_bounded_pattern_extraction_provider.rs
src/bin/phase7_bounded_pattern_extraction_provider.rs
tests/phase7_bounded_pattern_extraction_provider_test.rs
reports/phase7_bounded_pattern_extraction_provider.json
../../docs/eval/PHASE7_2_1_BOUNDED_PATTERN_EXTRACTION_PROVIDER.md
```

The provider is a deterministic weak baseline. `10/10` contract acceptance means only that the artifact is bounded and grounded; it does not mean Pattern validation, transfer success, persistence, or runtime authorization.

## Phase 7.2.2 Frozen Provider Capability Matrix

```powershell
cargo test -p synapse-eval --test phase7_pattern_provider_comparison_test --jobs 1 -- --test-threads=1
python scripts/eval/phase7_pattern_provider_comparison.py
```

Artifacts:

```text
config/phase7_2_2_canonical_prompt_v1.md
config/phase7_2_2_parser_policy_v1.json
config/phase7_2_2_scorer_policy_v1.json
config/phase7_2_2_provider_manifests.json
src/phase7_pattern_provider_comparison.rs
tests/phase7_pattern_provider_comparison_test.rs
reports/phase7_pattern_provider_comparison.json
../../docs/eval/PHASE7_2_2_PROVIDER_CAPABILITY_MATRIX.md
```

The weak baseline is measured; the model-backed row is blocked by authorization and has no fabricated metrics. `unsupported_claim_rate` is the primary safety metric. Linguistic sophistication, fluency, and style are not rewarded. Held-out transfer evaluation remains closed.
