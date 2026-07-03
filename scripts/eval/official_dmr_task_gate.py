#!/usr/bin/env python
"""Summarize the current official-style DMR task gate.

This gate reads committed sanitized aggregate reports only. It separates the
local official-style DMR evidence from the still-open published-comparable DMR
claim. It does not run retrieval, generation, hosted adapters, LLM judges, or
raw benchmark data.
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
        description="Summarize official-style DMR task readiness from committed reports."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-task-gate.json",
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


def input_paths(root: Path) -> dict[str, Path]:
    return {
        "official_dmr_50": root / "crates/eval/reports/official-dmr-50.json",
        "official_dmr_200": root / "crates/eval/reports/official-dmr-200.json",
        "official_dmr_500": root / "crates/eval/reports/official-dmr-500.json",
        "top_context_50": root
        / "crates/eval/reports/official-dmr-50-top-context-extractive.json",
        "top_context_200": root
        / "crates/eval/reports/official-dmr-200-top-context-extractive.json",
        "top_context_500": root
        / "crates/eval/reports/official-dmr-500-top-context-extractive.json",
        "answer_synthesis_audit": root
        / "crates/eval/reports/official-dmr-answer-synthesis-audit.json",
        "generator_ablation_summary": root
        / "crates/eval/reports/official-dmr-generator-ablation-summary.json",
        "bottleneck_taxonomy": root
        / "crates/eval/reports/official-dmr-bottleneck-taxonomy.json",
        "mapping_policy_review": root
        / "crates/eval/reports/dmr-mapping-policy-review.json",
        "top_context_judge_preflight": root
        / "crates/eval/reports/official-dmr-top-context-judge-preflight.json",
    }


def raw_policy_clean(reports: dict[str, dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {}
    dirty = False
    for name, report in reports.items():
        flags = {flag: bool(report.get(flag)) for flag in RAW_FLAGS if flag in report}
        if any(flags.values()):
            dirty = True
        details[name] = flags
    return not dirty, details


def answer_surface_present(report: dict[str, Any]) -> bool:
    aggregate = safe_get(report, ["answer_generation", "aggregate"], {})
    required = [
        "exact_accuracy",
        "punctuation_accuracy",
        "answer_substring_accuracy",
        "rouge_l_f1_mean",
        "llm_judge_status_counts",
        "llm_judge_accuracy",
    ]
    return all(key in aggregate for key in required)


def judge_count(report: dict[str, Any]) -> int:
    return int(
        safe_get(report, ["answer_generation", "aggregate", "llm_judge_status_counts", "judged"], 0)
        or 0
    )


def run_summary(report: dict[str, Any]) -> dict[str, Any]:
    aggregate = safe_get(report, ["answer_generation", "aggregate"], {})
    retrieval = report.get("retrieval", {})
    requested = int(report.get("sample_size_requested") or 0)
    scored = int(report.get("sample_size_used") or aggregate.get("n_queries") or 0)
    return {
        "requested": requested,
        "scored": scored,
        "mapping_skipped": max(requested - scored, 0),
        "answer_match_policy": report.get("answer_match_policy"),
        "retrieval_mode": report.get("retrieval_mode"),
        "generator_policy": safe_get(report, ["generator", "policy"]),
        "accelerator_requested": safe_get(report, ["accelerator", "requested"]),
        "cuda_device_id": safe_get(report, ["accelerator", "cuda_device_id"]),
        "retrieval_recall_at_10": retrieval.get("recall_at_10"),
        "retrieval_mrr_at_10": retrieval.get("mrr_at_10"),
        "exact_accuracy": aggregate.get("exact_accuracy"),
        "punctuation_accuracy": aggregate.get("punctuation_accuracy"),
        "answer_substring_accuracy": aggregate.get("answer_substring_accuracy"),
        "rouge_l_f1_mean": aggregate.get("rouge_l_f1_mean"),
        "llm_judge_count": judge_count(report),
        "llm_judge_accuracy": aggregate.get("llm_judge_accuracy"),
    }


def item(
    item_id: str,
    status: str,
    *,
    evidence: list[Path],
    conclusion: str,
    remaining: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "status": status,
        "evidence": [report_path(path) for path in evidence],
        "conclusion": conclusion,
        "remaining": remaining or [],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    paths = input_paths(root)
    reports = {name: load_json(path) for name, path in paths.items()}
    raw_clean, raw_details = raw_policy_clean(reports)

    baseline_names = ["official_dmr_50", "official_dmr_200", "official_dmr_500"]
    top_context_names = ["top_context_50", "top_context_200", "top_context_500"]
    baseline_reports = [reports[name] for name in baseline_names]
    top_context_reports = [reports[name] for name in top_context_names]
    baseline_runs = {
        "dmr_50": run_summary(reports["official_dmr_50"]),
        "dmr_200": run_summary(reports["official_dmr_200"]),
        "dmr_500_request": run_summary(reports["official_dmr_500"]),
    }
    top_context_runs = {
        "dmr_50": run_summary(reports["top_context_50"]),
        "dmr_200": run_summary(reports["top_context_200"]),
        "dmr_500_request": run_summary(reports["top_context_500"]),
    }

    answer_surface_ok = all(answer_surface_present(report) for report in baseline_reports)
    baseline_judge_backed = all(
        judge_count(report) == int(report.get("sample_size_used") or 0)
        for report in baseline_reports
    )
    top_context_judge_count = sum(judge_count(report) for report in top_context_reports)
    top_context_not_judged = top_context_judge_count == 0
    cuda_device_0 = all(
        safe_get(report, ["accelerator", "requested"]) == "cuda"
        and str(safe_get(report, ["accelerator", "cuda_device_id"])) == "0"
        for report in baseline_reports + top_context_reports
    )
    dmr_50_200_complete = (
        baseline_runs["dmr_50"]["requested"] == baseline_runs["dmr_50"]["scored"] == 50
        and baseline_runs["dmr_200"]["requested"] == baseline_runs["dmr_200"]["scored"] == 200
    )
    dmr_500_honest_partial = (
        baseline_runs["dmr_500_request"]["requested"] == 500
        and baseline_runs["dmr_500_request"]["scored"] == 323
        and safe_get(
            reports["mapping_policy_review"],
            ["review", "punctuation_boundary", "rejected_by_punctuation"],
        )
        == 177
    )
    bottlenecks_separated = all(
        key in reports["bottleneck_taxonomy"]
        for key in ["mapping_boundary", "largest_local_view", "read"]
    )
    generator_direction_repeats = bool(
        safe_get(
            reports["generator_ablation_summary"],
            ["aggregate_findings", "candidate_improves_substring_on_all_scale_views"],
        )
    ) and bool(
        safe_get(
            reports["generator_ablation_summary"],
            ["aggregate_findings", "candidate_improves_rouge_l_f1_on_all_scale_views"],
        )
    )
    preflight_status = safe_get(
        reports["top_context_judge_preflight"], ["result", "status"]
    )

    checks = [
        item(
            "answer_generation_scoring_surface_present",
            "satisfied" if answer_surface_ok else "failed",
            evidence=[paths[name] for name in baseline_names],
            conclusion=(
                "Pinned extractive DMR reports include exact, punctuation-normalized, substring, ROUGE-L, and LLM judge surfaces."
                if answer_surface_ok
                else "At least one pinned extractive DMR report is missing a required answer scoring surface."
            ),
        ),
        item(
            "baseline_extractive_judge_backed",
            "satisfied" if baseline_judge_backed else "failed",
            evidence=[paths[name] for name in baseline_names],
            conclusion=(
                "Pinned extractive DMR reports are fully judge-backed for their scored rows."
                if baseline_judge_backed
                else "At least one pinned extractive DMR report has unjudged scored rows."
            ),
        ),
        item(
            "cuda_device_0_for_pinned_runs",
            "satisfied" if cuda_device_0 else "failed",
            evidence=[paths[name] for name in baseline_names + top_context_names],
            conclusion=(
                "Pinned official-style DMR and top-context ablation reports record CUDA device 0."
                if cuda_device_0
                else "At least one pinned official-style DMR report does not record CUDA device 0."
            ),
        ),
        item(
            "dmr_50_200_fully_scored",
            "satisfied" if dmr_50_200_complete else "failed",
            evidence=[paths["official_dmr_50"], paths["official_dmr_200"]],
            conclusion=(
                "DMR 50 and DMR 200 are fully scored under the pinned punctuation mapping policy."
                if dmr_50_200_complete
                else "DMR 50 or DMR 200 is not fully scored under the pinned policy."
            ),
        ),
        item(
            "dmr_500_request_honestly_partial",
            "satisfied" if dmr_500_honest_partial else "failed",
            evidence=[paths["official_dmr_500"], paths["mapping_policy_review"]],
            conclusion=(
                "The DMR 500-request view is honestly recorded as 323 scored rows and 177 punctuation-mapping rejections."
                if dmr_500_honest_partial
                else "The DMR 500-request mapping boundary does not match the expected 323/500 local view."
            ),
        ),
        item(
            "bottlenecks_separated",
            "satisfied" if bottlenecks_separated else "failed",
            evidence=[paths["bottleneck_taxonomy"]],
            conclusion=(
                "Mapping coverage, retrieval/ranking, and answer synthesis are separated in the committed taxonomy."
                if bottlenecks_separated
                else "The DMR bottleneck taxonomy is missing required sections."
            ),
        ),
        item(
            "top_context_direction_repeats",
            "partial" if generator_direction_repeats else "failed",
            evidence=[paths["generator_ablation_summary"]],
            conclusion=(
                "Top-context extraction improves substring and ROUGE-L on every current scale view, but remains evaluation-only."
                if generator_direction_repeats
                else "The top-context generator direction does not consistently improve current scale views."
            ),
            remaining=["Judge-score top-context before making stronger answer-quality claims."],
        ),
        item(
            "top_context_candidate_judge_scoring",
            "blocked_external" if top_context_not_judged else "satisfied",
            evidence=[
                paths["top_context_50"],
                paths["top_context_200"],
                paths["top_context_500"],
                paths["top_context_judge_preflight"],
            ],
            conclusion=(
                f"Top-context candidate judge scoring is not complete; latest preflight status is {preflight_status}."
                if top_context_not_judged
                else "Top-context candidate reports contain judge-scored rows."
            ),
            remaining=[] if not top_context_not_judged else ["Provide valid judge authorization and rerun top-context DMR judge scoring."],
        ),
        item(
            "raw_or_generated_data_not_committed",
            "satisfied" if raw_clean else "failed",
            evidence=list(paths.values()),
            conclusion=(
                "Audited DMR reports do not record committed raw records, prompts, responses, answers, dialogs, memory content, or generated answers."
                if raw_clean
                else "At least one audited DMR report records committed raw or generated data."
            ),
        ),
    ]

    hard_failures = [entry["id"] for entry in checks if entry["status"] == "failed"]
    local_official_style_gate_passed = not hard_failures and all(
        entry["status"] in {"satisfied", "partial", "blocked_external"}
        for entry in checks
    )
    published_comparable_ready = False

    input_metadata = {
        name: {
            "path": report_path(path),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for name, path in paths.items()
    }

    status_counts: dict[str, int] = {}
    for entry in checks:
        status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1

    return {
        "schema_version": "king-synapse.official-dmr-task-gate.v1",
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
        "raw_policy": {"clean": raw_clean, "details": raw_details},
        "baseline_runs": baseline_runs,
        "top_context_runs": top_context_runs,
        "mapping_boundary": reports["bottleneck_taxonomy"]["mapping_boundary"],
        "largest_local_view": reports["bottleneck_taxonomy"]["largest_local_view"],
        "checks": checks,
        "status_counts": status_counts,
        "status": {
            "local_official_style_dmr_gate_passed": local_official_style_gate_passed,
            "published_comparable_official_dmr_ready": published_comparable_ready,
            "top_context_judge_ready": not top_context_not_judged,
            "runtime_generator_change_allowed": False,
            "runtime_ranking_change_allowed": False,
            "hard_failures": hard_failures,
            "open_gates": [
                "top_context_candidate_not_judge_scored",
                "published_comparable_mapping_policy_not_final",
                "answer_synthesis_quality_not_ready_for_official_claims",
            ],
        },
        "read": {
            "current_conclusion": (
                "Official-style DMR is locally executable and judge-backed for the pinned extractive baseline, "
                "but it is not yet a published-comparable official DMR result."
            ),
            "strongest_supported_result": (
                "The baseline path now covers retrieval -> answer generation -> exact/punctuation/ROUGE-L/LLM judge scoring on DMR 50, 200, and a 500-request/323-scored CUDA view."
            ),
            "weak_surfaces": [
                "DMR 500-request has 177 punctuation-mapping rejections before scoring.",
                "The largest local view still has 114 scored samples without a relevant top-10 retrieval.",
                "The largest local view has 118 top-1 retrieval hits whose extractive answer misses the gold substring.",
                "Top-context extraction improves lexical metrics but is not judge-scored and still leaves 90 top-1 misses on the largest local view.",
            ],
            "next_action": (
                "Keep feature freeze. If judge authorization is fixed, run judge-scored top-context DMR 50; "
                "otherwise keep DMR work limited to validation-only diagnostics and do not change runtime defaults."
            ),
        },
        "limits": [
            "This gate reads committed sanitized aggregate DMR reports only.",
            "It does not rerun retrieval, answer generation, LLM judges, hosted adapters, or product code.",
            "It does not inspect raw questions, answers, dialogs, memory content, generated answers, prompts, responses, or API keys.",
            "A passing local official-style DMR gate is not a published-comparable official DMR claim.",
        ],
    }


def main() -> None:
    args = parse_args()
    output = normalize_path_arg(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": report_path(output),
                "local_official_style_dmr_gate_passed": report["status"][
                    "local_official_style_dmr_gate_passed"
                ],
                "published_comparable_official_dmr_ready": report["status"][
                    "published_comparable_official_dmr_ready"
                ],
                "top_context_judge_ready": report["status"]["top_context_judge_ready"],
                "open_gates": report["status"]["open_gates"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
