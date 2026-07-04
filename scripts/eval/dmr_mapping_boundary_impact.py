#!/usr/bin/env python
"""Summarize the DMR mapping boundary using sanitized reports only."""

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
    parser = argparse.ArgumentParser(description="Summarize DMR mapping-boundary impact.")
    parser.add_argument(
        "--mapping-policy-review",
        type=Path,
        default=root / "crates/eval/reports/dmr-mapping-policy-review.json",
    )
    parser.add_argument(
        "--failure-taxonomy",
        type=Path,
        default=root / "crates/eval/reports/dmr-failure-mode-taxonomy.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/dmr-mapping-boundary-impact.json",
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


def pct(part: int | float, total: int | float) -> float | None:
    return round((float(part) / float(total)) * 100.0, 2) if total else None


def bucket(count: int, *, requested: int, rejected: int) -> dict[str, Any]:
    return {
        "count": count,
        "share_of_requested": pct(count, requested),
        "share_of_punctuation_rejected": pct(count, rejected),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    mapping_path = normalize_path_arg(args.mapping_policy_review)
    failure_path = normalize_path_arg(args.failure_taxonomy)

    mapping = load_json(mapping_path)
    failure = load_json(failure_path)

    review = mapping["review"]
    rows = review["rows"]
    policy_coverage = review["policy_coverage"]
    policy_ratio = review["policy_coverage_ratio"]
    first_match = review["incremental_first_match"]
    boundary = review["punctuation_boundary"]

    requested = int(rows["source_rows"])
    punctuation_accepted = int(boundary["accepted_by_punctuation"])
    punctuation_rejected = int(boundary["rejected_by_punctuation"])

    token_only = int(boundary["token_containment_rejected_by_punctuation"])
    overlap_75_only = int(boundary["overlap_75_rejected_by_punctuation_and_token_containment"])
    overlap_50_only = int(boundary["overlap_50_rejected_by_punctuation_token_and_overlap75"])
    any_token_only = int(boundary["any_token_rejected_by_stronger_policies"])
    no_diagnostic = int(boundary["no_diagnostic_match"])

    diagnostic_union_rows = {
        "pinned_punctuation": punctuation_accepted,
        "punctuation_or_significant_token_containment": punctuation_accepted + token_only,
        "punctuation_or_overlap_75": punctuation_accepted + token_only + overlap_75_only,
        "punctuation_or_overlap_50": (
            punctuation_accepted + token_only + overlap_75_only + overlap_50_only
        ),
        "punctuation_or_any_significant_token": (
            punctuation_accepted
            + token_only
            + overlap_75_only
            + overlap_50_only
            + any_token_only
        ),
    }

    report = {
        "schema_version": "king-synapse.dmr-mapping-boundary-impact.v1",
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
            "mapping_policy_review": {
                "path": report_path(mapping_path),
                "sha256": sha256_file(mapping_path),
            },
            "failure_taxonomy": {
                "path": report_path(failure_path),
                "sha256": sha256_file(failure_path),
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
            "requested_rows": requested,
            "rows_with_question_answer_and_chunks": rows["rows_with_question_answer_and_chunks"],
            "empty_memory_chunks": rows["empty_memory_chunks"],
            "punctuation_full_answer_accepted": punctuation_accepted,
            "punctuation_full_answer_rejected": punctuation_rejected,
            "failure_taxonomy_mapping_rejected": failure["scope"][
                "mapping_rejected_before_scoring"
            ],
        },
        "policy_coverage": {
            "strict_whitespace_full_answer": {
                "count": policy_coverage["strict_whitespace_full_answer"],
                "share_of_requested": pct(
                    policy_coverage["strict_whitespace_full_answer"], requested
                ),
            },
            "punctuation_full_answer": {
                "count": policy_coverage["punctuation_full_answer"],
                "share_of_requested": pct(policy_coverage["punctuation_full_answer"], requested),
            },
            "significant_token_containment": {
                "count": policy_coverage["significant_token_containment"],
                "share_of_requested": pct(
                    policy_coverage["significant_token_containment"], requested
                ),
            },
            "significant_token_overlap_75": {
                "count": policy_coverage["significant_token_overlap_75"],
                "share_of_requested": pct(
                    policy_coverage["significant_token_overlap_75"], requested
                ),
            },
            "significant_token_overlap_50": {
                "count": policy_coverage["significant_token_overlap_50"],
                "share_of_requested": pct(
                    policy_coverage["significant_token_overlap_50"], requested
                ),
            },
            "any_significant_token": {
                "count": policy_coverage["any_significant_token"],
                "share_of_requested": pct(policy_coverage["any_significant_token"], requested),
            },
        },
        "policy_coverage_ratio_from_source": policy_ratio,
        "incremental_first_match": first_match,
        "punctuation_rejected_breakdown": {
            "significant_token_containment_only": bucket(
                token_only, requested=requested, rejected=punctuation_rejected
            ),
            "overlap_75_without_full_token_containment": bucket(
                overlap_75_only, requested=requested, rejected=punctuation_rejected
            ),
            "overlap_50_without_overlap_75": bucket(
                overlap_50_only, requested=requested, rejected=punctuation_rejected
            ),
            "any_significant_token_only": bucket(
                any_token_only, requested=requested, rejected=punctuation_rejected
            ),
            "no_diagnostic_match": bucket(
                no_diagnostic, requested=requested, rejected=punctuation_rejected
            ),
        },
        "diagnostic_union_if_separately_labeled": {
            key: {
                "count": value,
                "share_of_requested": pct(value, requested),
            }
            for key, value in diagnostic_union_rows.items()
        },
        "read": {
            "primary_result": (
                "The 177 punctuation-rejected rows are mostly a mapping/scoring "
                "boundary, not evidence of empty memory chunks."
            ),
            "key_numbers": [
                "0/500 rows have empty memory chunks.",
                "122/177 punctuation-rejected rows contain all significant answer tokens in one memory chunk.",
                "174/177 punctuation-rejected rows have at least one diagnostic significant-token match.",
                "3/177 punctuation-rejected rows have no diagnostic significant-token match.",
            ],
            "official_boundary": (
                "The pinned local DMR policy remains punctuation-normalized full-answer "
                "matching. Relaxed diagnostic rows must not be silently counted as "
                "official hits without a separately labeled judge/manual validation."
            ),
            "architecture_read": (
                "This does not disprove Synapse's memory architecture. It narrows a "
                "major unresolved branch to mapping-policy validation before stronger "
                "published-comparable DMR claims."
            ),
            "next_action": (
                "Keep feature freeze. If DMR proof continues without hosted competitors, "
                "validate a separately labeled relaxed mapping policy with judge/manual "
                "checks rather than changing runtime defaults."
            ),
        },
        "limits": [
            "Uses committed sanitized mapping and failure-taxonomy reports only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, generated answers, prompts, raw responses, or API keys.",
            "Diagnostic union coverage is not an official DMR score.",
            "This report does not change memory schema, cognitive layers, CLI/MCP, retrieval, ranking, generator, or scoring defaults.",
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
                "punctuation_rejected_breakdown": report["punctuation_rejected_breakdown"],
                "read": report["read"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
