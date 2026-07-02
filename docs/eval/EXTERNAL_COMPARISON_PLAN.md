# External Memory Comparison Plan

Status: Draft, post-freeze evaluation

Date: 2026-07-02

Implementation status:

- First runnable harness: `cargo run -p synapse-eval --bin kr-external-eval -- --json crates/eval/reports/external-comparison-latest.json`
- First Graphiti adapter command: `python scripts/eval/graphiti_adapter.py`
- First Mem0 adapter command: `python scripts/eval/mem0_adapter.py`
- First Letta adapter command: `python scripts/eval/letta_adapter.py`
- First report: `crates/eval/reports/external-comparison-latest.json`
- Current local result: King Synapse is measured against the exported cognitive
  fixture. Graphiti/Zep is measured locally through `graphiti-core` with the
  Kuzu graph driver, deterministic local embeddings, and explicit fixture
  triplet import when `graphiti-core` and `kuzu` are installed. Full
  Neo4j/OpenAI extraction mode still requires `OPENAI_API_KEY`, `NEO4J_URI`,
  `NEO4J_USER`, and `NEO4J_PASSWORD`. Mem0 is wired into the same harness
  through the OSS Python SDK adapter; without `mem0ai` and either
  `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, or a custom `MEM0_CONFIG_JSON` /
  `MEM0_CONFIG_PATH`, it is reported as `not_configured`. If
  `DEEPSEEK_API_KEY` is present, the adapter generates a DeepSeek +
  HuggingFace + local Qdrant config automatically. Letta is wired through its
  official Python SDK adapter; without `letta-client` plus `LETTA_API_KEY`,
  `LETTA_BASE_URL`, or `LETTA_ENVIRONMENT=local`, it is reported as
  `not_configured`.

## Purpose

This document starts the external comparison phase for King Synapse after the
`v0.9.26-cognitive-memory-freeze` release. External comparison is deliberately
post-freeze work by ADR-007. It must not weaken the final release evidence, and
it must not turn source-reported product claims into locally measured results.

The goal is to compare King Synapse with Graphiti/Zep, Letta, Mem0, DMR, and
LongMemEval using one shared evaluation frame:

1. standard long-term memory behavior;
2. cognitive-trace behavior, which is the project-specific claim.

The cognitive-trace layer is the important differentiator. King Synapse should
not be evaluated only as "can it remember a fact?" The stronger question is
"can it explain why one hidden influence became dominant while other possible
influences stayed suppressed?"

## Source Notes

These sources were checked before creating this plan:

| System or benchmark | Source | Notes used for this plan |
| --- | --- | --- |
| Graphiti | <https://help.getzep.com/graphiti/getting-started/overview> | Graphiti builds and queries temporal context graphs with entities, relationships, facts, episodes, and hybrid search. |
| Graphiti repository | <https://github.com/getzep/graphiti> | Graphiti is described as an open-source temporal context graph engine with provenance, temporal fact management, and hybrid retrieval. |
| Zep paper | <https://arxiv.org/html/2501.13956> | Zep reports DMR and LongMemEval results using Graphiti-backed temporal knowledge graphs. Treat those as source-reported until reproduced locally. |
| Letta docs | <https://docs.letta.com/guides/core-concepts/stateful-agents/> | Letta persists agent state, memory blocks, messages, reasoning, tool calls, and lets agents modify memories through tools. |
| Letta repository | <https://github.com/letta-ai/letta> | Letta is positioned as a platform for stateful agents with advanced memory and self-improvement. |
| Mem0 docs | <https://docs.mem0.ai/introduction> | Mem0 is positioned as a universal self-improving memory layer for LLM applications. |
| Mem0 memory types | <https://docs.mem0.ai/core-concepts/memory-types> | Mem0 separates conversation, session, user, and organizational memory layers and merges them during retrieval. |
| Mem0 repository | <https://github.com/mem0ai/mem0> | Mem0 reports a newer memory algorithm with multi-signal retrieval and benchmark claims. Treat those as source-reported until reproduced locally. |
| LongMemEval | <https://arxiv.org/abs/2410.10813> | LongMemEval evaluates information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention. |

## Internal Baseline

The canonical internal fixture is:

- `crates/eval/datasets/exported_cognitive_session.toml`
- `exported_cognitive_session_report()`
- `cargo bench -p synapse-eval --bench exported_cognitive_session`

That fixture already encodes the user's design model:

- visible situation;
- hidden influence;
- distractors;
- state terms such as tired, anxious, hungry, subconscious, memory, and future;
- goal terms such as commute, attention, risk, review, communication, and
  decision;
- predicted next influence.

The external comparison must preserve that shape. Adapters may translate it
into each target system's API, but they must not remove the hidden-influence
or suppressed-candidate requirements.

## Evaluation Layers

### Layer 1: Long-Term Memory

These checks make King Synapse comparable with common memory systems:

| Dimension | Measurement question |
| --- | --- |
| Write or import model | Can the system ingest ordered episodes without manual answer injection? |
| Retrieval accuracy | Does the expected memory appear in the ranked context? |
| Multi-session reasoning | Can the answer require information from more than one session? |
| Temporal reasoning | Can the system choose the right dated or current fact? |
| Knowledge update handling | Can the system handle changed facts without losing history? |
| Abstention | Can the system avoid inventing unsupported memories? |
| Context cost | How much context is sent to the answering model? |
| Latency | How long does retrieval plus answer assembly take under a fixed setup? |
| Reproducibility | Can the run be reset, repeated, and inspected from stored artifacts? |

### Layer 2: Cognitive Trace

These checks are specific to the cognitive-memory thesis:

| Dimension | Measurement question |
| --- | --- |
| Visible seed recall | Does ordinary recall find the visible situation from the query? |
| Hidden activation | Does the visible seed activate the expected hidden influence? |
| State and goal modulation | Do body state, emotion, social pressure, goals, and future risk affect ranking without hiding evidence? |
| Dominant candidate | Does one hidden influence become the dominant trace candidate? |
| Suppressed alternatives | Are non-dominant candidates still visible for inspection? |
| Evidence path | Can the report explain the seed -> edge -> hidden influence path? |
| Predictive continuation | Can the dominant hidden influence continue into a likely next influence? |
| Post-report reinforcement | Can explicit reinforcement strengthen future activation only after the current report is computed? |
| Store boundary | Does persistence stay query-agnostic, with retrieval and trace logic outside storage? |

If a competitor cannot expose one of these surfaces, record `not supported`
instead of forcing an unfair proxy.

## Initial Source-Based Comparison

This table is not a benchmark result. It is a source-based feature map for the
first adapter design.

| System | Natural strength from sources | What must be measured locally | Current risk or unknown |
| --- | --- | --- | --- |
| King Synapse | Inspectable visible recall, latent activation, dominant/suppressed cognitive traces, predictive continuation, and post-report reinforcement through local benchmarks. | External adapters must run the same fixture against competitors and compare raw evidence. | Existing evidence is internal; no competitor adapter has run yet. |
| Graphiti/Zep | Temporal context graph, episodes, provenance, fact invalidation, hybrid semantic/full-text/graph retrieval, and source-reported DMR/LongMemEval results. | Whether its graph search can expose hidden influence competition, suppressed alternatives, and path evidence in the cognitive fixture. | Requires graph backend and LLM extraction; Zep/Graphiti numbers are source-reported until reproduced. |
| Letta | Stateful agents with persisted memory blocks, messages, reasoning, tool calls, and agent-editable memory. | Whether memory blocks and retrieval tools can be adapted to deterministic fixture scoring without agent-loop variability dominating the result. | Strong agent-state surface, but explicit trace dominance and suppressed-candidate reporting are not established by the checked sources. |
| Mem0 | Layered memory model, persistent personalization, multi-signal retrieval, temporal retrieval claims, and source-reported benchmark improvements. | Whether its memory layers can return evidence paths, hidden influence rank, and continuation support for the cognitive fixture. | Hosted/open-source/version behavior must be pinned; source-reported benchmark numbers are not local measurements. |
| LongMemEval | Public long-memory benchmark covering extraction, multi-session reasoning, temporal reasoning, updates, and abstention. | Import path, license-compatible dataset mirror, answer judge, and report format. | It tests long memory broadly, not cognitive trace dominance directly. |
| DMR | Older deep-memory retrieval sanity benchmark used by MemGPT/Zep literature. | Import path and fact-retrieval baseline. | Useful as a sanity check, but too fact-retrieval-oriented to validate the cognitive thesis alone. |

## Adapter-Neutral Protocol

Every external adapter should expose the same logical operations, even if a
target system has to approximate some of them:

| Operation | Required behavior |
| --- | --- |
| `reset_subject` | Create a fresh user, subject, collection, graph, agent, or database namespace for the run. |
| `ingest_episode` | Store one ordered episode with text, timestamp, subject id, and optional metadata. |
| `query_context` | Return ranked context for a natural-language query without being shown the expected answer. |
| `query_trace` | Return any available graph path, memory block evidence, edge, or explanation for why the ranked context was selected. |
| `predict_continuation` | Return a ranked next influence if the target system supports continuation. |
| `reinforce` | Strengthen a selected association only if the target system supports explicit learning. |
| `export_raw` | Persist raw request, response, ranked memories, evidence, timing, and model/provider configuration. |

Adapter outputs must separate:

- locally measured values;
- source-reported values;
- unsupported values;
- failed values.

## Cognitive Fixture Mapping

For each chain in `exported_cognitive_session.toml`, create an external run
with the following shape:

1. Ingest the visible seed, visible distractor, hidden influence, hidden
   distractor, future influence, and future distractor as ordered episodes.
2. Query only with the fixture query text.
3. Score whether the visible seed is found.
4. Score whether the expected hidden influence is ranked above hidden
   distractors or otherwise selected as the strongest evidence.
5. Record every available evidence path or explanation.
6. Ask for continuation from the dominant hidden influence only if the target
   supports that operation.
7. Run explicit reinforcement only after the current report has been captured.
8. Re-query and score whether future activation changes without rewriting the
   previous report.

Suggested per-chain metrics:

| Metric | Definition |
| --- | --- |
| `visible_seed_found` | Expected visible seed appears in retrieved context. |
| `hidden_influence_found` | Expected hidden influence appears in retrieved or trace evidence. |
| `hidden_influence_dominant` | Expected hidden influence ranks above hidden distractors. |
| `suppressed_alternatives_visible` | At least one non-dominant candidate is inspectable. |
| `evidence_path_available` | The system exposes why the hidden influence was selected. |
| `future_continuation_found` | Expected future influence appears after continuation. |
| `reinforcement_isolated` | Learning happens after the report and does not mutate current-report ranking. |

Do not add these metrics to the frozen `BenchmarkReport` contract until an RFC
or ADR approves the additive metric surface. The first runs can live in an
external report format under `crates/eval/reports/`.

The first external report format now lives behind the `kr-external-eval`
binary. It records runtime metadata, raw evidence, unsupported capabilities,
adapter failures, and source/local-result separation outside the deterministic
`BenchmarkReport` value object.

To run the current local comparison:

```bash
cargo run -p synapse-eval --bin kr-external-eval -- --json crates/eval/reports/external-comparison-latest.json
```

To connect the included Graphiti adapter, pass Python as the command and the
adapter script as an argument:

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

Each adapter receives one final argument from the harness: an input JSON path
containing the exported cognitive fixture. It must print one
`ExternalSystemRun` JSON object to stdout.

The adapter has two modes. With `GRAPHITI_BACKEND=neo4j`, it uses the normal
Graphiti/Neo4j path and requires OpenAI plus Neo4j configuration. Without those
credentials, if `graphiti-core` and `kuzu` are installed, it automatically uses
`GRAPHITI_BACKEND=kuzu`: a local deterministic Graphiti Kuzu path that measures
graph storage/search over fixture triplets. This Kuzu mode does not claim LLM
extraction, dominant/suppressed trace competition, prediction, or reinforcement
support; those capabilities are reported as `unsupported`.

The Mem0 adapter uses the OSS Python SDK's `Memory.add` and `Memory.search`
paths when configured. It can run with OpenAI defaults, a custom
`MEM0_CONFIG_JSON` / `MEM0_CONFIG_PATH`, or `DEEPSEEK_API_KEY` plus an
automatically generated HuggingFace embedder and local Qdrant vector store. It
uses a fresh `user_id` namespace per chain, measures visible and hidden
retrieval if Mem0 returns them, and reports path evidence, dominant/suppressed
trace competition, prediction, and reinforcement as `unsupported` unless Mem0
exposes those semantics through the SDK.

The Letta adapter uses the official Python SDK to create an agent with a fresh
memory block per chain, then reads the block back through the API. This measures
stateful memory-block persistence/inspection, not graph retrieval. Because
Letta memory blocks are always-visible agent context rather than path-bearing
trace graphs, evidence paths, dominant/suppressed trace competition,
prediction, and reinforcement are reported as `unsupported` unless exposed by
the configured SDK/API.

## LongMemEval And DMR Plan

LongMemEval should be the first external dataset because its categories align
with memory beyond isolated fact lookup:

- information extraction;
- multi-session reasoning;
- temporal reasoning;
- knowledge updates;
- abstention.

DMR should be used as a smaller sanity check after LongMemEval scaffolding is
clear. DMR can show whether a system can recover facts, but it should not be
treated as sufficient evidence for the cognitive-memory model.

Dataset mirrors belong under the reserved paths documented in
`crates/eval/README.md`:

- `crates/eval/datasets/longmemeval/`
- `crates/eval/datasets/dmr/`

Only mirror external datasets when their license and redistribution terms allow
it. Otherwise, store fetch instructions and local-cache checksums instead.

## Acceptance Gates For First Real Comparison

The first real external comparison run is accepted only when all gates pass:

1. The current King Synapse internal baseline still passes:
   `cargo bench -p synapse-eval --bench exported_cognitive_session`.
2. No default user memory database or production account is mutated.
3. Every external adapter uses a fresh disposable subject, namespace, or graph.
4. Source URLs, package versions, model names, prompts, and timestamps are
   captured in an external run manifest.
5. Raw retrieved memories, evidence, and answer text are stored for inspection.
6. Unsupported competitor features are marked `not supported`, not scored as
   silent failures.
7. Source-reported numbers are clearly separated from locally measured numbers.
8. The report includes at least one competitor adapter run before making
   comparative performance claims.

## Immediate Next Work

1. Build the Graphiti local adapter first, because its temporal graph model is
   the closest external shape to King Synapse edges and paths.
2. Build a Mem0 adapter second, because its API is simpler and its layered
   memory model is useful for comparison against user/session/organization
   memory.
3. Build a Letta adapter third, with special care to separate memory-system
   behavior from autonomous agent-loop behavior.
4. Import or script-fetch LongMemEval only after adapter reset and evidence
   export are stable.

The external comparison should begin with humility: King Synapse has strong
internal evidence for the cognitive-trace thesis, while the external systems
have broader ecosystem maturity and published benchmark claims. The right next
step is not to declare a winner. It is to make the comparison repeatable enough
that a winner, a weakness, or a genuinely new idea can be seen without guessing.
