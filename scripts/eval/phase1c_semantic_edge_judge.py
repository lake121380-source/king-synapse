"""Phase 1c: Semantic Edge Judge.

Three arms:
  A. co_retrieval only
  B. co_retrieval + semantic filtering
  C. co_retrieval + semantic relation classification

The experiment isolates the new variable: the rule generator still discovers
candidates; the judge only filters or interprets them. The judge can be the
local heuristic implementation or the DeepSeek-backed adapter.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ["HF_HUB_OFFLINE"] = "1"

from longmem_dmr_smoke import (
    DMR_FILE,
    DMR_REPO,
    configure_accelerator_environment,
    default_cache_root,
    default_fastembed_cache_dir,
    download_dataset,
    read_jsonl,
    repo_root,
    run_kr_eval,
    write_toml_dataset,
)
from official_dmr_eval import build_official_dmr_dataset


def summarize(report: dict) -> dict:
    hm = report.get("hypothesis_metrics") or {}
    survival = report.get("semantic_survival") or {}
    utility = survival.get("utility") or {}
    governance = survival.get("governance") or {}
    policy_search = survival.get("policy_search") or {}
    policies = policy_search.get("policies") or []
    return {
        "recall_at_10": report.get("recall_at_10", 0.0),
        "mrr_at_10": report.get("mrr_at_10", 0.0),
        "total_hypotheses": hm.get("total_hypotheses", 0),
        "confirmed": hm.get("confirmed", 0),
        "graduated_edges": hm.get("graduated_edges", 0),
        "edge_density_pct": hm.get("edge_density_pct", 0.0),
        "max_edge_out_degree": hm.get("max_edge_out_degree", 0),
        "edge_types": hm.get("edge_types", []),
        "semantic_judged": hm.get("semantic_judged", 0),
        "semantic_accepted": hm.get("semantic_accepted", 0),
        "semantic_rejected": hm.get("semantic_rejected", 0),
        "semantic_acceptance_rate": hm.get("semantic_acceptance_rate", 0.0),
        "semantic_cache_hits": report.get("semantic_cache_hits", 0),
        "semantic_cache_misses": report.get("semantic_cache_misses", 0),
        "semantic_cache_writes": report.get("semantic_cache_writes", 0),
        "semantic_judge_cache_path": report.get("semantic_judge_cache_path"),
        "semantic_audit_samples": report.get("semantic_audit_samples", []),
        "survival_candidates": survival.get("candidate_count", 0),
        "survival_accepted": survival.get("semantic_accepted_count", 0),
        "survival_unique_accepted": survival.get("unique_accepted_edges", 0),
        "survival_rejected": survival.get("semantic_rejected_count", 0),
        "survival_confirmed": survival.get("confirmed_count", 0),
        "survival_graduated": survival.get("graduated_count", 0),
        "survival_activated": survival.get("activated_count", 0),
        "confidence_buckets": survival.get("confidence_buckets", []),
        "utility_evaluated_queries": utility.get("evaluated_queries", 0),
        "utility_affected_queries": utility.get("affected_queries", 0),
        "utility_affected_edges": utility.get("affected_edges", 0),
        "utility_useful_edges": utility.get("useful_edges", 0),
        "utility_harmful_edges": utility.get("harmful_edges", 0),
        "utility_mean_rank_delta": utility.get("mean_rank_delta", 0.0),
        "utility_mean_mrr_delta": utility.get("mean_mrr_delta", 0.0),
        "utility_correct_rank_improvements": utility.get("correct_rank_improvements", 0),
        "utility_wrong_rank_promotions": utility.get("wrong_rank_promotions", 0),
        "attribution_evaluated_edges": utility.get("attribution_evaluated_edges", 0),
        "attribution_affected_edges": utility.get("attribution_affected_edges", 0),
        "causal_useful_edges": utility.get("causal_useful_edges", 0),
        "causal_harmful_edges": utility.get("causal_harmful_edges", 0),
        "causal_mean_rank_delta": utility.get("mean_causal_rank_delta", 0.0),
        "causal_mean_mrr_delta": utility.get("mean_causal_mrr_delta", 0.0),
        "governance_trusted_edges": governance.get("trusted_edges", 0),
        "governance_suspect_edges": governance.get("suspect_edges", 0),
        "governance_dormant_edges": governance.get("dormant_edges", 0),
        "governance_mean_weight": governance.get("mean_governance_weight", 0.0),
        "governance_evaluated_queries": governance.get("evaluated_queries", 0),
        "governance_changed_queries": governance.get("changed_queries", 0),
        "governance_mean_rank_delta": governance.get("mean_rank_delta_vs_full_graph", 0.0),
        "governance_mean_mrr_delta": governance.get("mean_mrr_delta_vs_full_graph", 0.0),
        "policy_best": policy_search.get("best_policy_by_mrr") or "none",
        "policy_summary": ",".join(
            f"{policy.get('name')}:{policy.get('mean_mrr_delta_vs_full_graph', 0.0):.4f}"
            for policy in policies
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 1c semantic edge judge A/B/C.")
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--rerank-pool", type=int, default=10)
    parser.add_argument("--endpoint", default="https://huggingface.co")
    parser.add_argument("--semantic-judge", choices=("heuristic", "deepseek"), default="heuristic")
    parser.add_argument("--no-semantic-judge-cache", action="store_true")
    parser.add_argument("--semantic-judge-cache-path", type=Path)
    parser.add_argument("--output-path", type=Path)
    parser.add_argument("--no-vectors", action="store_true", help="Disable dense vector retrieval.")
    parser.add_argument("--no-rerank", action="store_true", help="Disable cross-encoder reranking.")
    args = parser.parse_args()

    cache = default_cache_root()
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, cache / "dmr-msc-self-instruct")
    rows = read_jsonl(dmr_path)
    memories, queries, _examples, _skipped = build_official_dmr_dataset(
        rows, args.sample_size, "significant_token_containment"
    )

    tmpdir = Path(tempfile.mkdtemp(prefix="phase1c-"))
    dataset_path = tmpdir / f"dmr-{args.sample_size}.toml"
    write_toml_dataset(dataset_path, memories, queries)

    fastembed_dir = default_fastembed_cache_dir()
    fastembed_dir.mkdir(parents=True, exist_ok=True)
    configure_accelerator_environment(
        argparse.Namespace(
            accelerator="cpu",
            cuda_device_id=None,
            cuda_runtime_root=None,
            directml_device_id=None,
            fastembed_cache_dir=fastembed_dir,
            embed_batch_size=32,
            embed_max_length=256,
            rerank_batch_size=32,
            rerank_max_length=256,
        )
    )

    arms = {
        "A_co_retrieval_only": {"semantic_edge_mode": "off"},
        "B_semantic_filter": {"semantic_edge_mode": "filter"},
        "C_semantic_classify": {"semantic_edge_mode": "classify"},
    }

    results: dict[str, dict] = {}
    for name, config in arms.items():
        print(f"\n=== {name} ===")
        output = tmpdir / f"{name}.json"
        report = run_kr_eval(
            dataset_path,
            output,
            name,
            args.k,
            vectors=not args.no_vectors,
            rerank=not args.no_rerank,
            rerank_pool=args.rerank_pool,
            graph_activation=True,
            hypothesis_generation=True,
            hypothesis_graduation=True,
            semantic_edge_mode=config["semantic_edge_mode"],
            semantic_judge=args.semantic_judge,
            semantic_judge_cache=not args.no_semantic_judge_cache,
            semantic_judge_cache_path=args.semantic_judge_cache_path,
        )
        results[name] = summarize(report)
        summary = results[name]
        print(
            "  recall={recall_at_10:.4f} edges={graduated_edges} "
            "density={edge_density_pct:.2f}% max_degree={max_edge_out_degree} judged={semantic_judged} "
            "accepted={semantic_accepted} rejected={semantic_rejected} "
            "survival={survival_candidates}->{survival_unique_accepted}->{survival_confirmed}->"
            "{survival_graduated}->{survival_activated} "
            "utility_edges={utility_affected_edges} useful={utility_useful_edges} "
            "harmful={utility_harmful_edges} rank_delta={utility_mean_rank_delta:.2f} "
            "mrr_delta={utility_mean_mrr_delta:.4f} "
            "attr_edges={attribution_affected_edges} causal_useful={causal_useful_edges} "
            "causal_harmful={causal_harmful_edges} causal_mrr={causal_mean_mrr_delta:.4f} "
            "gov=T{governance_trusted_edges}/S{governance_suspect_edges}/D{governance_dormant_edges} "
            "gov_mrr={governance_mean_mrr_delta:.4f} "
            "best_policy={policy_best} policies=[{policy_summary}] "
            "cache_hit={semantic_cache_hits} cache_miss={semantic_cache_misses}".format(**summary)
        )

    out_path = args.output_path or repo_root() / "crates/eval/reports/phase1c-semantic-edge-judge.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
