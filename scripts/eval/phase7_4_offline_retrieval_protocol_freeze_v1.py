#!/usr/bin/env python3
"""Freeze the Phase 7.4.2 RQ1/RQ2 offline retrieval protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
DOCS = ROOT / "docs"

PLAN = DOCS / "KING_SYNAPSE_LONG_TERM_COMPLETION_PLAN.md"
COMPLETION_CONTRACT = CONFIG / "project_completion_contract_v1.json"
PROTOCOL_DOC = DOCS / "eval/PHASE7_4_2_OFFLINE_RETRIEVAL_EVALUATION_PROTOCOL.md"
CASE_SCHEMA = CONFIG / "phase7_4_offline_retrieval_case_schema_v1.json"
GOLD_SCHEMA = CONFIG / "phase7_4_offline_retrieval_gold_schema_v1.json"
ARM_OUTPUT_SCHEMA = CONFIG / "phase7_4_offline_retrieval_arm_output_schema_v1.json"
ENVIRONMENT = CONFIG / "phase7_4_offline_retrieval_execution_environment_v1.json"
PROTOCOL = CONFIG / "phase7_4_offline_retrieval_evaluation_protocol_v1.json"

STATE_V3 = PATTERN / "phase7_4_stage_state_v3.json"
READINESS_V3 = REPORTS / "phase7_4_readiness_v3.json"
M0_RECEIPT = REPORTS / "phase7_4_m0_governance_freeze_receipt_v1.json"

FIXTURES = REPORTS / "phase7_4_offline_retrieval_protocol_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_4_offline_retrieval_protocol_freeze_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_offline_retrieval_protocol_freeze_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_offline_retrieval_protocol_freeze_audit_v1.jsonl"
STATE_V4 = PATTERN / "phase7_4_stage_state_v4.json"
READINESS_V4 = REPORTS / "phase7_4_readiness_v4.json"
RECEIPT = REPORTS / "phase7_4_offline_retrieval_protocol_freeze_receipt_v1.json"

ENTRY_HEAD = "c8465f875cd6c01fc0e7fc5c804352462e6b6ef9"
ENTRY = "m0_governance_baseline_frozen_phase7_4_2_protocol_freeze_authorized"
NEXT = "construct_phase7_4_independent_source_inventory_and_sampling_frame_v1"

EXPECTED = {
    PLAN: "eb20101e78f01726a3d9ebe5ce7f7ec2777c300647cf52aae98936ddeb9602bf",
    COMPLETION_CONTRACT: "63831b2886346d047413656155eb95a960e04061eb5f161992439c1081d1f924",
    STATE_V3: "8f8e8f6cc9d57308c2508595e7cf5885261795c3cd9c29c60c1a5d71417549b1",
    READINESS_V3: "e748ddef11d7d4a99b0bb28a229d748a70aa9aa4f01be175e9d3099bf9b7566d",
    M0_RECEIPT: "1e9f8e6ecf67c4ddeddd5d6268275d95f123851ddfe0ccc6f30f3a2867e03c0f",
    PROTOCOL_DOC: "13ceee510f661e59c1ac468f3e1c4d20e89d8b0a6ea244c18be85dd1e6a60480",
    CASE_SCHEMA: "d2a89998a154b0c6e58d10309b263f1199fd1e4efef2cb239243490e4731481f",
    GOLD_SCHEMA: "7c96fbd29e11b755dd932a0e81348305e40f4d22aabbbf41ec438b8252239f1d",
    ARM_OUTPUT_SCHEMA: "b07881b289d5657eb1e66d5470c45532db54a18abed6ce193dfa6738605ce729",
    ENVIRONMENT: "5b5b02a7651da6fb7ef4d0a4c25efb76beb38bacd7f63a518ec06b168bdff786",
    PROTOCOL: "adc48017a40a1ae7685ce5b8868f2bdff623cf845aa845c8ca7e7986ecdac8fb",
}

OUTPUTS = [FIXTURES, MANIFEST, OUTCOME, AUDIT, STATE_V4, READINESS_V4, RECEIPT]


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
    body = (canonical(event) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("append_only_audit_mismatch:" + rel(path))
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(body)
    return hb(body)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git_head() -> str:
    result = run(["git", "rev-parse", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError("git_head_unavailable")
    return result.stdout.strip()


def entry_head_is_ancestor() -> bool:
    return (
        run(["git", "merge-base", "--is-ancestor", ENTRY_HEAD, git_head()]).returncode
        == 0
    )


def validate_schema(path: Path) -> bool:
    try:
        Draft202012Validator.check_schema(load(path))
        return True
    except Exception:
        return False


def fixture_document() -> dict[str, Any]:
    protocol = load(PROTOCOL)
    environment = load(ENVIRONMENT)
    case_schema = load(CASE_SCHEMA)
    gold_schema = load(GOLD_SCHEMA)
    arm_schema = load(ARM_OUTPUT_SCHEMA)
    state = load(STATE_V3)
    readiness = load(READINESS_V3)
    mde = (1.959963984540054 + 0.8416212335729143) * 0.2 / math.sqrt(160)
    checks = [
        ("completion_plan_hash", protocol["frozen_governance_inputs"][rel(PLAN)] == sha(PLAN)),
        ("completion_contract_hash", protocol["frozen_governance_inputs"][rel(COMPLETION_CONTRACT)] == sha(COMPLETION_CONTRACT)),
        ("state_v3_hash", protocol["frozen_governance_inputs"][rel(STATE_V3)] == sha(STATE_V3)),
        ("readiness_v3_hash", protocol["frozen_governance_inputs"][rel(READINESS_V3)] == sha(READINESS_V3)),
        ("m0_receipt_hash", protocol["frozen_governance_inputs"][rel(M0_RECEIPT)] == sha(M0_RECEIPT)),
        ("protocol_document_hash", protocol["protocol_document"]["sha256"] == sha(PROTOCOL_DOC)),
        ("case_schema_hash", protocol["schemas"]["blind_case"]["sha256"] == sha(CASE_SCHEMA)),
        ("gold_schema_hash", protocol["schemas"]["gold"]["sha256"] == sha(GOLD_SCHEMA)),
        ("arm_output_schema_hash", protocol["schemas"]["blind_arm_output"]["sha256"] == sha(ARM_OUTPUT_SCHEMA)),
        ("environment_hash", protocol["execution_environment"]["sha256"] == sha(ENVIRONMENT)),
        ("case_schema_valid", validate_schema(CASE_SCHEMA)),
        ("gold_schema_valid", validate_schema(GOLD_SCHEMA)),
        ("arm_output_schema_valid", validate_schema(ARM_OUTPUT_SCHEMA)),
        ("entry_state_exact", state["status"] == ENTRY and state["next_authorized_stage"] == "freeze_phase7_4_offline_retrieval_evaluation_protocol_v1"),
        ("entry_readiness_exact", readiness["phase7_4_2_protocol_freeze_authorized"] is True and readiness["next_authorized_stage"] == "freeze_phase7_4_offline_retrieval_evaluation_protocol_v1"),
        ("research_family_exact", [rq["rq_id"] for rq in protocol["research_questions"]] == ["RQ1", "RQ2"] and protocol["research_family"]["rq3_in_family"] is False),
        ("holm_familywise_rule", protocol["research_family"]["familywise_one_sided_alpha"] == 0.05 and protocol["research_family"]["multiplicity_procedure"] == "holm_bonferroni"),
        ("rq1_threshold", protocol["research_questions"][0]["minimum_practical_effect"] == 0.05),
        ("rq2_threshold", protocol["research_questions"][1]["minimum_practical_effect"] == 0.03),
        ("supported_recall_noninferiority", protocol["research_questions"][1]["supported_recall_noninferiority_margin"] == -0.02),
        ("sample_size_and_strata", protocol["sampling_design"]["target_selected_case_count"] == 168 and protocol["sampling_design"]["minimum_analyzable_case_count"] == 160 and len(protocol["sampling_design"]["strata"]) == 8),
        ("per_stratum_counts", protocol["sampling_design"]["target_selected_cases_per_stratum"] == 21 and protocol["sampling_design"]["minimum_analyzable_cases_per_stratum"] == 20),
        ("design_mde_recomputed", abs(mde - protocol["design_power"]["normal_approximation_mde"]) < 0.0001),
        ("candidate_pool_exact", case_schema["properties"]["candidate_memories"]["minItems"] == case_schema["properties"]["candidate_memories"]["maxItems"] == 10),
        ("cutoff_exact", arm_schema["properties"]["cutoff_k"]["const"] == 5 and all(arm["result_cutoff_k"] == 5 for arm in protocol["arms"])),
        ("memory_kinds_unchanged", case_schema["$defs"]["candidate_memory"]["properties"]["source_memory_kind"]["enum"] == ["fact", "preference", "failure", "playbook", "state"]),
        ("gold_support_states_exact", protocol["gold_support_states"] == ["supported", "partially_supported", "unsupported", "contradictory", "not_assessable"]),
        ("gold_minimum_and_no_deferral", gold_schema["properties"]["case_count"]["minimum"] == 160 and gold_schema["properties"]["deferred_count"]["const"] == 0),
        ("permutation_frozen", protocol["statistical_plan"]["monte_carlo_samples"] == 100000 and protocol["statistical_plan"]["permutation_seed"] == 7402001),
        ("bootstrap_frozen", protocol["statistical_plan"]["bootstrap"]["samples"] == 20000 and protocol["statistical_plan"]["bootstrap"]["seed"] == 7402002),
        ("maximum_unusable_rate", protocol["missing_and_failure_policy"]["maximum_unpaired_or_unusable_rate"] == 0.05),
        ("no_selective_rerun_or_drop", protocol["missing_and_failure_policy"]["selective_rerun_allowed"] is False and protocol["missing_and_failure_policy"]["selective_case_deletion_allowed"] is False),
        ("reference_gate_frozen", protocol["pre_effect_gates"]["reference_gate"]["blind_reviewer_count"] == 2 and protocol["pre_effect_gates"]["reference_gate"]["minimum_aggregate_span_f1"] == 0.8 and protocol["pre_effect_gates"]["reference_gate"]["minimum_aggregate_support_state_cohen_kappa"] == 0.7),
        ("leakage_zero_overlap", all(protocol["pre_effect_gates"]["leakage_gate"][key] == 0 for key in ["exact_case_id_overlap_max", "exact_source_id_overlap_max", "exact_normalized_source_text_hash_overlap_max", "exact_candidate_hash_overlap_max", "exact_evidence_hash_overlap_max", "label_or_adjudication_lineage_reuse_max", "unresolved_high_similarity_pair_max"])),
        ("realized_identifiability_frozen", protocol["realized_identifiability_gate"]["minimum_analyzable_pairs"] == 160 and protocol["realized_identifiability_gate"]["byte_identical_semantic_projection_replay_required"] is True),
        ("regression_gate_frozen", protocol["regression_gate"]["memory_recall_at_5_arm_b_minus_arm_a_one_sided_lower_bound_gt"] == -0.02 and protocol["regression_gate"]["reconstruction_failure_rate_max"] == 0.01),
        ("cost_gate_frozen", protocol["cost_gate"]["p95_latency_ratio_arm_b_over_arm_a_max"] == 2 and protocol["cost_gate"]["provider_cost_usd"] == 0),
        ("failure_taxonomy_exact", len(protocol["failure_taxonomy"]) == 20 and len(set(protocol["failure_taxonomy"])) == 20),
        ("environment_provider_free", environment["execution_lane"]["provider"] == "none" and environment["execution_lane"]["network_access_allowed"] is False and environment["execution_lane"]["gold_access_during_arm_execution_allowed"] is False),
        ("environment_seeds_match", environment["determinism"]["permutation_seed"] == protocol["statistical_plan"]["permutation_seed"] and environment["determinism"]["bootstrap_seed"] == protocol["statistical_plan"]["bootstrap"]["seed"]),
        ("semantic_replay_excludes_telemetry", environment["determinism"]["semantic_replay_projection_excludes"] == ["latency_ns", "resource_summary"]),
        ("phase7_3_effect_data_not_used", protocol["design_power"]["phase7_3_3_d_effect_data_used"] is False and protocol["freeze_status"]["phase7_3_3_d_effect_data_loaded"] is False),
        ("effect_content_closed", protocol["sampling_design"]["effect_content_opened_during_protocol_freeze"] is False and protocol["freeze_status"]["selected_effect_content_opened"] is False),
        ("execution_not_started", protocol["freeze_status"]["arm_execution_started"] is False and protocol["freeze_status"]["effect_scoring_started"] is False),
        ("no_core_runtime_or_write_authority", all(protocol["freeze_status"][key] is False for key in ["memory_kind_modified", "memory_schema_modified", "recall_engine_modified", "production_write_path_modified", "runtime_integration_authorized"])),
        ("productization_and_release_off", protocol["freeze_status"]["productization_authorized"] is False and protocol["freeze_status"]["release_authorized"] is False),
        ("next_stage_inventory_only", protocol["next_authorized_stage"] == NEXT),
    ]
    rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4.2-offline-retrieval-protocol-fixtures-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "fixtures": rows,
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "selected_effect_content_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4.2-offline-retrieval-protocol-freeze-manifest-v1",
        "status": "frozen_before_source_inventory_and_effect_content",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "protocol_artifacts": {
            rel(PROTOCOL_DOC): sha(PROTOCOL_DOC),
            rel(CASE_SCHEMA): sha(CASE_SCHEMA),
            rel(GOLD_SCHEMA): sha(GOLD_SCHEMA),
            rel(ARM_OUTPUT_SCHEMA): sha(ARM_OUTPUT_SCHEMA),
            rel(ENVIRONMENT): sha(ENVIRONMENT),
            rel(PROTOCOL): sha(PROTOCOL),
            rel(FIXTURES): sha(FIXTURES),
        },
        "selected_effect_content_opened": False,
        "independent_source_inventory_constructed": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    fixtures = load(FIXTURES)
    return {
        "schema_version": 1,
        "outcome_id": "phase7.4.2-offline-retrieval-protocol-freeze-outcome-v1",
        "status": "PASS_protocol_frozen_source_inventory_and_sampling_frame_authorized",
        "manifest_sha256": manifest_hash,
        "fixtures_sha256": sha(FIXTURES),
        "fixture_count": fixtures["fixture_count"],
        "failed_fixture_count": fixtures["failed_count"],
        "selected_effect_content_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4.2-offline-retrieval-protocol-v1-frozen",
        "event_type": "immutable_pre_effect_protocol_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "fixtures_sha256": sha(FIXTURES),
        "selected_effect_content_opened": False,
        "source_inventory_constructed": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v3_sha256": sha(STATE_V3),
        "phase7_4_readiness_v3_sha256": sha(READINESS_V3),
        "phase7_4_m0_governance_freeze_receipt_v1_sha256": sha(M0_RECEIPT),
        "phase7_4_offline_retrieval_protocol_document_v1_sha256": sha(PROTOCOL_DOC),
        "phase7_4_offline_retrieval_case_schema_v1_sha256": sha(CASE_SCHEMA),
        "phase7_4_offline_retrieval_gold_schema_v1_sha256": sha(GOLD_SCHEMA),
        "phase7_4_offline_retrieval_arm_output_schema_v1_sha256": sha(ARM_OUTPUT_SCHEMA),
        "phase7_4_offline_retrieval_environment_v1_sha256": sha(ENVIRONMENT),
        "phase7_4_offline_retrieval_protocol_v1_sha256": sha(PROTOCOL),
        "phase7_4_offline_retrieval_protocol_fixtures_v1_sha256": sha(FIXTURES),
        "phase7_4_offline_retrieval_protocol_manifest_v1_sha256": manifest_hash,
        "phase7_4_offline_retrieval_protocol_outcome_v1_sha256": outcome_hash,
        "phase7_4_offline_retrieval_protocol_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 4,
        "state_id": "phase7.4-stage-state-v4",
        "status": "phase7_4_2_offline_retrieval_protocol_frozen_source_inventory_and_sampling_frame_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "phase7_4_offline_retrieval_protocol_frozen": True,
        "independent_source_inventory_constructed": False,
        "sampling_frame_constructed": False,
        "selected_effect_content_opened": False,
        "reference_review_started": False,
        "gold_frozen": False,
        "retrieval_implementation_frozen": False,
        "arm_execution_started": False,
        "effect_scoring_started": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "memory_kind_modification_authorized": False,
        "memory_schema_modification_authorized": False,
        "recall_engine_modification_authorized": False,
        "production_memory_write_authorized": False,
        "runtime_integration_authorized": False,
        "productization_authorized": False,
        "release_authorized": False,
        "next_authorized_stage": NEXT,
    }


def readiness_document(
    manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str
) -> dict[str, Any]:
    return {
        "schema_version": 4,
        "readiness_id": "phase7.4-readiness-v4",
        "status": "PASS_offline_retrieval_protocol_frozen_source_inventory_authorized",
        "artifact_lineage": {
            **lineage(manifest_hash, outcome_hash, audit_hash),
            "phase7_4_stage_state_v4_sha256": state_hash,
        },
        "checks": {
            "m0_lineage_exact": True,
            "rq1_rq2_preregistered": True,
            "schemas_frozen": True,
            "statistics_and_multiplicity_frozen": True,
            "regression_and_cost_thresholds_frozen": True,
            "failure_taxonomy_frozen": True,
            "effect_content_closed": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "source_inventory_and_sampling_frame_authorized": True,
        "selected_effect_content_opening_authorized": False,
        "reference_review_authorized": False,
        "arm_execution_authorized": False,
        "effect_scoring_authorized": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def receipt_document(
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
    state_hash: str,
    readiness_hash: str,
) -> dict[str, Any]:
    fixtures = load(FIXTURES)
    return {
        "schema_version": 1,
        "receipt_id": "phase7.4.2-offline-retrieval-protocol-freeze-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v4_sha256": state_hash,
        "readiness_v4_sha256": readiness_hash,
        "fixture_count": fixtures["fixture_count"],
        "failed_fixture_count": fixtures["failed_count"],
        "selected_effect_content_opened": False,
        "source_inventory_constructed": False,
        "phase7_4_effect_provider_called": False,
        "same_version_semantic_retry_allowed": False,
        "runtime_integration_authorized": False,
        "productization_authorized": False,
        "release_authorized": False,
        "next_authorized_stage": NEXT,
    }


def preflight() -> dict[str, Any]:
    checks = {
        "input_hash:" + rel(path): path.exists() and sha(path) == digest
        for path, digest in EXPECTED.items()
    }
    if all(checks.values()):
        protocol = load(PROTOCOL)
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state": load(STATE_V3)["status"] == ENTRY,
                "entry_gate": protocol["entry_gate"] == ENTRY,
                "next_stage_inventory_only": protocol["next_authorized_stage"] == NEXT,
                "effect_content_closed": protocol["freeze_status"]["selected_effect_content_opened"] is False,
                "provider_not_called": protocol["freeze_status"]["phase7_4_effect_provider_called"] is False,
                "runtime_off": protocol["freeze_status"]["runtime_integration_authorized"] is False,
            }
        )
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def freeze() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    fixture_hash = once(FIXTURES, fixture_document())
    if not load(FIXTURES)["all_fixtures_passed"]:
        raise RuntimeError("protocol_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V4, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(
        READINESS_V4,
        readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
    )
    receipt_hash = once(
        RECEIPT,
        receipt_document(
            manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash
        ),
    )
    return {
        "status": "PASS",
        "fixture_count": load(FIXTURES)["fixture_count"],
        "fixtures_sha256": fixture_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v4_sha256": state_hash,
        "readiness_v4_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "selected_effect_content_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in OUTPUTS}
    if all(checks.values()):
        manifest_hash = sha(MANIFEST)
        outcome_hash = sha(OUTCOME)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V4)
        readiness_hash = sha(READINESS_V4)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(
                    path.exists() and sha(path) == digest for path, digest in EXPECTED.items()
                ),
                "fixtures_replay": load(FIXTURES) == fixture_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
                "audit_replay": AUDIT.read_bytes()
                == (canonical(audit_event(manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
                "state_v4_replay": load(STATE_V4)
                == state_document(manifest_hash, outcome_hash, audit_hash),
                "readiness_v4_replay": load(READINESS_V4)
                == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
                "receipt_replay": load(RECEIPT)
                == receipt_document(
                    manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash
                ),
                "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
                "next_gate_consistent": load(STATE_V4)["next_authorized_stage"]
                == load(READINESS_V4)["next_authorized_stage"]
                == load(RECEIPT)["next_authorized_stage"]
                == NEXT,
                "effect_content_closed": load(STATE_V4)["selected_effect_content_opened"] is False,
                "provider_not_called": load(STATE_V4)["phase7_4_effect_provider_called"] is False,
                "runtime_off": load(STATE_V4)["runtime_integration_authorized"] is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "selected_effect_content_opened": load(STATE_V4).get("selected_effect_content_opened")
        if STATE_V4.exists()
        else None,
        "runtime_integration_authorized": load(STATE_V4).get("runtime_integration_authorized")
        if STATE_V4.exists()
        else None,
        "next_authorized_stage": load(STATE_V4).get("next_authorized_stage")
        if STATE_V4.exists()
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--fixtures", action="store_true")
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        outcome = preflight()
    elif args.fixtures:
        outcome = fixture_document()
    elif args.freeze:
        outcome = freeze()
    else:
        outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
