# Validation Run 2026-07-02

Status: Passed

Phase: Phase 6 - Full System Evaluation

Scope: Stage 1 internal baseline validation and Stage 2 repeatability check

## Run Metadata

| Field | Value |
| --- | --- |
| Commit | `77573152663432e596245a4f25174443a58a87c8` |
| Branch | `main` |
| OS | Microsoft Windows NT 10.0.19045.0 |
| PowerShell | 5.1.19041.6456 |
| rustc | `rustc 1.95.0 (59807616e 2026-04-14)` |
| cargo | `cargo 1.95.0 (f2d3ce0bd 2026-03-21)` |
| Date | 2026-07-02 |

## Commands

### Formatting

```bash
cargo fmt --all -- --check
```

Result: passed.

### Evaluation Test Suite

```bash
cargo test -p synapse-eval
```

Result: passed.

Observed summary:

```text
test result: ok. 40 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

The test run also executed the `kr-eval`, `kr-external-eval`, and doc-test
targets with zero tests and no failures.

### Exported Cognitive Session Benchmark

```bash
cargo bench -p synapse-eval --bench exported_cognitive_session
```

Result: passed.

Observed report:

```json
{
  "benchmark": "exported-cognitive-session",
  "metrics": {
    "RecallAt10": 1.0,
    "HebbianConsistency": 1.0,
    "CognitiveTraceDominance": 1.0
  }
}
```

## Validation Result

Stage 1 internal baseline validation passed.

Current evidence supports:

- formatting is clean;
- the `synapse-eval` test suite passes;
- the exported cognitive-session benchmark preserves full recall, Hebbian
  consistency, and cognitive trace dominance scores.

Stage 1 alone does not prove repeatability across multiple runs, external
comparison reproducibility, Letta behavior, LongMemEval behavior, or DMR
behavior. Stage 2 below covers repeatability for the King Synapse fixture.

## Stage 2 Repeatability Check

Command shape:

```bash
cargo run -p synapse-eval --bin kr-external-eval -- \
  --systems king-synapse \
  --json <temporary-repeatability-report.json>
```

The command was run five times against temporary JSON output files under the
system temp directory. The temporary files were deleted after the metric summary
was extracted.

| Run | Status | Visible | Hidden | Dominant | Suppressed | Evidence | Future | Reinforcement |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | measured | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| 2 | measured | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| 3 | measured | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| 4 | measured | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| 5 | measured | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |

Observed mean-latency range:

```text
4.52 ms .. 4.70 ms
```

Stage 2 conclusion: stable for the exported cognitive-session fixture.

No drift was observed in:

- visible seed recall;
- hidden influence retrieval;
- dominant trace selection;
- suppressed alternative visibility;
- evidence path availability;
- future continuation;
- reinforcement isolation.

The `reinforcement_isolated` metric stayed at 8/8 in every run, so this
repeatability check did not observe reinforcement leaking backward into the
current report.

## Stage 3 External Comparison Rerun

Command shape:

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

Environment notes:

- Graphiti/Zep used local Kuzu deterministic mode.
- Mem0 used the OSS SDK with DeepSeek model `deepseek-v4-flash`, deterministic
  local embedder, and a temporary local Qdrant directory.
- Letta remained `not_configured` because `letta-client` and a Letta endpoint
  were not available.
- A stale invalid DeepSeek key was present in the shell on the first attempt;
  the successful rerun used a temporary hidden input override. No key was
  written to files.

Final rerun result:

| System | Status | Visible | Hidden | Dominant | Evidence | Future | Reinforcement |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| King Synapse | measured | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| Graphiti/Zep | measured | 8/8 | 8/8 | 0/8 unsupported | 8/8 | 0/8 unsupported | 0/8 unsupported |
| Mem0 | measured | 8/8 | 8/8 | 0/8 unsupported | 0/8 unsupported | 0/8 unsupported | 0/8 unsupported |
| Letta | not_configured | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 |

The latest checked-in external comparison report was updated:

`crates/eval/reports/external-comparison-latest.json`

## Stage 4 External-Run Manifest

An initial manifest was added:

`crates/eval/reports/external-comparison-manifest.json`

The manifest records:

- commit;
- OS and tool versions;
- Python package versions;
- adapter modes;
- model names;
- credential names required by each mode.

It does not record API key values.

## Stage 5 Letta Local Endpoint Attempt

Command shape:

```bash
LETTA_ENVIRONMENT=local \
cargo run -p synapse-eval --bin kr-external-eval -- \
  --systems letta \
  --letta-command python \
  --letta-arg scripts/eval/letta_adapter.py \
  --json <temp>/king-synapse-letta-local-validation.json
```

Environment notes:

- `letta-client` was installed successfully at version `1.12.1`.
- No `LETTA_API_KEY`, `LETTA_BASE_URL`, or `OPENAI_API_KEY` was available in
  the shell.
- `LETTA_ENVIRONMENT=local` was used to test a local Letta endpoint without
  writing credentials to files.

Result:

| System | Status | Visible | Hidden | Dominant | Evidence | Future | Reinforcement |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Letta | failed | 0/8 failed | 0/8 failed | 0/8 failed | 0/8 failed | 0/8 failed | 0/8 failed |

Failure reason:

```text
Letta adapter failed: Connection error.
```

The Letta-only external comparison report was saved at:

`crates/eval/reports/letta-external-comparison.json`

Stage 5 conclusion: the Letta SDK dependency is no longer missing, but no
local or hosted Letta endpoint was reachable in this environment. Letta is
therefore still not measured. The next Letta validation step requires either a
running local Letta server or a disposable hosted Letta project.

The temporary adapter input file was not committed.

## Stage 6 LongMemEval / DMR Smoke Run

Command:

```bash
python scripts/eval/longmem_dmr_smoke.py \
  --endpoint https://hf-mirror.com \
  --cleanup-cache
```

Runner:

`scripts/eval/longmem_dmr_smoke.py`

Report:

`crates/eval/reports/longmem-dmr-smoke-latest.json`

Environment and data notes:

- LongMemEval cleaned source: `xiaowu0162/longmemeval-cleaned`,
  revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`, license `mit`.
- DMR candidate source: `MemGPT/MSC-Self-Instruct`, revision
  `5138f416f8fa76b75b2e080da87e8a8e346e1500`, license `apache-2.0`.
- Raw source files were downloaded to a user cache outside the repository.
- Temporary TOML datasets were generated under the system temp directory.
- Raw questions, answers, dialogs, haystack sessions, and temporary TOML files
  were not committed.
- `--cleanup-cache` removed the downloaded raw cache after the report was
  written.
- Scoring used the existing `kr-eval` RecallEngine with FTS/entity branches
  only. No vectors, reranker, LLM judge, or hosted service was used.

Result:

| Dataset | Sample | Memory chunks | Recall@5 | Recall@10 | MRR@10 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LongMemEval cleaned | 10/10 | 484 | 0.600 | 0.817 | 0.383 | 0.510 |
| DMR candidate MSC-Self-Instruct | 20/20 | 100 | 0.192 | 0.317 | 0.124 | 0.162 |

Stage 6 conclusion: the fetch/cache path, schema loader, temporary dataset
generation, sanitized reporting, and small-sample run are working. This is not
a full LongMemEval or official DMR benchmark result. The low DMR candidate
score shows that plain FTS/entity recall is not enough for many question-style
deep-memory retrieval rows.
