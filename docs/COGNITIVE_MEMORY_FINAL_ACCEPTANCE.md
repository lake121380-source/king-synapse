# Cognitive Memory Final Acceptance

Status: **Living Acceptance Plan**

This document defines what must be true before King Synapse can be called a
complete cognitive memory system rather than an active Phase 5 implementation.
It is intentionally evidence-driven: every claim needs a source file, command,
benchmark, release note, or tag that proves it.

## Product Definition

The final system models memory as an inspectable associative network:

- visible recall finds seed memories from the current query;
- latent activation follows weighted edges to hidden influences;
- state and goal terms modulate hidden activation without hiding the evidence;
- cognitive trace reports the dominant candidate plus suppressed alternatives;
- predictive trace can continue from the dominant candidate to likely next
  hidden influences;
- explicit reinforcement can strengthen recalled or traced co-occurrence for
  future activation;
- lifecycle algorithms can reflect, merge, forget, and reinforce without
  changing the frozen recall contract.

The conceptual model is defined in `docs/COGNITIVE_NETWORK_MODEL.md`: a thought
is treated as a dominant candidate selected from a wider, state-modulated graph
of visible and hidden associations.

## Current Evidence

| Requirement | Evidence |
| --- | --- |
| Stable recall and adaptive-memory contracts | `docs/API_SURFACE.md`, `docs/COMPATIBILITY.md`, `docs/RECALL_PIPELINE.md`, `docs/ADAPTIVE_MEMORY.md` |
| Reflection rule-based main path | `reflection_yield_report()` and `docs/ROADMAP.md` v0.6.6 |
| Merge and forget deterministic baselines | `merge_precision_report()`, `forget_precision_report()` |
| Hebbian edge planning and persistence | `hebbian_consistency_report()`, `StoreMutation::UpdateEdge`, `SQLitePersistentStoreExecutor` |
| Recall-time spreading activation | `GraphActivationBooster`, `LatentActivationBooster` |
| Hidden influence inspection | `LatentActivationProbe`, `QueryLatentActivationProbe`, `cognitive_chain_recall_report()` |
| Dominant/suppressed cognitive trace | `CognitiveTraceProbe`, `cognitive_trace_dominance_report()` |
| Predictive trace continuation | `CognitiveTraceProbe::predict_continuation()`, `predictive_trace_report()` |
| Post-trace learning | `kr trace --reinforce`, `synapse_trace` with `reinforce: true`, `trace_reinforcement_report()` |
| Exported long-session validation | `crates/eval/datasets/exported_cognitive_session.toml`, `exported_cognitive_session_report()` |
| Cognitive-network design model | `docs/COGNITIVE_NETWORK_MODEL.md` |
| Manual surface validation | `docs/MANUAL_VALIDATION.md` |
| Release-candidate evidence | `docs/releases/v0.9.26-cognitive-memory-release-candidate.md` |

## Required Verification Gates

Before final release, run and record:

1. `cargo fmt --check`
2. `cargo check`
3. `cargo test`
4. `cargo clippy --all-targets --all-features -- -D warnings`
5. `cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/reference.toml --tag reference-baseline`
6. `cargo run -p synapse-eval --bin kr-eval -- --dataset crates/eval/datasets/multihop.toml --tag multihop-baseline`
7. `cargo bench -p synapse-eval --bench reflection_yield`
8. `cargo bench -p synapse-eval --bench merge_precision`
9. `cargo bench -p synapse-eval --bench forget_precision`
10. `cargo bench -p synapse-eval --bench hebbian_consistency`
11. `cargo bench -p synapse-eval --bench cognitive_chain_recall`
12. `cargo bench -p synapse-eval --bench cognitive_trace_dominance`
13. `cargo bench -p synapse-eval --bench trace_reinforcement`
14. `cargo bench -p synapse-eval --bench predictive_trace`
15. `cargo bench -p synapse-eval --bench activation_parameter_sweep`
16. `cargo bench -p synapse-eval --bench long_horizon_cognitive_memory`
17. `cargo bench -p synapse-eval --bench exported_cognitive_session`

Expected minimums:

- `reference` Recall@10 = `1.000`
- `multihop` Recall@10 = `1.000`
- `ReflectionYield = 1.0`
- `MergePrecision = 1.0`
- `ForgetPrecision = 1.0`
- `HebbianConsistency = 1.0`
- `cognitive-chain-recall` Recall@10 = `1.0`
- `CognitiveTraceDominance = 1.0`
- `trace-reinforcement` reports `CognitiveTraceDominance = 1.0` and
  `HebbianConsistency = 1.0`
- `predictive-trace` reports `RecallAt10 = 1.0`
- `activation-parameter-sweep` reports `RecallAt10 = 1.0`,
  `CognitiveTraceDominance = 1.0`, and `HebbianConsistency = 1.0`
- `long-horizon-cognitive-memory` reports `RecallAt10 = 1.0`,
  `CognitiveTraceDominance = 1.0`, and `HebbianConsistency = 1.0`
- `exported-cognitive-session` reports `RecallAt10 = 1.0`,
  `CognitiveTraceDominance = 1.0`, and `HebbianConsistency = 1.0`

## Remaining Finalization Work

- Freeze-review RFC-012 Reflection and create the reflection freeze tag/release
  note if the rule-based heuristic is accepted.
- Freeze-review RFC-013 Merge, RFC-014 Forget, and RFC-015 Hebbian with release
  notes and tags.
- Extend parameter sweeps beyond the deterministic activation/trace sweep to
  larger datasets and broader production ranges.
- Extend the exported long-session dataset to external comparison runs.
  Candidate comparisons: Graphiti, Letta, Mem0, or a larger documented
  long-session export.
- Rerun and paste dated manual validation outputs for final release using
  `docs/MANUAL_VALIDATION.md` as the baseline transcript.
- Promote the release-candidate evidence in
  `docs/releases/v0.9.26-cognitive-memory-release-candidate.md` into a final
  release note after the full gate list is rerun in one pass.
- Decide whether UI/deeper agent integrations are release blockers or a
  post-final product milestone.

## Completion Rule

The project is final only when every item in Required Verification Gates passes,
every Remaining Finalization Work item is either completed or explicitly moved
out of scope by an ADR, and the release/tag evidence is present in the repo.
