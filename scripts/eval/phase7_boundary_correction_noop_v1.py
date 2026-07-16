#!/usr/bin/env python3
"""Deterministic Phase 7.3.3-D1 no-op Boundary Correction Gate v1."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
REPORTS = ROOT / "crates/eval/reports"
PROTOCOL = CONFIG / "phase7_3_3_d_boundary_correction_protocol_v1.json"
B4_SUBMISSION = REPORTS / "phase7_3_3_d_boundary_omission_resolution_submission_v2.json"
CORRECTION_WORKLIST = REPORTS / "phase7_3_3_d_boundary_correction_worklist_v2.json"
READINESS_V10 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v10.json"
MANIFEST = REPORTS / "phase7_3_3_d_boundary_correction_manifest_v1.json"
SUBMISSION = REPORTS / "phase7_3_3_d_boundary_correction_noop_submission_v1.json"
READINESS_V11 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v11.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: Any) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{path.relative_to(ROOT)}")
        return hashlib.sha256(data).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hashlib.sha256(data).hexdigest()


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, bool]]:
    for path in (PROTOCOL, B4_SUBMISSION, CORRECTION_WORKLIST, READINESS_V10):
        if not path.is_file():
            raise ValueError(f"required_frozen_input_missing:{path.relative_to(ROOT)}")
    protocol = load(PROTOCOL)
    submission = load(B4_SUBMISSION)
    worklist = load(CORRECTION_WORKLIST)
    readiness = load(READINESS_V10)
    decisions = submission.get("decisions")
    candidates = worklist.get("candidates")
    lineage = readiness.get("artifact_lineage", {})
    gates = readiness.get("gates", {})
    checks = {
        "protocol_offline_deterministic": protocol.get("execution_mode") == "offline_deterministic" and protocol.get("provider_call_allowed") is False,
        "b4_submission_completed": submission.get("status") == "completed_boundary_omission_resolution",
        "b4_submission_decision_count_is_4": submission.get("decision_count") == 4 and isinstance(decisions, list) and len(decisions) == 4,
        "b4_all_decisions_resolved_as_non_claim": isinstance(decisions, list) and all(item.get("resolution") == "resolved_as_non_claim" for item in decisions),
        "b4_submission_no_boundary_correction_performed": submission.get("boundary_correction_performed") is False,
        "worklist_source_submission_hash_matches": worklist.get("source_submission_sha256") == sha256(B4_SUBMISSION),
        "worklist_candidate_count_is_zero": worklist.get("candidate_count") == 0,
        "worklist_candidates_is_exact_empty_list": isinstance(candidates, list) and candidates == [],
        "worklist_automatic_correction_not_authorized": worklist.get("automatic_correction_authorized") is False,
        "readiness_v10_stage_is_boundary_correction": readiness.get("next_authorized_stage") == "boundary_correction",
        "readiness_v10_resolution_completed": gates.get("boundary_omission_resolution_completed") is True,
        "readiness_v10_correction_not_required": gates.get("boundary_correction_required") is False,
        "readiness_v10_confirmed_omission_count_is_zero": readiness.get("confirmed_boundary_omission_count") == 0,
        "readiness_v10_resolved_non_claim_count_is_4": readiness.get("resolved_as_non_claim_count") == 4,
        "readiness_v10_worklist_hash_matches": lineage.get("boundary_correction_worklist_sha256") == sha256(CORRECTION_WORKLIST),
        "readiness_v10_submission_hash_matches": lineage.get("b4_submission_sha256") == sha256(B4_SUBMISSION),
        "coverage_qa_not_run_in_prior_stage": readiness.get("coverage_qa_rerun_performed") is False,
        "held_out_not_accessed": submission.get("held_out_accessed") is False and worklist.get("held_out_accessed") is False and gates.get("held_out_accessed") is False,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("zero_candidate_lineage_validation_failed:" + ",".join(failed))
    return submission, worklist, readiness, checks


def expected_manifest() -> dict[str, Any]:
    _, worklist, _, checks = validate_inputs()
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d1-boundary-correction-manifest-v1",
        "status": "frozen_not_started",
        "execution_mode": "offline_deterministic",
        "adapter_path": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
        "artifact_lineage": {
            "adapter_sha256": sha256(Path(__file__)),
            "protocol_sha256": sha256(PROTOCOL),
            "b4_submission_sha256": sha256(B4_SUBMISSION),
            "boundary_correction_worklist_sha256": sha256(CORRECTION_WORKLIST),
            "readiness_v10_sha256": sha256(READINESS_V10),
        },
        "frozen_input_candidate_count": worklist["candidate_count"],
        "zero_candidate_lineage_checks": checks,
        "provider_call_allowed": False,
        "boundary_change_allowed": False,
        "coverage_qa_execution_allowed_in_this_stage": False,
        "boundary_gold_freeze_allowed_in_this_stage": False,
        "support_label_access_allowed": False,
        "held_out_access_allowed": False,
    }


def freeze_manifest() -> dict[str, Any]:
    manifest = expected_manifest()
    digest = write_once(MANIFEST, manifest)
    return {
        "status": "boundary_correction_manifest_frozen_not_started",
        "manifest_sha256": digest,
        "input_candidate_count": manifest["frozen_input_candidate_count"],
        "provider_called": False,
        "held_out_accessed": False,
    }


def execute() -> dict[str, Any]:
    b4_submission, worklist, readiness_v10, checks = validate_inputs()
    if not MANIFEST.is_file():
        raise ValueError("frozen_manifest_required_before_execution")
    if load(MANIFEST) != expected_manifest():
        raise ValueError("frozen_manifest_does_not_match_current_inputs_or_adapter")
    manifest_hash = sha256(MANIFEST)
    submission = {
        "schema_version": 1,
        "submission_id": "phase7.3.3-d1-boundary-correction-noop-submission-v1",
        "status": "completed_noop_boundary_correction",
        "manifest_sha256": manifest_hash,
        "protocol_sha256": sha256(PROTOCOL),
        "source_b4_submission_sha256": sha256(B4_SUBMISSION),
        "source_worklist_sha256": sha256(CORRECTION_WORKLIST),
        "source_readiness_v10_sha256": sha256(READINESS_V10),
        "source_b4_decision_count": b4_submission["decision_count"],
        "source_confirmed_boundary_omission_count": readiness_v10["confirmed_boundary_omission_count"],
        "input_candidate_count": worklist["candidate_count"],
        "submission_candidate_count": 0,
        "corrected_candidate_count": 0,
        "corrections": [],
        "boundary_changes_performed": False,
        "zero_candidate_lineage_validated": True,
        "zero_candidate_lineage_checks": checks,
        "provider_called": False,
        "coverage_qa_rerun_performed": False,
        "boundary_gold_frozen": False,
        "support_review_allowed": False,
        "held_out_accessed": False,
    }
    submission_hash = write_once(SUBMISSION, submission)
    readiness = {
        "schema_version": 11,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v11",
        "status": "boundary_correction_complete_coverage_qa_rerun_authorized",
        "artifact_lineage": {
            **readiness_v10["artifact_lineage"],
            "readiness_v10_sha256": sha256(READINESS_V10),
            "boundary_correction_protocol_sha256": sha256(PROTOCOL),
            "boundary_correction_manifest_sha256": manifest_hash,
            "boundary_correction_submission_sha256": submission_hash,
        },
        "gates": {
            "dual_blind_gap_review_completed": True,
            "agreement_computed": True,
            "disagreements_resolved": True,
            "explicit_non_claim_accounting_frozen": True,
            "boundary_omission_resolution_completed": True,
            "boundary_correction_completed": True,
            "boundary_correction_required": False,
            "boundary_changes_performed": False,
            "zero_candidate_lineage_validated": True,
            "coverage_qa_rerun_allowed": True,
            "coverage_qa_passed": False,
            "boundary_gold_frozen": False,
            "support_review_allowed": False,
            "held_out_accessed": False,
        },
        "gap_count": readiness_v10["gap_count"],
        "adjudicated_gap_count": readiness_v10["adjudicated_gap_count"],
        "boundary_omission_candidate_count": readiness_v10["boundary_omission_candidate_count"],
        "confirmed_boundary_omission_count": 0,
        "resolved_as_non_claim_count": readiness_v10["resolved_as_non_claim_count"],
        "boundary_correction_input_candidate_count": 0,
        "boundary_correction_submission_candidate_count": 0,
        "corrected_candidate_count": 0,
        "next_authorized_stage": "coverage_qa_rerun",
        "automatic_boundary_repair_performed": False,
        "boundary_changes_performed": False,
        "coverage_qa_rerun_performed": False,
        "boundary_gold_frozen": False,
        "support_review_allowed": False,
        "held_out_accessed": False,
    }
    readiness_hash = write_once(READINESS_V11, readiness)
    return {
        "status": submission["status"],
        "manifest_sha256": manifest_hash,
        "submission_sha256": submission_hash,
        "readiness_v11_sha256": readiness_hash,
        "input_candidate_count": 0,
        "corrected_candidate_count": 0,
        "boundary_changes_performed": False,
        "coverage_qa_rerun_allowed": True,
        "coverage_qa_rerun_performed": False,
        "boundary_gold_frozen": False,
        "support_review_allowed": False,
        "provider_called": False,
        "held_out_accessed": False,
    }


def verify() -> dict[str, Any]:
    _, worklist, _, checks = validate_inputs()
    manifest_matches = not MANIFEST.exists() or load(MANIFEST) == expected_manifest()
    submission_valid = True
    readiness_valid = True
    if SUBMISSION.exists():
        frozen = load(SUBMISSION)
        submission_valid = frozen.get("status") == "completed_noop_boundary_correction" and frozen.get("input_candidate_count") == 0 and frozen.get("submission_candidate_count") == 0 and frozen.get("corrected_candidate_count") == 0 and frozen.get("corrections") == [] and frozen.get("boundary_changes_performed") is False
    if READINESS_V11.exists():
        frozen = load(READINESS_V11)
        gates = frozen.get("gates", {})
        readiness_valid = frozen.get("next_authorized_stage") == "coverage_qa_rerun" and gates.get("boundary_correction_completed") is True and gates.get("coverage_qa_rerun_allowed") is True and gates.get("coverage_qa_passed") is False and gates.get("boundary_gold_frozen") is False and gates.get("support_review_allowed") is False
    all_passed = all(checks.values()) and manifest_matches and submission_valid and readiness_valid
    return {
        "status": "verified" if all_passed else "failed",
        "all_passed": all_passed,
        "source_worklist_candidate_count": worklist["candidate_count"],
        "checks": {**checks, "manifest_matches_current_frozen_inputs": manifest_matches, "no_op_submission_valid_if_present": submission_valid, "readiness_v11_valid_if_present": readiness_valid},
        "hashes": {
            "adapter_sha256": sha256(Path(__file__)),
            "protocol_sha256": sha256(PROTOCOL),
            "b4_submission_sha256": sha256(B4_SUBMISSION),
            "boundary_correction_worklist_sha256": sha256(CORRECTION_WORKLIST),
            "readiness_v10_sha256": sha256(READINESS_V10),
            "manifest_sha256": sha256(MANIFEST) if MANIFEST.exists() else None,
            "submission_sha256": sha256(SUBMISSION) if SUBMISSION.exists() else None,
            "readiness_v11_sha256": sha256(READINESS_V11) if READINESS_V11.exists() else None,
        },
        "provider_called": False,
        "held_out_accessed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-inputs", action="store_true")
    group.add_argument("--freeze-manifest", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.verify_inputs:
        print(json.dumps(verify(), ensure_ascii=False, indent=2))
    elif args.freeze_manifest:
        print(json.dumps(freeze_manifest(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(execute(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())