#!/usr/bin/env python3
"""Final recursive audit for the Phase 7.3.3-D Confirmatory successor chain."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from phase7_execution_attempt_log import read_entries


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
SCRIPTS = ROOT / "scripts/eval"

STATE_99 = PATTERN / "phase7_3_3_d_support_stage_state_v99.json"
READY_110_EXPLORATORY = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v110.json"
DESIGN_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_design_protocol_v1.json"
COMPOSITION = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_composition_contract_v1.json"
SAMPLING_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_sampling_policy_v1.json"
DESIGN_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_design_manifest_v1.json"
STATE_100 = PATTERN / "phase7_3_3_d_support_stage_state_v100.json"
READY_111 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v111.json"
INVENTORY = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_source_inventory_v1.json"
ELIGIBILITY = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_eligibility_audit_v1.json"
OVERLAP = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_overlap_audit_v1.json"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_worklist_v1.json"
INVENTORY_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_manifest_v1.json"
STATE_101 = PATTERN / "phase7_3_3_d_support_stage_state_v101.json"
READY_112 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v112.json"
PREREG = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_preregistration_v1.json"
OPEN_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_dataset_opening_policy_v1.json"
OPEN_GATE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_report_v1.json"
OPEN_GATE_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_receipt_v1.json"
STATE_102 = PATTERN / "phase7_3_3_d_support_stage_state_v102.json"
READY_113 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v113.json"
DATASET = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_dataset_v1.json"
COMMITMENT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_commitment_audit_v1.json"
OPEN_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_open_manifest_v1.json"
OPEN_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_open_receipt_v1.json"
STATE_103 = PATTERN / "phase7_3_3_d_support_stage_state_v103.json"
READY_114 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v114.json"
GOLD = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_v1.json"
GOLD_SEAL = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_seal_v1.json"
GOLD_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_manifest_v1.json"
GOLD_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_receipt_v1.json"
STATE_104 = PATTERN / "phase7_3_3_d_support_stage_state_v104.json"
READY_115 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v115.json"
STRUCT_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_report_v1.json"
STRUCT_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_receipt_v1.json"
STATE_105 = PATTERN / "phase7_3_3_d_support_stage_state_v105.json"
READY_116 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v116.json"
EXEC_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_policy_v1.json"
ENV_FREEZE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_environment_freeze_manifest_v1.json"
EXEC_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_manifest_v1.json"
PREPARE_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_prepare_receipt_v1.json"
STATE_106 = PATTERN / "phase7_3_3_d_support_stage_state_v106.json"
READY_117 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v117.json"
ATTEMPT_LOG = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_attempts_v1.jsonl"
CANDIDATE_CASES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_candidate_arm_cases_v1"
ATOMIC_CASES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_atomic_arm_cases_v1"
CANDIDATE_SUBMISSION = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_candidate_arm_submission_v1.json"
ATOMIC_SUBMISSION = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_atomic_arm_submission_v1.json"
EXEC_RESULT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_result_v1.json"
EXEC_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_receipt_v1.json"
EXEC_NEGATIVE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_negative_result_v1.json"
STATE_107 = PATTERN / "phase7_3_3_d_support_stage_state_v107.json"
READY_118 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v118.json"
REALIZED_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_report_v1.json"
REALIZED_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_manifest_v1.json"
REALIZED_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_realized_identifiability_receipt_v1.json"
STATE_108 = PATTERN / "phase7_3_3_d_support_stage_state_v108.json"
READY_119 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v119.json"
ANALYSIS_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_report_v1.json"
ANALYSIS_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_manifest_v1.json"
ANALYSIS_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_paired_analysis_receipt_v1.json"
STATE_109 = PATTERN / "phase7_3_3_d_support_stage_state_v109.json"
READY_120 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v120.json"
POWER_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_report_v1.json"
POWER_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_manifest_v1.json"
POWER_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_power_compliance_receipt_v1.json"
STATE_110 = PATTERN / "phase7_3_3_d_support_stage_state_v110.json"
READY_121 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v121.json"

INVENTORY_ADAPTER = SCRIPTS / "phase7_multi_claim_successor_confirmatory_inventory_v1.py"
REFERENCE_ADAPTER = SCRIPTS / "phase7_multi_claim_successor_confirmatory_reference_v1.py"
EXECUTION_ADAPTER = SCRIPTS / "phase7_multi_claim_successor_confirmatory_execution_v1.py"
ANALYSIS_ADAPTER = SCRIPTS / "phase7_multi_claim_successor_confirmatory_analysis_v1.py"
POWER_ADAPTER = SCRIPTS / "phase7_multi_claim_successor_confirmatory_power_gate_v1.py"

FINAL_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_final_audit_manifest_v1.json"
FINAL_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_final_audit_report_v1.json"
FINAL_AUDIT_LOG = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_final_audit_log_v1.jsonl"
FINAL_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_final_audit_receipt_v1.json"
STATE_111 = PATTERN / "phase7_3_3_d_support_stage_state_v111.json"
READY_122 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v122.json"

CUR = "run_confirmatory_final_audit_v1"
SUCCESS_NEXT = "confirmatory_success_frozen_runtime_integration_not_authorized"
NEGATIVE_NEXT = "confirmatory_null_or_negative_frozen_runtime_integration_not_authorized"

SCOPED_JSON = [
    STATE_99, READY_110_EXPLORATORY, DESIGN_PROTOCOL, COMPOSITION, SAMPLING_POLICY,
    DESIGN_MANIFEST, STATE_100, READY_111, INVENTORY, ELIGIBILITY, OVERLAP,
    WORKLIST, INVENTORY_MANIFEST, STATE_101, READY_112, PREREG, OPEN_POLICY,
    OPEN_GATE, OPEN_GATE_RECEIPT, STATE_102, READY_113, DATASET, COMMITMENT,
    OPEN_MANIFEST, OPEN_RECEIPT, STATE_103, READY_114, GOLD, GOLD_SEAL,
    GOLD_MANIFEST, GOLD_RECEIPT, STATE_104, READY_115, STRUCT_REPORT,
    STRUCT_RECEIPT, STATE_105, READY_116, EXEC_POLICY, ENV_FREEZE,
    EXEC_MANIFEST, PREPARE_RECEIPT, STATE_106, READY_117, CANDIDATE_SUBMISSION,
    ATOMIC_SUBMISSION, EXEC_RESULT, EXEC_RECEIPT, STATE_107, READY_118,
    REALIZED_REPORT, REALIZED_MANIFEST, REALIZED_RECEIPT, STATE_108, READY_119,
    ANALYSIS_REPORT, ANALYSIS_MANIFEST, ANALYSIS_RECEIPT, STATE_109, READY_120,
    POWER_REPORT, POWER_MANIFEST, POWER_RECEIPT, STATE_110, READY_121,
]


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def once(path: Path, value: Any) -> str:
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("immutable_artifact_mismatch:" + rel(path))
        return hb(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hb(body)


def append_single_event(path: Path, event: dict[str, Any]) -> str:
    body = (json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("append_only_audit_mismatch:" + rel(path))
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(body)
    return hb(body)


def occurrences(value: Any, predicate: Callable[[str, Any], bool], path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if predicate(key, child):
                found.append(child_path)
            found.extend(occurrences(child, predicate, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(occurrences(child, predicate, f"{path}[{index}]"))
    return found


def policy_scan() -> dict[str, Any]:
    runtime_true: dict[str, list[str]] = {}
    unselected_true: dict[str, list[str]] = {}
    nonnull_cost: dict[str, list[str]] = {}
    for path in SCOPED_JSON:
        document = load(path)
        runtime = occurrences(document, lambda key, value: "runtime" in key.lower() and (key.lower().endswith("authorized") or key.lower().endswith("allowed")) and value is True)
        unselected = occurrences(document, lambda key, value: "unselected" in key.lower() and "opened" in key.lower() and value is True)
        costs = occurrences(document, lambda key, value: key.lower() in {"cost_usd", "usd_cost"} and value is not None)
        if runtime:
            runtime_true[rel(path)] = runtime
        if unselected:
            unselected_true[rel(path)] = unselected
        if costs:
            nonnull_cost[rel(path)] = costs
    return {
        "scoped_json_file_count": len(SCOPED_JSON),
        "runtime_authorized_true_occurrences": runtime_true,
        "unselected_content_opened_true_occurrences": unselected_true,
        "nonnull_usd_cost_occurrences": nonnull_cost,
    }


def checkpoint_hashes(directory: Path) -> dict[str, str]:
    return {rel(path): sha(path) for path in sorted(directory.glob("*.json"))}


def final_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-final-audit-manifest-v1",
        "status": "frozen_before_recursive_final_audit",
        "adapter_sha256": sha(SELF),
        "scoped_artifact_sha256": {rel(path): sha(path) for path in SCOPED_JSON},
        "attempt_log_sha256": sha(ATTEMPT_LOG),
        "candidate_checkpoint_sha256": checkpoint_hashes(CANDIDATE_CASES),
        "atomic_checkpoint_sha256": checkpoint_hashes(ATOMIC_CASES),
        "confirmatory_dataset_opened": True,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }


def audit_groups() -> dict[str, dict[str, bool]]:
    attempts = read_entries(ATTEMPT_LOG)
    analysis = load(ANALYSIS_REPORT)
    scan = policy_scan()
    pre_open_states = [load(path) for path in [STATE_99, STATE_100, STATE_101]]
    candidate_checkpoints = checkpoint_hashes(CANDIDATE_CASES)
    atomic_checkpoints = checkpoint_hashes(ATOMIC_CASES)
    return {
        "opening_gate_sequence": {
            "pre_gate_dataset_closed": all(state["confirmatory_dataset_opened"] is False for state in pre_open_states),
            "pre_gate_opening_not_authorized": all(state.get("confirmatory_opening_authorized") is False for state in pre_open_states),
            "gate_passed_before_open": load(STATE_102)["confirmatory_opening_authorized"] is True and load(STATE_102)["confirmatory_dataset_opened"] is False,
            "gate_report_lineage": load(OPEN_GATE_RECEIPT)["report_sha256"] == sha(OPEN_GATE) and load(OPEN_GATE_RECEIPT)["state_sha256"] == sha(STATE_102),
            "selected_opened_after_gate": load(STATE_103)["confirmatory_dataset_opened"] is True and load(OPEN_RECEIPT)["dataset_sha256"] == sha(DATASET),
            "unselected_remained_closed": all(load(path)["multi_claim_successor_confirmatory_unselected_content_opened"] is False for path in [STATE_102, STATE_103, STATE_104, STATE_105, STATE_106, STATE_107, STATE_108, STATE_109, STATE_110]),
        },
        "inventory_and_source": {
            "inventory_80_eligible_80": load(INVENTORY)["inventory_count"] == 80 and load(ELIGIBILITY)["eligible_count"] == 80,
            "selected_40": load(WORKLIST)["selected_count"] == 40 and load(DATASET)["case_count"] == 40,
            "four_per_category": len(load(WORKLIST)["category_counts"]) == 10 and set(load(WORKLIST)["category_counts"].values()) == {4},
            "zero_prior_phase7_overlap": load(OVERLAP)["candidate_hash_overlap_count"] == load(OVERLAP)["evidence_hash_overlap_count"] == load(OVERLAP)["source_identity_overlap_count"] == 0,
            "commitments_40_40": load(COMMITMENT)["candidate_hash_matches"] == load(COMMITMENT)["evidence_hash_matches"] == 40,
            "phase6_usage_disclosed": load(DESIGN_PROTOCOL)["source_lineage"]["prior_phase6_benchmark_usage_disclosed"] is True,
            "generality_not_authorized": load(DESIGN_PROTOCOL)["source_lineage"]["generality_claim_beyond_this_confirmatory_replication_allowed"] is False,
            "v2_signal_template_not_reused": load(COMPOSITION)["not_v2_signal_template_family"] is True,
        },
        "reference_and_structural": {
            "gold_frozen_40_240": load(GOLD)["support_gold_frozen"] is True and load(GOLD)["case_count"] == 40 and load(GOLD)["claim_count"] == 240,
            "gold_label_balance": load(GOLD)["label_counts"] == {"supported": 80, "partially_supported": 80, "unsupported": 80, "not_assessable": 0},
            "mechanical_not_model_gold": "not_human_or_model_gold" in load(GOLD)["status"],
            "gold_seal_lineage": load(GOLD_SEAL)["support_gold_sha256"] == sha(GOLD) and load(GOLD_RECEIPT)["support_gold_seal_sha256"] == sha(GOLD_SEAL),
            "structural_pass": load(STRUCT_REPORT)["structural_estimand_identifiable"] is True and not load(STRUCT_REPORT)["failed_checks"],
            "structural_receipt_lineage": load(STRUCT_RECEIPT)["report_sha256"] == sha(STRUCT_REPORT) and load(STRUCT_RECEIPT)["state_sha256"] == sha(STATE_105),
        },
        "execution": {
            "environment_frozen_before_calls": load(PREPARE_RECEIPT)["provider_called"] is False and load(STATE_106)["next_authorized_stage"] == "execute_confirmatory_candidate_atomic_arms_v1",
            "same_model_and_resources": load(EXEC_POLICY)["model"] == load(PREREG)["arms"]["model"] == "gpt-5.4" and load(EXEC_RESULT)["resource_equality_verified"] is True,
            "counterbalanced_20_20": load(EXEC_RESULT)["counterbalance_first_arm_counts"] == {"candidate": 20, "atomic": 20},
            "execution_80_pass": load(EXEC_RESULT)["status"] == "PASS" and load(EXEC_RESULT)["request_count"] == 80,
            "checkpoint_counts_40_40": len(candidate_checkpoints) == len(atomic_checkpoints) == 40,
            "attempt_log_80_started_80_completed": sum(row.get("event_type") == "confirmatory_arm_attempt_started" for row in attempts) == sum(row.get("event_type") == "confirmatory_arm_attempt_completed" for row in attempts) == 80,
            "attempt_log_no_failure": not any("failure" in str(row.get("event_type")) for row in attempts),
            "authoritative_negative_absent": not EXEC_NEGATIVE.exists(),
            "submissions_40_240": load(CANDIDATE_SUBMISSION)["case_count"] == 40 and load(ATOMIC_SUBMISSION)["case_count"] == 40 and load(ATOMIC_SUBMISSION)["atomic_unit_count"] == 240,
            "reference_invisible": load(EXEC_RESULT)["reference_content_loaded"] is False and load(EXEC_RESULT)["reference_labels_loaded"] is False,
            "execution_receipt_lineage": load(EXEC_RECEIPT)["candidate_submission_sha256"] == sha(CANDIDATE_SUBMISSION) and load(EXEC_RECEIPT)["atomic_submission_sha256"] == sha(ATOMIC_SUBMISSION) and load(EXEC_RECEIPT)["execution_result_sha256"] == sha(EXEC_RESULT),
        },
        "realized_and_analysis": {
            "realized_pass": load(REALIZED_REPORT)["realized_representation_identifiable"] is True and load(REALIZED_REPORT)["localization_scoring_authorized"] is True,
            "realized_no_failed_checks": not load(REALIZED_REPORT)["failed_checks"],
            "realized_receipt_lineage": load(REALIZED_RECEIPT)["report_sha256"] == sha(REALIZED_REPORT) and load(REALIZED_RECEIPT)["state_sha256"] == sha(STATE_108),
            "paired_40_no_drop": analysis["case_count"] == 40 and analysis["missingness_and_failures"]["paired_cases_dropped"] == 0,
            "preregistered_test_exact": analysis["paired_primary_effect"]["randomization_replicates"] == load(PREREG)["primary_test"]["replicates"] == 200000 and analysis["paired_primary_effect"]["randomization_seed"] == load(PREREG)["primary_test"]["seed"] == 733071,
            "bootstrap_exact": analysis["paired_primary_effect"]["bootstrap_replicates"] == load(PREREG)["uncertainty"]["replicates"] == 20000 and analysis["paired_primary_effect"]["bootstrap_seed"] == load(PREREG)["uncertainty"]["seed"] == 733072,
            "confirmatory_success": analysis["confirmatory_success"] is True and all(analysis["confirmatory_success_checks"].values()),
            "effect_positive": analysis["paired_primary_effect"]["estimate"] > 0,
            "bootstrap_lower_positive": analysis["paired_primary_effect"]["bootstrap_interval_95"][0] > 0,
            "one_sided_significant": analysis["paired_primary_effect"]["one_sided_p_value"] < analysis["paired_primary_effect"]["one_sided_alpha"] == 0.05,
            "analysis_receipt_lineage": load(ANALYSIS_RECEIPT)["analysis_report_sha256"] == sha(ANALYSIS_REPORT) and load(ANALYSIS_RECEIPT)["state_sha256"] == sha(STATE_109),
        },
        "power_compliance": {
            "gate_pass": load(POWER_REPORT)["status"] == "PASS_power_and_sample_size_compliance" and not load(POWER_REPORT)["failed_checks"],
            "required_preregistered_selected_analyzed_40": load(POWER_REPORT)["authoritative_required_clusters"] == load(POWER_REPORT)["preregistered_clusters"] == load(POWER_REPORT)["selected_clusters"] == load(POWER_REPORT)["analyzed_clusters"] == 40,
            "no_replanning": load(POWER_REPORT)["post_result_replanning"] is False,
            "no_replacement": load(POWER_REPORT)["post_open_replacement"] is False,
            "observed_power_not_computed": load(POWER_REPORT)["observed_power_computed"] is False,
            "power_receipt_lineage": load(POWER_RECEIPT)["report_sha256"] == sha(POWER_REPORT) and load(POWER_RECEIPT)["state_sha256"] == sha(STATE_110),
        },
        "immutable_adapter_lineage": {
            "inventory_adapter": load(DESIGN_MANIFEST)["adapter_sha256"] == load(INVENTORY_MANIFEST)["adapter_sha256"] == sha(INVENTORY_ADAPTER),
            "reference_adapter": load(OPEN_MANIFEST)["adapter_sha256"] == load(GOLD_MANIFEST)["adapter_sha256"] == sha(REFERENCE_ADAPTER),
            "execution_adapter": load(ENV_FREEZE)["adapter_sha256"] == load(EXEC_MANIFEST)["adapter_sha256"] == sha(EXECUTION_ADAPTER),
            "analysis_adapter": load(REALIZED_MANIFEST)["adapter_sha256"] == load(ANALYSIS_MANIFEST)["adapter_sha256"] == sha(ANALYSIS_ADAPTER),
            "power_adapter": load(POWER_MANIFEST)["adapter_sha256"] == sha(POWER_ADAPTER),
        },
        "global_policy": {
            "all_scoped_json_parsed": scan["scoped_json_file_count"] == len(SCOPED_JSON),
            "runtime_never_authorized": not scan["runtime_authorized_true_occurrences"],
            "unselected_content_never_opened": not scan["unselected_content_opened_true_occurrences"],
            "usd_cost_not_imputed": not scan["nonnull_usd_cost_occurrences"],
            "runtime_currently_off": load(STATE_110)["runtime_integration_authorized"] is False and load(READY_121)["runtime_integration_authorized"] is False,
        },
    }


def preflight() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in [*SCOPED_JSON, ATTEMPT_LOG, INVENTORY_ADAPTER, REFERENCE_ADAPTER, EXECUTION_ADAPTER, ANALYSIS_ADAPTER, POWER_ADAPTER]}
    checks.update({
        "candidate_checkpoint_count": CANDIDATE_CASES.exists() and len(list(CANDIDATE_CASES.glob("*.json"))) == 40,
        "atomic_checkpoint_count": ATOMIC_CASES.exists() and len(list(ATOMIC_CASES.glob("*.json"))) == 40,
    })
    if all(checks.values()):
        state, readiness = load(STATE_110), load(READY_121)
        checks.update({
            "state_gate": state["next_authorized_stage"] == CUR,
            "readiness_gate": readiness["next_authorized_stage"] == CUR,
            "power_compliance_pass": state["multi_claim_successor_confirmatory_power_compliance_passed"] is True,
            "confirmatory_success": load(ANALYSIS_REPORT)["confirmatory_success"] is True,
            "unselected_closed": state["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    outputs = [FINAL_MANIFEST, FINAL_REPORT, FINAL_AUDIT_LOG, FINAL_RECEIPT, STATE_111, READY_122]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    return {"status": "PASS", "manifest_sha256": once(FINAL_MANIFEST, final_manifest()), "scoped_json_file_count": len(SCOPED_JSON), "candidate_checkpoint_count": 40, "atomic_checkpoint_count": 40, "runtime_integration_authorized": False}


def audit() -> dict[str, Any]:
    if not FINAL_MANIFEST.exists() or load(FINAL_MANIFEST) != final_manifest():
        raise RuntimeError("final_manifest_invalid")
    groups = audit_groups()
    failed = {group: [key for key, value in checks.items() if not value] for group, checks in groups.items() if not all(checks.values())}
    if failed:
        raise RuntimeError("final_audit_failed:" + repr(failed))
    analysis = load(ANALYSIS_REPORT)
    confirmatory_success = analysis["confirmatory_success"]
    next_stage = SUCCESS_NEXT if confirmatory_success else NEGATIVE_NEXT
    scan = policy_scan()
    report_hash = once(FINAL_REPORT, {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-confirmatory-final-audit-report-v1",
        "status": "PASS_CONFIRMATORY_SUCCESS_CHAIN_COMPLETE_RUNTIME_INTEGRATION_NOT_AUTHORIZED" if confirmatory_success else "PASS_AUTHORITATIVE_CONFIRMATORY_NULL_OR_NEGATIVE_CHAIN_COMPLETE_RUNTIME_INTEGRATION_NOT_AUTHORIZED",
        "manifest_sha256": sha(FINAL_MANIFEST),
        "audit_groups": groups,
        "audit_summary": {"group_count": len(groups), "check_count": sum(len(checks) for checks in groups.values()), "failed_check_count": 0, "scoped_json_file_count": len(SCOPED_JSON), "candidate_checkpoint_count": 40, "atomic_checkpoint_count": 40},
        "authoritative_scientific_result": {
            "estimand": analysis["paired_primary_effect"]["estimand"],
            "estimate_atomic_minus_candidate": analysis["paired_primary_effect"]["estimate"],
            "bootstrap_interval_95": analysis["paired_primary_effect"]["bootstrap_interval_95"],
            "one_sided_p_value": analysis["paired_primary_effect"]["one_sided_p_value"],
            "alpha_one_sided": analysis["paired_primary_effect"]["one_sided_alpha"],
            "confirmatory_success": confirmatory_success,
            "scope": "frozen_phase6_test_split_source_specific_multi_claim_composites",
            "general_system_performance_claim_authorized": False,
        },
        "power_and_sample_size_disposition": {
            "status": load(POWER_REPORT)["status"],
            "required_clusters": 40,
            "preregistered_clusters": 40,
            "analyzed_clusters": 40,
            "post_result_replanning": False,
        },
        "policy_scan": scan,
        "confirmatory_dataset_opened": True,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    audit_log_hash = append_single_event(FINAL_AUDIT_LOG, {"event_id": "confirmatory-final-audit-v1-completed", "event_type": "authoritative_final_audit", "manifest_sha256": sha(FINAL_MANIFEST), "report_sha256": report_hash, "confirmatory_success": confirmatory_success, "runtime_integration_authorized": False})
    state, readiness = copy.deepcopy(load(STATE_110)), copy.deepcopy(load(READY_121))
    lineage = {
        "multi_claim_successor_confirmatory_final_audit_manifest_v1_sha256": sha(FINAL_MANIFEST),
        "multi_claim_successor_confirmatory_final_audit_report_v1_sha256": report_hash,
        "multi_claim_successor_confirmatory_final_audit_log_v1_sha256": audit_log_hash,
    }
    update = {
        "status": "phase7_3_3_d_multi_claim_successor_confirmatory_success_chain_completed_runtime_integration_not_authorized" if confirmatory_success else "phase7_3_3_d_multi_claim_successor_authoritative_confirmatory_null_or_negative_chain_completed",
        "next_authorized_stage": next_stage,
        "multi_claim_successor_phase7_3_3_d_confirmatory_chain_completed": True,
        "multi_claim_successor_confirmatory_final_audit_passed": True,
        "multi_claim_successor_confirmatory_success": confirmatory_success,
        "multi_claim_successor_confirmatory_general_system_performance_claim_authorized": False,
        "confirmatory_dataset_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 111, "state_id": "phase7.3.3-d-support-stage-state-v111"})
    readiness.update({"schema_version": 122, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v122"})
    state_hash = once(STATE_111, state)
    readiness["artifact_lineage"]["support_stage_state_v111_sha256"] = state_hash
    readiness_hash = once(READY_122, readiness)
    receipt_hash = once(FINAL_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-final-audit-receipt-v1",
        "status": "PASS_CONFIRMATORY_SUCCESS" if confirmatory_success else "PASS_AUTHORITATIVE_CONFIRMATORY_NULL_OR_NEGATIVE",
        "final_audit_manifest_sha256": sha(FINAL_MANIFEST),
        "final_audit_report_sha256": report_hash,
        "final_audit_log_sha256": audit_log_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "audit_check_count": sum(len(checks) for checks in groups.values()),
        "confirmatory_success": confirmatory_success,
        "general_system_performance_claim_authorized": False,
        "confirmatory_dataset_opened": True,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    return {"status": "PASS", "audit_check_count": sum(len(checks) for checks in groups.values()), "confirmatory_success": confirmatory_success, "paired_effect": analysis["paired_primary_effect"]["estimate"], "one_sided_p_value": analysis["paired_primary_effect"]["one_sided_p_value"], "report_sha256": report_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "runtime_integration_authorized": False, "next_authorized_stage": next_stage}


def verify() -> dict[str, Any]:
    paths = [FINAL_MANIFEST, FINAL_REPORT, FINAL_AUDIT_LOG, FINAL_RECEIPT, STATE_111, READY_122]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        report, receipt = load(FINAL_REPORT), load(FINAL_RECEIPT)
        groups = audit_groups()
        checks.update({
            "manifest_replay": load(FINAL_MANIFEST) == final_manifest(),
            "audit_groups_replay": report["audit_groups"] == groups,
            "all_checks_pass": all(all(values.values()) for values in groups.values()),
            "report_pass": report["audit_summary"]["failed_check_count"] == 0 and report["authoritative_scientific_result"]["confirmatory_success"] is True,
            "receipt_lineage": receipt["final_audit_manifest_sha256"] == sha(FINAL_MANIFEST) and receipt["final_audit_report_sha256"] == sha(FINAL_REPORT) and receipt["final_audit_log_sha256"] == sha(FINAL_AUDIT_LOG) and receipt["state_sha256"] == sha(STATE_111) and receipt["readiness_sha256"] == sha(READY_122),
            "terminal_gate": load(STATE_111)["next_authorized_stage"] == load(READY_122)["next_authorized_stage"] == SUCCESS_NEXT,
            "unselected_closed": load(STATE_111)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_111)["runtime_integration_authorized"] is False and load(READY_122)["runtime_integration_authorized"] is False and receipt["runtime_integration_authorized"] is False,
            "generality_not_authorized": receipt["general_system_performance_claim_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "confirmatory_success": load(FINAL_REPORT)["authoritative_scientific_result"]["confirmatory_success"] if FINAL_REPORT.exists() else None, "runtime_integration_authorized": load(STATE_111).get("runtime_integration_authorized") if STATE_111.exists() else None, "next_authorized_stage": load(STATE_111)["next_authorized_stage"] if STATE_111.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--audit", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    outcome = preflight() if args.preflight else prepare() if args.prepare else audit() if args.audit else verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
