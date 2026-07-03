#!/usr/bin/env python
"""DMR query-expansion ablation for Phase 6 validation.

This runner varies the temporary evaluation query text only. It does not change
the Synapse recall engine, memory schema, product CLI, or default ranking
behavior. Query expansion is derived from the question text alone; it does not
read gold answers or memory chunks.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

from dmr_chunk_ablation import build_chunks, mode_config, relevant_keys, row_parts
from longmem_dmr_smoke import (
    DMR_ANSWER_MATCH_POLICIES,
    DMR_FILE,
    DMR_REPO,
    configure_accelerator_environment,
    default_cache_root,
    default_fastembed_cache_dir,
    download_dataset,
    read_jsonl,
    repo_root,
    run_kr_eval,
    sanitize_eval_report,
    source_file_report,
    write_toml_dataset,
)


QUERY_POLICIES = {
    "original": "current DMR question without evaluation-time expansion",
    "keyword-boost": "append question-derived content keywords twice; no gold-answer or memory access",
}

STOPWORDS = {
    "a",
    "about",
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "before",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sanitized DMR query-expansion ablation.")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/ranking-ablation-dmr-50-query-expansion.json",
    )
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument(
        "--dmr-answer-match",
        choices=tuple(DMR_ANSWER_MATCH_POLICIES),
        default="punctuation",
    )
    parser.add_argument(
        "--query-policies",
        default="original,keyword-boost",
        help="Comma-separated query policies: original, keyword-boost.",
    )
    parser.add_argument(
        "--mode",
        choices=("baseline-rrf", "vectors", "vectors-rerank"),
        default="vectors-rerank",
    )
    parser.add_argument("--k", type=int, default=50)
    parser.add_argument("--reranker-pool", type=int, default=50)
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


def parse_query_policies(raw: str) -> list[str]:
    policies = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not policies:
        raise ValueError("at least one query policy is required")
    unknown = [policy for policy in policies if policy not in QUERY_POLICIES]
    if unknown:
        raise ValueError(f"unknown query policy: {', '.join(unknown)}")
    return list(dict.fromkeys(policies))


def normalized_tokens(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.casefold())


def question_keywords(question: str) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []
    for token in normalized_tokens(question):
        if len(token) <= 2 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        keywords.append(token)
    return keywords[:16]


def expand_query(question: str, policy: str) -> tuple[str, dict[str, Any]]:
    if policy == "original":
        return question, {
            "expanded": False,
            "keyword_count": 0,
            "appended_token_count": 0,
        }

    if policy == "keyword-boost":
        keywords = question_keywords(question)
        appended = keywords + keywords
        if not appended:
            return question, {
                "expanded": False,
                "keyword_count": 0,
                "appended_token_count": 0,
            }
        return f"{question} {' '.join(appended)}", {
            "expanded": True,
            "keyword_count": len(keywords),
            "appended_token_count": len(appended),
        }

    raise ValueError(f"unknown query policy: {policy}")


def select_rows(
    rows: list[dict[str, Any]],
    sample_size: int,
    answer_match_policy: str,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    selected: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for row_index, row in enumerate(rows):
        parts = row_parts(row_index, row)
        if parts is None:
            skipped["missing_question_or_answer"] += 1
            continue
        chunks = build_chunks(parts["row_token"], row, "dialog")
        if not relevant_keys(parts["answer"], chunks, answer_match_policy):
            skipped["answer_not_found_in_dialog_chunks"] += 1
            continue
        selected.append(parts)
        if len(selected) >= sample_size:
            break
    return selected, skipped


def build_variant_dataset(
    selected_rows: list[dict[str, Any]],
    query_policy: str,
    answer_match_policy: str,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    memories: list[dict[str, str]] = []
    queries: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    expansion_stats: list[dict[str, Any]] = []

    for selected in selected_rows:
        chunks = build_chunks(selected["row_token"], selected["row"], "dialog")
        relevant = relevant_keys(selected["answer"], chunks, answer_match_policy)
        if not chunks or not relevant:
            continue

        query, stats = expand_query(selected["question"], query_policy)
        memories.extend(chunks)
        queries.append({"query": query, "relevant": relevant})
        examples.append(
            {
                "sample_id": selected["sample_id"],
                "category": "dmr-candidate",
                "source_session_count": len(chunks),
                "relevant_count": len(relevant),
            }
        )
        expansion_stats.append(stats)

    n = len(expansion_stats) or 1
    summary = {
        "queries_expanded": sum(1 for item in expansion_stats if item["expanded"]),
        "keyword_count_mean": sum(item["keyword_count"] for item in expansion_stats) / n,
        "appended_token_count_mean": sum(item["appended_token_count"] for item in expansion_stats) / n,
    }
    return memories, queries, examples, summary


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant_id": run.get("variant_id"),
        "query_policy": run.get("query_policy"),
        "recall_at_10": run.get("recall_at_10"),
        "mrr_at_10": run.get("mrr_at_10"),
        "ndcg_at_10": run.get("ndcg_at_10"),
        "p50_latency_ms": run.get("p50_latency_ms"),
        "p95_latency_ms": run.get("p95_latency_ms"),
        "rank_bucket_counts": run.get("rank_bucket_counts"),
        "failure_type_counts": run.get("failure_type_counts"),
        "query_expansion_stats": run.get("query_expansion_stats"),
    }


def safe_delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def count_bucket(run: dict[str, Any], bucket: str) -> int:
    return int((run.get("rank_bucket_counts") or {}).get(bucket, 0))


def count_failure(run: dict[str, Any], failure: str) -> int:
    return int((run.get("failure_type_counts") or {}).get(failure, 0))


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {}
    control = next((run for run in runs if run.get("query_policy") == "original"), runs[0])
    best_recall = max(runs, key=lambda item: (item.get("recall_at_10") or 0.0, item.get("mrr_at_10") or 0.0))
    best_mrr = max(runs, key=lambda item: (item.get("mrr_at_10") or 0.0, item.get("recall_at_10") or 0.0))
    return {
        "control_variant": compact_run(control),
        "best_by_recall_at_10": compact_run(best_recall),
        "best_by_mrr_at_10": compact_run(best_mrr),
        "deltas_vs_control": [
            {
                "variant_id": run["variant_id"],
                "query_policy": run["query_policy"],
                "recall_at_10_delta": safe_delta(run.get("recall_at_10"), control.get("recall_at_10")),
                "mrr_at_10_delta": safe_delta(run.get("mrr_at_10"), control.get("mrr_at_10")),
                "p50_latency_ms_delta": safe_delta(run.get("p50_latency_ms"), control.get("p50_latency_ms")),
                "top_1_delta": count_bucket(run, "top_1") - count_bucket(control, "top_1"),
                "top_10_delta": count_bucket(run, "top_10") - count_bucket(control, "top_10"),
                "top_50_delta": count_bucket(run, "top_50") - count_bucket(control, "top_50"),
                "retrieval_miss_delta": count_failure(run, "retrieval_miss") - count_failure(control, "retrieval_miss"),
            }
            for run in runs
        ],
    }


def main() -> int:
    args = parse_args()
    root = repo_root()
    os.environ["HF_ENDPOINT"] = args.endpoint
    os.environ["FASTEMBED_CACHE_DIR"] = str(args.fastembed_cache_dir)
    args.output = args.output if args.output.is_absolute() else root / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    args.fastembed_cache_dir.mkdir(parents=True, exist_ok=True)

    if args.sample_size <= 0:
        raise ValueError("--sample-size must be positive")
    if args.k <= 0:
        raise ValueError("--k must be positive")
    if args.reranker_pool <= 0:
        raise ValueError("--reranker-pool must be positive")

    query_policies = parse_query_policies(args.query_policies)
    accelerator = configure_accelerator_environment(args)
    config = mode_config(args.mode)
    if args.mode == "vectors-rerank":
        config["rerank_pool"] = args.reranker_pool

    api = HfApi(endpoint=args.endpoint)
    dmr_info = api.dataset_info(DMR_REPO)
    info = {
        "repo_id": DMR_REPO,
        "revision": getattr(dmr_info, "sha", None),
        "license": (
            dmr_info.card_data.get("license")
            if getattr(dmr_info, "card_data", None) is not None and hasattr(dmr_info.card_data, "get")
            else None
        ),
    }
    dmr_cache = args.cache_root / "dmr-msc-self-instruct"
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
    rows = read_jsonl(dmr_path)
    selected_rows, selection_skipped = select_rows(rows, args.sample_size, args.dmr_answer_match)
    if not selected_rows:
        raise RuntimeError("DMR query-expansion ablation sample is empty")

    runs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="king-synapse-dmr-query-ablation-") as temp:
        temp_dir = Path(temp)
        for policy in query_policies:
            memories, queries, examples, expansion_stats = build_variant_dataset(
                selected_rows, policy, args.dmr_answer_match
            )
            if not queries:
                raise RuntimeError(f"query policy {policy} produced no queries")
            dataset_path = temp_dir / f"dmr-query-{policy}.toml"
            raw_output = temp_dir / f"dmr-query-{policy}-raw-report.json"
            write_toml_dataset(dataset_path, memories, queries)
            tag = f"dmr-query-{policy}-{args.mode}"
            print(f"running {tag}...", flush=True)
            raw = run_kr_eval(
                dataset_path,
                raw_output,
                tag,
                args.k,
                vectors=bool(config["vectors"]),
                rerank=bool(config["rerank"]),
                rerank_pool=int(config["rerank_pool"]),
                rrf_k=60.0,
                fts_weight=1.0,
                entity_weight=1.0,
                vector_weight=1.0,
            )
            run = sanitize_eval_report(raw, examples)
            run.update(
                {
                    "variant_id": f"query-policy-{policy}",
                    "ablated_parameter": "query_policy",
                    "ablated_value": policy,
                    "query_policy": policy,
                    "query_policy_description": QUERY_POLICIES[policy],
                    "query_expansion_stats": expansion_stats,
                    "mode": config["id"],
                    "label": f"{config['label']} with {policy} query policy",
                    "tag": raw.get("tag"),
                    "sample_size_used": len(queries),
                    "memory_chunks": len(memories),
                }
            )
            runs.append(run)

    report = {
        "schema_version": "king-synapse.dmr-query-expansion-ablation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/dmr_query_expansion_ablation.py",
        "endpoint": args.endpoint,
        "source": source_file_report(DMR_REPO, DMR_FILE, dmr_path, info),
        "cache_policy": {
            "cache_root_recorded": False,
            "fastembed_cache_dir_recorded": False,
            "fastembed_cache_configured": True,
            "raw_cache_retained": not args.cleanup_cache,
            "raw_records_committed": False,
        },
        "sample_size_requested": args.sample_size,
        "sample_size_selected": len(selected_rows),
        "selection_policy": "stable source order after current dialog chunk punctuation mapping",
        "selection_skipped": dict(sorted(selection_skipped.items())),
        "answer_match_policy": args.dmr_answer_match,
        "answer_match_policy_description": DMR_ANSWER_MATCH_POLICIES[args.dmr_answer_match],
        "ablation": {
            "parameter": "query_policy",
            "values": query_policies,
            "control": "original",
            "one_variable_policy": True,
        },
        "fixed": {
            "chunk_policy": "dialog",
            "retrieval_mode": config["id"],
            "vectors": bool(config["vectors"]),
            "rerank": bool(config["rerank"]),
            "reranker_pool": int(config["rerank_pool"]),
            "k": args.k,
        },
        "accelerator": accelerator,
        "runs": runs,
        "summary": summarize_runs(runs),
        "limits": [
            "This pass varies only temporary evaluation query text.",
            "The keyword-boost policy uses question text only and does not read gold answers or memory chunks.",
            "It does not change Synapse memory schema, recall defaults, product CLI, or ranking semantics.",
            "Report excludes raw questions, answers, dialogs, sessions, generated text, and temporary TOML data.",
            "Results are retrieval/ranking evidence, not official DMR answer-generation scores.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.cleanup_cache and dmr_cache.exists():
        shutil.rmtree(dmr_cache)

    print(
        json.dumps(
            {
                "output": str(args.output),
                "sample_size_selected": len(selected_rows),
                "query_policies": query_policies,
                "mode": config["id"],
                "accelerator": accelerator,
                "cleanup_cache": args.cleanup_cache,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
