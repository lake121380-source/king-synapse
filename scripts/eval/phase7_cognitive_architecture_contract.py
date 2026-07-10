#!/usr/bin/env python3
"""Run and validate the Phase 7.0 Cognitive Architecture Contract gate."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_cognitive_architecture_contract.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    env = os.environ.copy()
    env.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
    env.setdefault("CARGO_PROFILE_TEST_DEBUG", "0")
    env.setdefault("CARGO_BUILD_JOBS", "1")

    subprocess.run(
        [
            "cargo",
            "run",
            "-p",
            "synapse-eval",
            "--bin",
            "phase7_cognitive_architecture_contract",
            "--",
            "--json",
            str(REPORT),
            "--tag",
            "phase7-cognitive-architecture-contract",
        ],
        cwd=ROOT,
        check=True,
        env=env,
    )

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    require(report["status"] == "PASS", "Phase 7.0 report did not pass")
    require(report["mode"] == "eval_only_contract", "unexpected Phase 7.0 mode")
    require(report["canonical_validation"]["valid"], "canonical pattern is invalid")
    require(
        all(case["expectation_met"] for case in report["invalid_contract_cases"]),
        "one or more invalid contract cases did not fail as expected",
    )
    require(
        all(not artifact["runtime_authority"] for artifact in report["artifact_ladder"]),
        "a Phase 7.0 artifact has runtime authority",
    )
    require(
        all(not transition["autonomous"] for transition in report["lifecycle"]),
        "an autonomous pattern lifecycle transition was allowed",
    )
    require(
        "usage_count_without_outcome"
        in report["confidence_update_policy"]["prohibited_sources"],
        "usage-only confidence reinforcement was not prohibited",
    )
    require(
        report["decision"]["experience_to_pattern_mainline_authorized"],
        "Experience-to-Pattern mainline was not established",
    )
    require(
        not report["decision"]["pattern_discovery_algorithm_authorized"],
        "Phase 7.0 incorrectly authorized a pattern algorithm",
    )
    require(not report["guards"]["pattern_persisted"], "pattern persistence occurred")
    require(not report["guards"]["runtime_applied"], "runtime authority was applied")
    require(
        not report["guards"]["hermes_integration_performed"],
        "Hermes integration was performed",
    )

    print(f"Phase: {report['phase']}")
    print(f"Artifacts: {len(report['artifact_ladder'])}")
    print(f"Lifecycle transitions: {len(report['lifecycle'])}")
    print(f"Invalid contract cases: {len(report['invalid_contract_cases'])}")
    print(f"Pattern algorithm authorized: {report['decision']['pattern_discovery_algorithm_authorized']}")
    print(f"Runtime authorized: {report['decision']['runtime_authorization']}")
    print("PASS")
    print(f"Saved to {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
