#!/usr/bin/env python3
"""Deterministic A+C Support agreement and frame-v2 Support Gold freeze."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import statistics
import tempfile
from collections import Counter
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

TREF = D / "phase7_3_3_d_multi_claim_successor_type_metadata_reference_frame_v3.json"
TSEAL = R / "phase7_3_3_d_multi_claim_successor_type_metadata_reference_seal_frame_v3.json"
PKT = D / "phase7_3_3_d_multi_claim_successor_support_review_packet_frame_v5.json"
SUB_A = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_a_submission_frame_v5.json"
SUB_C = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_submission_frame_v5.json"
C_RESULT = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_result_frame_v5.json"
C_REC = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_receipt_frame_v5.json"
NEG_B = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_b_negative_frame_v5.json"
CLASS_B = R / "phase7_3_3_d_multi_claim_successor_support_v5_failure_classification.json"
SI = D / "phase7_3_3_d_support_stage_state_v90.json"
RI = R / "phase7_3_3_d1_reference_construction_readiness_v101.json"

APRO = C / "phase7_3_3_d_multi_claim_successor_support_agreement_protocol_frame_v5.json"
AFIX = R / "phase7_3_3_d_multi_claim_successor_support_agreement_fixtures_frame_v5.json"
AMAN = R / "phase7_3_3_d_multi_claim_successor_support_agreement_manifest_frame_v5.json"
AREP = R / "phase7_3_3_d_multi_claim_successor_support_agreement_report_frame_v5.json"
WL = D / "phase7_3_3_d_multi_claim_successor_support_label_disagreement_worklist_frame_v5.json"
AOUT = R / "phase7_3_3_d_multi_claim_successor_support_agreement_outcome_frame_v5.json"
AREC = R / "phase7_3_3_d_multi_claim_successor_support_agreement_receipt_frame_v5.json"
ASO = D / "phase7_3_3_d_support_stage_state_v91.json"
ARO = R / "phase7_3_3_d1_reference_construction_readiness_v102.json"

GPRO = C / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_protocol_frame_v2.json"
GFIX = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_fixtures_frame_v2.json"
GMAN = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_manifest_frame_v2.json"
GOLD = D / "phase7_3_3_d_multi_claim_successor_support_gold_frame_v2.json"
GREP = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_report_frame_v2.json"
GSEAL = R / "phase7_3_3_d_multi_claim_successor_support_gold_seal_frame_v2.json"
GREC = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_receipt_frame_v2.json"
GSO = D / "phase7_3_3_d_support_stage_state_v92.json"
GRO = R / "phase7_3_3_d1_reference_construction_readiness_v103.json"

AGREE_CUR = "construct_multi_claim_successor_support_agreement_a_c_frame_v5"
ADJ_NEXT = "adjudicate_multi_claim_successor_support_label_disagreements_frame_v5"
GOLD_CUR = "freeze_multi_claim_successor_support_gold_frame_v2"
STRUCT_NEXT = "evaluate_multi_claim_successor_structural_identifiability_frame_v2"
LABELS = ["supported", "partially_supported", "unsupported", "not_assessable"]

STATIC_EXPECTED = {
    TREF: "f19845566adc324d8210a5041c5ecee2338e4bf97a549d320b257c705a6da8d8",
    TSEAL: "59954ada0b6454f18011d51516f7c9ee65fdc879671ea762e87c976ab561e0b1",
    PKT: "634759bd4840d0b7fca64727a5602bae487796d60dfb6bbd8ad597a632c518b6",
    SUB_A: "3a186b9a9be817f1e19a4c85f7c4865b07eab2b4f9ce6e5e88f14146f211e185",
    NEG_B: "be30b6ebabe61f730be897dea0863712d8cdde636d5c9337c4b9e701f62d8d77",
    CLASS_B: "a534269aef195e915541dc1fc23cbba68b814fecfb7ca782257b284ea8a88b3e",
}


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def csha(value) -> str:
    return hb(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


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


def flatten(submission):
    return [decision for case in submission["cases"] for decision in case["decisions"]]


def input_lineage_checks():
    checks = {"static_hash:" + rel(path): path.exists() and sha(path) == expected for path, expected in STATIC_EXPECTED.items()}
    for path in [SUB_C, C_RESULT, C_REC, SI, RI]:
        checks["exists:" + rel(path)] = path.exists()
    if all(checks.values()):
        receipt, result = load(C_REC), load(C_RESULT)
        state, readiness = load(SI), load(RI)
        checks.update({
            "c_submission_lineage": receipt["submission_sha256"] == result["submission_sha256"] == sha(SUB_C),
            "c_result_lineage": receipt["result_sha256"] == sha(C_RESULT),
            "state_lineage": receipt["state_sha256"] == sha(SI),
            "readiness_lineage": receipt["readiness_sha256"] == sha(RI),
            "agreement_gate": state["next_authorized_stage"] == readiness["next_authorized_stage"] == AGREE_CUR,
            "reviewer_c_complete": state["multi_claim_successor_support_v5_reviewer_c_completed"] is True,
            "reviewer_b_excluded": load(CLASS_B)["reviewer_b_submission_created"] is False,
            "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    return checks


def kappa(a, b):
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[label] * cb[label] for label in LABELS) / (n * n)
    defined = not math.isclose(expected, 1.0)
    return {
        "observed_agreement": observed,
        "chance_expected_agreement": expected,
        "cohen_kappa": (observed - expected) / (1 - expected) if defined else None,
        "kappa_defined": defined,
    }


def agreement_protocol():
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-support-agreement-a-c-frame-v5",
        "status": "frozen_before_deterministic_computation",
        "reviewer_pair": ["reviewer_a_v5", "reviewer_c_v5_supplement"],
        "reviewer_b_disposition": "authoritative_empty_content_negative_excluded_no_retry",
        "claim_count": 240,
        "labels": LABELS,
        "metrics": ["raw_label_agreement", "cohen_kappa", "confusion_matrix", "label_marginals"],
        "label_disagreement_requires_blind_adjudication": True,
        "citation_or_diagnostic_agreement_in_scope": False,
        "support_gold_created": False,
        "provider_calls": 0,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def agreement_fixtures():
    first = kappa(["supported", "unsupported"], ["supported", "unsupported"])
    second = kappa(["supported", "supported"], ["supported", "unsupported"])
    rows = [
        {"fixture_id": "perfect_agreement", "passed": first["observed_agreement"] == 1 and first["cohen_kappa"] == 1},
        {"fixture_id": "partial_agreement", "passed": second["observed_agreement"] == 0.5},
        {"fixture_id": "b_excluded", "passed": agreement_protocol()["reviewer_b_disposition"].endswith("no_retry")},
        {"fixture_id": "disagreement_requires_adjudication", "passed": agreement_protocol()["label_disagreement_requires_blind_adjudication"] is True},
    ]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-support-agreement-fixtures-frame-v5", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def agreement_manifest():
    inputs = [TREF, TSEAL, PKT, SUB_A, SUB_C, C_RESULT, C_REC, NEG_B, CLASS_B, SI, RI]
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-support-agreement-manifest-frame-v5",
        "status": "frozen_before_deterministic_computation",
        "adapter_sha256": sha(SELF),
        "protocol_sha256": sha(APRO),
        "fixtures_sha256": sha(AFIX),
        "frozen_inputs": {rel(path): sha(path) for path in inputs},
        "claim_count": 240,
        "provider_calls": 0,
    }


def agreement_preflight():
    checks = input_lineage_checks()
    checks["outputs_absent"] = all(not path.exists() for path in [APRO, AFIX, AMAN, AREP, WL, AOUT, AREC, ASO, ARO])
    if SUB_C.exists():
        a, c = flatten(load(SUB_A)), flatten(load(SUB_C))
        checks.update({
            "a_240": len(a) == 240,
            "c_240": len(c) == 240,
            "claim_order_equal": [row["reference_claim_id"] for row in a] == [row["reference_claim_id"] for row in c],
            "labels_valid": all(row["support_label"] in LABELS for row in a + c),
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def agreement_prepare():
    checked = agreement_preflight()
    if checked["status"] != "PASS":
        return checked
    protocol_hash = once(APRO, agreement_protocol())
    fixture_hash = once(AFIX, agreement_fixtures())
    manifest_hash = once(AMAN, agreement_manifest())
    return {"status": "PASS", "protocol_sha256": protocol_hash, "fixtures_sha256": fixture_hash, "manifest_sha256": manifest_hash, "provider_calls": 0}


def agreement_verify_prepare():
    checks = input_lineage_checks()
    for path in [APRO, AFIX, AMAN]:
        checks["exists:" + rel(path)] = path.exists()
    if APRO.exists() and AFIX.exists() and AMAN.exists():
        checks.update({
            "protocol_replay": load(APRO) == agreement_protocol(),
            "fixtures_replay": load(AFIX) == agreement_fixtures(),
            "manifest_replay": load(AMAN) == agreement_manifest(),
            "fixtures_pass": load(AFIX)["all_fixtures_passed"] is True,
            "outputs_absent": all(not path.exists() for path in [AREP, WL, AOUT, AREC, ASO, ARO]),
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def agreement_docs():
    a, c = flatten(load(SUB_A)), flatten(load(SUB_C))
    labels_a = [row["support_label"] for row in a]
    labels_c = [row["support_label"] for row in c]
    confusion = {x: {y: sum(aa == x and cc == y for aa, cc in zip(labels_a, labels_c)) for y in LABELS} for x in LABELS}
    disagreements = []
    claim_index = {claim["reference_claim_id"]: claim for case in load(TREF)["cases"] for claim in case["claims"]}
    for left, right in zip(a, c, strict=True):
        if left["support_label"] != right["support_label"]:
            claim = claim_index[left["reference_claim_id"]]
            disagreements.append({
                "work_item_id": f"support-frame-v5-disagreement-{len(disagreements)+1:03d}",
                "case_id": next(case["case_id"] for case in load(TREF)["cases"] if any(q["reference_claim_id"] == claim["reference_claim_id"] for q in case["claims"])),
                "reference_claim_id": claim["reference_claim_id"],
                "source_excerpt": claim["source_excerpt"],
                "reviewer_a_label": left["support_label"],
                "reviewer_c_label": right["support_label"],
                "label_adjudication_required": True,
                "claim_or_metadata_mutation_allowed": False,
            })
    metrics = kappa(labels_a, labels_c)
    report = {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-support-agreement-report-frame-v5",
        "status": "completed_deterministic_agreement_analysis",
        "manifest_sha256": sha(AMAN),
        "reviewer_pair": ["reviewer_a_v5", "reviewer_c_v5_supplement"],
        "reviewer_b_excluded": True,
        "claim_count": 240,
        "agreement_count": 240 - len(disagreements),
        "disagreement_count": len(disagreements),
        **metrics,
        "reviewer_a_label_counts": dict(sorted(Counter(labels_a).items())),
        "reviewer_c_label_counts": dict(sorted(Counter(labels_c).items())),
        "confusion_matrix": confusion,
        "provider_calls": 0,
        "support_gold_created": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    worklist = {
        "schema_version": 1,
        "worklist_id": "phase7.3.3-d-multi-claim-successor-support-label-disagreement-worklist-frame-v5",
        "status": "frozen_empty_no_adjudication_required" if not disagreements else "frozen_blind_adjudication_required",
        "work_item_count": len(disagreements),
        "items": disagreements,
        "support_gold_created": False,
    }
    return report, worklist


def agreement_compute():
    checked = agreement_verify_prepare()
    if checked["status"] != "PASS":
        return checked
    report, worklist = agreement_docs()
    report_hash, worklist_hash = once(AREP, report), once(WL, worklist)
    next_stage = GOLD_CUR if worklist["work_item_count"] == 0 else ADJ_NEXT
    outcome_hash = once(AOUT, {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-support-agreement-outcome-frame-v5",
        "status": "unanimous_support_labels" if worklist["work_item_count"] == 0 else "support_label_adjudication_required",
        "agreement_report_sha256": report_hash,
        "disagreement_worklist_sha256": worklist_hash,
        "disagreement_count": worklist["work_item_count"],
        "support_gold_created": False,
        "next_authorized_stage": next_stage,
    })
    state, readiness = copy.deepcopy(load(SI)), copy.deepcopy(load(RI))
    lineage = {
        "multi_claim_successor_support_agreement_protocol_frame_v5_sha256": sha(APRO),
        "multi_claim_successor_support_agreement_manifest_frame_v5_sha256": sha(AMAN),
        "multi_claim_successor_support_agreement_report_frame_v5_sha256": report_hash,
        "multi_claim_successor_support_label_disagreement_worklist_frame_v5_sha256": worklist_hash,
        "multi_claim_successor_support_agreement_outcome_frame_v5_sha256": outcome_hash,
    }
    update = {
        "status": "multi_claim_successor_support_agreement_a_c_frame_v5_completed",
        "next_authorized_stage": next_stage,
        "multi_claim_successor_support_agreement_a_c_frame_v5_completed": True,
        "multi_claim_successor_support_frame_v5_disagreement_count": worklist["work_item_count"],
        "multi_claim_successor_support_frame_v2_gold_created": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 91, "state_id": "phase7.3.3-d-support-stage-state-v91"})
    readiness.update({"schema_version": 102, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v102"})
    state_hash = once(ASO, state)
    readiness["artifact_lineage"]["support_stage_state_v91_sha256"] = state_hash
    readiness_hash = once(ARO, readiness)
    receipt_hash = once(AREC, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-support-agreement-receipt-frame-v5",
        "status": "PASS",
        "manifest_sha256": sha(AMAN),
        "agreement_report_sha256": report_hash,
        "disagreement_worklist_sha256": worklist_hash,
        "outcome_sha256": outcome_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "disagreement_count": worklist["work_item_count"],
        "next_authorized_stage": next_stage,
    })
    return {"status": "PASS", "agreement_count": report["agreement_count"], "disagreement_count": worklist["work_item_count"], "cohen_kappa": report["cohen_kappa"], "report_sha256": report_hash, "receipt_sha256": receipt_hash, "next_authorized_stage": next_stage}


def agreement_verify():
    paths = [APRO, AFIX, AMAN, AREP, WL, AOUT, AREC, ASO, ARO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        report, worklist = agreement_docs()
        receipt = load(AREC)
        checks.update({
            "protocol_replay": load(APRO) == agreement_protocol(),
            "fixtures_replay": load(AFIX) == agreement_fixtures(),
            "manifest_replay": load(AMAN) == agreement_manifest(),
            "report_replay": load(AREP) == report,
            "worklist_replay": load(WL) == worklist,
            "receipt_lineage": receipt["agreement_report_sha256"] == sha(AREP) and receipt["disagreement_worklist_sha256"] == sha(WL) and receipt["state_sha256"] == sha(ASO) and receipt["readiness_sha256"] == sha(ARO),
            "state_gate": load(ASO)["next_authorized_stage"] == load(ARO)["next_authorized_stage"] == load(AOUT)["next_authorized_stage"],
            "confirmatory_closed": load(ASO)["confirmatory_dataset_opened"] is False and load(ARO)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(ASO)["runtime_integration_authorized"] is False and load(ARO)["runtime_integration_authorized"] is False,
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(ASO)["next_authorized_stage"] if ASO.exists() else None}


def resolved_labels():
    a, c = flatten(load(SUB_A)), flatten(load(SUB_C))
    if any(left["support_label"] != right["support_label"] for left, right in zip(a, c, strict=True)):
        raise RuntimeError("unresolved_support_disagreement")
    return {row["reference_claim_id"]: row["support_label"] for row in a}


def gold_protocol():
    return {
        "schema_version": 2,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-support-gold-freeze-frame-v2",
        "status": "frozen_before_offline_execution",
        "gold_scope": "Support labels only for the frozen 240-Claim successor frame-v2 reference",
        "resolution_basis": "exact independent Reviewer A+C label agreement",
        "reviewer_b_disposition": "authoritative empty-content negative excluded",
        "immutability": {"claim_boundary_mutation_allowed": False, "claim_metadata_mutation_allowed": False, "support_label_recomputation_allowed": False},
        "guards": {"provider_call_allowed": False, "confirmatory_dataset_opening_allowed": False, "runtime_integration_allowed": False},
        "passing_next_stage": STRUCT_NEXT,
    }


def gold_fixtures():
    rows = [
        {"fixture_id": "zero_disagreements", "passed": load(WL)["work_item_count"] == 0},
        {"fixture_id": "agreement_240", "passed": load(AREP)["agreement_count"] == 240},
        {"fixture_id": "type_reference_240", "passed": load(TREF)["claim_count"] == 240},
        {"fixture_id": "gold_field_label_only", "passed": gold_protocol()["gold_scope"].startswith("Support labels only")},
    ]
    return {"schema_version": 2, "fixtures_id": "phase7.3.3-d-support-gold-freeze-fixtures-frame-v2", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def gold_manifest():
    inputs = [TREF, TSEAL, SUB_A, SUB_C, AREP, WL, AOUT, AREC, ASO, ARO]
    return {
        "schema_version": 2,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-support-gold-freeze-manifest-frame-v2",
        "status": "frozen_ready_for_offline_execution",
        "adapter_sha256": sha(SELF),
        "protocol_sha256": sha(GPRO),
        "fixtures_sha256": sha(GFIX),
        "frozen_inputs": {rel(path): sha(path) for path in inputs},
        "case_count": 40,
        "claim_count": 240,
        "gold_fields": ["support_label"],
        "provider_calls": 0,
        "next_authorized_stage": GOLD_CUR,
    }


def gold_doc():
    labels = resolved_labels()
    cases = []
    for source_case in load(TREF)["cases"]:
        claims = []
        for source_claim in source_case["claims"]:
            claim = copy.deepcopy(source_claim)
            claim.update({
                "support_label": labels[claim["reference_claim_id"]],
                "gold_fields": ["support_label"],
                "label_resolution_basis": "independent_reviewer_a_c_exact_agreement",
                "diagnostic_fields_gold_status": "not_gold_not_collected_in_label_only_v5",
                "boundary_mutation_performed": False,
                "metadata_mutation_performed": False,
            })
            claims.append(claim)
        cases.append({"case_id": source_case["case_id"], "claim_count": len(claims), "claims": claims})
    counts = Counter(claim["support_label"] for case in cases for claim in case["claims"])
    return {
        "schema_version": 2,
        "support_gold_id": "phase7.3.3-d-multi-claim-successor-support-gold-frame-v2",
        "status": "frozen_project_support_gold_model_reviewed_not_human_gold",
        "gold_scope": "Support labels only",
        "gold_fields": ["support_label"],
        "artifact_lineage": {"type_metadata_reference_sha256": sha(TREF), "agreement_report_sha256": sha(AREP), "agreement_receipt_sha256": sha(AREC), "freeze_manifest_sha256": sha(GMAN)},
        "case_count": len(cases),
        "claim_count": sum(case["claim_count"] for case in cases),
        "label_counts": dict(sorted(counts.items())),
        "independent_label_agreement_count": 240,
        "adjudicated_label_count": 0,
        "support_gold_frozen": True,
        "support_label_recomputation_performed": False,
        "diagnostic_fields_promoted_to_gold": False,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "cases": cases,
    }


def gold_preflight():
    checks = {"agreement_verify": agreement_verify()["status"] == "PASS"}
    if ASO.exists() and ARO.exists() and WL.exists():
        checks.update({
            "state_gate": load(ASO)["next_authorized_stage"] == GOLD_CUR,
            "readiness_gate": load(ARO)["next_authorized_stage"] == GOLD_CUR,
            "zero_disagreements": load(WL)["work_item_count"] == 0,
            "agreement_240": load(AREP)["agreement_count"] == 240,
            "outputs_absent": all(not path.exists() for path in [GPRO, GFIX, GMAN, GOLD, GREP, GSEAL, GREC, GSO, GRO]),
            "confirmatory_closed": load(ASO)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(ASO)["runtime_integration_authorized"] is False,
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def gold_prepare():
    checked = gold_preflight()
    if checked["status"] != "PASS":
        return checked
    protocol_hash = once(GPRO, gold_protocol())
    fixture_hash = once(GFIX, gold_fixtures())
    manifest_hash = once(GMAN, gold_manifest())
    return {"status": "PASS", "protocol_sha256": protocol_hash, "fixtures_sha256": fixture_hash, "manifest_sha256": manifest_hash, "provider_calls": 0}


def gold_verify_prepare():
    checks = {"agreement_verify": agreement_verify()["status"] == "PASS"}
    for path in [GPRO, GFIX, GMAN]:
        checks["exists:" + rel(path)] = path.exists()
    if GPRO.exists() and GFIX.exists() and GMAN.exists():
        checks.update({
            "protocol_replay": load(GPRO) == gold_protocol(),
            "fixtures_replay": load(GFIX) == gold_fixtures(),
            "manifest_replay": load(GMAN) == gold_manifest(),
            "fixtures_pass": load(GFIX)["all_fixtures_passed"] is True,
            "outputs_absent": all(not path.exists() for path in [GOLD, GREP, GSEAL, GREC, GSO, GRO]),
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def gold_freeze():
    checked = gold_verify_prepare()
    if checked["status"] != "PASS":
        return checked
    gold = gold_doc()
    gold_hash = once(GOLD, gold)
    report_hash = once(GREP, {
        "schema_version": 2,
        "report_id": "phase7.3.3-d-multi-claim-successor-support-gold-freeze-report-frame-v2",
        "status": "PASS",
        "manifest_sha256": sha(GMAN),
        "support_gold_sha256": gold_hash,
        "case_count": 40,
        "claim_count": 240,
        "label_counts": gold["label_counts"],
        "gold_fields": ["support_label"],
        "provider_calls": 0,
        "next_authorized_stage": STRUCT_NEXT,
    })
    seal_hash = once(GSEAL, {
        "schema_version": 2,
        "seal_id": "phase7.3.3-d-multi-claim-successor-support-gold-seal-frame-v2",
        "status": "frozen_support_label_gold_not_human_gold",
        "support_gold_sha256": gold_hash,
        "freeze_report_sha256": report_hash,
        "claim_count": 240,
        "gold_fields": ["support_label"],
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": STRUCT_NEXT,
    })
    state, readiness = copy.deepcopy(load(ASO)), copy.deepcopy(load(ARO))
    lineage = {
        "multi_claim_successor_support_gold_freeze_protocol_frame_v2_sha256": sha(GPRO),
        "multi_claim_successor_support_gold_freeze_manifest_frame_v2_sha256": sha(GMAN),
        "multi_claim_successor_support_gold_frame_v2_sha256": gold_hash,
        "multi_claim_successor_support_gold_freeze_report_frame_v2_sha256": report_hash,
        "multi_claim_successor_support_gold_seal_frame_v2_sha256": seal_hash,
    }
    update = {
        "status": "multi_claim_successor_support_gold_frame_v2_frozen_structural_identifiability_authorized",
        "next_authorized_stage": STRUCT_NEXT,
        "multi_claim_successor_support_gold_frame_v2_created": True,
        "multi_claim_successor_support_gold_frame_v2_frozen": True,
        "multi_claim_successor_support_gold_frame_v2_sha256": gold_hash,
        "multi_claim_successor_structural_identifiability_frame_v2_authorized": True,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 92, "state_id": "phase7.3.3-d-support-stage-state-v92"})
    readiness.update({"schema_version": 103, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v103"})
    state_hash = once(GSO, state)
    readiness["artifact_lineage"]["support_stage_state_v92_sha256"] = state_hash
    readiness_hash = once(GRO, readiness)
    receipt_hash = once(GREC, {
        "schema_version": 2,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-support-gold-freeze-receipt-frame-v2",
        "status": "PASS",
        "manifest_sha256": sha(GMAN),
        "support_gold_sha256": gold_hash,
        "freeze_report_sha256": report_hash,
        "seal_sha256": seal_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "claim_count": 240,
        "gold_fields": ["support_label"],
        "support_gold_frozen": True,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": STRUCT_NEXT,
    })
    return {"status": "PASS", "support_gold_sha256": gold_hash, "label_counts": gold["label_counts"], "report_sha256": report_hash, "seal_sha256": seal_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": STRUCT_NEXT}


def gold_verify():
    paths = [GPRO, GFIX, GMAN, GOLD, GREP, GSEAL, GREC, GSO, GRO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        gold = load(GOLD)
        rows = [claim for case in gold["cases"] for claim in case["claims"]]
        receipt = load(GREC)
        checks.update({
            "protocol_replay": load(GPRO) == gold_protocol(),
            "fixtures_replay": load(GFIX) == gold_fixtures(),
            "manifest_replay": load(GMAN) == gold_manifest(),
            "gold_replay": gold == gold_doc(),
            "40_cases": gold["case_count"] == len(gold["cases"]) == 40,
            "240_claims": gold["claim_count"] == len(rows) == 240,
            "label_only": gold["gold_fields"] == ["support_label"] and all(claim["gold_fields"] == ["support_label"] for claim in rows),
            "agreement_resolution_240": gold["independent_label_agreement_count"] == 240 and gold["adjudicated_label_count"] == 0,
            "receipt_lineage": receipt["support_gold_sha256"] == sha(GOLD) and receipt["freeze_report_sha256"] == sha(GREP) and receipt["seal_sha256"] == sha(GSEAL) and receipt["state_sha256"] == sha(GSO) and receipt["readiness_sha256"] == sha(GRO),
            "state_gate": load(GSO)["next_authorized_stage"] == load(GRO)["next_authorized_stage"] == STRUCT_NEXT,
            "confirmatory_closed": load(GSO)["confirmatory_dataset_opened"] is False and load(GRO)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(GSO)["runtime_integration_authorized"] is False and load(GRO)["runtime_integration_authorized"] is False,
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(GSO)["next_authorized_stage"] if GSO.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["agreement-preflight", "agreement-prepare", "agreement-verify-prepare", "agreement-compute", "agreement-verify", "gold-preflight", "gold-prepare", "gold-verify-prepare", "gold-freeze", "gold-verify"]:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    actions = {
        "agreement_preflight": agreement_preflight,
        "agreement_prepare": agreement_prepare,
        "agreement_verify_prepare": agreement_verify_prepare,
        "agreement_compute": agreement_compute,
        "agreement_verify": agreement_verify,
        "gold_preflight": gold_preflight,
        "gold_prepare": gold_prepare,
        "gold_verify_prepare": gold_verify_prepare,
        "gold_freeze": gold_freeze,
        "gold_verify": gold_verify,
    }
    outcome = next(actions[name]() for name, enabled in vars(args).items() if enabled)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
