# Compatibility Policy

Effective from `v0.5.0-architecture-freeze`.

King Synapse follows SemVer starting with `0.5.0`. Because the project is still pre-1.0, minor version bumps carry stronger stability guarantees than they would after 1.0. This document defines exactly what is stable, what is not, and what a breaking change means.

## Scope

Everything listed in `docs/API_SURFACE.md` as **Stable** falls under this policy. Everything listed as **Experimental** does not. Items not listed in `docs/API_SURFACE.md` are **Internal** and are not covered by this policy.

## Version Rules

- `0.5.x` — patch and minor releases must not break stable APIs. Additive changes (new items, new trait impls that do not alter existing signatures, new enum variants gated behind `#[non_exhaustive]`) are allowed.
- `0.6.0` — the next version allowed to introduce breaking changes to stable APIs. Breaking changes require prior ADR approval and a documented migration path.
- `1.0.0` — locks the full SemVer promise. From 1.0 onward, breaking changes require a major version bump.

## What Counts as a Breaking Change

Breaking changes to **Stable** APIs include, but are not limited to:

- Removing a public item.
- Renaming a public item.
- Changing a trait method signature.
- Changing a function signature.
- Changing a struct field's type or visibility.
- Adding a required field to a public struct without a `Default` implementation.
- Adding a new required associated type / const to a stable trait.
- Removing an enum variant.
- Adding an enum variant to an enum that is not `#[non_exhaustive]`.
- Changing serialized (`serde`) representation of a stable type.
- Changing benchmark contract (`Recall@10` baselines for `reference` and `multihop` datasets) in a way that regresses results.
- Changing MCP tool names, input schemas, or output schemas.
- Changing CLI command names, flag names, or output structure.
- Renaming, deleting, or repurposing a directory under `crates/eval/datasets/`, `crates/eval/benches/`, or `crates/eval/reports/`.
- Removing an `AlgorithmMetric` variant.
- Changing the `BenchmarkReport` serialized shape in a way that alters existing metric encoding.
- Renaming any frozen Adaptive Common Model type (`MemoryImportance`, `ImportanceSignals`, `ImportanceSignal`, `ImportanceEstimator`, `MemoryEventId`, `MemoryEvent`, `MemoryEventKind`, `MemoryEventPayload`, `MemoryEventStream`, `AlgorithmContext`, `AlgorithmMetric`, `BenchmarkReport`). Rename = breaking regardless of behavioral equivalence.
- Adding a new top-level type (struct / enum / trait) under `crates/core/src/adaptive/` after `v0.5.9-adaptive-common-freeze`.
- Introducing an algorithm trait whose primary method deviates from `fn method(&self, target: &T, ctx: &AlgorithmContext<'_>) -> _`. This uniform shape is a hard rule; deviation requires an ADR.
- Adding new service-handle fields to `AlgorithmContext` (any `&dyn Store`, `&dyn RecallEngine`, `&dyn PolicyEngine`, `&dyn Graph`, `&dyn LlmClient`, or owned equivalents). The trait-object surface is closed at v0.5.2.

## What Does Not Count as a Breaking Change

The following are always allowed and never trigger a major version bump:

- Adding new stable items.
- Adding new `NoOp*` or `PlanOnly*` helpers.
- Adding new trait blanket impls.
- Adding new fields to structs marked `#[non_exhaustive]`.
- Adding new enum variants to enums marked `#[non_exhaustive]`.
- Adding a new `AlgorithmMetric` variant.
- Adding a new `ImportanceSignal`, `MemoryEventKind`, or `MemoryEventPayload` variant.
- Adding a new sibling directory under `crates/eval/datasets/`, `crates/eval/benches/`, or `crates/eval/reports/`.
- Adding a new algorithm module under `crates/core/src/adaptive/<algorithm>/` (e.g. `adaptive/reflection/`, `adaptive/merge/`), provided it does not introduce a new top-level shared type in `adaptive/` itself.
- Changing internal-only items.
- Changing algorithm implementations behind stable traits.
- Changing docs, error messages, log messages, or panic messages.
- Improving benchmark results.
- Performance optimizations that preserve API and semantics.

## Public vs Internal

An item is **public** if and only if it is listed in `docs/API_SURFACE.md`.

Everything else — including but not limited to the following — is **internal** and may change at any time:

- Private modules and private items.
- Dispatcher and executor internals not exposed as traits.
- SQL statements, table schemas, and index layouts.
- Vector index configuration.
- FTS5 tokenizer configuration.
- Reranker model choice.
- Working memory activation coefficients.
- Consolidation, reflection, and hebbian heuristics.
- Policy algorithm parameters.
- Internal file layouts on disk.

Depending on internal items is not supported.

## Experimental APIs

Items marked **Experimental** in `docs/API_SURFACE.md`:

- May be changed at any time in any release.
- Should be gated behind a Cargo feature or clearly documented as experimental.
- Are eligible for promotion to Stable through an ADR that lists the required stability tests.

Currently experimental: `synapse-eval` benchmark harness, dataset TOML schema, and metric outputs.

## Deprecation Policy

When a stable item must be replaced:

1. Add the replacement item as stable.
2. Mark the old item `#[deprecated]` in the same release.
3. Keep the deprecated item working for at least **one full minor version** (e.g. deprecated in `0.5.3` → earliest allowed removal is `0.7.0` under pre-1.0 rules, or `1.0.0` afterwards).
4. Removal requires a breaking-change release (`0.6.0` and later, or major bump post-1.0) and an ADR.

## Frozen Baselines

The following baselines are contractually stable and must be preserved:

- `reference` dataset: `Recall@10 = 1.000`
- `multihop` dataset: `Recall@10 = 1.000` after ADR-006 CJK query expansion

Any change that regresses these values on the frozen datasets is a breaking change and must be gated behind the same versioning rules as API breaks.

## ADR Requirements for Breaking Changes

Any breaking change to a Stable API requires an ADR that includes:

1. The item being changed and its current stable signature.
2. The proposed new signature.
3. The affected benchmark baselines and expected impact.
4. A migration path for callers.
5. The target release version.
6. A regression test that fails on the old behavior and passes on the new.

Breaking changes cannot be merged without a passing benchmark run demonstrating either preserved or explicitly-approved regressed baselines.
