#!/usr/bin/env python3
"""Freeze query-blind Atomic segmentation and its memory-only input projection."""
from __future__ import annotations

import argparse
import hashlib
import json
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

DOC = DOCS / "eval/PHASE7_4_2_QUERY_BLIND_ATOMIC_SEGMENTATION_PROTOCOL.md"
PROTOCOL = CONFIG / "phase7_4_query_blind_atomic_segmentation_protocol_v1.json"
SOURCE = PHASE_DATA / "phase7_4_selected_source_cases_v2.json"
AUTHORING_MANIFEST = REPORTS / "phase7_4_selected_source_authoring_manifest_v2.json"
AUTHORING_RECEIPT = REPORTS / "phase7_4_selected_source_authoring_receipt_v2.json"
STATE_V8 = PATTERN / "phase7_4_stage_state_v8.json"
READINESS_V8 = REPORTS / "phase7_4_readiness_v8.json"
PROTOTYPE_PROTOCOL = CONFIG / "phase7_4_atomic_evidence_shadow_prototype_protocol_v1.json"
OVERLAY_SCHEMA = CONFIG / "phase7_4_atomic_evidence_shadow_overlay_schema_v1.json"
PROTOTYPE_RECEIPT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_receipt_v1.json"
IMPLEMENTATION_MANIFEST = REPORTS / "phase7_4_atomic_evidence_shadow_implementation_manifest_v1.json"
RUST_CONSTRUCTOR = ROOT / "crates/eval/src/phase7_4_atomic_evidence_shadow.rs"
ENVIRONMENT = CONFIG / "phase7_4_offline_retrieval_execution_environment_v1.json"

PROJECTION = PHASE_DATA / "phase7_4_memory_only_segmentation_input_v1.json"
FIXTURES = REPORTS / "phase7_4_query_blind_atomic_segmentation_protocol_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_4_query_blind_atomic_segmentation_protocol_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_query_blind_atomic_segmentation_protocol_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_query_blind_atomic_segmentation_protocol_audit_v1.jsonl"
STATE_V9 = PATTERN / "phase7_4_stage_state_v9.json"
READINESS_V9 = REPORTS / "phase7_4_readiness_v9.json"
RECEIPT = REPORTS / "phase7_4_query_blind_atomic_segmentation_protocol_receipt_v1.json"

ENTRY_HEAD = "dea771be36366b1643607d8e1faef58171f7f679"
ENTRY = "phase7_4_selected_source_cases_v2_frozen_atomic_segmentation_protocol_freeze_authorized"
AUTHORIZED = "freeze_phase7_4_query_blind_atomic_segmentation_protocol_v1"
NEXT = "execute_phase7_4_query_blind_atomic_segmentation_v1"

EXPECTED = {
    DOC: "38f2910ab4ee6068907707584b774d80759c7f6692e1769d884e2f9aa74aa2c5",
    PROTOCOL: "805a67a066328943d80175871df14dba1741588b9234ab0bf908a72a7f25a8a5",
    SOURCE: "b06ff2ceb1d300561df937f73a1e9de9d8f5c9d6ca19cb57069b63acc834256d",
    AUTHORING_MANIFEST: "5f3cb96f3d9915a052e098101a6d5d0f6b65518af1878b39f22a789bc21fadde",
    AUTHORING_RECEIPT: "1aa792ea45c7c95c418ff06be02852e777489f8cfb717185eb261b130813dadf",
    STATE_V8: "a20c157c91d8ba96849fb99abc0952366f388bb0ce7ab38dac363f3a413b5aa6",
    READINESS_V8: "c2c40c691ea612fe7a48f96274d25a5628bfe86226596afeab3d1a6988ecf4c1",
    PROTOTYPE_PROTOCOL: "f727d431585ccbefd7f03f745706cee3ccdab7a7f96cfd3c52eb67d432795596",
    OVERLAY_SCHEMA: "daa5b77f6b922180d5c60f480f594e6274e7ae8dd75e747ded26c442e2de0af7",
    PROTOTYPE_RECEIPT: "a7ab56c1fb9f064143cd8a07932bef968d8c1fe66cc014c695efd97b404816c6",
    IMPLEMENTATION_MANIFEST: "448a7384d6108c1ff7c2b774f907f16a804883c8cceb772af95e47b76b46eb04",
    RUST_CONSTRUCTOR: "cfbaf4a564b098bf390024666d6ffe3017d38005cb0877be5f373be8cf8bc904",
    ENVIRONMENT: "5b5b02a7651da6fb7ef4d0a4c25efb76beb38bacd7f63a518ec06b168bdff786",
}

OUTPUTS = [
    PROJECTION,
    FIXTURES,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V9,
    READINESS_V9,
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


def memory_projection(memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "pool_ordinal": memory["pool_ordinal"],
        "source_memory_id": memory["source_memory_id"],
        "source_memory_kind": memory["source_memory_kind"],
        "source_memory_content": memory["source_memory_content"],
        "source_memory_content_sha256": memory["source_memory_content_sha256"],
        "source_memory_sha256": memory["source_memory_sha256"],
        "source_evidence_ids": memory["source_evidence_ids"],
        "source_event_ids": memory["source_event_ids"],
    }


def projection_document() -> dict[str, Any]:
    source = load(SOURCE)
    cases = [
        {
            "case_id": case["case_id"],
            "stratum": case["stratum"],
            "candidate_memories": [
                memory_projection(memory) for memory in case["candidate_memories"]
            ],
        }
        for case in source["cases"]
    ]
    return {
        "schema_version": 1,
        "projection_id": "phase7.4-memory-only-segmentation-input-v1",
        "status": "frozen_query_blind_memory_only_projection",
        "source_dataset_sha256": sha(SOURCE),
        "source_authoring_manifest_sha256": sha(AUTHORING_MANIFEST),
        "segmentation_protocol_sha256": sha(PROTOCOL),
        "case_count": len(cases),
        "memory_count": sum(len(case["candidate_memories"]) for case in cases),
        "cases": cases,
        "query_fields_copied": False,
        "gold_or_reference_fields_copied": False,
        "atomic_or_arm_fields_copied": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "network_used": False,
        "runtime_accessed": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
    }


def fixture_document() -> dict[str, Any]:
    projection = load(PROJECTION)
    source = load(SOURCE)
    protocol = load(PROTOCOL)
    state = load(STATE_V8)
    projected_cases = projection["cases"]
    source_cases = source["cases"]
    forbidden = set(protocol["query_blind_projection"]["forbidden_fields"])

    def contains_forbidden(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                key in forbidden or contains_forbidden(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(contains_forbidden(item) for item in value)
        return False

    allowed_case_fields = set(
        protocol["query_blind_projection"]["allowed_case_fields"]
    )
    allowed_memory_fields = set(
        protocol["query_blind_projection"]["allowed_memory_fields"]
    )
    all_memory_hashes_replay = True
    projection_exact = True
    for source_case, projected_case in zip(
        source_cases, projected_cases, strict=True
    ):
        projection_exact = projection_exact and projected_case == {
            "case_id": source_case["case_id"],
            "stratum": source_case["stratum"],
            "candidate_memories": [
                memory_projection(memory)
                for memory in source_case["candidate_memories"]
            ],
        }
        for memory in projected_case["candidate_memories"]:
            all_memory_hashes_replay = (
                all_memory_hashes_replay
                and hb(memory["source_memory_content"].encode("utf-8"))
                == memory["source_memory_content_sha256"]
            )
    strata = Counter(case["stratum"] for case in projected_cases)
    memory_ids = [
        memory["source_memory_id"]
        for case in projected_cases
        for memory in case["candidate_memories"]
    ]
    checks = [
        ("projection_replay_exact", projection == projection_document()),
        ("source_dataset_hash_exact", projection["source_dataset_sha256"] == sha(SOURCE)),
        ("case_count_168", projection["case_count"] == len(projected_cases) == 168),
        ("eight_strata_twenty_one_each", len(strata) == 8 and set(strata.values()) == {21}),
        ("memory_count_1680", projection["memory_count"] == len(memory_ids) == 1680),
        ("memory_ids_unique", len(set(memory_ids)) == 1680),
        ("source_projection_exact", projection_exact),
        ("case_fields_exact", all(set(case) == allowed_case_fields for case in projected_cases)),
        ("memory_fields_exact", all(set(memory) == allowed_memory_fields for case in projected_cases for memory in case["candidate_memories"])),
        ("memory_content_hashes_replay", all_memory_hashes_replay),
        ("no_forbidden_query_gold_atomic_arm_fields", not contains_forbidden(projection)),
        ("query_fields_not_copied", projection["query_fields_copied"] is False),
        ("gold_atomic_arm_fields_not_copied", projection["gold_or_reference_fields_copied"] is False and projection["atomic_or_arm_fields_copied"] is False),
        ("segmentation_not_executed", not any("atomic_units" in case for case in projected_cases)),
        ("entry_state_exact", state["status"] == ENTRY and state["next_authorized_stage"] == AUTHORIZED),
        ("protocol_next_execution_only", protocol["next_authorized_stage_after_pass"] == NEXT),
        ("placeholder_not_gold", protocol["non_label_placeholders"]["placeholder_is_gold_judgment"] is False),
        ("expected_representation_counts_frozen", protocol["representation_and_coverage_gate"]["memory_chunk_count"] == 1680 and protocol["representation_and_coverage_gate"]["atomic_unit_count"] == 3360),
        ("phase7_3_content_not_loaded", projection["phase7_3_3_d_content_loaded"] is False),
        ("provider_network_runtime_unused", projection["provider_called"] is False and projection["network_used"] is False and projection["runtime_accessed"] is False),
        ("effect_dataset_closed_to_arms", projection["selected_effect_dataset_opened_for_arm_execution"] is False),
        ("reference_gold_and_arms_closed", protocol["authority"]["reference_review_authorized"] is False and protocol["authority"]["gold_freeze_authorized"] is False and protocol["authority"]["arm_execution_authorized"] is False),
        ("runtime_product_release_closed", all(protocol["authority"][key] is False for key in ["runtime_integration_authorized", "productization_authorized", "release_authorized"])),
    ]
    rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4-query-blind-atomic-segmentation-protocol-fixtures-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "fixtures": rows,
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "case_count": 168,
        "memory_count": 1680,
        "query_fields_copied": False,
        "atomic_segmentation_executed": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4-query-blind-atomic-segmentation-protocol-manifest-v1",
        "status": "frozen_protocol_and_query_blind_memory_projection",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {rel(PROJECTION): sha(PROJECTION), rel(FIXTURES): sha(FIXTURES)},
        "case_count": 168,
        "memory_count": 1680,
        "query_fields_copied": False,
        "atomic_segmentation_executed": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "outcome_id": "phase7.4-query-blind-atomic-segmentation-protocol-outcome-v1",
        "status": "PASS_protocol_frozen_query_blind_segmentation_execution_authorized",
        "manifest_sha256": manifest_hash,
        "projection_sha256": sha(PROJECTION),
        "fixtures_sha256": sha(FIXTURES),
        "case_count": 168,
        "memory_count": 1680,
        "query_fields_copied": False,
        "atomic_segmentation_executed": False,
        "atomic_segmentation_execution_authorized": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-query-blind-atomic-segmentation-protocol-v1-frozen",
        "event_type": "immutable_segmentation_protocol_and_memory_only_projection_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "projection_sha256": sha(PROJECTION),
        "source_dataset_sha256": sha(SOURCE),
        "query_fields_copied": False,
        "atomic_segmentation_executed": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v8_sha256": sha(STATE_V8),
        "phase7_4_readiness_v8_sha256": sha(READINESS_V8),
        "phase7_4_selected_source_authoring_receipt_v2_sha256": sha(AUTHORING_RECEIPT),
        "phase7_4_query_blind_atomic_segmentation_protocol_v1_sha256": sha(PROTOCOL),
        "phase7_4_memory_only_segmentation_input_v1_sha256": sha(PROJECTION),
        "phase7_4_query_blind_atomic_segmentation_protocol_fixtures_v1_sha256": sha(FIXTURES),
        "phase7_4_query_blind_atomic_segmentation_protocol_manifest_v1_sha256": manifest_hash,
        "phase7_4_query_blind_atomic_segmentation_protocol_outcome_v1_sha256": outcome_hash,
        "phase7_4_query_blind_atomic_segmentation_protocol_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 9,
        "state_id": "phase7.4-stage-state-v9",
        "status": "phase7_4_query_blind_atomic_segmentation_protocol_frozen_execution_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "selected_source_content_frozen": True,
        "memory_only_segmentation_projection_frozen": True,
        "query_fields_copied_to_segmentation_projection": False,
        "selected_case_count": 168,
        "source_memory_count": 1680,
        "atomic_segmentation_protocol_frozen": True,
        "atomic_segmentation_execution_authorized": True,
        "atomic_segmentation_executed": False,
        "atomic_overlay_constructed": False,
        "reference_protocol_freeze_authorized": False,
        "reference_review_started": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
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
        "schema_version": 9,
        "readiness_id": "phase7.4-readiness-v9",
        "status": "PASS_query_blind_atomic_segmentation_execution_ready",
        "artifact_lineage": {
            **lineage(manifest_hash, outcome_hash, audit_hash),
            "phase7_4_stage_state_v9_sha256": state_hash,
        },
        "checks": {
            "source_dataset_exact": True,
            "memory_only_projection_exact": True,
            "query_fields_absent": True,
            "gold_atomic_and_arm_fields_absent": True,
            "source_memory_count_exact": True,
            "segmentation_algorithm_frozen": True,
            "overlay_compatibility_contract_frozen": True,
            "placeholders_are_not_gold": True,
            "segmentation_not_yet_executed": True,
            "effect_dataset_closed_to_arms": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "atomic_segmentation_execution_authorized": True,
        "reference_protocol_freeze_authorized": False,
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
        "receipt_id": "phase7.4-query-blind-atomic-segmentation-protocol-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v9_sha256": state_hash,
        "readiness_v9_sha256": readiness_hash,
        "protocol_sha256": sha(PROTOCOL),
        "projection_sha256": sha(PROJECTION),
        "case_count": 168,
        "memory_count": 1680,
        "query_fields_copied": False,
        "atomic_segmentation_executed": False,
        "atomic_segmentation_execution_authorized": True,
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
        state = load(STATE_V8)
        protocol = load(PROTOCOL)
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state_exact": state["status"] == ENTRY,
                "entry_authority_exact": state["next_authorized_stage"] == AUTHORIZED,
                "protocol_entry_exact": protocol["entry_gate"] == AUTHORIZED,
                "protocol_next_exact": protocol["next_authorized_stage_after_pass"] == NEXT,
                "projection_authorized": protocol["authority"]["memory_only_projection_construction_authorized"] is True,
                "segmentation_not_executed": state["atomic_overlay_constructed"] is False,
                "reference_and_arms_closed": state["reference_review_started"] is False and state["arm_execution_started"] is False,
                "effect_dataset_closed": state["selected_effect_dataset_opened_for_arm_execution"] is False,
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
    projection_hash = once(PROJECTION, projection_document())
    fixtures_hash = once(FIXTURES, fixture_document())
    if not load(FIXTURES)["all_fixtures_passed"]:
        raise RuntimeError("segmentation_protocol_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V9, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(
        READINESS_V9,
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
        "projection_sha256": projection_hash,
        "fixtures_sha256": fixtures_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v9_sha256": state_hash,
        "readiness_v9_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "case_count": 168,
        "memory_count": 1680,
        "query_fields_copied": False,
        "atomic_segmentation_executed": False,
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
        state_hash = sha(STATE_V9)
        readiness_hash = sha(READINESS_V9)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(path.exists() and sha(path) == digest for path, digest in EXPECTED.items()),
                "projection_replay": load(PROJECTION) == projection_document(),
                "fixtures_replay": load(FIXTURES) == fixture_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
                "audit_replay": AUDIT.read_bytes() == (canonical(audit_event(manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
                "state_v9_replay": load(STATE_V9) == state_document(manifest_hash, outcome_hash, audit_hash),
                "readiness_v9_replay": load(READINESS_V9) == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
                "receipt_replay": load(RECEIPT) == receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash),
                "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
                "next_gate_consistent": load(STATE_V9)["next_authorized_stage"] == load(READINESS_V9)["next_authorized_stage"] == load(RECEIPT)["next_authorized_stage"] == NEXT,
                "query_fields_absent": load(PROJECTION)["query_fields_copied"] is False,
                "segmentation_not_executed": load(STATE_V9)["atomic_segmentation_executed"] is False,
                "effect_dataset_closed": load(STATE_V9)["selected_effect_dataset_opened_for_arm_execution"] is False,
                "runtime_off": load(STATE_V9)["runtime_integration_authorized"] is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "query_fields_copied": load(PROJECTION).get("query_fields_copied") if PROJECTION.exists() else None,
        "atomic_segmentation_executed": load(STATE_V9).get("atomic_segmentation_executed") if STATE_V9.exists() else None,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V9).get("selected_effect_dataset_opened_for_arm_execution") if STATE_V9.exists() else None,
        "runtime_integration_authorized": load(STATE_V9).get("runtime_integration_authorized") if STATE_V9.exists() else None,
        "next_authorized_stage": load(STATE_V9).get("next_authorized_stage") if STATE_V9.exists() else None,
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
