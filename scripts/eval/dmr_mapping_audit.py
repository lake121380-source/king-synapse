#!/usr/bin/env python
"""Audit DMR candidate answer-to-memory mapping.

This script downloads the public DMR candidate source into the user cache and
writes only anonymized aggregate statistics. It does not run `kr-eval`, does
not invoke embedding or reranker models, and must not commit raw third-party
records.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

from longmem_dmr_smoke import (
    DMR_FILE,
    DMR_REPO,
    dataset_info,
    default_cache_root,
    download_dataset,
    flatten_text,
    read_jsonl,
    repo_root,
    sha256_file,
    stable_hash,
)


STOP_WORDS = {
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
    "being",
    "before",
    "but",
    "by",
    "did",
    "do",
    "does",
    "during",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "him",
    "his",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "me",
    "my",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "over",
    "she",
    "that",
    "the",
    "their",
    "them",
    "then",
    "these",
    "they",
    "this",
    "those",
    "to",
    "was",
    "we",
    "were",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "with",
    "within",
    "without",
    "yes",
    "you",
    "your",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit DMR candidate mapping without running retrieval.")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/dmr-mapping-audit.json",
    )
    parser.add_argument("--target-valid-rows", type=int, default=50)
    parser.add_argument("--example-limit", type=int, default=20)
    parser.add_argument("--cleanup-cache", action="store_true")
    return parser.parse_args()


def norm_whitespace(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def norm_punctuation(value: Any) -> str:
    return " ".join(re.findall(r"[\w]+", str(value).casefold()))


def tokens(value: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(value).casefold())


def significant_tokens(value: Any) -> list[str]:
    return [token for token in tokens(value) if len(token) >= 3 and token not in STOP_WORDS]


def answer_token_bucket(count: int) -> str:
    if count <= 3:
        return "1-3"
    if count <= 8:
        return "4-8"
    if count <= 16:
        return "9-16"
    if count <= 32:
        return "17-32"
    return "33+"


def ratio_bucket(value: float) -> str:
    if value == 0:
        return "0"
    if value < 0.25:
        return "0.01-0.24"
    if value < 0.5:
        return "0.25-0.49"
    if value < 0.75:
        return "0.50-0.74"
    if value < 1:
        return "0.75-0.99"
    return "1.00"


def build_labeled_chunks(row: dict[str, Any]) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for previous in row.get("previous_dialogs") or []:
        content = flatten_text(previous)
        if content:
            chunks.append({"label": "previous", "content": content})

    current_payload = {
        "personas": row.get("personas"),
        "dialog": row.get("dialog"),
        "summary_speaker_1": row.get("summary_speaker_1"),
        "summary_speaker_2": row.get("summary_speaker_2"),
    }
    current_content = flatten_text(current_payload)
    if current_content:
        chunks.append({"label": "current", "content": current_content})
    return chunks


def row_token(row_index: int, row: dict[str, Any], question: Any, answer: Any) -> str:
    metadata = row.get("metadata") or {}
    row_id = str(metadata.get("session_id") or metadata.get("initial_data_id") or row_index)
    return f"{row_index}:{row_id}:{stable_hash(str(question) + str(answer))}"


def source_bucket(labels: set[str]) -> str:
    if labels == {"previous"}:
        return "previous_only"
    if labels == {"current"}:
        return "current_only"
    if labels == {"previous", "current"}:
        return "both_previous_and_current"
    if not labels:
        return "no_current_exact_match"
    return "other"


def analyze_rows(rows: list[dict[str, Any]], target_valid_rows: int, example_limit: int) -> dict[str, Any]:
    full_counts: Counter[str] = Counter()
    first_valid_window: Counter[str] = Counter()
    chunk_count_distribution: Counter[str] = Counter()
    exact_match_source_rows: Counter[str] = Counter()
    accepted_relevant_chunk_count_distribution: Counter[str] = Counter()
    skipped_answer_token_buckets: Counter[str] = Counter()
    skipped_overlap_buckets: Counter[str] = Counter()
    skipped_examples: list[dict[str, Any]] = []

    accepted_rows = 0
    skipped_before_target_valid_rows = 0
    punctuation_recoverable_skips = 0
    all_significant_tokens_present_skips = 0
    any_significant_token_present_skips = 0
    no_significant_answer_token_skips = 0

    for row_index, row in enumerate(rows):
        instruct = row.get("self_instruct") or {}
        question = instruct.get("B")
        answer = instruct.get("A")
        if not question or not answer:
            full_counts["missing_question_or_answer"] += 1
            if accepted_rows < target_valid_rows:
                first_valid_window["missing_question_or_answer"] += 1
            continue

        full_counts["with_question_and_answer"] += 1
        chunks = build_labeled_chunks(row)
        if not chunks:
            full_counts["empty_memory_chunks"] += 1
            if accepted_rows < target_valid_rows:
                first_valid_window["empty_memory_chunks"] += 1
            continue

        chunk_count_distribution[str(len(chunks))] += 1
        answer_ws = norm_whitespace(answer)
        answer_punct = norm_punctuation(answer)
        answer_sig = set(significant_tokens(answer))
        answer_token_count = len(tokens(answer))

        exact_labels: set[str] = set()
        punctuation_labels: set[str] = set()
        significant_token_labels: set[str] = set()
        max_overlap = 0.0

        for chunk in chunks:
            content = chunk["content"]
            content_sig = set(significant_tokens(content))
            if answer_ws and answer_ws in norm_whitespace(content):
                exact_labels.add(chunk["label"])
            if answer_punct and answer_punct in norm_punctuation(content):
                punctuation_labels.add(chunk["label"])
            if answer_sig:
                overlap = len(answer_sig & content_sig) / len(answer_sig)
                max_overlap = max(max_overlap, overlap)
                if answer_sig <= content_sig:
                    significant_token_labels.add(chunk["label"])

        if exact_labels:
            full_counts["accepted_current_exact"] += 1
            accepted_rows += 1
            exact_match_source_rows[source_bucket(exact_labels)] += 1
            accepted_relevant_chunk_count_distribution[str(len(exact_labels))] += 1
            if accepted_rows <= target_valid_rows:
                first_valid_window["accepted_current_exact"] += 1
            continue

        full_counts["skipped_answer_not_found_current_exact"] += 1
        skipped_answer_token_buckets[answer_token_bucket(answer_token_count)] += 1
        skipped_overlap_buckets[ratio_bucket(max_overlap)] += 1

        if punctuation_labels:
            punctuation_recoverable_skips += 1
        if not answer_sig:
            no_significant_answer_token_skips += 1
        if significant_token_labels:
            all_significant_tokens_present_skips += 1
        if max_overlap > 0:
            any_significant_token_present_skips += 1

        if len(skipped_examples) < example_limit:
            token = row_token(row_index, row, question, answer)
            skipped_examples.append(
                {
                    "sample_id": stable_hash(f"{DMR_REPO}:{token}"),
                    "answer_token_bucket": answer_token_bucket(answer_token_count),
                    "chunk_count": len(chunks),
                    "punctuation_insensitive_exact_match": bool(punctuation_labels),
                    "all_significant_answer_tokens_present": bool(significant_token_labels),
                    "max_significant_token_overlap_bucket": ratio_bucket(max_overlap),
                }
            )

        if accepted_rows < target_valid_rows:
            skipped_before_target_valid_rows += 1
            first_valid_window["answer_not_found_in_memory_chunks"] += 1

    return {
        "target_valid_rows": target_valid_rows,
        "first_valid_window": dict(sorted(first_valid_window.items())),
        "full_dataset": {
            "counts": dict(sorted(full_counts.items())),
            "accepted_rows": accepted_rows,
            "skipped_rows": full_counts["skipped_answer_not_found_current_exact"],
            "skipped_rows_punctuation_insensitive_exact_match": punctuation_recoverable_skips,
            "skipped_rows_all_significant_answer_tokens_present": all_significant_tokens_present_skips,
            "skipped_rows_any_significant_answer_token_present": any_significant_token_present_skips,
            "skipped_rows_no_significant_answer_tokens": no_significant_answer_token_skips,
            "chunk_count_distribution": dict(sorted(chunk_count_distribution.items())),
        },
        "accepted_rows": {
            "exact_match_source_rows": dict(sorted(exact_match_source_rows.items())),
            "relevant_chunk_count_distribution": dict(sorted(accepted_relevant_chunk_count_distribution.items())),
        },
        "skipped_rows": {
            "answer_token_buckets": dict(sorted(skipped_answer_token_buckets.items())),
            "max_significant_token_overlap_buckets": dict(sorted(skipped_overlap_buckets.items())),
            "anonymized_examples": skipped_examples,
        },
    }


def source_file_report(path: Path, info: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo_id": DMR_REPO,
        "revision": info.get("revision"),
        "license": info.get("license"),
        "filename": DMR_FILE,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def remove_cache_dir(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise RuntimeError(f"refusing to remove unexpected cache path: {resolved_path}")
    if path.exists():
        shutil.rmtree(path)


def main() -> int:
    args = parse_args()
    root = repo_root()
    args.output = args.output if args.output.is_absolute() else root / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    os.environ["HF_ENDPOINT"] = args.endpoint

    api = HfApi(endpoint=args.endpoint)
    dmr_info = dataset_info(api, DMR_REPO)
    dmr_cache = args.cache_root / "dmr-mapping-audit"
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
    rows = read_jsonl(dmr_path)

    report = {
        "schema_version": "king-synapse.dmr-mapping-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/dmr_mapping_audit.py",
        "endpoint": args.endpoint,
        "source": source_file_report(dmr_path, dmr_info),
        "cache_policy": {
            "cache_root_recorded": False,
            "raw_cache_retained": not args.cleanup_cache,
            "raw_records_committed": False,
        },
        "criteria": {
            "current_exact": "casefold + whitespace-normalized full answer substring in generated memory chunks; same selection criterion as longmem_dmr_smoke.py",
            "punctuation_insensitive_exact": "diagnostic only; punctuation-stripped full answer substring",
            "significant_token_containment": "diagnostic only; all non-stopword answer tokens with length >= 3 present in a single chunk",
        },
        "audit": analyze_rows(rows, args.target_valid_rows, args.example_limit),
        "limits": [
            "This is a mapping audit, not a retrieval benchmark.",
            "Diagnostic recoverability counts are heuristics and are not scored as DMR hits.",
            "Report excludes raw questions, answers, dialogs, personas, summaries, and retrieved text.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.cleanup_cache:
        remove_cache_dir(dmr_cache, args.cache_root)

    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(rows),
                "accepted_rows": report["audit"]["full_dataset"]["accepted_rows"],
                "skipped_rows": report["audit"]["full_dataset"]["skipped_rows"],
                "cleanup_cache": args.cleanup_cache,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
