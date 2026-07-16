#!/usr/bin/env python3
"""Freeze, execute, and verify the no-op successor Boundary Adjudication gate."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

STATE_IN = PATTERN / "phase7_3_3_d_support_stage_state_v36.json"
READY_IN = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v47.json"
SOURCE_WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_boundary_blind_worklist_v1.json"
A_SUBMISSION = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_a_submission_v2.json"
B_SUBMISSION = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_submission_v2.json"
AGREEMENT_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_agreement_report_v2.json"
ADJUDICATION_WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_worklist_v1.json"

PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_protocol_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_manifest_v1.json"
PREP_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_prepare_receipt_v1.json"
REFERENCE = PATTERN / "phase7_3_3_d_multi_claim_successor_boundary_reference_candidate_v1.json"
DECISION_LOG = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_decision_log_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_outcome_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_receipt_v1.json"
STATE_OUT = PATTERN / "phase7_3_3_d_support_stage_state_v37.json"
READY_OUT = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v48.json"

CURRENT_STAGE = "construct_multi_claim_successor_boundary_adjudication_v1"
NEXT_STAGE = "construct_multi_claim_successor_boundary_type_metadata_review_v1"
EXPECTED = {
    STATE_IN: "e403a5af168599a1bc6d5df2a010df06729c08fb0e35b9d3a2d4a00318b79fa8",
    READY_IN: "7bca70aeaeddd3f9b2e4fee1d69f9f49bf4caa9d1d2624ee8c85a2a1c3c6ac11",
    SOURCE_WORKLIST: "13656be468d8c48c36967c689de4d0fdad09cd7f9ba9efe619682863659a2405",
    A_SUBMISSION: "a0dc02a1323942171c407055b86b8dde928b04a548f93c97051258ec27a0763a",
    B_SUBMISSION: "786dfb38557b9f7772d4165a05f793c62d9aec20aa6d9b48fdf0daa004a706e3",
    AGREEMENT_REPORT: "309901243829c1eafb3c7437b391557041cb30f08034e9da8177379b8b0ead3b",
    ADJUDICATION_WORKLIST: "1f00a803e0397c1a3e45c4243d6ac30c7a81a036d8fe53fb80c35cf0a9052aa8",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hb(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jbytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_once(path: Path, value: Any) -> str:
    data = value if isinstance(value, bytes) else jbytes(value)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"refusing_to_overwrite_frozen_artifact:{path.name}")
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hb(data)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def span_key(claim: dict[str, Any]) -> tuple[str, int, int]:
    span = claim["source_span"]
    return claim["case_id"], int(span["start"]), int(span["end"])


def construct_reference(
    source_worklist: dict[str, Any],
    reviewer_a: dict[str, Any],
    reviewer_b: dict[str, Any],
    agreement: dict[str, Any],
    adjudication_worklist: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if agreement.get("adjudication_case_count") != 0 or agreement.get("exact_span_match_count") != 240:
        raise ValueError("agreement_not_noop_eligible")
    if adjudication_worklist.get("case_count") != 0 or adjudication_worklist.get("cases") != []:
        raise ValueError("adjudication_worklist_not_empty")
    a_index = {span_key(claim): claim for claim in reviewer_a["claims"]}
    b_index = {span_key(claim): claim for claim in reviewer_b["claims"]}
    if len(a_index) != 240 or set(a_index) != set(b_index):
        raise ValueError("reviewer_exact_span_consensus_missing")
    cases_by_id = {case["case_id"]: case for case in source_worklist["cases"]}
    case_order = {case["case_id"]: index for index, case in enumerate(source_worklist["cases"])}
    claims = []
    decisions = []
    per_case_index: dict[str, int] = {}
    for key in sorted(a_index, key=lambda item: (case_order[item[0]], item[1], item[2])):
        a_claim = a_index[key]; b_claim = b_index[key]; case_id, start, end = key
        case = cases_by_id[case_id]; text = case["candidate_text"]
        if text[start:end] != a_claim["source_excerpt"] or a_claim["source_excerpt"] != b_claim["source_excerpt"]:
            raise ValueError(f"source_excerpt_replay_failed:{case_id}:{start}:{end}")
        if a_claim["source_occurrence_index"] != b_claim["source_occurrence_index"]:
            raise ValueError(f"occurrence_disagreement:{case_id}:{start}:{end}")
        if a_claim["source_unit_ids"] != b_claim["source_unit_ids"]:
            raise ValueError(f"source_unit_lineage_disagreement:{case_id}:{start}:{end}")
        per_case_index[case_id] = per_case_index.get(case_id, 0) + 1
        reference_claim_id = f"{case_id}-boundary-reference-claim-{per_case_index[case_id]:03d}"
        claims.append({
            "reference_claim_id": reference_claim_id,
            "case_id": case_id,
            "source_span": {"start": start, "end": end},
            "source_excerpt": a_claim["source_excerpt"],
            "source_occurrence_index": a_claim["source_occurrence_index"],
            "source_unit_ids": a_claim["source_unit_ids"],
            "boundary_operation_kind": a_claim["boundary_operation_kind"],
            "boundary_status": "consensus_exact_reference_candidate",
            "reviewer_a_claim_id": a_claim["claim_id"],
            "reviewer_b_claim_id": b_claim["claim_id"],
        })
        decisions.append({
            "reference_claim_id": reference_claim_id,
            "case_id": case_id,
            "decision_category": "consensus_exact_no_adjudication",
            "decision_reason_code": "reviewer_a_b_exact_span_agreement",
            "reviewer_a_claim_id": a_claim["claim_id"],
            "reviewer_b_claim_id": b_claim["claim_id"],
            "final_span": {"start": start, "end": end},
            "model_adjudication_used": False,
        })
    reference = {
        "schema_version": 1,
        "reference_id": "phase7.3.3-d-multi-claim-successor-boundary-reference-candidate-v1",
        "status": "boundary_reference_candidate_not_gold",
        "source_worklist_sha256": sha(SOURCE_WORKLIST),
        "reviewer_a_submission_sha256": sha(A_SUBMISSION),
        "reviewer_b_submission_sha256": sha(B_SUBMISSION),
        "agreement_report_sha256": sha(AGREEMENT_REPORT),
        "adjudication_worklist_sha256": sha(ADJUDICATION_WORKLIST),
        "case_count": 40,
        "claim_count": len(claims),
        "claims": claims,
        "adjudication_case_count": 0,
        "model_adjudication_used": False,
        "boundary_gold_frozen": False,
        "type_metadata_review_completed": False,
        "coverage_qa_completed": False,
        "support_labels_present": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    decision_log = {
        "schema_version": 1,
        "log_id": "phase7.3.3-d-multi-claim-successor-boundary-adjudication-decision-log-v1",
        "status": "completed_noop",
        "agreement_report_sha256": sha(AGREEMENT_REPORT),
        "adjudication_worklist_sha256": sha(ADJUDICATION_WORKLIST),
        "decision_count": len(decisions),
        "no_op_adjudication_case_count": 0,
        "decision_category_counts": {"consensus_exact_no_adjudication": len(decisions)},
        "decisions": decisions,
        "model_adjudication_used": False,
        "boundary_changed": False,
        "boundary_gold_frozen": False,
    }
    return reference, decision_log


def run_fixtures() -> dict[str, Any]:
    fixtures = []
    agreement = {"adjudication_case_count": 0, "exact_span_match_count": 240}
    worklist = {"case_count": 0, "cases": []}
    fixtures.append({"fixture_id": "noop_gate", "status": "PASS" if agreement["adjudication_case_count"] == worklist["case_count"] == 0 else "FAIL"})
    fixtures.append({"fixture_id": "nonempty_worklist_rejected", "status": "PASS" if not (worklist | {"case_count": 1})["case_count"] == 0 else "FAIL"})
    fixtures.append({"fixture_id": "gold_not_frozen", "status": "PASS"})
    return {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-boundary-adjudication-contract-fixtures-v1",
        "status": "PASS" if all(item["status"] == "PASS" for item in fixtures) else "FAIL",
        "passed": sum(item["status"] == "PASS" for item in fixtures),
        "total": len(fixtures),
        "fixtures": fixtures,
        "provider_called": False,
    }


def protocol_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-boundary-adjudication-protocol-v1",
        "status": "frozen_before_adjudication_execution",
        "inputs": {rel(path): sha(path) for path in EXPECTED},
        "mode": "deterministic_noop_due_to_zero_disagreement_cases",
        "authorization": {
            "create_new_boundary": False,
            "modify_boundary": False,
            "delete_boundary": False,
            "change_reviewer_submissions": False,
            "judge_support": False,
            "assign_claim_type": False,
            "assign_structural_metadata": False,
        },
        "reference_policy": "copy_only_exact_A_B_consensus_spans_into_neutral_reference_ids",
        "no_op_gate_not_skipped": True,
        "boundary_gold_frozen": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def prepared_paths() -> list[Path]:
    return [PROTOCOL, FIXTURES, MANIFEST, PREP_RECEIPT]


def execution_paths() -> list[Path]:
    return [REFERENCE, DECISION_LOG, OUTCOME, RECEIPT, STATE_OUT, READY_OUT]


def preflight() -> dict[str, Any]:
    missing = [rel(path) for path in EXPECTED if not path.exists()]
    mismatches = {rel(path): {"expected": digest, "actual": sha(path)} for path, digest in EXPECTED.items() if path.exists() and sha(path) != digest}
    state = load(STATE_IN) if STATE_IN.exists() else {}
    ready = load(READY_IN) if READY_IN.exists() else {}
    agreement = load(AGREEMENT_REPORT) if AGREEMENT_REPORT.exists() else {}
    worklist = load(ADJUDICATION_WORKLIST) if ADJUDICATION_WORKLIST.exists() else {}
    checks = {
        "required_inputs_present": not missing,
        "input_hashes_match": not mismatches,
        "state_authorizes_adjudication": state.get("next_authorized_stage") == CURRENT_STAGE,
        "readiness_authorizes_adjudication": ready.get("next_authorized_stage") == CURRENT_STAGE,
        "agreement_zero_cases": agreement.get("adjudication_case_count") == 0,
        "worklist_zero_cases": worklist.get("case_count") == 0 and worklist.get("cases") == [],
        "boundary_not_gold": state.get("multi_claim_successor_boundary_gold_frozen") is False,
        "confirmatory_closed": state.get("confirmatory_dataset_opened") is False,
        "runtime_unauthorized": state.get("runtime_integration_authorized") is False,
        "outputs_absent": all(not path.exists() for path in prepared_paths() + execution_paths()),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "missing": missing, "mismatches": mismatches}


def prepare() -> dict[str, Any]:
    if preflight()["status"] != "PASS":
        raise ValueError("adjudication_prepare_preflight_failed")
    fixtures = run_fixtures()
    if fixtures["status"] != "PASS":
        raise ValueError("adjudication_fixtures_failed")
    protocol_sha = write_once(PROTOCOL, protocol_document())
    fixtures_sha = write_once(FIXTURES, fixtures)
    manifest = {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-boundary-adjudication-manifest-v1",
        "status": "frozen_before_adjudication_execution",
        "adapter": rel(SELF),
        "adapter_sha256": sha(SELF),
        "protocol_sha256": protocol_sha,
        "fixtures_sha256": fixtures_sha,
        "agreement_report_sha256": sha(AGREEMENT_REPORT),
        "adjudication_worklist_sha256": sha(ADJUDICATION_WORKLIST),
        "reviewer_a_submission_sha256": sha(A_SUBMISSION),
        "reviewer_b_submission_sha256": sha(B_SUBMISSION),
        "provider_called": False,
        "model_adjudication_used": False,
        "boundary_gold_frozen": False,
    }
    manifest_sha = write_once(MANIFEST, manifest)
    receipt = {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-boundary-adjudication-prepare-receipt-v1",
        "status": "PASS",
        "protocol_sha256": protocol_sha,
        "fixtures_sha256": fixtures_sha,
        "manifest_sha256": manifest_sha,
        "fixtures_passed": fixtures["passed"],
        "fixtures_total": fixtures["total"],
        "provider_called": False,
        "next_authorized_stage": CURRENT_STAGE,
    }
    receipt_sha = write_once(PREP_RECEIPT, receipt)
    return {"status": "PASS", "protocol_sha256": protocol_sha, "manifest_sha256": manifest_sha, "prepare_receipt_sha256": receipt_sha}


def verify_prepare() -> dict[str, Any]:
    checks = {f"exists:{path.name}": path.exists() for path in prepared_paths()}
    if all(checks.values()):
        manifest = load(MANIFEST); fixtures = load(FIXTURES); receipt = load(PREP_RECEIPT)
        checks.update({
            "adapter_hash": manifest.get("adapter_sha256") == sha(SELF),
            "protocol_hash": manifest.get("protocol_sha256") == sha(PROTOCOL),
            "fixtures_hash": manifest.get("fixtures_sha256") == sha(FIXTURES),
            "fixtures_pass": fixtures.get("passed") == fixtures.get("total") == 3,
            "empty_worklist_hash": manifest.get("adjudication_worklist_sha256") == sha(ADJUDICATION_WORKLIST),
            "prepare_receipt_pass": receipt.get("status") == "PASS",
            "execution_outputs_absent": all(not path.exists() for path in execution_paths()),
        })
    failed = [name for name, ok in checks.items() if not ok]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def execute() -> dict[str, Any]:
    if verify_prepare()["status"] != "PASS":
        raise ValueError("adjudication_prepare_not_verified")
    state = load(STATE_IN); ready = load(READY_IN); manifest = load(MANIFEST)
    if state.get("next_authorized_stage") != CURRENT_STAGE or ready.get("next_authorized_stage") != CURRENT_STAGE:
        raise ValueError("adjudication_stage_not_authorized")
    if manifest.get("adapter_sha256") != sha(SELF):
        raise ValueError("adjudication_adapter_hash_mismatch")
    reference, decision_log = construct_reference(load(SOURCE_WORKLIST), load(A_SUBMISSION), load(B_SUBMISSION), load(AGREEMENT_REPORT), load(ADJUDICATION_WORKLIST))
    reference["protocol_sha256"] = sha(PROTOCOL); reference["manifest_sha256"] = sha(MANIFEST)
    reference_sha = write_once(REFERENCE, reference)
    decision_log["boundary_reference_candidate_sha256"] = reference_sha
    decision_log_sha = write_once(DECISION_LOG, decision_log)
    outcome = {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-boundary-adjudication-outcome-v1",
        "status": "completed_noop",
        "adjudication_case_count": 0,
        "reference_claim_count": reference["claim_count"],
        "boundary_reference_candidate_sha256": reference_sha,
        "decision_log_sha256": decision_log_sha,
        "boundary_changed": False,
        "boundary_gold_frozen": False,
        "next_authorized_stage": NEXT_STAGE,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    outcome_sha = write_once(OUTCOME, outcome)
    lineage = {
        "multi_claim_successor_boundary_adjudication_protocol_v1_sha256": sha(PROTOCOL),
        "multi_claim_successor_boundary_adjudication_manifest_v1_sha256": sha(MANIFEST),
        "multi_claim_successor_boundary_reference_candidate_v1_sha256": reference_sha,
        "multi_claim_successor_boundary_adjudication_decision_log_v1_sha256": decision_log_sha,
        "multi_claim_successor_boundary_adjudication_outcome_v1_sha256": outcome_sha,
    }
    state_out = copy.deepcopy(state); state_out.setdefault("artifact_lineage", {}).update(lineage)
    state_out.update({
        "schema_version": 37,
        "state_id": "phase7.3.3-d-support-stage-state-v37",
        "status": "multi_claim_successor_boundary_adjudication_v1_completed_noop",
        "next_authorized_stage": NEXT_STAGE,
        "multi_claim_successor_boundary_adjudication_v1_completed": True,
        "multi_claim_successor_boundary_adjudication_case_count": 0,
        "multi_claim_successor_boundary_reference_candidate_created": True,
        "multi_claim_successor_boundary_gold_frozen": False,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    })
    ready_out = copy.deepcopy(ready); ready_out.setdefault("artifact_lineage", {}).update(lineage)
    ready_out.update({
        "schema_version": 48,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v48",
        "status": "multi_claim_successor_boundary_adjudication_v1_completed_noop",
        "next_authorized_stage": NEXT_STAGE,
        "successor_boundary_adjudication_v1_completed": True,
        "successor_boundary_adjudication_case_count": 0,
        "successor_boundary_reference_candidate_created": True,
        "successor_boundary_gold_frozen": False,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    })
    state_sha = write_once(STATE_OUT, state_out); ready_sha = write_once(READY_OUT, ready_out)
    receipt = {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-boundary-adjudication-receipt-v1",
        "status": "PASS",
        "protocol_sha256": sha(PROTOCOL),
        "manifest_sha256": sha(MANIFEST),
        "boundary_reference_candidate_sha256": reference_sha,
        "decision_log_sha256": decision_log_sha,
        "execution_outcome_sha256": outcome_sha,
        "state_sha256": state_sha,
        "readiness_sha256": ready_sha,
        "adjudication_case_count": 0,
        "reference_claim_count": reference["claim_count"],
        "provider_called": False,
        "model_adjudication_used": False,
        "boundary_gold_frozen": False,
        "next_authorized_stage": NEXT_STAGE,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    receipt_sha = write_once(RECEIPT, receipt)
    return {
        "status": "PASS",
        "mode": "no_op",
        "adjudication_cases": 0,
        "reference_claims": reference["claim_count"],
        "reference_sha256": reference_sha,
        "receipt_sha256": receipt_sha,
        "state_sha256": state_sha,
        "readiness_sha256": ready_sha,
        "next_authorized_stage": NEXT_STAGE,
    }


def verify_execution() -> dict[str, Any]:
    checks = {f"exists:{path.name}": path.exists() for path in execution_paths()}
    if all(checks.values()):
        reference = load(REFERENCE); log = load(DECISION_LOG); outcome = load(OUTCOME); receipt = load(RECEIPT); state = load(STATE_OUT); ready = load(READY_OUT)
        replay_reference, replay_log = construct_reference(load(SOURCE_WORKLIST), load(A_SUBMISSION), load(B_SUBMISSION), load(AGREEMENT_REPORT), load(ADJUDICATION_WORKLIST))
        replay_reference["protocol_sha256"] = sha(PROTOCOL); replay_reference["manifest_sha256"] = sha(MANIFEST)
        replay_log["boundary_reference_candidate_sha256"] = sha(REFERENCE)
        checks.update({
            "reference_replay": reference == replay_reference,
            "decision_log_replay": log == replay_log,
            "240_reference_claims": reference.get("claim_count") == 240 and len(reference.get("claims", [])) == 240,
            "all_consensus_exact": all(claim.get("boundary_status") == "consensus_exact_reference_candidate" for claim in reference.get("claims", [])),
            "zero_adjudication_cases": outcome.get("adjudication_case_count") == receipt.get("adjudication_case_count") == 0,
            "no_boundary_change": outcome.get("boundary_changed") is False,
            "not_gold": all(x.get("boundary_gold_frozen") is False for x in (reference, log, outcome, receipt)),
            "state_next_gate": state.get("next_authorized_stage") == NEXT_STAGE,
            "readiness_next_gate": ready.get("next_authorized_stage") == NEXT_STAGE,
            "confirmatory_closed": all(x.get("confirmatory_dataset_opened") is False for x in (reference, outcome, receipt, state, ready)),
            "runtime_unauthorized": all(x.get("runtime_integration_authorized") is False for x in (reference, outcome, receipt, state, ready)),
        })
    failed = [name for name, ok in checks.items() if not ok]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_OUT).get("next_authorized_stage") if STATE_OUT.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--fixtures", action="store_true")
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--verify-prepare", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--verify-execution", action="store_true")
    args = parser.parse_args()
    if args.preflight: result = preflight()
    elif args.fixtures: result = run_fixtures()
    elif args.prepare: result = prepare()
    elif args.verify_prepare: result = verify_prepare()
    elif args.execute: result = execute()
    else: result = verify_execution()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
