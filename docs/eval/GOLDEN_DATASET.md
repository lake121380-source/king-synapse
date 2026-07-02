# Golden Dataset

Date: 2026-07-02

Status: current Phase 6 replay registry fixed.

Registry:

`crates/eval/datasets/regression/golden-manifest.json`

## What Is Fixed

| Set | Scope | Stored in repo? | Purpose |
| --- | --- | --- | --- |
| `coding-mem-20x30` | 20 memories, 30 queries | yes | Primary recall golden set. |
| `reference-20x5` | 20 memories, 5 queries | yes | Must preserve `Recall@10 = 1.0`. |
| `multihop-20x5` | 20 memories, 5 queries | yes | Must preserve `Recall@10 = 1.0` for multi-hop / CJK recall. |
| `exported-cognitive-session-8` | 8 cognitive chains | yes | Stable external-comparison cognitive fixture. |
| `expanded-cognitive-replay-20` | 20 cognitive chains | yes | 20 cognitive trace replays and 20 prediction replays. |
| `longmem-cleaned-50` | 50 LongMemEval cleaned queries | no raw records | Long-memory trend validation. |
| `dmr-msc-self-instruct-50` | 50 evaluated DMR candidate queries | no raw records | Retrieval/ranking and mapping validation. |
| `dmr-msc-self-instruct-50-punctuation` | 50 evaluated DMR candidate queries | no raw records | Punctuation-normalized DMR candidate validation. |

Raw LongMemEval and DMR records are intentionally not committed. Their fixed
source revisions, source hashes, sample sizes, and sanitized reports are listed
in the registry.

## Replay Rule

For ordinary PRs, replay the committed sets and algorithm baselines:

```bash
cargo test -p synapse-eval
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/coding_mem.toml --tag phase6-coding-mem-baseline --json crates/eval/reports/phase6-coding-mem-baseline.json
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/reference.toml --tag phase6-reference-baseline --json crates/eval/reports/phase6-reference-baseline.json
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/multihop.toml --tag phase6-multihop-baseline --json crates/eval/reports/phase6-multihop-baseline.json
cargo bench -p synapse-eval --bench exported_cognitive_session
cargo bench -p synapse-eval --bench expanded_cognitive_replay
```

For retrieval strategy changes, replay the full algorithm bench suite in
`docs/eval/BENCHMARK_BASELINE.md`.

For long-memory strategy changes, rerun the CUDA LongMemEval / DMR commands
from `README.md` and compare with `VALIDATION_LONGMEM_50.md`,
`VALIDATION_DMR_50.md`, `VALIDATION_DMR_50_PUNCTUATION.md`, and
`FAILURE_ANALYSIS.md`.

## Current Boundary

This registry fixes the current replay baseline, including the 20-chain
cognitive/prediction replay set. It does not prove hosted external systems or
official DMR completion; those remain separate Phase 6 boundaries. The current
DMR sets are candidate retrieval baselines, not official answer-generation
results. See `docs/eval/OFFICIAL_DMR_REVIEW.md`.
