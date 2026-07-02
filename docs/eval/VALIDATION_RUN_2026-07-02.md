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
