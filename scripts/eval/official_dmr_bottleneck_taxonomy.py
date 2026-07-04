#!/usr/bin/env python
"""Build a sanitized bottleneck taxonomy for official-style DMR.

This script consolidates existing sanitized DMR answer reports. It separates
mapping coverage, retrieval/ranking, and answer-synthesis opportunity loss
without reading raw questions, answers, dialogs, memory text, generated text,
or API keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Consolidate official-style DMR bottleneck taxonomy."
    )
    parser.add_argument(
        "--answer-audit",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-answer-synthesis-audit.json",
    )
    parser.add_argument(
        "--generator-summary",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-generator-ablation-summary.json",
    )
    parser.add_argument(
        "--mapping-policy-review",
        type=Path,
        default=root / "crates/eval/reports/dmr-mapping-policy-review.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-bottleneck-taxonomy.json",
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


def ratio(part: int | float, total: int | float) -> float | None:
    return float(part) / float(total) if total else None


def rounded(value: Any) -> Any:
    return round(value, 6) if isinstance(value, float) else value


def find_generator_run(summary: dict[str, Any], label: str) -> dict[str, Any]:
    for run in summary["runs"]:
        if run["label"] == label:
            return run
    raise KeyError(f"missing generator summary run: {label}")


def taxonomy_for_audit(audit: dict[str, Any], generator_run: dict[str, Any]) -> dict[str, Any]:
    scored = int(audit["sample_size_used"])
    top1 = int(audit["retrieval"]["top1_count"])
    top10_not_top1 = int(audit["retrieval"]["top10_not_top1_count"])
    not_retrieved = int(audit["retrieval"]["not_retrieved_top10_count"])
    opportunity = audit["answer_generation"]["opportunity_loss"]
    top1_without = int(opportunity["top1_without_answer_substring_count"])
    top10_without = int(opportunity["top10_without_answer_substring_count"])
    selected_non_first = int(opportunity["top1_selected_non_first_context_count"])
    overall = audit["answer_generation"]["overall"]
    by_bucket = audit["answer_generation"]["by_retrieval_bucket"]
    candidate = generator_run["candidate"]
    delta = generator_run["delta_candidate_minus_baseline"]

    return {
        "label": generator_run["label"],
        "report": audit["report"],
        "requested_samples": generator_run["requested_samples"],
        "scored_samples": scored,
        "baseline_generator": audit["generator_policy"],
        "candidate_generator": generator_run["candidate_generator"],
        "retrieval_buckets": {
            "top1_count": top1,
            "top10_not_top1_count": top10_not_top1,
            "not_retrieved_top10_count": not_retrieved,
            "top1_rate": rounded(ratio(top1, scored)),
            "top10_not_top1_rate": rounded(ratio(top10_not_top1, scored)),
            "not_retrieved_top10_rate": rounded(ratio(not_retrieved, scored)),
        },
        "baseline_answer_synthesis": {
            "answer_substring_accuracy": rounded(overall["answer_substring_accuracy"]),
            "rouge_l_f1_mean": rounded(overall["rouge_l_f1_mean"]),
            "top1_without_answer_substring_count": top1_without,
            "top1_without_answer_substring_rate_within_top1": rounded(
                ratio(top1_without, top1)
            ),
            "top10_without_answer_substring_count": top10_without,
            "top10_without_answer_substring_rate_within_retrieved_top10": rounded(
                ratio(top10_without, top1 + top10_not_top1)
            ),
            "top1_selected_non_first_context_count": selected_non_first,
            "top1_selected_non_first_context_rate_within_top1": rounded(
                ratio(selected_non_first, top1)
            ),
            "bucket_substring_accuracy": {
                bucket: rounded(stats["answer_substring_accuracy"])
                for bucket, stats in by_bucket.items()
            },
            "alignment_counts": overall["alignment_counts"],
        },
        "candidate_generator_effect": {
            "answer_substring_accuracy": candidate["answer_substring_accuracy"],
            "rouge_l_f1_mean": candidate["rouge_l_f1_mean"],
            "answer_substring_accuracy_delta": delta[
                "answer_substring_accuracy_delta"
            ],
            "rouge_l_f1_mean_delta": delta["rouge_l_f1_mean_delta"],
            "top1_without_answer_substring_count_delta": delta[
                "top1_without_answer_substring_count_delta"
            ],
            "candidate_top1_without_answer_substring_count": candidate[
                "top1_without_answer_substring_count"
            ],
            "candidate_top10_without_answer_substring_count": candidate[
                "top10_without_answer_substring_count"
            ],
            "candidate_not_retrieved_top10_count": candidate[
                "not_retrieved_top10_count"
            ],
        },
        "read": {
            "primary_boundary": "mixed",
            "why": (
                "Mapping, retrieval/ranking, and answer synthesis are all visible. "
                "Top-context extraction improves answer metrics but leaves a large "
                "residual generator loss, so it is evidence for a direction rather "
                "than a complete fix."
            ),
        },
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    answer_audit_path = normalize_path_arg(args.answer_audit)
    generator_summary_path = normalize_path_arg(args.generator_summary)
    mapping_review_path = normalize_path_arg(args.mapping_policy_review)

    answer_audit = load_json(answer_audit_path)
    generator_summary = load_json(generator_summary_path)
    mapping_review = load_json(mapping_review_path)

    mapping_boundary = mapping_review["review"]["punctuation_boundary"]
    policy_coverage = mapping_review["review"]["policy_coverage"]
    policy_coverage_ratio = mapping_review["review"]["policy_coverage_ratio"]

    views = []
    for audit in answer_audit["audits"]:
        label = {
            50: "DMR 50",
            200: "DMR 200",
            323: "DMR 500 request / 323 scored",
        }.get(audit["sample_size_used"])
        if label is None:
            raise ValueError(f"unexpected scored sample size: {audit['sample_size_used']}")
        views.append(taxonomy_for_audit(audit, find_generator_run(generator_summary, label)))

    largest = views[-1]
    largest_scored = largest["scored_samples"]
    largest_top1 = largest["retrieval_buckets"]["top1_count"]
    largest_retrieved_top10 = (
        largest["retrieval_buckets"]["top1_count"]
        + largest["retrieval_buckets"]["top10_not_top1_count"]
    )
    largest_baseline = largest["baseline_answer_synthesis"]
    largest_candidate = largest["candidate_generator_effect"]

    return {
        "schema_version": "king-synapse.official-dmr-bottleneck-taxonomy.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "inputs": {
            "answer_audit": {
                "path": report_path(answer_audit_path),
                "sha256": sha256_file(answer_audit_path),
            },
            "generator_summary": {
                "path": report_path(generator_summary_path),
                "sha256": sha256_file(generator_summary_path),
            },
            "mapping_policy_review": {
                "path": report_path(mapping_review_path),
                "sha256": sha256_file(mapping_review_path),
            },
        },
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "generated_answers_committed": False,
        "mapping_boundary": {
            "source_rows": mapping_review["review"]["rows"]["source_rows"],
            "punctuation_full_answer_coverage": policy_coverage[
                "punctuation_full_answer"
            ],
            "punctuation_full_answer_coverage_ratio": policy_coverage_ratio[
                "punctuation_full_answer"
            ],
            "rejected_by_punctuation": mapping_boundary["rejected_by_punctuation"],
            "token_containment_rejected_by_punctuation": mapping_boundary[
                "token_containment_rejected_by_punctuation"
            ],
            "no_diagnostic_match": mapping_boundary["no_diagnostic_match"],
        },
        "views": views,
        "largest_local_view": {
            "label": largest["label"],
            "scored_samples": largest_scored,
            "retrieved_top10_count": largest_retrieved_top10,
            "not_retrieved_top10_count": largest["retrieval_buckets"][
                "not_retrieved_top10_count"
            ],
            "top1_count": largest_top1,
            "baseline_top1_without_answer_substring_count": largest_baseline[
                "top1_without_answer_substring_count"
            ],
            "baseline_top10_without_answer_substring_count": largest_baseline[
                "top10_without_answer_substring_count"
            ],
            "baseline_top1_selected_non_first_context_count": largest_baseline[
                "top1_selected_non_first_context_count"
            ],
            "candidate_top1_without_answer_substring_count": largest_candidate[
                "candidate_top1_without_answer_substring_count"
            ],
            "candidate_top10_without_answer_substring_count": largest_candidate[
                "candidate_top10_without_answer_substring_count"
            ],
            "candidate_substring_accuracy_delta": largest_candidate[
                "answer_substring_accuracy_delta"
            ],
            "candidate_rouge_l_f1_delta": largest_candidate["rouge_l_f1_mean_delta"],
        },
        "read": {
            "conclusion": (
                "Official-style DMR is blocked by three separate bottlenecks: "
                "mapping coverage, retrieval/ranking, and answer synthesis. The "
                "largest pinned local view has 177 punctuation-mapping rejections "
                "before scoring, 114 scored samples without a relevant top-10 "
                "retrieval, and 118 top-1 retrieval hits whose extractive answer "
                "still lacks the gold substring."
            ),
            "generator_read": (
                "Top-context extraction is the clearest current answer-synthesis "
                "direction: it improves substring and ROUGE-L on every scale view "
                "and reduces top-1 opportunity loss. But on the largest local view "
                "it still leaves 90 top-1 hits without the gold substring, so it "
                "is not enough for an official DMR claim."
            ),
            "ranking_read": (
                "Ranking remains necessary because a large top10-not-top1 bucket "
                "and true top10 retrieval-miss bucket remain after answer scoring. "
                "Generator work cannot recover samples that never receive a "
                "relevant top-10 context."
            ),
            "mapping_read": (
                "The 500-request run is 323-scored under punctuation full-answer "
                "mapping. Relaxed token containment would increase coverage, but "
                "it is a separate diagnostic policy and cannot be silently promoted."
            ),
            "next_action": (
                "Do not change runtime defaults. Top-context DMR 50 is now "
                "judge-scored; the next DMR validation expansion is DMR 200 "
                "top-context judge scoring, otherwise continue with hosted "
                "external comparison when credentials/endpoints are ready."
            ),
        },
        "limits": [
            "Reads existing sanitized reports only.",
            "Does not rerun DMR retrieval, answer generation, or LLM judge calls.",
            "Does not inspect raw questions, answers, dialogs, memory content, generated answers, or API keys.",
            "Does not change runtime generator, retrieval, ranking, schema, cognitive layers, or CLI behavior.",
        ],
    }


def main() -> int:
    args = parse_args()
    args.output = normalize_path_arg(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "mapping_rejected_by_punctuation": report["mapping_boundary"][
                    "rejected_by_punctuation"
                ],
                "largest_local_view": report["largest_local_view"],
                "next_action": report["read"]["next_action"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
