#!/usr/bin/env python3
"""Deterministic gate for Phase 7.3.1 protocol readiness and frozen-judge calibration harness."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_independent_adjudication_calibration.json"
PROTOCOL = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_measurement_protocol.json"
REVIEWER_A = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_reviewer_a_template.json"
REVIEWER_B = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_reviewer_b_template.json"
ADJUDICATION = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_adjudication_template.json"
BLIND_PACKET = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_blind_review_packet.json"


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
            "phase7_independent_adjudication_calibration",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    reviewer_a = json.loads(REVIEWER_A.read_text(encoding="utf-8"))
    reviewer_b = json.loads(REVIEWER_B.read_text(encoding="utf-8"))
    adjudication = json.loads(ADJUDICATION.read_text(encoding="utf-8"))
    blind_packet = json.loads(BLIND_PACKET.read_text(encoding="utf-8"))

    assert report["phase"] == "Phase 7.3.1 Independent Candidate Adjudication & Frozen Judge Calibration"
    assert report["decision"] == "frozen_judge_diagnostic_calibration_complete"
    assert len(report["claim_source_anchors"]) == 65
    assert all(anchor["requires_independent_atomic_segmentation"] for anchor in report["claim_source_anchors"])
    assert len({anchor["anchor_id"] for anchor in report["claim_source_anchors"]}) == 65

    objects = {item["object"]: item for item in protocol["measurement_objects"]}
    assert set(objects) == {
        "evidence_bundle",
        "candidate",
        "frozen_judge",
        "prompt",
        "provider",
        "parser",
        "repair_policy",
        "extraction_algorithm",
    }
    assert objects["candidate"]["studied"] is True
    assert objects["frozen_judge"]["studied"] is True
    assert all(item["modified"] is False for item in objects.values())
    assert protocol["claim_origin_definitions"].keys() == {"explicit", "inferred", "synthesized"}
    assert protocol["calibration_policy"]["threshold_change_allowed"] is False
    assert protocol["calibration_policy"]["prompt_change_allowed"] is False
    assert protocol["calibration_policy"]["rule_change_allowed"] is False
    assert protocol["calibration_policy"]["same_data_optimization_allowed"] is False

    expected_claim_counts = (74, 77)
    for reviewer, expected_count in zip((reviewer_a, reviewer_b), expected_claim_counts):
        assert reviewer["completed"] is True
        assert len(reviewer["claims"]) == expected_count
        assert reviewer["blind_to_other_reviewer"] is True
        assert reviewer["blind_to_frozen_judge"] is True
        assert reviewer["blind_to_phase7_3_aggregates"] is True
        assert reviewer["held_out_accessed"] is False

    assert len(blind_packet["cases"]) == 10
    assert sum(len(case["claim_source_anchors"]) for case in blind_packet["cases"]) == 65
    assert blind_packet["blind_to_other_reviewer"] is True
    assert blind_packet["blind_to_frozen_judge"] is True
    assert blind_packet["blind_to_phase7_3_aggregates"] is True
    assert blind_packet["held_out_accessed"] is False
    serialized_packet = json.dumps(blind_packet, sort_keys=True)
    for forbidden_key in (
        '"reference_candidate":',
        '"unsupported_claim_rate":',
        '"scope_retention":',
        '"scorer_policy":',
        '"capability_matrix":',
        '"judge_warning":',
        '"reviewer_a":',
        '"reviewer_b":',
        '"adjudication":',
    ):
        assert forbidden_key not in serialized_packet

    assert adjudication["completed"] is True
    assert len(adjudication["claims"]) == 77
    assert adjudication["lineage"] is not None
    assert adjudication["disagreements_preserved"] is True
    assert report["agreement"] is None
    assert len(report["candidate_calibration_rows"]) == 10
    assert all(row["frozen_judge_unsupported_warning"] is True for row in report["candidate_calibration_rows"])
    strict = report["strict_safety_calibration"]
    assert (strict["true_positive"], strict["false_positive"], strict["false_negative"], strict["true_negative"], strict["excluded"]) == (9, 1, 0, 0, 0)
    assert strict["precision"] == 0.9
    assert strict["recall_sensitivity"] == 1.0
    assert strict["specificity"] == 0.0
    assert strict["balanced_accuracy"] == 0.5
    assert strict["matthews_correlation_coefficient"] is None
    strong = report["strong_error_calibration"]
    assert (strong["true_positive"], strong["false_positive"], strong["false_negative"], strong["true_negative"], strong["excluded"]) == (2, 1, 0, 0, 7)
    assert abs(strong["precision"] - 2 / 3) < 1e-12
    assert strong["recall_sensitivity"] == 1.0
    assert strong["specificity"] == 0.0
    assert strong["balanced_accuracy"] == 0.5
    assert strong["matthews_correlation_coefficient"] is None
    assert report["scope_calibration"] is None

    guards = report["guards"]
    assert guards["frozen_phase7_2_3_outputs_reused"] is True
    assert guards["evidence_bundle_frozen"] is True
    assert guards["candidate_modified"] is False
    assert guards["frozen_judge_modified"] is False
    assert guards["provider_calls_made"] is False
    assert guards["reviewer_a_completed"] is True
    assert guards["reviewer_b_completed"] is True
    assert guards["independent_adjudication_completed"] is True
    assert guards["scorer_calibration_completed"] is True
    assert guards["held_out_cases_untouched"] is True
    assert guards["runtime_authorized"] is False
    assert guards["hermes_authorized"] is False
    assert guards["candidate_learning_authorized"] is False
    assert guards["knowledge_promotion_authorized"] is False

    print("Phase: Phase 7.3.1 Independent Candidate Adjudication & Frozen Judge Calibration")
    print("Measurement objects: Candidate + Frozen Judge studied; all controls frozen")
    print("Claim-source anchors: 65 frozen fields independently segmented")
    print("Blind packet: 10 design cases / 65 anchors / no Judge or seed-label leakage")
    print("Reviewer A/B: two blind heterogeneous AI submissions completed (74/77 claims)")
    print("Agreement: frozen separately; third-model adjudication: 77/77 complete")
    print("Strict safety: TP=9 FP=1 FN=0 TN=0; precision=0.9 recall=1.0 specificity=0.0")
    print("Strong error: TP=2 FP=1 FN=0 TN=0 excluded=7; precision=0.6667 recall=1.0")
    print("Scope calibration: unavailable (scope labels were not adjudicated)")
    print("Decision: frozen_judge_diagnostic_calibration_complete")
    print("Held-out/runtime/Hermes: blocked")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
