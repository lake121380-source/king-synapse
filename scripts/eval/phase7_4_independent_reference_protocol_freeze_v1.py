#!/usr/bin/env python3
"""Freeze Phase 7.4 independent Reference protocol, packet, and worklists."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
DATASETS = ROOT / "crates/eval/datasets"
PATTERN = DATASETS / "pattern_extraction"
PHASE_DATA = DATASETS / "phase7_4"
REPORTS = ROOT / "crates/eval/reports"
DOCS = ROOT / "docs"

DOC = DOCS / "eval/PHASE7_4_2_INDEPENDENT_REFERENCE_PROTOCOL.md"
PROMPT = CONFIG / "phase7_4_independent_reference_reviewer_prompt_v1.md"
SUBMISSION_SCHEMA = CONFIG / "phase7_4_independent_reference_submission_schema_v1.json"
PROTOCOL = CONFIG / "phase7_4_independent_reference_protocol_v1.json"
GOLD_SCHEMA = CONFIG / "phase7_4_offline_retrieval_gold_schema_v1.json"
OFFLINE_PROTOCOL = CONFIG / "phase7_4_offline_retrieval_evaluation_protocol_v1.json"
SOURCE = PHASE_DATA / "phase7_4_selected_source_cases_v2.json"
OVERLAYS = PHASE_DATA / "phase7_4_atomic_overlay_dataset_v2.json"
REPRESENTATION = REPORTS / "phase7_4_atomic_segmentation_representation_coverage_gate_v2.json"
SEGMENTATION_RECEIPT = REPORTS / "phase7_4_query_blind_atomic_segmentation_receipt_v2.json"
STATE_V11 = PATTERN / "phase7_4_stage_state_v11.json"
READINESS_V11 = REPORTS / "phase7_4_readiness_v11.json"

PACKET = PHASE_DATA / "phase7_4_independent_reference_blind_packet_v1.json"
WORKLIST_A = PHASE_DATA / "phase7_4_reference_reviewer_a_worklist_v1.json"
WORKLIST_B = PHASE_DATA / "phase7_4_reference_reviewer_b_worklist_v1.json"
FIXTURES = REPORTS / "phase7_4_independent_reference_protocol_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_4_independent_reference_protocol_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_independent_reference_protocol_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_independent_reference_protocol_audit_v1.jsonl"
STATE_V12 = PATTERN / "phase7_4_stage_state_v12.json"
READINESS_V12 = REPORTS / "phase7_4_readiness_v12.json"
RECEIPT = REPORTS / "phase7_4_independent_reference_protocol_receipt_v1.json"

ENTRY_HEAD = "db93ec207f6ac641059a2a14819d4493e4a39735"
ENTRY = "phase7_4_formal_atomic_overlay_v2_representation_gate_passed_reference_protocol_freeze_authorized"
AUTHORIZED = "freeze_phase7_4_independent_reference_protocol_v1"
NEXT = "collect_phase7_4_independent_reference_submissions_v1"

EXPECTED = {
    DOC: "51d5c84e0e7bda32885869cdc0fb022fec4ac0bd144c2694e70aae84f66cfffd",
    PROMPT: "319e6e5737bf4e4fab4a82f197ae18a17a8a152d38d3485f43c5b4dd3311f904",
    SUBMISSION_SCHEMA: "91b59082d39422ab1e9701e5224191eb9c77583cea20cc836da4fb4c198db915",
    PROTOCOL: "32f02e880411a4895f52b5bb390565ff2063d3d0f93ad65fdea26d7995b006fa",
    GOLD_SCHEMA: "7c96fbd29e11b755dd932a0e81348305e40f4d22aabbbf41ec438b8252239f1d",
    OFFLINE_PROTOCOL: "adc48017a40a1ae7685ce5b8868f2bdff623cf845aa845c8ca7e7986ecdac8fb",
    SOURCE: "b06ff2ceb1d300561df937f73a1e9de9d8f5c9d6ca19cb57069b63acc834256d",
    OVERLAYS: "5930c2582ce8ba1cf433567c2b170524b2c8748bd7eaf1f7f0d20e624acc7601",
    REPRESENTATION: "10c53aabde6a5d7ac9b9b4552efe6cf3cc7b1d5ccbe379fa04659a7bcde57102",
    SEGMENTATION_RECEIPT: "5f603efb77c8f4250366cc96896b4216b58c8855fe88d79ea60f3d3209c7f2e6",
    STATE_V11: "131e8d340849580a2cbced92ba9b148905d7f7062292f15e42f3d82a9a80c983",
    READINESS_V11: "44edb29c0658684e03a2c0950e68ac081c1fc39bfe9071c49139ef64270f3d52",
}

OUTPUTS = [
    PACKET,
    WORKLIST_A,
    WORKLIST_B,
    FIXTURES,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V12,
    READINESS_V12,
    RECEIPT,
]


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


def schema_valid() -> bool:
    try:
        Draft202012Validator.check_schema(load(SUBMISSION_SCHEMA))
        return True
    except Exception:
        return False


def packet_atomic_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "atomic_claim_id": unit["atomic_claim_id"],
        "ordinal": unit["ordinal"],
        "claim_text": unit["claim_text"],
        "claim_text_sha256": unit["claim_text_sha256"],
        "source_locator": unit["source_locator"],
        "provenance": unit["provenance"],
    }


def packet_memory(
    memory: dict[str, Any], overlay: dict[str, Any]
) -> dict[str, Any]:
    return {
        "pool_ordinal": memory["pool_ordinal"],
        "source_memory_id": memory["source_memory_id"],
        "source_memory_kind": memory["source_memory_kind"],
        "source_memory_content": memory["source_memory_content"],
        "source_memory_content_sha256": memory["source_memory_content_sha256"],
        "source_memory_sha256": memory["source_memory_sha256"],
        "source_evidence_ids": memory["source_evidence_ids"],
        "source_event_ids": memory["source_event_ids"],
        "atomic_units": [
            packet_atomic_unit(unit)
            for unit in sorted(
                overlay["atomic_units"], key=lambda item: item["ordinal"]
            )
        ],
    }


def packet_document() -> dict[str, Any]:
    source = load(SOURCE)
    overlays = load(OVERLAYS)
    overlay_cases = {
        case["case_id"]: {
            overlay["source_memory_id"]: overlay for overlay in case["overlays"]
        }
        for case in overlays["cases"]
    }
    cases = []
    for case in source["cases"]:
        case_overlays = overlay_cases[case["case_id"]]
        memories = sorted(case["candidate_memories"], key=lambda item: item["pool_ordinal"])
        cases.append(
            {
                "case_id": case["case_id"],
                "query": case["query"],
                "source_events": case["source_events"],
                "source_evidence": case["source_evidence"],
                "candidate_memories": [
                    packet_memory(memory, case_overlays[memory["source_memory_id"]])
                    for memory in memories
                ],
            }
        )
    return {
        "schema_version": 1,
        "packet_id": "phase7.4-independent-reference-blind-packet-v1",
        "status": "frozen_blind_reference_packet_no_labels",
        "source_dataset_sha256": sha(SOURCE),
        "atomic_overlay_dataset_sha256": sha(OVERLAYS),
        "reference_protocol_sha256": sha(PROTOCOL),
        "reviewer_prompt_sha256": sha(PROMPT),
        "case_count": len(cases),
        "memory_count": sum(len(case["candidate_memories"]) for case in cases),
        "atomic_claim_count": sum(len(memory["atomic_units"]) for case in cases for memory in case["candidate_memories"]),
        "cases": cases,
        "authoring_domain_or_variant_present": False,
        "segmentation_placeholder_or_confidence_present": False,
        "reference_or_gold_labels_present": False,
        "arm_or_analysis_output_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
    }


def case_order(seed: int) -> list[str]:
    case_ids = [case["case_id"] for case in load(PACKET)["cases"]]
    return sorted(
        case_ids,
        key=lambda case_id: (
            hb(f"phase7.4-reference|{seed}|{case_id}".encode("utf-8")),
            case_id,
        ),
    )


def worklist_case(case: dict[str, Any]) -> dict[str, Any]:
    claims = []
    for memory in case["candidate_memories"]:
        for unit in memory["atomic_units"]:
            claims.append(
                {
                    "atomic_claim_id": unit["atomic_claim_id"],
                    "source_memory_id": memory["source_memory_id"],
                    "source_locator": unit["source_locator"],
                    "annotation_entered": False,
                }
            )
    return {"case_id": case["case_id"], "claim_worklist": claims}


def worklist_document(role: str, seed: int) -> dict[str, Any]:
    packet_cases = {case["case_id"]: case for case in load(PACKET)["cases"]}
    ordered = case_order(seed)
    return {
        "schema_version": 1,
        "worklist_id": f"phase7.4-independent-reference-{role}-worklist-v1",
        "status": "frozen_before_reviewer_assignment_or_annotation",
        "reviewer_role": role,
        "case_order_seed": seed,
        "case_order_material": f"phase7.4-reference|{seed}|<case_id>",
        "packet_sha256": sha(PACKET),
        "submission_schema_sha256": sha(SUBMISSION_SCHEMA),
        "case_count": len(ordered),
        "claim_count": sum(
            len(memory["atomic_units"])
            for case in packet_cases.values()
            for memory in case["candidate_memories"]
        ),
        "cases": [worklist_case(packet_cases[case_id]) for case_id in ordered],
        "reviewer_identity_assigned": False,
        "annotation_started": False,
        "other_reviewer_output_accessed": False,
        "agreement_computed": False,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
    }


def fixture_document() -> dict[str, Any]:
    packet = load(PACKET)
    worklist_a = load(WORKLIST_A)
    worklist_b = load(WORKLIST_B)
    protocol = load(PROTOCOL)
    state = load(STATE_V11)
    source = load(SOURCE)
    overlays = load(OVERLAYS)
    source_case_ids = [case["case_id"] for case in source["cases"]]
    packet_case_ids = [case["case_id"] for case in packet["cases"]]
    overlay_claim_ids = {
        unit["atomic_claim_id"]
        for case in overlays["cases"]
        for overlay in case["overlays"]
        for unit in overlay["atomic_units"]
    }
    packet_claim_ids = {
        unit["atomic_claim_id"]
        for case in packet["cases"]
        for memory in case["candidate_memories"]
        for unit in memory["atomic_units"]
    }
    forbidden = set(protocol["blind_packet"]["forbidden_fields"])

    def contains_forbidden(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                key in forbidden or contains_forbidden(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(contains_forbidden(item) for item in value)
        return False

    packet_memory_ids = [
        memory["source_memory_id"]
        for case in packet["cases"]
        for memory in case["candidate_memories"]
    ]
    worklist_a_claim_ids = [
        claim["atomic_claim_id"]
        for case in worklist_a["cases"]
        for claim in case["claim_worklist"]
    ]
    worklist_b_claim_ids = [
        claim["atomic_claim_id"]
        for case in worklist_b["cases"]
        for claim in case["claim_worklist"]
    ]
    checks = [
        ("submission_schema_valid", schema_valid()),
        ("packet_replay_exact", packet == packet_document()),
        ("packet_case_count_168", packet["case_count"] == len(packet["cases"]) == 168),
        ("packet_memory_count_1680", packet["memory_count"] == len(packet_memory_ids) == 1680),
        ("packet_claim_count_3360", packet["atomic_claim_count"] == len(packet_claim_ids) == 3360),
        ("packet_case_order_matches_source", packet_case_ids == source_case_ids),
        ("packet_claim_ids_match_overlays", packet_claim_ids == overlay_claim_ids),
        ("memory_ids_unique", len(set(packet_memory_ids)) == 1680),
        ("packet_memory_pool_order_exact", all([memory["pool_ordinal"] for memory in case["candidate_memories"]] == list(range(10)) for case in packet["cases"])),
        ("packet_atomic_order_exact", all([unit["ordinal"] for unit in memory["atomic_units"]] == [0, 1] for case in packet["cases"] for memory in case["candidate_memories"])),
        ("packet_has_no_forbidden_fields", not contains_forbidden(packet)),
        ("packet_blindness_flags_false", all(packet[key] is False for key in ["authoring_domain_or_variant_present", "segmentation_placeholder_or_confidence_present", "reference_or_gold_labels_present", "arm_or_analysis_output_present", "phase7_3_3_d_content_loaded", "provider_called", "selected_effect_dataset_opened_for_arm_execution", "runtime_integration_authorized"])),
        ("worklist_a_replay", worklist_a == worklist_document("reviewer_a", 7402301)),
        ("worklist_b_replay", worklist_b == worklist_document("reviewer_b", 7402302)),
        ("worklists_same_case_set", set(case["case_id"] for case in worklist_a["cases"]) == set(case["case_id"] for case in worklist_b["cases"]) == set(packet_case_ids)),
        ("worklists_distinct_case_order", [case["case_id"] for case in worklist_a["cases"]] != [case["case_id"] for case in worklist_b["cases"]]),
        ("worklist_claim_coverage_exact", set(worklist_a_claim_ids) == set(worklist_b_claim_ids) == packet_claim_ids and len(worklist_a_claim_ids) == len(worklist_b_claim_ids) == 3360),
        ("worklists_unassigned_and_unstarted", all(worklist[key] is False for worklist in [worklist_a, worklist_b] for key in ["reviewer_identity_assigned", "annotation_started", "other_reviewer_output_accessed", "agreement_computed", "provider_called", "selected_effect_dataset_opened_for_arm_execution", "runtime_integration_authorized"])),
        ("entry_state_exact", state["status"] == ENTRY and state["next_authorized_stage"] == AUTHORIZED),
        ("reference_thresholds_match_offline_protocol", protocol["agreement_gate"]["minimum_aggregate_span_f1"] == load(OFFLINE_PROTOCOL)["pre_effect_gates"]["reference_gate"]["minimum_aggregate_span_f1"] and protocol["agreement_gate"]["minimum_aggregate_support_state_cohen_kappa"] == load(OFFLINE_PROTOCOL)["pre_effect_gates"]["reference_gate"]["minimum_aggregate_support_state_cohen_kappa"] and protocol["agreement_gate"]["minimum_stratum_support_state_cohen_kappa"] == load(OFFLINE_PROTOCOL)["pre_effect_gates"]["reference_gate"]["minimum_stratum_support_state_cohen_kappa"]),
        ("independence_requires_three_distinct", protocol["independence"]["distinct_people_or_independent_review_entities_required"] == 3 and protocol["independence"]["same_person_or_model_session_for_a_and_b_allowed"] is False),
        ("review_not_started", state["reference_review_started"] is False),
        ("agreement_adjudication_gold_closed", protocol["authority"]["agreement_execution_authorized"] is False and protocol["authority"]["adjudication_authorized"] is False and protocol["authority"]["gold_freeze_authorized"] is False),
        ("arms_effect_runtime_closed", protocol["authority"]["arm_execution_authorized"] is False and protocol["authority"]["effect_scoring_authorized"] is False and protocol["authority"]["runtime_integration_authorized"] is False),
    ]
    rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4-independent-reference-protocol-fixtures-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "fixtures": rows,
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "case_count": 168,
        "memory_count": 1680,
        "atomic_claim_count": 3360,
        "reviewer_identities_assigned": False,
        "reference_review_started": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4-independent-reference-protocol-manifest-v1",
        "status": "frozen_reference_protocol_packet_and_unassigned_worklists",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {rel(PACKET): sha(PACKET), rel(WORKLIST_A): sha(WORKLIST_A), rel(WORKLIST_B): sha(WORKLIST_B), rel(FIXTURES): sha(FIXTURES)},
        "case_count": 168,
        "memory_count": 1680,
        "atomic_claim_count": 3360,
        "reviewer_identities_assigned": False,
        "reference_review_started": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "outcome_id": "phase7.4-independent-reference-protocol-outcome-v1",
        "status": "PASS_protocol_and_packets_frozen_independent_submission_collection_authorized",
        "manifest_sha256": manifest_hash,
        "packet_sha256": sha(PACKET),
        "worklist_a_sha256": sha(WORKLIST_A),
        "worklist_b_sha256": sha(WORKLIST_B),
        "fixtures_sha256": sha(FIXTURES),
        "independent_reference_submission_collection_authorized": True,
        "reviewer_identities_assigned": False,
        "reference_review_started": False,
        "agreement_execution_authorized": False,
        "gold_freeze_authorized": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-independent-reference-protocol-v1-frozen",
        "event_type": "immutable_reference_protocol_blind_packet_and_unassigned_worklist_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "packet_sha256": sha(PACKET),
        "worklist_a_sha256": sha(WORKLIST_A),
        "worklist_b_sha256": sha(WORKLIST_B),
        "reviewer_identities_assigned": False,
        "reference_review_started": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v11_sha256": sha(STATE_V11),
        "phase7_4_readiness_v11_sha256": sha(READINESS_V11),
        "phase7_4_query_blind_atomic_segmentation_receipt_v2_sha256": sha(SEGMENTATION_RECEIPT),
        "phase7_4_independent_reference_protocol_v1_sha256": sha(PROTOCOL),
        "phase7_4_independent_reference_blind_packet_v1_sha256": sha(PACKET),
        "phase7_4_reference_reviewer_a_worklist_v1_sha256": sha(WORKLIST_A),
        "phase7_4_reference_reviewer_b_worklist_v1_sha256": sha(WORKLIST_B),
        "phase7_4_independent_reference_protocol_fixtures_v1_sha256": sha(FIXTURES),
        "phase7_4_independent_reference_protocol_manifest_v1_sha256": manifest_hash,
        "phase7_4_independent_reference_protocol_outcome_v1_sha256": outcome_hash,
        "phase7_4_independent_reference_protocol_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 12,
        "state_id": "phase7.4-stage-state-v12",
        "status": "phase7_4_independent_reference_protocol_and_packets_frozen_submission_collection_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "source_and_atomic_datasets_frozen": True,
        "representation_and_evidence_coverage_gates_passed": True,
        "blind_reference_packet_frozen": True,
        "reviewer_a_worklist_frozen": True,
        "reviewer_b_worklist_frozen": True,
        "reviewer_identities_assigned": False,
        "distinct_reviewer_count_established": 0,
        "independent_reference_submission_collection_authorized": True,
        "reference_review_started": False,
        "reviewer_a_submission_frozen": False,
        "reviewer_b_submission_frozen": False,
        "agreement_execution_authorized": False,
        "adjudication_authorized": False,
        "gold_freeze_authorized": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "arm_execution_started": False,
        "effect_scoring_started": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "runtime_integration_authorized": False,
        "productization_authorized": False,
        "release_authorized": False,
        "next_authorized_stage": NEXT,
    }


def readiness_document(manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 12,
        "readiness_id": "phase7.4-readiness-v12",
        "status": "PASS_reference_packets_ready_reviewer_assignment_pending",
        "artifact_lineage": {**lineage(manifest_hash, outcome_hash, audit_hash), "phase7_4_stage_state_v12_sha256": state_hash},
        "checks": {
            "blind_packet_exact": True,
            "placeholder_gold_and_arm_fields_absent": True,
            "case_memory_and_claim_counts_exact": True,
            "reviewer_worklists_distinct_order": True,
            "submission_schema_and_prompt_frozen": True,
            "agreement_thresholds_frozen": True,
            "reviewer_identities_unassigned": True,
            "reference_review_not_started": True,
            "effect_dataset_closed_to_arms": True,
            "provider_not_called": True,
            "runtime_not_authorized": True
        },
        "independent_reference_submission_collection_authorized": True,
        "agreement_execution_authorized": False,
        "adjudication_authorized": False,
        "gold_freeze_authorized": False,
        "arm_execution_authorized": False,
        "effect_scoring_authorized": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT
    }


def receipt_document(manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str, readiness_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_id": "phase7.4-independent-reference-protocol-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v12_sha256": state_hash,
        "readiness_v12_sha256": readiness_hash,
        "packet_sha256": sha(PACKET),
        "worklist_a_sha256": sha(WORKLIST_A),
        "worklist_b_sha256": sha(WORKLIST_B),
        "submission_schema_sha256": sha(SUBMISSION_SCHEMA),
        "case_count": 168,
        "memory_count": 1680,
        "atomic_claim_count": 3360,
        "reviewer_identities_assigned": False,
        "independent_reference_submission_collection_authorized": True,
        "agreement_execution_authorized": False,
        "gold_freeze_authorized": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def preflight() -> dict[str, Any]:
    checks = {"input_hash:" + rel(path): path.exists() and sha(path) == digest for path, digest in EXPECTED.items()}
    if all(checks.values()):
        state = load(STATE_V11)
        protocol = load(PROTOCOL)
        checks.update({
            "entry_head_exact": git_head() == ENTRY_HEAD,
            "entry_state_exact": state["status"] == ENTRY,
            "entry_authority_exact": state["next_authorized_stage"] == AUTHORIZED,
            "protocol_entry_exact": protocol["entry_gate"] == AUTHORIZED,
            "protocol_next_exact": protocol["next_authorized_stage_after_pass"] == NEXT,
            "packet_and_worklist_construction_authorized": protocol["authority"]["blind_packet_construction_authorized"] is True and protocol["authority"]["reviewer_worklist_construction_authorized"] is True,
            "reference_not_started": state["reference_review_started"] is False,
            "gold_and_arms_closed": state["gold_frozen"] is False and state["arm_execution_started"] is False,
            "effect_dataset_closed": state["selected_effect_dataset_opened_for_arm_execution"] is False,
            "provider_not_called": state["phase7_4_effect_provider_called"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False,
            "submission_schema_valid": schema_valid(),
        })
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def freeze() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    packet_hash = once(PACKET, packet_document())
    worklist_a_hash = once(WORKLIST_A, worklist_document("reviewer_a", 7402301))
    worklist_b_hash = once(WORKLIST_B, worklist_document("reviewer_b", 7402302))
    fixtures_hash = once(FIXTURES, fixture_document())
    if not load(FIXTURES)["all_fixtures_passed"]:
        raise RuntimeError("independent_reference_protocol_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V12, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(READINESS_V12, readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash))
    receipt_hash = once(RECEIPT, receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash))
    return {
        "status": "PASS",
        "packet_sha256": packet_hash,
        "worklist_a_sha256": worklist_a_hash,
        "worklist_b_sha256": worklist_b_hash,
        "fixtures_sha256": fixtures_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v12_sha256": state_hash,
        "readiness_v12_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "case_count": 168,
        "memory_count": 1680,
        "atomic_claim_count": 3360,
        "reviewer_identities_assigned": False,
        "reference_review_started": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in OUTPUTS}
    if all(checks.values()):
        manifest_hash = sha(MANIFEST)
        outcome_hash = sha(OUTCOME)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V12)
        readiness_hash = sha(READINESS_V12)
        checks.update({
            "entry_head_is_ancestor": entry_head_is_ancestor(),
            "input_hashes": all(path.exists() and sha(path) == digest for path, digest in EXPECTED.items()),
            "packet_replay": load(PACKET) == packet_document(),
            "worklist_a_replay": load(WORKLIST_A) == worklist_document("reviewer_a", 7402301),
            "worklist_b_replay": load(WORKLIST_B) == worklist_document("reviewer_b", 7402302),
            "fixtures_replay": load(FIXTURES) == fixture_document(),
            "manifest_replay": load(MANIFEST) == manifest_document(),
            "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
            "audit_replay": AUDIT.read_bytes() == (canonical(audit_event(manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
            "state_v12_replay": load(STATE_V12) == state_document(manifest_hash, outcome_hash, audit_hash),
            "readiness_v12_replay": load(READINESS_V12) == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
            "receipt_replay": load(RECEIPT) == receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash),
            "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
            "next_gate_consistent": load(STATE_V12)["next_authorized_stage"] == load(READINESS_V12)["next_authorized_stage"] == load(RECEIPT)["next_authorized_stage"] == NEXT,
            "review_not_started": load(STATE_V12)["reference_review_started"] is False,
            "effect_dataset_closed": load(STATE_V12)["selected_effect_dataset_opened_for_arm_execution"] is False,
            "runtime_off": load(STATE_V12)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "reviewer_identities_assigned": load(STATE_V12).get("reviewer_identities_assigned") if STATE_V12.exists() else None,
        "reference_review_started": load(STATE_V12).get("reference_review_started") if STATE_V12.exists() else None,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V12).get("selected_effect_dataset_opened_for_arm_execution") if STATE_V12.exists() else None,
        "runtime_integration_authorized": load(STATE_V12).get("runtime_integration_authorized") if STATE_V12.exists() else None,
        "next_authorized_stage": load(STATE_V12).get("next_authorized_stage") if STATE_V12.exists() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
    elif args.freeze:
        result = freeze()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
