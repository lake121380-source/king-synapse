#!/usr/bin/env python3
"""Prepare and execute blind operation-based Boundary Reviewers for the multi-claim successor pilot."""
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
from typing import Any

from phase7_execution_attempt_log import append_event, read_entries

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
STATE_IN = PATTERN / "phase7_3_3_d_support_stage_state_v28.json"
READY_IN = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v39.json"
DATASET = PATTERN / "phase7_3_3_d_multi_claim_successor_selected_dataset_v1.json"
PRESCREEN_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_manifest_v1.json"
PRESCREEN_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_receipt_v1.json"
PRESCREEN_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_report_v1.json"
FRAME_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_frame_construction_protocol_v1.json"
PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_review_protocol_v1.json"
SCHEMA = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_review_output_schema_v1.json"
POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_execution_policy_v1.json"
PROMPT = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_prompt_v1.md"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_boundary_blind_worklist_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_contract_fixtures_v1.json"
PREP_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_review_prepare_manifest_v1.json"
PREP_OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_review_prepare_outcome_v1.json"
PREP_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_review_prepare_receipt_v1.json"
STATE_PREP = PATTERN / "phase7_3_3_d_support_stage_state_v29.json"
READY_PREP = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v40.json"
ATTEMPT_LOG = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_attempts_v1.jsonl"
BASE_URL = "https://api.gpt.ge/v1"
CREDENTIAL_ENV = "PHASE7_ATOMIC_JUDGE_API_KEY"
CURRENT_STAGE = "construct_multi_claim_successor_independent_boundary_review_a_v1"
EXECUTE_A_STAGE = "execute_multi_claim_successor_independent_boundary_review_a_v1"
EXECUTE_B_STAGE = "execute_multi_claim_successor_independent_boundary_review_b_v1"
AGREEMENT_STAGE = "construct_multi_claim_successor_boundary_agreement_v1"
REVIEWERS = {"a": {"model": "gpt-4.1"}, "b": {"model": "gemini-2.5-pro"}}
CLAIM_KEYS = {"boundary_operation", "boundary_rationale", "annotation_confidence"}
CONFIDENCE = {"low", "medium", "high"}
OP_KEYS = {
    "reuse_unit": {"kind", "unit_id"},
    "merge_units": {"kind", "unit_ids"},
    "slice_unit": {"kind", "unit_id", "relative_start", "relative_end"},
    "new_span": {"kind", "start", "end"},
}
EXPECTED = {
    STATE_IN: "0c1f74054e61d8f2cd51a44262d570abf65f2e332c35749a7d1b4c6a2204b9ce",
    READY_IN: "4ee818781e2f230f12168d646d0c620740bb45dd478a835a2bb73d701e5e57cb",
    DATASET: "858c60201f25a97e9787e96ef0554c05b3bf36b80c76f86406b520ecb203d3ca",
    PRESCREEN_MANIFEST: "08fd35df417262cd5e85092410fd7aac4d7072999811e7c4a93b3e4890319058",
    PRESCREEN_RECEIPT: "43c42b899217c02c0c56fe0c1efbf1783e8aeb42c7989021f32bf28e616916a0",
    PRESCREEN_REPORT: "ebe816dd5c2a4ce2ff5b8c64e37bc32521e0e04ef0fba9ce813afedc7065a1aa",
    FRAME_PROTOCOL: "0542448908e2818b58b0fe260371917a44c6f87735507583aabfd0dae901f9fc",
}


def hb(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def sha(path: Path) -> str: return hb(path.read_bytes())
def csha(value: Any) -> str: return hb(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8-sig"))
def rel(path: Path) -> str: return str(path.relative_to(ROOT)).replace("\\", "/")
def jbytes(value: Any) -> bytes: return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_bytes_once(path: Path, payload: bytes) -> str:
    if path.exists():
        if path.read_bytes() != payload: raise ValueError(f"immutable_artifact_exists_with_different_content:{rel(path)}")
        return hb(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload); temporary = Path(handle.name)
    temporary.replace(path); return hb(payload)


def write_json_once(path: Path, value: Any) -> str: return write_bytes_once(path, jbytes(value))


def unitize(text: str) -> list[dict[str, Any]]:
    units=[]; cursor=0; values=text.split("\n")
    for index,value in enumerate(values):
        start=cursor; end=start+len(value)
        units.append({"unit_id":f"unit-{index+1:03d}","unit_index":index,"start":start,"end":end,"text":value,"text_sha256":hb(value.encode("utf-8"))})
        cursor=end+(1 if index < len(values)-1 else 0)
    return units


def make_worklist() -> dict[str, Any]:
    cases=[]
    for source in load(DATASET)["cases"]:
        text=source["candidate_text"]; units=unitize(text)
        if any(text[u["start"]:u["end"]] != u["text"] for u in units): raise ValueError(f"unit_offset_replay_failed:{source['case_id']}")
        cases.append({"successor_index":source["successor_index"],"case_id":source["case_id"],"candidate_text":text,"candidate_sha256":source["candidate_sha256"],"offset_unit":"zero_based_unicode_code_point_end_exclusive","source_units":units,"valid_unit_ids":[u["unit_id"] for u in units]})
    return {"schema_version":1,"worklist_id":"phase7.3.3-d-multi-claim-successor-boundary-blind-worklist-v1","status":"frozen_boundary_only_blind_worklist","case_count":len(cases),"cases":cases,"evidence_present":False,"source_component_roles_present":False,"support_labels_present":False,"old_gold_present":False,"other_reviewer_output_present":False,"arm_outputs_present":False,"confirmatory_content_present":False}


def prompt_text() -> str:
    return """# Phase 7.3.3-D Multi-claim Successor Boundary Reviewer Prompt v1

## System message

You are an independent Boundary Reviewer constructing Atomic Claim spans for a scientific evaluation dataset.

Your only task is structural segmentation. Do not judge support or correctness. Evidence is intentionally absent. Do not output Claim Type, Claim Role, support labels, materiality, citations, centrality, anchor groups, or source excerpts.

The Candidate may contain compact snake_case assertion identifiers. Do not reject an assertion solely because it is symbolic or uses underscores. Judge whether the encoded content is independently truth-evaluable.

For each Candidate:
1. Identify every independently truth-evaluable assertion in the exact Candidate text.
2. Split content when parts could receive different truth values; do not merge merely because units are related.
3. Use the supplied operation representation. The adapter, not you, reconstructs exact text.
4. Prefer reuse_unit for a whole supplied unit.
5. Use merge_units only for consecutive units that together express one assertion and are not independently truth-evaluable.
6. Use slice_unit for a proper non-empty subspan of one unit. Relative offsets are Unicode code points; end is exclusive.
7. Use new_span only when other operations cannot express the boundary. Absolute offsets are over candidate_text; end is exclusive.
8. Do not create overlapping Claims. Every Candidate must contain at least one Claim.
9. Return strict JSON only and exactly the documented fields.

Return:
{
  "claims": [
    {
      "boundary_operation": {"kind": "reuse_unit", "unit_id": "unit-001"},
      "boundary_rationale": "brief segmentation-only rationale",
      "annotation_confidence": "low | medium | high"
    }
  ]
}

Allowed boundary_operation shapes:
- {"kind":"reuse_unit","unit_id":"unit-001"}
- {"kind":"merge_units","unit_ids":["unit-001","unit-002"]}
- {"kind":"slice_unit","unit_id":"unit-001","relative_start":0,"relative_end":5}
- {"kind":"new_span","start":0,"end":5}

Do not include Markdown, source_excerpt, claim_text, source_span, occurrence_index, support_label, claim_type, claim_role, material, material_error, or cited_evidence_ids.

## User message template

Perform an independent Boundary-only review of this frozen Candidate. Return operation-based strict JSON only.

{{CASE_JSON}}
"""


def protocol_document() -> dict[str, Any]:
    return {"schema_version":1,"protocol_id":"phase7.3.3-d-multi-claim-successor-boundary-review-protocol-v1","status":"frozen_before_any_boundary_provider_call","object_of_study":"atomic_claim_boundary_segmentation_under_operation_based_span_representation","boundary_semantics":{"independently_truth_evaluable_assertions":True,"different_possible_truth_values_require_split":True,"relatedness_alone_does_not_authorize_merge":True,"symbolic_snake_case_identifiers_are_not_automatically_non_claim":True,"at_least_one_claim_per_candidate":True,"no_overlapping_final_spans":True},"representation":{"route":"operation_based_deterministic_reconstruction","offset_unit":"zero_based_unicode_code_point_end_exclusive","operations":sorted(OP_KEYS),"model_returns_exact_excerpt":False,"adapter_derives_exact_excerpt":True,"adapter_derives_occurrence_index":True,"offset_clamping_allowed":False,"excerpt_repair_allowed":False},"review_separation":{"boundary_only":True,"claim_type_in_same_review":False,"structural_metadata_in_same_review":False,"support_in_same_review":False},"visibility":{"candidate_text":True,"source_units":True,"evidence":False,"source_component_roles":False,"support_labels":False,"old_gold":False,"other_reviewer_output":False,"arm_outputs":False,"confirmatory_content":False},"independence":{"reviewers":["a","b"],"same_prompt":True,"same_worklist":True,"different_requested_models":True,"both_manifests_frozen_before_reviewer_a_execution":True},"next_after_two_completed_submissions":AGREEMENT_STAGE}


def schema_document() -> dict[str, Any]:
    specs={"reuse_unit":{"unit_id":{"type":"string","minLength":1}},"merge_units":{"unit_ids":{"type":"array","minItems":2,"uniqueItems":True,"items":{"type":"string","minLength":1}}},"slice_unit":{"unit_id":{"type":"string","minLength":1},"relative_start":{"type":"integer","minimum":0},"relative_end":{"type":"integer","minimum":1}},"new_span":{"start":{"type":"integer","minimum":0},"end":{"type":"integer","minimum":1}}}
    variants=[]
    for kind,props in specs.items(): variants.append({"type":"object","required":["kind",*props.keys()],"properties":{"kind":{"const":kind},**props},"additionalProperties":False})
    return {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"phase7.3.3-d-multi-claim-successor-boundary-review-output-schema-v1","type":"object","required":["claims"],"properties":{"claims":{"type":"array","minItems":1,"items":{"type":"object","required":sorted(CLAIM_KEYS),"properties":{"boundary_operation":{"oneOf":variants},"boundary_rationale":{"type":"string","minLength":1},"annotation_confidence":{"enum":sorted(CONFIDENCE)}},"additionalProperties":False}}},"additionalProperties":False}


def policy_document() -> dict[str, Any]:
    return {"schema_version":1,"policy_id":"phase7.3.3-d-multi-claim-successor-boundary-reviewer-execution-policy-v1","authoritative_result_policy":{"first_returned_provider_content_per_case_authoritative":True,"provider_content_sha256_before_parse":True,"invalid_json_schema_or_semantics_is_negative_result":True,"automatic_repair_authorized":False,"semantic_retry_authorized":False,"selective_retry_authorized":False,"transport_failure_before_content_may_resume":True},"execution_controls":{"case_isolation":True,"temperature":0,"top_p":1,"max_tokens":2500,"response_format":{"type":"json_object"}},"data_handling":{"credential_env_name":CREDENTIAL_ENV,"api_key_recorded":False,"raw_provider_text_recorded":False,"provider_envelope_sha256_recorded":True,"provider_content_sha256_recorded":True},"prohibitions":["no_support_judgment","no_claim_type_judgment","no_metadata_judgment","no_prompt_modification_after_freeze","no_parser_modification_after_freeze","no_same_version_semantic_retry","no_confirmatory_open","no_runtime_integration"]}


def exact_occurrence_index(source: str, excerpt: str, start: int) -> int:
    positions=[]; cursor=0
    while True:
        found=source.find(excerpt,cursor)
        if found<0: break
        positions.append(found); cursor=found+1
    if start not in positions: raise ValueError("reconstructed_excerpt_occurrence_not_found")
    return positions.index(start)


def resolve_operation(case: dict[str, Any], operation: Any, claim_index: int) -> tuple[int,int,list[str],str]:
    if not isinstance(operation,dict): raise ValueError(f"boundary_operation_not_object:{claim_index}")
    kind=operation.get("kind")
    if kind not in OP_KEYS: raise ValueError(f"unknown_boundary_operation:{claim_index}:{kind}")
    if set(operation)!=OP_KEYS[kind]: raise ValueError(f"boundary_operation_fields_mismatch:{claim_index}:{kind}")
    units={u["unit_id"]:u for u in case["source_units"]}
    if kind=="reuse_unit":
        uid=operation["unit_id"]
        if uid not in units: raise ValueError(f"unknown_unit_id:{claim_index}:{uid}")
        u=units[uid]; return u["start"],u["end"],[uid],kind
    if kind=="merge_units":
        ids=operation["unit_ids"]
        if not isinstance(ids,list) or len(ids)<2 or len(set(ids))!=len(ids): raise ValueError(f"merge_units_invalid_ids:{claim_index}")
        if any(uid not in units for uid in ids): raise ValueError(f"merge_units_unknown_id:{claim_index}")
        indices=[units[uid]["unit_index"] for uid in ids]
        if indices!=sorted(indices) or indices!=list(range(indices[0],indices[-1]+1)): raise ValueError(f"merge_units_not_consecutive_source_order:{claim_index}")
        return units[ids[0]]["start"],units[ids[-1]]["end"],ids,kind
    if kind=="slice_unit":
        uid=operation["unit_id"]
        if uid not in units: raise ValueError(f"unknown_unit_id:{claim_index}:{uid}")
        rs,re=operation["relative_start"],operation["relative_end"]
        if not isinstance(rs,int) or isinstance(rs,bool) or not isinstance(re,int) or isinstance(re,bool): raise ValueError(f"slice_offsets_not_integers:{claim_index}")
        u=units[uid]; length=u["end"]-u["start"]
        if not (0<=rs<re<=length) or (rs==0 and re==length): raise ValueError(f"slice_offsets_invalid_or_not_proper:{claim_index}")
        return u["start"]+rs,u["start"]+re,[uid],kind
    start,end=operation["start"],operation["end"]
    if not isinstance(start,int) or isinstance(start,bool) or not isinstance(end,int) or isinstance(end,bool): raise ValueError(f"new_span_offsets_not_integers:{claim_index}")
    if not (0<=start<end<=len(case["candidate_text"])): raise ValueError(f"new_span_out_of_range:{claim_index}")
    ids=[u["unit_id"] for u in case["source_units"] if u["start"]<end and start<u["end"]]
    return start,end,ids,kind


def normalize_case(case: dict[str, Any], payload: Any, reviewer: str) -> list[dict[str, Any]]:
    if not isinstance(payload,dict) or set(payload)!={"claims"} or not isinstance(payload["claims"],list) or not payload["claims"]: raise ValueError("root_schema_invalid_or_empty_claims")
    text=case["candidate_text"]; rows=[]
    for i,raw in enumerate(payload["claims"]):
        if not isinstance(raw,dict) or set(raw)!=CLAIM_KEYS: raise ValueError(f"claim_fields_mismatch:{i}")
        if not isinstance(raw["boundary_rationale"],str) or not raw["boundary_rationale"].strip(): raise ValueError(f"boundary_rationale_invalid:{i}")
        if raw["annotation_confidence"] not in CONFIDENCE: raise ValueError(f"annotation_confidence_invalid:{i}")
        start,end,ids,kind=resolve_operation(case,raw["boundary_operation"],i); excerpt=text[start:end]
        if not excerpt: raise ValueError(f"empty_reconstructed_excerpt:{i}")
        rows.append({"case_id":case["case_id"],"source_span":{"start":start,"end":end},"source_excerpt":excerpt,"source_occurrence_index":exact_occurrence_index(text,excerpt,start),"source_unit_ids":ids,"boundary_operation_kind":kind,"boundary_rationale":raw["boundary_rationale"].strip(),"annotation_confidence":raw["annotation_confidence"],"reviewer":reviewer})
    rows.sort(key=lambda x:(x["source_span"]["start"],x["source_span"]["end"],x["boundary_operation_kind"])); previous=-1; seen=set()
    for i,row in enumerate(rows):
        span=(row["source_span"]["start"],row["source_span"]["end"])
        if span in seen: raise ValueError(f"duplicate_final_span:{i}")
        if span[0]<previous: raise ValueError(f"overlapping_final_spans:{i}")
        seen.add(span); previous=span[1]; row["claim_id"]=f"{case['case_id']}-{reviewer}-claim-{i+1:03d}"
    return rows


def fixture_case(text: str) -> dict[str, Any]:
    units=unitize(text); return {"case_id":"fixture-case","candidate_text":text,"candidate_sha256":hb(text.encode()),"source_units":units,"valid_unit_ids":[u["unit_id"] for u in units]}
def fixture_claim(op: dict[str, Any]) -> dict[str, Any]: return {"boundary_operation":op,"boundary_rationale":"fixture","annotation_confidence":"high"}


def run_fixtures() -> dict[str, Any]:
    fs=[]; case=fixture_case("alpha\nbeta\ngamma")
    outputs=[("reuse_unit_reconstructs_exact_text",{"claims":[fixture_claim({"kind":"reuse_unit","unit_id":"unit-001"})]},"alpha"),("merge_consecutive_units_includes_exact_joiner",{"claims":[fixture_claim({"kind":"merge_units","unit_ids":["unit-001","unit-002"]})]},"alpha\nbeta"),("slice_unit_reconstructs_proper_subspan",{"claims":[fixture_claim({"kind":"slice_unit","unit_id":"unit-001","relative_start":1,"relative_end":4})]},"lph"),("new_span_reconstructs_absolute_subspan",{"claims":[fixture_claim({"kind":"new_span","start":6,"end":10})]},"beta")]
    for fid,payload,expected in outputs:
        actual=normalize_case(case,payload,"fixture")[0]["source_excerpt"]; fs.append({"fixture_id":fid,"status":"PASS" if actual==expected else "FAIL"})
    rejects=[("unknown_unit_rejected",{"claims":[fixture_claim({"kind":"reuse_unit","unit_id":"unit-999"})]},"unknown_unit_id"),("nonconsecutive_merge_rejected",{"claims":[fixture_claim({"kind":"merge_units","unit_ids":["unit-001","unit-003"]})]},"merge_units_not_consecutive"),("full_unit_slice_rejected",{"claims":[fixture_claim({"kind":"slice_unit","unit_id":"unit-001","relative_start":0,"relative_end":5})]},"slice_offsets_invalid"),("overlapping_spans_rejected",{"claims":[fixture_claim({"kind":"reuse_unit","unit_id":"unit-001"}),fixture_claim({"kind":"new_span","start":2,"end":7})]},"overlapping_final_spans"),("empty_claim_list_rejected",{"claims":[]},"root_schema_invalid"),("support_field_rejected",{"claims":[{**fixture_claim({"kind":"reuse_unit","unit_id":"unit-001"}),"support_label":"supported"}]},"claim_fields_mismatch")]
    for fid,payload,expected in rejects:
        try: normalize_case(case,payload,"fixture")
        except ValueError as error: status="PASS" if expected in str(error) else "FAIL"; observed=str(error)
        else: status="FAIL"; observed="accepted"
        fs.append({"fixture_id":fid,"status":status,"observed":observed})
    valid_envelope=parse_provider_envelope(b'{"model":"gpt-4.1","choices":[]}')
    fs.append({"fixture_id":"valid_provider_envelope_decodes","status":"PASS" if valid_envelope.get("model")=="gpt-4.1" else "FAIL"})
    try: parse_provider_envelope(b'not-json')
    except ValueError as error: status="PASS" if str(error)=="provider_envelope_invalid_json" else "FAIL"; observed=str(error)
    else: status="FAIL"; observed="accepted"
    fs.append({"fixture_id":"invalid_provider_envelope_rejected_after_response_capture","status":status,"observed":observed})
    return {"schema_version":1,"report_id":"phase7.3.3-d-multi-claim-successor-boundary-reviewer-contract-fixtures-v1","status":"PASS" if all(x["status"]=="PASS" for x in fs) else "FAIL","passed":sum(x["status"]=="PASS" for x in fs),"total":len(fs),"fixtures":fs,"provider_called":False,"confirmatory_dataset_opened":False}


def reviewer_manifest(reviewer: str) -> Path: return REPORTS / f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{reviewer}_execution_manifest_v1.json"
def prepared_paths() -> list[Path]: return [PROTOCOL,SCHEMA,POLICY,PROMPT,WORKLIST,FIXTURES,PREP_MANIFEST,PREP_OUTCOME,STATE_PREP,READY_PREP,PREP_RECEIPT,reviewer_manifest("a"),reviewer_manifest("b")]


def manifest_document(reviewer: str, hashes: dict[str,str]) -> dict[str, Any]:
    return {"schema_version":1,"manifest_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-manifest-v1","status":"frozen_not_started","reviewer":reviewer,"provider":"api.gpt.ge","provider_base_url":BASE_URL,"model_requested":REVIEWERS[reviewer]["model"],"temperature":0,"top_p":1,"max_tokens":2500,"response_format":{"type":"json_object"},"credential_env_name":CREDENTIAL_ENV,"adapter_sha256":sha(Path(__file__)),"protocol_sha256":hashes[rel(PROTOCOL)],"schema_sha256":hashes[rel(SCHEMA)],"policy_sha256":hashes[rel(POLICY)],"prompt_sha256":hashes[rel(PROMPT)],"worklist_sha256":hashes[rel(WORKLIST)],"fixtures_sha256":hashes[rel(FIXTURES)],"case_count":40,"case_isolation":True,"first_provider_content_authoritative":True,"semantic_retry_authorized":False,"raw_provider_content_stored":False,"evidence_visible":False,"other_reviewer_output_visible":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False}


def preflight_prepare() -> dict[str, Any]:
    missing=[rel(p) for p in EXPECTED if not p.exists()]; mismatches={rel(p):{"expected":d,"actual":sha(p)} for p,d in EXPECTED.items() if p.exists() and sha(p)!=d}
    state=load(STATE_IN) if STATE_IN.exists() else {}; ready=load(READY_IN) if READY_IN.exists() else {}; dataset=load(DATASET) if DATASET.exists() else {}; report=load(PRESCREEN_REPORT) if PRESCREEN_REPORT.exists() else {}
    checks={"required_inputs_present":not missing,"input_hashes_match":not mismatches,"state_authorizes_prepare":state.get("next_authorized_stage")==CURRENT_STAGE,"readiness_authorizes_prepare":ready.get("next_authorized_stage")==CURRENT_STAGE,"prescreen_passed_40":report.get("status")=="PASS" and report.get("prescreen_pass_count")==40,"selected_count_40":dataset.get("case_count")==40 and len(dataset.get("cases",[]))==40,"boundary_blind_inputs":dataset.get("source_component_roles_present") is False and dataset.get("support_labels_present") is False and dataset.get("old_gold_present") is False,"provider_not_called":state.get("multi_claim_successor_provider_called") is False,"confirmatory_closed":state.get("confirmatory_dataset_opened") is False,"runtime_unauthorized":state.get("runtime_integration_authorized") is False,"outputs_absent":all(not p.exists() for p in prepared_paths())}
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"missing":missing,"mismatches":mismatches}


def build_prepare_outputs() -> dict[Path,bytes]:
    worklist=make_worklist(); fixtures=run_fixtures(); base={PROTOCOL:jbytes(protocol_document()),SCHEMA:jbytes(schema_document()),POLICY:jbytes(policy_document()),PROMPT:prompt_text().encode("utf-8"),WORKLIST:jbytes(worklist),FIXTURES:jbytes(fixtures)}; hashes={rel(p):hb(b) for p,b in base.items()}; manifests={reviewer_manifest(r):jbytes(manifest_document(r,hashes)) for r in REVIEWERS}; fixed={**base,**manifests}; fixed_hashes={rel(p):hb(b) for p,b in fixed.items()}
    prep={"schema_version":1,"manifest_id":"phase7.3.3-d-multi-claim-successor-boundary-review-prepare-manifest-v1","status":"frozen_before_any_boundary_provider_call","adapter":rel(Path(__file__)),"adapter_sha256":sha(Path(__file__)),"input_sha256":{rel(p):sha(p) for p in EXPECTED},"artifact_sha256":fixed_hashes,"reviewer_a_model":REVIEWERS["a"]["model"],"reviewer_b_model":REVIEWERS["b"]["model"],"both_execution_manifests_frozen_before_reviewer_a":True,"provider_called":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False}; prep_bytes=jbytes(prep); passed=fixtures["status"]=="PASS" and worklist["case_count"]==40
    outcome={"schema_version":1,"outcome_id":"phase7.3.3-d-multi-claim-successor-boundary-review-prepare-outcome-v1","status":"boundary_review_protocol_and_dual_manifests_frozen" if passed else "boundary_review_prepare_failed","case_count":worklist["case_count"],"fixtures_passed":fixtures["passed"],"fixtures_total":fixtures["total"],"provider_called":False,"boundary_submission_created":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False,"next_authorized_stage":EXECUTE_A_STAGE if passed else None}
    lineage={"multi_claim_successor_boundary_review_prepare_manifest_v1_sha256":hb(prep_bytes),**{Path(n).name.replace(".json","_sha256").replace(".md","_sha256"):d for n,d in fixed_hashes.items()}}
    state=copy.deepcopy(load(STATE_IN)); state.setdefault("artifact_lineage",{}).update(lineage); state.update({"schema_version":29,"state_id":"phase7.3.3-d-support-stage-state-v29","status":outcome["status"],"next_authorized_stage":outcome["next_authorized_stage"],"multi_claim_successor_boundary_review_protocol_frozen":passed,"multi_claim_successor_boundary_reviewer_a_manifest_frozen":passed,"multi_claim_successor_boundary_reviewer_b_manifest_frozen":passed,"multi_claim_successor_boundary_reviewer_a_completed":False,"multi_claim_successor_boundary_reviewer_b_completed":False,"multi_claim_successor_provider_called":False,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
    ready=copy.deepcopy(load(READY_IN)); ready.setdefault("artifact_lineage",{}).update(lineage); ready.update({"schema_version":40,"readiness_id":"phase7.3.3-d1-reference-construction-readiness-v40","status":outcome["status"],"next_authorized_stage":outcome["next_authorized_stage"],"successor_boundary_review_protocol_frozen":passed,"successor_boundary_reviewer_a_manifest_frozen":passed,"successor_boundary_reviewer_b_manifest_frozen":passed,"successor_boundary_reviewer_a_completed":False,"successor_boundary_reviewer_b_completed":False,"provider_called":False,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
    return {**fixed,PREP_MANIFEST:prep_bytes,PREP_OUTCOME:jbytes(outcome),STATE_PREP:jbytes(state),READY_PREP:jbytes(ready)}


def prepare() -> dict[str, Any]:
    if preflight_prepare()["status"]!="PASS": raise ValueError("prepare_preflight_failed")
    outputs=build_prepare_outputs(); hashes={rel(p):write_bytes_once(p,b) for p,b in outputs.items()}; outcome=load(PREP_OUTCOME); fixtures=load(FIXTURES)
    receipt={"schema_version":1,"receipt_id":"phase7.3.3-d-multi-claim-successor-boundary-review-prepare-receipt-v1","status":"PASS" if outcome["next_authorized_stage"]==EXECUTE_A_STAGE else "FAIL","artifact_sha256":hashes,"case_count":40,"fixtures_passed":fixtures["passed"],"fixtures_total":fixtures["total"],"both_execution_manifests_frozen_before_reviewer_a":True,"provider_called":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False,"next_authorized_stage":outcome["next_authorized_stage"]}; receipt_sha=write_json_once(PREP_RECEIPT,receipt)
    return {"status":receipt["status"],"case_count":40,"fixtures":f"{fixtures['passed']}/{fixtures['total']}","prepare_manifest_sha256":sha(PREP_MANIFEST),"reviewer_a_manifest_sha256":sha(reviewer_manifest("a")),"reviewer_b_manifest_sha256":sha(reviewer_manifest("b")),"receipt_sha256":receipt_sha,"state_sha256":sha(STATE_PREP),"readiness_sha256":sha(READY_PREP),"next_authorized_stage":outcome["next_authorized_stage"],"provider_called":False}


def verify_prepare() -> dict[str, Any]:
    expected=build_prepare_outputs(); checks={rel(p):p.exists() and p.read_bytes()==b for p,b in expected.items()}
    if PREP_RECEIPT.exists():
        receipt=load(PREP_RECEIPT)
        for name,digest in receipt.get("artifact_sha256",{}).items(): p=ROOT/name; checks[name+"#receipt_hash"]=p.exists() and sha(p)==digest
        checks[rel(PREP_RECEIPT)+"#status"]=receipt.get("status")=="PASS"
    else: checks[rel(PREP_RECEIPT)]=False
    state=load(STATE_PREP) if STATE_PREP.exists() else {}; work=load(WORKLIST) if WORKLIST.exists() else {}
    checks.update({"worklist_40":work.get("case_count")==40,"evidence_blind":work.get("evidence_present") is False,"support_blind":work.get("support_labels_present") is False,"both_manifests_exist":reviewer_manifest("a").exists() and reviewer_manifest("b").exists(),"next_gate":state.get("next_authorized_stage")==EXECUTE_A_STAGE,"provider_not_called":state.get("multi_claim_successor_provider_called") is False,"confirmatory_closed":state.get("confirmatory_dataset_opened") is False,"runtime_unauthorized":state.get("runtime_integration_authorized") is False})
    failed=[k for k,v in checks.items() if not v]; return {"status":"PASS" if not failed else "FAIL","checks":len(checks),"failed":failed,"next_authorized_stage":state.get("next_authorized_stage")}


def split_prompt() -> tuple[str,str]:
    text=PROMPT.read_text(encoding="utf-8-sig"); sm="## System message\n"; um="## User message template\n"
    if sm not in text or um not in text: raise ValueError("prompt_sections_missing")
    return text.split(sm,1)[1].split(um,1)[0].strip(),text.split(um,1)[1].strip()


def provider_request(key: str, model: str, system: str, user: str) -> bytes:
    payload={"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"temperature":0,"top_p":1,"max_tokens":2500,"response_format":{"type":"json_object"}}
    req=urllib.request.Request(BASE_URL+"/chat/completions",data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=300) as response: return response.read()


def parse_provider_envelope(raw: bytes) -> dict[str, Any]:
    try: envelope=json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as error: raise ValueError("provider_envelope_invalid_json") from error
    if not isinstance(envelope,dict): raise ValueError("provider_envelope_not_object")
    return envelope


def canonical_model_family(requested: str, reported: str) -> str:
    if reported==requested or reported.startswith(requested+"-"): return requested
    raise ValueError(f"provider_reported_model_outside_requested_family:{requested}:{reported}")
def checkpoint_path(r: str,c: str)->Path:return REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_reviewer_cases_v1"/r/f"{c}.json"
def submission_path(r: str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_submission_v1.json"
def result_path(r: str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_execution_result_v1.json"
def outcome_path(r: str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_execution_outcome_v1.json"
def receipt_path(r: str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_execution_receipt_v1.json"
def negative_path(r: str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_negative_result_v1.json"


def execution_state_paths(reviewer: str)->tuple[Path,Path,Path,Path,str]:
    if reviewer=="a": return STATE_PREP,READY_PREP,PATTERN/"phase7_3_3_d_support_stage_state_v30.json",REPORTS/"phase7_3_3_d1_reference_construction_readiness_v41.json",EXECUTE_A_STAGE
    return PATTERN/"phase7_3_3_d_support_stage_state_v30.json",REPORTS/"phase7_3_3_d1_reference_construction_readiness_v41.json",PATTERN/"phase7_3_3_d_support_stage_state_v31.json",REPORTS/"phase7_3_3_d1_reference_construction_readiness_v42.json",EXECUTE_B_STAGE


def authoritative_seen(msha: str,r: str,c: str)->bool:
    return any(e.get("manifest_sha256")==msha and e.get("reviewer")==r and e.get("case_id")==c and e.get("response_received") is True and e.get("authoritative_result") is True for e in read_entries(ATTEMPT_LOG))


def finalize_state(reviewer: str,status: str,next_stage: str|None,sub_sha: str|None,res_sha: str|None)->tuple[str,str]:
    state_in,ready_in,state_out,ready_out,_=execution_state_paths(reviewer); state=copy.deepcopy(load(state_in)); ready=copy.deepcopy(load(ready_in)); sv=30 if reviewer=="a" else 31; rv=41 if reviewer=="a" else 42; lineage={}
    if sub_sha: lineage[f"multi_claim_successor_boundary_reviewer_{reviewer}_submission_v1_sha256"]=sub_sha
    if res_sha: lineage[f"multi_claim_successor_boundary_reviewer_{reviewer}_execution_result_v1_sha256"]=res_sha
    state.setdefault("artifact_lineage",{}).update(lineage); ready.setdefault("artifact_lineage",{}).update(lineage)
    completed=status=="boundary_reviewer_completed"
    state.update({"schema_version":sv,"state_id":f"phase7.3.3-d-support-stage-state-v{sv}","status":status,"next_authorized_stage":next_stage,f"multi_claim_successor_boundary_reviewer_{reviewer}_completed":completed,"multi_claim_successor_provider_called":True,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
    ready.update({"schema_version":rv,"readiness_id":f"phase7.3.3-d1-reference-construction-readiness-v{rv}","status":status,"next_authorized_stage":next_stage,f"successor_boundary_reviewer_{reviewer}_completed":completed,"provider_called":True,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
    return write_json_once(state_out,state),write_json_once(ready_out,ready)


def execute(reviewer: str)->dict[str,Any]:
    state_in,ready_in,_,_,expected_stage=execution_state_paths(reviewer); manifest_path=reviewer_manifest(reviewer); required=[PROTOCOL,SCHEMA,POLICY,PROMPT,WORKLIST,FIXTURES,manifest_path,state_in,ready_in]
    if any(not p.exists() for p in required): raise ValueError("execution_required_artifact_missing")
    state=load(state_in); ready=load(ready_in)
    if state.get("next_authorized_stage")!=expected_stage or ready.get("next_authorized_stage")!=expected_stage: raise ValueError("execution_stage_not_authorized")
    manifest=load(manifest_path); msha=sha(manifest_path)
    for path,digest in {PROTOCOL:manifest["protocol_sha256"],SCHEMA:manifest["schema_sha256"],POLICY:manifest["policy_sha256"],PROMPT:manifest["prompt_sha256"],WORKLIST:manifest["worklist_sha256"],FIXTURES:manifest["fixtures_sha256"],Path(__file__):manifest["adapter_sha256"]}.items():
        if sha(path)!=digest: raise ValueError(f"execution_manifest_hash_mismatch:{rel(path)}")
    key=os.environ.get(CREDENTIAL_ENV)
    if not key: raise ValueError(f"credential_missing:{CREDENTIAL_ENV}")
    system,user_template=split_prompt(); case_results=[]; all_claims=[]; provider_models=set()
    for case in load(WORKLIST)["cases"]:
        cp=checkpoint_path(reviewer,case["case_id"])
        if cp.exists():
            saved=load(cp)
            if saved.get("manifest_sha256")!=msha: raise ValueError(f"checkpoint_manifest_mismatch:{case['case_id']}")
            case_results.append(saved["case_result"]); all_claims.extend(saved["claims"]); provider_models.add(saved["provider_reported_model"]); continue
        if authoritative_seen(msha,reviewer,case["case_id"]): raise ValueError(f"authoritative_content_seen_without_checkpoint_refusing_retry:{case['case_id']}")
        user=user_template.replace("{{CASE_JSON}}",json.dumps(case,ensure_ascii=False,indent=2)); raw=None; envelope_sha=None; content_sha=None
        try:
            raw=provider_request(key,manifest["model_requested"],system,user); envelope_sha=hb(raw); envelope=parse_provider_envelope(raw); content=envelope.get("choices",[{}])[0].get("message",{}).get("content")
            if not isinstance(content,str): raise ValueError("provider_content_not_string")
            content_sha=hb(content.encode("utf-8")); append_event({"event_type":"multi_claim_boundary_provider_content_received","manifest_sha256":msha,"reviewer":reviewer,"case_id":case["case_id"],"response_received":True,"authoritative_result":True,"provider_envelope_sha256":envelope_sha,"provider_content_sha256":content_sha},ATTEMPT_LOG)
            reported=envelope.get("model") or "unknown"; canonical=canonical_model_family(manifest["model_requested"],reported); claims=normalize_case(case,json.loads(content),reviewer)
            doc={"schema_version":1,"reviewer":reviewer,"case_id":case["case_id"],"manifest_sha256":msha,"provider_reported_model":reported,"canonical_model_family":canonical,"provider_envelope_sha256":envelope_sha,"provider_content_sha256":content_sha,"normalized_output_sha256":csha(claims),"claims":claims,"case_result":{"case_id":case["case_id"],"status":"completed","claim_count":len(claims)},"raw_provider_content_stored":False,"evidence_visible":False,"other_reviewer_output_visible":False,"confirmatory_dataset_opened":False}; write_json_once(cp,doc)
            append_event({"event_type":"multi_claim_boundary_case_authoritative_success","manifest_sha256":msha,"reviewer":reviewer,"case_id":case["case_id"],"response_received":True,"authoritative_result":True,"provider_content_sha256":content_sha,"normalized_output_sha256":doc["normalized_output_sha256"],"claim_count":len(claims),"provider_reported_model":reported,"canonical_model_family":canonical},ATTEMPT_LOG)
            case_results.append(doc["case_result"]); all_claims.extend(claims); provider_models.add(reported); print(f"Reviewer {reviewer.upper()} {case['case_id']}: {len(claims)} Claims",flush=True)
        except urllib.error.HTTPError as error:
            append_event({"event_type":"multi_claim_boundary_transport_failure","manifest_sha256":msha,"reviewer":reviewer,"case_id":case["case_id"],"status":f"http_{error.code}","response_received":False,"authoritative_result":False},ATTEMPT_LOG); return {"status":"TRANSPORT_FAILURE_RESUMABLE","reviewer":reviewer,"case_id":case["case_id"],"http_status":error.code}
        except Exception as error:
            received=raw is not None; append_event({"event_type":"multi_claim_boundary_experimental_failure" if received else "multi_claim_boundary_adapter_failure","manifest_sha256":msha,"reviewer":reviewer,"case_id":case["case_id"],"status":type(error).__name__,"error_code":str(error)[:300],"response_received":received,"authoritative_result":received,"provider_envelope_sha256":envelope_sha,"provider_content_sha256":content_sha},ATTEMPT_LOG)
            if not received: raise
            negative={"schema_version":1,"reviewer":reviewer,"manifest_sha256":msha,"case_id":case["case_id"],"status":"authoritative_negative_result","failure_type":type(error).__name__,"failure_code":str(error)[:300],"response_received":True,"provider_envelope_sha256":envelope_sha,"provider_content_sha256":content_sha,"raw_provider_content_stored":False,"boundary_capability_conclusion_authorized":False}; negative_sha=write_json_once(negative_path(reviewer),negative)
            outcome={"schema_version":1,"outcome_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-outcome-v1","status":"authoritative_negative_result","failure_case_id":case["case_id"],"negative_result_sha256":negative_sha,"same_version_retry_authorized":False,"next_authorized_stage":None,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False}; outcome_sha=write_json_once(outcome_path(reviewer),outcome); state_sha,ready_sha=finalize_state(reviewer,"boundary_reviewer_authoritative_negative_result",None,None,None)
            return {"status":"AUTHORITATIVE_NEGATIVE_RESULT","reviewer":reviewer,"case_id":case["case_id"],"failure_code":str(error),"outcome_sha256":outcome_sha,"state_sha256":state_sha,"readiness_sha256":ready_sha}
    requested=manifest["model_requested"]
    if {canonical_model_family(requested,m) for m in provider_models}!={requested}: raise ValueError("canonical_model_family_drift")
    submission={"schema_version":1,"submission_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-submission-v1","reviewer":reviewer,"reviewer_role":"independent_boundary_reviewer","manifest_sha256":msha,"worklist_sha256":sha(WORKLIST),"completed":True,"completed_case_count":len(case_results),"claim_count":len(all_claims),"blind_to_evidence":True,"blind_to_other_reviewer":True,"blind_to_support_labels":True,"blind_to_old_gold":True,"claims":all_claims,"completion_attestation":{"boundary_only":True,"support_not_judged":True,"claim_type_not_judged":True,"other_reviewer_not_seen":True,"all_exact_text_reconstructed_by_adapter":True}}; sub_sha=write_json_once(submission_path(reviewer),submission)
    result={"schema_version":1,"execution_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-v1","status":"completed","manifest_sha256":msha,"submission_sha256":sub_sha,"model_requested":requested,"canonical_model_family":requested,"provider_reported_models":sorted(provider_models),"completed_case_count":len(case_results),"claim_count":len(all_claims),"case_results":case_results,"raw_provider_content_stored":False,"confirmatory_dataset_opened":False}; res_sha=write_json_once(result_path(reviewer),result); next_stage=EXECUTE_B_STAGE if reviewer=="a" else AGREEMENT_STAGE
    outcome={"schema_version":1,"outcome_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-outcome-v1","status":"boundary_reviewer_completed","completed_case_count":len(case_results),"claim_count":len(all_claims),"submission_sha256":sub_sha,"execution_result_sha256":res_sha,"next_authorized_stage":next_stage,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False}; outcome_sha=write_json_once(outcome_path(reviewer),outcome); state_sha,ready_sha=finalize_state(reviewer,"boundary_reviewer_completed",next_stage,sub_sha,res_sha)
    receipt={"schema_version":1,"receipt_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-receipt-v1","status":"PASS","manifest_sha256":msha,"submission_sha256":sub_sha,"execution_result_sha256":res_sha,"execution_outcome_sha256":outcome_sha,"state_sha256":state_sha,"readiness_sha256":ready_sha,"completed_case_count":len(case_results),"claim_count":len(all_claims),"provider_called":True,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False,"next_authorized_stage":next_stage}; receipt_sha=write_json_once(receipt_path(reviewer),receipt)
    return {"status":"PASS","reviewer":reviewer,"model":requested,"cases":len(case_results),"claims":len(all_claims),"submission_sha256":sub_sha,"receipt_sha256":receipt_sha,"state_sha256":state_sha,"readiness_sha256":ready_sha,"next_authorized_stage":next_stage}


def main()->int:
    parser=argparse.ArgumentParser(); group=parser.add_mutually_exclusive_group(required=True); group.add_argument("--preflight-prepare",action="store_true"); group.add_argument("--fixtures",action="store_true"); group.add_argument("--prepare",action="store_true"); group.add_argument("--verify-prepare",action="store_true"); group.add_argument("--execute-reviewer",choices=sorted(REVIEWERS)); args=parser.parse_args()
    if args.preflight_prepare: result=preflight_prepare()
    elif args.fixtures: result=run_fixtures()
    elif args.prepare: result=prepare()
    elif args.verify_prepare: result=verify_prepare()
    else: result=execute(args.execute_reviewer)
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result.get("status") in {"PASS","TRANSPORT_FAILURE_RESUMABLE"} else 1


if __name__=="__main__": raise SystemExit(main())
