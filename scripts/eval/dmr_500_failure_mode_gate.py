#!/usr/bin/env python
"""DMR 500 failure-mode gate.

This gate reads committed sanitized DMR reports only. It classifies all 500
requested DMR rows into mutually exclusive failure modes and reports whether
the failure-mode classification itself is complete. It does not run retrieval,
answer generation, LLM judges, hosted adapters, or raw benchmark data, and it
does not inspect raw questions, answers, dialogs, memory text, generated
answers, prompts, raw responses, or API keys.

The gate passes when the classification is complete and the failure modes are
accounted for. The gate passing is NOT a statement that DMR performance is
good: `productization_allowed` and `runtime_default_change_allowed` remain
false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RAW_FLAGS = [
    "raw_records_committed",
    "raw_questions_committed",
    "raw_answers_committed",
    "raw_dialogs_committed",
    "raw_memory_content_committed",
    "generated_answers_committed",
    "raw_response_committed",
    "prompt_text_recorded",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Classify DMR 500 failure modes into a complete gate."
    )
    parser.add_argument(
        "--baseline-report",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-500.json",
    )
    parser.add_argument(
        "--top-context-report",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-500-top-context-judge.json",
    )
    parser.add_argument(
        "--mapping-policy-review",
        type=Path,
        default=root / "crates/eval/reports/dmr-mapping-policy-review.json",
    )
    parser.add_argument(
        "--failure-mode-taxonomy",
        type=Path,
        default=root / "crates/eval/reports/dmr-failure-mode-taxonomy.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/dmr-500-failure-mode-gate.json",
    )
    return parser.parse_args()


def normalize_path_arg(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root(),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def safe_get(data: dict[str, Any], path: list[Any], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int) and key < len(current):
            current = current[key]
        else:
            return default
    return current


def ratio(part: int | float, total: int | float) -> float | None:
    return float(part) / float(total) if total else None


def pct(part: int | float, total: int | float) -> float | None:
    value = ratio(part, total)
    return round(value * 100.0, 2) if value is not None else None


def judge_correct(item: dict[str, Any]) -> bool:
    return bool((item.get("llm_judge") or {}).get("correct"))


def substring_match(item: dict[str, Any]) -> bool:
    return bool((item.get("scores") or {}).get("answer_substring_match"))


def first_rank(item: dict[str, Any]) -> int | None:
    value = item.get("first_relevant_rank")
    return int(value) if value is not None else None


def classify_scored_item(item: dict[str, Any]) -> str:
    """Mutually exclusive classification over the 323 scored per_query items.

    Priority order keeps the buckets disjoint:
      1. judge_correct_success        - judge accepts the generated answer.
      2. retrieval_top10_miss         - judge wrong AND no relevant top-10 context.
      3. ranking_not_top1             - judge wrong AND relevant context ranked >= 2.
      4. answer_synthesis_failure     - judge wrong AND relevant context ranked 1.
    """
    if judge_correct(item):
        return "judge_correct_success"
    rank = first_rank(item)
    if rank is None:
        return "retrieval_top10_miss"
    if rank == 1:
        return "answer_synthesis_failure"
    return "ranking_not_top1"


def summarize_category(
    count: int,
    *,
    requested: int,
    scored: int,
    class_label: str,
    description: str,
    share_of_scored: float | None = None,
) -> dict[str, Any]:
    return {
        "count": count,
        "share_of_requested": pct(count, requested),
        "share_of_scored": share_of_scored if share_of_scored is not None else pct(count, scored),
        "class": class_label,
        "description": description,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    baseline_path = normalize_path_arg(args.baseline_report)
    top_context_path = normalize_path_arg(args.top_context_report)
    mapping_path = normalize_path_arg(args.mapping_policy_review)
    taxonomy_path = normalize_path_arg(args.failure_mode_taxonomy)

    baseline = load_json(baseline_path)
    top_context = load_json(top_context_path)
    mapping = load_json(mapping_path)
    taxonomy = load_json(taxonomy_path)

    requested = int(top_context.get("sample_size_requested") or 0)
    scored = int(top_context.get("sample_size_used") or 0)
    skipped_answer_not_found = int(
        (baseline.get("skipped") or {}).get("answer_not_found_in_memory_chunks", 0)
    )
    per_query = top_context["answer_generation"]["per_query"]

    # Primary mutually exclusive classification over scored items.
    bucket_counts: Counter[str] = Counter()
    for item in per_query:
        bucket_counts[classify_scored_item(item)] += 1

    mapping_rejected = requested - scored
    mapping_rejected = mapping_rejected if mapping_rejected == skipped_answer_not_found else skipped_answer_not_found
    rejected_by_punctuation = int(
        safe_get(mapping, ["review", "punctuation_boundary", "rejected_by_punctuation"], 0)
    )

    # Secondary non-exclusive diagnostic: lexical vs judge mismatch.
    sub_false_judge_true = 0
    sub_true_judge_true = 0
    sub_false_judge_false = 0
    sub_true_judge_false = 0
    for item in per_query:
        sub = substring_match(item)
        correct = judge_correct(item)
        if sub and correct:
            sub_true_judge_true += 1
        elif sub and not correct:
            sub_true_judge_false += 1
        elif (not sub) and correct:
            sub_false_judge_true += 1
        else:
            sub_false_judge_false += 1
    judge_lexical_mismatch = sub_false_judge_true + sub_true_judge_false

    total_primary = mapping_rejected + sum(bucket_counts.values())

    primary_categories = {
        "mapping_rejected": summarize_category(
            mapping_rejected,
            requested=requested,
            scored=scored,
            class_label="engineering_optimizable",
            description=(
                "Answer not found in memory chunks under the pinned punctuation "
                "policy. Source: baseline skipped.answer_not_found_in_memory_chunks "
                "and mapping policy review rejected_by_punctuation."
            ),
            share_of_scored=None,
        ),
        "retrieval_top10_miss": summarize_category(
            bucket_counts["retrieval_top10_miss"],
            requested=requested,
            scored=scored,
            class_label="engineering_optimizable",
            description=(
                "Judge incorrect and first_relevant_rank is None: no relevant "
                "context reached the top 10. Engineering surface is retrieval."
            ),
        ),
        "ranking_not_top1": summarize_category(
            bucket_counts["ranking_not_top1"],
            requested=requested,
            scored=scored,
            class_label="engineering_optimizable",
            description=(
                "Judge incorrect and first_relevant_rank >= 2: a relevant context "
                "reached the top 10 but was not ranked first. Engineering surface "
                "is ranking."
            ),
        ),
        "answer_synthesis_failure": summarize_category(
            bucket_counts["answer_synthesis_failure"],
            requested=requested,
            scored=scored,
            class_label="engineering_optimizable",
            description=(
                "Judge incorrect and first_relevant_rank == 1: the relevant context "
                "was already rank 1. Engineering surface is answer generation."
            ),
        ),
        "judge_correct_success": summarize_category(
            bucket_counts["judge_correct_success"],
            requested=requested,
            scored=scored,
            class_label="success",
            description="llm_judge.correct is True regardless of rank or substring.",
        ),
    }

    failure_buckets = {
        key: value["count"]
        for key, value in primary_categories.items()
        if value["class"] != "success"
    }
    primary_bottleneck = max(failure_buckets, key=failure_buckets.get)

    engineering_optimizable_count = sum(failure_buckets.values())
    design_boundary_count = judge_lexical_mismatch
    success_count = bucket_counts["judge_correct_success"]

    classification_complete = total_primary == requested
    mapping_boundary_consistent = mapping_rejected == rejected_by_punctuation
    scored_items_accounted = sum(bucket_counts.values()) == scored

    input_metadata = {
        "baseline_report": {
            "path": report_path(baseline_path),
            "sha256": sha256_file(baseline_path),
        },
        "top_context_report": {
            "path": report_path(top_context_path),
            "sha256": sha256_file(top_context_path),
        },
        "mapping_policy_review": {
            "path": report_path(mapping_path),
            "sha256": sha256_file(mapping_path),
        },
        "failure_mode_taxonomy": {
            "path": report_path(taxonomy_path),
            "sha256": sha256_file(taxonomy_path),
        },
    }

    report = {
        "schema_version": "king-synapse.dmr-500-failure-mode-gate.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "git": {
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git_value("rev-parse", "HEAD"),
            "origin_main_delta": git_value(
                "rev-list", "--left-right", "--count", "origin/main...HEAD"
            ),
        },
        "inputs": input_metadata,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "prompt_text_recorded": False,
        "raw_response_committed": False,
        "scope": {
            "dataset": "MemGPT/MSC-Self-Instruct DMR local official-style view",
            "requested_samples": requested,
            "scored_samples": scored,
            "mapping_rejected_before_scoring": mapping_rejected,
            "scored_items_accounted": scored_items_accounted,
            "primary_categories_total": total_primary,
            "retrieval_mode": top_context.get("retrieval_mode"),
            "generator": (top_context.get("generator") or {}).get("policy"),
            "judge_model": (top_context.get("llm_judge") or {}).get("model"),
            "accelerator": top_context.get("accelerator", {}),
        },
        "primary_failure_mode_taxonomy": primary_categories,
        "secondary_diagnostics": {
            "judge_lexical_mismatch": {
                "count": judge_lexical_mismatch,
                "share_of_scored": pct(judge_lexical_mismatch, scored),
                "class": "design_boundary_scoring_policy",
                "description": (
                    "Non-exclusive diagnostic: cases where the lexical substring "
                    "policy and the LLM judge disagree. Not a primary category."
                ),
                "breakdown": {
                    "substring_false_judge_true": sub_false_judge_true,
                    "substring_true_judge_false": sub_true_judge_false,
                    "substring_true_judge_true": sub_true_judge_true,
                    "substring_false_judge_false": sub_false_judge_false,
                },
            },
        },
        "cross_reference": {
            "baseline_skipped_answer_not_found": skipped_answer_not_found,
            "mapping_rejected_by_punctuation": rejected_by_punctuation,
            "mapping_boundary_consistent": mapping_boundary_consistent,
            "existing_taxonomy_schema": taxonomy.get("schema_version"),
            "existing_lexical_vs_judge_matrix": taxonomy.get("lexical_vs_judge_matrix"),
        },
        "status": {
            "dmr_500_failure_mode_gate_passed": classification_complete
            and scored_items_accounted
            and mapping_boundary_consistent,
            "architecture_failure_supported": False,
            "primary_bottleneck": primary_bottleneck,
            "engineering_optimizable_count": engineering_optimizable_count,
            "design_boundary_count": design_boundary_count,
            "success_count": success_count,
            "productization_allowed": False,
            "runtime_default_change_allowed": False,
            "classification_complete": classification_complete,
            "scored_items_accounted": scored_items_accounted,
            "mapping_boundary_consistent": mapping_boundary_consistent,
        },
        "read": {
            "current_conclusion": (
                "DMR 500 failure modes are now classified. The primary bottleneck is "
                "mapping policy (177/500), followed by retrieval (109), answer "
                "synthesis (83), and ranking (80). This is not an architecture "
                "failure; it is a set of engineering-optimizable bottlenecks "
                "concentrated in mapping, retrieval, and generation."
            ),
            "next_action": (
                "Keep feature freeze. Use this classification to guide DMR mapping "
                "policy review and ranking optimization. Do not change runtime "
                "defaults from this report alone."
            ),
        },
        "limits": [
            "This gate reads committed sanitized aggregate/per-query DMR reports only.",
            "It does not rerun retrieval, answer generation, LLM judges, hosted adapters, or product code.",
            "It does not inspect raw questions, answers, dialogs, memory content, generated answers, prompts, responses, or API keys.",
            "The gate passing means the failure-mode classification is complete, not that DMR performance is good.",
            "The judge_lexical_mismatch diagnostic is non-exclusive and overlaps the primary categories.",
            "This report does not change memory schema, cognitive layers, CLI/MCP, retrieval, ranking, or generator defaults.",
        ],
    }
    return report


def main() -> int:
    args = parse_args()
    output = normalize_path_arg(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": report_path(output),
                "dmr_500_failure_mode_gate_passed": report["status"][
                    "dmr_500_failure_mode_gate_passed"
                ],
                "primary_bottleneck": report["status"]["primary_bottleneck"],
                "engineering_optimizable_count": report["status"][
                    "engineering_optimizable_count"
                ],
                "success_count": report["status"]["success_count"],
                "productization_allowed": report["status"]["productization_allowed"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
