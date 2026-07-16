#!/usr/bin/env python3
"""Freeze the Phase 7.4 selected-source authoring contract and blank plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
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

DOC = DOCS / "eval/PHASE7_4_2_SELECTED_SOURCE_AUTHORING_PROTOCOL.md"
SCHEMA = CONFIG / "phase7_4_source_authoring_case_schema_v1.json"
CONTRACT = CONFIG / "phase7_4_selected_source_authoring_contract_v1.json"
PROTOCOL = CONFIG / "phase7_4_offline_retrieval_evaluation_protocol_v1.json"
BLIND_CASE_SCHEMA = CONFIG / "phase7_4_offline_retrieval_case_schema_v1.json"
STATE_V5 = PATTERN / "phase7_4_stage_state_v5.json"
READINESS_V5 = REPORTS / "phase7_4_readiness_v5.json"
INVENTORY_RECEIPT = REPORTS / "phase7_4_source_inventory_sampling_receipt_v1.json"
SAMPLING = PHASE_DATA / "phase7_4_sampling_frame_v1.json"
SELECTED = PHASE_DATA / "phase7_4_selected_slot_worklist_v1.json"

PLAN = PHASE_DATA / "phase7_4_selected_source_authoring_plan_v1.json"
FIXTURES = REPORTS / "phase7_4_selected_source_authoring_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_4_selected_source_authoring_contract_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_selected_source_authoring_contract_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_selected_source_authoring_contract_audit_v1.jsonl"
STATE_V6 = PATTERN / "phase7_4_stage_state_v6.json"
READINESS_V6 = REPORTS / "phase7_4_readiness_v6.json"
RECEIPT = REPORTS / "phase7_4_selected_source_authoring_contract_receipt_v1.json"

ENTRY_HEAD = "ac8c12ad9a39466ddb9040752edfaf5dd916dcc3"
ENTRY = "phase7_4_content_blind_inventory_and_sampling_frozen_authoring_contract_authorized"
AUTHORIZED = "freeze_phase7_4_selected_source_authoring_contract_v1"
NEXT = "author_phase7_4_selected_source_cases_v1"

EXPECTED = {
    DOC: "3d74f71073702db6f6eac073108ac17efedc26e449beca0f20293ab55849276a",
    SCHEMA: "4ff8342c706bd779e761ce7278556e173c7b8b612cc7150eea23deffbb346630",
    CONTRACT: "d0b7b46c07f946a27ce411d5fc658586563ca4e4001ab4fd607ccb61fa68cc24",
    PROTOCOL: "adc48017a40a1ae7685ce5b8868f2bdff623cf845aa845c8ca7e7986ecdac8fb",
    BLIND_CASE_SCHEMA: "d2a89998a154b0c6e58d10309b263f1199fd1e4efef2cb239243490e4731481f",
    STATE_V5: "36cfa8219a155886b88945f3f5d2ee0e78c121e703e3a564e78510a594944e68",
    READINESS_V5: "9b3a7e2b9b22f62922a4a2192ede7cc5bbd2340fbff338cc274f279352585a3c",
    INVENTORY_RECEIPT: "26474a1e68f39bcb7de69e0a08fa768a93ebc07652426750099be5fc05b3c997",
    SAMPLING: "11c6f245abcf71e566775d74026bc8df0ea7482e149186ec5dd6c16f9b63349b",
    SELECTED: "c4a080694d5b12d12694a7bb2084d486a02a2c690f90e6b07cf1326a198afcfa",
}

OUTPUTS = [
    PLAN,
    FIXTURES,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V6,
    READINESS_V6,
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


def validate_schema() -> bool:
    try:
        Draft202012Validator.check_schema(load(SCHEMA))
        return True
    except Exception:
        return False


def pool_key(case_id: str, memory_id: str) -> str:
    material = f"phase7.4|7402201|{case_id}|{memory_id}"
    return hb(material.encode("utf-8"))


def memory_slots(case_id: str, selection_rank: int) -> list[dict[str, Any]]:
    kinds = ["fact", "preference", "failure", "playbook", "state"]
    slots = []
    for ordinal in range(1, 11):
        memory_id = f"{case_id}-memory-{ordinal:02d}"
        slots.append(
            {
                "memory_authoring_ordinal": ordinal,
                "source_memory_id": memory_id,
                "source_memory_kind": kinds[
                    (ordinal - 1 + selection_rank - 1) % len(kinds)
                ],
                "candidate_pool_key_sha256": pool_key(case_id, memory_id),
            }
        )
    ordered = sorted(
        slots,
        key=lambda row: (
            row["candidate_pool_key_sha256"],
            row["source_memory_id"],
        ),
    )
    pool_ordinals = {
        row["source_memory_id"]: ordinal for ordinal, row in enumerate(ordered)
    }
    for slot in slots:
        slot["pool_ordinal"] = pool_ordinals[slot["source_memory_id"]]
    return slots


def case_plan(row: dict[str, Any]) -> dict[str, Any]:
    contract = load(CONTRACT)
    case_id = row["case_id"]
    rank = row["selection_rank_within_stratum"]
    domains = contract["selected_case_design"]["domains"]
    return {
        "case_id": case_id,
        "stratum": row["stratum"],
        "selection_rank_within_stratum": rank,
        "selection_key_sha256": row["selection_key_sha256"],
        "domain": domains[(rank - 1) % len(domains)],
        "scenario_variant": (rank - 1) // len(domains) + 1,
        "query_slot": {"query_id": f"{case_id}-query-01"},
        "entity_slots": [
            {"entity_id": f"{case_id}-entity-{ordinal:02d}"}
            for ordinal in range(1, 5)
        ],
        "source_event_slots": [
            {
                "source_event_id": f"{case_id}-event-{ordinal:02d}",
                "logical_time": ordinal,
            }
            for ordinal in range(1, 7)
        ],
        "source_evidence_slots": [
            {"source_evidence_id": f"{case_id}-evidence-{ordinal:02d}"}
            for ordinal in range(1, 9)
        ],
        "candidate_memory_slots": memory_slots(case_id, rank),
        "content_status": {
            "query_authored": False,
            "entity_names_authored": False,
            "event_descriptions_authored": False,
            "evidence_text_authored": False,
            "memory_content_authored": False,
            "atomic_overlay_constructed": False,
            "reference_review_started": False,
            "gold_frozen": False,
            "arm_execution_started": False,
        },
    }


def plan_document() -> dict[str, Any]:
    selected = load(SELECTED)["selected_slots"]
    cases = [case_plan(row) for row in selected]
    return {
        "schema_version": 1,
        "plan_id": "phase7.4-selected-source-authoring-plan-v1",
        "status": "frozen_blank_authoring_plan_no_source_text",
        "selected_worklist_sha256": sha(SELECTED),
        "sampling_frame_sha256": sha(SAMPLING),
        "authoring_contract_sha256": sha(CONTRACT),
        "source_case_schema_sha256": sha(SCHEMA),
        "selected_case_count": len(cases),
        "query_slot_count": len(cases),
        "entity_slot_count": len(cases) * 4,
        "source_event_slot_count": len(cases) * 6,
        "source_evidence_slot_count": len(cases) * 8,
        "candidate_memory_slot_count": len(cases) * 10,
        "candidate_pool_seed": 7402201,
        "cases": cases,
        "source_content_authored": False,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
    }


def fixture_document() -> dict[str, Any]:
    plan = load(PLAN)
    contract = load(CONTRACT)
    selected = load(SELECTED)["selected_slots"]
    state = load(STATE_V5)
    cases = plan["cases"]
    selected_ids = [row["case_id"] for row in selected]
    case_ids = [case["case_id"] for case in cases]
    strata = Counter(case["stratum"] for case in cases)
    domain_strata = Counter((case["stratum"], case["domain"]) for case in cases)
    design_cells = Counter(
        (case["stratum"], case["domain"], case["scenario_variant"])
        for case in cases
    )
    entity_ids = [
        slot["entity_id"] for case in cases for slot in case["entity_slots"]
    ]
    event_ids = [
        slot["source_event_id"]
        for case in cases
        for slot in case["source_event_slots"]
    ]
    evidence_ids = [
        slot["source_evidence_id"]
        for case in cases
        for slot in case["source_evidence_slots"]
    ]
    memory_ids = [
        slot["source_memory_id"]
        for case in cases
        for slot in case["candidate_memory_slots"]
    ]
    forbidden = set(contract["forbidden_authored_fields"]) | {
        "query",
        "text",
        "display_name",
        "description",
        "observed_text",
        "source_memory_content",
    }

    def contains_forbidden(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                key in forbidden or contains_forbidden(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(contains_forbidden(item) for item in value)
        return False

    checks = [
        ("source_case_schema_valid", validate_schema()),
        ("selected_case_count_168", len(cases) == plan["selected_case_count"] == 168),
        ("selected_worklist_order_exact", case_ids == selected_ids),
        ("selected_case_ids_unique", len(set(case_ids)) == 168),
        ("eight_strata", len(strata) == 8),
        ("twenty_one_cases_per_stratum", set(strata.values()) == {21}),
        ("three_cases_per_domain_per_stratum", set(domain_strata.values()) == {3}),
        ("one_case_per_design_cell", len(design_cells) == 168 and set(design_cells.values()) == {1}),
        ("scenario_variants_exact", {case["scenario_variant"] for case in cases} == {1, 2, 3}),
        ("query_slot_count_168", plan["query_slot_count"] == 168),
        ("four_entity_slots_per_case", all(len(case["entity_slots"]) == 4 for case in cases)),
        ("entity_slot_count_672", plan["entity_slot_count"] == len(entity_ids) == 672),
        ("entity_ids_unique", len(set(entity_ids)) == len(entity_ids)),
        ("six_event_slots_per_case", all(len(case["source_event_slots"]) == 6 for case in cases)),
        ("event_slot_count_1008", plan["source_event_slot_count"] == len(event_ids) == 1008),
        ("event_ids_unique", len(set(event_ids)) == len(event_ids)),
        ("event_logical_times_exact", all([slot["logical_time"] for slot in case["source_event_slots"]] == list(range(1, 7)) for case in cases)),
        ("eight_evidence_slots_per_case", all(len(case["source_evidence_slots"]) == 8 for case in cases)),
        ("evidence_slot_count_1344", plan["source_evidence_slot_count"] == len(evidence_ids) == 1344),
        ("evidence_ids_unique", len(set(evidence_ids)) == len(evidence_ids)),
        ("ten_memory_slots_per_case", all(len(case["candidate_memory_slots"]) == 10 for case in cases)),
        ("memory_slot_count_1680", plan["candidate_memory_slot_count"] == len(memory_ids) == 1680),
        ("memory_ids_unique", len(set(memory_ids)) == len(memory_ids)),
        ("two_of_each_memory_kind_per_case", all(set(Counter(slot["source_memory_kind"] for slot in case["candidate_memory_slots"]).values()) == {2} and len(Counter(slot["source_memory_kind"] for slot in case["candidate_memory_slots"])) == 5 for case in cases)),
        ("pool_ordinals_exact_per_case", all(sorted(slot["pool_ordinal"] for slot in case["candidate_memory_slots"]) == list(range(10)) for case in cases)),
        ("pool_keys_replay", all(slot["candidate_pool_key_sha256"] == pool_key(case["case_id"], slot["source_memory_id"]) for case in cases for slot in case["candidate_memory_slots"])),
        ("plan_replay_exact", plan == plan_document()),
        ("no_authored_content_or_forbidden_fields", not contains_forbidden(plan)),
        ("all_case_content_flags_false", all(not any(case["content_status"].values()) for case in cases)),
        ("top_level_content_flags_false", all(plan[key] is False for key in ["source_content_authored", "gold_or_reference_labels_present", "atomic_overlay_present", "arm_output_present", "phase7_3_3_d_content_loaded", "provider_called", "selected_effect_dataset_opened_for_arm_execution", "runtime_integration_authorized"])),
        ("entry_state_exact", state["status"] == ENTRY and state["next_authorized_stage"] == AUTHORIZED),
        ("contract_next_authoring_only", contract["next_authorized_stage_after_pass"] == NEXT),
        ("reserve_use_closed", contract["selected_case_design"]["reserve_case_use_allowed"] is False),
        ("reference_and_gold_closed", contract["authority"]["reference_review_authorized"] is False and contract["authority"]["gold_freeze_authorized"] is False),
        ("arm_and_effect_closed", contract["authority"]["arm_execution_authorized"] is False and contract["authority"]["effect_scoring_authorized"] is False),
        ("provider_closed", contract["authority"]["provider_call_authorized"] is False),
        ("runtime_product_release_closed", all(contract["authority"][key] is False for key in ["runtime_integration_authorized", "productization_authorized", "release_authorized"])),
    ]
    rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4-selected-source-authoring-contract-fixtures-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "fixtures": rows,
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "source_content_authored": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4-selected-source-authoring-contract-manifest-v1",
        "status": "frozen_blank_authoring_plan_and_contract",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {
            rel(PLAN): sha(PLAN),
            rel(FIXTURES): sha(FIXTURES),
        },
        "selected_case_count": 168,
        "candidate_memory_slot_count": 1680,
        "source_content_authored": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "outcome_id": "phase7.4-selected-source-authoring-contract-outcome-v1",
        "status": "PASS_authoring_contract_frozen_selected_source_authoring_authorized",
        "manifest_sha256": manifest_hash,
        "authoring_plan_sha256": sha(PLAN),
        "fixtures_sha256": sha(FIXTURES),
        "selected_case_count": 168,
        "source_content_authored": False,
        "selected_source_content_authoring_authorized": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-selected-source-authoring-contract-v1-frozen",
        "event_type": "immutable_authoring_contract_and_blank_plan_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "authoring_contract_sha256": sha(CONTRACT),
        "authoring_plan_sha256": sha(PLAN),
        "source_content_authored": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v5_sha256": sha(STATE_V5),
        "phase7_4_readiness_v5_sha256": sha(READINESS_V5),
        "phase7_4_source_inventory_sampling_receipt_v1_sha256": sha(INVENTORY_RECEIPT),
        "phase7_4_selected_source_authoring_protocol_sha256": sha(DOC),
        "phase7_4_source_authoring_case_schema_v1_sha256": sha(SCHEMA),
        "phase7_4_selected_source_authoring_contract_v1_sha256": sha(CONTRACT),
        "phase7_4_selected_source_authoring_plan_v1_sha256": sha(PLAN),
        "phase7_4_selected_source_authoring_contract_fixtures_v1_sha256": sha(FIXTURES),
        "phase7_4_selected_source_authoring_contract_manifest_v1_sha256": manifest_hash,
        "phase7_4_selected_source_authoring_contract_outcome_v1_sha256": outcome_hash,
        "phase7_4_selected_source_authoring_contract_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 6,
        "state_id": "phase7.4-stage-state-v6",
        "status": "phase7_4_selected_source_authoring_contract_frozen_source_authoring_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "source_slot_inventory_frozen": True,
        "sampling_frame_frozen": True,
        "selected_slot_worklist_frozen": True,
        "selected_source_authoring_contract_frozen": True,
        "selected_source_blank_authoring_plan_frozen": True,
        "selected_case_count": 168,
        "candidate_memory_slot_count": 1680,
        "selected_source_content_authoring_authorized": True,
        "selected_source_content_authored": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "atomic_segmentation_authorized": False,
        "reference_review_started": False,
        "gold_frozen": False,
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
        "schema_version": 6,
        "readiness_id": "phase7.4-readiness-v6",
        "status": "PASS_selected_source_authoring_contract_frozen",
        "artifact_lineage": {
            **lineage(manifest_hash, outcome_hash, audit_hash),
            "phase7_4_stage_state_v6_sha256": state_hash,
        },
        "checks": {
            "selected_worklist_exact": True,
            "domain_and_variant_balance_frozen": True,
            "identity_and_pool_order_frozen": True,
            "source_case_schema_frozen": True,
            "blank_plan_contains_no_source_text": True,
            "gold_atomic_and_arm_fields_absent": True,
            "effect_dataset_closed_to_arms": True,
            "phase7_3_3_d_content_not_loaded": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "selected_source_content_authoring_authorized": True,
        "atomic_segmentation_authorized": False,
        "reference_review_authorized": False,
        "selected_effect_dataset_opening_for_arm_execution_authorized": False,
        "arm_execution_authorized": False,
        "effect_scoring_authorized": False,
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
    return {
        "schema_version": 1,
        "receipt_id": "phase7.4-selected-source-authoring-contract-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v6_sha256": state_hash,
        "readiness_v6_sha256": readiness_hash,
        "authoring_contract_sha256": sha(CONTRACT),
        "source_case_schema_sha256": sha(SCHEMA),
        "authoring_plan_sha256": sha(PLAN),
        "selected_case_count": 168,
        "candidate_memory_slot_count": 1680,
        "source_content_authored": False,
        "selected_source_content_authoring_authorized": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def preflight() -> dict[str, Any]:
    checks = {
        "input_hash:" + rel(path): path.exists() and sha(path) == digest
        for path, digest in EXPECTED.items()
    }
    if all(checks.values()):
        state = load(STATE_V5)
        contract = load(CONTRACT)
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state_exact": state["status"] == ENTRY,
                "entry_authority_exact": state["next_authorized_stage"] == AUTHORIZED,
                "contract_entry_exact": contract["entry_gate"] == AUTHORIZED,
                "contract_next_authoring_only": contract["next_authorized_stage_after_pass"] == NEXT,
                "source_schema_valid": validate_schema(),
                "source_content_not_yet_authored": state["source_content_authored"] is False,
                "effect_content_closed": state["selected_effect_content_opened"] is False,
                "provider_not_called": state["phase7_4_effect_provider_called"] is False,
                "runtime_off": state["runtime_integration_authorized"] is False,
            }
        )
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def freeze() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    plan_hash = once(PLAN, plan_document())
    fixtures_hash = once(FIXTURES, fixture_document())
    if not load(FIXTURES)["all_fixtures_passed"]:
        raise RuntimeError("selected_source_authoring_contract_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V6, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(
        READINESS_V6,
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
        "authoring_plan_sha256": plan_hash,
        "fixtures_sha256": fixtures_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v6_sha256": state_hash,
        "readiness_v6_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "selected_case_count": 168,
        "candidate_memory_slot_count": 1680,
        "source_content_authored": False,
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
        state_hash = sha(STATE_V6)
        readiness_hash = sha(READINESS_V6)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(path.exists() and sha(path) == digest for path, digest in EXPECTED.items()),
                "plan_replay": load(PLAN) == plan_document(),
                "fixtures_replay": load(FIXTURES) == fixture_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
                "audit_replay": AUDIT.read_bytes() == (canonical(audit_event(manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
                "state_v6_replay": load(STATE_V6) == state_document(manifest_hash, outcome_hash, audit_hash),
                "readiness_v6_replay": load(READINESS_V6) == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
                "receipt_replay": load(RECEIPT) == receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash),
                "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
                "next_gate_consistent": load(STATE_V6)["next_authorized_stage"] == load(READINESS_V6)["next_authorized_stage"] == load(RECEIPT)["next_authorized_stage"] == NEXT,
                "source_content_not_authored": load(STATE_V6)["selected_source_content_authored"] is False,
                "effect_dataset_closed_to_arms": load(STATE_V6)["selected_effect_dataset_opened_for_arm_execution"] is False,
                "provider_not_called": load(STATE_V6)["phase7_4_effect_provider_called"] is False,
                "runtime_off": load(STATE_V6)["runtime_integration_authorized"] is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "source_content_authored": load(STATE_V6).get("selected_source_content_authored") if STATE_V6.exists() else None,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V6).get("selected_effect_dataset_opened_for_arm_execution") if STATE_V6.exists() else None,
        "runtime_integration_authorized": load(STATE_V6).get("runtime_integration_authorized") if STATE_V6.exists() else None,
        "next_authorized_stage": load(STATE_V6).get("next_authorized_stage") if STATE_V6.exists() else None,
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
