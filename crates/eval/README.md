# synapse-eval

Recall benchmark harness for King Synapse.

## Quick start

```bash
# baseline: RRF only (FTS + entity branches), no model downloads
cargo bench-recall -- --tag baseline-rrf --json results/baseline-rrf.json

# add the dense vector branch (downloads multilingual-e5-base ~470MB on first run)
cargo bench-recall -- --vectors --tag rrf-with-vectors --json results/rrf-with-vectors.json

# add the cross-encoder reranker (downloads bge-reranker-base ~300MB on first run)
cargo bench-recall -- --vectors --rerank --tag rrf-vec-rerank --json results/rrf-vec-rerank.json
```

`cargo bench-recall` is the workspace alias defined in `.cargo/config.toml`;
it expands to `cargo run --release -p synapse-eval --bin kr-eval --`.

## Metrics

Per run the harness reports:

- **Recall@5 / Recall@10**: fraction of relevant memories surfaced in top-K
- **MRR@10**: mean reciprocal rank of the first relevant hit
- **NDCG@10**: normalized discounted cumulative gain
- **P50 / P95 latency**: per-query wall-clock latency
- A `--json` dump containing every per-query miss for offline diffing

## Dataset

`datasets/coding_mem.toml` is the bundled golden set: 20 memories spread
across factual / preference / failure / playbook / state, plus 30 queries
covering FTS-only, entity-only, vector-only, and cross-lingual paraphrases.
Each query lists the keys of memories that count as relevant.

To add a new entry: write a `[[memories]]` block with a unique `key`, then
add `[[queries]]` blocks referencing that key in `relevant`.

## Network requirement

`--vectors` and `--rerank` download ONNX weights from HuggingFace on first
run into `FASTEMBED_CACHE_DIR` (or `./.fastembed_cache`). If `huggingface.co`
is unreachable from your network, set `HF_ENDPOINT=https://hf-mirror.com`
before running. The baseline RRF bench needs no network access.

## Baseline (rev 1ca25c6 + Phase 2 step 5 code)

```
tag:        baseline-rrf
corpus:     20 memories / 30 queries / top-10
Recall@5:   0.950
Recall@10:  0.950
MRR@10:     0.950
NDCG@10:    0.941
P50 lat:    1.17 ms
P95 lat:    1.89 ms
```

Two queries miss:
- "What dimension are our memory embeddings?" — paraphrase, vector branch should fix.
- "user language preference for commits" — CN-EN cross-lingual, vector branch should fix.

Both are exactly the kind of miss the dense + rerank branches are designed
to recover, so the harness gives us a real signal to optimize against.
