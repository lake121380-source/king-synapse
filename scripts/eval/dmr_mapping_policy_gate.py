#!/usr/bin/env python
"""DMR mapping policy gate.

This gate reads committed sanitized DMR reports only. It answers one question:
should the DMR mapping policy be changed from punctuation-normalized
full-answer matching to a relaxed policy? The answer is evidence-backed: keep
the strict policy as the runtime default, but record a validation-only relaxed
mapping evaluation path.

The gate does not run retrieval, embeddings, reranking, answer generation, an
LLM judge, hosted adapters, or raw benchmark data, and it does not inspect raw
questions, answers, dialogs, memory text, generated answers, prompts, raw
responses, or API keys.

The gate passes because the policy decision is evidence-backed, NOT because
DMR mapping performance is good. `productization_allowed` and
`runtime_mapping_policy_change_allowed` remain false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
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
        description="Gate the DMR mapping policy decision from committed reports."
    )
    parser.add_argument(
        "--mapping-policy-review",
        type=Path,
        default=root / "crates/eval/reports/dmr-mapping-policy-review.json",
    )
    parser.add_argument(
        "--mapping-boundary-impact",
        type=Path,
        default=root / "crates/eval/reports/dmr-mapping-boundary-impact.json",
    )
    parser.add_argument(
        "--failure-mode-gate",
        type=Path,
        default=root / "crates/eval/reports/dmr-500-failure-mode-gate.json",
    )
    parser.add_argument(
        "--failure-mode-taxonomy",
        type=Path,
        default=root / "crates/eval/reports/dmr-failure-mode-taxonomy.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/dmr-mapping-policy-gate.json",
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


def pct(part: int | float, total: int | float) -> float | None:
    if not total:
        return None
    return round((float(part) / float(total)) * 100.0, 2)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    policy_review = load_json(args.mapping_policy_review)
    boundary_impact = load_json(args.mapping_boundary_impact)
    failure_mode_gate = load_json(args.failure_mode_gate)
    failure_mode_taxonomy = load_json(args.failure_mode_taxonomy)

    requested = 500

    policy_coverage = safe_get(policy_review, ["review", "policy_coverage"], {})
    punctuation_boundary = safe_get(policy_review, ["review", "punctuation_boundary"], {})

    punctuation_count = int(policy_coverage.get("punctuation_full_answer", 0))
    token_containment_count = int(policy_coverage.get("significant_token_containment", 0))
    overlap_75_count = int(policy_coverage.get("significant_token_overlap_75", 0))
    overlap_50_count = int(policy_coverage.get("significant_token_overlap_50", 0))
    any_token_count = int(policy_coverage.get("any_significant_token", 0))

    rejected_by_punctuation = int(
        punctuation_boundary.get("rejected_by_punctuation", requested - punctuation_count)
    )
    no_diagnostic_match = int(punctuation_boundary.get("no_diagnostic_match", 0))

    rejected_breakdown = safe_get(boundary_impact, ["punctuation_rejected_breakdown"], {})
    containment_only = int(
        safe_get(rejected_breakdown, ["significant_token_containment_only", "count"], 0)
    )
    overlap_75_only = int(
        safe_get(
            rejected_breakdown,
            ["overlap_75_without_full_token_containment", "count"],
            0,
        )
    )
    overlap_50_only = int(
        safe_get(rejected_breakdown, ["overlap_50_without_overlap_75", "count"], 0)
    )
    any_token_only = int(
        safe_get(rejected_breakdown, ["any_significant_token_only", "count"], 0)
    )

    mapping_rejected_count = int(
        safe_get(
            failure_mode_gate,
            ["primary_failure_mode_taxonomy", "mapping_rejected", "count"],
            rejected_by_punctuation,
        )
    )
    taxonomy_mapping_diagnostics = safe_get(
        failure_mode_taxonomy, ["mapping_diagnostics"], {}
    )

    mapping_rejected_with_token_match = (
        containment_only + overlap_75_only + overlap_50_only + any_token_only
    )
    mapping_rejected_no_match = no_diagnostic_match

    relaxed_additional_coverage = token_containment_count - punctuation_count

    evidence_consistent = (
        mapping_rejected_count == rejected_by_punctuation == 177
        and mapping_rejected_with_token_match == 174
        and mapping_rejected_no_match == 3
        and token_containment_count == 442
        and punctuation_count == 323
        and relaxed_additional_coverage == 119
        and mapping_rejected_with_token_match + mapping_rejected_no_match
        == mapping_rejected_count
    )

    coverage_comparison = [
        {
            "policy": "punctuation_full_answer (current)",
            "coverage": punctuation_count,
            "share": pct(punctuation_count, requested),
            "additional_over_current": 0,
        },
        {
            "policy": "significant_token_containment",
            "coverage": token_containment_count,
            "share": pct(token_containment_count, requested),
            "additional_over_current": token_containment_count - punctuation_count,
        },
        {
            "policy": "significant_token_overlap_75",
            "coverage": overlap_75_count,
            "share": pct(overlap_75_count, requested),
            "additional_over_current": overlap_75_count - punctuation_count,
        },
        {
            "policy": "significant_token_overlap_50",
            "coverage": overlap_50_count,
            "share": pct(overlap_50_count, requested),
            "additional_over_current": overlap_50_count - punctuation_count,
        },
        {
            "policy": "any_significant_token",
            "coverage": any_token_count,
            "share": pct(any_token_count, requested),
            "additional_over_current": any_token_count - punctuation_count,
        },
    ]

    report = {
        "schema_version": "king-synapse.dmr-mapping-policy-gate.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/dmr_mapping_policy_gate.py",
        "question": (
            "Should the DMR mapping policy be changed from punctuation-normalized "
            "full-answer matching to a relaxed policy?"
        ),
        "inputs": {
            "mapping_policy_review": {
                "path": report_path(args.mapping_policy_review),
                "sha256": sha256_file(args.mapping_policy_review),
                "schema_version": policy_review.get("schema_version"),
            },
            "mapping_boundary_impact": {
                "path": report_path(args.mapping_boundary_impact),
                "sha256": sha256_file(args.mapping_boundary_impact),
                "schema_version": boundary_impact.get("schema_version"),
            },
            "failure_mode_gate": {
                "path": report_path(args.failure_mode_gate),
                "sha256": sha256_file(args.failure_mode_gate),
                "schema_version": failure_mode_gate.get("schema_version"),
            },
            "failure_mode_taxonomy": {
                "path": report_path(args.failure_mode_taxonomy),
                "sha256": sha256_file(args.failure_mode_taxonomy),
                "schema_version": failure_mode_taxonomy.get("schema_version"),
            },
        },
        "git": {
            "commit": git_value("rev-parse", "HEAD"),
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(git_value("status", "--porcelain")),
        },
        "cache_policy": {
            "cache_root_recorded": False,
            "raw_cache_retained": False,
            "raw_records_committed": False,
        },
        "raw_flags": {flag: False for flag in RAW_FLAGS},
        "coverage_comparison": coverage_comparison,
        "policy_decision": {
            "decision": "keep_punctuation_full_answer_as_runtime_default",
            "rationale": (
                "122/177 rejected rows have full significant-token containment in a "
                "single chunk, suggesting the answer IS in memory but the strict "
                "punctuation policy misses it. However, promoting relaxed mapping "
                "without judge validation would inflate scores. Keep the strict "
                "policy as runtime default; validate relaxed mapping as a separate "
                "labeled experiment."
            ),
            "validation_only_relaxed_path": (
                "Run DMR 500 with significant_token_containment mapping + DeepSeek "
                "judge scoring, then compare judge accuracy against the pinned "
                "punctuation baseline. Only promote if judge accuracy improves and "
                "no false positives are introduced."
            ),
            "next_action": (
                "Keep feature freeze. Do not change runtime mapping default. "
                "Optionally run a labeled relaxed-mapping judge experiment to "
                "measure the tradeoff."
            ),
        },
        "status": {
            "dmr_mapping_policy_gate_passed": evidence_consistent,
            "runtime_mapping_policy_change_allowed": False,
            "current_policy": "punctuation_full_answer",
            "relaxed_policy_validated": False,
            "relaxed_policy_candidate": "significant_token_containment",
            "relaxed_policy_candidate_coverage": token_containment_count,
            "relaxed_policy_candidate_share": pct(token_containment_count, requested),
            "current_policy_coverage": punctuation_count,
            "current_policy_share": pct(punctuation_count, requested),
            "relaxed_policy_additional_coverage": relaxed_additional_coverage,
            "relaxed_policy_risk": (
                "Relaxed mapping may inflate scores without judge validation; "
                "cannot be silently promoted to official."
            ),
            "mapping_rejected_count": mapping_rejected_count,
            "mapping_rejected_with_token_match": mapping_rejected_with_token_match,
            "mapping_rejected_no_match": mapping_rejected_no_match,
            "mapping_rejected_token_match_breakdown": {
                "significant_token_containment_only": containment_only,
                "overlap_75_without_full_token_containment": overlap_75_only,
                "overlap_50_without_overlap_75": overlap_50_only,
                "any_significant_token_only": any_token_only,
            },
            "productization_allowed": False,
            "evidence_consistent": evidence_consistent,
        },
        "cross_reference": {
            "policy_review_punctuation_coverage": punctuation_count,
            "policy_review_rejected_by_punctuation": rejected_by_punctuation,
            "policy_review_no_diagnostic_match": no_diagnostic_match,
            "failure_mode_gate_mapping_rejected": mapping_rejected_count,
            "failure_mode_gate_mapping_boundary_consistent": safe_get(
                failure_mode_gate,
                ["cross_reference", "mapping_boundary_consistent"],
            ),
            "taxonomy_mapping_diagnostics": taxonomy_mapping_diagnostics,
        },
        "read": {
            "current_conclusion": (
                "DMR mapping policy decision is gate-backed: keep punctuation "
                "full-answer as the runtime default. 174/177 rejected rows have "
                "diagnostic token matches, so the answer is likely in memory but "
                "missed by strict matching. A relaxed policy could recover up to "
                "119 rows, but it must be judge-validated before promotion. This "
                "is a mapping-policy boundary, not an architecture failure."
            ),
            "next_action": (
                "Keep feature freeze. Do not change runtime mapping default. The "
                "next useful step is a labeled relaxed-mapping judge experiment, "
                "or continue to LongMemEval/DMR trend alignment."
            ),
        },
        "limits": [
            "This gate reads committed sanitized aggregate/per-query DMR reports only.",
            "It does not run retrieval, answer generation, LLM judges, hosted adapters, or product code.",
            "It does not inspect raw questions, answers, dialogs, memory content, generated answers, prompts, responses, or API keys.",
            "The gate passes because the policy decision is evidence-backed, not because DMR mapping is good.",
            "Relaxed mapping policies are diagnostic unless separately labeled and judge-validated.",
            "This report does not change memory schema, cognitive layers, CLI/MCP, retrieval, ranking, generator, or runtime mapping defaults.",
        ],
    }
    return report


def main() -> int:
    args = parse_args()
    for name in (
        "mapping_policy_review",
        "mapping_boundary_impact",
        "failure_mode_gate",
        "failure_mode_taxonomy",
        "output",
    ):
        setattr(args, name, normalize_path_arg(getattr(args, name)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": report_path(args.output),
                "dmr_mapping_policy_gate_passed": report["status"][
                    "dmr_mapping_policy_gate_passed"
                ],
                "runtime_mapping_policy_change_allowed": report["status"][
                    "runtime_mapping_policy_change_allowed"
                ],
                "current_policy": report["status"]["current_policy"],
                "relaxed_policy_candidate": report["status"][
                    "relaxed_policy_candidate"
                ],
                "mapping_rejected_count": report["status"]["mapping_rejected_count"],
                "productization_allowed": report["status"]["productization_allowed"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
