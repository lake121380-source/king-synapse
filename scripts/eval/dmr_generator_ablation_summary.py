#!/usr/bin/env python
"""Consolidate sanitized DMR generator-ablation reports.

This reads only the already-sanitized official DMR answer-synthesis audit
outputs. It does not read raw questions, answers, dialogs, sessions, memory
content, generated text, or API keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Consolidate sanitized DMR generator-ablation metrics."
    )
    parser.add_argument(
        "--dmr-50-report",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-generator-ablation-dmr-50.json",
    )
    parser.add_argument(
        "--dmr-200-report",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-generator-ablation-dmr-200.json",
    )
    parser.add_argument(
        "--dmr-500-report",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-generator-ablation-dmr-500.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-generator-ablation-summary.json",
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


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root(), text=True
        ).strip()
    except Exception:
        return None


def rounded(value: Any) -> Any:
    return round(value, 6) if isinstance(value, float) else value


def overall_metric(audit: dict[str, Any], name: str) -> Any:
    return audit["answer_generation"]["overall"][name]


def opportunity_metric(audit: dict[str, Any], name: str) -> Any:
    return audit["answer_generation"]["opportunity_loss"][name]


def compact_audit(audit: dict[str, Any]) -> dict[str, Any]:
    top1_count = audit["retrieval"]["top1_count"]
    top1_without = opportunity_metric(audit, "top1_without_answer_substring_count")
    return {
        "retrieval_recall_at_10": rounded(audit["retrieval"]["recall_at_10"]),
        "retrieval_mrr_at_10": rounded(audit["retrieval"]["mrr_at_10"]),
        "top1_count": top1_count,
        "top10_not_top1_count": audit["retrieval"]["top10_not_top1_count"],
        "not_retrieved_top10_count": audit["retrieval"]["not_retrieved_top10_count"],
        "exact_accuracy": rounded(overall_metric(audit, "exact_accuracy")),
        "punctuation_accuracy": rounded(overall_metric(audit, "punctuation_accuracy")),
        "answer_substring_accuracy": rounded(
            overall_metric(audit, "answer_substring_accuracy")
        ),
        "rouge_l_f1_mean": rounded(overall_metric(audit, "rouge_l_f1_mean")),
        "rouge_l_recall_mean": rounded(overall_metric(audit, "rouge_l_recall_mean")),
        "top1_without_answer_substring_count": top1_without,
        "top1_without_answer_substring_rate": rounded(top1_without / top1_count)
        if top1_count
        else None,
        "top10_without_answer_substring_count": opportunity_metric(
            audit, "top10_without_answer_substring_count"
        ),
        "top1_selected_non_first_context_count": opportunity_metric(
            audit, "top1_selected_non_first_context_count"
        ),
        "llm_judge_status_counts": audit.get("llm_judge_status_counts", {}),
    }


def delta(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    base_metrics = compact_audit(base)
    candidate_metrics = compact_audit(candidate)
    base_substring = base_metrics["answer_substring_accuracy"]
    return {
        "retrieval_recall_at_10_delta": rounded(
            candidate_metrics["retrieval_recall_at_10"]
            - base_metrics["retrieval_recall_at_10"]
        ),
        "answer_substring_accuracy_delta": rounded(
            candidate_metrics["answer_substring_accuracy"]
            - base_metrics["answer_substring_accuracy"]
        ),
        "answer_substring_accuracy_multiplier": rounded(
            candidate_metrics["answer_substring_accuracy"] / base_substring
        )
        if base_substring
        else None,
        "rouge_l_f1_mean_delta": rounded(
            candidate_metrics["rouge_l_f1_mean"] - base_metrics["rouge_l_f1_mean"]
        ),
        "top1_without_answer_substring_count_delta": (
            candidate_metrics["top1_without_answer_substring_count"]
            - base_metrics["top1_without_answer_substring_count"]
        ),
        "top1_without_answer_substring_rate_delta": rounded(
            candidate_metrics["top1_without_answer_substring_rate"]
            - base_metrics["top1_without_answer_substring_rate"]
        ),
    }


def scale_view(
    *,
    run_id: str,
    label: str,
    path: Path,
    mapping_note: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    report = load_json(path)
    audits = {audit["generator_policy"]: audit for audit in report["audits"]}
    base = audits["extractive"]
    candidate = audits["top-context-extractive"]
    return (
        {
            "id": run_id,
            "label": label,
            "requested_samples": base["sample_size_requested"],
            "scored_samples": base["sample_size_used"],
            "mapping_note": mapping_note,
            "sample_sets_overlap_previous_scale_views": report.get(
                "summary", {}
            ).get("sample_sets_overlap", True),
            "baseline_generator": "extractive",
            "candidate_generator": "top-context-extractive",
            "baseline": compact_audit(base),
            "candidate": compact_audit(candidate),
            "delta_candidate_minus_baseline": delta(base, candidate),
        },
        {"path": report_path(path), "sha256": sha256_file(path)},
    )


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    views = [
        (
            "dmr_50",
            "DMR 50",
            args.dmr_50_report,
            "Pinned punctuation mapping; requested samples scored.",
        ),
        (
            "dmr_200",
            "DMR 200",
            args.dmr_200_report,
            "Pinned punctuation mapping; requested samples scored.",
        ),
        (
            "dmr_500_request_323_scored",
            "DMR 500 request / 323 scored",
            args.dmr_500_report,
            "DMR 500 request scored 323 samples under pinned punctuation mapping.",
        ),
    ]

    runs = []
    inputs = []
    for run_id, label, path, mapping_note in views:
        run, input_entry = scale_view(
            run_id=run_id, label=label, path=path, mapping_note=mapping_note
        )
        runs.append(run)
        inputs.append(input_entry)

    return {
        "schema_version": "king-synapse.official-dmr-generator-ablation-summary.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "runner": report_path(Path(__file__)),
        "inputs": inputs,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "generated_answers_committed": False,
        "aggregate_findings": {
            "scale_views": len(runs),
            "scales": [run["label"] for run in runs],
            "sample_sets_overlap": True,
            "overlap_note": (
                "The 50, 200, and 500-request reports are deterministic scale "
                "views from the same source order; do not sum them as "
                "independent examples."
            ),
            "candidate_improves_substring_on_all_scale_views": all(
                run["delta_candidate_minus_baseline"][
                    "answer_substring_accuracy_delta"
                ]
                > 0
                for run in runs
            ),
            "candidate_improves_rouge_l_f1_on_all_scale_views": all(
                run["delta_candidate_minus_baseline"]["rouge_l_f1_mean_delta"] > 0
                for run in runs
            ),
            "candidate_reduces_top1_without_substring_count_on_all_scale_views": all(
                run["delta_candidate_minus_baseline"][
                    "top1_without_answer_substring_count_delta"
                ]
                < 0
                for run in runs
            ),
            "judge_status": (
                "not available; DeepSeek probe returned "
                "authorization_error/HTTP 401 in the recorded judge probe"
            ),
            "decision": (
                "The top-context-extractive generator direction repeats across "
                "DMR 50, 200, and 500-request/323-scored local views, but "
                "remains evaluation-only evidence until fixed LLM judge scoring "
                "succeeds and absolute answer quality improves."
            ),
        },
        "runs": runs,
    }


def main() -> None:
    args = parse_args()
    report = build_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
