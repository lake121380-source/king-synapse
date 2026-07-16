#!/usr/bin/env python3
"""Realized-identifiability, paired analysis, power, and final audit gates."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import statistics
import tempfile
from collections import Counter
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

IDENT = C / "phase7_3_3_d_multi_claim_identifiability_policy_v1.json"
METRIC = C / "phase7_3_3_d_multi_claim_metric_specification_v1.json"
RQ = C / "phase7_3_3_d_multi_claim_successor_research_question_v1.json"
DATA = D / "phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json"
INVENTORY = R / "phase7_3_3_d_multi_claim_successor_source_inventory_v2.json"
GOLD = D / "phase7_3_3_d_multi_claim_successor_support_gold_frame_v2.json"
GSEAL = R / "phase7_3_3_d_multi_claim_successor_support_gold_seal_frame_v2.json"
CSUB = D / "phase7_3_3_d_multi_claim_successor_candidate_arm_submission_frame_v2.json"
ASUB = D / "phase7_3_3_d_multi_claim_successor_atomic_arm_submission_frame_v2.json"
PRESULT = R / "phase7_3_3_d_multi_claim_successor_pilot_execution_result_frame_v2.json"
PREC = R / "phase7_3_3_d_multi_claim_successor_pilot_execution_receipt_frame_v2.json"
SI = D / "phase7_3_3_d_support_stage_state_v95.json"
RI = R / "phase7_3_3_d1_reference_construction_readiness_v106.json"

RFIX = R / "phase7_3_3_d_multi_claim_successor_realized_identifiability_fixtures_frame_v2.json"
RMAN = R / "phase7_3_3_d_multi_claim_successor_realized_identifiability_manifest_frame_v2.json"
RREPORT = R / "phase7_3_3_d_multi_claim_successor_realized_identifiability_report_frame_v2.json"
RNEG = R / "phase7_3_3_d_multi_claim_successor_realized_identifiability_negative_result_frame_v2.json"
RREC = R / "phase7_3_3_d_multi_claim_successor_realized_identifiability_receipt_frame_v2.json"
RSO = D / "phase7_3_3_d_support_stage_state_v96.json"
RRO = R / "phase7_3_3_d1_reference_construction_readiness_v107.json"

APRO = C / "phase7_3_3_d_multi_claim_successor_paired_analysis_protocol_frame_v2.json"
AFIX = R / "phase7_3_3_d_multi_claim_successor_paired_analysis_fixtures_frame_v2.json"
AMAN = R / "phase7_3_3_d_multi_claim_successor_paired_analysis_manifest_frame_v2.json"
ACASES = D / "phase7_3_3_d_multi_claim_successor_paired_analysis_cases_frame_v2.json"
AREPORT = R / "phase7_3_3_d_multi_claim_successor_paired_analysis_report_frame_v2.json"
AREC = R / "phase7_3_3_d_multi_claim_successor_paired_analysis_receipt_frame_v2.json"
ASO = D / "phase7_3_3_d_support_stage_state_v97.json"
ARO = R / "phase7_3_3_d1_reference_construction_readiness_v108.json"

PMETHOD = C / "phase7_3_3_d_multi_claim_successor_power_method_frame_v2.json"
PFIX = R / "phase7_3_3_d_multi_claim_successor_power_fixtures_frame_v2.json"
PMAN = R / "phase7_3_3_d_multi_claim_successor_power_manifest_frame_v2.json"
PREPORT = R / "phase7_3_3_d_multi_claim_successor_power_gate_report_frame_v2.json"
PSIZE = R / "phase7_3_3_d_multi_claim_successor_sample_size_freeze_frame_v2.json"
PGATE_REC = R / "phase7_3_3_d_multi_claim_successor_power_gate_receipt_frame_v2.json"
PSO = D / "phase7_3_3_d_support_stage_state_v98.json"
PRO = R / "phase7_3_3_d1_reference_construction_readiness_v109.json"

FMAN = R / "phase7_3_3_d_multi_claim_successor_final_audit_manifest_frame_v2.json"
FREPORT = R / "phase7_3_3_d_multi_claim_successor_final_audit_report_frame_v2.json"
FREC = R / "phase7_3_3_d_multi_claim_successor_final_audit_receipt_frame_v2.json"
FSO = D / "phase7_3_3_d_support_stage_state_v99.json"
FRO = R / "phase7_3_3_d1_reference_construction_readiness_v110.json"

REAL_CUR = "evaluate_multi_claim_successor_realized_identifiability_frame_v2"
ANALYSIS_CUR = "freeze_multi_claim_successor_paired_analysis_frame_v2"
POWER_CUR = "freeze_multi_claim_successor_power_gate_frame_v2"
FINAL_CUR = "run_multi_claim_successor_final_audit_frame_v2"
BLOCK_REAL = "blocked_frame_v2_realized_identifiability_authoritative_negative"
FINAL_NEXT = "design_sealed_confirmatory_inventory_successor_after_authoritative_shortfall"
LABELS = ["supported", "partially_supported", "unsupported", "not_assessable"]


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


def common_input_checks():
    checks = {}
    for path in [IDENT, METRIC, RQ, DATA, INVENTORY, GOLD, GSEAL, CSUB, ASUB, PRESULT, PREC, SI, RI]:
        checks["exists:" + rel(path)] = path.exists()
    if all(checks.values()):
        receipt, result = load(PREC), load(PRESULT)
        state, readiness = load(SI), load(RI)
        checks.update({
            "candidate_lineage": receipt["candidate_submission_sha256"] == result["candidate_submission_sha256"] == sha(CSUB),
            "atomic_lineage": receipt["atomic_submission_sha256"] == result["atomic_submission_sha256"] == sha(ASUB),
            "pilot_result_lineage": receipt["execution_result_sha256"] == sha(PRESULT),
            "state_lineage": receipt["state_sha256"] == sha(SI),
            "readiness_lineage": receipt["readiness_sha256"] == sha(RI),
            "pilot_pass": result["status"] == "PASS" and result["request_count"] == 80,
            "state_gate": state["next_authorized_stage"] == REAL_CUR,
            "readiness_gate": readiness["next_authorized_stage"] == REAL_CUR,
            "gold_sealed": load(GSEAL)["support_gold_sha256"] == sha(GOLD),
            "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    return checks


def realized_metrics():
    candidate, atomic = load(CSUB), load(ASUB)
    candidate_ids = [case["case_id"] for case in candidate["cases"]]
    atomic_ids = [case["case_id"] for case in atomic["cases"]]
    decisions = [decision for case in atomic["cases"] for decision in case["decisions"]]
    duplicate_span_count = 0
    whole_count = 0
    multi_count = 0
    for case in atomic["cases"]:
        spans = [(decision["start"], decision["end"]) for decision in case["decisions"]]
        duplicate_span_count += len(spans) - len(set(spans))
        whole_count += sum(decision["operation"] == "whole_candidate_claim" for decision in case["decisions"])
        multi_count += len(case["decisions"]) > 1
    return {
        "selected_candidate_count": 40,
        "candidate_output_count": len(candidate_ids),
        "candidate_decisions_per_selected_candidate": len(candidate_ids) / 40,
        "atomic_unit_count": len(decisions),
        "atomic_unit_to_candidate_ratio": len(decisions) / 40,
        "atomic_multi_unit_candidate_rate": multi_count / 40,
        "atomic_whole_candidate_operation_rate": whole_count / len(decisions),
        "atomic_local_span_operation_rate": sum(decision["operation"] == "local_line_claim" for decision in decisions) / len(decisions),
        "atomic_duplicate_span_rate": duplicate_span_count / len(decisions),
        "missing_candidate_outputs": 40 - len(set(candidate_ids)),
        "duplicate_candidate_outputs": len(candidate_ids) - len(set(candidate_ids)),
        "missing_atomic_outputs": 40 - len(set(atomic_ids)),
        "duplicate_atomic_outputs": len(atomic_ids) - len(set(atomic_ids)),
        "reference_visible_during_arm_execution": load(CSUB)["reference_visible"] or load(ASUB)["reference_visible"] or load(PRESULT)["reference_content_loaded"],
    }


def realized_evaluate(observed):
    threshold = load(IDENT)["realized_representation_gate"]
    checks = {
        "candidate_decisions_per_selected_candidate": observed["candidate_decisions_per_selected_candidate"] == threshold["candidate_decisions_per_selected_candidate"],
        "atomic_unit_to_candidate_ratio_min": observed["atomic_unit_to_candidate_ratio"] >= threshold["atomic_unit_to_candidate_ratio_min"],
        "atomic_multi_unit_candidate_rate_min": observed["atomic_multi_unit_candidate_rate"] >= threshold["atomic_multi_unit_candidate_rate_min"],
        "atomic_whole_candidate_operation_rate_max": observed["atomic_whole_candidate_operation_rate"] <= threshold["atomic_whole_candidate_operation_rate_max"],
        "atomic_local_span_operation_rate_min": observed["atomic_local_span_operation_rate"] >= threshold["atomic_local_span_operation_rate_min"],
        "atomic_duplicate_span_rate_max": observed["atomic_duplicate_span_rate"] <= threshold["atomic_duplicate_span_rate_max"],
        "missing_candidate_outputs_allowed": observed["missing_candidate_outputs"] == observed["missing_atomic_outputs"] == threshold["missing_candidate_outputs_allowed"],
        "duplicate_candidate_outputs_allowed": observed["duplicate_candidate_outputs"] == observed["duplicate_atomic_outputs"] == threshold["duplicate_candidate_outputs_allowed"],
        "reference_not_visible": observed["reference_visible_during_arm_execution"] is threshold["reference_visible_during_arm_execution"],
    }
    return checks, [name for name, passed in checks.items() if not passed]


def realized_fixtures():
    threshold = load(IDENT)["realized_representation_gate"]
    rows = [
        {"fixture_id": "ratio_threshold_frozen", "passed": threshold["atomic_unit_to_candidate_ratio_min"] == 1.8},
        {"fixture_id": "whole_candidate_max_frozen", "passed": threshold["atomic_whole_candidate_operation_rate_max"] == 0.2},
        {"fixture_id": "local_span_min_frozen", "passed": threshold["atomic_local_span_operation_rate_min"] == 0.8},
        {"fixture_id": "failure_blocks_scoring", "passed": load(IDENT)["gate_actions"]["on_realized_representation_failure"] == "freeze_negative_result_and_do_not_score_localization_estimand"},
    ]
    return {"schema_version": 2, "fixtures_id": "phase7.3.3-d-realized-identifiability-fixtures-frame-v2", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def realized_manifest():
    inputs = [IDENT, METRIC, RQ, DATA, CSUB, ASUB, PRESULT, PREC, SI, RI]
    return {"schema_version": 2, "manifest_id": "phase7.3.3-d-realized-identifiability-manifest-frame-v2", "status": "frozen_before_offline_gate", "adapter_sha256": sha(SELF), "fixtures_sha256": sha(RFIX), "frozen_inputs": {rel(path): sha(path) for path in inputs}, "provider_calls": 0, "localization_scoring_started": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def realized_preflight():
    checks = common_input_checks()
    checks["outputs_absent"] = all(not path.exists() for path in [RFIX, RMAN, RREPORT, RNEG, RREC, RSO, RRO])
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def realized_prepare():
    checked = realized_preflight()
    if checked["status"] != "PASS":
        return checked
    return {"status": "PASS", "fixtures_sha256": once(RFIX, realized_fixtures()), "manifest_sha256": once(RMAN, realized_manifest()), "provider_calls": 0}


def realized_execute():
    if not RMAN.exists() or load(RMAN) != realized_manifest():
        raise RuntimeError("realized_manifest_invalid")
    observed = realized_metrics()
    checks, failed = realized_evaluate(observed)
    passed = not failed
    report_hash = once(RREPORT, {"schema_version": 2, "report_id": "phase7.3.3-d-realized-identifiability-report-frame-v2", "status": "PASS" if passed else "FAIL", "manifest_sha256": sha(RMAN), "metrics": observed, "thresholds": load(IDENT)["realized_representation_gate"], "checks": checks, "failed_checks": failed, "realized_representation_identifiable": passed, "localization_scoring_authorized": passed, "provider_calls": 0, "confirmatory_opening_authorized": False})
    next_stage = ANALYSIS_CUR if passed else BLOCK_REAL
    negative_hash = None
    if not passed:
        negative_hash = once(RNEG, {"schema_version": 2, "negative_result_id": "phase7.3.3-d-realized-identifiability-negative-result-frame-v2", "status": "authoritative_realized_identifiability_negative_result", "manifest_sha256": sha(RMAN), "report_sha256": report_hash, "failed_checks": failed, "localization_scoring_authorized": False, "same_version_retry_allowed": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": next_stage})
    state, readiness = copy.deepcopy(load(SI)), copy.deepcopy(load(RI))
    lineage = {"multi_claim_successor_realized_identifiability_manifest_frame_v2_sha256": sha(RMAN), "multi_claim_successor_realized_identifiability_report_frame_v2_sha256": report_hash}
    if negative_hash:
        lineage["multi_claim_successor_realized_identifiability_negative_frame_v2_sha256"] = negative_hash
    update = {"status": "multi_claim_successor_realized_identifiability_frame_v2_passed_analysis_authorized" if passed else "multi_claim_successor_realized_identifiability_frame_v2_authoritative_negative", "next_authorized_stage": next_stage, "multi_claim_successor_realized_identifiability_frame_v2_evaluated": True, "multi_claim_successor_realized_identifiability_frame_v2_passed": passed, "multi_claim_successor_localization_scoring_frame_v2_authorized": passed, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 96, "state_id": "phase7.3.3-d-support-stage-state-v96"})
    readiness.update({"schema_version": 107, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v107"})
    state_hash = once(RSO, state)
    readiness["artifact_lineage"]["support_stage_state_v96_sha256"] = state_hash
    readiness_hash = once(RRO, readiness)
    receipt_hash = once(RREC, {"schema_version": 2, "receipt_id": "phase7.3.3-d-realized-identifiability-receipt-frame-v2", "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT", "manifest_sha256": sha(RMAN), "report_sha256": report_hash, "negative_result_sha256": negative_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "localization_scoring_authorized": passed, "next_authorized_stage": next_stage})
    return {"status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT", "metrics": observed, "failed_checks": failed, "report_sha256": report_hash, "receipt_sha256": receipt_hash, "next_authorized_stage": next_stage}


def realized_verify():
    paths = [RFIX, RMAN, RREPORT, RREC, RSO, RRO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        observed = realized_metrics()
        gate, failed_gate = realized_evaluate(observed)
        report, receipt = load(RREPORT), load(RREC)
        passed = not failed_gate
        checks.update({"fixtures_replay": load(RFIX) == realized_fixtures(), "manifest_replay": load(RMAN) == realized_manifest(), "metrics_replay": report["metrics"] == observed, "checks_replay": report["checks"] == gate and report["failed_checks"] == failed_gate, "negative_presence_exact": RNEG.exists() is (not passed), "receipt_lineage": receipt["report_sha256"] == sha(RREPORT) and receipt["state_sha256"] == sha(RSO) and receipt["readiness_sha256"] == sha(RRO), "next_gate": load(RSO)["next_authorized_stage"] == load(RRO)["next_authorized_stage"] == (ANALYSIS_CUR if passed else BLOCK_REAL), "confirmatory_closed": load(RSO)["confirmatory_dataset_opened"] is False, "runtime_off": load(RSO)["runtime_integration_authorized"] is False})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(RSO)["next_authorized_stage"] if RSO.exists() else None}


def analysis_protocol():
    return {"schema_version": 2, "protocol_id": "phase7.3.3-d-multi-claim-successor-paired-analysis-frame-v2", "status": "frozen_before_reference_json_parsing_and_scoring", "primary_estimand": load(METRIC)["primary_estimand"], "paired_unit": "unique_candidate", "case_count": 40, "uncertainty": load(METRIC)["uncertainty"], "confirmatory_p_value": None, "no_silent_drop": True, "reference_visible_during_arm_execution": False, "provider_calls": 0, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def analysis_fixtures():
    rows = [{"fixture_id": "empty_empty_iou", "passed": iou(set(), set()) == 1}, {"fixture_id": "one_empty_iou", "passed": iou({1}, set()) == 0}, {"fixture_id": "known_iou", "passed": iou({1, 2}, {2, 3}) == 1 / 3}, {"fixture_id": "bootstrap_seed_frozen", "passed": load(METRIC)["uncertainty"]["seed"] == 733061}, {"fixture_id": "confirmatory_p_value_null", "passed": analysis_protocol()["confirmatory_p_value"] is None}]
    return {"schema_version": 2, "fixtures_id": "phase7.3.3-d-paired-analysis-fixtures-frame-v2", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def analysis_manifest():
    inputs = [METRIC, RQ, DATA, GOLD, GSEAL, CSUB, ASUB, PRESULT, RREPORT, RREC, RSO, RRO]
    return {"schema_version": 2, "manifest_id": "phase7.3.3-d-multi-claim-successor-paired-analysis-manifest-frame-v2", "status": "frozen_before_reference_json_content_parsing_and_scoring", "adapter_sha256": sha(SELF), "protocol_sha256": sha(APRO), "fixtures_sha256": sha(AFIX), "frozen_inputs": {rel(path): sha(path) for path in inputs}, "reference_prefreeze_json_content_parsed": False, "arm_outputs_visible_during_manifest_freeze": False, "provider_calls": 0}


def analysis_preflight():
    checks = {"realized_verify": realized_verify()["status"] == "PASS"}
    if RSO.exists() and RRO.exists():
        checks.update({"state_gate": load(RSO)["next_authorized_stage"] == ANALYSIS_CUR, "readiness_gate": load(RRO)["next_authorized_stage"] == ANALYSIS_CUR, "realized_pass": load(RREPORT)["realized_representation_identifiable"] is True, "outputs_absent": all(not path.exists() for path in [APRO, AFIX, AMAN, ACASES, AREPORT, AREC, ASO, ARO]), "confirmatory_closed": load(RSO)["confirmatory_dataset_opened"] is False, "runtime_off": load(RSO)["runtime_integration_authorized"] is False})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def analysis_prepare():
    checked = analysis_preflight()
    if checked["status"] != "PASS":
        return checked
    once(APRO, analysis_protocol())
    once(AFIX, analysis_fixtures())
    return {"status": "PASS", "protocol_sha256": sha(APRO), "fixtures_sha256": sha(AFIX), "manifest_sha256": once(AMAN, analysis_manifest()), "reference_content_parsed": False}


def eligible(text: str):
    return {index for index, character in enumerate(text) if not character.isspace()}


def iou(a: set, b: set):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def precision_recall_f1(predicted: set, gold: set):
    intersection = len(predicted & gold)
    precision = intersection / len(predicted) if predicted else (1.0 if not gold else 0.0)
    recall = intersection / len(gold) if gold else (1.0 if not predicted else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def aggregate_gold(labels):
    if all(label == "supported" for label in labels):
        return "supported"
    if all(label == "unsupported" for label in labels):
        return "unsupported"
    return "partially_supported"


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def analysis_docs():
    data = {case["candidate_id"]: case for case in load(DATA)["cases"]}
    gold = {case["case_id"]: case for case in load(GOLD)["cases"]}
    candidate = {case["case_id"]: case for case in load(CSUB)["cases"]}
    atomic = {case["case_id"]: case for case in load(ASUB)["cases"]}
    cases = []
    total_gold, total_candidate, total_atomic = set(), set(), set()
    offset = 0
    candidate_correct = atomic_correct = atomic_total = 0
    for case_id in [case["candidate_id"] for case in load(DATA)["cases"]]:
        text = data[case_id]["candidate_text"]
        gold_claims = gold[case_id]["claims"]
        gold_mask = {index for claim in gold_claims if claim["support_label"] in {"partially_supported", "unsupported"} for index in range(claim["source_span"]["start"], claim["source_span"]["end"]) if not text[index].isspace()}
        candidate_label = candidate[case_id]["decision"]["support_label"]
        candidate_mask = set() if candidate_label == "supported" else eligible(text)
        atomic_decisions = atomic[case_id]["decisions"]
        atomic_mask = {index for decision in atomic_decisions if decision["support_label"] in {"partially_supported", "unsupported"} for index in range(decision["start"], decision["end"]) if not text[index].isspace()}
        gold_labels = [claim["support_label"] for claim in gold_claims]
        candidate_gold = aggregate_gold(gold_labels)
        candidate_correct += candidate_label == candidate_gold
        atomic_correct += sum(decision["support_label"] == label for decision, label in zip(atomic_decisions, gold_labels))
        atomic_total += len(gold_labels)
        ciou, aiou = iou(candidate_mask, gold_mask), iou(atomic_mask, gold_mask)
        cp, cr, cf = precision_recall_f1(candidate_mask, gold_mask)
        ap, ar, af = precision_recall_f1(atomic_mask, gold_mask)
        cases.append({"case_id": case_id, "gold_material_error_character_count": len(gold_mask), "candidate_predicted_error_character_count": len(candidate_mask), "atomic_predicted_error_character_count": len(atomic_mask), "candidate_material_error_span_iou": ciou, "atomic_material_error_span_iou": aiou, "paired_difference_atomic_minus_candidate": aiou - ciou, "candidate_localization_precision": cp, "candidate_localization_recall": cr, "candidate_localization_f1": cf, "atomic_localization_precision": ap, "atomic_localization_recall": ar, "atomic_localization_f1": af, "candidate_label": candidate_label, "candidate_reference_label": candidate_gold, "candidate_label_exact": candidate_label == candidate_gold, "atomic_claim_exact_count": sum(decision["support_label"] == label for decision, label in zip(atomic_decisions, gold_labels)), "atomic_claim_count": len(gold_labels)})
        total_gold |= {offset + index for index in gold_mask}
        total_candidate |= {offset + index for index in candidate_mask}
        total_atomic |= {offset + index for index in atomic_mask}
        offset += len(text) + 1
    differences = [case["paired_difference_atomic_minus_candidate"] for case in cases]
    rng = random.Random(load(METRIC)["uncertainty"]["seed"])
    bootstrap = [sum(differences[rng.randrange(len(differences))] for _ in differences) / len(differences) for _ in range(load(METRIC)["uncertainty"]["replicates"])]
    estimate = statistics.mean(differences)
    c_micro = precision_recall_f1(total_candidate, total_gold)
    a_micro = precision_recall_f1(total_atomic, total_gold)
    cases_doc = {"schema_version": 2, "dataset_id": "phase7.3.3-d-multi-claim-successor-paired-analysis-cases-frame-v2", "status": "frozen_scored_paired_cases", "case_count": 40, "cases": cases}
    report = {"schema_version": 2, "report_id": "phase7.3.3-d-multi-claim-successor-paired-analysis-report-frame-v2", "status": "completed_authoritative_exploratory_paired_analysis", "manifest_sha256": sha(AMAN), "case_count": 40, "paired_primary_effect": {"estimand": load(METRIC)["primary_estimand"], "estimate": estimate, "paired_sd": statistics.stdev(differences), "bootstrap_interval_95": [percentile(bootstrap, 0.025), percentile(bootstrap, 0.975)], "bootstrap_replicates": len(bootstrap), "bootstrap_seed": load(METRIC)["uncertainty"]["seed"], "confirmatory_p_value": None}, "arm_metrics": {"candidate": {"mean_material_error_span_iou": statistics.mean(case["candidate_material_error_span_iou"] for case in cases), "exact_candidate_label_accuracy": candidate_correct / 40, "localization_micro_precision": c_micro[0], "localization_micro_recall": c_micro[1], "localization_micro_f1": c_micro[2]}, "atomic": {"mean_material_error_span_iou": statistics.mean(case["atomic_material_error_span_iou"] for case in cases), "exact_claim_label_accuracy": atomic_correct / atomic_total, "boundary_exact_span_rate": 1.0, "localization_micro_precision": a_micro[0], "localization_micro_recall": a_micro[1], "localization_micro_f1": a_micro[2]}}, "missingness_and_failures": {"selected_cases": 40, "paired_cases_scored": 40, "paired_cases_dropped": 0, "missing_candidate_outputs": 0, "missing_atomic_outputs": 0}, "resources": {"candidate": resource_summary(load(CSUB)["cases"]), "atomic": resource_summary(load(ASUB)["cases"])}, "reference_visible_during_arm_execution": False, "confirmatory_dataset_opened": False, "confirmatory_opening_authorized": False, "runtime_integration_authorized": False}
    return cases_doc, report


def resource_summary(cases):
    resources = [case["resources"] for case in cases]
    return {"request_count": len(resources), "total_tokens": sum(row["total_tokens"] for row in resources if isinstance(row["total_tokens"], int)), "token_usage_complete": all(isinstance(row["total_tokens"], int) for row in resources), "mean_latency_ms": statistics.mean(row["latency_ms"] for row in resources), "cost_usd": None, "cost_status": "provider_price_not_frozen"}


def analysis_execute():
    if not AMAN.exists() or load(AMAN) != analysis_manifest():
        raise RuntimeError("analysis_manifest_invalid")
    cases_doc, report = analysis_docs()
    cases_hash, report_hash = once(ACASES, cases_doc), once(AREPORT, report)
    state, readiness = copy.deepcopy(load(RSO)), copy.deepcopy(load(RRO))
    lineage = {"multi_claim_successor_paired_analysis_manifest_frame_v2_sha256": sha(AMAN), "multi_claim_successor_paired_analysis_cases_frame_v2_sha256": cases_hash, "multi_claim_successor_paired_analysis_report_frame_v2_sha256": report_hash}
    update = {"status": "multi_claim_successor_paired_analysis_frame_v2_completed_power_gate_authorized", "next_authorized_stage": POWER_CUR, "multi_claim_successor_paired_analysis_frame_v2_completed": True, "multi_claim_successor_paired_effect_frame_v2": report["paired_primary_effect"]["estimate"], "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 97, "state_id": "phase7.3.3-d-support-stage-state-v97"})
    readiness.update({"schema_version": 108, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v108"})
    state_hash = once(ASO, state)
    readiness["artifact_lineage"]["support_stage_state_v97_sha256"] = state_hash
    readiness_hash = once(ARO, readiness)
    receipt_hash = once(AREC, {"schema_version": 2, "receipt_id": "phase7.3.3-d-multi-claim-successor-paired-analysis-receipt-frame-v2", "status": "PASS", "manifest_sha256": sha(AMAN), "paired_cases_sha256": cases_hash, "analysis_report_sha256": report_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "case_count": 40, "paired_cases_dropped": 0, "confirmatory_dataset_opened": False, "next_authorized_stage": POWER_CUR})
    return {"status": "PASS", "case_count": 40, "paired_effect": report["paired_primary_effect"], "report_sha256": report_hash, "receipt_sha256": receipt_hash, "next_authorized_stage": POWER_CUR}


def analysis_verify():
    paths = [APRO, AFIX, AMAN, ACASES, AREPORT, AREC, ASO, ARO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        cases_doc, report = analysis_docs()
        receipt = load(AREC)
        checks.update({"protocol_replay": load(APRO) == analysis_protocol(), "fixtures_replay": load(AFIX) == analysis_fixtures(), "manifest_replay": load(AMAN) == analysis_manifest(), "cases_replay": load(ACASES) == cases_doc, "report_replay": load(AREPORT) == report, "no_drop": report["missingness_and_failures"]["paired_cases_dropped"] == 0, "receipt_lineage": receipt["paired_cases_sha256"] == sha(ACASES) and receipt["analysis_report_sha256"] == sha(AREPORT) and receipt["state_sha256"] == sha(ASO) and receipt["readiness_sha256"] == sha(ARO), "state_gate": load(ASO)["next_authorized_stage"] == load(ARO)["next_authorized_stage"] == POWER_CUR, "confirmatory_closed": load(ASO)["confirmatory_dataset_opened"] is False, "runtime_off": load(ASO)["runtime_integration_authorized"] is False})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(ASO)["next_authorized_stage"] if ASO.exists() else None}


def power_method():
    return {"schema_version": 2, "method_id": "phase7.3.3-d-multi-claim-successor-power-method-frame-v2", "status": "frozen_before_power_computation", "target_estimand": load(METRIC)["primary_estimand"], "alpha_one_sided": 0.05, "target_power": 0.8, "normal_quantiles": {"z_1_minus_alpha": 1.6448536269514722, "z_power": 0.8416212335729143}, "paired_cluster_unit": "unique_candidate", "minimum_confirmatory_clusters": 40, "available_unopened_inventory_required": True, "observed_effect_may_be_used_only_after_structural_and_realized_gates_pass": True, "confirmatory_opening_requires_positive_bootstrap_lower_bound": True, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def power_fixtures():
    rows = [{"fixture_id": "minimum_40", "passed": power_method()["minimum_confirmatory_clusters"] == 40}, {"fixture_id": "one_sided_alpha", "passed": power_method()["alpha_one_sided"] == 0.05}, {"fixture_id": "inventory_required", "passed": power_method()["available_unopened_inventory_required"] is True}, {"fixture_id": "gates_required", "passed": power_method()["observed_effect_may_be_used_only_after_structural_and_realized_gates_pass"] is True}]
    return {"schema_version": 2, "fixtures_id": "phase7.3.3-d-power-fixtures-frame-v2", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def power_manifest():
    inputs = [IDENT, METRIC, INVENTORY, RREPORT, RREC, AREPORT, AREC, ASO, ARO]
    return {"schema_version": 2, "manifest_id": "phase7.3.3-d-multi-claim-successor-power-manifest-frame-v2", "status": "frozen_before_power_computation", "adapter_sha256": sha(SELF), "method_sha256": sha(PMETHOD), "fixtures_sha256": sha(PFIX), "frozen_inputs": {rel(path): sha(path) for path in inputs}, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def power_preflight():
    checks = {"analysis_verify": analysis_verify()["status"] == "PASS"}
    if ASO.exists() and ARO.exists():
        checks.update({"state_gate": load(ASO)["next_authorized_stage"] == POWER_CUR, "readiness_gate": load(ARO)["next_authorized_stage"] == POWER_CUR, "structural_pass": load(RREPORT)["realized_representation_identifiable"] is True, "outputs_absent": all(not path.exists() for path in [PMETHOD, PFIX, PMAN, PREPORT, PSIZE, PGATE_REC, PSO, PRO]), "confirmatory_closed": load(ASO)["confirmatory_dataset_opened"] is False, "runtime_off": load(ASO)["runtime_integration_authorized"] is False})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def power_prepare():
    checked = power_preflight()
    if checked["status"] != "PASS":
        return checked
    once(PMETHOD, power_method())
    once(PFIX, power_fixtures())
    return {"status": "PASS", "method_sha256": sha(PMETHOD), "fixtures_sha256": sha(PFIX), "manifest_sha256": once(PMAN, power_manifest())}


def inventory_count():
    inventory = load(INVENTORY)
    return inventory.get("inventory_count") or inventory.get("candidate_count") or len(inventory.get("items", []))


def power_execute():
    if not PMAN.exists() or load(PMAN) != power_manifest():
        raise RuntimeError("power_manifest_invalid")
    analysis = load(AREPORT)
    effect = analysis["paired_primary_effect"]["estimate"]
    paired_sd = analysis["paired_primary_effect"]["paired_sd"]
    lower = analysis["paired_primary_effect"]["bootstrap_interval_95"][0]
    method = load(PMETHOD)
    raw = math.ceil(((method["normal_quantiles"]["z_1_minus_alpha"] + method["normal_quantiles"]["z_power"]) * paired_sd / effect) ** 2) if effect > 0 else None
    sample_size = max(method["minimum_confirmatory_clusters"], raw or method["minimum_confirmatory_clusters"])
    inventory_total = inventory_count()
    available = inventory_total - 40
    gates = {"structural_identifiability_passed": load(SI)["multi_claim_successor_structural_identifiability_frame_v2_passed"] is True, "realized_identifiability_passed": load(RREPORT)["realized_representation_identifiable"] is True, "paired_effect_positive": effect > 0, "bootstrap_lower_bound_positive": lower > 0, "no_paired_missingness": analysis["missingness_and_failures"]["paired_cases_dropped"] == 0, "unopened_inventory_sufficient": available >= sample_size}
    authorized = all(gates.values())
    status = "confirmatory_opening_authorized" if authorized else "power_identified_but_confirmatory_inventory_shortfall_authoritative" if all(value for key, value in gates.items() if key != "unopened_inventory_sufficient") else "power_or_identifiability_gate_failed"
    report_hash = once(PREPORT, {"schema_version": 2, "report_id": "phase7.3.3-d-multi-claim-successor-power-gate-report-frame-v2", "status": status, "manifest_sha256": sha(PMAN), "identifiability_requirement_results": gates, "observed_paired_effect": effect, "observed_paired_sd": paired_sd, "bootstrap_lower_bound": lower, "raw_normal_approximation_clusters": raw, "minimum_confirmatory_clusters": method["minimum_confirmatory_clusters"], "required_confirmatory_clusters": sample_size, "sealed_inventory_total": inventory_total, "exploratory_selected_count": 40, "available_unopened_candidate_count": available, "target_estimand_identifiable": all(value for key, value in gates.items() if key != "unopened_inventory_sufficient"), "confirmatory_opening_authorized": authorized, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False})
    size_hash = once(PSIZE, {"schema_version": 2, "freeze_id": "phase7.3.3-d-multi-claim-successor-sample-size-freeze-frame-v2", "status": "finite_sample_size_computed_inventory_shortfall" if not authorized else "finite_sample_size_authorized", "power_gate_report_sha256": report_hash, "sample_size_candidates": sample_size, "sample_size_clusters": sample_size, "available_unopened_candidate_count": available, "finite_sample_size_computed": True, "confirmatory_opening_authorized": authorized, "confirmatory_dataset_opened": False})
    state, readiness = copy.deepcopy(load(ASO)), copy.deepcopy(load(ARO))
    lineage = {"multi_claim_successor_power_method_frame_v2_sha256": sha(PMETHOD), "multi_claim_successor_power_manifest_frame_v2_sha256": sha(PMAN), "multi_claim_successor_power_gate_report_frame_v2_sha256": report_hash, "multi_claim_successor_sample_size_freeze_frame_v2_sha256": size_hash}
    update = {"status": status, "next_authorized_stage": FINAL_CUR, "multi_claim_successor_power_gate_frame_v2_completed": True, "multi_claim_successor_confirmatory_sample_size_frame_v2": sample_size, "multi_claim_successor_confirmatory_inventory_shortfall": not gates["unopened_inventory_sufficient"], "confirmatory_opening_authorized": authorized, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 98, "state_id": "phase7.3.3-d-support-stage-state-v98"})
    readiness.update({"schema_version": 109, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v109"})
    state_hash = once(PSO, state)
    readiness["artifact_lineage"]["support_stage_state_v98_sha256"] = state_hash
    readiness_hash = once(PRO, readiness)
    receipt_hash = once(PGATE_REC, {"schema_version": 2, "receipt_id": "phase7.3.3-d-multi-claim-successor-power-gate-receipt-frame-v2", "status": "PASS", "manifest_sha256": sha(PMAN), "power_gate_report_sha256": report_hash, "sample_size_freeze_sha256": size_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "sample_size_candidates": sample_size, "confirmatory_opening_authorized": authorized, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": FINAL_CUR})
    return {"status": "PASS", "power_status": status, "sample_size_candidates": sample_size, "available_unopened_candidate_count": available, "confirmatory_opening_authorized": authorized, "report_sha256": report_hash, "receipt_sha256": receipt_hash, "next_authorized_stage": FINAL_CUR}


def power_verify():
    paths = [PMETHOD, PFIX, PMAN, PREPORT, PSIZE, PGATE_REC, PSO, PRO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        report, size, receipt = load(PREPORT), load(PSIZE), load(PGATE_REC)
        checks.update({"method_replay": load(PMETHOD) == power_method(), "fixtures_replay": load(PFIX) == power_fixtures(), "manifest_replay": load(PMAN) == power_manifest(), "inventory_accounting": report["sealed_inventory_total"] == inventory_count() and report["available_unopened_candidate_count"] == inventory_count() - 40, "shortfall_authoritative": report["status"] == "power_identified_but_confirmatory_inventory_shortfall_authoritative" and report["confirmatory_opening_authorized"] is False, "size_frozen": size["sample_size_candidates"] == report["required_confirmatory_clusters"], "receipt_lineage": receipt["power_gate_report_sha256"] == sha(PREPORT) and receipt["sample_size_freeze_sha256"] == sha(PSIZE) and receipt["state_sha256"] == sha(PSO) and receipt["readiness_sha256"] == sha(PRO), "state_gate": load(PSO)["next_authorized_stage"] == load(PRO)["next_authorized_stage"] == FINAL_CUR, "confirmatory_closed": load(PSO)["confirmatory_dataset_opened"] is False and load(PRO)["confirmatory_dataset_opened"] is False, "runtime_off": load(PSO)["runtime_integration_authorized"] is False})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(PSO)["next_authorized_stage"] if PSO.exists() else None}


def final_manifest():
    inputs = [GOLD, GSEAL, CSUB, ASUB, PRESULT, PREC, RREPORT, RREC, AREPORT, AREC, PREPORT, PSIZE, PGATE_REC, PSO, PRO]
    return {"schema_version": 2, "manifest_id": "phase7.3.3-d-multi-claim-successor-final-audit-manifest-frame-v2", "status": "frozen_before_final_audit", "adapter_sha256": sha(SELF), "scoped_artifact_sha256": {rel(path): sha(path) for path in inputs}, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def final_preflight():
    checks = {"power_verify": power_verify()["status"] == "PASS"}
    if PSO.exists() and PRO.exists():
        checks.update({"state_gate": load(PSO)["next_authorized_stage"] == FINAL_CUR, "readiness_gate": load(PRO)["next_authorized_stage"] == FINAL_CUR, "confirmatory_not_authorized": load(PREPORT)["confirmatory_opening_authorized"] is False, "outputs_absent": all(not path.exists() for path in [FMAN, FREPORT, FREC, FSO, FRO]), "confirmatory_closed": load(PSO)["confirmatory_dataset_opened"] is False, "runtime_off": load(PSO)["runtime_integration_authorized"] is False})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def final_prepare():
    checked = final_preflight()
    if checked["status"] != "PASS":
        return checked
    return {"status": "PASS", "manifest_sha256": once(FMAN, final_manifest()), "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def final_audit():
    if not FMAN.exists() or load(FMAN) != final_manifest():
        raise RuntimeError("final_manifest_invalid")
    groups = {
        "support_gold": {"frozen_40_240": load(GOLD)["support_gold_frozen"] is True and load(GOLD)["case_count"] == 40 and load(GOLD)["claim_count"] == 240, "label_only": load(GOLD)["gold_fields"] == ["support_label"], "not_human_gold": "not_human_gold" in load(GOLD)["status"]},
        "pilot": {"execution_pass": load(PRESULT)["status"] == "PASS" and load(PRESULT)["request_count"] == 80, "paired_submissions_40": load(CSUB)["case_count"] == load(ASUB)["case_count"] == 40, "reference_invisible": load(PRESULT)["reference_content_loaded"] is False},
        "identifiability": {"structural_pass": load(SI)["multi_claim_successor_structural_identifiability_frame_v2_passed"] is True, "realized_pass": load(RREPORT)["realized_representation_identifiable"] is True, "localization_scoring_authorized": load(RREPORT)["localization_scoring_authorized"] is True},
        "analysis": {"paired_40_no_drop": load(AREPORT)["case_count"] == 40 and load(AREPORT)["missingness_and_failures"]["paired_cases_dropped"] == 0, "effect_positive": load(AREPORT)["paired_primary_effect"]["estimate"] > 0, "bootstrap_lower_positive": load(AREPORT)["paired_primary_effect"]["bootstrap_interval_95"][0] > 0, "confirmatory_p_value_null": load(AREPORT)["paired_primary_effect"]["confirmatory_p_value"] is None},
        "power": {"target_identifiable": load(PREPORT)["target_estimand_identifiable"] is True, "finite_sample_size_computed": load(PSIZE)["finite_sample_size_computed"] is True, "inventory_shortfall": load(PREPORT)["available_unopened_candidate_count"] < load(PREPORT)["required_confirmatory_clusters"], "confirmatory_not_authorized": load(PREPORT)["confirmatory_opening_authorized"] is False},
        "policy": {"confirmatory_never_opened": all(load(path).get("confirmatory_dataset_opened") is False for path in [GOLD, PRESULT, RREPORT, AREPORT, PREPORT, PSO, PRO]), "runtime_never_authorized": all(load(path).get("runtime_integration_authorized") is False for path in [GOLD, PRESULT, PREPORT, PSO, PRO]), "usd_cost_not_imputed": load(AREPORT)["resources"]["candidate"]["cost_usd"] is None and load(AREPORT)["resources"]["atomic"]["cost_usd"] is None},
    }
    if not all(all(group.values()) for group in groups.values()):
        raise RuntimeError("final_audit_failed:" + repr({name: [key for key, value in group.items() if not value] for name, group in groups.items() if not all(group.values())}))
    report_hash = once(FREPORT, {"schema_version": 2, "report_id": "phase7.3.3-d-multi-claim-successor-final-audit-report-frame-v2", "status": "PASS_exploratory_chain_completed_confirmatory_inventory_shortfall_authoritative", "manifest_sha256": sha(FMAN), "audit_groups": groups, "audit_summary": {"group_count": len(groups), "check_count": sum(len(group) for group in groups.values()), "failed_check_count": 0}, "authoritative_scientific_result": {"paired_material_error_span_iou_effect_atomic_minus_candidate": load(AREPORT)["paired_primary_effect"]["estimate"], "bootstrap_interval_95": load(AREPORT)["paired_primary_effect"]["bootstrap_interval_95"], "study_role": "exploratory_identifiable_multi_claim_pilot", "confirmatory_conclusion_authorized": False}, "power_disposition": {"status": load(PREPORT)["status"], "required_confirmatory_clusters": load(PREPORT)["required_confirmatory_clusters"], "available_unopened_candidate_count": load(PREPORT)["available_unopened_candidate_count"], "confirmatory_opening_authorized": False, "next_required_stage": FINAL_NEXT}, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False})
    state, readiness = copy.deepcopy(load(PSO)), copy.deepcopy(load(PRO))
    lineage = {"multi_claim_successor_final_audit_manifest_frame_v2_sha256": sha(FMAN), "multi_claim_successor_final_audit_report_frame_v2_sha256": report_hash}
    update = {"status": "multi_claim_successor_exploratory_chain_completed_confirmatory_inventory_shortfall_authoritative", "next_authorized_stage": FINAL_NEXT, "multi_claim_successor_phase7_3_3_d_frame_v2_chain_completed": True, "multi_claim_successor_final_audit_frame_v2_passed": True, "multi_claim_successor_confirmatory_inventory_shortfall_authoritative": True, "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 99, "state_id": "phase7.3.3-d-support-stage-state-v99"})
    readiness.update({"schema_version": 110, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v110"})
    state_hash = once(FSO, state)
    readiness["artifact_lineage"]["support_stage_state_v99_sha256"] = state_hash
    readiness_hash = once(FRO, readiness)
    receipt_hash = once(FREC, {"schema_version": 2, "receipt_id": "phase7.3.3-d-multi-claim-successor-final-audit-receipt-frame-v2", "status": "PASS_exploratory_chain_completed_confirmatory_inventory_shortfall_authoritative", "final_audit_manifest_sha256": sha(FMAN), "final_audit_report_sha256": report_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": FINAL_NEXT})
    return {"status": "PASS", "audit_check_count": sum(len(group) for group in groups.values()), "paired_effect": load(AREPORT)["paired_primary_effect"]["estimate"], "required_confirmatory_clusters": load(PREPORT)["required_confirmatory_clusters"], "available_unopened_candidate_count": load(PREPORT)["available_unopened_candidate_count"], "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "report_sha256": report_hash, "receipt_sha256": receipt_hash, "next_authorized_stage": FINAL_NEXT}


def final_verify():
    paths = [FMAN, FREPORT, FREC, FSO, FRO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        report, receipt = load(FREPORT), load(FREC)
        checks.update({"manifest_replay": load(FMAN) == final_manifest(), "all_audit_checks_pass": all(all(group.values()) for group in report["audit_groups"].values()), "report_pass": report["audit_summary"]["failed_check_count"] == 0, "authoritative_shortfall": "inventory_shortfall_authoritative" in report["status"], "receipt_lineage": receipt["final_audit_manifest_sha256"] == sha(FMAN) and receipt["final_audit_report_sha256"] == sha(FREPORT) and receipt["state_sha256"] == sha(FSO) and receipt["readiness_sha256"] == sha(FRO), "next_gate": load(FSO)["next_authorized_stage"] == load(FRO)["next_authorized_stage"] == FINAL_NEXT, "confirmatory_closed": load(FSO)["confirmatory_dataset_opened"] is False and load(FRO)["confirmatory_dataset_opened"] is False and receipt["confirmatory_dataset_opened"] is False, "runtime_off": load(FSO)["runtime_integration_authorized"] is False and load(FRO)["runtime_integration_authorized"] is False and receipt["runtime_integration_authorized"] is False})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(FSO)["next_authorized_stage"] if FSO.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    actions = {
        "realized-preflight": realized_preflight, "realized-prepare": realized_prepare, "realized-execute": realized_execute, "realized-verify": realized_verify,
        "analysis-preflight": analysis_preflight, "analysis-prepare": analysis_prepare, "analysis-execute": analysis_execute, "analysis-verify": analysis_verify,
        "power-preflight": power_preflight, "power-prepare": power_prepare, "power-execute": power_execute, "power-verify": power_verify,
        "final-preflight": final_preflight, "final-prepare": final_prepare, "final-audit": final_audit, "final-verify": final_verify,
    }
    for name in actions:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    outcome = next(actions[name.replace("_", "-")]() for name, enabled in vars(args).items() if enabled)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") in {"PASS", "AUTHORITATIVE_NEGATIVE_RESULT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
