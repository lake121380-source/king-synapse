#!/usr/bin/env python3
"""Deterministic quality gate for Phase 7.2.1 bounded extraction provider."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_bounded_pattern_extraction_provider.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_PROFILE_TEST_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_bounded_pattern_extraction_provider"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["phase"] == "Phase 7.2.1 Bounded Pattern Extraction Provider"
    assert report["summary"]["design_case_count"] == 10
    assert report["summary"]["provider_executions"] == 10
    assert report["summary"]["candidates_produced"] == 10
    assert report["summary"]["contract_accepted_cases"] == 10
    assert report["summary"]["mean_pattern_completeness"] == 1.0
    assert report["summary"]["mean_evidence_attribution_accuracy"] == 1.0
    assert report["summary"]["mean_scope_retention"] == 1.0
    assert report["summary"]["mean_counterexample_handling"] == 1.0
    assert len(report["fault_injections"]) == 6
    assert all(item["rejected"] for item in report["fault_injections"])
    assert report["guards"]["design_cases_only"] is True
    assert report["guards"]["held_out_cases_untouched"] is True
    assert report["guards"]["automatic_output_repair"] is False
    assert report["guards"]["knowledge_promotion_authorized"] is False
    assert report["guards"]["transfer_value_claimed"] is False
    assert report["guards"]["runtime_authorized"] is False
    assert report["decision"] == "provider_frozen_design_evaluation_only"

    print("Phase:", report["phase"])
    print("Provider:", report["provider_config"]["provider_id"])
    print("Design cases:", report["summary"]["design_case_count"])
    print("Contract accepted:", report["summary"]["contract_accepted_cases"])
    print("Quality diagnostics:", report["summary"]["cases_with_quality_diagnostics"])
    print("Mean reference token recall:", report["summary"]["mean_design_reference_token_recall"])
    print("Fault injections rejected:", len(report["fault_injections"]))
    print("Held-out cases untouched:", report["guards"]["held_out_cases_untouched"])
    print("Runtime authorized:", report["guards"]["runtime_authorized"])
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
