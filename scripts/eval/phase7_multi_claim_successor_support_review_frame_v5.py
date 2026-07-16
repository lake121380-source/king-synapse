#!/usr/bin/env python3
"""Phase 7.3.3-D Multi-claim Successor frame-v2 Support Review v5.

v5 is the governance-authorized label-only successor to the authoritative
v4.1 citation-mask serialization negative.  Frozen v1-v4.1 artifacts are
inputs only and are never rewritten by this adapter.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from phase7_execution_attempt_log import append_event, read_entries

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

TREF = D / "phase7_3_3_d_multi_claim_successor_type_metadata_reference_frame_v3.json"
DATA = D / "phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json"
CLASS = R / "phase7_3_3_d_multi_claim_successor_support_v4_1_failure_classification.json"
V41NEG = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_a_negative_frame_v4_1.json"
SI = D / "phase7_3_3_d_support_stage_state_v86.json"
RI = R / "phase7_3_3_d1_reference_construction_readiness_v97.json"

PRO = C / "phase7_3_3_d_multi_claim_successor_support_review_protocol_frame_v5.json"
SCH = C / "phase7_3_3_d_multi_claim_successor_support_review_schema_frame_v5.json"
POL = C / "phase7_3_3_d_multi_claim_successor_support_review_policy_frame_v5.json"
PROMPT = C / "phase7_3_3_d_multi_claim_successor_support_reviewer_prompt_frame_v5.md"
PKT = D / "phase7_3_3_d_multi_claim_successor_support_review_packet_frame_v5.json"
FIX = R / "phase7_3_3_d_multi_claim_successor_support_review_fixtures_frame_v5.json"
PM = R / "phase7_3_3_d_multi_claim_successor_support_review_prepare_manifest_frame_v5.json"
PR = R / "phase7_3_3_d_multi_claim_successor_support_review_prepare_receipt_frame_v5.json"
LOG = R / "phase7_3_3_d_multi_claim_successor_support_review_attempts_frame_v5.jsonl"
SP = D / "phase7_3_3_d_support_stage_state_v87.json"
RP = R / "phase7_3_3_d1_reference_construction_readiness_v98.json"

EXP = {
    TREF: "f19845566adc324d8210a5041c5ecee2338e4bf97a549d320b257c705a6da8d8",
    DATA: "788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe",
    CLASS: "724cc50fb533fe3716a5e18d0e706d50fc50b4e9c137d844ebb36d446b4caeb3",
    V41NEG: "26d012fae129d093a140581a00a6b803c50d0877ecf0d38d9a6a563e86073a13",
    SI: "453909cfc77d9b9bb677a92fb1a4a0587a294ca3b5ff10aa77b7fe672ce54bf5",
    RI: "b6b3f48ba02602cd6cf5bf394833d970062bc8e7ebb9221a1239b4042e11ade2",
}

CUR = "design_multi_claim_successor_support_review_frame_v5_label_only"
EXA = "execute_multi_claim_successor_support_reviewer_a_frame_v5"
EXB = "execute_multi_claim_successor_support_reviewer_b_frame_v5"
AGREE = "construct_multi_claim_successor_support_agreement_frame_v5"
FAIL = "classify_multi_claim_successor_support_v5_authoritative_negative"
MODELS = {"a": "gpt-4.1", "b": "gemini-2.5-pro"}
LABELS = ["supported", "partially_supported", "unsupported", "not_assessable"]
BASE = "https://api.gpt.ge/v1"
CRED = "PHASE7_ATOMIC_JUDGE_API_KEY"


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def once(path: Path, value) -> str:
    body = value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
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


def packet():
    evidence = {case["candidate_id"]: case for case in load(DATA)["cases"]}
    cases = []
    for reference_case in load(TREF)["cases"]:
        source = evidence[reference_case["case_id"]]
        cases.append({
            "case_id": reference_case["case_id"],
            "evidence_bundle": copy.deepcopy(source["evidence_bundle"]),
            "claim_count": len(reference_case["claims"]),
            "claims": [{
                key: copy.deepcopy(claim[key])
                for key in ["reference_claim_id", "claim_index", "source_excerpt", "claim_role", "claim_type", "claim_origin"]
            } for claim in reference_case["claims"]],
        })
    return {
        "schema_version": 5,
        "packet_id": "phase7.3.3-d-support-review-packet-frame-v5",
        "status": "frozen_evidence_visible_gold_hidden_label_only",
        "label_codebook": {str(index): label for index, label in enumerate(LABELS)},
        "case_count": 40,
        "claim_count": 240,
        "cases": cases,
        "support_gold_visible": False,
        "generation_roles_visible": False,
        "other_reviewer_visible": False,
        "citation_output_requested": False,
        "diagnostic_fields_requested": False,
    }


def prompt_text() -> str:
    return """# Independent Support Reviewer - Label-only Representation v5

## System message

Judge Evidence support for the six frozen Claims. Return bare JSON with exactly one key:
- label_codes: exactly six integers, where 0=supported, 1=partially_supported, 2=unsupported, 3=not_assessable.

Supported requires whole-Claim conservative entailment. Partially supported means a substantive core is supported but full scope, temporal extent, strength, or qualification is not. Unsupported means required support is absent or contradicted. Not assessable is reserved for Claims that cannot responsibly be evaluated from supplied Evidence. Do not infer causality, universality, permanence, or wider scope from narrower evidence.

Do not output citations, evidence masks, semantic label strings, reasons, confidence, Claim IDs, rationale, Markdown, or extra keys.

## User message template

Review this frozen case. Return bare JSON only.

{{CASE_JSON}}
"""


def schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["label_codes"],
        "properties": {
            "label_codes": {
                "type": "array",
                "minItems": 6,
                "maxItems": 6,
                "items": {"type": "integer", "minimum": 0, "maximum": 3},
            }
        },
        "additionalProperties": False,
    }


def protocol():
    return {
        "schema_version": 5,
        "protocol_id": "phase7.3.3-d-support-review-protocol-frame-v5",
        "status": "frozen_before_provider_call",
        "predecessor_v4_1_negative_sha256": sha(V41NEG),
        "predecessor_failure_classification_sha256": sha(CLASS),
        "single_intended_change": "support label codes only; citations moved to a later non-gold diagnostic stage",
        "support_semantics_unchanged": True,
        "citation_capability_in_estimand": False,
        "models": MODELS,
        "case_count": 40,
        "claim_count": 240,
        "first_provider_content_authoritative": True,
        "same_version_retry_allowed": False,
    }


def policy():
    return {
        "schema_version": 5,
        "policy_id": "phase7.3.3-d-support-review-policy-frame-v5",
        "case_isolation": True,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
        "raw_provider_content_stored": False,
        "transport_failure_resume_same_manifest": True,
        "invalid_content_authoritative_negative": True,
        "confirmatory_dataset_opening_allowed": False,
        "runtime_integration_allowed": False,
    }


def parse(case, output):
    if not isinstance(output, dict) or set(output) != {"label_codes"}:
        raise ValueError("root_invalid")
    codes = output["label_codes"]
    if not isinstance(codes, list) or len(codes) != case["claim_count"]:
        raise ValueError("fixed_length_mismatch")
    if any(type(code) is not int or code < 0 or code > 3 for code in codes):
        raise ValueError("label_code_invalid")
    return [{
        "reference_claim_id": claim["reference_claim_id"],
        "support_label": LABELS[codes[index]],
        "label_code": codes[index],
    } for index, claim in enumerate(case["claims"])]


def fixtures():
    case = packet()["cases"][0]
    examples = [
        ("valid", {"label_codes": [0, 0, 2, 2, 1, 1]}, True),
        ("short", {"label_codes": [0] * 5}, False),
        ("bad_code", {"label_codes": [9] * 6}, False),
        ("boolean_is_not_integer", {"label_codes": [True] * 6}, False),
        ("citation_forbidden", {"label_codes": [0] * 6, "citation_masks": ["000000"] * 6}, False),
    ]
    rows = []
    for fixture_id, output, expected in examples:
        try:
            parse(case, output)
            accepted = True
        except ValueError:
            accepted = False
        rows.append({"fixture_id": fixture_id, "passed": accepted == expected})
    return {
        "schema_version": 5,
        "fixtures_id": "phase7.3.3-d-support-review-fixtures-frame-v5",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "fixtures": rows,
    }


def mp(reviewer: str) -> Path:
    return R / f"phase7_3_3_d_multi_claim_successor_support_reviewer_{reviewer}_manifest_frame_v5.json"


def subp(reviewer: str) -> Path:
    return R / f"phase7_3_3_d_multi_claim_successor_support_reviewer_{reviewer}_submission_frame_v5.json"


def resp(reviewer: str) -> Path:
    return R / f"phase7_3_3_d_multi_claim_successor_support_reviewer_{reviewer}_result_frame_v5.json"


def recp(reviewer: str) -> Path:
    return R / f"phase7_3_3_d_multi_claim_successor_support_reviewer_{reviewer}_receipt_frame_v5.json"


def negp(reviewer: str) -> Path:
    return R / f"phase7_3_3_d_multi_claim_successor_support_reviewer_{reviewer}_negative_frame_v5.json"


def cpp(reviewer: str, case_id: str) -> Path:
    return R / "phase7_3_3_d_multi_claim_successor_support_reviewer_cases_frame_v5" / reviewer / f"{case_id}.json"


def manifest(reviewer: str):
    return {
        "schema_version": 5,
        "manifest_id": f"phase7.3.3-d-support-reviewer-{reviewer}-manifest-frame-v5",
        "status": "frozen_not_started",
        "reviewer": reviewer,
        "model_requested": MODELS[reviewer],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
        "credential_env_name": CRED,
        "adapter_sha256": sha(SELF),
        "protocol_sha256": sha(PRO),
        "schema_sha256": sha(SCH),
        "policy_sha256": sha(POL),
        "prompt_sha256": sha(PROMPT),
        "packet_sha256": sha(PKT),
        "fixtures_sha256": sha(FIX),
        "case_count": 40,
        "claim_count": 240,
        "first_provider_content_authoritative": True,
        "same_version_retry_allowed": False,
    }


def preflight():
    checks = {"input_hash:" + rel(path): path.exists() and sha(path) == expected for path, expected in EXP.items()}
    if all(checks.values()):
        state, readiness = load(SI), load(RI)
        checks.update({
            "state_gate": state["next_authorized_stage"] == CUR,
            "readiness_gate": readiness["next_authorized_stage"] == CUR,
            "v4_1_negative_preserved": state["multi_claim_successor_support_v4_1_negative_preserved"] is True,
            "same_version_retry_false": state["multi_claim_successor_support_v4_1_same_version_retry_allowed"] is False,
            "classification_authorizes_v5": load(CLASS)["next_authorized_stage"] == CUR,
            "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
            "outputs_absent": all(not path.exists() for path in [PRO, SCH, POL, PROMPT, PKT, FIX, PM, PR, SP, RP, mp("a"), mp("b")]),
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare():
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    once(PRO, protocol())
    once(SCH, schema())
    once(POL, policy())
    once(PROMPT, prompt_text().encode())
    packet_hash = once(PKT, packet())
    once(FIX, fixtures())
    reviewer_hashes = {reviewer: once(mp(reviewer), manifest(reviewer)) for reviewer in MODELS}
    prepare_manifest = {
        "schema_version": 5,
        "manifest_id": "phase7.3.3-d-support-review-prepare-manifest-frame-v5",
        "status": "frozen_before_any_v5_provider_call",
        "adapter_sha256": sha(SELF),
        "artifacts": {rel(path): sha(path) for path in [PRO, SCH, POL, PROMPT, PKT, FIX, mp("a"), mp("b")]},
        "v4_1_authoritative_negative_preserved": True,
        "single_intended_change": protocol()["single_intended_change"],
        "next_authorized_stage": EXA,
    }
    prepare_hash = once(PM, prepare_manifest)
    state, readiness = copy.deepcopy(load(SI)), copy.deepcopy(load(RI))
    lineage = {"multi_claim_successor_support_review_prepare_manifest_frame_v5_sha256": prepare_hash}
    update = {
        "status": "multi_claim_successor_support_review_frame_v5_frozen_reviewer_a_authorized",
        "next_authorized_stage": EXA,
        "multi_claim_successor_support_review_frame_v5_frozen": True,
        "multi_claim_successor_support_reviewer_a_frame_v5_completed": False,
        "multi_claim_successor_support_reviewer_b_frame_v5_completed": False,
        "multi_claim_successor_support_v4_1_negative_preserved": True,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 87, "state_id": "phase7.3.3-d-support-stage-state-v87"})
    readiness.update({"schema_version": 98, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v98"})
    state_hash = once(SP, state)
    readiness["artifact_lineage"]["support_stage_state_v87_sha256"] = state_hash
    readiness_hash = once(RP, readiness)
    receipt_hash = once(PR, {
        "schema_version": 5,
        "receipt_id": "phase7.3.3-d-support-review-prepare-receipt-frame-v5",
        "status": "PASS",
        "prepare_manifest_sha256": prepare_hash,
        "reviewer_a_manifest_sha256": reviewer_hashes["a"],
        "reviewer_b_manifest_sha256": reviewer_hashes["b"],
        "packet_sha256": packet_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "provider_called": False,
        "next_authorized_stage": EXA,
    })
    return {
        "status": "PASS",
        "prepare_manifest_sha256": prepare_hash,
        "receipt_sha256": receipt_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "next_authorized_stage": EXA,
    }


def states(reviewer: str):
    if reviewer == "a":
        return SP, RP, D / "phase7_3_3_d_support_stage_state_v88.json", R / "phase7_3_3_d1_reference_construction_readiness_v99.json", EXA, EXB, 88, 99
    return D / "phase7_3_3_d_support_stage_state_v88.json", R / "phase7_3_3_d1_reference_construction_readiness_v99.json", D / "phase7_3_3_d_support_stage_state_v89.json", R / "phase7_3_3_d1_reference_construction_readiness_v100.json", EXB, AGREE, 89, 100


def call(key: str, model: str, system: str, user: str) -> bytes:
    payload = {
        "model": model,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    request = urllib.request.Request(
        BASE + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return response.read()


def split_prompt():
    source = PROMPT.read_text(encoding="utf-8-sig").split("## System message\n\n", 1)[1]
    return [part.strip() for part in source.split("\n## User message template\n\n", 1)]


def canonical(requested: str, reported) -> str:
    if not isinstance(reported, str):
        raise ValueError("model_missing")
    normalized = reported.lower().rsplit("/", 1)[-1]
    expected = requested.lower()
    if normalized == expected or normalized.startswith(expected + "-"):
        return requested
    raise ValueError("model_family_mismatch")


def finish_state(reviewer: str, next_stage: str, submission_hash: str, result_hash: str):
    state_input, readiness_input, state_output, readiness_output, _, _, state_version, readiness_version = states(reviewer)
    state, readiness = copy.deepcopy(load(state_input)), copy.deepcopy(load(readiness_input))
    lineage = {
        f"multi_claim_successor_support_reviewer_{reviewer}_submission_frame_v5_sha256": submission_hash,
        f"multi_claim_successor_support_reviewer_{reviewer}_result_frame_v5_sha256": result_hash,
    }
    update = {
        "status": "multi_claim_successor_support_reviewer_frame_v5_completed",
        "next_authorized_stage": next_stage,
        f"multi_claim_successor_support_reviewer_{reviewer}_frame_v5_completed": True,
        "multi_claim_successor_support_review_frame_v5_provider_called": True,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": state_version, "state_id": f"phase7.3.3-d-support-stage-state-v{state_version}"})
    readiness.update({"schema_version": readiness_version, "readiness_id": f"phase7.3.3-d1-reference-construction-readiness-v{readiness_version}"})
    state_hash = once(state_output, state)
    readiness["artifact_lineage"][f"support_stage_state_v{state_version}_sha256"] = state_hash
    readiness_hash = once(readiness_output, readiness)
    return state_hash, readiness_hash


def execute(reviewer: str):
    state_input, readiness_input, _, _, expected_stage, next_stage, _, _ = states(reviewer)
    if load(state_input)["next_authorized_stage"] != expected_stage or load(readiness_input)["next_authorized_stage"] != expected_stage:
        raise RuntimeError("stage_not_authorized")
    frozen_manifest = load(mp(reviewer))
    manifest_hash = sha(mp(reviewer))
    for path, key in [(SELF, "adapter_sha256"), (PRO, "protocol_sha256"), (SCH, "schema_sha256"), (POL, "policy_sha256"), (PROMPT, "prompt_sha256"), (PKT, "packet_sha256"), (FIX, "fixtures_sha256")]:
        if sha(path) != frozen_manifest[key]:
            raise RuntimeError("manifest_hash_mismatch:" + rel(path))
    if resp(reviewer).exists():
        return {"status": "PASS", "terminal_outcome": "already_completed", "next_authorized_stage": load(resp(reviewer))["next_authorized_stage"]}
    if negp(reviewer).exists():
        return {"status": "AUTHORITATIVE_NEGATIVE_RESULT", "next_authorized_stage": FAIL}
    key = os.environ.get(CRED)
    if not key:
        raise RuntimeError("credential_missing:" + CRED)
    system, user_template = split_prompt()
    completed = []
    for case in load(PKT)["cases"]:
        checkpoint_path = cpp(reviewer, case["case_id"])
        if checkpoint_path.exists():
            completed.append(load(checkpoint_path))
            continue
        append_event({
            "event_type": "support_v5_attempt_started",
            "manifest_sha256": manifest_hash,
            "reviewer": reviewer,
            "case_id": case["case_id"],
            "response_received": False,
            "authoritative_result": False,
        }, LOG)
        try:
            raw = call(key, MODELS[reviewer], system, user_template.replace("{{CASE_JSON}}", json.dumps(case, ensure_ascii=False, indent=2)))
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            append_event({
                "event_type": "support_v5_transport_failure",
                "manifest_sha256": manifest_hash,
                "reviewer": reviewer,
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
            canonical_model = canonical(MODELS[reviewer], reported_model)
            decisions = parse(case, json.loads(content))
        except Exception as error:
            content_hash = hb(content.encode()) if isinstance(content, str) else None
            failure_code = type(error).__name__ + ":" + str(error)
            append_event({
                "event_type": "support_v5_contract_failure",
                "manifest_sha256": manifest_hash,
                "reviewer": reviewer,
                "case_id": case["case_id"],
                "failure_code": failure_code,
                "provider_envelope_sha256": envelope_hash,
                "provider_content_sha256": content_hash,
                "response_received": True,
                "authoritative_result": True,
            }, LOG)
            negative_hash = once(negp(reviewer), {
                "schema_version": 5,
                "negative_result_id": f"phase7.3.3-d-support-reviewer-{reviewer}-negative-frame-v5",
                "status": "authoritative_negative_result",
                "failed_case_id": case["case_id"],
                "completed_case_count": len(completed),
                "failure_code": failure_code,
                "manifest_sha256": manifest_hash,
                "same_version_retry_allowed": False,
                "capability_conclusion_authorized": False,
                "next_authorized_stage": FAIL,
            })
            return {"status": "AUTHORITATIVE_NEGATIVE_RESULT", "negative_result_sha256": negative_hash, "next_authorized_stage": FAIL}
        checkpoint = {
            "schema_version": 5,
            "checkpoint_id": f"support-v5-{reviewer}-{case['case_id']}",
            "manifest_sha256": manifest_hash,
            "reviewer": reviewer,
            "case_id": case["case_id"],
            "provider_reported_model": reported_model,
            "canonical_model_family": canonical_model,
            "provider_envelope_sha256": envelope_hash,
            "provider_content_sha256": content_hash,
            "decisions": decisions,
            "citation_output_requested": False,
            "boundary_mutation_performed": False,
            "type_metadata_mutation_performed": False,
        }
        checkpoint_hash = once(checkpoint_path, checkpoint)
        append_event({
            "event_type": "support_v5_attempt_completed",
            "manifest_sha256": manifest_hash,
            "reviewer": reviewer,
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
        "schema_version": 5,
        "submission_id": f"phase7.3.3-d-support-reviewer-{reviewer}-submission-frame-v5",
        "status": "completed_independent_support_label_review",
        "reviewer": reviewer,
        "manifest_sha256": manifest_hash,
        "case_count": 40,
        "decision_count": sum(len(case["decisions"]) for case in cases),
        "cases": cases,
        "citation_fields_present": False,
        "diagnostic_fields_present": False,
        "completed": True,
    }
    submission_hash = once(subp(reviewer), submission)
    result = {
        "schema_version": 5,
        "result_id": f"phase7.3.3-d-support-reviewer-{reviewer}-result-frame-v5",
        "status": "completed",
        "manifest_sha256": manifest_hash,
        "attempt_log_sha256": sha(LOG),
        "submission_sha256": submission_hash,
        "case_count": 40,
        "decision_count": submission["decision_count"],
        "next_authorized_stage": next_stage,
    }
    result_hash = once(resp(reviewer), result)
    state_hash, readiness_hash = finish_state(reviewer, next_stage, submission_hash, result_hash)
    receipt_hash = once(recp(reviewer), {
        "schema_version": 5,
        "receipt_id": f"phase7.3.3-d-support-reviewer-{reviewer}-receipt-frame-v5",
        "status": "PASS",
        "submission_sha256": submission_hash,
        "result_sha256": result_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "next_authorized_stage": next_stage,
    })
    return {
        "status": "PASS",
        "reviewer": reviewer,
        "case_count": 40,
        "decision_count": submission["decision_count"],
        "submission_sha256": submission_hash,
        "result_sha256": result_hash,
        "receipt_sha256": receipt_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "next_authorized_stage": next_stage,
    }


def verify():
    paths = [PRO, SCH, POL, PROMPT, PKT, FIX, PM, PR, SP, RP, mp("a"), mp("b")]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        checks.update({
            "packet_replay": load(PKT) == packet(),
            "protocol_replay": load(PRO) == protocol(),
            "schema_replay": load(SCH) == schema(),
            "policy_replay": load(POL) == policy(),
            "prompt_replay": PROMPT.read_bytes() == prompt_text().encode(),
            "fixtures_replay": load(FIX) == fixtures(),
            "manifests_replay": all(load(mp(reviewer)) == manifest(reviewer) for reviewer in MODELS),
            "attempt_log_chain": not LOG.exists() or isinstance(read_entries(LOG), list),
        })
    for reviewer in MODELS:
        if resp(reviewer).exists():
            submission = load(subp(reviewer))
            decisions = [decision for case in submission["cases"] for decision in case["decisions"]]
            checks.update({
                f"{reviewer}_40_cases": submission["case_count"] == len(submission["cases"]) == 40,
                f"{reviewer}_240_decisions": submission["decision_count"] == len(decisions) == 240,
                f"{reviewer}_labels_only": all(set(decision) == {"reference_claim_id", "support_label", "label_code"} for decision in decisions),
                f"{reviewer}_receipt_lineage": load(recp(reviewer))["submission_sha256"] == sha(subp(reviewer)) and load(recp(reviewer))["result_sha256"] == sha(resp(reviewer)),
            })
    failed = [name for name, passed in checks.items() if not passed]
    latest = D / "phase7_3_3_d_support_stage_state_v89.json"
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "terminal": {reviewer: "completed" if resp(reviewer).exists() else "negative" if negp(reviewer).exists() else None for reviewer in MODELS},
        "next_authorized_stage": load(latest)["next_authorized_stage"] if latest.exists() else load(SP)["next_authorized_stage"] if SP.exists() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["preflight", "prepare", "execute-a", "execute-b", "verify"]:
        group.add_argument("--" + name, action="store_true")
    arguments = parser.parse_args()
    if arguments.preflight:
        outcome = preflight()
    elif arguments.prepare:
        outcome = prepare()
    elif arguments.execute_a:
        outcome = execute("a")
    elif arguments.execute_b:
        outcome = execute("b")
    else:
        outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") in {"PASS", "TRANSPORT_FAILURE_RESUMABLE", "AUTHORITATIVE_NEGATIVE_RESULT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
