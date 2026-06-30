# King Synapse

> A persistently activated, decaying, reinforcing **associative memory network** for coding agents — so they stop repeating the same mistakes, stop re-learning your preferences, and stop forgetting where you left off.

**Status:** Phase 0 — early development. Single-binary daemon, SQLite-backed, MCP-compatible.

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

## What's in Phase 0

- `synapse-core`: SQLite + FTS5 storage, append-only event log, time-decay scoring.
- `synapse-mcp`: A stdio MCP server exposing `synapse_write`, `synapse_recall`, `synapse_list_recent`, `synapse_forget`.
- `kr`: A CLI for the same operations.

What's **not yet** in Phase 0 (coming in later phases):
- Vector embeddings (Phase 2)
- Knowledge graph layer with Kuzu (Phase 1)
- Spreading activation engine (Phase 2)
- Failure / preference extractors (Phase 3)
- Causal edges with 3-tier confidence (Phase 4)
- Tauri UI (Phase 5)
- Claude Code integration + multi-device sync (Phase 6)

See `docs/ROADMAP.md` for the full plan.

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

The agent then has `synapse_write`, `synapse_recall`, `synapse_list_recent`, `synapse_forget` available as tools.

## License

Apache-2.0.
