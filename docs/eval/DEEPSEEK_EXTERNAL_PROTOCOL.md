# DeepSeek External Protocol

Date: 2026-07-04

Status: passed as a Phase 6 domestic/local design-validation lane

Machine-readable report:

`crates/eval/reports/deepseek-external-protocol-gate.json`

Runner:

`scripts/eval/deepseek_external_protocol_gate.py`

## Question

Can Phase 6 validate Synapse's external comparison lane without treating
OpenAI hosted parity as the only proof path?

Current answer:

`Yes.`

The DeepSeek-first protocol is separate from the OpenAI/Neo4j hosted reference
lane. It validates the project's own design claim: Synapse exposes cognitive
trace surfaces that standard memory adapters do not expose on the same fixture.

## Protocol Boundary

| System | Mode | Current state |
| --- | --- | --- |
| King Synapse | Current local cognitive-memory engine | Measured |
| Graphiti/Zep | Local Kuzu graph driver with deterministic embeddings | Measured |
| Mem0 | Mem0 OSS with DeepSeek v4 flash, deterministic local embedder, local Qdrant | Measured |
| Letta | Official SDK endpoint path | Not configured |

No API key values are recorded. Reports only record credential names or
environment-variable presence.

## Result

| Check | Result |
| --- | --- |
| Shared 8-chain cognitive fixture | Passed |
| Synapse design surfaces | 8/8 visible, hidden, dominant trace, suppressed alternatives, evidence path, future continuation, reinforcement isolation |
| Graphiti/Zep local retrieval/path evidence | Measured |
| Mem0 DeepSeek retrieval | Measured |
| Unsupported surfaces counted separately | Passed |
| OpenAI hosted reference separated | Passed |
| Secrets recorded | No |

## Decision

The DeepSeek-first external validation lane is accepted as a valid Phase 6
design-validation path.

This does **not** mean:

- OpenAI/Neo4j hosted Graphiti/Zep has been measured;
- official OpenAI-style Mem0 has been measured;
- live Letta has been measured;
- hosted official competitor superiority can be claimed;
- productization may start.

It means:

- OpenAI is not a hard blocker for proving Synapse's own design thesis;
- DeepSeek can be the primary domestic model lane;
- hosted official parity remains a reference lane, not the only evidence lane;
- the next useful work is DMR failure-mode analysis or optional DeepSeek replay.
