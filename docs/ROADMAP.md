# Roadmap

| Phase | Weeks | Goal | Verification |
|---|---|---|---|
| 0 | 1-2 | Rust daemon + SQLite + FTS5 + MCP + CLI. Self-host on opencode. | Can persist and recall across sessions. |
| 1 | 3-5 | 5-kind extractors v1, scope resolver, append-only event log fully wired, Kuzu graph layer for entities and `MENTIONS` edges. | Memories auto-typed when written by extractor; entities link memories. |
| 2 | 6-7 | Vector embedder (`jina-v3` via llama.cpp), hybrid BM25+dense+RRF, `bge-reranker-v2-m3`, spreading-activation engine (3 hops, alpha=0.6, priming, scope weight). | `coding-mem-eval` suite passes baseline targets. |
| 3 | 8-9 | Frustration-signal detector and `FrustrationSignal` node type. Failure-extractor expedited path. | Repeated bug-fix attempts in eval drop measurably. |
| 4 | 10-12 | Three-tier causal-edge model (explicit / LLM-proposed-with-approval / co-occurrence stats). Approval UI flow. | Users can see and approve every `CAUSED` edge. |
| 5 | 13-15 | Tauri desktop UI: timeline, graph viewer, provenance, redact, conflict resolver. | Non-CLI users can manage memory end-to-end. |
| 6 | 16-18 | Claude Code hook integration + `cr-sqlite` multi-device sync. | Two machines stay consistent. |
| 7+ | — | Nightly consolidator, insights, team scopes (commercial). | — |

## Architecture sketch

```
Agent (opencode / Claude Code / Cursor)
  |  MCP stdio
  v
king-synapse daemon
  |-- Capture -> Extractors -> Graph Writer
  |-- Query   -> Entity Recognizer -> Spreading Activation
  |                                -> Vector Fallback -> Reranker -> Inject
  v
Storage: SQLite (FTS5 + sqlite-vec) + Kuzu (graph) + append-only event log
```
