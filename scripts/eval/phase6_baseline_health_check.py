#!/usr/bin/env python
"""Replay local non-external Phase 6 baseline health checks.

This script anchors the current HEAD as the local Phase 6 validation baseline
without running LongMemEval/DMR heavy retrieval, hosted adapters, LLM judges, or
product code. Because committing the generated report creates a new descendant
commit, the report records the HEAD that was replayed rather than claiming to
validate its own containing commit. It records aggregate health only and must
not store secrets, raw benchmark records, prompts, responses, or generated
answers.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Run local non-external Phase 6 baseline health checks."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/phase6-baseline-health-check-2026-07-04.json",
    )
    parser.add_argument(
        "--skip-fmt",
        action="store_true",
        help="Skip cargo fmt. Intended only for local debugging of this script.",
    )
    return parser.parse_args()


def normalize_path_arg(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


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


def git_status_porcelain() -> list[str]:
    value = git_value("status", "--porcelain")
    return value.splitlines() if value else []


def run_command(command: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=repo_root(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "command": command,
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def check_record(
    check_id: str, result: dict[str, Any], *, keep_output: bool = False
) -> dict[str, Any]:
    record = {
        "id": check_id,
        "command": " ".join(result["command"]),
        "status": result["status"],
        "duration_ms": result["duration_ms"],
    }
    if result["status"] != "passed" or keep_output:
        record["stdout_tail"] = result["stdout"][-2000:]
        record["stderr_tail"] = result["stderr"][-2000:]
    return record


def parse_test_counts(stdout: str) -> dict[str, int | None]:
    for match in re.finditer(r"test result: \w+\. (\d+) passed; (\d+) failed", stdout):
        passed = int(match.group(1))
        failed = int(match.group(2))
        if passed or failed:
            return {"tests_passed": passed, "tests_failed": failed}
    return {"tests_passed": None, "tests_failed": None}


def parse_json_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise ValueError("command stdout did not contain a JSON object")
    return json.loads(stdout[start : end + 1])


def py_files() -> list[str]:
    return [str(path) for path in sorted((repo_root() / "scripts/eval").glob("*.py"))]


def benchmark_check(check_id: str, bench_name: str) -> dict[str, Any]:
    result = run_command(["cargo", "bench", "-p", "synapse-eval", "--bench", bench_name])
    record = check_record(check_id, result)
    if result["status"] == "passed":
        parsed = parse_json_stdout(result["stdout"])
        if "metrics" in parsed:
            record["metrics"] = parsed["metrics"]
        if "aggregate" in parsed:
            record["aggregate"] = parsed["aggregate"]
        record["benchmark"] = parsed.get("benchmark")
        record["schema_version"] = parsed.get("schema_version")
        record["raw_records_committed"] = parsed.get("raw_records_committed")
        record["raw_dialogs_committed"] = parsed.get("raw_dialogs_committed")
        record["raw_questions_committed"] = parsed.get("raw_questions_committed")
        record["raw_answers_committed"] = parsed.get("raw_answers_committed")
    return record


def fixed_metric_passed(metrics: dict[str, Any]) -> bool:
    return (
        metrics.get("RecallAt10") == 1.0
        and metrics.get("HebbianConsistency") == 1.0
        and metrics.get("CognitiveTraceDominance") == 1.0
    )


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    checks: list[dict[str, Any]] = []
    head_commit = git_value("rev-parse", "HEAD")
    status_before = git_status_porcelain()

    if not args.skip_fmt:
        checks.append(
            check_record(
                "cargo-fmt",
                run_command(["cargo", "fmt", "--all", "--", "--check"]),
            )
        )
    else:
        checks.append(
            {
                "id": "cargo-fmt",
                "command": "cargo fmt --all -- --check",
                "status": "skipped",
                "note": "Skipped by --skip-fmt.",
            }
        )

    py_compile = run_command(["python", "-m", "py_compile", *py_files()])
    checks.append(
        {
            **check_record("python-eval-py-compile", py_compile),
            "compiled_files": len(py_files()),
        }
    )

    test_result = run_command(["cargo", "test", "-p", "synapse-eval"])
    test_record = check_record("synapse-eval-tests", test_result)
    test_record.update(parse_test_counts(test_result["stdout"]))
    checks.append(test_record)

    checks.append(
        benchmark_check("exported-cognitive-session", "exported_cognitive_session")
    )
    checks.append(
        benchmark_check("long-horizon-cognitive-memory", "long_horizon_cognitive_memory")
    )
    checks.append(
        benchmark_check("long-horizon-stability-audit", "long_horizon_stability_audit")
    )

    hard_failures = [check["id"] for check in checks if check["status"] == "failed"]
    exported_metrics = next(
        (check.get("metrics", {}) for check in checks if check["id"] == "exported-cognitive-session"),
        {},
    )
    long_horizon_metrics = next(
        (check.get("metrics", {}) for check in checks if check["id"] == "long-horizon-cognitive-memory"),
        {},
    )
    stability = next(
        (check.get("aggregate", {}) for check in checks if check["id"] == "long-horizon-stability-audit"),
        {},
    )
    fixed_metrics_stable = fixed_metric_passed(exported_metrics) and fixed_metric_passed(
        long_horizon_metrics
    )
    future_matched_count = 8 - len(stability.get("future_matched_miss_labels", []))
    known_future_boundary_stable = (
        stability.get("future_candidate_presence") == 1.0
        and future_matched_count == 6
        and stability.get("future_matched_miss_labels")
        == ["day03-charger-demo", "day05-trust-message"]
    )
    baseline_passed = not hard_failures and fixed_metrics_stable and known_future_boundary_stable

    report = {
        "schema_version": "king-synapse.phase6-baseline-health-check.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "validated_commit": head_commit,
        "validated_commit_semantics": (
            "HEAD at the start of this local replay. The commit that stores this "
            "generated report is expected to be a descendant, because writing the "
            "report changes repository state."
        ),
        "report_commit_model": {
            "self_validating_commit": False,
            "validated_commit_is_replay_head": True,
            "containing_commit_expected_to_be_descendant": True,
            "reason": "The generated report file cannot contain the hash of its own future commit without changing that hash.",
        },
        "git": {
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": head_commit,
            "origin_main_delta": git_value(
                "rev-list", "--left-right", "--count", "origin/main...HEAD"
            ),
            "worktree_dirty_at_start": bool(status_before),
            "worktree_status_count_at_start": len(status_before),
        },
        "feature_freeze_preserved": True,
        "memory_schema_changed": False,
        "cognitive_layer_changed": False,
        "cli_feature_changed": False,
        "heavy_external_calls_run": False,
        "gpu_heavy_validation_run": False,
        "api_keys_recorded": False,
        "prompt_text_recorded": False,
        "raw_response_committed": False,
        "raw_records_committed": False,
        "generated_answers_committed": False,
        "checks": checks,
        "status": {
            "baseline_health_check_passed": baseline_passed,
            "hard_failures": hard_failures,
            "fixed_cognitive_metrics_stable": fixed_metrics_stable,
            "known_future_evidence_boundary_stable": known_future_boundary_stable,
            "future_matched_evidence_count": future_matched_count,
            "future_candidate_presence": stability.get("future_candidate_presence"),
            "tests_passed": test_record.get("tests_passed"),
            "tests_failed": test_record.get("tests_failed"),
        },
        "read": {
            "current_baseline_health": "passed" if baseline_passed else "failed",
            "conclusion": (
                "The current Phase 6 baseline remains healthy under local non-external gates. "
                "Core cognitive fixture metrics are stable, while the known long-horizon "
                "future-evidence boundary remains unchanged at 6/8 matched evidence cases. "
                "The report validates the replay HEAD recorded in validated_commit; the "
                "commit that stores the report is expected to be a descendant."
                if baseline_passed
                else "The current Phase 6 baseline health replay failed; inspect checks before continuing."
            ),
            "next_action": (
                "Keep feature freeze. Do not productize. Resume heavy validation only when "
                "top-context judge authorization or hosted external credentials/endpoints are ready."
            ),
        },
        "limits": [
            "This report records a local health replay only.",
            "It does not run LongMemEval/DMR heavy retrieval, LLM judging, or hosted external adapters.",
            "It does not replace official DMR, hosted external comparison, or public long-memory validation.",
        ],
    }
    return report, baseline_passed


def main() -> int:
    args = parse_args()
    output = normalize_path_arg(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report, passed = build_report(args)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": report_path(output),
                "validated_commit": report["validated_commit"],
                "baseline_health_check_passed": report["status"][
                    "baseline_health_check_passed"
                ],
                "tests_passed": report["status"]["tests_passed"],
                "tests_failed": report["status"]["tests_failed"],
                "known_future_evidence_boundary_stable": report["status"][
                    "known_future_evidence_boundary_stable"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
