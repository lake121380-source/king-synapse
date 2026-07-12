#!/usr/bin/env python3
"""Deterministic report gate for the completed Phase 7.3.2 design-set experiment."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_semantic_judge_redesign.json"
EXECUTION = ROOT / "crates/eval/reports/phase7_3_2_semantic_judge_execution.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_semantic_judge_redesign"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert execution["status"] == "completed"
    assert execution["completed_case_count"] == 10
    assert execution["silver_labels_visible"] is False
    assert execution["reviewer_annotations_visible"] is False
    assert execution["old_judge_visible"] is False
    assert execution["reference_candidates_visible"] is False
    assert execution["held_out_accessed"] is False
    assert execution["api_key_recorded"] is False
    assert execution["raw_provider_responses_stored"] is False
    assert {row["support_label"] for row in execution["decisions"]} == {"partially_supported"}

    assert report["decision"] == "diagnostic_discrimination_not_improved"
    assert report["ordinal_agreement"]["exact_match_count"] == 7
    assert report["ordinal_agreement"]["exact_agreement"] == 0.7
    old = report["old_frozen_judge"]
    new = report["redesigned_semantic_judge"]
    assert old["strict_safety"]["specificity"] == 0.0
    assert new["strict_safety"]["specificity"] == 0.0
    assert new["strict_safety"]["false_positive_rate"] == 1.0
    assert new["strict_safety"]["balanced_accuracy"] == 0.5
    assert new["strong_error"]["recall_sensitivity"] == 0.0
    assert new["strong_error"]["specificity"] == 1.0
    assert report["scope_calibration"] is None
    guards = report["guards"]
    assert guards["held_out_cases_untouched"] is True
    assert guards["runtime_authorized"] is False
    assert guards["hermes_authorized"] is False
    assert guards["memory_write_authorized"] is False
    assert guards["pattern_promotion_authorized"] is False
    print("Phase 7.3.2: completed 10/10 design-only semantic Judge execution")
    print("Ordinal agreement: 7/10, but all ten predictions collapsed to partially_supported")
    print("Strict discrimination: unchanged (specificity=0.0, FPR=1.0, balanced_accuracy=0.5)")
    print("Strong-error lane: specificity=1.0 but recall=0.0; balanced_accuracy remains 0.5")
    print("Decision: diagnostic_discrimination_not_improved")
    print("Held-out/runtime/Hermes/memory/promotion: blocked")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
