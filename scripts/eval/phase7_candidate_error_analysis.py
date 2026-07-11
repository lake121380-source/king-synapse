#!/usr/bin/env python3
"""Deterministic gate for Phase 7.3 failure taxonomy and candidate error analysis."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "crates/eval/reports/phase7_candidate_error_analysis.json"
ANNOTATIONS = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_candidate_error_annotations.json"
EXECUTION = ROOT / "crates/eval/reports/phase7_2_3_real_provider_execution.json"


def main() -> int:
    env = os.environ.copy()
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_BUILD_JOBS"] = "1"
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_candidate_error_analysis"],
        cwd=ROOT,
        env=env,
        check=True,
    )

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    annotations = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))

    assert report["phase"] == "Phase 7.3 Failure Taxonomy & Candidate Error Analysis"
    assert report["decision"] == "taxonomy_seeded_independent_review_required"
    assert annotations["source_execution_id"] == execution["execution_id"]
    assert annotations["annotation_mode"] == "single_reviewer_model_assisted_seed"
    assert annotations["reviewer_count"] == 1
    assert annotations["independent_second_review"] is False
    assert annotations["inter_rater_agreement"] is None
    assert annotations["held_out_accessed"] is False
    assert len(annotations["cases"]) == 10

    summary = report["summary"]
    assert summary["candidate_count"] == 10
    assert summary["candidates_with_failure_labels"] == 10
    assert summary["total_failure_labels"] == 25
    assert summary["unsupported_warning_count"] == 10
    assert summary["scope_warning_count"] == 6
    assert summary["scope_expansion_label_count"] == 0
    assert summary["scope_warning_confirmation_rate"] == 0.0
    assert summary["evidence_failure_case_count"] == 0
    assert summary["counterexample_failure_case_count"] == 0

    primary = {item["kind"]: item for item in summary["primary_failure_distribution"]}
    assert primary["prediction_without_support"]["primary_count"] == 4
    assert primary["prediction_without_support"]["any_label_count"] == 10
    assert primary["unsupported_generalization"]["primary_count"] == 3
    assert primary["causal_leap"]["primary_count"] == 2
    assert primary["over_abstraction"]["primary_count"] == 1
    assert primary["missing_evidence"]["any_label_count"] == 0
    assert primary["counterexample_ignored"]["any_label_count"] == 0

    confounds = {item["kind"]: item for item in summary["metric_confound_distribution"]}
    assert confounds["lexical_novelty_confound"]["case_count"] == 5
    assert confounds["scope_field_placement_confound"]["case_count"] == 6

    falsifiability = summary["falsifiability"]
    assert falsifiability["structural_fields_present_count"] == 10
    assert falsifiability["structural_fields_present_rate"] == 1.0
    assert falsifiability["direct_in_scope_test_count"] == 8
    assert falsifiability["direct_in_scope_test_rate"] == 0.8
    assert falsifiability["semantic_validity_established_count"] == 0

    guards = report["guards"]
    assert guards["frozen_phase7_2_3_execution_reused"] is True
    assert guards["provider_calls_made"] is False
    assert guards["prompt_modified"] is False
    assert guards["parser_modified"] is False
    assert guards["scorer_modified"] is False
    assert guards["extraction_algorithm_modified"] is False
    assert guards["held_out_cases_untouched"] is True
    assert guards["independent_second_review_completed"] is False
    assert guards["candidate_learning_authorized"] is False
    assert guards["pattern_persistence_authorized"] is False
    assert guards["knowledge_promotion_authorized"] is False
    assert guards["runtime_authorized"] is False
    assert guards["hermes_authorized"] is False

    print("Phase: Phase 7.3 Failure Taxonomy & Candidate Error Analysis")
    print("Candidates: 10 frozen design outputs")
    print("Primary failures: prediction=4 generalization=3 causal=2 over-abstraction=1")
    print("Metric confounds: lexical=5 scope-placement=6")
    print("Falsifiability: structural=10/10 direct-in-scope=8/10 semantic-validity=0/10")
    print("Independent adjudication: required")
    print("Held-out/runtime/Hermes: blocked")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
