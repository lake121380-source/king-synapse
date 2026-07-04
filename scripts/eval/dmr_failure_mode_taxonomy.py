#!/usr/bin/env python
"""Classify sanitized DMR 500 failure modes.

This report uses committed aggregate/sanitized DMR evidence only. It does not
read raw questions, answers, dialogs, memory text, generated answers, prompts,
raw judge responses, or API keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Classify sanitized DMR 500 failure modes.")
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
        "--generator-ablation",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-generator-ablation-dmr-500.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/dmr-failure-mode-taxonomy.json",
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


def rounded(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def ratio(part: int | float, total: int | float) -> float | None:
    return float(part) / float(total) if total else None


def pct(part: int | float, total: int | float) -> float | None:
    value = ratio(part, total)
    return round(value * 100.0, 2) if value is not None else None


def judge_correct(item: dict[str, Any]) -> bool:
    return bool((item.get("llm_judge") or {}).get("correct"))


def first_rank(item: dict[str, Any]) -> int | None:
    value = item.get("first_relevant_rank")
    return int(value) if value is not None else None


def classify_candidate_item(item: dict[str, Any]) -> str:
    if judge_correct(item):
        return "judge_correct_success"
    rank = first_rank(item)
    if rank is None:
        return "retrieval_top10_miss"
    if rank == 1:
        return "top1_answer_synthesis_failure"
    return "top_context_ranking_boundary"


def compact_case(item: dict[str, Any]) -> dict[str, Any]:
    trace = item.get("generation_trace", {})
    judge = item.get("llm_judge", {})
    scores = item.get("scores", {})
    rouge = scores.get("rouge_l", {})
    return {
        "sample_id": item.get("sample_id"),
        "category": item.get("category"),
        "source_session_count": item.get("source_session_count"),
        "relevant_count": item.get("relevant_count"),
        "first_relevant_rank": item.get("first_relevant_rank"),
        "retrieved_context_count": item.get("retrieved_context_count"),
        "selected_context_rank": trace.get("selected_context_rank"),
        "selected_sentence_rank": trace.get("selected_sentence_rank"),
        "gold_answer_length": item.get("gold_answer_length"),
        "generated_answer_length": item.get("generated_answer_length"),
        "answer_substring_match": scores.get("answer_substring_match"),
        "rouge_l_f1": rounded(rouge.get("f1")),
        "llm_judge_correct": judge.get("correct"),
        "llm_judge_status": judge.get("status"),
        "llm_judge_reason_hash": judge.get("reason_hash"),
    }


def summarize_bucket(count: int, *, requested: int, scored: int, failures: int) -> dict[str, Any]:
    return {
        "count": count,
        "share_of_requested": pct(count, requested),
        "share_of_scored": pct(count, scored),
        "share_of_unresolved_requested": pct(count, failures),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    baseline_path = normalize_path_arg(args.baseline_report)
    top_context_path = normalize_path_arg(args.top_context_report)
    mapping_path = normalize_path_arg(args.mapping_policy_review)
    ablation_path = normalize_path_arg(args.generator_ablation)

    baseline = load_json(baseline_path)
    candidate = load_json(top_context_path)
    mapping = load_json(mapping_path)
    ablation = load_json(ablation_path)

    requested = int(candidate.get("sample_size_requested") or 0)
    scored = int(candidate.get("sample_size_used") or 0)
    mapping_rejected = requested - scored
    candidate_items = candidate["answer_generation"]["per_query"]
    baseline_items = {
        item["sample_id"]: item for item in baseline["answer_generation"]["per_query"]
    }

    bucket_counts: Counter[str] = Counter()
    bucket_cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidate_items:
        bucket = classify_candidate_item(item)
        bucket_counts[bucket] += 1
        if len(bucket_cases[bucket]) < 20:
            bucket_cases[bucket].append(compact_case(item))

    transition_counts: Counter[str] = Counter()
    candidate_only_by_rank: Counter[str] = Counter()
    for item in candidate_items:
        baseline_item = baseline_items.get(item["sample_id"], {})
        baseline_ok = judge_correct(baseline_item)
        candidate_ok = judge_correct(item)
        if baseline_ok and candidate_ok:
            transition = "both_correct"
        elif baseline_ok and not candidate_ok:
            transition = "baseline_only_correct"
        elif candidate_ok and not baseline_ok:
            transition = "candidate_only_correct"
        else:
            transition = "both_incorrect"
        transition_counts[transition] += 1
        if transition == "candidate_only_correct":
            rank = first_rank(item)
            if rank is None:
                candidate_only_by_rank["no_relevant_top10"] += 1
            elif rank == 1:
                candidate_only_by_rank["top1"] += 1
            else:
                candidate_only_by_rank["top10_not_top1"] += 1

    lexical_judge_matrix: Counter[str] = Counter()
    for item in candidate_items:
        substring = bool(item["scores"]["answer_substring_match"])
        correct = judge_correct(item)
        lexical_judge_matrix[f"substring_{str(substring).lower()}__judge_{str(correct).lower()}"] += 1

    unresolved = requested - bucket_counts["judge_correct_success"]
    scored_failures = scored - bucket_counts["judge_correct_success"]
    mutually_exclusive = {
        "mapping_rejected_before_scoring": summarize_bucket(
            mapping_rejected, requested=requested, scored=scored, failures=unresolved
        ),
        "retrieval_top10_miss": summarize_bucket(
            bucket_counts["retrieval_top10_miss"],
            requested=requested,
            scored=scored,
            failures=unresolved,
        ),
        "top_context_ranking_boundary": summarize_bucket(
            bucket_counts["top_context_ranking_boundary"],
            requested=requested,
            scored=scored,
            failures=unresolved,
        ),
        "top1_answer_synthesis_failure": summarize_bucket(
            bucket_counts["top1_answer_synthesis_failure"],
            requested=requested,
            scored=scored,
            failures=unresolved,
        ),
        "judge_correct_success": {
            "count": bucket_counts["judge_correct_success"],
            "share_of_requested": pct(bucket_counts["judge_correct_success"], requested),
            "share_of_scored": pct(bucket_counts["judge_correct_success"], scored),
        },
    }
    mutually_exclusive["mapping_rejected_before_scoring"]["share_of_scored"] = None

    report = {
        "schema_version": "king-synapse.dmr-failure-mode-taxonomy.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "git": {
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git_value("rev-parse", "HEAD"),
            "origin_main_delta": git_value(
                "rev-list", "--left-right", "--count", "origin/main...HEAD"
            ),
        },
        "inputs": {
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
            "generator_ablation": {
                "path": report_path(ablation_path),
                "sha256": sha256_file(ablation_path),
            },
        },
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
            "judge_failures_among_scored": scored_failures,
            "unresolved_requested_rows": unresolved,
            "generator_policy": candidate.get("generator", {}).get("policy"),
            "retrieval_mode": candidate.get("retrieval_mode"),
            "judge_model": candidate.get("llm_judge", {}).get("model"),
            "accelerator": candidate.get("accelerator", {}),
        },
        "mutually_exclusive_outcome_taxonomy": mutually_exclusive,
        "scored_candidate_failure_counts": dict(sorted(bucket_counts.items())),
        "baseline_to_candidate_judge_transitions": dict(sorted(transition_counts.items())),
        "candidate_only_correct_by_retrieval_bucket": dict(sorted(candidate_only_by_rank.items())),
        "lexical_vs_judge_matrix": dict(sorted(lexical_judge_matrix.items())),
        "mapping_diagnostics": {
            "punctuation_full_answer_coverage": mapping["review"]["policy_coverage"][
                "punctuation_full_answer"
            ],
            "punctuation_full_answer_coverage_ratio": mapping["review"][
                "policy_coverage_ratio"
            ]["punctuation_full_answer"],
            "significant_token_containment_coverage": mapping["review"][
                "policy_coverage"
            ]["significant_token_containment"],
            "diagnostic_only_relaxed_token_note": (
                "Relaxed token containment increases coverage but is not the pinned "
                "local scoring policy."
            ),
        },
        "generator_delta": {
            "baseline_judge_accuracy": baseline["answer_generation"]["aggregate"].get(
                "llm_judge_accuracy"
            ),
            "candidate_judge_accuracy": candidate["answer_generation"]["aggregate"].get(
                "llm_judge_accuracy"
            ),
            "baseline_substring_accuracy": baseline["answer_generation"]["aggregate"].get(
                "answer_substring_accuracy"
            ),
            "candidate_substring_accuracy": candidate["answer_generation"][
                "aggregate"
            ].get("answer_substring_accuracy"),
            "baseline_rouge_l_f1": baseline["answer_generation"]["aggregate"].get(
                "rouge_l_f1_mean"
            ),
            "candidate_rouge_l_f1": candidate["answer_generation"]["aggregate"].get(
                "rouge_l_f1_mean"
            ),
            "candidate_only_correct": transition_counts["candidate_only_correct"],
            "baseline_only_correct": transition_counts["baseline_only_correct"],
            "net_judge_correct_gain": transition_counts["candidate_only_correct"]
            - transition_counts["baseline_only_correct"],
        },
        "sanitized_case_samples": {
            key: value for key, value in sorted(bucket_cases.items())
        },
        "read": {
            "primary_result": (
                "DMR 500 top-context repeats the positive answer-synthesis direction, "
                "but most requested rows remain unresolved under the current local "
                "official-style policy."
            ),
            "main_failure_modes": [
                "Mapping is the largest unresolved requested-row bucket under the pinned punctuation policy.",
                "Retrieval/ranking remains material: many scored rows still lack a relevant top-10 context or place it below rank 1.",
                "Answer synthesis remains material even after a relevant chunk is ranked first.",
                "Chunk-empty failure is not supported by this audit; the committed mapping audits show the larger boundary is answer-to-memory mapping policy, not empty generated chunks.",
            ],
            "next_action": (
                "Keep feature freeze. Use this taxonomy to guide no-model failure "
                "analysis and hosted external comparison; do not change runtime "
                "defaults from this report alone."
            ),
        },
        "limits": [
            "Uses committed sanitized aggregate/per-query reports only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, generated answers, prompts, raw responses, or API keys.",
            "The mutually exclusive taxonomy is based on the top-context judge-scored DMR 500-request / 323-scored local view.",
            "Mapping rejected rows are a scoring/coverage boundary, not proof of runtime retrieval failure.",
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
                "scope": report["scope"],
                "mutually_exclusive_outcome_taxonomy": report[
                    "mutually_exclusive_outcome_taxonomy"
                ],
                "generator_delta": report["generator_delta"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
