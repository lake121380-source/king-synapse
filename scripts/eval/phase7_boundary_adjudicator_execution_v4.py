#!/usr/bin/env python3
"""Freeze and execute Phase 7.3.3-D1-A Boundary Adjudication v4.

V4 changes only output representation to operation-based span reconstruction.
Case-isolated Provider execution remains write-once and first-content authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from phase7_execution_attempt_log import append_event, read_entries, verify_entries

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
PROMPT = CONFIG / "phase7_3_3_d_boundary_adjudicator_prompt_v4.md"
ADJUDICATION_PROTOCOL = CONFIG / "phase7_3_3_d_boundary_adjudication_protocol_v4.json"
V3_ADJUDICATION_PROTOCOL = CONFIG / "phase7_3_3_d_boundary_adjudication_protocol_v3.json"
AGREEMENT_PROTOCOL = CONFIG / "phase7_3_3_d_boundary_agreement_protocol_v3.json"
FAILURE_TAXONOMY = CONFIG / "phase7_3_3_d_failure_taxonomy_v2.json"
LEVEL2_FAILURE_SUBTYPES = CONFIG / "phase7_3_3_d_level2_failure_subtypes_v1.json"
RESEARCH_ROUTES = CONFIG / "phase7_3_3_d_research_routes_v2.json"
REFERENCE_PROTOCOL = DATA / "phase7_3_3_d_boundary_reference_protocol_v3.json"
BOUNDARY_PACKET = DATA / "phase7_3_3_d_boundary_blind_review_packet_v1.json"
WORKLIST = REPORTS / "phase7_3_3_d_boundary_adjudication_worklist_a_e_v3.json"
AGREEMENT_REPORT = REPORTS / "phase7_3_3_d_boundary_agreement_a_e_v3.json"
REVIEWER_A = REPORTS / "phase7_3_3_d_boundary_reviewer_a_submission_v3.json"
REVIEWER_E = REPORTS / "phase7_3_3_d_boundary_reviewer_e_submission_v3.json"
V3_MANIFEST = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_manifest_v3.json"
V3_ATTEMPT_LOG = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_attempts_v3.jsonl"
V3_NEGATIVE_RESULT = REPORTS / "phase7_3_3_d_boundary_adjudicator_negative_result_v3.json"
V3_OUTCOME = REPORTS / "phase7_3_3_d1_boundary_adjudicator_execution_outcome_v3.json"
V3_SUBTYPE_ANALYSIS = REPORTS / "phase7_3_3_d_boundary_adjudicator_v3_failure_subtype_analysis_v1.json"
V3_REFERENCE_READINESS = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v4.json"
FIXTURE_REPORT = REPORTS / "phase7_3_3_d_boundary_adjudicator_contract_fixtures_v4.json"
MANIFEST = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_manifest_v4.json"
ATTEMPT_LOG = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_attempts_v4.jsonl"
CHECKPOINT_DIR = REPORTS / "phase7_3_3_d_boundary_adjudicator_cases_v4"
SUBMISSION = REPORTS / "phase7_3_3_d_boundary_adjudicator_submission_v4.json"
DECISION_LOG = REPORTS / "phase7_3_3_d_segmentation_decision_log_v4.json"
RESULT = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_result_v4.json"
NEGATIVE_RESULT = REPORTS / "phase7_3_3_d_boundary_adjudicator_negative_result_v4.json"
READINESS_V5 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v5.json"
EXECUTION_READINESS = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_readiness_v4.json"

BASE_URL = "https://api.gpt.ge/v1"
CREDENTIAL_ENV = "PHASE7_ATOMIC_JUDGE_API_KEY"
MODEL_REQUESTED = "gpt-5.4"
TEMPERATURE, TOP_P, MAX_TOKENS, TIMEOUT_SECONDS = 0, 1, 16000, 600
RESPONSE_FORMAT = {"type": "json_object"}
CLAIM_KEYS = {
    "anchor_id", "boundary_operation", "claim_type", "material",
    "claim_origin", "boundary_decision_rationale", "type_decision_rationale",
    "reason_codes",
}
OPERATION_KEYS = {
    "reuse_span": {"kind", "reviewer_claim_ids"},
    "merge_spans": {"kind", "reviewer_claim_ids"},
    "slice_span": {"kind", "reviewer_claim_ids", "relative_start", "relative_end"},
    "new_span": {"kind", "start", "end", "informed_by_reviewer_claim_ids"},
}
FORBIDDEN_MODEL_FIELDS = {"source_excerpt", "occurrence_index", "source_span", "claim_text", "source_reviewer_claim_ids"}
CLAIM_TYPES = {"proposition", "scope", "prediction", "causal", "counterexample", "limitation", "falsifiability"}
ORIGINS = {"explicit", "inferred", "synthesized"}
REASON_CODES = {
    "coordination", "nested_proposition", "scope_modifier", "temporal_qualifier",
    "prediction_clause", "evidence_attribution", "causal_relation",
    "counterexample_clause", "limitation_clause", "falsifiability_clause",
    "quantifier_or_threshold", "condition_or_exception", "independent_truth_value",
    "non_assertive_connector", "other_explained",
}
CLAIM_ROLE_BY_SOURCE_FIELD = {
    "proposition": "anchor", "prediction_statement": "prediction",
    "prediction_observable": "prediction_observable",
    "prediction_success_criterion": "prediction_criterion",
    "falsification_statement": "falsification",
    "falsification_observable": "falsification_observable",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha_bytes(raw)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_once(path: Path, value: Any) -> str:
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{path.relative_to(ROOT)}")
        return sha_bytes(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    temporary.replace(path)
    return sha_bytes(encoded)


def split_prompt() -> tuple[str, str]:
    text = PROMPT.read_text(encoding="utf-8-sig")
    sm, um = "## System message\n", "## User message template\n"
    if sm not in text or um not in text:
        raise ValueError("prompt_sections_missing")
    system = text.split(sm, 1)[1].split(um, 1)[0].strip()
    user = text.split(um, 1)[1].strip()
    if "{{CASE_JSON}}" not in user:
        raise ValueError("case_json_placeholder_missing")
    return system, user


def validate_frozen_inputs() -> dict[str, Any]:
    required = [
        PROMPT, ADJUDICATION_PROTOCOL, V3_ADJUDICATION_PROTOCOL, AGREEMENT_PROTOCOL,
        FAILURE_TAXONOMY, LEVEL2_FAILURE_SUBTYPES, RESEARCH_ROUTES,
        REFERENCE_PROTOCOL, BOUNDARY_PACKET, WORKLIST, AGREEMENT_REPORT,
        REVIEWER_A, REVIEWER_E, V3_MANIFEST, V3_ATTEMPT_LOG, V3_NEGATIVE_RESULT,
        V3_OUTCOME, V3_SUBTYPE_ANALYSIS, V3_REFERENCE_READINESS,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise ValueError("missing_frozen_inputs:" + ",".join(missing))

    protocol = load(ADJUDICATION_PROTOCOL)
    worklist = load(WORKLIST)
    agreement = load(AGREEMENT_REPORT)
    routes = load(RESEARCH_ROUTES)
    if protocol.get("status") != "frozen_before_v4_contract_fixtures_and_execution":
        raise ValueError("adjudication_protocol_v4_not_frozen")
    if protocol.get("research_route") != "route_b_operation_based_span_representation":
        raise ValueError("adjudication_protocol_v4_route_mismatch")
    if routes.get("status") != "route_b_design_frozen_execution_not_started":
        raise ValueError("research_routes_v2_not_frozen_before_execution")
    if routes.get("route_b", {}).get("protocol") != "V4":
        raise ValueError("research_route_b_protocol_mismatch")
    if worklist.get("status") != "frozen_ready_for_adjudication" or worklist.get("case_count") != 10:
        raise ValueError("adjudication_worklist_not_ready")
    for key in ("support_labels_included", "candidate_gold_or_silver_included", "evidence_bundle_included", "held_out_accessed"):
        if worklist.get(key) is not False:
            raise ValueError(f"adjudication_worklist_visibility_flag:{key}")
    if agreement.get("status") != "completed_frozen_before_adjudication":
        raise ValueError("agreement_report_not_completed")

    expected_hashes = {
        V3_ADJUDICATION_PROTOCOL: "be11ba0a3414a12e31d7baa7516ed02a61942e3dc16c156c9158c0da96f519bf",
        AGREEMENT_PROTOCOL: "8af77821fc4ab50f71dd63ea1f7ac2de6768b15e01e4627992095a5d55ac4597",
        REFERENCE_PROTOCOL: "859438f8610eb5c1018b7f35181785fb83d4fa8483156d93eb128268349e5964",
        BOUNDARY_PACKET: "38fba5a20c560704c7aedfd441c39c428dcdb4774cc0395d51d84b33c507197a",
        WORKLIST: "56132cc9977ec579c4a668f30dcdaa3818c94a528f7feb16dfd5920cda67afaf",
        AGREEMENT_REPORT: "0ddb0b873431ddf89b7301f44691b7897a2a36d757f8eace10877a35ed22e6c7",
        REVIEWER_A: "8bc7633afc0eb9a76a11c9152ad7960e28469062d91583a163620de2d141bb0d",
        REVIEWER_E: "368972c417fd79818f19beacc4745fbb6e363237e8e0ac7f67f2230222357663",
        FAILURE_TAXONOMY: "5def03716fc695e4165682cfa6dbb1c9c5400764ecad7e181812b72261e1f24a",
        LEVEL2_FAILURE_SUBTYPES: "80b198944c4f00d3f209689d65d1c4d2db53fb95667bfdf144a4f915ac6082d5",
        V3_MANIFEST: "7f4656e140f66f461612d638a27a18d8eb3d3dbf545a62cd5f7da53369aa788f",
        V3_ATTEMPT_LOG: "a17a8b267481403c240aa8473d9663f5d541ef0187a9307c00319b4ac88b62e0",
        V3_NEGATIVE_RESULT: "d35f9753c0cde6c660534b9b82db720096352e990266066dd29cfa7bb9aa2bb6",
        V3_OUTCOME: "db1d40d02890659c097e9036acabc2113e65d53eed8988a6d2a089f5dea5245f",
        V3_SUBTYPE_ANALYSIS: "16037e3bde2dd5a2b620874425d81b59927ba56faf913868f4142bd5484ea1c3",
        V3_REFERENCE_READINESS: "eee548b6d5d0b2ca8c36f9a90c9089b10e4a1c393313df665485651b4b3172ef",
    }
    for path, expected in expected_hashes.items():
        if sha(path) != expected:
            raise ValueError(f"frozen_input_hash_mismatch:{path.relative_to(ROOT)}")

    expected_lineage = {
        "boundary_packet_sha256": sha(BOUNDARY_PACKET),
        "boundary_reference_protocol_v3_sha256": sha(REFERENCE_PROTOCOL),
        "reviewer_a_submission_sha256": sha(REVIEWER_A),
        "reviewer_e_submission_sha256": sha(REVIEWER_E),
        "agreement_protocol_sha256": sha(AGREEMENT_PROTOCOL),
        "agreement_report_sha256": sha(AGREEMENT_REPORT),
    }
    for lineage_name, lineage in (("worklist", worklist.get("artifact_lineage", {})),):
        for key, digest in expected_lineage.items():
            if lineage.get(key) != digest:
                raise ValueError(f"{lineage_name}_lineage_mismatch:{key}")
    return {"protocol": protocol, "worklist": worklist, "agreement": agreement, "routes": routes}


def execution_manifest() -> dict[str, Any]:
    if load(FIXTURE_REPORT).get("all_fixtures_passed") is not True:
        raise ValueError("contract_fixtures_not_passed")
    return {
        "schema_version": 4,
        "manifest_id": "phase7.3.3-d1-a-boundary-adjudicator-execution-v4",
        "status": "frozen_not_started",
        "research_route": "route_b_operation_based_span_representation",
        "object_of_study": "boundary_adjudication_under_operation_based_span_representation",
        "controlled_hypothesis": load(ADJUDICATION_PROTOCOL)["controlled_hypothesis"],
        "treatment_declaration": {
            "changed_variable": "output_representation_only",
            "from": "model_generated_exact_excerpt_and_occurrence_index",
            "to": "operation_based_span_selection_with_deterministic_adapter_reconstruction",
            "semantic_rules_changed": False,
            "model_configuration_changed": False,
            "worklist_or_agreement_changed": False,
            "limit": "Success supports representation sensitivity; it does not prove V3 semantic decisions were correct.",
        },
        "gold_status": "model_adjudicated_boundary_reference_candidate_not_human_gold",
        "decision_environment": {
            "provider": "api.gpt.ge", "provider_base_url": BASE_URL,
            "model_requested": MODEL_REQUESTED, "canonical_model_family_expected": MODEL_REQUESTED,
            "temperature": TEMPERATURE, "top_p": TOP_P,
            "seed": None, "seed_supported_by_adapter": False,
            "max_tokens": MAX_TOKENS, "stop_sequences": [],
            "response_format": RESPONSE_FORMAT, "request_timeout_seconds": TIMEOUT_SECONDS,
            "credential_env_name": CREDENTIAL_ENV, "case_isolation": True,
        },
        "artifact_lineage": {
            "adapter_sha256": sha(Path(__file__)), "prompt_sha256": sha(PROMPT),
            "adjudication_protocol_v4_sha256": sha(ADJUDICATION_PROTOCOL),
            "adjudication_protocol_v3_sha256": sha(V3_ADJUDICATION_PROTOCOL),
            "agreement_protocol_sha256": sha(AGREEMENT_PROTOCOL),
            "agreement_report_sha256": sha(AGREEMENT_REPORT), "worklist_sha256": sha(WORKLIST),
            "reviewer_a_submission_sha256": sha(REVIEWER_A), "reviewer_e_submission_sha256": sha(REVIEWER_E),
            "boundary_packet_sha256": sha(BOUNDARY_PACKET),
            "boundary_reference_protocol_v3_sha256": sha(REFERENCE_PROTOCOL),
            "contract_fixtures_v4_sha256": sha(FIXTURE_REPORT),
            "failure_taxonomy_v2_sha256": sha(FAILURE_TAXONOMY),
            "level2_failure_subtypes_v1_sha256": sha(LEVEL2_FAILURE_SUBTYPES),
            "research_routes_v2_sha256": sha(RESEARCH_ROUTES),
            "v3_execution_manifest_sha256": sha(V3_MANIFEST),
            "v3_attempt_log_sha256": sha(V3_ATTEMPT_LOG),
            "v3_negative_result_sha256": sha(V3_NEGATIVE_RESULT),
            "v3_execution_outcome_sha256": sha(V3_OUTCOME),
            "v3_failure_subtype_analysis_sha256": sha(V3_SUBTYPE_ANALYSIS),
            "v3_reference_readiness_sha256": sha(V3_REFERENCE_READINESS),
        },
        "parser_contract": {
            "parser_version": "phase7_boundary_adjudicator_execution_v4.normalize_case.v1",
            "strict_root_schema": True, "strict_claim_fields": True,
            "strict_operation_specific_fields": True,
            "model_generated_excerpt_forbidden": True,
            "adapter_derived_exact_claim_text": True,
            "unicode_code_point_offsets": True, "end_offset_exclusive": True,
            "offset_clamping": False, "unknown_or_cross_anchor_ids_rejected": True,
            "reuse_requires_identical_spans": True,
            "merge_requires_two_distinct_spans": True,
            "slice_requires_nonempty_proper_subspan": True,
            "new_span_requires_valid_absolute_range": True,
            "all_anchors_required": True, "unknown_anchors_rejected": True,
            "overlapping_spans_rejected": True, "reason_code_enum_frozen": True,
            "boundary_and_type_rationales_separate": True,
            "protocol_owned_claim_role_and_anchor_group": True,
        },
        "prospective_failure_subtype_mapping": {
            "unknown_or_cross_anchor_reviewer_ids": "provenance_failure",
            "invalid_or_impossible_operation_reconstruction": "serialization_failure",
            "overlap_or_missing_anchor": "semantic_decision_failure",
            "verifier_or_internal_integrity_failure": "verification_failure",
            "insufficient_evidence": "classification_status_insufficient_evidence",
            "root_json_schema_or_unknown_operation_shape": "level_1_provider_representation_contract",
        },
        "execution_governance": {
            "first_returned_provider_content_per_case_authoritative": True,
            "provider_content_sha256_before_parse": True, "provider_envelope_sha256_recorded": True,
            "raw_provider_content_stored": False, "automatic_representation_repair": False,
            "automatic_semantic_repair": False, "semantic_retry_after_content": False,
            "selective_retry_after_content": False,
            "transport_failure_before_content_may_resume_same_manifest": True,
            "append_only_hash_chained_attempt_log": True, "write_once_case_checkpoints": True,
            "write_once_final_artifacts": True, "deterministic_segmentation_decision_log": True,
        },
        "visibility": {
            "source_anchor_text": True, "reviewer_a_boundary_submission": True,
            "reviewer_e_boundary_submission": True, "agreement_component_diagnostics": True,
            "evidence_bundle": False, "support_labels": False,
            "candidate_gold_or_silver": False, "historical_judge": False,
            "external_knowledge": False, "held_out": False,
        },
        "case_count": 10,
        "provider_called": False,
        "v4_execution_started": False,
        "coverage_qa_allowed": False,
        "boundary_gold_frozen": False,
        "support_review_allowed": False,
        "held_out_accessed": False,
    }


def execution_readiness(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 4,
        "readiness_id": "phase7.3.3-d1-a-boundary-adjudicator-execution-readiness-v4",
        "status": "v4_frozen_ready_not_started",
        "manifest_sha256": manifest_hash,
        "contract_fixtures_v4_sha256": sha(FIXTURE_REPORT),
        "adjudication_protocol_v4_sha256": sha(ADJUDICATION_PROTOCOL),
        "research_routes_v2_sha256": sha(RESEARCH_ROUTES),
        "provider_called": False,
        "v4_execution_started": False,
        "gates": {
            "agreement_frozen": True,
            "adjudication_allowed": True,
            "adjudication_completed": False,
            "coverage_qa_allowed": False,
            "boundary_gold_frozen": False,
            "support_review_allowed": False,
            "held_out_accessed": False,
        },
    }


def prepare() -> None:
    validate_frozen_inputs()
    split_prompt()
    if not FIXTURE_REPORT.exists() or load(FIXTURE_REPORT).get("all_fixtures_passed") is not True:
        raise ValueError("run_contract_fixtures_before_prepare")
    digest = write_once(MANIFEST, execution_manifest())
    if sha(MANIFEST) != digest:
        raise AssertionError("manifest_write_hash_mismatch")
    readiness_hash = write_once(EXECUTION_READINESS, execution_readiness(digest))
    print(json.dumps({
        "status": "v4_frozen_ready_not_started",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": digest,
        "execution_readiness_sha256": readiness_hash,
        "model_requested": MODEL_REQUESTED,
        "provider_called": False,
        "v4_execution_started": False,
        "coverage_qa_allowed": False,
        "boundary_gold_frozen": False,
        "support_review_allowed": False,
        "held_out_accessed": False,
    }, indent=2))


def exact_occurrences(source: str, excerpt: str) -> list[int]:
    starts, cursor = [], 0
    while True:
        found = source.find(excerpt, cursor)
        if found < 0:
            return starts
        starts.append(found); cursor = found + 1


def _strict_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _reviewer_ids(value: Any, anchor_id: str, response_index: int, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{field_name}_invalid:{anchor_id}:{response_index}")
    if len(value) != len(set(value)):
        raise ValueError(f"{field_name}_duplicate:{anchor_id}:{response_index}")
    return value


def _resolve_operation(
    anchor: dict[str, Any], operation: Any, response_index: int,
) -> tuple[int, int, list[str], str]:
    anchor_id = anchor["anchor_id"]
    if not isinstance(operation, dict):
        raise ValueError(f"boundary_operation_invalid:{anchor_id}:{response_index}")
    kind = operation.get("kind")
    if kind not in OPERATION_KEYS or set(operation) != OPERATION_KEYS[kind]:
        raise ValueError(f"boundary_operation_shape_invalid:{anchor_id}:{response_index}:{kind}")

    reviewer_claims = anchor["reviewer_a_claims"] + anchor["reviewer_e_claims"]
    reviewer_by_id = {claim["reviewer_claim_id"]: claim for claim in reviewer_claims}
    if len(reviewer_by_id) != len(reviewer_claims):
        raise ValueError(f"reviewer_claim_id_not_unique:{anchor_id}")

    id_field = "informed_by_reviewer_claim_ids" if kind == "new_span" else "reviewer_claim_ids"
    reviewer_ids = _reviewer_ids(operation[id_field], anchor_id, response_index, id_field)
    unknown = sorted(set(reviewer_ids) - set(reviewer_by_id))
    if unknown:
        raise ValueError(
            f"reviewer_claim_ids_unknown_or_cross_anchor:{anchor_id}:{response_index}:{','.join(unknown)}"
        )
    selected = [reviewer_by_id[claim_id] for claim_id in reviewer_ids]
    spans = [(claim["source_span"]["start"], claim["source_span"]["end"]) for claim in selected]
    source = anchor["source_text"]

    if kind == "reuse_span":
        if len(set(spans)) != 1:
            raise ValueError(f"reuse_span_requires_identical_spans:{anchor_id}:{response_index}")
        start, end = spans[0]
    elif kind == "merge_spans":
        if len(reviewer_ids) < 2 or len(set(spans)) < 2:
            raise ValueError(f"merge_spans_requires_two_distinct_spans:{anchor_id}:{response_index}")
        start = min(span[0] for span in spans)
        end = max(span[1] for span in spans)
        if (start, end) in set(spans):
            raise ValueError(f"merge_spans_non_expansive_envelope:{anchor_id}:{response_index}")
    elif kind == "slice_span":
        if len(set(spans)) != 1:
            raise ValueError(f"slice_span_requires_identical_base_spans:{anchor_id}:{response_index}")
        relative_start, relative_end = operation["relative_start"], operation["relative_end"]
        if not _strict_int(relative_start) or not _strict_int(relative_end):
            raise ValueError(f"slice_span_offsets_invalid:{anchor_id}:{response_index}")
        base_start, base_end = spans[0]
        base_length = base_end - base_start
        if not (0 <= relative_start < relative_end <= base_length):
            raise ValueError(f"slice_span_offsets_out_of_range:{anchor_id}:{response_index}")
        if relative_start == 0 and relative_end == base_length:
            raise ValueError(f"slice_span_must_be_proper_subspan:{anchor_id}:{response_index}")
        start, end = base_start + relative_start, base_start + relative_end
    else:
        start, end = operation["start"], operation["end"]
        if not _strict_int(start) or not _strict_int(end):
            raise ValueError(f"new_span_offsets_invalid:{anchor_id}:{response_index}")
        if not (0 <= start < end <= len(source)):
            raise ValueError(f"new_span_offsets_out_of_range:{anchor_id}:{response_index}")

    if not _strict_int(start) or not _strict_int(end) or not (0 <= start < end <= len(source)):
        raise ValueError(f"operation_reconstructed_span_invalid:{anchor_id}:{response_index}")
    return start, end, reviewer_ids, kind


def normalize_case(case: dict[str, Any], response_obj: Any) -> list[dict[str, Any]]:
    if not isinstance(response_obj, dict) or set(response_obj) != {"claims"} or not isinstance(response_obj["claims"], list):
        raise ValueError("response_schema_invalid")
    if not response_obj["claims"]:
        raise ValueError("claims_empty")

    anchors = {anchor["anchor_id"]: anchor for anchor in case["source_anchors"]}
    if len(anchors) != len(case["source_anchors"]):
        raise ValueError("source_anchor_id_not_unique")
    anchor_order = {anchor["anchor_id"]: index for index, anchor in enumerate(case["source_anchors"])}
    for anchor in anchors.values():
        if sha_bytes(anchor["source_text"].encode("utf-8")) != anchor["source_text_sha256"]:
            raise ValueError(f"source_text_sha256_mismatch:{anchor['anchor_id']}")
        if not (anchor["reviewer_a_claims"] and anchor["reviewer_e_claims"]):
            raise ValueError(f"anchor_without_both_reviewer_claim_sets:{anchor['anchor_id']}")
        for reviewer_claim in anchor["reviewer_a_claims"] + anchor["reviewer_e_claims"]:
            span = reviewer_claim.get("source_span", {})
            start, end = span.get("start"), span.get("end")
            if not _strict_int(start) or not _strict_int(end) or not (0 <= start < end <= len(anchor["source_text"])):
                raise ValueError(f"reviewer_claim_span_invalid:{anchor['anchor_id']}:{reviewer_claim.get('reviewer_claim_id')}")
            if anchor["source_text"][start:end] != reviewer_claim.get("claim_text"):
                raise ValueError(f"reviewer_claim_text_integrity_failure:{anchor['anchor_id']}:{reviewer_claim.get('reviewer_claim_id')}")

    seen_anchors: set[str] = set()
    spans_by_anchor: dict[str, list[tuple[int, int]]] = {anchor_id: [] for anchor_id in anchors}
    preliminary: list[dict[str, Any]] = []
    for response_index, claim in enumerate(response_obj["claims"], start=1):
        if not isinstance(claim, dict) or set(claim) != CLAIM_KEYS:
            raise ValueError(f"claim_fields_invalid:{response_index}")
        if set(claim) & FORBIDDEN_MODEL_FIELDS:
            raise ValueError(f"model_owned_span_field_forbidden:{response_index}")
        anchor_id = claim["anchor_id"]
        if anchor_id not in anchors:
            raise ValueError(f"unknown_anchor:{anchor_id}")
        anchor = anchors[anchor_id]
        source_field = anchor["source_field"]
        if source_field not in CLAIM_ROLE_BY_SOURCE_FIELD:
            raise ValueError(f"source_field_role_unmapped:{source_field}")

        start, end, provenance, operation_kind = _resolve_operation(anchor, claim["boundary_operation"], response_index)
        if any(max(start, existing_start) < min(end, existing_end) for existing_start, existing_end in spans_by_anchor[anchor_id]):
            raise ValueError(f"overlapping_claim_spans:{anchor_id}:{response_index}")
        spans_by_anchor[anchor_id].append((start, end))

        claim_text = anchor["source_text"][start:end]
        if not claim_text.strip():
            raise ValueError(f"operation_reconstructed_blank_claim:{anchor_id}:{response_index}")
        starts = exact_occurrences(anchor["source_text"], claim_text)
        if start not in starts:
            raise ValueError(f"derived_occurrence_verification_failure:{anchor_id}:{response_index}")
        occurrence = starts.index(start)

        if claim["claim_type"] not in CLAIM_TYPES:
            raise ValueError(f"claim_type_invalid:{anchor_id}:{response_index}")
        if not isinstance(claim["material"], bool) or claim["claim_origin"] not in ORIGINS:
            raise ValueError(f"structural_metadata_invalid:{anchor_id}:{response_index}")
        for key in ("boundary_decision_rationale", "type_decision_rationale"):
            if not isinstance(claim[key], str) or not claim[key].strip():
                raise ValueError(f"{key}_required:{anchor_id}:{response_index}")
        reasons = claim["reason_codes"]
        if not isinstance(reasons, list) or not reasons or any(not isinstance(code, str) or code not in REASON_CODES for code in reasons):
            raise ValueError(f"reason_codes_invalid:{anchor_id}:{response_index}")
        if len(reasons) != len(set(reasons)):
            raise ValueError(f"reason_codes_duplicate:{anchor_id}:{response_index}")

        seen_anchors.add(anchor_id)
        preliminary.append({
            "case_id": case["case_id"], "response_sha256": case["response_sha256"],
            "anchor_id": anchor_id, "source_field": source_field, "source_index": anchor["source_index"],
            "source_text_sha256": anchor["source_text_sha256"],
            "source_span": {"start": start, "end": end},
            "source_occurrence_index": occurrence, "claim_text": claim_text,
            "claim_type": claim["claim_type"],
            "claim_role": CLAIM_ROLE_BY_SOURCE_FIELD[source_field],
            "anchor_group": f"{case['case_id']}::{source_field}", "material": claim["material"],
            "claim_origin": claim["claim_origin"],
            "boundary_decision_rationale": claim["boundary_decision_rationale"].strip(),
            "type_decision_rationale": claim["type_decision_rationale"].strip(),
            "reason_codes": reasons, "source_reviewer_claim_ids": provenance,
            "boundary_operation_kind": operation_kind,
        })

    missing = sorted(set(anchors) - seen_anchors)
    if missing:
        raise ValueError("anchors_without_final_claims:" + ",".join(missing))
    preliminary.sort(key=lambda row: (
        anchor_order[row["anchor_id"]], row["source_span"]["start"],
        row["source_span"]["end"], row["claim_text"],
    ))
    return [
        {"adjudicated_claim_id": f"adjudicated-{case['case_id']}-claim-{index:03d}", **row}
        for index, row in enumerate(preliminary, start=1)
    ]


def span_set(claims: list[dict[str, Any]]) -> set[tuple[int, int]]:
    return {(c["source_span"]["start"], c["source_span"]["end"]) for c in claims}


def segmentation_category(a: set[tuple[int, int]], e: set[tuple[int, int]], final: set[tuple[int, int]]) -> str:
    if final == a == e: return "consensus_exact"
    if final == a: return "keep_a_segmentation"
    if final == e: return "keep_e_segmentation"
    if len(final) < len(a) and len(final) < len(e): return "merge_both"
    if len(final) > len(a) and len(final) > len(e): return "split_both"
    return "new_segmentation"


def generate_decision_log(worklist: dict[str, Any], claims: list[dict[str, Any]], manifest_hash: str, submission_hash: str) -> dict[str, Any]:
    final_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        final_by_anchor.setdefault(claim["anchor_id"], []).append(claim)
    entries, category_counts, reason_counts, per_case = [], Counter(), Counter(), {}
    for case in worklist["cases"]:
        case_counter: Counter[str] = Counter()
        for anchor in case["source_anchors"]:
            aid, finals = anchor["anchor_id"], final_by_anchor.get(anchor["anchor_id"], [])
            if not finals:
                raise ValueError(f"decision_log_anchor_without_final_claims:{aid}")
            a, e, final = span_set(anchor["reviewer_a_claims"]), span_set(anchor["reviewer_e_claims"]), span_set(finals)
            category = segmentation_category(a, e, final)
            category_counts[category] += 1; case_counter[category] += 1
            entry_reasons = sorted({code for claim in finals for code in claim["reason_codes"]})
            reason_counts.update(code for claim in finals for code in claim["reason_codes"])
            entries.append({
                "case_id": case["case_id"], "anchor_id": aid, "source_field": anchor["source_field"],
                "reviewer_a_claim_count": len(a), "reviewer_e_claim_count": len(e), "final_claim_count": len(final),
                "reviewer_a_span_set": [{"start": s, "end": x} for s, x in sorted(a)],
                "reviewer_e_span_set": [{"start": s, "end": x} for s, x in sorted(e)],
                "final_span_set": [{"start": s, "end": x} for s, x in sorted(final)],
                "decision_category": category, "reason_codes": entry_reasons,
                "final_claim_ids": [c["adjudicated_claim_id"] for c in finals],
            })
        per_case[case["case_id"]] = case_counter
    representatives = {cat: [{"case_id": x["case_id"], "anchor_id": x["anchor_id"]}
                             for x in entries if x["decision_category"] == cat][:3]
                       for cat in sorted(category_counts)}
    return {
        "schema_version": 4, "log_id": "phase7.3.3-d1-a-segmentation-decision-log-v4",
        "status": "deterministically_generated_from_frozen_adjudication",
        "manifest_sha256": manifest_hash, "submission_sha256": submission_hash,
        "adjudication_protocol_sha256": sha(ADJUDICATION_PROTOCOL),
        "agreement_report_sha256": sha(AGREEMENT_REPORT), "worklist_sha256": sha(WORKLIST),
        "classification_unit": "source_anchor", "decision_count_by_category": dict(sorted(category_counts.items())),
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "per_case_counts": {k: dict(sorted(v.items())) for k, v in sorted(per_case.items())},
        "representative_decisions": representatives, "entries": entries, "entry_count": len(entries),
        "provider_called_for_log_generation": False, "held_out_accessed": False,
    }


def fixture_case(specs: list[tuple[str, str, list[tuple[int, int]], list[tuple[int, int]]]]) -> dict[str, Any]:
    anchors = []
    for index, (anchor_id, source_text, a_spans, e_spans) in enumerate(specs):
        def make(prefix: str, spans: list[tuple[int, int]]) -> list[dict[str, Any]]:
            return [
                {
                    "reviewer_claim_id": f"reviewer-{prefix}-fixture-{index}-{claim_index}",
                    "source_span": {"start": start, "end": end},
                    "claim_text": source_text[start:end],
                    "claim_type": "proposition", "material": True,
                    "claim_origin": "explicit",
                }
                for claim_index, (start, end) in enumerate(spans)
            ]
        anchors.append({
            "anchor_id": anchor_id, "source_field": "proposition", "source_index": index,
            "source_text": source_text, "source_text_sha256": sha_bytes(source_text.encode("utf-8")),
            "reviewer_a_claims": make("a", a_spans), "reviewer_e_claims": make("e", e_spans),
            "component_diagnostics": [],
        })
    return {"case_id": "fixture_case", "response_sha256": "0" * 64, "source_anchors": anchors}


def fixture_claim(anchor: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "anchor_id": anchor["anchor_id"], "boundary_operation": operation,
        "claim_type": "proposition", "material": True, "claim_origin": "explicit",
        "boundary_decision_rationale": "One independently truth-evaluable assertion.",
        "type_decision_rationale": "The selected span states a proposition.",
        "reason_codes": ["independent_truth_value"],
    }


def reviewer_id(anchor: dict[str, Any], reviewer: str, index: int = 0) -> str:
    return anchor[f"reviewer_{reviewer}_claims"][index]["reviewer_claim_id"]


def expect_reject(case: dict[str, Any], response: dict[str, Any], prefix: str) -> str:
    try:
        normalize_case(case, response)
    except ValueError as error:
        if not str(error).startswith(prefix):
            raise AssertionError(f"unexpected_fixture_error:{prefix}:{error}") from error
        return str(error)
    raise AssertionError(f"fixture_was_not_rejected:{prefix}")


def run_contract_fixtures() -> dict[str, Any]:
    validate_frozen_inputs()
    split_prompt()
    fixtures: list[dict[str, Any]] = []

    reuse = fixture_case([("fixture-reuse", "Alpha holds.", [(0, 12)], [(0, 12)])])
    reuse_anchor = reuse["source_anchors"][0]
    normalized = normalize_case(reuse, {"claims": [fixture_claim(reuse_anchor, {
        "kind": "reuse_span", "reviewer_claim_ids": [reviewer_id(reuse_anchor, "a"), reviewer_id(reuse_anchor, "e")],
    })]})
    assert normalized[0]["claim_text"] == "Alpha holds." and normalized[0]["source_span"] == {"start": 0, "end": 12}
    fixtures.append({"fixture_id": "reuse_span_derives_exact_text", "expected": "pass", "actual": "pass"})

    merge = fixture_case([("fixture-merge", "Alpha and Beta hold.", [(0, 5), (10, 14)], [(0, 5), (10, 14)])])
    merge_anchor = merge["source_anchors"][0]
    normalized = normalize_case(merge, {"claims": [fixture_claim(merge_anchor, {
        "kind": "merge_spans", "reviewer_claim_ids": [reviewer_id(merge_anchor, "a", 0), reviewer_id(merge_anchor, "a", 1)],
    })]})
    assert normalized[0]["claim_text"] == "Alpha and Beta" and normalized[0]["source_span"] == {"start": 0, "end": 14}
    fixtures.append({"fixture_id": "merge_spans_derives_envelope", "expected": "pass", "actual": "pass"})

    sliced = fixture_case([("fixture-slice", "Alpha holds.", [(0, 12)], [(0, 12)])])
    sliced_anchor = sliced["source_anchors"][0]
    normalized = normalize_case(sliced, {"claims": [fixture_claim(sliced_anchor, {
        "kind": "slice_span", "reviewer_claim_ids": [reviewer_id(sliced_anchor, "a"), reviewer_id(sliced_anchor, "e")],
        "relative_start": 0, "relative_end": 5,
    })]})
    assert normalized[0]["claim_text"] == "Alpha" and normalized[0]["source_span"] == {"start": 0, "end": 5}
    fixtures.append({"fixture_id": "slice_span_derives_proper_subspan", "expected": "pass", "actual": "pass"})

    new = fixture_case([("fixture-new", "Alpha Beta.", [(0, 5)], [(6, 10)])])
    new_anchor = new["source_anchors"][0]
    normalized = normalize_case(new, {"claims": [fixture_claim(new_anchor, {
        "kind": "new_span", "start": 6, "end": 10,
        "informed_by_reviewer_claim_ids": [reviewer_id(new_anchor, "a"), reviewer_id(new_anchor, "e")],
    })]})
    assert normalized[0]["claim_text"] == "Beta" and normalized[0]["source_span"] == {"start": 6, "end": 10}
    fixtures.append({"fixture_id": "new_span_derives_exact_source_slice", "expected": "pass", "actual": "pass"})

    forbidden = fixture_claim(reuse_anchor, {"kind": "reuse_span", "reviewer_claim_ids": [reviewer_id(reuse_anchor, "a")]})
    forbidden["source_excerpt"] = "Alpha holds."
    fixtures.append({"fixture_id": "model_provided_source_excerpt_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(reuse, {"claims": [forbidden]}, "claim_fields_invalid")})

    unknown = fixture_claim(reuse_anchor, {"kind": "reuse_span", "reviewer_claim_ids": ["invented-reviewer-id"]})
    fixtures.append({"fixture_id": "unknown_reviewer_id_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(reuse, {"claims": [unknown]}, "reviewer_claim_ids_unknown_or_cross_anchor")})

    cross = fixture_case([("fixture-cross-a", "Alpha holds.", [(0, 12)], [(0, 12)]),
                          ("fixture-cross-b", "Beta holds.", [(0, 11)], [(0, 11)])])
    cross_a, cross_b = cross["source_anchors"]
    cross_claim = fixture_claim(cross_a, {"kind": "reuse_span", "reviewer_claim_ids": [reviewer_id(cross_b, "a")]})
    fixtures.append({"fixture_id": "cross_anchor_reviewer_id_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(cross, {"claims": [cross_claim]}, "reviewer_claim_ids_unknown_or_cross_anchor")})

    identical_merge = fixture_claim(reuse_anchor, {
        "kind": "merge_spans", "reviewer_claim_ids": [reviewer_id(reuse_anchor, "a"), reviewer_id(reuse_anchor, "e")],
    })
    fixtures.append({"fixture_id": "merge_identical_spans_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(reuse, {"claims": [identical_merge]}, "merge_spans_requires_two_distinct_spans")})

    bad_slice = fixture_claim(sliced_anchor, {
        "kind": "slice_span", "reviewer_claim_ids": [reviewer_id(sliced_anchor, "a")],
        "relative_start": 0, "relative_end": 13,
    })
    fixtures.append({"fixture_id": "slice_out_of_range_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(sliced, {"claims": [bad_slice]}, "slice_span_offsets_out_of_range")})

    full_slice = fixture_claim(sliced_anchor, {
        "kind": "slice_span", "reviewer_claim_ids": [reviewer_id(sliced_anchor, "a")],
        "relative_start": 0, "relative_end": 12,
    })
    fixtures.append({"fixture_id": "slice_full_span_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(sliced, {"claims": [full_slice]}, "slice_span_must_be_proper_subspan")})

    bad_new = fixture_claim(new_anchor, {
        "kind": "new_span", "start": 6, "end": 99,
        "informed_by_reviewer_claim_ids": [reviewer_id(new_anchor, "a")],
    })
    fixtures.append({"fixture_id": "new_span_out_of_range_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(new, {"claims": [bad_new]}, "new_span_offsets_out_of_range")})

    overlap = fixture_case([("fixture-overlap", "Alpha Beta Gamma", [(0, 10)], [(6, 16)])])
    overlap_anchor = overlap["source_anchors"][0]
    overlap_response = {"claims": [
        fixture_claim(overlap_anchor, {"kind": "reuse_span", "reviewer_claim_ids": [reviewer_id(overlap_anchor, "a")]}),
        fixture_claim(overlap_anchor, {"kind": "reuse_span", "reviewer_claim_ids": [reviewer_id(overlap_anchor, "e")]}),
    ]}
    fixtures.append({"fixture_id": "overlapping_final_spans_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(overlap, overlap_response, "overlapping_claim_spans")})

    missing = fixture_case([("fixture-missing-a", "Alpha holds.", [(0, 12)], [(0, 12)]),
                            ("fixture-missing-b", "Beta holds.", [(0, 11)], [(0, 11)])])
    missing_anchor = missing["source_anchors"][0]
    fixtures.append({"fixture_id": "missing_anchor_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(missing, {"claims": [fixture_claim(missing_anchor, {
                         "kind": "reuse_span", "reviewer_claim_ids": [reviewer_id(missing_anchor, "a")],
                     })]}, "anchors_without_final_claims")})

    examples = {
        "consensus_exact": ({(0, 1)}, {(0, 1)}, {(0, 1)}),
        "keep_a_segmentation": ({(0, 1)}, {(0, 2)}, {(0, 1)}),
        "keep_e_segmentation": ({(0, 1)}, {(0, 2)}, {(0, 2)}),
        "merge_both": ({(0, 1), (2, 3)}, {(0, 2), (2, 3)}, {(0, 3)}),
        "split_both": ({(0, 3)}, {(0, 2)}, {(0, 1), (1, 2)}),
        "new_segmentation": ({(0, 1)}, {(1, 2)}, {(2, 3)}),
    }
    actual = {expected: segmentation_category(*sets) for expected, sets in examples.items()}
    if any(expected != observed for expected, observed in actual.items()):
        raise AssertionError(f"segmentation_category_fixture_failed:{actual}")
    fixtures.append({"fixture_id": "all_six_deterministic_segmentation_categories", "expected": "pass", "actual": "pass", "categories": actual})

    report = {
        "schema_version": 4,
        "report_id": "phase7.3.3-d1-a-boundary-adjudicator-contract-fixtures-v4",
        "status": "completed_offline_before_manifest_and_execution",
        "adapter_sha256": sha(Path(__file__)), "prompt_sha256": sha(PROMPT),
        "adjudication_protocol_v4_sha256": sha(ADJUDICATION_PROTOCOL),
        "level2_failure_subtypes_v1_sha256": sha(LEVEL2_FAILURE_SUBTYPES),
        "worklist_sha256": sha(WORKLIST),
        "fixture_count": len(fixtures), "passed_fixture_count": len(fixtures),
        "all_fixtures_passed": True, "fixtures": fixtures,
        "provider_called": False, "v4_execution_started": False,
        "held_out_accessed": False,
    }
    write_once(FIXTURE_REPORT, report)
    return report


def request_provider(key: str, system: str, user: str) -> tuple[dict[str, Any], bytes]:
    payload = {"model": MODEL_REQUESTED, "temperature": TEMPERATURE, "top_p": TOP_P,
               "max_tokens": MAX_TOKENS, "response_format": RESPONSE_FORMAT,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    request = urllib.request.Request(BASE_URL + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")), raw


def extract_content(envelope: Any) -> tuple[str, str]:
    if not isinstance(envelope, dict): raise ValueError("provider_envelope_not_object")
    reported = envelope.get("model")
    if not isinstance(reported, str) or not reported: raise ValueError("provider_reported_model_missing")
    choices = envelope.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict): raise ValueError("provider_choices_invalid")
    message = choices[0].get("message")
    if not isinstance(message, dict): raise ValueError("provider_message_invalid")
    content = message.get("content")
    if not isinstance(content, str) or not content: raise ValueError("provider_content_missing_or_non_text")
    return reported, content


def canonical_model_family(reported: str) -> str:
    if reported == MODEL_REQUESTED or reported.startswith(MODEL_REQUESTED + "-"): return MODEL_REQUESTED
    raise ValueError(f"provider_reported_model_outside_requested_family:{MODEL_REQUESTED}:{reported}")


def checkpoint_path(case_id: str) -> Path:
    return CHECKPOINT_DIR / f"{case_id}.json"


def failure_classification(error: Exception, content_received: bool) -> dict[str, Any]:
    code = str(error)
    level1_prefixes = (
        "provider_", "response_schema_invalid", "claims_empty", "claim_fields_invalid",
        "boundary_operation_invalid", "boundary_operation_shape_invalid",
    )
    if not content_received or isinstance(error, json.JSONDecodeError) or code.startswith(level1_prefixes):
        return {
            "level": 1, "level_code": "provider_representation_contract",
            "classification_status": "not_applicable_below_level_2", "observed_subtype": None,
        }
    if code.startswith(("reviewer_claim_ids_unknown_or_cross_anchor", "unknown_anchor")):
        subtype = "provenance_failure"
    elif code.startswith((
        "reuse_span_requires_identical_spans", "merge_spans_requires_two_distinct_spans",
        "merge_spans_non_expansive_envelope", "slice_span_requires_identical_base_spans",
        "slice_span_offsets_invalid", "slice_span_offsets_out_of_range",
        "slice_span_must_be_proper_subspan", "new_span_offsets_invalid",
        "new_span_offsets_out_of_range", "operation_reconstructed_span_invalid",
        "operation_reconstructed_blank_claim",
    )):
        subtype = "serialization_failure"
    elif code.startswith(("overlapping_claim_spans", "anchors_without_final_claims")):
        subtype = "semantic_decision_failure"
    elif code.startswith((
        "source_anchor_id_not_unique", "source_text_sha256_mismatch",
        "anchor_without_both_reviewer_claim_sets", "reviewer_claim_span_invalid",
        "reviewer_claim_text_integrity_failure", "reviewer_claim_id_not_unique",
        "derived_occurrence_verification_failure", "source_field_role_unmapped",
    )):
        subtype = "verification_failure"
    else:
        return {
            "level": 2, "level_code": "boundary_semantic_contract",
            "classification_status": "insufficient_evidence", "observed_subtype": None,
        }
    return {
        "level": 2, "level_code": "boundary_semantic_contract",
        "classification_status": "classified", "observed_subtype": subtype,
    }


def execute() -> int:
    state = validate_frozen_inputs()
    if not MANIFEST.exists(): raise ValueError("execution_manifest_missing_run_prepare_first")
    if load(MANIFEST) != execution_manifest(): raise ValueError("execution_manifest_verification_failed")
    manifest_hash = sha(MANIFEST)
    if ATTEMPT_LOG.exists(): verify_entries(read_entries(ATTEMPT_LOG))
    key = os.environ.get(CREDENTIAL_ENV)
    if not key: raise ValueError(f"credential_env_missing:{CREDENTIAL_ENV}")
    system_prompt, user_template = split_prompt()
    worklist, entries = state["worklist"], read_entries(ATTEMPT_LOG)
    all_claims, case_results, reported_models, canonical_models = [], [], set(), set()
    for case in worklist["cases"]:
        case_id, checkpoint = case["case_id"], checkpoint_path(case["case_id"])
        if checkpoint.exists():
            saved = load(checkpoint)
            if saved.get("manifest_sha256") != manifest_hash or saved.get("case_id") != case_id or saved.get("status") != "completed":
                raise ValueError(f"case_checkpoint_verification_failed:{case_id}")
            all_claims.extend(saved["claims"]); case_results.append(saved["case_result"])
            reported_models.add(saved["provider_reported_model"]); canonical_models.add(saved["canonical_model_family"])
            print(f"Adjudicator {case_id}: resumed immutable checkpoint ({len(saved['claims'])} Claims)", flush=True)
            continue
        prior = [x for x in entries if x.get("manifest_sha256") == manifest_hash and x.get("case_id") == case_id and x.get("response_received") is True]
        if prior: raise ValueError(f"authoritative_content_already_recorded_without_checkpoint:{case_id}")
        append_event({"event_type": "boundary_adjudication_case_attempt_started", "manifest_sha256": manifest_hash,
                      "case_id": case_id, "response_received": False, "authoritative_result": False}, ATTEMPT_LOG)
        envelope_bytes = None; envelope_hash = None; content_hash = None; content_received = False
        try:
            case_json = json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            envelope, envelope_bytes = request_provider(key, system_prompt, user_template.replace("{{CASE_JSON}}", case_json))
            envelope_hash = sha_bytes(envelope_bytes)
            reported, content = extract_content(envelope)
            content_received, content_hash = True, sha_bytes(content.encode("utf-8"))
            append_event({"event_type": "boundary_adjudication_provider_content_received", "manifest_sha256": manifest_hash,
                          "case_id": case_id, "response_received": True, "authoritative_result": True,
                          "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash,
                          "raw_provider_content_stored": False}, ATTEMPT_LOG)
            claims = normalize_case(case, json.loads(content)); canonical = canonical_model_family(reported)
            saved = {"schema_version": 4, "case_id": case_id, "status": "completed", "manifest_sha256": manifest_hash,
                     "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash,
                     "provider_reported_model": reported, "canonical_model_family": canonical,
                     "normalized_claims_sha256": canonical_sha(claims), "claims": claims,
                     "case_result": {"case_id": case_id, "status": "completed", "anchor_count": len(case["source_anchors"]),
                                     "claim_count": len(claims), "provider_content_sha256": content_hash},
                     "raw_provider_content_stored": False, "held_out_accessed": False}
            write_once(checkpoint, saved)
            append_event({"event_type": "boundary_adjudication_case_authoritative_success", "manifest_sha256": manifest_hash,
                          "case_id": case_id, "response_received": True, "authoritative_result": True,
                          "provider_content_sha256": content_hash, "normalized_output_sha256": canonical_sha(claims),
                          "claim_count": len(claims), "provider_reported_model": reported,
                          "canonical_model_family": canonical}, ATTEMPT_LOG)
            all_claims.extend(claims); case_results.append(saved["case_result"])
            reported_models.add(reported); canonical_models.add(canonical)
            print(f"Adjudicator {case_id}: {len(claims)} Claims", flush=True)
        except urllib.error.HTTPError as error:
            append_event({"event_type": "boundary_adjudication_case_transport_failure", "manifest_sha256": manifest_hash,
                          "case_id": case_id, "status": f"http_{error.code}", "response_received": False,
                          "authoritative_result": False}, ATTEMPT_LOG)
            print(f"TRANSPORT FAILURE {case_id}: HTTP {error.code}"); return 3
        except (urllib.error.URLError, TimeoutError) as error:
            append_event({"event_type": "boundary_adjudication_case_transport_failure", "manifest_sha256": manifest_hash,
                          "case_id": case_id, "status": type(error).__name__, "response_received": False,
                          "authoritative_result": False}, ATTEMPT_LOG)
            print(f"TRANSPORT FAILURE {case_id}: {type(error).__name__}: {error}"); return 3
        except Exception as error:
            response_received = envelope_bytes is not None
            classification = failure_classification(error, content_received)
            event = {
                "event_type": "boundary_adjudication_case_experimental_failure" if response_received else "boundary_adjudication_case_adapter_failure",
                "manifest_sha256": manifest_hash, "case_id": case_id,
                "status": type(error).__name__, "error_code": str(error)[:400],
                "response_received": response_received, "provider_content_received": content_received,
                "authoritative_result": response_received,
                "failure_level": classification["level"],
                "failure_level_code": classification["level_code"],
                "level2_subtype_classification_status": classification["classification_status"],
                "level2_observed_subtype": classification["observed_subtype"],
            }
            if envelope_hash:
                event["provider_envelope_sha256"] = envelope_hash
            if content_hash:
                event["provider_content_sha256"] = content_hash
            append_event(event, ATTEMPT_LOG)
            write_once(NEGATIVE_RESULT, {
                "schema_version": 4,
                "result_id": "phase7.3.3-d1-a-boundary-adjudicator-negative-result-v4",
                "status": "authoritative_negative_result" if response_received else "adapter_failure",
                "manifest_sha256": manifest_hash, "case_id": case_id,
                "failure_type": type(error).__name__, "failure_code": str(error)[:400],
                "response_received": response_received,
                "provider_content_received": content_received,
                "provider_envelope_sha256": envelope_hash,
                "provider_content_sha256": content_hash,
                "failure_taxonomy": {
                    "level": classification["level"],
                    "level_code": classification["level_code"],
                    "attribution": {
                        "primary": "provider" if response_received else "implementation",
                        "subtype": "frozen_adjudication_contract_failure" if response_received else "local_adapter_failure_before_provider_response",
                        "confidence": "high" if response_received else "medium",
                        "evidence": [str(error)[:400]], "counterevidence": [],
                    },
                    "level2_diagnostic_subtype": {
                        "classification_status": classification["classification_status"],
                        "observed_subtype": classification["observed_subtype"],
                        "prospectively_frozen_before_v4_execution": True,
                        "level2_failure_subtypes_v1_sha256": sha(LEVEL2_FAILURE_SUBTYPES),
                    },
                },
                "raw_provider_content_stored": False,
                "same_manifest_retry_authorized": not response_received,
                "adjudication_completed": False,
                "coverage_qa_allowed": False,
                "boundary_gold_frozen": False,
                "support_review_allowed": False,
                "held_out_accessed": False,
            })
            print(f"EXPERIMENTAL FAILURE {case_id}: {type(error).__name__}: {error}")
            return 4
    if canonical_models != {MODEL_REQUESTED}: raise ValueError(f"canonical_model_family_drift:{sorted(canonical_models)}")
    submission = {"schema_version": 4, "submission_id": "phase7.3.3-d1-a-boundary-adjudicator-submission-v4",
                  "status": "completed_model_adjudicated_boundary_reference_candidate",
                  "gold_status": "model_adjudicated_boundary_reference_candidate_not_human_gold",
                  "manifest_sha256": manifest_hash, "adjudication_protocol_sha256": sha(ADJUDICATION_PROTOCOL),
                  "agreement_report_sha256": sha(AGREEMENT_REPORT), "worklist_sha256": sha(WORKLIST),
                  "case_count": len(case_results), "claim_count": len(all_claims), "claims": all_claims,
                  "boundary_gold_frozen": False, "coverage_qa_completed": False,
                  "support_review_allowed": False, "held_out_accessed": False}
    submission_hash = write_once(SUBMISSION, submission)
    decision = generate_decision_log(worklist, all_claims, manifest_hash, submission_hash)
    decision_hash = write_once(DECISION_LOG, decision)
    verify_entries(read_entries(ATTEMPT_LOG)); attempt_hash = sha(ATTEMPT_LOG)
    result = {"schema_version": 4, "execution_id": "phase7.3.3-d1-a-boundary-adjudicator-execution-v4",
              "status": "completed", "manifest_sha256": manifest_hash, "submission_sha256": submission_hash,
              "segmentation_decision_log_sha256": decision_hash, "attempt_log_sha256": attempt_hash,
              "model_requested": MODEL_REQUESTED, "canonical_model_family": MODEL_REQUESTED,
              "provider_reported_models": sorted(reported_models), "completed_case_count": len(case_results),
              "claim_count": len(all_claims), "case_results": case_results, "raw_provider_content_stored": False,
              "adjudication_completed": True, "coverage_qa_allowed": True, "coverage_qa_completed": False,
              "boundary_gold_frozen": False, "support_review_allowed": False, "held_out_accessed": False}
    result_hash = write_once(RESULT, result)
    readiness = {
        "schema_version": 5,
        "state_id": "phase7.3.3-d1-reference-construction-readiness-v5",
        "status": "v4_adjudication_completed_coverage_qa_allowed",
        "preserves_v3_negative_readiness_sha256": sha(V3_REFERENCE_READINESS),
        "preserves_v4_execution_readiness_sha256": sha(EXECUTION_READINESS),
        "manifest_sha256": manifest_hash,
        "adjudicator_submission_sha256": submission_hash,
        "segmentation_decision_log_sha256": decision_hash,
        "execution_result_sha256": result_hash,
        "gates": {
            "agreement_frozen": True, "adjudication_allowed": True,
            "adjudication_completed": True, "coverage_qa_allowed": True,
            "coverage_qa_completed": False, "boundary_gold_frozen": False,
            "support_review_allowed": False, "held_out_accessed": False,
        },
    }
    readiness_hash = write_once(READINESS_V5, readiness)
    print(json.dumps({
        "status": "completed", "manifest_sha256": manifest_hash,
        "cases": len(case_results), "claims": len(all_claims),
        "submission_sha256": submission_hash,
        "segmentation_decision_log_sha256": decision_hash,
        "execution_result_sha256": result_hash,
        "readiness_v5_sha256": readiness_hash,
        "decision_count_by_category": decision["decision_count_by_category"],
        "coverage_qa_allowed": True, "boundary_gold_frozen": False,
        "support_review_allowed": False,
    }, ensure_ascii=False, indent=2))
    return 0


def verify() -> dict[str, Any]:
    state = validate_frozen_inputs()
    checks: dict[str, Any] = {"frozen_inputs": True, "held_out_accessed": False}
    if FIXTURE_REPORT.exists():
        fixture = load(FIXTURE_REPORT)
        checks.update({"fixtures_passed": fixture.get("all_fixtures_passed") is True,
                       "fixture_adapter_sha_matches": fixture.get("adapter_sha256") == sha(Path(__file__)),
                       "fixture_prompt_sha_matches": fixture.get("prompt_sha256") == sha(PROMPT)})
    if MANIFEST.exists():
        checks["manifest_matches_current_frozen_environment"] = load(MANIFEST) == execution_manifest()
        checks["manifest_sha256"] = sha(MANIFEST)
    if ATTEMPT_LOG.exists(): verify_entries(read_entries(ATTEMPT_LOG)); checks["attempt_log_hash_chain_valid"] = True
    if SUBMISSION.exists():
        submission = load(SUBMISSION)
        regenerated = generate_decision_log(state["worklist"], submission["claims"], sha(MANIFEST), sha(SUBMISSION))
        checks.update({"decision_log_deterministic_replay": DECISION_LOG.exists() and load(DECISION_LOG) == regenerated,
                       "submission_claim_count": len(submission["claims"]),
                       "boundary_gold_frozen": submission.get("boundary_gold_frozen"),
                       "support_review_allowed": submission.get("support_review_allowed")})
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true"); parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if sum(bool(x) for x in (args.fixtures, args.prepare, args.execute, args.verify)) != 1:
        parser.error("choose exactly one of --fixtures, --prepare, --execute, --verify")
    if args.fixtures: print(json.dumps(run_contract_fixtures(), ensure_ascii=False, indent=2)); return 0
    if args.prepare: prepare(); return 0
    if args.execute: return execute()
    print(json.dumps(verify(), ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())

