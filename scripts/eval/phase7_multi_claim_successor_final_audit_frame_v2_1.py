#!/usr/bin/env python3
"""Final Audit v2.1 successor with recursive policy-occurrence scanning."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

BASE_ADAPTER = ROOT / "scripts/eval/phase7_multi_claim_successor_pilot_gates_frame_v2.py"
GOLD = D / "phase7_3_3_d_multi_claim_successor_support_gold_frame_v2.json"
GSEAL = R / "phase7_3_3_d_multi_claim_successor_support_gold_seal_frame_v2.json"
STRUCT = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_report_frame_v2.json"
STRUCT_REC = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_receipt_frame_v2.json"
CSUB = D / "phase7_3_3_d_multi_claim_successor_candidate_arm_submission_frame_v2.json"
ASUB = D / "phase7_3_3_d_multi_claim_successor_atomic_arm_submission_frame_v2.json"
PRESULT = R / "phase7_3_3_d_multi_claim_successor_pilot_execution_result_frame_v2.json"
PILOT_REC = R / "phase7_3_3_d_multi_claim_successor_pilot_execution_receipt_frame_v2.json"
RREPORT = R / "phase7_3_3_d_multi_claim_successor_realized_identifiability_report_frame_v2.json"
RREC = R / "phase7_3_3_d_multi_claim_successor_realized_identifiability_receipt_frame_v2.json"
AREPORT = R / "phase7_3_3_d_multi_claim_successor_paired_analysis_report_frame_v2.json"
AREC = R / "phase7_3_3_d_multi_claim_successor_paired_analysis_receipt_frame_v2.json"
PREPORT = R / "phase7_3_3_d_multi_claim_successor_power_gate_report_frame_v2.json"
PSIZE = R / "phase7_3_3_d_multi_claim_successor_sample_size_freeze_frame_v2.json"
POWER_REC = R / "phase7_3_3_d_multi_claim_successor_power_gate_receipt_frame_v2.json"
RMAN = R / "phase7_3_3_d_multi_claim_successor_realized_identifiability_manifest_frame_v2.json"
AMAN = R / "phase7_3_3_d_multi_claim_successor_paired_analysis_manifest_frame_v2.json"
PMAN = R / "phase7_3_3_d_multi_claim_successor_power_manifest_frame_v2.json"
SI = D / "phase7_3_3_d_support_stage_state_v98.json"
RI = R / "phase7_3_3_d1_reference_construction_readiness_v109.json"

IMPL = R / "phase7_3_3_d_multi_claim_successor_final_audit_v2_preexecution_implementation_failure.json"
IMPL_REC = R / "phase7_3_3_d_multi_claim_successor_final_audit_v2_preexecution_implementation_failure_receipt.json"
MAN = R / "phase7_3_3_d_multi_claim_successor_final_audit_manifest_frame_v2_1.json"
REPORT = R / "phase7_3_3_d_multi_claim_successor_final_audit_report_frame_v2_1.json"
REC = R / "phase7_3_3_d_multi_claim_successor_final_audit_receipt_frame_v2_1.json"
SO = D / "phase7_3_3_d_support_stage_state_v99.json"
RO = R / "phase7_3_3_d1_reference_construction_readiness_v110.json"

CUR = "run_multi_claim_successor_final_audit_frame_v2"
NEXT = "design_sealed_confirmatory_inventory_successor_after_authoritative_shortfall"
BASE_HASH = "5967ee2f43ecd6855ec89c6e6166a3de29b4c6630fe03f8f2619a2d37a3b5b9b"
SCOPED = [GOLD, GSEAL, STRUCT, STRUCT_REC, CSUB, ASUB, PRESULT, PILOT_REC, RREPORT, RREC, AREPORT, AREC, PREPORT, PSIZE, POWER_REC, RMAN, AMAN, PMAN, SI, RI]


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def once(path: Path, value) -> str:
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("immutable_artifact_mismatch:" + rel(path))
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hb(body)


def occurrences(value, predicate, path="$"):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if predicate(key, child):
                found.append(child_path)
            found.extend(occurrences(child, predicate, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(occurrences(child, predicate, f"{path}[{index}]"))
    return found


def policy_scan():
    confirmatory_true = {}
    runtime_true = {}
    nonnull_cost = {}
    for path in SCOPED:
        document = load(path)
        c = occurrences(document, lambda key, value: key in {"confirmatory_dataset_opened", "confirmatory_opening_authorized"} and value is True)
        r = occurrences(document, lambda key, value: "runtime" in key and (key.endswith("authorized") or key.endswith("integration_authorized")) and value is True)
        u = occurrences(document, lambda key, value: key in {"cost_usd", "usd_cost"} and value is not None)
        if c:
            confirmatory_true[rel(path)] = c
        if r:
            runtime_true[rel(path)] = r
        if u:
            nonnull_cost[rel(path)] = u
    return {"scoped_json_file_count": len(SCOPED), "confirmatory_true_occurrences": confirmatory_true, "runtime_authorized_true_occurrences": runtime_true, "nonnull_usd_cost_occurrences": nonnull_cost}


def implementation_failure():
    realized = load(RREPORT)
    return {
        "schema_version": "2.1",
        "failure_id": "phase7.3.3-d-multi-claim-successor-final-audit-v2-preexecution-implementation-failure",
        "status": "frozen_preexecution_implementation_failure",
        "failure_level": "level_0_audit_adapter_implementation",
        "failure_subtype": "missing_policy_field_treated_as_not_false",
        "frozen_base_adapter_sha256": sha(BASE_ADAPTER),
        "trigger": "base final audit used document.get(field) is False for every scoped artifact",
        "witness_artifact": rel(RREPORT),
        "witness_field": "confirmatory_dataset_opened",
        "witness_field_present": "confirmatory_dataset_opened" in realized,
        "base_expression_would_pass": realized.get("confirmatory_dataset_opened") is False,
        "provider_called": False,
        "final_audit_v2_manifest_created": False,
        "state_mutation_performed": False,
        "scientific_outputs_mutated": False,
        "controlled_successor_change": "replace presence-sensitive all-is-false check with recursive affirmative-true occurrence scan",
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def manifest():
    return {
        "schema_version": "2.1",
        "manifest_id": "phase7.3.3-d-multi-claim-successor-final-audit-manifest-frame-v2.1",
        "status": "frozen_before_final_audit",
        "adapter_sha256": sha(SELF),
        "frozen_base_adapter_sha256": sha(BASE_ADAPTER),
        "preexecution_implementation_failure_sha256": sha(IMPL),
        "scoped_artifact_sha256": {rel(path): sha(path) for path in SCOPED},
        "controlled_change": implementation_failure()["controlled_successor_change"],
        "scientific_metrics_changed": False,
        "power_decision_changed": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def preflight():
    checks = {"base_adapter_hash": BASE_ADAPTER.exists() and sha(BASE_ADAPTER) == BASE_HASH}
    checks.update({"exists:" + rel(path): path.exists() for path in SCOPED})
    if all(checks.values()):
        state, readiness = load(SI), load(RI)
        checks.update({
            "state_gate": state["next_authorized_stage"] == CUR,
            "readiness_gate": readiness["next_authorized_stage"] == CUR,
            "power_shortfall": load(PREPORT)["status"] == "power_identified_but_confirmatory_inventory_shortfall_authoritative",
            "confirmatory_not_authorized": load(PREPORT)["confirmatory_opening_authorized"] is False,
            "witness_field_missing": "confirmatory_dataset_opened" not in load(RREPORT),
            "base_final_outputs_absent": not (R / "phase7_3_3_d_multi_claim_successor_final_audit_manifest_frame_v2.json").exists(),
            "successor_outputs_absent": all(not path.exists() for path in [IMPL, IMPL_REC, MAN, REPORT, REC, SO, RO]),
            "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare():
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    failure_hash = once(IMPL, implementation_failure())
    failure_receipt_hash = once(IMPL_REC, {"schema_version": "2.1", "receipt_id": "phase7.3.3-d-final-audit-v2-preexecution-implementation-failure-receipt", "status": "PASS", "implementation_failure_sha256": failure_hash, "provider_called": False, "state_mutation_performed": False, "successor_final_audit_authorized": True})
    manifest_hash = once(MAN, manifest())
    return {"status": "PASS", "implementation_failure_sha256": failure_hash, "implementation_failure_receipt_sha256": failure_receipt_hash, "manifest_sha256": manifest_hash, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def audit_groups():
    scan = policy_scan()
    gold = load(GOLD)
    structural = load(STRUCT)
    realized = load(RREPORT)
    pilot = load(PRESULT)
    analysis = load(AREPORT)
    power = load(PREPORT)
    size = load(PSIZE)
    return {
        "support_gold": {"frozen_40_240": gold["support_gold_frozen"] is True and gold["case_count"] == 40 and gold["claim_count"] == 240, "label_only": gold["gold_fields"] == ["support_label"], "not_human_gold": "not_human_gold" in gold["status"], "seal_lineage": load(GSEAL)["support_gold_sha256"] == sha(GOLD)},
        "structural_identifiability": {"report_pass": structural["status"] == "PASS" and structural["structural_estimand_identifiable"] is True, "no_failed_checks": structural["failed_checks"] == [], "receipt_lineage": load(STRUCT_REC)["report_sha256"] == sha(STRUCT)},
        "pilot": {"execution_pass_80": pilot["status"] == "PASS" and pilot["request_count"] == 80, "paired_submissions_40": load(CSUB)["case_count"] == load(ASUB)["case_count"] == 40, "result_lineage": pilot["candidate_submission_sha256"] == sha(CSUB) and pilot["atomic_submission_sha256"] == sha(ASUB), "reference_invisible": pilot["reference_content_loaded"] is False and pilot["reference_labels_loaded"] is False},
        "realized_identifiability": {"report_pass": realized["status"] == "PASS" and realized["realized_representation_identifiable"] is True, "localization_scoring_authorized": realized["localization_scoring_authorized"] is True, "receipt_lineage": load(RREC)["report_sha256"] == sha(RREPORT)},
        "paired_analysis": {"paired_40_no_drop": analysis["case_count"] == 40 and analysis["missingness_and_failures"]["paired_cases_dropped"] == 0, "effect_positive": analysis["paired_primary_effect"]["estimate"] > 0, "bootstrap_lower_positive": analysis["paired_primary_effect"]["bootstrap_interval_95"][0] > 0, "confirmatory_p_value_null": analysis["paired_primary_effect"]["confirmatory_p_value"] is None, "receipt_lineage": load(AREC)["analysis_report_sha256"] == sha(AREPORT)},
        "power": {"target_identifiable": power["target_estimand_identifiable"] is True, "finite_sample_size_computed": size["finite_sample_size_computed"] is True, "inventory_shortfall": power["available_unopened_candidate_count"] < power["required_confirmatory_clusters"], "confirmatory_not_authorized": power["confirmatory_opening_authorized"] is False, "receipt_lineage": load(POWER_REC)["power_gate_report_sha256"] == sha(PREPORT) and load(POWER_REC)["sample_size_freeze_sha256"] == sha(PSIZE)},
        "global_policy": {"all_scoped_json_parsed": scan["scoped_json_file_count"] == len(SCOPED), "confirmatory_never_opened_or_authorized": not scan["confirmatory_true_occurrences"], "runtime_never_authorized": not scan["runtime_authorized_true_occurrences"], "usd_cost_not_imputed": not scan["nonnull_usd_cost_occurrences"], "entry_state_closed": load(SI)["confirmatory_dataset_opened"] is False and load(RI)["confirmatory_dataset_opened"] is False},
        "successor_lineage": {"base_adapter_immutable": sha(BASE_ADAPTER) == BASE_HASH, "preexecution_failure_preserved": load(IMPL)["status"] == "frozen_preexecution_implementation_failure", "base_realized_manifest_adapter": load(RMAN)["adapter_sha256"] == BASE_HASH, "base_analysis_manifest_adapter": load(AMAN)["adapter_sha256"] == BASE_HASH, "base_power_manifest_adapter": load(PMAN)["adapter_sha256"] == BASE_HASH},
    }


def audit():
    if not MAN.exists() or load(MAN) != manifest():
        raise RuntimeError("manifest_invalid")
    groups = audit_groups()
    failed = {name: [key for key, value in group.items() if not value] for name, group in groups.items() if not all(group.values())}
    if failed:
        raise RuntimeError("final_audit_failed:" + repr(failed))
    scan = policy_scan()
    analysis, power = load(AREPORT), load(PREPORT)
    report_hash = once(REPORT, {
        "schema_version": "2.1",
        "report_id": "phase7.3.3-d-multi-claim-successor-final-audit-report-frame-v2.1",
        "status": "PASS_exploratory_chain_completed_confirmatory_inventory_shortfall_authoritative",
        "manifest_sha256": sha(MAN),
        "preexecution_implementation_failure_sha256": sha(IMPL),
        "audit_groups": groups,
        "audit_summary": {"group_count": len(groups), "check_count": sum(len(group) for group in groups.values()), "failed_check_count": 0, "scoped_json_file_count": len(SCOPED)},
        "authoritative_scientific_result": {"paired_material_error_span_iou_effect_atomic_minus_candidate": analysis["paired_primary_effect"]["estimate"], "bootstrap_interval_95": analysis["paired_primary_effect"]["bootstrap_interval_95"], "study_role": "exploratory_identifiable_multi_claim_pilot", "confirmatory_conclusion_authorized": False},
        "power_disposition": {"status": power["status"], "required_confirmatory_clusters": power["required_confirmatory_clusters"], "available_unopened_candidate_count": power["available_unopened_candidate_count"], "confirmatory_opening_authorized": False, "next_required_stage": NEXT},
        "policy_scan": scan,
        "confirmatory_dataset_opened": False,
        "confirmatory_opening_authorized": False,
        "runtime_integration_authorized": False,
    })
    state, readiness = copy.deepcopy(load(SI)), copy.deepcopy(load(RI))
    lineage = {"multi_claim_successor_final_audit_v2_preexecution_implementation_failure_sha256": sha(IMPL), "multi_claim_successor_final_audit_manifest_frame_v2_1_sha256": sha(MAN), "multi_claim_successor_final_audit_report_frame_v2_1_sha256": report_hash}
    update = {"status": "multi_claim_successor_exploratory_chain_completed_confirmatory_inventory_shortfall_authoritative", "next_authorized_stage": NEXT, "multi_claim_successor_phase7_3_3_d_frame_v2_chain_completed": True, "multi_claim_successor_final_audit_frame_v2_1_passed": True, "multi_claim_successor_confirmatory_inventory_shortfall_authoritative": True, "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 99, "state_id": "phase7.3.3-d-support-stage-state-v99"})
    readiness.update({"schema_version": 110, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v110"})
    state_hash = once(SO, state)
    readiness["artifact_lineage"]["support_stage_state_v99_sha256"] = state_hash
    readiness_hash = once(RO, readiness)
    receipt_hash = once(REC, {"schema_version": "2.1", "receipt_id": "phase7.3.3-d-multi-claim-successor-final-audit-receipt-frame-v2.1", "status": "PASS_exploratory_chain_completed_confirmatory_inventory_shortfall_authoritative", "final_audit_manifest_sha256": sha(MAN), "final_audit_report_sha256": report_hash, "implementation_failure_sha256": sha(IMPL), "state_sha256": state_hash, "readiness_sha256": readiness_hash, "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": NEXT})
    return {"status": "PASS", "audit_check_count": sum(len(group) for group in groups.values()), "paired_effect": analysis["paired_primary_effect"]["estimate"], "required_confirmatory_clusters": power["required_confirmatory_clusters"], "available_unopened_candidate_count": power["available_unopened_candidate_count"], "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "report_sha256": report_hash, "receipt_sha256": receipt_hash, "next_authorized_stage": NEXT}


def verify():
    paths = [IMPL, IMPL_REC, MAN, REPORT, REC, SO, RO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        groups = audit_groups()
        report, receipt = load(REPORT), load(REC)
        checks.update({
            "implementation_failure_replay": load(IMPL) == implementation_failure(),
            "manifest_replay": load(MAN) == manifest(),
            "audit_groups_replay": report["audit_groups"] == groups,
            "all_audit_checks_pass": all(all(group.values()) for group in groups.values()),
            "report_pass": report["audit_summary"]["failed_check_count"] == 0,
            "authoritative_shortfall": "inventory_shortfall_authoritative" in report["status"],
            "receipt_lineage": receipt["final_audit_manifest_sha256"] == sha(MAN) and receipt["final_audit_report_sha256"] == sha(REPORT) and receipt["implementation_failure_sha256"] == sha(IMPL) and receipt["state_sha256"] == sha(SO) and receipt["readiness_sha256"] == sha(RO),
            "next_gate": load(SO)["next_authorized_stage"] == load(RO)["next_authorized_stage"] == NEXT,
            "confirmatory_closed": load(SO)["confirmatory_dataset_opened"] is False and load(RO)["confirmatory_dataset_opened"] is False and receipt["confirmatory_dataset_opened"] is False,
            "runtime_off": load(SO)["runtime_integration_authorized"] is False and load(RO)["runtime_integration_authorized"] is False and receipt["runtime_integration_authorized"] is False,
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(SO)["next_authorized_stage"] if SO.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["preflight", "prepare", "audit", "verify"]:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    outcome = preflight() if args.preflight else prepare() if args.prepare else audit() if args.audit else verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
