#!/usr/bin/env python
"""Sanitized official-style DMR answer-synthesis audit.

This script reads existing official DMR answer-generation reports and explains
whether low answer scores come from retrieval misses or from the deterministic
extractive generator failing after a relevant chunk was already returned.

It only uses sanitized fields already present in the reports: sample IDs, ranks,
lengths, hashes, generation trace metadata, and aggregate scores. It does not
read raw questions, answers, dialogs, sessions, memory content, or generated
answer text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Audit sanitized official DMR answer synthesis.")
    parser.add_argument(
        "--reports",
        nargs="+",
        type=Path,
        default=[
            root / "crates/eval/reports/official-dmr-50.json",
            root / "crates/eval/reports/official-dmr-200.json",
            root / "crates/eval/reports/official-dmr-500.json",
        ],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-answer-synthesis-audit.json",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rank_bucket(rank: int | None) -> str:
    if rank == 1:
        return "top1"
    if rank is not None and rank <= 10:
        return "top10_not_top1"
    return "not_retrieved_top10"


def alignment(item: dict[str, Any]) -> str:
    first_rank = item.get("first_relevant_rank")
    selected_rank = item.get("generation_trace", {}).get("selected_context_rank")
    if first_rank is None:
        return "no_relevant_context_in_top10"
    if selected_rank is None:
        return "no_context_selected"
    if selected_rank == first_rank:
        return "selected_first_relevant_context"
    if selected_rank < first_rank:
        return "selected_before_first_relevant_context"
    return "selected_after_first_relevant_context"


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(items)
    if n == 0:
        return {
            "count": 0,
            "exact_accuracy": None,
            "punctuation_accuracy": None,
            "answer_substring_accuracy": None,
            "rouge_l_f1_mean": None,
            "rouge_l_recall_mean": None,
            "generated_length_mean": None,
            "gold_length_mean": None,
            "alignment_counts": {},
        }

    exact = sum(1 for item in items if item["scores"]["exact_match"])
    punctuation = sum(1 for item in items if item["scores"]["punctuation_match"])
    substring = sum(1 for item in items if item["scores"]["answer_substring_match"])
    return {
        "count": n,
        "exact_accuracy": exact / n,
        "punctuation_accuracy": punctuation / n,
        "answer_substring_accuracy": substring / n,
        "rouge_l_f1_mean": mean([item["scores"]["rouge_l"]["f1"] for item in items]),
        "rouge_l_recall_mean": mean([item["scores"]["rouge_l"]["recall"] for item in items]),
        "generated_length_mean": mean([float(item["generated_answer_length"]) for item in items]),
        "gold_length_mean": mean([float(item["gold_answer_length"]) for item in items]),
        "alignment_counts": dict(sorted(Counter(alignment(item) for item in items).items())),
    }


def compact_case(item: dict[str, Any]) -> dict[str, Any]:
    trace = item.get("generation_trace", {})
    return {
        "sample_id": item["sample_id"],
        "rank_bucket": rank_bucket(item.get("first_relevant_rank")),
        "first_relevant_rank": item.get("first_relevant_rank"),
        "selected_context_rank": trace.get("selected_context_rank"),
        "selected_sentence_rank": trace.get("selected_sentence_rank"),
        "retrieved_context_count": item.get("retrieved_context_count"),
        "relevant_count": item.get("relevant_count"),
        "generated_answer_length": item.get("generated_answer_length"),
        "gold_answer_length": item.get("gold_answer_length"),
        "answer_substring_match": item["scores"]["answer_substring_match"],
        "rouge_l_f1": item["scores"]["rouge_l"]["f1"],
        "alignment": alignment(item),
    }


def audit_report(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    items = report["answer_generation"]["per_query"]
    bucketed: dict[str, list[dict[str, Any]]] = {
        "top1": [],
        "top10_not_top1": [],
        "not_retrieved_top10": [],
    }
    for item in items:
        bucketed[rank_bucket(item.get("first_relevant_rank"))].append(item)

    top1_misses = [
        item
        for item in bucketed["top1"]
        if not item["scores"]["answer_substring_match"]
    ]
    top10_misses = [
        item
        for item in bucketed["top1"] + bucketed["top10_not_top1"]
        if not item["scores"]["answer_substring_match"]
    ]
    wrong_context_after_top1 = [
        item
        for item in bucketed["top1"]
        if item.get("generation_trace", {}).get("selected_context_rank") != 1
    ]

    return {
        "report": report_path(path),
        "schema_version": report.get("schema_version"),
        "sample_size_requested": report.get("sample_size_requested"),
        "sample_size_used": report.get("sample_size_used"),
        "retrieval_mode": report.get("retrieval_mode"),
        "generator_policy": report.get("generator", {}).get("policy"),
        "llm_judge_status_counts": report["answer_generation"]["aggregate"].get(
            "llm_judge_status_counts", {}
        ),
        "llm_judge_accuracy": report["answer_generation"]["aggregate"].get(
            "llm_judge_accuracy"
        ),
        "retrieval": {
            "recall_at_10": report["retrieval"].get("recall_at_10"),
            "mrr_at_10": report["retrieval"].get("mrr_at_10"),
            "top1_count": len(bucketed["top1"]),
            "top10_not_top1_count": len(bucketed["top10_not_top1"]),
            "not_retrieved_top10_count": len(bucketed["not_retrieved_top10"]),
        },
        "answer_generation": {
            "overall": summarize(items),
            "by_retrieval_bucket": {
                bucket: summarize(bucket_items) for bucket, bucket_items in bucketed.items()
            },
            "opportunity_loss": {
                "top1_without_answer_substring_count": len(top1_misses),
                "top10_without_answer_substring_count": len(top10_misses),
                "top1_selected_non_first_context_count": len(wrong_context_after_top1),
            },
        },
        "sanitized_case_samples": {
            "top1_without_answer_substring": [compact_case(item) for item in top1_misses[:20]],
            "top10_without_answer_substring": [compact_case(item) for item in top10_misses[:20]],
            "not_retrieved_top10": [
                compact_case(item) for item in bucketed["not_retrieved_top10"][:20]
            ],
        },
    }


def combined_summary(audits: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "reports": len(audits),
        "sample_sets_overlap": True,
        "overlap_note": "Input reports may be deterministic expansions or generator variants; do not sum report rows as independent unique examples unless the inputs are known disjoint.",
        "total_report_rows": sum(int(audit["sample_size_used"]) for audit in audits),
        "top1_without_answer_substring_report_rows": sum(
            audit["answer_generation"]["opportunity_loss"][
                "top1_without_answer_substring_count"
            ]
            for audit in audits
        ),
        "top10_without_answer_substring_report_rows": sum(
            audit["answer_generation"]["opportunity_loss"][
                "top10_without_answer_substring_count"
            ]
            for audit in audits
        ),
        "not_retrieved_top10_report_rows": sum(
            audit["retrieval"]["not_retrieved_top10_count"] for audit in audits
        ),
    }


def main() -> int:
    args = parse_args()
    args.output = args.output if args.output.is_absolute() else repo_root() / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    inputs = []
    audits = []
    for report in args.reports:
        report = report if report.is_absolute() else repo_root() / report
        loaded = load_json(report)
        inputs.append({"path": report_path(report), "sha256": sha256_file(report)})
        audits.append(audit_report(report, loaded))

    result = {
        "schema_version": "king-synapse.official-dmr-answer-synthesis-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/official_dmr_answer_audit.py",
        "inputs": inputs,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "generated_answers_committed": False,
        "summary": combined_summary(audits),
        "audits": audits,
        "limits": [
            "Uses sanitized official DMR reports only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Classifies answer-synthesis opportunity loss; it does not change retrieval, ranking, or generation behavior.",
            "LLM judge status is copied from input reports; this audit does not run or reinterpret judge calls.",
        ],
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "summary": result["summary"],
                "reports": [
                    {
                        "report": audit["report"],
                        "sample_size_used": audit["sample_size_used"],
                        "retrieval": audit["retrieval"],
                        "opportunity_loss": audit["answer_generation"]["opportunity_loss"],
                    }
                    for audit in audits
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
