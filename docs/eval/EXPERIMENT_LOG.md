# Experiment Log

This log records validation attempts that affect Phase 6 decisions. It avoids
raw third-party records and credential values.

| Date | Experiment | Command / report | Result | Decision |
| --- | --- | --- | --- | --- |
| 2026-07-02 | LongMemEval / DMR retrieval branch smoke | `crates/eval/reports/longmem-dmr-smoke-latest.json`, `longmem-dmr-smoke-vector.json`, `longmem-dmr-smoke-vector-rerank.json` | LongMemEval vector improved Recall@10 to `1.000`; DMR vector+reranker improved Recall@10 to `0.658`; reranker hurt LongMemEval top-10. | Keep feature freeze. Expand to 50/50 before architecture changes. |
| 2026-07-02 | CUDA validation smoke | `docs/eval/GPU_VALIDATION_2026-07-02.md` | CUDA provider passed after installing CUDA 12 runtime DLLs into a user cache. RTX 2060 4GB required fixed batch and max-length limits. | Use GPU for vector/reranker validation; keep runtime cache outside the repository. |
| 2026-07-02 | LongMemEval / DMR 50 validation | `crates/eval/reports/longmem-50-validation.json`, `crates/eval/reports/dmr-50-validation.json`, `docs/eval/FAILURE_ANALYSIS.md` | LongMemEval Recall@10: baseline `0.503`, vector `0.663`, reranker `0.590`. DMR Recall@10: baseline `0.188`, vector `0.438`, reranker `0.584`. | Architecture not disproven. Focus next on DMR mapping/chunk skips and final ranking, not feature growth. |
