#!/usr/bin/env python3
"""Deterministic quality gate for Phase 7.1 Transfer Evaluation Protocol."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_transfer_evaluation_protocol.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_PROFILE_TEST_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_transfer_evaluation_protocol"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["phase"] == "Phase 7.1 Transfer Evaluation Protocol"
    assert report["dataset"]["scenario_count"] == 30
    assert report["dataset"]["design_count"] == 10
    assert report["dataset"]["held_out_count"] == 20
    assert len(report["dataset"]["category_counts"]) == 6
    assert len(report["arms"]) == 6
    assert len(report["metrics"]) >= 13
    assert report["all_scenarios_valid"] is True
    assert report["guards"]["dataset_frozen"] is True
    assert report["guards"]["baseline_comparison_protocol_complete"] is True
    assert report["guards"]["outcome_evaluation_complete"] is False
    assert report["guards"]["pattern_discovery_implemented"] is False
    assert report["guards"]["runtime_authorized"] is False
    assert report["guards"]["hermes_authorized"] is False
    assert report["decision"] == "protocol_frozen_pattern_algorithm_blocked"

    print("Phase:", report["phase"])
    print("Scenarios:", report["dataset"]["scenario_count"])
    print("Held-out:", report["dataset"]["held_out_count"])
    print("Experiment arms:", len(report["arms"]))
    print("Metrics:", len(report["metrics"]))
    print("Outcome evaluation complete:", report["guards"]["outcome_evaluation_complete"])
    print("Runtime authorized:", report["guards"]["runtime_authorized"])
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
