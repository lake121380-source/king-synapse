#!/usr/bin/env python3
"""Deterministic Phase 7.3.3-D1 Boundary Gold Freeze Gate v1."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import phase7_boundary_coverage_v4 as base
import phase7_boundary_coverage_rerun_v1 as rerun

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

PROTOCOL = CONFIG / "phase7_3_3_d_boundary_gold_freeze_protocol_v1.json"
REFERENCE_POLICY = CONFIG / "phase7_3_3_d_reference_construction_policy_v1.json"
SUPPORT_PROTOCOL = DATA / "phase7_3_3_d_support_reference_protocol_v1.json"
BOUNDARY_SUBMISSION = REPORTS / "phase7_3_3_d_boundary_adjudicator_submission_v4.json"
ACCOUNTING = REPORTS / "phase7_3_3_d_explicit_non_claim_accounting_v1.json"
COVERAGE_REPORT = REPORTS / "phase7_3_3_d_boundary_coverage_rerun_report_v1.json"
RESIDUAL_WORKLIST = REPORTS / "phase7_3_3_d_boundary_coverage_rerun_gap_worklist_v1.json"
READINESS_V12 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v12.json"

MANIFEST = REPORTS / "phase7_3_3_d_boundary_gold_freeze_manifest_v1.json"
BOUNDARY_GOLD = DATA / "phase7_3_3_d_boundary_gold_v1.json"
FREEZE_RECEIPT = REPORTS / "phase7_3_3_d_boundary_gold_freeze_receipt_v1.json"
SUPPORT_STATE_V2 = DATA / "phase7_3_3_d_support_stage_state_v2.json"
READINESS_V13 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v13.json"


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


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    required = (
        PROTOCOL, REFERENCE_POLICY, SUPPORT_PROTOCOL, BOUNDARY_SUBMISSION,
        ACCOUNTING, COVERAGE_REPORT, RESIDUAL_WORKLIST, READINESS_V12,
        rerun.MANIFEST, rerun.PROTOCOL, base.PACKET, base.WORKLIST,
    )
    for path in required:
        if not path.is_file():
            raise ValueError(f"required_frozen_input_missing:{path.relative_to(ROOT)}")

    protocol = load(PROTOCOL)
    submission = load(BOUNDARY_SUBMISSION)
    accounting = load(ACCOUNTING)
    report = load(COVERAGE_REPORT)
    residual = load(RESIDUAL_WORKLIST)
    readiness = load(READINESS_V12)

    packet = base.load(base.PACKET)
    boundary_worklist = base.load(base.WORKLIST)
    order, anchors, worklist_anchors = base.indexes(packet, boundary_worklist)
    claims_by, structural = base.validate(order, anchors, worklist_anchors, submission)
    reconstructed_accounting, rerun_context = rerun.validate_and_construct()
    expected_accounting = {
        **reconstructed_accounting,
        "coverage_rerun_manifest_sha256": sha256(rerun.MANIFEST),
    }

    claim_ids = [claim.get("adjudicated_claim_id") for claim in submission.get("claims", [])]
    support_keys = {"support_label", "cited_evidence_ids", "support_rationale", "support_confidence"}
    coverage_metrics = readiness.get("coverage_metrics", {})
    gates = readiness.get("gates", {})
    lineage = readiness.get("artifact_lineage", {})
    report_gate_values = report.get("freeze_gate_values", {})

    checks = {
        "protocol_offline_deterministic": protocol.get("execution_mode") == "offline_deterministic",
        "boundary_submission_completed_reference_candidate": submission.get("status") == "completed_model_adjudicated_boundary_reference_candidate" and submission.get("claim_count") == 118 and len(submission.get("claims", [])) == 118,
        "boundary_submission_not_previously_frozen": submission.get("boundary_gold_frozen") is False and submission.get("support_review_allowed") is False,
        "claim_ids_unique_and_nonempty": len(claim_ids) == len(set(claim_ids)) == 118 and all(isinstance(item, str) and item for item in claim_ids),
        "support_fields_absent_from_boundary_claims": all(not support_keys.intersection(claim) for claim in submission.get("claims", [])),
        "boundary_structural_validation_clean": all(structural.get(name) == 0 for name in ("invalid_span_count", "blank_or_zero_length_claim_count", "claim_text_mismatch_count", "source_occurrence_mismatch_count", "unknown_anchor_count", "missing_anchor_count", "unknown_reviewer_claim_id_count", "source_metadata_mismatch_count", "duplicate_adjudicated_claim_id_count", "sequential_claim_id_failure_count", "overlap_characters")),
        "stored_accounting_matches_deterministic_reconstruction": accounting == expected_accounting,
        "explicit_non_claim_span_count_is_84": accounting.get("span_count") == 84 and len(accounting.get("spans", [])) == 84,
        "coverage_report_passed": report.get("status") == "passed" and report.get("freeze_gates_passed") is True and report.get("freeze_gate_failures") == [] and report.get("boundary_gold_freeze_allowed") is True,
        "coverage_report_accounting_hash_matches": report.get("explicit_non_claim_accounting_sha256") == sha256(ACCOUNTING),
        "coverage_report_manifest_hash_matches": report.get("coverage_rerun_manifest_sha256") == sha256(rerun.MANIFEST),
        "coverage_gate_values_zero": all(report_gate_values.get(name) == 0 for name in ("invalid_claim_span_count", "claim_text_mismatch_count", "claim_overlap_characters", "invalid_non_claim_span_count", "invalid_non_claim_metadata_count", "invalid_non_claim_reason_code_count", "non_claim_overlap_characters", "claim_non_claim_conflict_characters", "eligible_gap_characters", "unclassified_characters", "lineage_failure_count")),
        "three_class_accounting_complete": report.get("three_class_accounting", {}).get("accounting_ratio") == 1.0 and report.get("three_class_accounting", {}).get("accounted_characters") == report.get("three_class_accounting", {}).get("total_anchor_characters") and report.get("three_class_accounting", {}).get("unclassified_characters") == 0,
        "residual_worklist_empty": residual.get("status") == "no_unaccounted_eligible_gaps" and residual.get("residual_gap_count") == 0 and residual.get("eligible_gap_character_count") == 0 and residual.get("gaps") == [],
        "residual_report_hash_matches": residual.get("coverage_rerun_report_sha256") == sha256(COVERAGE_REPORT),
        "readiness_v12_authorizes_freeze": readiness.get("status") == "coverage_qa_rerun_passed_boundary_gold_freeze_authorized" and readiness.get("next_authorized_stage") == "boundary_gold_freeze" and gates.get("boundary_gold_freeze_allowed") is True and gates.get("boundary_gold_frozen") is False and gates.get("support_review_allowed") is False,
        "readiness_v12_coverage_hashes_match": lineage.get("explicit_non_claim_accounting_sha256") == sha256(ACCOUNTING) and lineage.get("coverage_rerun_report_sha256") == sha256(COVERAGE_REPORT) and lineage.get("coverage_rerun_residual_worklist_sha256") == sha256(RESIDUAL_WORKLIST),
        "readiness_v12_metrics_pass": coverage_metrics.get("eligible_gap_characters") == 0 and coverage_metrics.get("unclassified_characters") == 0 and coverage_metrics.get("overlap_conflicts") == 0 and coverage_metrics.get("lineage_failures") == 0 and coverage_metrics.get("accounting_ratio") == 1.0,
        "rerun_lineage_revalidation_passed": all(rerun_context["checks"].values()),
        "held_out_not_accessed": submission.get("held_out_accessed") is False and accounting.get("held_out_accessed") is False and report.get("held_out_accessed") is False and residual.get("held_out_accessed") is False and readiness.get("held_out_accessed") is False,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise ValueError("boundary_gold_freeze_input_validation_failed:" + ",".join(failures))

    context = {
        "checks": checks,
        "structural": structural,
        "anchor_count": len(order),
        "case_count": len({case_id for case_id, _ in order}),
        "claims_by": claims_by,
    }
    inputs = {
        "submission": submission,
        "accounting": accounting,
        "report": report,
        "residual": residual,
        "readiness": readiness,
    }
    return inputs, context


def build_gold(inputs: dict[str, Any], manifest_hash: str) -> dict[str, Any]:
    submission = inputs["submission"]
    accounting = inputs["accounting"]
    report = inputs["report"]
    claims = []
    for source in submission["claims"]:
        claim = {
            "boundary_claim_id": source["adjudicated_claim_id"],
            "source_adjudicated_claim_id": source["adjudicated_claim_id"],
            **{key: value for key, value in source.items() if key != "adjudicated_claim_id"},
        }
        claims.append(claim)
    three_class = report["three_class_accounting"]
    return {
        "schema_version": 1,
        "boundary_gold_id": "phase7.3.3-d1-project-boundary-gold-v1",
        "status": "frozen_project_boundary_gold",
        "reference_status": "project_boundary_gold_model_adjudicated_not_human_gold",
        "freeze_manifest_sha256": manifest_hash,
        "artifact_lineage": {
            "boundary_reference_candidate_sha256": sha256(BOUNDARY_SUBMISSION),
            "explicit_non_claim_accounting_sha256": sha256(ACCOUNTING),
            "coverage_rerun_report_sha256": sha256(COVERAGE_REPORT),
            "coverage_rerun_residual_worklist_sha256": sha256(RESIDUAL_WORKLIST),
            "readiness_v12_sha256": sha256(READINESS_V12),
            "boundary_reference_protocol_sha256": submission["adjudication_protocol_sha256"],
            "boundary_agreement_report_sha256": submission["agreement_report_sha256"],
            "boundary_adjudication_worklist_sha256": submission["worklist_sha256"],
        },
        "case_count": submission["case_count"],
        "anchor_count": 65,
        "boundary_claim_count": len(claims),
        "explicit_non_claim_span_count": accounting["span_count"],
        "protocol_excluded_span_count": three_class["protocol_excluded_span_count"],
        "claims": claims,
        "explicit_non_claim_spans": accounting["spans"],
        "protocol_excluded_spans": three_class["protocol_excluded_spans"],
        "coverage_metrics": {
            "total_anchor_characters": three_class["total_anchor_characters"],
            "claim_characters": three_class["claim_characters"],
            "explicit_non_claim_characters": three_class["explicit_non_claim_characters"],
            "protocol_excluded_characters": three_class["protocol_excluded_characters"],
            "unclassified_characters": three_class["unclassified_characters"],
            "accounted_characters": three_class["accounted_characters"],
            "accounting_ratio": three_class["accounting_ratio"],
        },
        "boundary_claim_fields_immutable": [
            "boundary_claim_id", "case_id", "response_sha256", "anchor_id",
            "source_field", "source_index", "source_text_sha256", "source_span",
            "source_occurrence_index", "claim_text", "claim_type", "claim_role",
            "anchor_group", "material", "claim_origin",
        ],
        "support_labels_present": False,
        "provider_called_for_freeze": False,
        "held_out_accessed": False,
    }


def expected_manifest() -> dict[str, Any]:
    inputs, context = validate_inputs()
    sources = {
        "adapter": Path(__file__),
        "protocol": PROTOCOL,
        "reference_construction_policy": REFERENCE_POLICY,
        "support_reference_protocol": SUPPORT_PROTOCOL,
        "boundary_reference_candidate": BOUNDARY_SUBMISSION,
        "explicit_non_claim_accounting": ACCOUNTING,
        "coverage_rerun_report": COVERAGE_REPORT,
        "coverage_rerun_residual_worklist": RESIDUAL_WORKLIST,
        "readiness_v12": READINESS_V12,
        "coverage_rerun_manifest": rerun.MANIFEST,
        "coverage_rerun_adapter": Path(rerun.__file__),
    }
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d1-boundary-gold-freeze-manifest-v1",
        "status": "frozen_not_started",
        "execution_mode": "offline_deterministic",
        "artifact_lineage": {name + "_sha256": sha256(path) for name, path in sources.items()},
        "validated_case_count": inputs["submission"]["case_count"],
        "validated_anchor_count": context["anchor_count"],
        "validated_boundary_claim_count": inputs["submission"]["claim_count"],
        "validated_explicit_non_claim_span_count": inputs["accounting"]["span_count"],
        "entry_gate_checks": context["checks"],
        "expected_outputs": {
            "boundary_gold": BOUNDARY_GOLD.relative_to(ROOT).as_posix(),
            "freeze_receipt": FREEZE_RECEIPT.relative_to(ROOT).as_posix(),
            "support_stage_state_v2": SUPPORT_STATE_V2.relative_to(ROOT).as_posix(),
            "readiness_v13": READINESS_V13.relative_to(ROOT).as_posix(),
        },
        "provider_call_allowed": False,
        "semantic_mutation_allowed": False,
        "support_judgment_allowed_in_this_stage": False,
        "held_out_access_allowed": False,
    }


def execute() -> dict[str, Any]:
    inputs, context = validate_inputs()
    if not MANIFEST.is_file():
        raise ValueError("frozen_manifest_required_before_execution")
    if load(MANIFEST) != expected_manifest():
        raise ValueError("frozen_manifest_does_not_match_current_inputs_or_adapter")
    manifest_hash = sha256(MANIFEST)
    gold = build_gold(inputs, manifest_hash)
    gold_hash = write_once(BOUNDARY_GOLD, gold)
    receipt = {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d1-boundary-gold-freeze-receipt-v1",
        "status": "completed_boundary_gold_freeze",
        "manifest_sha256": manifest_hash,
        "boundary_gold_sha256": gold_hash,
        "entry_gate_checks": context["checks"],
        "case_count": gold["case_count"],
        "anchor_count": gold["anchor_count"],
        "boundary_claim_count": gold["boundary_claim_count"],
        "explicit_non_claim_span_count": gold["explicit_non_claim_span_count"],
        "protocol_excluded_span_count": gold["protocol_excluded_span_count"],
        "claims_added_deleted_or_semantically_modified": False,
        "support_labels_added": False,
        "provider_called": False,
        "held_out_accessed": False,
    }
    receipt_hash = write_once(FREEZE_RECEIPT, receipt)
    support_state = {
        "schema_version": 2,
        "state_id": "phase7.3.3-d1-b-support-stage-state-v2",
        "boundary_state": "frozen_project_boundary_gold",
        "support_state": "authorized_not_started",
        "blocked_reason": None,
        "boundary_gold_sha256": gold_hash,
        "boundary_gold_freeze_receipt_sha256": receipt_hash,
        "boundary_claim_count": gold["boundary_claim_count"],
        "support_review_packets_generated": False,
        "support_reviewer_a_completed": False,
        "support_reviewer_b_completed": False,
        "support_agreement_available": False,
        "support_adjudication_allowed": False,
        "support_gold_frozen": False,
        "support_gold_sha256": None,
        "immutable_boundary_claim_fields": gold["boundary_claim_fields_immutable"],
        "support_review_allowed": True,
        "held_out_accessed": False,
    }
    support_state_hash = write_once(SUPPORT_STATE_V2, support_state)
    prior = inputs["readiness"]
    readiness = {
        "schema_version": 13,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v13",
        "status": "boundary_gold_frozen_support_review_packet_construction_authorized",
        "artifact_lineage": {
            **prior["artifact_lineage"],
            "readiness_v12_sha256": sha256(READINESS_V12),
            "boundary_gold_freeze_protocol_sha256": sha256(PROTOCOL),
            "boundary_gold_freeze_manifest_sha256": manifest_hash,
            "boundary_gold_sha256": gold_hash,
            "boundary_gold_freeze_receipt_sha256": receipt_hash,
            "support_stage_state_v2_sha256": support_state_hash,
        },
        "gates": {
            **prior["gates"],
            "boundary_gold_freeze_allowed": True,
            "boundary_gold_frozen": True,
            "support_review_packet_construction_allowed": True,
            "support_review_allowed": True,
            "support_review_started": False,
            "held_out_accessed": False,
        },
        "boundary_gold": {
            "boundary_gold_sha256": gold_hash,
            "reference_status": gold["reference_status"],
            "case_count": gold["case_count"],
            "anchor_count": gold["anchor_count"],
            "boundary_claim_count": gold["boundary_claim_count"],
            "explicit_non_claim_span_count": gold["explicit_non_claim_span_count"],
            "protocol_excluded_span_count": gold["protocol_excluded_span_count"],
            "coverage_accounting_ratio": gold["coverage_metrics"]["accounting_ratio"],
        },
        "next_authorized_stage": "support_review_packet_construction",
        "boundary_gold_frozen": True,
        "support_review_allowed": True,
        "support_review_started": False,
        "support_gold_frozen": False,
        "held_out_accessed": False,
    }
    readiness_hash = write_once(READINESS_V13, readiness)
    return {
        "status": receipt["status"],
        "manifest_sha256": manifest_hash,
        "boundary_gold_sha256": gold_hash,
        "freeze_receipt_sha256": receipt_hash,
        "support_stage_state_v2_sha256": support_state_hash,
        "readiness_v13_sha256": readiness_hash,
        "case_count": gold["case_count"],
        "anchor_count": gold["anchor_count"],
        "boundary_claim_count": gold["boundary_claim_count"],
        "explicit_non_claim_span_count": gold["explicit_non_claim_span_count"],
        "protocol_excluded_span_count": gold["protocol_excluded_span_count"],
        "support_review_packet_construction_allowed": True,
        "support_review_started": False,
        "provider_called": False,
        "held_out_accessed": False,
    }


def verify() -> dict[str, Any]:
    inputs, context = validate_inputs()
    manifest_matches = not MANIFEST.exists() or load(MANIFEST) == expected_manifest()
    gold_valid = True
    if BOUNDARY_GOLD.exists():
        expected = build_gold(inputs, sha256(MANIFEST))
        gold_valid = load(BOUNDARY_GOLD) == expected
    readiness_valid = True
    if READINESS_V13.exists():
        frozen = load(READINESS_V13)
        readiness_valid = frozen.get("next_authorized_stage") == "support_review_packet_construction" and frozen.get("boundary_gold_frozen") is True and frozen.get("support_review_allowed") is True and frozen.get("support_review_started") is False
    return {
        "status": "verified" if all(context["checks"].values()) and manifest_matches and gold_valid and readiness_valid else "failed",
        "all_entry_gate_checks_passed": all(context["checks"].values()),
        "validated_boundary_claim_count": inputs["submission"]["claim_count"],
        "validated_explicit_non_claim_span_count": inputs["accounting"]["span_count"],
        "manifest_matches_current_inputs": manifest_matches,
        "boundary_gold_valid_if_present": gold_valid,
        "readiness_v13_valid_if_present": readiness_valid,
        "hashes": {
            "adapter_sha256": sha256(Path(__file__)),
            "protocol_sha256": sha256(PROTOCOL),
            "manifest_sha256": sha256(MANIFEST) if MANIFEST.exists() else None,
            "boundary_gold_sha256": sha256(BOUNDARY_GOLD) if BOUNDARY_GOLD.exists() else None,
            "freeze_receipt_sha256": sha256(FREEZE_RECEIPT) if FREEZE_RECEIPT.exists() else None,
            "support_stage_state_v2_sha256": sha256(SUPPORT_STATE_V2) if SUPPORT_STATE_V2.exists() else None,
            "readiness_v13_sha256": sha256(READINESS_V13) if READINESS_V13.exists() else None,
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
        result = verify()
    elif args.freeze_manifest:
        manifest = expected_manifest()
        result = {
            "status": "boundary_gold_freeze_manifest_frozen_not_started",
            "manifest_sha256": write_once(MANIFEST, manifest),
            "validated_boundary_claim_count": manifest["validated_boundary_claim_count"],
            "provider_called": False,
            "held_out_accessed": False,
        }
    else:
        result = execute()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())