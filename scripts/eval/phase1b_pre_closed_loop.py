"""Phase 1b-pre: Closed Loop Validation.

Three arms:
  A. Static baseline: FTS + Vector + Rerank (no hypothesis, no activation)
  B. Dynamic without graduation: + hypothesis generation + activation (temporary edges)
  C. Full ecology: + hypothesis generation + graduation + activation (long-term edges)

Question: does improvement come from "immediate reasoning" or "long-term memory evolution"?

Graph Quality Metrics (NOT Recall):
  1. Edge density (target < 5%)
  2. Edge diversity (multiple relation types)
  3. Hypothesis survival curve (candidate -> confirmed)
  4. Activation differentiation (non-uniform bonuses)
"""
import json, os, sys, tempfile, hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ["HF_HUB_OFFLINE"] = "1"

from longmem_dmr_smoke import (
    DMR_FILE, DMR_REPO, default_cache_root, default_fastembed_cache_dir,
    download_dataset, read_jsonl, repo_root, run_kr_eval, write_toml_dataset,
    configure_accelerator_environment,
)
from official_dmr_eval import build_official_dmr_dataset

import argparse

# Load DMR dataset
cache = default_cache_root()
dmr_path = download_dataset(DMR_REPO, DMR_FILE, "https://huggingface.co", cache / "dmr-msc-self-instruct")
rows = read_jsonl(dmr_path)
memories, queries, examples, skipped = build_official_dmr_dataset(rows, 50, "significant_token_containment")
print(f"Loaded {len(memories)} memories, {len(queries)} queries")

# Write dataset TOML
tmpdir = Path(tempfile.mkdtemp(prefix="phase1b-pre-"))
dataset_path = tmpdir / "dmr-50.toml"
write_toml_dataset(dataset_path, memories, queries)
print(f"Dataset written to {dataset_path}")

# Configure accelerator (CPU — no NVIDIA GPU available)
fastembed_dir = default_fastembed_cache_dir()
fastembed_dir.mkdir(parents=True, exist_ok=True)
configure_accelerator_environment(argparse.Namespace(
    accelerator="cpu",
    cuda_device_id=None,
    cuda_runtime_root=None,
    directml_device_id=None,
    fastembed_cache_dir=fastembed_dir,
    embed_batch_size=32,
    embed_max_length=256,
    rerank_batch_size=32,
    rerank_max_length=256,
))

results = {}

# === A. Static baseline ===
print("\n=== A: static baseline (vectors-rerank) ===")
out_a = tmpdir / "baseline.json"
run_kr_eval(dataset_path, out_a, "baseline", 10,
            vectors=True, rerank=True, rerank_pool=10)
r_a = json.loads(out_a.read_text())
results["A_baseline"] = {
    "recall_at_10": r_a["recall_at_10"],
    "mrr_at_10": r_a["mrr_at_10"],
}
print(f"  Recall@10={r_a['recall_at_10']:.4f} MRR@10={r_a['mrr_at_10']:.4f}")

# === B. Dynamic without graduation (hypothesis generation, no graduation) ===
print("\n=== B: hypothesis generation (no graduation) ===")
out_b = tmpdir / "hyp-no-grad.json"
run_kr_eval(dataset_path, out_b, "hyp-no-grad", 10,
            vectors=True, rerank=True, rerank_pool=10,
            hypothesis_generation=True, hypothesis_graduation=False)
r_b = json.loads(out_b.read_text())
hm_b = r_b.get("hypothesis_metrics", {})
results["B_hyp_no_grad"] = {
    "recall_at_10": r_b["recall_at_10"],
    "mrr_at_10": r_b["mrr_at_10"],
    "total_hypotheses": hm_b.get("total_hypotheses", 0),
    "candidates": hm_b.get("candidates", 0),
    "observed": hm_b.get("observed", 0),
    "confirmed": hm_b.get("confirmed", 0),
    "forgotten": hm_b.get("forgotten", 0),
}
print(f"  Recall@10={r_b['recall_at_10']:.4f} MRR@10={r_b['mrr_at_10']:.4f}")
print(f"  hypotheses: {hm_b.get('total_hypotheses', 0)} (cand={hm_b.get('candidates',0)}, obs={hm_b.get('observed',0)}, conf={hm_b.get('confirmed',0)})")

# === C. Full ecology (hypothesis generation + graduation) ===
print("\n=== C: full ecology (hypothesis + graduation) ===")
out_c = tmpdir / "hyp-full.json"
run_kr_eval(dataset_path, out_c, "hyp-full", 10,
            vectors=True, rerank=True, rerank_pool=10,
            hypothesis_generation=True, hypothesis_graduation=True)
r_c = json.loads(out_c.read_text())
hm_c = r_c.get("hypothesis_metrics", {})
results["C_full_ecology"] = {
    "recall_at_10": r_c["recall_at_10"],
    "mrr_at_10": r_c["mrr_at_10"],
    "total_hypotheses": hm_c.get("total_hypotheses", 0),
    "candidates": hm_c.get("candidates", 0),
    "observed": hm_c.get("observed", 0),
    "confirmed": hm_c.get("confirmed", 0),
    "forgotten": hm_c.get("forgotten", 0),
    "graduated_edges": hm_c.get("graduated_edges", 0),
    "edge_density_pct": hm_c.get("edge_density_pct", 0),
    "edge_types": hm_c.get("edge_types", []),
}
print(f"  Recall@10={r_c['recall_at_10']:.4f} MRR@10={r_c['mrr_at_10']:.4f}")
print(f"  hypotheses: {hm_c.get('total_hypotheses', 0)} (cand={hm_c.get('candidates',0)}, obs={hm_c.get('observed',0)}, conf={hm_c.get('confirmed',0)})")
print(f"  graduated_edges: {hm_c.get('graduated_edges', 0)}, density: {hm_c.get('edge_density_pct', 0):.1f}%")
print(f"  edge_types: {hm_c.get('edge_types', [])}")

# === Summary ===
print("\n=== SUMMARY ===")
print(f"{'Arm':<25} {'Recall@10':>10} {'MRR@10':>10} {'Hypotheses':>12} {'Confirmed':>10}")
print("-" * 70)
for arm, d in results.items():
    print(f"{arm:<25} {d['recall_at_10']:>10.4f} {d['mrr_at_10']:>10.4f} {d.get('total_hypotheses', '-'):>12} {d.get('confirmed', '-'):>10}")

# Save
out_path = repo_root() / "crates/eval/reports/phase1b-pre-closed-loop-50.json"
out_path.write_text(json.dumps(results, indent=2))
print(f"\nSaved to {out_path}")
