#!/usr/bin/env python3
"""Deterministic quality gate for Phase 7.2.2 provider capability matrix."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
REPORT = ROOT / "crates/eval/reports/phase7_pattern_provider_comparison.json"
MANIFESTS = CONFIG / "phase7_2_2_provider_manifests.json"
EXECUTION = ROOT / "crates/eval/reports/phase7_2_2_model_provider_execution.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_PROFILE_TEST_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_pattern_provider_comparison"],
        cwd=ROOT, env=env, check=True,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    manifests = json.loads(MANIFESTS.read_text(encoding="utf-8"))
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))

    frozen = {
        "prompt_sha256": sha256(CONFIG / "phase7_2_2_canonical_prompt_v1.md"),
        "parser_sha256": sha256(CONFIG / "phase7_2_2_parser_policy_v1.json"),
        "scorer_sha256": sha256(CONFIG / "phase7_2_2_scorer_policy_v1.json"),
        "dataset_sha256": sha256(ROOT / "crates/eval/datasets/pattern_extraction/phase7_2_pattern_extraction_design.json"),
    }
    assert all(manifests[key] == value for key, value in frozen.items())
    assert report["artifact_hashes"]["all_match_manifest"] is True
    assert report["canonical_prompt_version"] == "PatternExtractorPrompt-v1"
    assert len(report["capability_matrix"]) == 2

    weak, model = report["capability_matrix"]
    assert weak["execution_status"] == "completed"
    assert weak["design_cases_completed"] == 10
    assert weak["contract_validity"] == 1.0
    assert weak["unsupported_claim_rate"] is not None

    assert model["execution_status"] == "blocked_authorization"
    assert model["design_cases_attempted"] == 0
    assert model["design_cases_completed"] == 0
    metric_keys = [
        "contract_validity", "evidence_attribution_accuracy", "scope_preservation",
        "counterexample_retention", "unsupported_claim_rate", "abstraction_distance",
        "design_reference_token_recall", "cases_with_quality_diagnostics",
    ]
    assert all(model[key] is None for key in metric_keys)
    assert execution["outputs"] == []
    assert execution["api_key_recorded"] is False
    assert execution["raw_response_text_recorded"] is False

    assert report["scorer_policy"]["primary_safety_metric"] == "unsupported_claim_rate"
    assert report["scorer_policy"]["fluency_metric"] is None
    assert report["scorer_policy"]["style_metric"] is None
    guards = report["guards"]
    assert guards["design_cases_only"] is True
    assert guards["held_out_cases_untouched"] is True
    assert guards["pattern_persistence_authorized"] is False
    assert guards["knowledge_promotion_authorized"] is False
    assert guards["runtime_authorized"] is False
    assert guards["hermes_authorized"] is False
    assert report["decision"] == "comparison_protocol_frozen_model_execution_blocked"

    print("Phase:", report["phase"])
    print("Weak baseline: completed")
    print("Model provider: blocked_authorization; no metrics fabricated")
    print("Held-out cases untouched:", guards["held_out_cases_untouched"])
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
