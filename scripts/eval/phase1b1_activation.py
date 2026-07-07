"""Phase 1b-1: Activation Differentiation Test.

Four arms:
  A. Static baseline: FTS + Vector + Rerank
  B. Full ecology (hypothesis + graduation) — no activation
  C. Full ecology + GraphActivationBooster — using graduated edges
  D. Entity edges + activation (Phase 1 style, for comparison)

Key metric: activation differentiation (entropy/variance of activation_bonus),
NOT Recall@10.
"""
import json, os, sys, tempfile, math
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

cache = default_cache_root()
dmr_path = download_dataset(DMR_REPO, DMR_FILE, "https://huggingface.co", cache / "dmr-msc-self-instruct")
rows = read_jsonl(dmr_path)
memories, queries, examples, skipped = build_official_dmr_dataset(rows, 50, "significant_token_containment")
print(f"Loaded {len(memories)} memories, {len(queries)} queries")

tmpdir = Path(tempfile.mkdtemp(prefix="phase1b1-"))
dataset_path = tmpdir / "dmr-50.toml"
write_toml_dataset(dataset_path, memories, queries)
print(f"Dataset: {dataset_path}")

fastembed_dir = default_fastembed_cache_dir()
fastembed_dir.mkdir(parents=True, exist_ok=True)
configure_accelerator_environment(argparse.Namespace(
    accelerator="cpu", cuda_device_id=None, cuda_runtime_root=None,
    directml_device_id=None, fastembed_cache_dir=fastembed_dir,
    embed_batch_size=32, embed_max_length=256, rerank_batch_size=32, rerank_max_length=256,
))

results = {}

def activation_stats(report):
    """Compute activation differentiation metrics from per-query diagnostics."""
    all_bonuses = []
    per_query_stats = []
    for q in report.get("per_query", []):
        bonuses = [h.get("activation_bonus", 0) for h in q.get("returned_hit_diagnostics", [])]
        if bonuses:
            all_bonuses.extend(bonuses)
            mean = sum(bonuses) / len(bonuses)
            variance = sum((b - mean) ** 2 for b in bonuses) / len(bonuses)
            std = math.sqrt(variance)
            # Shannon entropy (normalized)
            total = sum(bonuses)
            if total > 0:
                probs = [b / total for b in bonuses if b > 0]
                entropy = -sum(p * math.log2(p) for p in probs) / max(1, len(probs))
            else:
                entropy = 1.0  # uniform = max entropy
            per_query_stats.append({"mean": mean, "std": std, "entropy": entropy, "n": len(bonuses)})
    if all_bonuses:
        overall_mean = sum(all_bonuses) / len(all_bonuses)
        overall_var = sum((b - overall_mean) ** 2 for b in all_bonuses) / len(all_bonuses)
        overall_std = math.sqrt(overall_var)
        nonzero = sum(1 for b in all_bonuses if b > 0)
        distinct_values = len(set(round(b, 4) for b in all_bonuses))
    else:
        overall_mean = overall_std = nonzero = distinct_values = 0
    return {
        "total_hits": len(all_bonuses),
        "nonzero_bonuses": nonzero,
        "distinct_bonus_values": distinct_values,
        "mean": round(overall_mean, 6),
        "std": round(overall_std, 6),
        "mean_per_query_entropy": round(sum(s["entropy"] for s in per_query_stats) / max(1, len(per_query_stats)), 4),
    }

# === A. Static baseline ===
print("\n=== A: static baseline ===")
out_a = tmpdir / "baseline.json"
run_kr_eval(dataset_path, out_a, "A-baseline", 10, vectors=True, rerank=True, rerank_pool=10)
r_a = json.loads(out_a.read_text())
results["A_baseline"] = {"recall": r_a["recall_at_10"], "mrr": r_a["mrr_at_10"], "activation": activation_stats(r_a)}
print(f"  recall={r_a['recall_at_10']:.4f}")

# === B. Full ecology (no activation) ===
print("\n=== B: full ecology (no activation) ===")
out_b = tmpdir / "ecology.json"
run_kr_eval(dataset_path, out_b, "B-ecology", 10, vectors=True, rerank=True, rerank_pool=10,
            hypothesis_generation=True, hypothesis_graduation=True)
r_b = json.loads(out_b.read_text())
hm_b = r_b.get("hypothesis_metrics", {})
results["B_ecology"] = {"recall": r_b["recall_at_10"], "mrr": r_b["mrr_at_10"], "activation": activation_stats(r_b),
                         "hypotheses": hm_b.get("total_hypotheses",0), "confirmed": hm_b.get("confirmed",0),
                         "graduated_edges": hm_b.get("graduated_edges",0), "density": hm_b.get("edge_density_pct",0)}
print(f"  recall={r_b['recall_at_10']:.4f} edges={hm_b.get('graduated_edges',0)} density={hm_b.get('edge_density_pct',0):.1f}%")

# === C. Full ecology + activation ===
print("\n=== C: full ecology + activation ===")
out_c = tmpdir / "ecology-activation.json"
run_kr_eval(dataset_path, out_c, "C-eco-act", 10, vectors=True, rerank=True, rerank_pool=10,
            hypothesis_generation=True, hypothesis_graduation=True,
            graph_activation=True)
r_c = json.loads(out_c.read_text())
hm_c = r_c.get("hypothesis_metrics", {})
results["C_ecology_activation"] = {"recall": r_c["recall_at_10"], "mrr": r_c["mrr_at_10"], "activation": activation_stats(r_c),
                                    "hypotheses": hm_c.get("total_hypotheses",0), "confirmed": hm_c.get("confirmed",0),
                                    "graduated_edges": hm_c.get("graduated_edges",0), "density": hm_c.get("edge_density_pct",0)}
print(f"  recall={r_c['recall_at_10']:.4f} edges={hm_c.get('graduated_edges',0)} density={hm_c.get('edge_density_pct',0):.1f}%")

# === D. Entity edges + activation (Phase 1 comparison) ===
print("\n=== D: entity edges + activation (Phase 1 style) ===")
out_d = tmpdir / "entity-activation.json"
run_kr_eval(dataset_path, out_d, "D-entity-act", 10, vectors=True, rerank=True, rerank_pool=10,
            graph_activation=True)
r_d = json.loads(out_d.read_text())
results["D_entity_activation"] = {"recall": r_d["recall_at_10"], "mrr": r_d["mrr_at_10"], "activation": activation_stats(r_d),
                                   "edge_count": r_d.get("edge_count", 0)}
print(f"  recall={r_d['recall_at_10']:.4f} edges={r_d.get('edge_count',0)}")

# === Summary ===
print("\n" + "="*90)
print("ACTIVATION DIFFERENTIATION ANALYSIS")
print("="*90)
print(f"{'Arm':<28} {'Recall':>7} {'Edges':>7} {'Density':>8} {'Mean Bonus':>11} {'Std':>8} {'Distinct':>9} {'Entropy':>8}")
print("-"*90)
for arm, d in results.items():
    a = d.get("activation", {})
    edges = d.get("graduated_edges", d.get("edge_count", 0))
    density = d.get("density", 0)
    print(f"{arm:<28} {d['recall']:>7.4f} {edges:>7} {density:>7.1f}% {a.get('mean',0):>11.6f} {a.get('std',0):>8.6f} {a.get('distinct_bonus_values',0):>9} {a.get('mean_per_query_entropy',0):>8.4f}")

print("\nKey question: Does C (ecology+activation) show higher std / more distinct values than D (entity+activation)?")
print("  Higher std = activation is differentiating between nodes")
print("  More distinct values = graph has meaningful structure")
print("  Lower entropy = activation is concentrated (not uniform)")

out_path = repo_root() / "crates/eval/reports/phase1b1-activation-differentiation-50.json"
out_path.write_text(json.dumps(results, indent=2))
print(f"\nSaved to {out_path}")
