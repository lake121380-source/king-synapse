#!/usr/bin/env python3
"""Freeze Phase 7.3.3-D Atomic-vs-Candidate paired diagnostic protocol v1.

This gate is deliberately offline and non-executing. It validates the two
frozen measurement lanes, freezes their exact pairing/worklist and advances
the state machine only to execute_atomic_vs_candidate_paired_evaluation_v1.
It never calls a Provider and never calculates paired evaluation metrics.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

PROTOCOL = CONFIG / "phase7_3_3_d_atomic_vs_candidate_paired_evaluation_protocol_v1.json"
AGGREGATION = CONFIG / "phase7_3_3_d_atomic_vs_candidate_aggregation_policy_v1.json"
METRICS = CONFIG / "phase7_3_3_d_atomic_vs_candidate_metric_specification_v1.json"
CANDIDATE = REPORTS / "phase7_3_2_semantic_judge_execution.json"
BOUNDARY = DATA / "phase7_3_3_d_boundary_gold_v1.json"
SUPPORT = DATA / "phase7_3_3_d_support_gold_v1.json"
STATE_V10 = DATA / "phase7_3_3_d_support_stage_state_v10.json"
READINESS_V21 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v21.json"
HISTORICAL_AGGREGATOR = ROOT / "crates/eval/src/phase7_atomic_claim_measurement.rs"
OLD_COMPATIBILITY = REPORTS / "phase7_3_3_d_gold_compatibility_state_v1.json"
DUAL_LANE = REPORTS / "phase7_3_3_d_dual_lane_comparison_manifest_v1.json"

ALIGNMENT_AUDIT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_baseline_alignment_audit_v1.json"
COMPATIBILITY_REPORT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_gold_compatibility_report_v1.json"
COMPATIBILITY_STATE_V2 = REPORTS / "phase7_3_3_d_gold_compatibility_state_v2.json"
WORKLIST = DATA / "phase7_3_3_d_atomic_vs_candidate_paired_worklist_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_atomic_vs_candidate_protocol_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_atomic_vs_candidate_protocol_freeze_manifest_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_protocol_freeze_receipt_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_atomic_vs_candidate_protocol_freeze_outcome_v1.json"
STATE_V11 = DATA / "phase7_3_3_d_support_stage_state_v11.json"
READINESS_V22 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v22.json"

FORBIDDEN_EXECUTION_ARTIFACTS = (
    REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_execution_v1.json",
    REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_metrics_v1.json",
    REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_result_v1.json",
)

EXPECTED_SHA = {
    CANDIDATE: "19dba48a7666c7fbdd0002e2d86ccbdd888f5ea8f208c28feb41c1f1c2c27a67",
    BOUNDARY: "233c51af2a3c537be57a8838a8697444affea5b5b80e0835f98bab4ea567f1a0",
    SUPPORT: "845b1fe97e9357d511f52f5e9d1b995bdcb8d3b1991c27a88c5656fdeae08cf5",
    STATE_V10: "de0b2981005a87ea11329ccdc357257d78141570215accfc60b24047a4ed15dd",
    READINESS_V21: "79ebc4824bc393bf3b3c8f41a38b369e79b2508487c61167679d3483f22e7d60",
    HISTORICAL_AGGREGATOR: "1bd0611ea97083251ef070e2c0c3fe1ae397ae979283780a99be3e73f2c31a0f",
}
EXPECTED_DESIGN_SHA = "334b74dbd2e8fce9f9de7e9087e909324fe4b34cc9c0f262a6ce3a6c9f193b2d"
EXPECTED_CANDIDATE_EXECUTION_SHA = "59ca1865e770a1295def91b51248fadd2b5cff777e183fac9813abc28ca9f1e1"
ALLOWED_LABELS = {"supported", "partially_supported", "unsupported", "not_assessable"}
BOUNDARY_IMMUTABLE_FIELDS = (
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


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_once(path: Path, value: Any) -> str:
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{rel(path)}")
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as stream:
        stream.write(raw)
        temp_path = Path(stream.name)
    temp_path.replace(path)
    return digest


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_map(items: Iterable[dict[str, Any]], key: str, name: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        identity = item.get(key)
        require(isinstance(identity, str) and bool(identity), f"{name}_missing_or_invalid_{key}")
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


def aggregate_claims(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the frozen multi-anchor material gate without numeric weights."""
    require(bool(claims), "aggregation_empty_claim_set")
    ids = [claim.get("boundary_claim_id") for claim in claims]
    require(all(isinstance(x, str) and x for x in ids), "aggregation_invalid_claim_id")
    require(len(ids) == len(set(ids)), "aggregation_duplicate_claim_id")
    for claim in claims:
        require(claim.get("support_label") in ALLOWED_LABELS,
                f"aggregation_invalid_label:{claim.get('boundary_claim_id')}")
    anchors = [claim for claim in claims if claim.get("claim_role") == "anchor"]
    require(bool(anchors), "aggregation_missing_anchor")
    require(all(claim.get("material") is True for claim in anchors), "aggregation_non_material_anchor")
    labels = Counter(claim["support_label"] for claim in claims)
    vector = {
        "supported_count": labels["supported"],
        "partially_supported_count": labels["partially_supported"],
        "unsupported_count": labels["unsupported"],
        "not_assessable_count": labels["not_assessable"],
    }
    anchor_labels = {claim["support_label"] for claim in anchors}
    material_secondary = [
        claim for claim in claims
        if claim.get("claim_role") != "anchor" and claim.get("material") is True
    ]
    if "unsupported" in anchor_labels:
        aggregate = "unsupported"
        rule = "anchor_unsupported"
    elif "not_assessable" in anchor_labels:
        aggregate = "not_assessable"
        rule = "anchor_not_assessable"
    elif "partially_supported" in anchor_labels:
        aggregate = "partially_supported"
        rule = "anchor_partially_supported"
    elif any(claim["support_label"] != "supported" for claim in material_secondary):
        aggregate = "partially_supported"
        rule = "material_secondary_not_fully_supported"
    else:
        aggregate = "supported"
        rule = "all_anchors_and_material_secondary_supported"
    return {"atomic_support_vector": vector, "aggregated_candidate_label": aggregate, "applied_rule": rule}


def validate_pair_records(candidate_decisions: list[dict[str, Any]], boundary_claims: list[dict[str, Any]],
                          support_claims: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(candidate_decisions) == 10, "candidate_completed_case_count_not_10")
    candidate_by_id = unique_map(candidate_decisions, "case_id", "candidate_case")
    candidate_order = [item["case_id"] for item in candidate_decisions]
    require(len(boundary_claims) == 118, "boundary_claim_count_not_118")
    require(len(support_claims) == 118, "support_claim_count_not_118")
    boundary_by_id = unique_map(boundary_claims, "boundary_claim_id", "boundary_claim")
    support_by_id = unique_map(support_claims, "boundary_claim_id", "support_claim")
    
    boundary_ids = [claim["boundary_claim_id"] for claim in boundary_claims]
    support_ids = [claim["boundary_claim_id"] for claim in support_claims]
    require(boundary_ids == support_ids, "boundary_support_claim_id_or_order_drift")
    boundary_order = ordered_unique(claim["case_id"] for claim in boundary_claims)
    support_order = ordered_unique(claim["case_id"] for claim in support_claims)
    require(candidate_order == boundary_order == support_order, "case_order_drift")
    require(set(candidate_by_id) == set(boundary_order), "candidate_boundary_case_set_mismatch")

    claims_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for boundary_claim, support_claim in zip(boundary_claims, support_claims):
        claim_id = boundary_claim["boundary_claim_id"]
        require(support_by_id[claim_id] is support_claim, f"support_claim_internal_lookup_failure:{claim_id}")
        for field in BOUNDARY_IMMUTABLE_FIELDS:
            require(boundary_claim.get(field) == support_claim.get(field),
                    f"support_boundary_immutable_field_drift:{claim_id}:{field}")
        require(support_claim.get("support_label") in ALLOWED_LABELS, f"invalid_support_label:{claim_id}")
        case_id = boundary_claim.get("case_id")
        require(case_id in candidate_by_id, f"unknown_boundary_case:{case_id}")
        expected_response_sha = candidate_by_id[case_id].get("candidate_response_sha256")
        require(boundary_claim.get("response_sha256") == expected_response_sha,
                f"candidate_response_sha_drift:{case_id}:{claim_id}")
        claims_by_case[case_id].append(support_claim)

    case_summaries: list[dict[str, Any]] = []
    for index, case_id in enumerate(candidate_order, 1):
        decision = candidate_by_id[case_id]
        require(decision.get("support_label") in ALLOWED_LABELS, f"invalid_candidate_label:{case_id}")
        claims = claims_by_case[case_id]
        anchors = [claim for claim in claims if claim.get("claim_role") == "anchor"]
        require(bool(anchors), f"case_missing_anchor:{case_id}")
        require(all(claim.get("material") is True for claim in anchors), f"case_non_material_anchor:{case_id}")
        case_summaries.append({
            "pair_index": index,
            "case_id": case_id,
            "candidate_response_sha256": decision["candidate_response_sha256"],
            "candidate_support_label": decision["support_label"],
            "atomic_claim_count": len(claims),
            "anchor_claim_count": len(anchors),
            "material_claim_count": sum(claim.get("material") is True for claim in claims),
        })
    return {
        "candidate_case_order": candidate_order,
        "claim_ids": boundary_ids,
        "claims_by_case": dict(claims_by_case),
        "case_summaries": case_summaries,
        "candidate_by_id": candidate_by_id,
        "boundary_by_id": boundary_by_id,
        "support_by_id": support_by_id,
    }


def validate_inputs() -> dict[str, Any]:
    required = [PROTOCOL, AGGREGATION, METRICS, CANDIDATE, BOUNDARY, SUPPORT, STATE_V10,
                READINESS_V21, HISTORICAL_AGGREGATOR, OLD_COMPATIBILITY, DUAL_LANE]
    for path in required:
        require(path.is_file(), f"required_input_missing:{rel(path)}")
    for path, expected in EXPECTED_SHA.items():
        require(sha256(path) == expected, f"input_sha_mismatch:{rel(path)}")
    for path in FORBIDDEN_EXECUTION_ARTIFACTS:
        require(not path.exists(), f"paired_execution_started_before_protocol_freeze:{rel(path)}")

    protocol, aggregation, metrics = load(PROTOCOL), load(AGGREGATION), load(METRICS)
    candidate, boundary, support = load(CANDIDATE), load(BOUNDARY), load(SUPPORT)
    state, readiness = load(STATE_V10), load(READINESS_V21)
    require(protocol.get("status") == "frozen", "protocol_status_not_frozen")
    require(aggregation.get("status") == "frozen", "aggregation_status_not_frozen")
    require(metrics.get("status") == "frozen", "metric_specification_status_not_frozen")
    require(protocol.get("study_design") == "retrospective_frozen_ten_case_paired_diagnostic_analysis",
            "study_design_not_retrospective_diagnostic")
    require(protocol.get("execution_policy", {}).get("provider_calls_allowed") is False,
            "protocol_provider_call_guard_missing")
    require(protocol.get("execution_policy", {}).get("held_out_access_allowed") is False,
            "protocol_held_out_guard_missing")
    require(protocol.get("anti_circularity_guard", {}).get("independent_reference_required_for_accuracy_claims") is True,
            "anti_circularity_guard_missing")
    require(aggregation.get("primary_candidate_aggregation", {}).get("name") == "multi_anchor_material_gate",
            "unexpected_primary_aggregation_policy")
    require(metrics.get("study_type") == "retrospective_descriptive_paired_diagnostic_analysis",
            "metric_study_type_mismatch")

    require(candidate.get("status") == "completed", "candidate_execution_not_completed")
    require(candidate.get("completed_case_count") == 10, "candidate_completed_count_not_10")
    require(candidate.get("design_dataset_sha256") == EXPECTED_DESIGN_SHA, "candidate_design_sha_mismatch")
    require(candidate.get("candidate_execution_sha256") == EXPECTED_CANDIDATE_EXECUTION_SHA,
            "candidate_source_execution_sha_mismatch")
    require(candidate.get("held_out_accessed") is False, "candidate_held_out_access_detected")
    require(all(item.get("support_label") == "partially_supported" for item in candidate.get("decisions", [])),
            "historical_candidate_label_distribution_changed")

    require(boundary.get("status") == "frozen_project_boundary_gold", "boundary_gold_status_invalid")
    require(boundary.get("case_count") == 10 and boundary.get("boundary_claim_count") == 118,
            "boundary_gold_counts_invalid")
    require(boundary.get("held_out_accessed") is False, "boundary_held_out_access_detected")
    require(support.get("status") == "frozen_project_support_gold", "support_gold_status_invalid")
    require(support.get("support_gold_frozen") is True, "support_gold_not_frozen")
    require(support.get("case_count") == 10 and support.get("claim_count") == 118,
            "support_gold_counts_invalid")
    require(support.get("gold_fields") == ["support_label"], "support_gold_field_contract_changed")
    require(support.get("held_out_accessed") is False, "support_held_out_access_detected")
    require(Counter(x.get("support_label") for x in support.get("claims", [])) ==
            Counter({"supported": 86, "partially_supported": 26, "unsupported": 6}),
            "support_gold_label_distribution_changed")

    require(state.get("next_authorized_stage") == "freeze_atomic_vs_candidate_paired_evaluation_protocol_v1",
            "state_does_not_authorize_protocol_freeze")
    require(state.get("paired_evaluation_protocol_frozen") is False and
            state.get("paired_evaluation_started") is False, "state_already_advanced")
    require(readiness.get("next_authorized_stage") == "freeze_atomic_vs_candidate_paired_evaluation_protocol_v1",
            "readiness_does_not_authorize_protocol_freeze")
    require(readiness.get("paired_evaluation_protocol_frozen") is False and
            readiness.get("paired_evaluation_started") is False, "readiness_already_advanced")
    require(state.get("held_out_accessed") is False and readiness.get("held_out_accessed") is False,
            "held_out_access_detected")

    pairing = validate_pair_records(candidate["decisions"], boundary["claims"], support["claims"])
    return {
        "protocol": protocol, "aggregation": aggregation, "metrics": metrics,
        "candidate": candidate, "boundary": boundary, "support": support,
        "state": state, "readiness": readiness, "pairing": pairing,
    }


def fixture_claim(claim_id: str, label: str = "supported", role: str = "secondary",
                  material: bool = True) -> dict[str, Any]:
    return {
        "boundary_claim_id": claim_id,
        "support_label": label,
        "claim_role": role,
        "material": material,
    }


def expect_failure(name: str, action: Any, expected_fragment: str) -> dict[str, Any]:
    try:
        action()
    except ValueError as error:
        passed = expected_fragment in str(error)
        return {"fixture_id": name, "expected": "reject", "passed": passed, "observed": str(error)}
    return {"fixture_id": name, "expected": "reject", "passed": False, "observed": "accepted"}


def expect_aggregate(name: str, claims: list[dict[str, Any]], expected_label: str,
                     expected_vector: dict[str, int] | None = None) -> dict[str, Any]:
    try:
        observed = aggregate_claims(claims)
        passed = observed["aggregated_candidate_label"] == expected_label
        if expected_vector is not None:
            passed = passed and observed["atomic_support_vector"] == expected_vector
        return {"fixture_id": name, "expected": expected_label, "passed": passed, "observed": observed}
    except ValueError as error:
        return {"fixture_id": name, "expected": expected_label, "passed": False, "observed": str(error)}


def run_contract_fixtures(context: dict[str, Any] | None = None) -> dict[str, Any]:
    if context is None:
        context = validate_inputs()
    candidate = copy.deepcopy(context["candidate"]["decisions"])
    boundary = copy.deepcopy(context["boundary"]["claims"])
    support = copy.deepcopy(context["support"]["claims"])
    fixtures: list[dict[str, Any]] = []

    try:
        validate_pair_records(candidate, boundary, support)
        fixtures.append({"fixture_id": "exact_pair_acceptance", "expected": "accept", "passed": True,
                         "observed": "accepted"})
    except ValueError as error:
        fixtures.append({"fixture_id": "exact_pair_acceptance", "expected": "accept", "passed": False,
                         "observed": str(error)})

    fixtures.append(expect_failure("missing_candidate_case_rejection",
        lambda: validate_pair_records(candidate[:-1], boundary, support), "candidate_completed_case_count_not_10"))
    fixtures.append(expect_failure("extra_candidate_case_rejection",
        lambda: validate_pair_records(candidate + [dict(candidate[0], case_id="extra_case")], boundary, support),
        "candidate_completed_case_count_not_10"))
    fixtures.append(expect_failure("duplicate_candidate_case_rejection",
        lambda: validate_pair_records(candidate[:-1] + [copy.deepcopy(candidate[0])], boundary, support),
        "duplicate_candidate_case"))
    fixtures.append(expect_failure("case_order_drift_rejection",
        lambda: validate_pair_records(candidate[:1] + [candidate[2], candidate[1]] + candidate[3:], boundary, support),
        "case_order_drift"))

    changed_sha_boundary = copy.deepcopy(boundary)
    changed_sha_boundary[0]["response_sha256"] = "0" * 64
    changed_sha_support = copy.deepcopy(support)
    changed_sha_support[0]["response_sha256"] = "0" * 64
    fixtures.append(expect_failure("candidate_sha_drift_rejection",
        lambda: validate_pair_records(candidate, changed_sha_boundary, changed_sha_support),
        "candidate_response_sha_drift"))

    fixtures.extend([
        expect_aggregate("all_supported_aggregation", [
            fixture_claim("a", role="anchor"), fixture_claim("b")], "supported"),
        expect_aggregate("anchor_partial_aggregation", [
            fixture_claim("a", "partially_supported", "anchor"), fixture_claim("b")], "partially_supported"),
        expect_aggregate("anchor_unsupported_aggregation", [
            fixture_claim("a", "unsupported", "anchor"), fixture_claim("b")], "unsupported"),
        expect_aggregate("anchor_not_assessable_aggregation", [
            fixture_claim("a", "not_assessable", "anchor"), fixture_claim("b")], "not_assessable"),
        expect_aggregate("secondary_partial_aggregation", [
            fixture_claim("a", role="anchor"), fixture_claim("b", "partially_supported")], "partially_supported"),
        expect_aggregate("secondary_unsupported_maps_to_partial", [
            fixture_claim("a", role="anchor"), fixture_claim("b", "unsupported")], "partially_supported"),
        expect_aggregate("multi_anchor_supported_aggregation", [
            fixture_claim("a", role="anchor"), fixture_claim("b", role="anchor"), fixture_claim("c")], "supported"),
    ])
    fixtures.append(expect_failure("missing_anchor_rejection",
        lambda: aggregate_claims([fixture_claim("a")]), "aggregation_missing_anchor"))
    fixtures.append(expect_failure("non_material_anchor_rejection",
        lambda: aggregate_claims([fixture_claim("a", role="anchor", material=False)]),
        "aggregation_non_material_anchor"))
    fixtures.append(expect_failure("invalid_label_rejection",
        lambda: aggregate_claims([fixture_claim("a", "invented", "anchor")]), "aggregation_invalid_label"))
    fixtures.append(expect_failure("duplicate_claim_rejection",
        lambda: aggregate_claims([fixture_claim("a", role="anchor"), fixture_claim("a")]),
        "aggregation_duplicate_claim_id"))
    fixtures.append(expect_aggregate("four_class_vector_accounting", [
        fixture_claim("a", "supported", "anchor"),
        fixture_claim("b", "partially_supported"),
        fixture_claim("c", "unsupported", material=False),
        fixture_claim("d", "not_assessable", material=False),
    ], "partially_supported", {
        "supported_count": 1, "partially_supported_count": 1,
        "unsupported_count": 1, "not_assessable_count": 1,
    }))
    passed = sum(item["passed"] for item in fixtures)
    return {
        "schema_version": 1,
        "fixture_suite_id": "phase7.3.3-d-atomic-vs-candidate-protocol-contract-fixtures-v1",
        "status": "passed" if passed == len(fixtures) else "failed",
        "fixture_count": len(fixtures),
        "passed_count": passed,
        "failed_count": len(fixtures) - passed,
        "fixtures": fixtures,
        "provider_called": False,
        "held_out_accessed": False,
    }


def build_worklist(context: dict[str, Any]) -> dict[str, Any]:
    pairing = context["pairing"]
    entries = []
    for summary in pairing["case_summaries"]:
        case_id = summary["case_id"]
        claim_ids = [claim["boundary_claim_id"] for claim in pairing["claims_by_case"][case_id]]
        entries.append({
            "pair_id": f"atomic-vs-candidate-{case_id}",
            "pair_index": summary["pair_index"],
            "case_id": case_id,
            "candidate_response_sha256": summary["candidate_response_sha256"],
            "candidate_decision_locator": {
                "artifact": rel(CANDIDATE), "decision_index": summary["pair_index"] - 1,
                "case_id": case_id,
            },
            "atomic_claim_count": len(claim_ids),
            "atomic_claim_ids": claim_ids,
            "atomic_decision_locator": {
                "boundary_artifact": rel(BOUNDARY), "support_artifact": rel(SUPPORT),
                "case_id": case_id,
            },
        })
    return {
        "schema_version": 1,
        "worklist_id": "phase7.3.3-d-atomic-vs-candidate-paired-worklist-v1",
        "status": "frozen",
        "study_type": "retrospective_frozen_ten_case_paired_diagnostic_analysis",
        "case_count": len(entries),
        "claim_count": sum(item["atomic_claim_count"] for item in entries),
        "pair_identity_fields": ["case_id", "candidate_response_sha256"],
        "entries": entries,
        "contains_paired_metrics": False,
        "contains_provider_output": False,
        "provider_called": False,
        "held_out_accessed": False,
    }


def build_pre_manifest_artifacts(context: dict[str, Any], fixtures: dict[str, Any]) -> dict[Path, Any]:
    pairing = context["pairing"]
    case_summaries = pairing["case_summaries"]
    audit = {
        "schema_version": 1,
        "audit_id": "phase7.3.3-d-atomic-vs-candidate-baseline-alignment-audit-v1",
        "status": "passed",
        "alignment_contract": "exact_case_id_and_candidate_response_sha256",
        "candidate_case_count": len(context["candidate"]["decisions"]),
        "boundary_case_count": len(pairing["candidate_case_order"]),
        "support_case_count": len(pairing["candidate_case_order"]),
        "atomic_claim_count": len(pairing["claim_ids"]),
        "case_order_exact": True,
        "case_identity_exact": True,
        "candidate_response_sha256_exact": True,
        "boundary_support_claim_identity_and_order_exact": True,
        "boundary_immutable_fields_exact_in_support_gold": True,
        "cases": [
            {
                "pair_index": item["pair_index"], "case_id": item["case_id"],
                "candidate_response_sha256": item["candidate_response_sha256"],
                "atomic_claim_count": item["atomic_claim_count"],
                "anchor_claim_count": item["anchor_claim_count"],
            }
            for item in case_summaries
        ],
        "provider_called": False,
        "held_out_accessed": False,
    }
    compatibility = {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-atomic-vs-candidate-gold-compatibility-report-v1",
        "status": "frozen",
        "conclusion": "compatible_for_retrospective_diagnostic_pairing_only",
        "study_object": "diagnostic_resolution_support_heterogeneity_error_localization_and_information_masking",
        "compatible_uses": [
            "exact case pairing", "diagnostic resolution analysis",
            "deterministic aggregation replay", "information masking analysis",
        ],
        "incompatible_uses": [
            "causal measurement-protocol attribution", "intrinsic accuracy superiority",
            "model capability ranking", "generalization claims",
        ],
        "candidate_lane": {
            "status": "frozen_historical_descriptive_comparator",
            "case_count": 10,
            "measurement_unit": "candidate",
            "provider_rerun_authorized": False,
            "causal_protocol_attribution_authorized": False,
        },
        "atomic_lane": {
            "status": "frozen_project_reference_model_adjudicated_not_human_gold",
            "case_count": 10, "claim_count": 118,
            "measurement_unit": "atomic_claim",
            "gold_fields": ["support_label"],
            "provider_rerun_authorized": False,
        },
        "known_asymmetries": context["protocol"]["lanes"]["candidate_level"]["known_asymmetries"],
        "anti_circularity_guard_applied": True,
        "independent_reference_required_for_accuracy_claims": True,
        "baseline_alignment_audit_sha256": None,
        "provider_called": False,
        "held_out_accessed": False,
    }
    worklist = build_worklist(context)
    return {ALIGNMENT_AUDIT: audit, COMPATIBILITY_REPORT: compatibility, WORKLIST: worklist, FIXTURES: fixtures}


def freeze() -> dict[str, Any]:
    context = validate_inputs()
    fixtures = run_contract_fixtures(context)
    require(fixtures["status"] == "passed", "contract_fixture_suite_failed")

    pre = build_pre_manifest_artifacts(context, fixtures)
    audit_sha = write_once(ALIGNMENT_AUDIT, pre[ALIGNMENT_AUDIT])
    pre[COMPATIBILITY_REPORT]["baseline_alignment_audit_sha256"] = audit_sha
    compatibility_report_sha = write_once(COMPATIBILITY_REPORT, pre[COMPATIBILITY_REPORT])
    worklist_sha = write_once(WORKLIST, pre[WORKLIST])
    fixtures_sha = write_once(FIXTURES, pre[FIXTURES])

    compatibility_state = {
        "schema_version": 2,
        "check_id": "phase7.3.3-d-gold-compatibility-v2",
        "status": "frozen_compatible_for_retrospective_diagnostic_pairing_only",
        "supersedes_without_overwriting": rel(OLD_COMPATIBILITY),
        "historical_v1_status": load(OLD_COMPATIBILITY).get("status"),
        "historical_v1_sha256": sha256(OLD_COMPATIBILITY),
        "boundary_gold_sha256": sha256(BOUNDARY),
        "support_gold_sha256": sha256(SUPPORT),
        "candidate_baseline_sha256": sha256(CANDIDATE),
        "historical_aggregator_sha256": sha256(HISTORICAL_AGGREGATOR),
        "compatibility_classification": "compatible_for_retrospective_diagnostic_pairing_only",
        "compatibility_report_frozen": True,
        "compatibility_report_sha256": compatibility_report_sha,
        "design_model_execution_allowed": False,
        "paired_protocol_freeze_allowed": True,
        "provider_called": False,
        "held_out_accessed": False,
    }
    compatibility_state_sha = write_once(COMPATIBILITY_STATE_V2, compatibility_state)

    adapter_sha = sha256(Path(__file__))
    manifest = {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-atomic-vs-candidate-protocol-freeze-manifest-v1",
        "status": "frozen",
        "authorized_operation": "freeze_protocol_and_pairing_only",
        "study_type": "retrospective_frozen_ten_case_paired_diagnostic_analysis",
        "frozen_inputs": {
            rel(PROTOCOL): sha256(PROTOCOL), rel(AGGREGATION): sha256(AGGREGATION),
            rel(METRICS): sha256(METRICS), rel(CANDIDATE): sha256(CANDIDATE),
            rel(BOUNDARY): sha256(BOUNDARY), rel(SUPPORT): sha256(SUPPORT),
            rel(STATE_V10): sha256(STATE_V10), rel(READINESS_V21): sha256(READINESS_V21),
            rel(HISTORICAL_AGGREGATOR): sha256(HISTORICAL_AGGREGATOR),
            rel(OLD_COMPATIBILITY): sha256(OLD_COMPATIBILITY), rel(DUAL_LANE): sha256(DUAL_LANE),
        },
        "frozen_pre_execution_artifacts": {
            rel(ALIGNMENT_AUDIT): audit_sha,
            rel(COMPATIBILITY_REPORT): compatibility_report_sha,
            rel(COMPATIBILITY_STATE_V2): compatibility_state_sha,
            rel(WORKLIST): worklist_sha,
            rel(FIXTURES): fixtures_sha,
        },
        "adapter": {"path": rel(Path(__file__)), "sha256": adapter_sha},
        "case_count": 10,
        "claim_count": 118,
        "provider_calls_allowed": False,
        "provider_called": False,
        "held_out_access_allowed": False,
        "held_out_accessed": False,
        "paired_metrics_calculation_authorized": False,
        "paired_execution_started": False,
        "mutation_or_repair_authorized": False,
    }
    manifest_sha = write_once(MANIFEST, manifest)

    receipt = {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-atomic-vs-candidate-protocol-freeze-receipt-v1",
        "status": "protocol_freeze_completed",
        "manifest_sha256": manifest_sha,
        "protocol_sha256": sha256(PROTOCOL),
        "aggregation_policy_sha256": sha256(AGGREGATION),
        "metric_specification_sha256": sha256(METRICS),
        "paired_worklist_sha256": worklist_sha,
        "contract_fixtures_sha256": fixtures_sha,
        "contract_fixtures_passed": fixtures["passed_count"],
        "contract_fixtures_failed": fixtures["failed_count"],
        "case_count": 10,
        "claim_count": 118,
        "paired_evaluation_started": False,
        "provider_called": False,
        "held_out_accessed": False,
    }
    receipt_sha = write_once(RECEIPT, receipt)

    state_v11 = copy.deepcopy(context["state"])
    state_v11.update({
        "schema_version": 11,
        "state_id": "phase7.3.3-d-support-stage-state-v11",
        "paired_evaluation_state": "protocol_frozen_execution_not_started",
        "paired_evaluation_protocol_frozen": True,
        "paired_worklist_frozen": True,
        "paired_evaluation_started": False,
        "paired_evaluation_completed": False,
        "next_authorized_stage": "execute_atomic_vs_candidate_paired_evaluation_v1",
        "provider_called_for_freeze": False,
        "held_out_accessed": False,
    })
    state_v11.setdefault("artifact_lineage", {}).update({
        "support_stage_state_v10_sha256": sha256(STATE_V10),
        "paired_evaluation_protocol_sha256": sha256(PROTOCOL),
        "paired_aggregation_policy_sha256": sha256(AGGREGATION),
        "paired_metric_specification_sha256": sha256(METRICS),
        "paired_worklist_sha256": worklist_sha,
        "paired_protocol_freeze_manifest_sha256": manifest_sha,
        "paired_protocol_freeze_receipt_sha256": receipt_sha,
    })
    state_v11_sha = write_once(STATE_V11, state_v11)

    outcome = {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-atomic-vs-candidate-protocol-freeze-outcome-v1",
        "status": "passed_protocol_frozen_execution_not_started",
        "manifest_sha256": manifest_sha,
        "receipt_sha256": receipt_sha,
        "state_v11_sha256": state_v11_sha,
        "compatibility_conclusion": "compatible_for_retrospective_diagnostic_pairing_only",
        "next_authorized_stage": "execute_atomic_vs_candidate_paired_evaluation_v1",
        "paired_metrics_created": False,
        "paired_evaluation_started": False,
        "provider_called": False,
        "held_out_accessed": False,
    }
    outcome_sha = write_once(OUTCOME, outcome)

    readiness_v22 = copy.deepcopy(context["readiness"])
    readiness_v22.update({
        "schema_version": 22,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v22",
        "status": "atomic_vs_candidate_protocol_frozen_execution_authorized_not_started",
        "next_authorized_stage": "execute_atomic_vs_candidate_paired_evaluation_v1",
        "paired_evaluation_state": "protocol_frozen_execution_not_started",
        "paired_evaluation_protocol_frozen": True,
        "paired_worklist_frozen": True,
        "paired_evaluation_started": False,
        "paired_evaluation_completed": False,
        "provider_called_for_freeze": False,
        "held_out_accessed": False,
    })
    readiness_v22.setdefault("artifact_lineage", {}).update({
        "readiness_v21_sha256": sha256(READINESS_V21),
        "paired_protocol_freeze_manifest_sha256": manifest_sha,
        "paired_protocol_freeze_receipt_sha256": receipt_sha,
        "support_stage_state_v11_sha256": state_v11_sha,
        "paired_protocol_freeze_outcome_sha256": outcome_sha,
    })
    readiness_v22_sha = write_once(READINESS_V22, readiness_v22)
    return {
        "status": "passed_protocol_frozen_execution_not_started",
        "manifest_sha256": manifest_sha, "receipt_sha256": receipt_sha,
        "outcome_sha256": outcome_sha, "state_v11_sha256": state_v11_sha,
        "readiness_v22_sha256": readiness_v22_sha,
        "next_authorized_stage": "execute_atomic_vs_candidate_paired_evaluation_v1",
    }


def verify_frozen() -> dict[str, Any]:
    validate_inputs()
    required_outputs = [ALIGNMENT_AUDIT, COMPATIBILITY_REPORT, COMPATIBILITY_STATE_V2, WORKLIST,
                        FIXTURES, MANIFEST, RECEIPT, OUTCOME, STATE_V11, READINESS_V22]
    for path in required_outputs:
        require(path.is_file(), f"frozen_artifact_missing:{rel(path)}")
    for path in FORBIDDEN_EXECUTION_ARTIFACTS:
        require(not path.exists(), f"forbidden_paired_execution_artifact_exists:{rel(path)}")

    fixtures = load(FIXTURES)
    require(fixtures.get("status") == "passed" and fixtures.get("failed_count") == 0,
            "frozen_contract_fixtures_not_passed")
    worklist = load(WORKLIST)
    require(worklist.get("status") == "frozen", "worklist_not_frozen")
    require(worklist.get("case_count") == 10 and worklist.get("claim_count") == 118,
            "worklist_counts_invalid")
    require(worklist.get("contains_paired_metrics") is False and
            worklist.get("contains_provider_output") is False, "worklist_scope_violation")

    manifest = load(MANIFEST)
    require(manifest.get("status") == "frozen", "manifest_not_frozen")
    for path_text, expected in manifest.get("frozen_inputs", {}).items():
        path = ROOT / Path(path_text)
        require(path.is_file() and sha256(path) == expected, f"manifest_input_hash_mismatch:{path_text}")
    for path_text, expected in manifest.get("frozen_pre_execution_artifacts", {}).items():
        path = ROOT / Path(path_text)
        require(path.is_file() and sha256(path) == expected, f"manifest_artifact_hash_mismatch:{path_text}")
    require(manifest.get("provider_called") is False and manifest.get("held_out_accessed") is False,
            "manifest_provider_or_held_out_violation")
    require(manifest.get("paired_execution_started") is False and
            manifest.get("paired_metrics_calculation_authorized") is False,
            "manifest_execution_scope_violation")

    state = load(STATE_V11)
    readiness = load(READINESS_V22)
    for name, artifact in (("state", state), ("readiness", readiness)):
        require(artifact.get("paired_evaluation_state") == "protocol_frozen_execution_not_started",
                f"{name}_paired_state_invalid")
        require(artifact.get("paired_evaluation_protocol_frozen") is True, f"{name}_protocol_not_frozen")
        require(artifact.get("paired_worklist_frozen") is True, f"{name}_worklist_not_frozen")
        require(artifact.get("paired_evaluation_started") is False, f"{name}_execution_started")
        require(artifact.get("paired_evaluation_completed") is False, f"{name}_execution_completed")
        require(artifact.get("next_authorized_stage") == "execute_atomic_vs_candidate_paired_evaluation_v1",
                f"{name}_next_stage_invalid")
        require(artifact.get("provider_called_for_freeze") is False and
                artifact.get("held_out_accessed") is False, f"{name}_provider_or_held_out_violation")
    return {
        "status": "verified_protocol_frozen_execution_not_started",
        "artifact_count": len(required_outputs),
        "case_count": 10,
        "claim_count": 118,
        "manifest_sha256": sha256(MANIFEST),
        "state_v11_sha256": sha256(STATE_V11),
        "readiness_v22_sha256": sha256(READINESS_V22),
        "forbidden_execution_artifacts_present": False,
        "provider_called": False,
        "held_out_accessed": False,
        "next_authorized_stage": "execute_atomic_vs_candidate_paired_evaluation_v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-inputs", action="store_true")
    group.add_argument("--run-contract-fixtures", action="store_true")
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify_inputs:
        context = validate_inputs()
        result = {
            "status": "inputs_verified",
            "case_count": len(context["pairing"]["candidate_case_order"]),
            "claim_count": len(context["pairing"]["claim_ids"]),
            "provider_called": False,
            "held_out_accessed": False,
        }
    elif args.run_contract_fixtures:
        result = run_contract_fixtures()
        require(result["status"] == "passed", "contract_fixture_suite_failed")
    elif args.freeze:
        result = freeze()
    else:
        result = verify_frozen()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
