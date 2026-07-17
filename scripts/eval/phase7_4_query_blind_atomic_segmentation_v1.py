#!/usr/bin/env python3
"""Execute and freeze Phase 7.4 query-blind Atomic segmentation."""
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

PROTOCOL = CONFIG / "phase7_4_query_blind_atomic_segmentation_protocol_v1.json"
PROJECTION = PHASE_DATA / "phase7_4_memory_only_segmentation_input_v1.json"
STATE_V9 = PATTERN / "phase7_4_stage_state_v9.json"
READINESS_V9 = REPORTS / "phase7_4_readiness_v9.json"
PROTOCOL_RECEIPT = REPORTS / "phase7_4_query_blind_atomic_segmentation_protocol_receipt_v1.json"
OVERLAY_SCHEMA = CONFIG / "phase7_4_atomic_evidence_shadow_overlay_schema_v1.json"
RUST_CONSTRUCTOR = ROOT / "crates/eval/src/phase7_4_atomic_evidence_shadow.rs"
RUST_BIN = ROOT / "crates/eval/src/bin/phase7_4_atomic_segmentation_v1.rs"
ENVIRONMENT = CONFIG / "phase7_4_offline_retrieval_execution_environment_v1.json"

OVERLAYS = PHASE_DATA / "phase7_4_atomic_overlay_dataset_v1.json"
REPRESENTATION = REPORTS / "phase7_4_atomic_segmentation_representation_coverage_gate_v1.json"
FIXTURES = REPORTS / "phase7_4_query_blind_atomic_segmentation_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_4_query_blind_atomic_segmentation_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_query_blind_atomic_segmentation_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_query_blind_atomic_segmentation_audit_v1.jsonl"
STATE_V10 = PATTERN / "phase7_4_stage_state_v10.json"
READINESS_V10 = REPORTS / "phase7_4_readiness_v10.json"
RECEIPT = REPORTS / "phase7_4_query_blind_atomic_segmentation_receipt_v1.json"

ENTRY_HEAD = "dc1498d5a8ed26161bf93c77d5fcfde680e52c30"
ENTRY = "phase7_4_query_blind_atomic_segmentation_protocol_frozen_execution_authorized"
AUTHORIZED = "execute_phase7_4_query_blind_atomic_segmentation_v1"
NEXT = "freeze_phase7_4_independent_reference_protocol_v1"
CONSTRUCTOR_VERSION = "phase7.4-atomic-evidence-shadow-prototype-v1"

EXPECTED = {
    PROTOCOL: "805a67a066328943d80175871df14dba1741588b9234ab0bf908a72a7f25a8a5",
    PROJECTION: "c27d60e89e273962b0b32bd4496fed1cac56d1009d8c65d002f5b50ff33cc07b",
    STATE_V9: "e44de9f24d06aa8e2784ff0f48c10d1ce0faa2e42453e380bf5adebff929f3fd",
    READINESS_V9: "aca579a9e9d218cffcc8d9aada9cb1b7d439414e5813f6a82b4569d2115574bb",
    PROTOCOL_RECEIPT: "206fb82127f439130682cd24b40d5a84ed7b5952bea752d3b131a9581830e623",
    OVERLAY_SCHEMA: "daa5b77f6b922180d5c60f480f594e6274e7ae8dd75e747ded26c442e2de0af7",
    RUST_CONSTRUCTOR: "cfbaf4a564b098bf390024666d6ffe3017d38005cb0877be5f373be8cf8bc904",
    RUST_BIN: "9b65f3077b40f47c3d76c27414243d68cb67b79dcddd8bdd5abf776c6aeea57d",
    ENVIRONMENT: "5b5b02a7651da6fb7ef4d0a4c25efb76beb38bacd7f63a518ec06b168bdff786",
}

OUTPUTS = [
    OVERLAYS,
    REPRESENTATION,
    FIXTURES,
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


def rust_unit_tests_pass() -> bool:
    result = run(
        [
            "cargo",
            "test",
            "--quiet",
            "-p",
            "synapse-eval",
            "--bin",
            "phase7_4_atomic_segmentation_v1",
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
        "phase7_4_atomic_segmentation_v1",
        "--",
        "--input",
        str(PROJECTION),
    ]
    first = run(command)
    second = run(command)
    if first.returncode != 0:
        raise RuntimeError("rust_segmentation_first_run_failure:" + first.stderr.strip())
    if second.returncode != 0:
        raise RuntimeError("rust_segmentation_second_run_failure:" + second.stderr.strip())
    if first.stdout != second.stdout:
        raise RuntimeError("rust_segmentation_stdout_replay_mismatch")
    parsed = json.loads(first.stdout)
    parsed["rust_stdout_sha256"] = hb(first.stdout.encode("utf-8"))
    parsed["rust_replay_byte_identical"] = True
    parsed["rust_unit_tests_passed"] = True
    return parsed, first.stdout


def exact_span(source: str, start: int, end: int) -> str:
    return "".join(list(source)[start:end])


def validation(
    dataset: dict[str, Any], rust_stdout: str | None = None
) -> tuple[list[tuple[str, bool]], dict[str, Any]]:
    projection = load(PROJECTION)
    protocol = load(PROTOCOL)
    schema = load(OVERLAY_SCHEMA)
    validator = Draft202012Validator(schema)
    projected_cases = projection["cases"]
    segmented_cases = dataset["cases"]
    overlay_count = 0
    unit_count = 0
    whole_memory_single_unit_count = 0
    zero_unit_memory_count = 0
    span_out_of_bounds_count = 0
    span_overlap_count = 0
    uncovered_character_count = 0
    reconstruction_failure_count = 0
    schema_failure_count = 0
    provenance_failure_count = 0
    identity_failure_count = 0
    placeholder_failure_count = 0
    authority_failure_count = 0
    case_memory_alignment = True
    overlay_ids: list[str] = []
    claim_ids: list[str] = []
    strata = Counter()

    for projected_case, segmented_case in zip(
        projected_cases, segmented_cases, strict=True
    ):
        strata[segmented_case["stratum"]] += 1
        case_memory_alignment = (
            case_memory_alignment
            and projected_case["case_id"] == segmented_case["case_id"]
            and projected_case["stratum"] == segmented_case["stratum"]
            and len(projected_case["candidate_memories"])
            == len(segmented_case["overlays"])
        )
        for memory, overlay in zip(
            projected_case["candidate_memories"],
            segmented_case["overlays"],
            strict=True,
        ):
            overlay_count += 1
            units = overlay.get("atomic_units", [])
            unit_count += len(units)
            if not units:
                zero_unit_memory_count += 1
            source = memory["source_memory_content"]
            character_count = len(source)
            expected_overlay_id = "aes-v1-" + hb(
                f"phase7.4|{memory['source_memory_id']}|{memory['source_memory_sha256']}|{CONSTRUCTOR_VERSION}".encode(
                    "utf-8"
                )
            )
            if (
                overlay.get("overlay_id") != expected_overlay_id
                or overlay.get("source_memory_id") != memory["source_memory_id"]
                or overlay.get("source_memory_sha256")
                != memory["source_memory_sha256"]
                or overlay.get("source_memory_content_sha256")
                != memory["source_memory_content_sha256"]
                or overlay.get("source_memory_kind")
                != memory["source_memory_kind"]
                or overlay.get("segmentation_contract_version")
                != CONSTRUCTOR_VERSION
            ):
                identity_failure_count += 1
            overlay_ids.append(overlay.get("overlay_id", ""))
            schema_errors = list(validator.iter_errors(overlay))
            if schema_errors:
                schema_failure_count += 1

            cursor = 0
            ordered_claim_ids = []
            for ordinal, unit in enumerate(units):
                locator = unit.get("source_locator", {})
                start = locator.get("start_char", -1)
                end = locator.get("end_char", -1)
                if (
                    locator.get("locator_type") != "source_memory_text_span"
                    or not isinstance(start, int)
                    or not isinstance(end, int)
                    or start < 0
                    or end > character_count
                    or start >= end
                ):
                    span_out_of_bounds_count += 1
                    continue
                if start < cursor:
                    span_overlap_count += 1
                if start > cursor:
                    uncovered_character_count += start - cursor
                cursor = max(cursor, end)
                claim_text = unit.get("claim_text", "")
                claim_hash = hb(claim_text.encode("utf-8"))
                expected_claim_id = "aes-claim-v1-" + hb(
                    f"{expected_overlay_id}|{ordinal}|{claim_hash}".encode("utf-8")
                )
                if (
                    unit.get("ordinal") != ordinal
                    or unit.get("claim_text_sha256") != claim_hash
                    or unit.get("atomic_claim_id") != expected_claim_id
                    or exact_span(source, start, end) != claim_text
                ):
                    identity_failure_count += 1
                claim_ids.append(unit.get("atomic_claim_id", ""))
                ordered_claim_ids.append(unit.get("atomic_claim_id", ""))
                provenance = unit.get("provenance", {})
                if (
                    provenance.get("source_memory_id")
                    != memory["source_memory_id"]
                    or provenance.get("source_memory_sha256")
                    != memory["source_memory_sha256"]
                    or provenance.get("source_evidence_ids")
                    != memory["source_evidence_ids"]
                    or provenance.get("source_event_ids")
                    != memory["source_event_ids"]
                ):
                    provenance_failure_count += 1
                confidence = unit.get("confidence", {})
                if (
                    unit.get("support_state") != "not_assessable"
                    or confidence.get("support_confidence") != 0.0
                    or confidence.get("extraction_confidence") != 1.0
                    or confidence.get("calibration_status") != "not_assessable"
                    or unit.get("contradiction_links") != []
                ):
                    placeholder_failure_count += 1
            if cursor < character_count:
                uncovered_character_count += character_count - cursor
            if len(units) == 1:
                locator = units[0].get("source_locator", {})
                if (
                    locator.get("start_char") == 0
                    and locator.get("end_char") == character_count
                ):
                    whole_memory_single_unit_count += 1
            reconstruction = overlay.get("reconstruction", {})
            if (
                reconstruction.get("source_memory_id")
                != memory["source_memory_id"]
                or reconstruction.get("ordered_atomic_claim_ids")
                != ordered_claim_ids
                or reconstruction.get("status") != "complete"
                or reconstruction.get("deterministic") is not True
                or reconstruction.get("overlap_characters") != 0
                or reconstruction.get("unresolved_gap_count") != 0
            ):
                reconstruction_failure_count += 1
            if overlay.get("authority") != {
                "eval_only": True,
                "memory_mutated": False,
                "promotion_authorized": False,
                "recall_engine_mutated": False,
                "runtime_applied": False,
                "store_written": False,
            }:
                authority_failure_count += 1

    forbidden_output_fields = {
        "query",
        "query_id",
        "expected_answer",
        "relevant_memory_ids",
        "evidence_spans",
        "gold_label",
        "arm_output",
        "arm_score",
        "analysis_result",
    }

    def contains_forbidden(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                key in forbidden_output_fields or contains_forbidden(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(contains_forbidden(item) for item in value)
        return False

    expected_counts = protocol["representation_and_coverage_gate"]
    checks = [
        ("rust_unit_tests_passed", dataset.get("rust_unit_tests_passed") is True),
        ("rust_stdout_replay_byte_identical", dataset.get("rust_replay_byte_identical") is True),
        ("rust_stdout_hash_replays", rust_stdout is None or dataset.get("rust_stdout_sha256") == hb(rust_stdout.encode("utf-8"))),
        ("projection_hash_exact", dataset["input_projection_sha256"] == sha(PROJECTION)),
        ("algorithm_and_constructor_exact", dataset["segmentation_algorithm_id"] == protocol["segmentation_algorithm"]["algorithm_id"] and dataset["overlay_constructor_contract_version"] == CONSTRUCTOR_VERSION),
        ("case_count_168", dataset["case_count"] == len(segmented_cases) == expected_counts["case_count"]),
        ("eight_strata_twenty_one_each", len(strata) == 8 and set(strata.values()) == {21}),
        ("case_memory_alignment_exact", case_memory_alignment),
        ("memory_count_1680", dataset["memory_count"] == overlay_count == expected_counts["memory_chunk_count"]),
        ("atomic_unit_count_3360", dataset["atomic_unit_count"] == unit_count == expected_counts["atomic_unit_count"]),
        ("exactly_two_units_per_memory", unit_count == overlay_count * 2),
        ("atomic_units_gt_memory_chunks", unit_count > overlay_count),
        ("whole_memory_single_unit_count_zero", whole_memory_single_unit_count == 0),
        ("zero_unit_memory_count_zero", zero_unit_memory_count == 0),
        ("span_out_of_bounds_count_zero", span_out_of_bounds_count == 0),
        ("span_overlap_count_zero", span_overlap_count == 0),
        ("uncovered_character_count_zero", uncovered_character_count == 0),
        ("reconstruction_failure_count_zero", reconstruction_failure_count == 0),
        ("overlay_schema_failure_count_zero", schema_failure_count == 0),
        ("provenance_failure_count_zero", provenance_failure_count == 0),
        ("identity_failure_count_zero", identity_failure_count == 0),
        ("placeholder_failure_count_zero", placeholder_failure_count == 0),
        ("authority_failure_count_zero", authority_failure_count == 0),
        ("overlay_ids_unique", len(set(overlay_ids)) == overlay_count),
        ("atomic_claim_ids_unique", len(set(claim_ids)) == unit_count),
        ("no_query_gold_arm_or_analysis_fields", not contains_forbidden(dataset)),
        ("blindness_access_counts_zero", all(dataset[key] == 0 for key in ["query_access_count", "gold_or_reference_access_count", "arm_output_access_count", "phase7_3_3_d_content_access_count"])),
        ("provider_network_runtime_write_counts_zero", all(dataset[key] == 0 for key in ["provider_call_count", "network_access_count", "runtime_access_count", "store_write_count", "recall_engine_access_count"])),
        ("effect_dataset_closed_to_arms", dataset["selected_effect_dataset_opened_for_arm_execution"] is False),
        ("runtime_not_authorized", dataset["runtime_integration_authorized"] is False),
    ]
    diagnostics = {
        "case_count": len(segmented_cases),
        "memory_count": overlay_count,
        "atomic_unit_count": unit_count,
        "whole_memory_single_unit_count": whole_memory_single_unit_count,
        "zero_unit_memory_count": zero_unit_memory_count,
        "span_out_of_bounds_count": span_out_of_bounds_count,
        "span_overlap_count": span_overlap_count,
        "uncovered_character_count": uncovered_character_count,
        "reconstruction_failure_count": reconstruction_failure_count,
        "overlay_schema_failure_count": schema_failure_count,
        "provenance_failure_count": provenance_failure_count,
        "identity_failure_count": identity_failure_count,
        "placeholder_failure_count": placeholder_failure_count,
        "authority_failure_count": authority_failure_count,
    }
    return checks, diagnostics


def representation_document() -> dict[str, Any]:
    dataset = load(OVERLAYS)
    checks, diagnostics = validation(dataset)
    rows = [{"gate_check": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 1,
        "report_id": "phase7.4-atomic-segmentation-representation-coverage-gate-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "segmentation_algorithm_id": dataset["segmentation_algorithm_id"],
        "input_projection_sha256": sha(PROJECTION),
        "overlay_dataset_sha256": sha(OVERLAYS),
        "checks": rows,
        "diagnostics": diagnostics,
        "all_checks_passed": all(row["passed"] for row in rows),
        "reference_protocol_freeze_authorized": all(
            row["passed"] for row in rows
        ),
        "reference_review_authorized": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT
        if all(row["passed"] for row in rows)
        else "freeze_authoritative_segmentation_or_representation_negative_result",
    }


def fixture_document() -> dict[str, Any]:
    dataset = load(OVERLAYS)
    checks, diagnostics = validation(dataset)
    rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4-query-blind-atomic-segmentation-fixtures-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "fixtures": rows,
        "diagnostics": diagnostics,
        "all_fixtures_passed": all(row["passed"] for row in rows),
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
        "schema_version": 1,
        "manifest_id": "phase7.4-query-blind-atomic-segmentation-manifest-v1",
        "status": "frozen_query_blind_atomic_overlay_dataset",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "rust_execution_adapter_sha256": sha(RUST_BIN),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {
            rel(OVERLAYS): sha(OVERLAYS),
            rel(REPRESENTATION): sha(REPRESENTATION),
            rel(FIXTURES): sha(FIXTURES),
        },
        "rust_stdout_sha256": dataset["rust_stdout_sha256"],
        "rust_replay_byte_identical": dataset["rust_replay_byte_identical"],
        "case_count": 168,
        "memory_count": 1680,
        "atomic_unit_count": 3360,
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
        "schema_version": 1,
        "outcome_id": "phase7.4-query-blind-atomic-segmentation-outcome-v1",
        "status": "PASS_segmentation_and_representation_gate_reference_protocol_freeze_authorized",
        "manifest_sha256": manifest_hash,
        "overlay_dataset_sha256": sha(OVERLAYS),
        "representation_gate_sha256": sha(REPRESENTATION),
        "fixtures_sha256": sha(FIXTURES),
        "case_count": 168,
        "memory_count": 1680,
        "atomic_unit_count": 3360,
        "reference_protocol_freeze_authorized": True,
        "reference_review_authorized": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-query-blind-atomic-segmentation-v1-frozen",
        "event_type": "immutable_query_blind_atomic_overlay_and_representation_gate_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "overlay_dataset_sha256": sha(OVERLAYS),
        "representation_gate_sha256": sha(REPRESENTATION),
        "case_count": 168,
        "memory_count": 1680,
        "atomic_unit_count": 3360,
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
        "phase7_4_stage_state_v9_sha256": sha(STATE_V9),
        "phase7_4_readiness_v9_sha256": sha(READINESS_V9),
        "phase7_4_query_blind_atomic_segmentation_protocol_receipt_v1_sha256": sha(
            PROTOCOL_RECEIPT
        ),
        "phase7_4_atomic_overlay_dataset_v1_sha256": sha(OVERLAYS),
        "phase7_4_atomic_segmentation_representation_coverage_gate_v1_sha256": sha(
            REPRESENTATION
        ),
        "phase7_4_query_blind_atomic_segmentation_fixtures_v1_sha256": sha(
            FIXTURES
        ),
        "phase7_4_query_blind_atomic_segmentation_manifest_v1_sha256": manifest_hash,
        "phase7_4_query_blind_atomic_segmentation_outcome_v1_sha256": outcome_hash,
        "phase7_4_query_blind_atomic_segmentation_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 10,
        "state_id": "phase7.4-stage-state-v10",
        "status": "phase7_4_query_blind_atomic_segmentation_and_representation_gate_passed_reference_protocol_freeze_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "selected_source_content_frozen": True,
        "memory_only_segmentation_projection_frozen": True,
        "query_blind_atomic_segmentation_executed": True,
        "atomic_overlay_dataset_frozen": True,
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


def readiness_document(
    manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str
) -> dict[str, Any]:
    return {
        "schema_version": 10,
        "readiness_id": "phase7.4-readiness-v10",
        "status": "PASS_atomic_segmentation_reference_protocol_freeze_ready",
        "artifact_lineage": {
            **lineage(manifest_hash, outcome_hash, audit_hash),
            "phase7_4_stage_state_v10_sha256": state_hash,
        },
        "checks": {
            "query_blind_input_exact": True,
            "rust_replay_byte_identical": True,
            "overlay_schema_and_integrity_passed": True,
            "memory_and_atomic_counts_exact": True,
            "span_coverage_complete": True,
            "provenance_exact": True,
            "placeholders_not_gold": True,
            "representation_gate_passed": True,
            "evidence_coverage_gate_passed": True,
            "effect_dataset_closed_to_arms": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "reference_protocol_freeze_authorized": True,
        "reference_review_authorized": False,
        "gold_freeze_authorized": False,
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
    dataset = load(OVERLAYS)
    return {
        "schema_version": 1,
        "receipt_id": "phase7.4-query-blind-atomic-segmentation-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v10_sha256": state_hash,
        "readiness_v10_sha256": readiness_hash,
        "overlay_dataset_sha256": sha(OVERLAYS),
        "representation_gate_sha256": sha(REPRESENTATION),
        "fixtures_sha256": sha(FIXTURES),
        "rust_stdout_sha256": dataset["rust_stdout_sha256"],
        "rust_replay_byte_identical": True,
        "case_count": 168,
        "memory_count": 1680,
        "atomic_unit_count": 3360,
        "representation_and_coverage_gate_passed": True,
        "reference_protocol_freeze_authorized": True,
        "reference_review_authorized": False,
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
        protocol = load(PROTOCOL)
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state_exact": state["status"] == ENTRY,
                "entry_authority_exact": state["next_authorized_stage"] == AUTHORIZED,
                "protocol_next_exact": protocol["next_authorized_stage_after_pass"] == AUTHORIZED,
                "segmentation_authorized": state["atomic_segmentation_execution_authorized"] is True,
                "segmentation_not_already_executed": state["atomic_segmentation_executed"] is False,
                "query_fields_absent": load(PROJECTION)["query_fields_copied"] is False,
                "reference_gold_and_arms_closed": state["reference_review_started"] is False and state["gold_frozen"] is False and state["arm_execution_started"] is False,
                "effect_dataset_closed": state["selected_effect_dataset_opened_for_arm_execution"] is False,
                "provider_not_called": state["phase7_4_effect_provider_called"] is False,
                "runtime_off": state["runtime_integration_authorized"] is False,
                "rust_unit_tests_pass": rust_unit_tests_pass(),
            }
        )
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
        return {
            "status": "FAIL",
            "failed": [name for name, passed in checks if not passed],
            "diagnostics": diagnostics,
            "authoritative_outputs_written": False,
        }
    overlay_hash = once(OVERLAYS, dataset)
    representation_hash = once(REPRESENTATION, representation_document())
    fixtures_hash = once(FIXTURES, fixture_document())
    if not load(REPRESENTATION)["all_checks_passed"] or not load(FIXTURES)[
        "all_fixtures_passed"
    ]:
        raise RuntimeError("segmentation_gate_or_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V10, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(
        READINESS_V10,
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
        "overlay_dataset_sha256": overlay_hash,
        "representation_gate_sha256": representation_hash,
        "fixtures_sha256": fixtures_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v10_sha256": state_hash,
        "readiness_v10_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "case_count": diagnostics["case_count"],
        "memory_count": diagnostics["memory_count"],
        "atomic_unit_count": diagnostics["atomic_unit_count"],
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
        state_hash = sha(STATE_V10)
        readiness_hash = sha(READINESS_V10)
        replay_dataset, rust_stdout = rust_execution()
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(path.exists() and sha(path) == digest for path, digest in EXPECTED.items()),
                "overlay_dataset_replay": load(OVERLAYS) == replay_dataset,
                "rust_stdout_hash_replay": load(OVERLAYS)["rust_stdout_sha256"] == hb(rust_stdout.encode("utf-8")),
                "representation_replay": load(REPRESENTATION) == representation_document(),
                "fixtures_replay": load(FIXTURES) == fixture_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
                "audit_replay": AUDIT.read_bytes() == (canonical(audit_event(manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
                "state_v10_replay": load(STATE_V10) == state_document(manifest_hash, outcome_hash, audit_hash),
                "readiness_v10_replay": load(READINESS_V10) == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
                "receipt_replay": load(RECEIPT) == receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash),
                "representation_gate_pass": load(REPRESENTATION)["all_checks_passed"] is True,
                "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
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
        "representation_and_coverage_gate_passed": load(STATE_V10).get("representation_gate_passed") if STATE_V10.exists() else None,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V10).get("selected_effect_dataset_opened_for_arm_execution") if STATE_V10.exists() else None,
        "runtime_integration_authorized": load(STATE_V10).get("runtime_integration_authorized") if STATE_V10.exists() else None,
        "next_authorized_stage": load(STATE_V10).get("next_authorized_stage") if STATE_V10.exists() else None,
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
