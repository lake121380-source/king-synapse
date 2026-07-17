#!/usr/bin/env python3
"""Execute the formal overlay v2 successor for Phase 7.4 segmentation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
DATASETS = ROOT / "crates/eval/datasets"
PATTERN = DATASETS / "pattern_extraction"
PHASE_DATA = DATASETS / "phase7_4"
REPORTS = ROOT / "crates/eval/reports"

V1_PYTHON = ROOT / "scripts/eval/phase7_4_query_blind_atomic_segmentation_v1.py"
V1_SPEC = importlib.util.spec_from_file_location(
    "phase7_4_query_blind_atomic_segmentation_v1", V1_PYTHON
)
if V1_SPEC is None or V1_SPEC.loader is None:
    raise RuntimeError("segmentation_v1_adapter_import_failed")
V1 = importlib.util.module_from_spec(V1_SPEC)
V1_SPEC.loader.exec_module(V1)

POLICY = CONFIG / "phase7_4_atomic_segmentation_successor_policy_v2.json"
SCHEMA_V2 = CONFIG / "phase7_4_atomic_evidence_overlay_schema_v2.json"
PROTOCOL = CONFIG / "phase7_4_query_blind_atomic_segmentation_protocol_v1.json"
PROJECTION = PHASE_DATA / "phase7_4_memory_only_segmentation_input_v1.json"
ATTEMPTS = REPORTS / "phase7_4_query_blind_atomic_segmentation_attempts_v1.jsonl"
SUCCESSOR_RECEIPT = REPORTS / "phase7_4_atomic_segmentation_successor_receipt_v2.json"
STATE_V10 = PATTERN / "phase7_4_stage_state_v10.json"
READINESS_V10 = REPORTS / "phase7_4_readiness_v10.json"
V1_RUST = ROOT / "crates/eval/src/bin/phase7_4_atomic_segmentation_v1.rs"
V2_RUST = ROOT / "crates/eval/src/bin/phase7_4_atomic_segmentation_v2.rs"
PROTOTYPE_RUST = ROOT / "crates/eval/src/phase7_4_atomic_evidence_shadow.rs"
ENVIRONMENT = CONFIG / "phase7_4_offline_retrieval_execution_environment_v1.json"

OVERLAYS = PHASE_DATA / "phase7_4_atomic_overlay_dataset_v2.json"
REPRESENTATION = REPORTS / "phase7_4_atomic_segmentation_representation_coverage_gate_v2.json"
FIXTURES = REPORTS / "phase7_4_query_blind_atomic_segmentation_fixtures_v2.json"
MANIFEST = REPORTS / "phase7_4_query_blind_atomic_segmentation_manifest_v2.json"
OUTCOME = REPORTS / "phase7_4_query_blind_atomic_segmentation_outcome_v2.json"
AUDIT = REPORTS / "phase7_4_query_blind_atomic_segmentation_audit_v2.jsonl"
STATE_V11 = PATTERN / "phase7_4_stage_state_v11.json"
READINESS_V11 = REPORTS / "phase7_4_readiness_v11.json"
RECEIPT = REPORTS / "phase7_4_query_blind_atomic_segmentation_receipt_v2.json"

V1_OUTPUTS = [
    PHASE_DATA / "phase7_4_atomic_overlay_dataset_v1.json",
    REPORTS / "phase7_4_atomic_segmentation_representation_coverage_gate_v1.json",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_fixtures_v1.json",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_manifest_v1.json",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_outcome_v1.json",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_audit_v1.jsonl",
    REPORTS / "phase7_4_query_blind_atomic_segmentation_receipt_v1.json",
]

ENTRY_HEAD = "2b3b6083ccff452886d85f8a8b9945d12f07fd2a"
ENTRY = "phase7_4_atomic_segmentation_v1_source_hash_failure_formal_overlay_v2_execution_authorized"
AUTHORIZED = "execute_phase7_4_query_blind_atomic_segmentation_v2"
NEXT = "freeze_phase7_4_independent_reference_protocol_v1"
CONTRACT_VERSION = "phase7.4-query-blind-sentence-segmentation-overlay-v2"

EXPECTED = {
    POLICY: "0d0aa0b6bf78fa1bddb2d6337d9975ba37ebdc97dddb1e088eec865c62f7c5b0",
    SCHEMA_V2: "865e5b4f9bf1bf49ce1d38d4b5084c307d3975382cc28195a8c30cd01750f790",
    PROTOCOL: "805a67a066328943d80175871df14dba1741588b9234ab0bf908a72a7f25a8a5",
    PROJECTION: "c27d60e89e273962b0b32bd4496fed1cac56d1009d8c65d002f5b50ff33cc07b",
    ATTEMPTS: "7de5b1f1017fa1f481b62e9ad0f8017cb7852478bd0c96c799fc660707002193",
    SUCCESSOR_RECEIPT: "c6d1f05e9327eb87bfc9f4364d961efeef7da213c7845fbbf2de1763758cae0b",
    STATE_V10: "5ef7f50767621d695fcb8e9e297facf8a120b328aa7fea2d83cea1ea6f7b7902",
    READINESS_V10: "c6593e30d8f78a517f1b2d9132c16f1c836e37b25597b05bf126df73224b6292",
    V1_PYTHON: "50cc5e69cd0f5e82ae85ea7bfc5ad04263a64b71f97ed8c6b0cd12b8a2400ec2",
    V1_RUST: "9b65f3077b40f47c3d76c27414243d68cb67b79dcddd8bdd5abf776c6aeea57d",
    V2_RUST: "e0d62c829fe626e561bd1ed7f79930ecfbb38bf0e03cc8ee110a2f1a079fff22",
    PROTOTYPE_RUST: "cfbaf4a564b098bf390024666d6ffe3017d38005cb0877be5f373be8cf8bc904",
    ENVIRONMENT: "5b5b02a7651da6fb7ef4d0a4c25efb76beb38bacd7f63a518ec06b168bdff786",
}

OUTPUTS = [
    OVERLAYS,
    REPRESENTATION,
    FIXTURES,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V11,
    READINESS_V11,
    RECEIPT,
]

V1.OVERLAY_SCHEMA = SCHEMA_V2
V1.CONSTRUCTOR_VERSION = CONTRACT_VERSION


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


def rust_unit_tests_pass() -> bool:
    result = run(
        [
            "cargo",
            "test",
            "--quiet",
            "-p",
            "synapse-eval",
            "--bin",
            "phase7_4_atomic_segmentation_v2",
        ]
    )
    return result.returncode == 0


def rust_execution() -> tuple[dict[str, Any], str]:
    command = [
        "cargo",
        "run",
        "--quiet",
        "-p",
        "synapse-eval",
        "--bin",
        "phase7_4_atomic_segmentation_v2",
        "--",
        "--input",
        str(PROJECTION),
    ]
    first = run(command)
    second = run(command)
    if first.returncode != 0:
        raise RuntimeError("formal_v2_first_run_failure:" + first.stderr.strip())
    if second.returncode != 0:
        raise RuntimeError("formal_v2_second_run_failure:" + second.stderr.strip())
    if first.stdout != second.stdout:
        raise RuntimeError("formal_v2_stdout_replay_mismatch")
    parsed = json.loads(first.stdout)
    parsed["rust_stdout_sha256"] = hb(first.stdout.encode("utf-8"))
    parsed["rust_replay_byte_identical"] = True
    parsed["rust_unit_tests_passed"] = True
    parsed["retained_v1_attempt_log_sha256"] = sha(ATTEMPTS)
    parsed["formal_overlay_schema_v2_sha256"] = sha(SCHEMA_V2)
    parsed["v1_authoritative_outputs_written"] = False
    return parsed, first.stdout


def validation(
    dataset: dict[str, Any], rust_stdout: str | None = None
) -> tuple[list[tuple[str, bool]], dict[str, Any]]:
    base_checks, diagnostics = V1.validation(dataset, rust_stdout)
    overlays = [
        overlay for case in dataset["cases"] for overlay in case["overlays"]
    ]
    successor_checks = [
        ("v1_authoritative_outputs_absent", all(not path.exists() for path in V1_OUTPUTS)),
        ("v1_attempt_retained", dataset["retained_v1_attempt_log_sha256"] == sha(ATTEMPTS)),
        ("formal_schema_hash_exact", dataset["formal_overlay_schema_v2_sha256"] == sha(SCHEMA_V2)),
        ("dataset_schema_version_v2", dataset["schema_version"] == 2),
        ("formal_overlay_roots_exact", all(overlay["schema_version"] == 2 and overlay["status"] == "eval_only_formal_atomic_overlay" and overlay["segmentation_contract_version"] == CONTRACT_VERSION for overlay in overlays)),
        ("source_projection_unchanged", load(POLICY)["source_hash_contract"]["source_dataset_and_projection_unchanged"] is True and sha(PROJECTION) == EXPECTED[PROJECTION]),
        ("prototype_unchanged", sha(PROTOTYPE_RUST) == EXPECTED[PROTOTYPE_RUST]),
        ("sentence_algorithm_unchanged", dataset["segmentation_algorithm_id"] == load(PROTOCOL)["segmentation_algorithm"]["algorithm_id"]),
        ("v1_authoritative_outputs_written_false", dataset["v1_authoritative_outputs_written"] is False),
    ]
    return [*base_checks, *successor_checks], diagnostics


def representation_document() -> dict[str, Any]:
    dataset = load(OVERLAYS)
    checks, diagnostics = validation(dataset)
    rows = [{"gate_check": name, "passed": passed} for name, passed in checks]
    passed = all(row["passed"] for row in rows)
    return {
        "schema_version": 2,
        "report_id": "phase7.4-atomic-segmentation-representation-coverage-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "segmentation_algorithm_id": dataset["segmentation_algorithm_id"],
        "formal_overlay_contract_version": CONTRACT_VERSION,
        "input_projection_sha256": sha(PROJECTION),
        "overlay_dataset_sha256": sha(OVERLAYS),
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "checks": rows,
        "diagnostics": diagnostics,
        "all_checks_passed": passed,
        "reference_protocol_freeze_authorized": passed,
        "reference_review_authorized": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT
        if passed
        else "freeze_authoritative_segmentation_or_representation_negative_result",
    }


def fixture_document() -> dict[str, Any]:
    checks, diagnostics = validation(load(OVERLAYS))
    rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 2,
        "fixtures_id": "phase7.4-query-blind-atomic-segmentation-fixtures-v2",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "fixtures": rows,
        "diagnostics": diagnostics,
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "retained_v1_attempt": True,
        "v1_authoritative_outputs_written": False,
        "query_access_count": 0,
        "gold_or_reference_access_count": 0,
        "arm_output_access_count": 0,
        "provider_call_count": 0,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
    }


def manifest_document() -> dict[str, Any]:
    dataset = load(OVERLAYS)
    return {
        "schema_version": 2,
        "manifest_id": "phase7.4-query-blind-atomic-segmentation-manifest-v2",
        "status": "frozen_formal_overlay_v2_query_blind_dataset",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "rust_execution_adapter_v2_sha256": sha(V2_RUST),
        "retained_v1_python_adapter_sha256": sha(V1_PYTHON),
        "retained_v1_rust_adapter_sha256": sha(V1_RUST),
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {rel(OVERLAYS): sha(OVERLAYS), rel(REPRESENTATION): sha(REPRESENTATION), rel(FIXTURES): sha(FIXTURES)},
        "rust_stdout_sha256": dataset["rust_stdout_sha256"],
        "rust_replay_byte_identical": dataset["rust_replay_byte_identical"],
        "case_count": 168,
        "memory_count": 1680,
        "atomic_unit_count": 3360,
        "v1_authoritative_outputs_written": False,
        "query_access_count": 0,
        "gold_or_reference_access_count": 0,
        "arm_output_access_count": 0,
        "provider_call_count": 0,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "outcome_id": "phase7.4-query-blind-atomic-segmentation-outcome-v2",
        "status": "PASS_formal_overlay_v2_representation_gate_reference_protocol_freeze_authorized",
        "manifest_sha256": manifest_hash,
        "overlay_dataset_sha256": sha(OVERLAYS),
        "representation_gate_sha256": sha(REPRESENTATION),
        "fixtures_sha256": sha(FIXTURES),
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "case_count": 168,
        "memory_count": 1680,
        "atomic_unit_count": 3360,
        "v1_authoritative_outputs_written": False,
        "reference_protocol_freeze_authorized": True,
        "reference_review_authorized": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-query-blind-atomic-segmentation-v2-frozen",
        "event_type": "immutable_formal_overlay_v2_and_representation_gate_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "overlay_dataset_sha256": sha(OVERLAYS),
        "representation_gate_sha256": sha(REPRESENTATION),
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "case_count": 168,
        "memory_count": 1680,
        "atomic_unit_count": 3360,
        "v1_authoritative_outputs_written": False,
        "query_access_count": 0,
        "gold_or_reference_access_count": 0,
        "arm_output_access_count": 0,
        "provider_call_count": 0,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v10_sha256": sha(STATE_V10),
        "phase7_4_readiness_v10_sha256": sha(READINESS_V10),
        "phase7_4_atomic_segmentation_successor_receipt_v2_sha256": sha(SUCCESSOR_RECEIPT),
        "phase7_4_atomic_segmentation_v1_attempt_log_sha256": sha(ATTEMPTS),
        "phase7_4_atomic_overlay_dataset_v2_sha256": sha(OVERLAYS),
        "phase7_4_atomic_segmentation_representation_coverage_gate_v2_sha256": sha(REPRESENTATION),
        "phase7_4_query_blind_atomic_segmentation_fixtures_v2_sha256": sha(FIXTURES),
        "phase7_4_query_blind_atomic_segmentation_manifest_v2_sha256": manifest_hash,
        "phase7_4_query_blind_atomic_segmentation_outcome_v2_sha256": outcome_hash,
        "phase7_4_query_blind_atomic_segmentation_audit_v2_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 11,
        "state_id": "phase7.4-stage-state-v11",
        "status": "phase7_4_formal_atomic_overlay_v2_representation_gate_passed_reference_protocol_freeze_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "selected_source_content_frozen": True,
        "memory_only_segmentation_projection_frozen": True,
        "v1_segmentation_failure_retained": True,
        "v1_authoritative_outputs_written": False,
        "formal_overlay_v2_execution_completed": True,
        "atomic_overlay_dataset_v2_frozen": True,
        "selected_case_count": 168,
        "source_memory_count": 1680,
        "atomic_unit_count": 3360,
        "representation_gate_passed": True,
        "evidence_coverage_gate_passed": True,
        "query_access_count": 0,
        "gold_or_reference_access_count": 0,
        "arm_output_access_count": 0,
        "reference_protocol_freeze_authorized": True,
        "reference_review_authorized": False,
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


def readiness_document(manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 11,
        "readiness_id": "phase7.4-readiness-v11",
        "status": "PASS_formal_atomic_overlay_v2_reference_protocol_freeze_ready",
        "artifact_lineage": {**lineage(manifest_hash, outcome_hash, audit_hash), "phase7_4_stage_state_v11_sha256": state_hash},
        "checks": {
            "v1_failure_retained": True,
            "v1_outputs_absent": True,
            "formal_overlay_v2_schema_passed": True,
            "rust_replay_byte_identical": True,
            "memory_and_atomic_counts_exact": True,
            "span_coverage_complete": True,
            "provenance_exact": True,
            "placeholders_not_gold": True,
            "representation_gate_passed": True,
            "evidence_coverage_gate_passed": True,
            "effect_dataset_closed_to_arms": True,
            "provider_not_called": True,
            "runtime_not_authorized": True
        },
        "reference_protocol_freeze_authorized": True,
        "reference_review_authorized": False,
        "gold_freeze_authorized": False,
        "arm_execution_authorized": False,
        "effect_scoring_authorized": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT
    }


def receipt_document(manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str, readiness_hash: str) -> dict[str, Any]:
    dataset = load(OVERLAYS)
    return {
        "schema_version": 2,
        "receipt_id": "phase7.4-query-blind-atomic-segmentation-receipt-v2",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v11_sha256": state_hash,
        "readiness_v11_sha256": readiness_hash,
        "overlay_dataset_sha256": sha(OVERLAYS),
        "representation_gate_sha256": sha(REPRESENTATION),
        "fixtures_sha256": sha(FIXTURES),
        "rust_stdout_sha256": dataset["rust_stdout_sha256"],
        "rust_replay_byte_identical": True,
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "case_count": 168,
        "memory_count": 1680,
        "atomic_unit_count": 3360,
        "v1_authoritative_outputs_written": False,
        "representation_and_coverage_gate_passed": True,
        "reference_protocol_freeze_authorized": True,
        "reference_review_authorized": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def preflight() -> dict[str, Any]:
    checks = {"input_hash:" + rel(path): path.exists() and sha(path) == digest for path, digest in EXPECTED.items()}
    if all(checks.values()):
        state = load(STATE_V10)
        policy = load(POLICY)
        checks.update({
            "entry_head_exact": git_head() == ENTRY_HEAD,
            "entry_state_exact": state["status"] == ENTRY,
            "entry_authority_exact": state["next_authorized_stage"] == AUTHORIZED,
            "policy_next_exact": policy["next_authorized_stage_after_pass"] == AUTHORIZED,
            "formal_v2_authorized": state["formal_overlay_v2_execution_authorized"] is True,
            "segmentation_not_already_executed": state["atomic_segmentation_executed"] is False,
            "v1_outputs_absent": all(not path.exists() for path in V1_OUTPUTS),
            "projection_query_blind": load(PROJECTION)["query_fields_copied"] is False,
            "reference_gold_and_arms_closed": state["reference_review_started"] is False and state["gold_frozen"] is False and state["arm_execution_started"] is False,
            "effect_dataset_closed": state["selected_effect_dataset_opened_for_arm_execution"] is False,
            "provider_not_called": state["phase7_4_effect_provider_called"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False,
            "rust_v2_unit_tests_pass": rust_unit_tests_pass(),
        })
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def execute() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    dataset, rust_stdout = rust_execution()
    checks, diagnostics = validation(dataset, rust_stdout)
    if not all(passed for _, passed in checks):
        return {"status": "FAIL", "failed": [name for name, passed in checks if not passed], "diagnostics": diagnostics, "authoritative_outputs_written": False}
    overlay_hash = once(OVERLAYS, dataset)
    representation_hash = once(REPRESENTATION, representation_document())
    fixtures_hash = once(FIXTURES, fixture_document())
    if not load(REPRESENTATION)["all_checks_passed"] or not load(FIXTURES)["all_fixtures_passed"]:
        raise RuntimeError("formal_v2_gate_or_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V11, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(READINESS_V11, readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash))
    receipt_hash = once(RECEIPT, receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash))
    return {
        "status": "PASS",
        "overlay_dataset_sha256": overlay_hash,
        "representation_gate_sha256": representation_hash,
        "fixtures_sha256": fixtures_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v11_sha256": state_hash,
        "readiness_v11_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "case_count": diagnostics["case_count"],
        "memory_count": diagnostics["memory_count"],
        "atomic_unit_count": diagnostics["atomic_unit_count"],
        "v1_authoritative_outputs_written": False,
        "representation_and_coverage_gate_passed": True,
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
        state_hash = sha(STATE_V11)
        readiness_hash = sha(READINESS_V11)
        replay_dataset, rust_stdout = rust_execution()
        checks.update({
            "entry_head_is_ancestor": entry_head_is_ancestor(),
            "input_hashes": all(path.exists() and sha(path) == digest for path, digest in EXPECTED.items()),
            "v1_outputs_absent": all(not path.exists() for path in V1_OUTPUTS),
            "overlay_dataset_replay": load(OVERLAYS) == replay_dataset,
            "rust_stdout_hash_replay": load(OVERLAYS)["rust_stdout_sha256"] == hb(rust_stdout.encode("utf-8")),
            "representation_replay": load(REPRESENTATION) == representation_document(),
            "fixtures_replay": load(FIXTURES) == fixture_document(),
            "manifest_replay": load(MANIFEST) == manifest_document(),
            "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
            "audit_replay": AUDIT.read_bytes() == (canonical(audit_event(manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
            "state_v11_replay": load(STATE_V11) == state_document(manifest_hash, outcome_hash, audit_hash),
            "readiness_v11_replay": load(READINESS_V11) == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
            "receipt_replay": load(RECEIPT) == receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash),
            "representation_gate_pass": load(REPRESENTATION)["all_checks_passed"] is True,
            "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
            "next_gate_consistent": load(STATE_V11)["next_authorized_stage"] == load(READINESS_V11)["next_authorized_stage"] == load(RECEIPT)["next_authorized_stage"] == NEXT,
            "effect_dataset_closed": load(STATE_V11)["selected_effect_dataset_opened_for_arm_execution"] is False,
            "runtime_off": load(STATE_V11)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "representation_and_coverage_gate_passed": load(STATE_V11).get("representation_gate_passed") if STATE_V11.exists() else None,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V11).get("selected_effect_dataset_opened_for_arm_execution") if STATE_V11.exists() else None,
        "runtime_integration_authorized": load(STATE_V11).get("runtime_integration_authorized") if STATE_V11.exists() else None,
        "next_authorized_stage": load(STATE_V11).get("next_authorized_stage") if STATE_V11.exists() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
    elif args.execute:
        result = execute()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
