#!/usr/bin/env python3
"""Construct the Phase 7.4 content-blind source inventory and sampling frame."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
DATASETS = ROOT / "crates/eval/datasets"
PATTERN = DATASETS / "pattern_extraction"
PHASE_DATA = DATASETS / "phase7_4"
REPORTS = ROOT / "crates/eval/reports"
DOCS = ROOT / "docs"

DOC = DOCS / "eval/PHASE7_4_2_SOURCE_INVENTORY_AND_SAMPLING_FRAME.md"
CONTRACT = CONFIG / "phase7_4_source_inventory_sampling_contract_v1.json"
PROTOCOL = CONFIG / "phase7_4_offline_retrieval_evaluation_protocol_v1.json"
STATE_V4 = PATTERN / "phase7_4_stage_state_v4.json"
READINESS_V4 = REPORTS / "phase7_4_readiness_v4.json"
PROTOCOL_RECEIPT = REPORTS / "phase7_4_offline_retrieval_protocol_freeze_receipt_v1.json"

INVENTORY = PHASE_DATA / "phase7_4_source_slot_inventory_v1.json"
SAMPLING = PHASE_DATA / "phase7_4_sampling_frame_v1.json"
SELECTED = PHASE_DATA / "phase7_4_selected_slot_worklist_v1.json"
FIXTURES = REPORTS / "phase7_4_source_inventory_sampling_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_4_source_inventory_sampling_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_source_inventory_sampling_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_source_inventory_sampling_audit_v1.jsonl"
STATE_V5 = PATTERN / "phase7_4_stage_state_v5.json"
READINESS_V5 = REPORTS / "phase7_4_readiness_v5.json"
RECEIPT = REPORTS / "phase7_4_source_inventory_sampling_receipt_v1.json"

ENTRY_HEAD = "4bbb6ab667cc56ba1363cd148bf3f9310dabf48d"
ENTRY = "phase7_4_2_offline_retrieval_protocol_frozen_source_inventory_and_sampling_frame_authorized"
AUTHORIZED = "construct_phase7_4_independent_source_inventory_and_sampling_frame_v1"
NEXT = "freeze_phase7_4_selected_source_authoring_contract_v1"

EXPECTED = {
    DOC: "9de3e0339d8897ba1b22c60fbb74078a01caa2cd31141e34f6a3414e57e19a54",
    CONTRACT: "7f219419c53858b5ee618b77d73f08e44c1045f01bf55794f2da23953b007a48",
    PROTOCOL: "adc48017a40a1ae7685ce5b8868f2bdff623cf845aa845c8ca7e7986ecdac8fb",
    STATE_V4: "85350ee78464988545d08c450dbce61f34508f4349a3d7fee87f8367d7f1db08",
    READINESS_V4: "4fff7fb54306e58b8ed06c369768a8ea9894d81c265e4887db7c9266ccab2cc8",
    PROTOCOL_RECEIPT: "5a9d2897a3a9dbadc0a87c67798bda821c5bc24578176b1fdada7c08770ffda5",
}

OUTPUTS = [
    INVENTORY,
    SAMPLING,
    SELECTED,
    FIXTURES,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V5,
    READINESS_V5,
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
    return run(["git", "merge-base", "--is-ancestor", ENTRY_HEAD, git_head()]).returncode == 0


def empty_content_status() -> dict[str, bool]:
    return {
        "query_authored": False,
        "memory_content_authored": False,
        "evidence_content_authored": False,
        "atomic_overlay_constructed": False,
        "reference_review_started": False,
        "gold_frozen": False,
        "selected_effect_content_opened": False,
    }


def slot_rows() -> list[dict[str, Any]]:
    rows = []
    contract = load(CONTRACT)
    for item in contract["strata"]:
        for ordinal in range(1, contract["inventory"]["slot_count_per_stratum"] + 1):
            rows.append(
                {
                    "case_id": f"p74-{item['code']}-{ordinal:03d}",
                    "stratum": item["stratum"],
                    "stratum_code": item["code"],
                    "stratum_ordinal": ordinal,
                    "source_namespace": contract["inventory"]["source_namespace"],
                    "content_status": empty_content_status(),
                    "phase7_3_3_d_lineage_used": False,
                }
            )
    return rows


def inventory_document() -> dict[str, Any]:
    rows = slot_rows()
    return {
        "schema_version": 1,
        "inventory_id": "phase7.4-independent-source-slot-inventory-v1",
        "status": "frozen_content_blind_slot_inventory",
        "source_namespace": "phase7_4_independent_v1",
        "slot_count": len(rows),
        "stratum_count": 8,
        "slot_count_per_stratum": 30,
        "slots": rows,
        "query_content_present": False,
        "memory_content_present": False,
        "evidence_content_present": False,
        "atomic_overlay_present": False,
        "gold_or_review_label_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }


def selection_key(stratum: str, case_id: str) -> str:
    material = f"phase7.4|7402101|{stratum}|{case_id}"
    return hb(material.encode("utf-8"))


def sampling_rows() -> list[dict[str, Any]]:
    by_stratum: dict[str, list[dict[str, Any]]] = {}
    for slot in slot_rows():
        by_stratum.setdefault(slot["stratum"], []).append(slot)
    rows = []
    stratum_order = [item["stratum"] for item in load(CONTRACT)["strata"]]
    for stratum in stratum_order:
        ordered = sorted(
            by_stratum[stratum],
            key=lambda slot: (selection_key(stratum, slot["case_id"]), slot["case_id"]),
        )
        for rank, slot in enumerate(ordered, start=1):
            rows.append(
                {
                    "case_id": slot["case_id"],
                    "stratum": stratum,
                    "selection_key_sha256": selection_key(stratum, slot["case_id"]),
                    "selection_rank_within_stratum": rank,
                    "role": "selected" if rank <= 21 else "reserve",
                    "content_status": empty_content_status(),
                }
            )
    return rows


def sampling_document() -> dict[str, Any]:
    rows = sampling_rows()
    return {
        "schema_version": 1,
        "sampling_frame_id": "phase7.4-content-blind-sampling-frame-v1",
        "status": "frozen_before_source_content_authoring",
        "inventory_sha256": sha(INVENTORY),
        "selection_seed": 7402101,
        "selection_material": "phase7.4|7402101|<stratum>|<case_id>",
        "selection_order": [
            "selection_key_sha256_ascending",
            "case_id_ascending",
        ],
        "slot_count": len(rows),
        "selected_count": sum(row["role"] == "selected" for row in rows),
        "reserve_count": sum(row["role"] == "reserve" for row in rows),
        "rows": rows,
        "reserve_replacement_after_content_authoring_allowed": False,
        "same_version_reselection_allowed": False,
        "selected_effect_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }


def selected_document() -> dict[str, Any]:
    selected = [row for row in sampling_rows() if row["role"] == "selected"]
    return {
        "schema_version": 1,
        "worklist_id": "phase7.4-selected-source-slot-worklist-v1",
        "status": "frozen_selected_slots_content_not_authored",
        "inventory_sha256": sha(INVENTORY),
        "sampling_frame_sha256": sha(SAMPLING),
        "selected_slot_count": len(selected),
        "selected_slots": selected,
        "query_content_present": False,
        "memory_content_present": False,
        "evidence_content_present": False,
        "atomic_overlay_present": False,
        "gold_or_review_label_present": False,
        "selected_effect_content_opened": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }


def fixture_document() -> dict[str, Any]:
    inventory = load(INVENTORY)
    sampling = load(SAMPLING)
    selected = load(SELECTED)
    slots = inventory["slots"]
    rows = sampling["rows"]
    selected_rows = [row for row in rows if row["role"] == "selected"]
    reserve_rows = [row for row in rows if row["role"] == "reserve"]
    slot_strata = Counter(slot["stratum"] for slot in slots)
    selected_strata = Counter(row["stratum"] for row in selected_rows)
    reserve_strata = Counter(row["stratum"] for row in reserve_rows)
    forbidden_fields = {
        "query",
        "source_memory_content",
        "claim_text",
        "support_state",
        "gold_label",
        "expected_answer",
        "arm_output",
    }

    def contains_forbidden(value: Any) -> bool:
        if isinstance(value, dict):
            return any(key in forbidden_fields or contains_forbidden(item) for key, item in value.items())
        if isinstance(value, list):
            return any(contains_forbidden(item) for item in value)
        return False

    expected_rows = sampling_rows()
    checks = [
        ("inventory_count_240", inventory["slot_count"] == len(slots) == 240),
        ("eight_strata", len(slot_strata) == 8),
        ("thirty_slots_per_stratum", set(slot_strata.values()) == {30}),
        ("case_ids_unique", len({slot["case_id"] for slot in slots}) == 240),
        ("case_ids_match_namespace", all(re.fullmatch(r"p74-(tu|co|pe|fl|cr|me|ub|al)-\d{3}", slot["case_id"]) for slot in slots)),
        ("source_namespace_exact", all(slot["source_namespace"] == "phase7_4_independent_v1" for slot in slots)),
        ("slot_ordinals_complete", all(sorted(slot["stratum_ordinal"] for slot in slots if slot["stratum"] == stratum) == list(range(1, 31)) for stratum in slot_strata)),
        ("sampling_covers_inventory", {row["case_id"] for row in rows} == {slot["case_id"] for slot in slots}),
        ("sampling_replay_exact", rows == expected_rows),
        ("selection_keys_unique", len({row["selection_key_sha256"] for row in rows}) == 240),
        ("selected_count_168", sampling["selected_count"] == len(selected_rows) == 168),
        ("reserve_count_72", sampling["reserve_count"] == len(reserve_rows) == 72),
        ("selected_21_per_stratum", set(selected_strata.values()) == {21}),
        ("reserve_9_per_stratum", set(reserve_strata.values()) == {9}),
        ("selected_worklist_exact", selected["selected_slots"] == selected_rows),
        ("selected_worklist_count", selected["selected_slot_count"] == 168),
        ("no_forbidden_content_fields", not contains_forbidden(inventory) and not contains_forbidden(sampling) and not contains_forbidden(selected)),
        ("all_content_status_false", all(not any(slot["content_status"].values()) for slot in slots) and all(not any(row["content_status"].values()) for row in rows)),
        ("inventory_content_flags_false", all(inventory[key] is False for key in ["query_content_present", "memory_content_present", "evidence_content_present", "atomic_overlay_present", "gold_or_review_label_present"])),
        ("selected_content_flags_false", all(selected[key] is False for key in ["query_content_present", "memory_content_present", "evidence_content_present", "atomic_overlay_present", "gold_or_review_label_present", "selected_effect_content_opened"])),
        ("phase7_3_content_not_loaded", inventory["phase7_3_3_d_content_loaded"] is False and selected["phase7_3_3_d_content_loaded"] is False),
        ("reserve_replacement_closed", sampling["reserve_replacement_after_content_authoring_allowed"] is False),
        ("same_version_reselection_closed", sampling["same_version_reselection_allowed"] is False),
        ("provider_not_called", inventory["provider_called"] is False and sampling["provider_called"] is False and selected["provider_called"] is False),
        ("runtime_not_authorized", inventory["runtime_integration_authorized"] is False and sampling["runtime_integration_authorized"] is False and selected["runtime_integration_authorized"] is False),
    ]
    fixture_rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4-source-inventory-sampling-fixtures-v1",
        "status": "PASS" if all(row["passed"] for row in fixture_rows) else "FAIL",
        "fixture_count": len(fixture_rows),
        "passed_count": sum(row["passed"] for row in fixture_rows),
        "failed_count": sum(not row["passed"] for row in fixture_rows),
        "fixtures": fixture_rows,
        "all_fixtures_passed": all(row["passed"] for row in fixture_rows),
        "selected_effect_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4-source-inventory-sampling-manifest-v1",
        "status": "frozen_content_blind_inventory_and_sampling_frame",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {
            rel(INVENTORY): sha(INVENTORY),
            rel(SAMPLING): sha(SAMPLING),
            rel(SELECTED): sha(SELECTED),
            rel(FIXTURES): sha(FIXTURES),
        },
        "slot_count": 240,
        "selected_count": 168,
        "reserve_count": 72,
        "content_authored": False,
        "selected_effect_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "outcome_id": "phase7.4-source-inventory-sampling-outcome-v1",
        "status": "PASS_content_blind_selection_frozen_authoring_contract_authorized",
        "manifest_sha256": manifest_hash,
        "inventory_sha256": sha(INVENTORY),
        "sampling_frame_sha256": sha(SAMPLING),
        "selected_worklist_sha256": sha(SELECTED),
        "fixtures_sha256": sha(FIXTURES),
        "slot_count": 240,
        "selected_count": 168,
        "reserve_count": 72,
        "content_authored": False,
        "selected_effect_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-source-inventory-sampling-v1-frozen",
        "event_type": "immutable_content_blind_selection_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "inventory_sha256": sha(INVENTORY),
        "sampling_frame_sha256": sha(SAMPLING),
        "selected_worklist_sha256": sha(SELECTED),
        "content_authored": False,
        "effect_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v4_sha256": sha(STATE_V4),
        "phase7_4_readiness_v4_sha256": sha(READINESS_V4),
        "phase7_4_offline_retrieval_protocol_receipt_v1_sha256": sha(PROTOCOL_RECEIPT),
        "phase7_4_source_inventory_sampling_contract_v1_sha256": sha(CONTRACT),
        "phase7_4_source_slot_inventory_v1_sha256": sha(INVENTORY),
        "phase7_4_sampling_frame_v1_sha256": sha(SAMPLING),
        "phase7_4_selected_slot_worklist_v1_sha256": sha(SELECTED),
        "phase7_4_source_inventory_sampling_fixtures_v1_sha256": sha(FIXTURES),
        "phase7_4_source_inventory_sampling_manifest_v1_sha256": manifest_hash,
        "phase7_4_source_inventory_sampling_outcome_v1_sha256": outcome_hash,
        "phase7_4_source_inventory_sampling_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 5,
        "state_id": "phase7.4-stage-state-v5",
        "status": "phase7_4_content_blind_inventory_and_sampling_frozen_authoring_contract_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "source_slot_inventory_frozen": True,
        "sampling_frame_frozen": True,
        "selected_slot_worklist_frozen": True,
        "source_slot_count": 240,
        "selected_slot_count": 168,
        "reserve_slot_count": 72,
        "source_content_authored": False,
        "selected_effect_content_opened": False,
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
        "schema_version": 5,
        "readiness_id": "phase7.4-readiness-v5",
        "status": "PASS_content_blind_sampling_frozen_authoring_contract_authorized",
        "artifact_lineage": {
            **lineage(manifest_hash, outcome_hash, audit_hash),
            "phase7_4_stage_state_v5_sha256": state_hash,
        },
        "checks": {
            "inventory_count_and_strata_exact": True,
            "selection_deterministic": True,
            "selected_and_reserve_counts_exact": True,
            "selection_content_blind": True,
            "phase7_3_3_d_content_not_loaded": True,
            "effect_content_closed": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "selected_source_authoring_contract_freeze_authorized": True,
        "source_content_authoring_authorized": False,
        "selected_effect_content_opening_authorized": False,
        "reference_review_authorized": False,
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
        "receipt_id": "phase7.4-source-inventory-sampling-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v5_sha256": state_hash,
        "readiness_v5_sha256": readiness_hash,
        "inventory_sha256": sha(INVENTORY),
        "sampling_frame_sha256": sha(SAMPLING),
        "selected_worklist_sha256": sha(SELECTED),
        "slot_count": 240,
        "selected_count": 168,
        "reserve_count": 72,
        "content_authored": False,
        "selected_effect_content_opened": False,
        "provider_called": False,
        "same_version_reselection_allowed": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def preflight() -> dict[str, Any]:
    checks = {
        "input_hash:" + rel(path): path.exists() and sha(path) == digest
        for path, digest in EXPECTED.items()
    }
    if all(checks.values()):
        state = load(STATE_V4)
        contract = load(CONTRACT)
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state": state["status"] == ENTRY,
                "entry_authority": state["next_authorized_stage"] == AUTHORIZED,
                "contract_entry": contract["entry_gate"] == AUTHORIZED,
                "next_stage_authoring_contract_only": contract["next_authorized_stage_after_pass"] == NEXT,
                "content_not_authorized": contract["authority"]["source_content_authoring_authorized"] is False,
                "effect_content_closed": contract["authority"]["selected_effect_content_opening_authorized"] is False,
                "runtime_off": contract["authority"]["runtime_integration_authorized"] is False,
            }
        )
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def construct() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    inventory_hash = once(INVENTORY, inventory_document())
    sampling_hash = once(SAMPLING, sampling_document())
    selected_hash = once(SELECTED, selected_document())
    fixtures_hash = once(FIXTURES, fixture_document())
    if not load(FIXTURES)["all_fixtures_passed"]:
        raise RuntimeError("inventory_sampling_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V5, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(
        READINESS_V5,
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
        "inventory_sha256": inventory_hash,
        "sampling_frame_sha256": sampling_hash,
        "selected_worklist_sha256": selected_hash,
        "fixtures_sha256": fixtures_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v5_sha256": state_hash,
        "readiness_v5_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "slot_count": 240,
        "selected_count": 168,
        "reserve_count": 72,
        "content_authored": False,
        "selected_effect_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in OUTPUTS}
    if all(checks.values()):
        manifest_hash = sha(MANIFEST)
        outcome_hash = sha(OUTCOME)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V5)
        readiness_hash = sha(READINESS_V5)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(
                    path.exists() and sha(path) == digest for path, digest in EXPECTED.items()
                ),
                "inventory_replay": load(INVENTORY) == inventory_document(),
                "sampling_replay": load(SAMPLING) == sampling_document(),
                "selected_replay": load(SELECTED) == selected_document(),
                "fixtures_replay": load(FIXTURES) == fixture_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
                "audit_replay": AUDIT.read_bytes()
                == (canonical(audit_event(manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
                "state_v5_replay": load(STATE_V5)
                == state_document(manifest_hash, outcome_hash, audit_hash),
                "readiness_v5_replay": load(READINESS_V5)
                == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
                "receipt_replay": load(RECEIPT)
                == receipt_document(
                    manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash
                ),
                "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
                "next_gate_consistent": load(STATE_V5)["next_authorized_stage"]
                == load(READINESS_V5)["next_authorized_stage"]
                == load(RECEIPT)["next_authorized_stage"]
                == NEXT,
                "content_not_authored": load(STATE_V5)["source_content_authored"] is False,
                "effect_content_closed": load(STATE_V5)["selected_effect_content_opened"] is False,
                "runtime_off": load(STATE_V5)["runtime_integration_authorized"] is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "content_authored": load(STATE_V5).get("source_content_authored")
        if STATE_V5.exists()
        else None,
        "selected_effect_content_opened": load(STATE_V5).get("selected_effect_content_opened")
        if STATE_V5.exists()
        else None,
        "runtime_integration_authorized": load(STATE_V5).get("runtime_integration_authorized")
        if STATE_V5.exists()
        else None,
        "next_authorized_stage": load(STATE_V5).get("next_authorized_stage")
        if STATE_V5.exists()
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--construct", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        outcome = preflight()
    elif args.construct:
        outcome = construct()
    else:
        outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
