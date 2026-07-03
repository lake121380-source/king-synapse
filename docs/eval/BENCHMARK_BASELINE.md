# Benchmark Baseline

Date: 2026-07-02

Status: Phase 6 baseline fixed for the current validation scope.

Machine-readable manifest:

`crates/eval/reports/phase6-benchmark-baseline.json`

Golden dataset registry:

`crates/eval/datasets/regression/golden-manifest.json`

## Recall Baselines

These are lightweight, local, no-model-download replay gates.

| Dataset | Report | Memories | Queries | Recall@10 | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| `coding_mem.toml` | `phase6-coding-mem-baseline.json` | 20 | 30 | 0.950 | Must stay at or above 0.950 unless an ADR records an intentional baseline change. |
| `reference.toml` | `phase6-reference-baseline.json` | 20 | 5 | 1.000 | Must remain 1.000. |
| `multihop.toml` | `phase6-multihop-baseline.json` | 20 | 5 | 1.000 | Must remain 1.000. |

Known `coding_mem` misses remain intentional baseline signal:

- `What dimension are our memory embeddings?`
- `user language preference for commits`

Those are the two misses the vector branch is expected to address. Do not hide
them by changing the golden set without recording the reason.

## Algorithm Baselines

The full algorithm bench run completed with every fixed metric at `1.0`.

| Benchmark | Fixed metric(s) |
| --- | --- |
| `reflection-yield` | `ReflectionYield = 1.0` |
| `reflection-yield-deterministic` | `ReflectionYield = 1.0` |
| `merge-precision` | `MergePrecision = 1.0` |
| `forget-precision` | `ForgetPrecision = 1.0` |
| `hebbian-consistency` | `HebbianConsistency = 1.0` |
| `cognitive-chain-recall` | `RecallAt10 = 1.0` |
| `cognitive-trace-dominance` | `CognitiveTraceDominance = 1.0` |
| `trace-reinforcement` | `CognitiveTraceDominance = 1.0`, `HebbianConsistency = 1.0` |
| `predictive-trace` | `RecallAt10 = 1.0` |
| `activation-parameter-sweep` | `RecallAt10 = 1.0`, `CognitiveTraceDominance = 1.0`, `HebbianConsistency = 1.0` |
| `long-horizon-cognitive-memory` | `RecallAt10 = 1.0`, `CognitiveTraceDominance = 1.0`, `HebbianConsistency = 1.0` |
| `exported-cognitive-session` | `RecallAt10 = 1.0`, `CognitiveTraceDominance = 1.0`, `HebbianConsistency = 1.0` |
| `expanded-cognitive-replay` | `RecallAt10 = 1.0`, `CognitiveTraceDominance = 1.0`, `HebbianConsistency = 1.0` |

These metrics are deterministic `BenchmarkReport` values. A future change that
lowers one of them is a regression unless the change is intentionally approved
and documented.

The checked long-horizon cognitive-memory report is
`crates/eval/reports/long-horizon-cognitive-memory.json`. Its readable boundary
is recorded in `docs/eval/LONG_HORIZON_VALIDATION.md`.

The detailed long-horizon stability audit is
`crates/eval/reports/long-horizon-stability-audit.json`. It is not a frozen
`BenchmarkReport` contract value; it is a diagnostic report that records old /
new memory separation, future continuation, and reinforcement drift checks.
Current diagnostic read: visible / trace stability is `1.000`, while future
candidate presence is also `1.000`. Future matched-evidence stability is
`0.750`: the two misses are present as continuation candidates at rank 1 but do
not carry matched evidence terms.

`expanded-cognitive-replay` loads
`crates/eval/datasets/regression/expanded_cognitive_replay.toml`. It fixes 20
cognitive trace replays and 20 prediction replays without changing the
8-chain external-comparison fixture.

## Long-Memory Baselines

These are validation baselines, not lightweight PR gates. They use sanitized
reports and keep raw third-party data out of the repo.

| Dataset | Report | Baseline Recall@10 | Vector Recall@10 | Vector + reranker Recall@10 | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| LongMemEval cleaned 50 | `longmem-50-validation.json` | 0.503 | 0.663 | 0.590 | Explain movement across all three modes. |
| DMR candidate 50 | `dmr-50-validation.json` | 0.188 | 0.438 | 0.584 | Track mapping/chunk skips separately from retrieval failures. |
| DMR candidate 50, punctuation mapping | `dmr-50-punctuation-validation.json` | 0.198 | 0.280 | 0.468 | Treat as the pinned punctuation-normalized candidate rerun; do not compare as the same sample as strict-string DMR. |

Heavy LongMemEval / DMR reruns should use the CUDA path documented in
`docs/eval/GPU_VALIDATION_2026-07-02.md`.

The 50-sample long-memory reports also record process-tree CPU and memory
metrics for each retrieval mode.

DMR candidate baselines are not official DMR benchmark scores. See
`docs/eval/OFFICIAL_DMR_REVIEW.md` for the answer-generation and judge
requirements that remain open.

## Replay Commands

```bash
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/coding_mem.toml --tag phase6-coding-mem-baseline --json crates/eval/reports/phase6-coding-mem-baseline.json
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/reference.toml --tag phase6-reference-baseline --json crates/eval/reports/phase6-reference-baseline.json
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/multihop.toml --tag phase6-multihop-baseline --json crates/eval/reports/phase6-multihop-baseline.json
```

```bash
cargo bench -p synapse-eval --bench reflection_yield --bench merge_precision --bench forget_precision --bench hebbian_consistency --bench cognitive_chain_recall --bench cognitive_trace_dominance --bench trace_reinforcement --bench predictive_trace --bench activation_parameter_sweep --bench long_horizon_cognitive_memory --bench exported_cognitive_session --bench expanded_cognitive_replay
```
