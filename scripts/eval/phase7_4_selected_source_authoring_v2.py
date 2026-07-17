#!/usr/bin/env python3
"""Author the bounded de-templated Phase 7.4 selected source dataset v2."""
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

V1_ADAPTER = ROOT / "scripts/eval/phase7_4_selected_source_authoring_v1.py"
V1_SPEC = importlib.util.spec_from_file_location(
    "phase7_4_selected_source_authoring_v1", V1_ADAPTER
)
if V1_SPEC is None or V1_SPEC.loader is None:
    raise RuntimeError("v1_authoring_adapter_import_failed")
V1 = importlib.util.module_from_spec(V1_SPEC)
V1_SPEC.loader.exec_module(V1)

SCHEMA = CONFIG / "phase7_4_source_authoring_case_schema_v1.json"
CONTRACT = CONFIG / "phase7_4_selected_source_authoring_contract_v1.json"
PLAN = PHASE_DATA / "phase7_4_selected_source_authoring_plan_v1.json"
POLICY = CONFIG / "phase7_4_selected_source_authoring_successor_policy_v2.json"
ATTEMPTS = REPORTS / "phase7_4_selected_source_authoring_preflight_attempts_v1.jsonl"
SUCCESSOR_RECEIPT = REPORTS / "phase7_4_selected_source_authoring_successor_receipt_v2.json"
STATE_V7 = PATTERN / "phase7_4_stage_state_v7.json"
READINESS_V7 = REPORTS / "phase7_4_readiness_v7.json"

DATASET = PHASE_DATA / "phase7_4_selected_source_cases_v2.json"
FIXTURES = REPORTS / "phase7_4_selected_source_authoring_fixtures_v2.json"
MANIFEST = REPORTS / "phase7_4_selected_source_authoring_manifest_v2.json"
OUTCOME = REPORTS / "phase7_4_selected_source_authoring_outcome_v2.json"
AUDIT = REPORTS / "phase7_4_selected_source_authoring_audit_v2.jsonl"
STATE_V8 = PATTERN / "phase7_4_stage_state_v8.json"
READINESS_V8 = REPORTS / "phase7_4_readiness_v8.json"
RECEIPT = REPORTS / "phase7_4_selected_source_authoring_receipt_v2.json"

V1_AUTHORITATIVE_OUTPUTS = [
    PHASE_DATA / "phase7_4_selected_source_cases_v1.json",
    REPORTS / "phase7_4_selected_source_authoring_fixtures_v1.json",
    REPORTS / "phase7_4_selected_source_authoring_manifest_v1.json",
    REPORTS / "phase7_4_selected_source_authoring_outcome_v1.json",
    REPORTS / "phase7_4_selected_source_authoring_audit_v1.jsonl",
    REPORTS / "phase7_4_selected_source_authoring_receipt_v1.json",
]

ENTRY_HEAD = "6528f0686140ee175c994757a38da5af510dcad6"
ENTRY = "phase7_4_source_authoring_v1_preflight_failed_bounded_v2_authorized"
AUTHORIZED = "author_phase7_4_selected_source_cases_v2"
NEXT = "freeze_phase7_4_query_blind_atomic_segmentation_protocol_v1"

EXPECTED = {
    V1_ADAPTER: "2afdfc696775f23d3b8e024e7d936010086837781fd09d1e6a6b907f1e68458e",
    SCHEMA: "4ff8342c706bd779e761ce7278556e173c7b8b612cc7150eea23deffbb346630",
    CONTRACT: "d0b7b46c07f946a27ce411d5fc658586563ca4e4001ab4fd607ccb61fa68cc24",
    PLAN: "88b0c0f338a6e5037a81eacc37470a67c4953fced73efb41cc5bc8964474ccdd",
    POLICY: "5057e18dee0d4a4acb745e2cfbd3269df387bbf7d26acbb79d98fd5a7e2bd6e6",
    ATTEMPTS: "9e9a8d317d7b204598849d677c15201aa52efdbd4a2567db146fa5dc3e240aad",
    SUCCESSOR_RECEIPT: "d891995795a4d49e0e31c41797ee23c26e1fb05682a2eea02c395cb1009f93c8",
    STATE_V7: "c8e2cdd070184b6ce5df51fad4209c01fe66e871f058743945b061e3ede65792",
    READINESS_V7: "cdc6ff74826dff7d8f28caf7b85165dab08d54b9b2caba2b1602a23ddbfa5cdf",
}

OUTPUTS = [
    DATASET,
    FIXTURES,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V8,
    READINESS_V8,
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


def decapitalize(value: str) -> str:
    return value[:1].lower() + value[1:] if value else value


def scoped_text(subject: str, constraint: str, value: str) -> str:
    return f"For {subject} under {constraint}, {decapitalize(value)}"


def structural_case_projection(case: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(case, ensure_ascii=False))
    for event in value["source_events"]:
        event.pop("description")
        event.pop("description_sha256")
    for evidence in value["source_evidence"]:
        evidence.pop("observed_text")
        evidence.pop("observed_text_sha256")
    for memory in value["candidate_memories"]:
        memory.pop("source_memory_content")
        memory.pop("source_memory_content_sha256")
        memory.pop("source_memory_sha256")
    return value


def dataset_document() -> dict[str, Any]:
    v1_draft = V1.dataset_document()
    plan_by_id = {case["case_id"]: case for case in load(PLAN)["cases"]}
    cases = json.loads(json.dumps(v1_draft["cases"], ensure_ascii=False))
    for case in cases:
        case_plan = plan_by_id[case["case_id"]]
        profile = V1.tagged_profile(case_plan)
        subject = profile["subject"]
        constraint = profile["constraint"]
        for event in case["source_events"]:
            event["description"] = scoped_text(
                subject, constraint, event["description"]
            )
            event["description_sha256"] = hb(
                event["description"].encode("utf-8")
            )
        for evidence in case["source_evidence"]:
            evidence["observed_text"] = scoped_text(
                subject, constraint, evidence["observed_text"]
            )
            evidence["observed_text_sha256"] = hb(
                evidence["observed_text"].encode("utf-8")
            )
        for memory in case["candidate_memories"]:
            memory["source_memory_content"] = scoped_text(
                subject, constraint, memory["source_memory_content"]
            )
            memory["source_memory_content_sha256"] = hb(
                memory["source_memory_content"].encode("utf-8")
            )
            memory["source_memory_sha256"] = V1.source_memory_hash(memory)
    return {
        "schema_version": 2,
        "dataset_id": "phase7.4-selected-source-cases-v2",
        "status": "frozen_bounded_successor_synthetic_sources_before_atomic_segmentation",
        "authoring_plan_sha256": sha(PLAN),
        "authoring_contract_sha256": sha(CONTRACT),
        "source_case_schema_sha256": sha(SCHEMA),
        "successor_policy_v2_sha256": sha(POLICY),
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "v1_authoritative_dataset_written": False,
        "case_count": len(cases),
        "cases": cases,
        "source_content_authored": True,
        "source_content_frozen": True,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "network_used": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
    }


def bounded_successor_checks(dataset: dict[str, Any]) -> list[tuple[str, bool]]:
    v1_draft = V1.dataset_document()
    v1_by_id = {case["case_id"]: case for case in v1_draft["cases"]}
    v2_by_id = {case["case_id"]: case for case in dataset["cases"]}
    structure_exact = all(
        structural_case_projection(v1_by_id[case_id])
        == structural_case_projection(v2_by_id[case_id])
        for case_id in v1_by_id
    )
    query_exact = all(
        v1_by_id[case_id]["query"] == v2_by_id[case_id]["query"]
        for case_id in v1_by_id
    )
    non_query_text_changed = all(
        all(
            left["description"] != right["description"]
            for left, right in zip(
                v1_by_id[case_id]["source_events"],
                v2_by_id[case_id]["source_events"],
                strict=True,
            )
        )
        and all(
            left["observed_text"] != right["observed_text"]
            for left, right in zip(
                v1_by_id[case_id]["source_evidence"],
                v2_by_id[case_id]["source_evidence"],
                strict=True,
            )
        )
        and all(
            left["source_memory_content"] != right["source_memory_content"]
            for left, right in zip(
                v1_by_id[case_id]["candidate_memories"],
                v2_by_id[case_id]["candidate_memories"],
                strict=True,
            )
        )
        for case_id in v1_by_id
    )
    scope_present = True
    plan_by_id = {case["case_id"]: case for case in load(PLAN)["cases"]}
    for case_id, case in v2_by_id.items():
        profile = V1.tagged_profile(plan_by_id[case_id])
        prefix = f"For {profile['subject']} under {profile['constraint']},"
        scope_present = scope_present and all(
            row["description"].startswith(prefix) for row in case["source_events"]
        )
        scope_present = scope_present and all(
            row["observed_text"].startswith(prefix)
            for row in case["source_evidence"]
        )
        scope_present = scope_present and all(
            row["source_memory_content"].startswith(prefix)
            for row in case["candidate_memories"]
        )
    return [
        ("v1_authoritative_outputs_absent", all(not path.exists() for path in V1_AUTHORITATIVE_OUTPUTS)),
        ("v1_failed_attempt_retained", sha(ATTEMPTS) == EXPECTED[ATTEMPTS]),
        ("case_structure_exact_to_frozen_v1_plan", structure_exact),
        ("query_bytes_unchanged", query_exact),
        ("all_non_query_text_de_templated", non_query_text_changed),
        ("case_local_scope_clause_present", scope_present),
        ("thresholds_not_relaxed", load(POLICY)["unchanged_frozen_design"]["exact_normalized_text_duplicate_count_max"] == 0 and load(POLICY)["unchanged_frozen_design"]["normalized_five_gram_jaccard_manual_review_threshold"] == 0.85 and load(POLICY)["unchanged_frozen_design"]["unresolved_high_similarity_pair_count_max"] == 0),
    ]


def all_checks(dataset: dict[str, Any]) -> tuple[list[tuple[str, bool]], dict[str, Any]]:
    original, diagnostics = V1.dataset_checks(dataset)
    return [*original, *bounded_successor_checks(dataset)], diagnostics


def fixture_document() -> dict[str, Any]:
    dataset = load(DATASET)
    checks, diagnostics = all_checks(dataset)
    rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 2,
        "fixtures_id": "phase7.4-selected-source-authoring-fixtures-v2",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "fixtures": rows,
        "diagnostics": diagnostics,
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "v1_authoritative_outputs_written": False,
        "v1_failed_attempt_retained": True,
        "source_content_authored": True,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
    }


def case_hashes() -> list[dict[str, str]]:
    return [
        {
            "case_id": case["case_id"],
            "case_sha256": hb(canonical(case).encode("utf-8")),
        }
        for case in load(DATASET)["cases"]
    ]


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "manifest_id": "phase7.4-selected-source-authoring-manifest-v2",
        "status": "frozen_bounded_successor_selected_synthetic_sources",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {rel(DATASET): sha(DATASET), rel(FIXTURES): sha(FIXTURES)},
        "case_hashes": case_hashes(),
        "case_count": 168,
        "v1_authoritative_outputs_written": False,
        "v1_failed_attempt_retained": True,
        "selection_slots_and_queries_unchanged": True,
        "similarity_threshold_relaxed": False,
        "source_content_authored": True,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "network_used": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "outcome_id": "phase7.4-selected-source-authoring-outcome-v2",
        "status": "PASS_bounded_v2_sources_frozen_segmentation_protocol_freeze_authorized",
        "manifest_sha256": manifest_hash,
        "dataset_sha256": sha(DATASET),
        "fixtures_sha256": sha(FIXTURES),
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "case_count": 168,
        "v1_authoritative_outputs_written": False,
        "source_content_frozen": True,
        "similarity_threshold_relaxed": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-selected-source-authoring-v2-frozen",
        "event_type": "immutable_bounded_successor_source_content_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "dataset_sha256": sha(DATASET),
        "successor_policy_v2_sha256": sha(POLICY),
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "case_count": 168,
        "v1_authoritative_outputs_written": False,
        "source_content_frozen": True,
        "similarity_threshold_relaxed": False,
        "case_reselection_performed": False,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v7_sha256": sha(STATE_V7),
        "phase7_4_readiness_v7_sha256": sha(READINESS_V7),
        "phase7_4_selected_source_authoring_successor_receipt_v2_sha256": sha(
            SUCCESSOR_RECEIPT
        ),
        "phase7_4_selected_source_authoring_v1_attempt_log_sha256": sha(ATTEMPTS),
        "phase7_4_selected_source_authoring_successor_policy_v2_sha256": sha(POLICY),
        "phase7_4_selected_source_cases_v2_sha256": sha(DATASET),
        "phase7_4_selected_source_authoring_fixtures_v2_sha256": sha(FIXTURES),
        "phase7_4_selected_source_authoring_manifest_v2_sha256": manifest_hash,
        "phase7_4_selected_source_authoring_outcome_v2_sha256": outcome_hash,
        "phase7_4_selected_source_authoring_audit_v2_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 8,
        "state_id": "phase7.4-stage-state-v8",
        "status": "phase7_4_selected_source_cases_v2_frozen_atomic_segmentation_protocol_freeze_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "selected_source_authoring_contract_frozen": True,
        "v1_preflight_failure_retained": True,
        "v1_authoritative_outputs_written": False,
        "v2_successor_policy_frozen": True,
        "selected_source_content_authored": True,
        "selected_source_content_frozen": True,
        "selected_case_count": 168,
        "exact_normalized_text_duplicate_count": 0,
        "unresolved_high_similarity_pair_count": 0,
        "atomic_segmentation_protocol_freeze_authorized": True,
        "atomic_segmentation_execution_authorized": False,
        "atomic_overlay_constructed": False,
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
        "schema_version": 8,
        "readiness_id": "phase7.4-readiness-v8",
        "status": "PASS_bounded_v2_selected_source_cases_frozen",
        "artifact_lineage": {
            **lineage(manifest_hash, outcome_hash, audit_hash),
            "phase7_4_stage_state_v8_sha256": state_hash,
        },
        "checks": {
            "v1_failure_retained": True,
            "v1_authoritative_outputs_absent": True,
            "bounded_successor_structure_exact": True,
            "query_bytes_unchanged": True,
            "selected_case_count_exact": True,
            "source_case_schema_valid": True,
            "all_text_and_memory_hashes_replay": True,
            "all_references_resolved": True,
            "no_forbidden_labels_or_outputs": True,
            "exact_duplicate_count_zero": True,
            "unresolved_high_similarity_pair_count_zero": True,
            "phase7_3_3_d_content_not_loaded": True,
            "provider_and_network_unused": True,
            "effect_dataset_closed_to_arms": True,
            "runtime_not_authorized": True,
        },
        "atomic_segmentation_protocol_freeze_authorized": True,
        "atomic_segmentation_execution_authorized": False,
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
    fixtures = load(FIXTURES)
    return {
        "schema_version": 2,
        "receipt_id": "phase7.4-selected-source-authoring-receipt-v2",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v8_sha256": state_hash,
        "readiness_v8_sha256": readiness_hash,
        "dataset_sha256": sha(DATASET),
        "fixtures_sha256": sha(FIXTURES),
        "retained_v1_attempt_log_sha256": sha(ATTEMPTS),
        "case_count": 168,
        "authored_text_count": fixtures["diagnostics"]["authored_text_count"],
        "exact_normalized_text_duplicate_count": fixtures["diagnostics"][
            "exact_normalized_text_duplicate_count"
        ],
        "high_similarity_pair_count": fixtures["diagnostics"][
            "high_similarity_pair_count"
        ],
        "v1_authoritative_outputs_written": False,
        "source_content_frozen": True,
        "similarity_threshold_relaxed": False,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
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
    diagnostics: dict[str, Any] = {}
    if all(checks.values()):
        state = load(STATE_V7)
        policy = load(POLICY)
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state_exact": state["status"] == ENTRY,
                "entry_authority_exact": state["next_authorized_stage"] == AUTHORIZED,
                "policy_next_exact": policy["next_authorized_stage_after_pass"] == AUTHORIZED,
                "v2_authoring_authorized": state[
                    "v2_selected_source_content_authoring_authorized"
                ]
                is True,
                "v1_outputs_absent": all(
                    not path.exists() for path in V1_AUTHORITATIVE_OUTPUTS
                ),
                "source_not_already_authored": state[
                    "selected_source_content_authored"
                ]
                is False,
                "effect_dataset_closed": state[
                    "selected_effect_dataset_opened_for_arm_execution"
                ]
                is False,
                "provider_not_called": state["phase7_4_effect_provider_called"]
                is False,
                "runtime_off": state["runtime_integration_authorized"] is False,
            }
        )
        if all(checks.values()):
            draft = dataset_document()
            draft_checks, diagnostics = all_checks(draft)
            checks.update({"draft:" + name: passed for name, passed in draft_checks})
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "draft_diagnostics": diagnostics,
    }


def author() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    dataset_hash = once(DATASET, dataset_document())
    fixtures_hash = once(FIXTURES, fixture_document())
    if not load(FIXTURES)["all_fixtures_passed"]:
        raise RuntimeError("selected_source_authoring_v2_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V8, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(
        READINESS_V8,
        readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
    )
    receipt_hash = once(
        RECEIPT,
        receipt_document(
            manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash
        ),
    )
    diagnostics = load(FIXTURES)["diagnostics"]
    return {
        "status": "PASS",
        "dataset_sha256": dataset_hash,
        "fixtures_sha256": fixtures_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v8_sha256": state_hash,
        "readiness_v8_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "case_count": 168,
        "authored_text_count": diagnostics["authored_text_count"],
        "exact_normalized_text_duplicate_count": diagnostics[
            "exact_normalized_text_duplicate_count"
        ],
        "high_similarity_pair_count": diagnostics["high_similarity_pair_count"],
        "source_content_frozen": True,
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
        state_hash = sha(STATE_V8)
        readiness_hash = sha(READINESS_V8)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(
                    path.exists() and sha(path) == digest
                    for path, digest in EXPECTED.items()
                ),
                "v1_outputs_absent": all(
                    not path.exists() for path in V1_AUTHORITATIVE_OUTPUTS
                ),
                "dataset_replay": load(DATASET) == dataset_document(),
                "fixtures_replay": load(FIXTURES) == fixture_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
                "audit_replay": AUDIT.read_bytes()
                == (
                    canonical(audit_event(manifest_hash, outcome_hash)) + "\n"
                ).encode("utf-8"),
                "state_v8_replay": load(STATE_V8)
                == state_document(manifest_hash, outcome_hash, audit_hash),
                "readiness_v8_replay": load(READINESS_V8)
                == readiness_document(
                    manifest_hash, outcome_hash, audit_hash, state_hash
                ),
                "receipt_replay": load(RECEIPT)
                == receipt_document(
                    manifest_hash,
                    outcome_hash,
                    audit_hash,
                    state_hash,
                    readiness_hash,
                ),
                "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
                "next_gate_consistent": load(STATE_V8)["next_authorized_stage"]
                == load(READINESS_V8)["next_authorized_stage"]
                == load(RECEIPT)["next_authorized_stage"]
                == NEXT,
                "source_content_frozen": load(STATE_V8)[
                    "selected_source_content_frozen"
                ]
                is True,
                "effect_dataset_closed_to_arms": load(STATE_V8)[
                    "selected_effect_dataset_opened_for_arm_execution"
                ]
                is False,
                "provider_not_called": load(STATE_V8)[
                    "phase7_4_effect_provider_called"
                ]
                is False,
                "runtime_off": load(STATE_V8)["runtime_integration_authorized"]
                is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "source_content_frozen": load(STATE_V8).get(
            "selected_source_content_frozen"
        )
        if STATE_V8.exists()
        else None,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V8).get(
            "selected_effect_dataset_opened_for_arm_execution"
        )
        if STATE_V8.exists()
        else None,
        "runtime_integration_authorized": load(STATE_V8).get(
            "runtime_integration_authorized"
        )
        if STATE_V8.exists()
        else None,
        "next_authorized_stage": load(STATE_V8).get("next_authorized_stage")
        if STATE_V8.exists()
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--author", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
    elif args.author:
        result = author()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
