# King Synapse

> A persistently activated, decaying, reinforcing **associative memory network** for coding agents — so they stop repeating the same mistakes, stop re-learning your preferences, and stop forgetting where you left off.

**Status:**

- **Architecture:** ✅ Stable — frozen at `v0.5.0-architecture-freeze`. See `docs/API_SURFACE.md` and `docs/COMPATIBILITY.md`.
- **Adaptive Common Model:** ✅ Frozen — `v0.5.9-adaptive-common-freeze`. Importance, Event, Context, and Benchmark contracts are read-only. See `docs/rfcs/RFC-011-adaptive-memory-common-model.md`.
- **Algorithm:** 🚧 In Progress — RFC-012 Reflection has a v0.6.6 rule-based main path; freeze review and broader cognitive-memory behavior are next.

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
- `RecallEngine`: fuses FTS, entity, and optional vector branches with RRF; supports optional fastembed query embeddings, cross-encoder reranking, explain output, additive recall boosters including graph/latent activation, and cognitive probes for inspecting hidden multi-step influence.
- Working memory and adaptive memory: frozen public traits for activation, consolidation, reflection processing, Hebbian execution, store integration, adaptive policies, and the RFC-011 Adaptive Common Model, plus rule-based Phase 5 algorithms for reflection, merge, forget, and Hebbian reinforcement.
- `synapse-eval`: benchmark harness and frozen datasets for recall baselines, including `reference`, `multihop`, reflection yield, merge/forget precision, Hebbian consistency, cognitive-chain recall, cognitive-trace dominance, and trace reinforcement.
- `synapse-mcp`: a stdio MCP server exposing write, recall, recent-list, forget, entity-list, neighbor, edge-inspection, Hebbian reinforcement, latent-activation, and cognitive-trace tools, including optional post-recall and post-trace reinforcement.
- `kr`: a CLI for writing, recalling, inspecting, invalidating, embedding backfill, and stats.

Still on the roadmap:

- Freeze-review RFC-012 Reflection's rule-based heuristic against its deterministic baseline.
- Freeze-review RFC-013/RFC-014/RFC-015 now that merge, forget, Hebbian reinforcement, latent inspection, cognitive trace, and trace learning all have deterministic baselines.
- External benchmark comparisons, larger parameter sweeps, and long-horizon memory trials.
- UI, deeper agent integrations, and final release/tag evidence.

See `docs/ROADMAP.md`, `docs/ADAPTIVE_MEMORY.md`, `docs/API_SURFACE.md`, `docs/COMPATIBILITY.md`, and `docs/COGNITIVE_MEMORY_FINAL_ACCEPTANCE.md` for the current roadmap, adaptive memory architecture, public API list, stability policy, and final cognitive-memory acceptance gates. Release notes: `RELEASE-v0.2.0.md`, `docs/releases/v0.3.9-memory-evolution-freeze.md`, `docs/releases/v0.4.9-adaptive-memory-foundation.md`, `docs/releases/v0.4.19-reflection-processing-freeze.md`, `docs/releases/v0.4.29-hebbian-execution-freeze.md`, `docs/releases/v0.4.39-store-integration-freeze.md`, `docs/releases/v0.4.49-adaptive-policies-freeze.md`, and `docs/releases/v0.5.0-architecture-freeze.md`.

For the broader "King Recall v3 / AI Cognitive Memory Engine" proposal and
how it maps onto the current RFC-driven implementation plan, see
`docs/V3_PROPOSAL_REVIEW.md`.

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
./target/release/kr recall "pnpm windows" --graph-activation --graph-steps 2 --explain
./target/release/kr recall "forgot water commute attention" --latent-activation --latent-auto-context --explain
./target/release/kr recall "forgot water commute attention" --reinforce --reinforce-k 3
./target/release/kr edges <memory-id> --direction both
./target/release/kr reinforce <memory-id-a> <memory-id-b> --event recalled --query "forgot water commute"
./target/release/kr latent <memory-id> --steps 2 --state tired --goal commute
./target/release/kr latent-query "forgot water before commute while tired" --auto-context
./target/release/kr trace "forgot water before commute while tired" --auto-context
./target/release/kr trace "forgot water before commute while tired" --auto-context --reinforce --reinforce-k 3

# List recent
./target/release/kr list --limit 10

# See where the DB lives
./target/release/kr where

# Run the RFC-012 Reflection benchmark
cargo bench -p synapse-eval --bench reflection_yield
cargo bench -p synapse-eval --bench trace_reinforcement
cargo bench -p synapse-eval --bench activation_parameter_sweep
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

The agent then has `synapse_write`, `synapse_recall`, `synapse_list_recent`, `synapse_forget`, `synapse_entities`, `synapse_neighbors`, `synapse_edges`, `synapse_reinforce`, `synapse_latent_activation`, `synapse_latent_query`, and `synapse_trace` available as tools.

## License

Apache-2.0.
