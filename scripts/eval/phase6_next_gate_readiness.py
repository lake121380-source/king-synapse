#!/usr/bin/env python
"""Record readiness for the next Phase 6 validation gate.

The requirements audit currently branches on two external conditions:
top-context DMR judge authorization, or hosted/official external comparison
configuration. This script records those conditions without storing secrets,
prompts, raw responses, or raw benchmark data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


JUDGE_ENV_VARS = ["DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_JUDGE_MODEL"]
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
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Record Phase 6 next-gate readiness.")
    parser.add_argument(
        "--top-context-preflight",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-top-context-judge-preflight.json",
    )
    parser.add_argument(
        "--hosted-external-report",
        type=Path,
        default=root / "crates/eval/reports/external-comparison-hosted.json",
    )
    parser.add_argument(
        "--official-dmr-task-gate",
        type=Path,
        default=root / "crates/eval/reports/official-dmr-task-gate.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/phase6-next-gate-readiness.json",
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


def hosted_requirements(
    env: dict[str, bool], *, letta_environment_local: bool
) -> dict[str, Any]:
    graphiti_ready = all(
        env.get(name, False)
        for name in ["OPENAI_API_KEY", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
    )
    mem0_ready = bool(
        env.get("OPENAI_API_KEY")
        or env.get("MEM0_CONFIG_JSON")
        or env.get("MEM0_CONFIG_PATH")
    )
    letta_ready = bool(
        env.get("LETTA_API_KEY")
        or env.get("LETTA_BASE_URL")
        or letta_environment_local
    )
    return {
        "graphiti_zep_ready": graphiti_ready,
        "mem0_official_ready": mem0_ready,
        "letta_ready": letta_ready,
        "letta_environment_local": letta_environment_local,
        "all_hosted_ready": graphiti_ready and mem0_ready and letta_ready,
        "missing_for_graphiti_zep": [
            name
            for name in ["OPENAI_API_KEY", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
            if not env.get(name)
        ],
        "missing_for_mem0_official": []
        if mem0_ready
        else ["OPENAI_API_KEY or MEM0_CONFIG_JSON or MEM0_CONFIG_PATH"],
        "missing_for_letta": []
        if letta_ready
        else ["LETTA_API_KEY or LETTA_BASE_URL or LETTA_ENVIRONMENT=local"],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    preflight_path = normalize_path_arg(args.top_context_preflight)
    hosted_path = normalize_path_arg(args.hosted_external_report)
    official_dmr_path = normalize_path_arg(args.official_dmr_task_gate)
    preflight = load_json(preflight_path)
    hosted = load_json(hosted_path)
    official_dmr = load_json(official_dmr_path)

    env = env_presence(JUDGE_ENV_VARS + HOSTED_ENV_VARS)
    letta_environment_local = (
        os.environ.get("LETTA_ENVIRONMENT", "").strip().lower() == "local"
    )
    hosted_ready = hosted_requirements(
        env, letta_environment_local=letta_environment_local
    )
    preflight_result = preflight.get("result", {})
    judge_ready = preflight_result.get("status") == "judged"
    top_context_dmr_50_complete = bool(
        safe_get(official_dmr, ["status", "top_context_judge_ready"])
    )
    hosted_report_summary = hosted.get("summary", {})

    if top_context_dmr_50_complete and hosted_ready["all_hosted_ready"]:
        next_action = "Run hosted/official external comparison on the shared cognitive fixture."
        next_gate_ready = True
        blocking_reason = None
    elif top_context_dmr_50_complete:
        next_action = (
            "No heavy next-gate run is currently selected. Do not rerun DMR 50; "
            "select a DMR 200/500 top-context judge expansion or configure hosted "
            "external credentials/endpoints."
        )
        next_gate_ready = False
        blocking_reason = (
            "DMR 50 top-context judge scoring is complete; hosted external "
            "comparison credentials/endpoints are not configured, and no DMR "
            "expansion scope is selected."
        )
    elif judge_ready:
        next_action = "Run judge-scored top-context DMR 50 before broader changes."
        next_gate_ready = True
        blocking_reason = None
    elif hosted_ready["all_hosted_ready"]:
        next_action = "Run hosted/official external comparison on the shared cognitive fixture."
        next_gate_ready = True
        blocking_reason = None
    else:
        next_action = (
            "No heavy next-gate run is currently ready. Keep feature freeze and "
            "wait for a valid judge key or hosted external credentials/endpoints."
        )
        next_gate_ready = False
        blocking_reason = (
            "Top-context judge is not ready, and hosted external comparison "
            "credentials/endpoints are not configured."
        )

    return {
        "schema_version": "king-synapse.phase6-next-gate-readiness.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "inputs": {
            "top_context_preflight": {
                "path": report_path(preflight_path),
                "sha256": sha256_file(preflight_path),
                "decision": preflight.get("decision"),
            },
            "hosted_external_report": {
                "path": report_path(hosted_path),
                "sha256": sha256_file(hosted_path),
                "summary": hosted_report_summary,
            },
            "official_dmr_task_gate": {
                "path": report_path(official_dmr_path),
                "sha256": sha256_file(official_dmr_path),
            },
        },
        "env_presence": env,
        "env_checks": {
            "LETTA_ENVIRONMENT_is_local": letta_environment_local,
        },
        "api_keys_recorded": False,
        "prompt_text_recorded": False,
        "raw_response_committed": False,
        "raw_records_committed": False,
        "top_context_judge": {
            "ready": judge_ready,
            "status": preflight_result.get("status"),
            "http_status": preflight_result.get("http_status"),
            "decision": preflight.get("decision"),
            "dmr_50_complete": top_context_dmr_50_complete,
            "api_key_present": preflight.get("llm_judge", {}).get("api_key_present"),
            "api_key_recorded": preflight.get("llm_judge", {}).get("api_key_recorded"),
        },
        "hosted_external": {
            "ready": hosted_ready["all_hosted_ready"],
            "requirements": hosted_ready,
            "last_report_measured_systems": hosted_report_summary.get("measured_systems"),
            "last_report_not_configured_systems": hosted_report_summary.get(
                "not_configured_systems"
            ),
            "last_report_failed_systems": hosted_report_summary.get("failed_systems"),
        },
        "read": {
            "next_gate_ready": next_gate_ready,
            "blocking_reason": blocking_reason,
            "next_action": next_action,
        },
        "limits": [
            "Records environment variable presence only, not values.",
            "Does not run DMR retrieval, answer generation, LLM judging, or hosted adapters.",
            "Does not inspect raw benchmark records or generated answers.",
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
                "top_context_judge_ready": report["top_context_judge"]["ready"],
                "hosted_external_ready": report["hosted_external"]["ready"],
                "next_gate_ready": report["read"]["next_gate_ready"],
                "next_action": report["read"]["next_action"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
