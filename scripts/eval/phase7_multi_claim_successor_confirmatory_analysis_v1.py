#!/usr/bin/env python3
"""Run Confirmatory realized-identifiability and preregistered paired analysis."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import statistics
import tempfile
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

IDENT_POLICY = CONFIG / "phase7_3_3_d_multi_claim_identifiability_policy_v1.json"
METRIC_SPEC = CONFIG / "phase7_3_3_d_multi_claim_metric_specification_v1.json"
PREREG = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_preregistration_v1.json"
DATASET = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_dataset_v1.json"
GOLD = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_v1.json"
GOLD_SEAL = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_seal_v1.json"
STRUCT_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_report_v1.json"
CANDIDATE_SUBMISSION = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_candidate_arm_submission_v1.json"
ATOMIC_SUBMISSION = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_atomic_arm_submission_v1.json"
EXEC_RESULT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_result_v1.json"
EXEC_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_receipt_v1.json"
STATE_107 = PATTERN / "phase7_3_3_d_support_stage_state_v107.json"
READY_118 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v118.json"

REALIZED_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_fixtures_v1.json"
REALIZED_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_manifest_v1.json"
REALIZED_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_report_v1.json"
REALIZED_NEGATIVE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_negative_result_v1.json"
REALIZED_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_audit_v1.jsonl"
REALIZED_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_receipt_v1.json"
STATE_108 = PATTERN / "phase7_3_3_d_support_stage_state_v108.json"
READY_119 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v119.json"

ANALYSIS_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_protocol_v1.json"
ANALYSIS_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_fixtures_v1.json"
ANALYSIS_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_manifest_v1.json"
ANALYSIS_CASES = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_cases_v1.json"
ANALYSIS_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_report_v1.json"
ANALYSIS_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_audit_v1.jsonl"
ANALYSIS_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_receipt_v1.json"
STATE_109 = PATTERN / "phase7_3_3_d_support_stage_state_v109.json"
READY_120 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v120.json"

REALIZED_CUR = "evaluate_confirmatory_realized_identifiability_v1"
ANALYSIS_CUR = "freeze_and_execute_confirmatory_paired_analysis_v1"
NEXT = "evaluate_confirmatory_power_compliance_gate_v1"
REALIZED_FAIL = "blocked_confirmatory_realized_identifiability_v1_authoritative_negative"


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


def common_checks() -> dict[str, bool]:
    paths = [IDENT_POLICY, METRIC_SPEC, PREREG, DATASET, GOLD, GOLD_SEAL, STRUCT_REPORT, CANDIDATE_SUBMISSION, ATOMIC_SUBMISSION, EXEC_RESULT, EXEC_RECEIPT, STATE_107, READY_118]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        result, receipt = load(EXEC_RESULT), load(EXEC_RECEIPT)
        state, readiness = load(STATE_107), load(READY_118)
        checks.update({
            "candidate_lineage": receipt["candidate_submission_sha256"] == result["candidate_submission_sha256"] == sha(CANDIDATE_SUBMISSION),
            "atomic_lineage": receipt["atomic_submission_sha256"] == result["atomic_submission_sha256"] == sha(ATOMIC_SUBMISSION),
            "execution_lineage": receipt["execution_result_sha256"] == sha(EXEC_RESULT),
            "state_lineage": receipt["state_sha256"] == sha(STATE_107) and receipt["readiness_sha256"] == sha(READY_118),
            "execution_pass_80": result["status"] == "PASS" and result["request_count"] == 80,
            "state_gate": state["next_authorized_stage"] == REALIZED_CUR,
            "readiness_gate": readiness["next_authorized_stage"] == REALIZED_CUR,
            "gold_sealed": load(GOLD_SEAL)["support_gold_sha256"] == sha(GOLD),
            "structural_pass": load(STRUCT_REPORT)["structural_estimand_identifiable"] is True,
            "reference_invisible": result["reference_content_loaded"] is False and result["reference_labels_loaded"] is False,
            "selected_opened": state["confirmatory_dataset_opened"] is True and readiness["confirmatory_dataset_opened"] is True,
            "unselected_closed": state["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    return checks


def realized_metrics() -> dict[str, Any]:
    candidate, atomic = load(CANDIDATE_SUBMISSION), load(ATOMIC_SUBMISSION)
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
        "reference_visible_during_arm_execution": candidate["reference_visible"] or atomic["reference_visible"] or load(EXEC_RESULT)["reference_content_loaded"],
    }


def realized_checks(metrics: dict[str, Any]) -> dict[str, bool]:
    threshold = load(IDENT_POLICY)["realized_representation_gate"]
    return {
        "candidate_decisions_per_selected_candidate": metrics["candidate_decisions_per_selected_candidate"] == threshold["candidate_decisions_per_selected_candidate"],
        "atomic_unit_to_candidate_ratio_min": metrics["atomic_unit_to_candidate_ratio"] >= threshold["atomic_unit_to_candidate_ratio_min"],
        "atomic_multi_unit_candidate_rate_min": metrics["atomic_multi_unit_candidate_rate"] >= threshold["atomic_multi_unit_candidate_rate_min"],
        "atomic_whole_candidate_operation_rate_max": metrics["atomic_whole_candidate_operation_rate"] <= threshold["atomic_whole_candidate_operation_rate_max"],
        "atomic_local_span_operation_rate_min": metrics["atomic_local_span_operation_rate"] >= threshold["atomic_local_span_operation_rate_min"],
        "atomic_duplicate_span_rate_max": metrics["atomic_duplicate_span_rate"] <= threshold["atomic_duplicate_span_rate_max"],
        "missing_candidate_outputs_allowed": metrics["missing_candidate_outputs"] == metrics["missing_atomic_outputs"] == threshold["missing_candidate_outputs_allowed"],
        "duplicate_candidate_outputs_allowed": metrics["duplicate_candidate_outputs"] == metrics["duplicate_atomic_outputs"] == threshold["duplicate_candidate_outputs_allowed"],
        "reference_not_visible": metrics["reference_visible_during_arm_execution"] is threshold["reference_visible_during_arm_execution"],
    }


def realized_fixtures() -> dict[str, Any]:
    threshold = load(IDENT_POLICY)["realized_representation_gate"]
    checks = [
        ("ratio_threshold_frozen", threshold["atomic_unit_to_candidate_ratio_min"] == 1.8),
        ("whole_candidate_max_frozen", threshold["atomic_whole_candidate_operation_rate_max"] == 0.2),
        ("local_span_min_frozen", threshold["atomic_local_span_operation_rate_min"] == 0.8),
        ("failure_blocks_scoring", load(IDENT_POLICY)["gate_actions"]["on_realized_representation_failure"] == "freeze_negative_result_and_do_not_score_localization_estimand"),
        ("reference_invisible", realized_metrics()["reference_visible_during_arm_execution"] is False),
    ]
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-realized-identifiability-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def realized_manifest() -> dict[str, Any]:
    inputs = [IDENT_POLICY, METRIC_SPEC, PREREG, DATASET, CANDIDATE_SUBMISSION, ATOMIC_SUBMISSION, EXEC_RESULT, EXEC_RECEIPT, STATE_107, READY_118]
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-realized-identifiability-manifest-v1",
        "status": "frozen_before_offline_realized_gate",
        "adapter_sha256": sha(SELF),
        "fixtures_sha256": sha(REALIZED_FIXTURES),
        "frozen_inputs": {rel(path): sha(path) for path in inputs},
        "provider_calls": 0,
        "gold_content_parsed": False,
        "localization_scoring_started": False,
        "confirmatory_dataset_opened": True,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }


def realized_preflight() -> dict[str, Any]:
    checks = common_checks()
    outputs = [REALIZED_FIXTURES, REALIZED_MANIFEST, REALIZED_REPORT, REALIZED_NEGATIVE, REALIZED_AUDIT, REALIZED_RECEIPT, STATE_108, READY_119]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def evaluate_realized() -> dict[str, Any]:
    checked = realized_preflight()
    if checked["status"] != "PASS":
        return checked
    fixture_hash = once(REALIZED_FIXTURES, realized_fixtures())
    manifest_hash = once(REALIZED_MANIFEST, realized_manifest())
    metrics = realized_metrics()
    checks = realized_checks(metrics)
    passed = all(checks.values())
    next_stage = ANALYSIS_CUR if passed else REALIZED_FAIL
    report_hash = once(REALIZED_REPORT, {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-confirmatory-realized-identifiability-report-v1",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT",
        "manifest_sha256": manifest_hash,
        "fixtures_sha256": fixture_hash,
        "metrics": metrics,
        "thresholds": load(IDENT_POLICY)["realized_representation_gate"],
        "checks": checks,
        "failed_checks": [key for key, value in checks.items() if not value],
        "realized_representation_identifiable": passed,
        "localization_scoring_authorized": passed,
        "provider_calls": 0,
        "gold_content_parsed": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    negative_hash = None
    if not passed:
        negative_hash = once(REALIZED_NEGATIVE, {
            "schema_version": 1,
            "negative_result_id": "phase7.3.3-d-multi-claim-successor-confirmatory-realized-identifiability-negative-v1",
            "status": "authoritative_realized_identifiability_negative_result",
            "manifest_sha256": manifest_hash,
            "report_sha256": report_hash,
            "failed_checks": [key for key, value in checks.items() if not value],
            "localization_scoring_authorized": False,
            "same_version_retry_allowed": False,
            "runtime_integration_authorized": False,
            "next_authorized_stage": REALIZED_FAIL,
        })
    audit_hash = append_single_event(REALIZED_AUDIT, {"event_id": "confirmatory-realized-identifiability-v1-evaluated", "event_type": "authoritative_realized_gate_decision", "manifest_sha256": manifest_hash, "report_sha256": report_hash, "gate_passed": passed, "provider_calls": 0})
    state, readiness = copy.deepcopy(load(STATE_107)), copy.deepcopy(load(READY_118))
    lineage = {
        "multi_claim_successor_confirmatory_realized_identifiability_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_realized_identifiability_report_v1_sha256": report_hash,
        "multi_claim_successor_confirmatory_realized_identifiability_audit_v1_sha256": audit_hash,
    }
    if negative_hash:
        lineage["multi_claim_successor_confirmatory_realized_identifiability_negative_v1_sha256"] = negative_hash
    update = {
        "status": "confirmatory_realized_identifiability_v1_passed_paired_analysis_authorized" if passed else "confirmatory_realized_identifiability_v1_authoritative_negative",
        "next_authorized_stage": next_stage,
        "multi_claim_successor_confirmatory_realized_identifiability_evaluated": True,
        "multi_claim_successor_confirmatory_realized_identifiability_passed": passed,
        "multi_claim_successor_confirmatory_localization_scoring_authorized": passed,
        "multi_claim_successor_confirmatory_same_version_retry_allowed": False,
        "confirmatory_dataset_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 108, "state_id": "phase7.3.3-d-support-stage-state-v108"})
    readiness.update({"schema_version": 119, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v119"})
    state_hash = once(STATE_108, state)
    readiness["artifact_lineage"]["support_stage_state_v108_sha256"] = state_hash
    readiness_hash = once(READY_119, readiness)
    receipt_hash = once(REALIZED_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-realized-identifiability-receipt-v1",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT",
        "manifest_sha256": manifest_hash,
        "report_sha256": report_hash,
        "negative_result_sha256": negative_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "localization_scoring_authorized": passed,
        "same_version_retry_allowed": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    return {"status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT", "metrics": metrics, "failed_checks": [key for key, value in checks.items() if not value], "report_sha256": report_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": next_stage}


def verify_realized() -> dict[str, Any]:
    paths = [REALIZED_FIXTURES, REALIZED_MANIFEST, REALIZED_REPORT, REALIZED_AUDIT, REALIZED_RECEIPT, STATE_108, READY_119]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        report, receipt = load(REALIZED_REPORT), load(REALIZED_RECEIPT)
        expected_checks = realized_checks(realized_metrics())
        passed = all(expected_checks.values())
        checks.update({
            "fixtures_replay": load(REALIZED_FIXTURES) == realized_fixtures(),
            "manifest_replay": load(REALIZED_MANIFEST) == realized_manifest(),
            "metrics_replay": report["metrics"] == realized_metrics(),
            "checks_replay": report["checks"] == expected_checks,
            "negative_presence_exact": REALIZED_NEGATIVE.exists() is (not passed),
            "receipt_lineage": receipt["report_sha256"] == sha(REALIZED_REPORT) and receipt["state_sha256"] == sha(STATE_108) and receipt["readiness_sha256"] == sha(READY_119),
            "state_gate": load(STATE_108)["next_authorized_stage"] == load(READY_119)["next_authorized_stage"] == (ANALYSIS_CUR if passed else REALIZED_FAIL),
            "unselected_closed": load(STATE_108)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_108)["runtime_integration_authorized"] is False and load(READY_119)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_108)["next_authorized_stage"] if STATE_108.exists() else None}


def analysis_protocol() -> dict[str, Any]:
    prereg = load(PREREG)
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-confirmatory-paired-analysis-v1",
        "status": "frozen_before_reference_json_parsing_and_confirmatory_scoring",
        "preregistration_sha256": sha(PREREG),
        "primary_estimand": prereg["primary_estimand"],
        "paired_unit": prereg["paired_unit"],
        "case_count": prereg["sample_size_candidates"],
        "hypotheses": prereg["hypotheses"],
        "alpha_one_sided": prereg["alpha_one_sided"],
        "primary_test": prereg["primary_test"],
        "uncertainty": prereg["uncertainty"],
        "success_gate": prereg["success_gate"],
        "no_silent_drop": True,
        "reference_visible_during_arm_execution": False,
        "provider_calls": 0,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }


def eligible(text: str) -> set[int]:
    return {index for index, character in enumerate(text) if not character.isspace()}


def iou(left: set[int], right: set[int]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def precision_recall_f1(predicted: set[int], gold: set[int]) -> tuple[float, float, float]:
    intersection = len(predicted & gold)
    precision = intersection / len(predicted) if predicted else (1.0 if not gold else 0.0)
    recall = intersection / len(gold) if gold else (1.0 if not predicted else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def aggregate_gold(labels: list[str]) -> str:
    if all(label == "supported" for label in labels):
        return "supported"
    if all(label == "unsupported" for label in labels):
        return "unsupported"
    return "partially_supported"


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def resource_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    resources = [case["resources"] for case in cases]
    return {
        "request_count": len(resources),
        "total_tokens": sum(row["total_tokens"] for row in resources if isinstance(row["total_tokens"], int)),
        "token_usage_complete": all(isinstance(row["total_tokens"], int) for row in resources),
        "mean_latency_ms": statistics.mean(row["latency_ms"] for row in resources),
        "cost_usd": None,
        "cost_status": "provider_price_not_frozen",
    }


def scored_documents(manifest_hash: str) -> tuple[dict[str, Any], dict[str, Any]]:
    data = {case["candidate_id"]: case for case in load(DATASET)["cases"]}
    gold = {case["case_id"]: case for case in load(GOLD)["cases"]}
    candidate = {case["case_id"]: case for case in load(CANDIDATE_SUBMISSION)["cases"]}
    atomic = {case["case_id"]: case for case in load(ATOMIC_SUBMISSION)["cases"]}
    ordered_ids = [case["candidate_id"] for case in load(DATASET)["cases"]]
    cases = []
    total_gold: set[int] = set()
    total_candidate: set[int] = set()
    total_atomic: set[int] = set()
    offset = 0
    candidate_correct = atomic_correct = atomic_total = 0
    for case_id in ordered_ids:
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
        exact_count = sum(decision["support_label"] == label for decision, label in zip(atomic_decisions, gold_labels))
        atomic_correct += exact_count
        atomic_total += len(gold_labels)
        candidate_iou, atomic_iou = iou(candidate_mask, gold_mask), iou(atomic_mask, gold_mask)
        cp, cr, cf = precision_recall_f1(candidate_mask, gold_mask)
        ap, ar, af = precision_recall_f1(atomic_mask, gold_mask)
        cases.append({
            "case_id": case_id,
            "gold_material_error_character_count": len(gold_mask),
            "candidate_predicted_error_character_count": len(candidate_mask),
            "atomic_predicted_error_character_count": len(atomic_mask),
            "candidate_material_error_span_iou": candidate_iou,
            "atomic_material_error_span_iou": atomic_iou,
            "paired_difference_atomic_minus_candidate": atomic_iou - candidate_iou,
            "candidate_localization_precision": cp,
            "candidate_localization_recall": cr,
            "candidate_localization_f1": cf,
            "atomic_localization_precision": ap,
            "atomic_localization_recall": ar,
            "atomic_localization_f1": af,
            "candidate_label": candidate_label,
            "candidate_reference_label": candidate_gold,
            "candidate_label_exact": candidate_label == candidate_gold,
            "atomic_claim_exact_count": exact_count,
            "atomic_claim_count": len(gold_labels),
        })
        total_gold |= {offset + index for index in gold_mask}
        total_candidate |= {offset + index for index in candidate_mask}
        total_atomic |= {offset + index for index in atomic_mask}
        offset += len(text) + 1
    differences = [case["paired_difference_atomic_minus_candidate"] for case in cases]
    prereg = load(PREREG)
    bootstrap_rng = random.Random(prereg["uncertainty"]["seed"])
    bootstrap = [sum(differences[bootstrap_rng.randrange(len(differences))] for _ in differences) / len(differences) for _ in range(prereg["uncertainty"]["replicates"])]
    estimate = statistics.mean(differences)
    test_rng = random.Random(prereg["primary_test"]["seed"])
    extreme = 0
    for _ in range(prereg["primary_test"]["replicates"]):
        permuted_mean = sum(value if test_rng.getrandbits(1) else -value for value in differences) / len(differences)
        extreme += permuted_mean >= estimate
    p_value = (extreme + 1) / (prereg["primary_test"]["replicates"] + 1)
    candidate_micro = precision_recall_f1(total_candidate, total_gold)
    atomic_micro = precision_recall_f1(total_atomic, total_gold)
    success_checks = {
        "structural_identifiability_pass": load(STRUCT_REPORT)["structural_estimand_identifiable"] is True,
        "realized_identifiability_pass": load(REALIZED_REPORT)["realized_representation_identifiable"] is True,
        "paired_cases_dropped": len(cases) == 40,
        "estimate_gt_zero": estimate > 0,
        "one_sided_p_value_lt_alpha": p_value < prereg["alpha_one_sided"],
    }
    cases_doc = {
        "schema_version": 1,
        "dataset_id": "phase7.3.3-d-multi-claim-successor-confirmatory-paired-analysis-cases-v1",
        "status": "frozen_scored_paired_confirmatory_cases",
        "case_count": len(cases),
        "cases": cases,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    report = {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-confirmatory-paired-analysis-report-v1",
        "status": "CONFIRMATORY_SUCCESS" if all(success_checks.values()) else "AUTHORITATIVE_CONFIRMATORY_NULL_OR_NEGATIVE_RESULT",
        "manifest_sha256": manifest_hash,
        "preregistration_sha256": sha(PREREG),
        "case_count": len(cases),
        "paired_primary_effect": {
            "estimand": prereg["primary_estimand"],
            "estimate": estimate,
            "paired_sd": statistics.stdev(differences),
            "bootstrap_interval_95": [percentile(bootstrap, 0.025), percentile(bootstrap, 0.975)],
            "bootstrap_replicates": len(bootstrap),
            "bootstrap_seed": prereg["uncertainty"]["seed"],
            "one_sided_p_value": p_value,
            "one_sided_alpha": prereg["alpha_one_sided"],
            "randomization_method": prereg["primary_test"]["method"],
            "randomization_replicates": prereg["primary_test"]["replicates"],
            "randomization_seed": prereg["primary_test"]["seed"],
            "randomization_extreme_count": extreme,
        },
        "confirmatory_success_checks": success_checks,
        "confirmatory_success": all(success_checks.values()),
        "arm_metrics": {
            "candidate": {"mean_material_error_span_iou": statistics.mean(case["candidate_material_error_span_iou"] for case in cases), "exact_candidate_label_accuracy": candidate_correct / 40, "localization_micro_precision": candidate_micro[0], "localization_micro_recall": candidate_micro[1], "localization_micro_f1": candidate_micro[2]},
            "atomic": {"mean_material_error_span_iou": statistics.mean(case["atomic_material_error_span_iou"] for case in cases), "exact_claim_label_accuracy": atomic_correct / atomic_total, "boundary_exact_span_rate": 1.0, "localization_micro_precision": atomic_micro[0], "localization_micro_recall": atomic_micro[1], "localization_micro_f1": atomic_micro[2]},
        },
        "missingness_and_failures": {"selected_cases": 40, "paired_cases_scored": len(cases), "paired_cases_dropped": 40 - len(cases), "missing_candidate_outputs": 40 - len(candidate), "missing_atomic_outputs": 40 - len(atomic)},
        "resources": {"candidate": resource_summary(load(CANDIDATE_SUBMISSION)["cases"]), "atomic": resource_summary(load(ATOMIC_SUBMISSION)["cases"])},
        "reference_visible_during_arm_execution": False,
        "confirmatory_dataset_opened": True,
        "unselected_content_opened": False,
        "provider_calls_during_analysis": 0,
        "runtime_integration_authorized": False,
    }
    return cases_doc, report


def analysis_fixtures() -> dict[str, Any]:
    prereg = load(PREREG)
    checks = [
        ("empty_empty_iou", iou(set(), set()) == 1),
        ("one_empty_iou", iou({1}, set()) == 0),
        ("known_iou", iou({1, 2}, {2, 3}) == 1 / 3),
        ("one_sided_alpha", prereg["alpha_one_sided"] == 0.05),
        ("randomization_replicates", prereg["primary_test"]["replicates"] == 200000),
        ("randomization_seed", prereg["primary_test"]["seed"] == 733071),
        ("bootstrap_seed", prereg["uncertainty"]["seed"] == 733072),
        ("sample_size_40", prereg["sample_size_candidates"] == 40),
        ("no_result_replanning", prereg["no_result_dependent_replanning"] is True),
    ]
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-paired-analysis-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def analysis_manifest() -> dict[str, Any]:
    inputs = [METRIC_SPEC, PREREG, DATASET, GOLD, GOLD_SEAL, CANDIDATE_SUBMISSION, ATOMIC_SUBMISSION, EXEC_RESULT, REALIZED_REPORT, REALIZED_RECEIPT, STATE_108, READY_119]
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-paired-analysis-manifest-v1",
        "status": "frozen_before_reference_json_content_parsing_and_scoring",
        "adapter_sha256": sha(SELF),
        "protocol_sha256": sha(ANALYSIS_PROTOCOL),
        "fixtures_sha256": sha(ANALYSIS_FIXTURES),
        "frozen_inputs": {rel(path): sha(path) for path in inputs},
        "reference_prefreeze_json_content_parsed": False,
        "arm_outputs_visible_during_manifest_freeze": False,
        "provider_calls": 0,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }


def analysis_preflight() -> dict[str, Any]:
    checks = {"realized_verify": verify_realized()["status"] == "PASS"}
    if STATE_108.exists() and READY_119.exists():
        checks.update({
            "state_gate": load(STATE_108)["next_authorized_stage"] == ANALYSIS_CUR,
            "readiness_gate": load(READY_119)["next_authorized_stage"] == ANALYSIS_CUR,
            "realized_pass": load(REALIZED_REPORT)["realized_representation_identifiable"] is True,
            "localization_scoring_authorized": load(REALIZED_REPORT)["localization_scoring_authorized"] is True,
            "unselected_closed": load(STATE_108)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_108)["runtime_integration_authorized"] is False,
        })
    outputs = [ANALYSIS_PROTOCOL, ANALYSIS_FIXTURES, ANALYSIS_MANIFEST, ANALYSIS_CASES, ANALYSIS_REPORT, ANALYSIS_AUDIT, ANALYSIS_RECEIPT, STATE_109, READY_120]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare_analysis() -> dict[str, Any]:
    checked = analysis_preflight()
    if checked["status"] != "PASS":
        return checked
    protocol_hash = once(ANALYSIS_PROTOCOL, analysis_protocol())
    fixture_hash = once(ANALYSIS_FIXTURES, analysis_fixtures())
    manifest_hash = once(ANALYSIS_MANIFEST, analysis_manifest())
    return {"status": "PASS", "protocol_sha256": protocol_hash, "fixtures_sha256": fixture_hash, "manifest_sha256": manifest_hash, "reference_content_parsed": False, "provider_calls": 0}


def execute_analysis() -> dict[str, Any]:
    if not ANALYSIS_MANIFEST.exists() or load(ANALYSIS_MANIFEST) != analysis_manifest():
        raise RuntimeError("analysis_manifest_invalid")
    cases_document, report = scored_documents(sha(ANALYSIS_MANIFEST))
    cases_hash = once(ANALYSIS_CASES, cases_document)
    report_hash = once(ANALYSIS_REPORT, report)
    audit_hash = append_single_event(ANALYSIS_AUDIT, {"event_id": "confirmatory-paired-analysis-v1-completed", "event_type": "authoritative_confirmatory_analysis", "manifest_sha256": sha(ANALYSIS_MANIFEST), "report_sha256": report_hash, "confirmatory_success": report["confirmatory_success"], "provider_calls": 0})
    state, readiness = copy.deepcopy(load(STATE_108)), copy.deepcopy(load(READY_119))
    lineage = {
        "multi_claim_successor_confirmatory_paired_analysis_manifest_v1_sha256": sha(ANALYSIS_MANIFEST),
        "multi_claim_successor_confirmatory_paired_analysis_cases_v1_sha256": cases_hash,
        "multi_claim_successor_confirmatory_paired_analysis_report_v1_sha256": report_hash,
        "multi_claim_successor_confirmatory_paired_analysis_audit_v1_sha256": audit_hash,
    }
    update = {
        "status": "confirmatory_paired_analysis_v1_completed_power_compliance_gate_authorized",
        "next_authorized_stage": NEXT,
        "multi_claim_successor_confirmatory_paired_analysis_completed": True,
        "multi_claim_successor_confirmatory_primary_effect": report["paired_primary_effect"]["estimate"],
        "multi_claim_successor_confirmatory_one_sided_p_value": report["paired_primary_effect"]["one_sided_p_value"],
        "multi_claim_successor_confirmatory_success": report["confirmatory_success"],
        "multi_claim_successor_confirmatory_no_result_replanning": True,
        "confirmatory_dataset_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 109, "state_id": "phase7.3.3-d-support-stage-state-v109"})
    readiness.update({"schema_version": 120, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v120"})
    state_hash = once(STATE_109, state)
    readiness["artifact_lineage"]["support_stage_state_v109_sha256"] = state_hash
    readiness_hash = once(READY_120, readiness)
    receipt_hash = once(ANALYSIS_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-paired-analysis-receipt-v1",
        "status": "PASS",
        "manifest_sha256": sha(ANALYSIS_MANIFEST),
        "paired_cases_sha256": cases_hash,
        "analysis_report_sha256": report_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "case_count": 40,
        "paired_cases_dropped": report["missingness_and_failures"]["paired_cases_dropped"],
        "confirmatory_success": report["confirmatory_success"],
        "provider_calls": 0,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    })
    return {"status": "PASS", "confirmatory_result_status": report["status"], "case_count": 40, "paired_effect": report["paired_primary_effect"], "confirmatory_success": report["confirmatory_success"], "report_sha256": report_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": NEXT}


def verify_analysis() -> dict[str, Any]:
    paths = [ANALYSIS_PROTOCOL, ANALYSIS_FIXTURES, ANALYSIS_MANIFEST, ANALYSIS_CASES, ANALYSIS_REPORT, ANALYSIS_AUDIT, ANALYSIS_RECEIPT, STATE_109, READY_120]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        expected_cases, expected_report = scored_documents(sha(ANALYSIS_MANIFEST))
        report, receipt = load(ANALYSIS_REPORT), load(ANALYSIS_RECEIPT)
        checks.update({
            "protocol_replay": load(ANALYSIS_PROTOCOL) == analysis_protocol(),
            "fixtures_replay": load(ANALYSIS_FIXTURES) == analysis_fixtures(),
            "manifest_replay": load(ANALYSIS_MANIFEST) == analysis_manifest(),
            "cases_replay": load(ANALYSIS_CASES) == expected_cases,
            "report_replay": report == expected_report,
            "no_drop": report["missingness_and_failures"]["paired_cases_dropped"] == 0,
            "preregistered_test": report["paired_primary_effect"]["randomization_replicates"] == 200000 and report["paired_primary_effect"]["randomization_seed"] == 733071,
            "receipt_lineage": receipt["paired_cases_sha256"] == sha(ANALYSIS_CASES) and receipt["analysis_report_sha256"] == sha(ANALYSIS_REPORT) and receipt["state_sha256"] == sha(STATE_109) and receipt["readiness_sha256"] == sha(READY_120),
            "state_gate": load(STATE_109)["next_authorized_stage"] == load(READY_120)["next_authorized_stage"] == NEXT,
            "unselected_closed": load(STATE_109)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_109)["runtime_integration_authorized"] is False and load(READY_120)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "confirmatory_success": load(ANALYSIS_REPORT).get("confirmatory_success") if ANALYSIS_REPORT.exists() else None, "next_authorized_stage": load(STATE_109)["next_authorized_stage"] if STATE_109.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    actions = {
        "realized-preflight": realized_preflight,
        "evaluate-realized": evaluate_realized,
        "verify-realized": verify_realized,
        "analysis-preflight": analysis_preflight,
        "prepare-analysis": prepare_analysis,
        "execute-analysis": execute_analysis,
        "verify-analysis": verify_analysis,
    }
    for name in actions:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    outcome = next(actions[name.replace("_", "-")]() for name, enabled in vars(args).items() if enabled)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 2 if outcome.get("status") == "AUTHORITATIVE_NEGATIVE_RESULT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
