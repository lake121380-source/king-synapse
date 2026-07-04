#!/usr/bin/env python
"""Audit whether Phase 6 report input hashes still match current files.

This is a no-model/no-external consistency check. It reads committed aggregate
reports, inspects their `inputs` path/sha256 records, and reports whether those
inputs still match the current workspace. It does not run retrieval, ranking,
generation, hosted adapters, LLM judges, product code, or raw benchmark data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REPORTS = [
    "crates/eval/reports/phase6-requirements-audit.json",
    "crates/eval/reports/phase6-objective-coverage-audit.json",
    "crates/eval/reports/official-dmr-task-gate.json",
    "crates/eval/reports/longmem-dmr-trend-alignment.json",
    "crates/eval/reports/ranking-objective-split-decision.json",
    "crates/eval/reports/ranking-task-gate.json",
    "crates/eval/reports/deepseek-external-protocol-gate.json",
    "crates/eval/reports/hosted-external-preconditions.json",
    "crates/eval/reports/external-comparison-task-gate.json",
    "crates/eval/reports/long-horizon-task-gate.json",
    "crates/eval/reports/productization-decision-gate.json",
    "crates/eval/reports/next-validation-action-gate.json",
    "crates/eval/reports/readme-claims-support-audit.json",
    "crates/eval/reports/phase6-current-system-gate.json",
]

ALLOWED_CYCLE_LAG_EDGES = {
    (
        "crates/eval/reports/phase6-requirements-audit.json",
        "crates/eval/reports/productization-decision-gate.json",
    ),
    (
        "crates/eval/reports/phase6-requirements-audit.json",
        "crates/eval/reports/next-validation-action-gate.json",
    ),
    (
        "crates/eval/reports/phase6-objective-coverage-audit.json",
        "crates/eval/reports/productization-decision-gate.json",
    ),
    (
        "crates/eval/reports/phase6-objective-coverage-audit.json",
        "crates/eval/reports/next-validation-action-gate.json",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Audit Phase 6 report input-hash freshness."
    )
    parser.add_argument(
        "--reports",
        nargs="+",
        type=Path,
        default=[root / path for path in DEFAULT_REPORTS],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/phase6-evidence-freshness-audit.json",
    )
    return parser.parse_args()


def normalize_path_arg(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def edge_path(value: str | None) -> str | None:
    return value.replace("\\", "/") if value else value


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


def extract_input_records(inputs: Any, prefix: str = "") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(inputs, dict):
        has_record_shape = "path" in inputs and ("sha256" in inputs or "exists" in inputs)
        if has_record_shape:
            records.append(
                {
                    "input_id": prefix.rstrip("."),
                    "path": inputs.get("path"),
                    "recorded_exists": inputs.get("exists"),
                    "recorded_sha256": inputs.get("sha256"),
                }
            )
        else:
            for key, value in inputs.items():
                records.extend(extract_input_records(value, f"{prefix}{key}."))
    elif isinstance(inputs, list):
        for index, value in enumerate(inputs):
            records.extend(extract_input_records(value, f"{prefix}{index}."))
    return records


def audit_record(report: Path, input_record: dict[str, Any]) -> dict[str, Any]:
    raw_path = input_record.get("path")
    current_path = normalize_path_arg(Path(raw_path)) if raw_path else None
    current_exists = bool(current_path and current_path.exists())
    current_sha = sha256_file(current_path) if current_path and current_path.exists() else None
    recorded_sha = input_record.get("recorded_sha256")
    recorded_exists = input_record.get("recorded_exists")
    report_rel = report_path(report)
    input_rel = report_path(current_path) if current_path else raw_path
    if recorded_exists is False and not current_exists:
        status = "fresh_missing"
    elif recorded_exists is False and current_exists:
        status = "exists_changed"
    elif recorded_exists is True and not current_exists:
        status = "missing_now"
    elif recorded_sha and current_sha == recorded_sha:
        status = "fresh"
    elif (
        recorded_sha
        and current_sha
        and (edge_path(report_rel), edge_path(input_rel)) in ALLOWED_CYCLE_LAG_EDGES
    ):
        status = "cycle_lag"
    elif recorded_sha:
        status = "stale_sha"
    else:
        status = "unhashed"

    return {
        "report": report_rel,
        "input_id": input_record.get("input_id"),
        "input_path": raw_path,
        "status": status,
        "recorded_exists": recorded_exists,
        "current_exists": current_exists,
        "recorded_sha256": recorded_sha,
        "current_sha256": current_sha,
        "cycle_lag_allowed": status == "cycle_lag",
    }


def audit_report(path: Path) -> dict[str, Any]:
    report = load_json(path)
    input_records = extract_input_records(report.get("inputs", {}))
    audited = [audit_record(path, record) for record in input_records]
    status_counts: dict[str, int] = {}
    for record in audited:
        status = record["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    stale = [
        record
        for record in audited
        if record["status"] not in {"fresh", "fresh_missing", "unhashed", "cycle_lag"}
    ]
    return {
        "report": report_path(path),
        "exists": path.exists(),
        "schema_version": report.get("schema_version"),
        "generated_at": report.get("generated_at"),
        "runner": report.get("runner"),
        "git_commit_recorded": (report.get("git") or {}).get("commit"),
        "input_count": len(audited),
        "status_counts": dict(sorted(status_counts.items())),
        "fresh": not stale,
        "stale_inputs": stale,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    reports = [normalize_path_arg(path) for path in args.reports]
    report_audits = [audit_report(path) for path in reports]
    stale_reports = [report for report in report_audits if not report["fresh"]]
    cycle_lag_reports = [
        report
        for report in report_audits
        if report["status_counts"].get("cycle_lag", 0) > 0
    ]
    no_input_reports = [
        report["report"] for report in report_audits if report["input_count"] == 0
    ]
    status_counts: dict[str, int] = {}
    for report in report_audits:
        for status, count in report["status_counts"].items():
            status_counts[status] = status_counts.get(status, 0) + count

    return {
        "schema_version": "king-synapse.phase6-evidence-freshness-audit.v1",
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
        "reports": report_audits,
        "status": {
            "evidence_freshness_audit_passed": not stale_reports,
            "reports_checked": len(report_audits),
            "reports_with_no_inputs": no_input_reports,
            "stale_report_count": len(stale_reports),
            "stale_reports": [report["report"] for report in stale_reports],
            "cycle_lag_report_count": len(cycle_lag_reports),
            "cycle_lag_reports": [report["report"] for report in cycle_lag_reports],
            "input_status_counts": dict(sorted(status_counts.items())),
        },
        "read": {
            "current_conclusion": (
                "All audited Phase 6 report input hashes match current files, aside from allowed aggregate-report cycle lag."
                if not stale_reports
                else "At least one audited Phase 6 report has stale input hashes."
            ),
            "next_action": (
                "Keep using the current evidence chain."
                if not stale_reports
                else "Regenerate stale reports in dependency order before using them for decisions."
            ),
        },
        "limits": [
            "This audit checks recorded input file hashes only.",
            "It does not prove benchmark correctness or rerun benchmark logic.",
            "Report git commit fields may point to the replay/generation HEAD rather than the future commit that stores the generated report.",
            "Allowed cycle lag is limited to documented aggregate-report cycles where requirements/objective coverage read productization/next-action gates that also read the top-level audits.",
            "The audit intentionally does not include itself as an input to avoid a self-reference loop.",
        ],
    }


def main() -> int:
    args = parse_args()
    output = normalize_path_arg(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": report_path(output),
                "evidence_freshness_audit_passed": report["status"][
                    "evidence_freshness_audit_passed"
                ],
                "reports_checked": report["status"]["reports_checked"],
                "stale_report_count": report["status"]["stale_report_count"],
                "stale_reports": report["status"]["stale_reports"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"]["evidence_freshness_audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
