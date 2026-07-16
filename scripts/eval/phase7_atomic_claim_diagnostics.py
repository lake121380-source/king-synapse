#!/usr/bin/env python3
"""Deterministic gate for Phase 7.3.3-A diagnostic instrumentation."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_atomic_claim_diagnostics_readiness.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_atomic_claim_diagnostics"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "diagnostics_ready_four_label_controls_frozen_model_execution_pending"
    assert report["diagnostics_change_gate_decision"] is False
    assert report["four_label_local_claim_calibration_available"] is True
    assert report["missing_gold_atomic_claim_labels"] == []
    assert report["original_gold_atomic_claim_label_counts"] == {
        "not_assessable": 4,
        "supported": 12,
        "unsupported": 8,
    }
    assert report["supplement_gold_atomic_claim_label_counts"] == {
        "partially_supported": 4,
    }
    assert report["combined_gold_atomic_claim_label_counts"] == {
        "not_assessable": 4,
        "partially_supported": 4,
        "supported": 12,
        "unsupported": 8,
    }
    assert report["candidate_collapse_gate_uses_original_balanced_controls_only"] is True
    assert report["partial_supplement_change_gate_decision"] is False
    assert report["real_model_diagnostics"] is None
    assert report["real_model_supplement_diagnostics"] is None

    perfect = report["perfect_probe"]
    assert perfect["overall_claim_support"]["exact_accuracy"] == 1.0
    assert perfect["aggregation_error_attribution"]["candidate_classification"]["exact_accuracy"] == 1.0
    assert perfect["aggregation_error_attribution"]["attribution_counts"] == {"correct": 16}

    collapsed = report["always_partial_probe"]
    assert collapsed["overall_claim_support"]["exact_accuracy"] == 0.0
    assert collapsed["aggregation_error_attribution"]["candidate_classification"]["exact_accuracy"] == 0.25
    assert collapsed["aggregation_error_attribution"]["attribution_counts"] == {
        "claim_classification_error": 12,
        "masked_claim_error": 4,
    }
    assert len(collapsed["support_confusion_by_claim_type"]) == 7

    supplement = report["supplement_perfect_probe"]
    assert supplement["overall_claim_support"]["item_count"] == 4
    assert supplement["overall_claim_support"]["exact_accuracy"] == 1.0
    assert supplement["overall_claim_support"]["observed_gold_labels"] == ["partially_supported"]
    assert supplement["aggregation_error_attribution"]["candidate_classification"]["exact_accuracy"] == 1.0
    assert supplement["aggregation_error_attribution"]["attribution_counts"] == {"correct": 4}

    guards = report["guards"]
    assert guards["atomic_protocol_modified"] is False
    assert guards["atomic_prompt_modified"] is False
    assert guards["balanced_controls_modified"] is False
    assert guards["aggregation_policy_modified"] is False
    assert guards["readiness_thresholds_modified"] is False
    assert guards["diagnostic_supplement_changes_candidate_gate"] is False
    assert guards["model_execution_completed"] is False
    assert guards["held_out_accessed"] is False
    assert guards["runtime_authorized"] is False
    assert guards["memory_write_authorized"] is False

    print("Phase 7.3.3-A diagnostics: ready")
    print("Perfect probe: claim=1.00, candidate=1.00")
    print("Always-partial probe: claim=0.00, candidate=0.25")
    print("Attribution: 12 classification errors, 4 masked claim errors")
    print("Four-label local Claim coverage: available through frozen diagnostics-only supplement")
    print("Original balanced Candidate collapse gate: unchanged")
    print("Real model / design / held-out execution: not run")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
