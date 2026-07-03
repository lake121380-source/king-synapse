# External Validation

Date: 2026-07-03

Status: local external comparison completed; hosted/official configuration
probe recorded.

Reports:

- `crates/eval/reports/external-comparison-latest.json`
- `crates/eval/reports/external-comparison-hosted.json`

## What Was Tested

This run uses the exported cognitive-session fixture. It checks whether each
system can retrieve the visible memory, find the hidden influence, expose why a
trace won, keep suppressed alternatives visible, predict a continuation, and
keep reinforcement isolated after the report.

This is not a hosted benchmark claim. The hosted/official probe checks whether
Graphiti/Zep Neo4j/OpenAI mode, Mem0 official configuration, and a live Letta
endpoint are available in the current environment. Missing configuration is
recorded as `not_configured`, not as a competitor failure.

## Measured Setup

| System | Mode | Status |
| --- | --- | --- |
| King Synapse | Local in-memory store with the exported cognitive fixture | measured |
| Graphiti/Zep | `graphiti-core 0.29.2` with local Kuzu, deterministic embeddings, and explicit fixture triplets | measured |
| Mem0 | `mem0ai 2.0.11` OSS SDK with DeepSeek, deterministic local embedder, and local Qdrant | measured |
| Letta | `letta-client 1.12.1` adapter installed, but no endpoint configured | not configured |

Secrets are not stored in the report. The Mem0 run required
`DEEPSEEK_API_KEY`; the report records only the required environment variable
name, not the value.

## Hosted / Official Configuration Probe

The hosted probe forced Graphiti/Zep onto the Neo4j/OpenAI path, disabled the
Mem0 DeepSeek fallback so Mem0 would require an OpenAI/custom official
configuration, and checked Letta for a real endpoint. Result:

| System | Hosted / official mode | Status | Missing configuration |
| --- | --- | --- | --- |
| King Synapse | Local baseline on the same fixture | measured | none |
| Graphiti/Zep | Neo4j/OpenAI path | not configured | `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` |
| Mem0 | OSS SDK with OpenAI/custom config, no DeepSeek fallback | not configured | `OPENAI_API_KEY` or `MEM0_CONFIG_JSON` / `MEM0_CONFIG_PATH` |
| Letta | Hosted or local endpoint through `letta-client` | not configured | `LETTA_API_KEY`, `LETTA_BASE_URL`, or `LETTA_ENVIRONMENT=local` |

The probe wrote `crates/eval/reports/external-comparison-hosted.json`.
Summary: one measured system, three `not_configured` systems, zero failed
systems. No hosted competitor score is available yet.

The heavy LongMemEval / DMR validation path remains GPU-first. This external
fixture run is small and mostly adapter/API bound, so no CPU long-horizon
evaluation was started here.

## Result

| System | Visible memory | Hidden influence | Dominant trace | Suppressed alternatives | Evidence path | Future continuation | Reinforcement isolation | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| King Synapse | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 4.51 ms |
| Graphiti/Zep local | 8/8 | 8/8 | unsupported | unsupported | 8/8 | unsupported | unsupported | 136.55 ms |
| Mem0 OSS | 7/8 | 8/8 | unsupported | unsupported | unsupported | unsupported | unsupported | 2995.50 ms |
| Letta SDK | not configured | not configured | not configured | not configured | not configured | not configured | not configured | 0.00 ms |

## Read

King Synapse is the only measured system in this fixture that exposes the full
cognitive trace: visible seed, hidden influence, dominant candidate, suppressed
alternatives, evidence path, future continuation, and post-report
reinforcement isolation.

Graphiti/Zep local mode is strong at graph-style retrieval and evidence paths,
but this adapter does not expose King Synapse-style dominant/suppressed trace
competition, prediction, or reinforcement isolation.

Mem0 retrieved the hidden influence in every chain and the visible memory in
seven of eight chains. Through the measured OSS adapter, it does not expose
path evidence, trace competition, prediction, or reinforcement isolation.

Letta is not judged yet. The SDK is installed, but a hosted or local endpoint
must be configured before it can be measured.

The hosted/official probe confirms that the remaining external comparison gap
is environmental, not a current adapter crash: hosted Graphiti/Zep, official
Mem0, and Letta all require credentials or endpoints that are not present in
this environment.

## Current Conclusion

This external validation supports the project thesis in a narrow, honest way:
King Synapse currently exposes more inspectable cognitive-trace structure than
the measured competitor adapters on the same fixture.

It does not prove that King Synapse is better at every long-memory task. The
next validation boundary is still DMR judge scoring, DMR mapping/ranking, plus
a real Letta endpoint and hosted-mode reruns for Graphiti/Zep and Mem0 when
those environments are available.

## Reproduction Command

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

Hosted/official configuration probe:

```powershell
$env:GRAPHITI_BACKEND = 'neo4j'
$env:DEEPSEEK_API_KEY = ''
$env:MEM0_CONFIG_JSON = ''
$env:MEM0_CONFIG_PATH = ''
$env:OPENAI_API_KEY = ''
$env:LETTA_API_KEY = ''
$env:LETTA_BASE_URL = ''
$env:LETTA_ENVIRONMENT = ''
cargo run -p synapse-eval --bin kr-external-eval -- --systems all --graphiti-command python --graphiti-arg scripts/eval/graphiti_adapter.py --mem0-command python --mem0-arg scripts/eval/mem0_adapter.py --letta-command python --letta-arg scripts/eval/letta_adapter.py --json crates/eval/reports/external-comparison-hosted.json
```
