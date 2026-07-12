#!/usr/bin/env python3
"""Deterministic gate for Phase 7.3.1-C artifact lineage and transitions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_artifact_lineage_transition_gate.json"
PROTOCOL = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_artifact_lineage_protocol.json"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        [
            "cargo",
            "run",
            "-p",
            "synapse-eval",
            "--bin",
            "phase7_artifact_lineage_transition_gate",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert report["state"] == "judge_calibration_allowed"
    assert report["review_progress"]["completed_count"] == 2
    assert report["review_progress"]["required_count"] == 2
    assert report["review_progress"]["completion_order_independent"] is True
    assert report["lineage"]["artifact_lineage_broken"] is False
    assert report["lineage"]["foundational_lineage_valid"] is True
    assert HEX64.fullmatch(report["silver_labels_sha256"])
    assert HEX64.fullmatch(report["frozen_judge_sha256"])
    assert report["lineage"]["silver_lineage_valid"] is True
    assert report["lineage"]["calibration_lineage_valid"] is True

    assert protocol["hash_policy"]["algorithm"] == "sha256"
    assert protocol["hash_policy"]["hashed_representation"] == "exact_file_bytes"
    assert protocol["hash_policy"]["embedded_self_hash_allowed"] is False
    assert protocol["hash_policy"]["hash_mismatch_invalidates_downstream"] is True
    assert protocol["transition_policy"]["skip_allowed"] is False
    assert protocol["transition_policy"]["backward_transition_allowed"] is False
    assert protocol["transition_policy"]["same_state_recheck_allowed"] is True

    for item in report["artifacts"]:
        assert HEX64.fullmatch(item["sha256"])
        assert sha256(ROOT / item["path"]) == item["sha256"]
    assert HEX64.fullmatch(report["agreement_report_sha256"])
    assert HEX64.fullmatch(report["adjudication_sha256"])

    assert report["permissions"]["agreement_computation_allowed"] is False
    assert report["permissions"]["adjudication_allowed"] is False
    assert report["permissions"]["silver_freeze_allowed"] is False
    assert report["permissions"]["judge_calibration_allowed"] is True
    for key in (
        "fake_reviewers_generated",
        "fake_agreement_metrics_generated",
        "judge_calibration_executed",
        "held_out_accessed",
        "runtime_authorized",
        "hermes_authorized",
        "memory_write_authorized",
        "extractor_modified",
        "judge_modified",
    ):
        assert report["guards"][key] is False

    print("Phase: Phase 7.3.1-C Artifact Lineage & Irreversible Transition Gate")
    assert report["guards"]["adjudication_executed"] is True
    assert report["guards"]["silver_labels_generated"] is True

    print("Workflow state: judge_calibration_allowed (exact Silver + frozen-Judge lineage)")
    print("Hash representation: exact file bytes, SHA-256")
    print("Agreement/adjudication/Silver frozen; calibration lineage declared and valid")
    print("Held-out/runtime/Hermes/memory writes: blocked")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
