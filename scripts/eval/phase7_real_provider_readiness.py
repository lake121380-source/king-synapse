#!/usr/bin/env python3
"""Deterministic quality gate for Phase 7.2.3 real provider readiness."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_real_provider_readiness.json"
EXECUTION = ROOT / "crates/eval/reports/phase7_2_3_real_provider_execution.json"
HISTORICAL = ROOT / "crates/eval/reports/phase7_2_2_model_provider_execution.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_PROFILE_TEST_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_real_provider_readiness"],
        cwd=ROOT,
        env=env,
        check=True,
    )

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))

    assert report["phase"] == "Phase 7.2.3 Real Provider Readiness Validation"
    assert report["decision"] == "provider_ready_candidates_require_quality_review"
    assert report["artifact_hashes"]["frozen_protocol_matches_manifest"] is True
    assert report["artifact_hashes"]["execution_matches_frozen_protocol"] is True

    summary = report["summary"]
    assert summary["design_case_count"] == 10
    assert summary["attempted_design_cases"] == 10
    assert summary["completed_design_cases"] == 10
    assert summary["strict_parser_acceptance_rate"] == 1.0
    assert summary["contract_validity"] == 1.0
    assert summary["evidence_attribution_accuracy"] == 1.0
    assert summary["scope_preservation"] == 0.7
    assert summary["counterexample_retention"] == 1.0
    assert abs(summary["unsupported_claim_rate"] - 0.5128640676484479) < 1e-12
    assert summary["unsupported_claim_requires_review"] is True

    guards = report["guards"]
    assert guards["authenticated_preflight_completed"] is True
    assert guards["all_design_requests_attempted_once"] is True
    assert guards["all_design_outputs_strictly_parsed"] is True
    assert guards["all_candidates_contract_valid"] is True
    assert guards["provider_ready"] is True
    assert guards["automatic_output_repair"] is False
    assert guards["selective_retry"] is False
    assert guards["api_key_recorded"] is False
    assert guards["raw_response_text_recorded"] is False
    assert guards["held_out_cases_untouched"] is True
    assert guards["candidate_learning_authorized"] is False
    assert guards["pattern_persistence_authorized"] is False
    assert guards["knowledge_promotion_authorized"] is False
    assert guards["runtime_authorized"] is False
    assert guards["hermes_authorized"] is False

    assert execution["status"] == "completed"
    assert len(execution["outputs"]) == 10
    assert execution["api_key_recorded"] is False
    assert execution["raw_response_text_recorded"] is False

    # Phase 7.2.2 remains a frozen historical record rather than being rewritten.
    assert historical["status"] == "blocked_authorization"
    assert historical["attempted_design_cases"] == 0
    assert historical["completed_design_cases"] == 0
    assert historical["outputs"] == []

    print("Phase: Phase 7.2.3 Real Provider Readiness Validation")
    print("Provider readiness: PASS (10/10 frozen design cases)")
    print(f"Unsupported claim rate: {summary['unsupported_claim_rate']:.4f} (quality review required)")
    print("Held-out cases untouched: true")
    print("Knowledge/runtime authorization: false")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
