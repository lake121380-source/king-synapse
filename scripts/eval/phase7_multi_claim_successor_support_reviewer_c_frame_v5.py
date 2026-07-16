#!/usr/bin/env python3
"""Classify Support v5 reviewer-B empty content and run reviewer C.

Reviewer C is a new supplemental independent reviewer, not a retry of B.
It reuses the immutable v5 label-only protocol, schema, prompt, packet, and
parser under a new manifest and model identity.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import tempfile
import urllib.error
from pathlib import Path

from phase7_execution_attempt_log import append_event, read_entries

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

BASE_ADAPTER = ROOT / "scripts/eval/phase7_multi_claim_successor_support_review_frame_v5.py"
PRO = C / "phase7_3_3_d_multi_claim_successor_support_review_protocol_frame_v5.json"
SCH = C / "phase7_3_3_d_multi_claim_successor_support_review_schema_frame_v5.json"
POL = C / "phase7_3_3_d_multi_claim_successor_support_review_policy_frame_v5.json"
PROMPT = C / "phase7_3_3_d_multi_claim_successor_support_reviewer_prompt_frame_v5.md"
PKT = D / "phase7_3_3_d_multi_claim_successor_support_review_packet_frame_v5.json"
FIX_SHARED = R / "phase7_3_3_d_multi_claim_successor_support_review_fixtures_frame_v5.json"
SUB_A = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_a_submission_frame_v5.json"
MAN_B = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_b_manifest_frame_v5.json"
NEG_B = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_b_negative_frame_v5.json"
LOG_B = R / "phase7_3_3_d_multi_claim_successor_support_review_attempts_frame_v5.jsonl"
SI = D / "phase7_3_3_d_support_stage_state_v88.json"
RI = R / "phase7_3_3_d1_reference_construction_readiness_v99.json"

CLASS = R / "phase7_3_3_d_multi_claim_successor_support_v5_failure_classification.json"
ENTRY = C / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_entry_protocol_frame_v5.json"
FIX = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_fixtures_frame_v5.json"
MAN = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_manifest_frame_v5.json"
PREP = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_prepare_outcome_frame_v5.json"
PREP_REC = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_prepare_receipt_frame_v5.json"
LOG = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_attempts_frame_v5.jsonl"
CASES = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_cases_frame_v5" / "c"
SUB = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_submission_frame_v5.json"
RESULT = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_result_frame_v5.json"
OUT = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_outcome_frame_v5.json"
REC = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_receipt_frame_v5.json"
NEG_C = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_negative_frame_v5.json"
SP = D / "phase7_3_3_d_support_stage_state_v89.json"
RP = R / "phase7_3_3_d1_reference_construction_readiness_v100.json"
SO = D / "phase7_3_3_d_support_stage_state_v90.json"
RO = R / "phase7_3_3_d1_reference_construction_readiness_v101.json"

EXPECTED = {
    BASE_ADAPTER: "6284b6ef1427693ca9d5bd5678df50c004a3df35745426b42e02521058cbe37b",
    PRO: "8fa87914929a97fcfbe3d6e3f2d4a51cbc4d7c235a315b0513d992b771429d7a",
    SCH: "269e096513d69048629a7c8c751e554f824c873a647a1955d20adcd8f0720c77",
    POL: "b14225f3342d8b09a09f0d6b5ba6bd2d48e268e0d55b13c481268ad68b9d2b20",
    PROMPT: "54ff3f4ce65a1f3116c9703a3fe9ad868616467bbc3f5b744aa42b83e00cb104",
    PKT: "634759bd4840d0b7fca64727a5602bae487796d60dfb6bbd8ad597a632c518b6",
    FIX_SHARED: "35b74e16b6af3ebe6e6e7f2f2a6e239004d1337611377de5052f0b7375769c03",
    SUB_A: "3a186b9a9be817f1e19a4c85f7c4865b07eab2b4f9ce6e5e88f14146f211e185",
    MAN_B: "ee11f2305c107220003bded3467561c85d3f32c867231203b469ee1967004a2a",
    NEG_B: "be30b6ebabe61f730be897dea0863712d8cdde636d5c9337c4b9e701f62d8d77",
    LOG_B: "cf3af9b8c18f68cec07b751be17189a789948285df45f3fc37e16a21823bfbac",
    SI: "b126b9cc98f75b6f2f2ba3444b2660e410ca670d1064bf47e83ee0f88e9eebf6",
    RI: "83de83f512d34e8e9350ae76b4adcca56c9b4bb64c831485f6887ee9b060bd1e",
}

CUR = "classify_multi_claim_successor_support_v5_authoritative_negative"
EXEC = "execute_multi_claim_successor_support_reviewer_c_frame_v5"
AGREE = "construct_multi_claim_successor_support_agreement_a_c_frame_v5"
BLOCKED = "blocked_multi_claim_successor_support_reviewer_c_authoritative_negative"
MODEL = "qwen3.5-plus"
CRED = "PHASE7_ATOMIC_JUDGE_API_KEY"
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def once(path: Path, value) -> str:
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("immutable_artifact_mismatch:" + rel(path))
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hb(body)


def base():
    if sha(BASE_ADAPTER) != EXPECTED[BASE_ADAPTER]:
        raise RuntimeError("frozen_v5_adapter_hash_mismatch")
    spec = importlib.util.spec_from_file_location("frozen_support_v5", BASE_ADAPTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def failure_event():
    matches = [
        event for event in read_entries(LOG_B)
        if event.get("reviewer") == "b"
        and event.get("event_type") == "support_v5_contract_failure"
        and event.get("authoritative_result") is True
    ]
    if len(matches) != 1:
        raise RuntimeError("reviewer_b_authoritative_failure_event_cardinality")
    return matches[0]


def classification():
    negative, event = load(NEG_B), failure_event()
    if event.get("provider_content_sha256") != EMPTY_SHA:
        raise RuntimeError("reviewer_b_content_not_empty")
    return {
        "schema_version": 1,
        "classification_id": "phase7.3.3-d-multi-claim-successor-support-v5-failure-classification",
        "status": "frozen_authoritative_negative_classification",
        "reviewer": "b",
        "negative_result_sha256": sha(NEG_B),
        "attempt_log_sha256": sha(LOG_B),
        "failure_level": "level_1_provider_output_representation_contract",
        "failure_subtype": "empty_provider_content",
        "failure_code": negative["failure_code"],
        "failed_case_id": negative["failed_case_id"],
        "completed_case_count": 0,
        "response_received": True,
        "provider_content_sha256": EMPTY_SHA,
        "raw_provider_content_stored": False,
        "support_label_capability_conclusion_authorized": False,
        "same_version_retry_allowed": False,
        "reviewer_a_submission_preserved": True,
        "reviewer_b_submission_created": False,
        "supplemental_reviewer_c_authorized": True,
        "reviewer_c_is_reviewer_b_retry": False,
        "agreement_pair_if_c_completes": ["reviewer_a_v5", "reviewer_c_v5_supplement"],
        "next_authorized_stage": EXEC,
    }


def entry_protocol(classification_hash: str):
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-entry-frame-v5",
        "status": "frozen_before_reviewer_c_provider_call",
        "predecessor_negative_result_sha256": sha(NEG_B),
        "failure_classification_sha256": classification_hash,
        "reviewer_a_submission_sha256": sha(SUB_A),
        "reviewer_b_same_version_retry_allowed": False,
        "reviewer_c_role": "supplemental_independent_support_label_reviewer",
        "reviewer_c_is_reviewer_b_retry": False,
        "reviewer_c_model": MODEL,
        "frozen_shared_inputs": {rel(path): sha(path) for path in [PRO, SCH, POL, PROMPT, PKT, FIX_SHARED, BASE_ADAPTER]},
        "invariants": [
            "same v5 label-only support semantics",
            "same v5 prompt/schema/policy/packet",
            "same case isolation and first-content-authoritative policy",
            "reviewer A and B outputs hidden",
            "no claim, boundary, type, or metadata mutation",
        ],
        "agreement_if_completed": "Reviewer A v5 versus supplemental Reviewer C v5",
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": EXEC,
    }


def fixtures():
    module = base()
    case = load(PKT)["cases"][0]
    rows = []
    examples = [
        ("valid_label_only", {"label_codes": [0, 0, 2, 2, 1, 1]}, True),
        ("empty_content_rejected", None, False),
        ("citation_extra_rejected", {"label_codes": [0] * 6, "citations": []}, False),
        ("foreign_model_rejected", "foreign-model", False),
    ]
    for fixture_id, value, expected in examples:
        try:
            if fixture_id == "empty_content_rejected":
                module.parse(case, json.loads(""))
            elif fixture_id == "foreign_model_rejected":
                module.canonical(MODEL, value)
            else:
                module.parse(case, value)
            accepted = True
        except Exception:
            accepted = False
        rows.append({"fixture_id": fixture_id, "passed": accepted == expected})
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-fixtures-frame-v5",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "fixtures": rows,
    }


def manifest(entry_hash: str, fixture_hash: str):
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-manifest-frame-v5",
        "status": "frozen_not_started",
        "reviewer": "c",
        "reviewer_role": "supplemental_independent_support_label_reviewer",
        "reviewer_b_retry": False,
        "model_requested": MODEL,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
        "credential_env_name": CRED,
        "supplemental_adapter_sha256": sha(SELF),
        "frozen_v5_adapter_sha256": sha(BASE_ADAPTER),
        "entry_protocol_sha256": entry_hash,
        "protocol_sha256": sha(PRO),
        "schema_sha256": sha(SCH),
        "policy_sha256": sha(POL),
        "prompt_sha256": sha(PROMPT),
        "packet_sha256": sha(PKT),
        "shared_fixtures_sha256": sha(FIX_SHARED),
        "supplemental_fixtures_sha256": fixture_hash,
        "reviewer_a_submission_sha256": sha(SUB_A),
        "reviewer_b_negative_result_sha256": sha(NEG_B),
        "case_count": 40,
        "claim_count": 240,
        "case_isolation": True,
        "first_provider_content_authoritative": True,
        "semantic_retry_allowed": False,
        "raw_provider_content_stored": False,
        "citation_output_requested": False,
        "other_reviewer_visible": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def preflight():
    checks = {"input_hash:" + rel(path): path.exists() and sha(path) == expected for path, expected in EXPECTED.items()}
    if all(checks.values()):
        state, readiness = load(SI), load(RI)
        negative, event = load(NEG_B), failure_event()
        checks.update({
            "state_gate": state["next_authorized_stage"] == "execute_multi_claim_successor_support_reviewer_b_frame_v5",
            "readiness_gate": readiness["next_authorized_stage"] == "execute_multi_claim_successor_support_reviewer_b_frame_v5",
            "negative_gate": negative["next_authorized_stage"] == CUR,
            "empty_content_hash": event["provider_content_sha256"] == EMPTY_SHA,
            "reviewer_a_complete": load(SUB_A)["decision_count"] == 240,
            "same_version_retry_false": negative["same_version_retry_allowed"] is False,
            "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
            "outputs_absent": all(not path.exists() for path in [CLASS, ENTRY, FIX, MAN, PREP, PREP_REC, SP, RP]),
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare():
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    fixture_hash = once(FIX, fixtures())
    classification_hash = once(CLASS, classification())
    entry_hash = once(ENTRY, entry_protocol(classification_hash))
    manifest_hash = once(MAN, manifest(entry_hash, fixture_hash))
    state, readiness = copy.deepcopy(load(SI)), copy.deepcopy(load(RI))
    lineage = {
        "multi_claim_successor_support_v5_failure_classification_sha256": classification_hash,
        "multi_claim_successor_support_reviewer_c_entry_protocol_frame_v5_sha256": entry_hash,
        "multi_claim_successor_support_reviewer_c_fixtures_frame_v5_sha256": fixture_hash,
        "multi_claim_successor_support_reviewer_c_manifest_frame_v5_sha256": manifest_hash,
    }
    update = {
        "status": "multi_claim_successor_support_reviewer_c_frame_v5_prepared",
        "next_authorized_stage": EXEC,
        "multi_claim_successor_support_v5_reviewer_b_negative_preserved": True,
        "multi_claim_successor_support_v5_reviewer_b_same_version_retry_allowed": False,
        "multi_claim_successor_support_v5_reviewer_c_authorized": True,
        "multi_claim_successor_support_v5_reviewer_c_completed": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 89, "state_id": "phase7.3.3-d-support-stage-state-v89"})
    readiness.update({"schema_version": 100, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v100"})
    state_hash = once(SP, state)
    readiness["artifact_lineage"]["support_stage_state_v89_sha256"] = state_hash
    readiness_hash = once(RP, readiness)
    outcome_hash = once(PREP, {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-prepare-outcome-frame-v5",
        "status": "PASS",
        "failure_classification_sha256": classification_hash,
        "entry_protocol_sha256": entry_hash,
        "fixtures_sha256": fixture_hash,
        "manifest_sha256": manifest_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "provider_called": False,
        "next_authorized_stage": EXEC,
    })
    receipt_hash = once(PREP_REC, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-prepare-receipt-frame-v5",
        "status": "PASS",
        "outcome_sha256": outcome_hash,
        "manifest_sha256": manifest_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "next_authorized_stage": EXEC,
    })
    return {
        "status": "PASS",
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "receipt_sha256": receipt_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "next_authorized_stage": EXEC,
    }


def verify_prepare():
    paths = [CLASS, ENTRY, FIX, MAN, PREP, PREP_REC, SP, RP]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        frozen_manifest = load(MAN)
        checks.update({
            "classification_replay": load(CLASS) == classification(),
            "entry_replay": load(ENTRY) == entry_protocol(sha(CLASS)),
            "fixtures_replay": load(FIX) == fixtures(),
            "manifest_replay": frozen_manifest == manifest(sha(ENTRY), sha(FIX)),
            "supplemental_adapter_frozen": frozen_manifest["supplemental_adapter_sha256"] == sha(SELF),
            "base_adapter_frozen": frozen_manifest["frozen_v5_adapter_sha256"] == sha(BASE_ADAPTER),
            "reviewer_c_not_b_retry": frozen_manifest["reviewer_b_retry"] is False,
            "state_gate": load(SP)["next_authorized_stage"] == EXEC,
            "readiness_gate": load(RP)["next_authorized_stage"] == EXEC,
            "confirmatory_closed": load(SP)["confirmatory_dataset_opened"] is False and load(RP)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(SP)["runtime_integration_authorized"] is False and load(RP)["runtime_integration_authorized"] is False,
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def cp(case_id: str) -> Path:
    return CASES / f"{case_id}.json"


def finish(status: str, next_stage: str, submission_hash=None, result_hash=None, negative_hash=None):
    state, readiness = copy.deepcopy(load(SP)), copy.deepcopy(load(RP))
    lineage = {}
    if submission_hash:
        lineage["multi_claim_successor_support_reviewer_c_submission_frame_v5_sha256"] = submission_hash
    if result_hash:
        lineage["multi_claim_successor_support_reviewer_c_result_frame_v5_sha256"] = result_hash
    if negative_hash:
        lineage["multi_claim_successor_support_reviewer_c_negative_frame_v5_sha256"] = negative_hash
    completed = status == "multi_claim_successor_support_reviewer_c_frame_v5_completed"
    update = {
        "status": status,
        "next_authorized_stage": next_stage,
        "multi_claim_successor_support_v5_reviewer_c_provider_called": True,
        "multi_claim_successor_support_v5_reviewer_c_completed": completed,
        "multi_claim_successor_support_agreement_a_c_frame_v5_authorized": completed,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 90, "state_id": "phase7.3.3-d-support-stage-state-v90"})
    readiness.update({"schema_version": 101, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v101"})
    state_hash = once(SO, state)
    readiness["artifact_lineage"]["support_stage_state_v90_sha256"] = state_hash
    readiness_hash = once(RO, readiness)
    return state_hash, readiness_hash


def execute():
    checked = verify_prepare()
    if checked["status"] != "PASS":
        raise RuntimeError("prepare_not_verified:" + ",".join(checked["failed"]))
    if load(SP)["next_authorized_stage"] != EXEC or load(RP)["next_authorized_stage"] != EXEC:
        raise RuntimeError("stage_not_authorized")
    key = os.environ.get(CRED)
    if not key:
        raise RuntimeError("credential_missing:" + CRED)
    module = base()
    frozen_manifest = load(MAN)
    manifest_hash = sha(MAN)
    frozen = {
        SELF: frozen_manifest["supplemental_adapter_sha256"],
        BASE_ADAPTER: frozen_manifest["frozen_v5_adapter_sha256"],
        ENTRY: frozen_manifest["entry_protocol_sha256"],
        PRO: frozen_manifest["protocol_sha256"],
        SCH: frozen_manifest["schema_sha256"],
        POL: frozen_manifest["policy_sha256"],
        PROMPT: frozen_manifest["prompt_sha256"],
        PKT: frozen_manifest["packet_sha256"],
        FIX_SHARED: frozen_manifest["shared_fixtures_sha256"],
        FIX: frozen_manifest["supplemental_fixtures_sha256"],
        SUB_A: frozen_manifest["reviewer_a_submission_sha256"],
        NEG_B: frozen_manifest["reviewer_b_negative_result_sha256"],
    }
    for path, expected in frozen.items():
        if sha(path) != expected:
            raise RuntimeError("manifest_hash_mismatch:" + rel(path))
    system, user_template = module.split_prompt()
    completed = []
    for case in load(PKT)["cases"]:
        checkpoint_path = cp(case["case_id"])
        if checkpoint_path.exists():
            completed.append(load(checkpoint_path))
            continue
        append_event({
            "event_type": "support_v5_reviewer_c_attempt_started",
            "manifest_sha256": manifest_hash,
            "reviewer": "c",
            "case_id": case["case_id"],
            "response_received": False,
            "authoritative_result": False,
        }, LOG)
        try:
            raw = module.call(key, MODEL, system, user_template.replace("{{CASE_JSON}}", json.dumps(case, ensure_ascii=False, indent=2)))
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            append_event({
                "event_type": "support_v5_reviewer_c_transport_failure",
                "manifest_sha256": manifest_hash,
                "reviewer": "c",
                "case_id": case["case_id"],
                "failure_type": type(error).__name__,
                "response_received": False,
                "same_manifest_resume_allowed": True,
            }, LOG)
            return {"status": "TRANSPORT_FAILURE_RESUMABLE", "completed_case_count": len(completed), "failed_case_id": case["case_id"]}
        envelope_hash = hb(raw)
        content = None
        try:
            envelope = json.loads(raw.decode())
            reported_model = envelope.get("model")
            content = envelope["choices"][0]["message"]["content"]
            content_hash = hb(content.encode())
            canonical_model = module.canonical(MODEL, reported_model)
            decisions = module.parse(case, json.loads(content))
        except Exception as error:
            content_hash = hb(content.encode()) if isinstance(content, str) else None
            failure_code = type(error).__name__ + ":" + str(error)
            append_event({
                "event_type": "support_v5_reviewer_c_contract_failure",
                "manifest_sha256": manifest_hash,
                "reviewer": "c",
                "case_id": case["case_id"],
                "failure_code": failure_code,
                "provider_envelope_sha256": envelope_hash,
                "provider_content_sha256": content_hash,
                "response_received": True,
                "authoritative_result": True,
            }, LOG)
            negative_hash = once(NEG_C, {
                "schema_version": 1,
                "negative_result_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-negative-frame-v5",
                "status": "authoritative_negative_result",
                "reviewer": "c",
                "manifest_sha256": manifest_hash,
                "failed_case_id": case["case_id"],
                "completed_case_count": len(completed),
                "failure_code": failure_code,
                "same_version_retry_allowed": False,
                "support_label_capability_conclusion_authorized": False,
                "reviewer_b_retry": False,
                "next_authorized_stage": BLOCKED,
            })
            state_hash, readiness_hash = finish("multi_claim_successor_support_reviewer_c_authoritative_negative", BLOCKED, negative_hash=negative_hash)
            return {
                "status": "AUTHORITATIVE_NEGATIVE_RESULT",
                "negative_result_sha256": negative_hash,
                "state_sha256": state_hash,
                "readiness_sha256": readiness_hash,
                "same_version_retry_allowed": False,
                "next_authorized_stage": BLOCKED,
            }
        checkpoint = {
            "schema_version": 1,
            "checkpoint_id": f"support-v5-c-{case['case_id']}",
            "manifest_sha256": manifest_hash,
            "reviewer": "c",
            "reviewer_role": "supplemental_independent_support_label_reviewer",
            "reviewer_b_retry": False,
            "case_id": case["case_id"],
            "provider_reported_model": reported_model,
            "canonical_model_family": canonical_model,
            "provider_envelope_sha256": envelope_hash,
            "provider_content_sha256": content_hash,
            "decisions": decisions,
            "citation_output_requested": False,
            "raw_provider_content_stored": False,
        }
        checkpoint_hash = once(checkpoint_path, checkpoint)
        append_event({
            "event_type": "support_v5_reviewer_c_attempt_completed",
            "manifest_sha256": manifest_hash,
            "reviewer": "c",
            "case_id": case["case_id"],
            "decision_count": len(decisions),
            "checkpoint_sha256": checkpoint_hash,
            "provider_content_sha256": content_hash,
            "response_received": True,
            "authoritative_result": True,
        }, LOG)
        completed.append(checkpoint)
    cases = [{"case_id": row["case_id"], "decisions": row["decisions"]} for row in completed]
    submission = {
        "schema_version": 1,
        "submission_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-submission-frame-v5",
        "status": "completed_supplemental_independent_support_label_review",
        "reviewer": "c",
        "reviewer_role": "supplemental_independent_support_label_reviewer",
        "reviewer_b_retry": False,
        "manifest_sha256": manifest_hash,
        "case_count": 40,
        "decision_count": sum(len(case["decisions"]) for case in cases),
        "cases": cases,
        "citation_fields_present": False,
        "diagnostic_fields_present": False,
        "completed": True,
    }
    submission_hash = once(SUB, submission)
    result_hash = once(RESULT, {
        "schema_version": 1,
        "result_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-result-frame-v5",
        "status": "completed",
        "manifest_sha256": manifest_hash,
        "attempt_log_sha256": sha(LOG),
        "submission_sha256": submission_hash,
        "case_count": 40,
        "decision_count": submission["decision_count"],
        "canonical_model_family": MODEL,
        "next_authorized_stage": AGREE,
    })
    state_hash, readiness_hash = finish("multi_claim_successor_support_reviewer_c_frame_v5_completed", AGREE, submission_hash, result_hash)
    outcome_hash = once(OUT, {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-outcome-frame-v5",
        "status": "PASS",
        "submission_sha256": submission_hash,
        "result_sha256": result_hash,
        "agreement_pair": ["reviewer_a_v5", "reviewer_c_v5_supplement"],
        "reviewer_b_excluded": True,
        "next_authorized_stage": AGREE,
    })
    receipt_hash = once(REC, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-support-reviewer-c-receipt-frame-v5",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "submission_sha256": submission_hash,
        "result_sha256": result_hash,
        "outcome_sha256": outcome_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "case_count": 40,
        "decision_count": submission["decision_count"],
        "next_authorized_stage": AGREE,
    })
    return {
        "status": "PASS",
        "reviewer": "c",
        "case_count": 40,
        "decision_count": submission["decision_count"],
        "submission_sha256": submission_hash,
        "result_sha256": result_hash,
        "receipt_sha256": receipt_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "next_authorized_stage": AGREE,
    }


def verify_reviewer():
    paths = [MAN, SUB, RESULT, OUT, REC, SO, RO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        module = base()
        submission, result, receipt = load(SUB), load(RESULT), load(REC)
        decisions = [decision for case in submission["cases"] for decision in case["decisions"]]
        replay = True
        for case in load(PKT)["cases"]:
            checkpoint = load(cp(case["case_id"]))
            replay = replay and checkpoint["decisions"] == module.parse(case, {
                "label_codes": [decision["label_code"] for decision in checkpoint["decisions"]]
            })
        checks.update({
            "attempt_log_chain": isinstance(read_entries(LOG), list),
            "40_cases": submission["case_count"] == len(submission["cases"]) == 40,
            "240_decisions": submission["decision_count"] == len(decisions) == 240,
            "labels_only": all(set(decision) == {"reference_claim_id", "support_label", "label_code"} for decision in decisions),
            "checkpoint_replay": replay,
            "submission_lineage": result["submission_sha256"] == receipt["submission_sha256"] == sha(SUB),
            "result_lineage": receipt["result_sha256"] == sha(RESULT),
            "reviewer_c_not_b_retry": submission["reviewer_b_retry"] is False,
            "state_gate": load(SO)["next_authorized_stage"] == AGREE,
            "readiness_gate": load(RO)["next_authorized_stage"] == AGREE,
            "confirmatory_closed": load(SO)["confirmatory_dataset_opened"] is False and load(RO)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(SO)["runtime_integration_authorized"] is False and load(RO)["runtime_integration_authorized"] is False,
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(SO)["next_authorized_stage"] if SO.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["preflight", "fixtures", "prepare", "verify-prepare", "execute", "verify-reviewer"]:
        group.add_argument("--" + name, action="store_true")
    arguments = parser.parse_args()
    if arguments.preflight:
        outcome = preflight()
    elif arguments.fixtures:
        outcome = fixtures()
    elif arguments.prepare:
        outcome = prepare()
    elif arguments.verify_prepare:
        outcome = verify_prepare()
    elif arguments.execute:
        outcome = execute()
    else:
        outcome = verify_reviewer()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") in {"PASS", "TRANSPORT_FAILURE_RESUMABLE", "AUTHORITATIVE_NEGATIVE_RESULT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
