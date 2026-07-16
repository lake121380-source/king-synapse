#!/usr/bin/env python3
"""Freeze the Phase 7.3.3-D identifiable multi-claim successor entry contract.

Design-only: no successor data opening, provider call, scoring, Confirmatory,
or Runtime authorization.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

RESEARCH_QUESTION = CONFIG / "phase7_3_3_d_multi_claim_successor_research_question_v1.json"
CONSTRUCTION_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_frame_construction_protocol_v1.json"
REFERENCE_SCHEMA = CONFIG / "phase7_3_3_d_multi_claim_reference_schema_v1.json"
IDENTIFIABILITY_POLICY = CONFIG / "phase7_3_3_d_multi_claim_identifiability_policy_v1.json"
SAMPLING_POLICY = CONFIG / "phase7_3_3_d_multi_claim_sampling_policy_v1.json"
METRIC_SPEC = CONFIG / "phase7_3_3_d_multi_claim_metric_specification_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_entry_manifest_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_entry_outcome_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_entry_receipt_v1.json"
STATE = DATA / "phase7_3_3_d_support_stage_state_v25.json"
READINESS = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v36.json"

STATE_PREV = DATA / "phase7_3_3_d_support_stage_state_v24.json"
READINESS_PREV = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v35.json"
FINAL_AUDIT_MANIFEST = REPORTS / "phase7_3_3_d_independent_pilot_final_audit_manifest_v1.json"
FINAL_AUDIT_REPORT = REPORTS / "phase7_3_3_d_independent_pilot_final_audit_report_v1.json"
FINAL_AUDIT_RECEIPT = REPORTS / "phase7_3_3_d_independent_pilot_final_audit_receipt_v1.json"
ANALYSIS_V2_REPORT = REPORTS / "phase7_3_3_d_independent_pilot_analysis_report_v2.json"
POWER_V2_REPORT = REPORTS / "phase7_3_3_d_independent_pilot_power_gate_report_v2.json"
SAMPLE_SIZE_V2 = REPORTS / "phase7_3_3_d_independent_pilot_sample_size_freeze_v2.json"

EXPECTED_INPUT_SHA256 = {
    STATE_PREV: "66ebb491cfe5693119e27ffb85c8917fc85f610fcb5305bedbc42ab353f5af77",
    READINESS_PREV: "0ed907df793f413261954743d879a80b4a681ed265febabbd3e1d71971176b29",
    FINAL_AUDIT_MANIFEST: "3e0f6908038b866c31a37b11bf9b045a3df3e579336414ec7ee68003dab6b65b",
    FINAL_AUDIT_REPORT: "887a6f65cd53870e6a6dcb23f22f01dd7769576643800bd359ad8ccdb471fa5c",
    FINAL_AUDIT_RECEIPT: "a10dd05932f6631ea7133cd2b1f419cfe217721dff14caeee530f41b5a0c93d3",
    ANALYSIS_V2_REPORT: "2e641f82f11c4543a4b86418c4255c6397cef15da11d8d717acd289f81611406",
    POWER_V2_REPORT: "41dd789447225e89373e47d5371a3801f34ce8e77e54b5145fd897142d3ef199",
    SAMPLE_SIZE_V2: "3a99e6103623c462e66343be175bfde5da1c2101c4173dd71c015f6cd36f50a8",
}

CONFIG_OUTPUTS = [RESEARCH_QUESTION, CONSTRUCTION_PROTOCOL, REFERENCE_SCHEMA,
                  IDENTIFIABILITY_POLICY, SAMPLING_POLICY, METRIC_SPEC]
OUTPUTS = [*CONFIG_OUTPUTS, FIXTURES, MANIFEST, OUTCOME, STATE, READINESS, RECEIPT]
NEXT_STAGE = "construct_multi_claim_successor_sampling_frame_v1"
ENTRY_STATUS = "multi_claim_successor_entry_protocol_frozen_sampling_not_started"
PRIMARY_ESTIMAND = "paired_mean_material_error_span_iou_atomic_minus_candidate"
LABELS = ("supported", "partially_supported", "unsupported")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def raw(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def write_once(path: Path, value: Any) -> str:
    content = raw(value)
    expected = digest_bytes(content)
    if path.exists():
        require(path.read_bytes() == content, f"immutable_artifact_conflict:{rel(path)}")
        return expected
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    temporary.replace(path)
    return expected


def design_documents() -> dict[Path, dict[str, Any]]:
    research = {
        "schema_version": 1,
        "research_question_id": "phase7.3.3-d-multi-claim-successor-research-question-v1",
        "status": "frozen_before_successor_content_open",
        "study_role": "exploratory_identifiable_successor_pilot",
        "predecessor_finding": {
            "pilot_status": "completed_single_claim_frame",
            "observed_candidate_exact_accuracy": 0.55,
            "observed_atomic_exact_accuracy": 0.55,
            "observed_paired_exact_effect": 0.0,
            "general_atomic_localization_superiority_estimable": False,
            "interpretation": "The zero paired exact-label effect is not a localization-superiority effect because both arms collapsed to whole-Candidate units."
        },
        "object_of_study": "diagnostic_localization_capability_after_atomic_decomposition",
        "research_question": "When a Candidate contains multiple independently adjudicable claims with within-Candidate support heterogeneity, does Atomic-level measurement localize material support errors more precisely than Candidate-level measurement under equal resources?",
        "primary_estimand": PRIMARY_ESTIMAND,
        "unit_of_pairing": "unique_candidate",
        "primary_hypothesis": "The mean per-Candidate material-error span IoU of the Atomic arm exceeds that of the Candidate arm.",
        "null_hypothesis": "The paired mean difference in material-error span IoU is less than or equal to zero.",
        "scope_constraints": [
            "No conclusion from the predecessor single-claim Pilot is reused as a successor effect estimate.",
            "No Confirmatory sample size is computed until structural and realized-representation identifiability gates pass.",
            "The successor remains exploratory until a later power gate explicitly authorizes Confirmatory opening.",
            "Transport compliance is reported separately from semantic and localization capability."
        ],
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False
    }

    construction = {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-multi-claim-frame-construction-protocol-v1",
        "status": "frozen_before_successor_content_open",
        "purpose": "Construct a new independent multi-claim Reference that makes the target localization estimand structurally identifiable.",
        "stages": [
            "entry_protocol_freeze", "metadata_first_source_inventory",
            "deterministic_sampling_frame_freeze", "selected_content_open",
            "candidate_multi_claim_prescreen", "independent_boundary_review_a",
            "independent_boundary_review_b", "boundary_agreement", "boundary_adjudication",
            "independent_support_review_a", "independent_support_review_b",
            "support_agreement", "support_adjudication",
            "character_accounting_and_coverage_qa", "reference_freeze_and_seal",
            "structural_identifiability_gate", "equal_resource_dual_arm_execution",
            "realized_representation_identifiability_gate", "exploratory_scoring",
            "power_and_sample_size_gate"
        ],
        "independence_contract": {
            "new_source_inventory_required": True,
            "exclude_route_a_candidate_hash_overlap": True,
            "exclude_predecessor_pilot_candidate_hash_overlap": True,
            "exclude_evidence_hash_overlap_with_prior_gold_when_available": True,
            "old_boundary_or_support_gold_may_seed_new_labels": False,
            "old_arm_outputs_visible_to_reference_reviewers": False,
            "new_reference_visible_to_arms": False,
            "arms_visible_to_each_other": False
        },
        "review_separation": {
            "boundary_decision_separate_from_support_decision": True,
            "claim_type_separate_from_boundary": True,
            "structural_metadata_separate_from_support_label": True,
            "coverage_gaps_explicitly_classified": True,
            "uncovered_eligible_characters_allowed_at_freeze": 0
        },
        "candidate_contract": {
            "one_candidate_record_per_unique_candidate_text": True,
            "candidate_must_support_multiple_independently_adjudicable_claims": True,
            "coordination_or_clause_count_is_only_prescreen_not_gold": True,
            "within_candidate_support_heterogeneity_required_at_frame_level": True
        },
        "failure_governance": {
            "first_provider_content_authoritative": True,
            "same_version_semantic_retry_allowed": False,
            "silent_repair_allowed": False,
            "failed_version_retained": True,
            "successor_version_required_for_contract_change": True,
            "gate_skipping_allowed": False
        },
        "current_scope": "design_only_no_successor_dataset_content_open_no_provider_call",
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False
    }

    reference_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "phase7.3.3-d-multi-claim-reference-schema-v1",
        "title": "Phase 7.3.3-D Multi-claim Successor Reference",
        "type": "object",
        "required": ["schema_version", "reference_id", "status", "cases"],
        "properties": {
            "schema_version": {"const": 1},
            "reference_id": {"type": "string", "minLength": 1},
            "status": {"const": "frozen_and_sealed"},
            "cases": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["case_id", "candidate_text", "candidate_sha256",
                                 "eligible_start_char", "eligible_end_char", "evidence_items",
                                 "reference_claims", "explicit_non_claim_spans",
                                 "protocol_excluded_spans", "coverage_accounting"],
                    "properties": {
                        "case_id": {"type": "string", "minLength": 1},
                        "candidate_text": {"type": "string", "minLength": 1},
                        "candidate_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        "eligible_start_char": {"type": "integer", "minimum": 0},
                        "eligible_end_char": {"type": "integer", "minimum": 1},
                        "evidence_items": {
                            "type": "array", "minItems": 1,
                            "items": {"type": "object",
                                      "required": ["evidence_id", "evidence_text", "evidence_sha256"],
                                      "properties": {
                                          "evidence_id": {"type": "string", "minLength": 1},
                                          "evidence_text": {"type": "string"},
                                          "evidence_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
                                      "additionalProperties": False}
                        },
                        "reference_claims": {
                            "type": "array", "minItems": 1,
                            "items": {"type": "object",
                                      "required": ["claim_id", "start_char", "end_char", "source_excerpt",
                                                   "occurrence_index", "claim_role", "claim_type", "support_label",
                                                   "material_error", "cited_evidence_ids",
                                                   "boundary_decision_reason", "support_decision_reason"],
                                      "properties": {
                                          "claim_id": {"type": "string", "minLength": 1},
                                          "start_char": {"type": "integer", "minimum": 0},
                                          "end_char": {"type": "integer", "minimum": 1},
                                          "source_excerpt": {"type": "string", "minLength": 1},
                                          "occurrence_index": {"type": "integer", "minimum": 0},
                                          "claim_role": {"enum": ["anchor", "support", "qualification", "boundary", "prediction", "exception"]},
                                          "claim_type": {"enum": ["proposition", "causal", "prediction", "scope", "falsifiability", "limitation", "condition", "exception"]},
                                          "support_label": {"enum": list(LABELS)},
                                          "material_error": {"type": "boolean"},
                                          "cited_evidence_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                                          "boundary_decision_reason": {"type": "string", "minLength": 1},
                                          "support_decision_reason": {"type": "string", "minLength": 1}},
                                      "additionalProperties": False}
                        },
                        "explicit_non_claim_spans": {"type": "array", "items": {"$ref": "#/$defs/accounted_span"}},
                        "protocol_excluded_spans": {"type": "array", "items": {"$ref": "#/$defs/accounted_span"}},
                        "coverage_accounting": {
                            "type": "object",
                            "required": ["eligible_gap_characters", "overlap_characters", "all_eligible_characters_accounted"],
                            "properties": {"eligible_gap_characters": {"const": 0},
                                           "overlap_characters": {"const": 0},
                                           "all_eligible_characters_accounted": {"const": True}},
                            "additionalProperties": False}
                    },
                    "additionalProperties": False
                }
            }
        },
        "$defs": {"accounted_span": {"type": "object",
                                       "required": ["start_char", "end_char", "source_excerpt", "reason_code"],
                                       "properties": {"start_char": {"type": "integer", "minimum": 0},
                                                      "end_char": {"type": "integer", "minimum": 1},
                                                      "source_excerpt": {"type": "string"},
                                                      "reason_code": {"type": "string", "minLength": 1}},
                                       "additionalProperties": False}},
        "additionalProperties": False,
        "semantic_invariants_not_expressible_in_json_schema": [
            "source_excerpt equals candidate_text[start_char:end_char] exactly",
            "candidate_sha256 hashes exact UTF-8 candidate_text bytes",
            "each cited_evidence_id exists in evidence_items",
            "material_error is true exactly when support_label is partially_supported or unsupported",
            "claim, explicit-non-claim, and protocol-excluded spans account for every eligible character exactly once",
            "claim IDs and case IDs are unique"
        ]
    }

    identifiability = {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d-multi-claim-identifiability-policy-v1",
        "status": "frozen_before_successor_content_open",
        "target_estimand": PRIMARY_ESTIMAND,
        "all_checks_required": True,
        "structural_reference_gate": {
            "minimum_selected_candidate_count": 32,
            "target_selected_candidate_count": 40,
            "unique_candidate_rate_min": 1.0,
            "median_reference_claims_per_candidate_min": 2.0,
            "multi_claim_candidate_rate_min": 0.8,
            "reference_claim_to_candidate_ratio_min": 1.8,
            "within_candidate_label_heterogeneity_rate_min": 0.5,
            "supported_plus_material_error_candidate_rate_min": 0.3,
            "material_error_claim_rate_min": 0.25,
            "unsupported_claim_rate_min": 0.1,
            "partially_supported_claim_rate_min": 0.1,
            "maximum_single_label_share": 0.7,
            "eligible_gap_characters_required": 0,
            "overlap_characters_required": 0
        },
        "realized_representation_gate": {
            "candidate_decisions_per_selected_candidate": 1,
            "atomic_unit_to_candidate_ratio_min": 1.8,
            "atomic_multi_unit_candidate_rate_min": 0.8,
            "atomic_whole_candidate_operation_rate_max": 0.2,
            "atomic_local_span_operation_rate_min": 0.8,
            "atomic_duplicate_span_rate_max": 0.05,
            "missing_candidate_outputs_allowed": 0,
            "duplicate_candidate_outputs_allowed": 0,
            "reference_visible_during_arm_execution": False
        },
        "gate_actions": {
            "on_pass": "authorize_exploratory_scoring_only",
            "on_structural_failure": "freeze_negative_result_and_do_not_execute_arms",
            "on_realized_representation_failure": "freeze_negative_result_and_do_not_score_localization_estimand",
            "same_version_retry_allowed": False,
            "confirmatory_opening_authorized": False
        },
        "threshold_rationale": "Structural anti-degeneracy requirements frozen before successor content opening; not effect-size or significance thresholds.",
        "runtime_integration_authorized": False
    }

    sampling = {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d-multi-claim-successor-sampling-policy-v1",
        "status": "frozen_before_successor_inventory_open",
        "target_selected_candidate_count": 40,
        "minimum_selected_candidate_count": 32,
        "sampling_unit": "unique_candidate_text",
        "duplicate_candidate_hash_allowed": False,
        "source_requirements": {
            "new_inventory_required": True,
            "route_a_overlap_excluded": True,
            "predecessor_independent_pilot_overlap_excluded": True,
            "evidence_overlap_excluded_when_identity_available": True
        },
        "selection": {
            "method": "deterministic_stratified_hash_order",
            "seed": 733051,
            "prescreen_dimensions": ["source_family", "evidence_item_count_bucket", "deterministic_clause_count_bucket"],
            "support_labels_available_during_sampling": False,
            "old_gold_available_during_sampling": False,
            "clause_count_is_gold_claim_count": False,
            "shortfall_action": "freeze_shortfall_and_stop_without_manual_backfill"
        },
        "content_opening": {
            "entry_freeze_stage": False,
            "sampling_frame_stage": "only_after_metadata_inventory_and_manifest_freeze",
            "confirmatory_dataset_opened": False
        },
        "provider_call_authorized": False,
        "runtime_integration_authorized": False
    }

    metric = {
        "schema_version": 1,
        "metric_specification_id": "phase7.3.3-d-multi-claim-metric-specification-v1",
        "status": "frozen_before_successor_content_open",
        "primary_estimand": PRIMARY_ESTIMAND,
        "gold_material_error_mask": "Union of exact Reference claim character spans labeled partially_supported or unsupported.",
        "candidate_arm_predicted_error_mask": "Empty when Candidate label is supported; otherwise the entire eligible Candidate span.",
        "atomic_arm_predicted_error_mask": "Union of Atomic claim spans predicted partially_supported or unsupported.",
        "per_candidate_material_error_span_iou": {
            "formula": "intersection_characters / union_characters",
            "empty_gold_empty_prediction": 1.0,
            "one_empty_one_nonempty": 0.0
        },
        "paired_primary_effect": "mean(atomic_per_candidate_iou - candidate_per_candidate_iou)",
        "candidate_reference_label_aggregation": {
            "all_claims_supported": "supported",
            "all_claims_unsupported": "unsupported",
            "otherwise": "partially_supported"
        },
        "secondary_metrics": [
            "unsupported_claim_detection_recall", "material_error_localization_precision",
            "material_error_localization_recall", "material_error_localization_micro_f1",
            "unsupported_masking_rate", "exact_candidate_label_accuracy",
            "atomic_exact_claim_label_accuracy", "boundary_exact_span_rate",
            "boundary_mean_matched_iou", "diagnostic_span_compactness",
            "transport_compliance", "tokens_and_latency_by_arm"
        ],
        "uncertainty": {"method": "unique_candidate_nonparametric_bootstrap",
                        "seed": 733061, "replicates": 20000, "interval": 0.95,
                        "confirmatory_p_value": None},
        "missingness": {"no_silent_drop": True, "all_selected_cases_in_denominator": True,
                        "transport_failure_reported_separately": True},
        "cost_policy": {"token_and_latency_measurement_required": True,
                        "usd_cost_may_be_non_null_only_if_provider_price_was_frozen_before_execution": True},
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False
    }
    return {RESEARCH_QUESTION: research, CONSTRUCTION_PROTOCOL: construction,
            REFERENCE_SCHEMA: reference_schema, IDENTIFIABILITY_POLICY: identifiability,
            SAMPLING_POLICY: sampling, METRIC_SPEC: metric}


def valid_frame_summary() -> dict[str, Any]:
    labels = ([ ["supported", "unsupported"] for _ in range(20)]
              + [["supported", "partially_supported"] for _ in range(12)]
              + [["supported", "supported"] for _ in range(8)])
    return {"selected_candidate_count": 40, "unique_candidate_count": 40,
            "labels_per_candidate": labels, "eligible_gap_characters": 0,
            "overlap_characters": 0}


def valid_representation_summary() -> dict[str, Any]:
    return {"selected_candidate_count": 40, "candidate_decision_count": 40,
            "atomic_units_per_candidate": [2] * 32 + [1] * 8,
            "atomic_whole_candidate_operation_count": 8,
            "atomic_local_span_operation_count": 64,
            "atomic_duplicate_span_count": 0,
            "missing_candidate_output_count": 0,
            "duplicate_candidate_output_count": 0,
            "reference_visible_during_execution": False}


def structural_failures(summary: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    p = policy["structural_reference_gate"]
    selected, unique = summary["selected_candidate_count"], summary["unique_candidate_count"]
    labels_per_candidate = summary["labels_per_candidate"]
    claims_per_candidate = [len(labels) for labels in labels_per_candidate]
    all_labels = [label for labels in labels_per_candidate for label in labels]
    counts, total = Counter(all_labels), len(all_labels)
    material = counts["partially_supported"] + counts["unsupported"]
    checks = {
        "minimum_selected_candidate_count": selected >= p["minimum_selected_candidate_count"],
        "unique_candidate_rate": selected > 0 and unique / selected >= p["unique_candidate_rate_min"],
        "median_reference_claims_per_candidate": bool(claims_per_candidate) and statistics.median(claims_per_candidate) >= p["median_reference_claims_per_candidate_min"],
        "multi_claim_candidate_rate": selected > 0 and sum(n >= 2 for n in claims_per_candidate) / selected >= p["multi_claim_candidate_rate_min"],
        "reference_claim_to_candidate_ratio": selected > 0 and total / selected >= p["reference_claim_to_candidate_ratio_min"],
        "within_candidate_label_heterogeneity_rate": selected > 0 and sum(len(set(x)) >= 2 for x in labels_per_candidate) / selected >= p["within_candidate_label_heterogeneity_rate_min"],
        "supported_plus_material_error_candidate_rate": selected > 0 and sum("supported" in x and any(y != "supported" for y in x) for x in labels_per_candidate) / selected >= p["supported_plus_material_error_candidate_rate_min"],
        "material_error_claim_rate": total > 0 and material / total >= p["material_error_claim_rate_min"],
        "unsupported_claim_rate": total > 0 and counts["unsupported"] / total >= p["unsupported_claim_rate_min"],
        "partially_supported_claim_rate": total > 0 and counts["partially_supported"] / total >= p["partially_supported_claim_rate_min"],
        "maximum_single_label_share": total > 0 and max(counts.values(), default=0) / total <= p["maximum_single_label_share"],
        "eligible_gap_characters": summary["eligible_gap_characters"] == p["eligible_gap_characters_required"],
        "overlap_characters": summary["overlap_characters"] == p["overlap_characters_required"]}
    return [name for name, ok in checks.items() if not ok]


def representation_failures(summary: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    p = policy["realized_representation_gate"]
    selected, units = summary["selected_candidate_count"], summary["atomic_units_per_candidate"]
    total = sum(units)
    checks = {
        "candidate_decisions_per_selected_candidate": summary["candidate_decision_count"] == selected * p["candidate_decisions_per_selected_candidate"],
        "atomic_unit_to_candidate_ratio": selected > 0 and total / selected >= p["atomic_unit_to_candidate_ratio_min"],
        "atomic_multi_unit_candidate_rate": selected > 0 and sum(n >= 2 for n in units) / selected >= p["atomic_multi_unit_candidate_rate_min"],
        "atomic_whole_candidate_operation_rate": total > 0 and summary["atomic_whole_candidate_operation_count"] / total <= p["atomic_whole_candidate_operation_rate_max"],
        "atomic_local_span_operation_rate": total > 0 and summary["atomic_local_span_operation_count"] / total >= p["atomic_local_span_operation_rate_min"],
        "atomic_duplicate_span_rate": total > 0 and summary["atomic_duplicate_span_count"] / total <= p["atomic_duplicate_span_rate_max"],
        "missing_candidate_outputs": summary["missing_candidate_output_count"] == p["missing_candidate_outputs_allowed"],
        "duplicate_candidate_outputs": summary["duplicate_candidate_output_count"] == p["duplicate_candidate_outputs_allowed"],
        "reference_blind": summary["reference_visible_during_execution"] is p["reference_visible_during_arm_execution"]}
    return [name for name, ok in checks.items() if not ok]


def fixture_definitions() -> list[dict[str, Any]]:
    good = valid_frame_summary()
    no_hetero = copy.deepcopy(good)
    no_hetero["labels_per_candidate"] = ([["supported", "supported"] for _ in range(20)]
        + [["unsupported", "unsupported"] for _ in range(10)]
        + [["partially_supported", "partially_supported"] for _ in range(10)])
    no_unsupported = copy.deepcopy(good)
    no_unsupported["labels_per_candidate"] = [["partially_supported" if y == "unsupported" else y for y in x] for x in no_unsupported["labels_per_candidate"]]
    no_partial = copy.deepcopy(good)
    no_partial["labels_per_candidate"] = [["unsupported" if y == "partially_supported" else y for y in x] for x in no_partial["labels_per_candidate"]]
    single = copy.deepcopy(good); single["labels_per_candidate"] = [["supported"] for _ in range(40)]
    duplicate = copy.deepcopy(good); duplicate["unique_candidate_count"] = 39
    gap = copy.deepcopy(good); gap["eligible_gap_characters"] = 1
    rep = valid_representation_summary()
    collapsed = copy.deepcopy(rep); collapsed.update({"atomic_units_per_candidate": [1] * 40, "atomic_whole_candidate_operation_count": 40, "atomic_local_span_operation_count": 0})
    dup_span = copy.deepcopy(rep); dup_span["atomic_duplicate_span_count"] = 4
    missing = copy.deepcopy(rep); missing["candidate_decision_count"] = 39
    visible = copy.deepcopy(rep); visible["reference_visible_during_execution"] = True
    low_local = copy.deepcopy(rep); low_local.update({"atomic_whole_candidate_operation_count": 20, "atomic_local_span_operation_count": 52})
    return [
        {"fixture_id": "structural_valid_multi_claim_diverse", "gate": "structural", "input": good, "expected_pass": True, "expected_failures": []},
        {"fixture_id": "structural_reject_single_claim_collapse", "gate": "structural", "input": single, "expected_pass": False, "expected_failures_contains": ["median_reference_claims_per_candidate", "multi_claim_candidate_rate", "reference_claim_to_candidate_ratio"]},
        {"fixture_id": "structural_reject_duplicate_candidate", "gate": "structural", "input": duplicate, "expected_pass": False, "expected_failures": ["unique_candidate_rate"]},
        {"fixture_id": "structural_reject_no_within_candidate_heterogeneity", "gate": "structural", "input": no_hetero, "expected_pass": False, "expected_failures": ["within_candidate_label_heterogeneity_rate", "supported_plus_material_error_candidate_rate"]},
        {"fixture_id": "structural_reject_no_unsupported_claims", "gate": "structural", "input": no_unsupported, "expected_pass": False, "expected_failures": ["unsupported_claim_rate"]},
        {"fixture_id": "structural_reject_no_partial_claims", "gate": "structural", "input": no_partial, "expected_pass": False, "expected_failures": ["partially_supported_claim_rate"]},
        {"fixture_id": "structural_reject_unaccounted_character", "gate": "structural", "input": gap, "expected_pass": False, "expected_failures": ["eligible_gap_characters"]},
        {"fixture_id": "representation_valid_localized_atomic_units", "gate": "representation", "input": rep, "expected_pass": True, "expected_failures": []},
        {"fixture_id": "representation_reject_whole_candidate_collapse", "gate": "representation", "input": collapsed, "expected_pass": False, "expected_failures_contains": ["atomic_unit_to_candidate_ratio", "atomic_multi_unit_candidate_rate", "atomic_whole_candidate_operation_rate", "atomic_local_span_operation_rate"]},
        {"fixture_id": "representation_reject_duplicate_spans", "gate": "representation", "input": dup_span, "expected_pass": False, "expected_failures": ["atomic_duplicate_span_rate"]},
        {"fixture_id": "representation_reject_missing_candidate_decision", "gate": "representation", "input": missing, "expected_pass": False, "expected_failures": ["candidate_decisions_per_selected_candidate"]},
        {"fixture_id": "representation_reject_reference_visibility", "gate": "representation", "input": visible, "expected_pass": False, "expected_failures": ["reference_blind"]},
        {"fixture_id": "representation_reject_low_local_span_rate", "gate": "representation", "input": low_local, "expected_pass": False, "expected_failures_contains": ["atomic_whole_candidate_operation_rate", "atomic_local_span_operation_rate"]}]


def fixture_report() -> dict[str, Any]:
    policy = design_documents()[IDENTIFIABILITY_POLICY]
    rows = []
    for fixture in fixture_definitions():
        failures = structural_failures(fixture["input"], policy) if fixture["gate"] == "structural" else representation_failures(fixture["input"], policy)
        observed_pass = not failures
        ok = observed_pass is fixture["expected_pass"]
        if "expected_failures" in fixture:
            ok = ok and failures == fixture["expected_failures"]
        if "expected_failures_contains" in fixture:
            ok = ok and set(fixture["expected_failures_contains"]).issubset(failures)
        rows.append({"fixture_id": fixture["fixture_id"], "gate": fixture["gate"],
                     "expected_pass": fixture["expected_pass"], "observed_pass": observed_pass,
                     "observed_failures": failures, "contract_pass": ok})
    passed = sum(row["contract_pass"] for row in rows)
    return {"schema_version": 1,
            "fixture_report_id": "phase7.3.3-d-multi-claim-successor-contract-fixtures-v1",
            "status": "PASS" if passed == len(rows) else "FAIL",
            "passed": passed, "total": len(rows), "fixtures": rows,
            "provider_called": False, "successor_content_opened": False,
            "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def preflight_checks(require_outputs_absent: bool = True) -> dict[str, Any]:
    missing = [rel(path) for path in EXPECTED_INPUT_SHA256 if not path.exists()]
    hashes = {rel(path): digest(path) for path in EXPECTED_INPUT_SHA256 if path.exists()}
    mismatches = {rel(path): {"expected": expected, "observed": hashes.get(rel(path))}
                  for path, expected in EXPECTED_INPUT_SHA256.items()
                  if path.exists() and hashes[rel(path)] != expected}
    state = load(STATE_PREV) if STATE_PREV.exists() else {}
    ready = load(READINESS_PREV) if READINESS_PREV.exists() else {}
    final = load(FINAL_AUDIT_REPORT) if FINAL_AUDIT_REPORT.exists() else {}
    power = load(POWER_V2_REPORT) if POWER_V2_REPORT.exists() else {}
    checks = {
        "required_inputs_present": not missing,
        "required_input_hashes_match": not mismatches,
        "predecessor_chain_completed": final.get("status") == "PASS_independent_pilot_chain_completed",
        "state_authorizes_successor_design": state.get("next_authorized_stage") == "design_successor_identifiable_multi_claim_pilot_frame_v1",
        "readiness_authorizes_successor_design": ready.get("next_authorized_stage") == "design_successor_identifiable_multi_claim_pilot_frame_v1",
        "predecessor_estimand_not_identifiable": power.get("status") == "power_infeasible_current_single_claim_frame" and power.get("observed_exact_effect_used_for_target_power") is False,
        "sample_size_remains_null": load(SAMPLE_SIZE_V2).get("sample_size_candidates") is None if SAMPLE_SIZE_V2.exists() else False,
        "confirmatory_closed": state.get("confirmatory_dataset_opened") is False and ready.get("confirmatory_dataset_opened") is False and final.get("confirmatory_opening_authorized") is False,
        "runtime_unauthorized": state.get("runtime_integration_authorized") is False and ready.get("runtime_integration_authorized") is False and final.get("runtime_integration_authorized") is False,
        "outputs_absent": not any(path.exists() for path in OUTPUTS) if require_outputs_absent else True}
    return {"checks": checks, "missing": missing, "mismatches": mismatches, "input_hashes": hashes}


def preflight() -> None:
    result = preflight_checks(True); ok = all(result["checks"].values())
    print(json.dumps({"status": "PASS" if ok else "FAIL", **result}, ensure_ascii=False, indent=2))
    if not ok: raise SystemExit(1)


def run_contract_fixtures() -> None:
    report = fixture_report(); print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS": raise SystemExit(1)


def build_manifest(docs: dict[Path, dict[str, Any]], fixtures: dict[str, Any]) -> dict[str, Any]:
    policy = docs[IDENTIFIABILITY_POLICY]
    return {"schema_version": 1,
            "manifest_id": "phase7.3.3-d-multi-claim-successor-entry-manifest-v1",
            "status": "frozen_before_successor_content_open",
            "stage": "design_successor_identifiable_multi_claim_pilot_frame_v1",
            "adapter": rel(Path(__file__).resolve()),
            "adapter_sha256": digest(Path(__file__).resolve()),
            "predecessor_artifact_sha256": {rel(path): expected for path, expected in EXPECTED_INPUT_SHA256.items()},
            "design_artifact_sha256": {rel(path): digest_bytes(raw(value)) for path, value in docs.items()},
            "fixture_artifact_sha256": digest_bytes(raw(fixtures)),
            "frozen_thresholds": {"structural_reference_gate": policy["structural_reference_gate"],
                                  "realized_representation_gate": policy["realized_representation_gate"]},
            "primary_estimand": PRIMARY_ESTIMAND,
            "successor_content_opened": False, "provider_called": False,
            "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def derived_documents(manifest_sha: str, design_hashes: dict[str, str], fixture_sha: str):
    state = copy.deepcopy(load(STATE_PREV)); state["schema_version"] = 25
    state["state_id"] = "phase7.3.3-d-support-stage-state-v25"
    lineage = dict(state.get("artifact_lineage", {}))
    lineage.update({"support_stage_state_v24_sha256": EXPECTED_INPUT_SHA256[STATE_PREV],
                    "readiness_v35_sha256": EXPECTED_INPUT_SHA256[READINESS_PREV],
                    "multi_claim_successor_entry_manifest_v1_sha256": manifest_sha,
                    "multi_claim_successor_contract_fixtures_v1_sha256": fixture_sha})
    for path_text, value in design_hashes.items(): lineage[Path(path_text).stem + "_sha256"] = value
    state["artifact_lineage"] = lineage
    state.update({"independent_pilot_chain_completed": True,
                  "predecessor_single_claim_estimand_identifiable": False,
                  "multi_claim_successor_design_started": True,
                  "multi_claim_successor_entry_protocol_frozen": True,
                  "multi_claim_successor_sampling_frame_frozen": False,
                  "multi_claim_successor_reference_frozen": False,
                  "multi_claim_structural_identifiability_gate_passed": False,
                  "multi_claim_realized_representation_gate_passed": False,
                  "multi_claim_successor_content_opened": False,
                  "multi_claim_successor_provider_called": False,
                  "next_authorized_stage": NEXT_STAGE,
                  "confirmatory_dataset_opened": False,
                  "confirmatory_opening_authorized": False,
                  "runtime_integration_authorized": False})
    ready = copy.deepcopy(load(READINESS_PREV)); ready["schema_version"] = 36
    ready["readiness_id"] = "phase7.3.3-d1-reference-construction-readiness-v36"
    ready_lineage = dict(ready.get("artifact_lineage", {}))
    ready_lineage.update({"support_stage_state_v24_sha256": EXPECTED_INPUT_SHA256[STATE_PREV],
                          "readiness_v35_sha256": EXPECTED_INPUT_SHA256[READINESS_PREV],
                          "multi_claim_successor_entry_manifest_v1_sha256": manifest_sha,
                          "multi_claim_successor_contract_fixtures_v1_sha256": fixture_sha})
    for path_text, value in design_hashes.items(): ready_lineage[Path(path_text).stem + "_sha256"] = value
    ready["artifact_lineage"] = ready_lineage
    ready.update({"status": ENTRY_STATUS,
                  "predecessor_pilot_status": "completed_power_infeasible_single_claim_frame",
                  "successor_study_role": "exploratory_identifiable_multi_claim_pilot",
                  "successor_entry_protocol_status": "frozen",
                  "successor_sampling_status": "not_started",
                  "successor_reference_status": "not_constructed",
                  "successor_structural_identifiability_status": "not_evaluated",
                  "successor_realized_representation_status": "not_evaluated",
                  "successor_primary_estimand": PRIMARY_ESTIMAND,
                  "sample_size_candidates": None,
                  "next_authorized_stage": NEXT_STAGE,
                  "successor_content_opened": False, "provider_called": False,
                  "confirmatory_dataset_opened": False,
                  "confirmatory_opening_authorized": False,
                  "runtime_integration_authorized": False})
    outcome = {"schema_version": 1,
               "outcome_id": "phase7.3.3-d-multi-claim-successor-entry-outcome-v1",
               "status": ENTRY_STATUS, "primary_estimand": PRIMARY_ESTIMAND,
               "design_artifact_count": len(design_hashes), "contract_fixtures": "13/13_PASS",
               "predecessor_single_claim_result_retained": True,
               "predecessor_effect_used_as_successor_localization_effect": False,
               "successor_content_opened": False, "provider_called": False,
               "confirmatory_dataset_opened": False,
               "confirmatory_opening_authorized": False,
               "runtime_integration_authorized": False,
               "next_authorized_stage": NEXT_STAGE}
    return state, ready, outcome


def freeze() -> None:
    entry = preflight_checks(True)
    if not all(entry["checks"].values()):
        print(json.dumps({"status": "FAIL", **entry}, ensure_ascii=False, indent=2)); raise SystemExit(1)
    docs, fixtures = design_documents(), fixture_report()
    require(fixtures["status"] == "PASS", "contract_fixtures_failed")
    manifest = build_manifest(docs, fixtures)
    hashes = {rel(path): write_once(path, value) for path, value in docs.items()}
    fixture_sha = write_once(FIXTURES, fixtures); hashes[rel(FIXTURES)] = fixture_sha
    manifest_sha = write_once(MANIFEST, manifest); hashes[rel(MANIFEST)] = manifest_sha
    state, ready, outcome = derived_documents(manifest_sha, manifest["design_artifact_sha256"], fixture_sha)
    outcome_sha = write_once(OUTCOME, outcome); state_sha = write_once(STATE, state)
    ready_sha = write_once(READINESS, ready)
    hashes.update({rel(OUTCOME): outcome_sha, rel(STATE): state_sha, rel(READINESS): ready_sha})
    receipt = {"schema_version": 1,
               "receipt_id": "phase7.3.3-d-multi-claim-successor-entry-receipt-v1",
               "status": "PASS", "artifact_sha256": hashes,
               "design_artifact_count": len(docs), "fixtures_passed": fixtures["passed"],
               "fixtures_total": fixtures["total"], "primary_estimand": PRIMARY_ESTIMAND,
               "successor_content_opened": False, "provider_called": False,
               "confirmatory_dataset_opened": False,
               "confirmatory_opening_authorized": False,
               "runtime_integration_authorized": False,
               "next_authorized_stage": NEXT_STAGE}
    receipt_sha = write_once(RECEIPT, receipt)
    print(json.dumps({"status": "PASS", "entry_status": ENTRY_STATUS,
                      "design_artifacts": len(docs),
                      "fixtures": f"{fixtures['passed']}/{fixtures['total']}",
                      "manifest_sha256": manifest_sha, "receipt_sha256": receipt_sha,
                      "state_sha256": state_sha, "readiness_sha256": ready_sha,
                      "next_authorized_stage": NEXT_STAGE,
                      "successor_content_opened": False, "provider_called": False,
                      "confirmatory_dataset_opened": False,
                      "runtime_integration_authorized": False}, ensure_ascii=False, indent=2))


def verify() -> None:
    missing = [rel(path) for path in OUTPUTS if not path.exists()]
    if missing:
        print(json.dumps({"status": "FAIL", "missing": missing}, indent=2)); raise SystemExit(1)
    docs, fixtures = design_documents(), fixture_report()
    manifest, receipt, state = load(MANIFEST), load(RECEIPT), load(STATE)
    ready, outcome = load(READINESS), load(OUTCOME)
    predecessor = preflight_checks(False)
    checks = {
        "all_outputs_exist": True,
        "predecessor_inputs_unchanged": predecessor["checks"]["required_inputs_present"] and predecessor["checks"]["required_input_hashes_match"],
        "adapter_hash": manifest["adapter_sha256"] == digest(Path(__file__).resolve()),
        "design_documents_exact": all(path.read_bytes() == raw(value) for path, value in docs.items()),
        "design_hash_lineage": all(manifest["design_artifact_sha256"][rel(path)] == digest(path) for path in docs),
        "fixture_exact": FIXTURES.read_bytes() == raw(fixtures),
        "fixture_pass": fixtures["status"] == "PASS" and fixtures["passed"] == fixtures["total"] == 13,
        "fixture_hash_lineage": manifest["fixture_artifact_sha256"] == digest(FIXTURES),
        "manifest_predecessor_hashes": manifest["predecessor_artifact_sha256"] == {rel(path): expected for path, expected in EXPECTED_INPUT_SHA256.items()},
        "primary_estimand_consistent": load(RESEARCH_QUESTION)["primary_estimand"] == load(IDENTIFIABILITY_POLICY)["target_estimand"] == load(METRIC_SPEC)["primary_estimand"] == PRIMARY_ESTIMAND,
        "single_claim_effect_not_reused": load(RESEARCH_QUESTION)["predecessor_finding"]["general_atomic_localization_superiority_estimable"] is False and outcome["predecessor_effect_used_as_successor_localization_effect"] is False,
        "structural_gate_frozen": load(IDENTIFIABILITY_POLICY)["structural_reference_gate"]["median_reference_claims_per_candidate_min"] == 2.0 and load(IDENTIFIABILITY_POLICY)["structural_reference_gate"]["within_candidate_label_heterogeneity_rate_min"] == 0.5,
        "realized_gate_frozen": load(IDENTIFIABILITY_POLICY)["realized_representation_gate"]["atomic_unit_to_candidate_ratio_min"] == 1.8 and load(IDENTIFIABILITY_POLICY)["realized_representation_gate"]["atomic_whole_candidate_operation_rate_max"] == 0.2,
        "state_v25": state["schema_version"] == 25 and state["multi_claim_successor_entry_protocol_frozen"] is True and state["next_authorized_stage"] == NEXT_STAGE,
        "readiness_v36": ready["schema_version"] == 36 and ready["status"] == ENTRY_STATUS and ready["next_authorized_stage"] == NEXT_STAGE,
        "receipt_hash_lineage": all(receipt["artifact_sha256"].get(rel(path)) == digest(path) for path in [*CONFIG_OUTPUTS, FIXTURES, MANIFEST, OUTCOME, STATE, READINESS]),
        "successor_not_opened": all(x is False for x in [manifest["successor_content_opened"], fixtures["successor_content_opened"], outcome["successor_content_opened"], state["multi_claim_successor_content_opened"], ready["successor_content_opened"], receipt["successor_content_opened"]]),
        "provider_not_called": all(x is False for x in [manifest["provider_called"], fixtures["provider_called"], outcome["provider_called"], state["multi_claim_successor_provider_called"], ready["provider_called"], receipt["provider_called"]]),
        "confirmatory_closed": all(x is False for x in [manifest["confirmatory_dataset_opened"], fixtures["confirmatory_dataset_opened"], outcome["confirmatory_dataset_opened"], outcome["confirmatory_opening_authorized"], state["confirmatory_dataset_opened"], state["confirmatory_opening_authorized"], ready["confirmatory_dataset_opened"], ready["confirmatory_opening_authorized"], receipt["confirmatory_dataset_opened"], receipt["confirmatory_opening_authorized"]]),
        "runtime_unauthorized": all(x is False for x in [manifest["runtime_integration_authorized"], fixtures["runtime_integration_authorized"], outcome["runtime_integration_authorized"], state["runtime_integration_authorized"], ready["runtime_integration_authorized"], receipt["runtime_integration_authorized"]]),
        "receipt_pass": receipt["status"] == "PASS" and receipt["fixtures_passed"] == receipt["fixtures_total"] == 13}
    failed = [name for name, ok in checks.items() if not ok]
    print(json.dumps({"status": "PASS" if not failed else "FAIL", "checks": checks,
                      "failed": failed, "hashes": {rel(path): digest(path) for path in OUTPUTS},
                      "next_authorized_stage": ready["next_authorized_stage"]}, ensure_ascii=False, indent=2))
    if failed: raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--run-contract-fixtures", action="store_true")
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight: preflight()
    elif args.run_contract_fixtures: run_contract_fixtures()
    elif args.freeze: freeze()
    else: verify()


if __name__ == "__main__":
    main()
