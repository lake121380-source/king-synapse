#!/usr/bin/env python
"""Summarize the current Phase 4 external comparison gate.

This gate reads committed aggregate external-comparison reports only. It keeps
local fixture evidence separate from hosted/official competitor readiness and
preserves unsupported/not_configured as distinct statuses rather than failures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRACE_METRICS = [
    "hidden_influence_dominant",
    "suppressed_alternatives_visible",
    "evidence_path_available",
    "future_continuation_found",
    "reinforcement_isolated",
]

ALL_METRICS = [
    "visible_seed_found",
    "hidden_influence_found",
    *TRACE_METRICS,
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Summarize external comparison readiness from committed reports."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/external-comparison-task-gate.json",
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
        "external_comparison_latest": root
        / "crates/eval/reports/external-comparison-latest.json",
        "external_comparison_hosted": root
        / "crates/eval/reports/external-comparison-hosted.json",
        "external_comparison_manifest": root
        / "crates/eval/reports/external-comparison-manifest.json",
        "phase6_next_gate_readiness": root
        / "crates/eval/reports/phase6-next-gate-readiness.json",
    }


def find_system(report: dict[str, Any], system_name: str) -> dict[str, Any]:
    for system in report.get("systems", []):
        if system.get("system") == system_name:
            return system
    raise KeyError(f"missing system in external report: {system_name}")


def metric_counts(system: dict[str, Any], metric_name: str) -> dict[str, int]:
    metrics = safe_get(system, ["aggregate", "metrics"], {})
    counts = metrics.get(metric_name, {})
    return {
        "hit": int(counts.get("hit") or 0),
        "miss": int(counts.get("miss") or 0),
        "unsupported": int(counts.get("unsupported") or 0),
        "not_configured": int(counts.get("not_configured") or 0),
        "failed": int(counts.get("failed") or 0),
    }


def compact_system(system: dict[str, Any]) -> dict[str, Any]:
    metrics = {
        metric: metric_counts(system, metric)
        for metric in ALL_METRICS
        if metric in safe_get(system, ["aggregate", "metrics"], {})
    }
    return {
        "system": system.get("system"),
        "kind": system.get("kind"),
        "version": system.get("version"),
        "status": system.get("status"),
        "capabilities": system.get("capabilities", {}),
        "chains": safe_get(system, ["aggregate", "chains"]),
        "mean_latency_ms": safe_get(system, ["aggregate", "mean_latency_ms"]),
        "metrics": metrics,
    }


def manifest_status(manifest: dict[str, Any], system_name: str) -> dict[str, Any]:
    for system in manifest.get("systems", []):
        if system.get("system") == system_name:
            return {
                "system": system.get("system"),
                "status": system.get("status"),
                "mode": system.get("mode"),
                "credentials": system.get("credentials", []),
                "missing": system.get("missing", []),
                "secrets_recorded": system.get("secrets_recorded"),
                "hosted_mode_credentials_not_used": system.get(
                    "hosted_mode_credentials_not_used", []
                ),
            }
    return {"system": system_name, "status": "missing"}


def all_metric_totals_separated(system: dict[str, Any]) -> bool:
    chains = int(safe_get(system, ["aggregate", "chains"], 0) or 0)
    metrics = safe_get(system, ["aggregate", "metrics"], {})
    for counts in metrics.values():
        total = sum(int(counts.get(key) or 0) for key in ["hit", "miss", "unsupported", "not_configured", "failed"])
        if total != chains:
            return False
    return True


def trace_hits(system: dict[str, Any], chains: int) -> bool:
    return all(metric_counts(system, metric)["hit"] == chains for metric in TRACE_METRICS)


def unsupported_trace_separated(system: dict[str, Any], chains: int) -> bool:
    return all(
        metric_counts(system, metric)["unsupported"] == chains
        and metric_counts(system, metric)["failed"] == 0
        for metric in [
            "hidden_influence_dominant",
            "suppressed_alternatives_visible",
            "future_continuation_found",
            "reinforcement_isolated",
        ]
    )


def not_configured_all_metrics(system: dict[str, Any], chains: int) -> bool:
    return all(
        metric_counts(system, metric)["not_configured"] == chains
        and metric_counts(system, metric)["failed"] == 0
        for metric in ALL_METRICS
    )


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
    latest = reports["external_comparison_latest"]
    hosted = reports["external_comparison_hosted"]
    manifest = reports["external_comparison_manifest"]
    readiness = reports["phase6_next_gate_readiness"]

    latest_summary = latest.get("summary", {})
    hosted_summary = hosted.get("summary", {})
    latest_chains = int(latest.get("fixture_chains") or 0)
    hosted_chains = int(hosted.get("fixture_chains") or 0)

    local_synapse = find_system(latest, "King Synapse")
    local_graphiti = find_system(latest, "Graphiti/Zep")
    local_mem0 = find_system(latest, "Mem0")
    local_letta = find_system(latest, "Letta")
    hosted_synapse = find_system(hosted, "King Synapse")
    hosted_graphiti = find_system(hosted, "Graphiti/Zep")
    hosted_mem0 = find_system(hosted, "Mem0")
    hosted_letta = find_system(hosted, "Letta")

    shared_fixture = latest_chains == hosted_chains == 8 and all(
        safe_get(system, ["aggregate", "chains"]) == 8
        for system in [
            local_synapse,
            local_graphiti,
            local_mem0,
            local_letta,
            hosted_synapse,
            hosted_graphiti,
            hosted_mem0,
            hosted_letta,
        ]
    )
    local_measured = (
        latest_summary.get("measured_systems") == 3
        and latest_summary.get("not_configured_systems") == 1
        and latest_summary.get("failed_systems") == 0
        and local_synapse.get("status") == "measured"
        and local_graphiti.get("status") == "measured"
        and local_mem0.get("status") == "measured"
        and local_letta.get("status") == "not_configured"
    )
    status_separation = all(
        all_metric_totals_separated(system)
        for system in [local_synapse, local_graphiti, local_mem0, local_letta]
    )
    synapse_trace_complete = trace_hits(local_synapse, latest_chains)
    competitor_unsupported_separated = unsupported_trace_separated(
        local_graphiti, latest_chains
    ) and unsupported_trace_separated(local_mem0, latest_chains)
    letta_not_configured_separated = not_configured_all_metrics(local_letta, latest_chains)
    hosted_not_ready = (
        hosted_summary.get("measured_systems") == 1
        and hosted_summary.get("not_configured_systems") == 3
        and hosted_summary.get("failed_systems") == 0
        and hosted_graphiti.get("status") == "not_configured"
        and hosted_mem0.get("status") == "not_configured"
        and hosted_letta.get("status") == "not_configured"
        and safe_get(readiness, ["hosted_external", "ready"]) is False
    )
    manifest_secrets_clean = all(
        system.get("secrets_recorded") is not True
        for system in manifest.get("systems", [])
    )
    missing_requirements = safe_get(readiness, ["hosted_external", "requirements"], {})

    checks = [
        item(
            "shared_cognitive_fixture_registered",
            "satisfied" if shared_fixture else "failed",
            evidence=[
                paths["external_comparison_latest"],
                paths["external_comparison_hosted"],
            ],
            conclusion=(
                "Local and hosted-probe external reports use the same 8-chain cognitive fixture."
                if shared_fixture
                else "External reports do not agree on the expected 8-chain fixture shape."
            ),
        ),
        item(
            "local_external_comparison_measured",
            "satisfied" if local_measured else "failed",
            evidence=[paths["external_comparison_latest"]],
            conclusion=(
                "Local external comparison measures King Synapse, Graphiti/Zep local, and Mem0 OSS, with Letta marked not_configured and zero failed systems."
                if local_measured
                else "Local external comparison does not have the expected measured/not_configured split."
            ),
        ),
        item(
            "unsupported_and_not_configured_are_separate",
            "satisfied"
            if status_separation
            and competitor_unsupported_separated
            and letta_not_configured_separated
            else "failed",
            evidence=[paths["external_comparison_latest"]],
            conclusion=(
                "Unsupported trace surfaces and not_configured Letta surfaces are counted separately from failures."
                if status_separation
                and competitor_unsupported_separated
                and letta_not_configured_separated
                else "Unsupported/not_configured accounting is incomplete or mixed with failures."
            ),
        ),
        item(
            "local_synapse_trace_surface_complete",
            "satisfied" if synapse_trace_complete else "failed",
            evidence=[paths["external_comparison_latest"]],
            conclusion=(
                "King Synapse records 8/8 hits for dominant trace, suppressed alternatives, evidence path, future continuation, and reinforcement isolation."
                if synapse_trace_complete
                else "King Synapse local trace metrics are not complete on the shared fixture."
            ),
        ),
        item(
            "hosted_official_comparison_not_ready",
            "blocked_external" if hosted_not_ready else "failed",
            evidence=[
                paths["external_comparison_hosted"],
                paths["phase6_next_gate_readiness"],
            ],
            conclusion=(
                "Hosted/official comparison is not ready: hosted report has 1 measured system, 3 not_configured systems, and zero failed systems."
                if hosted_not_ready
                else "Hosted/official comparison readiness does not match the expected blocked state."
            ),
            remaining=[
                "Configure Graphiti/Zep Neo4j/OpenAI credentials.",
                "Configure official Mem0 OpenAI/custom config.",
                "Configure Letta hosted or local endpoint.",
            ],
        ),
        item(
            "secrets_not_recorded",
            "satisfied" if manifest_secrets_clean else "failed",
            evidence=[paths["external_comparison_manifest"]],
            conclusion=(
                "External comparison manifest records credential names only and does not record secret values."
                if manifest_secrets_clean
                else "External comparison manifest indicates at least one secret value was recorded."
            ),
        ),
    ]

    hard_failures = [entry["id"] for entry in checks if entry["status"] == "failed"]
    local_gate_passed = not hard_failures and all(
        entry["status"] in {"satisfied", "blocked_external"} for entry in checks
    )
    hosted_ready = not hosted_not_ready and bool(
        safe_get(readiness, ["hosted_external", "ready"])
    )

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
        "schema_version": "king-synapse.external-comparison-task-gate.v1",
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
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "local_comparison": {
            "summary": latest_summary,
            "systems": [
                compact_system(local_synapse),
                compact_system(local_graphiti),
                compact_system(local_mem0),
                compact_system(local_letta),
            ],
        },
        "hosted_official_probe": {
            "summary": hosted_summary,
            "systems": [
                compact_system(hosted_synapse),
                compact_system(hosted_graphiti),
                compact_system(hosted_mem0),
                compact_system(hosted_letta),
            ],
            "requirements": missing_requirements,
        },
        "manifest": {
            "validated_commit": manifest.get("validated_commit"),
            "packages": manifest.get("packages", {}),
            "systems": [
                manifest_status(manifest, "King Synapse"),
                manifest_status(manifest, "Graphiti/Zep"),
                manifest_status(manifest, "Mem0"),
                manifest_status(manifest, "Letta"),
            ],
        },
        "checks": checks,
        "status_counts": status_counts,
        "status": {
            "local_external_comparison_gate_passed": local_gate_passed,
            "local_trace_advantage_supported": synapse_trace_complete,
            "unsupported_counted_separately": status_separation
            and competitor_unsupported_separated
            and letta_not_configured_separated,
            "hosted_official_external_ready": hosted_ready,
            "hosted_official_comparison_complete": False,
            "hosted_competitor_superiority_claim_allowed": False,
            "hard_failures": hard_failures,
            "open_gates": [
                "hosted_graphiti_zep_not_configured",
                "official_mem0_not_configured",
                "letta_endpoint_not_configured",
            ],
        },
        "read": {
            "current_conclusion": (
                "Local external comparison supports Synapse's inspectable cognitive-trace advantage on the shared fixture, "
                "but hosted/official competitor comparison is still not configured."
            ),
            "strongest_supported_result": (
                "On the 8-chain cognitive fixture, King Synapse hits dominant trace, suppressed alternatives, evidence paths, future continuation, and reinforcement isolation 8/8 while measured adapters expose some of those surfaces as unsupported."
            ),
            "weak_surfaces": [
                "Hosted Graphiti/Zep Neo4j/OpenAI comparison is not configured.",
                "Official/recommended Mem0 configuration is not configured.",
                "Live or local Letta endpoint is not configured.",
                "Local adapter evidence is not the same as hosted/official fairness.",
            ],
            "next_action": (
                "Keep feature freeze. Configure hosted competitor credentials/endpoints before rerunning the fair external comparison; until then, do not claim hosted competitor superiority."
            ),
        },
        "limits": [
            "This gate reads committed aggregate external-comparison reports only.",
            "It does not run hosted adapters, external services, benchmarks, LLM judges, or product code.",
            "It records credential names and readiness statuses only, not secret values.",
            "A passing local external comparison gate is not a hosted/official competitor superiority claim.",
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
                "local_external_comparison_gate_passed": report["status"][
                    "local_external_comparison_gate_passed"
                ],
                "hosted_official_external_ready": report["status"][
                    "hosted_official_external_ready"
                ],
                "unsupported_counted_separately": report["status"][
                    "unsupported_counted_separately"
                ],
                "open_gates": report["status"]["open_gates"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
