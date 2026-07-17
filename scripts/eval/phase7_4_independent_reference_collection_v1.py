#!/usr/bin/env python3
"""Validate and freeze external Phase 7.4 independent Reference submissions."""
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

RUNBOOK = DOCS / "eval/PHASE7_4_2_REFERENCE_COLLECTION_RUNBOOK.md"
IDENTITY_SCHEMA = CONFIG / "phase7_4_independent_reference_identity_declaration_schema_v1.json"
SUBMISSION_SCHEMA = CONFIG / "phase7_4_independent_reference_submission_schema_v1.json"
PROTOCOL = CONFIG / "phase7_4_independent_reference_protocol_v1.json"
PROMPT = CONFIG / "phase7_4_independent_reference_reviewer_prompt_v1.md"
PACKET = PHASE_DATA / "phase7_4_independent_reference_blind_packet_v1.json"
WORKLIST_A = PHASE_DATA / "phase7_4_reference_reviewer_a_worklist_v1.json"
WORKLIST_B = PHASE_DATA / "phase7_4_reference_reviewer_b_worklist_v1.json"
PROTOCOL_RECEIPT = REPORTS / "phase7_4_independent_reference_protocol_receipt_v1.json"
STATE_V12 = PATTERN / "phase7_4_stage_state_v12.json"
READINESS_V12 = REPORTS / "phase7_4_readiness_v12.json"

FROZEN_IDENTITY = PHASE_DATA / "phase7_4_reference_identity_declaration_v1.json"
FROZEN_A = PHASE_DATA / "phase7_4_reference_reviewer_a_submission_v1.json"
FROZEN_B = PHASE_DATA / "phase7_4_reference_reviewer_b_submission_v1.json"
VALIDATION = REPORTS / "phase7_4_independent_reference_collection_validation_v1.json"
MANIFEST = REPORTS / "phase7_4_independent_reference_collection_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_independent_reference_collection_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_independent_reference_collection_audit_v1.jsonl"
STATE_V13 = PATTERN / "phase7_4_stage_state_v13.json"
READINESS_V13 = REPORTS / "phase7_4_readiness_v13.json"
RECEIPT = REPORTS / "phase7_4_independent_reference_collection_receipt_v1.json"

ENTRY_HEAD = "731b70d3315506cff1eda85a1c9c6974d9f3d3a2"
ENTRY = "phase7_4_independent_reference_protocol_and_packets_frozen_submission_collection_authorized"
AUTHORIZED = "collect_phase7_4_independent_reference_submissions_v1"
NEXT = "freeze_phase7_4_independent_reference_agreement_protocol_v1"

EXPECTED = {
    RUNBOOK: "8ca35285e20c547dc9148306a70816582a13044ebb92f89ea451bb8fc65bafcc",
    IDENTITY_SCHEMA: "a870bb610300e2b7a10329d15eada9883fdb786310da27feb74b4a4811305c11",
    SUBMISSION_SCHEMA: "91b59082d39422ab1e9701e5224191eb9c77583cea20cc836da4fb4c198db915",
    PROTOCOL: "32f02e880411a4895f52b5bb390565ff2063d3d0f93ad65fdea26d7995b006fa",
    PROMPT: "319e6e5737bf4e4fab4a82f197ae18a17a8a152d38d3485f43c5b4dd3311f904",
    PACKET: "ea7e4f60091a34e4274be1fbd440ca726e96c3916daa35c41402bcc1c3a4627e",
    WORKLIST_A: "9a53ddb3926029c195e171dc62da1c930000b37568bbd0eb3c937abd83e80d23",
    WORKLIST_B: "0cf05e7cccecd08d1798f607988392966ac22cb6de3a1f467b6ccbccd5ee6580",
    PROTOCOL_RECEIPT: "2cc2ba9f7d4c326fc7d8ab3b53d0b7c013f535d3c859ff37818990f4c452c672",
    STATE_V12: "559d31955dcb55bdc0786ab77ee83ae4059be29f686534b0fa67138584cfc3c8",
    READINESS_V12: "2555ff3f01eb1b7271208157a96a7693aaface5b16b16824214db3fd752a66cf",
}

OUTPUTS = [
    FROZEN_IDENTITY,
    FROZEN_A,
    FROZEN_B,
    VALIDATION,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V13,
    READINESS_V13,
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


def semantic_sha(value: Any) -> str:
    return hb(canonical(value).encode("utf-8"))


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


def root_checks() -> dict[str, bool]:
    checks = {
        "input_hash:" + rel(path): path.exists() and sha(path) == digest
        for path, digest in EXPECTED.items()
    }
    if all(checks.values()):
        state = load(STATE_V12)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "entry_state_exact": state["status"] == ENTRY,
                "entry_authority_exact": state["next_authorized_stage"]
                == AUTHORIZED,
                "collection_authorized": state[
                    "independent_reference_submission_collection_authorized"
                ]
                is True,
                "review_not_started": state["reference_review_started"] is False,
                "reviewer_identities_unassigned": state[
                    "reviewer_identities_assigned"
                ]
                is False,
                "agreement_gold_and_arms_closed": state[
                    "agreement_execution_authorized"
                ]
                is False
                and state["gold_freeze_authorized"] is False
                and state["arm_execution_started"] is False,
                "effect_dataset_closed": state[
                    "selected_effect_dataset_opened_for_arm_execution"
                ]
                is False,
                "provider_not_called": state["phase7_4_effect_provider_called"]
                is False,
                "runtime_off": state["runtime_integration_authorized"] is False,
                "outputs_absent": all(not path.exists() for path in OUTPUTS),
            }
        )
    return checks


def packet_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cases = {case["case_id"]: case for case in load(PACKET)["cases"]}
    claims = {}
    for case in cases.values():
        for memory in case["candidate_memories"]:
            for unit in memory["atomic_units"]:
                claims[unit["atomic_claim_id"]] = {
                    "case_id": case["case_id"],
                    "source_memory_id": memory["source_memory_id"],
                    "source_memory_character_count": len(
                        memory["source_memory_content"]
                    ),
                    "atomic_source_span": unit["source_locator"],
                }
    return cases, claims


def identity_checks(identity: dict[str, Any]) -> list[tuple[str, bool]]:
    schema = load(IDENTITY_SCHEMA)
    valid = Draft202012Validator(schema).is_valid(identity)
    raw_entities = identity.get("review_entities", [])
    entities = (
        raw_entities
        if isinstance(raw_entities, list)
        and all(isinstance(entity, dict) for entity in raw_entities)
        else []
    )
    roles = [entity.get("role") for entity in entities]
    commitments = [entity.get("identity_commitment_sha256") for entity in entities]
    return [
        ("identity_schema_valid", valid),
        (
            "identity_protocol_receipt_exact",
            identity.get("reference_protocol_receipt_sha256")
            == sha(PROTOCOL_RECEIPT),
        ),
        ("identity_packet_exact", identity.get("packet_sha256") == sha(PACKET)),
        (
            "identity_roles_exact",
            sorted(roles) == ["adjudicator", "reviewer_a", "reviewer_b"],
        ),
        (
            "identity_commitments_distinct",
            len(commitments) == 3
            and len(set(commitments)) == 3
            and identity.get("identity_commitments_distinct") is True,
        ),
        (
            "identity_independence_flags_exact",
            valid
            and all(
                entity.get("assignment_accepted") is True
                and entity.get("is_source_author") is False
                and entity.get("is_arm_implementer") is False
                and entity.get(
                    "shares_person_or_model_session_with_other_review_entity"
                )
                is False
                and entity.get("other_reviewer_output_accessed") is False
                and entity.get("agreement_or_gold_accessed") is False
                and entity.get("provider_called") is False
                for entity in entities
            ),
        ),
        (
            "identity_privacy_flags_exact",
            identity.get("personal_data_present") is False
            and identity.get("credentials_present") is False,
        ),
    ]


def worklist_expected(role: str) -> dict[str, Any]:
    return load(WORKLIST_A if role == "reviewer_a" else WORKLIST_B)


def submission_checks(
    submission: dict[str, Any],
    role: str,
    identity_semantic_hash: str,
) -> tuple[list[tuple[str, bool]], dict[str, int]]:
    schema = load(SUBMISSION_SCHEMA)
    worklist = worklist_expected(role)
    _, claim_map = packet_maps()
    schema_valid = Draft202012Validator(schema).is_valid(submission)
    expected_submission_id = (
        "phase7.4-independent-reference-reviewer-a-submission-v1"
        if role == "reviewer_a"
        else "phase7.4-independent-reference-reviewer-b-submission-v1"
    )
    worklist_path = WORKLIST_A if role == "reviewer_a" else WORKLIST_B
    expected_case_ids = [case["case_id"] for case in worklist["cases"]]
    raw_observed_cases = submission.get("cases", [])
    observed_cases = (
        raw_observed_cases
        if isinstance(raw_observed_cases, list)
        and all(isinstance(case, dict) for case in raw_observed_cases)
        else []
    )
    observed_case_ids = [case.get("case_id") for case in observed_cases]
    case_order_exact = observed_case_ids == expected_case_ids
    claim_order_exact = True
    identity_exact = True
    span_rule_failure_count = 0
    duplicate_claim_count = 0
    observed_claim_ids: list[str] = []
    for work_case, submitted_case in zip(
        worklist["cases"], observed_cases, strict=False
    ):
        expected_claims = work_case["claim_worklist"]
        raw_annotations = submitted_case.get("claim_annotations", [])
        annotations = (
            raw_annotations
            if isinstance(raw_annotations, list)
            and all(isinstance(annotation, dict) for annotation in raw_annotations)
            else []
        )
        expected_claim_ids = [claim["atomic_claim_id"] for claim in expected_claims]
        submitted_claim_ids = [
            annotation.get("atomic_claim_id") for annotation in annotations
        ]
        if submitted_claim_ids != expected_claim_ids:
            claim_order_exact = False
        for expected_claim, annotation in zip(
            expected_claims, annotations, strict=False
        ):
            claim_id = annotation.get("atomic_claim_id")
            observed_claim_ids.append(claim_id)
            claim = claim_map.get(claim_id)
            if (
                claim is None
                or annotation.get("source_memory_id")
                != expected_claim["source_memory_id"]
                or claim.get("source_memory_id")
                != annotation.get("source_memory_id")
                or claim.get("case_id") != submitted_case.get("case_id")
            ):
                identity_exact = False
                continue
            state = annotation.get("support_state")
            relevant = annotation.get("query_relevant")
            raw_spans = annotation.get("evidence_spans", [])
            spans = (
                raw_spans
                if isinstance(raw_spans, list)
                and all(isinstance(span, dict) for span in raw_spans)
                else []
            )
            should_have_spans = relevant is True and state in {
                "supported",
                "partially_supported",
            }
            if should_have_spans != bool(spans):
                span_rule_failure_count += 1
                continue
            atomic_span = claim["atomic_source_span"]
            previous_end = None
            seen_spans = set()
            for span in spans:
                start = span.get("start_char")
                end = span.get("end_char")
                key = (start, end)
                if (
                    not isinstance(start, int)
                    or not isinstance(end, int)
                    or start >= end
                    or start < atomic_span["start_char"]
                    or end > atomic_span["end_char"]
                    or end > claim["source_memory_character_count"]
                    or (previous_end is not None and start < previous_end)
                    or key in seen_spans
                ):
                    span_rule_failure_count += 1
                    break
                seen_spans.add(key)
                previous_end = end
    claim_ids_are_strings = all(
        isinstance(claim_id, str) for claim_id in observed_claim_ids
    )
    duplicate_claim_count = (
        len(observed_claim_ids) - len(set(observed_claim_ids))
        if claim_ids_are_strings
        else len(observed_claim_ids)
    )
    checks = [
        (f"{role}_submission_schema_valid", schema_valid),
        (
            f"{role}_submission_identity_exact",
            submission.get("submission_id") == expected_submission_id
            and submission.get("reviewer_role") == role,
        ),
        (
            f"{role}_identity_declaration_hash_exact",
            submission.get("reviewer_identity_declaration_sha256")
            == identity_semantic_hash,
        ),
        (f"{role}_packet_hash_exact", submission.get("packet_sha256") == sha(PACKET)),
        (
            f"{role}_worklist_hash_exact",
            submission.get("worklist_sha256") == sha(worklist_path),
        ),
        (
            f"{role}_counts_exact",
            submission.get("case_count") == 168
            and submission.get("claim_annotation_count") == 3360
            and submission.get("deferred_count") == 0
            and len(observed_cases) == 168
            and len(observed_claim_ids) == 3360,
        ),
        (f"{role}_case_order_exact", case_order_exact),
        (f"{role}_claim_order_exact", claim_order_exact),
        (f"{role}_claim_memory_case_identity_exact", identity_exact),
        (
            f"{role}_claim_ids_unique",
            claim_ids_are_strings and duplicate_claim_count == 0,
        ),
        (f"{role}_span_rules_pass", span_rule_failure_count == 0),
        (
            f"{role}_blindness_flags_exact",
            submission.get("other_reviewer_output_accessed") is False
            and submission.get("authoring_or_arm_output_accessed") is False
            and submission.get("provider_called") is False,
        ),
    ]
    diagnostics = {
        "observed_case_count": len(observed_cases),
        "observed_claim_count": len(observed_claim_ids),
        "duplicate_claim_count": duplicate_claim_count,
        "span_rule_failure_count": span_rule_failure_count,
    }
    return checks, diagnostics


def validate_external(
    identity_path: Path, reviewer_a_path: Path, reviewer_b_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = load(identity_path)
    reviewer_a = load(reviewer_a_path)
    reviewer_b = load(reviewer_b_path)
    roots = root_checks()
    identity_rows = identity_checks(identity)
    identity_hash = semantic_sha(identity)
    a_rows, a_diagnostics = submission_checks(reviewer_a, "reviewer_a", identity_hash)
    b_rows, b_diagnostics = submission_checks(reviewer_b, "reviewer_b", identity_hash)
    checks = [
        *[(name, passed) for name, passed in roots.items()],
        *identity_rows,
        *a_rows,
        *b_rows,
        (
            "reviewer_submission_semantic_hashes_distinct",
            semantic_sha(reviewer_a) != semantic_sha(reviewer_b),
        ),
        (
            "agreement_not_computed_during_collection",
            load(STATE_V12)["agreement_execution_authorized"] is False,
        ),
    ]
    rows = [{"check_id": name, "passed": passed} for name, passed in checks]
    report = {
        "schema_version": 1,
        "validation_id": "phase7.4-independent-reference-collection-validation-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "checks": rows,
        "check_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "reviewer_a_diagnostics": a_diagnostics,
        "reviewer_b_diagnostics": b_diagnostics,
        "identity_declaration_semantic_sha256": identity_hash,
        "reviewer_a_submission_semantic_sha256": semantic_sha(reviewer_a),
        "reviewer_b_submission_semantic_sha256": semantic_sha(reviewer_b),
        "all_checks_passed": all(row["passed"] for row in rows),
        "agreement_executed": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }
    return identity, reviewer_a, reviewer_b, report


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4-independent-reference-collection-manifest-v1",
        "status": "frozen_independent_reviewer_identity_commitments_and_submissions",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {
            rel(FROZEN_IDENTITY): sha(FROZEN_IDENTITY),
            rel(FROZEN_A): sha(FROZEN_A),
            rel(FROZEN_B): sha(FROZEN_B),
            rel(VALIDATION): sha(VALIDATION),
        },
        "identity_declaration_semantic_sha256": semantic_sha(load(FROZEN_IDENTITY)),
        "reviewer_a_submission_semantic_sha256": semantic_sha(load(FROZEN_A)),
        "reviewer_b_submission_semantic_sha256": semantic_sha(load(FROZEN_B)),
        "distinct_reviewer_count": 3,
        "case_count_per_reviewer": 168,
        "claim_count_per_reviewer": 3360,
        "agreement_executed": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "outcome_id": "phase7.4-independent-reference-collection-outcome-v1",
        "status": "PASS_independent_submissions_frozen_agreement_protocol_freeze_authorized",
        "manifest_sha256": manifest_hash,
        "identity_declaration_sha256": sha(FROZEN_IDENTITY),
        "reviewer_a_submission_sha256": sha(FROZEN_A),
        "reviewer_b_submission_sha256": sha(FROZEN_B),
        "validation_sha256": sha(VALIDATION),
        "distinct_reviewer_count": 3,
        "reviewer_a_submission_frozen": True,
        "reviewer_b_submission_frozen": True,
        "agreement_protocol_freeze_authorized": True,
        "agreement_executed": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-independent-reference-collection-v1-frozen",
        "event_type": "immutable_independent_identity_commitment_and_submission_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "identity_declaration_sha256": sha(FROZEN_IDENTITY),
        "reviewer_a_submission_sha256": sha(FROZEN_A),
        "reviewer_b_submission_sha256": sha(FROZEN_B),
        "distinct_reviewer_count": 3,
        "agreement_executed": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v12_sha256": sha(STATE_V12),
        "phase7_4_readiness_v12_sha256": sha(READINESS_V12),
        "phase7_4_independent_reference_protocol_receipt_v1_sha256": sha(PROTOCOL_RECEIPT),
        "phase7_4_reference_identity_declaration_v1_sha256": sha(FROZEN_IDENTITY),
        "phase7_4_reference_reviewer_a_submission_v1_sha256": sha(FROZEN_A),
        "phase7_4_reference_reviewer_b_submission_v1_sha256": sha(FROZEN_B),
        "phase7_4_independent_reference_collection_validation_v1_sha256": sha(VALIDATION),
        "phase7_4_independent_reference_collection_manifest_v1_sha256": manifest_hash,
        "phase7_4_independent_reference_collection_outcome_v1_sha256": outcome_hash,
        "phase7_4_independent_reference_collection_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 13,
        "state_id": "phase7.4-stage-state-v13",
        "status": "phase7_4_independent_reference_submissions_frozen_agreement_protocol_freeze_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "blind_reference_packet_frozen": True,
        "reviewer_identities_assigned": True,
        "distinct_reviewer_count_established": 3,
        "reference_review_started": True,
        "reference_review_completed": True,
        "reviewer_a_submission_frozen": True,
        "reviewer_b_submission_frozen": True,
        "agreement_protocol_freeze_authorized": True,
        "agreement_execution_authorized": False,
        "agreement_executed": False,
        "adjudication_authorized": False,
        "gold_freeze_authorized": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "arm_execution_started": False,
        "effect_scoring_started": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "productization_authorized": False,
        "release_authorized": False,
        "next_authorized_stage": NEXT,
    }


def readiness_document(manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 13,
        "readiness_id": "phase7.4-readiness-v13",
        "status": "PASS_independent_submissions_frozen_agreement_protocol_ready",
        "artifact_lineage": {**lineage(manifest_hash, outcome_hash, audit_hash), "phase7_4_stage_state_v13_sha256": state_hash},
        "checks": {
            "three_distinct_identity_commitments": True,
            "reviewer_a_submission_schema_and_lineage_passed": True,
            "reviewer_b_submission_schema_and_lineage_passed": True,
            "all_claims_covered_exactly_once": True,
            "span_rules_passed": True,
            "other_reviewer_and_agreement_blindness_passed": True,
            "agreement_not_yet_executed": True,
            "gold_not_frozen": True,
            "effect_dataset_closed_to_arms": True,
            "provider_not_called": True,
            "runtime_not_authorized": True
        },
        "agreement_protocol_freeze_authorized": True,
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
        "receipt_id": "phase7.4-independent-reference-collection-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v13_sha256": state_hash,
        "readiness_v13_sha256": readiness_hash,
        "identity_declaration_sha256": sha(FROZEN_IDENTITY),
        "reviewer_a_submission_sha256": sha(FROZEN_A),
        "reviewer_b_submission_sha256": sha(FROZEN_B),
        "validation_sha256": sha(VALIDATION),
        "distinct_reviewer_count": 3,
        "case_count_per_reviewer": 168,
        "claim_count_per_reviewer": 3360,
        "agreement_protocol_freeze_authorized": True,
        "agreement_executed": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def status_document() -> dict[str, Any]:
    roots = root_checks()
    return {
        "status": "WAITING_FOR_INDEPENDENT_REVIEWERS"
        if all(roots.values())
        else "BLOCKED_BY_LOCAL_LINEAGE_OR_EXISTING_OUTPUT",
        "root_checks_passed": all(roots.values()),
        "failed_root_checks": [name for name, passed in roots.items() if not passed],
        "required_external_inputs": [
            "sanitized_identity_declaration_with_three_distinct_commitments",
            "reviewer_a_complete_3360_claim_submission",
            "reviewer_b_complete_3360_claim_submission",
        ],
        "reviewer_identities_assigned": False,
        "reference_review_started": False,
        "agreement_executed": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": AUTHORIZED,
    }


def freeze_external(identity_path: Path, a_path: Path, b_path: Path) -> dict[str, Any]:
    identity, reviewer_a, reviewer_b, report = validate_external(identity_path, a_path, b_path)
    if not report["all_checks_passed"]:
        return report
    identity_hash = once(FROZEN_IDENTITY, identity)
    reviewer_a_hash = once(FROZEN_A, reviewer_a)
    reviewer_b_hash = once(FROZEN_B, reviewer_b)
    validation_hash = once(VALIDATION, report)
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V13, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(READINESS_V13, readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash))
    receipt_hash = once(RECEIPT, receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash))
    return {
        "status": "PASS",
        "identity_declaration_sha256": identity_hash,
        "reviewer_a_submission_sha256": reviewer_a_hash,
        "reviewer_b_submission_sha256": reviewer_b_hash,
        "validation_sha256": validation_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v13_sha256": state_hash,
        "readiness_v13_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "agreement_protocol_freeze_authorized": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def require_external_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    values = [args.identity_declaration, args.reviewer_a, args.reviewer_b]
    if any(value is None for value in values):
        raise ValueError("identity_declaration_reviewer_a_and_reviewer_b_paths_required")
    paths = tuple(Path(value).resolve() for value in values)
    if any(not path.is_file() for path in paths):
        raise ValueError("one_or_more_external_input_files_missing")
    return paths[0], paths[1], paths[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true")
    group.add_argument("--validate", action="store_true")
    group.add_argument("--freeze", action="store_true")
    parser.add_argument("--identity-declaration")
    parser.add_argument("--reviewer-a")
    parser.add_argument("--reviewer-b")
    args = parser.parse_args()
    try:
        if args.status:
            result = status_document()
            exit_code = 0 if result["root_checks_passed"] else 1
        else:
            identity_path, a_path, b_path = require_external_paths(args)
            if args.validate:
                _, _, _, result = validate_external(identity_path, a_path, b_path)
            else:
                result = freeze_external(identity_path, a_path, b_path)
            exit_code = 0 if result.get("status") == "PASS" else 1
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
    ) as error:
        result = {"status": "FAIL", "error": str(error)}
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
