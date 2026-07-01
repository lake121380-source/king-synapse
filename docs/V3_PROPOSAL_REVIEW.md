# King Recall v3 Proposal Review

Status: **Engineering Review**

This note reviews the pasted "King Recall v3 / AI Cognitive Memory Engine"
proposal against the current King Synapse repository.

## Verdict

The proposal is directionally strong, but it is **not complete enough as a
development specification**.

It works well as a vision document: it names the product category, explains why
plain vector memory is insufficient, and describes the long-term cognitive
memory shape. It does not yet define enough concrete contracts, data models,
quality gates, and migration boundaries for engineers to implement directly.

The current repository already has the missing engineering machinery:

- frozen public API surface in `docs/API_SURFACE.md`;
- compatibility rules in `docs/COMPATIBILITY.md`;
- recall contract in `docs/RECALL_PIPELINE.md`;
- working/adaptive-memory contracts in `docs/WORKING_MEMORY.md` and
  `docs/ADAPTIVE_MEMORY.md`;
- algorithm implementation rules in `docs/ALGORITHM_GUIDELINES.md`;
- RFC-011 shared algorithm model and RFC-012 Reflection Algorithm.

Therefore, the v3 proposal should be treated as a **vision layer**, not as the
authoritative implementation plan. The authoritative development plan remains
the RFC + ADR + benchmark system already in the repository.

## Coverage Assessment

| Area | Proposal coverage | Engineering gap |
| --- | --- | --- |
| Vision | Strong | Needs version alignment with current `v0.5.x` / Phase 5 language. |
| Scope | Good | Must explicitly preserve non-goals: no Chat UI, no agent framework, no LLM orchestration. |
| Architecture | Good high-level shape | Needs exact module boundaries and frozen API constraints. |
| Graph | Aspirational | Needs a concrete schema, persistence model, and migration policy before implementation. |
| Memory lifecycle | Good conceptually | Current lifecycle must flow through existing Plan -> Execute -> Report -> Sink contracts. |
| Retrieval | Good direction | Must preserve frozen RecallHit, RecallEngine, RRF, rerank, and booster invariants. |
| Reflection | Good milestone | Needs deterministic algorithm, benchmark, and store-integration mapping. |
| Predictive recall | Future-facing | Should wait until Reflection/Merge/Forget/Hebbian have measurable baselines. |
| Storage | Names SQLite, sqlite-vec, Kuzu | Needs explicit owner boundaries: Store remains durable persistence boundary. |
| API | Mentions MCP | Needs exact tool schemas and compatibility policy. |
| Testing | Missing | Needs tests, clippy, frozen recall baselines, and algorithm benchmarks. |
| Release process | Missing | Needs ADRs, RFC status updates, release notes, and tags. |

## Current Engineering Translation

The proposal's v3 capability list maps to the current repository like this:

| v3 concept | Current implementation / contract |
| --- | --- |
| Associative Memory | FTS + entity branch + vector branch + working-memory activation; SQLite edge persistence now exists for adaptive associations. |
| Dynamic Edge | Hebbian contracts and StoreMutation-backed SQLite edge persistence exist; recall-time graph use still needs a measured integration milestone. |
| Working Memory | Implemented as `WorkingMemoryBuffer` and `WorkingMemoryActivationBooster`. |
| Long-term Memory | Implemented through SQLite-backed `Store`. |
| Explainable Recall | Implemented through `RecallHit` provenance fields and `--explain`. |
| Reflection | RFC-012 skeleton, NoOp, deterministic reference; benchmark milestone is next. |
| Forgetting | Policy and store-integration contracts exist; concrete algorithm is planned. |
| Predictive Recall | Not yet implemented; should be gated behind benchmarks and ADRs. |

## Required Additions Before Treating v3 As A Dev Spec

Before the v3 proposal can become a direct implementation document, it needs:

1. A compatibility section that says which stable APIs may not change.
2. A graph schema RFC with node types, edge types, weights, decay, constraints,
   and migration rules.
3. A lifecycle RFC that maps capture, consolidation, archive, and forget to
   existing execution/report/sink contracts.
4. A retrieval RFC update only if new behavior cannot fit behind the existing
   RecallBooster or retriever boundaries.
5. MCP tool schemas with stable input/output examples.
6. Benchmark definitions for every algorithm claim.
7. Quality gates: `cargo test`, clippy, `reference` Recall@10, `multihop`
   Recall@10, and algorithm-specific `BenchmarkReport` output.
8. A release/tag process for each milestone.

## Near-Term Development Decision

Do **not** start by rewriting the workspace into the proposed v3 directory tree.
That would break the current frozen architecture without delivering user-visible
intelligence.

Instead, continue Phase 5:

```text
RFC-012 Reflection Algorithm
  -> deterministic reference
  -> reflection-yield benchmark
  -> mapping into existing Reflection Processing reports
  -> conservative StoreMutation integration
```

This route advances the v3 goal of a cognitive memory engine while preserving
the stable foundation already built.

## Immediate Next Milestone

Implement `v0.6.3-reflection-benchmark`:

- add a deterministic `reflection-yield` benchmark under
  `crates/eval/benches/algorithms/`;
- emit `BenchmarkReport { benchmark: "reflection-yield", ... }`;
- map the metric to `AlgorithmMetric::ReflectionYield`;
- use only public APIs;
- preserve frozen recall baselines:
  - `reference` Recall@10 = `1.000`;
  - `multihop` Recall@10 = `0.600`.

After this milestone, the project can compare future Reflection algorithms
against a known deterministic reference instead of arguing from architecture
alone.

Next milestone after the benchmark:

```text
v0.6.4-reflection-processing-adapter
  ReflectionOutput -> ReflectionEvent -> ReflectionReport

v0.6.5-reflection-store-mutation-plan
  ReflectionPlan -> StoreMutationPlan

v0.6.6-rule-based-reflection
  Deterministic reference -> production-like heuristic
```

This keeps the algorithm side-effect free while proving that concrete
reflection results can enter the existing processing and store-mutation
planning pipelines. Durable SQLite edge writes now exist behind the Store
executor boundary; the next graph milestone is measured recall-time use of
those edges without changing frozen recall contracts.
