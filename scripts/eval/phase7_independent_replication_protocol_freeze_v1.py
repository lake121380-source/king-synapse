#!/usr/bin/env python3
"""Offline freeze gate for Phase 7.3.3-D independent replication v1."""
from __future__ import annotations

import argparse, copy, hashlib, json, tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

PROTOCOL = CONFIG / "phase7_3_3_d_independent_replication_protocol_v1.json"
SAMPLING = CONFIG / "phase7_3_3_d_independent_pilot_sampling_policy_v1.json"
REFERENCE = CONFIG / "phase7_3_3_d_independent_reference_policy_v1.json"
DUAL_ARM = CONFIG / "phase7_3_3_d_equal_resource_dual_arm_policy_v1.json"
ANALYSIS = CONFIG / "phase7_3_3_d_independent_replication_analysis_plan_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_independent_replication_protocol_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_independent_replication_protocol_freeze_manifest_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_independent_replication_protocol_freeze_receipt_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_independent_replication_protocol_freeze_outcome_v1.json"
STATE_V13 = DATA / "phase7_3_3_d_support_stage_state_v13.json"
READINESS_V24 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v24.json"

STATE_V12 = DATA / "phase7_3_3_d_support_stage_state_v12.json"
READINESS_V23 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v23.json"
PAIRED_RESULT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_result_v1.json"
PAIRED_RECEIPT = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_result_freeze_receipt_v1.json"
PAIRED_OUTCOME = REPORTS / "phase7_3_3_d_atomic_vs_candidate_paired_result_freeze_outcome_v1.json"

EXPECTED_SHA = {
    STATE_V12: "73d81e7a58409d35f597a261cd3e8cf80c1f911bbb434494cbdc7aaaddf69d95",
    READINESS_V23: "ec52d86a7c605655f871c8be4a622a126137fb8275476b0ea51ae24e6dc48eca",
    PAIRED_RESULT: "2fe04b0cc418381b6937f0b0b417e6c6ef6aba3ff3331e3446291559beda2548",
    PAIRED_RECEIPT: "565189d8d1cbfcdf39e1e9b63b0d30e0f1b031398e9bec38ef2d550476ca11ca",
    PAIRED_OUTCOME: "384f8c9662928ae8882459f9a3788ae816cfaff554b1866beb5838c3d11e5448",
}
FROZEN_STATUS = "independent_replication_protocol_frozen_pilot_not_opened"
NEXT_STAGE = "construct_independent_pilot_sampling_frame_v1"

def rel(path: Path) -> str: return path.relative_to(ROOT).as_posix()
def sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8-sig"))
def raw(value: Any) -> bytes: return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()

def require(ok: bool, message: str) -> None:
    if not ok: raise ValueError(message)

def write_once(path: Path, value: Any) -> str:
    content = raw(value); digest = hashlib.sha256(content).hexdigest()
    if path.exists():
        require(path.read_bytes() == content, f"immutable_artifact_differs:{rel(path)}")
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as stream:
        stream.write(content); temporary = Path(stream.name)
    temporary.replace(path); return digest

def documents() -> dict[str, dict[str, Any]]:
    protocol = {
        "schema_version": 1, "protocol_id": "phase7.3.3-d-independent-replication-protocol-v1",
        "status": "frozen", "study_family": "prospective_independent_replication",
        "current_gate_scope": "protocol_design_only_no_dataset_opening",
        "research_question": "Does Atomic-level measurement improve correctness or diagnostic localization under an independent dataset, independent reference, and equal resources?",
        "stages": ["protocol_freeze", "pilot_sampling_frame_freeze", "pilot_reference_construction", "equal_resource_pilot", "pilot_effect_cost_estimation", "power_and_sample_size_freeze", "confirmatory_dataset_open", "confirmatory_reference", "confirmatory_equal_resource_execution", "result_freeze"],
        "pilot_role": "exploratory_not_confirmatory", "confirmatory_role": "prospective_after_power_freeze",
        "independence": {
            "exclude_ten_design_cases": True, "exclude_candidate_hash_overlap": True,
            "exclude_evidence_hash_overlap": True, "exclude_source_identity_overlap_when_available": True,
            "reference_blind_to_both_arms": True, "arms_blind_to_reference": True,
            "arms_blind_to_each_other": True, "confirmatory_closed_until_power_freeze": True,
        },
        "anti_circularity": {
            "route_a_boundary_gold_for_accuracy": False, "route_a_support_gold_for_accuracy": False,
            "arm_output_may_modify_reference": False, "reference_independent_from_both_arms": True,
        },
        "primary_estimands": ["candidate_level_correctness_difference", "material_error_detection_difference", "diagnostic_localization_difference"],
        "failure_governance": {
            "first_provider_content_authoritative": True, "semantic_retry": False,
            "output_repair": False, "infrastructure_retry_only_before_content": True,
            "change_requires_successor_version": True, "outcome_dependent_replacement": False,
            "failure_is_immutable_outcome": True,
        },
        "pilot_allowed_claims": ["feasibility", "effect_size_estimate", "mixed_support_rate", "failure_rate", "cost_latency", "power_inputs"],
        "pilot_forbidden_claims": ["generalization", "universal_superiority", "confirmatory_accuracy_superiority", "production_readiness"],
        "runtime": {"integration": False, "shadow_mode": False, "memory_write": False, "pattern_promotion": False},
    }
    sampling = {
        "schema_version": 1, "policy_id": "phase7.3.3-d-independent-pilot-sampling-policy-v1", "status": "frozen",
        "target": 40, "minimum": 30, "maximum": 50, "confirmatory_sample": False,
        "unit": "candidate_with_frozen_evidence_bundle",
        "sequence": ["freeze_inventory_ids_hashes", "apply_pre_outcome_eligibility", "freeze_eligible_inventory", "deterministic_select", "freeze_selected_ids_hashes", "open_selected_content"],
        "selection": {"method": "sha256_ranked_stratified", "seed": "phase7.3.3-d-pilot-v1-20260715", "tie_breaker": "candidate_id"},
        "pre_outcome_strata": ["domain", "source_family", "candidate_length_band", "evidence_count_band"],
        "forbidden_outcome_strata": ["support_label", "mixed_support", "arm_correctness", "agreement", "effect_size"],
        "exclusions": {"design_case_ids": [f"extract_{i:02d}" for i in range(1, 11)], "candidate_hash_overlap": "exclude", "evidence_hash_overlap": "exclude", "source_identity_overlap": "exclude_when_available", "calibration_fixture": "exclude"},
        "attrition": {"post_opening_replacement": False, "shortfall_reported": True, "pre_opening_replacement": "next_deterministic_rank"},
        "current_gate": {"inventory_accessed": False, "candidate_content_accessed": False, "evidence_content_accessed": False, "selected_ids_frozen": False},
    }
    reference = {
        "schema_version": 1, "policy_id": "phase7.3.3-d-independent-reference-policy-v1", "status": "frozen",
        "label": "independent_replication_reference_not_route_a_project_gold",
        "reviewers": 2, "adjudicators": 1,
        "blinding": {"no_arm_outputs": True, "no_route_a_boundary_gold": True, "no_route_a_support_gold": True, "no_historical_labels": True, "independent_submissions": True},
        "outputs": ["claim_inventory", "claim_spans", "materiality", "support_labels", "candidate_reference_label", "material_error_spans", "non_claim_accounting"],
        "quality_gates": ["boundary_agreement", "support_agreement", "adjudication", "coverage_accounting", "lineage", "freeze_replay"],
        "gold_fields": ["claim_span", "materiality", "support_label", "candidate_reference_label", "material_error_span"],
        "diagnostic_only": ["reason", "rationale", "confidence", "citation_explanation"],
        "prohibited_sources": ["route_a_boundary_gold", "route_a_support_gold", "candidate_arm", "atomic_arm", "arm_metrics"],
        "freeze_order": "reference_frozen_and_sealed_before_arm_scoring",
        "human_gold_name_only_if_all_decisions_human": True,
    }
    dual_arm = {
        "schema_version": 1, "policy_id": "phase7.3.3-d-equal-resource-dual-arm-policy-v1", "status": "frozen", "paired": True,
        "must_match": ["provider", "model", "temperature", "top_p", "seed_if_supported", "max_output_tokens", "candidate", "evidence", "reviewer_count", "adjudicator_count", "attempt_policy", "failure_policy"],
        "only_difference": {"candidate_arm": "single_candidate_judgment", "atomic_arm": "segment_claims_judge_and_aggregate"},
        "parity": {"request_count": True, "reviewers": True, "adjudicators": True, "max_output_tokens": True, "evidence_visibility": True, "case_isolation": True},
        "report_separately": ["input_tokens", "output_tokens", "latency", "human_minutes"],
        "isolation": {"separate_contexts": True, "no_cross_arm_visibility": True, "no_reference_visibility": True, "counterbalanced_order": True},
        "failure": {"transport_separate": True, "schema_separate": True, "semantic_NA_after_prerequisite_failure": True, "first_content_authoritative": True, "semantic_retry": False, "repair": False},
    }
    analysis = {
        "schema_version": 1, "analysis_plan_id": "phase7.3.3-d-independent-replication-analysis-plan-v1", "status": "frozen",
        "pilot": {"confirmatory_p_values": False, "effect_uncertainty": True, "all_cases": True, "failure_rates": True, "mixed_support": True, "cost": True, "generalization": False},
        "primary_endpoints": ["candidate_level_exact_correctness", "material_error_detection", "diagnostic_localization_precision_recall_f1"],
        "secondary_endpoints": ["ordinal_distance", "unsupported_masking", "partial_localization", "failure_rates", "agreement", "cost"],
        "power_sequence": ["freeze_pilot", "estimate_paired_effect_missingness", "freeze_power_method", "freeze_sample_size", "open_confirmatory_dataset"],
        "power_defaults": {"alpha": 0.05, "power": 0.8, "minimum_confirmatory_candidates": 100, "multiplicity": "Holm_unless_successor_frozen"},
        "missingness": {"all_selected_cases": True, "failures_not_dropped": True, "complete_case_not_primary": True, "semantic_NA_after_prerequisite_failure": True},
        "reporting": {"denominators": True, "confidence_intervals": True, "domain_and_claim_type_strata": True, "pilot_confirmatory_not_pooled": True, "cost_quality_tradeoff": True},
        "current_authorization": {"pilot_metrics": False, "power_analysis": False, "confirmatory_opening": False, "confirmatory_inference": False},
    }
    return {"protocol": protocol, "sampling": sampling, "reference": reference, "dual_arm": dual_arm, "analysis": analysis}

def validate_bundle(b: dict[str, Any]) -> None:
    p, s, r, d, a = (b[k] for k in ("protocol", "sampling", "reference", "dual_arm", "analysis"))
    require(p["status"] == "frozen" and p["current_gate_scope"] == "protocol_design_only_no_dataset_opening", "protocol_scope_invalid")
    for key in ("exclude_ten_design_cases", "exclude_candidate_hash_overlap", "exclude_evidence_hash_overlap", "reference_blind_to_both_arms", "arms_blind_to_reference", "arms_blind_to_each_other", "confirmatory_closed_until_power_freeze"):
        require(p["independence"].get(key) is True, f"independence_missing:{key}")
    require(p["anti_circularity"].get("route_a_boundary_gold_for_accuracy") is False, "boundary_gold_circularity")
    require(p["anti_circularity"].get("route_a_support_gold_for_accuracy") is False, "support_gold_circularity")
    require(p["anti_circularity"].get("reference_independent_from_both_arms") is True, "reference_not_independent")
    g = p["failure_governance"]
    require(g["first_provider_content_authoritative"] and not g["semantic_retry"] and not g["output_repair"], "failure_governance_invalid")
    require(g["change_requires_successor_version"] and not g["outcome_dependent_replacement"], "version_or_replacement_invalid")
    require(not any(p["runtime"].values()), "runtime_authorized")

    require(isinstance(s["target"], int) and s["minimum"] <= s["target"] <= s["maximum"] and 30 <= s["target"] <= 50, "pilot_target_invalid")
    require(s["confirmatory_sample"] is False, "pilot_mislabeled_confirmatory")
    require(s["selection"]["method"] == "sha256_ranked_stratified", "sampling_not_deterministic")
    require({"support_label", "arm_correctness", "effect_size"} <= set(s["forbidden_outcome_strata"]), "outcome_strata_allowed")
    require(s["attrition"]["post_opening_replacement"] is False, "post_opening_replacement_allowed")
    require(not any(s["current_gate"].values()), "dataset_accessed_during_freeze")
    require(set(s["exclusions"]["design_case_ids"]) == {f"extract_{i:02d}" for i in range(1, 11)}, "design_case_exclusion_incomplete")

    require(r["reviewers"] >= 2 and r["adjudicators"] >= 1, "reference_staffing_invalid")
    for key in ("no_arm_outputs", "no_route_a_boundary_gold", "no_route_a_support_gold", "no_historical_labels", "independent_submissions"):
        require(r["blinding"].get(key) is True, f"reference_blinding_missing:{key}")
    require(r["freeze_order"] == "reference_frozen_and_sealed_before_arm_scoring", "reference_freeze_order_invalid")
    require({"route_a_boundary_gold", "route_a_support_gold", "candidate_arm", "atomic_arm"} <= set(r["prohibited_sources"]), "reference_prohibited_sources_incomplete")

    require(d["paired"] is True, "dual_arm_not_paired")
    for key in ("provider", "model", "temperature", "candidate", "evidence", "reviewer_count", "adjudicator_count"):
        require(key in d["must_match"], f"arm_parity_missing:{key}")
    require(all(d["parity"].values()), "resource_parity_false")
    require(d["isolation"]["no_cross_arm_visibility"] and d["isolation"]["no_reference_visibility"], "arm_leakage")
    require(d["failure"]["first_content_authoritative"] and not d["failure"]["semantic_retry"] and not d["failure"]["repair"], "arm_failure_policy_invalid")

    require(a["pilot"]["confirmatory_p_values"] is False and a["pilot"]["generalization"] is False, "pilot_claim_scope_invalid")
    require(a["power_sequence"][-1] == "open_confirmatory_dataset", "confirmatory_opening_order_invalid")
    require(not any(a["current_authorization"].values()), "future_stage_prematurely_authorized")
    require(a["reporting"]["pilot_confirmatory_not_pooled"] is True, "pilot_confirmatory_pooling_allowed")

def setv(b: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = b
    for key in path[:-1]: node = node[key]
    node[path[-1]] = value

def remove(b: dict[str, Any], path: tuple[str, ...], value: str) -> None:
    node = b
    for key in path: node = node[key]
    node.remove(value)

Mutation = Callable[[dict[str, Any]], None]
def fixture_defs() -> list[tuple[str, Mutation | None, str | None]]:
    return [
        ("valid_bundle", None, None),
        ("design_overlap", lambda b: b["sampling"]["exclusions"]["design_case_ids"].remove("extract_10"), "design_case_exclusion_incomplete"),
        ("candidate_hash_overlap", lambda b: setv(b, ("protocol", "independence", "exclude_candidate_hash_overlap"), False), "independence_missing:exclude_candidate_hash_overlap"),
        ("evidence_hash_overlap", lambda b: setv(b, ("protocol", "independence", "exclude_evidence_hash_overlap"), False), "independence_missing:exclude_evidence_hash_overlap"),
        ("reference_sees_arm", lambda b: setv(b, ("reference", "blinding", "no_arm_outputs"), False), "reference_blinding_missing:no_arm_outputs"),
        ("reference_sees_boundary_gold", lambda b: setv(b, ("reference", "blinding", "no_route_a_boundary_gold"), False), "reference_blinding_missing:no_route_a_boundary_gold"),
        ("reference_sees_support_gold", lambda b: setv(b, ("reference", "blinding", "no_route_a_support_gold"), False), "reference_blinding_missing:no_route_a_support_gold"),
        ("support_gold_scores_accuracy", lambda b: setv(b, ("protocol", "anti_circularity", "route_a_support_gold_for_accuracy"), True), "support_gold_circularity"),
        ("single_reference_reviewer", lambda b: setv(b, ("reference", "reviewers"), 1), "reference_staffing_invalid"),
        ("no_adjudicator", lambda b: setv(b, ("reference", "adjudicators"), 0), "reference_staffing_invalid"),
        ("manual_sampling", lambda b: setv(b, ("sampling", "selection", "method"), "manual"), "sampling_not_deterministic"),
        ("outcome_sampling", lambda b: remove(b, ("sampling", "forbidden_outcome_strata"), "support_label"), "outcome_strata_allowed"),
        ("post_open_replacement", lambda b: setv(b, ("sampling", "attrition", "post_opening_replacement"), True), "post_opening_replacement_allowed"),
        ("dataset_opened", lambda b: setv(b, ("sampling", "current_gate", "candidate_content_accessed"), True), "dataset_accessed_during_freeze"),
        ("pilot_too_small", lambda b: setv(b, ("sampling", "target"), 20), "pilot_target_invalid"),
        ("pilot_confirmatory", lambda b: setv(b, ("sampling", "confirmatory_sample"), True), "pilot_mislabeled_confirmatory"),
        ("provider_not_equal", lambda b: remove(b, ("dual_arm", "must_match"), "provider"), "arm_parity_missing:provider"),
        ("evidence_not_equal", lambda b: remove(b, ("dual_arm", "must_match"), "evidence"), "arm_parity_missing:evidence"),
        ("reviewer_resources_not_equal", lambda b: setv(b, ("dual_arm", "parity", "reviewers"), False), "resource_parity_false"),
        ("cross_arm_visibility", lambda b: setv(b, ("dual_arm", "isolation", "no_cross_arm_visibility"), False), "arm_leakage"),
        ("gold_visibility", lambda b: setv(b, ("dual_arm", "isolation", "no_reference_visibility"), False), "arm_leakage"),
        ("semantic_retry", lambda b: setv(b, ("dual_arm", "failure", "semantic_retry"), True), "arm_failure_policy_invalid"),
        ("output_repair", lambda b: setv(b, ("protocol", "failure_governance", "output_repair"), True), "failure_governance_invalid"),
        ("pilot_p_values", lambda b: setv(b, ("analysis", "pilot", "confirmatory_p_values"), True), "pilot_claim_scope_invalid"),
        ("confirmatory_open_early", lambda b: setv(b, ("analysis", "power_sequence"), ["open_confirmatory_dataset", "power"]), "confirmatory_opening_order_invalid"),
        ("confirmatory_authorized", lambda b: setv(b, ("analysis", "current_authorization", "confirmatory_opening"), True), "future_stage_prematurely_authorized"),
        ("runtime_authorized", lambda b: setv(b, ("protocol", "runtime", "integration"), True), "runtime_authorized"),
        ("pilot_confirmatory_pooling", lambda b: setv(b, ("analysis", "reporting", "pilot_confirmatory_not_pooled"), False), "pilot_confirmatory_pooling_allowed"),
    ]

def run_fixtures() -> dict[str, Any]:
    results = []
    for fixture_id, mutation, expected in fixture_defs():
        candidate = copy.deepcopy(documents())
        if mutation: mutation(candidate)
        observed = None
        try: validate_bundle(candidate)
        except ValueError as exc: observed = str(exc)
        results.append({"fixture_id": fixture_id, "expected": expected or "PASS", "observed": observed or "PASS", "passed": observed == expected})
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-independent-replication-contract-fixtures-v1", "status": "all_passed" if all(x["passed"] for x in results) else "failed", "fixture_count": len(results), "passed_count": sum(x["passed"] for x in results), "failed_count": sum(not x["passed"] for x in results), "results": results}

def verify_inputs() -> dict[str, Any]:
    for path, expected in EXPECTED_SHA.items():
        require(path.exists(), f"missing_input:{rel(path)}")
        require(sha256(path) == expected, f"input_sha_mismatch:{rel(path)}")
    state, readiness = load(STATE_V12), load(READINESS_V23)
    require(state["next_authorized_stage"] == "design_independent_replication_protocol_v1", "state_not_authorized")
    require(readiness["next_authorized_stage"] == "design_independent_replication_protocol_v1", "readiness_not_authorized")
    require(state["paired_evaluation_result_frozen"] is True, "paired_result_not_frozen")
    require(readiness["independent_replication_started"] is False, "replication_already_started")
    require(not state["held_out_accessed"] and not readiness["held_out_accessed"], "held_out_already_accessed")
    require(not state["runtime_integration_authorized"], "runtime_already_authorized")
    return {"status": "authoritative_inputs_verified", "input_count": len(EXPECTED_SHA), "provider_called": False, "held_out_accessed": False}

def freeze() -> dict[str, Any]:
    verify_inputs(); docs = documents(); validate_bundle(docs)
    hashes = {
        "protocol": write_once(PROTOCOL, docs["protocol"]),
        "sampling": write_once(SAMPLING, docs["sampling"]),
        "reference": write_once(REFERENCE, docs["reference"]),
        "dual_arm": write_once(DUAL_ARM, docs["dual_arm"]),
        "analysis": write_once(ANALYSIS, docs["analysis"]),
    }
    fixtures = run_fixtures(); require(fixtures["failed_count"] == 0, "fixtures_failed")
    hashes["fixtures"] = write_once(FIXTURES, fixtures)
    artifact_paths = {"protocol": PROTOCOL, "sampling": SAMPLING, "reference": REFERENCE, "dual_arm": DUAL_ARM, "analysis": ANALYSIS, "fixtures": FIXTURES}
    manifest = {
        "schema_version": 1, "manifest_id": "phase7.3.3-d-independent-replication-protocol-freeze-manifest-v1",
        "status": "frozen_before_independent_dataset_opening", "frozen_date": "2026-07-15",
        "adapter": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "inputs": [{"path": rel(p), "sha256": h} for p, h in EXPECTED_SHA.items()],
        "protocol_artifacts": [{"path": rel(artifact_paths[k]), "sha256": hashes[k]} for k in artifact_paths],
        "environment": {"offline_gate": True, "provider_called": False, "held_out_accessed": False, "pilot_dataset_opened": False, "confirmatory_dataset_opened": False},
        "immutability": {"write_once": True, "semantic_retry": False, "repair": False, "successor_version_for_change": True},
        "expected_successors": [rel(RECEIPT), rel(OUTCOME), rel(STATE_V13), rel(READINESS_V24)],
    }
    manifest_sha = write_once(MANIFEST, manifest)
    receipt = {
        "schema_version": 1, "receipt_id": "phase7.3.3-d-independent-replication-protocol-freeze-receipt-v1", "status": FROZEN_STATUS,
        "manifest_sha256": manifest_sha, "protocol_sha256": hashes["protocol"], "sampling_policy_sha256": hashes["sampling"],
        "reference_policy_sha256": hashes["reference"], "dual_arm_policy_sha256": hashes["dual_arm"], "analysis_plan_sha256": hashes["analysis"],
        "fixtures_sha256": hashes["fixtures"], "fixture_count": fixtures["fixture_count"], "fixture_passed_count": fixtures["passed_count"],
        "provider_called": False, "held_out_accessed": False, "pilot_dataset_opened": False, "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False, "next_authorized_stage": NEXT_STAGE,
    }
    receipt_sha = write_once(RECEIPT, receipt)
    outcome = {
        "schema_version": 1, "outcome_id": "phase7.3.3-d-independent-replication-protocol-freeze-outcome-v1", "status": FROZEN_STATUS,
        "receipt_sha256": receipt_sha, "gate_passed": True, "protocol_bundle_frozen": True,
        "pilot_sampling_frame_frozen": False, "pilot_execution_started": False, "independent_reference_started": False,
        "confirmatory_dataset_opened": False, "provider_called": False, "held_out_accessed": False,
        "runtime_integration_authorized": False, "next_authorized_stage": NEXT_STAGE,
    }
    outcome_sha = write_once(OUTCOME, outcome)
    old_state = load(STATE_V12); state = copy.deepcopy(old_state)
    state.update({
        "schema_version": 13, "state_id": "phase7.3.3-d-support-stage-state-v13",
        "independent_replication_protocol_frozen": True, "independent_replication_state": FROZEN_STATUS,
        "independent_replication_started": False, "independent_pilot_sampling_frame_frozen": False,
        "independent_pilot_dataset_opened": False, "independent_reference_started": False,
        "independent_dual_arm_execution_started": False, "confirmatory_dataset_opened": False,
        "next_authorized_stage": NEXT_STAGE, "runtime_integration_authorized": False,
        "provider_called_for_independent_replication": False, "held_out_accessed": False,
    })
    state["artifact_lineage"] = dict(old_state["artifact_lineage"])
    state["artifact_lineage"].update({
        "support_stage_state_v12_sha256": EXPECTED_SHA[STATE_V12], "readiness_v23_sha256": EXPECTED_SHA[READINESS_V23],
        "independent_replication_protocol_sha256": hashes["protocol"], "independent_pilot_sampling_policy_sha256": hashes["sampling"],
        "independent_reference_policy_sha256": hashes["reference"], "equal_resource_dual_arm_policy_sha256": hashes["dual_arm"],
        "independent_replication_analysis_plan_sha256": hashes["analysis"], "independent_replication_contract_fixtures_sha256": hashes["fixtures"],
        "independent_replication_protocol_freeze_manifest_sha256": manifest_sha, "independent_replication_protocol_freeze_receipt_sha256": receipt_sha,
        "independent_replication_protocol_freeze_outcome_sha256": outcome_sha,
    })
    state_sha = write_once(STATE_V13, state)
    old_ready = load(READINESS_V23); readiness = copy.deepcopy(old_ready)
    readiness.update({
        "schema_version": 24, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v24", "status": FROZEN_STATUS,
        "next_authorized_stage": NEXT_STAGE, "independent_replication_protocol_frozen": True, "independent_replication_state": FROZEN_STATUS,
        "independent_replication_started": False, "independent_pilot_sampling_frame_frozen": False,
        "independent_pilot_dataset_opened": False, "independent_reference_started": False,
        "independent_dual_arm_execution_started": False, "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False, "provider_called_for_independent_replication": False, "held_out_accessed": False,
    })
    readiness["artifact_lineage"] = dict(old_ready["artifact_lineage"])
    readiness["artifact_lineage"].update({"readiness_v23_sha256": EXPECTED_SHA[READINESS_V23], "support_stage_state_v13_sha256": state_sha, "independent_replication_protocol_freeze_outcome_sha256": outcome_sha})
    readiness_sha = write_once(READINESS_V24, readiness)
    return {
        "status": FROZEN_STATUS, **{f"{k}_sha256": v for k, v in hashes.items()},
        "manifest_sha256": manifest_sha, "receipt_sha256": receipt_sha, "outcome_sha256": outcome_sha,
        "state_v13_sha256": state_sha, "readiness_v24_sha256": readiness_sha,
        "fixture_count": fixtures["fixture_count"], "fixture_passed_count": fixtures["passed_count"],
        "provider_called": False, "held_out_accessed": False, "runtime_integration_authorized": False, "next_authorized_stage": NEXT_STAGE,
    }

def verify_outputs() -> dict[str, Any]:
    summary = freeze(); docs = documents()
    expected = {PROTOCOL: docs["protocol"], SAMPLING: docs["sampling"], REFERENCE: docs["reference"], DUAL_ARM: docs["dual_arm"], ANALYSIS: docs["analysis"], FIXTURES: run_fixtures()}
    for path, value in expected.items(): require(path.read_bytes() == raw(value), f"content_mismatch:{rel(path)}")
    manifest = load(MANIFEST)
    require(manifest["adapter"]["sha256"] == sha256(Path(__file__).resolve()), "adapter_sha_mismatch")
    for item in manifest["inputs"] + manifest["protocol_artifacts"]:
        path = ROOT / item["path"]; require(path.exists() and sha256(path) == item["sha256"], f"lineage_mismatch:{item['path']}")
    fixtures = load(FIXTURES); require(fixtures["failed_count"] == 0 and fixtures["passed_count"] == fixtures["fixture_count"], "fixtures_not_all_passed")
    state, readiness = load(STATE_V13), load(READINESS_V24)
    for item in (state, readiness):
        require(item["next_authorized_stage"] == NEXT_STAGE, "next_stage_mismatch")
        require(item["independent_replication_protocol_frozen"] is True, "protocol_not_frozen_in_state")
        require(item["independent_pilot_dataset_opened"] is False and item["confirmatory_dataset_opened"] is False, "dataset_opened_in_state")
        require(item["held_out_accessed"] is False and item["runtime_integration_authorized"] is False, "guard_failure")
    summary["status"] = "verified_" + FROZEN_STATUS; summary["json_artifact_count"] = 11
    return summary

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-inputs", action="store_true"); parser.add_argument("--run-contract-fixtures", action="store_true")
    parser.add_argument("--freeze", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(); require(sum((args.verify_inputs, args.run_contract_fixtures, args.freeze, args.verify)) == 1, "select_one_action")
    if args.verify_inputs: result = verify_inputs()
    elif args.run_contract_fixtures:
        verify_inputs(); result = run_fixtures(); require(result["failed_count"] == 0, "fixtures_failed")
    elif args.freeze: result = freeze()
    else: result = verify_outputs()
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
