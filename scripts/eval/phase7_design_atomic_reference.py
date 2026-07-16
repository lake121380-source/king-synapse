#!/usr/bin/env python3
"""Freeze and verify Phase 7.3.3-D1 reference-construction infrastructure.

This script is deliberately offline. It never calls a provider, never opens held-out
artifacts, and never constructs support Gold before Boundary Gold is frozen.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
CONFIG = ROOT / "crates/eval/config"
REPORTS = ROOT / "crates/eval/reports"

DESIGN = DATA / "phase7_2_pattern_extraction_design.json"
PROVIDER_EXECUTION = REPORTS / "phase7_2_3_real_provider_execution.json"
BLIND_PACKET = DATA / "phase7_3_1_blind_review_packet.json"
SILVER = DATA / "phase7_3_1_model_adjudicated_silver_labels.json"
HISTORICAL_A = REPORTS / "phase7_3_2_semantic_judge_execution.json"
AGGREGATOR_SOURCE = ROOT / "crates/eval/src/phase7_atomic_claim_measurement.rs"

POLICY = CONFIG / "phase7_3_3_d_reference_construction_policy_v1.json"
BOUNDARY_PROTOCOL = DATA / "phase7_3_3_d_boundary_reference_protocol_v1.json"
SUPPORT_PROTOCOL = DATA / "phase7_3_3_d_support_reference_protocol_v1.json"
BOUNDARY_PACKET = DATA / "phase7_3_3_d_boundary_blind_review_packet_v1.json"
BOUNDARY_A = DATA / "phase7_3_3_d_boundary_reviewer_a_template_v1.json"
BOUNDARY_B = DATA / "phase7_3_3_d_boundary_reviewer_b_template_v1.json"
BOUNDARY_AGREEMENT = REPORTS / "phase7_3_3_d_boundary_agreement_template_v1.json"
BOUNDARY_ADJ = DATA / "phase7_3_3_d_boundary_adjudication_template_v1.json"
SUPPORT_A = DATA / "phase7_3_3_d_support_reviewer_a_template_v1.json"
SUPPORT_B = DATA / "phase7_3_3_d_support_reviewer_b_template_v1.json"
SUPPORT_AGREEMENT = REPORTS / "phase7_3_3_d_support_agreement_template_v1.json"
SUPPORT_ADJ = DATA / "phase7_3_3_d_support_adjudication_template_v1.json"
SUPPORT_STATE = DATA / "phase7_3_3_d_support_stage_state_v1.json"
COMPATIBILITY_STATE = REPORTS / "phase7_3_3_d_gold_compatibility_state_v1.json"
COMPARISON_MANIFEST = REPORTS / "phase7_3_3_d_dual_lane_comparison_manifest_v1.json"
READINESS = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v2.json"

CLAIM_TYPES = [
    "proposition", "scope", "prediction", "causal", "counterexample",
    "limitation", "falsifiability",
]
CLAIM_ORIGINS = ["explicit", "inferred", "synthesized"]
SUPPORT_LABELS = ["supported", "partially_supported", "unsupported", "not_assessable"]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_once(path: Path, value: Any) -> str:
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"frozen_artifact_changed:{path.relative_to(ROOT)}")
        return hashlib.sha256(encoded).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temp = Path(handle.name)
    temp.replace(path)
    return hashlib.sha256(encoded).hexdigest()


def source_hashes() -> dict[str, str]:
    return {
        "design_dataset": sha256_file(DESIGN),
        "real_provider_execution": sha256_file(PROVIDER_EXECUTION),
        "phase7_3_1_blind_packet": sha256_file(BLIND_PACKET),
        "model_adjudicated_silver_labels": sha256_file(SILVER),
        "historical_pipeline_a_execution": sha256_file(HISTORICAL_A),
        "frozen_aggregator_source": sha256_file(AGGREGATOR_SOURCE),
    }


def verify_source_lineage() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    design = load(DESIGN)
    provider = load(PROVIDER_EXECUTION)
    packet = load(BLIND_PACKET)
    silver = load(SILVER)
    historical = load(HISTORICAL_A)

    if len(design["cases"]) != 10 or len({c["id"] for c in design["cases"]}) != 10:
        raise ValueError("expected_10_unique_design_cases")
    if provider.get("completed_design_cases") != 10 or len(provider.get("outputs", [])) != 10:
        raise ValueError("real_provider_execution_not_complete")
    if packet.get("held_out_accessed") is not False or len(packet.get("cases", [])) != 10:
        raise ValueError("blind_packet_invalid_or_held_out_accessed")
    if silver.get("human_gold") is not False or silver.get("label_status") != "model_adjudicated_silver_not_human_gold":
        raise ValueError("historical_reference_must_remain_silver")
    if historical.get("completed_case_count") != 10 or len(historical.get("decisions", [])) != 10:
        raise ValueError("historical_pipeline_a_not_complete")

    design_by_id = {row["id"]: row for row in design["cases"]}
    provider_by_id = {row["case_id"]: row for row in provider["outputs"]}
    packet_by_id = {row["case_id"]: row for row in packet["cases"]}
    expected_ids = sorted(design_by_id)
    if sorted(provider_by_id) != expected_ids or sorted(packet_by_id) != expected_ids:
        raise ValueError("design_case_id_lineage_mismatch")

    canonical: list[dict[str, Any]] = []
    for case_id in expected_ids:
        d = design_by_id[case_id]
        p = provider_by_id[case_id]
        b = packet_by_id[case_id]
        if b["response_sha256"] != p["response_sha256"] or b["candidate"] != p["candidate"]:
            raise ValueError(f"candidate_lineage_mismatch:{case_id}")
        if b["evidence_input"] != d["input"]:
            raise ValueError(f"evidence_lineage_mismatch:{case_id}")
        anchors = b.get("claim_source_anchors", [])
        if not anchors:
            raise ValueError(f"missing_claim_source_anchors:{case_id}")
        seen_anchor_ids: set[str] = set()
        for anchor in anchors:
            if anchor["anchor_id"] in seen_anchor_ids:
                raise ValueError(f"duplicate_anchor_id:{anchor['anchor_id']}")
            seen_anchor_ids.add(anchor["anchor_id"])
            if anchor["case_id"] != case_id or anchor["response_sha256"] != p["response_sha256"]:
                raise ValueError(f"anchor_lineage_mismatch:{anchor['anchor_id']}")
            if sha256_text(anchor["source_text"]) != anchor["source_text_sha256"]:
                raise ValueError(f"anchor_text_hash_mismatch:{anchor['anchor_id']}")
        canonical.append({
            "case_id": case_id,
            "response_sha256": p["response_sha256"],
            "evidence_input": b["evidence_input"],
            "candidate": b["candidate"],
            "claim_source_anchors": anchors,
        })
    return canonical, historical


def build_policy(hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d-reference-construction-policy-v1",
        "phase": "Phase 7.3.3-D1 Reference Construction",
        "research_question": "Whether protocol-owned Atomic Claims plus deterministic aggregation improve diagnostic visibility and attribution without materially degrading Candidate-level discrimination.",
        "measurement_objects": {
            "evidence_bundle": "frozen_assumed_correct_not_studied",
            "candidate": "studied",
            "boundary_reference": "constructed_then_frozen",
            "support_reference": "constructed_only_after_boundary_freeze",
            "historical_candidate_judge": "frozen_descriptive_comparator",
            "extractor_prompt_provider": "frozen_not_studied",
        },
        "irreversible_stage_order": [
            "d1_a_boundary_review", "d1_a_boundary_agreement", "d1_a_boundary_adjudication_and_freeze",
            "d1_b_support_review", "d1_b_support_agreement", "d1_b_support_adjudication_and_freeze",
            "d1_c_gold_compatibility_check_and_freeze", "d2_model_execution", "d3_comparison",
        ],
        "hard_gates": {
            "support_before_boundary_gold": "forbidden",
            "compatibility_before_support_gold": "forbidden",
            "design_model_execution_before_compatibility_freeze": "forbidden",
            "held_out_access": "forbidden",
            "prompt_parser_aggregator_threshold_tuning_after_first_execution": "forbidden",
            "automatic_repair": "forbidden",
            "selective_semantic_retry": "forbidden",
            "first_returned_provider_output_authoritative": True,
        },
        "historical_reference_status": "model_adjudicated_silver_not_human_gold",
        "source_artifact_sha256": hashes,
    }


def build_boundary_protocol(hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d1-a-boundary-reference-protocol-v1",
        "purpose": "Independently identify Atomic Claim boundaries and structural metadata without support decisions.",
        "unit_of_review": "one source anchor within one frozen real-provider Candidate",
        "reviewer_visible": ["frozen_evidence_bundle", "candidate_source_anchor_text", "source_field", "source_index", "boundary_annotation_rules"],
        "reviewer_prohibited": [
            "support_labels", "candidate_gold_or_silver_labels", "historical_or_new_judge_outputs",
            "gold_evidence_attribution", "other_reviewer_submission", "phase7_3_aggregate_metrics",
            "reference_candidate", "held_out_cases",
        ],
        "required_claim_fields": [
            "reviewer_claim_id", "source_span", "claim_text", "claim_type", "centrality",
            "material", "claim_origin", "boundary_rationale", "annotation_confidence",
        ],
        "claim_type_enum": CLAIM_TYPES,
        "claim_origin_enum": CLAIM_ORIGINS,
        "span_semantics": "UTF-8 decoded Python string code-point offsets [start,end) within exactly one source_text anchor.",
        "boundary_rules": [
            "Every independently truth-evaluable assertion must receive its own non-empty span.",
            "Claims may not cross source-anchor boundaries.",
            "Overlapping claims require an explicit split_or_overlap rationale.",
            "Do not assign support labels or evidence IDs.",
            "Claim origin is structural provenance only: explicit, inferred, or synthesized; it is not a support decision.",
        ],
        "agreement_metrics": [
            "claim_count_agreement", "exact_span_agreement", "span_iou", "claim_type_agreement",
            "centrality_agreement", "material_agreement", "claim_origin_agreement",
            "split_merge_disagreement_count", "fundamental_boundary_disagreement_count",
        ],
        "freeze_rule": "Boundary Gold may freeze only after two completed blind submissions, an immutable Agreement Report hash, and completed adjudication.",
        "source_artifact_sha256": hashes,
    }


def build_support_protocol(hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d1-b-support-reference-protocol-v1",
        "purpose": "Independently judge support for immutable Boundary Gold Claims.",
        "entry_gate": "boundary_state must be agreed or adjudicated and Boundary Gold SHA-256 must be present",
        "boundary_mutation": "forbidden",
        "reviewer_visible": ["frozen_evidence_bundle", "frozen_boundary_claims", "support_label_definitions", "reason_code_definitions"],
        "reviewer_prohibited": [
            "candidate_gold_or_silver_labels", "historical_or_new_judge_outputs", "other_reviewer_submission",
            "phase7_3_aggregate_metrics", "reference_candidate", "held_out_cases",
        ],
        "required_support_fields": [
            "boundary_claim_id", "support_label", "cited_evidence_ids", "reason_codes",
            "support_rationale", "annotation_confidence",
        ],
        "support_label_enum": SUPPORT_LABELS,
        "agreement_metrics": [
            "exact_support_agreement", "cohen_kappa", "krippendorff_alpha",
            "supported_partial_disagreements", "partial_unsupported_disagreements",
            "fundamental_support_disagreements", "evidence_attribution_agreement",
        ],
        "state_rule": "If boundary_state is disputed or invalid, support_state must be blocked.",
        "freeze_rule": "Support Gold may freeze only after two completed blind submissions, an immutable Agreement Report hash, and completed adjudication referencing Boundary Gold SHA-256.",
        "source_artifact_sha256": hashes,
    }


def boundary_packet(cases: list[dict[str, Any]], hashes: dict[str, str]) -> dict[str, Any]:
    rows=[]
    for case in cases:
        evidence = dict(case["evidence_input"])
        evidence.pop("prohibited_inputs", None)
        rows.append({
            "case_id": case["case_id"],
            "response_sha256": case["response_sha256"],
            "evidence_input": evidence,
            "candidate_identity": {
                "candidate_id": case["candidate"]["id"],
                "candidate_status": case["candidate"]["status"],
            },
            "source_anchors": [{
                "anchor_id": a["anchor_id"],
                "source_field": a["source_field"],
                "source_index": a["source_index"],
                "source_text": a["source_text"],
                "source_text_sha256": a["source_text_sha256"],
            } for a in case["claim_source_anchors"]],
        })
    packet={
        "schema_version": 1,
        "packet_id": "phase7.3.3-d1-a-boundary-blind-review-packet-v1",
        "protocol_id": "phase7.3.3-d1-a-boundary-reference-protocol-v1",
        "packet_role": "boundary_only_blind_review",
        "case_count": len(rows),
        "blind_to_support_labels": True,
        "blind_to_candidate_gold_or_silver": True,
        "blind_to_judge_outputs": True,
        "blind_to_other_reviewer": True,
        "held_out_accessed": False,
        "reference_candidates_visible": False,
        "source_artifact_sha256": hashes,
        "cases": rows,
    }
    def all_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(all_keys(v) for v in value.values()), set())
        if isinstance(value, list):
            return set().union(*(all_keys(v) for v in value), set())
        return set()
    forbidden_keys={
        "final_support_label", "aggregate_support_label", "support_label",
        "unsupported_claim_rate", "judge_warning", "reference_candidate",
    }
    leaked=sorted(forbidden_keys & all_keys(packet))
    if leaked:
        raise ValueError(f"boundary_packet_leakage:{leaked}")
    return packet


def boundary_template(reviewer: str, packet_hash: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "submission_id": f"phase7.3.3-d1-a-boundary-reviewer-{reviewer.lower()}-submission-v1",
        "reviewer_id": f"reviewer_{reviewer.lower()}",
        "reviewer_role": "independent_boundary_reviewer",
        "protocol_id": "phase7.3.3-d1-a-boundary-reference-protocol-v1",
        "boundary_packet_sha256": packet_hash,
        "completed": False,
        "blind_to_other_reviewer": True,
        "blind_to_support_labels": True,
        "held_out_accessed": False,
        "cases": [{
            "case_id": c["case_id"],
            "response_sha256": c["response_sha256"],
            "anchors": [{
                "anchor_id": a["anchor_id"],
                "source_text_sha256": a["source_text_sha256"],
                "boundary_claims": [],
                "anchor_review_complete": False,
            } for a in c["claim_source_anchors"]],
            "case_review_complete": False,
        } for c in cases],
        "completion_attestation": {
            "support_labels_not_used": False,
            "candidate_labels_not_used": False,
            "other_reviewer_not_seen": False,
            "all_spans_verified_against_source": False,
        },
    }


def boundary_agreement_template(packet_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "report_id": "phase7.3.3-d1-a-boundary-agreement-v1",
        "protocol_id": "phase7.3.3-d1-a-boundary-reference-protocol-v1",
        "boundary_packet_sha256": packet_hash,
        "status": "unavailable",
        "blocked_reason": "two_completed_independent_boundary_reviews_required",
        "reviewer_a_submission_sha256": None,
        "reviewer_b_submission_sha256": None,
        "metrics": {
            "claim_count_agreement": None,
            "exact_span_agreement": None,
            "mean_span_iou": None,
            "claim_type_agreement": None,
            "centrality_agreement": None,
            "material_agreement": None,
            "claim_origin_agreement": None,
        },
        "disagreement_counts": {
            "split_merge": None,
            "fundamental_boundary": None,
            "type": None,
            "centrality": None,
            "material": None,
            "origin": None,
        },
        "agreement_computed_before_adjudication": True,
        "held_out_accessed": False,
    }


def boundary_adjudication_template(packet_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "adjudication_id": "phase7.3.3-d1-a-boundary-adjudication-v1",
        "protocol_id": "phase7.3.3-d1-a-boundary-reference-protocol-v1",
        "boundary_packet_sha256": packet_hash,
        "boundary_state": "not_started",
        "completed": False,
        "entry_requirements": {
            "reviewer_a_completed": False,
            "reviewer_b_completed": False,
            "agreement_report_available": False,
            "agreement_report_sha256": None,
        },
        "lineage": {
            "reviewer_a_submission_sha256": None,
            "reviewer_b_submission_sha256": None,
            "agreement_report_sha256": None,
        },
        "adjudicated_claims": [],
        "disagreements_preserved": False,
        "boundary_gold_frozen": False,
        "boundary_gold_sha256": None,
        "held_out_accessed": False,
    }


def blocked_support_reviewer_template(reviewer: str, hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "submission_id": f"phase7.3.3-d1-b-support-reviewer-{reviewer.lower()}-submission-v1",
        "reviewer_id": f"reviewer_{reviewer.lower()}",
        "reviewer_role": "independent_support_reviewer",
        "protocol_id": "phase7.3.3-d1-b-support-reference-protocol-v1",
        "status": "blocked",
        "blocked_reason": "boundary_gold_not_frozen",
        "boundary_gold_sha256": None,
        "completed": False,
        "blind_to_other_reviewer": True,
        "blind_to_candidate_gold_or_silver": True,
        "held_out_accessed": False,
        "claims": [],
        "immutable_boundary_fields_attested": False,
        "source_artifact_sha256": hashes,
    }


def blocked_support_agreement_template() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "report_id": "phase7.3.3-d1-b-support-agreement-v1",
        "protocol_id": "phase7.3.3-d1-b-support-reference-protocol-v1",
        "status": "blocked",
        "blocked_reason": "boundary_gold_and_two_completed_support_reviews_required",
        "boundary_gold_sha256": None,
        "reviewer_a_submission_sha256": None,
        "reviewer_b_submission_sha256": None,
        "metrics": {
            "exact_support_agreement": None,
            "cohen_kappa": None,
            "krippendorff_alpha": None,
            "evidence_attribution_agreement": None,
        },
        "disagreement_counts": {
            "supported_partial": None,
            "partial_unsupported": None,
            "fundamental": None,
            "evidence_attribution": None,
        },
        "agreement_computed_before_adjudication": True,
        "held_out_accessed": False,
    }


def blocked_support_adjudication_template() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "adjudication_id": "phase7.3.3-d1-b-support-adjudication-v1",
        "protocol_id": "phase7.3.3-d1-b-support-reference-protocol-v1",
        "status": "blocked",
        "blocked_reason": "boundary_gold_and_support_agreement_not_available",
        "boundary_gold_sha256": None,
        "support_agreement_report_sha256": None,
        "completed": False,
        "adjudicated_support_labels": [],
        "support_gold_frozen": False,
        "support_gold_sha256": None,
        "held_out_accessed": False,
    }


def support_state(hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "state_id": "phase7.3.3-d1-b-support-stage-state-v1",
        "boundary_state": "not_started",
        "support_state": "blocked",
        "blocked_reason": "boundary_gold_not_frozen",
        "boundary_gold_sha256": None,
        "support_review_packets_generated": False,
        "support_reviewer_a_completed": False,
        "support_reviewer_b_completed": False,
        "support_agreement_available": False,
        "support_adjudication_allowed": False,
        "support_gold_frozen": False,
        "support_gold_sha256": None,
        "immutable_boundary_claim_fields": [
            "boundary_claim_id", "case_id", "anchor_id", "source_span", "claim_text",
            "claim_type", "centrality", "material", "claim_origin",
        ],
        "source_artifact_sha256": hashes,
    }


def compatibility_state(hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "check_id": "phase7.3.3-d1-c-gold-compatibility-v1",
        "status": "blocked",
        "blocked_reason": "boundary_and_support_gold_not_frozen",
        "boundary_gold_sha256": None,
        "support_gold_sha256": None,
        "aggregator_sha256": hashes["frozen_aggregator_source"],
        "historical_candidate_reference_status": "model_adjudicated_silver_not_human_gold",
        "historical_candidate_reference_sha256": hashes["model_adjudicated_silver_labels"],
        "classification_enum": ["compatible", "gold_granularity_disagreement", "gold_aggregation_incompatibility"],
        "compatibility_report_frozen": False,
        "compatibility_report_sha256": None,
        "design_model_execution_allowed": False,
        "held_out_accessed": False,
    }


def comparison_manifest(hashes: dict[str, str], historical: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-dual-lane-comparison-manifest-v1",
        "status": "blocked_pending_d1_c_compatibility_freeze",
        "design_case_count": 10,
        "held_out_accessed": False,
        "d2_a_historical_lane": {
            "purpose": "descriptive_project_evolution_only",
            "execution_sha256": hashes["historical_pipeline_a_execution"],
            "requested_model": historical["model_requested"],
            "resolved_model": historical["resolved_model"],
            "prompt_version": historical["prompt_version"],
            "prompt_sha256": historical["prompt_sha256"],
            "causal_protocol_attribution_authorized": False,
            "model_version_confounded": True,
            "rerun_allowed": False,
        },
        "d2_b_contemporaneous_controlled_lane": {
            "purpose": "causal_measurement_unit_comparison",
            "status": "not_executable",
            "entry_gate": "D1-C compatibility report frozen",
            "same_provider_required": True,
            "same_requested_model_required": True,
            "same_resolved_model_required": True,
            "same_temperature_top_p_required": True,
            "same_evidence_and_design_cases_required": True,
            "close_execution_window_required": True,
            "separately_frozen_prompts_and_parsers_required": True,
            "first_response_authoritative": True,
            "resolved_model_hard_gate": "Pipeline A resolved_model must equal Pipeline B resolved_model or controlled_comparison_available=false",
            "controlled_comparison_available": False,
        },
        "source_artifact_sha256": hashes,
    }


def main() -> int:
    cases, historical = verify_source_lineage()
    hashes = source_hashes()
    artifact_hashes: dict[str, str] = {}
    artifact_hashes[str(POLICY.relative_to(ROOT))] = atomic_write_once(POLICY, build_policy(hashes))
    artifact_hashes[str(BOUNDARY_PROTOCOL.relative_to(ROOT))] = atomic_write_once(BOUNDARY_PROTOCOL, build_boundary_protocol(hashes))
    artifact_hashes[str(SUPPORT_PROTOCOL.relative_to(ROOT))] = atomic_write_once(SUPPORT_PROTOCOL, build_support_protocol(hashes))
    packet = boundary_packet(cases, hashes)
    packet_hash = atomic_write_once(BOUNDARY_PACKET, packet)
    artifact_hashes[str(BOUNDARY_PACKET.relative_to(ROOT))] = packet_hash
    artifact_hashes[str(BOUNDARY_A.relative_to(ROOT))] = atomic_write_once(BOUNDARY_A, boundary_template("A", packet_hash, cases))
    artifact_hashes[str(BOUNDARY_B.relative_to(ROOT))] = atomic_write_once(BOUNDARY_B, boundary_template("B", packet_hash, cases))
    artifact_hashes[str(BOUNDARY_AGREEMENT.relative_to(ROOT))] = atomic_write_once(BOUNDARY_AGREEMENT, boundary_agreement_template(packet_hash))
    artifact_hashes[str(BOUNDARY_ADJ.relative_to(ROOT))] = atomic_write_once(BOUNDARY_ADJ, boundary_adjudication_template(packet_hash))
    artifact_hashes[str(SUPPORT_A.relative_to(ROOT))] = atomic_write_once(SUPPORT_A, blocked_support_reviewer_template("A", hashes))
    artifact_hashes[str(SUPPORT_B.relative_to(ROOT))] = atomic_write_once(SUPPORT_B, blocked_support_reviewer_template("B", hashes))
    artifact_hashes[str(SUPPORT_AGREEMENT.relative_to(ROOT))] = atomic_write_once(SUPPORT_AGREEMENT, blocked_support_agreement_template())
    artifact_hashes[str(SUPPORT_ADJ.relative_to(ROOT))] = atomic_write_once(SUPPORT_ADJ, blocked_support_adjudication_template())
    artifact_hashes[str(SUPPORT_STATE.relative_to(ROOT))] = atomic_write_once(SUPPORT_STATE, support_state(hashes))
    artifact_hashes[str(COMPATIBILITY_STATE.relative_to(ROOT))] = atomic_write_once(COMPATIBILITY_STATE, compatibility_state(hashes))
    artifact_hashes[str(COMPARISON_MANIFEST.relative_to(ROOT))] = atomic_write_once(COMPARISON_MANIFEST, comparison_manifest(hashes, historical))

    readiness = {
        "schema_version": 1,
        "report_id": "phase7.3.3-d1-reference-construction-readiness-v2",
        "status": "boundary_review_ready_support_blocked",
        "design_case_count": 10,
        "canonical_candidate_source": "phase7_2_3_real_provider_execution.json via verified phase7_3_1_blind_review_packet lineage",
        "reference_candidate_used": False,
        "historical_reference_status": "model_adjudicated_silver_not_human_gold",
        "boundary_packet_ready": True,
        "boundary_reviewer_templates_ready": True,
        "boundary_agreement_available": False,
        "boundary_adjudication_allowed": False,
        "boundary_gold_frozen": False,
        "support_templates_ready_but_blocked": True,
        "support_stage_state": "blocked",
        "support_blocked_reason": "boundary_gold_not_frozen",
        "compatibility_check_state": "blocked",
        "design_model_execution_allowed": False,
        "historical_lane_descriptive_only": True,
        "controlled_lane_available": False,
        "held_out_accessed": False,
        "provider_called": False,
        "artifact_sha256": artifact_hashes,
        "source_artifact_sha256": hashes,
        "next_required_action": "Obtain two independent Boundary-only reviews using the frozen packet; then compute Agreement before adjudication.",
    }
    readiness_hash = atomic_write_once(READINESS, readiness)
    print(json.dumps({
        "status": readiness["status"],
        "readiness_sha256": readiness_hash,
        "boundary_packet_sha256": packet_hash,
        "artifact_count": len(artifact_hashes) + 1,
        "design_model_execution_allowed": False,
        "held_out_accessed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

