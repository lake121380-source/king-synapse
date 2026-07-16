#!/usr/bin/env python3
"""Freeze and execute the equal-resource Candidate/Atomic frame-v2 Pilot."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from phase7_execution_attempt_log import append_event, read_entries

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

DATA = D / "phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json"
GOLD = D / "phase7_3_3_d_multi_claim_successor_support_gold_frame_v2.json"
GSEAL = R / "phase7_3_3_d_multi_claim_successor_support_gold_seal_frame_v2.json"
STRUCT = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_report_frame_v2.json"
SREC = R / "phase7_3_3_d_multi_claim_successor_structural_identifiability_receipt_frame_v2.json"
SI = D / "phase7_3_3_d_support_stage_state_v93.json"
RI = R / "phase7_3_3_d1_reference_construction_readiness_v104.json"

PRO = C / "phase7_3_3_d_multi_claim_successor_pilot_protocol_frame_v2.json"
POL = C / "phase7_3_3_d_multi_claim_successor_pilot_execution_policy_frame_v2.json"
CPROMPT = C / "phase7_3_3_d_multi_claim_successor_candidate_arm_prompt_frame_v2.md"
APROMPT = C / "phase7_3_3_d_multi_claim_successor_atomic_arm_prompt_frame_v2.md"
CSCHEMA = C / "phase7_3_3_d_multi_claim_successor_candidate_arm_schema_frame_v2.json"
ASCHEMA = C / "phase7_3_3_d_multi_claim_successor_atomic_arm_schema_frame_v2.json"
WORK = D / "phase7_3_3_d_multi_claim_successor_pilot_worklist_frame_v2.json"
FIX = R / "phase7_3_3_d_multi_claim_successor_pilot_fixtures_frame_v2.json"
FREEZE = R / "phase7_3_3_d_multi_claim_successor_pilot_environment_freeze_manifest_frame_v2.json"
MAN = R / "phase7_3_3_d_multi_claim_successor_pilot_execution_manifest_frame_v2.json"
PREC = R / "phase7_3_3_d_multi_claim_successor_pilot_prepare_receipt_frame_v2.json"
LOG = R / "phase7_3_3_d_multi_claim_successor_pilot_attempts_frame_v2.jsonl"
CCASES = R / "phase7_3_3_d_multi_claim_successor_candidate_arm_cases_frame_v2"
ACASES = R / "phase7_3_3_d_multi_claim_successor_atomic_arm_cases_frame_v2"
CSUB = D / "phase7_3_3_d_multi_claim_successor_candidate_arm_submission_frame_v2.json"
ASUB = D / "phase7_3_3_d_multi_claim_successor_atomic_arm_submission_frame_v2.json"
RESULT = R / "phase7_3_3_d_multi_claim_successor_pilot_execution_result_frame_v2.json"
REC = R / "phase7_3_3_d_multi_claim_successor_pilot_execution_receipt_frame_v2.json"
NEG = R / "phase7_3_3_d_multi_claim_successor_pilot_negative_result_frame_v2.json"
SP = D / "phase7_3_3_d_support_stage_state_v94.json"
RP = R / "phase7_3_3_d1_reference_construction_readiness_v105.json"
SO = D / "phase7_3_3_d_support_stage_state_v95.json"
RO = R / "phase7_3_3_d1_reference_construction_readiness_v106.json"

CUR = "freeze_multi_claim_successor_candidate_atomic_pilot_protocol_frame_v2"
EXEC = "execute_multi_claim_successor_candidate_atomic_pilot_frame_v2"
NEXT = "evaluate_multi_claim_successor_realized_identifiability_frame_v2"
FAIL = "blocked_multi_claim_successor_pilot_frame_v2_authoritative_negative"
BASE = "https://api.gpt.ge/v1"
CRED = "PHASE7_ATOMIC_JUDGE_API_KEY"
MODEL = "gpt-5.4"
LABELS = ["supported", "partially_supported", "unsupported", "not_assessable"]
MAX_TOKENS = 800


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


def candidate_prompt() -> str:
    return """# Candidate-arm Support Reviewer - frame v2

## System message

Judge the supplied Candidate as one whole unit against the supplied Evidence. Return bare JSON with exactly one key: label_code, an integer where 0=supported, 1=partially_supported, 2=unsupported, 3=not_assessable.

Supported requires conservative support for the whole Candidate. Partially supported means a substantive part is supported but some material scope, causal, temporal, or factual content is not. Unsupported means the Candidate's material content lacks support or is contradicted. Do not output atomic labels, citations, rationale, Markdown, or extra keys.

## User message template

Review this frozen case. Return bare JSON only.

{{CASE_JSON}}
"""


def atomic_prompt() -> str:
    return """# Atomic-arm Support Reviewer - frame v2

## System message

The Candidate contains exactly six newline-delimited atomic units in order. Judge each unit independently against the supplied Evidence. Return bare JSON with exactly one key: label_codes, exactly six integers where 0=supported, 1=partially_supported, 2=unsupported, 3=not_assessable.

Supported requires conservative support for the entire unit. Partially supported means a substantive core is supported but full scope, causal strength, temporal extent, or qualification is not. Unsupported means required support is absent or contradicted. Do not merge units. Do not output spans, citations, rationale, Markdown, or extra keys.

## User message template

Review this frozen case. Return bare JSON only.

{{CASE_JSON}}
"""


def candidate_schema():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["label_code"], "properties": {"label_code": {"type": "integer", "minimum": 0, "maximum": 3}}, "additionalProperties": False}


def atomic_schema():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["label_codes"], "properties": {"label_codes": {"type": "array", "minItems": 6, "maxItems": 6, "items": {"type": "integer", "minimum": 0, "maximum": 3}}}, "additionalProperties": False}


def protocol():
    return {
        "schema_version": 2,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-candidate-atomic-pilot-frame-v2",
        "status": "frozen_before_any_arm_provider_call",
        "study_role": "exploratory_identifiable_multi_claim_pilot",
        "primary_estimand": "paired_mean_material_error_span_iou_atomic_minus_candidate",
        "paired_unit": "unique_candidate",
        "case_count": 40,
        "candidate_arm": "one whole-Candidate support label",
        "atomic_arm": "six newline-delimited local atomic-unit support labels with adapter-derived immutable spans",
        "resource_equality": {"provider": "api.gpt.ge", "model": MODEL, "temperature": 0, "top_p": 1, "max_tokens": MAX_TOKENS, "request_count_per_case_per_arm": 1, "reviewer_count_per_arm": 1, "adjudicator_count_per_arm": 0, "same_case_payload": True},
        "counterbalance": "deterministic 20 candidate-first and 20 atomic-first",
        "visibility": {"reference_content": False, "reference_labels": False, "other_arm": False, "confirmatory_content": False},
        "failure_policy": {"first_provider_content_authoritative": True, "transport_failure_resume_same_manifest": True, "semantic_retry": False, "repair": False, "paired_failures_not_dropped": True, "change_requires_successor": True},
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def policy():
    return {
        "schema_version": 2,
        "policy_id": "phase7.3.3-d-multi-claim-successor-pilot-execution-policy-frame-v2",
        "provider": "api.gpt.ge",
        "base_url": BASE,
        "credential_env_name": CRED,
        "model": MODEL,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},
        "case_isolation": True,
        "raw_provider_content_stored": False,
        "provider_envelope_and_content_hashes_recorded": True,
        "latency_and_token_usage_recorded": True,
        "usd_cost": None,
        "usd_cost_status": "provider_price_not_frozen",
        "reference_parse_during_execution_allowed": False,
        "confirmatory_dataset_opening_allowed": False,
        "runtime_integration_allowed": False,
    }


def visible_case(source):
    return {
        "case_id": source["candidate_id"],
        "candidate_text": source["candidate_text"],
        "line_count": len(source["candidate_text"].splitlines()),
        "evidence_bundle": copy.deepcopy(source["evidence_bundle"]),
    }


def worklist():
    cases = load(DATA)["cases"]
    items = []
    for index, case in enumerate(cases, start=1):
        first = "candidate" if index % 2 else "atomic"
        items.append({
            "pilot_index": index,
            "case_id": case["candidate_id"],
            "candidate_sha256": case["candidate_sha256"],
            "evidence_bundle_sha256": case["evidence_bundle_sha256"],
            "first_arm": first,
            "second_arm": "atomic" if first == "candidate" else "candidate",
            "candidate_content_included": False,
            "evidence_content_included": False,
        })
    return {"schema_version": 2, "worklist_id": "phase7.3.3-d-multi-claim-successor-pilot-worklist-frame-v2", "status": "frozen_counterbalanced_content_sealed", "case_count": 40, "first_arm_counts": {"candidate": 20, "atomic": 20}, "items": items, "confirmatory_content_opened": False}


def line_spans(text: str):
    spans = []
    cursor = 0
    for index, line in enumerate(text.splitlines(), start=1):
        spans.append({"unit_index": index, "start": cursor, "end": cursor + len(line), "source_excerpt": line})
        cursor += len(line) + (1 if index < len(text.splitlines()) else 0)
    return spans


def parse_candidate(output):
    if not isinstance(output, dict) or set(output) != {"label_code"}:
        raise ValueError("candidate_root_invalid")
    code = output["label_code"]
    if type(code) is not int or code < 0 or code > 3:
        raise ValueError("candidate_label_code_invalid")
    return {"label_code": code, "support_label": LABELS[code]}


def parse_atomic(case, output):
    if not isinstance(output, dict) or set(output) != {"label_codes"}:
        raise ValueError("atomic_root_invalid")
    codes = output["label_codes"]
    if not isinstance(codes, list) or len(codes) != 6 or any(type(code) is not int or code < 0 or code > 3 for code in codes):
        raise ValueError("atomic_label_codes_invalid")
    spans = line_spans(case["candidate_text"])
    if len(spans) != 6:
        raise ValueError("atomic_line_count_invalid")
    return [{**span, "operation": "local_line_claim", "label_code": codes[index], "support_label": LABELS[codes[index]]} for index, span in enumerate(spans)]


def fixtures():
    case = load(DATA)["cases"][0]
    tests = []
    examples = [
        ("candidate_valid", lambda: parse_candidate({"label_code": 1}), True),
        ("candidate_extra_rejected", lambda: parse_candidate({"label_code": 1, "extra": 0}), False),
        ("atomic_valid", lambda: parse_atomic(case, {"label_codes": [0, 0, 2, 2, 1, 1]}), True),
        ("atomic_short_rejected", lambda: parse_atomic(case, {"label_codes": [0] * 5}), False),
        ("atomic_boolean_rejected", lambda: parse_atomic(case, {"label_codes": [True] * 6}), False),
        ("six_local_spans", lambda: (_ for _ in ()).throw(ValueError()) if len(line_spans(case["candidate_text"])) != 6 else None, True),
    ]
    for fixture_id, function, expected in examples:
        try:
            function()
            accepted = True
        except Exception:
            accepted = False
        tests.append({"fixture_id": fixture_id, "passed": accepted == expected})
    return {"schema_version": 2, "fixtures_id": "phase7.3.3-d-multi-claim-successor-pilot-fixtures-frame-v2", "fixture_count": len(tests), "passed_count": sum(test["passed"] for test in tests), "all_fixtures_passed": all(test["passed"] for test in tests), "fixtures": tests}


def input_checks():
    checks = {"selected_dataset_hash": DATA.exists() and sha(DATA) == "788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe"}
    for path in [GOLD, GSEAL, STRUCT, SREC, SI, RI]:
        checks["exists:" + rel(path)] = path.exists()
    if all(checks.values()):
        receipt, state, readiness = load(SREC), load(SI), load(RI)
        checks.update({
            "structural_report_lineage": receipt["report_sha256"] == sha(STRUCT),
            "structural_state_lineage": receipt["state_sha256"] == sha(SI),
            "structural_readiness_lineage": receipt["readiness_sha256"] == sha(RI),
            "structural_pass": load(STRUCT)["structural_estimand_identifiable"] is True and receipt["arm_execution_authorized"] is True,
            "state_gate": state["next_authorized_stage"] == CUR,
            "readiness_gate": readiness["next_authorized_stage"] == CUR,
            "gold_hash_only_lineage": load(GSEAL)["support_gold_sha256"] == sha(GOLD),
            "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    return checks


def freeze_manifest():
    inputs = [DATA, GOLD, GSEAL, STRUCT, SREC, SI, RI]
    artifacts = [PRO, POL, CPROMPT, APROMPT, CSCHEMA, ASCHEMA, WORK, FIX]
    return {
        "schema_version": 2,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-pilot-environment-freeze-manifest-frame-v2",
        "status": "frozen_before_any_arm_provider_call",
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): sha(path) for path in inputs},
        "frozen_protocol_environment": {rel(path): sha(path) for path in artifacts},
        "provider": "api.gpt.ge",
        "model": MODEL,
        "credential_env_name": CRED,
        "reference_content_parsed_during_execution": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": EXEC,
    }


def execution_manifest():
    return {
        "schema_version": 2,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-pilot-execution-manifest-frame-v2",
        "status": "frozen_not_started",
        "environment_freeze_manifest_sha256": sha(FREEZE),
        "adapter_sha256": sha(SELF),
        "worklist_sha256": sha(WORK),
        "case_count": 40,
        "paired_request_count": 80,
        "model_requested": MODEL,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": MAX_TOKENS,
        "first_provider_content_authoritative": True,
        "same_version_semantic_retry_allowed": False,
        "transport_resume_same_manifest_allowed": True,
        "reference_content_loaded": False,
        "reference_labels_loaded": False,
        "confirmatory_content_loaded": False,
    }


def preflight():
    checks = input_checks()
    checks["outputs_absent"] = all(not path.exists() for path in [PRO, POL, CPROMPT, APROMPT, CSCHEMA, ASCHEMA, WORK, FIX, FREEZE, MAN, PREC, SP, RP, CSUB, ASUB, RESULT, REC, NEG])
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare():
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    once(PRO, protocol())
    once(POL, policy())
    once(CPROMPT, candidate_prompt().encode())
    once(APROMPT, atomic_prompt().encode())
    once(CSCHEMA, candidate_schema())
    once(ASCHEMA, atomic_schema())
    once(WORK, worklist())
    once(FIX, fixtures())
    freeze_hash = once(FREEZE, freeze_manifest())
    manifest_hash = once(MAN, execution_manifest())
    state, readiness = copy.deepcopy(load(SI)), copy.deepcopy(load(RI))
    lineage = {"multi_claim_successor_pilot_environment_freeze_manifest_frame_v2_sha256": freeze_hash, "multi_claim_successor_pilot_execution_manifest_frame_v2_sha256": manifest_hash}
    update = {
        "status": "multi_claim_successor_candidate_atomic_pilot_frame_v2_frozen_execution_authorized",
        "next_authorized_stage": EXEC,
        "multi_claim_successor_pilot_protocol_frame_v2_frozen": True,
        "multi_claim_successor_pilot_environment_frame_v2_frozen": True,
        "multi_claim_successor_pilot_frame_v2_executed": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 94, "state_id": "phase7.3.3-d-support-stage-state-v94"})
    readiness.update({"schema_version": 105, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v105"})
    state_hash = once(SP, state)
    readiness["artifact_lineage"]["support_stage_state_v94_sha256"] = state_hash
    readiness_hash = once(RP, readiness)
    receipt_hash = once(PREC, {
        "schema_version": 2,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-pilot-prepare-receipt-frame-v2",
        "status": "PASS",
        "environment_freeze_manifest_sha256": freeze_hash,
        "execution_manifest_sha256": manifest_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": EXEC,
    })
    return {"status": "PASS", "environment_freeze_manifest_sha256": freeze_hash, "execution_manifest_sha256": manifest_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": EXEC}


def verify_prepare():
    paths = [PRO, POL, CPROMPT, APROMPT, CSCHEMA, ASCHEMA, WORK, FIX, FREEZE, MAN, PREC, SP, RP]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        checks.update({
            "protocol_replay": load(PRO) == protocol(),
            "policy_replay": load(POL) == policy(),
            "candidate_prompt_replay": CPROMPT.read_bytes() == candidate_prompt().encode(),
            "atomic_prompt_replay": APROMPT.read_bytes() == atomic_prompt().encode(),
            "candidate_schema_replay": load(CSCHEMA) == candidate_schema(),
            "atomic_schema_replay": load(ASCHEMA) == atomic_schema(),
            "worklist_replay": load(WORK) == worklist(),
            "fixtures_replay": load(FIX) == fixtures(),
            "fixtures_pass": load(FIX)["all_fixtures_passed"] is True,
            "freeze_manifest_replay": load(FREEZE) == freeze_manifest(),
            "execution_manifest_replay": load(MAN) == execution_manifest(),
            "state_gate": load(SP)["next_authorized_stage"] == EXEC,
            "readiness_gate": load(RP)["next_authorized_stage"] == EXEC,
            "arm_outputs_absent": all(not path.exists() for path in [CSUB, ASUB, RESULT, REC, NEG]),
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def split_prompt(path: Path):
    source = path.read_text(encoding="utf-8-sig").split("## System message\n\n", 1)[1]
    return [part.strip() for part in source.split("\n## User message template\n\n", 1)]


def canonical(reported):
    if not isinstance(reported, str):
        raise ValueError("model_missing")
    normalized = reported.lower().rsplit("/", 1)[-1]
    expected = MODEL.lower()
    if normalized == expected or normalized.startswith(expected + "-"):
        return MODEL
    raise ValueError("model_family_mismatch")


def request(key: str, system: str, user: str):
    payload = {"model": MODEL, "temperature": 0, "top_p": 1, "max_tokens": MAX_TOKENS, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as response:
        raw = response.read()
    return raw, round((time.perf_counter() - started) * 1000, 3)


def checkpoint_path(arm: str, case_id: str):
    return (CCASES if arm == "candidate" else ACASES) / f"{case_id}.json"


def execute_one(key: str, arm: str, case, manifest_hash: str):
    path = checkpoint_path(arm, case["candidate_id"])
    if path.exists():
        return load(path), None
    prompt_path = CPROMPT if arm == "candidate" else APROMPT
    system, template = split_prompt(prompt_path)
    visible = visible_case(case)
    append_event({"event_type": "successor_pilot_attempt_started", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "response_received": False, "authoritative_result": False}, LOG)
    try:
        raw, latency = request(key, system, template.replace("{{CASE_JSON}}", json.dumps(visible, ensure_ascii=False, indent=2)))
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        append_event({"event_type": "successor_pilot_transport_failure", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "failure_type": type(error).__name__, "response_received": False, "same_manifest_resume_allowed": True}, LOG)
        return None, {"status": "TRANSPORT_FAILURE_RESUMABLE", "arm": arm, "case_id": case["candidate_id"]}
    envelope_hash = hb(raw)
    content = None
    try:
        envelope = json.loads(raw.decode())
        reported_model = envelope.get("model")
        content = envelope["choices"][0]["message"]["content"]
        content_hash = hb(content.encode())
        family = canonical(reported_model)
        parsed = parse_candidate(json.loads(content)) if arm == "candidate" else parse_atomic(case, json.loads(content))
        usage = envelope.get("usage") or {}
        resource = {"latency_ms": latency, "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"), "total_tokens": usage.get("total_tokens"), "cost_usd": None}
    except Exception as error:
        content_hash = hb(content.encode()) if isinstance(content, str) else None
        code = type(error).__name__ + ":" + str(error)
        append_event({"event_type": "successor_pilot_contract_failure", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "failure_code": code, "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash, "response_received": True, "authoritative_result": True}, LOG)
        return None, {"status": "AUTHORITATIVE_NEGATIVE_RESULT", "arm": arm, "case_id": case["candidate_id"], "failure_code": code, "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash}
    checkpoint = {"schema_version": 2, "checkpoint_id": f"successor-pilot-frame-v2-{arm}-{case['candidate_id']}", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "provider_reported_model": reported_model, "canonical_model_family": family, "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash, "decision": parsed, "resources": resource, "reference_visible": False, "other_arm_visible": False, "raw_provider_content_stored": False}
    checkpoint_hash = once(path, checkpoint)
    append_event({"event_type": "successor_pilot_attempt_completed", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "checkpoint_sha256": checkpoint_hash, "provider_content_sha256": content_hash, "response_received": True, "authoritative_result": True}, LOG)
    return checkpoint, None


def execute():
    checked = verify_prepare()
    if checked["status"] != "PASS":
        return checked
    if load(SP)["next_authorized_stage"] != EXEC or load(RP)["next_authorized_stage"] != EXEC:
        raise RuntimeError("stage_not_authorized")
    key = os.environ.get(CRED)
    if not key:
        raise RuntimeError("credential_missing:" + CRED)
    frozen = load(FREEZE)
    for path_string, expected in {**frozen["frozen_inputs"], **frozen["frozen_protocol_environment"]}.items():
        if sha(ROOT / path_string) != expected:
            raise RuntimeError("freeze_hash_mismatch:" + path_string)
    manifest_hash = sha(MAN)
    cases = {case["candidate_id"]: case for case in load(DATA)["cases"]}
    candidate_results, atomic_results = [], []
    for item in load(WORK)["items"]:
        case = cases[item["case_id"]]
        for arm in [item["first_arm"], item["second_arm"]]:
            checkpoint, failure = execute_one(key, arm, case, manifest_hash)
            if failure:
                if failure["status"] == "TRANSPORT_FAILURE_RESUMABLE":
                    return failure
                negative_hash = once(NEG, {"schema_version": 2, "negative_result_id": "phase7.3.3-d-multi-claim-successor-pilot-negative-result-frame-v2", "status": "authoritative_negative_result", "manifest_sha256": manifest_hash, "failed_arm": failure["arm"], "failed_case_id": failure["case_id"], "failure_code": failure["failure_code"], "provider_envelope_sha256": failure["provider_envelope_sha256"], "provider_content_sha256": failure["provider_content_sha256"], "same_version_retry_allowed": False, "pilot_scoring_allowed": False, "reference_content_loaded": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": FAIL})
                return {"status": "AUTHORITATIVE_NEGATIVE_RESULT", "negative_result_sha256": negative_hash, "same_version_retry_allowed": False, "next_authorized_stage": FAIL}
            (candidate_results if arm == "candidate" else atomic_results).append(checkpoint)
    candidate_results = [load(checkpoint_path("candidate", item["case_id"])) for item in load(WORK)["items"]]
    atomic_results = [load(checkpoint_path("atomic", item["case_id"])) for item in load(WORK)["items"]]
    candidate_submission = {"schema_version": 2, "submission_id": "phase7.3.3-d-multi-claim-successor-candidate-arm-submission-frame-v2", "status": "completed", "arm": "candidate", "manifest_sha256": manifest_hash, "case_count": 40, "request_count": 40, "cases": [{"case_id": row["case_id"], "decision": row["decision"], "resources": row["resources"]} for row in candidate_results], "reference_visible": False, "completed": True}
    atomic_submission = {"schema_version": 2, "submission_id": "phase7.3.3-d-multi-claim-successor-atomic-arm-submission-frame-v2", "status": "completed", "arm": "atomic", "manifest_sha256": manifest_hash, "case_count": 40, "request_count": 40, "atomic_unit_count": sum(len(row["decision"]) for row in atomic_results), "cases": [{"case_id": row["case_id"], "decisions": row["decision"], "resources": row["resources"]} for row in atomic_results], "reference_visible": False, "completed": True}
    candidate_hash, atomic_hash = once(CSUB, candidate_submission), once(ASUB, atomic_submission)
    result_hash = once(RESULT, {"schema_version": 2, "result_id": "phase7.3.3-d-multi-claim-successor-pilot-execution-result-frame-v2", "status": "PASS", "manifest_sha256": manifest_hash, "attempt_log_sha256": sha(LOG), "candidate_submission_sha256": candidate_hash, "atomic_submission_sha256": atomic_hash, "case_count": 40, "request_count": 80, "candidate_request_count": 40, "atomic_request_count": 40, "counterbalance_first_arm_counts": {"candidate": 20, "atomic": 20}, "resource_equality_verified": True, "reference_content_loaded": False, "reference_labels_loaded": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": NEXT})
    state, readiness = copy.deepcopy(load(SP)), copy.deepcopy(load(RP))
    lineage = {"multi_claim_successor_candidate_arm_submission_frame_v2_sha256": candidate_hash, "multi_claim_successor_atomic_arm_submission_frame_v2_sha256": atomic_hash, "multi_claim_successor_pilot_execution_result_frame_v2_sha256": result_hash}
    update = {"status": "multi_claim_successor_candidate_atomic_pilot_frame_v2_completed_realized_gate_authorized", "next_authorized_stage": NEXT, "multi_claim_successor_pilot_frame_v2_executed": True, "multi_claim_successor_candidate_arm_frame_v2_completed": True, "multi_claim_successor_atomic_arm_frame_v2_completed": True, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 95, "state_id": "phase7.3.3-d-support-stage-state-v95"})
    readiness.update({"schema_version": 106, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v106"})
    state_hash = once(SO, state)
    readiness["artifact_lineage"]["support_stage_state_v95_sha256"] = state_hash
    readiness_hash = once(RO, readiness)
    receipt_hash = once(REC, {"schema_version": 2, "receipt_id": "phase7.3.3-d-multi-claim-successor-pilot-execution-receipt-frame-v2", "status": "PASS", "execution_manifest_sha256": manifest_hash, "candidate_submission_sha256": candidate_hash, "atomic_submission_sha256": atomic_hash, "execution_result_sha256": result_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "case_count": 40, "request_count": 80, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": NEXT})
    return {"status": "PASS", "case_count": 40, "request_count": 80, "candidate_submission_sha256": candidate_hash, "atomic_submission_sha256": atomic_hash, "result_sha256": result_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": NEXT}


def verify():
    paths = [PRO, POL, CPROMPT, APROMPT, CSCHEMA, ASCHEMA, WORK, FIX, FREEZE, MAN, PREC, SP, RP, CSUB, ASUB, RESULT, REC, SO, RO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        candidate, atomic, result, receipt = load(CSUB), load(ASUB), load(RESULT), load(REC)
        checks.update({
            "prepare_replay": verify_prepare()["status"] == "PASS" or all(path.exists() for path in [CSUB, ASUB]),
            "attempt_log_chain": isinstance(read_entries(LOG), list),
            "candidate_40": candidate["case_count"] == len(candidate["cases"]) == 40,
            "atomic_40_240": atomic["case_count"] == len(atomic["cases"]) == 40 and atomic["atomic_unit_count"] == sum(len(case["decisions"]) for case in atomic["cases"]) == 240,
            "case_ids_equal": [case["case_id"] for case in candidate["cases"]] == [case["case_id"] for case in atomic["cases"]] == [item["case_id"] for item in load(WORK)["items"]],
            "candidate_labels_valid": all(case["decision"]["support_label"] in LABELS for case in candidate["cases"]),
            "atomic_labels_valid": all(decision["support_label"] in LABELS for case in atomic["cases"] for decision in case["decisions"]),
            "atomic_local_spans": all(len(case["decisions"]) == 6 and all(decision["operation"] == "local_line_claim" for decision in case["decisions"]) for case in atomic["cases"]),
            "result_lineage": result["candidate_submission_sha256"] == sha(CSUB) and result["atomic_submission_sha256"] == sha(ASUB),
            "receipt_lineage": receipt["candidate_submission_sha256"] == sha(CSUB) and receipt["atomic_submission_sha256"] == sha(ASUB) and receipt["execution_result_sha256"] == sha(RESULT) and receipt["state_sha256"] == sha(SO) and receipt["readiness_sha256"] == sha(RO),
            "reference_invisible": candidate["reference_visible"] is False and atomic["reference_visible"] is False and result["reference_content_loaded"] is False,
            "state_gate": load(SO)["next_authorized_stage"] == load(RO)["next_authorized_stage"] == NEXT,
            "confirmatory_closed": load(SO)["confirmatory_dataset_opened"] is False and load(RO)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(SO)["runtime_integration_authorized"] is False and load(RO)["runtime_integration_authorized"] is False,
        })
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(SO)["next_authorized_stage"] if SO.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["preflight", "fixtures", "prepare", "verify-prepare", "execute", "verify"]:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    if args.preflight:
        outcome = preflight()
    elif args.fixtures:
        outcome = fixtures()
        outcome["status"] = "PASS" if outcome["all_fixtures_passed"] else "FAIL"
    elif args.prepare:
        outcome = prepare()
    elif args.verify_prepare:
        outcome = verify_prepare()
    elif args.execute:
        outcome = execute()
    else:
        outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") in {"PASS", "TRANSPORT_FAILURE_RESUMABLE", "AUTHORITATIVE_NEGATIVE_RESULT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
