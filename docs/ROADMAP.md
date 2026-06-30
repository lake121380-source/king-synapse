# Roadmap

| Phase | Weeks | Goal | Verification |
|---|---|---|---|
| 0 | 1-2 | Rust daemon + SQLite + FTS5 + MCP + CLI. Self-host on opencode. | Can persist and recall across sessions. |
| 1 | 3-5 | 5-kind extractors v1, scope resolver, append-only event log fully wired, entity graph in plain SQLite tables (Kuzu dropped). | Memories auto-typed when written by extractor; entities link memories. |
| 2 | 6-7 | Vector embedder (multilingual-e5-base via fastembed), hybrid BM25+dense+RRF, cross-encoder reranker (bge-reranker-base), spreading activation 3 hops, eval harness with golden set. | `kr-eval` bench passes baseline targets. |
| 3 | 8-9 | Memory evolution: working-memory buffer, consolidator, Hebbian edges with feedback, reflection-as-event, decay tuning. | Repeated bug-fix attempts in eval drop measurably. |
| 4 | 10-12 | Three-tier causal-edge model (explicit / LLM-proposed-with-approval / co-occurrence stats). Approval UI flow. | Users can see and approve every `CAUSED` edge. |
| 5 | 13-15 | Tauri desktop UI: timeline, graph viewer, provenance, redact, conflict resolver. | Non-CLI users can manage memory end-to-end. |
| 6 | 16-18 | Claude Code hook integration + `cr-sqlite` multi-device sync. | Two machines stay consistent. |
| 7+ | — | Nightly consolidator, insights, team scopes (commercial). | — |

## Phase 2 substeps

| Step | Status | Verification |
|---|---|---|
| 1. sqlite-vec wiring + embedding_state schema | done (5c88ac6) | Schema migrates cleanly. |
| 2. Reserve Embedder error variant | done (1caa5bd) | Variant compiles. |
| 3. Embedder (fastembed E5) + embed-backfill CLI | done (3e77d3b) | vec0 round-trip tests pass. |
| 4. RecallEngine + RRF 3-branch fusion + Store slimdown | done (1ca25c6) | RRF unit + integration tests pass. |
| 5. Reranker trait + FastEmbedReranker + eval harness + 30-query golden set | this commit | `kr-eval --tag baseline-rrf` → Recall@10 0.950, MRR 0.950 on RRF-only. |
| 5.5 | next | `RecallHit` field expansion finalized; `kr recall --explain` shows per-branch ranks. |
| 6 | pending | Spreading activation 3 hops (alpha=0.6, priming). Activation bonus fills `RecallHit::activation_bonus`. bench Recall@10 ≥ baseline + MRR up. |
| 6.5 | pending | Golden set grown to 100-300 queries; nightly CI runs bench. |

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
