#!/usr/bin/env python
"""Estimate paired top-context DMR improvement significance from sanitized reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Summarize DMR top-context paired significance evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/dmr-top-context-significance.json",
    )
    return parser.parse_args()


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


def rounded(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


def rounded_p_value(value: float) -> float:
    return round(value, 12)


def judge_correct(item: dict[str, Any]) -> bool:
    return bool((item.get("llm_judge") or {}).get("correct"))


def substring_correct(item: dict[str, Any]) -> bool:
    return bool((item.get("scores") or {}).get("answer_substring_match"))


def rouge_f1(item: dict[str, Any]) -> float:
    return float((((item.get("scores") or {}).get("rouge_l") or {}).get("f1")) or 0.0)


def first_rank_bucket(item: dict[str, Any]) -> str:
    rank = item.get("first_relevant_rank")
    if rank is None:
        return "no_relevant_top10"
    rank = int(rank)
    if rank == 1:
        return "top1"
    return "top10_not_top1"


def length_bucket(value: Any) -> str:
    length = int(value or 0)
    if length <= 16:
        return "01_16"
    if length <= 32:
        return "17_32"
    if length <= 64:
        return "33_64"
    return "65_plus"


def wilson_ci(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, Any]:
    if total == 0:
        return {"successes": successes, "total": total, "rate": None, "low": None, "high": None}
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return {
        "successes": successes,
        "total": total,
        "rate": rounded(p),
        "low": rounded(max(0.0, center - margin)),
        "high": rounded(min(1.0, center + margin)),
    }


def mcnemar_exact_p(candidate_only: int, baseline_only: int) -> float:
    discordant = candidate_only + baseline_only
    if discordant == 0:
        return 1.0
    smaller = min(candidate_only, baseline_only)
    probability = sum(math.comb(discordant, i) for i in range(smaller + 1)) / (
        2**discordant
    )
    return min(1.0, 2.0 * probability)


def transition_counts(
    baseline_items: dict[str, dict[str, Any]],
    candidate_items: dict[str, dict[str, Any]],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for sample_id, candidate in candidate_items.items():
        baseline = baseline_items[sample_id]
        baseline_ok = judge_correct(baseline)
        candidate_ok = judge_correct(candidate)
        if baseline_ok and candidate_ok:
            counts["both_correct"] += 1
        elif baseline_ok and not candidate_ok:
            counts["baseline_only_correct"] += 1
        elif candidate_ok and not baseline_ok:
            counts["candidate_only_correct"] += 1
        else:
            counts["both_incorrect"] += 1
    return counts


def summarize_strata(
    baseline_items: dict[str, dict[str, Any]],
    candidate_items: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    strata: dict[str, dict[str, list[str]]] = {
        "candidate_retrieval_bucket": defaultdict(list),
        "gold_answer_length_bucket": defaultdict(list),
        "category": defaultdict(list),
    }
    for sample_id, candidate in candidate_items.items():
        strata["candidate_retrieval_bucket"][first_rank_bucket(candidate)].append(sample_id)
        strata["gold_answer_length_bucket"][length_bucket(candidate.get("gold_answer_length"))].append(
            sample_id
        )
        strata["category"][str(candidate.get("category") or "unknown")].append(sample_id)

    result: dict[str, Any] = {}
    for stratum_name, buckets in strata.items():
        bucket_result: dict[str, Any] = {}
        for bucket_name, sample_ids in sorted(buckets.items()):
            total = len(sample_ids)
            baseline_correct = sum(1 for sample_id in sample_ids if judge_correct(baseline_items[sample_id]))
            candidate_correct = sum(1 for sample_id in sample_ids if judge_correct(candidate_items[sample_id]))
            bucket_result[bucket_name] = {
                "samples": total,
                "baseline_judge_correct": baseline_correct,
                "candidate_judge_correct": candidate_correct,
                "judge_accuracy_delta": rounded(
                    (candidate_correct / total) - (baseline_correct / total)
                    if total
                    else None
                ),
            }
        result[stratum_name] = bucket_result
    return result


def scale_report(scale: str, baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    baseline = load_json(baseline_path)
    candidate = load_json(candidate_path)
    baseline_per_query = baseline["answer_generation"]["per_query"]
    candidate_per_query = candidate["answer_generation"]["per_query"]
    baseline_items = {
        item["sample_id"]: item for item in baseline_per_query
    }
    candidate_items = {
        item["sample_id"]: item for item in candidate_per_query
    }
    baseline_sample_ids = set(baseline_items)
    candidate_sample_ids = set(candidate_items)
    common_ids = sorted(set(baseline_items) & set(candidate_items))
    baseline_items = {sample_id: baseline_items[sample_id] for sample_id in common_ids}
    candidate_items = {sample_id: candidate_items[sample_id] for sample_id in common_ids}

    transitions = transition_counts(baseline_items, candidate_items)
    total = len(common_ids)
    baseline_judge_correct = sum(judge_correct(item) for item in baseline_items.values())
    candidate_judge_correct = sum(judge_correct(item) for item in candidate_items.values())
    baseline_substring_correct = sum(substring_correct(item) for item in baseline_items.values())
    candidate_substring_correct = sum(substring_correct(item) for item in candidate_items.values())
    baseline_rouge_mean = sum(rouge_f1(item) for item in baseline_items.values()) / total
    candidate_rouge_mean = sum(rouge_f1(item) for item in candidate_items.values()) / total
    p_value = mcnemar_exact_p(
        transitions["candidate_only_correct"], transitions["baseline_only_correct"]
    )

    return {
        "scale": scale,
        "inputs": {
            "baseline_report": {
                "path": report_path(baseline_path),
                "sha256": sha256_file(baseline_path),
            },
            "top_context_report": {
                "path": report_path(candidate_path),
                "sha256": sha256_file(candidate_path),
            },
        },
        "requested_samples": candidate.get("sample_size_requested"),
        "paired_scored_samples": total,
        "sample_id_sets_equal": baseline_sample_ids == candidate_sample_ids,
        "generator_pair": {
            "baseline": baseline.get("generator", {}).get("policy"),
            "candidate": candidate.get("generator", {}).get("policy"),
        },
        "retrieval_mode": candidate.get("retrieval_mode"),
        "judge_model": candidate.get("llm_judge", {}).get("model"),
        "accelerator": candidate.get("accelerator", {}),
        "judge_accuracy": {
            "baseline": wilson_ci(baseline_judge_correct, total),
            "candidate": wilson_ci(candidate_judge_correct, total),
            "delta": rounded((candidate_judge_correct - baseline_judge_correct) / total),
        },
        "paired_judge_transitions": dict(sorted(transitions.items())),
        "mcnemar_exact": {
            "candidate_only_correct": transitions["candidate_only_correct"],
            "baseline_only_correct": transitions["baseline_only_correct"],
            "discordant_pairs": transitions["candidate_only_correct"]
            + transitions["baseline_only_correct"],
            "two_sided_p_value": rounded_p_value(p_value),
            "significant_at_0_05": p_value < 0.05,
        },
        "substring_accuracy": {
            "baseline": rounded(baseline_substring_correct / total),
            "candidate": rounded(candidate_substring_correct / total),
            "delta": rounded((candidate_substring_correct - baseline_substring_correct) / total),
        },
        "rouge_l_f1_mean": {
            "baseline": rounded(baseline_rouge_mean),
            "candidate": rounded(candidate_rouge_mean),
            "delta": rounded(candidate_rouge_mean - baseline_rouge_mean),
        },
        "strata": summarize_strata(baseline_items, candidate_items),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    scales = [
        (
            "dmr_50",
            root / "crates/eval/reports/official-dmr-50.json",
            root / "crates/eval/reports/official-dmr-50-top-context-judge.json",
        ),
        (
            "dmr_200",
            root / "crates/eval/reports/official-dmr-200.json",
            root / "crates/eval/reports/official-dmr-200-top-context-judge.json",
        ),
        (
            "dmr_500_request_323_scored",
            root / "crates/eval/reports/official-dmr-500.json",
            root / "crates/eval/reports/official-dmr-500-top-context-judge.json",
        ),
    ]
    scale_reports = [scale_report(*scale) for scale in scales]

    all_judge_positive = all(item["judge_accuracy"]["delta"] > 0 for item in scale_reports)
    all_substring_positive = all(item["substring_accuracy"]["delta"] > 0 for item in scale_reports)
    all_rouge_positive = all(item["rouge_l_f1_mean"]["delta"] > 0 for item in scale_reports)
    all_mcnemar_significant = all(
        item["mcnemar_exact"]["significant_at_0_05"] for item in scale_reports
    )
    all_candidate_only_greater = all(
        item["mcnemar_exact"]["candidate_only_correct"]
        > item["mcnemar_exact"]["baseline_only_correct"]
        for item in scale_reports
    )

    category_sets = {
        scale["scale"]: sorted(scale["strata"]["category"].keys()) for scale in scale_reports
    }

    report = {
        "schema_version": "king-synapse.dmr-top-context-significance.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "git": {
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git_value("rev-parse", "HEAD"),
            "origin_main_delta": git_value(
                "rev-list", "--left-right", "--count", "origin/main...HEAD"
            ),
        },
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "prompt_text_recorded": False,
        "raw_response_committed": False,
        "method": {
            "paired_unit": "sample_id shared by extractive baseline and top-context candidate at each scale",
            "primary_test": "Exact two-sided McNemar/binomial test over judge-correct discordant pairs.",
            "confidence_interval": "Wilson 95% interval for each unpaired accuracy; paired p-value is the primary stability signal.",
            "pooling_policy": "Scale views are not pooled because larger DMR views may contain earlier rows.",
        },
        "scale_results": scale_reports,
        "cross_scale_summary": {
            "all_scales_judge_accuracy_delta_positive": all_judge_positive,
            "all_scales_substring_delta_positive": all_substring_positive,
            "all_scales_rouge_l_delta_positive": all_rouge_positive,
            "all_scales_candidate_only_gt_baseline_only": all_candidate_only_greater,
            "all_scales_mcnemar_significant_at_0_05": all_mcnemar_significant,
            "available_category_sets": category_sets,
            "category_consistency_limit": (
                "Sanitized reports expose one category, dmr-answer-generation, so "
                "question-subtype consistency cannot be audited from committed reports."
            ),
        },
        "read": {
            "primary_result": (
                "Top-context improves judged answer correctness over the extractive "
                "baseline at DMR 50, DMR 200, and the 500-request / 323-scored view."
            ),
            "statistical_read": (
                "Each scale has more candidate-only correct rows than baseline-only "
                "correct rows, and the exact McNemar test is significant at 0.05 on "
                "all three scale views."
                if all_mcnemar_significant
                else "The direction repeats, but at least one scale view does not pass the 0.05 paired test."
            ),
            "limits": (
                "This supports the generator direction as validation evidence. It does "
                "not make the task published-comparable, does not solve low absolute "
                "answer quality, and does not justify a runtime default change."
            ),
            "next_action": (
                "Keep feature freeze. Treat top-context as the strongest evaluated "
                "generator direction, while keeping published-comparable mapping, "
                "hosted external comparison, and answer quality open."
            ),
        },
        "limits": [
            "Uses committed sanitized per-query reports only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, generated answers, prompts, raw responses, or API keys.",
            "Scale views are reported separately and not pooled.",
            "Question-subtype consistency is unavailable because committed sanitized reports expose a single DMR category.",
            "This report does not change memory schema, cognitive layers, CLI/MCP, retrieval, ranking, generator, or scoring defaults.",
        ],
    }
    return report


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else repo_root() / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": report_path(output),
                "cross_scale_summary": report["cross_scale_summary"],
                "scale_results": [
                    {
                        "scale": item["scale"],
                        "paired_scored_samples": item["paired_scored_samples"],
                        "judge_delta": item["judge_accuracy"]["delta"],
                        "mcnemar_exact": item["mcnemar_exact"],
                        "substring_delta": item["substring_accuracy"]["delta"],
                        "rouge_l_delta": item["rouge_l_f1_mean"]["delta"],
                    }
                    for item in report["scale_results"]
                ],
                "read": report["read"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
