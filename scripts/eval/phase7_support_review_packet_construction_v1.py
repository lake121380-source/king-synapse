#!/usr/bin/env python3
"""Deterministic Phase 7.3.3-D1-B Support Review Packet Construction Gate v1."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

PROTOCOL = CONFIG / "phase7_3_3_d_support_review_packet_construction_protocol_v1.json"
SUPPORT_PROTOCOL = DATA / "phase7_3_3_d_support_reference_protocol_v1.json"
EVIDENCE_SOURCE = DATA / "phase7_3_1_blind_review_packet.json"
BOUNDARY_GOLD = DATA / "phase7_3_3_d_boundary_gold_v1.json"
SUPPORT_STATE_V2 = DATA / "phase7_3_3_d_support_stage_state_v2.json"
READINESS_V13 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v13.json"

MANIFEST = REPORTS / "phase7_3_3_d_support_review_packet_construction_manifest_v1.json"
SHARED_PACKET = DATA / "phase7_3_3_d_support_blind_review_packet_v1.json"
REVIEWER_A_PACKET = DATA / "phase7_3_3_d_support_reviewer_a_packet_v1.json"
REVIEWER_B_PACKET = DATA / "phase7_3_3_d_support_reviewer_b_packet_v1.json"
REVIEWER_A_SUBMISSION = DATA / "phase7_3_3_d_support_reviewer_a_submission_v2.json"
REVIEWER_B_SUBMISSION = DATA / "phase7_3_3_d_support_reviewer_b_submission_v2.json"
RECEIPT = REPORTS / "phase7_3_3_d_support_review_packet_construction_receipt_v1.json"
SUPPORT_STATE_V3 = DATA / "phase7_3_3_d_support_stage_state_v3.json"
READINESS_V14 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v14.json"

CLAIM_VISIBLE_FIELDS = [
    "boundary_claim_id",
    "case_id",
    "response_sha256",
    "anchor_id",
    "source_field",
    "source_index",
    "source_span",
    "claim_text",
    "claim_type",
    "claim_role",
    "anchor_group",
    "material",
    "claim_origin",
]
SUPPORT_LABELS = {"supported", "partially_supported", "unsupported", "not_assessable"}
CONFIDENCE = {"low", "medium", "high"}
FORBIDDEN_PACKET_KEYS = {
    "support_label",
    "cited_evidence_ids",
    "support_rationale",
    "annotation_confidence",
    "human_support_label",
    "candidate",
    "reference_candidate",
    "historical_judge",
    "silver_label",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha256(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def recursive_key_hits(value: Any, keys: set[str]) -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys:
                hits.append(key)
            hits.extend(recursive_key_hits(child, keys))
    elif isinstance(value, list):
        for child in value:
            hits.extend(recursive_key_hits(child, keys))
    return hits


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    required = (
        PROTOCOL,
        SUPPORT_PROTOCOL,
        EVIDENCE_SOURCE,
        BOUNDARY_GOLD,
        SUPPORT_STATE_V2,
        READINESS_V13,
    )
    for path in required:
        if not path.is_file():
            raise ValueError(f"required_frozen_input_missing:{path.relative_to(ROOT)}")

    protocol = load(PROTOCOL)
    support_protocol = load(SUPPORT_PROTOCOL)
    evidence = load(EVIDENCE_SOURCE)
    gold = load(BOUNDARY_GOLD)
    state = load(SUPPORT_STATE_V2)
    readiness = load(READINESS_V13)
    gates = readiness.get("gates", {})
    lineage = readiness.get("artifact_lineage", {})

    evidence_cases = evidence.get("cases", [])
    evidence_by_case = {item.get("case_id"): item for item in evidence_cases}
    claims = gold.get("claims", [])
    claims_by_case: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        claims_by_case.setdefault(claim.get("case_id"), []).append(claim)

    claim_ids = [claim.get("boundary_claim_id") for claim in claims]
    visible_claim_ids = []
    claim_forbidden_hits: list[str] = []
    claim_field_failures: list[str] = []
    response_hash_failures: list[str] = []
    evidence_id_failures: list[str] = []
    for claim in claims:
        visible_claim_ids.append(claim.get("boundary_claim_id"))
        claim_forbidden_hits.extend(sorted(set(claim) & FORBIDDEN_PACKET_KEYS))
        missing = [field for field in CLAIM_VISIBLE_FIELDS if field not in claim]
        if missing:
            claim_field_failures.append(f"{claim.get('boundary_claim_id')}:{','.join(missing)}")
        case_id = claim.get("case_id")
        source_case = evidence_by_case.get(case_id)
        if source_case is None or claim.get("response_sha256") != source_case.get("response_sha256"):
            response_hash_failures.append(str(claim.get("boundary_claim_id")))
        if source_case is not None:
            valid_ids = {experience.get("memory_id") for experience in source_case.get("evidence_input", {}).get("experiences", [])}
            if not valid_ids:
                evidence_id_failures.append(f"{case_id}:no_evidence_ids")

    source_forbidden_hits = sorted(set(recursive_key_hits(
        [{"evidence_input": item.get("evidence_input")} for item in evidence_cases],
        FORBIDDEN_PACKET_KEYS,
    )))
    # The evidence bundle has no support decisions; candidate/reference fields are excluded below by construction.
    case_ids = sorted(evidence_by_case)
    claim_case_ids = sorted(claims_by_case)
    checks = {
        "protocol_offline_deterministic": protocol.get("execution_mode") == "offline_deterministic",
        "support_protocol_identity_valid": support_protocol.get("protocol_id") == "phase7.3.3-d1-b-support-reference-protocol-v1",
        "boundary_gold_frozen": gold.get("status") == "frozen_project_boundary_gold" and gold.get("reference_status") == "project_boundary_gold_model_adjudicated_not_human_gold",
        "boundary_gold_hash_matches_readiness": lineage.get("boundary_gold_sha256") == sha256(BOUNDARY_GOLD),
        "boundary_gold_counts_valid": gold.get("case_count") == 10 and gold.get("anchor_count") == 65 and gold.get("boundary_claim_count") == 118 and len(claims) == 118,
        "boundary_gold_claim_ids_unique": len(claim_ids) == len(set(claim_ids)) == 118 and all(isinstance(item, str) and item for item in claim_ids),
        "boundary_gold_support_labels_absent": gold.get("support_labels_present") is False and not claim_forbidden_hits,
        "boundary_gold_coverage_passed": gold.get("coverage_metrics", {}).get("unclassified_characters") == 0 and gold.get("coverage_metrics", {}).get("accounting_ratio") == 1.0,
        "support_state_v2_authorizes_packet_construction": state.get("boundary_state") == "frozen_project_boundary_gold" and state.get("support_state") == "authorized_not_started" and state.get("support_review_allowed") is True and state.get("support_review_packets_generated") is False,
        "readiness_v13_authorizes_packet_construction": readiness.get("next_authorized_stage") == "support_review_packet_construction" and readiness.get("boundary_gold_frozen") is True and readiness.get("support_review_allowed") is True and readiness.get("support_review_started") is False,
        "evidence_source_has_ten_cases": evidence.get("case_count", len(evidence_cases)) == 10 and len(evidence_cases) == 10 and case_ids == [f"extract_{index:02d}" for index in range(1, 11)],
        "evidence_and_gold_cases_match": case_ids == claim_case_ids,
        "each_case_has_boundary_claims": all(len(claims_by_case.get(case_id, [])) > 0 for case_id in case_ids),
        "claim_fields_available": not claim_field_failures,
        "claim_response_hashes_match_evidence": not response_hash_failures,
        "evidence_bundles_have_ids": not evidence_id_failures,
        "source_evidence_has_no_support_decisions": not source_forbidden_hits,
        "held_out_not_accessed": evidence.get("held_out_accessed") is False and gold.get("held_out_accessed") is False and state.get("held_out_accessed") is False and readiness.get("held_out_accessed") is False,
    }
    if not all(checks.values()):
        failures = [name for name, passed in checks.items() if not passed]
        raise ValueError("support_packet_construction_input_validation_failed:" + ",".join(failures))

    return {
        "protocol": protocol,
        "support_protocol": support_protocol,
        "evidence": evidence,
        "gold": gold,
        "state": state,
        "readiness": readiness,
        "evidence_by_case": evidence_by_case,
        "claims_by_case": claims_by_case,
    }, {
        "checks": checks,
        "claim_count": len(claims),
        "case_count": len(case_ids),
        "evidence_count": sum(len(item.get("evidence_input", {}).get("experiences", [])) for item in evidence_cases),
        "claim_case_ids": claim_case_ids,
    }


def expected_manifest(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d1-b-support-review-packet-construction-manifest-v1",
        "status": "frozen_not_started",
        "execution_mode": "offline_deterministic",
        "artifact_lineage": {
            "adapter_sha256": sha256(Path(__file__)),
            "packet_construction_protocol_sha256": sha256(PROTOCOL),
            "support_reference_protocol_sha256": sha256(SUPPORT_PROTOCOL),
            "evidence_source_sha256": sha256(EVIDENCE_SOURCE),
            "boundary_gold_sha256": sha256(BOUNDARY_GOLD),
            "support_stage_state_v2_sha256": sha256(SUPPORT_STATE_V2),
            "readiness_v13_sha256": sha256(READINESS_V13),
        },
        "validated_case_count": context["case_count"],
        "validated_boundary_claim_count": context["claim_count"],
        "validated_evidence_item_count": context["evidence_count"],
        "entry_gate_checks": context["checks"],
        "expected_outputs": {
            "shared_packet": str(SHARED_PACKET.relative_to(ROOT)),
            "reviewer_a_packet": str(REVIEWER_A_PACKET.relative_to(ROOT)),
            "reviewer_b_packet": str(REVIEWER_B_PACKET.relative_to(ROOT)),
            "reviewer_a_submission_template": str(REVIEWER_A_SUBMISSION.relative_to(ROOT)),
            "reviewer_b_submission_template": str(REVIEWER_B_SUBMISSION.relative_to(ROOT)),
            "construction_receipt": str(RECEIPT.relative_to(ROOT)),
            "support_stage_state_v3": str(SUPPORT_STATE_V3.relative_to(ROOT)),
            "readiness_v14": str(READINESS_V14.relative_to(ROOT)),
        },
        "provider_call_allowed": False,
        "support_execution_allowed_in_this_stage": False,
        "boundary_mutation_allowed": False,
        "held_out_access_allowed": False,
    }


def visible_claim(claim: dict[str, Any]) -> dict[str, Any]:
    return {field: deepcopy(claim[field]) for field in CLAIM_VISIBLE_FIELDS}


def build_shared_packet(inputs: dict[str, Any]) -> dict[str, Any]:
    evidence_by_case = inputs["evidence_by_case"]
    claims_by_case = inputs["claims_by_case"]
    cases = []
    for case_id in sorted(evidence_by_case):
        source_case = evidence_by_case[case_id]
        evidence_bundle = deepcopy(source_case["evidence_input"])
        claims = [visible_claim(claim) for claim in claims_by_case[case_id]]
        valid_ids = [item["memory_id"] for item in evidence_bundle.get("experiences", [])]
        cases.append({
            "case_id": case_id,
            "response_sha256": source_case["response_sha256"],
            "evidence_bundle_sha256": object_sha256(evidence_bundle),
            "evidence_bundle": evidence_bundle,
            "valid_evidence_ids": valid_ids,
            "boundary_claims": claims,
            "boundary_claim_count": len(claims),
        })
    return {
        "schema_version": 1,
        "packet_id": "phase7.3.3-d1-b-support-blind-review-packet-v1",
        "protocol_id": "phase7.3.3-d1-b-support-review-packet-construction-protocol-v1",
        "support_reference_protocol_id": "phase7.3.3-d1-b-support-reference-protocol-v1",
        "packet_role": "frozen_evidence_and_boundary_claim_input_only",
        "status": "frozen_ready_for_independent_support_review",
        "boundary_gold_sha256": sha256(BOUNDARY_GOLD),
        "evidence_source_sha256": sha256(EVIDENCE_SOURCE),
        "case_count": len(cases),
        "boundary_claim_count": sum(case["boundary_claim_count"] for case in cases),
        "evidence_item_count": sum(len(case["valid_evidence_ids"]) for case in cases),
        "blind_to_other_reviewer": True,
        "blind_to_candidate_gold_or_silver": True,
        "blind_to_judge_outputs": True,
        "blind_to_phase7_3_aggregate_metrics": True,
        "held_out_accessed": False,
        "provider_called_for_construction": False,
        "reviewer_visible": [
            "frozen_evidence_bundle",
            "frozen_boundary_claims",
            "support_label_definitions",
            "reason_code_definitions",
            "reviewer_output_contract",
        ],
        "reviewer_prohibited": [
            "candidate_gold_or_silver_labels",
            "historical_or_new_judge_outputs",
            "other_reviewer_submission",
            "phase7_3_aggregate_metrics",
            "reference_candidate",
            "provider_raw_responses",
            "held_out_cases",
            "boundary_adjudication_rationales",
            "boundary_reviewer_claim_ids",
        ],
        "support_label_definitions": inputs["protocol"]["support_label_definitions"],
        "reason_code_definitions": inputs["protocol"]["reason_code_definitions"],
        "reviewer_output_contract": inputs["protocol"]["reviewer_output_contract"],
        "claim_visible_fields": inputs["protocol"]["packet_construction_contract"]["claim_visible_fields"],
        "cases": cases,
    }


def build_reviewer_packet(shared: dict[str, Any], reviewer: str, shared_hash: str) -> dict[str, Any]:
    packet = deepcopy(shared)
    reviewer_id = f"reviewer_{reviewer}"
    packet["packet_id"] = f"phase7.3.3-d1-b-support-{reviewer}-packet-v1"
    packet["packet_role"] = "independent_support_reviewer_input_only"
    packet["reviewer_id"] = reviewer_id
    packet["reviewer_copy_rule"] = "One clean copy for one independent reviewer; do not share or merge reviewer packets."
    packet["shared_packet_sha256"] = shared_hash
    packet["other_reviewer_id"] = None
    return packet


def build_submission_template(packet: dict[str, Any], reviewer: str, packet_hash: str) -> dict[str, Any]:
    claims = [
        {
            "boundary_claim_id": claim["boundary_claim_id"],
            "support_label": None,
            "cited_evidence_ids": [],
            "reason_codes": [],
            "support_rationale": None,
            "annotation_confidence": None,
        }
        for case in packet["cases"]
        for claim in case["boundary_claims"]
    ]
    # These are empty decision slots, not prelabels; execution will require a completed replacement.
    return {
        "schema_version": 2,
        "submission_id": f"phase7.3.3-d1-b-support-reviewer-{reviewer}-submission-v2",
        "reviewer_id": f"reviewer_{reviewer}",
        "reviewer_role": "independent_support_reviewer",
        "protocol_id": "phase7.3.3-d1-b-support-reference-protocol-v1",
        "packet_id": packet["packet_id"],
        "packet_sha256": packet_hash,
        "status": "ready_not_started",
        "blocked_reason": None,
        "boundary_gold_sha256": sha256(BOUNDARY_GOLD),
        "completed": False,
        "blind_to_other_reviewer": True,
        "blind_to_candidate_gold_or_silver": True,
        "held_out_accessed": False,
        "claims": claims,
        "expected_claim_count": len(claims),
        "immutable_boundary_fields_attested": False,
        "source_artifact_sha256": {
            "boundary_gold": sha256(BOUNDARY_GOLD),
            "support_packet": packet_hash,
            "evidence_source": sha256(EVIDENCE_SOURCE),
            "support_reference_protocol": sha256(SUPPORT_PROTOCOL),
        },
    }


def build_support_state(packet_hashes: dict[str, str], template_hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "state_id": "phase7.3.3-d1-b-support-stage-state-v3",
        "boundary_state": "frozen_project_boundary_gold",
        "support_state": "review_packets_frozen_independent_review_authorized",
        "blocked_reason": None,
        "boundary_gold_sha256": sha256(BOUNDARY_GOLD),
        "boundary_gold_freeze_receipt_sha256": load(REPORTS / "phase7_3_3_d_boundary_gold_freeze_receipt_v1.json")["boundary_gold_sha256"],
        "boundary_claim_count": 118,
        "support_review_packets_generated": True,
        "shared_packet_sha256": packet_hashes["shared"],
        "reviewer_a_packet_sha256": packet_hashes["reviewer_a"],
        "reviewer_b_packet_sha256": packet_hashes["reviewer_b"],
        "reviewer_a_submission_template_sha256": template_hashes["reviewer_a"],
        "reviewer_b_submission_template_sha256": template_hashes["reviewer_b"],
        "support_reviewer_a_completed": False,
        "support_reviewer_b_completed": False,
        "support_agreement_available": False,
        "support_adjudication_allowed": False,
        "support_gold_frozen": False,
        "support_gold_sha256": None,
        "support_review_allowed": True,
        "support_review_started": False,
        "next_authorized_stage": "independent_support_review_execution",
        "immutable_boundary_claim_fields": [
            "boundary_claim_id", "case_id", "response_sha256", "anchor_id", "source_field", "source_index",
            "source_span", "claim_text", "claim_type", "claim_role", "anchor_group", "material", "claim_origin",
        ],
        "held_out_accessed": False,
        "provider_called_for_packet_construction": False,
    }


def build_readiness_v14(packet_hashes: dict[str, str], template_hashes: dict[str, str], state_hash: str) -> dict[str, Any]:
    prior = load(READINESS_V13)
    lineage = {
        **prior["artifact_lineage"],
        "support_packet_construction_protocol_sha256": sha256(PROTOCOL),
        "support_packet_construction_manifest_sha256": sha256(MANIFEST),
        "support_blind_packet_sha256": packet_hashes["shared"],
        "support_reviewer_a_packet_sha256": packet_hashes["reviewer_a"],
        "support_reviewer_b_packet_sha256": packet_hashes["reviewer_b"],
        "support_reviewer_a_submission_template_sha256": template_hashes["reviewer_a"],
        "support_reviewer_b_submission_template_sha256": template_hashes["reviewer_b"],
        "support_stage_state_v3_sha256": state_hash,
    }
    gates = {
        **prior["gates"],
        "support_review_packet_construction_allowed": True,
        "support_review_packet_construction_completed": True,
        "support_reviewer_a_execution_allowed": True,
        "support_reviewer_b_execution_allowed": True,
        "support_review_started": False,
        "support_gold_frozen": False,
        "held_out_accessed": False,
    }
    return {
        "schema_version": 14,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v14",
        "status": "support_review_packets_frozen_independent_review_authorized",
        "artifact_lineage": lineage,
        "gates": gates,
        "boundary_gold": prior["boundary_gold"],
        "support_review": {
            "shared_packet_sha256": packet_hashes["shared"],
            "reviewer_a_packet_sha256": packet_hashes["reviewer_a"],
            "reviewer_b_packet_sha256": packet_hashes["reviewer_b"],
            "reviewer_a_submission_template_sha256": template_hashes["reviewer_a"],
            "reviewer_b_submission_template_sha256": template_hashes["reviewer_b"],
            "boundary_claim_count": 118,
            "reviewer_a_completed": False,
            "reviewer_b_completed": False,
            "agreement_available": False,
            "support_gold_frozen": False,
        },
        "next_authorized_stage": "independent_support_review_execution",
        "boundary_gold_frozen": True,
        "support_review_allowed": True,
        "support_review_started": False,
        "support_gold_frozen": False,
        "held_out_accessed": False,
    }


def execute() -> dict[str, Any]:
    inputs, context = validate_inputs()
    manifest = expected_manifest(context)
    if not MANIFEST.is_file():
        raise ValueError("support_packet_construction_manifest_not_frozen")
    if load(MANIFEST) != manifest:
        raise ValueError("support_packet_construction_manifest_mismatch")

    shared = build_shared_packet(inputs)
    shared_hash = write_once(SHARED_PACKET, shared)
    reviewer_a = build_reviewer_packet(shared, "a", shared_hash)
    reviewer_b = build_reviewer_packet(shared, "b", shared_hash)
    reviewer_a_hash = write_once(REVIEWER_A_PACKET, reviewer_a)
    reviewer_b_hash = write_once(REVIEWER_B_PACKET, reviewer_b)

    reviewer_a_template = build_submission_template(reviewer_a, "a", reviewer_a_hash)
    reviewer_b_template = build_submission_template(reviewer_b, "b", reviewer_b_hash)
    reviewer_a_template_hash = write_once(REVIEWER_A_SUBMISSION, reviewer_a_template)
    reviewer_b_template_hash = write_once(REVIEWER_B_SUBMISSION, reviewer_b_template)

    packet_hashes = {"shared": shared_hash, "reviewer_a": reviewer_a_hash, "reviewer_b": reviewer_b_hash}
    template_hashes = {"reviewer_a": reviewer_a_template_hash, "reviewer_b": reviewer_b_template_hash}
    state = build_support_state(packet_hashes, template_hashes)
    state_hash = write_once(SUPPORT_STATE_V3, state)
    readiness = build_readiness_v14(packet_hashes, template_hashes, state_hash)
    readiness_hash = write_once(READINESS_V14, readiness)

    receipt = {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d1-b-support-review-packet-construction-receipt-v1",
        "status": "completed_support_review_packet_construction",
        "manifest_sha256": sha256(MANIFEST),
        "packet_construction_protocol_sha256": sha256(PROTOCOL),
        "boundary_gold_sha256": sha256(BOUNDARY_GOLD),
        "evidence_source_sha256": sha256(EVIDENCE_SOURCE),
        "shared_packet_sha256": shared_hash,
        "reviewer_a_packet_sha256": reviewer_a_hash,
        "reviewer_b_packet_sha256": reviewer_b_hash,
        "reviewer_a_submission_template_sha256": reviewer_a_template_hash,
        "reviewer_b_submission_template_sha256": reviewer_b_template_hash,
        "support_stage_state_v3_sha256": state_hash,
        "readiness_v14_sha256": readiness_hash,
        "case_count": 10,
        "boundary_claim_count": 118,
        "evidence_item_count": context["evidence_count"],
        "reviewer_a_completed": False,
        "reviewer_b_completed": False,
        "support_review_started": False,
        "support_gold_frozen": False,
        "provider_called": False,
        "held_out_accessed": False,
    }
    receipt_hash = write_once(RECEIPT, receipt)
    return {
        "status": receipt["status"],
        "manifest_sha256": sha256(MANIFEST),
        "shared_packet_sha256": shared_hash,
        "reviewer_a_packet_sha256": reviewer_a_hash,
        "reviewer_b_packet_sha256": reviewer_b_hash,
        "reviewer_a_submission_template_sha256": reviewer_a_template_hash,
        "reviewer_b_submission_template_sha256": reviewer_b_template_hash,
        "support_stage_state_v3_sha256": state_hash,
        "readiness_v14_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "case_count": 10,
        "boundary_claim_count": 118,
        "evidence_item_count": context["evidence_count"],
        "support_review_packet_construction_completed": True,
        "support_reviewer_a_execution_allowed": True,
        "support_reviewer_b_execution_allowed": True,
        "support_review_started": False,
        "provider_called": False,
        "held_out_accessed": False,
    }


def verify() -> dict[str, Any]:
    inputs, context = validate_inputs()
    expected = expected_manifest(context)
    manifest_matches = MANIFEST.is_file() and load(MANIFEST) == expected
    outputs_present = all(path.is_file() for path in (
        SHARED_PACKET, REVIEWER_A_PACKET, REVIEWER_B_PACKET,
        REVIEWER_A_SUBMISSION, REVIEWER_B_SUBMISSION, RECEIPT,
        SUPPORT_STATE_V3, READINESS_V14,
    ))
    output_valid = False
    hashes: dict[str, str | None] = {
        "adapter_sha256": sha256(Path(__file__)),
        "protocol_sha256": sha256(PROTOCOL),
        "manifest_sha256": sha256(MANIFEST) if MANIFEST.exists() else None,
        "shared_packet_sha256": sha256(SHARED_PACKET) if SHARED_PACKET.exists() else None,
        "reviewer_a_packet_sha256": sha256(REVIEWER_A_PACKET) if REVIEWER_A_PACKET.exists() else None,
        "reviewer_b_packet_sha256": sha256(REVIEWER_B_PACKET) if REVIEWER_B_PACKET.exists() else None,
        "reviewer_a_submission_template_sha256": sha256(REVIEWER_A_SUBMISSION) if REVIEWER_A_SUBMISSION.exists() else None,
        "reviewer_b_submission_template_sha256": sha256(REVIEWER_B_SUBMISSION) if REVIEWER_B_SUBMISSION.exists() else None,
        "receipt_sha256": sha256(RECEIPT) if RECEIPT.exists() else None,
        "support_stage_state_v3_sha256": sha256(SUPPORT_STATE_V3) if SUPPORT_STATE_V3.exists() else None,
        "readiness_v14_sha256": sha256(READINESS_V14) if READINESS_V14.exists() else None,
    }
    if outputs_present and manifest_matches:
        shared = load(SHARED_PACKET)
        reviewer_a = load(REVIEWER_A_PACKET)
        reviewer_b = load(REVIEWER_B_PACKET)
        template_a = load(REVIEWER_A_SUBMISSION)
        template_b = load(REVIEWER_B_SUBMISSION)
        state = load(SUPPORT_STATE_V3)
        readiness = load(READINESS_V14)
        receipt = load(RECEIPT)
        expected_shared = build_shared_packet(inputs)
        # Rebuild packets with exact serialized shared hash and compare against persisted artifacts.
        expected_shared_hash = sha256(SHARED_PACKET)
        expected_a = build_reviewer_packet(expected_shared, "a", expected_shared_hash)
        expected_b = build_reviewer_packet(expected_shared, "b", expected_shared_hash)
        expected_a_hash = sha256(REVIEWER_A_PACKET)
        expected_b_hash = sha256(REVIEWER_B_PACKET)
        expected_template_a = build_submission_template(expected_a, "a", expected_a_hash)
        expected_template_b = build_submission_template(expected_b, "b", expected_b_hash)
        state_expected = build_support_state({"shared": expected_shared_hash, "reviewer_a": expected_a_hash, "reviewer_b": expected_b_hash}, {"reviewer_a": sha256(REVIEWER_A_SUBMISSION), "reviewer_b": sha256(REVIEWER_B_SUBMISSION)})
        readiness_expected = build_readiness_v14({"shared": expected_shared_hash, "reviewer_a": expected_a_hash, "reviewer_b": expected_b_hash}, {"reviewer_a": sha256(REVIEWER_A_SUBMISSION), "reviewer_b": sha256(REVIEWER_B_SUBMISSION)}, sha256(SUPPORT_STATE_V3))
        output_valid = (
            shared == expected_shared and reviewer_a == expected_a and reviewer_b == expected_b
            and template_a == expected_template_a and template_b == expected_template_b
            and state == state_expected and readiness == readiness_expected
            and receipt.get("status") == "completed_support_review_packet_construction"
            and receipt.get("support_review_started") is False
            and receipt.get("support_gold_frozen") is False
            and receipt.get("provider_called") is False
            and receipt.get("held_out_accessed") is False
        )
    return {
        "status": "verified" if all(context["checks"].values()) and manifest_matches and outputs_present and output_valid else "failed",
        "all_entry_gate_checks_passed": all(context["checks"].values()),
        "manifest_matches_current_inputs": manifest_matches,
        "all_outputs_present": outputs_present,
        "all_outputs_match_deterministic_reconstruction": output_valid,
        "validated_case_count": context["case_count"],
        "validated_boundary_claim_count": context["claim_count"],
        "validated_evidence_item_count": context["evidence_count"],
        "hashes": hashes,
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
        _, context = validate_inputs()
        manifest = expected_manifest(context)
        result = {
            "status": "support_review_packet_construction_manifest_frozen_not_started",
            "manifest_sha256": write_once(MANIFEST, manifest),
            "validated_case_count": context["case_count"],
            "validated_boundary_claim_count": context["claim_count"],
            "validated_evidence_item_count": context["evidence_count"],
            "provider_called": False,
            "held_out_accessed": False,
        }
    else:
        result = execute()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

