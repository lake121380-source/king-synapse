#!/usr/bin/env python3
"""Freeze and execute independent Reviewer D under the frozen Phase 7.3.3-D1-A v3 Boundary protocol.

The adapter never stores credentials or raw provider text. Returned content is
hashed, strictly parsed once, and persisted only as normalized immutable Claims.
Transport failures may resume under the same Manifest; semantic/schema failures
are authoritative negative results and may not be retried.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from phase7_execution_attempt_log import append_event, read_entries

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
CONFIG = ROOT / "crates/eval/config"
REPORTS = ROOT / "crates/eval/reports"
PACKET = DATA / "phase7_3_3_d_boundary_blind_review_packet_v1.json"
PROTOCOL = DATA / "phase7_3_3_d_boundary_reference_protocol_v3.json"
POLICY = CONFIG / "phase7_3_3_d_boundary_reviewer_execution_policy_v3.json"
PROMPT = CONFIG / "phase7_3_3_d_boundary_reviewer_prompt_v3.md"
BASE_URL = "https://api.gpt.ge/v1"
CREDENTIAL_ENV = "PHASE7_ATOMIC_JUDGE_API_KEY"
ATTEMPT_LOG = REPORTS / "phase7_3_3_d_boundary_reviewer_d_execution_attempts_v3.jsonl"
CORE_V3_ADAPTER = ROOT / "scripts/eval/phase7_boundary_reviewer_execution_v3.py"
INTERPRETATION_SUPPLEMENT = REPORTS / "phase7_3_3_d_boundary_contract_interpretation_supplement_v3.json"
FIXTURE_REPORT = REPORTS / "phase7_3_3_d_boundary_reviewer_contract_fixtures_v3.json"

REVIEWERS = {
    "d": {"model": "claude-sonnet-4-6", "manifest": REPORTS / "phase7_3_3_d_boundary_reviewer_d_execution_manifest_v3.json"},
}
CLAIM_KEYS = {"anchor_id", "source_excerpt", "occurrence_index", "claim_type", "material", "claim_origin", "boundary_rationale", "annotation_confidence"}
CLAIM_TYPES = {"proposition", "scope", "prediction", "causal", "counterexample", "limitation", "falsifiability"}
CLAIM_ROLE_BY_SOURCE_FIELD = {
    "proposition": "anchor",
    "prediction_statement": "prediction",
    "prediction_observable": "prediction_observable",
    "prediction_success_criterion": "prediction_criterion",
    "falsification_statement": "falsification",
    "falsification_observable": "falsification_observable",
}
ORIGINS = {"explicit", "inferred", "synthesized"}
CONFIDENCE = {"low", "medium", "high"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: Any) -> str:
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{path.relative_to(ROOT)}")
        return hashlib.sha256(encoded).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temp = Path(handle.name)
    temp.replace(path)
    return hashlib.sha256(encoded).hexdigest()


def split_prompt() -> tuple[str, str]:
    text = PROMPT.read_text(encoding="utf-8-sig")
    sm, um = "## System message\n", "## User message template\n"
    if sm not in text or um not in text:
        raise ValueError("prompt_sections_missing")
    return text.split(sm, 1)[1].split(um, 1)[0].strip(), text.split(um, 1)[1].strip()


def execution_policy() -> dict[str, Any]:
    return {
        "schema_version": 3,
        "policy_id": "phase7.3.3-d1-a-boundary-reviewer-execution-policy-v3",
        "phase": "Phase 7.3.3-D1-A v3 Occurrence-Aware Protocol-Owned Claim Role Boundary Review",
        "authoritative_result_policy": {
            "first_returned_provider_response_per_case_is_authoritative": True,
            "invalid_json_or_schema_is_negative_result": True,
            "automatic_repair_authorized": False,
            "semantic_retry_authorized": False,
            "selective_retry_authorized": False,
            "transport_failure_before_provider_content_may_resume": True,
        },
        "independence_controls": {
            "different_requested_models": True,
            "same_frozen_prompt": True,
            "same_frozen_packet": True,
            "case_isolation": True,
            "other_reviewer_output_visible": False,
            "judge_output_visible": False,
            "candidate_gold_or_silver_visible": False,
            "support_labels_visible": False,
            "web_tools_enabled": False,
            "external_memory_enabled": False,
        },
        "model_identity_handling": {
            "provider_reported_model_recorded_per_case": True,
            "canonical_model_family_derived_by_frozen_rule": True,
            "byte_identical_provider_alias_required": False,
            "outside_requested_family_is_negative_result": True,
        },
        "data_handling": {
            "credential_env_name": CREDENTIAL_ENV,
            "api_key_recorded": False,
            "raw_provider_text_recorded": False,
            "raw_provider_text_sha256_recorded": True,
            "normalized_claims_recorded": True,
            "held_out_loaded": False,
        },
        "post_execution_prohibitions": [
            "no_prompt_modification", "no_parser_modification", "no_packet_modification",
            "no_result_replacement", "no_semantic_retry", "no_support_adjudication",
            "no_held_out_access",
        ],
    }


def manifest(reviewer: str) -> dict[str, Any]:
    cfg = REVIEWERS[reviewer]
    return {
        "schema_version": 3,
        "manifest_id": f"phase7.3.3-d1-a-boundary-reviewer-{reviewer}-execution-v3",
        "reviewer": reviewer,
        "reviewer_type": "ai_model",
        "provider": "api.gpt.ge",
        "provider_base_url": BASE_URL,
        "model_requested": cfg["model"],
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
        "credential_env_name": CREDENTIAL_ENV,
        "adapter_sha256": sha(Path(__file__)),
        "frozen_core_v3_adapter_sha256": sha(CORE_V3_ADAPTER),
        "interpretation_supplement_sha256": sha(INTERPRETATION_SUPPLEMENT),
        "prompt_sha256": sha(PROMPT),
        "packet_sha256": sha(PACKET),
        "protocol_sha256": sha(PROTOCOL),
        "execution_policy_sha256": sha(POLICY),
        "contract_fixtures_sha256": sha(FIXTURE_REPORT),
        "case_count": 10,
        "case_isolation": True,
        "other_reviewer_visible": False,
        "support_labels_visible": False,
        "historical_judge_visible": False,
        "candidate_gold_or_silver_visible": False,
        "reference_candidates_visible": False,
        "held_out_accessed": False,
        "raw_provider_responses_stored": False,
        "first_response_authoritative": True,
        "status": "frozen_not_started",
    }


def prepare() -> None:
    if not FIXTURE_REPORT.exists() or load(FIXTURE_REPORT).get("all_fixtures_passed") is not True:
        raise ValueError("contract_fixtures_must_pass_before_prepare")
    packet = load(PACKET)
    if packet.get("case_count") != 10 or packet.get("held_out_accessed") is not False:
        raise ValueError("boundary_packet_not_ready")
    policy_hash = write_once(POLICY, execution_policy())
    outputs = {"policy_sha256": policy_hash, "manifests": {}}
    for reviewer, cfg in REVIEWERS.items():
        outputs["manifests"][reviewer] = write_once(cfg["manifest"], manifest(reviewer))
    print(json.dumps(outputs, indent=2))


def request(key: str, model: str, system: str, user: str) -> tuple[dict[str, Any], bytes]:
    payload = {
        "model": model,
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")), raw


def normalize_case(case: dict[str, Any], response_obj: dict[str, Any], reviewer: str) -> list[dict[str, Any]]:
    if not isinstance(response_obj, dict) or set(response_obj) != {"claims"} or not isinstance(response_obj["claims"], list):
        raise ValueError("response_schema_invalid")
    anchors = {row["anchor_id"]: row for row in case["source_anchors"]}
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    spans_by_anchor: dict[str, list[tuple[int, int]]] = {anchor_id: [] for anchor_id in anchors}
    for index, claim in enumerate(response_obj["claims"], start=1):
        if not isinstance(claim, dict) or set(claim) != CLAIM_KEYS:
            raise ValueError(f"claim_fields_invalid:{index}")
        anchor_id = claim["anchor_id"]
        if anchor_id not in anchors:
            raise ValueError(f"unknown_anchor:{anchor_id}")
        anchor = anchors[anchor_id]
        source_field = anchor["source_field"]
        if source_field not in CLAIM_ROLE_BY_SOURCE_FIELD:
            raise ValueError(f"source_field_role_unmapped:{source_field}")
        excerpt = claim["source_excerpt"]
        source = anchor["source_text"]
        if not isinstance(excerpt, str) or not excerpt.strip():
            raise ValueError(f"source_excerpt_empty:{anchor_id}:{index}")
        starts: list[int] = []
        cursor = 0
        while True:
            found = source.find(excerpt, cursor)
            if found < 0:
                break
            starts.append(found)
            cursor = found + 1
        if not starts:
            raise ValueError(f"source_excerpt_not_found:{anchor_id}:{index}")
        occurrence_index = claim["occurrence_index"]
        if not isinstance(occurrence_index, int) or isinstance(occurrence_index, bool) or occurrence_index < 0 or occurrence_index >= len(starts):
            raise ValueError(f"source_excerpt_occurrence_out_of_range:{anchor_id}:{index}:{occurrence_index}:{len(starts)}")
        start = starts[occurrence_index]
        end = start + len(excerpt)
        if any(max(start, prior_start) < min(end, prior_end) for prior_start, prior_end in spans_by_anchor[anchor_id]):
            raise ValueError(f"overlapping_claim_spans:{anchor_id}:{index}")
        spans_by_anchor[anchor_id].append((start, end))
        seen.add(anchor_id)
        if claim["claim_type"] not in CLAIM_TYPES:
            raise ValueError(f"claim_type_invalid:{anchor_id}:{index}")
        if not isinstance(claim["material"], bool) or claim["claim_origin"] not in ORIGINS or claim["annotation_confidence"] not in CONFIDENCE:
            raise ValueError(f"claim_metadata_invalid:{anchor_id}:{index}")
        if not isinstance(claim["boundary_rationale"], str) or not claim["boundary_rationale"].strip():
            raise ValueError(f"boundary_rationale_required:{anchor_id}:{index}")
        normalized.append({
            "reviewer_claim_id": f"reviewer-{reviewer}-{case['case_id']}-claim-{index:03d}",
            "case_id": case["case_id"],
            "response_sha256": case["response_sha256"],
            "anchor_id": anchor_id,
            "source_field": source_field,
            "source_index": anchor["source_index"],
            "source_text_sha256": anchor["source_text_sha256"],
            "source_span": {"start": start, "end": end},
            "source_occurrence_index": occurrence_index,
            "claim_text": excerpt,
            "claim_type": claim["claim_type"],
            "claim_role": CLAIM_ROLE_BY_SOURCE_FIELD[source_field],
            "anchor_group": f"{case['case_id']}::{source_field}",
            "material": claim["material"],
            "claim_origin": claim["claim_origin"],
            "boundary_rationale": claim["boundary_rationale"],
            "annotation_confidence": claim["annotation_confidence"],
        })
    missing = sorted(set(anchors) - seen)
    if missing:
        raise ValueError("anchors_without_claims:" + ",".join(missing))
    return normalized


def fixture_case(source_texts: list[tuple[str, str]]) -> dict[str, Any]:
    anchors = []
    for index, (source_field, source_text) in enumerate(source_texts):
        anchors.append({
            "anchor_id": f"fixture-{source_field}-{index:02d}",
            "source_field": source_field,
            "source_index": index,
            "source_text": source_text,
            "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        })
    return {"case_id": "fixture_case", "response_sha256": "0" * 64, "source_anchors": anchors}


def fixture_claim(anchor_id: str, excerpt: str) -> dict[str, Any]:
    return {
        "anchor_id": anchor_id,
        "source_excerpt": excerpt,
        "occurrence_index": 0,
        "claim_type": "proposition",
        "material": True,
        "claim_origin": "explicit",
        "boundary_rationale": "fixture",
        "annotation_confidence": "high",
    }


def run_contract_fixtures() -> dict[str, Any]:
    fixtures: list[dict[str, Any]] = []

    one = fixture_case([("proposition", "One atomic proposition.")])
    aid = one["source_anchors"][0]["anchor_id"]
    normalized = normalize_case(one, {"claims": [fixture_claim(aid, "One atomic proposition.")]}, "fixture")
    fixtures.append({"fixture_id": "one_proposition_one_anchor_claim", "expected": "pass", "actual": "pass", "claim_count": len(normalized)})

    multiple = fixture_case([("proposition", "Alpha holds. Beta holds.")])
    aid = multiple["source_anchors"][0]["anchor_id"]
    normalized = normalize_case(multiple, {"claims": [fixture_claim(aid, "Alpha holds."), fixture_claim(aid, "Beta holds.")]}, "fixture")
    if {row["claim_role"] for row in normalized} != {"anchor"} or len({row["anchor_group"] for row in normalized}) != 1:
        raise AssertionError("multiple_anchor_claim_protocol_normalization_failed")
    fixtures.append({"fixture_id": "one_proposition_multiple_anchor_claims", "expected": "pass", "actual": "pass", "claim_count": len(normalized)})

    repeated = fixture_case([("proposition", "Alpha holds. Alpha holds.")])
    aid = repeated["source_anchors"][0]["anchor_id"]
    first = fixture_claim(aid, "Alpha holds.")
    second = fixture_claim(aid, "Alpha holds.")
    second["occurrence_index"] = 1
    normalized = normalize_case(repeated, {"claims": [first, second]}, "fixture")
    if [row["source_span"]["start"] for row in normalized] != [0, 13]:
        raise AssertionError("repeated_excerpt_occurrence_resolution_failed")
    fixtures.append({"fixture_id": "repeated_excerpt_occurrence_disambiguation", "expected": "pass", "actual": "pass", "starts": [row["source_span"]["start"] for row in normalized]})

    crossing = fixture_case([("proposition", "Alpha holds."), ("prediction_statement", "Beta follows.")])
    aid = crossing["source_anchors"][0]["anchor_id"]
    try:
        normalize_case(crossing, {"claims": [fixture_claim(aid, "Alpha holds. Beta follows.")]}, "fixture")
    except ValueError as error:
        crossing_error = str(error)
    else:
        raise AssertionError("cross_anchor_claim_was_accepted")
    fixtures.append({"fixture_id": "claim_crossing_anchors", "expected": "reject", "actual": "reject", "error_code": crossing_error})

    overlap = fixture_case([("proposition", "Alpha and Beta hold.")])
    aid = overlap["source_anchors"][0]["anchor_id"]
    try:
        normalize_case(overlap, {"claims": [fixture_claim(aid, "Alpha and Beta"), fixture_claim(aid, "Beta hold.")]}, "fixture")
    except ValueError as error:
        overlap_error = str(error)
    else:
        raise AssertionError("overlapping_claims_were_accepted")
    fixtures.append({"fixture_id": "overlapping_claims_within_anchor", "expected": "reject", "actual": "reject", "error_code": overlap_error})

    out_of_range = fixture_case([("proposition", "Alpha holds. Alpha holds.")])
    aid = out_of_range["source_anchors"][0]["anchor_id"]
    bad = fixture_claim(aid, "Alpha holds.")
    bad["occurrence_index"] = 2
    try:
        normalize_case(out_of_range, {"claims": [bad]}, "fixture")
    except ValueError as error:
        range_error = str(error)
    else:
        raise AssertionError("out_of_range_occurrence_was_accepted")
    fixtures.append({"fixture_id": "occurrence_index_out_of_range", "expected": "reject", "actual": "reject", "error_code": range_error})

    report = {
        "schema_version": 3,
        "report_id": "phase7.3.3-d1-a-boundary-reviewer-contract-fixtures-v3",
        "protocol_sha256": sha(PROTOCOL),
        "prompt_sha256": sha(PROMPT),
        "adapter_sha256": sha(Path(__file__)),
        "fixture_count": len(fixtures),
        "passed_fixture_count": len(fixtures),
        "all_fixtures_passed": True,
        "fixtures": fixtures,
        "provider_called": False,
        "held_out_accessed": False,
    }
    write_once(FIXTURE_REPORT, report)
    return report

def canonical_model_family(requested: str, reported: str) -> str:
    if reported == requested or reported.startswith(requested + "-"):
        return requested
    raise ValueError(f"provider_reported_model_outside_requested_family:{requested}:{reported}")


def case_checkpoint(reviewer: str, case_id: str) -> Path:
    return REPORTS / "phase7_3_3_d_boundary_reviewer_cases_v3" / reviewer / f"{case_id}.json"


def execute(reviewer: str) -> int:
    cfg=REVIEWERS[reviewer]
    if not POLICY.exists() or not cfg["manifest"].exists():
        raise ValueError("run_prepare_before_execution")
    expected=manifest(reviewer)
    if load(cfg["manifest"]) != expected:
        raise ValueError("execution_manifest_verification_failed")
    manifest_hash=sha(cfg["manifest"])
    key=os.environ.get(CREDENTIAL_ENV, "").strip()
    if not key:
        print(f"BLOCKED: {CREDENTIAL_ENV} is not present")
        return 2
    packet=load(PACKET); system,user_template=split_prompt()
    all_claims=[]; case_results=[]; provider_reported_models=set(); canonical_models=set()
    for case in packet["cases"]:
        checkpoint=case_checkpoint(reviewer,case["case_id"])
        if checkpoint.exists():
            saved=load(checkpoint)
            if saved.get("manifest_sha256") != manifest_hash or saved.get("case_id") != case["case_id"]:
                raise ValueError(f"checkpoint_lineage_invalid:{case['case_id']}")
            all_claims.extend(saved["claims"]); case_results.append(saved["case_result"]); provider_reported_models.add(saved["provider_reported_model"]); canonical_models.add(saved["canonical_model_family"])
            continue
        entries=read_entries(ATTEMPT_LOG)
        returned=[e for e in entries if e.get("manifest_sha256")==manifest_hash and e.get("case_id")==case["case_id"] and e.get("response_received") is True]
        if returned:
            raise ValueError(f"authoritative_response_exists_without_checkpoint:{case['case_id']}")
        append_event({"event_type":"boundary_case_attempt_started","manifest_sha256":manifest_hash,"reviewer":reviewer,"case_id":case["case_id"],"response_received":False},ATTEMPT_LOG)
        provider_bytes = None
        content_bytes = None
        provider_envelope_sha256 = None
        provider_content_sha256 = None
        try:
            visible={"case_id":case["case_id"],"response_sha256":case["response_sha256"],"evidence_input":case["evidence_input"],"source_anchors":case["source_anchors"]}
            user=user_template.replace("{{CASE_JSON}}",json.dumps(visible,ensure_ascii=False,indent=2))
            envelope,provider_bytes=request(key,cfg["model"],system,user)
            provider_envelope_sha256 = hashlib.sha256(provider_bytes).hexdigest()
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("provider_content_not_string")
            content_bytes = content.encode("utf-8")
            provider_content_sha256 = hashlib.sha256(content_bytes).hexdigest()
            append_event({"event_type":"boundary_case_provider_content_received","manifest_sha256":manifest_hash,"reviewer":reviewer,"case_id":case["case_id"],"response_received":True,"authoritative_result":True,"provider_envelope_sha256":provider_envelope_sha256,"provider_content_sha256":provider_content_sha256},ATTEMPT_LOG)
            parsed=json.loads(content)
            claims=normalize_case(case,parsed,reviewer)
            provider_reported_model = envelope.get("model") or "unknown"
            canonical_model = canonical_model_family(cfg["model"], provider_reported_model)
            result={
                "schema_version":3,"reviewer":reviewer,"case_id":case["case_id"],
                "manifest_sha256":manifest_hash,"provider_reported_model":provider_reported_model,
                "canonical_model_family":canonical_model,
                "provider_envelope_sha256":provider_envelope_sha256,
                "provider_content_sha256":provider_content_sha256,
                "claims":claims,
                "case_result":{"case_id":case["case_id"],"status":"completed","claim_count":len(claims)},
                "raw_provider_response_stored":False,"held_out_accessed":False,
            }
            write_once(checkpoint,result)
            append_event({"event_type":"boundary_case_authoritative_success","manifest_sha256":manifest_hash,"reviewer":reviewer,"case_id":case["case_id"],"response_received":True,"authoritative_result":True,"provider_content_sha256":result["provider_content_sha256"],"normalized_output_sha256":canonical_sha(claims),"claim_count":len(claims),"provider_reported_model":provider_reported_model,"canonical_model_family":canonical_model},ATTEMPT_LOG)
            all_claims.extend(claims); case_results.append(result["case_result"]); provider_reported_models.add(provider_reported_model); canonical_models.add(canonical_model)
            print(f"Reviewer {reviewer.upper()} {case['case_id']}: {len(claims)} Claims",flush=True)
        except urllib.error.HTTPError as error:
            append_event({"event_type":"boundary_case_transport_failure","manifest_sha256":manifest_hash,"reviewer":reviewer,"case_id":case["case_id"],"status":f"http_{error.code}","response_received":False,"authoritative_result":False},ATTEMPT_LOG)
            print(f"TRANSPORT FAILURE reviewer {reviewer} {case['case_id']}: HTTP {error.code}")
            return 3
        except Exception as error:
            response_received=provider_bytes is not None
            event={"event_type":"boundary_case_experimental_failure" if response_received else "boundary_case_adapter_failure","manifest_sha256":manifest_hash,"reviewer":reviewer,"case_id":case["case_id"],"status":type(error).__name__,"error_code":str(error)[:240],"response_received":response_received,"authoritative_result":response_received}
            if provider_envelope_sha256 is not None: event["provider_envelope_sha256"] = provider_envelope_sha256
            if provider_content_sha256 is not None: event["provider_content_sha256"] = provider_content_sha256
            append_event(event,ATTEMPT_LOG)
            negative=REPORTS / f"phase7_3_3_d_boundary_reviewer_{reviewer}_negative_result_v3.json"
            write_once(negative,{"schema_version":3,"reviewer":reviewer,"manifest_sha256":manifest_hash,"case_id":case["case_id"],"status":"authoritative_negative_result" if response_received else "adapter_failure","failure_type":type(error).__name__,"failure_code":str(error)[:240],"response_received":response_received,"provider_envelope_sha256":provider_envelope_sha256,"provider_content_sha256":provider_content_sha256,"raw_provider_response_stored":False,"held_out_accessed":False})
            print(f"EXPERIMENTAL FAILURE reviewer {reviewer} {case['case_id']}: {type(error).__name__}: {error}")
            return 4
    if canonical_models != {cfg["model"]}:
        raise ValueError(f"canonical_model_family_drift:{sorted(canonical_models)}")
    canonical_model = next(iter(canonical_models))
    submission_path=REPORTS / f"phase7_3_3_d_boundary_reviewer_{reviewer}_submission_v3.json"
    result_path=REPORTS / f"phase7_3_3_d_boundary_reviewer_{reviewer}_execution_result_v3.json"
    submission={
        "schema_version":3,"submission_id":f"phase7.3.3-d1-a-boundary-reviewer-{reviewer}-submission-v3",
        "reviewer_id":f"ai_boundary_reviewer_{reviewer}_{cfg['model']}","reviewer_role":"independent_boundary_reviewer",
        "protocol_id":"phase7.3.3-d1-a-boundary-reference-protocol-v3","boundary_packet_sha256":sha(PACKET),
        "completed":True,"blind_to_other_reviewer":True,"blind_to_support_labels":True,"blind_to_candidate_gold_or_silver":True,
        "held_out_accessed":False,"claims":all_claims,
        "completion_attestation":{"support_labels_not_used":True,"candidate_labels_not_used":True,"other_reviewer_not_seen":True,"all_spans_verified_against_source":True},
    }
    write_once(submission_path,submission)
    write_once(result_path,{"schema_version":3,"execution_id":f"phase7.3.3-d1-a-boundary-reviewer-{reviewer}-execution-v3","status":"completed","manifest_sha256":manifest_hash,"submission_sha256":sha(submission_path),"model_requested":cfg["model"],"canonical_model_family":canonical_model,"provider_reported_models":sorted(provider_reported_models),"completed_case_count":len(case_results),"claim_count":len(all_claims),"case_results":case_results,"raw_provider_responses_stored":False,"held_out_accessed":False})
    print(json.dumps({"reviewer":reviewer,"status":"completed","canonical_model_family":canonical_model,"provider_reported_models":sorted(provider_reported_models),"cases":len(case_results),"claims":len(all_claims),"submission_sha256":sha(submission_path)},indent=2))
    return 0


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--fixtures",action="store_true"); parser.add_argument("--prepare",action="store_true"); parser.add_argument("--reviewer",choices=["d"])
    args=parser.parse_args()
    if args.fixtures:
        print(json.dumps(run_contract_fixtures(), indent=2)); return 0
    if args.prepare:
        prepare(); return 0
    if args.reviewer:
        return execute(args.reviewer)
    parser.error("use --fixtures, --prepare, or --reviewer")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
