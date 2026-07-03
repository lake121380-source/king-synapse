#!/usr/bin/env python
"""Cross-ablation DMR ranking transition audit.

This script reads existing sanitized reports and compares rank transitions for
the same DMR 50 sample set. It does not inspect raw third-party questions,
answers, dialogs, sessions, memory content, or generated text.
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
    parser = argparse.ArgumentParser(description="Audit sanitized DMR rank transitions.")
    parser.add_argument(
        "--candidate-report",
        type=Path,
        default=root / "crates/eval/reports/dmr-50-punctuation-validation.json",
    )
    parser.add_argument(
        "--top-k-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-50-top-k.json",
    )
    parser.add_argument(
        "--chunk-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-50-chunk-policy.json",
    )
    parser.add_argument(
        "--query-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-50-query-expansion.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-transition-audit-dmr-50.json",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def candidate_runs(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {run["mode"]: run for run in report["datasets"][0]["kr_eval_runs"]}


def top_k_runs(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(run["k"]): run for run in report["datasets"][0]["runs"]}


def ablation_runs(report: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {run[key]: run for run in report["runs"]}


def per_query_by_sample(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["sample_id"]: item for item in run.get("per_query", [])}


def rank(item: dict[str, Any] | None) -> int | None:
    if item is None:
        return None
    value = item.get("first_relevant_rank")
    return int(value) if value is not None else None


def bucket(rank_value: int | None) -> str:
    if rank_value is None:
        return "absent"
    if rank_value == 1:
        return "top1"
    if rank_value <= 10:
        return "top10"
    if rank_value <= 50:
        return "top50"
    return "after50"


def in_top(rank_value: int | None, k: int) -> bool:
    return rank_value is not None and rank_value <= k


def transition(left: int | None, right: int | None) -> str:
    return f"{bucket(left)}->{bucket(right)}"


def effect(left: int | None, right: int | None) -> str:
    left_top10 = in_top(left, 10)
    right_top10 = in_top(right, 10)
    if not left_top10 and right_top10:
        return "recovered_to_top10"
    if left_top10 and not right_top10:
        return "suppressed_from_top10"
    if left == 1 and right == 1:
        return "stable_top1"
    if left != 1 and right == 1:
        return "promoted_to_top1"
    if left == 1 and right != 1:
        return "demoted_from_top1"
    if left_top10 and right_top10:
        return "top10_preserved"
    if bucket(left) != bucket(right):
        return "bucket_changed_outside_top10"
    return "no_top10_change"


def decision_bucket(top10_rank: int | None, top50_rank: int | None) -> str:
    if top10_rank == 1:
        return "top1_hit"
    if in_top(top10_rank, 10):
        return "top10_not_top1"
    if in_top(top50_rank, 50):
        return "top50_only_late_rank"
    return "top50_retrieval_miss"


def compact_case(
    *,
    sample_id: str,
    baseline: int | None,
    vectors: int | None,
    rerank_top10: int | None,
    rerank_top50: int | None,
    merged_session: int | None,
    keyword_boost: int | None,
) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "ranks": {
            "baseline_rrf": baseline,
            "vectors": vectors,
            "reranker_top10": rerank_top10,
            "reranker_top50": rerank_top50,
            "merged_session_top50": merged_session,
            "keyword_boost_top50": keyword_boost,
        },
        "control_bucket": decision_bucket(rerank_top10, rerank_top50),
        "baseline_to_vector": effect(baseline, vectors),
        "vector_to_reranker": effect(vectors, rerank_top10),
        "dialog_to_merged_session": effect(rerank_top50, merged_session),
        "original_to_keyword_boost": effect(rerank_top50, keyword_boost),
    }


def summarize_subset(
    cases: list[dict[str, Any]],
    *,
    source_rank_name: str,
    target_rank_name: str,
    effect_name: str,
) -> dict[str, Any]:
    return {
        "count": len(cases),
        "target_bucket_counts": dict(
            sorted(Counter(bucket(case["ranks"][target_rank_name]) for case in cases).items())
        ),
        "effect_counts": dict(sorted(Counter(case[effect_name] for case in cases).items())),
        "sample_ids": [case["sample_id"] for case in cases],
        "rank_pairs": [
            {
                "sample_id": case["sample_id"],
                "source_rank": case["ranks"][source_rank_name],
                "target_rank": case["ranks"][target_rank_name],
            }
            for case in cases
        ],
    }


def audit(
    *,
    candidate_report: dict[str, Any],
    top_k_report: dict[str, Any],
    chunk_report: dict[str, Any],
    query_report: dict[str, Any],
) -> dict[str, Any]:
    candidate = candidate_runs(candidate_report)
    top_k = top_k_runs(top_k_report)
    chunk = ablation_runs(chunk_report, "chunk_policy")
    query = ablation_runs(query_report, "query_policy")

    baseline = per_query_by_sample(candidate["baseline-rrf"])
    vectors = per_query_by_sample(candidate["vectors"])
    top10 = per_query_by_sample(top_k[10])
    top50 = per_query_by_sample(top_k[50])
    merged = per_query_by_sample(chunk["merged-session"])
    keyword = per_query_by_sample(query["keyword-boost"])

    sample_ids = sorted(set(top50) | set(top10) | set(baseline) | set(vectors))
    cases = [
        compact_case(
            sample_id=sample_id,
            baseline=rank(baseline.get(sample_id)),
            vectors=rank(vectors.get(sample_id)),
            rerank_top10=rank(top10.get(sample_id)),
            rerank_top50=rank(top50.get(sample_id)),
            merged_session=rank(merged.get(sample_id)),
            keyword_boost=rank(keyword.get(sample_id)),
        )
        for sample_id in sample_ids
    ]

    top50_only = [case for case in cases if case["control_bucket"] == "top50_only_late_rank"]
    top50_miss = [case for case in cases if case["control_bucket"] == "top50_retrieval_miss"]
    reranker_suppressed = [
        case for case in cases if case["vector_to_reranker"] == "suppressed_from_top10"
    ]
    reranker_demoted_top1 = [
        case for case in cases if case["vector_to_reranker"] == "demoted_from_top1"
    ]
    keyword_hurt_top1 = [
        case
        for case in cases
        if case["ranks"]["reranker_top50"] == 1 and case["ranks"]["keyword_boost_top50"] != 1
    ]
    merged_hurt_top1 = [
        case
        for case in cases
        if case["ranks"]["reranker_top50"] == 1 and case["ranks"]["merged_session_top50"] != 1
    ]

    return {
        "sample_size": len(cases),
        "control_bucket_counts": dict(sorted(Counter(case["control_bucket"] for case in cases).items())),
        "baseline_to_vector_effect_counts": dict(
            sorted(Counter(case["baseline_to_vector"] for case in cases).items())
        ),
        "vector_to_reranker_effect_counts": dict(
            sorted(Counter(case["vector_to_reranker"] for case in cases).items())
        ),
        "dialog_to_merged_session_effect_counts": dict(
            sorted(Counter(case["dialog_to_merged_session"] for case in cases).items())
        ),
        "original_to_keyword_boost_effect_counts": dict(
            sorted(Counter(case["original_to_keyword_boost"] for case in cases).items())
        ),
        "top50_only_cases": summarize_subset(
            top50_only,
            source_rank_name="reranker_top50",
            target_rank_name="reranker_top50",
            effect_name="vector_to_reranker",
        ),
        "top50_retrieval_miss_under_control": {
            "count": len(top50_miss),
            "sample_ids": [case["sample_id"] for case in top50_miss],
            "merged_session_result": summarize_subset(
                top50_miss,
                source_rank_name="reranker_top50",
                target_rank_name="merged_session_top50",
                effect_name="dialog_to_merged_session",
            ),
            "keyword_boost_result": summarize_subset(
                top50_miss,
                source_rank_name="reranker_top50",
                target_rank_name="keyword_boost_top50",
                effect_name="original_to_keyword_boost",
            ),
        },
        "reranker_suppressed_top10_cases": summarize_subset(
            reranker_suppressed,
            source_rank_name="vectors",
            target_rank_name="reranker_top10",
            effect_name="vector_to_reranker",
        ),
        "reranker_demoted_top1_cases": summarize_subset(
            reranker_demoted_top1,
            source_rank_name="vectors",
            target_rank_name="reranker_top10",
            effect_name="vector_to_reranker",
        ),
        "merged_session_hurt_top1_cases": summarize_subset(
            merged_hurt_top1,
            source_rank_name="reranker_top50",
            target_rank_name="merged_session_top50",
            effect_name="dialog_to_merged_session",
        ),
        "keyword_boost_hurt_top1_cases": summarize_subset(
            keyword_hurt_top1,
            source_rank_name="reranker_top50",
            target_rank_name="keyword_boost_top50",
            effect_name="original_to_keyword_boost",
        ),
        "cases": cases,
    }


def main() -> int:
    args = parse_args()
    args.output = args.output if args.output.is_absolute() else repo_root() / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    candidate_report = load_json(args.candidate_report)
    top_k_report = load_json(args.top_k_report)
    chunk_report = load_json(args.chunk_report)
    query_report = load_json(args.query_report)
    result = audit(
        candidate_report=candidate_report,
        top_k_report=top_k_report,
        chunk_report=chunk_report,
        query_report=query_report,
    )

    report = {
        "schema_version": "king-synapse.ranking-transition-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_transition_audit.py",
        "inputs": {
            "candidate_report": {
                "path": report_path(args.candidate_report),
                "sha256": sha256_file(args.candidate_report),
            },
            "top_k_report": {
                "path": report_path(args.top_k_report),
                "sha256": sha256_file(args.top_k_report),
            },
            "chunk_report": {
                "path": report_path(args.chunk_report),
                "sha256": sha256_file(args.chunk_report),
            },
            "query_report": {
                "path": report_path(args.query_report),
                "sha256": sha256_file(args.query_report),
            },
        },
        "dataset": "DMR candidate MSC-Self-Instruct, punctuation-normalized 50",
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "audit": result,
        "limits": [
            "Uses sanitized per-query sample IDs and ranks only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Classifies cross-ablation rank transitions; it does not change retrieval or ranking behavior.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sample_size": result["sample_size"],
                "control_bucket_counts": result["control_bucket_counts"],
                "baseline_to_vector_effect_counts": result["baseline_to_vector_effect_counts"],
                "vector_to_reranker_effect_counts": result["vector_to_reranker_effect_counts"],
                "dialog_to_merged_session_effect_counts": result["dialog_to_merged_session_effect_counts"],
                "original_to_keyword_boost_effect_counts": result["original_to_keyword_boost_effect_counts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
