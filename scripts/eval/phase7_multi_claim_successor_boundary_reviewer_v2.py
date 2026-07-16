#!/usr/bin/env python3
"""Prepare and execute compact operation-only Boundary Review v2."""
from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, os, sys, urllib.error
from pathlib import Path
from typing import Any

SELF=Path(__file__).resolve(); ROOT=SELF.parents[2]
V1=ROOT/"scripts/eval/phase7_multi_claim_successor_boundary_reviewer_v1.py"
sys.path.insert(0,str(V1.parent))
spec=importlib.util.spec_from_file_location("phase7_boundary_v1_frozen",V1)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.__file__=str(SELF)
CONFIG=ROOT/"crates/eval/config"; PATTERN=ROOT/"crates/eval/datasets/pattern_extraction"; REPORTS=ROOT/"crates/eval/reports"
m.STATE_IN=PATTERN/"phase7_3_3_d_support_stage_state_v32.json"; m.READY_IN=REPORTS/"phase7_3_3_d1_reference_construction_readiness_v43.json"
ENTRY_PROTOCOL=CONFIG/"phase7_3_3_d_multi_claim_successor_boundary_review_v2_entry_protocol_v1.json"
ENTRY_CLASSIFICATION=REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_failure_classification_v1.json"
ENTRY_MANIFEST=REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_review_v2_entry_manifest_v1.json"
ENTRY_RECEIPT=REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_review_v2_entry_receipt_v1.json"
V1_PROTOCOL=CONFIG/"phase7_3_3_d_multi_claim_successor_boundary_review_protocol_v1.json"
m.WORKLIST=PATTERN/"phase7_3_3_d_multi_claim_successor_boundary_blind_worklist_v1.json"
m.PROTOCOL=CONFIG/"phase7_3_3_d_multi_claim_successor_boundary_review_protocol_v2.json"
m.SCHEMA=CONFIG/"phase7_3_3_d_multi_claim_successor_boundary_review_output_schema_v2.json"
m.POLICY=CONFIG/"phase7_3_3_d_multi_claim_successor_boundary_reviewer_execution_policy_v2.json"
m.PROMPT=CONFIG/"phase7_3_3_d_multi_claim_successor_boundary_reviewer_prompt_v2.md"
m.FIXTURES=REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_reviewer_contract_fixtures_v2.json"
m.PREP_MANIFEST=REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_review_prepare_manifest_v2.json"
m.PREP_OUTCOME=REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_review_prepare_outcome_v2.json"
m.PREP_RECEIPT=REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_review_prepare_receipt_v2.json"
m.STATE_PREP=PATTERN/"phase7_3_3_d_support_stage_state_v33.json"; m.READY_PREP=REPORTS/"phase7_3_3_d1_reference_construction_readiness_v44.json"
m.ATTEMPT_LOG=REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_reviewer_attempts_v2.jsonl"
m.CURRENT_STAGE="construct_multi_claim_successor_boundary_review_v2"
m.EXECUTE_A_STAGE="execute_multi_claim_successor_independent_boundary_review_a_v2"
m.EXECUTE_B_STAGE="execute_multi_claim_successor_independent_boundary_review_b_v2"
m.AGREEMENT_STAGE="construct_multi_claim_successor_boundary_agreement_v2"
m.EXPECTED={m.STATE_IN:"f5882b990f58093b6533bf6b9b1e8d0ef001f81415d203eca1904c2ff9c5edf9",m.READY_IN:"12cf2c110d3bd8dcd50ebde6aba72741c24a790d93a9da3e08c5a8c9c5497b23",ENTRY_PROTOCOL:"f3a9c401978f96d45c628214e65b9b0fabbbab3f56fd9e7cfab99e3b25c6555f",ENTRY_CLASSIFICATION:"2634b8d2d2963930616eb4a19bbb33ad87b3b27b98697a930174e55cfa60bd2e",ENTRY_MANIFEST:"e3441e4e7e15f2e4b9304096864921dfdb4f93a7200ed2e942d6100beb7513a1",ENTRY_RECEIPT:"4366f01c747a9c75437078e295cc162ca49dfe5351f028753d9d2e7038560644",m.WORKLIST:"13656be468d8c48c36967c689de4d0fdad09cd7f9ba9efe619682863659a2405",V1_PROTOCOL:"c1fc720a6b156652822754937a8ec36e4a76d97cd7980a26812327c9a51a3a21"}

def prompt_text()->str:
 return """# Phase 7.3.3-D Multi-claim Successor Boundary Reviewer Prompt v2

## System message

You are an independent Boundary Reviewer. Perform structural Atomic Claim segmentation only. Do not judge support, correctness, Claim Type, metadata, materiality, centrality, citations, or evidence.

Identify every independently truth-evaluable assertion. Split parts that could receive different truth values. Relatedness alone does not authorize merging. Compact snake_case assertions are valid Claims. Do not overlap Claims. Return at least one Claim.

Return compact strict JSON with exactly one root field named operations. Each item must be exactly one allowed operation:
- {"kind":"reuse_unit","unit_id":"unit-001"}
- {"kind":"merge_units","unit_ids":["unit-001","unit-002"]}
- {"kind":"slice_unit","unit_id":"unit-001","relative_start":0,"relative_end":5}
- {"kind":"new_span","start":0,"end":5}

Use reuse_unit whenever a whole supplied unit is one Claim. merge_units is only for consecutive units that jointly form one assertion and are not independently truth-evaluable. slice_unit must be a proper non-empty subspan. new_span is last resort. Offsets are zero-based Unicode code points, end exclusive.

Output example: {"operations":[{"kind":"reuse_unit","unit_id":"unit-001"}]}

Do not output rationale, confidence, Markdown, excerpts, claim text, spans, occurrence indices, support labels, types, roles, or citations. Keep JSON compact.

## User message template

Segment this frozen Candidate. Return compact operation-only JSON.

{{CASE_JSON}}
"""

def protocol_document()->dict[str,Any]:
 return {"schema_version":2,"protocol_id":"phase7.3.3-d-multi-claim-successor-boundary-review-protocol-v2","status":"frozen_before_any_v2_provider_call","predecessor_protocol_sha256":m.sha(V1_PROTOCOL),"entry_protocol_sha256":m.sha(ENTRY_PROTOCOL),"object_of_study":"atomic_claim_boundary_segmentation_under_compact_operation_only_representation","boundary_semantics_unchanged_from_v1":True,"representation":{"root_field":"operations","operation_only":True,"rationale_removed":True,"confidence_removed":True,"model_returns_exact_excerpt":False,"adapter_reconstructs_exact_excerpt":True,"operations":sorted(m.OP_KEYS)},"controlled_invariants":{"worklist_sha256":m.sha(m.WORKLIST),"reviewer_models":m.REVIEWERS,"provider":"api.gpt.ge","temperature":0,"top_p":1,"max_tokens":2500,"evidence_visible":False,"other_reviewer_visible":False},"both_v2_manifests_frozen_before_reviewer_a_v2":True,"reviewer_a_v1_reused":False,"next_after_two_completed_v2_submissions":m.AGREEMENT_STAGE}

def schema_document()->dict[str,Any]:
 specs={"reuse_unit":{"unit_id":{"type":"string","minLength":1}},"merge_units":{"unit_ids":{"type":"array","minItems":2,"uniqueItems":True,"items":{"type":"string","minLength":1}}},"slice_unit":{"unit_id":{"type":"string","minLength":1},"relative_start":{"type":"integer","minimum":0},"relative_end":{"type":"integer","minimum":1}},"new_span":{"start":{"type":"integer","minimum":0},"end":{"type":"integer","minimum":1}}}
 variants=[{"type":"object","required":["kind",*props],"properties":{"kind":{"const":kind},**props},"additionalProperties":False} for kind,props in specs.items()]
 return {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"phase7.3.3-d-multi-claim-successor-boundary-review-output-schema-v2","type":"object","required":["operations"],"properties":{"operations":{"type":"array","minItems":1,"items":{"oneOf":variants}}},"additionalProperties":False}

def policy_document()->dict[str,Any]:
 return {"schema_version":2,"policy_id":"phase7.3.3-d-multi-claim-successor-boundary-reviewer-execution-policy-v2","authoritative_result_policy":{"first_returned_provider_content_per_case_authoritative":True,"provider_response_sha256_before_envelope_parse":True,"provider_content_sha256_before_content_parse":True,"invalid_json_schema_or_semantics_is_negative_result":True,"same_version_retry_after_content":False,"transport_failure_before_content_may_resume":True},"execution_controls":{"case_isolation":True,"temperature":0,"top_p":1,"max_tokens":2500,"response_format":{"type":"json_object"}},"single_intended_change_from_v1":"compact operation-only serialization","prohibitions":["no_rationale_output","no_confidence_output","no_support","no_type","no_metadata","no_repair","no_same_version_semantic_retry","no_confirmatory_open","no_runtime_integration"]}

def normalize_case(case:dict[str,Any],payload:Any,reviewer:str)->list[dict[str,Any]]:
 if not isinstance(payload,dict) or set(payload)!={"operations"} or not isinstance(payload["operations"],list) or not payload["operations"]:raise ValueError("root_schema_invalid_or_empty_operations")
 text=case["candidate_text"];rows=[]
 for i,op in enumerate(payload["operations"]):
  start,end,ids,kind=m.resolve_operation(case,op,i);excerpt=text[start:end]
  if not excerpt:raise ValueError(f"empty_reconstructed_excerpt:{i}")
  rows.append({"case_id":case["case_id"],"source_span":{"start":start,"end":end},"source_excerpt":excerpt,"source_occurrence_index":m.exact_occurrence_index(text,excerpt,start),"source_unit_ids":ids,"boundary_operation_kind":kind,"reviewer":reviewer})
 rows.sort(key=lambda x:(x["source_span"]["start"],x["source_span"]["end"],x["boundary_operation_kind"]));previous=-1;seen=set()
 for i,row in enumerate(rows):
  span=(row["source_span"]["start"],row["source_span"]["end"])
  if span in seen:raise ValueError(f"duplicate_final_span:{i}")
  if span[0]<previous:raise ValueError(f"overlapping_final_spans:{i}")
  seen.add(span);previous=span[1];row["claim_id"]=f"{case['case_id']}-{reviewer}-v2-claim-{i+1:03d}"
 return rows

def run_fixtures()->dict[str,Any]:
 fs=[];case=m.fixture_case("alpha\nbeta\ngamma")
 accepts=[("reuse",{"operations":[{"kind":"reuse_unit","unit_id":"unit-001"}]},"alpha"),("merge",{"operations":[{"kind":"merge_units","unit_ids":["unit-001","unit-002"]}]},"alpha\nbeta"),("slice",{"operations":[{"kind":"slice_unit","unit_id":"unit-001","relative_start":1,"relative_end":4}]},"lph"),("new",{"operations":[{"kind":"new_span","start":6,"end":10}]},"beta")]
 for fid,payload,expected in accepts:fs.append({"fixture_id":fid,"status":"PASS" if normalize_case(case,payload,"fixture")[0]["source_excerpt"]==expected else "FAIL"})
 rejects=[("unknown",{"operations":[{"kind":"reuse_unit","unit_id":"unit-999"}]},"unknown_unit_id"),("nonconsecutive",{"operations":[{"kind":"merge_units","unit_ids":["unit-001","unit-003"]}]},"not_consecutive"),("full_slice",{"operations":[{"kind":"slice_unit","unit_id":"unit-001","relative_start":0,"relative_end":5}]},"slice_offsets_invalid"),("overlap",{"operations":[{"kind":"reuse_unit","unit_id":"unit-001"},{"kind":"new_span","start":2,"end":7}]},"overlapping_final_spans"),("empty",{"operations":[]},"root_schema_invalid"),("v1_shape",{"claims":[]},"root_schema_invalid")]
 for fid,payload,needle in rejects:
  try:normalize_case(case,payload,"fixture")
  except ValueError as e:status="PASS" if needle in str(e) else "FAIL";observed=str(e)
  else:status="FAIL";observed="accepted"
  fs.append({"fixture_id":fid,"status":status,"observed":observed})
 valid=m.parse_provider_envelope(b'{"model":"gpt-4.1","choices":[]}');fs.append({"fixture_id":"valid_envelope","status":"PASS" if valid.get("model")=="gpt-4.1" else "FAIL"})
 try:m.parse_provider_envelope(b'not-json')
 except ValueError as e:status="PASS" if str(e)=="provider_envelope_invalid_json" else "FAIL";observed=str(e)
 else:status="FAIL";observed="accepted"
 fs.append({"fixture_id":"invalid_envelope","status":status,"observed":observed})
 return {"schema_version":2,"report_id":"phase7.3.3-d-multi-claim-successor-boundary-reviewer-contract-fixtures-v2","status":"PASS" if all(x["status"]=="PASS" for x in fs) else "FAIL","passed":sum(x["status"]=="PASS" for x in fs),"total":len(fs),"fixtures":fs,"provider_called":False,"confirmatory_dataset_opened":False}

def reviewer_manifest(r:str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_execution_manifest_v2.json"
def prepared_paths()->list[Path]:return [m.PROTOCOL,m.SCHEMA,m.POLICY,m.PROMPT,m.FIXTURES,m.PREP_MANIFEST,m.PREP_OUTCOME,m.PREP_RECEIPT,m.STATE_PREP,m.READY_PREP,reviewer_manifest("a"),reviewer_manifest("b")]
def manifest_document(r:str,hashes:dict[str,str])->dict[str,Any]:
 return {"schema_version":2,"manifest_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{r}-execution-manifest-v2","status":"frozen_not_started","reviewer":r,"provider":"api.gpt.ge","provider_base_url":m.BASE_URL,"model_requested":m.REVIEWERS[r]["model"],"temperature":0,"top_p":1,"max_tokens":2500,"response_format":{"type":"json_object"},"credential_env_name":m.CREDENTIAL_ENV,"adapter_sha256":m.sha(SELF),"protocol_sha256":hashes[m.rel(m.PROTOCOL)],"schema_sha256":hashes[m.rel(m.SCHEMA)],"policy_sha256":hashes[m.rel(m.POLICY)],"prompt_sha256":hashes[m.rel(m.PROMPT)],"worklist_sha256":m.sha(m.WORKLIST),"fixtures_sha256":hashes[m.rel(m.FIXTURES)],"entry_receipt_sha256":m.sha(ENTRY_RECEIPT),"case_count":40,"case_isolation":True,"compact_operation_only":True,"first_provider_content_authoritative":True,"semantic_retry_authorized":False,"raw_provider_content_stored":False,"evidence_visible":False,"other_reviewer_output_visible":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False}

def preflight_prepare()->dict[str,Any]:
 missing=[m.rel(p) for p in m.EXPECTED if not p.exists()];mismatch={m.rel(p):{"expected":d,"actual":m.sha(p)} for p,d in m.EXPECTED.items() if p.exists() and m.sha(p)!=d};state=m.load(m.STATE_IN) if m.STATE_IN.exists() else {};ready=m.load(m.READY_IN) if m.READY_IN.exists() else {};work=m.load(m.WORKLIST) if m.WORKLIST.exists() else {}
 checks={"required_inputs_present":not missing,"input_hashes_match":not mismatch,"state_authorizes_v2":state.get("next_authorized_stage")==m.CURRENT_STAGE,"readiness_authorizes_v2":ready.get("next_authorized_stage")==m.CURRENT_STAGE,"worklist_40":work.get("case_count")==40 and len(work.get("cases",[]))==40,"blind_worklist":work.get("evidence_present") is False and work.get("support_labels_present") is False and work.get("old_gold_present") is False,"v1_negative_preserved":state.get("multi_claim_successor_boundary_review_v1_negative_preserved") is True,"provider_not_called":state.get("multi_claim_successor_boundary_review_v2_provider_called") is False,"confirmatory_closed":state.get("confirmatory_dataset_opened") is False,"runtime_unauthorized":state.get("runtime_integration_authorized") is False,"outputs_absent":all(not p.exists() for p in prepared_paths())}
 return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"missing":missing,"mismatches":mismatch}

def build_prepare()->dict[Path,bytes]:
 fixtures=run_fixtures();base={m.PROTOCOL:m.jbytes(protocol_document()),m.SCHEMA:m.jbytes(schema_document()),m.POLICY:m.jbytes(policy_document()),m.PROMPT:prompt_text().encode("utf-8"),m.FIXTURES:m.jbytes(fixtures)};hashes={m.rel(p):m.hb(b) for p,b in base.items()};manifests={reviewer_manifest(r):m.jbytes(manifest_document(r,hashes)) for r in m.REVIEWERS};fixed={**base,**manifests};fixed_hash={m.rel(p):m.hb(b) for p,b in fixed.items()};passed=fixtures["status"]=="PASS"
 prep={"schema_version":2,"manifest_id":"phase7.3.3-d-multi-claim-successor-boundary-review-prepare-manifest-v2","status":"frozen_before_any_v2_provider_call","adapter":m.rel(SELF),"adapter_sha256":m.sha(SELF),"input_sha256":{m.rel(p):m.sha(p) for p in m.EXPECTED},"artifact_sha256":fixed_hash,"worklist_sha256":m.sha(m.WORKLIST),"both_v2_execution_manifests_frozen_before_a":True,"provider_called":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False};prep_b=m.jbytes(prep)
 outcome={"schema_version":2,"outcome_id":"phase7.3.3-d-multi-claim-successor-boundary-review-prepare-outcome-v2","status":"boundary_review_v2_frozen" if passed else "boundary_review_v2_prepare_failed","fixtures_passed":fixtures["passed"],"fixtures_total":fixtures["total"],"case_count":40,"provider_called":False,"next_authorized_stage":m.EXECUTE_A_STAGE if passed else None,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False}
 lineage={"multi_claim_successor_boundary_review_prepare_manifest_v2_sha256":m.hb(prep_b),**{Path(n).name.replace(".json","_sha256").replace(".md","_sha256"):d for n,d in fixed_hash.items()}}
 state=copy.deepcopy(m.load(m.STATE_IN));state.setdefault("artifact_lineage",{}).update(lineage);state.update({"schema_version":33,"state_id":"phase7.3.3-d-support-stage-state-v33","status":outcome["status"],"next_authorized_stage":outcome["next_authorized_stage"],"multi_claim_successor_boundary_review_v2_frozen":passed,"multi_claim_successor_boundary_reviewer_a_v2_completed":False,"multi_claim_successor_boundary_reviewer_b_v2_completed":False,"multi_claim_successor_boundary_review_v2_provider_called":False,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
 ready=copy.deepcopy(m.load(m.READY_IN));ready.setdefault("artifact_lineage",{}).update(lineage);ready.update({"schema_version":44,"readiness_id":"phase7.3.3-d1-reference-construction-readiness-v44","status":outcome["status"],"next_authorized_stage":outcome["next_authorized_stage"],"successor_boundary_review_v2_frozen":passed,"successor_boundary_reviewer_a_v2_completed":False,"successor_boundary_reviewer_b_v2_completed":False,"provider_called":False,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
 return {**fixed,m.PREP_MANIFEST:prep_b,m.PREP_OUTCOME:m.jbytes(outcome),m.STATE_PREP:m.jbytes(state),m.READY_PREP:m.jbytes(ready)}

def prepare()->dict[str,Any]:
 if preflight_prepare()["status"]!="PASS":raise ValueError("prepare_preflight_failed")
 built=build_prepare();hashes={m.rel(p):m.write_bytes_once(p,b) for p,b in built.items()};out=m.load(m.PREP_OUTCOME);fx=m.load(m.FIXTURES);receipt={"schema_version":2,"receipt_id":"phase7.3.3-d-multi-claim-successor-boundary-review-prepare-receipt-v2","status":"PASS" if out["next_authorized_stage"]==m.EXECUTE_A_STAGE else "FAIL","artifact_sha256":hashes,"case_count":40,"fixtures_passed":fx["passed"],"fixtures_total":fx["total"],"both_v2_manifests_frozen_before_a":True,"provider_called":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False,"next_authorized_stage":out["next_authorized_stage"]};rsha=m.write_json_once(m.PREP_RECEIPT,receipt)
 return {"status":receipt["status"],"fixtures":f"{fx['passed']}/{fx['total']}","prepare_manifest_sha256":m.sha(m.PREP_MANIFEST),"reviewer_a_manifest_sha256":m.sha(reviewer_manifest("a")),"reviewer_b_manifest_sha256":m.sha(reviewer_manifest("b")),"receipt_sha256":rsha,"state_sha256":m.sha(m.STATE_PREP),"readiness_sha256":m.sha(m.READY_PREP),"next_authorized_stage":out["next_authorized_stage"]}

def verify_prepare()->dict[str,Any]:
 expected=build_prepare();checks={m.rel(p):p.exists() and p.read_bytes()==b for p,b in expected.items()};checks[m.rel(m.PREP_RECEIPT)]=m.PREP_RECEIPT.exists() and m.load(m.PREP_RECEIPT).get("status")=="PASS";state=m.load(m.STATE_PREP) if m.STATE_PREP.exists() else {};checks.update({"next_gate":state.get("next_authorized_stage")==m.EXECUTE_A_STAGE,"worklist_unchanged":m.sha(m.WORKLIST)==m.EXPECTED[m.WORKLIST],"both_manifests":reviewer_manifest("a").exists() and reviewer_manifest("b").exists(),"provider_not_called":state.get("multi_claim_successor_boundary_review_v2_provider_called") is False,"confirmatory_closed":state.get("confirmatory_dataset_opened") is False,"runtime_unauthorized":state.get("runtime_integration_authorized") is False});failed=[k for k,v in checks.items() if not v];return {"status":"PASS" if not failed else "FAIL","checks":len(checks),"failed":failed,"next_authorized_stage":state.get("next_authorized_stage")}

def checkpoint_path(r:str,c:str)->Path:return REPORTS/"phase7_3_3_d_multi_claim_successor_boundary_reviewer_cases_v2"/r/f"{c}.json"
def submission_path(r:str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_submission_v2.json"
def result_path(r:str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_execution_result_v2.json"
def outcome_path(r:str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_execution_outcome_v2.json"
def receipt_path(r:str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_execution_receipt_v2.json"
def negative_path(r:str)->Path:return REPORTS/f"phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_negative_result_v2.json"
def execution_state_paths(r:str)->tuple[Path,Path,Path,Path,str]:
 if r=="a":return m.STATE_PREP,m.READY_PREP,PATTERN/"phase7_3_3_d_support_stage_state_v34.json",REPORTS/"phase7_3_3_d1_reference_construction_readiness_v45.json",m.EXECUTE_A_STAGE
 return PATTERN/"phase7_3_3_d_support_stage_state_v34.json",REPORTS/"phase7_3_3_d1_reference_construction_readiness_v45.json",PATTERN/"phase7_3_3_d_support_stage_state_v35.json",REPORTS/"phase7_3_3_d1_reference_construction_readiness_v46.json",m.EXECUTE_B_STAGE

def finalize_state(r:str,status:str,next_stage:str|None,sub_sha:str|None,res_sha:str|None)->tuple[str,str]:
 state_in,ready_in,state_out,ready_out,_=execution_state_paths(r);state=copy.deepcopy(m.load(state_in));ready=copy.deepcopy(m.load(ready_in));sv=34 if r=="a" else 35;rv=45 if r=="a" else 46;lineage={}
 if sub_sha:lineage[f"multi_claim_successor_boundary_reviewer_{r}_submission_v2_sha256"]=sub_sha
 if res_sha:lineage[f"multi_claim_successor_boundary_reviewer_{r}_execution_result_v2_sha256"]=res_sha
 state.setdefault("artifact_lineage",{}).update(lineage);ready.setdefault("artifact_lineage",{}).update(lineage);completed=status=="boundary_reviewer_v2_completed"
 state.update({"schema_version":sv,"state_id":f"phase7.3.3-d-support-stage-state-v{sv}","status":status,"next_authorized_stage":next_stage,f"multi_claim_successor_boundary_reviewer_{r}_v2_completed":completed,"multi_claim_successor_boundary_review_v2_provider_called":True,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
 ready.update({"schema_version":rv,"readiness_id":f"phase7.3.3-d1-reference-construction-readiness-v{rv}","status":status,"next_authorized_stage":next_stage,f"successor_boundary_reviewer_{r}_v2_completed":completed,"provider_called":True,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
 return m.write_json_once(state_out,state),m.write_json_once(ready_out,ready)

def authoritative_seen(msha:str,r:str,c:str)->bool:return any(e.get("manifest_sha256")==msha and e.get("reviewer")==r and e.get("case_id")==c and e.get("response_received") is True and e.get("authoritative_result") is True for e in m.read_entries(m.ATTEMPT_LOG))


def execute(reviewer: str)->dict[str,Any]:
    state_in,ready_in,_,_,expected_stage=execution_state_paths(reviewer)
    manifest_path=reviewer_manifest(reviewer)
    required=[m.PROTOCOL,m.SCHEMA,m.POLICY,m.PROMPT,m.WORKLIST,m.FIXTURES,manifest_path,state_in,ready_in]
    if any(not p.exists() for p in required):
        raise ValueError("execution_required_artifact_missing")
    state=m.load(state_in); ready=m.load(ready_in)
    if state.get("next_authorized_stage")!=expected_stage or ready.get("next_authorized_stage")!=expected_stage:
        raise ValueError("execution_stage_not_authorized")
    manifest=m.load(manifest_path); manifest_sha=m.sha(manifest_path)
    frozen={
        m.PROTOCOL:manifest["protocol_sha256"],
        m.SCHEMA:manifest["schema_sha256"],
        m.POLICY:manifest["policy_sha256"],
        m.PROMPT:manifest["prompt_sha256"],
        m.WORKLIST:manifest["worklist_sha256"],
        m.FIXTURES:manifest["fixtures_sha256"],
        SELF:manifest["adapter_sha256"],
    }
    for path,digest in frozen.items():
        if m.sha(path)!=digest:
            raise ValueError(f"execution_manifest_hash_mismatch:{m.rel(path)}")
    key=os.environ.get(m.CREDENTIAL_ENV)
    if not key:
        raise ValueError(f"credential_missing:{m.CREDENTIAL_ENV}")
    system,user_template=m.split_prompt()
    case_results=[]; all_claims=[]; provider_models=set()
    for case in m.load(m.WORKLIST)["cases"]:
        case_id=case["case_id"]
        checkpoint=checkpoint_path(reviewer,case_id)
        if checkpoint.exists():
            saved=m.load(checkpoint)
            if saved.get("manifest_sha256")!=manifest_sha:
                raise ValueError(f"checkpoint_manifest_mismatch:{case_id}")
            case_results.append(saved["case_result"])
            all_claims.extend(saved["claims"])
            provider_models.add(saved["provider_reported_model"])
            continue
        if authoritative_seen(manifest_sha,reviewer,case_id):
            raise ValueError(f"authoritative_content_seen_without_checkpoint_refusing_retry:{case_id}")
        user=user_template.replace("{{CASE_JSON}}",json.dumps(case,ensure_ascii=False,indent=2))
        raw=None; envelope_sha=None; content_sha=None
        try:
            raw=m.provider_request(key,manifest["model_requested"],system,user)
            envelope_sha=m.hb(raw)
            envelope=m.parse_provider_envelope(raw)
            content=envelope.get("choices",[{}])[0].get("message",{}).get("content")
            if not isinstance(content,str):
                raise ValueError("provider_content_not_string")
            content_sha=m.hb(content.encode("utf-8"))
            m.append_event({
                "event_type":"multi_claim_boundary_v2_provider_content_received",
                "manifest_sha256":manifest_sha,
                "reviewer":reviewer,
                "case_id":case_id,
                "response_received":True,
                "authoritative_result":True,
                "provider_envelope_sha256":envelope_sha,
                "provider_content_sha256":content_sha,
            },m.ATTEMPT_LOG)
            reported=envelope.get("model") or "unknown"
            canonical=m.canonical_model_family(manifest["model_requested"],reported)
            claims=normalize_case(case,json.loads(content),reviewer)
            doc={
                "schema_version":2,
                "reviewer":reviewer,
                "case_id":case_id,
                "manifest_sha256":manifest_sha,
                "provider_reported_model":reported,
                "canonical_model_family":canonical,
                "provider_envelope_sha256":envelope_sha,
                "provider_content_sha256":content_sha,
                "normalized_output_sha256":m.csha(claims),
                "representation":"compact_operation_only_v2",
                "claims":claims,
                "case_result":{"case_id":case_id,"status":"completed","claim_count":len(claims)},
                "raw_provider_content_stored":False,
                "evidence_visible":False,
                "other_reviewer_output_visible":False,
                "confirmatory_dataset_opened":False,
            }
            m.write_json_once(checkpoint,doc)
            m.append_event({
                "event_type":"multi_claim_boundary_v2_case_authoritative_success",
                "manifest_sha256":manifest_sha,
                "reviewer":reviewer,
                "case_id":case_id,
                "response_received":True,
                "authoritative_result":True,
                "provider_content_sha256":content_sha,
                "normalized_output_sha256":doc["normalized_output_sha256"],
                "claim_count":len(claims),
                "provider_reported_model":reported,
                "canonical_model_family":canonical,
            },m.ATTEMPT_LOG)
            case_results.append(doc["case_result"])
            all_claims.extend(claims)
            provider_models.add(reported)
            print(f"Reviewer {reviewer.upper()} v2 {case_id}: {len(claims)} Claims",flush=True)
        except urllib.error.HTTPError as error:
            m.append_event({
                "event_type":"multi_claim_boundary_v2_transport_failure",
                "manifest_sha256":manifest_sha,
                "reviewer":reviewer,
                "case_id":case_id,
                "status":f"http_{error.code}",
                "response_received":False,
                "authoritative_result":False,
            },m.ATTEMPT_LOG)
            return {"status":"TRANSPORT_FAILURE_RESUMABLE","reviewer":reviewer,"case_id":case_id,"http_status":error.code}
        except Exception as error:
            received=raw is not None
            m.append_event({
                "event_type":"multi_claim_boundary_v2_experimental_failure" if received else "multi_claim_boundary_v2_adapter_failure",
                "manifest_sha256":manifest_sha,
                "reviewer":reviewer,
                "case_id":case_id,
                "status":type(error).__name__,
                "error_code":str(error)[:300],
                "response_received":received,
                "authoritative_result":received,
                "provider_envelope_sha256":envelope_sha,
                "provider_content_sha256":content_sha,
            },m.ATTEMPT_LOG)
            if not received:
                raise
            negative={
                "schema_version":2,
                "negative_result_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-negative-result-v2",
                "reviewer":reviewer,
                "manifest_sha256":manifest_sha,
                "case_id":case_id,
                "status":"authoritative_negative_result",
                "failure_type":type(error).__name__,
                "failure_code":str(error)[:300],
                "response_received":True,
                "provider_envelope_sha256":envelope_sha,
                "provider_content_sha256":content_sha,
                "raw_provider_content_stored":False,
                "same_version_retry_authorized":False,
                "boundary_capability_conclusion_authorized":False,
            }
            negative_sha=m.write_json_once(negative_path(reviewer),negative)
            outcome={
                "schema_version":2,
                "outcome_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-outcome-v2",
                "status":"authoritative_negative_result",
                "failure_case_id":case_id,
                "negative_result_sha256":negative_sha,
                "same_version_retry_authorized":False,
                "next_authorized_stage":None,
                "confirmatory_dataset_opened":False,
                "runtime_integration_authorized":False,
            }
            outcome_sha=m.write_json_once(outcome_path(reviewer),outcome)
            state_sha,ready_sha=finalize_state(reviewer,"boundary_reviewer_v2_authoritative_negative_result",None,None,None)
            return {
                "status":"AUTHORITATIVE_NEGATIVE_RESULT",
                "reviewer":reviewer,
                "case_id":case_id,
                "failure_type":type(error).__name__,
                "failure_code":str(error),
                "negative_result_sha256":negative_sha,
                "outcome_sha256":outcome_sha,
                "state_sha256":state_sha,
                "readiness_sha256":ready_sha,
            }
    requested=manifest["model_requested"]
    if {m.canonical_model_family(requested,reported) for reported in provider_models}!={requested}:
        raise ValueError("canonical_model_family_drift")
    submission={
        "schema_version":2,
        "submission_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-submission-v2",
        "reviewer":reviewer,
        "reviewer_role":"independent_boundary_reviewer",
        "manifest_sha256":manifest_sha,
        "worklist_sha256":m.sha(m.WORKLIST),
        "completed":True,
        "completed_case_count":len(case_results),
        "claim_count":len(all_claims),
        "blind_to_evidence":True,
        "blind_to_other_reviewer":True,
        "blind_to_support_labels":True,
        "blind_to_old_gold":True,
        "representation":"compact_operation_only_v2",
        "claims":all_claims,
        "completion_attestation":{
            "boundary_only":True,
            "support_not_judged":True,
            "claim_type_not_judged":True,
            "other_reviewer_not_seen":True,
            "all_exact_text_reconstructed_by_adapter":True,
            "rationale_not_requested":True,
            "confidence_not_requested":True,
        },
    }
    submission_sha=m.write_json_once(submission_path(reviewer),submission)
    result={
        "schema_version":2,
        "execution_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-v2",
        "status":"completed",
        "manifest_sha256":manifest_sha,
        "submission_sha256":submission_sha,
        "model_requested":requested,
        "canonical_model_family":requested,
        "provider_reported_models":sorted(provider_models),
        "completed_case_count":len(case_results),
        "claim_count":len(all_claims),
        "case_results":case_results,
        "representation":"compact_operation_only_v2",
        "raw_provider_content_stored":False,
        "confirmatory_dataset_opened":False,
    }
    result_sha=m.write_json_once(result_path(reviewer),result)
    next_stage=m.EXECUTE_B_STAGE if reviewer=="a" else m.AGREEMENT_STAGE
    outcome={
        "schema_version":2,
        "outcome_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-outcome-v2",
        "status":"boundary_reviewer_v2_completed",
        "completed_case_count":len(case_results),
        "claim_count":len(all_claims),
        "submission_sha256":submission_sha,
        "execution_result_sha256":result_sha,
        "next_authorized_stage":next_stage,
        "confirmatory_dataset_opened":False,
        "runtime_integration_authorized":False,
    }
    outcome_sha=m.write_json_once(outcome_path(reviewer),outcome)
    state_sha,ready_sha=finalize_state(reviewer,"boundary_reviewer_v2_completed",next_stage,submission_sha,result_sha)
    receipt={
        "schema_version":2,
        "receipt_id":f"phase7.3.3-d-multi-claim-successor-boundary-reviewer-{reviewer}-execution-receipt-v2",
        "status":"PASS",
        "manifest_sha256":manifest_sha,
        "submission_sha256":submission_sha,
        "execution_result_sha256":result_sha,
        "execution_outcome_sha256":outcome_sha,
        "state_sha256":state_sha,
        "readiness_sha256":ready_sha,
        "completed_case_count":len(case_results),
        "claim_count":len(all_claims),
        "provider_called":True,
        "confirmatory_dataset_opened":False,
        "runtime_integration_authorized":False,
        "next_authorized_stage":next_stage,
    }
    receipt_sha=m.write_json_once(receipt_path(reviewer),receipt)
    return {
        "status":"PASS",
        "reviewer":reviewer,
        "model":requested,
        "cases":len(case_results),
        "claims":len(all_claims),
        "submission_sha256":submission_sha,
        "receipt_sha256":receipt_sha,
        "state_sha256":state_sha,
        "readiness_sha256":ready_sha,
        "next_authorized_stage":next_stage,
    }


def main()->int:
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight-prepare",action="store_true")
    group.add_argument("--fixtures",action="store_true")
    group.add_argument("--prepare",action="store_true")
    group.add_argument("--verify-prepare",action="store_true")
    group.add_argument("--execute-reviewer",choices=sorted(m.REVIEWERS))
    args=parser.parse_args()
    if args.preflight_prepare:
        result=preflight_prepare()
    elif args.fixtures:
        result=run_fixtures()
    elif args.prepare:
        result=prepare()
    elif args.verify_prepare:
        result=verify_prepare()
    else:
        result=execute(args.execute_reviewer)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result.get("status") in {"PASS","TRANSPORT_FAILURE_RESUMABLE"} else 1


if __name__=="__main__":
    raise SystemExit(main())
