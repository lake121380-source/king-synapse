#!/usr/bin/env python3
"""Deterministic Phase 7.3.3-D Atomic-vs-Candidate paired evaluation v1.

The study is a retrospective ten-design-case diagnostic comparison.  It replays
frozen Candidate labels and frozen Atomic support labels, calculates mechanical
metrics, and freezes an exploratory result.  It does not call a Provider,
regenerate semantics, access held-out data, or make accuracy/generalization
claims.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

PROTOCOL = CONFIG / "phase7_3_3_d_atomic_vs_candidate_paired_evaluation_protocol_v1.json"
AGGREGATION = CONFIG / "phase7_3_3_d_atomic_vs_candidate_aggregation_policy_v1.json"
METRIC_SPEC = CONFIG / "phase7_3_3_d_atomic_vs_candidate_metric_specification_v1.json"
CANDIDATE = REPORTS / "phase7_3_2_semantic_judge_execution.json"
BOUNDARY = DATA / "phase7_3_3_d_boundary_gold_v1.json"
SUPPORT = DATA / "phase7_3_3_d_support_gold_v1.json"
WORKLIST = DATA / "phase7_3_3_d_atomic_vs_candidate_paired_worklist_v1.json"
BOUNDARY_PACKET = DATA / "phase7_3_3_d_boundary_blind_review_packet_v1.json"
PROTOCOL_FREEZE_MANIFEST = REPORTS / "phase7_3_3_d_atomic_vs_candidate_protocol_freeze_manifest_v1.json"
PROTOCOL_FREEZE_RECEIPT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_protocol_freeze_receipt_v1.json"
PROTOCOL_FREEZE_OUTCOME = REPORTS / "phase7_3_3_d_atomic_vs_candidate_protocol_freeze_outcome_v1.json"
PROTOCOL_FIXTURES = REPORTS / "phase7_3_3_d_atomic_vs_candidate_protocol_contract_fixtures_v1.json"
ALIGNMENT_AUDIT_V1 = REPORTS / "phase7_3_3_d_atomic_vs_candidate_baseline_alignment_audit_v1.json"
COMPATIBILITY_REPORT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_gold_compatibility_report_v1.json"
STATE_V11 = DATA / "phase7_3_3_d_support_stage_state_v11.json"
READINESS_V22 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v22.json"

EVIDENCE_AUDIT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_evidence_lineage_audit_v1.json"
PAIRED_FIXTURES = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_contract_fixtures_v1.json"
EXECUTION_MANIFEST = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_execution_manifest_v1.json"
EXECUTION = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_execution_v1.json"
METRICS = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_metrics_v1.json"
LIMITATIONS = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_limitations_v1.json"
RESULT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_result_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_result_freeze_receipt_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_result_freeze_outcome_v1.json"
NEGATIVE_RESULT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_execution_negative_result_v1.json"
STATE_V12 = DATA / "phase7_3_3_d_support_stage_state_v12.json"
READINESS_V23 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v23.json"

EXPECTED_SHA = {
    PROTOCOL: "4633fe608f7ea8ac29d50964d15e9344bd1a9eeac7416aec37720bc5ced90f68",
    AGGREGATION: "3696e335a7504cb5ab61769a6ce6c5a87d9b7a92399a9e924fef87328a79c457",
    METRIC_SPEC: "818079b893bb3aa6034e51cdaf10be0aad9578e0f9f86f079999daf44ead82ab",
    CANDIDATE: "19dba48a7666c7fbdd0002e2d86ccbdd888f5ea8f208c28feb41c1f1c2c27a67",
    BOUNDARY: "233c51af2a3c537be57a8838a8697444affea5b5b80e0835f98bab4ea567f1a0",
    SUPPORT: "845b1fe97e9357d511f52f5e9d1b995bdcb8d3b1991c27a88c5656fdeae08cf5",
    WORKLIST: "4b70c31b0e5ba00841d32a6fb68db8b8d5be6547777fa384f82eb67dac12c259",
    BOUNDARY_PACKET: "38fba5a20c560704c7aedfd441c39c428dcdb4774cc0395d51d84b33c507197a",
    PROTOCOL_FREEZE_MANIFEST: "363678ded12dc74f5f869e8cd4f94b75e54dcca8ca96ea9caf52eb3b58faca53",
    PROTOCOL_FREEZE_RECEIPT: "b1a5bce30b035f9f0b050dfc8c67878bfe6b580fd14aab5785a938f671a9e674",
    PROTOCOL_FREEZE_OUTCOME: "4c398e64f8e5e280803b4a8d35cb66439ce0c46da7daa16ac0a64819f04ada0f",
    PROTOCOL_FIXTURES: "e2e77f9be8211729f119483b0ab509e49c2197b09644b451c17e017b483b3eb4",
    ALIGNMENT_AUDIT_V1: "a28adec44de6b0d05c6d7158dc3c38d152093b99bbf733b27c76a28238463b32",
    COMPATIBILITY_REPORT: "4d7507c72f187c785e17b2ef4f6c8f05191c7c032f1796fc415f77a863ac2009",
    STATE_V11: "a551eee93f0a176dfa61c5faae7f78090aac2cbdd9f615a35e8642a90518f75a",
    READINESS_V22: "543fdd812aac50a74d9c332372493d0f9659d4133fbb4f471331455b4b3bf413",
}
EXPECTED_DESIGN_SHA = "334b74dbd2e8fce9f9de7e9087e909324fe4b34cc9c0f262a6ce3a6c9f193b2d"
EXPECTED_PROVIDER_EXECUTION_SHA = "59ca1865e770a1295def91b51248fadd2b5cff777e183fac9813abc28ca9f1e1"
ALLOWED_LABELS = ("supported", "partially_supported", "unsupported", "not_assessable")
ORDINAL = {"supported": 0, "partially_supported": 1, "unsupported": 2}
ALLOWED_ROLES = {
    "anchor", "prediction", "falsification_observable", "prediction_observable",
    "prediction_criterion", "falsification",
}
IMMUTABLE_FIELDS = (
    "boundary_claim_id", "case_id", "response_sha256", "anchor_id", "source_field",
    "source_index", "source_text_sha256", "source_span", "source_occurrence_index",
    "claim_text", "claim_type", "claim_role", "anchor_group", "material", "claim_origin",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()




def artifact_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def canonical_artifact_sha(value: Any) -> str:
    return hashlib.sha256(artifact_bytes(value)).hexdigest()

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def write_once(path: Path, value: Any) -> str:
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    if path.exists():
        require(path.read_bytes() == raw, f"immutable_artifact_exists_with_different_content:{rel(path)}")
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as stream:
        stream.write(raw)
        temporary = Path(stream.name)
    temporary.replace(path)
    return digest


def unique_map(items: Iterable[dict[str, Any]], key: str, name: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        identity = item.get(key)
        require(isinstance(identity, str) and identity, f"{name}_invalid_{key}")
        require(identity not in result, f"duplicate_{name}:{identity}")
        result[identity] = item
    return result


def ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0, "zero_metric_denominator")
    return {"numerator": numerator, "denominator": denominator, "value": round(numerator / denominator, 6)}


def validate_resolution(claim: dict[str, Any]) -> bool:
    label = claim.get("support_label")
    method = claim.get("label_resolution_method")
    if method == "exact_reviewer_agreement":
        return claim.get("reviewer_a_label") == claim.get("reviewer_b_label") == label
    if method == "adjudicated_frozen_reviewer_selection":
        selected = claim.get("selected_frozen_decision")
        source = claim.get("selected_source_reviewer")
        expected_source_label = claim.get("reviewer_a_label") if source == "reviewer_a" else (
            claim.get("reviewer_b_label") if source == "reviewer_b" else None
        )
        return bool(
            isinstance(claim.get("adjudication_item_id"), str)
            and isinstance(selected, dict)
            and selected.get("support_label") == label == expected_source_label
            and claim.get("selected_frozen_decision_sha256") == canonical_sha(selected)
        )
    return False


def span_valid(claim: dict[str, Any]) -> bool:
    span = claim.get("source_span")
    return bool(
        isinstance(span, dict)
        and isinstance(span.get("start"), int)
        and isinstance(span.get("end"), int)
        and 0 <= span["start"] < span["end"]
        and isinstance(claim.get("claim_text"), str)
        and len(claim["claim_text"]) == span["end"] - span["start"]
    )


def exact_source_match(claim: dict[str, Any], packet_case: dict[str, Any]) -> bool:
    anchors = [anchor for anchor in packet_case.get("source_anchors", [])
               if anchor.get("anchor_id") == claim.get("anchor_id")
               and anchor.get("source_field") == claim.get("source_field")
               and anchor.get("source_index") == claim.get("source_index")]
    if len(anchors) != 1 or not span_valid(claim):
        return False
    anchor = anchors[0]
    source_text = anchor.get("source_text")
    span = claim["source_span"]
    if not isinstance(source_text, str) or span["end"] > len(source_text):
        return False
    if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != claim.get("source_text_sha256"):
        return False
    if anchor.get("source_text_sha256") != claim.get("source_text_sha256"):
        return False
    if source_text[span["start"]:span["end"]] != claim.get("claim_text"):
        return False
    excerpt = claim["claim_text"]
    positions: list[int] = []
    offset = 0
    while True:
        found = source_text.find(excerpt, offset)
        if found < 0:
            break
        positions.append(found)
        offset = found + 1
    occurrence = claim.get("source_occurrence_index")
    return isinstance(occurrence, int) and 0 <= occurrence < len(positions) and positions[occurrence] == span["start"]


def validate_dataset(candidate_decisions: list[dict[str, Any]], boundary_claims: list[dict[str, Any]],
                     support_claims: list[dict[str, Any]], worklist_entries: list[dict[str, Any]],
                     packet_cases: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(candidate_decisions) == 10, "candidate_case_count_not_10")
    require(len(boundary_claims) == 118, "boundary_claim_count_not_118")
    require(len(support_claims) == 118, "support_claim_count_not_118")
    require(len(worklist_entries) == 10, "worklist_case_count_not_10")
    require(len(packet_cases) == 10, "evidence_packet_case_count_not_10")

    candidate_by_case = unique_map(candidate_decisions, "case_id", "candidate_case")
    worklist_by_case = unique_map(worklist_entries, "case_id", "worklist_case")
    packet_by_case = unique_map(packet_cases, "case_id", "evidence_packet_case")
    boundary_by_claim = unique_map(boundary_claims, "boundary_claim_id", "boundary_claim")
    support_by_claim = unique_map(support_claims, "boundary_claim_id", "support_claim")

    candidate_order = [item["case_id"] for item in candidate_decisions]
    boundary_order = ordered_unique(item["case_id"] for item in boundary_claims)
    support_order = ordered_unique(item["case_id"] for item in support_claims)
    worklist_order = [item["case_id"] for item in worklist_entries]
    packet_order = [item["case_id"] for item in packet_cases]
    require(candidate_order == boundary_order == support_order == worklist_order == packet_order,
            "paired_case_order_mismatch")
    require(set(candidate_by_case) == set(worklist_by_case) == set(packet_by_case), "paired_case_set_mismatch")

    boundary_ids = [item["boundary_claim_id"] for item in boundary_claims]
    support_ids = [item["boundary_claim_id"] for item in support_claims]
    require(boundary_ids == support_ids, "boundary_support_claim_id_or_order_mismatch")
    claims_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for boundary_claim, support_claim in zip(boundary_claims, support_claims):
        claim_id = boundary_claim["boundary_claim_id"]
        require(support_by_claim[claim_id] is support_claim, f"support_lookup_failure:{claim_id}")
        for field in IMMUTABLE_FIELDS:
            require(boundary_claim.get(field) == support_claim.get(field),
                    f"boundary_immutable_field_mismatch:{claim_id}:{field}")
        label = support_claim.get("support_label")
        require(label in ALLOWED_LABELS, f"invalid_support_label:{claim_id}")
        role = support_claim.get("claim_role")
        require(role in ALLOWED_ROLES, f"unknown_claim_role:{claim_id}:{role}")
        require(support_claim.get("material") is True, f"non_material_claim_in_frozen_gold:{claim_id}")
        case_id = support_claim.get("case_id")
        require(case_id in candidate_by_case, f"unknown_claim_case:{claim_id}:{case_id}")
        expected_sha = candidate_by_case[case_id].get("candidate_response_sha256")
        require(support_claim.get("response_sha256") == expected_sha,
                f"claim_candidate_sha_mismatch:{claim_id}")
        claims_by_case[case_id].append(support_claim)

    for index, case_id in enumerate(candidate_order, 1):
        candidate = candidate_by_case[case_id]
        work = worklist_by_case[case_id]
        packet = packet_by_case[case_id]
        require(candidate.get("support_label") in ALLOWED_LABELS, f"invalid_candidate_label:{case_id}")
        candidate_sha = candidate.get("candidate_response_sha256")
        require(work.get("pair_index") == index, f"worklist_pair_index_mismatch:{case_id}")
        require(work.get("candidate_response_sha256") == candidate_sha,
                f"worklist_candidate_sha_mismatch:{case_id}")
        require(packet.get("response_sha256") == candidate_sha, f"evidence_packet_response_sha_mismatch:{case_id}")
        claim_ids = [item["boundary_claim_id"] for item in claims_by_case[case_id]]
        require(work.get("atomic_claim_ids") == claim_ids, f"worklist_claim_ids_mismatch:{case_id}")
        require(work.get("atomic_claim_count") == len(claim_ids), f"worklist_claim_count_mismatch:{case_id}")
        require(any(item.get("claim_role") == "anchor" for item in claims_by_case[case_id]),
                f"case_missing_anchor:{case_id}")
        for claim in claims_by_case[case_id]:
            require(exact_source_match(claim, packet),
                    f"claim_exact_source_traceability_failure:{claim.get('boundary_claim_id')}")
    return {
        "candidate_order": candidate_order,
        "candidate_by_case": candidate_by_case,
        "claims_by_case": dict(claims_by_case),
        "boundary_by_claim": boundary_by_claim,
        "support_by_claim": support_by_claim,
        "worklist_by_case": worklist_by_case,
        "packet_by_case": packet_by_case,
    }


def validate_inputs(require_not_started: bool = True) -> dict[str, Any]:
    for path, expected in EXPECTED_SHA.items():
        require(path.is_file(), f"required_input_missing:{rel(path)}")
        require(sha256(path) == expected, f"required_input_sha_mismatch:{rel(path)}")
    protocol, aggregation, metric_spec = load(PROTOCOL), load(AGGREGATION), load(METRIC_SPEC)
    candidate, boundary, support, worklist = load(CANDIDATE), load(BOUNDARY), load(SUPPORT), load(WORKLIST)
    packet, state, readiness = load(BOUNDARY_PACKET), load(STATE_V11), load(READINESS_V22)

    require(protocol.get("status") == aggregation.get("status") == metric_spec.get("status") == "frozen",
            "protocol_component_not_frozen")
    require(protocol.get("primary_aggregation_policy") == aggregation.get("policy_id"),
            "aggregation_policy_reference_mismatch")
    require(protocol.get("metric_specification") == metric_spec.get("metric_specification_id"),
            "metric_specification_reference_mismatch")
    require(protocol.get("execution_policy", {}).get("provider_calls_allowed") is False,
            "provider_call_guard_missing")
    require(protocol.get("execution_policy", {}).get("held_out_access_allowed") is False,
            "held_out_guard_missing")
    require(protocol.get("anti_circularity_guard", {}).get("independent_reference_required_for_accuracy_claims") is True,
            "anti_circularity_guard_missing")
    require(aggregation.get("primary_candidate_aggregation", {}).get("post_execution_tuning_allowed") is False,
            "aggregation_tuning_guard_missing")
    require(worklist.get("status") == "frozen" and worklist.get("contains_paired_metrics") is False,
            "worklist_not_frozen_or_contains_metrics")
    require(worklist.get("contains_provider_output") is False, "worklist_contains_provider_output")

    require(candidate.get("status") == "completed" and candidate.get("completed_case_count") == 10,
            "candidate_baseline_not_complete")
    require(candidate.get("design_dataset_sha256") == EXPECTED_DESIGN_SHA,
            "candidate_design_dataset_lineage_mismatch")
    require(candidate.get("candidate_execution_sha256") == EXPECTED_PROVIDER_EXECUTION_SHA,
            "candidate_provider_execution_lineage_mismatch")
    packet_sources = packet.get("source_artifact_sha256", {})
    require(packet_sources.get("design_dataset") == EXPECTED_DESIGN_SHA,
            "evidence_packet_design_lineage_mismatch")
    require(packet_sources.get("real_provider_execution") == EXPECTED_PROVIDER_EXECUTION_SHA,
            "evidence_packet_provider_execution_lineage_mismatch")
    require(packet_sources.get("historical_pipeline_a_execution") == sha256(CANDIDATE),
            "evidence_packet_candidate_baseline_lineage_mismatch")
    require(packet.get("held_out_accessed") is False, "evidence_packet_held_out_access_detected")
    require(support.get("support_gold_frozen") is True and support.get("gold_fields") == ["support_label"],
            "support_gold_contract_invalid")
    require(boundary.get("held_out_accessed") is False and support.get("held_out_accessed") is False,
            "gold_held_out_access_detected")

    require(state.get("paired_evaluation_state") == "protocol_frozen_execution_not_started",
            "state_not_at_paired_execution_entry")
    require(state.get("paired_evaluation_protocol_frozen") is True and state.get("paired_worklist_frozen") is True,
            "state_protocol_or_worklist_not_frozen")
    require(state.get("paired_evaluation_started") is False,
            "state_says_paired_execution_already_started")
    require(state.get("next_authorized_stage") == "execute_atomic_vs_candidate_paired_evaluation_v1",
            "state_does_not_authorize_paired_execution")
    require(readiness.get("next_authorized_stage") == "execute_atomic_vs_candidate_paired_evaluation_v1",
            "readiness_does_not_authorize_paired_execution")
    require(state.get("held_out_accessed") is False and readiness.get("held_out_accessed") is False,
            "state_or_readiness_held_out_access_detected")
    if require_not_started:
        for path in (EXECUTION, METRICS, RESULT, RECEIPT, OUTCOME, STATE_V12, READINESS_V23, NEGATIVE_RESULT):
            require(not path.exists(), f"paired_execution_output_already_exists:{rel(path)}")

    paired = validate_dataset(candidate["decisions"], boundary["claims"], support["claims"],
                              worklist["entries"], packet["cases"])
    return {
        "protocol": protocol, "aggregation": aggregation, "metric_spec": metric_spec,
        "candidate": candidate, "boundary": boundary, "support": support,
        "worklist": worklist, "packet": packet, "state": state, "readiness": readiness,
        "paired": paired,
    }


def validate_claim_set(claims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    require(bool(claims), "aggregation_empty_claim_set")
    unique_map(claims, "boundary_claim_id", "aggregation_claim")
    for claim in claims:
        require(claim.get("support_label") in ALLOWED_LABELS,
                f"aggregation_invalid_label:{claim.get('boundary_claim_id')}")
        require(claim.get("claim_role") in ALLOWED_ROLES,
                f"aggregation_unknown_claim_role:{claim.get('boundary_claim_id')}")
    anchors = [claim for claim in claims if claim.get("claim_role") == "anchor"]
    require(bool(anchors), "aggregation_missing_anchor")
    require(all(claim.get("material") is True for claim in anchors), "aggregation_non_material_anchor")
    material = [claim for claim in claims if claim.get("material") is True]
    return anchors, material


def aggregate_primary(claims: list[dict[str, Any]]) -> dict[str, Any]:
    anchors, material = validate_claim_set(claims)
    counts = Counter(claim["support_label"] for claim in claims)
    vector = {f"{label}_count": counts[label] for label in ALLOWED_LABELS}
    anchor_labels = {claim["support_label"] for claim in anchors}
    secondary_material = [claim for claim in material if claim.get("claim_role") != "anchor"]
    if "unsupported" in anchor_labels:
        label, rule = "unsupported", "anchor_unsupported"
    elif "not_assessable" in anchor_labels:
        label, rule = "not_assessable", "anchor_not_assessable"
    elif "partially_supported" in anchor_labels:
        label, rule = "partially_supported", "anchor_partially_supported"
    elif any(claim["support_label"] != "supported" for claim in secondary_material):
        label, rule = "partially_supported", "material_secondary_not_fully_supported"
    else:
        label, rule = "supported", "all_anchors_and_material_secondary_supported"
    return {"atomic_support_vector": vector, "label": label, "applied_rule": rule}


def weakest_label(claims: list[dict[str, Any]]) -> str:
    precedence = ("unsupported", "not_assessable", "partially_supported", "supported")
    labels = {claim["support_label"] for claim in claims}
    return next(label for label in precedence if label in labels)


def aggregate_sensitivity(claims: list[dict[str, Any]]) -> dict[str, str]:
    anchors, material = validate_claim_set(claims)
    return {
        "strict_weakest_material_claim": weakest_label(material),
        "anchor_only": weakest_label(anchors),
    }


def build_evidence_audit(context: dict[str, Any]) -> dict[str, Any]:
    paired = context["paired"]
    cases = []
    for index, case_id in enumerate(paired["candidate_order"], 1):
        candidate = paired["candidate_by_case"][case_id]
        packet = paired["packet_by_case"][case_id]
        cases.append({
            "pair_index": index,
            "case_id": case_id,
            "candidate_response_sha256": candidate["candidate_response_sha256"],
            "evidence_bundle_sha256": canonical_sha(packet["evidence_input"]),
            "design_dataset_lineage_exact": True,
            "provider_execution_lineage_exact": True,
            "candidate_baseline_lineage_exact": True,
        })
    return {
        "schema_version": 1,
        "audit_id": "phase7.3.3-d-atomic-vs-candidate-evidence-lineage-audit-v1",
        "status": "passed",
        "case_count": 10,
        "design_dataset_sha256": EXPECTED_DESIGN_SHA,
        "candidate_source_execution_sha256": EXPECTED_PROVIDER_EXECUTION_SHA,
        "candidate_baseline_sha256": sha256(CANDIDATE),
        "boundary_blind_packet_sha256": sha256(BOUNDARY_PACKET),
        "case_order_exact": True,
        "candidate_response_identity_exact": True,
        "evidence_bundle_available_for_all_cases": True,
        "cases": cases,
        "provider_called": False,
        "held_out_accessed": False,
    }


def claim_traceable(claim: dict[str, Any], packet_case: dict[str, Any]) -> bool:
    return bool(
        isinstance(claim.get("case_id"), str)
        and isinstance(claim.get("response_sha256"), str)
        and len(claim["response_sha256"]) == 64
        and isinstance(claim.get("boundary_claim_id"), str)
        and span_valid(claim)
        and claim.get("support_label") in ALLOWED_LABELS
        and validate_resolution(claim)
        and exact_source_match(claim, packet_case)
    )


def execute_pairs(context: dict[str, Any]) -> dict[str, Any]:
    paired = context["paired"]
    cases: list[dict[str, Any]] = []
    claims_table: list[dict[str, Any]] = []
    for pair_index, case_id in enumerate(paired["candidate_order"], 1):
        candidate = paired["candidate_by_case"][case_id]
        claims = paired["claims_by_case"][case_id]
        primary = aggregate_primary(claims)
        sensitivity = aggregate_sensitivity(claims)
        non_supported_ids = [
            claim["boundary_claim_id"] for claim in claims if claim["support_label"] != "supported"
        ]
        vector = primary["atomic_support_vector"]
        nonzero_categories = sum(value > 0 for value in vector.values())
        case_record = {
            "pair_id": f"atomic-vs-candidate-{case_id}",
            "pair_index": pair_index,
            "case_id": case_id,
            "candidate_response_sha256": candidate["candidate_response_sha256"],
            "candidate_level_label": candidate["support_label"],
            "atomic_claim_count": len(claims),
            "atomic_support_vector": vector,
            "atomic_nonzero_support_category_count": nonzero_categories,
            "primary_atomic_aggregate_label": primary["label"],
            "primary_aggregation_rule": primary["applied_rule"],
            "secondary_sensitivity_labels": sensitivity,
            "mixed_support": nonzero_categories >= 2,
            "unsupported_claim_count": vector["unsupported_count"],
            "non_supported_claim_count": len(non_supported_ids),
            "non_supported_claim_ids": non_supported_ids,
            "claim_type_count": len({claim["claim_type"] for claim in claims}),
            "support_state_categories_lost_by_candidate_compression": max(0, nonzero_categories - 1),
        }
        cases.append(case_record)
        for claim_index, claim in enumerate(claims, 1):
            claims_table.append({
                "case_id": case_id,
                "pair_index": pair_index,
                "claim_index_within_case": claim_index,
                "boundary_claim_id": claim["boundary_claim_id"],
                "candidate_response_sha256": claim["response_sha256"],
                "source_field": claim["source_field"],
                "source_index": claim["source_index"],
                "source_span": claim["source_span"],
                "source_occurrence_index": claim["source_occurrence_index"],
                "claim_text": claim["claim_text"],
                "claim_type": claim["claim_type"],
                "claim_role": claim["claim_role"],
                "material": claim["material"],
                "support_label": claim["support_label"],
                "label_resolution_method": claim["label_resolution_method"],
                "traceable": claim_traceable(claim, paired["packet_by_case"][case_id]),
            })
    require(len(cases) == 10, "execution_case_count_not_10")
    require(len(claims_table) == 118, "execution_claim_count_not_118")
    return {
        "schema_version": 1,
        "execution_id": "phase7.3.3-d-atomic-vs-candidate-paired-execution-v1",
        "status": "completed_mechanical_offline_deterministic",
        "study_type": "retrospective_design_case_diagnostic_comparison",
        "not_accuracy_validation": True,
        "manifest_sha256": sha256(EXECUTION_MANIFEST),
        "input_sha256": {
            "candidate_baseline": sha256(CANDIDATE),
            "boundary_gold": sha256(BOUNDARY),
            "support_gold": sha256(SUPPORT),
            "paired_worklist": sha256(WORKLIST),
        },
        "case_count": 10,
        "claim_count": 118,
        "cases": cases,
        "claims": claims_table,
        "provider_called": False,
        "held_out_accessed": False,
        "semantic_regeneration_performed": False,
        "label_mutation_performed": False,
        "boundary_mutation_performed": False,
        "rationale_promoted_to_gold": False,
    }


def nested_counts(rows: list[dict[str, Any]], group_field: str) -> dict[str, dict[str, int]]:
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        groups[str(row[group_field])][row["support_label"]] += 1
    return {
        group: {label: counter[label] for label in ALLOWED_LABELS}
        for group, counter in sorted(groups.items())
    }


def compute_metrics(execution: dict[str, Any], execution_sha256: str | None = None) -> dict[str, Any]:
    cases = execution["cases"]
    claims = execution["claims"]
    candidate_distribution = Counter(case["candidate_level_label"] for case in cases)
    aggregate_distribution = Counter(case["primary_atomic_aggregate_label"] for case in cases)
    mixed_cases = [case for case in cases if case["mixed_support"]]
    unsupported_masking = [
        case for case in cases
        if case["candidate_level_label"] != "unsupported" and case["unsupported_claim_count"] > 0
    ]
    supported_masking_claims = [
        claim for claim in claims
        if claim["support_label"] == "supported"
        and next(case for case in cases if case["case_id"] == claim["case_id"])["candidate_level_label"] != "supported"
    ]
    non_supported = [claim for claim in claims if claim["support_label"] != "supported"]
    localized_non_supported = [claim for claim in non_supported if claim["traceable"]]
    traceable = [claim for claim in claims if claim["traceable"]]
    exact = [case for case in cases if case["candidate_level_label"] == case["primary_atomic_aggregate_label"]]
    assessable_pairs = [
        case for case in cases
        if case["candidate_level_label"] in ORDINAL and case["primary_atomic_aggregate_label"] in ORDINAL
    ]
    distances = [
        abs(ORDINAL[case["candidate_level_label"]] - ORDINAL[case["primary_atomic_aggregate_label"]])
        for case in assessable_pairs
    ]
    ordinal_severity = {
        "distance_sum": sum(distances),
        "assessable_pair_count": len(distances),
        "maximum_possible_distance_sum": 2 * len(distances),
        "value": round(sum(distances) / (2 * len(distances)), 6) if distances else None,
    }
    vectors = [tuple(case["atomic_support_vector"][f"{label}_count"] for label in ALLOWED_LABELS) for case in cases]
    unique_vectors = sorted(set(vectors))
    non_supported_by_type = Counter(claim["claim_type"] for claim in non_supported)
    non_supported_by_role = Counter(claim["claim_role"] for claim in non_supported)
    sensitivity_rows = [
        {
            "case_id": case["case_id"],
            "candidate_level_label": case["candidate_level_label"],
            "primary_multi_anchor_material_gate": case["primary_atomic_aggregate_label"],
            "strict_weakest_material_claim": case["secondary_sensitivity_labels"]["strict_weakest_material_claim"],
            "anchor_only": case["secondary_sensitivity_labels"]["anchor_only"],
        }
        for case in cases
    ]
    per_case = [
        {
            "case_id": case["case_id"],
            "candidate_response_sha256": case["candidate_response_sha256"],
            "candidate_level_label": case["candidate_level_label"],
            "atomic_support_vector": case["atomic_support_vector"],
            "primary_atomic_aggregate_label": case["primary_atomic_aggregate_label"],
            "mixed_support": case["mixed_support"],
            "unsupported_claim_count": case["unsupported_claim_count"],
            "non_supported_claim_count": case["non_supported_claim_count"],
            "non_supported_claim_ids": case["non_supported_claim_ids"],
            "claim_type_count": case["claim_type_count"],
            "support_state_categories_lost_by_candidate_compression": case["support_state_categories_lost_by_candidate_compression"],
        }
        for case in cases
    ]
    return {
        "schema_version": 1,
        "metrics_id": "phase7.3.3-d-atomic-vs-candidate-paired-metrics-v1",
        "status": "completed_mechanical_metrics_frozen_candidate",
        "study_type": "retrospective_design_case_diagnostic_comparison",
        "execution_sha256": execution_sha256 or canonical_artifact_sha(execution),
        "case_count": len(cases),
        "claim_count": len(claims),
        "candidate_label_distribution": {label: candidate_distribution[label] for label in ALLOWED_LABELS},
        "candidate_unique_label_count": len(candidate_distribution),
        "candidate_single_class_prediction_rate": ratio(max(candidate_distribution.values()), len(cases)),
        "primary_atomic_aggregate_distribution": {label: aggregate_distribution[label] for label in ALLOWED_LABELS},
        "atomic_support_vector_per_case": [
            {"case_id": case["case_id"], **case["atomic_support_vector"]} for case in cases
        ],
        "mixed_support_case_rate": ratio(len(mixed_cases), len(cases)),
        "mixed_support_case_ids": [case["case_id"] for case in mixed_cases],
        "unsupported_masking_case_rate": ratio(len(unsupported_masking), len(cases)),
        "unsupported_masking_case_ids": [case["case_id"] for case in unsupported_masking],
        "supported_content_masking_claim_count": len(supported_masking_claims),
        "supported_content_masking_claim_ids": [claim["boundary_claim_id"] for claim in supported_masking_claims],
        "non_supported_claim_localization_coverage": ratio(len(localized_non_supported), len(non_supported)),
        "non_supported_claim_count": len(non_supported),
        "partially_supported_claim_count": sum(claim["support_label"] == "partially_supported" for claim in claims),
        "unsupported_claim_count": sum(claim["support_label"] == "unsupported" for claim in claims),
        "not_assessable_claim_count": sum(claim["support_label"] == "not_assessable" for claim in claims),
        "candidate_to_primary_aggregate_exact_agreement": ratio(len(exact), len(cases)),
        "candidate_to_primary_aggregate_exact_case_ids": [case["case_id"] for case in exact],
        "candidate_to_primary_aggregate_ordinal_severity": ordinal_severity,
        "candidate_to_primary_aggregate_adjacent_disagreement_count": sum(distance == 1 for distance in distances),
        "candidate_to_primary_aggregate_extreme_disagreement_count": sum(distance == 2 for distance in distances),
        "candidate_to_primary_aggregate_not_assessable_pair_count": len(cases) - len(assessable_pairs),
        "atomic_vector_unique_state_count": len(unique_vectors),
        "atomic_vector_unique_states": [
            dict(zip((f"{label}_count" for label in ALLOWED_LABELS), vector)) for vector in unique_vectors
        ],
        "traceability_completeness": ratio(len(traceable), len(claims)),
        "diagnostic_resolution": {
            "candidate_output_unique_state_count": len(candidate_distribution),
            "atomic_vector_unique_state_count": len(unique_vectors),
            "total_locatable_non_supported_claim_count": len(localized_non_supported),
            "total_claim_type_count": len({claim["claim_type"] for claim in claims}),
            "total_support_state_categories_lost_by_candidate_compression": sum(
                case["support_state_categories_lost_by_candidate_compression"] for case in cases
            ),
        },
        "per_case_full_paired_table": per_case,
        "support_label_by_claim_type": nested_counts(claims, "claim_type"),
        "support_label_by_claim_role": nested_counts(claims, "claim_role"),
        "non_supported_claims_by_claim_type": dict(sorted(non_supported_by_type.items())),
        "non_supported_claims_by_claim_role": dict(sorted(non_supported_by_role.items())),
        "primary_vs_secondary_aggregation_sensitivity": sensitivity_rows,
        "provider_called": False,
        "held_out_accessed": False,
        "confirmatory_statistics_computed": False,
        "accuracy_superiority_computed": False,
    }



def fixture_result(name: str, passed: bool, expected: Any, observed: Any) -> dict[str, Any]:
    return {"fixture": name, "passed": passed, "expected": expected, "observed": observed}


def expect_error(name: str, operation: Callable[[], Any], expected_prefix: str) -> dict[str, Any]:
    try:
        operation()
    except Exception as exc:  # fixtures intentionally exercise contract rejection
        observed = str(exc)
        return fixture_result(name, observed.startswith(expected_prefix), expected_prefix, observed)
    return fixture_result(name, False, expected_prefix, "no_error")


def pairing_fixture_inputs(context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                                                                 list[dict[str, Any]], list[dict[str, Any]],
                                                                 list[dict[str, Any]]]:
    return (
        copy.deepcopy(context["candidate"]["decisions"]),
        copy.deepcopy(context["boundary"]["claims"]),
        copy.deepcopy(context["support"]["claims"]),
        copy.deepcopy(context["worklist"]["entries"]),
        copy.deepcopy(context["packet"]["cases"]),
    )


def run_pairing_fixtures(context: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    c, b, s, w, p = pairing_fixture_inputs(context)
    c.pop()
    results.append(expect_error("pairing_missing_case", lambda: validate_dataset(c, b, s, w, p),
                                "candidate_case_count_not_10"))

    c, b, s, w, p = pairing_fixture_inputs(context)
    c[1] = copy.deepcopy(c[0])
    results.append(expect_error("pairing_duplicate_case", lambda: validate_dataset(c, b, s, w, p),
                                "duplicate_candidate_case"))

    c, b, s, w, p = pairing_fixture_inputs(context)
    w[0]["candidate_response_sha256"] = "0" * 64
    results.append(expect_error("pairing_candidate_sha_mismatch", lambda: validate_dataset(c, b, s, w, p),
                                "worklist_candidate_sha_mismatch"))

    c, b, s, w, p = pairing_fixture_inputs(context)
    w[0], w[1] = w[1], w[0]
    results.append(expect_error("pairing_case_order_drift", lambda: validate_dataset(c, b, s, w, p),
                                "paired_case_order_mismatch"))

    c, b, s, w, p = pairing_fixture_inputs(context)
    b[1] = copy.deepcopy(b[0])
    results.append(expect_error("pairing_duplicate_atomic_claim", lambda: validate_dataset(c, b, s, w, p),
                                "duplicate_boundary_claim"))

    c, b, s, w, p = pairing_fixture_inputs(context)
    b.pop()
    results.append(expect_error("pairing_missing_atomic_claim", lambda: validate_dataset(c, b, s, w, p),
                                "boundary_claim_count_not_118"))

    c, b, s, w, p = pairing_fixture_inputs(context)
    s[0]["support_label"] = "maybe_supported"
    results.append(expect_error("pairing_illegal_support_label", lambda: validate_dataset(c, b, s, w, p),
                                "invalid_support_label"))

    c, b, s, w, p = pairing_fixture_inputs(context)
    s[0]["boundary_claim_id"] = "boundary-claim-fixture-mismatch"
    results.append(expect_error("pairing_boundary_support_claim_id_mismatch",
                                lambda: validate_dataset(c, b, s, w, p),
                                "boundary_support_claim_id_or_order_mismatch"))
    return results


def fixture_claim(identity: str, label: str, role: str = "anchor", material: bool = True) -> dict[str, Any]:
    return {"boundary_claim_id": identity, "support_label": label, "claim_role": role, "material": material}


def run_aggregation_fixtures() -> list[dict[str, Any]]:
    positive = [
        ("aggregation_all_supported", [fixture_claim("a", "supported"),
                                        fixture_claim("b", "supported", "prediction")], "supported"),
        ("aggregation_anchor_partial", [fixture_claim("a", "partially_supported")], "partially_supported"),
        ("aggregation_anchor_unsupported", [fixture_claim("a", "unsupported")], "unsupported"),
        ("aggregation_secondary_partial", [fixture_claim("a", "supported"),
                                             fixture_claim("b", "partially_supported", "prediction")],
         "partially_supported"),
        ("aggregation_secondary_unsupported", [fixture_claim("a", "supported"),
                                                 fixture_claim("b", "unsupported", "prediction")],
         "partially_supported"),
        ("aggregation_not_assessable", [fixture_claim("a", "not_assessable")], "not_assessable"),
        ("aggregation_multi_anchor", [fixture_claim("a", "supported"),
                                       fixture_claim("b", "partially_supported")], "partially_supported"),
    ]
    results = []
    for name, claims, expected in positive:
        observed = aggregate_primary(claims)["label"]
        results.append(fixture_result(name, observed == expected, expected, observed))
    results.append(expect_error("aggregation_no_anchor",
                                lambda: aggregate_primary([fixture_claim("x", "supported", "prediction")]),
                                "aggregation_missing_anchor"))
    results.append(expect_error("aggregation_empty_claim_set", lambda: aggregate_primary([]),
                                "aggregation_empty_claim_set"))
    results.append(expect_error("aggregation_unknown_claim_role",
                                lambda: aggregate_primary([fixture_claim("x", "supported", "unknown")]),
                                "aggregation_unknown_claim_role"))
    return results


def synthetic_case(case_id: str, candidate: str, aggregate: str, vector: dict[str, int]) -> dict[str, Any]:
    non_supported = vector["partially_supported_count"] + vector["unsupported_count"] + vector["not_assessable_count"]
    return {
        "case_id": case_id,
        "candidate_response_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
        "candidate_level_label": candidate,
        "primary_atomic_aggregate_label": aggregate,
        "atomic_support_vector": vector,
        "mixed_support": sum(value > 0 for value in vector.values()) >= 2,
        "unsupported_claim_count": vector["unsupported_count"],
        "non_supported_claim_count": non_supported,
        "non_supported_claim_ids": [f"{case_id}-n-{i}" for i in range(non_supported)],
        "claim_type_count": 1,
        "support_state_categories_lost_by_candidate_compression": max(0, sum(value > 0 for value in vector.values()) - 1),
        "secondary_sensitivity_labels": {"strict_weakest_material_claim": aggregate, "anchor_only": aggregate},
    }


def synthetic_claim(case_id: str, index: int, label: str) -> dict[str, Any]:
    return {
        "case_id": case_id, "boundary_claim_id": f"{case_id}-claim-{index}",
        "claim_type": "proposition", "claim_role": "anchor", "support_label": label, "traceable": True,
    }


def vector(supported: int = 0, partially_supported: int = 0,
           unsupported: int = 0, not_assessable: int = 0) -> dict[str, int]:
    return {
        "supported_count": supported, "partially_supported_count": partially_supported,
        "unsupported_count": unsupported, "not_assessable_count": not_assessable,
    }


def synthetic_execution(cases: list[dict[str, Any]], labels_by_case: list[list[str]]) -> dict[str, Any]:
    claims = [synthetic_claim(case["case_id"], index, label)
              for case, labels in zip(cases, labels_by_case)
              for index, label in enumerate(labels, 1)]
    return {"cases": cases, "claims": claims}


def run_metric_fixtures() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    specifications = [
        ("metrics_exact_agreement",
         [synthetic_case("exact", "partially_supported", "partially_supported", vector(partially_supported=1))],
         [["partially_supported"]],
         lambda m: m["candidate_to_primary_aggregate_exact_agreement"]["value"] == 1.0, True),
        ("metrics_adjacent_disagreement",
         [synthetic_case("adjacent", "partially_supported", "supported", vector(supported=1))],
         [["partially_supported"]],
         lambda m: m["candidate_to_primary_aggregate_adjacent_disagreement_count"] == 1, True),
        ("metrics_extreme_disagreement",
         [synthetic_case("extreme", "supported", "unsupported", vector(unsupported=1))],
         [["unsupported"]],
         lambda m: m["candidate_to_primary_aggregate_extreme_disagreement_count"] == 1, True),
        ("metrics_single_label_collapse",
         [synthetic_case("collapse-a", "partially_supported", "supported", vector(supported=1)),
          synthetic_case("collapse-b", "partially_supported", "partially_supported", vector(supported=1, partially_supported=1))],
         [["supported"], ["supported", "partially_supported"]],
         lambda m: m["candidate_unique_label_count"] == 1 and m["candidate_single_class_prediction_rate"]["value"] == 1.0, True),
        ("metrics_mixed_support",
         [synthetic_case("mixed", "partially_supported", "partially_supported", vector(supported=1, partially_supported=1))],
         [["supported", "partially_supported"]],
         lambda m: m["mixed_support_case_rate"]["value"] == 1.0, True),
        ("metrics_unsupported_masking",
         [synthetic_case("mask", "partially_supported", "partially_supported", vector(supported=1, unsupported=1))],
         [["supported", "unsupported"]],
         lambda m: m["unsupported_masking_case_rate"]["value"] == 1.0, True),
    ]
    for name, cases, labels, predicate, expected in specifications:
        metrics = compute_metrics(synthetic_execution(cases, labels), execution_sha256="fixture")
        observed = bool(predicate(metrics))
        results.append(fixture_result(name, observed == expected, expected, observed))
    return results


def run_contract_fixtures(context: dict[str, Any]) -> dict[str, Any]:
    groups = {
        "pairing": run_pairing_fixtures(context),
        "aggregation": run_aggregation_fixtures(),
        "metrics": run_metric_fixtures(),
    }
    all_results = [result for values in groups.values() for result in values]
    passed = sum(result["passed"] for result in all_results)
    return {
        "schema_version": 1,
        "fixture_suite_id": "phase7.3.3-d-atomic-vs-candidate-paired-contract-fixtures-v1",
        "status": "passed" if passed == len(all_results) else "failed",
        "group_counts": {name: len(values) for name, values in groups.items()},
        "total_count": len(all_results),
        "passed_count": passed,
        "failed_count": len(all_results) - passed,
        "groups": groups,
        "provider_called": False,
        "held_out_accessed": False,
    }


def manifest_input_paths() -> list[Path]:
    return [
        PROTOCOL, AGGREGATION, METRIC_SPEC, CANDIDATE, BOUNDARY, SUPPORT, WORKLIST,
        BOUNDARY_PACKET, PROTOCOL_FREEZE_MANIFEST, PROTOCOL_FREEZE_RECEIPT,
        PROTOCOL_FREEZE_OUTCOME, PROTOCOL_FIXTURES, ALIGNMENT_AUDIT_V1,
        COMPATIBILITY_REPORT, STATE_V11, READINESS_V22,
    ]


def formal_output_paths() -> list[Path]:
    return [EXECUTION, METRICS, LIMITATIONS, RESULT, RECEIPT, OUTCOME, STATE_V12, READINESS_V23]


def build_execution_manifest(evidence_audit_sha: str, fixtures_sha: str) -> dict[str, Any]:
    adapter = Path(__file__).resolve()
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-atomic-vs-candidate-paired-execution-manifest-v1",
        "status": "frozen",
        "authorized_operation": "offline_deterministic_retrospective_paired_diagnostic_execution_v1",
        "study_type": "retrospective_design_case_diagnostic_comparison",
        "reference_labels": [
            "retrospective_design_case_diagnostic_comparison",
            "not_human_gold_accuracy_validation",
            "not_generalization_evidence",
        ],
        "frozen_inputs": {rel(path): sha256(path) for path in manifest_input_paths()},
        "frozen_pre_execution_artifacts": {
            rel(EVIDENCE_AUDIT): evidence_audit_sha,
            rel(PAIRED_FIXTURES): fixtures_sha,
        },
        "adapter": {"path": rel(adapter), "sha256": sha256(adapter)},
        "required_case_count": 10,
        "required_claim_count": 118,
        "execution_environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform_system": platform.system(),
            "platform_release": platform.release(),
            "byte_order": sys.byteorder,
            "working_directory": rel(ROOT),
        },
        "expected_output_paths": [rel(path) for path in formal_output_paths()],
        "negative_result_path": rel(NEGATIVE_RESULT),
        "provider_policy": {
            "provider_calls_allowed": False,
            "provider_called": False,
            "no_provider_declaration": "all_labels_are_replayed_from_frozen_artifacts",
        },
        "held_out_policy": {
            "held_out_access_allowed": False,
            "held_out_accessed": False,
            "no_held_out_declaration": "only_frozen_ten_design_cases_are_in_scope",
        },
        "mutation_policy": {
            "candidate_mutation_allowed": False,
            "boundary_mutation_allowed": False,
            "support_label_mutation_allowed": False,
            "evidence_mutation_allowed": False,
            "semantic_regeneration_allowed": False,
            "automatic_repair_allowed": False,
            "selective_retry_allowed": False,
        },
        "failure_policy": {
            "contract_failure_is_first_class_outcome": True,
            "same_version_retry_allowed": False,
            "formal_result_allowed_after_failure": False,
        },
        "runtime_integration_authorized": False,
    }


def freeze_manifest() -> dict[str, Any]:
    context = validate_inputs(require_not_started=True)
    for path in formal_output_paths() + [NEGATIVE_RESULT]:
        require(not path.exists(), f"formal_output_exists_before_manifest:{rel(path)}")
    fixtures = run_contract_fixtures(context)
    require(fixtures["status"] == "passed", "paired_contract_fixture_suite_failed")
    evidence_sha = write_once(EVIDENCE_AUDIT, build_evidence_audit(context))
    fixtures_sha = write_once(PAIRED_FIXTURES, fixtures)
    manifest = build_execution_manifest(evidence_sha, fixtures_sha)
    manifest_sha = write_once(EXECUTION_MANIFEST, manifest)
    verify_execution_manifest(require_outputs_absent=True)
    return {
        "status": "paired_execution_manifest_frozen",
        "manifest_sha256": manifest_sha,
        "evidence_lineage_audit_sha256": evidence_sha,
        "paired_contract_fixtures_sha256": fixtures_sha,
        "fixture_count": fixtures["total_count"],
        "fixture_passed_count": fixtures["passed_count"],
        "case_count": 10,
        "claim_count": 118,
        "next_authorized_operation": "execute_offline_deterministic_paired_evaluation_v1",
        "provider_called": False,
        "held_out_accessed": False,
    }


def verify_execution_manifest(require_outputs_absent: bool) -> dict[str, Any]:
    require(EXECUTION_MANIFEST.is_file(), "paired_execution_manifest_missing")
    manifest = load(EXECUTION_MANIFEST)
    require(manifest.get("status") == "frozen", "paired_execution_manifest_not_frozen")
    require(manifest.get("authorized_operation") ==
            "offline_deterministic_retrospective_paired_diagnostic_execution_v1",
            "paired_execution_operation_not_authorized")
    for path_text, expected in manifest.get("frozen_inputs", {}).items():
        path = ROOT / Path(path_text)
        require(path.is_file(), f"manifest_input_missing:{path_text}")
        require(sha256(path) == expected, f"manifest_input_sha_mismatch:{path_text}")
    for path_text, expected in manifest.get("frozen_pre_execution_artifacts", {}).items():
        path = ROOT / Path(path_text)
        require(path.is_file(), f"manifest_pre_execution_artifact_missing:{path_text}")
        require(sha256(path) == expected, f"manifest_pre_execution_artifact_sha_mismatch:{path_text}")
    adapter = manifest.get("adapter", {})
    adapter_path = ROOT / Path(adapter.get("path", ""))
    require(adapter_path.is_file() and sha256(adapter_path) == adapter.get("sha256"),
            "manifest_adapter_sha_mismatch")
    require(manifest.get("required_case_count") == 10 and manifest.get("required_claim_count") == 118,
            "manifest_required_counts_invalid")
    require(manifest.get("provider_policy", {}).get("provider_calls_allowed") is False and
            manifest.get("provider_policy", {}).get("provider_called") is False,
            "manifest_provider_guard_invalid")
    require(manifest.get("held_out_policy", {}).get("held_out_access_allowed") is False and
            manifest.get("held_out_policy", {}).get("held_out_accessed") is False,
            "manifest_held_out_guard_invalid")
    require(manifest.get("runtime_integration_authorized") is False,
            "manifest_runtime_authorization_violation")
    require(manifest.get("expected_output_paths") == [rel(path) for path in formal_output_paths()],
            "manifest_expected_output_paths_mismatch")
    if require_outputs_absent:
        for path in formal_output_paths() + [NEGATIVE_RESULT]:
            require(not path.exists(), f"output_exists_before_formal_execution:{rel(path)}")
    fixtures = load(PAIRED_FIXTURES)
    require(fixtures.get("status") == "passed" and fixtures.get("failed_count") == 0,
            "paired_contract_fixtures_not_passed")
    audit = load(EVIDENCE_AUDIT)
    require(audit.get("status") == "passed" and audit.get("case_count") == 10,
            "evidence_lineage_audit_not_passed")
    return manifest


def build_limitations() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "limitations_id": "phase7.3.3-d-atomic-vs-candidate-paired-limitations-v1",
        "status": "frozen",
        "study_type": "retrospective_design_case_diagnostic_comparison",
        "reference_labels": [
            "retrospective_design_case_diagnostic_comparison",
            "not_human_gold_accuracy_validation",
            "not_generalization_evidence",
        ],
        "limitations": [
            "Only ten previously observed design cases are included.",
            "The Candidate lane is a historical single-Judge descriptive comparator.",
            "The Atomic lane uses a later dual-review model-adjudicated Project Support Gold.",
            "The lane asymmetry prevents causal attribution to measurement unit alone.",
            "The Atomic-derived reference cannot establish intrinsic Atomic accuracy superiority.",
            "No independent held-out replication dataset was accessed.",
            "No Human Gold was constructed or claimed.",
            "No model capability ranking or confirmatory significance claim is authorized.",
            "No runtime integration or memory-write readiness is authorized.",
        ],
        "authorized_interpretation_scope": [
            "support heterogeneity on the frozen ten cases",
            "non-supported Atomic Claim localization",
            "Candidate-label information compression",
            "deterministic aggregation sensitivity",
            "artifact traceability",
        ],
        "provider_called": False,
        "held_out_accessed": False,
        "runtime_integration_authorized": False,
    }


def build_result(execution_sha: str, metrics_sha: str, limitations_sha: str,
                 metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "result_id": "phase7.3.3-d-atomic-vs-candidate-paired-result-v1",
        "status": "frozen_exploratory_design_case_diagnostic_result",
        "study_type": "retrospective_design_case_diagnostic_comparison",
        "reference_labels": [
            "retrospective_design_case_diagnostic_comparison",
            "not_human_gold_accuracy_validation",
            "not_generalization_evidence",
        ],
        "artifact_sha256": {
            "execution": execution_sha,
            "metrics": metrics_sha,
            "limitations": limitations_sha,
            "execution_manifest": sha256(EXECUTION_MANIFEST),
        },
        "case_count": metrics["case_count"],
        "claim_count": metrics["claim_count"],
        "primary_findings": {
            "candidate_label_distribution": metrics["candidate_label_distribution"],
            "candidate_unique_label_count": metrics["candidate_unique_label_count"],
            "candidate_single_class_prediction_rate": metrics["candidate_single_class_prediction_rate"],
            "atomic_vector_unique_state_count": metrics["atomic_vector_unique_state_count"],
            "mixed_support_case_rate": metrics["mixed_support_case_rate"],
            "unsupported_masking_case_rate": metrics["unsupported_masking_case_rate"],
            "non_supported_claim_localization_coverage": metrics["non_supported_claim_localization_coverage"],
            "non_supported_claim_count": metrics["non_supported_claim_count"],
            "candidate_to_primary_aggregate_exact_agreement": metrics["candidate_to_primary_aggregate_exact_agreement"],
            "candidate_to_primary_aggregate_ordinal_severity": metrics["candidate_to_primary_aggregate_ordinal_severity"],
            "traceability_completeness": metrics["traceability_completeness"],
        },
        "authorized_conclusions": [
            "Atomic representation exposed claim-level support heterogeneity on the frozen design cases.",
            "Atomic representation localized non-supported claims on the frozen design cases.",
            "Candidate labels compressed multiple Atomic support states into one label on the frozen design cases.",
        ],
        "forbidden_conclusions": [
            "Atomic-level measurement is more accurate.",
            "Atomic-level measurement is universally superior.",
            "The findings generalize beyond the ten frozen design cases.",
            "The Project Support Gold is Human Gold.",
            "Runtime integration is ready or authorized.",
        ],
        "sensitivity_analysis_is_secondary": True,
        "accuracy_superiority_claim_authorized": False,
        "generalization_claim_authorized": False,
        "human_gold_claim_authorized": False,
        "runtime_integration_authorized": False,
        "provider_called": False,
        "held_out_accessed": False,
    }


def build_receipt(execution_sha: str, metrics_sha: str, limitations_sha: str,
                  result_sha: str, fixture_sha: str, evidence_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-atomic-vs-candidate-paired-result-freeze-receipt-v1",
        "status": "paired_result_freeze_completed",
        "execution_manifest_sha256": sha256(EXECUTION_MANIFEST),
        "paired_contract_fixtures_sha256": fixture_sha,
        "evidence_lineage_audit_sha256": evidence_sha,
        "execution_sha256": execution_sha,
        "metrics_sha256": metrics_sha,
        "limitations_sha256": limitations_sha,
        "result_sha256": result_sha,
        "case_count": 10,
        "claim_count": 118,
        "provider_called": False,
        "held_out_accessed": False,
        "runtime_integration_authorized": False,
    }


def build_state_v12(result_sha: str, receipt_sha: str, execution_sha: str,
                    metrics_sha: str, limitations_sha: str) -> dict[str, Any]:
    state = copy.deepcopy(load(STATE_V11))
    state.update({
        "schema_version": 12,
        "state_id": "phase7.3.3-d-support-stage-state-v12",
        "paired_evaluation_state": "design_case_atomic_vs_candidate_paired_result_frozen_exploratory",
        "paired_evaluation_protocol_frozen": True,
        "paired_worklist_frozen": True,
        "paired_evaluation_started": True,
        "paired_evaluation_completed": True,
        "paired_evaluation_result_frozen": True,
        "paired_evaluation_study_type": "retrospective_design_case_diagnostic_comparison",
        "paired_evaluation_case_count": 10,
        "paired_evaluation_claim_count": 118,
        "next_authorized_stage": "design_independent_replication_protocol_v1",
        "runtime_integration_authorized": False,
        "provider_called_for_paired_evaluation": False,
        "held_out_accessed": False,
    })
    state.setdefault("artifact_lineage", {}).update({
        "support_stage_state_v11_sha256": sha256(STATE_V11),
        "paired_execution_manifest_sha256": sha256(EXECUTION_MANIFEST),
        "paired_execution_sha256": execution_sha,
        "paired_metrics_sha256": metrics_sha,
        "paired_limitations_sha256": limitations_sha,
        "paired_result_sha256": result_sha,
        "paired_result_freeze_receipt_sha256": receipt_sha,
    })
    return state


def build_outcome(execution_sha: str, metrics_sha: str, result_sha: str,
                  receipt_sha: str, state_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-atomic-vs-candidate-paired-result-freeze-outcome-v1",
        "status": "passed_design_case_paired_result_frozen_exploratory",
        "study_type": "retrospective_design_case_diagnostic_comparison",
        "execution_manifest_sha256": sha256(EXECUTION_MANIFEST),
        "execution_sha256": execution_sha,
        "metrics_sha256": metrics_sha,
        "result_sha256": result_sha,
        "receipt_sha256": receipt_sha,
        "state_v12_sha256": state_sha,
        "case_count": 10,
        "claim_count": 118,
        "paired_evaluation_started": True,
        "paired_evaluation_completed": True,
        "formal_result_frozen": True,
        "negative_result_created": False,
        "next_authorized_stage": "design_independent_replication_protocol_v1",
        "provider_called": False,
        "held_out_accessed": False,
        "runtime_integration_authorized": False,
    }


def build_readiness_v23(result_sha: str, receipt_sha: str, outcome_sha: str,
                        state_sha: str) -> dict[str, Any]:
    readiness = copy.deepcopy(load(READINESS_V22))
    readiness.update({
        "schema_version": 23,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v23",
        "status": "atomic_vs_candidate_design_case_paired_result_frozen_exploratory",
        "reference_status": "project_boundary_and_support_gold_frozen_model_adjudicated_not_human_gold",
        "paired_evaluation_state": "design_case_atomic_vs_candidate_paired_result_frozen_exploratory",
        "paired_evaluation_protocol_frozen": True,
        "paired_worklist_frozen": True,
        "paired_evaluation_started": True,
        "paired_evaluation_completed": True,
        "paired_evaluation_result_frozen": True,
        "next_authorized_stage": "design_independent_replication_protocol_v1",
        "independent_replication_started": False,
        "runtime_integration_authorized": False,
        "provider_called_for_paired_evaluation": False,
        "held_out_accessed": False,
    })
    readiness.setdefault("artifact_lineage", {}).update({
        "readiness_v22_sha256": sha256(READINESS_V22),
        "support_stage_state_v12_sha256": state_sha,
        "paired_result_sha256": result_sha,
        "paired_result_freeze_receipt_sha256": receipt_sha,
        "paired_result_freeze_outcome_sha256": outcome_sha,
    })
    return readiness


def build_all_formal_artifacts(context: dict[str, Any]) -> dict[Path, Any]:
    execution = execute_pairs(context)
    execution_sha = canonical_artifact_sha(execution)
    metrics = compute_metrics(execution, execution_sha256=execution_sha)
    metrics_sha = canonical_artifact_sha(metrics)
    limitations = build_limitations()
    limitations_sha = canonical_artifact_sha(limitations)
    result = build_result(execution_sha, metrics_sha, limitations_sha, metrics)
    result_sha = canonical_artifact_sha(result)
    receipt = build_receipt(execution_sha, metrics_sha, limitations_sha, result_sha,
                            sha256(PAIRED_FIXTURES), sha256(EVIDENCE_AUDIT))
    receipt_sha = canonical_artifact_sha(receipt)
    state = build_state_v12(result_sha, receipt_sha, execution_sha, metrics_sha, limitations_sha)
    state_sha = canonical_artifact_sha(state)
    outcome = build_outcome(execution_sha, metrics_sha, result_sha, receipt_sha, state_sha)
    outcome_sha = canonical_artifact_sha(outcome)
    readiness = build_readiness_v23(result_sha, receipt_sha, outcome_sha, state_sha)
    return {
        EXECUTION: execution,
        METRICS: metrics,
        LIMITATIONS: limitations,
        RESULT: result,
        RECEIPT: receipt,
        OUTCOME: outcome,
        STATE_V12: state,
        READINESS_V23: readiness,
    }


def validate_formal_artifacts(artifacts: dict[Path, Any]) -> None:
    execution = artifacts[EXECUTION]
    metrics = artifacts[METRICS]
    result = artifacts[RESULT]
    state = artifacts[STATE_V12]
    readiness = artifacts[READINESS_V23]
    require(execution.get("case_count") == 10 and len(execution.get("cases", [])) == 10,
            "formal_execution_case_count_invalid")
    require(execution.get("claim_count") == 118 and len(execution.get("claims", [])) == 118,
            "formal_execution_claim_count_invalid")
    require(all(claim.get("traceable") is True for claim in execution["claims"]),
            "formal_execution_traceability_incomplete")
    require(metrics.get("case_count") == 10 and metrics.get("claim_count") == 118,
            "formal_metrics_counts_invalid")
    require(metrics.get("traceability_completeness", {}).get("numerator") == 118 and
            metrics.get("traceability_completeness", {}).get("denominator") == 118,
            "formal_metrics_traceability_not_118_of_118")
    require(metrics.get("partially_supported_claim_count") == 26 and
            metrics.get("unsupported_claim_count") == 6 and
            metrics.get("not_assessable_claim_count") == 0,
            "formal_metrics_support_gold_distribution_mismatch")
    require(sum(metrics.get("candidate_label_distribution", {}).values()) == 10,
            "formal_metrics_candidate_distribution_invalid")
    require(result.get("accuracy_superiority_claim_authorized") is False and
            result.get("generalization_claim_authorized") is False and
            result.get("human_gold_claim_authorized") is False,
            "formal_result_scope_guard_invalid")
    require(state.get("paired_evaluation_state") ==
            "design_case_atomic_vs_candidate_paired_result_frozen_exploratory" and
            readiness.get("paired_evaluation_state") == state.get("paired_evaluation_state"),
            "formal_final_state_invalid")
    require(state.get("next_authorized_stage") == "design_independent_replication_protocol_v1" and
            readiness.get("next_authorized_stage") == "design_independent_replication_protocol_v1",
            "formal_next_stage_invalid")
    for artifact in artifacts.values():
        require(artifact.get("held_out_accessed") is False, "formal_artifact_held_out_violation")
    require(execution.get("provider_called") is False and metrics.get("provider_called") is False and
            result.get("provider_called") is False, "formal_artifact_provider_violation")
    require(state.get("runtime_integration_authorized") is False and
            readiness.get("runtime_integration_authorized") is False,
            "formal_runtime_authorization_violation")


def build_negative_result(exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "result_id": "phase7.3.3-d-atomic-vs-candidate-paired-execution-negative-result-v1",
        "status": "authoritative_negative_result",
        "manifest_sha256": sha256(EXECUTION_MANIFEST) if EXECUTION_MANIFEST.exists() else None,
        "failure_type": type(exc).__name__,
        "failure_code": str(exc)[:1000],
        "failure_stage": "offline_deterministic_paired_execution_contract",
        "same_version_retry_allowed": False,
        "formal_result_allowed": False,
        "paired_evaluation_completed": False,
        "next_stage_authorized": False,
        "provider_called": False,
        "held_out_accessed": False,
        "runtime_integration_authorized": False,
    }


def execute_formal() -> dict[str, Any]:
    require(not NEGATIVE_RESULT.exists(), "authoritative_negative_result_exists_no_retry")
    try:
        context = validate_inputs(require_not_started=False)
        verify_execution_manifest(require_outputs_absent=True)
        artifacts = build_all_formal_artifacts(context)
        validate_formal_artifacts(artifacts)
    except Exception as exc:
        if not any(path.exists() for path in formal_output_paths()):
            negative_sha = write_once(NEGATIVE_RESULT, build_negative_result(exc))
            raise RuntimeError(f"paired_execution_failed_negative_result_frozen:{negative_sha}:{exc}") from exc
        raise

    hashes: dict[str, str] = {}
    for path in formal_output_paths():
        expected = canonical_artifact_sha(artifacts[path])
        observed = write_once(path, artifacts[path])
        require(observed == expected, f"formal_artifact_write_sha_mismatch:{rel(path)}")
        hashes[rel(path)] = observed
    verified = verify_frozen()
    return {
        "status": "design_case_atomic_vs_candidate_paired_result_frozen_exploratory",
        "case_count": 10,
        "claim_count": 118,
        "artifact_sha256": hashes,
        "verification": verified,
        "next_authorized_stage": "design_independent_replication_protocol_v1",
        "provider_called": False,
        "held_out_accessed": False,
        "runtime_integration_authorized": False,
    }


def verify_frozen() -> dict[str, Any]:
    context = validate_inputs(require_not_started=False)
    manifest = verify_execution_manifest(require_outputs_absent=False)
    require(not NEGATIVE_RESULT.exists(), "negative_result_exists_with_claimed_formal_success")
    required = [EVIDENCE_AUDIT, PAIRED_FIXTURES, EXECUTION_MANIFEST] + formal_output_paths()
    for path in required:
        require(path.is_file(), f"required_frozen_artifact_missing:{rel(path)}")
        load(path)  # JSON parse is part of verification.

    expected = build_all_formal_artifacts(context)
    for path in formal_output_paths():
        observed_value = load(path)
        require(observed_value == expected[path], f"deterministic_replay_mismatch:{rel(path)}")
        require(sha256(path) == canonical_artifact_sha(observed_value),
                f"independent_sha_recomputation_mismatch:{rel(path)}")

    execution = load(EXECUTION)
    metrics = load(METRICS)
    limitations = load(LIMITATIONS)
    result = load(RESULT)
    receipt = load(RECEIPT)
    outcome = load(OUTCOME)
    state = load(STATE_V12)
    readiness = load(READINESS_V23)
    validate_formal_artifacts(expected)

    require(execution.get("manifest_sha256") == sha256(EXECUTION_MANIFEST),
            "execution_manifest_lineage_mismatch")
    require(metrics.get("execution_sha256") == sha256(EXECUTION),
            "metrics_execution_lineage_mismatch")
    require(result.get("artifact_sha256", {}).get("execution") == sha256(EXECUTION) and
            result.get("artifact_sha256", {}).get("metrics") == sha256(METRICS) and
            result.get("artifact_sha256", {}).get("limitations") == sha256(LIMITATIONS),
            "result_artifact_lineage_mismatch")
    require(receipt.get("result_sha256") == sha256(RESULT) and
            receipt.get("execution_sha256") == sha256(EXECUTION) and
            receipt.get("metrics_sha256") == sha256(METRICS),
            "receipt_artifact_lineage_mismatch")
    require(outcome.get("receipt_sha256") == sha256(RECEIPT) and
            outcome.get("result_sha256") == sha256(RESULT) and
            outcome.get("state_v12_sha256") == sha256(STATE_V12),
            "outcome_artifact_lineage_mismatch")
    require(state.get("artifact_lineage", {}).get("paired_result_sha256") == sha256(RESULT) and
            state.get("artifact_lineage", {}).get("paired_result_freeze_receipt_sha256") == sha256(RECEIPT),
            "state_artifact_lineage_mismatch")
    require(readiness.get("artifact_lineage", {}).get("support_stage_state_v12_sha256") == sha256(STATE_V12) and
            readiness.get("artifact_lineage", {}).get("paired_result_freeze_outcome_sha256") == sha256(OUTCOME),
            "readiness_artifact_lineage_mismatch")
    require(manifest.get("adapter", {}).get("sha256") == sha256(Path(__file__).resolve()),
            "post_manifest_adapter_mutation_detected")
    require(execution.get("case_count") == 10 and execution.get("claim_count") == 118,
            "verified_execution_counts_invalid")
    require(metrics.get("traceability_completeness", {}).get("value") == 1.0,
            "verified_traceability_not_complete")
    require(outcome.get("negative_result_created") is False and
            outcome.get("formal_result_frozen") is True,
            "verified_outcome_status_invalid")
    require(state.get("paired_evaluation_started") is True and
            state.get("paired_evaluation_completed") is True and
            readiness.get("paired_evaluation_started") is True and
            readiness.get("paired_evaluation_completed") is True,
            "verified_completion_state_invalid")
    require(state.get("next_authorized_stage") == "design_independent_replication_protocol_v1" and
            readiness.get("next_authorized_stage") == "design_independent_replication_protocol_v1",
            "verified_next_stage_invalid")
    require(limitations.get("runtime_integration_authorized") is False and
            result.get("runtime_integration_authorized") is False and
            outcome.get("runtime_integration_authorized") is False,
            "verified_runtime_scope_violation")

    return {
        "status": "verified_design_case_atomic_vs_candidate_paired_result_frozen_exploratory",
        "json_artifact_count": len(required),
        "case_count": 10,
        "claim_count": 118,
        "traceable_claim_count": 118,
        "contract_fixture_count": load(PAIRED_FIXTURES)["total_count"],
        "contract_fixture_failed_count": load(PAIRED_FIXTURES)["failed_count"],
        "manifest_sha256": sha256(EXECUTION_MANIFEST),
        "execution_sha256": sha256(EXECUTION),
        "metrics_sha256": sha256(METRICS),
        "result_sha256": sha256(RESULT),
        "receipt_sha256": sha256(RECEIPT),
        "outcome_sha256": sha256(OUTCOME),
        "state_v12_sha256": sha256(STATE_V12),
        "readiness_v23_sha256": sha256(READINESS_V23),
        "negative_result_present": False,
        "provider_called": False,
        "held_out_accessed": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": "design_independent_replication_protocol_v1",
    }


def verify_inputs_command() -> dict[str, Any]:
    context = validate_inputs(require_not_started=True)
    return {
        "status": "verified_paired_execution_inputs",
        "case_count": len(context["paired"]["candidate_order"]),
        "claim_count": sum(len(value) for value in context["paired"]["claims_by_case"].values()),
        "protocol_sha256": sha256(PROTOCOL),
        "aggregation_policy_sha256": sha256(AGGREGATION),
        "metric_specification_sha256": sha256(METRIC_SPEC),
        "candidate_baseline_sha256": sha256(CANDIDATE),
        "boundary_gold_sha256": sha256(BOUNDARY),
        "support_gold_sha256": sha256(SUPPORT),
        "paired_worklist_sha256": sha256(WORKLIST),
        "evidence_packet_sha256": sha256(BOUNDARY_PACKET),
        "provider_called": False,
        "held_out_accessed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-inputs", action="store_true")
    group.add_argument("--run-contract-fixtures", action="store_true")
    group.add_argument("--freeze-manifest", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify_inputs:
            output = verify_inputs_command()
        elif args.run_contract_fixtures:
            output = run_contract_fixtures(validate_inputs(require_not_started=True))
        elif args.freeze_manifest:
            output = freeze_manifest()
        elif args.execute:
            output = execute_formal()
        else:
            output = verify_frozen()
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output.get("status", "").startswith(("verified", "passed", "paired", "design_case")) or output.get("status") == "passed" else 1
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)},
                         ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
