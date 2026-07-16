#!/usr/bin/env python3
"""Freeze and execute the Independent Pilot power/sample-size gate.

This gate refuses to invent a finite confirmatory sample size when the frozen
Pilot frame cannot identify the intended general Atomic-localization estimand.
"""
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

PLAN = C / "phase7_3_3_d_independent_replication_analysis_plan_v1.json"
ANALYSIS_PROTOCOL = C / "phase7_3_3_d_independent_pilot_analysis_protocol_v2.json"
ANALYSIS_MANIFEST = R / "phase7_3_3_d_independent_pilot_analysis_execution_manifest_v2.json"
ANALYSIS_REPORT = R / "phase7_3_3_d_independent_pilot_analysis_report_v2.json"
ANALYSIS_RECEIPT = R / "phase7_3_3_d_independent_pilot_analysis_freeze_receipt_v2.json"
ANALYSIS_V1_NEGATIVE = R / "phase7_3_3_d_independent_pilot_analysis_negative_result_v1.json"
STATE_PREV = D / "phase7_3_3_d_support_stage_state_v22.json"
READY_PREV = R / "phase7_3_3_d1_reference_construction_readiness_v33.json"

METHOD = C / "phase7_3_3_d_independent_pilot_power_method_v2.json"
MANIFEST = R / "phase7_3_3_d_independent_pilot_power_gate_manifest_v2.json"
REPORT = R / "phase7_3_3_d_independent_pilot_power_gate_report_v2.json"
SAMPLE = R / "phase7_3_3_d_independent_pilot_sample_size_freeze_v2.json"
RECEIPT = R / "phase7_3_3_d_independent_pilot_power_gate_receipt_v2.json"
STATE = D / "phase7_3_3_d_support_stage_state_v23.json"
READY = R / "phase7_3_3_d1_reference_construction_readiness_v34.json"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_once(path: Path, value) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable_artifact_conflict:{path.relative_to(ROOT)}")
        return digest_bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)
    return digest_bytes(data)


def preflight_checks():
    required = [
        PLAN,
        ANALYSIS_PROTOCOL,
        ANALYSIS_MANIFEST,
        ANALYSIS_REPORT,
        ANALYSIS_RECEIPT,
        ANALYSIS_V1_NEGATIVE,
        STATE_PREV,
        READY_PREV,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        return {"required_inputs_present": False, "missing": missing}
    analysis = load(ANALYSIS_REPORT)
    state = load(STATE_PREV)
    readiness = load(READY_PREV)
    return {
        "required_inputs_present": True,
        "analysis_v2_frozen": analysis["status"] == "frozen_exploratory_pilot_result_corrective_successor",
        "analysis_receipt_matches": load(ANALYSIS_RECEIPT)["artifact_sha256"]["analysis_report"] == digest(ANALYSIS_REPORT),
        "analysis_v1_negative_frozen": load(ANALYSIS_V1_NEGATIVE)["status"] == "authoritative_implementation_negative_result"
        and load(ANALYSIS_V1_NEGATIVE)["analysis_v1_outputs_eligible_for_final_pilot_conclusion"] is False
        and load(ANALYSIS_V1_NEGATIVE)["power_gate_v1_inherited_lineage_eligible_for_final_conclusion"] is False,
        "predecessor_outputs_excluded": analysis["predecessor_analysis_v1_outputs_used"] is False
        and analysis["predecessor_power_gate_v1_outputs_used"] is False,
        "effect_and_missingness_frozen": state["independent_pilot_effect_frozen"] is True
        and state["independent_pilot_missingness_frozen"] is True
        and state["independent_pilot_analysis_v2_completed"] is True,
        "authorized_stage": state["next_authorized_stage"] == "freeze_independent_pilot_power_method_v2"
        and readiness["next_authorized_stage"] == "freeze_independent_pilot_power_method_v2",
        "structural_degeneracy_observed": analysis["structural_diagnostics"]["general_atomic_localization_superiority_estimable"] is False
        and analysis["structural_diagnostics"]["localization_estimand_status"]
        == "degenerate_representation_equivalent_single_claim_frame",
        "no_missing_pairs": analysis["missingness_and_failures"]["paired_cases_dropped"] == 0,
        "outputs_absent": not any(path.exists() for path in [METHOD, MANIFEST, REPORT, SAMPLE, RECEIPT, STATE, READY]),
        "confirmatory_closed": analysis["confirmatory_content_opened"] is False
        and state["confirmatory_dataset_opened"] is False
        and readiness["confirmatory_dataset_opened"] is False,
        "runtime_unauthorized": state["runtime_integration_authorized"] is False
        and readiness["runtime_integration_authorized"] is False,
    }


def preflight():
    checks = preflight_checks()
    ok = all(value for key, value in checks.items() if key != "missing")
    print(json.dumps({"status": "PASS" if ok else "FAIL", "checks": checks}, indent=2))
    if not ok:
        raise SystemExit(1)


def method_document():
    plan = load(PLAN)
    return {
        "schema_version": 2,
        "method_id": "phase7.3.3-d-independent-pilot-power-method-v2",
        "status": "frozen_before_sample_size_decision",
        "target_confirmatory_estimand": "general_atomic_diagnostic_localization_superiority_over_candidate_level",
        "target_endpoint": "diagnostic_localization_precision_recall_f1",
        "decision_sequence": [
            "verify_frozen_pilot_effect_and_missingness",
            "verify_target_estimand_identifiability_on_pilot_frame",
            "verify_non_equivalent_candidate_and_atomic_representations",
            "only_if_identifiable_compute_finite_confirmatory_sample_size",
            "otherwise_freeze_null_sample_size_and_keep_confirmatory_closed",
        ],
        "identifiability_requirements": {
            "reference_contains_multi_claim_or_localizable_within_candidate_structure": True,
            "atomic_arm_contains_finer_than_whole_candidate_operations": True,
            "target_localization_endpoint_non_degenerate": True,
            "paired_candidate_clusters_available": True,
        },
        "finite_sample_size_authorized_only_if_all_identifiability_requirements_pass": True,
        "numeric_defaults_if_future_successor_frame_is_identifiable": {
            "alpha": plan["power_defaults"]["alpha"],
            "power": plan["power_defaults"]["power"],
            "minimum_confirmatory_candidates": plan["power_defaults"]["minimum_confirmatory_candidates"],
            "multiplicity": plan["power_defaults"]["multiplicity"],
        },
        "current_pilot_not_used_to_impute_unidentified_localization_effect": True,
        "paired_exact_accuracy_effect_is_not_a_substitute_for_the_target_localization_estimand": True,
        "confirmatory_content_opened": False,
        "runtime_integration_authorized": False,
    }


def freeze_method():
    checks = preflight_checks()
    ok = all(value for key, value in checks.items() if key != "missing")
    if not ok:
        raise ValueError("power_gate_preflight_failed")
    method_hash = write_once(METHOD, method_document())
    manifest = {
        "schema_version": 2,
        "manifest_id": "phase7.3.3-d-independent-pilot-power-gate-manifest-v2",
        "status": "frozen_before_power_gate_decision",
        "artifact_sha256": {
            "adapter": digest(Path(__file__)),
            "analysis_plan": digest(PLAN),
            "analysis_protocol": digest(ANALYSIS_PROTOCOL),
            "analysis_execution_manifest": digest(ANALYSIS_MANIFEST),
            "analysis_report": digest(ANALYSIS_REPORT),
            "analysis_receipt": digest(ANALYSIS_RECEIPT),
            "analysis_v1_negative_result": digest(ANALYSIS_V1_NEGATIVE),
            "power_method": method_hash,
            "state_v22": digest(STATE_PREV),
            "readiness_v33": digest(READY_PREV),
        },
        "sample_size_decision_started": False,
        "confirmatory_content_opened": False,
        "runtime_integration_authorized": False,
    }
    manifest_hash = write_once(MANIFEST, manifest)
    print(
        json.dumps(
            {
                "status": "power_method_and_manifest_frozen",
                "power_method_sha256": method_hash,
                "manifest_sha256": manifest_hash,
                "sample_size_decision_started": False,
                "confirmatory_content_opened": False,
            },
            indent=2,
        )
    )


def frozen_input_checks():
    if not METHOD.exists() or not MANIFEST.exists():
        return {"method_and_manifest_present": False}
    manifest = load(MANIFEST)
    method = load(METHOD)
    return {
        "method_and_manifest_present": True,
        "adapter": manifest["artifact_sha256"]["adapter"] == digest(Path(__file__)),
        "plan": manifest["artifact_sha256"]["analysis_plan"] == digest(PLAN),
        "analysis_protocol": manifest["artifact_sha256"]["analysis_protocol"] == digest(ANALYSIS_PROTOCOL),
        "analysis_manifest": manifest["artifact_sha256"]["analysis_execution_manifest"] == digest(ANALYSIS_MANIFEST),
        "analysis_report": manifest["artifact_sha256"]["analysis_report"] == digest(ANALYSIS_REPORT),
        "analysis_receipt": manifest["artifact_sha256"]["analysis_receipt"] == digest(ANALYSIS_RECEIPT),
        "analysis_v1_negative_result": manifest["artifact_sha256"]["analysis_v1_negative_result"] == digest(ANALYSIS_V1_NEGATIVE),
        "power_method": manifest["artifact_sha256"]["power_method"] == digest(METHOD),
        "previous_state": manifest["artifact_sha256"]["state_v22"] == digest(STATE_PREV),
        "previous_readiness": manifest["artifact_sha256"]["readiness_v33"] == digest(READY_PREV),
        "decision_not_started_at_freeze": manifest["sample_size_decision_started"] is False,
        "target_method_frozen": method["status"] == "frozen_before_sample_size_decision"
        and method["finite_sample_size_authorized_only_if_all_identifiability_requirements_pass"] is True,
        "confirmatory_closed": manifest["confirmatory_content_opened"] is False
        and method["confirmatory_content_opened"] is False,
    }


def execute_gate():
    checks = frozen_input_checks()
    if not all(checks.values()):
        raise ValueError("frozen_power_gate_inputs_invalid")
    if any(path.exists() for path in [REPORT, SAMPLE, RECEIPT, STATE, READY]):
        raise ValueError("power_gate_terminal_artifact_exists")

    analysis = load(ANALYSIS_REPORT)
    diagnostics = analysis["structural_diagnostics"]
    reference_multi_claim = diagnostics["reference_claim_count"] > analysis["case_count"]
    atomic_finer = not diagnostics["all_atomic_operations_whole_candidate"]
    endpoint_non_degenerate = diagnostics["general_atomic_localization_superiority_estimable"] is True
    clusters_available = analysis["unique_candidate_cluster_count"] > 1
    requirement_results = {
        "reference_contains_multi_claim_or_localizable_within_candidate_structure": reference_multi_claim,
        "atomic_arm_contains_finer_than_whole_candidate_operations": atomic_finer,
        "target_localization_endpoint_non_degenerate": endpoint_non_degenerate,
        "paired_candidate_clusters_available": clusters_available,
    }
    identifiable = all(requirement_results.values())
    if identifiable:
        raise ValueError("unexpected_identifiable_frame_requires_successor_numeric_power_implementation")

    report = {
        "schema_version": 2,
        "report_id": "phase7.3.3-d-independent-pilot-power-gate-report-v2",
        "status": "power_infeasible_current_single_claim_frame",
        "manifest_sha256": digest(MANIFEST),
        "power_method_sha256": digest(METHOD),
        "analysis_report_sha256": digest(ANALYSIS_REPORT),
        "analysis_v1_negative_result_sha256": digest(ANALYSIS_V1_NEGATIVE),
        "predecessor_analysis_v1_outputs_used": False,
        "predecessor_power_gate_v1_outputs_used": False,
        "target_confirmatory_estimand": load(METHOD)["target_confirmatory_estimand"],
        "identifiability_requirement_results": requirement_results,
        "target_estimand_identifiable": False,
        "observed_pilot_exact_effect_atomic_minus_candidate": analysis["paired_primary_effect"]["estimate"],
        "observed_exact_effect_used_for_target_power": False,
        "reason": "The sealed Pilot has one full-Candidate reference claim per case and all Atomic-arm operations are whole_candidate_claim. Candidate and Atomic localization representations are therefore structurally equivalent for the intended general localization estimand.",
        "scientific_interpretation": "The current frame supports semantic and representation feasibility analysis only. It cannot identify or power a confirmatory claim of general Atomic diagnostic-localization superiority.",
        "required_successor_design": {
            "new_frame_required": True,
            "frame_properties": [
                "multiple independently adjudicable claims within at least some Candidates",
                "pre-frozen diagnostic heterogeneity including supported and material-error regions",
                "Atomic operations capable of selecting claim-local spans rather than only whole_candidate_claim",
                "independent Reference construction repeated without Route A Gold or arm visibility",
            ],
            "same_pilot_frame_reuse_for_target_power_authorized": False,
        },
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    report_hash = write_once(REPORT, report)

    sample = {
        "schema_version": 2,
        "freeze_id": "phase7.3.3-d-independent-pilot-sample-size-freeze-v2",
        "status": "frozen_null_sample_size_power_infeasible_current_single_claim_frame",
        "manifest_sha256": digest(MANIFEST),
        "power_gate_report_sha256": report_hash,
        "target_confirmatory_estimand": report["target_confirmatory_estimand"],
        "sample_size_candidates": None,
        "sample_size_clusters": None,
        "finite_sample_size_authorized": False,
        "alpha": load(METHOD)["numeric_defaults_if_future_successor_frame_is_identifiable"]["alpha"],
        "target_power": load(METHOD)["numeric_defaults_if_future_successor_frame_is_identifiable"]["power"],
        "minimum_confirmatory_candidates_if_estimable": load(METHOD)["numeric_defaults_if_future_successor_frame_is_identifiable"]["minimum_confirmatory_candidates"],
        "null_reason": "target_localization_estimand_not_identifiable_on_frozen_single_claim_pilot_frame",
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    sample_hash = write_once(SAMPLE, sample)

    receipt = {
        "schema_version": 2,
        "receipt_id": "phase7.3.3-d-independent-pilot-power-gate-receipt-v2",
        "status": "frozen_power_infeasible_current_single_claim_frame",
        "artifact_sha256": {
            "power_method": digest(METHOD),
            "power_gate_manifest": digest(MANIFEST),
            "analysis_report": digest(ANALYSIS_REPORT),
            "analysis_v1_negative_result": digest(ANALYSIS_V1_NEGATIVE),
            "power_gate_report": report_hash,
            "sample_size_freeze": sample_hash,
        },
        "target_estimand_identifiable": False,
        "finite_sample_size_frozen": False,
        "sample_size_candidates": None,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    receipt_hash = write_once(RECEIPT, receipt)

    previous_state = load(STATE_PREV)
    state_lineage = dict(previous_state["artifact_lineage"])
    state_lineage.update(
        {
            "support_stage_state_v22_sha256": digest(STATE_PREV),
            "readiness_v33_sha256": digest(READY_PREV),
            "independent_pilot_power_method_v2_sha256": digest(METHOD),
            "independent_pilot_power_gate_manifest_v2_sha256": digest(MANIFEST),
            "independent_pilot_power_gate_report_v2_sha256": report_hash,
            "independent_pilot_sample_size_freeze_v2_sha256": sample_hash,
            "independent_pilot_power_gate_receipt_v2_sha256": receipt_hash,
        }
    )
    state = {
        "schema_version": 23,
        "state_id": "phase7.3.3-d-support-stage-state-v23",
        "boundary_state": previous_state["boundary_state"],
        "support_state": previous_state["support_state"],
        "artifact_lineage": state_lineage,
        "boundary_gold_sha256": previous_state["boundary_gold_sha256"],
        "support_gold_sha256": previous_state["support_gold_sha256"],
        "runtime_integration_authorized": False,
        "independent_replication_state": "independent_pilot_power_gate_v2_completed_power_infeasible_current_single_claim_frame",
        "analysis_v1_authoritative_implementation_negative": True,
        "analysis_v1_outputs_eligible_for_final_conclusion": False,
        "power_gate_v1_outputs_eligible_for_final_conclusion": False,
        "independent_pilot_analysis_v2_completed": True,
        "independent_pilot_power_method_v2_frozen": True,
        "independent_pilot_power_gate_v2_completed": True,
        "general_atomic_localization_superiority_estimable": False,
        "independent_confirmatory_sample_size_candidates": None,
        "independent_confirmatory_opening_authorized": False,
        "next_authorized_stage": "final_audit_independent_pilot_chain_v1",
        "confirmatory_dataset_opened": False,
    }
    state_hash = write_once(STATE, state)

    previous_ready = load(READY_PREV)
    ready_lineage = dict(previous_ready["artifact_lineage"])
    ready_lineage.update(
        {
            "readiness_v33_sha256": digest(READY_PREV),
            "support_stage_state_v22_sha256": digest(STATE_PREV),
            "power_method_v2_sha256": digest(METHOD),
            "power_gate_manifest_v2_sha256": digest(MANIFEST),
            "power_gate_report_v2_sha256": report_hash,
            "sample_size_freeze_v2_sha256": sample_hash,
            "power_gate_receipt_v2_sha256": receipt_hash,
            "support_stage_state_v23_sha256": state_hash,
        }
    )
    readiness = {
        "schema_version": 44,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v34",
        "status": "independent_pilot_power_infeasible_current_single_claim_frame",
        "artifact_lineage": ready_lineage,
        "reference_status": "frozen_and_sealed",
        "dual_arm_status": "v4_completed_equal_resource_scored_by_v2",
        "analysis_v1_status": "authoritative_implementation_negative_excluded",
        "power_gate_v1_status": "excluded_due_inherited_invalid_analysis_lineage",
        "analysis_v2_status": "frozen_exploratory_pilot_result_corrective_successor",
        "power_gate_v2_status": "frozen_power_infeasible_current_single_claim_frame",
        "sample_size_candidates": None,
        "confirmatory_opening_authorized": False,
        "next_authorized_stage": "final_audit_independent_pilot_chain_v1",
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    readiness_hash = write_once(READY, readiness)

    print(
        json.dumps(
            {
                "status": report["status"],
                "power_gate_report_sha256": report_hash,
                "sample_size_freeze_sha256": sample_hash,
                "receipt_sha256": receipt_hash,
                "state_v23_sha256": state_hash,
                "readiness_v34_sha256": readiness_hash,
                "sample_size_candidates": None,
                "confirmatory_dataset_opened": False,
            },
            indent=2,
        )
    )


def verify():
    required = [METHOD, MANIFEST, REPORT, SAMPLE, RECEIPT, STATE, READY]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        print(json.dumps({"status": "FAIL", "missing": missing}, indent=2))
        raise SystemExit(1)
    frozen = frozen_input_checks()
    report = load(REPORT)
    sample = load(SAMPLE)
    receipt = load(RECEIPT)
    state = load(STATE)
    readiness = load(READY)
    reqs = report["identifiability_requirement_results"]
    checks = {
        "frozen_inputs": all(frozen.values()),
        "report_hash_lineage": report["manifest_sha256"] == digest(MANIFEST)
        and report["analysis_report_sha256"] == digest(ANALYSIS_REPORT),
        "sample_hash_lineage": sample["power_gate_report_sha256"] == digest(REPORT)
        and sample["manifest_sha256"] == digest(MANIFEST),
        "receipt_hash_lineage": receipt["artifact_sha256"]["power_gate_report"] == digest(REPORT)
        and receipt["artifact_sha256"]["sample_size_freeze"] == digest(SAMPLE),
        "structural_gate_failed": reqs["reference_contains_multi_claim_or_localizable_within_candidate_structure"] is False
        and reqs["atomic_arm_contains_finer_than_whole_candidate_operations"] is False
        and reqs["target_localization_endpoint_non_degenerate"] is False,
        "clusters_available": reqs["paired_candidate_clusters_available"] is True,
        "target_not_identifiable": report["target_estimand_identifiable"] is False,
        "exact_effect_not_substituted": report["observed_exact_effect_used_for_target_power"] is False,
        "sample_size_null": sample["sample_size_candidates"] is None
        and sample["sample_size_clusters"] is None
        and sample["finite_sample_size_authorized"] is False,
        "confirmatory_not_authorized": sample["confirmatory_opening_authorized"] is False
        and receipt["confirmatory_opening_authorized"] is False
        and state["independent_confirmatory_opening_authorized"] is False
        and readiness["confirmatory_opening_authorized"] is False,
        "confirmatory_closed": not any(
            [
                report["confirmatory_dataset_opened"],
                sample["confirmatory_dataset_opened"],
                receipt["confirmatory_dataset_opened"],
                state["confirmatory_dataset_opened"],
                readiness["confirmatory_dataset_opened"],
            ]
        ),
        "successor_required": report["required_successor_design"]["new_frame_required"] is True
        and report["required_successor_design"]["same_pilot_frame_reuse_for_target_power_authorized"] is False,
        "predecessor_outputs_excluded": report["predecessor_analysis_v1_outputs_used"] is False
        and report["predecessor_power_gate_v1_outputs_used"] is False
        and state["analysis_v1_outputs_eligible_for_final_conclusion"] is False
        and state["power_gate_v1_outputs_eligible_for_final_conclusion"] is False,
        "state_v23": state["independent_pilot_power_gate_v2_completed"] is True
        and state["independent_pilot_power_method_v2_frozen"] is True
        and state["next_authorized_stage"] == "final_audit_independent_pilot_chain_v1",
        "readiness_v34": readiness["power_gate_v2_status"] == "frozen_power_infeasible_current_single_claim_frame"
        and readiness["analysis_v1_status"] == "authoritative_implementation_negative_excluded"
        and readiness["power_gate_v1_status"] == "excluded_due_inherited_invalid_analysis_lineage"
        and readiness["analysis_v2_status"] == "frozen_exploratory_pilot_result_corrective_successor"
        and readiness["next_authorized_stage"] == "final_audit_independent_pilot_chain_v1",
        "runtime_unauthorized": report["runtime_integration_authorized"] is False
        and sample["runtime_integration_authorized"] is False
        and receipt["runtime_integration_authorized"] is False
        and state["runtime_integration_authorized"] is False
        and readiness["runtime_integration_authorized"] is False,
    }
    ok = all(checks.values())
    print(
        json.dumps(
            {
                "status": "PASS" if ok else "FAIL",
                "checks": checks,
                "hashes": {
                    "power_method": digest(METHOD),
                    "manifest": digest(MANIFEST),
                    "report": digest(REPORT),
                    "sample_size_freeze": digest(SAMPLE),
                    "receipt": digest(RECEIPT),
                    "state_v23": digest(STATE),
                    "readiness_v34": digest(READY),
                },
            },
            indent=2,
        )
    )
    if not ok:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--freeze-method", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        preflight()
    elif args.freeze_method:
        freeze_method()
    elif args.execute:
        execute_gate()
    else:
        verify()


if __name__ == "__main__":
    main()
