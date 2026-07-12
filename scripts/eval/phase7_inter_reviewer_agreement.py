#!/usr/bin/env python3
"""Deterministic gate for the Phase 7.3.1 inter-reviewer Agreement Gate."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_inter_reviewer_agreement.json"
PROTOCOL = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_inter_reviewer_agreement_protocol.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_inter_reviewer_agreement"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    assert report["decision"] == "agreement_report_ready_adjudication_required"
    assert report["metrics"] is not None
    assert report["metrics"]["segmentation"]["reviewer_a_claim_count"] == 74
    assert report["metrics"]["segmentation"]["reviewer_b_claim_count"] == 77
    assert protocol["source_span_unit"] == "unicode_scalar_index_half_open"
    assert protocol["alignment_policy"]["minimum_iou"] == 0.5
    assert protocol["alignment_policy"]["claim_text_similarity_used"] is False
    assert protocol["agreement_input"] == "raw_blind_reviewer_submissions_only"
    assert protocol["adjudicated_labels_allowed"] is False
    assert protocol["frozen_judge_visible"] is False
    assert protocol["phase7_3_seed_visible"] is False
    assert protocol["held_out_accessed"] is False

    guards = report["guards"]
    assert guards["raw_blind_submissions_only"] is True
    assert guards["adjudicated_labels_used"] is False
    assert guards["frozen_judge_visible"] is False
    assert guards["phase7_3_seed_visible"] is False
    assert guards["held_out_cases_untouched"] is True
    assert guards["reviewer_a_completed"] is True
    assert guards["reviewer_b_completed"] is True
    assert guards["agreement_report_completed"] is True
    assert guards["runtime_authorized"] is False
    assert guards["hermes_authorized"] is False

    print("Phase: Phase 7.3.1-B Inter-reviewer Agreement Gate")
    print("Source spans: Unicode scalar half-open offsets")
    print("Alignment: deterministic greedy span IoU, frozen threshold 0.5")
    print("Reviewer A/B: completed (74/77 claims)")
    print("Agreement: available and frozen")
    print("Adjudication: required; Judge/held-out/runtime/Hermes: blocked")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
