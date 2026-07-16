#!/usr/bin/env python3
"""Validate and freeze the Phase 7.4.1 eval-only shadow implementation gate."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
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

DESIGN_DOC = DOCS / "PHASE7_4_ATOMIC_EVIDENCE_SUBSTRATE_DESIGN.md"
DESIGN_CONTRACT = CONFIG / "phase7_4_design_contract_v1.json"
PROTOCOL_DOC = DOCS / "eval/PHASE7_4_1_ATOMIC_EVIDENCE_SHADOW_PROTOTYPE_PROTOCOL.md"
OVERLAY_SCHEMA = CONFIG / "phase7_4_atomic_evidence_shadow_overlay_schema_v1.json"
PROTOCOL = CONFIG / "phase7_4_atomic_evidence_shadow_prototype_protocol_v1.json"
PROTOCOL_FIXTURES = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_fixtures_v1.json"
PROTOCOL_MANIFEST = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_manifest_v1.json"
PROTOCOL_OUTCOME = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_outcome_v1.json"
PROTOCOL_AUDIT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_audit_v1.jsonl"
PROTOCOL_RECEIPT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_receipt_v1.json"
STATE_V1 = PATTERN / "phase7_4_stage_state_v1.json"
READINESS_V1 = REPORTS / "phase7_4_readiness_v1.json"

PREDECESSOR_STATE = PATTERN / "phase7_3_3_d_support_stage_state_v111.json"
PREDECESSOR_READINESS = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v122.json"
PREDECESSOR_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_final_audit_report_v1.json"
PREDECESSOR_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_final_audit_receipt_v1.json"

EVAL_LIB = ROOT / "crates/eval/src/lib.rs"
IMPLEMENTATION = ROOT / "crates/eval/src/phase7_4_atomic_evidence_shadow.rs"
FIXTURE_RUNNER = ROOT / "crates/eval/src/bin/phase7_4_atomic_evidence_shadow.rs"
TESTS = ROOT / "crates/eval/tests/phase7_4_atomic_evidence_shadow_test.rs"
EVAL_CARGO = ROOT / "crates/eval/Cargo.toml"
CARGO_LOCK = ROOT / "Cargo.lock"

IMPLEMENTATION_FIXTURES = REPORTS / "phase7_4_atomic_evidence_shadow_implementation_fixtures_v1.json"
IMPLEMENTATION_MANIFEST = REPORTS / "phase7_4_atomic_evidence_shadow_implementation_manifest_v1.json"
GATE_REPORT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_report_v1.json"
NEGATIVE_RESULT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_negative_result_v1.json"
AUDIT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_audit_v1.jsonl"
STATE_V2 = PATTERN / "phase7_4_stage_state_v2.json"
READINESS_V2 = REPORTS / "phase7_4_readiness_v2.json"
RECEIPT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_receipt_v1.json"

ENTRY = "implement_phase7_4_eval_only_shadow_overlay_v1"
NEXT_PASS = "freeze_phase7_4_offline_retrieval_evaluation_protocol_v1"
NEXT_FAIL = "authoritative_prototype_contract_negative_result_frozen_no_same_version_retry"

EXPECTED_FROZEN_SHA256 = {
    DESIGN_DOC: "ec193194e37fcbf7e0074e9ed6db17910ecde45da74fa8f3d8fe29a178934a03",
    DESIGN_CONTRACT: "7e3680b434458f70c4ccff114b3d05db1a52348207e662ac4f65d48d80d6da91",
    PROTOCOL_DOC: "eda349de723c15ae7ff528554bde1ff6de39bc2cffd2fd398c033bb7382a81a7",
    OVERLAY_SCHEMA: "daa5b77f6b922180d5c60f480f594e6274e7ae8dd75e747ded26c442e2de0af7",
    PROTOCOL: "f727d431585ccbefd7f03f745706cee3ccdab7a7f96cfd3c52eb67d432795596",
    PROTOCOL_FIXTURES: "7f21b9f99c4804739cb95c70b09e74e30d64cfe9ac87882fbcb9c7d7d7385f25",
    PROTOCOL_MANIFEST: "b547a7907352b08e3f7b20ea375964ff986f47d2514dc1d6b1c74cd281c03da2",
    PROTOCOL_OUTCOME: "ebe5f0288446ada78641940ad8f2b6e75b751a703fe04863fc0372f9481e6210",
    PROTOCOL_AUDIT: "78aa2e7e4fc402782c5e962b2157c3fc83e7b38c22e54128870cd7b413aa5702",
    PROTOCOL_RECEIPT: "88b564d65e436cbc10eb76f3022686196a3c0ca7ef6c46e7f2891e142727202c",
    STATE_V1: "2d83da67c5eff92a4c3b3bf4876ff438c52c2248b34d6eb31cb8a4efe56ca3da",
    READINESS_V1: "2d8d2e9c0678963eb135b40d22562f8a5fcc0eb0084a9038b144d45becacba3d",
    PREDECESSOR_STATE: "bcd96ad07f1d64fe5b08ce2c28bb45b1f0a6e63bf35128cb034129e8c09a5d88",
    PREDECESSOR_READINESS: "42a4bc3a5202a16c30e9615d3a9bf4f35d1fda619f6edea6b84b2b0d4ee64bf8",
    PREDECESSOR_REPORT: "8f08360a85e164e19fadae13f77cf5eb67b73607f0344d2a4d8cf53475f6d0c7",
    PREDECESSOR_RECEIPT: "e5f1c8f32b079c9c4b62047afa225a0942d37b2c9d75b91883824b58faf9c694",
}

POSITIVE_TESTS = {
    "exact_two_unit_overlay_is_valid_and_eval_only": "two_unit_exact_nonoverlapping_spans",
    "evidence_id_locator_with_complete_provenance_is_valid": "evidence_id_locator_with_complete_provenance",
    "identical_input_replays_byte_identically": "byte_identical_deterministic_replay",
    "explicit_partial_reconstruction_preserves_gap_count": "explicit_partial_reconstruction",
    "all_existing_memory_kinds_are_accepted": "all_five_existing_memory_kinds",
    "canonical_json_has_sorted_root_keys_and_schema_shape": "canonical_json_schema_shape",
    "emitted_overlay_passes_serialized_integrity_validation": "serialized_integrity_round_trip",
    "multi_unit_overlay_passes_prototype_representation_gate": "representation_gate_positive",
}

REJECTION_TESTS = {
    "claimed_source_hash_mismatch_is_rejected": "source_hash_failure",
    "serialized_claim_text_hash_mismatch_is_rejected": "claim_hash_failure",
    "out_of_bounds_span_is_rejected": "span_boundary_failure",
    "source_excerpt_mismatch_is_rejected": "span_boundary_failure",
    "overlapping_spans_are_rejected": "span_overlap_failure",
    "duplicate_ordinal_is_rejected": "ordinal_failure",
    "skipped_ordinal_is_rejected": "ordinal_failure",
    "unknown_provenance_is_rejected": "provenance_failure",
    "nonfinite_or_out_of_bounds_confidence_is_rejected": "confidence_failure",
    "atomic_claim_memory_kind_is_rejected": "input_lineage_failure",
    "serialized_runtime_authority_claim_is_rejected": "authority_boundary_failure",
    "whole_memory_single_unit_is_recorded_but_fails_representation_gate": "representation_degeneracy",
    "inconsistent_reconstruction_status_is_rejected": "reconstruction_failure",
    "undeclared_text_span_gap_is_rejected": "reconstruction_failure",
}

OUTPUTS = {
    IMPLEMENTATION_FIXTURES,
    IMPLEMENTATION_MANIFEST,
    GATE_REPORT,
    NEGATIVE_RESULT,
    AUDIT,
    STATE_V2,
    READINESS_V2,
    RECEIPT,
}


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


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def command_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": result["command"],
        "exit_code": result["exit_code"],
        "passed": result["exit_code"] == 0,
    }


def version(command: list[str]) -> str:
    result = run(command)
    if result["exit_code"] != 0:
        return "unavailable"
    return result["stdout"].strip()


def changed_paths() -> list[str]:
    result = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    if result["exit_code"] != 0:
        return ["<git-status-unavailable>"]
    ignored = {rel(path) for path in OUTPUTS}
    paths = []
    for line in result["stdout"].splitlines():
        if len(line) < 4:
            continue
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path not in ignored:
            paths.append(path)
    return sorted(paths)


def path_is_allowed(path: str) -> bool:
    if path == "crates/eval/src/lib.rs":
        return True
    if path.startswith("crates/eval/") and "phase7_4" in path:
        return True
    if path.startswith("scripts/eval/phase7_4"):
        return True
    if path == "docs/PHASE7_4_ATOMIC_EVIDENCE_SUBSTRATE_DESIGN.md":
        return True
    if path == "docs/eval/PHASE7_4_1_ATOMIC_EVIDENCE_SHADOW_PROTOTYPE_PROTOCOL.md":
        return True
    return False


def implementation_sources() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in [IMPLEMENTATION, FIXTURE_RUNNER, TESTS]
    )


def static_boundary_checks() -> dict[str, bool]:
    paths = changed_paths()
    source = implementation_sources()
    dependency_patterns = [
        r"\bsynapse_core\b",
        r"\buse\s+synapse::",
        r"\bextern\s+crate\b",
    ]
    provider_patterns = [
        r"reqwest::",
        r"ureq::",
        r"std::net::",
        r"tokio::net::",
        r"Provider::",
        r"Command::new\(\s*\"curl\"",
    ]
    return {
        "all_changed_paths_version_isolated": bool(paths) and all(path_is_allowed(path) for path in paths),
        "no_core_path_changed": all(not path.startswith("crates/core/") for path in paths),
        "no_phase7_3_3_d_path_changed": all("phase7_3_3_d" not in path for path in paths),
        "no_core_crate_import": not any(re.search(pattern, source) for pattern in dependency_patterns),
        "no_network_or_provider_call_surface": not any(re.search(pattern, source) for pattern in provider_patterns),
        "no_phase7_3_3_d_effect_path_literal": "phase7_3_3_d" not in source
        and "datasets/pattern_extraction" not in source,
        "eval_cargo_manifest_unchanged": rel(EVAL_CARGO) not in paths,
        "cargo_lock_unchanged": rel(CARGO_LOCK) not in paths,
    }


def parse_test_names(output: str) -> list[str]:
    names = []
    for line in output.splitlines():
        match = re.fullmatch(r"([A-Za-z0-9_]+): test", line.strip())
        if match:
            names.append(match.group(1))
    return sorted(names)


def validate_synthetic_output(first: dict[str, Any] | None, second: dict[str, Any] | None) -> dict[str, Any]:
    checks: dict[str, bool] = {
        "runner_outputs_present": first is not None and second is not None,
        "runner_replay_byte_identical": first == second and first is not None,
    }
    errors: list[str] = []
    if first is None:
        checks.update(
            {
                "schema_conformance": False,
                "deterministic_identity": False,
                "canonical_overlay_hash": False,
                "authority_zero": False,
                "reconstruction_lineage_complete": False,
                "representation_gate_pass": False,
                "synthetic_only_no_effect_access": False,
            }
        )
        return {"checks": checks, "schema_errors": ["runner_output_unavailable"]}
    overlay = first.get("overlay")
    schema = load(OVERLAY_SCHEMA)
    try:
        Draft202012Validator.check_schema(schema)
        errors = sorted(error.message for error in Draft202012Validator(schema).iter_errors(overlay))
    except Exception as error:  # pragma: no cover - authoritative failure path
        errors = [f"schema_validator_error:{error}"]
    checks["schema_conformance"] = not errors
    canonical_overlay = canonical(overlay)
    checks["canonical_overlay_hash"] = (
        hb(canonical_overlay.encode("utf-8")) == first.get("canonical_overlay_json_sha256")
    )

    deterministic_identity = False
    authority_zero = False
    reconstruction_lineage = False
    if isinstance(overlay, dict):
        source_id = overlay.get("source_memory_id")
        source_hash = overlay.get("source_memory_sha256")
        contract_version = overlay.get("segmentation_contract_version")
        expected_overlay_id = "aes-v1-" + hb(
            f"phase7.4|{source_id}|{source_hash}|{contract_version}".encode("utf-8")
        )
        units = overlay.get("atomic_units", [])
        claim_ids = []
        unit_identity_checks = []
        for ordinal, unit in enumerate(units):
            claim_hash = hb(unit.get("claim_text", "").encode("utf-8"))
            expected_claim_id = "aes-claim-v1-" + hb(
                f"{expected_overlay_id}|{ordinal}|{claim_hash}".encode("utf-8")
            )
            claim_ids.append(unit.get("atomic_claim_id"))
            unit_identity_checks.append(
                unit.get("ordinal") == ordinal
                and unit.get("claim_text_sha256") == claim_hash
                and unit.get("atomic_claim_id") == expected_claim_id
            )
        deterministic_identity = overlay.get("overlay_id") == expected_overlay_id and all(
            unit_identity_checks
        )
        authority = overlay.get("authority", {})
        authority_zero = authority == {
            "eval_only": True,
            "runtime_applied": False,
            "memory_mutated": False,
            "store_written": False,
            "recall_engine_mutated": False,
            "promotion_authorized": False,
        }
        reconstruction = overlay.get("reconstruction", {})
        provenance_ok = all(
            unit.get("provenance", {}).get("source_memory_id") == source_id
            and unit.get("provenance", {}).get("source_memory_sha256") == source_hash
            for unit in units
        )
        reconstruction_lineage = (
            reconstruction.get("source_memory_id") == source_id
            and reconstruction.get("ordered_atomic_claim_ids") == claim_ids
            and reconstruction.get("status") == "complete"
            and reconstruction.get("unresolved_gap_count") == 0
            and provenance_ok
        )
    checks["deterministic_identity"] = deterministic_identity
    checks["authority_zero"] = authority_zero
    checks["reconstruction_lineage_complete"] = reconstruction_lineage
    representation = first.get("representation", {})
    checks["representation_gate_pass"] = (
        representation.get("passed") is True
        and representation.get("atomic_unit_count_gt_memory_chunk_count") is True
        and representation.get("whole_memory_single_unit_degeneracy") is False
    )
    checks["synthetic_only_no_effect_access"] = (
        first.get("synthetic_only") is True
        and first.get("effect_dataset_opened") is False
        and first.get("provider_called") is False
        and first.get("runtime_integration_authorized") is False
    )
    return {"checks": checks, "schema_errors": errors}


def execute_fixtures() -> dict[str, Any]:
    fmt = run(["cargo", "fmt", "--check"])
    tests = run(
        [
            "cargo",
            "test",
            "-p",
            "synapse-eval",
            "--test",
            "phase7_4_atomic_evidence_shadow_test",
            "--",
            "--test-threads=1",
        ]
    )
    listed = run(
        [
            "cargo",
            "test",
            "-q",
            "-p",
            "synapse-eval",
            "--test",
            "phase7_4_atomic_evidence_shadow_test",
            "--",
            "--list",
        ]
    )
    checked = run(["cargo", "check", "-p", "synapse-eval"])
    runner_command = [
        "cargo",
        "run",
        "-q",
        "-p",
        "synapse-eval",
        "--bin",
        "phase7_4_atomic_evidence_shadow",
        "--",
        "--emit-fixture",
    ]
    first_run = run(runner_command)
    second_run = run(runner_command)
    first = None
    second = None
    try:
        if first_run["exit_code"] == 0:
            first = json.loads(first_run["stdout"])
        if second_run["exit_code"] == 0:
            second = json.loads(second_run["stdout"])
    except json.JSONDecodeError:
        first = None
        second = None
    observed_tests = parse_test_names(listed["stdout"])
    expected_tests = sorted(set(POSITIVE_TESTS) | set(REJECTION_TESTS))
    test_suite_passed = tests["exit_code"] == 0 and listed["exit_code"] == 0
    rows = []
    for test_name, fixture_id in sorted(POSITIVE_TESTS.items()):
        rows.append(
            {
                "fixture_id": fixture_id,
                "test_name": test_name,
                "fixture_class": "positive",
                "expected_outcome": "accepted_or_gate_pass_recorded",
                "passed": test_suite_passed and test_name in observed_tests,
            }
        )
    for test_name, reason in sorted(REJECTION_TESTS.items()):
        rows.append(
            {
                "fixture_id": test_name.removesuffix("_is_rejected"),
                "test_name": test_name,
                "fixture_class": "rejection",
                "expected_failure_kind": reason,
                "passed": test_suite_passed and test_name in observed_tests,
            }
        )
    synthetic_validation = validate_synthetic_output(first, second)
    boundary = static_boundary_checks()
    commands = {
        "cargo_fmt_check": command_summary(fmt),
        "targeted_contract_tests": command_summary(tests),
        "targeted_contract_test_inventory": command_summary(listed),
        "cargo_check_synapse_eval": command_summary(checked),
        "synthetic_runner_first": command_summary(first_run),
        "synthetic_runner_replay": command_summary(second_run),
    }
    all_passed = (
        all(item["passed"] for item in rows)
        and observed_tests == expected_tests
        and all(item["passed"] for item in commands.values())
        and all(synthetic_validation["checks"].values())
        and all(boundary.values())
    )
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4.1-atomic-evidence-shadow-implementation-fixtures-v1",
        "status": "PASS" if all_passed else "FAIL",
        "synthetic_only": True,
        "fixture_count": len(rows),
        "passed_fixture_count": sum(item["passed"] for item in rows),
        "failed_fixture_count": sum(not item["passed"] for item in rows),
        "observed_test_count": len(observed_tests),
        "expected_test_count": len(expected_tests),
        "observed_tests_exact": observed_tests == expected_tests,
        "fixtures": rows,
        "commands": commands,
        "synthetic_validation": synthetic_validation,
        "implementation_boundary": boundary,
        "synthetic_runner_output": first,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "runtime_integration_authorized": False,
        "all_fixtures_passed": all_passed,
    }


def implementation_hashes() -> dict[str, str]:
    return {
        rel(path): sha(path)
        for path in [SELF, EVAL_LIB, IMPLEMENTATION, FIXTURE_RUNNER, TESTS, EVAL_CARGO, CARGO_LOCK]
    }


def environment_document() -> dict[str, Any]:
    rustc_verbose = version(["rustc", "-vV"])
    return {
        "python": sys.version.split()[0],
        "jsonschema": importlib.metadata.version("jsonschema"),
        "cargo": version(["cargo", "--version"]),
        "rustc": version(["rustc", "--version"]),
        "rustc_verbose_sha256": hb(rustc_verbose.encode("utf-8")),
        "git_head": version(["git", "rev-parse", "HEAD"]),
        "working_tree_commit_created": False,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4.1-atomic-evidence-shadow-implementation-manifest-v1",
        "status": "implementation_frozen_for_prototype_gate",
        "entry_gate": ENTRY,
        "execution_mode": "offline_deterministic_synthetic_eval_only",
        "frozen_protocol_inputs": {
            rel(path): digest for path, digest in EXPECTED_FROZEN_SHA256.items()
        },
        "implementation_artifacts": implementation_hashes(),
        "implementation_fixtures_sha256": sha(IMPLEMENTATION_FIXTURES),
        "execution_environment": environment_document(),
        "observed_changed_paths_excluding_gate_outputs": changed_paths(),
        "no_commit_or_push_performed": True,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "memory_kind_modified": False,
        "memory_schema_modified": False,
        "recall_engine_modified": False,
        "production_write_path_modified": False,
        "runtime_integration_authorized": False,
    }


def gate_document(manifest_hash: str) -> dict[str, Any]:
    fixtures = load(IMPLEMENTATION_FIXTURES)
    synthetic = fixtures["synthetic_validation"]["checks"]
    boundary = fixtures["implementation_boundary"]
    rows_by_class = {
        fixture_class: [row for row in fixtures["fixtures"] if row["fixture_class"] == fixture_class]
        for fixture_class in ["positive", "rejection"]
    }
    schema = load(OVERLAY_SCHEMA)
    memory_kinds = schema["properties"]["source_memory_kind"]["enum"]
    checks = [
        {
            "check_id": "schema_conformance",
            "passed": synthetic["schema_conformance"] and synthetic["canonical_overlay_hash"],
        },
        {
            "check_id": "deterministic_ids_and_serialization",
            "passed": synthetic["deterministic_identity"]
            and synthetic["runner_replay_byte_identical"],
        },
        {
            "check_id": "positive_fixtures_accepted",
            "passed": all(row["passed"] for row in rows_by_class["positive"]),
        },
        {
            "check_id": "rejection_fixtures_rejected_with_frozen_reason_codes",
            "passed": all(row["passed"] for row in rows_by_class["rejection"]),
        },
        {
            "check_id": "no_store_recall_engine_runtime_or_write_dependency",
            "passed": boundary["all_changed_paths_version_isolated"]
            and boundary["no_core_path_changed"]
            and boundary["no_core_crate_import"]
            and boundary["eval_cargo_manifest_unchanged"],
        },
        {
            "check_id": "no_new_memory_kind",
            "passed": memory_kinds == ["fact", "preference", "failure", "playbook", "state"]
            and "atomic_claim" not in memory_kinds
            and boundary["no_core_path_changed"],
        },
        {
            "check_id": "no_provider_call",
            "passed": boundary["no_network_or_provider_call_surface"]
            and synthetic["synthetic_only_no_effect_access"],
        },
        {
            "check_id": "no_phase7_3_3_d_effect_data_access",
            "passed": boundary["no_phase7_3_3_d_path_changed"]
            and boundary["no_phase7_3_3_d_effect_path_literal"]
            and fixtures["phase7_3_3_d_effect_data_loaded"] is False,
        },
        {
            "check_id": "zero_runtime_persistence_mutation_promotion_and_learning_authority",
            "passed": synthetic["authority_zero"]
            and fixtures["runtime_integration_authorized"] is False,
        },
        {
            "check_id": "source_reconstruction_lineage_complete",
            "passed": synthetic["reconstruction_lineage_complete"]
            and synthetic["representation_gate_pass"],
        },
        {
            "check_id": "version_isolated_sha256_manifest",
            "passed": len(manifest_hash) == 64
            and all(len(value) == 64 for value in implementation_hashes().values())
            and all(EXPECTED_FROZEN_SHA256[path] == sha(path) for path in EXPECTED_FROZEN_SHA256),
        },
        {
            "check_id": "deterministic_replay_and_receipt_pass",
            "passed": fixtures["all_fixtures_passed"]
            and synthetic["runner_replay_byte_identical"]
            and manifest_hash == sha(IMPLEMENTATION_MANIFEST),
            "receipt_issuance_preconditions_satisfied": fixtures["all_fixtures_passed"]
            and synthetic["runner_replay_byte_identical"]
            and manifest_hash == sha(IMPLEMENTATION_MANIFEST),
        },
    ]
    frozen_check_ids = load(PROTOCOL)["prototype_gate"]["checks"]
    exact_gate_inventory = [check["check_id"] for check in checks] == frozen_check_ids
    all_passed = exact_gate_inventory and all(check["passed"] for check in checks)
    return {
        "schema_version": 1,
        "gate_id": "phase7.4.1-atomic-evidence-shadow-prototype-gate-v1",
        "status": "PASS_shadow_prototype_frozen_offline_retrieval_protocol_authorized"
        if all_passed
        else "FAIL_authoritative_prototype_contract_negative_result_required",
        "manifest_sha256": manifest_hash,
        "implementation_fixtures_sha256": sha(IMPLEMENTATION_FIXTURES),
        "frozen_gate_check_inventory_exact": exact_gate_inventory,
        "check_count": len(checks),
        "passed_check_count": sum(check["passed"] for check in checks),
        "failed_check_count": sum(not check["passed"] for check in checks),
        "checks": checks,
        "representation_gate_passed": synthetic["representation_gate_pass"],
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "runtime_integration_authorized": False,
        "all_checks_passed": all_passed,
        "same_version_semantic_retry_allowed": False,
        "next_authorized_stage": NEXT_PASS if all_passed else NEXT_FAIL,
    }


def negative_document(manifest_hash: str, gate_hash: str) -> dict[str, Any]:
    gate = load(GATE_REPORT)
    return {
        "schema_version": 1,
        "negative_result_id": "phase7.4.1-atomic-evidence-shadow-prototype-negative-result-v1",
        "status": "authoritative_prototype_contract_negative_result_frozen",
        "manifest_sha256": manifest_hash,
        "gate_report_sha256": gate_hash,
        "implementation_fixtures_sha256": sha(IMPLEMENTATION_FIXTURES),
        "failed_checks": [check["check_id"] for check in gate["checks"] if not check["passed"]],
        "same_version_semantic_retry_allowed": False,
        "phase7_4_effect_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT_FAIL,
    }


def audit_event(
    manifest_hash: str, gate_hash: str, negative_hash: str | None
) -> dict[str, Any]:
    passed = load(GATE_REPORT)["all_checks_passed"]
    event = {
        "event_id": "phase7.4.1-atomic-evidence-shadow-prototype-gate-v1",
        "event_type": "immutable_prototype_gate_pass"
        if passed
        else "authoritative_prototype_contract_negative_result",
        "manifest_sha256": manifest_hash,
        "implementation_fixtures_sha256": sha(IMPLEMENTATION_FIXTURES),
        "gate_report_sha256": gate_hash,
        "gate_passed": passed,
        "effect_dataset_opened": False,
        "provider_called": False,
        "predecessor_mutated": False,
        "runtime_integration_authorized": False,
        "same_version_semantic_retry_allowed": False,
        "next_authorized_stage": NEXT_PASS if passed else NEXT_FAIL,
    }
    if negative_hash is not None:
        event["negative_result_sha256"] = negative_hash
    return event


def artifact_lineage(
    manifest_hash: str,
    gate_hash: str,
    audit_hash: str,
    negative_hash: str | None,
) -> dict[str, str]:
    lineage = {
        "phase7_4_stage_state_v1_sha256": sha(STATE_V1),
        "phase7_4_readiness_v1_sha256": sha(READINESS_V1),
        "phase7_4_shadow_prototype_protocol_freeze_receipt_v1_sha256": sha(PROTOCOL_RECEIPT),
        "phase7_4_shadow_implementation_fixtures_v1_sha256": sha(IMPLEMENTATION_FIXTURES),
        "phase7_4_shadow_implementation_manifest_v1_sha256": manifest_hash,
        "phase7_4_shadow_prototype_gate_report_v1_sha256": gate_hash,
        "phase7_4_shadow_prototype_gate_audit_v1_sha256": audit_hash,
    }
    if negative_hash is not None:
        lineage["phase7_4_shadow_prototype_negative_result_v1_sha256"] = negative_hash
    return lineage


def state_document(
    manifest_hash: str,
    gate_hash: str,
    audit_hash: str,
    negative_hash: str | None,
) -> dict[str, Any]:
    passed = load(GATE_REPORT)["all_checks_passed"]
    return {
        "schema_version": 2,
        "state_id": "phase7.4-stage-state-v2",
        "status": "phase7_4_1_shadow_prototype_gate_passed_offline_retrieval_protocol_authorized"
        if passed
        else "phase7_4_1_authoritative_prototype_contract_negative_result_frozen",
        "predecessor_phase": "phase7_3_3_d",
        "predecessor_terminal_gate": "confirmatory_success_frozen_runtime_integration_not_authorized",
        "predecessor_mutated": False,
        "artifact_lineage": artifact_lineage(
            manifest_hash, gate_hash, audit_hash, negative_hash
        ),
        "phase7_4_design_frozen": True,
        "phase7_4_shadow_prototype_protocol_frozen": True,
        "phase7_4_shadow_prototype_implementation_started": True,
        "phase7_4_shadow_prototype_implementation_completed": True,
        "phase7_4_shadow_prototype_gate_passed": passed,
        "phase7_4_representation_gate_passed": load(GATE_REPORT)["representation_gate_passed"],
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "memory_kind_modification_authorized": False,
        "memory_schema_modification_authorized": False,
        "recall_engine_modification_authorized": False,
        "production_memory_write_authorized": False,
        "runtime_integration_authorized": False,
        "same_version_semantic_retry_allowed": False,
        "next_authorized_stage": NEXT_PASS if passed else NEXT_FAIL,
    }


def readiness_document(
    manifest_hash: str,
    gate_hash: str,
    audit_hash: str,
    negative_hash: str | None,
    state_hash: str,
) -> dict[str, Any]:
    passed = load(GATE_REPORT)["all_checks_passed"]
    return {
        "schema_version": 2,
        "readiness_id": "phase7.4-readiness-v2",
        "status": "PASS_shadow_prototype_gate_offline_retrieval_protocol_authorized"
        if passed
        else "FAIL_authoritative_prototype_contract_negative_result_frozen",
        "artifact_lineage": {
            **artifact_lineage(manifest_hash, gate_hash, audit_hash, negative_hash),
            "phase7_4_stage_state_v2_sha256": state_hash,
        },
        "checks": {
            "frozen_protocol_inputs_unchanged": all(
                sha(path) == digest for path, digest in EXPECTED_FROZEN_SHA256.items()
            ),
            "implementation_fixtures_pass": load(IMPLEMENTATION_FIXTURES)["all_fixtures_passed"],
            "prototype_gate_pass": passed,
            "representation_gate_pass": load(GATE_REPORT)["representation_gate_passed"],
            "predecessor_read_only": True,
            "effect_dataset_closed": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "offline_retrieval_protocol_freeze_authorized": passed,
        "offline_retrieval_effect_execution_authorized": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "same_version_semantic_retry_allowed": False,
        "next_authorized_stage": NEXT_PASS if passed else NEXT_FAIL,
    }


def receipt_document(
    manifest_hash: str,
    gate_hash: str,
    audit_hash: str,
    negative_hash: str | None,
    state_hash: str,
    readiness_hash: str,
) -> dict[str, Any]:
    passed = load(GATE_REPORT)["all_checks_passed"]
    receipt = {
        "schema_version": 1,
        "receipt_id": "phase7.4.1-atomic-evidence-shadow-prototype-gate-receipt-v1",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT_FROZEN",
        "implementation_fixtures_sha256": sha(IMPLEMENTATION_FIXTURES),
        "implementation_manifest_sha256": manifest_hash,
        "gate_report_sha256": gate_hash,
        "audit_log_sha256": audit_hash,
        "state_v2_sha256": state_hash,
        "readiness_v2_sha256": readiness_hash,
        "gate_check_count": load(GATE_REPORT)["check_count"],
        "failed_gate_check_count": load(GATE_REPORT)["failed_check_count"],
        "representation_gate_passed": load(GATE_REPORT)["representation_gate_passed"],
        "predecessor_mutated": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "same_version_semantic_retry_allowed": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT_PASS if passed else NEXT_FAIL,
    }
    if negative_hash is not None:
        receipt["negative_result_sha256"] = negative_hash
    return receipt


def preflight() -> dict[str, Any]:
    checks = {
        "frozen_input_hash:" + rel(path): path.exists() and sha(path) == digest
        for path, digest in EXPECTED_FROZEN_SHA256.items()
    }
    required_implementation = [EVAL_LIB, IMPLEMENTATION, FIXTURE_RUNNER, TESTS, EVAL_CARGO, CARGO_LOCK]
    checks.update(
        {
            "implementation_artifacts_present": all(path.exists() for path in required_implementation),
            "state_v1_authorizes_entry": load(STATE_V1).get("next_authorized_stage") == ENTRY
            if STATE_V1.exists()
            else False,
            "readiness_v1_authorizes_entry": load(READINESS_V1).get("next_authorized_stage") == ENTRY
            if READINESS_V1.exists()
            else False,
            "effect_dataset_closed": load(STATE_V1).get("phase7_4_effect_dataset_opened") is False
            if STATE_V1.exists()
            else False,
            "provider_not_called": load(STATE_V1).get("phase7_4_effect_provider_called") is False
            if STATE_V1.exists()
            else False,
            "runtime_not_authorized": load(STATE_V1).get("runtime_integration_authorized") is False
            if STATE_V1.exists()
            else False,
            "outputs_absent": all(not path.exists() for path in OUTPUTS),
        }
    )
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def freeze() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    fixtures_hash = once(IMPLEMENTATION_FIXTURES, execute_fixtures())
    manifest_hash = once(IMPLEMENTATION_MANIFEST, manifest_document())
    gate_hash = once(GATE_REPORT, gate_document(manifest_hash))
    negative_hash = None
    if not load(GATE_REPORT)["all_checks_passed"]:
        negative_hash = once(NEGATIVE_RESULT, negative_document(manifest_hash, gate_hash))
    audit_hash = append_single_event(
        AUDIT, audit_event(manifest_hash, gate_hash, negative_hash)
    )
    state_hash = once(
        STATE_V2,
        state_document(manifest_hash, gate_hash, audit_hash, negative_hash),
    )
    readiness_hash = once(
        READINESS_V2,
        readiness_document(
            manifest_hash, gate_hash, audit_hash, negative_hash, state_hash
        ),
    )
    receipt_hash = once(
        RECEIPT,
        receipt_document(
            manifest_hash,
            gate_hash,
            audit_hash,
            negative_hash,
            state_hash,
            readiness_hash,
        ),
    )
    passed = load(GATE_REPORT)["all_checks_passed"]
    return {
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT_FROZEN",
        "implementation_fixtures_sha256": fixtures_hash,
        "implementation_manifest_sha256": manifest_hash,
        "gate_report_sha256": gate_hash,
        "negative_result_sha256": negative_hash,
        "audit_sha256": audit_hash,
        "state_v2_sha256": state_hash,
        "readiness_v2_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "gate_check_count": load(GATE_REPORT)["check_count"],
        "failed_gate_check_count": load(GATE_REPORT)["failed_check_count"],
        "phase7_4_effect_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT_PASS if passed else NEXT_FAIL,
    }


def verify() -> dict[str, Any]:
    required = [
        IMPLEMENTATION_FIXTURES,
        IMPLEMENTATION_MANIFEST,
        GATE_REPORT,
        AUDIT,
        STATE_V2,
        READINESS_V2,
        RECEIPT,
    ]
    checks = {"exists:" + rel(path): path.exists() for path in required}
    if all(checks.values()):
        replay_fixtures = execute_fixtures()
        manifest_hash = sha(IMPLEMENTATION_MANIFEST)
        gate_hash = sha(GATE_REPORT)
        negative_hash = sha(NEGATIVE_RESULT) if NEGATIVE_RESULT.exists() else None
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V2)
        readiness_hash = sha(READINESS_V2)
        checks.update(
            {
                "frozen_input_hashes": all(
                    path.exists() and sha(path) == digest
                    for path, digest in EXPECTED_FROZEN_SHA256.items()
                ),
                "implementation_fixtures_replay": load(IMPLEMENTATION_FIXTURES)
                == replay_fixtures,
                "implementation_manifest_replay": load(IMPLEMENTATION_MANIFEST)
                == manifest_document(),
                "gate_report_replay": load(GATE_REPORT) == gate_document(manifest_hash),
                "negative_result_presence_matches_gate": NEGATIVE_RESULT.exists()
                == (not load(GATE_REPORT)["all_checks_passed"]),
                "negative_result_replay": (
                    not NEGATIVE_RESULT.exists()
                    or load(NEGATIVE_RESULT) == negative_document(manifest_hash, gate_hash)
                ),
                "append_only_audit_replay": AUDIT.read_bytes()
                == (canonical(audit_event(manifest_hash, gate_hash, negative_hash)) + "\n").encode(
                    "utf-8"
                ),
                "state_v2_replay": load(STATE_V2)
                == state_document(manifest_hash, gate_hash, audit_hash, negative_hash),
                "readiness_v2_replay": load(READINESS_V2)
                == readiness_document(
                    manifest_hash, gate_hash, audit_hash, negative_hash, state_hash
                ),
                "receipt_replay": load(RECEIPT)
                == receipt_document(
                    manifest_hash,
                    gate_hash,
                    audit_hash,
                    negative_hash,
                    state_hash,
                    readiness_hash,
                ),
                "receipt_lineage": load(RECEIPT)["implementation_manifest_sha256"]
                == manifest_hash
                and load(RECEIPT)["gate_report_sha256"] == gate_hash
                and load(RECEIPT)["audit_log_sha256"] == audit_hash
                and load(RECEIPT)["state_v2_sha256"] == state_hash
                and load(RECEIPT)["readiness_v2_sha256"] == readiness_hash,
                "effect_dataset_closed": load(STATE_V2)["phase7_4_effect_dataset_opened"] is False,
                "provider_not_called": load(STATE_V2)["phase7_4_effect_provider_called"] is False,
                "runtime_not_authorized": load(STATE_V2)["runtime_integration_authorized"] is False
                and load(READINESS_V2)["runtime_integration_authorized"] is False,
                "next_gate_consistent": load(STATE_V2)["next_authorized_stage"]
                == load(READINESS_V2)["next_authorized_stage"]
                == load(RECEIPT)["next_authorized_stage"],
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "gate_passed": load(GATE_REPORT).get("all_checks_passed") if GATE_REPORT.exists() else None,
        "phase7_4_effect_dataset_opened": load(STATE_V2).get("phase7_4_effect_dataset_opened")
        if STATE_V2.exists()
        else None,
        "runtime_integration_authorized": load(STATE_V2).get("runtime_integration_authorized")
        if STATE_V2.exists()
        else None,
        "next_authorized_stage": load(STATE_V2).get("next_authorized_stage")
        if STATE_V2.exists()
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
        outcome = execute_fixtures()
    elif args.freeze:
        outcome = freeze()
    else:
        outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
