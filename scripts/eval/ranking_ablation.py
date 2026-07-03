#!/usr/bin/env python
"""Ranking ablation runner for Phase 6 validation.

The runner varies one ranking parameter at a time and writes only sanitized
retrieval metrics. Raw third-party questions, answers, dialogs, and sessions
stay in temporary/cache locations and must not be committed.
"""

from __future__ import annotations

import argparse
import json
import os
import math
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

from longmem_dmr_smoke import (
    DMR_ANSWER_MATCH_POLICIES,
    DMR_FILE,
    DMR_REPO,
    LONGMEM_FILE,
    LONGMEM_REPO,
    build_longmem_dataset,
    configure_accelerator_environment,
    dataset_info,
    default_cache_root,
    default_fastembed_cache_dir,
    download_dataset,
    dmr_tag_base,
    read_jsonl,
    repo_root,
    run_kr_eval,
    sanitize_eval_report,
    source_file_report,
    write_toml_dataset,
)
from official_dmr_eval import build_official_dmr_dataset


DEFAULT_RRF_K = 60.0
DEFAULT_BRANCH_WEIGHT = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sanitized ranking ablations.")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json",
    )
    parser.add_argument(
        "--datasets",
        default="dmr",
        help="Comma-separated datasets: dmr, longmem, all.",
    )
    parser.add_argument("--dmr-sample-size", type=int, default=50)
    parser.add_argument("--longmem-sample-size", type=int, default=50)
    parser.add_argument(
        "--dmr-answer-match",
        choices=tuple(DMR_ANSWER_MATCH_POLICIES),
        default="punctuation",
    )
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument(
        "--ablation",
        choices=("reranker-pool", "top-k", "rrf-k", "vector-weight"),
        default="reranker-pool",
        help="Ranking parameter to vary. Exactly one parameter is varied per run.",
    )
    parser.add_argument(
        "--reranker-pools",
        default="10,25,50,100",
        help="Comma-separated reranker pool sizes for --ablation reranker-pool.",
    )
    parser.add_argument(
        "--top-k-values",
        default="10,25,50",
        help="Comma-separated top-k values for --ablation top-k.",
    )
    parser.add_argument(
        "--rrf-k-values",
        default="20,40,60,80",
        help="Comma-separated RRF k values for --ablation rrf-k.",
    )
    parser.add_argument(
        "--vector-weights",
        default="0.5,1.0,1.5,2.0",
        help="Comma-separated vector branch weights for --ablation vector-weight.",
    )
    parser.add_argument("--fixed-reranker-pool", type=int, default=50)
    parser.add_argument("--embed-batch-size", type=int, default=None)
    parser.add_argument("--embed-max-length", type=int, default=None)
    parser.add_argument("--rerank-batch-size", type=int, default=None)
    parser.add_argument("--rerank-max-length", type=int, default=None)
    parser.add_argument(
        "--accelerator",
        choices=("env", "cpu", "cuda", "directml"),
        default="cuda",
        help="Default is cuda because Phase 6 long-memory validation is GPU-first.",
    )
    parser.add_argument("--cuda-device-id", default="0")
    parser.add_argument("--cuda-runtime-root", type=Path, default=None)
    parser.add_argument("--directml-device-id", default=None)
    parser.add_argument("--cleanup-cache", action="store_true")
    return parser.parse_args()


def parse_dataset_selection(raw: str) -> set[str]:
    aliases = {
        "all": "all",
        "dmr": "dmr",
        "longmem": "longmem",
        "longmemeval": "longmem",
    }
    requested = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not requested:
        requested = ["dmr"]
    selected: set[str] = set()
    for part in requested:
        if part not in aliases:
            raise ValueError(f"unknown dataset: {part}")
        canonical = aliases[part]
        if canonical == "all":
            return {"dmr", "longmem"}
        selected.add(canonical)
    return selected


def parse_int_list(raw: str, *, name: str) -> list[int]:
    values: list[int] = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        parsed = int(value)
        if parsed <= 0:
            raise ValueError(f"{name} values must be positive: {parsed}")
        values.append(parsed)
    if not values:
        raise ValueError(f"no {name} values selected")
    return values


def parse_float_list(raw: str, *, name: str) -> list[float]:
    values: list[float] = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        parsed = float(value)
        if not math.isfinite(parsed) or parsed < 0.0:
            raise ValueError(f"{name} values must be finite and non-negative: {parsed}")
        values.append(parsed)
    if not values:
        raise ValueError(f"no {name} values selected")
    return values


def format_number(value: float) -> str:
    return format(value, "g")


def get_branch_weight(run: dict[str, Any], branch: str) -> float:
    direct_key = f"{branch}_weight"
    if direct_key in run and run.get(direct_key) is not None:
        return float(run[direct_key])
    weights = run.get("rrf_weights") or {}
    value = weights.get(branch)
    if value is not None:
        return float(value)
    return DEFAULT_BRANCH_WEIGHT


def build_dataset_specs(args: argparse.Namespace, api: HfApi) -> tuple[list[dict[str, Any]], list[Path]]:
    selected = parse_dataset_selection(args.datasets)
    specs: list[dict[str, Any]] = []
    cleanup_paths: list[Path] = []

    if "dmr" in selected:
        dmr_info = dataset_info(api, DMR_REPO)
        dmr_cache = args.cache_root / "dmr-msc-self-instruct"
        cleanup_paths.append(dmr_cache)
        dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
        rows = read_jsonl(dmr_path)
        memories, queries, examples, skipped = build_official_dmr_dataset(
            rows, args.dmr_sample_size, args.dmr_answer_match
        )
        if not queries:
            raise RuntimeError("DMR ranking ablation sample is empty.")
        specs.append(
            {
                "id": "dmr",
                "name": "DMR candidate MSC-Self-Instruct ranking ablation",
                "source": source_file_report(DMR_REPO, DMR_FILE, dmr_path, dmr_info),
                "sample_size_requested": args.dmr_sample_size,
                "memories": memories,
                "queries": queries,
                "examples": examples,
                "skipped": skipped,
                "toml_name": "dmr-ranking-ablation.toml",
                "tag_base": f"{dmr_tag_base(args.dmr_answer_match)}-ranking-ablation",
                "metadata": {
                    "answer_match_policy": args.dmr_answer_match,
                    "answer_match_policy_description": DMR_ANSWER_MATCH_POLICIES[args.dmr_answer_match],
                },
            }
        )

    if "longmem" in selected:
        longmem_info = dataset_info(api, LONGMEM_REPO)
        longmem_cache = args.cache_root / "longmemeval-cleaned"
        cleanup_paths.append(longmem_cache)
        longmem_path = download_dataset(LONGMEM_REPO, LONGMEM_FILE, args.endpoint, longmem_cache)
        rows = json.loads(longmem_path.read_text(encoding="utf-8"))
        memories, queries, examples, skipped = build_longmem_dataset(rows, args.longmem_sample_size)
        if not queries:
            raise RuntimeError("LongMemEval ranking ablation sample is empty.")
        specs.append(
            {
                "id": "longmem",
                "name": "LongMemEval cleaned ranking ablation",
                "source": source_file_report(LONGMEM_REPO, LONGMEM_FILE, longmem_path, longmem_info),
                "sample_size_requested": args.longmem_sample_size,
                "memories": memories,
                "queries": queries,
                "examples": examples,
                "skipped": skipped,
                "toml_name": "longmem-ranking-ablation.toml",
                "tag_base": "longmemeval-ranking-ablation",
                "metadata": {},
            }
        )

    return specs, cleanup_paths


def run_reranker_pool_ablation(
    *,
    dataset_path: Path,
    output_dir: Path,
    tag_base: str,
    examples: list[dict[str, Any]],
    k: int,
    reranker_pools: list[int],
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for pool in reranker_pools:
        tag = f"{tag_base}-pool-{pool}"
        raw_output = output_dir / f"{tag}-raw-report.json"
        print(f"running {tag}...", flush=True)
        raw = run_kr_eval(
            dataset_path,
            raw_output,
            tag,
            k,
            vectors=True,
            rerank=True,
            rerank_pool=pool,
            rrf_k=DEFAULT_RRF_K,
            fts_weight=DEFAULT_BRANCH_WEIGHT,
            entity_weight=DEFAULT_BRANCH_WEIGHT,
            vector_weight=DEFAULT_BRANCH_WEIGHT,
        )
        run = sanitize_eval_report(raw, examples)
        run.update(
            {
                "variant_id": f"reranker-pool-{pool}",
                "ablated_parameter": "reranker_pool",
                "ablated_value": pool,
                "reranker_pool": pool,
                "k": k,
                "rrf_k": raw.get("rrf_k"),
                "rrf_weights": raw.get("rrf_weights"),
                "mode": "vectors-rerank",
                "label": f"RRF + vectors + reranker pool {pool}",
                "tag": raw.get("tag"),
            }
        )
        runs.append(run)
    return runs


def run_top_k_ablation(
    *,
    dataset_path: Path,
    output_dir: Path,
    tag_base: str,
    examples: list[dict[str, Any]],
    top_k_values: list[int],
    reranker_pool: int,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for k in top_k_values:
        tag = f"{tag_base}-top-k-{k}"
        raw_output = output_dir / f"{tag}-raw-report.json"
        print(f"running {tag}...", flush=True)
        raw = run_kr_eval(
            dataset_path,
            raw_output,
            tag,
            k,
            vectors=True,
            rerank=True,
            rerank_pool=reranker_pool,
            rrf_k=DEFAULT_RRF_K,
            fts_weight=DEFAULT_BRANCH_WEIGHT,
            entity_weight=DEFAULT_BRANCH_WEIGHT,
            vector_weight=DEFAULT_BRANCH_WEIGHT,
        )
        run = sanitize_eval_report(raw, examples)
        run.update(
            {
                "variant_id": f"top-k-{k}",
                "ablated_parameter": "top_k",
                "ablated_value": k,
                "reranker_pool": reranker_pool,
                "k": k,
                "rrf_k": raw.get("rrf_k"),
                "rrf_weights": raw.get("rrf_weights"),
                "mode": "vectors-rerank",
                "label": f"RRF + vectors + reranker top-k {k}",
                "tag": raw.get("tag"),
            }
        )
        runs.append(run)
    return runs


def run_rrf_k_ablation(
    *,
    dataset_path: Path,
    output_dir: Path,
    tag_base: str,
    examples: list[dict[str, Any]],
    k: int,
    rrf_k_values: list[float],
    reranker_pool: int,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for rrf_k in rrf_k_values:
        tag = f"{tag_base}-rrf-k-{format_number(rrf_k)}"
        raw_output = output_dir / f"{tag}-raw-report.json"
        print(f"running {tag}...", flush=True)
        raw = run_kr_eval(
            dataset_path,
            raw_output,
            tag,
            k,
            vectors=True,
            rerank=True,
            rerank_pool=reranker_pool,
            rrf_k=rrf_k,
            fts_weight=DEFAULT_BRANCH_WEIGHT,
            entity_weight=DEFAULT_BRANCH_WEIGHT,
            vector_weight=DEFAULT_BRANCH_WEIGHT,
        )
        run = sanitize_eval_report(raw, examples)
        run.update(
            {
                "variant_id": f"rrf-k-{format_number(rrf_k)}",
                "ablated_parameter": "rrf_k",
                "ablated_value": rrf_k,
                "reranker_pool": reranker_pool,
                "k": k,
                "rrf_k": raw.get("rrf_k"),
                "rrf_weights": raw.get("rrf_weights"),
                "vector_weight": (raw.get("rrf_weights") or {}).get("vector"),
                "mode": "vectors-rerank",
                "label": f"RRF k {format_number(rrf_k)} + vectors + reranker",
                "tag": raw.get("tag"),
            }
        )
        runs.append(run)
    return runs


def run_vector_weight_ablation(
    *,
    dataset_path: Path,
    output_dir: Path,
    tag_base: str,
    examples: list[dict[str, Any]],
    k: int,
    vector_weights: list[float],
    reranker_pool: int,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for vector_weight in vector_weights:
        tag = f"{tag_base}-vector-weight-{format_number(vector_weight)}"
        raw_output = output_dir / f"{tag}-raw-report.json"
        print(f"running {tag}...", flush=True)
        raw = run_kr_eval(
            dataset_path,
            raw_output,
            tag,
            k,
            vectors=True,
            rerank=True,
            rerank_pool=reranker_pool,
            rrf_k=DEFAULT_RRF_K,
            fts_weight=DEFAULT_BRANCH_WEIGHT,
            entity_weight=DEFAULT_BRANCH_WEIGHT,
            vector_weight=vector_weight,
        )
        run = sanitize_eval_report(raw, examples)
        run.update(
            {
                "variant_id": f"vector-weight-{format_number(vector_weight)}",
                "ablated_parameter": "vector_weight",
                "ablated_value": vector_weight,
                "reranker_pool": reranker_pool,
                "k": k,
                "rrf_k": raw.get("rrf_k"),
                "rrf_weights": raw.get("rrf_weights"),
                "vector_weight": (raw.get("rrf_weights") or {}).get("vector"),
                "mode": "vectors-rerank",
                "label": f"RRF vector weight {format_number(vector_weight)} + vectors + reranker",
                "tag": raw.get("tag"),
            }
        )
        runs.append(run)
    return runs


def summarize_runs(runs: list[dict[str, Any]], ablated_parameter: str) -> dict[str, Any]:
    if not runs:
        return {}
    best_recall = max(runs, key=lambda item: (item.get("recall_at_10") or 0.0, item.get("mrr_at_10") or 0.0))
    best_mrr = max(runs, key=lambda item: (item.get("mrr_at_10") or 0.0, item.get("recall_at_10") or 0.0))
    control = control_run(runs, ablated_parameter)
    return {
        "best_by_recall_at_10": compact_run(best_recall),
        "best_by_mrr_at_10": compact_run(best_mrr),
        "control_variant": compact_run(control),
        "deltas_vs_control": [
            {
                "variant_id": run["variant_id"],
                "ablated_parameter": run["ablated_parameter"],
                "ablated_value": run["ablated_value"],
                "reranker_pool": run["reranker_pool"],
                "k": run["k"],
                "rrf_k": run.get("rrf_k"),
                "fts_weight": get_branch_weight(run, "fts"),
                "entity_weight": get_branch_weight(run, "entity"),
                "vector_weight": get_branch_weight(run, "vector"),
                "rrf_k_delta": safe_delta(run.get("rrf_k"), control.get("rrf_k")),
                "fts_weight_delta": safe_delta(get_branch_weight(run, "fts"), get_branch_weight(control, "fts")),
                "entity_weight_delta": safe_delta(
                    get_branch_weight(run, "entity"), get_branch_weight(control, "entity")
                ),
                "vector_weight_delta": safe_delta(
                    get_branch_weight(run, "vector"), get_branch_weight(control, "vector")
                ),
                "recall_at_10_delta": safe_delta(run.get("recall_at_10"), control.get("recall_at_10")),
                "mrr_at_10_delta": safe_delta(run.get("mrr_at_10"), control.get("mrr_at_10")),
                "p50_latency_ms_delta": safe_delta(run.get("p50_latency_ms"), control.get("p50_latency_ms")),
                "total_ms_delta": safe_delta(run.get("total_ms"), control.get("total_ms")),
                "top_1_delta": count_rank_bucket(run, "top_1") - count_rank_bucket(control, "top_1"),
                "retrieval_miss_delta": count_failure(run, "retrieval_miss") - count_failure(control, "retrieval_miss"),
            }
            for run in runs
        ],
    }


def control_run(runs: list[dict[str, Any]], ablated_parameter: str) -> dict[str, Any]:
    if ablated_parameter == "reranker_pool":
        return next((run for run in runs if run.get("reranker_pool") == 50), runs[0])
    if ablated_parameter == "top_k":
        return next((run for run in runs if run.get("k") == 10), runs[0])
    if ablated_parameter == "rrf_k":
        return min(
            runs,
            key=lambda run: abs(
                (float(run.get("rrf_k")) if run.get("rrf_k") is not None else DEFAULT_RRF_K)
                - DEFAULT_RRF_K
            ),
        )
    if ablated_parameter == "vector_weight":
        return min(runs, key=lambda run: abs(get_branch_weight(run, "vector") - DEFAULT_BRANCH_WEIGHT))
    return runs[0]


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant_id": run.get("variant_id"),
        "ablated_parameter": run.get("ablated_parameter"),
        "ablated_value": run.get("ablated_value"),
        "reranker_pool": run.get("reranker_pool"),
        "k": run.get("k"),
        "rrf_k": run.get("rrf_k"),
        "rrf_weights": run.get("rrf_weights"),
        "fts_weight": get_branch_weight(run, "fts"),
        "entity_weight": get_branch_weight(run, "entity"),
        "vector_weight": get_branch_weight(run, "vector"),
        "recall_at_10": run.get("recall_at_10"),
        "mrr_at_10": run.get("mrr_at_10"),
        "ndcg_at_10": run.get("ndcg_at_10"),
        "p50_latency_ms": run.get("p50_latency_ms"),
        "p95_latency_ms": run.get("p95_latency_ms"),
        "rank_bucket_counts": run.get("rank_bucket_counts"),
        "failure_type_counts": run.get("failure_type_counts"),
    }


def safe_delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def count_rank_bucket(run: dict[str, Any], bucket: str) -> int:
    return int((run.get("rank_bucket_counts") or {}).get(bucket, 0))


def count_failure(run: dict[str, Any], failure: str) -> int:
    return int((run.get("failure_type_counts") or {}).get(failure, 0))


def dataset_report(spec: dict[str, Any], runs: list[dict[str, Any]], ablated_parameter: str) -> dict[str, Any]:
    categories = Counter(example["category"] for example in spec["examples"])
    report = {
        "id": spec["id"],
        "name": spec["name"],
        "source": spec["source"],
        "sample_size_requested": spec["sample_size_requested"],
        "sample_size_used": len(spec["queries"]),
        "selection_policy": "stable source order after dataset-specific mapping policy",
        "skipped": dict(sorted(spec["skipped"].items())),
        "category_counts": dict(sorted(categories.items())),
        "temporary_dataset_committed": False,
        "raw_records_committed": False,
        "memory_chunks": len(spec["memories"]),
        "runs": runs,
        "summary": summarize_runs(runs, ablated_parameter),
    }
    report.update(spec.get("metadata") or {})
    return report


def main() -> int:
    args = parse_args()
    root = repo_root()
    os.environ["HF_ENDPOINT"] = args.endpoint
    os.environ["FASTEMBED_CACHE_DIR"] = str(args.fastembed_cache_dir)
    args.output = args.output if args.output.is_absolute() else root / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    args.fastembed_cache_dir.mkdir(parents=True, exist_ok=True)

    accelerator = configure_accelerator_environment(args)
    if args.fixed_reranker_pool <= 0:
        raise ValueError("--fixed-reranker-pool must be positive")
    reranker_pools = parse_int_list(args.reranker_pools, name="reranker-pools")
    top_k_values = parse_int_list(args.top_k_values, name="top-k-values")
    rrf_k_values = parse_float_list(args.rrf_k_values, name="rrf-k-values")
    vector_weights = parse_float_list(args.vector_weights, name="vector-weights")
    api = HfApi(endpoint=args.endpoint)
    specs, cleanup_paths = build_dataset_specs(args, api)
    ablated_parameter = {
        "reranker-pool": "reranker_pool",
        "top-k": "top_k",
        "rrf-k": "rrf_k",
        "vector-weight": "vector_weight",
    }[args.ablation]

    with tempfile.TemporaryDirectory(prefix="king-synapse-ranking-ablation-") as temp:
        temp_dir = Path(temp)
        for spec in specs:
            dataset_path = temp_dir / spec["toml_name"]
            write_toml_dataset(dataset_path, spec["memories"], spec["queries"])
            if args.ablation == "reranker-pool":
                spec["runs"] = run_reranker_pool_ablation(
                    dataset_path=dataset_path,
                    output_dir=temp_dir,
                    tag_base=spec["tag_base"],
                    examples=spec["examples"],
                    k=args.k,
                    reranker_pools=reranker_pools,
                )
            elif args.ablation == "top-k":
                spec["runs"] = run_top_k_ablation(
                    dataset_path=dataset_path,
                    output_dir=temp_dir,
                    tag_base=spec["tag_base"],
                    examples=spec["examples"],
                    top_k_values=top_k_values,
                    reranker_pool=args.fixed_reranker_pool,
                )
            elif args.ablation == "rrf-k":
                spec["runs"] = run_rrf_k_ablation(
                    dataset_path=dataset_path,
                    output_dir=temp_dir,
                    tag_base=spec["tag_base"],
                    examples=spec["examples"],
                    k=args.k,
                    rrf_k_values=rrf_k_values,
                    reranker_pool=args.fixed_reranker_pool,
                )
            else:
                spec["runs"] = run_vector_weight_ablation(
                    dataset_path=dataset_path,
                    output_dir=temp_dir,
                    tag_base=spec["tag_base"],
                    examples=spec["examples"],
                    k=args.k,
                    vector_weights=vector_weights,
                    reranker_pool=args.fixed_reranker_pool,
                )

    report = {
        "schema_version": "king-synapse.ranking-ablation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_ablation.py",
        "endpoint": args.endpoint,
        "cache_policy": {
            "cache_root_recorded": False,
            "fastembed_cache_dir_recorded": False,
            "fastembed_cache_configured": True,
            "raw_cache_retained": not args.cleanup_cache,
            "raw_records_committed": False,
        },
        "ablation": {
            "parameter": ablated_parameter,
            "values": (
                reranker_pools
                if args.ablation == "reranker-pool"
                else top_k_values
                if args.ablation == "top-k"
                else rrf_k_values
                if args.ablation == "rrf-k"
                else vector_weights
            ),
            "fixed": {
                "k": None if args.ablation == "top-k" else args.k,
                "reranker_pool": None if args.ablation == "reranker-pool" else args.fixed_reranker_pool,
                "rrf_k": None if args.ablation == "rrf-k" else DEFAULT_RRF_K,
                "fts_weight": DEFAULT_BRANCH_WEIGHT,
                "entity_weight": DEFAULT_BRANCH_WEIGHT,
                "vector_weight": None if args.ablation == "vector-weight" else DEFAULT_BRANCH_WEIGHT,
                "vectors": True,
                "rerank": True,
            },
            "one_variable_policy": True,
        },
        "accelerator": accelerator,
        "datasets": [dataset_report(spec, spec["runs"], ablated_parameter) for spec in specs],
        "limits": [
            f"This pass varies {ablated_parameter} only; top-k, chunking, and query expansion stay fixed.",
            "RRF k and branch weights are now exposed in kr-eval and can be swept independently.",
            "Report excludes raw questions, answers, dialogs, and session text.",
            "Results are ranking evidence, not official answer-generation DMR scores.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.cleanup_cache:
        for path in cleanup_paths:
            if path.exists():
                shutil.rmtree(path)

    print(
        json.dumps(
            {
                "output": str(args.output),
                "datasets": {spec["id"]: len(spec["queries"]) for spec in specs},
                "ablation": ablated_parameter,
                "values": reranker_pools if args.ablation == "reranker-pool" else top_k_values,
                "accelerator": accelerator,
                "cleanup_cache": args.cleanup_cache,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
