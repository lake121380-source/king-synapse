#!/usr/bin/env python3
"""Deterministic quality gate for Phase 7.2 extraction protocol."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_pattern_extraction_protocol.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_PROFILE_TEST_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_pattern_extraction_protocol"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["phase"] == "Phase 7.2 Evidence-Grounded Pattern Extraction Protocol"
    assert report["dataset"]["case_count"] == 10
    assert report["dataset"]["held_out_references"] == 0
    assert report["dataset"]["reference_candidates_valid"] == 10
    assert report["all_reference_candidates_valid"] is True
    assert report["all_negative_cases_rejected"] is True
    assert len(report["metrics"]) >= 11
    assert report["guards"]["design_cases_only"] is True
    assert report["guards"]["target_problem_excluded"] is True
    assert report["guards"]["expected_transfer_excluded"] is True
    assert report["guards"]["held_out_cases_untouched"] is True
    assert report["guards"]["extraction_algorithm_implemented"] is False
    assert report["guards"]["model_evaluation_completed"] is False
    assert report["guards"]["runtime_authorized"] is False
    assert report["decision"] == "protocol_frozen_extraction_algorithm_blocked"

    print("Phase:", report["phase"])
    print("Design cases:", report["dataset"]["case_count"])
    print("Reference candidates valid:", report["dataset"]["reference_candidates_valid"])
    print("Negative cases:", len(report["negative_cases"]))
    print("Extraction algorithm implemented:", report["guards"]["extraction_algorithm_implemented"])
    print("Held-out cases untouched:", report["guards"]["held_out_cases_untouched"])
    print("Runtime authorized:", report["guards"]["runtime_authorized"])
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
