#!/usr/bin/env python3
"""Deterministic gate for the Phase 7.3.3 atomic-claim protocol freeze."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_atomic_claim_measurement.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_atomic_claim_measurement"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "protocol_frozen_model_execution_pending"
    assert report["decision"] == "atomic_claim_protocol_ready_not_yet_capability_validated"
    validation = report["protocol_validation"]
    assert validation["control_case_count"] == 16
    assert validation["balanced_four_class_controls"] is True
    assert validation["expected_aggregation_consistent"] is True
    assert validation["atomic_claim_count"] == validation["exact_source_span_count"]
    assert validation["candidate_label_counts"] == {
        "not_assessable": 4,
        "partially_supported": 4,
        "supported": 4,
        "unsupported": 4,
    }
    legacy = report["legacy_design_distribution"]
    assert legacy["label_counts"] == {
        "partially_supported": 7,
        "supported": 1,
        "unsupported": 2,
    }
    assert legacy["majority_class_accuracy"] == 0.7
    for probe in report["collapse_probes"]:
        assert probe["exact_accuracy"] == 0.25
        assert probe["macro_recall"] == 0.25
        assert probe["single_class_prediction_rate"] == 1.0
    guards = report["guards"]
    assert guards["model_execution_completed"] is False
    assert guards["held_out_cases_untouched"] is True
    assert guards["memory_write_authorized"] is False
    assert guards["pattern_promotion_authorized"] is False
    assert guards["runtime_authorized"] is False
    assert guards["hermes_authorized"] is False
    print("Phase 7.3.3 protocol: frozen")
    print("Balanced controls: 16 (4 per label)")
    print("Every single-class predictor: accuracy=0.25, macro_recall=0.25")
    print("Atomic Judge model execution: pending")
    print("Held-out/runtime/Hermes/memory/promotion: blocked")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
