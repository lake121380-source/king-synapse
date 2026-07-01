# Manual Validation

Status: **Baseline Transcript**

This file records manual validation scenarios for the user-facing cognitive
memory surfaces. Commands that would persist memories should be run against a
temporary configuration or in-memory harness during release validation, not
against a user's default database.

## Scope

Covered surfaces:

- `kr recall`
- `kr latent-query`
- `kr trace`
- `kr trace --reinforce`
- MCP `synapse_trace`

The deterministic benchmark evidence lives in
`docs/COGNITIVE_MEMORY_FINAL_ACCEPTANCE.md`; this file covers normal and
empty/error input behavior that is easier to inspect as a transcript.

## CLI Recall

Normal input:

```bash
cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/reference.toml --tag manual-recall
```

Expected result:

- command exits successfully;
- `Recall@10 = 1.000`;
- per-query misses report says all queries hit `Recall@10 == 1.0`.

Empty/error input:

```bash
cargo run -p synapse-cli -- recall ""
```

Expected result:

- command exits without panic;
- output contains no hits, or JSON output is an empty hit list when `--json` is
  used;
- no memory is written or reinforced.

## CLI Latent Query

Normal input:

```bash
cargo bench -p synapse-eval --bench cognitive_chain_recall
```

Expected result:

- command exits successfully;
- `benchmark = "cognitive-chain-recall"`;
- `RecallAt10 = 1.0`;
- fixture covers visible query -> seed memory -> hidden influence.

Empty/error input:

```bash
cargo run -p synapse-cli -- latent-query "" --json
```

Expected result:

- command exits without panic;
- report contains an empty or low-information `seeds`/`activations` set;
- latent inspection does not create `RecallHit`s and does not mutate Store.

## CLI Trace

Normal input:

```bash
cargo bench -p synapse-eval --bench cognitive_trace_dominance
```

Expected result:

- command exits successfully;
- `benchmark = "cognitive-trace-dominance"`;
- `CognitiveTraceDominance = 1.0`;
- dominant candidate is the expected hidden/downstream influence in every
  fixture case.

Empty/error input:

```bash
cargo run -p synapse-cli -- trace "" --json
```

Expected result:

- command exits without panic;
- report has no dominant candidate when no visible or latent evidence exists;
- trace does not reinforce unless `--reinforce` is explicitly supplied.

## CLI Trace Reinforcement

Normal input:

```bash
cargo bench -p synapse-eval --bench trace_reinforcement
```

Expected result:

- command exits successfully;
- `benchmark = "trace-reinforcement"`;
- `CognitiveTraceDominance = 1.0`;
- `HebbianConsistency = 1.0`;
- reinforcement happens only after the trace report is computed.

Empty/error input:

```bash
cargo run -p synapse-cli -- trace "" --reinforce --reinforce-k 0 --json
```

Expected result:

- command exits without panic;
- no reinforcement report is produced when fewer than two distinct memory ids
  are available;
- Store remains unchanged.

## MCP Trace

Normal input:

```json
{
  "name": "synapse_trace",
  "arguments": {
    "query": "forgot water before commute while tired",
    "auto_context": true,
    "reinforce": true,
    "reinforce_k": 3
  }
}
```

Expected result:

- response contains `report`;
- response contains `reinforcement` when enough distinct visible/dominant
  memory ids exist;
- `reinforcement` is `null` when disabled or when insufficient memory ids are
  available;
- learning routes through Hebbian -> StoreMutation -> SQLite, not through the
  trace probe itself.

Empty/error input:

```json
{
  "name": "synapse_trace",
  "arguments": {
    "query": "",
    "reinforce": true,
    "reinforce_k": 1
  }
}
```

Expected result:

- response is a valid JSON object or a structured MCP error;
- no panic or process crash;
- `report.dominant` is absent/null when no evidence exists;
- `reinforcement` is `null` unless at least two distinct memory ids are
  available.

## Release Use

Before a final cognitive-memory release, rerun these scenarios and paste the
actual command outputs or MCP responses into a dated release-validation note.
