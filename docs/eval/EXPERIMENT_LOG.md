# Experiment Log

This log records validation attempts that affect Phase 6 decisions. It avoids
raw third-party records and credential values.

| Date | Experiment | Command / report | Result | Decision |
| --- | --- | --- | --- | --- |
| 2026-07-02 | LongMemEval / DMR retrieval branch smoke | `crates/eval/reports/longmem-dmr-smoke-latest.json`, `longmem-dmr-smoke-vector.json`, `longmem-dmr-smoke-vector-rerank.json` | LongMemEval vector improved Recall@10 to `1.000`; DMR vector+reranker improved Recall@10 to `0.658`; reranker hurt LongMemEval top-10. | Keep feature freeze. Expand to 50/50 before architecture changes. |
| 2026-07-02 | CUDA validation smoke | `docs/eval/GPU_VALIDATION_2026-07-02.md` | Code-level CUDA provider selection compiles; local CUDA run is blocked by missing `cublasLt64_12.dll`. | Do not run 50-sample vector/reranker validation on CPU. Resume only after CUDA 12 runtime is installed and the CUDA smoke check passes. |

