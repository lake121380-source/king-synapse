#!/usr/bin/env python
"""Audit hosted/official external-comparison preconditions.

This no-model audit answers why the next Phase 6 hosted external comparison
cannot run in the current environment, and what exact configuration boundary
must close before it can run. It records environment variable presence only,
never secret values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HOSTED_ENV_VARS = [
    "OPENAI_API_KEY",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "MEM0_CONFIG_JSON",
    "MEM0_CONFIG_PATH",
    "LETTA_API_KEY",
    "LETTA_BASE_URL",
    "LETTA_ENVIRONMENT",
    "DEEPSEEK_API_KEY",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Audit hosted external comparison preconditions."
    )
    parser.add_argument(
        "--next-gate-readiness",
        type=Path,
        default=root / "crates/eval/reports/phase6-next-gate-readiness.json",
    )
    parser.add_argument(
        "--hosted-external-report",
        type=Path,
        default=root / "crates/eval/reports/external-comparison-hosted.json",
    )
    parser.add_argument(
        "--external-manifest",
        type=Path,
        default=root / "crates/eval/reports/external-comparison-manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/hosted-external-preconditions.json",
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


def env_presence(names: list[str]) -> dict[str, bool]:
    return {name: bool(os.environ.get(name)) for name in names}


def requirement_group(
    group_id: str,
    *,
    required_all: list[str] | None = None,
    required_any: list[str] | None = None,
    env: dict[str, bool],
    note: str,
) -> dict[str, Any]:
    required_all = required_all or []
    required_any = required_any or []
    missing_all = [name for name in required_all if not env.get(name)]
    any_satisfied = not required_any or any(env.get(name) for name in required_any)
    ready = not missing_all and any_satisfied
    return {
        "id": group_id,
        "ready": ready,
        "required_all": required_all,
        "required_any": required_any,
        "present_all": [name for name in required_all if env.get(name)],
        "missing_all": missing_all,
        "present_any": [name for name in required_any if env.get(name)],
        "missing_any": [] if any_satisfied else required_any,
        "note": note,
    }


def system_statuses(report: dict[str, Any]) -> dict[str, str]:
    return {
        str(system.get("system")): str(system.get("status"))
        for system in report.get("systems", [])
    }


def blocking_reasons(*reasons: str | None) -> list[str]:
    return [reason for reason in reasons if reason]


def manifest_system(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    for system in manifest.get("systems", []):
        if system.get("system") == name:
            return system
    return {}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    readiness_path = normalize_path_arg(args.next_gate_readiness)
    hosted_path = normalize_path_arg(args.hosted_external_report)
    manifest_path = normalize_path_arg(args.external_manifest)

    readiness = load_json(readiness_path)
    hosted = load_json(hosted_path)
    manifest = load_json(manifest_path)
    env = env_presence(HOSTED_ENV_VARS)
    letta_environment_local = (
        os.environ.get("LETTA_ENVIRONMENT", "").strip().lower() == "local"
    )
    env["LETTA_ENVIRONMENT_LOCAL_MODE"] = letta_environment_local

    graphiti = requirement_group(
        "hosted_graphiti_zep",
        required_all=["OPENAI_API_KEY", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"],
        env=env,
        note="Required for hosted/standard Graphiti/Zep Neo4j/OpenAI comparison.",
    )
    mem0 = requirement_group(
        "official_mem0",
        required_any=["OPENAI_API_KEY", "MEM0_CONFIG_JSON", "MEM0_CONFIG_PATH"],
        env=env,
        note=(
            "Official/recommended Mem0 comparison needs OpenAI defaults or an explicit "
            "Mem0 config. The automatic DeepSeek + deterministic local embedder "
            "fallback is a local OSS comparison and is not counted as hosted/official."
        ),
    )
    letta = requirement_group(
        "live_or_local_letta",
        required_any=["LETTA_API_KEY", "LETTA_BASE_URL", "LETTA_ENVIRONMENT_LOCAL_MODE"],
        env=env,
        note="Required for a real hosted or local Letta endpoint measurement.",
    )

    all_ready = bool(graphiti["ready"] and mem0["ready"] and letta["ready"])
    hosted_summary = hosted.get("summary", {})
    hosted_statuses = system_statuses(hosted)
    deepseek_only = bool(
        env.get("DEEPSEEK_API_KEY")
        and not env.get("OPENAI_API_KEY")
        and not env.get("MEM0_CONFIG_JSON")
        and not env.get("MEM0_CONFIG_PATH")
    )
    hosted_probe_matches_blocked_state = (
        hosted_summary.get("measured_systems") == 1
        and hosted_summary.get("not_configured_systems") == 3
        and hosted_summary.get("failed_systems") == 0
        and hosted_statuses.get("King Synapse") == "measured"
        and hosted_statuses.get("Graphiti/Zep") == "not_configured"
        and hosted_statuses.get("Mem0") == "not_configured"
        and hosted_statuses.get("Letta") == "not_configured"
    )
    next_gate_agrees = (
        safe_get(readiness, ["hosted_external", "ready"]) is False
        and safe_get(readiness, ["read", "next_gate_ready"]) is False
    )
    secrets_clean = all(
        system.get("secrets_recorded") is not True for system in manifest.get("systems", [])
    )

    hard_failures = []
    if not hosted_probe_matches_blocked_state:
        hard_failures.append("hosted_probe_state_unexpected")
    if not next_gate_agrees:
        hard_failures.append("next_gate_readiness_disagrees")
    if not secrets_clean:
        hard_failures.append("external_manifest_records_secret_values")

    return {
        "schema_version": "king-synapse.hosted-external-preconditions.v1",
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
            "next_gate_readiness": {
                "path": report_path(readiness_path),
                "sha256": sha256_file(readiness_path),
            },
            "hosted_external_report": {
                "path": report_path(hosted_path),
                "sha256": sha256_file(hosted_path),
                "summary": hosted_summary,
            },
            "external_manifest": {
                "path": report_path(manifest_path),
                "sha256": sha256_file(manifest_path),
            },
        },
        "env_presence": env,
        "api_keys_recorded": False,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "prompt_text_recorded": False,
        "raw_response_committed": False,
        "fairness_contract": {
            "fixture": "shared 8-chain exported cognitive session fixture",
            "systems": [
                {
                    "system": "King Synapse",
                    "required_mode": "current standard local configuration",
                    "current_status": hosted_statuses.get("King Synapse"),
                },
                {
                    "system": "Graphiti/Zep",
                    "required_mode": "hosted or standard Neo4j/OpenAI path",
                    "current_status": hosted_statuses.get("Graphiti/Zep"),
                },
                {
                    "system": "Mem0",
                    "required_mode": "official/recommended OpenAI config or explicit Mem0 config",
                    "current_status": hosted_statuses.get("Mem0"),
                },
                {
                    "system": "Letta",
                    "required_mode": "hosted API or local endpoint",
                    "current_status": hosted_statuses.get("Letta"),
                },
            ],
            "disallowed_substitutes": [
                "Counting Graphiti/Zep local Kuzu deterministic mode as hosted Graphiti/Zep.",
                "Counting Mem0 automatic DeepSeek + deterministic local embedder fallback as official Mem0.",
                "Counting an installed Letta SDK without LETTA_API_KEY, LETTA_BASE_URL, or LETTA_ENVIRONMENT=local as a measured Letta endpoint.",
            ],
        },
        "preconditions": {
            "graphiti_zep": graphiti,
            "mem0_official": mem0,
            "letta": letta,
            "all_ready": all_ready,
            "missing_groups": [
                group["id"]
                for group in [graphiti, mem0, letta]
                if not group["ready"]
            ],
        },
        "hosted_probe": {
            "matches_blocked_state": hosted_probe_matches_blocked_state,
            "summary": hosted_summary,
            "statuses": hosted_statuses,
        },
        "manifest_boundary": {
            "secrets_clean": secrets_clean,
            "graphiti_manifest": manifest_system(manifest, "Graphiti/Zep"),
            "mem0_manifest": manifest_system(manifest, "Mem0"),
            "letta_manifest": manifest_system(manifest, "Letta"),
        },
        "deepseek_boundary": {
            "deepseek_api_key_present": env.get("DEEPSEEK_API_KEY", False),
            "deepseek_only_for_mem0_official": deepseek_only,
            "decision": (
                "DeepSeek is present, but DeepSeek-only configuration is not accepted "
                "as hosted/official external comparison evidence. It remains valid "
                "for DMR judging and local Mem0 OSS fallback evidence only."
            ),
        },
        "runbook": {
            "ready_to_run_hosted_external": all_ready,
            "command_when_ready": (
                "cargo run -p synapse-eval --bin kr-external-eval -- "
                "--graphiti-command python --graphiti-arg scripts/eval/graphiti_adapter.py "
                "--mem0-command python --mem0-arg scripts/eval/mem0_adapter.py "
                "--letta-command python --letta-arg scripts/eval/letta_adapter.py "
                "--json crates/eval/reports/external-comparison-hosted.json"
            ),
            "post_run_gates": [
                "python scripts/eval/phase6_next_gate_readiness.py",
                "python scripts/eval/external_comparison_task_gate.py",
                "python scripts/eval/phase6_requirements_audit.py",
                "python scripts/eval/phase6_objective_coverage_audit.py",
                "python scripts/eval/productization_decision_gate.py",
                "python scripts/eval/phase6_current_system_gate.py",
            ],
        },
        "status": {
            "hosted_external_preconditions_audit_passed": not hard_failures,
            "hosted_external_ready": all_ready,
            "hosted_external_run_allowed": all_ready,
            "hosted_comparison_complete": False,
            "productization_allowed": False,
            "runtime_default_change_allowed": False,
            "hard_failures": hard_failures,
            "blocking_reasons": blocking_reasons(
                "hosted_graphiti_zep_not_configured"
                if not graphiti["ready"]
                else None,
                "official_mem0_not_configured" if not mem0["ready"] else None,
                "letta_endpoint_not_configured" if not letta["ready"] else None,
            ),
        },
        "read": {
            "current_conclusion": (
                "Hosted/official external comparison cannot run in the current "
                "environment. DeepSeek is present, but OpenAI/Neo4j, explicit "
                "Mem0 official config, and Letta endpoint preconditions are not "
                "satisfied."
            ),
            "next_action": (
                "Keep feature freeze. Configure the missing hosted competitor "
                "credentials/endpoints, then rerun the shared cognitive fixture "
                "with the hosted command and refresh Phase 6 gates."
            ),
        },
        "limits": [
            "Records environment variable presence only, not values.",
            "Does not run hosted adapters, external services, retrieval, ranking, judges, or product code.",
            "Does not inspect raw benchmark records, raw responses, prompts, or generated answers.",
            "A passing precondition audit proves the blocked state is well-defined; it is not hosted-comparison completion.",
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
                "hosted_external_preconditions_audit_passed": report["status"][
                    "hosted_external_preconditions_audit_passed"
                ],
                "hosted_external_ready": report["status"]["hosted_external_ready"],
                "hosted_external_run_allowed": report["status"][
                    "hosted_external_run_allowed"
                ],
                "blocking_reasons": [
                    reason
                    for reason in report["status"]["blocking_reasons"]
                    if reason
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"]["hosted_external_preconditions_audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
