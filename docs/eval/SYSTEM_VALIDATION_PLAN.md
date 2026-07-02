# System Validation Plan

Status: Active validation phase

Date: 2026-07-02

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
```

Required result:

- formatting passes;
- `synapse-eval` tests pass;
- exported cognitive session keeps visible recall, hidden influence, dominant
  trace, suppressed alternatives, prediction, and reinforcement checks intact.
- expanded cognitive replay keeps 20 cognitive trace checks and 20 prediction
  checks intact.

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

It records end-to-end latency and branch deltas from existing reports. Memory,
CPU, embedding sub-stage, vector-search sub-stage, and reranker sub-stage
timings are explicitly marked as not yet instrumented.

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
  `docs/eval/PERFORMANCE_ANALYSIS.md`; sub-stage timing instrumentation remains
  a follow-up.
- Hosted Graphiti and official-embedding Mem0 reruns: not started.
