#!/usr/bin/env python3
"""Audit preregistered Confirmatory sample-size and power-gate compliance."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

EXPLORATORY_POWER = REPORTS / "phase7_3_3_d_multi_claim_successor_power_gate_report_frame_v2.json"
EXPLORATORY_SIZE = REPORTS / "phase7_3_3_d_multi_claim_successor_sample_size_freeze_frame_v2.json"
PREREG = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_preregistration_v1.json"
INVENTORY = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_source_inventory_v1.json"
ELIGIBILITY = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_eligibility_audit_v1.json"
OVERLAP = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_overlap_audit_v1.json"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_worklist_v1.json"
OPEN_GATE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_report_v1.json"
DATASET = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_dataset_v1.json"
STRUCT_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_report_v1.json"
REALIZED_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_report_v1.json"
ANALYSIS_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_report_v1.json"
ANALYSIS_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_receipt_v1.json"
STATE_109 = PATTERN / "phase7_3_3_d_support_stage_state_v109.json"
READY_120 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v120.json"

POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_policy_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_manifest_v1.json"
REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_report_v1.json"
AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_audit_v1.jsonl"
RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_receipt_v1.json"
STATE_110 = PATTERN / "phase7_3_3_d_support_stage_state_v110.json"
READY_121 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v121.json"

CUR = "evaluate_confirmatory_power_compliance_gate_v1"
NEXT = "run_confirmatory_final_audit_v1"
FAIL = "blocked_confirmatory_power_compliance_v1_authoritative_negative"


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def once(path: Path, value: Any) -> str:
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("immutable_artifact_mismatch:" + rel(path))
        return hb(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hb(body)


def append_single_event(path: Path, event: dict[str, Any]) -> str:
    body = (json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("append_only_audit_mismatch:" + rel(path))
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(body)
    return hb(body)


def policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d-multi-claim-successor-confirmatory-power-compliance-v1",
        "status": "audit_policy_inheriting_pre_result_sample_size_freeze",
        "authoritative_sample_size_source": rel(EXPLORATORY_SIZE),
        "required_confirmatory_clusters": 40,
        "preregistered_clusters": 40,
        "required_alpha_one_sided": 0.05,
        "compliance_checks": [
            "authoritative_power_lineage",
            "inventory_sufficient_before_opening",
            "selected_exactly_40_before_opening",
            "analyzed_exactly_40_without_drop",
            "no_post_result_replanning",
            "no_post_open_replacement",
            "unselected_inventory_remains_closed",
        ],
        "observed_power_estimation_required": False,
        "post_result_sample_size_change_allowed": False,
        "provider_calls": 0,
        "runtime_integration_authorized": False,
        "next_authorized_stage_on_pass": NEXT,
        "next_authorized_stage_on_failure": FAIL,
    }


def compliance_checks() -> dict[str, bool]:
    prereg, analysis = load(PREREG), load(ANALYSIS_REPORT)
    return {
        "exploratory_power_status_authoritative": load(EXPLORATORY_POWER)["status"] == "power_identified_but_confirmatory_inventory_shortfall_authoritative",
        "authoritative_required_clusters_40": load(EXPLORATORY_SIZE)["sample_size_clusters"] == load(EXPLORATORY_POWER)["required_confirmatory_clusters"] == 40,
        "opening_gate_used_new_inventory": load(OPEN_GATE)["confirmatory_opening_authorized"] is True and load(OPEN_GATE)["selected_count"] == 40,
        "metadata_inventory_80": load(INVENTORY)["inventory_count"] == 80,
        "eligible_inventory_sufficient": load(ELIGIBILITY)["eligible_count"] >= 40,
        "zero_overlap_before_selection": load(OVERLAP)["status"] == "PASS" and load(OVERLAP)["candidate_hash_overlap_count"] == load(OVERLAP)["evidence_hash_overlap_count"] == load(OVERLAP)["source_identity_overlap_count"] == 0,
        "worklist_selected_40": load(WORKLIST)["selected_count"] == len(load(WORKLIST)["items"]) == 40,
        "preregistered_clusters_40": prereg["sample_size_candidates"] == 40,
        "preregistered_alpha": prereg["alpha_one_sided"] == 0.05,
        "dataset_opened_selected_40": load(DATASET)["case_count"] == len(load(DATASET)["cases"]) == 40,
        "structural_gate_passed": load(STRUCT_REPORT)["structural_estimand_identifiable"] is True,
        "realized_gate_passed": load(REALIZED_REPORT)["realized_representation_identifiable"] is True,
        "analyzed_40_no_drop": analysis["case_count"] == analysis["missingness_and_failures"]["paired_cases_scored"] == 40 and analysis["missingness_and_failures"]["paired_cases_dropped"] == 0,
        "randomization_protocol_unchanged": analysis["paired_primary_effect"]["randomization_replicates"] == prereg["primary_test"]["replicates"] and analysis["paired_primary_effect"]["randomization_seed"] == prereg["primary_test"]["seed"],
        "no_result_dependent_replanning": prereg["no_result_dependent_replanning"] is True and load(STATE_109)["multi_claim_successor_confirmatory_no_result_replanning"] is True,
        "no_post_open_replacement": [case["candidate_id"] for case in load(DATASET)["cases"]] == [item["candidate_id"] for item in load(WORKLIST)["items"]],
        "unselected_inventory_closed": load(STATE_109)["multi_claim_successor_confirmatory_unselected_content_opened"] is False and load(READY_120)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
        "analysis_lineage": load(ANALYSIS_RECEIPT)["analysis_report_sha256"] == sha(ANALYSIS_REPORT) and load(ANALYSIS_RECEIPT)["state_sha256"] == sha(STATE_109),
        "runtime_off": load(STATE_109)["runtime_integration_authorized"] is False and load(READY_120)["runtime_integration_authorized"] is False,
    }


def fixtures() -> dict[str, Any]:
    checks = compliance_checks()
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks.items()]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-power-compliance-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def manifest() -> dict[str, Any]:
    inputs = [EXPLORATORY_POWER, EXPLORATORY_SIZE, PREREG, INVENTORY, ELIGIBILITY, OVERLAP, WORKLIST, OPEN_GATE, DATASET, STRUCT_REPORT, REALIZED_REPORT, ANALYSIS_REPORT, ANALYSIS_RECEIPT, STATE_109, READY_120]
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-power-compliance-manifest-v1",
        "status": "frozen_before_compliance_gate_evaluation",
        "adapter_sha256": sha(SELF),
        "policy_sha256": sha(POLICY),
        "fixtures_sha256": sha(FIXTURES),
        "frozen_inputs": {rel(path): sha(path) for path in inputs},
        "provider_calls": 0,
        "post_result_replanning": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }


def preflight() -> dict[str, Any]:
    inputs = [EXPLORATORY_POWER, EXPLORATORY_SIZE, PREREG, INVENTORY, ELIGIBILITY, OVERLAP, WORKLIST, OPEN_GATE, DATASET, STRUCT_REPORT, REALIZED_REPORT, ANALYSIS_REPORT, ANALYSIS_RECEIPT, STATE_109, READY_120]
    checks = {"exists:" + rel(path): path.exists() for path in inputs}
    if all(checks.values()):
        state, readiness = load(STATE_109), load(READY_120)
        checks.update({
            "state_gate": state["next_authorized_stage"] == CUR,
            "readiness_gate": readiness["next_authorized_stage"] == CUR,
            "confirmatory_analysis_complete": state["multi_claim_successor_confirmatory_paired_analysis_completed"] is True,
            "unselected_closed": state["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    outputs = [POLICY, FIXTURES, MANIFEST, REPORT, AUDIT, RECEIPT, STATE_110, READY_121]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def evaluate() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    policy_hash = once(POLICY, policy())
    fixture_hash = once(FIXTURES, fixtures())
    manifest_hash = once(MANIFEST, manifest())
    checks = compliance_checks()
    passed = all(checks.values())
    next_stage = NEXT if passed else FAIL
    analysis = load(ANALYSIS_REPORT)
    report_hash = once(REPORT, {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-confirmatory-power-compliance-report-v1",
        "status": "PASS_power_and_sample_size_compliance" if passed else "AUTHORITATIVE_NEGATIVE_power_or_sample_size_noncompliance",
        "manifest_sha256": manifest_hash,
        "policy_sha256": policy_hash,
        "fixtures_sha256": fixture_hash,
        "checks": checks,
        "failed_checks": [key for key, value in checks.items() if not value],
        "authoritative_required_clusters": 40,
        "preregistered_clusters": load(PREREG)["sample_size_candidates"],
        "selected_clusters": load(WORKLIST)["selected_count"],
        "analyzed_clusters": analysis["case_count"],
        "paired_cases_dropped": analysis["missingness_and_failures"]["paired_cases_dropped"],
        "post_result_replanning": False,
        "post_open_replacement": False,
        "observed_power_computed": False,
        "confirmatory_success": analysis["confirmatory_success"],
        "provider_calls": 0,
        "confirmatory_dataset_opened": True,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    audit_hash = append_single_event(AUDIT, {"event_id": "confirmatory-power-compliance-v1-evaluated", "event_type": "authoritative_power_sample_size_compliance_gate", "manifest_sha256": manifest_hash, "report_sha256": report_hash, "gate_passed": passed, "provider_calls": 0})
    state, readiness = copy.deepcopy(load(STATE_109)), copy.deepcopy(load(READY_120))
    lineage = {
        "multi_claim_successor_confirmatory_power_compliance_policy_v1_sha256": policy_hash,
        "multi_claim_successor_confirmatory_power_compliance_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_power_compliance_report_v1_sha256": report_hash,
        "multi_claim_successor_confirmatory_power_compliance_audit_v1_sha256": audit_hash,
    }
    update = {
        "status": "confirmatory_power_compliance_v1_passed_final_audit_authorized" if passed else "confirmatory_power_compliance_v1_authoritative_negative",
        "next_authorized_stage": next_stage,
        "multi_claim_successor_confirmatory_power_compliance_evaluated": True,
        "multi_claim_successor_confirmatory_power_compliance_passed": passed,
        "multi_claim_successor_confirmatory_authoritative_clusters": 40,
        "multi_claim_successor_confirmatory_analyzed_clusters": analysis["case_count"],
        "multi_claim_successor_confirmatory_post_result_replanning": False,
        "confirmatory_dataset_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 110, "state_id": "phase7.3.3-d-support-stage-state-v110"})
    readiness.update({"schema_version": 121, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v121"})
    state_hash = once(STATE_110, state)
    readiness["artifact_lineage"]["support_stage_state_v110_sha256"] = state_hash
    readiness_hash = once(READY_121, readiness)
    receipt_hash = once(RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-power-compliance-receipt-v1",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT",
        "manifest_sha256": manifest_hash,
        "report_sha256": report_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "required_clusters": 40,
        "analyzed_clusters": analysis["case_count"],
        "post_result_replanning": False,
        "same_version_retry_allowed": False,
        "provider_calls": 0,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    return {"status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT", "required_clusters": 40, "analyzed_clusters": analysis["case_count"], "post_result_replanning": False, "report_sha256": report_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": next_stage}


def verify() -> dict[str, Any]:
    paths = [POLICY, FIXTURES, MANIFEST, REPORT, AUDIT, RECEIPT, STATE_110, READY_121]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        report, receipt = load(REPORT), load(RECEIPT)
        checks.update({
            "policy_replay": load(POLICY) == policy(),
            "fixtures_replay": load(FIXTURES) == fixtures(),
            "manifest_replay": load(MANIFEST) == manifest(),
            "checks_replay": report["checks"] == compliance_checks(),
            "gate_pass": not report["failed_checks"] and report["status"] == "PASS_power_and_sample_size_compliance",
            "receipt_lineage": receipt["report_sha256"] == sha(REPORT) and receipt["state_sha256"] == sha(STATE_110) and receipt["readiness_sha256"] == sha(READY_121),
            "state_gate": load(STATE_110)["next_authorized_stage"] == load(READY_121)["next_authorized_stage"] == NEXT,
            "no_replanning": report["post_result_replanning"] is False and receipt["post_result_replanning"] is False,
            "unselected_closed": load(STATE_110)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_110)["runtime_integration_authorized"] is False and load(READY_121)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_110)["next_authorized_stage"] if STATE_110.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--evaluate", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    outcome = preflight() if args.preflight else evaluate() if args.evaluate else verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 2 if outcome.get("status") == "AUTHORITATIVE_NEGATIVE_RESULT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
