# King Synapse

> A persistently activated, decaying, reinforcing **associative memory network** for coding agents — so they stop repeating the same mistakes, stop re-learning your preferences, and stop forgetting where you left off.

**Status:**

- **Architecture:** ✅ Stable — frozen at `v0.5.0-architecture-freeze`. See `docs/API_SURFACE.md` and `docs/COMPATIBILITY.md`.
- **Adaptive Common Model:** ✅ Frozen — `v0.5.9-adaptive-common-freeze`. Importance, Event, Context, and Benchmark contracts are read-only. See `docs/rfcs/RFC-011-adaptive-memory-common-model.md`.
- **Algorithm:** 🚧 In Progress — RFC-012 Reflection Algorithm is next.

Phase 1–4 freeze tags: `v0.2.0-recall-api-freeze`, `v0.3.9-memory-evolution-freeze`, `v0.4.9-adaptive-memory-foundation`, `v0.4.19-reflection-processing-freeze`, `v0.4.29-hebbian-execution-freeze`, `v0.4.39-store-integration-freeze`, `v0.4.49-adaptive-policies-freeze`.

## Why

The biggest unsolved problem in coding agents isn't reasoning — it's **memory**. Every other tool today either:

- forgets between sessions (Cursor, default Claude Code),
- stores flat text only the human can author (CLAUDE.md, `.cursor/rules`), or
- treats memory as a black box (Mem0, Letta) that the user can't inspect, edit, or trust.

King Synapse takes a different bet: **memory is a network, not a database.** Memories are nodes; their relationships are weighted edges; recall is *spreading activation* across the network — not a vector search.

## Design tenets

1. **Append-only with bi-temporal stamps** — memories are never overwritten; old beliefs are superseded, not deleted. You can replay history.
2. **Provenance is a first-class column** — every memory knows whether the user said it, the agent guessed it, or an extractor inferred it.
3. **Scopes are explicit** — `global` / `user` / `project:<id>` / `file:<path>` / `session:<id>` — no more "is this preference mine, or this repo's?"
4. **Five kinds of memory**, each with its own decay rate and extractor:
   - `fact`     — stable repo/project facts
   - `preference` — what you like / hate (slowest decay)
   - `failure`  — what *didn't* work last time
   - `playbook` — how-we-fix-X patterns
   - `state`    — what you were working on (fastest decay)
5. **Local-first** — single SQLite file, no cloud calls on the hot path.
6. **Transparent** — every memory and every edge can be inspected, edited, redacted, or rolled back.

## What's implemented now

- `synapse-core`: SQLite + FTS5 storage, append-only event log, entity extraction, sqlite-vec embeddings, hybrid recall, time-decay scoring, and stable adaptive-memory contracts.
- `RecallEngine`: fuses FTS, entity, and optional vector branches with RRF; supports optional fastembed query embeddings, cross-encoder reranking, explain output, and additive recall boosters.
- Working memory and adaptive memory: frozen public traits for activation, consolidation, reflection processing, Hebbian execution, store integration, adaptive policies, and the RFC-011 Adaptive Common Model.
- `synapse-eval`: benchmark harness and frozen datasets for recall baselines, including `reference` and `multihop`.
- `synapse-mcp`: a stdio MCP server exposing write, recall, recent-list, forget, entity-list, and neighbor tools.
- `kr`: a CLI for writing, recalling, inspecting, invalidating, embedding backfill, and stats.

Still on the roadmap:

- Concrete Phase 5 algorithms behind the frozen traits, starting with RFC-012 Reflection Algorithm.
- Production-grade memory evolution behavior for merge, forget, and Hebbian reinforcement.
- External benchmark comparisons and larger parameter sweeps.
- UI and deeper agent integrations.

See `docs/ROADMAP.md`, `docs/ADAPTIVE_MEMORY.md`, `docs/API_SURFACE.md`, and `docs/COMPATIBILITY.md` for the current roadmap, adaptive memory architecture, public API list, and stability policy. Release notes: `RELEASE-v0.2.0.md`, `docs/releases/v0.3.9-memory-evolution-freeze.md`, `docs/releases/v0.4.9-adaptive-memory-foundation.md`, `docs/releases/v0.4.19-reflection-processing-freeze.md`, `docs/releases/v0.4.29-hebbian-execution-freeze.md`, `docs/releases/v0.4.39-store-integration-freeze.md`, `docs/releases/v0.4.49-adaptive-policies-freeze.md`, and `docs/releases/v0.5.0-architecture-freeze.md`.

## Build

Requires Rust 1.80+.

```bash
cargo build --release
```

Binaries land in `target/release/`:
- `kr.exe` (or `kr` on Unix) — the CLI
- `synapse-mcp.exe` — the MCP server

## Try it

```bash
# Write some memories
./target/release/kr write "本仓库测试用 pnpm test:ci" --kind fact --scope project:king-synapse
./target/release/kr write "用户讨厌在 catch 里吞错" --kind preference --scope user
./target/release/kr write "Windows 上 pnpm install 走代理会卡死，改用 corepack" --kind failure

# Recall
./target/release/kr recall "pnpm windows"
./target/release/kr recall "测试" --kind fact

# List recent
./target/release/kr list --limit 10

# See where the DB lives
./target/release/kr where
```

## Plug into opencode

Add to your `opencode.json`:

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

The agent then has `synapse_write`, `synapse_recall`, `synapse_list_recent`, `synapse_forget`, `synapse_entities`, and `synapse_neighbors` available as tools.

## License

Apache-2.0.
