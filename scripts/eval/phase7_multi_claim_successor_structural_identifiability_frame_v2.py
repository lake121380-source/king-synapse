#!/usr/bin/env python3
"""Evaluate the inherited structural-identifiability gate on frame v2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
import tempfile
from collections import Counter
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

POL = C / "phase7_3_3_d_multi_claim_identifiability_policy_v1.json"
MET = C / "phase7_3_3_d_multi_claim_metric_specification_v1.json"
RQ = C / "phase7_3_3_d_multi_claim_successor_research_question_v1.json"
DESIGN = C / "phase7_3_3_d_multi_claim_successor_sampling_frame_v2_design_protocol.json"
SEL = D / "phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json"
GOLD = D / "phase7_3_3_d_multi_claim_successor_support_gold_frame_v2.json"
GSEAL = R / "phase7_3_3_d_multi_claim_successor_support_gold_seal_frame_v2.json"
GREC = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_receipt_frame_v2.json"
SI = D / "phase7_3_3_d_support_stage_state_v92.json"
RI = R / "phase7_3_3_d1_reference_construction_readiness_v103.json"

FIX = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_fixtures_frame_v2.json"
MAN = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_manifest_frame_v2.json"
REPORT = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_report_frame_v2.json"
NEG = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_negative_result_frame_v2.json"
REC = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_receipt_frame_v2.json"
SO = D / "phase7_3_3_d_support_stage_state_v93.json"
RO = R / "phase7_3_3_d1_reference_construction_readiness_v104.json"

CUR = "evaluate_multi_claim_successor_structural_identifiability_frame_v2"
PASS_NEXT = "freeze_multi_claim_successor_candidate_atomic_pilot_protocol_frame_v2"
FAIL_NEXT = "blocked_frame_v2_structural_identifiability_authoritative_negative"
STATIC = {
    POL: "4fdff3226798cb7c14c0b2cf053ae08700e4c2d03247468d42c71eb025268af6",
    MET: "16e919ba0219fae008581f2d441c755e2a3f3f4eb1b6111d46b6e1c6dcec1113",
    RQ: "bee33d10c4396cde8e767ffac2aeb4a7aff442ac595acf7d67de28cae5ce022f",
    SEL: "788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe",
}


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


def input_checks():
    checks = {"static_hash:" + rel(path): path.exists() and sha(path) == expected for path, expected in STATIC.items()}
    for path in [DESIGN, GOLD, GSEAL, GREC, SI, RI]:
        checks["exists:" + rel(path)] = path.exists()
    if all(checks.values()):
        receipt, seal = load(GREC), load(GSEAL)
        state, readiness = load(SI), load(RI)
        checks.update({
            "gold_lineage": receipt["support_gold_sha256"] == seal["support_gold_sha256"] == sha(GOLD),
            "seal_lineage": receipt["seal_sha256"] == sha(GSEAL),
            "state_lineage": receipt["state_sha256"] == sha(SI),
            "readiness_lineage": receipt["readiness_sha256"] == sha(RI),
            "state_gate": state["next_authorized_stage"] == CUR,
            "readiness_gate": readiness["next_authorized_stage"] == CUR,
            "gold_frozen": load(GOLD)["support_gold_frozen"] is True and state["multi_claim_successor_support_gold_frame_v2_frozen"] is True,
            "thresholds_inherited": load(DESIGN)["prospective_contract"]["thresholds_inherited_without_relaxation"] is True,
            "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    return checks


def metrics():
    selected = load(SEL)
    gold = load(GOLD)
    selected_by_id = {case["candidate_id"]: case for case in selected["cases"]}
    cases = gold["cases"]
    claim_counts = [len(case["claims"]) for case in cases]
    labels = [claim["support_label"] for case in cases for claim in case["claims"]]
    label_counts = Counter(labels)
    claim_count = len(labels)
    heterogeneous = sum(len({claim["support_label"] for claim in case["claims"]}) > 1 for case in cases)
    support_and_error = sum(
        any(claim["support_label"] == "supported" for claim in case["claims"])
        and any(claim["support_label"] in {"partially_supported", "unsupported"} for claim in case["claims"])
        for case in cases
    )
    gaps = overlaps = 0
    for case in cases:
        text = selected_by_id[case["case_id"]]["candidate_text"]
        coverage = [0] * len(text)
        for claim in case["claims"]:
            for index in range(claim["source_span"]["start"], claim["source_span"]["end"]):
                coverage[index] += 1
        gaps += sum(not character.isspace() and coverage[index] == 0 for index, character in enumerate(text))
        overlaps += sum(not character.isspace() and coverage[index] > 1 for index, character in enumerate(text))
    return {
        "selected_candidate_count": len(cases),
        "unique_candidate_rate": len({case["case_id"] for case in cases}) / len(cases),
        "median_reference_claims_per_candidate": statistics.median(claim_counts),
        "multi_claim_candidate_rate": sum(count >= 2 for count in claim_counts) / len(claim_counts),
        "reference_claim_to_candidate_ratio": claim_count / len(cases),
        "within_candidate_label_heterogeneity_rate": heterogeneous / len(cases),
        "supported_plus_material_error_candidate_rate": support_and_error / len(cases),
        "material_error_claim_rate": (label_counts["partially_supported"] + label_counts["unsupported"]) / claim_count,
        "unsupported_claim_rate": label_counts["unsupported"] / claim_count,
        "partially_supported_claim_rate": label_counts["partially_supported"] / claim_count,
        "maximum_single_label_share": max(label_counts.values()) / claim_count,
        "eligible_gap_characters": gaps,
        "overlap_characters": overlaps,
        "case_count": len(cases),
        "claim_count": claim_count,
        "label_counts": dict(sorted(label_counts.items())),
    }


def evaluate(observed):
    threshold = load(POL)["structural_reference_gate"]
    checks = {
        "minimum_selected_candidate_count": observed["selected_candidate_count"] >= threshold["minimum_selected_candidate_count"],
        "target_selected_candidate_count": observed["selected_candidate_count"] == threshold["target_selected_candidate_count"],
        "unique_candidate_rate_min": observed["unique_candidate_rate"] >= threshold["unique_candidate_rate_min"],
        "median_reference_claims_per_candidate_min": observed["median_reference_claims_per_candidate"] >= threshold["median_reference_claims_per_candidate_min"],
        "multi_claim_candidate_rate_min": observed["multi_claim_candidate_rate"] >= threshold["multi_claim_candidate_rate_min"],
        "reference_claim_to_candidate_ratio_min": observed["reference_claim_to_candidate_ratio"] >= threshold["reference_claim_to_candidate_ratio_min"],
        "within_candidate_label_heterogeneity_rate_min": observed["within_candidate_label_heterogeneity_rate"] >= threshold["within_candidate_label_heterogeneity_rate_min"],
        "supported_plus_material_error_candidate_rate_min": observed["supported_plus_material_error_candidate_rate"] >= threshold["supported_plus_material_error_candidate_rate_min"],
        "material_error_claim_rate_min": observed["material_error_claim_rate"] >= threshold["material_error_claim_rate_min"],
        "unsupported_claim_rate_min": observed["unsupported_claim_rate"] >= threshold["unsupported_claim_rate_min"],
        "partially_supported_claim_rate_min": observed["partially_supported_claim_rate"] >= threshold["partially_supported_claim_rate_min"],
        "maximum_single_label_share": observed["maximum_single_label_share"] <= threshold["maximum_single_label_share"],
        "eligible_gap_characters_required": observed["eligible_gap_characters"] == threshold["eligible_gap_characters_required"],
        "overlap_characters_required": observed["overlap_characters"] == threshold["overlap_characters_required"],
    }
    return checks, [name for name, passed in checks.items() if not passed]


def fixtures():
    threshold = load(POL)["structural_reference_gate"]
    rows = [
        {"fixture_id": "all_checks_required", "passed": load(POL)["all_checks_required"] is True},
        {"fixture_id": "threshold_hash_inherited", "passed": load(DESIGN)["prospective_contract"]["thresholds_inherited_without_relaxation"] is True},
        {"fixture_id": "partial_threshold_unchanged", "passed": threshold["partially_supported_claim_rate_min"] == 0.1},
        {"fixture_id": "maximum_share_unchanged", "passed": threshold["maximum_single_label_share"] == 0.7},
        {"fixture_id": "failure_blocks_arms", "passed": load(POL)["gate_actions"]["on_structural_failure"] == "freeze_negative_result_and_do_not_execute_arms"},
    ]
    return {"schema_version": 2, "fixtures_id": "phase7.3.3-d-structural-identifiability-fixtures-frame-v2", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def manifest():
    inputs = [POL, MET, RQ, DESIGN, SEL, GOLD, GSEAL, GREC, SI, RI]
    return {
        "schema_version": 2,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-structural-identifiability-manifest-frame-v2",
        "status": "frozen_ready_for_offline_gate",
        "adapter_sha256": sha(SELF),
        "fixtures_sha256": sha(FIX),
        "frozen_inputs": {rel(path): sha(path) for path in inputs},
        "policy_sha256": sha(POL),
        "target_estimand": load(POL)["target_estimand"],
        "all_checks_required": True,
        "same_version_retry_allowed": False,
        "provider_calls": 0,
        "next_authorized_stage": CUR,
    }


def preflight():
    checks = input_checks()
    checks["outputs_absent"] = all(not path.exists() for path in [FIX, MAN, REPORT, NEG, REC, SO, RO])
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare():
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    fixture_hash = once(FIX, fixtures())
    manifest_hash = once(MAN, manifest())
    return {"status": "PASS", "fixtures_sha256": fixture_hash, "manifest_sha256": manifest_hash, "provider_calls": 0}


def execute():
    if not MAN.exists() or load(MAN) != manifest():
        raise RuntimeError("manifest_invalid")
    observed = metrics()
    checks, failed = evaluate(observed)
    passed = not failed
    report_hash = once(REPORT, {
        "schema_version": 2,
        "report_id": "phase7.3.3-d-multi-claim-successor-structural-identifiability-report-frame-v2",
        "status": "PASS" if passed else "FAIL",
        "manifest_sha256": sha(MAN),
        "target_estimand": load(POL)["target_estimand"],
        "metrics": observed,
        "thresholds": load(POL)["structural_reference_gate"],
        "checks": checks,
        "failed_checks": failed,
        "all_checks_required": True,
        "structural_estimand_identifiable": passed,
        "arm_execution_authorized": passed,
        "confirmatory_opening_authorized": False,
        "provider_calls": 0,
    })
    next_stage = PASS_NEXT if passed else FAIL_NEXT
    negative_hash = None
    if not passed:
        negative_hash = once(NEG, {
            "schema_version": 2,
            "negative_result_id": "phase7.3.3-d-multi-claim-successor-structural-identifiability-negative-result-frame-v2",
            "status": "authoritative_structural_identifiability_negative_result",
            "manifest_sha256": sha(MAN),
            "report_sha256": report_hash,
            "failed_checks": failed,
            "failure_attribution": "frozen_frame_v2_sampling_and_reference_label_composition",
            "model_capability_conclusion_authorized": False,
            "arm_execution_authorized": False,
            "same_version_retry_allowed": False,
            "confirmatory_dataset_opened": False,
            "runtime_integration_authorized": False,
            "next_authorized_stage": next_stage,
        })
    state, readiness = copy.deepcopy(load(SI)), copy.deepcopy(load(RI))
    lineage = {
        "multi_claim_successor_structural_identifiability_manifest_frame_v2_sha256": sha(MAN),
        "multi_claim_successor_structural_identifiability_report_frame_v2_sha256": report_hash,
    }
    if negative_hash:
        lineage["multi_claim_successor_structural_identifiability_negative_frame_v2_sha256"] = negative_hash
    update = {
        "status": "multi_claim_successor_structural_identifiability_frame_v2_passed_pilot_protocol_authorized" if passed else "multi_claim_successor_structural_identifiability_frame_v2_authoritative_negative",
        "next_authorized_stage": next_stage,
        "multi_claim_successor_structural_identifiability_frame_v2_evaluated": True,
        "multi_claim_successor_structural_identifiability_frame_v2_passed": passed,
        "multi_claim_successor_arm_execution_frame_v2_authorized": passed,
        "multi_claim_successor_structural_identifiability_frame_v2_negative_preserved": not passed,
        "multi_claim_successor_structural_identifiability_frame_v2_same_version_retry_allowed": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 93, "state_id": "phase7.3.3-d-support-stage-state-v93"})
    readiness.update({"schema_version": 104, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v104"})
    state_hash = once(SO, state)
    readiness["artifact_lineage"]["support_stage_state_v93_sha256"] = state_hash
    readiness_hash = once(RO, readiness)
    receipt_hash = once(REC, {
        "schema_version": 2,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-structural-identifiability-receipt-frame-v2",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT",
        "manifest_sha256": sha(MAN),
        "report_sha256": report_hash,
        "negative_result_sha256": negative_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "structural_estimand_identifiable": passed,
        "arm_execution_authorized": passed,
        "same_version_retry_allowed": False,
        "next_authorized_stage": next_stage,
    })
    return {"status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT", "metrics": observed, "failed_checks": failed, "report_sha256": report_hash, "negative_result_sha256": negative_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "arm_execution_authorized": passed, "next_authorized_stage": next_stage}


def verify():
    paths = [FIX, MAN, REPORT, REC, SO, RO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        report, receipt = load(REPORT), load(REC)
        observed = metrics()
        gate_checks, failed_gate = evaluate(observed)
        passed = not failed_gate
        checks.update({
            "inputs_unchanged": all(input_checks().values()),
            "fixtures_replay": load(FIX) == fixtures(),
            "manifest_replay": load(MAN) == manifest(),
            "metrics_replay": report["metrics"] == observed,
            "checks_replay": report["checks"] == gate_checks and report["failed_checks"] == failed_gate,
            "negative_presence_exact": NEG.exists() is (not passed),
            "receipt_lineage": receipt["report_sha256"] == sha(REPORT) and receipt["state_sha256"] == sha(SO) and receipt["readiness_sha256"] == sha(RO),
            "authorization_consistent": report["arm_execution_authorized"] is passed and load(SO)["multi_claim_successor_arm_execution_frame_v2_authorized"] is passed,
            "next_gate": load(SO)["next_authorized_stage"] == load(RO)["next_authorized_stage"] == (PASS_NEXT if passed else FAIL_NEXT),
            "confirmatory_closed": load(SO)["confirmatory_dataset_opened"] is False and load(RO)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(SO)["runtime_integration_authorized"] is False and load(RO)["runtime_integration_authorized"] is False,
        })
        if NEG.exists():
            checks["negative_lineage"] = receipt["negative_result_sha256"] == sha(NEG)
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "terminal_outcome": "pass" if REPORT.exists() and load(REPORT)["status"] == "PASS" else "authoritative_negative_result" if NEG.exists() else None, "next_authorized_stage": load(SO)["next_authorized_stage"] if SO.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["preflight", "fixtures", "prepare", "execute", "verify"]:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    if args.preflight:
        outcome = preflight()
    elif args.fixtures:
        outcome = fixtures()
        outcome["status"] = "PASS" if outcome["all_fixtures_passed"] else "FAIL"
    elif args.prepare:
        outcome = prepare()
    elif args.execute:
        outcome = execute()
    else:
        outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") in {"PASS", "AUTHORITATIVE_NEGATIVE_RESULT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
