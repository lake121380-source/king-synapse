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
- "What dimension are our memory embeddings?" — paraphrase, vector branch should fix.
- "user language preference for commits" — CN-EN cross-lingual, vector branch should fix.

Both are exactly the kind of miss the dense + rerank branches are designed
to recover, so the harness gives us a real signal to optimize against.

## Layout (v0.5.3 harness contract)

The `crates/eval` layout is frozen by `v0.5.3-benchmark-harness`. Existing
dataset files and reserved benchmark/report paths have fixed roles. Renaming
or deleting an existing path is a breaking change under
`docs/COMPATIBILITY.md`. Adding a sibling dataset or benchmark path is
non-breaking.

| Path | Role |
| --- | --- |
| `datasets/reference.toml` | Recall Platform baseline. `Recall@10 = 1.000` — must not regress. |
| `datasets/multihop.toml` | Multi-hop and mixed Chinese/English technical recall baseline. `Recall@10 = 1.000` after ADR-006 CJK query expansion — must not regress. |
| `datasets/coding_mem.toml` | Bundled 20-memory / 30-query golden set for `cargo bench-recall`. |
| `datasets/regression/` | Frozen regression datasets. Add here to lock in a known corpus + queries and detect future retrieval / algorithm regressions. |
| `datasets/synthetic/` | Synthetic datasets for scale and stress testing (controlled size and distribution). |
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

1. **Deterministic value object.** Same `(dataset, algorithm, config)` → identical `BenchmarkReport`. No `timestamp`, `hostname`, `cpu`, `random_seed`, or `git_dirty` fields.
2. **Sparse by design.** A report contains only the metrics that are meaningful for that benchmark. Missing metrics MUST NOT be treated as `0.0`.
3. **Finite values (SHOULD).** Producers should emit finite `f64` values; `NaN` / `Inf` are neither validated nor forbidden.
4. **Benchmark naming.** `benchmark` field uses `lowercase-kebab-case`: `reference-recall`, `multihop-recall`, `reflection-yield`, `merge-precision`, `hebbian-consistency`.

`AlgorithmMetric` is `#[non_exhaustive]`. Adding a new variant is non-breaking; removing or renaming one is breaking.

## Algorithm → Benchmark → Metric Discipline

Every algorithm RFC (RFC-012 onward) MUST:

1. Ship at least one benchmark under `benches/algorithms/`.
2. Map that benchmark to at least one `AlgorithmMetric` variant. If no existing variant fits, the RFC proposes a new variant as an additive change to `AlgorithmMetric`.
3. Emit results as `BenchmarkReport` values that satisfy the determinism invariant.

An algorithm that ships without a benchmark cannot be compared against previous versions, so it does not ship.
