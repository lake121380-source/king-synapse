# ADR-006: CJK Query Expansion Baseline

Status: Accepted

## Context

The `multihop` benchmark contains Chinese natural-language queries that refer
to English technical memories. Before this ADR, the default lexical pipeline
treated each Chinese clause as a long FTS token unless the query had spaces.
That kept `multihop` at `Recall@10 = 0.600` even when the intended technical
concepts were explicit in Chinese, such as "向量", "维度约束", and "前缀记忆".

## Decision

`RecallEngine` may add a small deterministic CJK query-expansion dictionary
before calling the Store FTS primitive. The dictionary maps Chinese technical
markers to existing English/code tokens already present in stored memories.

Examples:

- `向量`, `维度约束` -> `vector`, `embedding`, `dim`, `VEC_DIM`, `768`
- `前缀记忆` -> `prefix`, `query`, `passage`
- `大表`, `维护` -> `table`, `autovacuum`, `VACUUM`, `ANALYZE`

This is intentionally not a general segmenter, embedding model, or LLM step,
and Store remains a query-agnostic primitive layer. It is an explainable bridge
for mixed Chinese/English technical recall.

## Consequences

- `reference` remains `Recall@10 = 1.000`.
- `multihop` is intentionally raised to `Recall@10 = 1.000`.
- Future baseline checks should treat `multihop Recall@10 = 1.000` as the
  current floor. Regressions below that value require investigation.
- Historical release notes that recorded `0.600` remain accurate snapshots of
  earlier milestones and are not rewritten.
