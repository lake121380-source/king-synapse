#!/usr/bin/env python3
"""Freeze and execute the preregistered Confirmatory Candidate/Atomic arms."""
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
from typing import Any

from phase7_execution_attempt_log import append_event, read_entries


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

DATASET = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_dataset_v1.json"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_worklist_v1.json"
GOLD = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_v1.json"
GOLD_SEAL = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_seal_v1.json"
STRUCT_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_report_v1.json"
STRUCT_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_receipt_v1.json"
PREREG = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_preregistration_v1.json"
STATE_105 = PATTERN / "phase7_3_3_d_support_stage_state_v105.json"
READY_116 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v116.json"

PILOT_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_pilot_protocol_frame_v2.json"
PILOT_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_pilot_execution_policy_frame_v2.json"
CANDIDATE_PROMPT = CONFIG / "phase7_3_3_d_multi_claim_successor_candidate_arm_prompt_frame_v2.md"
ATOMIC_PROMPT = CONFIG / "phase7_3_3_d_multi_claim_successor_atomic_arm_prompt_frame_v2.md"
CANDIDATE_SCHEMA = CONFIG / "phase7_3_3_d_multi_claim_successor_candidate_arm_schema_frame_v2.json"
ATOMIC_SCHEMA = CONFIG / "phase7_3_3_d_multi_claim_successor_atomic_arm_schema_frame_v2.json"

EXEC_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_policy_v1.json"
EXEC_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_fixtures_v1.json"
ENV_FREEZE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_environment_freeze_manifest_v1.json"
EXEC_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_manifest_v1.json"
PREPARE_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_prepare_audit_v1.jsonl"
PREPARE_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_prepare_receipt_v1.json"
STATE_106 = PATTERN / "phase7_3_3_d_support_stage_state_v106.json"
READY_117 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v117.json"

ATTEMPT_LOG = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_attempts_v1.jsonl"
CANDIDATE_CASES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_candidate_arm_cases_v1"
ATOMIC_CASES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_atomic_arm_cases_v1"
CANDIDATE_SUBMISSION = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_candidate_arm_submission_v1.json"
ATOMIC_SUBMISSION = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_atomic_arm_submission_v1.json"
EXEC_RESULT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_result_v1.json"
EXEC_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_receipt_v1.json"
EXEC_NEGATIVE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_execution_negative_result_v1.json"
STATE_107 = PATTERN / "phase7_3_3_d_support_stage_state_v107.json"
READY_118 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v118.json"

PREPARE_CUR = "freeze_confirmatory_candidate_atomic_execution_environment_v1"
EXEC_CUR = "execute_confirmatory_candidate_atomic_arms_v1"
NEXT = "evaluate_confirmatory_realized_identifiability_v1"
FAIL = "blocked_confirmatory_execution_v1_authoritative_negative"
BASE = "https://api.gpt.ge/v1"
CREDENTIAL = "PHASE7_ATOMIC_JUDGE_API_KEY"
MODEL = "gpt-5.4"
MAX_TOKENS = 800
LABELS = ["supported", "partially_supported", "unsupported", "not_assessable"]


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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
    body = (json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("append_only_audit_mismatch:" + rel(path))
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(body)
    return hb(body)


def split_prompt(path: Path) -> tuple[str, str]:
    source = path.read_text(encoding="utf-8-sig").split("## System message\n\n", 1)[1]
    return tuple(part.strip() for part in source.split("\n## User message template\n\n", 1))  # type: ignore[return-value]


def line_spans(text: str) -> list[dict[str, Any]]:
    rows, cursor = [], 0
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        rows.append({"unit_index": index, "start": cursor, "end": cursor + len(line), "source_excerpt": line})
        cursor += len(line) + (1 if index < len(lines) else 0)
    return rows


def parse_candidate(output: Any) -> dict[str, Any]:
    if not isinstance(output, dict) or set(output) != {"label_code"}:
        raise ValueError("candidate_root_invalid")
    code = output["label_code"]
    if type(code) is not int or code < 0 or code > 3:
        raise ValueError("candidate_label_code_invalid")
    return {"label_code": code, "support_label": LABELS[code]}


def parse_atomic(case: dict[str, Any], output: Any) -> list[dict[str, Any]]:
    if not isinstance(output, dict) or set(output) != {"label_codes"}:
        raise ValueError("atomic_root_invalid")
    codes = output["label_codes"]
    if not isinstance(codes, list) or len(codes) != 6 or any(type(code) is not int or code < 0 or code > 3 for code in codes):
        raise ValueError("atomic_label_codes_invalid")
    spans = line_spans(case["candidate_text"])
    if len(spans) != 6:
        raise ValueError("atomic_line_count_invalid")
    return [{**span, "operation": "local_line_claim", "label_code": code, "support_label": LABELS[code]} for span, code in zip(spans, codes)]


def execution_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d-multi-claim-successor-confirmatory-execution-policy-v1",
        "status": "frozen_before_any_confirmatory_arm_provider_call",
        "provider": "api.gpt.ge",
        "base_url": BASE,
        "credential_env_name": CREDENTIAL,
        "model": MODEL,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},
        "case_isolation": True,
        "paired_request_count": 80,
        "raw_provider_content_stored": False,
        "provider_envelope_and_content_hashes_recorded": True,
        "latency_and_token_usage_recorded": True,
        "usd_cost": None,
        "usd_cost_status": "provider_price_not_frozen",
        "first_provider_content_authoritative": True,
        "transport_failure_resume_same_manifest": True,
        "semantic_retry": False,
        "repair": False,
        "paired_failures_not_dropped": True,
        "reference_content_loaded_during_execution": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }


def fixtures() -> dict[str, Any]:
    case = load(DATASET)["cases"][0]
    tests = []
    examples = [
        ("candidate_valid", lambda: parse_candidate({"label_code": 1}), True),
        ("candidate_extra_rejected", lambda: parse_candidate({"label_code": 1, "extra": 0}), False),
        ("atomic_valid", lambda: parse_atomic(case, {"label_codes": [0, 2, 1, 0, 2, 1]}), True),
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
    inherited = load(PREREG)["arms"]["prompt_and_schema_hashes_inherited_exactly"]
    tests.extend([
        {"fixture_id": "candidate_prompt_inherited", "passed": inherited[rel(CANDIDATE_PROMPT)] == sha(CANDIDATE_PROMPT)},
        {"fixture_id": "atomic_prompt_inherited", "passed": inherited[rel(ATOMIC_PROMPT)] == sha(ATOMIC_PROMPT)},
        {"fixture_id": "schemas_inherited", "passed": inherited[rel(CANDIDATE_SCHEMA)] == sha(CANDIDATE_SCHEMA) and inherited[rel(ATOMIC_SCHEMA)] == sha(ATOMIC_SCHEMA)},
        {"fixture_id": "model_inherited", "passed": load(PREREG)["arms"]["model"] == load(PILOT_PROTOCOL)["resource_equality"]["model"] == MODEL},
        {"fixture_id": "counterbalance_20_20", "passed": load(WORKLIST)["first_arm_counts"] == {"atomic": 20, "candidate": 20}},
    ])
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-execution-fixtures-v1", "fixture_count": len(tests), "passed_count": sum(test["passed"] for test in tests), "all_fixtures_passed": all(test["passed"] for test in tests), "fixtures": tests}


def input_checks() -> dict[str, bool]:
    paths = [DATASET, WORKLIST, GOLD, GOLD_SEAL, STRUCT_REPORT, STRUCT_RECEIPT, PREREG, STATE_105, READY_116, PILOT_PROTOCOL, PILOT_POLICY, CANDIDATE_PROMPT, ATOMIC_PROMPT, CANDIDATE_SCHEMA, ATOMIC_SCHEMA]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        state, readiness, structural = load(STATE_105), load(READY_116), load(STRUCT_REPORT)
        checks.update({
            "state_gate": state["next_authorized_stage"] == PREPARE_CUR,
            "readiness_gate": readiness["next_authorized_stage"] == PREPARE_CUR,
            "structural_lineage": load(STRUCT_RECEIPT)["report_sha256"] == sha(STRUCT_REPORT) and load(STRUCT_RECEIPT)["state_sha256"] == sha(STATE_105),
            "structural_pass": structural["structural_estimand_identifiable"] is True and structural["confirmatory_arm_execution_authorized"] is True,
            "gold_sealed": load(GOLD_SEAL)["support_gold_sha256"] == sha(GOLD),
            "dataset_40": load(DATASET)["case_count"] == len(load(DATASET)["cases"]) == 40,
            "prereg_40": load(PREREG)["sample_size_candidates"] == 40,
            "prompt_hashes_inherited": load(PREREG)["arms"]["prompt_and_schema_hashes_inherited_exactly"] == {rel(path): sha(path) for path in [CANDIDATE_PROMPT, ATOMIC_PROMPT, CANDIDATE_SCHEMA, ATOMIC_SCHEMA]},
            "model_inherited": load(PREREG)["arms"]["model"] == MODEL,
            "selected_opened": state["confirmatory_dataset_opened"] is True and readiness["confirmatory_dataset_opened"] is True,
            "unselected_closed": state["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "execution_not_started": state["multi_claim_successor_confirmatory_arm_execution_started"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    return checks


def environment_freeze() -> dict[str, Any]:
    frozen_inputs = [DATASET, WORKLIST, GOLD, GOLD_SEAL, STRUCT_REPORT, STRUCT_RECEIPT, PREREG, STATE_105, READY_116]
    protocol_environment = [PILOT_PROTOCOL, PILOT_POLICY, CANDIDATE_PROMPT, ATOMIC_PROMPT, CANDIDATE_SCHEMA, ATOMIC_SCHEMA, EXEC_POLICY, EXEC_FIXTURES]
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-environment-freeze-v1",
        "status": "frozen_before_any_confirmatory_arm_provider_call",
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): sha(path) for path in frozen_inputs},
        "frozen_protocol_environment": {rel(path): sha(path) for path in protocol_environment},
        "provider": "api.gpt.ge",
        "model": MODEL,
        "credential_env_name": CREDENTIAL,
        "reference_content_loaded_during_execution": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": EXEC_CUR,
    }


def execution_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-execution-manifest-v1",
        "status": "frozen_not_started",
        "environment_freeze_manifest_sha256": sha(ENV_FREEZE),
        "adapter_sha256": sha(SELF),
        "selected_worklist_sha256": sha(WORKLIST),
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
        "unselected_content_loaded": False,
        "runtime_integration_authorized": False,
    }


def prepare_preflight() -> dict[str, Any]:
    checks = input_checks()
    outputs = [EXEC_POLICY, EXEC_FIXTURES, ENV_FREEZE, EXEC_MANIFEST, PREPARE_AUDIT, PREPARE_RECEIPT, STATE_106, READY_117, ATTEMPT_LOG, CANDIDATE_SUBMISSION, ATOMIC_SUBMISSION, EXEC_RESULT, EXEC_RECEIPT, EXEC_NEGATIVE, STATE_107, READY_118]
    checks["outputs_absent"] = all(not path.exists() for path in outputs) and not CANDIDATE_CASES.exists() and not ATOMIC_CASES.exists()
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare() -> dict[str, Any]:
    checked = prepare_preflight()
    if checked["status"] != "PASS":
        return checked
    policy_hash = once(EXEC_POLICY, execution_policy())
    fixture_hash = once(EXEC_FIXTURES, fixtures())
    freeze_hash = once(ENV_FREEZE, environment_freeze())
    manifest_hash = once(EXEC_MANIFEST, execution_manifest())
    audit_hash = append_single_event(PREPARE_AUDIT, {"event_id": "confirmatory-execution-environment-v1-frozen", "event_type": "immutable_execution_environment_freeze", "environment_freeze_sha256": freeze_hash, "execution_manifest_sha256": manifest_hash, "provider_called": False})
    state, readiness = copy.deepcopy(load(STATE_105)), copy.deepcopy(load(READY_116))
    lineage = {
        "multi_claim_successor_confirmatory_execution_policy_v1_sha256": policy_hash,
        "multi_claim_successor_confirmatory_execution_fixtures_v1_sha256": fixture_hash,
        "multi_claim_successor_confirmatory_environment_freeze_v1_sha256": freeze_hash,
        "multi_claim_successor_confirmatory_execution_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_execution_prepare_audit_v1_sha256": audit_hash,
    }
    update = {
        "status": "confirmatory_execution_environment_v1_frozen_arms_authorized",
        "next_authorized_stage": EXEC_CUR,
        "multi_claim_successor_confirmatory_execution_protocol_frozen": True,
        "multi_claim_successor_confirmatory_execution_environment_frozen": True,
        "multi_claim_successor_confirmatory_arm_execution_started": False,
        "multi_claim_successor_confirmatory_arm_execution_completed": False,
        "confirmatory_dataset_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 106, "state_id": "phase7.3.3-d-support-stage-state-v106"})
    readiness.update({"schema_version": 117, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v117"})
    state_hash = once(STATE_106, state)
    readiness["artifact_lineage"]["support_stage_state_v106_sha256"] = state_hash
    readiness_hash = once(READY_117, readiness)
    receipt_hash = once(PREPARE_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-execution-prepare-receipt-v1",
        "status": "PASS",
        "environment_freeze_manifest_sha256": freeze_hash,
        "execution_manifest_sha256": manifest_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "provider_called": False,
        "reference_visible": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": EXEC_CUR,
    })
    return {"status": "PASS", "environment_freeze_manifest_sha256": freeze_hash, "execution_manifest_sha256": manifest_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": EXEC_CUR}


def verify_prepare() -> dict[str, Any]:
    paths = [EXEC_POLICY, EXEC_FIXTURES, ENV_FREEZE, EXEC_MANIFEST, PREPARE_AUDIT, PREPARE_RECEIPT, STATE_106, READY_117]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        receipt = load(PREPARE_RECEIPT)
        checks.update({
            "policy_replay": load(EXEC_POLICY) == execution_policy(),
            "fixtures_replay": load(EXEC_FIXTURES) == fixtures(),
            "environment_replay": load(ENV_FREEZE) == environment_freeze(),
            "manifest_replay": load(EXEC_MANIFEST) == execution_manifest(),
            "fixtures_pass": load(EXEC_FIXTURES)["all_fixtures_passed"] is True,
            "receipt_lineage": receipt["environment_freeze_manifest_sha256"] == sha(ENV_FREEZE) and receipt["execution_manifest_sha256"] == sha(EXEC_MANIFEST) and receipt["state_sha256"] == sha(STATE_106) and receipt["readiness_sha256"] == sha(READY_117),
            "state_gate": load(STATE_106)["next_authorized_stage"] == load(READY_117)["next_authorized_stage"] == EXEC_CUR,
            "provider_not_called": receipt["provider_called"] is False,
            "reference_invisible": receipt["reference_visible"] is False,
            "unselected_closed": load(STATE_106)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_106)["runtime_integration_authorized"] is False and load(READY_117)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_106)["next_authorized_stage"] if STATE_106.exists() else None}


def canonical_model(reported: Any) -> str:
    if not isinstance(reported, str):
        raise ValueError("model_missing")
    normalized = reported.lower().rsplit("/", 1)[-1]
    expected = MODEL.lower()
    if normalized == expected or normalized.startswith(expected + "-"):
        return MODEL
    raise ValueError("model_family_mismatch")


def request(key: str, system: str, user: str) -> tuple[bytes, float]:
    payload = {"model": MODEL, "temperature": 0, "top_p": 1, "max_tokens": MAX_TOKENS, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as response:
        raw = response.read()
    return raw, round((time.perf_counter() - started) * 1000, 3)


def visible_case(case: dict[str, Any]) -> dict[str, Any]:
    return {"case_id": case["candidate_id"], "candidate_text": case["candidate_text"], "line_count": len(case["candidate_text"].splitlines()), "evidence_bundle": copy.deepcopy(case["evidence_bundle"])}


def checkpoint_path(arm: str, case_id: str) -> Path:
    return (CANDIDATE_CASES if arm == "candidate" else ATOMIC_CASES) / f"{case_id}.json"


def execute_one(key: str, arm: str, case: dict[str, Any], manifest_hash: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    path = checkpoint_path(arm, case["candidate_id"])
    if path.exists():
        checkpoint = load(path)
        if checkpoint["manifest_sha256"] != manifest_hash:
            raise RuntimeError("checkpoint_manifest_mismatch:" + case["candidate_id"])
        return checkpoint, None
    prompt = CANDIDATE_PROMPT if arm == "candidate" else ATOMIC_PROMPT
    system, template = split_prompt(prompt)
    append_event({"event_type": "confirmatory_arm_attempt_started", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "response_received": False, "authoritative_result": False}, ATTEMPT_LOG)
    try:
        raw, latency = request(key, system, template.replace("{{CASE_JSON}}", json.dumps(visible_case(case), ensure_ascii=False, indent=2)))
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        append_event({"event_type": "confirmatory_arm_transport_failure", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "failure_type": type(error).__name__, "response_received": False, "authoritative_result": False, "same_manifest_resume_allowed": True}, ATTEMPT_LOG)
        return None, {"status": "TRANSPORT_FAILURE_RESUMABLE", "arm": arm, "case_id": case["candidate_id"]}
    envelope_hash = hb(raw)
    content = None
    try:
        envelope = json.loads(raw.decode("utf-8"))
        reported_model = envelope.get("model")
        content = envelope["choices"][0]["message"]["content"]
        content_hash = hb(content.encode("utf-8"))
        family = canonical_model(reported_model)
        parsed = parse_candidate(json.loads(content)) if arm == "candidate" else parse_atomic(case, json.loads(content))
        usage = envelope.get("usage") or {}
        resources = {"latency_ms": latency, "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"), "total_tokens": usage.get("total_tokens"), "cost_usd": None}
    except Exception as error:
        content_hash = hb(content.encode("utf-8")) if isinstance(content, str) else None
        failure_code = type(error).__name__ + ":" + str(error)
        append_event({"event_type": "confirmatory_arm_contract_failure", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "failure_code": failure_code, "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash, "response_received": True, "authoritative_result": True}, ATTEMPT_LOG)
        return None, {"status": "AUTHORITATIVE_NEGATIVE_RESULT", "arm": arm, "case_id": case["candidate_id"], "failure_code": failure_code, "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash}
    checkpoint = {
        "schema_version": 1,
        "checkpoint_id": f"confirmatory-v1-{arm}-{case['candidate_id']}",
        "manifest_sha256": manifest_hash,
        "arm": arm,
        "case_id": case["candidate_id"],
        "provider_reported_model": reported_model,
        "canonical_model_family": family,
        "provider_envelope_sha256": envelope_hash,
        "provider_content_sha256": content_hash,
        "decision": parsed,
        "resources": resources,
        "reference_visible": False,
        "other_arm_visible": False,
        "raw_provider_content_stored": False,
    }
    checkpoint_hash = once(path, checkpoint)
    append_event({"event_type": "confirmatory_arm_attempt_completed", "manifest_sha256": manifest_hash, "arm": arm, "case_id": case["candidate_id"], "checkpoint_sha256": checkpoint_hash, "provider_content_sha256": content_hash, "response_received": True, "authoritative_result": True}, ATTEMPT_LOG)
    return checkpoint, None


def frozen_hash_check() -> None:
    frozen = load(ENV_FREEZE)
    for path_string, expected in {**frozen["frozen_inputs"], **frozen["frozen_protocol_environment"]}.items():
        if sha(ROOT / path_string) != expected:
            raise RuntimeError("freeze_hash_mismatch:" + path_string)


def execute() -> dict[str, Any]:
    checked = verify_prepare()
    if checked["status"] != "PASS":
        return checked
    if load(STATE_106)["next_authorized_stage"] != EXEC_CUR or load(READY_117)["next_authorized_stage"] != EXEC_CUR:
        raise RuntimeError("stage_not_authorized")
    key = os.environ.get(CREDENTIAL)
    if not key:
        raise RuntimeError("credential_missing:" + CREDENTIAL)
    frozen_hash_check()
    manifest_hash = sha(EXEC_MANIFEST)
    cases = {case["candidate_id"]: case for case in load(DATASET)["cases"]}
    for item in sorted(load(WORKLIST)["items"], key=lambda row: row["confirmatory_index"]):
        case = cases[item["candidate_id"]]
        for arm in [item["first_arm"], item["second_arm"]]:
            _, failure = execute_one(key, arm, case, manifest_hash)
            if failure:
                if failure["status"] == "TRANSPORT_FAILURE_RESUMABLE":
                    return failure
                negative_hash = once(EXEC_NEGATIVE, {
                    "schema_version": 1,
                    "negative_result_id": "phase7.3.3-d-multi-claim-successor-confirmatory-execution-negative-v1",
                    "status": "authoritative_negative_result",
                    "manifest_sha256": manifest_hash,
                    "failed_arm": failure["arm"],
                    "failed_case_id": failure["case_id"],
                    "failure_code": failure["failure_code"],
                    "provider_envelope_sha256": failure["provider_envelope_sha256"],
                    "provider_content_sha256": failure["provider_content_sha256"],
                    "same_version_retry_allowed": False,
                    "confirmatory_scoring_allowed": False,
                    "reference_content_loaded": False,
                    "unselected_content_opened": False,
                    "runtime_integration_authorized": False,
                    "next_authorized_stage": FAIL,
                })
                return {"status": "AUTHORITATIVE_NEGATIVE_RESULT", "negative_result_sha256": negative_hash, "same_version_retry_allowed": False, "next_authorized_stage": FAIL}
    candidate_rows = [load(checkpoint_path("candidate", item["candidate_id"])) for item in sorted(load(WORKLIST)["items"], key=lambda row: row["confirmatory_index"])]
    atomic_rows = [load(checkpoint_path("atomic", item["candidate_id"])) for item in sorted(load(WORKLIST)["items"], key=lambda row: row["confirmatory_index"])]
    candidate_submission = {
        "schema_version": 1,
        "submission_id": "phase7.3.3-d-multi-claim-successor-confirmatory-candidate-arm-submission-v1",
        "status": "completed",
        "arm": "candidate",
        "manifest_sha256": manifest_hash,
        "case_count": 40,
        "request_count": 40,
        "cases": [{"case_id": row["case_id"], "decision": row["decision"], "resources": row["resources"]} for row in candidate_rows],
        "reference_visible": False,
        "completed": True,
        "runtime_integration_authorized": False,
    }
    atomic_submission = {
        "schema_version": 1,
        "submission_id": "phase7.3.3-d-multi-claim-successor-confirmatory-atomic-arm-submission-v1",
        "status": "completed",
        "arm": "atomic",
        "manifest_sha256": manifest_hash,
        "case_count": 40,
        "request_count": 40,
        "atomic_unit_count": sum(len(row["decision"]) for row in atomic_rows),
        "cases": [{"case_id": row["case_id"], "decisions": row["decision"], "resources": row["resources"]} for row in atomic_rows],
        "reference_visible": False,
        "completed": True,
        "runtime_integration_authorized": False,
    }
    candidate_hash = once(CANDIDATE_SUBMISSION, candidate_submission)
    atomic_hash = once(ATOMIC_SUBMISSION, atomic_submission)
    result_hash = once(EXEC_RESULT, {
        "schema_version": 1,
        "result_id": "phase7.3.3-d-multi-claim-successor-confirmatory-execution-result-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "attempt_log_sha256": sha(ATTEMPT_LOG),
        "candidate_submission_sha256": candidate_hash,
        "atomic_submission_sha256": atomic_hash,
        "case_count": 40,
        "request_count": 80,
        "candidate_request_count": 40,
        "atomic_request_count": 40,
        "counterbalance_first_arm_counts": {"candidate": 20, "atomic": 20},
        "resource_equality_verified": True,
        "reference_content_loaded": False,
        "reference_labels_loaded": False,
        "unselected_content_opened": False,
        "confirmatory_dataset_opened": True,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    })
    state, readiness = copy.deepcopy(load(STATE_106)), copy.deepcopy(load(READY_117))
    lineage = {
        "multi_claim_successor_confirmatory_candidate_arm_submission_v1_sha256": candidate_hash,
        "multi_claim_successor_confirmatory_atomic_arm_submission_v1_sha256": atomic_hash,
        "multi_claim_successor_confirmatory_execution_result_v1_sha256": result_hash,
        "multi_claim_successor_confirmatory_execution_attempt_log_v1_sha256": sha(ATTEMPT_LOG),
    }
    update = {
        "status": "confirmatory_candidate_atomic_execution_v1_completed_realized_gate_authorized",
        "next_authorized_stage": NEXT,
        "multi_claim_successor_confirmatory_arm_execution_started": True,
        "multi_claim_successor_confirmatory_arm_execution_completed": True,
        "multi_claim_successor_confirmatory_candidate_arm_completed": True,
        "multi_claim_successor_confirmatory_atomic_arm_completed": True,
        "confirmatory_dataset_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 107, "state_id": "phase7.3.3-d-support-stage-state-v107"})
    readiness.update({"schema_version": 118, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v118"})
    state_hash = once(STATE_107, state)
    readiness["artifact_lineage"]["support_stage_state_v107_sha256"] = state_hash
    readiness_hash = once(READY_118, readiness)
    receipt_hash = once(EXEC_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-execution-receipt-v1",
        "status": "PASS",
        "execution_manifest_sha256": manifest_hash,
        "attempt_log_sha256": sha(ATTEMPT_LOG),
        "candidate_submission_sha256": candidate_hash,
        "atomic_submission_sha256": atomic_hash,
        "execution_result_sha256": result_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "case_count": 40,
        "request_count": 80,
        "reference_visible": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    })
    return {"status": "PASS", "case_count": 40, "request_count": 80, "candidate_submission_sha256": candidate_hash, "atomic_submission_sha256": atomic_hash, "result_sha256": result_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": NEXT}


def verify_execution() -> dict[str, Any]:
    paths = [EXEC_POLICY, EXEC_FIXTURES, ENV_FREEZE, EXEC_MANIFEST, PREPARE_AUDIT, PREPARE_RECEIPT, STATE_106, READY_117, ATTEMPT_LOG, CANDIDATE_SUBMISSION, ATOMIC_SUBMISSION, EXEC_RESULT, EXEC_RECEIPT, STATE_107, READY_118]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        candidate, atomic, result, receipt = load(CANDIDATE_SUBMISSION), load(ATOMIC_SUBMISSION), load(EXEC_RESULT), load(EXEC_RECEIPT)
        work_ids = [item["candidate_id"] for item in sorted(load(WORKLIST)["items"], key=lambda row: row["confirmatory_index"])]
        attempt_entries = read_entries(ATTEMPT_LOG)
        checks.update({
            "prepare_replay": verify_prepare()["status"] == "PASS",
            "attempt_log_chain": len(attempt_entries) >= 160,
            "authoritative_completions_80": sum(entry.get("event_type") == "confirmatory_arm_attempt_completed" for entry in attempt_entries) == 80,
            "candidate_40": candidate["case_count"] == len(candidate["cases"]) == 40,
            "atomic_40_240": atomic["case_count"] == len(atomic["cases"]) == 40 and atomic["atomic_unit_count"] == sum(len(case["decisions"]) for case in atomic["cases"]) == 240,
            "case_ids_equal": [case["case_id"] for case in candidate["cases"]] == [case["case_id"] for case in atomic["cases"]] == work_ids,
            "candidate_labels_valid": all(case["decision"]["support_label"] in LABELS for case in candidate["cases"]),
            "atomic_labels_valid": all(decision["support_label"] in LABELS for case in atomic["cases"] for decision in case["decisions"]),
            "atomic_local_spans": all(len(case["decisions"]) == 6 and all(decision["operation"] == "local_line_claim" for decision in case["decisions"]) for case in atomic["cases"]),
            "result_lineage": result["candidate_submission_sha256"] == sha(CANDIDATE_SUBMISSION) and result["atomic_submission_sha256"] == sha(ATOMIC_SUBMISSION) and result["attempt_log_sha256"] == sha(ATTEMPT_LOG),
            "receipt_lineage": receipt["candidate_submission_sha256"] == sha(CANDIDATE_SUBMISSION) and receipt["atomic_submission_sha256"] == sha(ATOMIC_SUBMISSION) and receipt["execution_result_sha256"] == sha(EXEC_RESULT) and receipt["state_sha256"] == sha(STATE_107) and receipt["readiness_sha256"] == sha(READY_118),
            "reference_invisible": candidate["reference_visible"] is False and atomic["reference_visible"] is False and result["reference_content_loaded"] is False and result["reference_labels_loaded"] is False,
            "state_gate": load(STATE_107)["next_authorized_stage"] == load(READY_118)["next_authorized_stage"] == NEXT,
            "unselected_closed": load(STATE_107)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_107)["runtime_integration_authorized"] is False and load(READY_118)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_107)["next_authorized_stage"] if STATE_107.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["prepare-preflight", "prepare", "verify-prepare", "execute", "verify-execution"]:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    if args.prepare_preflight:
        outcome = prepare_preflight()
    elif args.prepare:
        outcome = prepare()
    elif args.verify_prepare:
        outcome = verify_prepare()
    elif args.execute:
        outcome = execute()
    else:
        outcome = verify_execution()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") in {"PASS", "TRANSPORT_FAILURE_RESUMABLE"} else 2 if outcome.get("status") == "AUTHORITATIVE_NEGATIVE_RESULT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
