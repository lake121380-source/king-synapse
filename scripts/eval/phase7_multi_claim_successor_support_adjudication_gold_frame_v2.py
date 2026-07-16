#!/usr/bin/env python3
"""Blind Support disagreement adjudication and frame-v2 Gold freeze."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from phase7_execution_attempt_log import append_event, read_entries

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
R = ROOT / "crates/eval/reports"

DATA = D / "phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json"
TREF = D / "phase7_3_3_d_multi_claim_successor_type_metadata_reference_frame_v3.json"
TSEAL = R / "phase7_3_3_d_multi_claim_successor_type_metadata_reference_seal_frame_v3.json"
SUB_A = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_a_submission_frame_v5.json"
SUB_C = R / "phase7_3_3_d_multi_claim_successor_support_reviewer_c_submission_frame_v5.json"
BCLASS = R / "phase7_3_3_d_multi_claim_successor_support_v5_failure_classification.json"
AGREE = R / "phase7_3_3_d_multi_claim_successor_support_agreement_report_frame_v5.json"
WL = D / "phase7_3_3_d_multi_claim_successor_support_label_disagreement_worklist_frame_v5.json"
AREC = R / "phase7_3_3_d_multi_claim_successor_support_agreement_receipt_frame_v5.json"
SI = D / "phase7_3_3_d_support_stage_state_v91.json"
RI = R / "phase7_3_3_d1_reference_construction_readiness_v102.json"

PRO = C / "phase7_3_3_d_multi_claim_successor_support_adjudication_protocol_frame_v5.json"
SCH = C / "phase7_3_3_d_multi_claim_successor_support_adjudication_schema_frame_v5.json"
POL = C / "phase7_3_3_d_multi_claim_successor_support_adjudication_policy_frame_v5.json"
PROMPT = C / "phase7_3_3_d_multi_claim_successor_support_adjudicator_prompt_frame_v5.md"
PACKET = D / "phase7_3_3_d_multi_claim_successor_support_adjudication_packet_frame_v5.json"
MAPPING = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_private_mapping_frame_v5.json"
FIX = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_fixtures_frame_v5.json"
MAN = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_manifest_frame_v5.json"
PREC = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_prepare_receipt_frame_v5.json"
LOG = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_attempts_frame_v5.jsonl"
CASES = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_cases_frame_v5"
SUB = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_submission_frame_v5.json"
RESULT = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_result_frame_v5.json"
ADJ_REC = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_receipt_frame_v5.json"
NEG = R / "phase7_3_3_d_multi_claim_successor_support_adjudication_negative_frame_v5.json"

GPRO = C / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_protocol_frame_v2.json"
GFIX = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_fixtures_frame_v2.json"
GMAN = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_manifest_frame_v2.json"
REF = D / "phase7_3_3_d_multi_claim_successor_support_reference_candidate_frame_v2.json"
RQA = R / "phase7_3_3_d_multi_claim_successor_support_reference_candidate_qa_frame_v2.json"
RSEAL = R / "phase7_3_3_d_multi_claim_successor_support_reference_candidate_seal_frame_v2.json"
GOLD = D / "phase7_3_3_d_multi_claim_successor_support_gold_frame_v2.json"
GREP = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_report_frame_v2.json"
GSEAL = R / "phase7_3_3_d_multi_claim_successor_support_gold_seal_frame_v2.json"
GREC = R / "phase7_3_3_d_multi_claim_successor_support_gold_freeze_receipt_frame_v2.json"
SO = D / "phase7_3_3_d_support_stage_state_v92.json"
RO = R / "phase7_3_3_d1_reference_construction_readiness_v103.json"

CUR = "adjudicate_multi_claim_successor_support_label_disagreements_frame_v5"
NEXT = "evaluate_multi_claim_successor_structural_identifiability_frame_v2"
FAIL = "blocked_multi_claim_successor_support_adjudication_frame_v5_authoritative_negative"
BASE = "https://api.gpt.ge/v1"
CRED = "PHASE7_ATOMIC_JUDGE_API_KEY"
MODEL = "gpt-5.4"
LABELS = ["supported", "partially_supported", "unsupported", "not_assessable"]
EXPECTED = {
    DATA: "788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe",
    TREF: "f19845566adc324d8210a5041c5ecee2338e4bf97a549d320b257c705a6da8d8",
    TSEAL: "59954ada0b6454f18011d51516f7c9ee65fdc879671ea762e87c976ab561e0b1",
    SUB_A: "3a186b9a9be817f1e19a4c85f7c4865b07eab2b4f9ce6e5e88f14146f211e185",
    SUB_C: "476c3e79eece5ae90fa408f8b1e9c180f010fdf1985c0d5177b5c0612a2bbbb7",
    BCLASS: "a534269aef195e915541dc1fc23cbba68b814fecfb7ca782257b284ea8a88b3e",
    AGREE: "6062765d9275210a4061e1dcbaf502b12ac3e7bd589aabe143ae77e59caeaa0e",
    WL: "f7887cbed29f8e3ed2fb84daafd97dd2a5585f4ee47974258ac62bcd1b226c04",
    AREC: "0428c9a20896393b043ebd583d72f9f48854f2f2055835720795b67d0834acb6",
    SI: "7c809dc301fd2c22f07f8abc4446317c1da19ed683ef07626a4706d1b5c8ee11",
    RI: "7c0b8664fc5b6c2122940ddf6df299e44b99083854ab515111968e0e143d7bfc",
}


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


def flatten(submission):
    return [decision for case in submission["cases"] for decision in case["decisions"]]


def prompt_text() -> str:
    return """# Blind Support Label Adjudicator - frame v5

## System message

Choose which of two anonymous Support labels is more defensible for the frozen Claim under the supplied Evidence. Return bare JSON with exactly one key: option_code, integer 0 or 1 selecting options[0] or options[1].

Supported requires conservative entailment of the whole Claim. Partially supported means a substantive core is supported but full scope, causal strength, temporal extent, or qualification is not. Unsupported means required support is absent or contradicted. Not assessable is reserved for Claims that cannot responsibly be evaluated from supplied Evidence.

Do not output a label string, reviewer identity, citations, rationale, Markdown, or extra keys. Do not modify the Claim.

## User message template

Adjudicate this frozen item. Return bare JSON only.

{{ITEM_JSON}}
"""


def schema():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["option_code"], "properties": {"option_code": {"type": "integer", "minimum": 0, "maximum": 1}}, "additionalProperties": False}


def protocol():
    return {"schema_version": 1, "protocol_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-frame-v5", "status": "frozen_before_provider_call", "work_item_count": 47, "adjudication_object": "select one immutable anonymous reviewer label option", "option_order": "sha256(reference_claim_id) parity", "source_reviewer_identity_visible": False, "reviewer_marginal_distributions_visible": False, "evidence_visible": True, "claim_mutation_allowed": False, "model": MODEL, "first_provider_content_authoritative": True, "same_version_retry_allowed": False, "transport_resume_same_manifest_allowed": True, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def policy():
    return {"schema_version": 1, "policy_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-policy-frame-v5", "provider": "api.gpt.ge", "base_url": BASE, "credential_env_name": CRED, "model": MODEL, "temperature": 0, "top_p": 1, "max_tokens": 120, "response_format": {"type": "json_object"}, "case_isolation": True, "raw_provider_content_stored": False, "provider_hashes_recorded": True, "invalid_content_authoritative_negative": True, "confirmatory_dataset_opening_allowed": False, "runtime_integration_allowed": False}


def indexed_inputs():
    evidence = {case["candidate_id"]: case for case in load(DATA)["cases"]}
    claims = {claim["reference_claim_id"]: claim for case in load(TREF)["cases"] for claim in case["claims"]}
    a = {row["reference_claim_id"]: row for row in flatten(load(SUB_A))}
    c = {row["reference_claim_id"]: row for row in flatten(load(SUB_C))}
    return evidence, claims, a, c


def packet_and_mapping():
    evidence, claims, a, c = indexed_inputs()
    public, private = [], []
    for work in load(WL)["items"]:
        claim_id = work["reference_claim_id"]
        left = ("reviewer_a_v5", a[claim_id]["support_label"])
        right = ("reviewer_c_v5_supplement", c[claim_id]["support_label"])
        ordered = [left, right] if int(hashlib.sha256(claim_id.encode()).hexdigest(), 16) % 2 == 0 else [right, left]
        public.append({"work_item_id": work["work_item_id"], "case_id": work["case_id"], "reference_claim_id": claim_id, "claim": {key: copy.deepcopy(claims[claim_id][key]) for key in ["source_excerpt", "claim_role", "claim_type", "claim_origin"]}, "evidence_bundle": copy.deepcopy(evidence[work["case_id"]]["evidence_bundle"]), "options": [ordered[0][1], ordered[1][1]]})
        private.append({"work_item_id": work["work_item_id"], "reference_claim_id": claim_id, "option_sources": [ordered[0][0], ordered[1][0]], "option_labels": [ordered[0][1], ordered[1][1]]})
    packet = {"schema_version": 1, "packet_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-packet-frame-v5", "status": "frozen_blind_option_packet", "work_item_count": len(public), "items": public, "source_reviewer_identity_visible": False, "reviewer_marginal_distributions_visible": False}
    mapping = {"schema_version": 1, "mapping_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-private-mapping-frame-v5", "status": "frozen_not_visible_to_adjudicator", "work_item_count": len(private), "items": private}
    return packet, mapping


def parse(output):
    if not isinstance(output, dict) or set(output) != {"option_code"}:
        raise ValueError("root_invalid")
    code = output["option_code"]
    if type(code) is not int or code not in {0, 1}:
        raise ValueError("option_code_invalid")
    return code


def fixtures():
    tests = []
    for fixture_id, output, expected in [("valid_zero", {"option_code": 0}, True), ("valid_one", {"option_code": 1}, True), ("two_rejected", {"option_code": 2}, False), ("boolean_rejected", {"option_code": True}, False), ("label_leak_rejected", {"option_code": 0, "label": "supported"}, False)]:
        try:
            parse(output)
            accepted = True
        except ValueError:
            accepted = False
        tests.append({"fixture_id": fixture_id, "passed": accepted == expected})
    packet, mapping = packet_and_mapping()
    tests.extend([{"fixture_id": "47_items", "passed": packet["work_item_count"] == mapping["work_item_count"] == 47}, {"fixture_id": "public_sources_hidden", "passed": all("reviewer" not in json.dumps(item) for item in packet["items"])}, {"fixture_id": "mapping_options_match", "passed": all(public["options"] == private["option_labels"] for public, private in zip(packet["items"], mapping["items"]))}])
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-support-adjudication-fixtures-frame-v5", "fixture_count": len(tests), "passed_count": sum(test["passed"] for test in tests), "all_fixtures_passed": all(test["passed"] for test in tests), "fixtures": tests}


def manifest():
    inputs = list(EXPECTED)
    artifacts = [PRO, SCH, POL, PROMPT, PACKET, MAPPING, FIX]
    return {"schema_version": 1, "manifest_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-manifest-frame-v5", "status": "frozen_not_started", "adapter_sha256": sha(SELF), "frozen_inputs": {rel(path): sha(path) for path in inputs}, "frozen_protocol_artifacts": {rel(path): sha(path) for path in artifacts}, "model_requested": MODEL, "case_count": 47, "first_provider_content_authoritative": True, "same_version_retry_allowed": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def gold_protocol():
    return {"schema_version": 2, "protocol_id": "phase7.3.3-d-multi-claim-successor-support-gold-freeze-frame-v2", "status": "frozen_before_adjudication_execution", "gold_scope": "Support labels only", "resolution": {"agreement_claims": 193, "adjudication_claims": 47}, "gold_creation_requires_completed_47_item_adjudication": True, "claim_boundary_mutation_allowed": False, "claim_metadata_mutation_allowed": False, "support_label_recomputation_allowed": False, "diagnostic_fields_promoted_to_gold": False, "provider_calls_during_gold_freeze": 0, "confirmatory_dataset_opening_allowed": False, "runtime_integration_allowed": False, "passing_next_stage": NEXT}


def gold_fixtures():
    rows = [{"fixture_id": "partition_193_47", "passed": 193 + 47 == 240}, {"fixture_id": "label_only", "passed": gold_protocol()["gold_scope"] == "Support labels only"}, {"fixture_id": "adjudication_required", "passed": gold_protocol()["gold_creation_requires_completed_47_item_adjudication"] is True}, {"fixture_id": "confirmatory_closed", "passed": gold_protocol()["confirmatory_dataset_opening_allowed"] is False}]
    return {"schema_version": 2, "fixtures_id": "phase7.3.3-d-support-gold-freeze-fixtures-frame-v2", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def preflight():
    checks = {"input_hash:" + rel(path): path.exists() and sha(path) == expected for path, expected in EXPECTED.items()}
    if all(checks.values()):
        state, readiness = load(SI), load(RI)
        checks.update({"state_gate": state["next_authorized_stage"] == CUR, "readiness_gate": readiness["next_authorized_stage"] == CUR, "disagreements_47": load(WL)["work_item_count"] == load(AGREE)["disagreement_count"] == 47, "agreement_193": load(AGREE)["agreement_count"] == 193, "reviewer_b_excluded": load(BCLASS)["reviewer_b_submission_created"] is False, "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False, "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False, "outputs_absent": all(not path.exists() for path in [PRO, SCH, POL, PROMPT, PACKET, MAPPING, FIX, MAN, PREC, SUB, RESULT, ADJ_REC, NEG, GPRO, GFIX, GMAN, REF, RQA, RSEAL, GOLD, GREP, GSEAL, GREC, SO, RO])})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def prepare():
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    packet, mapping = packet_and_mapping()
    once(PRO, protocol()); once(SCH, schema()); once(POL, policy()); once(PROMPT, prompt_text().encode()); once(PACKET, packet); once(MAPPING, mapping); once(FIX, fixtures()); once(GPRO, gold_protocol()); once(GFIX, gold_fixtures())
    manifest_hash = once(MAN, manifest())
    receipt_hash = once(PREC, {"schema_version": 1, "receipt_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-prepare-receipt-frame-v5", "status": "PASS", "manifest_sha256": manifest_hash, "packet_sha256": sha(PACKET), "private_mapping_sha256": sha(MAPPING), "gold_protocol_sha256": sha(GPRO), "gold_fixtures_sha256": sha(GFIX), "provider_called": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": CUR})
    return {"status": "PASS", "manifest_sha256": manifest_hash, "receipt_sha256": receipt_hash, "fixtures": f"{fixtures()['passed_count']}/{fixtures()['fixture_count']}", "next_authorized_stage": CUR}


def verify_prepare():
    paths = [PRO, SCH, POL, PROMPT, PACKET, MAPPING, FIX, MAN, PREC, GPRO, GFIX]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        packet, mapping = packet_and_mapping()
        checks.update({"protocol_replay": load(PRO) == protocol(), "schema_replay": load(SCH) == schema(), "policy_replay": load(POL) == policy(), "prompt_replay": PROMPT.read_bytes() == prompt_text().encode(), "packet_replay": load(PACKET) == packet, "mapping_replay": load(MAPPING) == mapping, "fixtures_replay": load(FIX) == fixtures(), "fixtures_pass": load(FIX)["all_fixtures_passed"] is True, "manifest_replay": load(MAN) == manifest(), "gold_protocol_replay": load(GPRO) == gold_protocol(), "gold_fixtures_replay": load(GFIX) == gold_fixtures(), "outputs_absent": all(not path.exists() for path in [SUB, RESULT, ADJ_REC, NEG, GMAN, REF, RQA, RSEAL, GOLD, GREP, GSEAL, GREC, SO, RO])})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def split_prompt():
    source = PROMPT.read_text(encoding="utf-8-sig").split("## System message\n\n", 1)[1]
    return [part.strip() for part in source.split("\n## User message template\n\n", 1)]


def canonical(reported):
    if not isinstance(reported, str):
        raise ValueError("model_missing")
    normalized, expected = reported.lower().rsplit("/", 1)[-1], MODEL.lower()
    if normalized == expected or normalized.startswith(expected + "-"):
        return MODEL
    raise ValueError("model_family_mismatch")


def request(key, system, user):
    payload = {"model": MODEL, "temperature": 0, "top_p": 1, "max_tokens": 120, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as response:
        return response.read()


def cp(work_item_id):
    return CASES / f"{work_item_id}.json"


def mapping_index():
    return {item["work_item_id"]: item for item in load(MAPPING)["items"]}


def execute():
    if SUB.exists() and RESULT.exists() and ADJ_REC.exists():
        return freeze_gold(sha(SUB), sha(RESULT), sha(ADJ_REC))
    if NEG.exists():
        return {"status": "AUTHORITATIVE_NEGATIVE_RESULT", "negative_result_sha256": sha(NEG), "next_authorized_stage": FAIL}
    checked = verify_prepare()
    if checked["status"] != "PASS":
        return checked
    if load(SI)["next_authorized_stage"] != CUR or load(RI)["next_authorized_stage"] != CUR:
        raise RuntimeError("stage_not_authorized")
    key = os.environ.get(CRED)
    if not key:
        raise RuntimeError("credential_missing:" + CRED)
    frozen = load(MAN)
    for path_string, expected in {**frozen["frozen_inputs"], **frozen["frozen_protocol_artifacts"]}.items():
        if sha(ROOT / path_string) != expected:
            raise RuntimeError("manifest_hash_mismatch:" + path_string)
    system, template = split_prompt()
    manifest_hash = sha(MAN)
    private = mapping_index()
    completed = []
    for item in load(PACKET)["items"]:
        path = cp(item["work_item_id"])
        if path.exists():
            completed.append(load(path)); continue
        append_event({"event_type": "support_adjudication_attempt_started", "manifest_sha256": manifest_hash, "work_item_id": item["work_item_id"], "reference_claim_id": item["reference_claim_id"], "response_received": False, "authoritative_result": False}, LOG)
        try:
            raw = request(key, system, template.replace("{{ITEM_JSON}}", json.dumps(item, ensure_ascii=False, indent=2)))
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            append_event({"event_type": "support_adjudication_transport_failure", "manifest_sha256": manifest_hash, "work_item_id": item["work_item_id"], "failure_type": type(error).__name__, "response_received": False, "same_manifest_resume_allowed": True}, LOG)
            return {"status": "TRANSPORT_FAILURE_RESUMABLE", "completed_item_count": len(completed), "failed_work_item_id": item["work_item_id"]}
        envelope_hash = hb(raw); content = None
        try:
            envelope = json.loads(raw.decode()); reported = envelope.get("model"); content = envelope["choices"][0]["message"]["content"]; content_hash = hb(content.encode()); family = canonical(reported); option = parse(json.loads(content)); mapping = private[item["work_item_id"]]; selected_label = mapping["option_labels"][option]; selected_source = mapping["option_sources"][option]
        except Exception as error:
            content_hash = hb(content.encode()) if isinstance(content, str) else None; code = type(error).__name__ + ":" + str(error)
            append_event({"event_type": "support_adjudication_contract_failure", "manifest_sha256": manifest_hash, "work_item_id": item["work_item_id"], "failure_code": code, "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash, "response_received": True, "authoritative_result": True}, LOG)
            negative_hash = once(NEG, {"schema_version": 1, "negative_result_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-negative-frame-v5", "status": "authoritative_negative_result", "manifest_sha256": manifest_hash, "failed_work_item_id": item["work_item_id"], "completed_item_count": len(completed), "failure_code": code, "same_version_retry_allowed": False, "support_gold_creation_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": FAIL})
            return {"status": "AUTHORITATIVE_NEGATIVE_RESULT", "negative_result_sha256": negative_hash, "next_authorized_stage": FAIL}
        checkpoint = {"schema_version": 1, "checkpoint_id": f"support-adjudication-frame-v5-{item['work_item_id']}", "manifest_sha256": manifest_hash, "work_item_id": item["work_item_id"], "reference_claim_id": item["reference_claim_id"], "provider_reported_model": reported, "canonical_model_family": family, "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash, "selected_option_code": option, "selected_support_label": selected_label, "selected_source_reviewer": selected_source, "claim_mutation_performed": False, "raw_provider_content_stored": False}
        checkpoint_hash = once(path, checkpoint)
        append_event({"event_type": "support_adjudication_attempt_completed", "manifest_sha256": manifest_hash, "work_item_id": item["work_item_id"], "reference_claim_id": item["reference_claim_id"], "checkpoint_sha256": checkpoint_hash, "provider_content_sha256": content_hash, "response_received": True, "authoritative_result": True}, LOG)
        completed.append(checkpoint)
    decisions = [load(cp(item["work_item_id"])) for item in load(PACKET)["items"]]
    submission_hash = once(SUB, {"schema_version": 1, "submission_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-submission-frame-v5", "status": "completed", "manifest_sha256": manifest_hash, "work_item_count": 47, "decision_count": 47, "decisions": [{key: row[key] for key in ["work_item_id", "reference_claim_id", "selected_option_code", "selected_support_label", "selected_source_reviewer"]} for row in decisions], "claim_mutation_performed": False, "completed": True})
    result_hash = once(RESULT, {"schema_version": 1, "result_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-result-frame-v5", "status": "PASS", "manifest_sha256": manifest_hash, "attempt_log_sha256": sha(LOG), "submission_sha256": submission_hash, "work_item_count": 47, "decision_count": 47, "provider_calls": 47, "support_gold_freeze_authorized": True})
    adjudication_receipt_hash = once(ADJ_REC, {"schema_version": 1, "receipt_id": "phase7.3.3-d-multi-claim-successor-support-adjudication-receipt-frame-v5", "status": "PASS", "manifest_sha256": manifest_hash, "submission_sha256": submission_hash, "result_sha256": result_hash, "work_item_count": 47, "decision_count": 47, "support_gold_freeze_authorized": True})
    return freeze_gold(submission_hash, result_hash, adjudication_receipt_hash)


def resolved_labels():
    a = {row["reference_claim_id"]: row["support_label"] for row in flatten(load(SUB_A))}
    c = {row["reference_claim_id"]: row["support_label"] for row in flatten(load(SUB_C))}
    adjudicated = {row["reference_claim_id"]: row["selected_support_label"] for row in load(SUB)["decisions"]}
    labels = {}
    for claim_id in a:
        labels[claim_id] = a[claim_id] if a[claim_id] == c[claim_id] else adjudicated[claim_id]
    return labels


def reference_doc():
    labels = resolved_labels(); cases = []
    for source_case in load(TREF)["cases"]:
        claims = []
        for source_claim in source_case["claims"]:
            claim = copy.deepcopy(source_claim); claim_id = claim["reference_claim_id"]
            claim.update({"support_label": labels[claim_id], "label_resolution_basis": "independent_a_c_exact_agreement" if next(row["support_label"] for row in flatten(load(SUB_A)) if row["reference_claim_id"] == claim_id) == next(row["support_label"] for row in flatten(load(SUB_C)) if row["reference_claim_id"] == claim_id) else "blind_adjudication_selected_immutable_option", "diagnostic_fields_authoritative": False, "boundary_mutation_performed": False, "metadata_mutation_performed": False})
            claims.append(claim)
        cases.append({"case_id": source_case["case_id"], "claim_count": len(claims), "claims": claims})
    counts = Counter(claim["support_label"] for case in cases for claim in case["claims"])
    return {"schema_version": 2, "reference_candidate_id": "phase7.3.3-d-multi-claim-successor-support-reference-candidate-frame-v2", "status": "verified_model_reviewed_and_adjudicated_support_label_reference_candidate", "case_count": 40, "claim_count": 240, "label_counts": dict(sorted(counts.items())), "independent_label_agreement_count": 193, "adjudicated_label_count": 47, "support_gold_created": False, "cases": cases}


def gold_manifest(submission_hash, result_hash, adjudication_receipt_hash):
    inputs = [TREF, TSEAL, SUB_A, SUB_C, AGREE, WL, SUB, RESULT, ADJ_REC]
    return {"schema_version": 2, "manifest_id": "phase7.3.3-d-multi-claim-successor-support-gold-freeze-manifest-frame-v2", "status": "frozen_after_completed_adjudication_before_gold_write", "adapter_sha256": sha(SELF), "protocol_sha256": sha(GPRO), "fixtures_sha256": sha(GFIX), "frozen_inputs": {rel(path): sha(path) for path in inputs}, "adjudication_submission_sha256": submission_hash, "adjudication_result_sha256": result_hash, "adjudication_receipt_sha256": adjudication_receipt_hash, "case_count": 40, "claim_count": 240, "gold_fields": ["support_label"], "provider_calls_during_gold_freeze": 0, "next_authorized_stage": NEXT}


def gold_doc():
    reference = load(REF); cases = []
    for source_case in reference["cases"]:
        claims = []
        for source_claim in source_case["claims"]:
            claim = copy.deepcopy(source_claim); claim.update({"gold_fields": ["support_label"], "diagnostic_fields_gold_status": "not_gold_not_collected_in_label_only_v5"}); claims.append(claim)
        cases.append({"case_id": source_case["case_id"], "claim_count": len(claims), "claims": claims})
    return {"schema_version": 2, "support_gold_id": "phase7.3.3-d-multi-claim-successor-support-gold-frame-v2", "status": "frozen_project_support_gold_model_reviewed_and_adjudicated_not_human_gold", "gold_scope": "Support labels only", "gold_fields": ["support_label"], "artifact_lineage": {"type_metadata_reference_sha256": sha(TREF), "support_reference_candidate_sha256": sha(REF), "adjudication_submission_sha256": sha(SUB), "freeze_manifest_sha256": sha(GMAN)}, "case_count": 40, "claim_count": 240, "label_counts": reference["label_counts"], "independent_label_agreement_count": 193, "adjudicated_label_count": 47, "support_gold_frozen": True, "support_label_recomputation_performed": False, "diagnostic_fields_promoted_to_gold": False, "provider_called_during_gold_freeze": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "cases": cases}


def freeze_gold(submission_hash, result_hash, adjudication_receipt_hash):
    gm_hash = once(GMAN, gold_manifest(submission_hash, result_hash, adjudication_receipt_hash))
    ref_hash = once(REF, reference_doc())
    reference = load(REF); rows = [claim for case in reference["cases"] for claim in case["claims"]]; qa_checks = {"case_count_40": reference["case_count"] == len(reference["cases"]) == 40, "claim_count_240": reference["claim_count"] == len(rows) == 240, "claim_ids_unique": len({row["reference_claim_id"] for row in rows}) == 240, "labels_valid": all(row["support_label"] in LABELS for row in rows), "resolution_partition": reference["independent_label_agreement_count"] + reference["adjudicated_label_count"] == 240, "boundary_immutable": all(row["boundary_mutation_performed"] is False for row in rows), "metadata_immutable": all(row["metadata_mutation_performed"] is False for row in rows)}
    if not all(qa_checks.values()):
        raise RuntimeError("reference_qa_failed")
    qa_hash = once(RQA, {"schema_version": 2, "qa_id": "phase7.3.3-d-multi-claim-successor-support-reference-candidate-qa-frame-v2", "status": "PASS", "reference_candidate_sha256": ref_hash, "checks": qa_checks, "failed_checks": []})
    reference_seal_hash = once(RSEAL, {"schema_version": 2, "seal_id": "phase7.3.3-d-multi-claim-successor-support-reference-candidate-seal-frame-v2", "status": "verified_and_sealed_not_final_gold", "reference_candidate_sha256": ref_hash, "qa_sha256": qa_hash, "claim_count": 240, "support_reference_candidate_sealed": True})
    gold_hash = once(GOLD, gold_doc())
    report_hash = once(GREP, {"schema_version": 2, "report_id": "phase7.3.3-d-multi-claim-successor-support-gold-freeze-report-frame-v2", "status": "PASS", "manifest_sha256": gm_hash, "support_gold_sha256": gold_hash, "reference_candidate_sha256": ref_hash, "case_count": 40, "claim_count": 240, "label_counts": load(GOLD)["label_counts"], "gold_fields": ["support_label"], "provider_calls_during_gold_freeze": 0, "next_authorized_stage": NEXT})
    seal_hash = once(GSEAL, {"schema_version": 2, "seal_id": "phase7.3.3-d-multi-claim-successor-support-gold-seal-frame-v2", "status": "frozen_support_label_gold_not_human_gold", "support_gold_sha256": gold_hash, "freeze_report_sha256": report_hash, "reference_candidate_seal_sha256": reference_seal_hash, "claim_count": 240, "gold_fields": ["support_label"], "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": NEXT})
    state, readiness = copy.deepcopy(load(SI)), copy.deepcopy(load(RI)); lineage = {"multi_claim_successor_support_adjudication_manifest_frame_v5_sha256": sha(MAN), "multi_claim_successor_support_adjudication_submission_frame_v5_sha256": submission_hash, "multi_claim_successor_support_adjudication_result_frame_v5_sha256": result_hash, "multi_claim_successor_support_gold_freeze_manifest_frame_v2_sha256": gm_hash, "multi_claim_successor_support_reference_candidate_frame_v2_sha256": ref_hash, "multi_claim_successor_support_gold_frame_v2_sha256": gold_hash, "multi_claim_successor_support_gold_seal_frame_v2_sha256": seal_hash}; update = {"status": "multi_claim_successor_support_gold_frame_v2_frozen_structural_identifiability_authorized", "next_authorized_stage": NEXT, "multi_claim_successor_support_adjudication_frame_v5_completed": True, "multi_claim_successor_support_reference_candidate_frame_v2_sealed": True, "multi_claim_successor_support_gold_frame_v2_created": True, "multi_claim_successor_support_gold_frame_v2_frozen": True, "multi_claim_successor_support_gold_frame_v2_sha256": gold_hash, "multi_claim_successor_structural_identifiability_frame_v2_authorized": True, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    for document in [state, readiness]: document.setdefault("artifact_lineage", {}).update(lineage); document.update(update)
    state.update({"schema_version": 92, "state_id": "phase7.3.3-d-support-stage-state-v92"}); readiness.update({"schema_version": 103, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v103"}); state_hash = once(SO, state); readiness["artifact_lineage"]["support_stage_state_v92_sha256"] = state_hash; readiness_hash = once(RO, readiness)
    gold_receipt_hash = once(GREC, {"schema_version": 2, "receipt_id": "phase7.3.3-d-multi-claim-successor-support-gold-freeze-receipt-frame-v2", "status": "PASS", "manifest_sha256": gm_hash, "adjudication_receipt_sha256": adjudication_receipt_hash, "reference_candidate_sha256": ref_hash, "reference_candidate_qa_sha256": qa_hash, "reference_candidate_seal_sha256": reference_seal_hash, "support_gold_sha256": gold_hash, "freeze_report_sha256": report_hash, "seal_sha256": seal_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "claim_count": 240, "gold_fields": ["support_label"], "support_gold_frozen": True, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False, "next_authorized_stage": NEXT})
    return {"status": "PASS", "adjudication_submission_sha256": submission_hash, "adjudication_result_sha256": result_hash, "adjudication_receipt_sha256": adjudication_receipt_hash, "support_reference_candidate_sha256": ref_hash, "support_gold_sha256": gold_hash, "label_counts": load(GOLD)["label_counts"], "gold_receipt_sha256": gold_receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": NEXT}


def verify():
    paths = [PRO, SCH, POL, PROMPT, PACKET, MAPPING, FIX, MAN, PREC, LOG, SUB, RESULT, ADJ_REC, GPRO, GFIX, GMAN, REF, RQA, RSEAL, GOLD, GREP, GSEAL, GREC, SO, RO]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        packet, mapping = packet_and_mapping(); decisions = load(SUB)["decisions"]; reference = load(REF); gold = load(GOLD); rows = [claim for case in gold["cases"] for claim in case["claims"]]; receipt = load(GREC)
        checks.update({"protocol_replay": load(PRO) == protocol(), "packet_replay": load(PACKET) == packet, "mapping_replay": load(MAPPING) == mapping, "fixtures_replay": load(FIX) == fixtures(), "manifest_replay": load(MAN) == manifest(), "attempt_log_chain": isinstance(read_entries(LOG), list), "adjudication_47": load(SUB)["decision_count"] == len(decisions) == 47, "adjudication_labels_valid": all(row["selected_support_label"] in LABELS for row in decisions), "gold_manifest_replay": load(GMAN) == gold_manifest(sha(SUB), sha(RESULT), sha(ADJ_REC)), "reference_replay": reference == reference_doc(), "gold_replay": gold == gold_doc(), "40_240": gold["case_count"] == len(gold["cases"]) == 40 and gold["claim_count"] == len(rows) == 240, "resolution_partition": gold["independent_label_agreement_count"] == 193 and gold["adjudicated_label_count"] == 47, "label_only": gold["gold_fields"] == ["support_label"] and all(row["gold_fields"] == ["support_label"] for row in rows), "receipt_lineage": receipt["adjudication_receipt_sha256"] == sha(ADJ_REC) and receipt["support_gold_sha256"] == sha(GOLD) and receipt["freeze_report_sha256"] == sha(GREP) and receipt["seal_sha256"] == sha(GSEAL) and receipt["state_sha256"] == sha(SO) and receipt["readiness_sha256"] == sha(RO), "state_gate": load(SO)["next_authorized_stage"] == load(RO)["next_authorized_stage"] == NEXT, "confirmatory_closed": load(SO)["confirmatory_dataset_opened"] is False and load(RO)["confirmatory_dataset_opened"] is False, "runtime_off": load(SO)["runtime_integration_authorized"] is False and load(RO)["runtime_integration_authorized"] is False})
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(SO)["next_authorized_stage"] if SO.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser(); group = parser.add_mutually_exclusive_group(required=True)
    for name in ["preflight", "fixtures", "prepare", "verify-prepare", "execute", "verify"]: group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    if args.preflight: outcome = preflight()
    elif args.fixtures: outcome = fixtures(); outcome["status"] = "PASS" if outcome["all_fixtures_passed"] else "FAIL"
    elif args.prepare: outcome = prepare()
    elif args.verify_prepare: outcome = verify_prepare()
    elif args.execute: outcome = execute()
    else: outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2)); return 0 if outcome.get("status") in {"PASS", "TRANSPORT_FAILURE_RESUMABLE", "AUTHORITATIVE_NEGATIVE_RESULT"} else 1


if __name__ == "__main__": raise SystemExit(main())
