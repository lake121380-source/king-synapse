#!/usr/bin/env python
"""Review DMR answer-to-memory mapping policy coverage.

This script audits mapping policies only. It downloads the public DMR
candidate source into the user cache, builds the same memory chunks used by the
DMR candidate harness, and writes only anonymized aggregate statistics. It does
not run retrieval, embeddings, reranking, answer generation, or an LLM judge.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

from dmr_mapping_audit import (
    answer_token_bucket,
    build_labeled_chunks,
    norm_punctuation,
    norm_whitespace,
    ratio_bucket,
    significant_tokens,
    source_file_report,
    tokens,
)
from longmem_dmr_smoke import (
    DMR_FILE,
    DMR_REPO,
    dataset_info,
    default_cache_root,
    download_dataset,
    read_jsonl,
    repo_root,
    stable_hash,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review DMR mapping-policy coverage without retrieval.")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/dmr-mapping-policy-review.json",
    )
    parser.add_argument("--example-limit", type=int, default=20)
    parser.add_argument("--cleanup-cache", action="store_true")
    return parser.parse_args()


def remove_cache_dir(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise RuntimeError(f"refusing to remove unexpected cache path: {resolved_path}")
    if path.exists():
        shutil.rmtree(path)


def row_token(row_index: int, row: dict[str, Any], question: Any, answer: Any) -> str:
    metadata = row.get("metadata") or {}
    row_id = str(metadata.get("session_id") or metadata.get("initial_data_id") or row_index)
    return f"{row_index}:{row_id}:{stable_hash(str(question) + str(answer))}"


def policy_bools(answer: Any, chunks: list[dict[str, str]]) -> dict[str, Any]:
    answer_ws = norm_whitespace(answer)
    answer_punct = norm_punctuation(answer)
    answer_sig = set(significant_tokens(answer))
    max_overlap = 0.0

    strict = False
    punctuation = False
    token_containment = False
    any_significant_token = False

    for chunk in chunks:
        content = chunk["content"]
        content_sig = set(significant_tokens(content))
        if answer_ws and answer_ws in norm_whitespace(content):
            strict = True
        if answer_punct and answer_punct in norm_punctuation(content):
            punctuation = True
        if answer_sig:
            overlap = len(answer_sig & content_sig) / len(answer_sig)
            max_overlap = max(max_overlap, overlap)
            if overlap > 0:
                any_significant_token = True
            if answer_sig <= content_sig:
                token_containment = True

    return {
        "strict_whitespace_full_answer": strict,
        "punctuation_full_answer": punctuation,
        "significant_token_containment": token_containment,
        "any_significant_token": any_significant_token,
        "overlap_75": max_overlap >= 0.75,
        "overlap_50": max_overlap >= 0.5,
        "max_overlap": max_overlap,
        "answer_token_count": len(tokens(answer)),
        "answer_significant_token_count": len(answer_sig),
    }


def analyze_rows(rows: list[dict[str, Any]], example_limit: int) -> dict[str, Any]:
    total_rows = 0
    missing_question_or_answer = 0
    empty_memory_chunks = 0
    policy_counts: Counter[str] = Counter()
    first_policy_counts: Counter[str] = Counter()
    combinations: Counter[str] = Counter()
    not_punctuation_overlap_buckets: Counter[str] = Counter()
    not_punctuation_token_buckets: Counter[str] = Counter()
    not_punctuation_significant_token_buckets: Counter[str] = Counter()
    not_punctuation_examples: list[dict[str, Any]] = []

    policy_order = [
        "strict_whitespace_full_answer",
        "punctuation_full_answer",
        "significant_token_containment",
        "overlap_75",
        "overlap_50",
        "any_significant_token",
    ]

    for row_index, row in enumerate(rows):
        instruct = row.get("self_instruct") or {}
        question = instruct.get("B")
        answer = instruct.get("A")
        if not question or not answer:
            missing_question_or_answer += 1
            continue

        chunks = build_labeled_chunks(row)
        if not chunks:
            empty_memory_chunks += 1
            continue

        total_rows += 1
        policies = policy_bools(answer, chunks)

        active = [name for name in policy_order if policies[name]]
        combinations["+".join(active) if active else "none"] += 1
        for name in active:
            policy_counts[name] += 1

        for name in policy_order:
            if policies[name]:
                first_policy_counts[name] += 1
                break
        else:
            first_policy_counts["none"] += 1

        if not policies["punctuation_full_answer"]:
            not_punctuation_overlap_buckets[ratio_bucket(policies["max_overlap"])] += 1
            not_punctuation_token_buckets[answer_token_bucket(policies["answer_token_count"])] += 1
            not_punctuation_significant_token_buckets[
                answer_token_bucket(policies["answer_significant_token_count"])
            ] += 1
            if len(not_punctuation_examples) < example_limit:
                token = row_token(row_index, row, question, answer)
                not_punctuation_examples.append(
                    {
                        "sample_id": stable_hash(f"{DMR_REPO}:{token}"),
                        "answer_token_bucket": answer_token_bucket(policies["answer_token_count"]),
                        "answer_significant_token_bucket": answer_token_bucket(
                            policies["answer_significant_token_count"]
                        ),
                        "max_significant_token_overlap_bucket": ratio_bucket(policies["max_overlap"]),
                        "significant_token_containment": bool(policies["significant_token_containment"]),
                        "overlap_75": bool(policies["overlap_75"]),
                        "overlap_50": bool(policies["overlap_50"]),
                    }
                )

    punctuation_count = policy_counts["punctuation_full_answer"]
    strict_count = policy_counts["strict_whitespace_full_answer"]
    token_count = policy_counts["significant_token_containment"]
    overlap_75_count = policy_counts["overlap_75"]
    overlap_50_count = policy_counts["overlap_50"]
    any_token_count = policy_counts["any_significant_token"]

    return {
        "rows": {
            "source_rows": len(rows),
            "rows_with_question_answer_and_chunks": total_rows,
            "missing_question_or_answer": missing_question_or_answer,
            "empty_memory_chunks": empty_memory_chunks,
        },
        "policy_coverage": {
            "strict_whitespace_full_answer": strict_count,
            "punctuation_full_answer": punctuation_count,
            "significant_token_containment": token_count,
            "significant_token_overlap_75": overlap_75_count,
            "significant_token_overlap_50": overlap_50_count,
            "any_significant_token": any_token_count,
        },
        "policy_coverage_ratio": {
            "strict_whitespace_full_answer": strict_count / total_rows if total_rows else None,
            "punctuation_full_answer": punctuation_count / total_rows if total_rows else None,
            "significant_token_containment": token_count / total_rows if total_rows else None,
            "significant_token_overlap_75": overlap_75_count / total_rows if total_rows else None,
            "significant_token_overlap_50": overlap_50_count / total_rows if total_rows else None,
            "any_significant_token": any_token_count / total_rows if total_rows else None,
        },
        "incremental_first_match": dict(sorted(first_policy_counts.items())),
        "policy_combinations": dict(sorted(combinations.items())),
        "punctuation_boundary": {
            "accepted_by_punctuation": punctuation_count,
            "rejected_by_punctuation": total_rows - punctuation_count,
            "strict_subset_inside_punctuation": strict_count,
            "punctuation_added_over_strict": punctuation_count - strict_count,
            "token_containment_total": token_count,
            "token_containment_rejected_by_punctuation": first_policy_counts["significant_token_containment"],
            "overlap_75_rejected_by_punctuation_and_token_containment": first_policy_counts["overlap_75"],
            "overlap_50_rejected_by_punctuation_token_and_overlap75": first_policy_counts["overlap_50"],
            "any_token_rejected_by_stronger_policies": first_policy_counts["any_significant_token"],
            "no_diagnostic_match": first_policy_counts["none"],
            "rejected_by_punctuation_overlap_buckets": dict(sorted(not_punctuation_overlap_buckets.items())),
            "rejected_by_punctuation_answer_token_buckets": dict(sorted(not_punctuation_token_buckets.items())),
            "rejected_by_punctuation_significant_token_buckets": dict(
                sorted(not_punctuation_significant_token_buckets.items())
            ),
            "anonymized_rejected_examples": not_punctuation_examples,
        },
        "policy_read": {
            "strict_whitespace_full_answer": "Highest precision local mapping but too low coverage for larger official-style DMR runs.",
            "punctuation_full_answer": "Current pinned deterministic boundary; enough for 323/500 scored rows but not 500/500.",
            "significant_token_containment": "Higher coverage but can over-accept paraphrases or generic short answers; requires a separate label and judge/manual validation before scoring.",
            "overlap_thresholds": "Diagnostic only; useful for failure localization, not safe as a scoring selection policy by itself.",
        },
    }


def main() -> int:
    args = parse_args()
    root = repo_root()
    args.output = args.output if args.output.is_absolute() else root / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    os.environ["HF_ENDPOINT"] = args.endpoint

    api = HfApi(endpoint=args.endpoint)
    dmr_info = dataset_info(api, DMR_REPO)
    dmr_cache = args.cache_root / "dmr-mapping-policy-review"
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
    rows = read_jsonl(dmr_path)

    report = {
        "schema_version": "king-synapse.dmr-mapping-policy-review.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/dmr_mapping_policy_review.py",
        "endpoint": args.endpoint,
        "source": source_file_report(dmr_path, dmr_info),
        "cache_policy": {
            "cache_root_recorded": False,
            "raw_cache_retained": not args.cleanup_cache,
            "raw_records_committed": False,
        },
        "criteria": {
            "strict_whitespace_full_answer": "casefold + whitespace-normalized full answer substring in a generated memory chunk",
            "punctuation_full_answer": "casefold + punctuation-normalized full answer substring in a generated memory chunk",
            "significant_token_containment": "all non-stopword answer tokens with length >= 3 present in one generated memory chunk",
            "overlap_thresholds": "max significant-token overlap in one generated memory chunk",
        },
        "review": analyze_rows(rows, args.example_limit),
        "limits": [
            "This is a mapping-policy review, not a retrieval benchmark.",
            "Relaxed token policies are diagnostic unless separately labeled and validated.",
            "Report excludes raw questions, answers, dialogs, personas, summaries, and memory chunk text.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.cleanup_cache:
        remove_cache_dir(dmr_cache, args.cache_root)

    review = report["review"]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": review["rows"]["rows_with_question_answer_and_chunks"],
                "punctuation_full_answer": review["policy_coverage"]["punctuation_full_answer"],
                "rejected_by_punctuation": review["punctuation_boundary"]["rejected_by_punctuation"],
                "significant_token_containment": review["policy_coverage"]["significant_token_containment"],
                "cleanup_cache": args.cleanup_cache,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
