# King Synapse

<p align="center">
  <strong>Readable memory for coding agents.</strong><br />
  A local associative memory network that remembers facts, follows hidden influences,
  explains why one trace won, and learns after the current answer is finished.
</p>

<p align="center">
  <a href="https://github.com/lake121380-source/king-synapse/stargazers"><img src="https://img.shields.io/github/stars/lake121380-source/king-synapse?style=social" alt="GitHub stars" /></a>
  <a href="https://github.com/lake121380-source/king-synapse/actions/workflows/ci.yml"><img src="https://github.com/lake121380-source/king-synapse/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/lake121380-source/king-synapse/blob/main/LICENSE"><img src="https://img.shields.io/github/license/lake121380-source/king-synapse" alt="License" /></a>
  <img src="https://img.shields.io/badge/language-Rust-orange" alt="Rust" />
  <img src="https://img.shields.io/badge/status-cognitive%20memory%20validated-2ea44f" alt="Status" />
</p>

## Why This Exists

Most coding agents still forget like a browser tab.

They may remember a note, a rule, or a chat summary, but they usually cannot
show the chain behind a thought: what memory started it, what hidden influence
pulled it forward, which alternatives were suppressed, and what likely happens
next.

King Synapse treats memory as a network, not a notebook.

```text
visible memory -> hidden influence -> dominant trace -> possible future
                 \-> suppressed alternatives stay visible
```

That makes it useful for long-running coding agents that need to stop repeating
the same mistakes, stop re-learning your preferences, and explain their memory
instead of hiding it inside a black box.

## What It Does

- Stores memories locally in SQLite with explicit scope, kind, provenance, and time.
- Connects memories with weighted edges so recall can spread through a graph.
- Finds visible memories from a query, then activates hidden influences nearby.
- Reports the dominant trace and the suppressed alternatives.
- Predicts likely next influences from the winning trace.
- Reinforces an association only after the current report is already captured.
- Exposes the same engine through a CLI and an MCP server for coding agents.

## A Small Example

Imagine this chain:

```text
skipped water before commute
  -> tired mood
  -> narrower attention
  -> higher scooter fall risk
  -> future mistake risk
```

A flat memory system may retrieve one sentence. King Synapse tries to show the
path: the visible seed, the hidden influence that became dominant, the other
possible traces that lost, and the next risk that follows.

## Quick Start

```bash
git clone https://github.com/lake121380-source/king-synapse.git
cd king-synapse
cargo build --release
```

Write a few memories:

```bash
./target/release/kr write "Skipped water before the scooter commute lowered mood." --kind state --scope user
./target/release/kr write "Tired mood narrows commute attention and raises fall risk." --kind fact --scope user
./target/release/kr write "Future commute mistakes increase when attention narrows." --kind fact --scope user
```

Recall and inspect the chain:

```bash
./target/release/kr recall "water commute attention" --explain
./target/release/kr trace "forgot water before commute while tired" --auto-context --predict
./target/release/kr trace "forgot water before commute while tired" --auto-context --reinforce --reinforce-k 3
```

On Windows, use `.\target\release\kr.exe` instead of `./target/release/kr`.

For a complete disposable run with sample output, see [docs/DEMO.md](docs/DEMO.md).

## Use It From An Agent

King Synapse includes a stdio MCP server.

```json
{
  "mcp": {
    "king-synapse": {
      "type": "local",
      "command": ["path/to/synapse-mcp"],
      "enabled": true
    }
  }
}
```

The MCP server exposes tools for write, recall, recent-list, forget,
entity-list, neighbor lookup, edge inspection, reinforcement, latent activation,
latent query, and cognitive trace.

## How It Is Different

| Project | Best at | What King Synapse adds |
| --- | --- | --- |
| Mem0 | Product-style long-term memory for AI apps. | Inspectable trace competition: dominant influence, suppressed alternatives, and post-report reinforcement. |
| Graphiti/Zep | Temporal knowledge graphs and graph evidence. | A cognitive trace layer over recall: hidden influence activation, prediction, and reinforcement isolation. |
| Letta | Stateful agents with editable memory blocks. | A local graph memory engine that can explain why a memory path won. |
| Flat notes / rules files | Human-authored instructions. | Automatic recall, graph activation, edge learning, and explainable memory paths. |

## Current Evaluation

The checked-in external comparison report is
[external-comparison-latest.json](crates/eval/reports/external-comparison-latest.json).
The readable summary is
[EXTERNAL_VALIDATION.md](docs/eval/EXTERNAL_VALIDATION.md).
The hosted/official configuration probe is recorded in
[external-comparison-hosted.json](crates/eval/reports/external-comparison-hosted.json):
Synapse is measured on the fixture, while hosted Graphiti/Zep, official Mem0
configuration, and Letta are `not_configured` in this environment.

| System | Local result on the cognitive fixture |
| --- | --- |
| King Synapse | 8/8 visible seed, 8/8 hidden influence, 8/8 dominant trace, 8/8 suppressed alternatives, 8/8 evidence paths, 8/8 future continuation, 8/8 reinforcement isolation. |
| Graphiti/Zep | 8/8 visible seed, 8/8 hidden influence, 8/8 evidence paths. Dominant/suppressed trace, prediction, and reinforcement are not exposed by this adapter. |
| Mem0 | 7/8 visible seed, 8/8 hidden influence through Mem0 OSS + DeepSeek + local Qdrant. Path evidence and trace competition are not exposed by this adapter. |
| Letta | Adapter and SDK are present, but no Letta endpoint is configured yet. |

The checked-in 50-sample long-memory reports use external data cached outside
the repo and commit only aggregate, redacted metrics:
[LongMemEval 50](crates/eval/reports/longmem-50-validation.json) and
[DMR 50](crates/eval/reports/dmr-50-validation.json).
The Phase 6 replay baseline is fixed in
[BENCHMARK_BASELINE.md](docs/eval/BENCHMARK_BASELINE.md) and
[GOLDEN_DATASET.md](docs/eval/GOLDEN_DATASET.md).
A current six-stage requirements audit is recorded in
[phase6-requirements-audit.json](crates/eval/reports/phase6-requirements-audit.json):
official-style DMR is local but not published-comparable, no global ranking
default is supported yet, hosted external comparisons are still open, and
productization is not ready.

The deterministic long-horizon cognitive gate is also recorded:
[LONG_HORIZON_VALIDATION.md](docs/eval/LONG_HORIZON_VALIDATION.md) and
[long-horizon-cognitive-memory.json](crates/eval/reports/long-horizon-cognitive-memory.json).
It passes the fixed long-session fixture with Recall@10 `1.000`,
CognitiveTraceDominance `1.000`, and HebbianConsistency `1.000`.
A detailed stability audit is also checked in at
[long-horizon-stability-audit.json](crates/eval/reports/long-horizon-stability-audit.json):
visible seed retention, old/new memory separation, hidden trace dominance, and
dominant-trace drift resistance are `1.000`. Expected future candidates are
present in top 10 for `8/8` cases, but only `6/8` currently carry matched
evidence terms. The audit records the two misses with empty candidate
matched-term arrays, so they are evidence-matching misses, not candidate-recall
misses.

| Validation | Baseline FTS/entity | + vector | + vector + reranker | Current read |
| --- | ---: | ---: | ---: | --- |
| LongMemEval cleaned 50 | 0.503 | 0.663 | 0.590 | Vector recall helps; reranker improves top-1 / MRR but can hurt top-10 coverage. |
| DMR candidate 50 | 0.188 | 0.438 | 0.584 | DMR improves strongly with vectors and reranking, but mapping/chunk skips remain large. |

The DMR row above is a candidate retrieval validation, not an official DMR
accuracy / ROUGE-L result. A separate official-style answer-generation runner
now scores generated answers against gold answers without committing raw
questions, answers, or generated text:
[OFFICIAL_DMR_RESULT.md](docs/eval/OFFICIAL_DMR_RESULT.md).

| Official-style DMR run | Retrieval Recall@10 | Exact | Substring | ROUGE-L F1 | Judge |
| --- | ---: | ---: | ---: | ---: | --- |
| 50 CUDA samples | 0.468 | 0.000 | 0.060 | 0.041 | 50 judged / 0 error |
| 50 CUDA top-context generator | 0.468 | 0.000 | 0.220 | 0.103 | not requested |
| 5-sample judge probe | 0.667 | 0.000 | 0.200 | 0.082 | 5 judged / 0 error |
| 200 CUDA samples | 0.411 | 0.000 | 0.040 | 0.037 | 200 judged / 0 error |
| 200 CUDA top-context generator | 0.411 | 0.000 | 0.120 | 0.067 | not requested |
| 500 request / 323 scored CUDA samples | 0.381 | 0.000 | 0.046 | 0.039 | 323 judged / 0 error |
| 500 request / 323 scored top-context generator | 0.380 | 0.000 | 0.121 | 0.075 | not requested |

This is still not a published-comparable official DMR result. The pinned
extractive 5 / 50 / 200 / 500-request runs are fully judged locally on
`deepseek-v4-flash`, but a later top-context candidate judge preflight now
returns HTTP `401` in the current environment. The remaining boundary is
published-comparable scoring policy, answer-generation quality, candidate
judge scoring, and the honest large-run claim of `500 request / 323 scored`,
not `500/500`.
The scoring review lives in [OFFICIAL_DMR_REVIEW.md](docs/eval/OFFICIAL_DMR_REVIEW.md).
The answer-synthesis audit adds another boundary: in the 323-scored
DMR 500-request run, `118/128` top-1 retrieval hits still did not include the
gold answer substring in the generated answer. That means the system can find a
relevant chunk and still fail to turn it into the final answer. The generator
ablation summary is recorded in
[official-dmr-generator-ablation-summary.json](crates/eval/reports/official-dmr-generator-ablation-summary.json).
The bottleneck taxonomy is recorded in
[official-dmr-bottleneck-taxonomy.json](crates/eval/reports/official-dmr-bottleneck-taxonomy.json).

| DMR scale | Extractive substring | Top-context substring | Extractive ROUGE-L F1 | Top-context ROUGE-L F1 |
| --- | ---: | ---: | ---: | ---: |
| 50 | 0.060 | 0.220 | 0.041 | 0.103 |
| 200 | 0.040 | 0.120 | 0.037 | 0.067 |
| 500 request / 323 scored | 0.046 | 0.121 | 0.039 | 0.075 |

So answer synthesis is now a real optimization target, but it is still
eval-only evidence. The top-context generator ablation has not been
judge-scored yet; the current DeepSeek configuration blocks that next judge
pass with HTTP `401`. Official DMR or product claims still need a finalized
published-comparable protocol and better answer-generation quality.

So the project is not in "add more features" mode. The current validation read
is: the architecture still holds, and the next work is narrower. DMR mapping
policy is now pinned to punctuation full-answer matching, and DMR 200 ranking
failure analysis shows both late-ranking cases and true top-50 retrieval
misses before any default ranking change. LongMemEval cross-check blocks a
global reranker-pool change for now because it prefers a different pool and
still keeps vector-only as the strongest top-10 coverage baseline. DMR 50
chunk-policy ablation shows that full-session merging removes top-50 misses
but hurts top-10 and top-1 placement, while keyword-boost query expansion keeps
misses unchanged and also hurts ranking. These are ranking tradeoffs, not
simple default changes. The DMR 50 transition audit keeps vector retrieval and
reranking as the productive direction; the DMR 200 transition audit repeats the
same pattern at larger scale, while also recording the reranker's small
regression surface. The latest pool-signal guard audit adds LongMemEval 500
and changes the decision: the last screened guard
(`top1_single_source_rerank_margin_gt_1`) is now blocked. It keeps Recall@10
slightly positive on LongMemEval 500 (`+0.0004`) but introduces `3` top-10
suppressions and one top-1 demotion, while adding `75.2 ms/query` amortized
latency on that dataset and about `0.5-0.8 s` on triggered queries. So no
tested pool-signal guard should become a runtime default. CUDA validation
status is recorded in
[GPU_VALIDATION_2026-07-02.md](docs/eval/GPU_VALIDATION_2026-07-02.md).

Run the same comparison:

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

## Architecture

```mermaid
flowchart LR
  A["write memory"] --> B["SQLite + FTS5 store"]
  B --> C["entities, scopes, kinds, timestamps"]
  C --> D["weighted memory graph"]
  Q["query"] --> R["visible recall"]
  R --> L["latent activation"]
  L --> T["dominant trace + suppressed alternatives"]
  T --> P["prediction"]
  T --> F["post-report reinforcement"]
  F --> D
```

The hot path is local-first. External services are only used by optional
comparison adapters or optional embedding/reranking paths.

## Project Status

- Core architecture is stable.
- Cognitive memory behavior is validated by local benchmarks and manual traces.
- Current phase is system validation: feature growth is frozen by default while internal benchmarks, external comparison, and long-horizon tests are checked.
- The Phase 6 requirements audit keeps productization blocked until official DMR, hosted comparison, ranking, and demo-claim gaps close.
- The deterministic long-horizon cognitive benchmark passes, but broader real-world long-horizon evidence is still open.
- External comparison is active: King Synapse, Graphiti/Zep local, and Mem0 OSS are measured; hosted Graphiti/Zep, official Mem0 configuration, and Letta still need credentials or endpoints.
- LongMemEval and DMR candidate retrieval now have 50-sample validation reports; official-style DMR answer-generation has local 5/50/200 and 500-request reports, and pinned DeepSeek judge runs now return `0` errors on `deepseek-v4-flash`.
- The next-gate readiness audit currently blocks heavy follow-up runs: top-context DMR judge preflight returns HTTP `401`, and hosted competitor comparison still lacks credentials or endpoints.
- Ranking guard work has expanded through LongMemEval 500. No tested pool-signal guard is safe enough for a runtime default.
- Phase 6 benchmark and golden replay baselines are fixed for the current validation scope.
- Public API stability notes live in `docs/API_SURFACE.md` and `docs/COMPATIBILITY.md`.

## Useful Commands

```bash
# Run the main tests
cargo test -p synapse-eval

# Run the cognitive-memory benchmark fixture
cargo bench -p synapse-eval --bench exported_cognitive_session

# Run the expanded 20-chain cognitive/prediction replay fixture
cargo bench -p synapse-eval --bench expanded_cognitive_replay

# Run the deterministic long-horizon cognitive-memory fixture
cargo bench -p synapse-eval --bench long_horizon_cognitive_memory

# Run the detailed long-horizon stability audit
cargo bench -p synapse-eval --bench long_horizon_stability_audit

# Run recall benchmarks
cargo run --release -p synapse-eval --bin kr-eval -- --tag baseline-rrf --json crates/eval/reports/baseline-rrf.json

# Run the Phase 6 lightweight replay baselines
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/coding_mem.toml --tag phase6-coding-mem-baseline --json crates/eval/reports/phase6-coding-mem-baseline.json
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/reference.toml --tag phase6-reference-baseline --json crates/eval/reports/phase6-reference-baseline.json
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/multihop.toml --tag phase6-multihop-baseline --json crates/eval/reports/phase6-multihop-baseline.json

# Run the 50-sample LongMemEval / DMR CUDA validation
python scripts/eval/longmem_dmr_smoke.py --endpoint https://hf-mirror.com --datasets longmem --modes all --longmem-sample-size 50 --k 50 --accelerator cuda --cuda-device-id 0 --embed-batch-size 32 --embed-max-length 256 --rerank-batch-size 32 --rerank-max-length 256 --output crates/eval/reports/longmem-50-validation.json --cleanup-cache
python scripts/eval/longmem_dmr_smoke.py --endpoint https://hf-mirror.com --datasets dmr --modes all --dmr-sample-size 50 --k 50 --accelerator cuda --cuda-device-id 0 --embed-batch-size 32 --embed-max-length 256 --rerank-batch-size 32 --rerank-max-length 256 --output crates/eval/reports/dmr-50-validation.json --cleanup-cache

# Build release binaries
cargo build --release
```

## Documentation

| Doc | What it is for |
| --- | --- |
| `docs/ROADMAP.md` | Current roadmap and next work. |
| `docs/DEMO.md` | A disposable CLI run with real sample output. |
| `docs/eval/SYSTEM_VALIDATION_PLAN.md` | Feature freeze rules, validation order, failure modes, and win criteria. |
| `docs/eval/SYSTEM_VALIDATION_REPORT.md` | Current system-validation conclusion and remaining limits. |
| `crates/eval/reports/readme-claims-support-audit.json` | README claim support check against committed Phase 6 evidence. |
| `crates/eval/reports/phase6-requirements-audit.json` | Current six-stage evidence matrix and productization gate status. |
| `crates/eval/reports/phase6-objective-coverage-audit.json` | Checklist mapping the six-stage objective to committed evidence and open gates. |
| `crates/eval/reports/phase6-next-gate-readiness.json` | Current readiness check for top-context judge scoring and hosted external comparison. |
| `crates/eval/reports/phase6-baseline-health-check-2026-07-04.json` | Latest local non-external Phase 6 health replay. |
| `docs/eval/LONG_HORIZON_VALIDATION.md` | Deterministic long-horizon cognitive-memory result, stability audit, and boundary. |
| `docs/eval/EXTERNAL_VALIDATION.md` | Readable external comparison result for Synapse, Graphiti/Zep, Mem0, and Letta. |
| `crates/eval/reports/external-comparison-hosted.json` | Hosted/official external configuration probe. |
| `docs/eval/BENCHMARK_BASELINE.md` | Fixed Phase 6 benchmark baselines and replay gates. |
| `docs/eval/GOLDEN_DATASET.md` | Golden dataset registry and replay policy. |
| `docs/eval/PERFORMANCE_ANALYSIS.md` | Phase 6 latency and performance-boundary analysis. |
| `crates/eval/reports/phase6-substage-timing-probe.json` | Small CUDA sub-stage and process metrics probe for embedding/vector/reranker/CPU/memory/GPU-memory costs. |
| `docs/eval/EXPERIMENT_LOG.md` | Phase 6 validation attempts and decisions. |
| `docs/eval/OFFICIAL_DMR_REVIEW.md` | Why current DMR reports are candidate retrieval baselines, not official DMR benchmark results. |
| `docs/eval/OFFICIAL_DMR_RESULT.md` | Sanitized official-style DMR answer-generation, judge probe, and answer-synthesis audit results. |
| `docs/eval/VALIDATION_LONGMEM_50.md` | LongMemEval 50-sample validation result. |
| `docs/eval/VALIDATION_DMR_50.md` | DMR 50-sample validation result. |
| `docs/eval/VALIDATION_DMR_50_PUNCTUATION.md` | DMR 50 rerun with punctuation-normalized answer mapping. |
| `docs/eval/RANKING_ABLATION.md` | DMR ranking ablations, transition audits, and LongMemEval cross-checks. |
| `docs/eval/DMR_MAPPING_AUDIT.md` | DMR skipped-row mapping audit. |
| `docs/eval/DMR_MAPPING_POLICY_REVIEW.md` | DMR mapping-policy coverage and the punctuation-boundary decision. |
| `docs/eval/FAILURE_ANALYSIS.md` | Anonymous failure bucket analysis. |
| `docs/eval/GPU_VALIDATION_2026-07-02.md` | CUDA validation status and runtime notes. |
| `docs/eval/LONGMEM_DMR_DATA_PLAN.md` | LongMemEval / DMR license, cache, and smoke-test rules. |
| `docs/COGNITIVE_NETWORK_MODEL.md` | The cognitive-network algorithm model. |
| `docs/COGNITIVE_MEMORY_FINAL_ACCEPTANCE.md` | Final cognitive-memory acceptance gates. |
| `docs/eval/EXTERNAL_COMPARISON_PLAN.md` | External comparison plan and adapter rules. |
| `docs/API_SURFACE.md` | Public API surface. |
| `docs/COMPATIBILITY.md` | Stability and compatibility policy. |
| `docs/MANUAL_VALIDATION.md` | Manual validation transcript. |
| `docs/V3_PROPOSAL_REVIEW.md` | How the broader King Recall v3 idea maps to this implementation. |

## Star History

Stars are not the point of the engine, but they do help people find the work.

<a href="https://star-history.com/#lake121380-source/king-synapse&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=lake121380-source/king-synapse&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=lake121380-source/king-synapse&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=lake121380-source/king-synapse&type=Date" />
  </picture>
</a>

## License

Apache-2.0. See `LICENSE`.
