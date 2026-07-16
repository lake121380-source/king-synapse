#!/usr/bin/env python3
"""Freeze and execute the final audit of the Phase 7.3.3-D Independent Pilot chain."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

SAMPLING_RECEIPT = R / "phase7_3_3_d_independent_pilot_sampling_freeze_receipt_v1.json"
SELECTED_DATASET = D / "phase7_3_3_d_independent_pilot_selected_dataset_v1.json"
FRAME_AUDIT = R / "phase7_3_3_d_independent_pilot_single_proposition_frame_audit_v1.json"
REFERENCE = D / "phase7_3_3_d_independent_pilot_reference_v1.json"
REFERENCE_SEAL = R / "phase7_3_3_d_independent_pilot_reference_seal_v1.json"
REFERENCE_QA = R / "phase7_3_3_d_independent_pilot_reference_qa_v1.json"
REFERENCE_REPLAY = R / "phase7_3_3_d_independent_pilot_reference_replay_v1.json"
REFERENCE_OUTCOME = R / "phase7_3_3_d_independent_pilot_reference_freeze_outcome_v1.json"
REVIEWER_A_NEGATIVE = R / "phase7_3_3_d_independent_pilot_reference_reviewer_a_negative_result_v1.json"
REVIEWER_B_NEGATIVE = R / "phase7_3_3_d_independent_pilot_reference_reviewer_b_negative_result_v2.json"
AGREEMENT_NEGATIVE = R / "phase7_3_3_d_independent_pilot_reference_agreement_negative_result_v1.json"
AGREEMENT_REPORT = R / "phase7_3_3_d_independent_pilot_reference_agreement_report_v2.json"
ADJUDICATION_RESULT = R / "phase7_3_3_d_independent_pilot_reference_adjudication_execution_result_v1.json"
DUAL_NEGATIVES = [R / f"phase7_3_3_d_independent_pilot_dual_arm_negative_result_v{version}.json" for version in (1, 2, 3)]
DUAL_MANIFEST_V4 = R / "phase7_3_3_d_independent_pilot_dual_arm_execution_manifest_v4.json"
DUAL_RESULT_V4 = R / "phase7_3_3_d_independent_pilot_dual_arm_execution_result_v4.json"
CANDIDATE_SUBMISSION = D / "phase7_3_3_d_independent_pilot_candidate_arm_submission_v4.json"
ATOMIC_SUBMISSION = D / "phase7_3_3_d_independent_pilot_atomic_arm_submission_v4.json"
ANALYSIS_V1_NEGATIVE = R / "phase7_3_3_d_independent_pilot_analysis_negative_result_v1.json"
ANALYSIS_V1_REPORT = R / "phase7_3_3_d_independent_pilot_analysis_report_v1.json"
POWER_V1_REPORT = R / "phase7_3_3_d_independent_pilot_power_gate_report_v1.json"
POWER_V1_SAMPLE = R / "phase7_3_3_d_independent_pilot_sample_size_freeze_v1.json"
ANALYSIS_V2_PROTOCOL = C / "phase7_3_3_d_independent_pilot_analysis_protocol_v2.json"
ANALYSIS_V2_FREEZE = R / "phase7_3_3_d_independent_pilot_analysis_freeze_manifest_v2.json"
ANALYSIS_V2_MANIFEST = R / "phase7_3_3_d_independent_pilot_analysis_execution_manifest_v2.json"
ANALYSIS_V2_PAIRED = D / "phase7_3_3_d_independent_pilot_paired_analysis_cases_v2.json"
ANALYSIS_V2_REPORT = R / "phase7_3_3_d_independent_pilot_analysis_report_v2.json"
ANALYSIS_V2_RECEIPT = R / "phase7_3_3_d_independent_pilot_analysis_freeze_receipt_v2.json"
POWER_V2_METHOD = C / "phase7_3_3_d_independent_pilot_power_method_v2.json"
POWER_V2_MANIFEST = R / "phase7_3_3_d_independent_pilot_power_gate_manifest_v2.json"
POWER_V2_REPORT = R / "phase7_3_3_d_independent_pilot_power_gate_report_v2.json"
POWER_V2_SAMPLE = R / "phase7_3_3_d_independent_pilot_sample_size_freeze_v2.json"
POWER_V2_RECEIPT = R / "phase7_3_3_d_independent_pilot_power_gate_receipt_v2.json"
STATE_PREV = D / "phase7_3_3_d_support_stage_state_v23.json"
READY_PREV = R / "phase7_3_3_d1_reference_construction_readiness_v34.json"
MANIFEST = R / "phase7_3_3_d_independent_pilot_final_audit_manifest_v1.json"
REPORT = R / "phase7_3_3_d_independent_pilot_final_audit_report_v1.json"
STATE = D / "phase7_3_3_d_support_stage_state_v24.json"
READY = R / "phase7_3_3_d1_reference_construction_readiness_v35.json"
RECEIPT = R / "phase7_3_3_d_independent_pilot_final_audit_receipt_v1.json"
OUTPUTS = [MANIFEST, REPORT, STATE, READY, RECEIPT]
REQUIRED = [SAMPLING_RECEIPT, SELECTED_DATASET, FRAME_AUDIT, REFERENCE, REFERENCE_SEAL, REFERENCE_QA,
    REFERENCE_REPLAY, REFERENCE_OUTCOME, REVIEWER_A_NEGATIVE, REVIEWER_B_NEGATIVE, AGREEMENT_NEGATIVE,
    AGREEMENT_REPORT, ADJUDICATION_RESULT, *DUAL_NEGATIVES, DUAL_MANIFEST_V4, DUAL_RESULT_V4,
    CANDIDATE_SUBMISSION, ATOMIC_SUBMISSION, ANALYSIS_V1_NEGATIVE, ANALYSIS_V1_REPORT, POWER_V1_REPORT,
    POWER_V1_SAMPLE, ANALYSIS_V2_PROTOCOL, ANALYSIS_V2_FREEZE, ANALYSIS_V2_MANIFEST, ANALYSIS_V2_PAIRED,
    ANALYSIS_V2_REPORT, ANALYSIS_V2_RECEIPT, POWER_V2_METHOD, POWER_V2_MANIFEST, POWER_V2_REPORT,
    POWER_V2_SAMPLE, POWER_V2_RECEIPT, STATE_PREV, READY_PREV]


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_once(path: Path, value) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable_artifact_conflict:{rel(path)}")
        return digest_bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)
    return digest_bytes(data)


def scoped_json_paths() -> list[Path]:
    paths = []
    for base in [C, D, R]:
        for path in base.glob("*.json"):
            name = path.name
            if ("independent_pilot" in name or name.startswith("phase7_3_3_d_support_stage_state_v")
                    or name.startswith("phase7_3_3_d1_reference_construction_readiness_v")) and path not in OUTPUTS:
                paths.append(path)
    return sorted(set(paths), key=rel)


def preflight_checks():
    missing = [rel(path) for path in REQUIRED if not path.exists()]
    return {
        "required_inputs_present": not missing,
        "missing": missing,
        "outputs_absent": not any(path.exists() for path in OUTPUTS),
        "state_authorizes_final_audit": load(STATE_PREV).get("next_authorized_stage") == "final_audit_independent_pilot_chain_v1" if not missing else False,
        "readiness_authorizes_final_audit": load(READY_PREV).get("next_authorized_stage") == "final_audit_independent_pilot_chain_v1" if not missing else False,
        "confirmatory_closed_at_entry": load(STATE_PREV).get("confirmatory_dataset_opened") is False and load(READY_PREV).get("confirmatory_dataset_opened") is False if not missing else False,
        "runtime_unauthorized_at_entry": load(STATE_PREV).get("runtime_integration_authorized") is False and load(READY_PREV).get("runtime_integration_authorized") is False if not missing else False,
    }


def preflight():
    checks = preflight_checks()
    ok = all(value for key, value in checks.items() if key != "missing")
    print(json.dumps({"status": "PASS" if ok else "FAIL", "checks": checks}, indent=2))
    if not ok:
        raise SystemExit(1)


def freeze_manifest():
    checks = preflight_checks()
    if not all(value for key, value in checks.items() if key != "missing"):
        raise ValueError("final_audit_preflight_failed")
    scope = scoped_json_paths()
    manifest = {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-independent-pilot-final-audit-manifest-v1",
        "status": "frozen_before_final_audit_decision",
        "adapter_sha256": digest(Path(__file__)),
        "scoped_artifact_sha256": {rel(path): digest(path) for path in scope},
        "scoped_json_file_count": len(scope),
        "required_load_bearing_artifacts": [rel(path) for path in REQUIRED],
        "audit_started": False,
        "confirmatory_content_opened": False,
        "runtime_integration_authorized": False,
    }
    manifest_hash = write_once(MANIFEST, manifest)
    print(json.dumps({"status": "final_audit_manifest_frozen", "manifest_sha256": manifest_hash,
        "scoped_json_file_count": len(scope), "audit_started": False}, indent=2))


def manifest_checks():
    if not MANIFEST.exists():
        return {"manifest_present": False}
    manifest = load(MANIFEST)
    expected = manifest["scoped_artifact_sha256"]
    return {
        "manifest_present": True,
        "adapter_unchanged": manifest["adapter_sha256"] == digest(Path(__file__)),
        "scoped_files_unchanged": all((ROOT / path).exists() and digest(ROOT / path) == sha for path, sha in expected.items()),
        "required_covered": all(rel(path) in expected for path in REQUIRED),
        "audit_not_started_at_freeze": manifest["audit_started"] is False,
        "confirmatory_closed_at_freeze": manifest["confirmatory_content_opened"] is False,
        "runtime_unauthorized_at_freeze": manifest["runtime_integration_authorized"] is False,
    }


def recursive_policy_scan(paths: list[Path]):
    confirmatory_true, runtime_true, nonnull_usd_cost = [], [], []
    def walk(value, path, artifact):
        if isinstance(value, dict):
            for key, child in value.items():
                field = f"{path}.{key}" if path else key
                if key in {"confirmatory_content_opened", "confirmatory_dataset_opened"} and child is True:
                    confirmatory_true.append({"artifact": artifact, "field": field})
                if key == "runtime_integration_authorized" and child is True:
                    runtime_true.append({"artifact": artifact, "field": field})
                if key in {"cost_usd", "usd_cost"} and child is not None:
                    nonnull_usd_cost.append({"artifact": artifact, "field": field, "value": child})
                walk(child, field, artifact)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]", artifact)
    for artifact_path in paths:
        walk(load(artifact_path), "", rel(artifact_path))
    return {"parsed_json_file_count": len(paths), "confirmatory_true_occurrences": confirmatory_true,
        "runtime_authorized_true_occurrences": runtime_true, "nonnull_usd_cost_occurrences": nonnull_usd_cost}


def execute_audit():
    frozen = manifest_checks()
    if not all(frozen.values()):
        raise ValueError(f"final_audit_manifest_invalid:{frozen}")
    if any(path.exists() for path in [REPORT, STATE, READY, RECEIPT]):
        raise ValueError("final_audit_terminal_artifact_exists")
    sampling, selected, frame = load(SAMPLING_RECEIPT), load(SELECTED_DATASET), load(FRAME_AUDIT)
    reference, seal, qa, replay = load(REFERENCE), load(REFERENCE_SEAL), load(REFERENCE_QA), load(REFERENCE_REPLAY)
    reference_outcome = load(REFERENCE_OUTCOME)
    reviewer_a_negative, reviewer_b_negative = load(REVIEWER_A_NEGATIVE), load(REVIEWER_B_NEGATIVE)
    agreement_negative, agreement, adjudication = load(AGREEMENT_NEGATIVE), load(AGREEMENT_REPORT), load(ADJUDICATION_RESULT)
    dual_negatives = [load(path) for path in DUAL_NEGATIVES]
    dual_manifest, dual_result = load(DUAL_MANIFEST_V4), load(DUAL_RESULT_V4)
    candidate, atomic = load(CANDIDATE_SUBMISSION), load(ATOMIC_SUBMISSION)
    analysis_negative = load(ANALYSIS_V1_NEGATIVE)
    analysis_v2_protocol, analysis_v2_manifest = load(ANALYSIS_V2_PROTOCOL), load(ANALYSIS_V2_MANIFEST)
    paired_v2, analysis_v2, analysis_v2_receipt = load(ANALYSIS_V2_PAIRED), load(ANALYSIS_V2_REPORT), load(ANALYSIS_V2_RECEIPT)
    power_v2, sample_v2, power_receipt_v2 = load(POWER_V2_REPORT), load(POWER_V2_SAMPLE), load(POWER_V2_RECEIPT)
    state_prev, ready_prev = load(STATE_PREV), load(READY_PREV)

    sampling_checks = {
        "receipt_pass": sampling["status"] == "PASS",
        "selected_40_of_80": sampling["selected_count"] == 40 and sampling["eligible_count"] == 80 and selected["case_count"] == 40,
        "fixtures_8_of_8": sampling["fixtures_passed"] == 8 and sampling["fixtures_total"] == 8,
        "confirmatory_closed": sampling["confirmatory_dataset_opened"] is False and selected["confirmatory_content_opened"] is False,
        "frame_structure_frozen": frame["case_count"] == 40 and frame["unique_candidate_text_count"] == 10 and frame["duplicate_candidate_count"] == 30,
    }
    reference_checks = {
        "seal_hash_matches": seal["reference_sha256"] == digest(REFERENCE),
        "reference_40_cases_40_claims": reference["case_count"] == 40 and reference["claim_count"] == 40,
        "reference_label_counts": reference["label_counts"] == {"supported": 38, "unsupported": 2},
        "qa_pass": qa["status"] == "PASS" and qa["passed_case_count"] == 40 and qa["unaccounted_eligible_character_count"] == 0 and qa["overlap_character_count"] == 0,
        "replay_pass": replay["status"] == "PASS" and replay["semantic_object_equal"] is True and replay["case_count_40"] is True,
        "freeze_outcome": reference_outcome["status"] == "independent_pilot_reference_frozen_and_sealed" and reference_outcome["adjudicated_cases"] == 8,
        "historical_reference_negatives_retained": reviewer_a_negative["status"] == "authoritative_negative_result" and reviewer_a_negative["same_version_retry_allowed"] is False and reviewer_b_negative["status"] == "authoritative_negative_result" and reviewer_b_negative["same_version_retry_allowed"] is False and agreement_negative["status"] == "authoritative_negative_result",
        "agreement_and_adjudication_complete": agreement["status"] == "completed" and agreement["case_count"] == 40 and agreement["adjudication"]["support_label_disagreement_count"] == 8 and adjudication["status"] == "completed",
    }
    dual_checks = {f"v{index}_immutable_excluded": item["status"] == "authoritative_negative_result" and item["same_version_retry_allowed"] is False and item["pilot_scoring_allowed"] is False and item["reference_content_loaded"] is False for index, item in enumerate(dual_negatives, 1)}
    candidate_case_ids = [item["case_id"] for item in candidate["cases"]]
    atomic_case_ids = [item["case_id"] for item in atomic["cases"]]
    dual_checks.update({
        "v4_manifest_reference_blind": dual_manifest["reference_content_loaded"] is False and dual_manifest["reference_labels_loaded"] is False,
        "v4_completed_80_requests": dual_result["case_count"] == 40 and dual_result["request_count"] == 80 and dual_result["candidate_request_count"] == 40 and dual_result["atomic_request_count"] == 40,
        "v4_counterbalanced_20_20": dual_result["counterbalance_first_arm_counts"] == {"candidate": 20, "atomic": 20},
        "v4_submissions_complete": candidate["case_count"] == 40 and candidate["request_count"] == 40 and atomic["case_count"] == 40 and atomic["request_count"] == 40,
        "v4_no_missing_or_duplicate_cases": len(set(candidate_case_ids)) == 40 and len(set(atomic_case_ids)) == 40 and set(candidate_case_ids) == set(atomic_case_ids),
        "v4_submission_hashes": dual_result["candidate_submission_sha256"] == digest(CANDIDATE_SUBMISSION) and dual_result["atomic_submission_sha256"] == digest(ATOMIC_SUBMISSION),
        "v4_reference_invisible": dual_result["reference_content_loaded"] is False and dual_result["reference_labels_loaded"] is False and candidate["reference_visible"] is False and atomic["reference_visible"] is False,
        "v4_resource_equality": dual_result["resource_equality_verified"] is True,
        "v4_single_claim_frame_observed": dual_result["single_proposition_frame"] is True and atomic["claim_count"] == 40 and atomic["segmentation_operation_counts"] == {"whole_candidate_claim": 40},
    })
    analysis_checks = {
        "analysis_v1_authoritative_negative": analysis_negative["status"] == "authoritative_implementation_negative_result" and analysis_negative["analysis_v1_scientific_conclusion_authorized"] is False and analysis_negative["analysis_v1_outputs_eligible_for_final_pilot_conclusion"] is False,
        "power_v1_excluded": analysis_negative["power_gate_v1_inherited_lineage_eligible_for_final_conclusion"] is False and state_prev["power_gate_v1_outputs_eligible_for_final_conclusion"] is False,
        "analysis_v2_successor_contract": analysis_v2_protocol["predecessor_analysis_v1_outputs_used"] is False and analysis_v2_protocol["predecessor_power_gate_v1_outputs_used"] is False,
        "analysis_v2_manifest_before_reference_parse": analysis_v2_manifest["status"] == "frozen_before_reference_json_content_parsing_and_scoring" and analysis_v2_manifest["reference_prefreeze_json_content_parsed"] is False and analysis_v2_manifest["reference_prefreeze_labels_or_claims_inspected"] is False,
        "analysis_v2_40_paired_no_drop": paired_v2["case_count"] == 40 and len(paired_v2["cases"]) == 40 and analysis_v2["missingness_and_failures"]["paired_cases_dropped"] == 0,
        "analysis_v2_authoritative_hash_lineage": analysis_v2_receipt["artifact_sha256"]["analysis_report"] == digest(ANALYSIS_V2_REPORT) and analysis_v2_receipt["artifact_sha256"]["execution_manifest"] == digest(ANALYSIS_V2_MANIFEST),
        "analysis_v2_predecessor_outputs_unused": analysis_v2["predecessor_analysis_v1_outputs_used"] is False and analysis_v2["predecessor_power_gate_v1_outputs_used"] is False,
        "paired_exact_effect_frozen": analysis_v2["paired_primary_effect"]["estimate"] == 0.0,
        "localization_superiority_not_estimable": analysis_v2["structural_diagnostics"]["general_atomic_localization_superiority_estimable"] is False and analysis_v2["structural_diagnostics"]["localization_estimand_status"] == "degenerate_representation_equivalent_single_claim_frame",
    }
    requirements = power_v2["identifiability_requirement_results"]
    power_checks = {
        "power_v2_hash_lineage": power_receipt_v2["artifact_sha256"]["power_gate_report"] == digest(POWER_V2_REPORT) and power_receipt_v2["artifact_sha256"]["sample_size_freeze"] == digest(POWER_V2_SAMPLE),
        "three_structural_requirements_fail": requirements["reference_contains_multi_claim_or_localizable_within_candidate_structure"] is False and requirements["atomic_arm_contains_finer_than_whole_candidate_operations"] is False and requirements["target_localization_endpoint_non_degenerate"] is False,
        "clusters_available": requirements["paired_candidate_clusters_available"] is True,
        "target_not_identifiable": power_v2["target_estimand_identifiable"] is False,
        "exact_effect_not_substituted": power_v2["observed_pilot_exact_effect_atomic_minus_candidate"] == 0.0 and power_v2["observed_exact_effect_used_for_target_power"] is False,
        "sample_size_null": sample_v2["sample_size_candidates"] is None and sample_v2["sample_size_clusters"] is None and sample_v2["finite_sample_size_authorized"] is False,
        "confirmatory_not_authorized": sample_v2["confirmatory_opening_authorized"] is False and power_receipt_v2["confirmatory_opening_authorized"] is False,
    }
    manifest_data = load(MANIFEST)
    policy_scan = recursive_policy_scan([ROOT / path for path in manifest_data["scoped_artifact_sha256"]])
    global_policy_checks = {
        "all_scoped_json_parsed": policy_scan["parsed_json_file_count"] == manifest_data["scoped_json_file_count"],
        "confirmatory_never_opened": not policy_scan["confirmatory_true_occurrences"],
        "runtime_never_authorized": not policy_scan["runtime_authorized_true_occurrences"],
        "usd_cost_not_imputed": not policy_scan["nonnull_usd_cost_occurrences"],
        "entry_state_closed": state_prev["confirmatory_dataset_opened"] is False and ready_prev["confirmatory_dataset_opened"] is False,
    }
    groups = {"sampling": sampling_checks, "independent_reference": reference_checks, "dual_arm": dual_checks,
        "analysis": analysis_checks, "power_and_sample_size": power_checks, "global_policy": global_policy_checks}
    if not all(all(group.values()) for group in groups.values()):
        failed = {name: [key for key, value in group.items() if not value] for name, group in groups.items() if not all(group.values())}
        raise ValueError(f"final_audit_failed:{failed}")

    report = {
        "schema_version": 1, "report_id": "phase7.3.3-d-independent-pilot-final-audit-report-v1",
        "status": "PASS_independent_pilot_chain_completed", "manifest_sha256": digest(MANIFEST), "audit_groups": groups,
        "audit_summary": {"group_count": len(groups), "check_count": sum(len(group) for group in groups.values()),
            "failed_check_count": 0, "scoped_json_file_count": policy_scan["parsed_json_file_count"]},
        "authoritative_scientific_result": {"analysis_version": "v2_corrective_successor",
            "candidate_exact_accuracy": analysis_v2["arm_metrics"]["candidate"]["exact_accuracy"],
            "atomic_exact_accuracy": analysis_v2["arm_metrics"]["atomic"]["exact_accuracy"],
            "paired_exact_effect_atomic_minus_candidate": analysis_v2["paired_primary_effect"]["estimate"],
            "general_atomic_diagnostic_localization_superiority_estimable": False,
            "general_atomic_diagnostic_localization_superiority_conclusion_authorized": False,
            "interpretation": "The exploratory paired exact-label effect is zero on this frozen single-claim frame. It is not a substitute for the non-identifiable general localization-superiority estimand."},
        "lineage_disposition": {"analysis_v1": "immutable_implementation_negative_retained_and_excluded",
            "power_gate_v1": "immutable_output_retained_and_excluded_due_inherited_invalid_analysis_lineage",
            "analysis_v2": "authoritative_exploratory_corrective_successor", "power_gate_v2": "authoritative_power_and_sample_size_gate"},
        "power_disposition": {"status": "power_infeasible_current_single_claim_frame", "sample_size_candidates": None,
            "finite_confirmatory_sample_size_authorized": False, "successor_design_required": True},
        "resource_accounting": {"candidate_total_tokens": analysis_v2["resources"]["candidate"]["total_tokens"],
            "atomic_total_tokens": analysis_v2["resources"]["atomic"]["total_tokens"], "candidate_cost_usd": None,
            "atomic_cost_usd": None, "cost_status": "provider_billing_price_not_frozen"},
        "policy_scan": policy_scan, "confirmatory_dataset_opened": False, "confirmatory_opening_authorized": False,
        "runtime_integration_authorized": False}
    report_hash = write_once(REPORT, report)
    state_lineage = dict(state_prev["artifact_lineage"])
    state_lineage.update({"support_stage_state_v23_sha256": digest(STATE_PREV), "readiness_v34_sha256": digest(READY_PREV),
        "independent_pilot_final_audit_manifest_v1_sha256": digest(MANIFEST), "independent_pilot_final_audit_report_v1_sha256": report_hash})
    state = {"schema_version": 24, "state_id": "phase7.3.3-d-support-stage-state-v24",
        "boundary_state": state_prev["boundary_state"], "support_state": state_prev["support_state"], "artifact_lineage": state_lineage,
        "boundary_gold_sha256": state_prev["boundary_gold_sha256"], "support_gold_sha256": state_prev["support_gold_sha256"],
        "runtime_integration_authorized": False,
        "independent_replication_state": "independent_pilot_chain_completed_power_infeasible_current_single_claim_frame",
        "independent_pilot_chain_completed": True, "analysis_v1_authoritative_implementation_negative": True,
        "analysis_v1_outputs_eligible_for_final_conclusion": False, "power_gate_v1_outputs_eligible_for_final_conclusion": False,
        "analysis_v2_authoritative_exploratory_result": True, "power_gate_v2_authoritative": True,
        "independent_pilot_exact_effect_atomic_minus_candidate": 0.0, "general_atomic_localization_superiority_estimable": False,
        "independent_confirmatory_sample_size_candidates": None, "independent_confirmatory_opening_authorized": False,
        "next_authorized_stage": "design_successor_identifiable_multi_claim_pilot_frame_v1", "confirmatory_dataset_opened": False}
    state_hash = write_once(STATE, state)
    ready_lineage = dict(ready_prev["artifact_lineage"])
    ready_lineage.update({"readiness_v34_sha256": digest(READY_PREV), "support_stage_state_v23_sha256": digest(STATE_PREV),
        "independent_pilot_final_audit_manifest_v1_sha256": digest(MANIFEST), "independent_pilot_final_audit_report_v1_sha256": report_hash,
        "support_stage_state_v24_sha256": state_hash})
    readiness = {"schema_version": 45, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v35",
        "status": "independent_pilot_chain_completed_power_infeasible_current_single_claim_frame", "artifact_lineage": ready_lineage,
        "reference_status": "frozen_and_sealed", "dual_arm_status": "v4_completed_equal_resource_scored_by_analysis_v2",
        "analysis_v1_status": "authoritative_implementation_negative_excluded",
        "power_gate_v1_status": "excluded_due_inherited_invalid_analysis_lineage",
        "analysis_v2_status": "authoritative_exploratory_corrective_successor",
        "power_gate_v2_status": "authoritative_power_infeasible_current_single_claim_frame", "final_audit_status": "PASS",
        "sample_size_candidates": None, "confirmatory_opening_authorized": False,
        "next_authorized_stage": "design_successor_identifiable_multi_claim_pilot_frame_v1",
        "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    readiness_hash = write_once(READY, readiness)
    receipt = {"schema_version": 1, "receipt_id": "phase7.3.3-d-independent-pilot-final-audit-receipt-v1",
        "status": "PASS_independent_pilot_chain_completed",
        "artifact_sha256": {"final_audit_manifest": digest(MANIFEST), "final_audit_report": report_hash,
            "support_stage_state_v24": state_hash, "readiness_v35": readiness_hash,
            "analysis_v1_negative_result": digest(ANALYSIS_V1_NEGATIVE), "analysis_v2_report": digest(ANALYSIS_V2_REPORT),
            "power_gate_v1_report": digest(POWER_V1_REPORT), "power_gate_v2_report": digest(POWER_V2_REPORT),
            "sample_size_freeze_v2": digest(POWER_V2_SAMPLE)},
        "authoritative_analysis_version": "v2", "authoritative_power_gate_version": "v2", "sample_size_candidates": None,
        "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    receipt_hash = write_once(RECEIPT, receipt)
    print(json.dumps({"status": report["status"], "check_count": report["audit_summary"]["check_count"],
        "scoped_json_file_count": report["audit_summary"]["scoped_json_file_count"], "report_sha256": report_hash,
        "state_v24_sha256": state_hash, "readiness_v35_sha256": readiness_hash, "receipt_sha256": receipt_hash,
        "sample_size_candidates": None, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}, indent=2))


def verify():
    required = [MANIFEST, REPORT, STATE, READY, RECEIPT]
    missing = [rel(path) for path in required if not path.exists()]
    if missing:
        print(json.dumps({"status": "FAIL", "missing": missing}, indent=2)); raise SystemExit(1)
    frozen, report, state, readiness, receipt = manifest_checks(), load(REPORT), load(STATE), load(READY), load(RECEIPT)
    groups = report["audit_groups"]
    checks = {
        "manifest_inputs_unchanged": all(frozen.values()), "all_audit_checks_passed": all(all(group.values()) for group in groups.values()),
        "report_completed": report["status"] == "PASS_independent_pilot_chain_completed" and report["audit_summary"]["failed_check_count"] == 0,
        "authoritative_versions": report["lineage_disposition"]["analysis_v2"] == "authoritative_exploratory_corrective_successor" and report["lineage_disposition"]["power_gate_v2"] == "authoritative_power_and_sample_size_gate",
        "excluded_predecessors": report["lineage_disposition"]["analysis_v1"] == "immutable_implementation_negative_retained_and_excluded" and "excluded" in report["lineage_disposition"]["power_gate_v1"],
        "sample_size_null": report["power_disposition"]["sample_size_candidates"] is None and receipt["sample_size_candidates"] is None,
        "state_v24_complete": state["independent_pilot_chain_completed"] is True and state["analysis_v2_authoritative_exploratory_result"] is True and state["power_gate_v2_authoritative"] is True,
        "readiness_v35_complete": readiness["final_audit_status"] == "PASS" and readiness["status"] == "independent_pilot_chain_completed_power_infeasible_current_single_claim_frame",
        "receipt_hash_lineage": receipt["artifact_sha256"]["final_audit_manifest"] == digest(MANIFEST) and receipt["artifact_sha256"]["final_audit_report"] == digest(REPORT) and receipt["artifact_sha256"]["support_stage_state_v24"] == digest(STATE) and receipt["artifact_sha256"]["readiness_v35"] == digest(READY),
        "confirmatory_closed": report["confirmatory_dataset_opened"] is False and report["confirmatory_opening_authorized"] is False and state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False and receipt["confirmatory_dataset_opened"] is False,
        "runtime_unauthorized": report["runtime_integration_authorized"] is False and state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False and receipt["runtime_integration_authorized"] is False,
        "usd_cost_null": report["resource_accounting"]["candidate_cost_usd"] is None and report["resource_accounting"]["atomic_cost_usd"] is None and not report["policy_scan"]["nonnull_usd_cost_occurrences"],
    }
    ok = all(checks.values())
    print(json.dumps({"status": "PASS" if ok else "FAIL", "checks": checks,
        "hashes": {"manifest": digest(MANIFEST), "report": digest(REPORT), "state_v24": digest(STATE),
            "readiness_v35": digest(READY), "receipt": digest(RECEIPT)}}, indent=2))
    if not ok: raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--freeze-manifest", action="store_true")
    group.add_argument("--audit", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight: preflight()
    elif args.freeze_manifest: freeze_manifest()
    elif args.audit: execute_audit()
    else: verify()


if __name__ == "__main__":
    main()
