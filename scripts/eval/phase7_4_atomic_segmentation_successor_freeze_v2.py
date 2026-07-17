#!/usr/bin/env python3
"""Classify segmentation v1 failure and freeze formal overlay successor v2."""
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

DOC = DOCS / "eval/PHASE7_4_2_ATOMIC_SEGMENTATION_SUCCESSOR_V2.md"
POLICY = CONFIG / "phase7_4_atomic_segmentation_successor_policy_v2.json"
SCHEMA_V2 = CONFIG / "phase7_4_atomic_evidence_overlay_schema_v2.json"
V1_PYTHON = ROOT / "scripts/eval/phase7_4_query_blind_atomic_segmentation_v1.py"
V1_RUST = ROOT / "crates/eval/src/bin/phase7_4_atomic_segmentation_v1.rs"
ATTEMPTS = REPORTS / "phase7_4_query_blind_atomic_segmentation_attempts_v1.jsonl"
PROTOCOL = CONFIG / "phase7_4_query_blind_atomic_segmentation_protocol_v1.json"
PROJECTION = PHASE_DATA / "phase7_4_memory_only_segmentation_input_v1.json"
STATE_V9 = PATTERN / "phase7_4_stage_state_v9.json"
READINESS_V9 = REPORTS / "phase7_4_readiness_v9.json"
PROTOCOL_RECEIPT = REPORTS / "phase7_4_query_blind_atomic_segmentation_protocol_receipt_v1.json"

CLASSIFICATION = REPORTS / "phase7_4_atomic_segmentation_v1_failure_classification.json"
MANIFEST = REPORTS / "phase7_4_atomic_segmentation_successor_manifest_v2.json"
OUTCOME = REPORTS / "phase7_4_atomic_segmentation_successor_outcome_v2.json"
AUDIT = REPORTS / "phase7_4_atomic_segmentation_successor_audit_v2.jsonl"
STATE_V10 = PATTERN / "phase7_4_stage_state_v10.json"
READINESS_V10 = REPORTS / "phase7_4_readiness_v10.json"
RECEIPT = REPORTS / "phase7_4_atomic_segmentation_successor_receipt_v2.json"

V1_OUTPUTS = [
    PHASE_DATA / "phase7_4_atomic_overlay_dataset_v1.json",
    REPORTS / "phase7_4_atomic_segmentation_representation_coverage_gate_v1.json",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_fixtures_v1.json",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_manifest_v1.json",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_outcome_v1.json",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_audit_v1.jsonl",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_receipt_v1.json",
]

ENTRY_HEAD = "dc1498d5a8ed26161bf93c77d5fcfde680e52c30"
ENTRY = "phase7_4_query_blind_atomic_segmentation_protocol_frozen_execution_authorized"
V1_AUTHORIZED = "execute_phase7_4_query_blind_atomic_segmentation_v1"
FREEZE_GATE = "classify_phase7_4_atomic_segmentation_v1_failure_and_freeze_v2_successor"
NEXT = "execute_phase7_4_query_blind_atomic_segmentation_v2"

EXPECTED = {
    DOC: "0b49c07f3d0c15a5dfd52b9b7a89bf87b312fc85915e370be8be7335a9377c92",
    POLICY: "0d0aa0b6bf78fa1bddb2d6337d9975ba37ebdc97dddb1e088eec865c62f7c5b0",
    SCHEMA_V2: "865e5b4f9bf1bf49ce1d38d4b5084c307d3975382cc28195a8c30cd01750f790",
    V1_PYTHON: "50cc5e69cd0f5e82ae85ea7bfc5ad04263a64b71f97ed8c6b0cd12b8a2400ec2",
    V1_RUST: "9b65f3077b40f47c3d76c27414243d68cb67b79dcddd8bdd5abf776c6aeea57d",
    ATTEMPTS: "7de5b1f1017fa1f481b62e9ad0f8017cb7852478bd0c96c799fc660707002193",
    PROTOCOL: "805a67a066328943d80175871df14dba1741588b9234ab0bf908a72a7f25a8a5",
    PROJECTION: "c27d60e89e273962b0b32bd4496fed1cac56d1009d8c65d002f5b50ff33cc07b",
    STATE_V9: "e44de9f24d06aa8e2784ff0f48c10d1ce0faa2e42453e380bf5adebff929f3fd",
    READINESS_V9: "aca579a9e9d218cffcc8d9aada9cb1b7d439414e5813f6a82b4569d2115574bb",
    PROTOCOL_RECEIPT: "206fb82127f439130682cd24b40d5a84ed7b5952bea752d3b131a9581830e623",
}

OUTPUTS = [
    CLASSIFICATION,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V10,
    READINESS_V10,
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


def attempt_event() -> dict[str, Any]:
    lines = ATTEMPTS.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise RuntimeError("segmentation_attempt_event_count_mismatch")
    return json.loads(lines[0])


def schema_valid() -> bool:
    try:
        Draft202012Validator.check_schema(load(SCHEMA_V2))
        return True
    except Exception:
        return False


def classification_document() -> dict[str, Any]:
    attempt = attempt_event()
    return {
        "schema_version": 1,
        "classification_id": "phase7.4-atomic-segmentation-v1-failure-classification",
        "status": "classified_before_first_overlay_no_authoritative_outputs",
        "entry_head": ENTRY_HEAD,
        "python_adapter_sha256": sha(V1_PYTHON),
        "rust_adapter_sha256": sha(V1_RUST),
        "attempt_log_sha256": sha(ATTEMPTS),
        "failure_taxonomy": attempt["failure_taxonomy"],
        "classified_failure": attempt["classified_failure"],
        "failure_detail": attempt["failure_detail"],
        "authoritative_outputs_written": False,
        "atomic_or_arm_output_written": False,
        "reference_or_gold_output_written": False,
        "query_access_count": 0,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "source_dataset_mutation_allowed": False,
        "prototype_constructor_mutation_allowed": False,
        "same_version_retry_allowed": False,
        "bounded_formal_overlay_v2_authorized": True,
        "next_authorized_stage": NEXT,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "manifest_id": "phase7.4-atomic-segmentation-successor-manifest-v2",
        "status": "frozen_v1_failure_and_formal_overlay_v2_compatibility_contract",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {rel(CLASSIFICATION): sha(CLASSIFICATION)},
        "v1_authoritative_outputs_absent": all(not path.exists() for path in V1_OUTPUTS),
        "source_dataset_and_projection_unchanged": True,
        "prototype_constructor_and_schema_unchanged": True,
        "sentence_algorithm_and_thresholds_unchanged": True,
        "atomic_segmentation_executed_v2": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(classification_hash: str, manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "outcome_id": "phase7.4-atomic-segmentation-successor-outcome-v2",
        "status": "PASS_v1_failure_retained_formal_overlay_v2_execution_authorized",
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "attempt_log_sha256": sha(ATTEMPTS),
        "formal_overlay_schema_v2_sha256": sha(SCHEMA_V2),
        "v1_authoritative_outputs_written": False,
        "v2_segmentation_execution_authorized": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(
    classification_hash: str, manifest_hash: str, outcome_hash: str
) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-atomic-segmentation-successor-v2-frozen",
        "event_type": "immutable_source_hash_failure_classification_and_formal_overlay_successor",
        "entry_head": ENTRY_HEAD,
        "attempt_log_sha256": sha(ATTEMPTS),
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "formal_overlay_schema_v2_sha256": sha(SCHEMA_V2),
        "classified_failure": "source_memory_hash_contract_mismatch",
        "v1_authoritative_outputs_written": False,
        "source_or_projection_mutated": False,
        "prototype_mutated": False,
        "sentence_algorithm_changed": False,
        "atomic_segmentation_executed_v2": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(
    classification_hash: str,
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v9_sha256": sha(STATE_V9),
        "phase7_4_readiness_v9_sha256": sha(READINESS_V9),
        "phase7_4_query_blind_atomic_segmentation_protocol_receipt_v1_sha256": sha(
            PROTOCOL_RECEIPT
        ),
        "phase7_4_atomic_segmentation_v1_attempt_log_sha256": sha(ATTEMPTS),
        "phase7_4_atomic_segmentation_successor_policy_v2_sha256": sha(POLICY),
        "phase7_4_atomic_evidence_overlay_schema_v2_sha256": sha(SCHEMA_V2),
        "phase7_4_atomic_segmentation_v1_failure_classification_sha256": classification_hash,
        "phase7_4_atomic_segmentation_successor_manifest_v2_sha256": manifest_hash,
        "phase7_4_atomic_segmentation_successor_outcome_v2_sha256": outcome_hash,
        "phase7_4_atomic_segmentation_successor_audit_v2_sha256": audit_hash,
    }


def state_document(
    classification_hash: str,
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 10,
        "state_id": "phase7.4-stage-state-v10",
        "status": "phase7_4_atomic_segmentation_v1_source_hash_failure_formal_overlay_v2_execution_authorized",
        "artifact_lineage": lineage(
            classification_hash, manifest_hash, outcome_hash, audit_hash
        ),
        "selected_source_content_frozen": True,
        "memory_only_segmentation_projection_frozen": True,
        "v1_execution_attempt_retained": True,
        "v1_failure_classified": True,
        "v1_classified_failure": "source_memory_hash_contract_mismatch",
        "v1_authoritative_outputs_written": False,
        "v1_same_version_retry_allowed": False,
        "formal_overlay_v2_schema_frozen": True,
        "formal_overlay_v2_execution_authorized": True,
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
    classification_hash: str,
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
    state_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 10,
        "readiness_id": "phase7.4-readiness-v10",
        "status": "PASS_v1_failure_classified_formal_overlay_v2_execution_ready",
        "artifact_lineage": {
            **lineage(
                classification_hash, manifest_hash, outcome_hash, audit_hash
            ),
            "phase7_4_stage_state_v10_sha256": state_hash,
        },
        "checks": {
            "v1_attempt_retained": True,
            "v1_outputs_absent": True,
            "source_and_projection_unchanged": True,
            "prototype_unchanged": True,
            "formal_overlay_schema_v2_valid": True,
            "sentence_algorithm_unchanged": True,
            "thresholds_unchanged": True,
            "effect_dataset_closed_to_arms": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "formal_overlay_v2_execution_authorized": True,
        "reference_protocol_freeze_authorized": False,
        "reference_review_authorized": False,
        "arm_execution_authorized": False,
        "effect_scoring_authorized": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def receipt_document(
    classification_hash: str,
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
    state_hash: str,
    readiness_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "receipt_id": "phase7.4-atomic-segmentation-successor-receipt-v2",
        "status": "PASS",
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v10_sha256": state_hash,
        "readiness_v10_sha256": readiness_hash,
        "attempt_log_sha256": sha(ATTEMPTS),
        "successor_policy_v2_sha256": sha(POLICY),
        "formal_overlay_schema_v2_sha256": sha(SCHEMA_V2),
        "v1_authoritative_outputs_written": False,
        "formal_overlay_v2_execution_authorized": True,
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
        state = load(STATE_V9)
        policy = load(POLICY)
        attempt = attempt_event()
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state_exact": state["status"] == ENTRY,
                "v1_was_authorized": state["next_authorized_stage"] == V1_AUTHORIZED,
                "policy_gate_exact": policy["entry_gate"] == FREEZE_GATE,
                "policy_next_exact": policy["next_authorized_stage_after_pass"] == NEXT,
                "attempt_class_exact": attempt["classified_failure"] == "source_memory_hash_contract_mismatch" and attempt["failure_taxonomy"] == "input_lineage_failure",
                "attempt_no_output": attempt["authoritative_outputs_written"] is False,
                "v1_outputs_absent": all(not path.exists() for path in V1_OUTPUTS),
                "formal_schema_valid": schema_valid(),
                "source_projection_unchanged": policy["source_hash_contract"]["source_dataset_and_projection_unchanged"] is True,
                "prototype_unchanged": policy["formal_overlay_contract"]["prototype_schema_or_constructor_modified"] is False,
                "sentence_algorithm_unchanged": policy["unchanged_segmentation_design"]["sentence_algorithm_id"] == load(PROTOCOL)["segmentation_algorithm"]["algorithm_id"],
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
    classification_hash = once(CLASSIFICATION, classification_document())
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(classification_hash, manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(classification_hash, manifest_hash, outcome_hash))
    state_hash = once(STATE_V10, state_document(classification_hash, manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(READINESS_V10, readiness_document(classification_hash, manifest_hash, outcome_hash, audit_hash, state_hash))
    receipt_hash = once(RECEIPT, receipt_document(classification_hash, manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash))
    return {
        "status": "PASS",
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v10_sha256": state_hash,
        "readiness_v10_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "classified_failure": "source_memory_hash_contract_mismatch",
        "v1_authoritative_outputs_written": False,
        "formal_overlay_v2_execution_authorized": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in OUTPUTS}
    if all(checks.values()):
        classification_hash = sha(CLASSIFICATION)
        manifest_hash = sha(MANIFEST)
        outcome_hash = sha(OUTCOME)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V10)
        readiness_hash = sha(READINESS_V10)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(path.exists() and sha(path) == digest for path, digest in EXPECTED.items()),
                "v1_outputs_absent": all(not path.exists() for path in V1_OUTPUTS),
                "classification_replay": load(CLASSIFICATION) == classification_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME) == outcome_document(classification_hash, manifest_hash),
                "audit_replay": AUDIT.read_bytes() == (canonical(audit_event(classification_hash, manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
                "state_v10_replay": load(STATE_V10) == state_document(classification_hash, manifest_hash, outcome_hash, audit_hash),
                "readiness_v10_replay": load(READINESS_V10) == readiness_document(classification_hash, manifest_hash, outcome_hash, audit_hash, state_hash),
                "receipt_replay": load(RECEIPT) == receipt_document(classification_hash, manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash),
                "next_gate_consistent": load(STATE_V10)["next_authorized_stage"] == load(READINESS_V10)["next_authorized_stage"] == load(RECEIPT)["next_authorized_stage"] == NEXT,
                "effect_dataset_closed": load(STATE_V10)["selected_effect_dataset_opened_for_arm_execution"] is False,
                "runtime_off": load(STATE_V10)["runtime_integration_authorized"] is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "v1_authoritative_outputs_written": False,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V10).get("selected_effect_dataset_opened_for_arm_execution") if STATE_V10.exists() else None,
        "runtime_integration_authorized": load(STATE_V10).get("runtime_integration_authorized") if STATE_V10.exists() else None,
        "next_authorized_stage": load(STATE_V10).get("next_authorized_stage") if STATE_V10.exists() else None,
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
