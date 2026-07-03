#!/usr/bin/env python
"""DMR chunk-policy ablation for Phase 6 validation.

This runner varies the temporary DMR memory chunking policy only. It does not
change the Synapse recall engine, memory schema, product CLI, or default
ranking behavior. Raw DMR questions, answers, dialogs, sessions, and generated
temporary TOML datasets stay outside committed files.
"""

from __future__ import annotations

import argparse
import json
import os
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
    SMOKE_CONFIGS,
    build_dialog_chunk,
    configure_accelerator_environment,
    default_cache_root,
    default_fastembed_cache_dir,
    dmr_answer_matches,
    download_dataset,
    flatten_text,
    read_jsonl,
    repo_root,
    run_kr_eval,
    sanitize_eval_report,
    source_file_report,
    stable_hash,
    write_toml_dataset,
)


CHUNK_POLICIES = {
    "dialog": "current policy: previous dialogs and current payload are separate memory chunks",
    "merged-session": "one merged memory chunk per DMR source row",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sanitized DMR chunk-policy ablation.")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/ranking-ablation-dmr-50-chunk-policy.json",
    )
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument(
        "--dmr-answer-match",
        choices=tuple(DMR_ANSWER_MATCH_POLICIES),
        default="punctuation",
    )
    parser.add_argument(
        "--chunk-policies",
        default="dialog,merged-session",
        help="Comma-separated chunk policies: dialog, merged-session.",
    )
    parser.add_argument(
        "--mode",
        choices=tuple(config["id"] for config in SMOKE_CONFIGS),
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


def parse_chunk_policies(raw: str) -> list[str]:
    policies = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not policies:
        raise ValueError("at least one chunk policy is required")
    unknown = [policy for policy in policies if policy not in CHUNK_POLICIES]
    if unknown:
        raise ValueError(f"unknown chunk policy: {', '.join(unknown)}")
    return list(dict.fromkeys(policies))


def mode_config(mode: str) -> dict[str, Any]:
    for config in SMOKE_CONFIGS:
        if config["id"] == mode:
            return dict(config)
    raise ValueError(f"unknown mode: {mode}")


def current_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "personas": row.get("personas"),
        "dialog": row.get("dialog"),
        "summary_speaker_1": row.get("summary_speaker_1"),
        "summary_speaker_2": row.get("summary_speaker_2"),
    }


def row_parts(row_index: int, row: dict[str, Any]) -> dict[str, Any] | None:
    instruct = row.get("self_instruct") or {}
    question = instruct.get("B")
    answer = instruct.get("A")
    if not question or not answer:
        return None
    metadata = row.get("metadata") or {}
    row_id = str(metadata.get("session_id") or metadata.get("initial_data_id") or row_index)
    row_token = f"{row_index}:{row_id}:{stable_hash(str(question) + str(answer))}"
    return {
        "row": row,
        "row_token": row_token,
        "question": str(question),
        "answer": str(answer),
        "sample_id": stable_hash(f"{DMR_REPO}:{row_token}"),
    }


def build_chunks(row_token: str, row: dict[str, Any], policy: str) -> list[dict[str, str]]:
    if policy == "dialog":
        chunks: list[dict[str, str]] = []
        for prev_index, previous in enumerate(row.get("previous_dialogs") or []):
            chunk = build_dialog_chunk(row_token, f"previous_{prev_index}", previous)
            if chunk["content"]:
                chunks.append(chunk)
        current_chunk = build_dialog_chunk(row_token, "current", current_payload(row))
        if current_chunk["content"]:
            chunks.append(current_chunk)
        return chunks

    if policy == "merged-session":
        merged_content = flatten_text(
            {
                "previous_dialogs": row.get("previous_dialogs"),
                "current": current_payload(row),
            }
        )
        if not merged_content:
            return []
        return [
            {
                "key": f"dmr_{stable_hash(row_token)}_merged",
                "content": merged_content,
            }
        ]

    raise ValueError(f"unknown chunk policy: {policy}")


def relevant_keys(answer: str, chunks: list[dict[str, str]], answer_match_policy: str) -> list[str]:
    return [
        chunk["key"]
        for chunk in chunks
        if dmr_answer_matches(answer, chunk["content"], answer_match_policy)
    ]


def select_dialog_mapped_rows(
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
    chunk_policy: str,
    answer_match_policy: str,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    memories: list[dict[str, str]] = []
    queries: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()

    for selected in selected_rows:
        chunks = build_chunks(selected["row_token"], selected["row"], chunk_policy)
        if not chunks:
            skipped["no_memory_chunks"] += 1
            continue
        relevant = relevant_keys(selected["answer"], chunks, answer_match_policy)
        if not relevant:
            skipped["answer_not_found_in_policy_chunks"] += 1
            continue

        memories.extend(chunks)
        queries.append({"query": selected["question"], "relevant": relevant})
        examples.append(
            {
                "sample_id": selected["sample_id"],
                "category": "dmr-candidate",
                "source_session_count": len(chunks),
                "relevant_count": len(relevant),
            }
        )

    return memories, queries, examples, skipped


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant_id": run.get("variant_id"),
        "chunk_policy": run.get("chunk_policy"),
        "memory_chunks": run.get("memory_chunks"),
        "sample_size_used": run.get("sample_size_used"),
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


def count_bucket(run: dict[str, Any], bucket: str) -> int:
    return int((run.get("rank_bucket_counts") or {}).get(bucket, 0))


def count_failure(run: dict[str, Any], failure: str) -> int:
    return int((run.get("failure_type_counts") or {}).get(failure, 0))


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {}
    control = next((run for run in runs if run.get("chunk_policy") == "dialog"), runs[0])
    best_recall = max(runs, key=lambda item: (item.get("recall_at_10") or 0.0, item.get("mrr_at_10") or 0.0))
    best_mrr = max(runs, key=lambda item: (item.get("mrr_at_10") or 0.0, item.get("recall_at_10") or 0.0))
    return {
        "control_variant": compact_run(control),
        "best_by_recall_at_10": compact_run(best_recall),
        "best_by_mrr_at_10": compact_run(best_mrr),
        "deltas_vs_control": [
            {
                "variant_id": run["variant_id"],
                "chunk_policy": run["chunk_policy"],
                "recall_at_10_delta": safe_delta(run.get("recall_at_10"), control.get("recall_at_10")),
                "mrr_at_10_delta": safe_delta(run.get("mrr_at_10"), control.get("mrr_at_10")),
                "p50_latency_ms_delta": safe_delta(run.get("p50_latency_ms"), control.get("p50_latency_ms")),
                "memory_chunks_delta": int(run.get("memory_chunks", 0)) - int(control.get("memory_chunks", 0)),
                "top_1_delta": count_bucket(run, "top_1") - count_bucket(control, "top_1"),
                "top_10_delta": count_bucket(run, "top_10") - count_bucket(control, "top_10"),
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

    chunk_policies = parse_chunk_policies(args.chunk_policies)
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
    selected_rows, selection_skipped = select_dialog_mapped_rows(
        rows, args.sample_size, args.dmr_answer_match
    )
    if not selected_rows:
        raise RuntimeError("DMR chunk-policy ablation sample is empty")

    runs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="king-synapse-dmr-chunk-ablation-") as temp:
        temp_dir = Path(temp)
        for policy in chunk_policies:
            memories, queries, examples, skipped = build_variant_dataset(
                selected_rows, policy, args.dmr_answer_match
            )
            if not queries:
                raise RuntimeError(f"chunk policy {policy} produced no queries")
            dataset_path = temp_dir / f"dmr-chunk-{policy}.toml"
            raw_output = temp_dir / f"dmr-chunk-{policy}-raw-report.json"
            write_toml_dataset(dataset_path, memories, queries)
            tag = f"dmr-chunk-{policy}-{args.mode}"
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
                    "variant_id": f"chunk-policy-{policy}",
                    "ablated_parameter": "chunk_policy",
                    "ablated_value": policy,
                    "chunk_policy": policy,
                    "chunk_policy_description": CHUNK_POLICIES[policy],
                    "mode": config["id"],
                    "label": f"{config['label']} with {policy} chunks",
                    "tag": raw.get("tag"),
                    "sample_size_used": len(queries),
                    "memory_chunks": len(memories),
                    "skipped": dict(sorted(skipped.items())),
                }
            )
            runs.append(run)

    report = {
        "schema_version": "king-synapse.dmr-chunk-ablation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/dmr_chunk_ablation.py",
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
            "parameter": "chunk_policy",
            "values": chunk_policies,
            "control": "dialog",
            "one_variable_policy": True,
        },
        "fixed": {
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
            "This pass varies only temporary DMR memory chunk policy.",
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
                "chunk_policies": chunk_policies,
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
