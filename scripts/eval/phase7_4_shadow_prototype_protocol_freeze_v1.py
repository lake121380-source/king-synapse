#!/usr/bin/env python3
"""Freeze the Phase 7.4.1 eval-only Atomic Evidence shadow protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
DOCS = ROOT / "docs"

DESIGN_DOC = DOCS / "PHASE7_4_ATOMIC_EVIDENCE_SUBSTRATE_DESIGN.md"
DESIGN_CONTRACT = CONFIG / "phase7_4_design_contract_v1.json"
PROTOCOL_DOC = DOCS / "eval/PHASE7_4_1_ATOMIC_EVIDENCE_SHADOW_PROTOTYPE_PROTOCOL.md"
OVERLAY_SCHEMA = CONFIG / "phase7_4_atomic_evidence_shadow_overlay_schema_v1.json"
PROTOCOL = CONFIG / "phase7_4_atomic_evidence_shadow_prototype_protocol_v1.json"

PREDECESSOR_STATE = PATTERN / "phase7_3_3_d_support_stage_state_v111.json"
PREDECESSOR_READINESS = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v122.json"
PREDECESSOR_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_final_audit_report_v1.json"
PREDECESSOR_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_final_audit_receipt_v1.json"

FIXTURES = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_audit_v1.jsonl"
STATE = PATTERN / "phase7_4_stage_state_v1.json"
READINESS = REPORTS / "phase7_4_readiness_v1.json"
RECEIPT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_receipt_v1.json"

ENTRY = "phase7_4_1_design_frozen_shadow_prototype_pending"
NEXT = "implement_phase7_4_eval_only_shadow_overlay_v1"

EXPECTED = {
    DESIGN_DOC: "ec193194e37fcbf7e0074e9ed6db17910ecde45da74fa8f3d8fe29a178934a03",
    DESIGN_CONTRACT: "7e3680b434458f70c4ccff114b3d05db1a52348207e662ac4f65d48d80d6da91",
    PROTOCOL_DOC: "eda349de723c15ae7ff528554bde1ff6de39bc2cffd2fd398c033bb7382a81a7",
    OVERLAY_SCHEMA: "daa5b77f6b922180d5c60f480f594e6274e7ae8dd75e747ded26c442e2de0af7",
    PROTOCOL: "f727d431585ccbefd7f03f745706cee3ccdab7a7f96cfd3c52eb67d432795596",
    PREDECESSOR_STATE: "bcd96ad07f1d64fe5b08ce2c28bb45b1f0a6e63bf35128cb034129e8c09a5d88",
    PREDECESSOR_READINESS: "42a4bc3a5202a16c30e9615d3a9bf4f35d1fda619f6edea6b84b2b0d4ee64bf8",
    PREDECESSOR_REPORT: "8f08360a85e164e19fadae13f77cf5eb67b73607f0344d2a4d8cf53475f6d0c7",
    PREDECESSOR_RECEIPT: "e5f1c8f32b079c9c4b62047afa225a0942d37b2c9d75b91883824b58faf9c694",
}


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


def fixture_document() -> dict[str, Any]:
    design = load(DESIGN_CONTRACT)
    protocol = load(PROTOCOL)
    schema = load(OVERLAY_SCHEMA)
    authority = schema["$defs"]["authority"]["properties"]
    memory_kinds = schema["properties"]["source_memory_kind"]["enum"]
    required_gate_checks = set(protocol["prototype_gate"]["checks"])
    checks = [
        ("design_document_hash", design["design_document"]["sha256"] == sha(DESIGN_DOC)),
        ("design_contract_entry_gate", design["status"] == ENTRY),
        ("design_next_authority", design["current_authority"]["authorized_stage"] == "construct_phase7_4_eval_only_shadow_prototype_protocol_v1"),
        ("protocol_document_hash", protocol["protocol_document"]["sha256"] == sha(PROTOCOL_DOC)),
        ("overlay_schema_hash", protocol["output_schema"]["sha256"] == sha(OVERLAY_SCHEMA)),
        ("protocol_design_hashes", protocol["frozen_design_inputs"][rel(DESIGN_DOC)] == sha(DESIGN_DOC) and protocol["frozen_design_inputs"][rel(DESIGN_CONTRACT)] == sha(DESIGN_CONTRACT)),
        ("existing_memory_kinds_only", memory_kinds == ["fact", "preference", "failure", "playbook", "state"] and "atomic_claim" not in memory_kinds),
        ("authority_constructor_controlled", schema["$defs"]["authority"]["additionalProperties"] is False),
        ("authority_runtime_false", authority["runtime_applied"]["const"] is False),
        ("authority_memory_false", authority["memory_mutated"]["const"] is False),
        ("authority_store_false", authority["store_written"]["const"] is False),
        ("authority_engine_false", authority["recall_engine_mutated"]["const"] is False),
        ("authority_promotion_false", authority["promotion_authorized"]["const"] is False),
        ("implementation_eval_only", all(not path.startswith("crates/core/") for path in protocol["implementation_boundary"]["allowed_paths"])),
        ("no_mutable_runtime_handles", protocol["implementation_boundary"]["mutable_memory_input_allowed"] is False and protocol["implementation_boundary"]["store_handle_allowed"] is False and protocol["implementation_boundary"]["recall_engine_handle_allowed"] is False),
        ("no_claim_extraction", protocol["authorized_prototype"]["claim_extraction"] is False),
        ("no_provider_call", protocol["authorized_prototype"]["provider_call"] is False and protocol["freeze_status"]["phase7_4_effect_provider_called"] is False),
        ("effect_dataset_closed", protocol["freeze_status"]["phase7_4_effect_dataset_opened"] is False),
        ("predecessor_effect_data_not_loaded", protocol["freeze_status"]["phase7_3_3_d_effect_data_loaded"] is False),
        ("prototype_not_started", protocol["freeze_status"]["prototype_implementation_started"] is False),
        ("no_runtime_or_core_mutation", all(protocol["freeze_status"][key] is False for key in ["memory_kind_modified", "memory_schema_modified", "recall_engine_modified", "production_write_path_modified", "runtime_integration_authorized"])),
        ("gate_has_twelve_checks", len(required_gate_checks) == 12),
        ("failure_taxonomy_frozen", len(protocol["failure_taxonomy"]) == 16 and len(set(protocol["failure_taxonomy"])) == 16),
        ("next_stage_overlay_only", protocol["next_authorized_stage"] == NEXT),
        ("predecessor_terminal_gate", load(PREDECESSOR_STATE)["next_authorized_stage"] == load(PREDECESSOR_READINESS)["next_authorized_stage"] == design["predecessor_freeze"]["terminal_gate"]),
        ("predecessor_runtime_off", load(PREDECESSOR_STATE)["runtime_integration_authorized"] is False and load(PREDECESSOR_READINESS)["runtime_integration_authorized"] is False),
    ]
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks]
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4.1-atomic-evidence-shadow-prototype-protocol-fixtures-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "fixtures": rows,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4.1-atomic-evidence-shadow-prototype-protocol-freeze-manifest-v1",
        "status": "frozen_before_shadow_overlay_implementation",
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "protocol_freeze_artifacts": {
            rel(DESIGN_DOC): sha(DESIGN_DOC),
            rel(DESIGN_CONTRACT): sha(DESIGN_CONTRACT),
            rel(PROTOCOL_DOC): sha(PROTOCOL_DOC),
            rel(OVERLAY_SCHEMA): sha(OVERLAY_SCHEMA),
            rel(PROTOCOL): sha(PROTOCOL),
            rel(FIXTURES): sha(FIXTURES),
        },
        "predecessor_mutated": False,
        "prototype_implementation_started": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "outcome_id": "phase7.4.1-atomic-evidence-shadow-prototype-protocol-freeze-outcome-v1",
        "status": "PASS_protocol_frozen_shadow_overlay_implementation_authorized",
        "manifest_sha256": manifest_hash,
        "fixtures_sha256": sha(FIXTURES),
        "fixture_count": load(FIXTURES)["fixture_count"],
        "failed_fixture_count": 0,
        "predecessor_mutated": False,
        "prototype_implementation_started": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_design_document_sha256": sha(DESIGN_DOC),
        "phase7_4_design_contract_v1_sha256": sha(DESIGN_CONTRACT),
        "phase7_4_shadow_prototype_protocol_document_v1_sha256": sha(PROTOCOL_DOC),
        "phase7_4_shadow_overlay_schema_v1_sha256": sha(OVERLAY_SCHEMA),
        "phase7_4_shadow_prototype_protocol_v1_sha256": sha(PROTOCOL),
        "phase7_4_shadow_prototype_protocol_fixtures_v1_sha256": sha(FIXTURES),
        "phase7_4_shadow_prototype_protocol_freeze_manifest_v1_sha256": manifest_hash,
        "phase7_4_shadow_prototype_protocol_freeze_outcome_v1_sha256": outcome_hash,
        "phase7_4_shadow_prototype_protocol_freeze_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "state_id": "phase7.4-stage-state-v1",
        "status": "phase7_4_1_shadow_prototype_protocol_frozen_implementation_authorized",
        "predecessor_phase": "phase7_3_3_d",
        "predecessor_terminal_gate": "confirmatory_success_frozen_runtime_integration_not_authorized",
        "predecessor_mutated": False,
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "phase7_4_design_frozen": True,
        "phase7_4_shadow_prototype_protocol_frozen": True,
        "phase7_4_shadow_prototype_implementation_authorized": True,
        "phase7_4_shadow_prototype_implementation_started": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "memory_kind_modification_authorized": False,
        "memory_schema_modification_authorized": False,
        "recall_engine_modification_authorized": False,
        "production_memory_write_authorized": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def readiness_document(manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "readiness_id": "phase7.4-readiness-v1",
        "status": "PASS_shadow_prototype_protocol_frozen",
        "artifact_lineage": {
            **lineage(manifest_hash, outcome_hash, audit_hash),
            "phase7_4_stage_state_v1_sha256": state_hash,
        },
        "checks": {
            "design_contract_frozen": True,
            "overlay_schema_frozen": True,
            "prototype_protocol_frozen": True,
            "protocol_fixtures_pass": True,
            "predecessor_read_only": True,
            "effect_dataset_closed": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "prototype_implementation_authorized": True,
        "prototype_implementation_started": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def receipt_document(manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str, readiness_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_id": "phase7.4.1-atomic-evidence-shadow-prototype-protocol-freeze-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "fixture_count": load(FIXTURES)["fixture_count"],
        "failed_fixture_count": 0,
        "predecessor_mutated": False,
        "prototype_implementation_started": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "same_version_semantic_retry_allowed": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def preflight() -> dict[str, Any]:
    checks = {"input_hash:" + rel(path): path.exists() and sha(path) == digest for path, digest in EXPECTED.items()}
    if all(checks.values()):
        design = load(DESIGN_CONTRACT)
        protocol = load(PROTOCOL)
        checks.update({
            "design_entry_gate": design["status"] == ENTRY,
            "design_authorizes_protocol": design["current_authority"]["authorized_stage"] == "construct_phase7_4_eval_only_shadow_prototype_protocol_v1",
            "protocol_entry_gate": protocol["entry_gate"] == ENTRY,
            "protocol_next_stage": protocol["next_authorized_stage"] == NEXT,
            "effect_dataset_closed": protocol["freeze_status"]["phase7_4_effect_dataset_opened"] is False,
            "provider_not_called": protocol["freeze_status"]["phase7_4_effect_provider_called"] is False,
            "runtime_off": protocol["freeze_status"]["runtime_integration_authorized"] is False,
        })
    outputs = [FIXTURES, MANIFEST, OUTCOME, AUDIT, STATE, READINESS, RECEIPT]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
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
    audit_hash = append_single_event(AUDIT, {
        "event_id": "phase7.4.1-shadow-prototype-protocol-v1-frozen",
        "event_type": "immutable_protocol_freeze",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "fixture_count": load(FIXTURES)["fixture_count"],
        "predecessor_mutated": False,
        "prototype_implementation_started": False,
        "effect_dataset_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    })
    state_hash = once(STATE, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(READINESS, readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash))
    receipt_hash = once(RECEIPT, receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash))
    return {
        "status": "PASS",
        "fixture_count": load(FIXTURES)["fixture_count"],
        "fixtures_sha256": fixture_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "receipt_sha256": receipt_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "prototype_implementation_started": False,
        "phase7_4_effect_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    paths = [FIXTURES, MANIFEST, OUTCOME, AUDIT, STATE, READINESS, RECEIPT]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        manifest_hash = sha(MANIFEST)
        outcome_hash = sha(OUTCOME)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE)
        readiness_hash = sha(READINESS)
        receipt = load(RECEIPT)
        checks.update({
            "input_hashes": all(path.exists() and sha(path) == digest for path, digest in EXPECTED.items()),
            "fixtures_replay": load(FIXTURES) == fixture_document(),
            "manifest_replay": load(MANIFEST) == manifest_document(),
            "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
            "state_replay": load(STATE) == state_document(manifest_hash, outcome_hash, audit_hash),
            "readiness_replay": load(READINESS) == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
            "receipt_replay": receipt == receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash),
            "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
            "receipt_lineage": receipt["manifest_sha256"] == manifest_hash and receipt["outcome_sha256"] == outcome_hash and receipt["state_sha256"] == state_hash and receipt["readiness_sha256"] == readiness_hash,
            "next_gate": load(STATE)["next_authorized_stage"] == load(READINESS)["next_authorized_stage"] == NEXT,
            "prototype_not_started": load(STATE)["phase7_4_shadow_prototype_implementation_started"] is False,
            "effect_dataset_closed": load(STATE)["phase7_4_effect_dataset_opened"] is False,
            "provider_not_called": load(STATE)["phase7_4_effect_provider_called"] is False,
            "predecessor_not_mutated": load(STATE)["predecessor_mutated"] is False,
            "runtime_off": load(STATE)["runtime_integration_authorized"] is False and load(READINESS)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "prototype_implementation_started": load(STATE).get("phase7_4_shadow_prototype_implementation_started") if STATE.exists() else None,
        "phase7_4_effect_dataset_opened": load(STATE).get("phase7_4_effect_dataset_opened") if STATE.exists() else None,
        "runtime_integration_authorized": load(STATE).get("runtime_integration_authorized") if STATE.exists() else None,
        "next_authorized_stage": load(STATE).get("next_authorized_stage") if STATE.exists() else None,
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
        outcome["status"] = "PASS" if outcome["all_fixtures_passed"] else "FAIL"
    elif args.freeze:
        outcome = freeze()
    else:
        outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
