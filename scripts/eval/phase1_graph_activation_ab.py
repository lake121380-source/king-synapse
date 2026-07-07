"""Phase 1 A/B: baseline vs graph activation on DMR 50."""
import json, os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ["HF_HUB_OFFLINE"] = "1"

from longmem_dmr_smoke import (
    DMR_FILE, DMR_REPO, default_cache_root, default_fastembed_cache_dir,
    download_dataset, read_jsonl, repo_root, run_kr_eval, write_toml_dataset,
    configure_accelerator_environment,
)
from official_dmr_eval import build_official_dmr_dataset

# Load DMR dataset
cache = default_cache_root()
dmr_path = download_dataset(DMR_REPO, DMR_FILE, "https://huggingface.co", cache / "dmr-msc-self-instruct")
rows = read_jsonl(dmr_path)
memories, queries, examples, skipped = build_official_dmr_dataset(rows, 50, "significant_token_containment")
print(f"Loaded {len(memories)} memories, {len(queries)} queries")

# Write dataset TOML
tmpdir = Path(tempfile.mkdtemp(prefix="phase1-ab-"))
dataset_path = tmpdir / "dmr-50.toml"
write_toml_dataset(dataset_path, memories, queries)
print(f"Dataset written to {dataset_path}")

# Configure accelerator. NOTE: this host has an AMD Radeon Pro VII, no NVIDIA GPU,
# so onnxruntime CUDA provider is unavailable (silent fallback to CPU in Python ort,
# hard failure in Rust ort). Run on CPU to match prior Phase 0 baseline runs (which
# were also CPU despite the cuda field recording the *requested* accelerator).
import argparse
from longmem_dmr_smoke import default_fastembed_cache_dir
fastembed_dir = Path(os.environ.get("FASTEMBED_CACHE_DIR", "")) or default_fastembed_cache_dir()
fastembed_dir.mkdir(parents=True, exist_ok=True)
accel_cfg = configure_accelerator_environment(argparse.Namespace(
    accelerator="cpu",
    cuda_device_id=None,
    cuda_runtime_root=None,
    directml_device_id=None,
    fastembed_cache_dir=fastembed_dir,
    embed_batch_size=None,
    embed_max_length=None,
    rerank_batch_size=None,
    rerank_max_length=None,
))
print(f"accelerator config: {accel_cfg}")

# Run A: baseline (vectors-rerank, no graph activation)
print("\n=== A: baseline (vectors-rerank, no graph activation) ===")
out_a = tmpdir / "baseline.json"
report_a = run_kr_eval(dataset_path, out_a, "baseline-graph-ab", 10,
                       vectors=True, rerank=True, rerank_pool=50,
                       graph_activation=False)
r_a = json.loads(out_a.read_text())
print(f"  Recall@10={r_a['recall_at_10']:.4f} MRR@10={r_a['mrr_at_10']:.4f} n_queries={r_a['n_queries']}")

# Run B: with graph activation
print("\n=== B: vectors-rerank + graph activation ===")
out_b = tmpdir / "graph-activation.json"
report_b = run_kr_eval(dataset_path, out_b, "graph-activation-ab", 10,
                       vectors=True, rerank=True, rerank_pool=50,
                       graph_activation=True)
r_b = json.loads(out_b.read_text())
print(f"  Recall@10={r_b['recall_at_10']:.4f} MRR@10={r_b['mrr_at_10']:.4f} n_queries={r_b['n_queries']}")
print(f"  edge_count={r_b.get('edge_count', 'N/A')}")

# Compare per-query
print("\n=== PER-QUERY COMPARISON ===")
qa_by_q = {q['query']: q for q in r_a['per_query']}
qb_by_q = {q['query']: q for q in r_b['per_query']}
diffs = 0
for q_text, qa in qa_by_q.items():
    qb = qb_by_q.get(q_text)
    if not qb:
        continue
    ra = qa['recall_at_10']
    rb = qb['recall_at_10']
    if ra != rb:
        diffs += 1
        print(f"  DIFF: recall {ra}->{rb} | query: {q_text[:60]}...")
        # Check if activation_bonus changed ranking
        for i, (ha, hb) in enumerate(zip(qa['returned_hit_diagnostics'], qb['returned_hit_diagnostics'])):
            if ha['key'] != hb['key']:
                print(f"    rank {i+1}: A={ha['key'][:20]} (act={ha['activation_bonus']:.4f}) -> B={hb['key'][:20]} (act={hb['activation_bonus']:.4f})")

print(f"\nTotal queries with different recall: {diffs}")
print(f"Recall@10: A={r_a['recall_at_10']:.4f} B={r_b['recall_at_10']:.4f} delta={r_b['recall_at_10']-r_a['recall_at_10']:+.4f}")
print(f"MRR@10:    A={r_a['mrr_at_10']:.4f} B={r_b['mrr_at_10']:.4f} delta={r_b['mrr_at_10']-r_a['mrr_at_10']:+.4f}")

# Save results
output = {
    "baseline": {"recall_at_10": r_a['recall_at_10'], "mrr_at_10": r_a['mrr_at_10']},
    "graph_activation": {"recall_at_10": r_b['recall_at_10'], "mrr_at_10": r_b['mrr_at_10'], "edge_count": r_b.get('edge_count', 0)},
    "delta_recall": r_b['recall_at_10'] - r_a['recall_at_10'],
    "delta_mrr": r_b['mrr_at_10'] - r_a['mrr_at_10'],
    "queries_with_different_recall": diffs,
}
out_path = repo_root() / "crates/eval/reports/phase1-graph-activation-ab-50.json"
out_path.write_text(json.dumps(output, indent=2))
print(f"\nSaved to {out_path}")
