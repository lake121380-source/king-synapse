#!/usr/bin/env python
"""Gate the DeepSeek-first external validation protocol.

This gate separates two different questions:

1. Can Synapse be validated under a domestic / DeepSeek-first protocol?
2. Has the OpenAI/Neo4j hosted reference comparison been completed?

The first question can pass without pretending the second question is complete.
The report records environment-variable presence only and never records secret
values.
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


TRACE_METRICS = [
    "hidden_influence_dominant",
    "suppressed_alternatives_visible",
    "evidence_path_available",
    "future_continuation_found",
    "reinforcement_isolated",
]

RETRIEVAL_METRICS = [
    "visible_seed_found",
    "hidden_influence_found",
]

ALL_METRICS = [*RETRIEVAL_METRICS, *TRACE_METRICS]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Audit the DeepSeek-first external validation protocol."
    )
    parser.add_argument(
        "--external-comparison",
        type=Path,
        default=root / "crates/eval/reports/external-comparison-latest.json",
    )
    parser.add_argument(
        "--external-manifest",
        type=Path,
        default=root / "crates/eval/reports/external-comparison-manifest.json",
    )
    parser.add_argument(
        "--external-task-gate",
        type=Path,
        default=root / "crates/eval/reports/external-comparison-task-gate.json",
    )
    parser.add_argument(
        "--hosted-preconditions",
        type=Path,
        default=root / "crates/eval/reports/hosted-external-preconditions.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/deepseek-external-protocol-gate.json",
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


def find_system(report: dict[str, Any], system_name: str) -> dict[str, Any]:
    for system in report.get("systems", []):
        if system.get("system") == system_name:
            return system
    return {}


def manifest_system(manifest: dict[str, Any], system_name: str) -> dict[str, Any]:
    for system in manifest.get("systems", []):
        if system.get("system") == system_name:
            return system
    return {}


def metric_counts(system: dict[str, Any], metric_name: str) -> dict[str, int]:
    counts = safe_get(system, ["aggregate", "metrics", metric_name], {})
    return {
        "hit": int(counts.get("hit") or 0),
        "miss": int(counts.get("miss") or 0),
        "unsupported": int(counts.get("unsupported") or 0),
        "not_configured": int(counts.get("not_configured") or 0),
        "failed": int(counts.get("failed") or 0),
    }


def metric_hits(system: dict[str, Any], metrics: list[str], expected_hits: int) -> bool:
    return all(metric_counts(system, metric)["hit"] == expected_hits for metric in metrics)


def metric_unsupported(
    system: dict[str, Any], metrics: list[str], expected_count: int
) -> bool:
    return all(
        metric_counts(system, metric)["unsupported"] == expected_count
        and metric_counts(system, metric)["failed"] == 0
        for metric in metrics
    )


def metric_not_configured(
    system: dict[str, Any], metrics: list[str], expected_count: int
) -> bool:
    return all(
        metric_counts(system, metric)["not_configured"] == expected_count
        and metric_counts(system, metric)["failed"] == 0
        for metric in metrics
    )


def check(
    check_id: str,
    passed: bool,
    *,
    evidence: list[Path],
    conclusion: str,
    failure: str,
    severity: str = "required",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "passed" if passed else "failed",
        "severity": severity,
        "evidence": [report_path(path) for path in evidence],
        "conclusion": conclusion if passed else failure,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "external_comparison": normalize_path_arg(args.external_comparison),
        "external_manifest": normalize_path_arg(args.external_manifest),
        "external_task_gate": normalize_path_arg(args.external_task_gate),
        "hosted_preconditions": normalize_path_arg(args.hosted_preconditions),
    }
    reports = {name: load_json(path) for name, path in paths.items()}
    comparison = reports["external_comparison"]
    manifest = reports["external_manifest"]
    task_gate = reports["external_task_gate"]
    hosted = reports["hosted_preconditions"]

    synapse = find_system(comparison, "King Synapse")
    graphiti = find_system(comparison, "Graphiti/Zep")
    mem0 = find_system(comparison, "Mem0")
    letta = find_system(comparison, "Letta")
    manifest_synapse = manifest_system(manifest, "King Synapse")
    manifest_graphiti = manifest_system(manifest, "Graphiti/Zep")
    manifest_mem0 = manifest_system(manifest, "Mem0")
    manifest_letta = manifest_system(manifest, "Letta")

    chains = int(comparison.get("fixture_chains") or 0)
    shared_fixture = chains == 8 and all(
        safe_get(system, ["aggregate", "chains"]) == chains
        for system in [synapse, graphiti, mem0, letta]
    )
    measured_expected = (
        synapse.get("status") == "measured"
        and graphiti.get("status") == "measured"
        and mem0.get("status") == "measured"
        and letta.get("status") == "not_configured"
        and safe_get(comparison, ["summary", "failed_systems"]) == 0
    )
    synapse_design_surface_complete = metric_hits(synapse, ALL_METRICS, chains)
    graphiti_retrieval_measured = (
        metric_hits(graphiti, RETRIEVAL_METRICS, chains)
        and metric_counts(graphiti, "evidence_path_available")["hit"] == chains
    )
    mem0_deepseek_measured = (
        metric_counts(mem0, "hidden_influence_found")["hit"] == chains
        and metric_counts(mem0, "visible_seed_found")["hit"] >= chains - 1
    )
    competitor_trace_boundary_clean = metric_unsupported(
        graphiti,
        [
            "hidden_influence_dominant",
            "suppressed_alternatives_visible",
            "future_continuation_found",
            "reinforcement_isolated",
        ],
        chains,
    ) and metric_unsupported(
        mem0,
        [
            "hidden_influence_dominant",
            "suppressed_alternatives_visible",
            "future_continuation_found",
            "reinforcement_isolated",
        ],
        chains,
    )
    letta_boundary_clean = metric_not_configured(letta, ALL_METRICS, chains)
    local_external_gate_passed = bool(
        safe_get(task_gate, ["status", "local_external_comparison_gate_passed"])
    )
    unsupported_counted_separately = bool(
        safe_get(task_gate, ["status", "unsupported_counted_separately"])
    )
    hosted_official_still_open = not bool(
        safe_get(task_gate, ["status", "hosted_official_external_ready"])
    )
    hosted_preconditions_passed = bool(
        safe_get(
            hosted,
            ["status", "hosted_external_preconditions_audit_passed"],
        )
    )
    hosted_run_allowed = bool(
        safe_get(hosted, ["status", "hosted_external_run_allowed"])
    )
    secrets_clean = all(
        system.get("secrets_recorded") is not True for system in manifest.get("systems", [])
    )
    mem0_manifest_deepseek = (
        manifest_mem0.get("status") == "measured"
        and manifest_mem0.get("llm_model") == "deepseek-v4-flash"
        and manifest_mem0.get("embedder") == "king-synapse-deterministic"
        and manifest_mem0.get("vector_store") == "local qdrant"
        and "DEEPSEEK_API_KEY" in manifest_mem0.get("credentials", [])
        and manifest_mem0.get("secrets_recorded") is False
    )
    graphiti_manifest_local = (
        manifest_graphiti.get("status") == "measured"
        and "Kuzu" in str(manifest_graphiti.get("mode", ""))
        and not manifest_graphiti.get("credentials")
    )

    checks = [
        check(
            "shared_fixture_shape",
            shared_fixture,
            evidence=[paths["external_comparison"]],
            conclusion="DeepSeek protocol evidence uses the shared 8-chain cognitive fixture.",
            failure="DeepSeek protocol evidence does not use the expected 8-chain fixture.",
        ),
        check(
            "deepseek_protocol_systems_measured",
            measured_expected,
            evidence=[paths["external_comparison"]],
            conclusion="Synapse, Graphiti/Zep local, and Mem0 DeepSeek are measured; Letta is separated as not_configured; failed systems are zero.",
            failure="Measured/not_configured system split does not match the DeepSeek protocol.",
        ),
        check(
            "mem0_deepseek_manifest_boundary",
            mem0_manifest_deepseek,
            evidence=[paths["external_manifest"]],
            conclusion="Mem0 evidence is explicitly DeepSeek v4 flash with deterministic local embedder and local Qdrant; key value is not recorded.",
            failure="Mem0 DeepSeek manifest boundary is missing or ambiguous.",
        ),
        check(
            "graphiti_local_manifest_boundary",
            graphiti_manifest_local,
            evidence=[paths["external_manifest"]],
            conclusion="Graphiti/Zep evidence is explicit local Kuzu deterministic graph evidence, not an OpenAI/Neo4j hosted claim.",
            failure="Graphiti local manifest boundary is missing or ambiguous.",
        ),
        check(
            "synapse_design_surface_complete",
            synapse_design_surface_complete,
            evidence=[paths["external_comparison"], paths["external_task_gate"]],
            conclusion="Synapse hits visible recall, hidden influence, dominant trace, suppressed alternatives, evidence path, future continuation, and reinforcement isolation 8/8.",
            failure="Synapse design-surface metrics are not complete on the shared fixture.",
        ),
        check(
            "competitor_retrieval_surfaces_measured",
            graphiti_retrieval_measured and mem0_deepseek_measured,
            evidence=[paths["external_comparison"]],
            conclusion="Graphiti local and Mem0 DeepSeek retrieve the shared fixture well enough to compare exposed surfaces instead of treating competitors as absent.",
            failure="Graphiti local or Mem0 DeepSeek retrieval evidence is too weak for the protocol.",
        ),
        check(
            "unsupported_surfaces_separated",
            local_external_gate_passed
            and unsupported_counted_separately
            and competitor_trace_boundary_clean
            and letta_boundary_clean,
            evidence=[paths["external_task_gate"], paths["external_comparison"]],
            conclusion="Unsupported trace surfaces and not_configured Letta are separated from failures.",
            failure="Unsupported/not_configured accounting is mixed with failures or incomplete.",
        ),
        check(
            "openai_reference_not_required_for_deepseek_protocol",
            hosted_official_still_open
            and hosted_preconditions_passed
            and not hosted_run_allowed,
            evidence=[paths["hosted_preconditions"], paths["external_task_gate"]],
            conclusion="OpenAI/Neo4j hosted reference remains open, but it is not required for the DeepSeek-first design validation protocol.",
            failure="Hosted reference boundary is missing or incorrectly marked ready.",
        ),
        check(
            "secrets_not_recorded",
            secrets_clean,
            evidence=[paths["external_manifest"]],
            conclusion="External comparison manifest records credential names only, not secret values.",
            failure="External comparison manifest indicates a secret value was recorded.",
        ),
    ]

    hard_failures = [entry["id"] for entry in checks if entry["status"] == "failed"]
    gate_passed = not hard_failures
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
        "schema_version": "king-synapse.deepseek-external-protocol-gate.v1",
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
        "env_presence": {
            "DEEPSEEK_API_KEY": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY")),
            "NEO4J_URI": bool(os.environ.get("NEO4J_URI")),
            "LETTA_API_KEY": bool(os.environ.get("LETTA_API_KEY")),
            "LETTA_BASE_URL": bool(os.environ.get("LETTA_BASE_URL")),
            "LETTA_ENVIRONMENT": bool(os.environ.get("LETTA_ENVIRONMENT")),
        },
        "api_keys_recorded": False,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "generated_answers_committed": False,
        "protocol": {
            "name": "deepseek_first_external_design_validation",
            "purpose": "Validate Synapse's own cognitive-memory design surfaces under a domestic/DeepSeek-compatible reproducible setup.",
            "model_boundary": {
                "mem0_llm_model": manifest_mem0.get("llm_model"),
                "mem0_embedder": manifest_mem0.get("embedder"),
                "mem0_vector_store": manifest_mem0.get("vector_store"),
                "deepseek_key_value_recorded": False,
            },
            "systems": {
                "synapse": {
                    "status": synapse.get("status"),
                    "mode": manifest_synapse.get("mode"),
                },
                "graphiti_zep": {
                    "status": graphiti.get("status"),
                    "mode": manifest_graphiti.get("mode"),
                },
                "mem0": {
                    "status": mem0.get("status"),
                    "mode": manifest_mem0.get("mode"),
                    "llm_model": manifest_mem0.get("llm_model"),
                },
                "letta": {
                    "status": letta.get("status"),
                    "mode": manifest_letta.get("mode"),
                    "missing": manifest_letta.get("missing", []),
                },
            },
        },
        "checks": checks,
        "status_counts": status_counts,
        "status": {
            "deepseek_external_protocol_gate_passed": gate_passed,
            "deepseek_protocol_external_validation_complete": gate_passed,
            "phase6_external_validation_blocked_by_openai": False,
            "openai_official_reference_required_for_this_protocol": False,
            "hosted_official_reference_still_open": hosted_official_still_open,
            "hosted_official_superiority_claim_allowed": False,
            "productization_allowed": False,
            "runtime_default_change_allowed": False,
            "hard_failures": hard_failures,
        },
        "read": {
            "current_conclusion": (
                "The DeepSeek-first external protocol passes: Synapse's unique cognitive trace surfaces are validated on the shared fixture against local Graphiti/Zep and Mem0 DeepSeek evidence. This does not claim OpenAI/Neo4j hosted official competitor completion."
                if gate_passed
                else "The DeepSeek-first external protocol does not pass yet; inspect hard_failures."
            ),
            "design_position": (
                "For this project, OpenAI-hosted parity is a reference lane, not the only proof lane. The primary Phase 6 proof can be the reproducible DeepSeek/local protocol as long as the README names the boundary clearly."
            ),
            "next_action": (
                "Keep feature freeze. Continue DMR failure-mode analysis and optional DeepSeek replay; do not start productization or claim hosted official superiority."
            ),
        },
        "limits": [
            "This gate reads committed aggregate external-comparison evidence only.",
            "It does not call DeepSeek, OpenAI, Neo4j, Qdrant, Letta, hosted adapters, benchmarks, LLM judges, or product code.",
            "It validates a DeepSeek/local reproducible protocol, not an OpenAI/Neo4j hosted official comparison.",
            "A passing protocol gate is not product readiness and does not authorize runtime default changes.",
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
                "deepseek_external_protocol_gate_passed": report["status"][
                    "deepseek_external_protocol_gate_passed"
                ],
                "deepseek_protocol_external_validation_complete": report["status"][
                    "deepseek_protocol_external_validation_complete"
                ],
                "phase6_external_validation_blocked_by_openai": report["status"][
                    "phase6_external_validation_blocked_by_openai"
                ],
                "hosted_official_reference_still_open": report["status"][
                    "hosted_official_reference_still_open"
                ],
                "hard_failures": report["status"]["hard_failures"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"]["deepseek_external_protocol_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
