#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

PROTOCOL = CONFIG / "phase7_3_3_d_support_lineage_correction_protocol_v1.json"
BOUNDARY_GOLD = DATA / "phase7_3_3_d_boundary_gold_v1.json"
BOUNDARY_FREEZE_RECEIPT = REPORTS / "phase7_3_3_d_boundary_gold_freeze_receipt_v1.json"
SHARED_PACKET = DATA / "phase7_3_3_d_support_blind_review_packet_v1.json"
REVIEWER_A_PACKET = DATA / "phase7_3_3_d_support_reviewer_a_packet_v1.json"
REVIEWER_B_PACKET = DATA / "phase7_3_3_d_support_reviewer_b_packet_v1.json"
REVIEWER_A_TEMPLATE = DATA / "phase7_3_3_d_support_reviewer_a_submission_v2.json"
REVIEWER_B_TEMPLATE = DATA / "phase7_3_3_d_support_reviewer_b_submission_v2.json"
CONSTRUCTION_MANIFEST = REPORTS / "phase7_3_3_d_support_review_packet_construction_manifest_v1.json"
CONSTRUCTION_RECEIPT = REPORTS / "phase7_3_3_d_support_review_packet_construction_receipt_v1.json"
STATE_V3 = DATA / "phase7_3_3_d_support_stage_state_v3.json"
READINESS_V14 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v14.json"

MANIFEST = REPORTS / "phase7_3_3_d_support_lineage_correction_manifest_v1.json"
STATE_V4 = DATA / "phase7_3_3_d_support_stage_state_v4.json"
READINESS_V15 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v15.json"
RECEIPT = REPORTS / "phase7_3_3_d_support_lineage_correction_receipt_v1.json"

UNCHANGED = {
    "boundary_gold_sha256": BOUNDARY_GOLD,
    "shared_packet_sha256": SHARED_PACKET,
    "reviewer_a_packet_sha256": REVIEWER_A_PACKET,
    "reviewer_b_packet_sha256": REVIEWER_B_PACKET,
    "reviewer_a_submission_template_sha256": REVIEWER_A_TEMPLATE,
    "reviewer_b_submission_template_sha256": REVIEWER_B_TEMPLATE,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_once(path: Path, value: Any) -> str:
    data = dump_bytes(value)
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError(f"immutable artifact already exists with different content: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return sha256(path)


def validate_inputs() -> dict[str, Any]:
    required = [
        PROTOCOL, BOUNDARY_GOLD, BOUNDARY_FREEZE_RECEIPT, SHARED_PACKET,
        REVIEWER_A_PACKET, REVIEWER_B_PACKET, REVIEWER_A_TEMPLATE,
        REVIEWER_B_TEMPLATE, CONSTRUCTION_MANIFEST, CONSTRUCTION_RECEIPT,
        STATE_V3, READINESS_V14,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"missing required artifacts: {missing}")

    state = load(STATE_V3)
    readiness = load(READINESS_V14)
    construction_receipt = load(CONSTRUCTION_RECEIPT)
    boundary_gold_hash = sha256(BOUNDARY_GOLD)
    freeze_receipt_hash = sha256(BOUNDARY_FREEZE_RECEIPT)
    observed = state.get("boundary_gold_freeze_receipt_sha256")

    checks = {
        "state_v3_is_expected_version": state.get("schema_version") == 3,
        "state_v3_records_boundary_gold_hash": state.get("boundary_gold_sha256") == boundary_gold_hash,
        "defect_reproduced_field_equals_boundary_gold_hash": observed == boundary_gold_hash,
        "defect_reproduced_field_differs_from_receipt_hash": observed != freeze_receipt_hash,
        "readiness_v14_authorizes_support_execution": readiness.get("next_authorized_stage") == "independent_support_review_execution",
        "support_review_not_started": state.get("support_review_started") is False and readiness.get("support_review_started") is False,
        "support_gold_not_frozen": state.get("support_gold_frozen") is False and readiness.get("support_gold_frozen") is False,
        "packet_construction_provider_not_called": state.get("provider_called_for_packet_construction") is False and construction_receipt.get("provider_called") is False,
        "held_out_not_accessed": state.get("held_out_accessed") is False and readiness.get("held_out_accessed") is False,
        "construction_manifest_hash_matches_receipt": construction_receipt.get("manifest_sha256") == sha256(CONSTRUCTION_MANIFEST),
    }
    for field, path in UNCHANGED.items():
        state_field = field
        if field == "reviewer_a_submission_template_sha256":
            state_field = field
        if field == "reviewer_b_submission_template_sha256":
            state_field = field
        checks[f"state_v3_{field}_matches_file"] = state.get(state_field) == sha256(path)

    if not all(checks.values()):
        failed = [name for name, ok in checks.items() if not ok]
        raise RuntimeError(f"lineage correction entry gate failed: {failed}")

    return {
        "state": state,
        "readiness": readiness,
        "boundary_gold_sha256": boundary_gold_hash,
        "boundary_gold_freeze_receipt_sha256": freeze_receipt_hash,
        "observed_incorrect_value": observed,
        "checks": checks,
        "unchanged_hashes": {name: sha256(path) for name, path in UNCHANGED.items()},
    }


def expected_manifest(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d1-b-support-lineage-correction-manifest-v1",
        "status": "frozen_not_executed",
        "protocol_sha256": sha256(PROTOCOL),
        "input_artifacts": {
            "support_stage_state_v3_sha256": sha256(STATE_V3),
            "readiness_v14_sha256": sha256(READINESS_V14),
            "boundary_gold_freeze_receipt_sha256": ctx["boundary_gold_freeze_receipt_sha256"],
            "support_packet_construction_manifest_sha256": sha256(CONSTRUCTION_MANIFEST),
            "support_packet_construction_receipt_sha256": sha256(CONSTRUCTION_RECEIPT),
            **ctx["unchanged_hashes"],
        },
        "observed_defect": {
            "field": "boundary_gold_freeze_receipt_sha256",
            "observed_value": ctx["observed_incorrect_value"],
            "expected_value": ctx["boundary_gold_freeze_receipt_sha256"],
            "observed_value_equals_boundary_gold_sha256": True,
        },
        "allowed_change": "create successor state/readiness artifacts with corrected receipt lineage only",
        "provider_call_allowed": False,
        "held_out_access_allowed": False,
    }


def build_state_v4(ctx: dict[str, Any], manifest_hash: str) -> dict[str, Any]:
    state = copy.deepcopy(ctx["state"])
    state["schema_version"] = 4
    state["state_id"] = "phase7.3.3-d1-b-support-stage-state-v4"
    state["support_state"] = "review_packets_frozen_lineage_corrected_independent_review_authorized"
    state["boundary_gold_freeze_receipt_sha256"] = ctx["boundary_gold_freeze_receipt_sha256"]
    state["lineage_correction"] = {
        "correction_protocol_sha256": sha256(PROTOCOL),
        "correction_manifest_sha256": manifest_hash,
        "supersedes_state_v3_for_authorization": True,
        "state_v3_preserved_as_historical_artifact": True,
        "corrected_field": "boundary_gold_freeze_receipt_sha256",
        "previous_incorrect_value": ctx["observed_incorrect_value"],
        "corrected_value": ctx["boundary_gold_freeze_receipt_sha256"],
        "packet_content_changed": False,
    }
    return state


def build_readiness_v15(ctx: dict[str, Any], manifest_hash: str, state_v4_hash: str) -> dict[str, Any]:
    readiness = copy.deepcopy(ctx["readiness"])
    readiness["schema_version"] = 15
    readiness["readiness_id"] = "phase7.3.3-d1-reference-construction-readiness-v15"
    readiness["status"] = "support_review_packets_frozen_lineage_corrected_independent_review_authorized"
    lineage = readiness["artifact_lineage"]
    lineage["readiness_v14_sha256"] = sha256(READINESS_V14)
    lineage["support_lineage_correction_protocol_sha256"] = sha256(PROTOCOL)
    lineage["support_lineage_correction_manifest_sha256"] = manifest_hash
    lineage["support_stage_state_v4_sha256"] = state_v4_hash
    gates = readiness["gates"]
    gates["support_lineage_defect_reproduced"] = True
    gates["support_lineage_correction_completed"] = True
    gates["support_packet_hashes_unchanged_after_lineage_correction"] = True
    readiness["support_review"]["boundary_gold_freeze_receipt_sha256"] = ctx["boundary_gold_freeze_receipt_sha256"]
    readiness["support_review"]["lineage_corrected"] = True
    return readiness


def verify_outputs() -> dict[str, Any]:
    ctx = validate_inputs()
    required = [MANIFEST, STATE_V4, READINESS_V15, RECEIPT]
    if not all(path.exists() for path in required):
        return {"status": "not_executed", "all_outputs_present": False}
    manifest = load(MANIFEST)
    expected = expected_manifest(ctx)
    manifest_ok = manifest == expected
    manifest_hash = sha256(MANIFEST)
    state_expected = build_state_v4(ctx, manifest_hash)
    state_ok = load(STATE_V4) == state_expected
    state_hash = sha256(STATE_V4)
    readiness_expected = build_readiness_v15(ctx, manifest_hash, state_hash)
    readiness_ok = load(READINESS_V15) == readiness_expected
    receipt = load(RECEIPT)
    unchanged_now = {name: sha256(path) for name, path in UNCHANGED.items()}
    unchanged_ok = unchanged_now == ctx["unchanged_hashes"]
    receipt_ok = (
        receipt.get("status") == "completed_support_lineage_correction"
        and receipt.get("manifest_sha256") == manifest_hash
        and receipt.get("support_stage_state_v4_sha256") == state_hash
        and receipt.get("readiness_v15_sha256") == sha256(READINESS_V15)
        and receipt.get("corrected_boundary_gold_freeze_receipt_sha256") == ctx["boundary_gold_freeze_receipt_sha256"]
        and receipt.get("unchanged_artifact_hashes") == ctx["unchanged_hashes"]
        and receipt.get("provider_called") is False
        and receipt.get("held_out_accessed") is False
    )
    return {
        "status": "verified" if all([manifest_ok, state_ok, readiness_ok, unchanged_ok, receipt_ok]) else "failed",
        "manifest_matches": manifest_ok,
        "state_v4_matches": state_ok,
        "readiness_v15_matches": readiness_ok,
        "packet_and_template_hashes_unchanged": unchanged_ok,
        "receipt_matches": receipt_ok,
        "hashes": {
            "manifest_sha256": manifest_hash,
            "support_stage_state_v4_sha256": state_hash,
            "readiness_v15_sha256": sha256(READINESS_V15),
            "receipt_sha256": sha256(RECEIPT),
        },
        "provider_called": False,
        "held_out_accessed": False,
    }


def execute() -> dict[str, Any]:
    ctx = validate_inputs()
    if not MANIFEST.exists():
        raise RuntimeError("freeze the correction manifest before execution")
    expected = expected_manifest(ctx)
    if load(MANIFEST) != expected:
        raise RuntimeError("frozen correction manifest does not match current inputs")
    manifest_hash = sha256(MANIFEST)
    state = build_state_v4(ctx, manifest_hash)
    state_hash = write_once(STATE_V4, state)
    readiness = build_readiness_v15(ctx, manifest_hash, state_hash)
    readiness_hash = write_once(READINESS_V15, readiness)
    receipt = {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d1-b-support-lineage-correction-receipt-v1",
        "status": "completed_support_lineage_correction",
        "protocol_sha256": sha256(PROTOCOL),
        "manifest_sha256": manifest_hash,
        "historical_support_stage_state_v3_sha256": sha256(STATE_V3),
        "historical_readiness_v14_sha256": sha256(READINESS_V14),
        "support_stage_state_v4_sha256": state_hash,
        "readiness_v15_sha256": readiness_hash,
        "previous_incorrect_value": ctx["observed_incorrect_value"],
        "corrected_boundary_gold_freeze_receipt_sha256": ctx["boundary_gold_freeze_receipt_sha256"],
        "unchanged_artifact_hashes": ctx["unchanged_hashes"],
        "packet_content_changed": False,
        "support_review_started": False,
        "support_gold_frozen": False,
        "provider_called": False,
        "held_out_accessed": False,
        "next_authorized_stage": "independent_support_review_execution",
    }
    receipt_hash = write_once(RECEIPT, receipt)
    verified = verify_outputs()
    if verified["status"] != "verified":
        raise RuntimeError(f"lineage correction verification failed: {verified}")
    return {
        "status": "completed_support_lineage_correction",
        "support_stage_state_v4_sha256": state_hash,
        "readiness_v15_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "packet_and_template_hashes_unchanged": True,
        "next_authorized_stage": "independent_support_review_execution",
        "provider_called": False,
        "held_out_accessed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-inputs", action="store_true")
    group.add_argument("--freeze-manifest", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify_inputs:
        ctx = validate_inputs()
        result = {"status": "verified_inputs", "checks": ctx["checks"], "provider_called": False, "held_out_accessed": False}
    elif args.freeze_manifest:
        ctx = validate_inputs()
        result = {
            "status": "support_lineage_correction_manifest_frozen_not_executed",
            "manifest_sha256": write_once(MANIFEST, expected_manifest(ctx)),
            "provider_called": False,
            "held_out_accessed": False,
        }
    elif args.execute:
        result = execute()
    else:
        result = verify_outputs()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") not in {"failed", "not_executed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
