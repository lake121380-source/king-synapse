#!/usr/bin/env python
"""Audit whether current Phase 6 changes respect the feature freeze.

This is a no-model/no-external guard. It compares the current work against a
base ref, checks staged/working/untracked paths, and fails if changes touch
protected product/runtime boundaries such as memory schema, cognitive layers,
CLI/MCP surfaces, or runtime ranking/default code.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTECTED_PREFIXES = [
    "crates/core/src/adaptive/",
    "crates/core/src/store/",
    "crates/core/src/working_memory/",
    "crates/cli/src/",
    "crates/mcp-server/src/",
]

PROTECTED_EXACT = {
    "crates/core/Cargo.toml",
    "crates/core/src/config.rs",
    "crates/core/src/embed.rs",
    "crates/core/src/entity.rs",
    "crates/core/src/lib.rs",
    "crates/core/src/model.rs",
    "crates/core/src/rerank.rs",
    "crates/core/src/recall/booster.rs",
    "crates/core/src/recall/cognitive_trace.rs",
    "crates/core/src/recall/engine.rs",
    "crates/core/src/recall/graph_activation.rs",
    "crates/core/src/recall/hit.rs",
    "crates/core/src/recall/latent_activation.rs",
    "crates/core/src/recall/latent_booster.rs",
    "crates/core/src/recall/mod.rs",
    "crates/core/src/recall/query_latent.rs",
    "crates/core/src/recall/rrf.rs",
    "crates/cli/Cargo.toml",
    "crates/mcp-server/Cargo.toml",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Audit Phase 6 feature-freeze path boundaries."
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git ref used as the comparison base for committed local changes.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/phase6-feature-freeze-audit.json",
    )
    return parser.parse_args()


def normalize_path_arg(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def git_value(*args: str, check: bool = True) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root(),
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def git_lines(*args: str, check: bool = True) -> list[str]:
    value = git_value(*args, check=check)
    return value.splitlines() if value else []


def normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def parse_name_status(lines: list[str], source: str) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        changes.append(
            {
                "source": source,
                "status": status,
                "path": normalize_repo_path(path),
            }
        )
    return changes


def parse_untracked_from_status(lines: list[str]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("?? "):
            changes.append(
                {
                    "source": "untracked",
                    "status": "??",
                    "path": normalize_repo_path(line[3:]),
                }
            )
    return changes


def protected_reason(path: str) -> str | None:
    if path in PROTECTED_EXACT:
        return "protected_exact"
    for prefix in PROTECTED_PREFIXES:
        if path.startswith(prefix):
            return f"protected_prefix:{prefix}"
    return None


def collect_changes(base_ref: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    base_commit = git_value("rev-parse", base_ref, check=False)
    head_commit = git_value("rev-parse", "HEAD")
    if base_commit:
        committed = parse_name_status(
            git_lines("diff", "--name-status", f"{base_ref}...HEAD", check=False),
            "committed_since_base",
        )
    else:
        committed = []
    staged = parse_name_status(
        git_lines("diff", "--cached", "--name-status", check=False),
        "staged",
    )
    working = parse_name_status(
        git_lines("diff", "--name-status", check=False),
        "working_tree",
    )
    status_lines = git_lines("status", "--porcelain", check=False)
    untracked = parse_untracked_from_status(status_lines)
    return (
        committed + staged + working + untracked,
        {
            "base_ref": base_ref,
            "base_commit": base_commit,
            "head_commit": head_commit,
            "base_ref_resolved": bool(base_commit),
            "worktree_dirty": bool(status_lines),
            "worktree_status_count": len(status_lines),
        },
    )


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    changes, git_context = collect_changes(args.base_ref)
    protected_changes = []
    for change in changes:
        reason = protected_reason(change["path"])
        if reason:
            protected_changes.append({**change, "reason": reason})

    source_counts: dict[str, int] = {}
    for change in changes:
        source = change["source"]
        source_counts[source] = source_counts.get(source, 0) + 1

    passed = not protected_changes and git_context["base_ref_resolved"]
    return {
        "schema_version": "king-synapse.phase6-feature-freeze-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "git": {
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git_context["head_commit"],
            "origin_main_delta": git_value(
                "rev-list", "--left-right", "--count", "origin/main...HEAD",
                check=False,
            ),
            **git_context,
        },
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "policy": {
            "protected_prefixes": PROTECTED_PREFIXES,
            "protected_exact": sorted(PROTECTED_EXACT),
            "allowed_by_default": [
                "docs/eval/",
                "scripts/eval/",
                "crates/eval/reports/",
                "README.md",
            ],
        },
        "changes": changes,
        "status": {
            "feature_freeze_audit_passed": passed,
            "base_ref_resolved": git_context["base_ref_resolved"],
            "change_count": len(changes),
            "change_source_counts": dict(sorted(source_counts.items())),
            "protected_change_count": len(protected_changes),
            "protected_changes": protected_changes,
            "memory_schema_changed": any(
                change["path"].startswith("crates/core/src/store/")
                for change in protected_changes
            ),
            "cognitive_layer_changed": any(
                change["path"].startswith("crates/core/src/adaptive/")
                or change["path"].startswith("crates/core/src/working_memory/")
                or change["path"].startswith("crates/core/src/recall/")
                for change in protected_changes
            ),
            "cli_or_mcp_surface_changed": any(
                change["path"].startswith("crates/cli/")
                or change["path"].startswith("crates/mcp-server/")
                for change in protected_changes
            ),
            "runtime_default_or_ranking_code_changed": any(
                change["path"]
                in {
                    "crates/core/src/config.rs",
                    "crates/core/src/rerank.rs",
                    "crates/core/src/recall/engine.rs",
                    "crates/core/src/recall/rrf.rs",
                    "crates/core/src/recall/mod.rs",
                }
                for change in protected_changes
            ),
        },
        "read": {
            "current_conclusion": (
                "Current local changes respect the Phase 6 feature-freeze protected boundaries."
                if passed
                else "Current local changes touch protected Phase 6 feature-freeze boundaries."
            ),
            "next_action": (
                "Continue validation-only work."
                if passed
                else "Remove, revert, or explicitly justify protected-boundary changes before continuing."
            ),
        },
        "limits": [
            "This audit is a path-boundary guard, not a semantic proof.",
            "It does not inspect raw benchmark data, run models, call hosted adapters, or run product code.",
            "It uses Git path changes to catch obvious memory schema, cognitive layer, CLI/MCP, and runtime-default edits.",
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
                "feature_freeze_audit_passed": report["status"][
                    "feature_freeze_audit_passed"
                ],
                "change_count": report["status"]["change_count"],
                "protected_change_count": report["status"][
                    "protected_change_count"
                ],
                "protected_changes": report["status"]["protected_changes"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"]["feature_freeze_audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
