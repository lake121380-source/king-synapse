#!/usr/bin/env python3
"""Phase 7.3.3-D1-B4 Boundary Omission Resolution v2."""
from __future__ import annotations
import argparse, hashlib, json, os, tempfile, urllib.error, urllib.request
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event, next_attempt_number, read_entries

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'crates/eval/config'; DATA=ROOT/'crates/eval/datasets/pattern_extraction'; REPORTS=ROOT/'crates/eval/reports'
B3_WORKLIST=REPORTS/'phase7_3_3_d_boundary_omission_resolution_worklist_v1.json'
B3_SUBMISSION=REPORTS/'phase7_3_3_d_non_claim_adjudication_submission_v1.json'
B3_READINESS=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v8.json'
B4_V1_READINESS=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v9.json'
B2_PACKET=DATA/'phase7_3_3_d_non_claim_accounting_review_packet_v1.json'
PROTOCOL=CONFIG/'phase7_3_3_d_boundary_omission_resolution_protocol_v2.json'
POLICY=CONFIG/'phase7_3_3_d_boundary_omission_resolution_execution_policy_v2.json'
PROMPT=CONFIG/'phase7_3_3_d_boundary_omission_resolution_prompt_v2.md'
WORKLIST=DATA/'phase7_3_3_d_boundary_omission_resolution_packet_v2.json'
FIXTURES=REPORTS/'phase7_3_3_d_boundary_omission_resolution_contract_fixtures_v2.json'
MANIFEST=REPORTS/'phase7_3_3_d_boundary_omission_resolution_execution_manifest_v2.json'
ATTEMPT_LOG=REPORTS/'phase7_3_3_d_boundary_omission_resolution_attempts_v2.jsonl'
CASE_DIR=REPORTS/'phase7_3_3_d_boundary_omission_resolution_cases_v2'
RESULT=REPORTS/'phase7_3_3_d_boundary_omission_resolution_execution_result_v2.json'
SUBMISSION=REPORTS/'phase7_3_3_d_boundary_omission_resolution_submission_v2.json'
CORRECTION=REPORTS/'phase7_3_3_d_boundary_correction_worklist_v2.json'
READINESS=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v10.json'
BASE_URL='https://api.gpt.ge/v1'; CREDENTIAL_ENV='PHASE7_ATOMIC_JUDGE_API_KEY'
MODEL='gpt-5.4'; TEMP=0; TOP_P=1; MAX_TOKENS=8000; TIMEOUT=600; RESP={'type':'json_object'}
RESOLUTIONS={'resolved_as_non_claim','confirmed_boundary_omission'}
SEVERITIES={'cosmetic','semantic_modifier','independent_claim_missing'}
TARGET={'coverage-gap-012','coverage-gap-067','coverage-gap-069','coverage-gap-082'}


def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()
def sb(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def csha(v:Any)->str: return sb(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def write_once(p:Path,v:Any)->str:
    b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
    if p.exists():
        if p.read_bytes()!=b: raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
        return sb(b)
    p.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:
        h.write(b); t=Path(h.name)
    t.replace(p); return sb(b)
def text_once(p:Path,s:str)->str:
    b=s.encode()
    if p.exists():
        if p.read_bytes()!=b: raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
        return sb(b)
    p.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:
        h.write(b); t=Path(h.name)
    t.replace(p); return sb(b)


def protocol()->dict[str,Any]:
    return {
      'schema_version':1,
      'protocol_id':'phase7.3.3-d1-b4-boundary-omission-resolution-v2',
      'research_object':'resolution of the four frozen Boundary Omission Candidates remaining after D1-B3',
      'input_candidate_count':4,
      'change_from_v1':'Only provider model identity canonicalization changes: a dated snapshot whose leaf identifier begins with gpt-5.4- is accepted as canonical family gpt-5.4.',
      'allowed_resolutions':{
        'resolved_as_non_claim':{
          'definition':'The frozen Gap does not require a Claim Boundary correction under the current Atomic Claim policy.',
          'severity_must_be_null':True},
        'confirmed_boundary_omission':{
          'definition':'The frozen Gap contains content that must be represented by a Boundary Claim or incorporated into a corrected Claim span.',
          'severity_required':True,'allowed_severity_codes':sorted(SEVERITIES)}},
      'allowed_changes':['resolution','severity','rationale'],
      'forbidden_changes':['change_gap_id','change_gap_span','change_gap_text','create_gap','delete_gap','split_gap','merge_gap','edit_existing_claim','create_corrected_claim','freeze_boundary_gold','run_coverage_qa','label_support'],
      'output_contract':{'one_isolated_case_per_request':True,'bare_json_only':True,'exact_gap_order_required':True,'top_level_keys':['case_id','decisions'],'decision_keys':['gap_id','resolution','severity','rationale']},
      'severity_policy':{'cosmetic':'lexical or form-boundary issue without a separately asserted proposition','semantic_modifier':'condition, limitation, relation, or other semantic modifier that must be represented','independent_claim_missing':'a separately verifiable proposition is absent'},
      'post_resolution':{'automatic_correction':False,'coverage_qa_rerun':False,'boundary_gold_freeze':False,'support_review_allowed':False,'held_out_accessed':False}}

def policy()->dict[str,Any]:
    return {'schema_version':1,'policy_id':'phase7.3.3-d1-b4-boundary-omission-resolution-execution-policy-v2','authoritative_result_policy':{'first_provider_content_authoritative':True,'invalid_json_schema_or_semantics_authoritative_negative':True,'semantic_retry':False,'transport_failure_before_content_resume_same_manifest':True},'model_identity_canonicalization':{'requested_family':MODEL,'accepted_leaf_forms':['gpt-5.4','gpt-5.4-*'],'canonical_family':MODEL},'execution_controls':{'case_isolation':True,'model':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESP},'data_handling':{'credential_env_name':CREDENTIAL_ENV,'raw_provider_response_stored':False,'envelope_hash_recorded':True,'content_hash_recorded':True,'held_out_loaded':False},'prohibitions':['no_boundary_repair','no_coverage_qa_rerun','no_gold_freeze','no_support_review']}

def prompt()->str:
    return '''# Phase 7.3.3-D1-B4 Boundary Omission Resolution Prompt v2

## System message
You resolve one frozen Boundary Omission Candidate. The Gap ID, source span, Gap text, source anchor, and existing claims are immutable. This stage may classify the Gap only; it may not edit spans, create or delete Claims, repair Boundary, rerun Coverage QA, freeze Boundary Gold, or label Support.

Choose exactly one resolution: `resolved_as_non_claim` or `confirmed_boundary_omission`.
- `resolved_as_non_claim` means no Boundary correction is required under the current Atomic Claim policy; severity must be null.
- `confirmed_boundary_omission` means the Gap contains content that must be represented by a Claim Boundary or incorporated into a corrected Claim span; choose exactly one severity: `cosmetic`, `semantic_modifier`, or `independent_claim_missing`.

Use only the source anchor, current claims, frozen Gap, and its B3 rationale. Treat the severity as an analysis label, not a correction instruction. Return bare JSON only:
{"case_id":"b4-001-coverage-gap-012","decisions":[{"gap_id":"coverage-gap-012","resolution":"confirmed_boundary_omission","severity":"independent_claim_missing","rationale":"..."}]}

## User message template
Resolve the existing frozen Boundary Omission Candidate. Do not modify its Gap, span, or claims. Return bare JSON only.

CASE_PACKET_JSON:
{CASE_PACKET_JSON}
'''


def inputs()->tuple[dict[str,Any],dict[str,Any],dict[str,Any]]:
    wl=load(B3_WORKLIST); sub=load(B3_SUBMISSION); p=load(B2_PACKET)
    if wl.get('held_out_accessed') is not False or sub.get('held_out_accessed') is not False or p.get('held_out_accessed') is not False: raise ValueError('held_out_state_invalid')
    if wl.get('omission_candidate_count')!=4: raise ValueError('b3_omission_count_invalid')
    candidates={x['gap_id']:x for x in wl.get('omission_candidates',[])}
    if set(candidates)!=TARGET: raise ValueError(f'b4_target_set_mismatch:{sorted(candidates)}')
    decisions={x['gap_id']:x for x in sub.get('decisions',[]) if x.get('final_classification')=='boundary_omission_candidate'}
    # B3's submission contains only adjudicated disagreement decisions; the four B4
    # candidates are the frozen downstream worklist and may include exact-agreement
    # rows carried forward by the coverage accounting stage.
    anchors={a['anchor_id']:{'case_id':c['case_id'],**a} for c in p['cases'] for a in c['anchors']}
    gaps={g['gap_id']:{'case_id':c['case_id'],**g} for c in p['cases'] for g in c['gaps']}
    return candidates, {gid:decisions.get(gid, {'gap_id':gid,'rationale':None}) for gid in TARGET}, {'anchors':anchors,'gaps':gaps}

def build_worklist()->dict[str,Any]:
    candidates,b3,ref=inputs(); cases=[]
    for i,gid in enumerate(sorted(TARGET,key=lambda x:int(x.rsplit('-',1)[1])),1):
        c=candidates[gid]; g=ref['gaps'][gid]; a=ref['anchors'][c['anchor_id']]
        if a['case_id']!=c['case_id'] or g['case_id']!=c['case_id']: raise ValueError(f'case_lineage_invalid:{gid}')
        s,e=c['source_span']['start'],c['source_span']['end']
        if a['source_text'][s:e]!=c['gap_text']: raise ValueError(f'gap_lineage_invalid:{gid}')
        if g['source_span']!=c['source_span']: raise ValueError(f'span_lineage_invalid:{gid}')
        cases.append({'case_id':f'b4-{i:03d}-{gid}','source_case_id':c['case_id'],'gap_id':gid,'anchor':{'anchor_id':a['anchor_id'],'source_field':a['source_field'],'source_index':a['source_index'],'source_text':a['source_text'],'current_claims':a['current_claims']},'gap':{'gap_id':gid,'source_span':c['source_span'],'gap_text':c['gap_text'],'eligible_non_whitespace_count':g['eligible_non_whitespace_count']},'b3_context':{'final_classification':'boundary_omission_candidate','rationale':b3[gid]['rationale'],'source_stage':'D1-B3 non-claim accounting adjudication'}})
    return {'schema_version':1,'worklist_id':'phase7.3.3-d1-b4-boundary-omission-resolution-packet-v2','status':'frozen_input_worklist','case_count':4,'gap_count':4,'case_isolation':True,'held_out_accessed':False,'source_lineage':{'b3_worklist_sha256':sha(B3_WORKLIST),'b3_submission_sha256':sha(B3_SUBMISSION),'b3_readiness_sha256':sha(B3_READINESS),'b4_v1_readiness_sha256':sha(B4_V1_READINESS),'b2_packet_sha256':sha(B2_PACKET)},'cases':cases}

def normalize(case:dict[str,Any],obj:Any)->dict[str,Any]:
    if not isinstance(obj,dict) or set(obj)!= {'case_id','decisions'} or obj['case_id']!=case['case_id']: raise ValueError('response_top_level_or_case_id_invalid')
    ds=obj['decisions']
    if not isinstance(ds,list) or len(ds)!=1: raise ValueError('decision_count_invalid')
    d=ds[0]
    if not isinstance(d,dict) or set(d)!= {'gap_id','resolution','severity','rationale'}: raise ValueError('decision_fields_invalid')
    if d['gap_id']!=case['gap_id'] or d['resolution'] not in RESOLUTIONS or not isinstance(d['rationale'],str) or not d['rationale'].strip(): raise ValueError('decision_identity_resolution_or_rationale_invalid')
    if d['resolution']=='resolved_as_non_claim':
        if d['severity'] is not None: raise ValueError('non_claim_severity_must_be_null')
    elif d['severity'] not in SEVERITIES: raise ValueError('omission_severity_invalid')
    return {'case_id':case['case_id'],'gap_id':case['gap_id'],'resolution':d['resolution'],'severity':d['severity'],'rationale':d['rationale'].strip()}

def fixtures()->dict[str,Any]:
    c={'case_id':'fixture-1','gap_id':'coverage-gap-012'}
    valid={'case_id':'fixture-1','decisions':[{'gap_id':'coverage-gap-012','resolution':'confirmed_boundary_omission','severity':'independent_claim_missing','rationale':'The span contains an independently verifiable proposition.'}]}
    tests=[('valid',c,valid,True),('unknown_resolution',c,{**valid,'decisions':[dict(valid['decisions'][0],resolution='bad')]},False),('non_claim_with_severity',c,{**valid,'decisions':[dict(valid['decisions'][0],resolution='resolved_as_non_claim',severity='cosmetic')]},False),('non_claim_bad_severity',c,{**valid,'decisions':[dict(valid['decisions'][0],resolution='resolved_as_non_claim',severity='cosmetic')]},False),('omission_missing_severity',c,{**valid,'decisions':[dict(valid['decisions'][0],severity=None)]},False),('wrong_gap',c,{**valid,'decisions':[dict(valid['decisions'][0],gap_id='coverage-gap-999')]},False),('extra_field',c,{**valid,'decisions':[dict(valid['decisions'][0],edited_span=[1,2])]},False),('blank_rationale',c,{**valid,'decisions':[dict(valid['decisions'][0],rationale=' ')]},False)]
    r=[]
    for n,cc,obj,want in tests:
        ok=True; err=None
        try: normalize(cc,obj)
        except Exception as e: ok=False; err=str(e)
        r.append({'fixture':n,'expected_pass':want,'observed_pass':ok,'fixture_passed':ok==want,'observed_error':err})
    for n,reported,want in [('model_family_exact','gpt-5.4',True),('model_family_dated_snapshot','gpt-5.4-2026-03-05',True),('model_family_other','gpt-5.5-2026-03-05',False)]:
        ok=True; err=None
        try: model_family(reported)
        except Exception as e: ok=False; err=str(e)
        r.append({'fixture':n,'expected_pass':want,'observed_pass':ok,'fixture_passed':ok==want,'observed_error':err})
    return {'schema_version':1,'report_id':'phase7.3.3-d1-b4-boundary-omission-resolution-contract-fixtures-v2','fixture_count':len(r),'fixtures_passed':sum(x['fixture_passed'] for x in r),'all_fixtures_passed':all(x['fixture_passed'] for x in r),'provider_called':False,'held_out_accessed':False,'results':r}

def prepare()->None:
    h={'protocol_sha256':write_once(PROTOCOL,protocol()),'policy_sha256':write_once(POLICY,policy()),'prompt_sha256':text_once(PROMPT,prompt()),'worklist_sha256':write_once(WORKLIST,build_worklist()),'fixtures_sha256':write_once(FIXTURES,fixtures())}
    f=load(FIXTURES)
    if not f['all_fixtures_passed']: raise ValueError('contract_fixtures_failed')
    w=load(WORKLIST)
    print(json.dumps({'status':'prepared_offline',**h,'case_count':w['case_count'],'gap_count':w['gap_count'],'fixtures':f"{f['fixtures_passed']}/{f['fixture_count']}",'provider_called':False,'held_out_accessed':False},ensure_ascii=False,indent=2))

def expected_manifest()->dict[str,Any]:
    if not all(p.exists() for p in [PROTOCOL,POLICY,PROMPT,WORKLIST,FIXTURES]): raise ValueError('prepare_required')
    if not load(FIXTURES)['all_fixtures_passed']: raise ValueError('fixtures_not_passed')
    return {'schema_version':1,'manifest_id':'phase7.3.3-d1-b4-boundary-omission-resolution-execution-v2','status':'frozen_not_started','provider':'api.gpt.ge','provider_base_url':BASE_URL,'model_requested':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESP,'model_identity_canonicalization':{'accepted_leaf_forms':['gpt-5.4','gpt-5.4-*'],'canonical_family':MODEL},'credential_env_name':CREDENTIAL_ENV,'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(PROTOCOL),'execution_policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'worklist_sha256':sha(WORKLIST),'contract_fixtures_sha256':sha(FIXTURES),'b3_worklist_sha256':sha(B3_WORKLIST),'b3_submission_sha256':sha(B3_SUBMISSION),'b4_v1_readiness_sha256':sha(B4_V1_READINESS),'case_count':load(WORKLIST)['case_count'],'gap_count':load(WORKLIST)['gap_count'],'case_isolation':True,'first_provider_content_authoritative':True,'transport_resume_same_manifest_only':True,'semantic_retry_authorized':False,'raw_provider_responses_stored':False,'held_out_accessed':False}

def freeze_manifest()->None:
    h=write_once(MANIFEST,expected_manifest()); print(json.dumps({'status':'manifest_frozen_not_started','manifest_sha256':h,'provider_called':False,'held_out_accessed':False},indent=2))

def prompt_parts()->tuple[str,str]:
    t=PROMPT.read_text(encoding='utf-8-sig'); sm='## System message\n'; um='## User message template\n'
    if sm not in t or um not in t: raise ValueError('prompt_sections_missing')
    return t.split(sm,1)[1].split(um,1)[0].strip(),t.split(um,1)[1].strip()

def model_family(reported:str)->str:
    n=reported.strip().lower(); leaf=n.rsplit('/',1)[-1]; requested=MODEL.lower()
    if leaf==requested or leaf.startswith(requested+'-'): return MODEL
    raise ValueError(f'provider_model_outside_requested_family:{reported}')

def request(key:str,system:str,user:str)->bytes:
    payload={'model':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESP,'messages':[{'role':'system','content':system},{'role':'user','content':user}]}
    req=urllib.request.Request(BASE_URL+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=TIMEOUT) as r: return r.read()

def parse(raw:bytes)->tuple[str,str,str,Any]:
    try: e=json.loads(raw.decode())
    except Exception as x: raise ValueError('provider_envelope_invalid_json') from x
    if not isinstance(e,dict): raise ValueError('provider_envelope_not_object')
    reported=e.get('model')
    if not isinstance(reported,str) or not reported.strip(): raise ValueError('provider_reported_model_missing')
    canonical=model_family(reported); cs=e.get('choices')
    if not isinstance(cs,list) or not cs or not isinstance(cs[0],dict): raise ValueError('provider_choices_invalid')
    msg=cs[0].get('message')
    if not isinstance(msg,dict) or not isinstance(msg.get('content'),str) or not msg['content'].strip(): raise ValueError('provider_content_missing')
    content=msg['content']
    try: obj=json.loads(content)
    except Exception as x: raise ValueError('provider_content_invalid_json') from x
    return reported,canonical,sb(content.encode()),obj

def cpath(cid:str)->Path: return CASE_DIR/(cid+'.json')

def run_case(case:dict[str,Any],manifest_sha:str,key:str,system:str,template:str)->tuple[str,dict[str,Any]|None]:
    cp=cpath(case['case_id'])
    if cp.exists():
        x=load(cp)
        if x.get('manifest_sha256')!=manifest_sha: raise ValueError('checkpoint_manifest_mismatch')
        return x.get('status'),x
    n=next_attempt_number(manifest_sha,ATTEMPT_LOG); raw=None; eh=None; ch=None
    try:
        raw=request(key,system,template.replace('{CASE_PACKET_JSON}',json.dumps(case,ensure_ascii=False,separators=(',',':')))); eh=sb(raw)
        reported,canonical,ch,obj=parse(raw); d=normalize(case,obj)
        x={'schema_version':1,'checkpoint_id':'phase7.3.3-d1-b4-'+case['case_id']+'-v2','status':'authoritative_success','manifest_sha256':manifest_sha,'case_id':case['case_id'],'gap_id':case['gap_id'],'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':reported,'canonical_model_family':canonical,'decision':d,'decision_sha256':csha(d),'raw_provider_response_stored':False,'held_out_accessed':False}
        write_once(cp,x)
        append_event({'event_type':'d1_b4_v2_case_authoritative_success','manifest_sha256':manifest_sha,'attempt_number':n,'case_id':case['case_id'],'status':'completed','response_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'normalized_output_sha256':csha(d),'provider_reported_model':reported,'canonical_model_family':canonical},ATTEMPT_LOG)
        return 'authoritative_success',x
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
        st=f'http_{e.code}' if isinstance(e,urllib.error.HTTPError) else type(e).__name__
        append_event({'event_type':'d1_b4_v2_case_transport_failure','manifest_sha256':manifest_sha,'attempt_number':n,'case_id':case['case_id'],'status':st,'response_received':False,'authoritative_result':False},ATTEMPT_LOG)
        return 'transport_failure',None
    except Exception as e:
        got=raw is not None; st='authoritative_negative' if got else 'adapter_failure'
        x={'schema_version':1,'checkpoint_id':'phase7.3.3-d1-b4-'+case['case_id']+'-v2','status':st,'manifest_sha256':manifest_sha,'case_id':case['case_id'],'gap_id':case['gap_id'],'failure_type':type(e).__name__,'failure_code':str(e)[:500],'response_received':got,'authoritative_result':got,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'raw_provider_response_stored':False,'boundary_capability_conclusion_authorized':False,'held_out_accessed':False}
        if got: write_once(cp,x)
        append_event({'event_type':'d1_b4_v2_case_authoritative_negative' if got else 'd1_b4_case_adapter_failure','manifest_sha256':manifest_sha,'attempt_number':n,'case_id':case['case_id'],'status':st,'failure_type':type(e).__name__,'failure_code':str(e)[:500],'response_received':got,'authoritative_result':got,'provider_envelope_sha256':eh,'provider_content_sha256':ch},ATTEMPT_LOG)
        return st,x if got else None

def execute()->int:
    if not MANIFEST.exists(): raise ValueError('manifest_not_frozen')
    m=load(MANIFEST)
    if m!=expected_manifest(): raise ValueError('frozen_manifest_verification_failed')
    mh=sha(MANIFEST); key=os.environ.get(CREDENTIAL_ENV)
    if not key: raise ValueError(f'credential_env_missing:{CREDENTIAL_ENV}')
    system,template=prompt_parts(); w=load(WORKLIST); read_entries(ATTEMPT_LOG)
    append_event({'event_type':'d1_b4_v2_execution_invocation','manifest_sha256':mh,'status':'started_or_resumed','response_received':False,'authoritative_result':False},ATTEMPT_LOG)
    results=[]
    for case in w['cases']:
        st,x=run_case(case,mh,key,system,template); results.append({'case_id':case['case_id'],'gap_id':case['gap_id'],'status':st}); print(json.dumps(results[-1],ensure_ascii=False),flush=True)
        if st=='transport_failure': return 3
    out={'schema_version':1,'execution_id':'phase7.3.3-d1-b4-boundary-omission-resolution-execution-v2','status':'completed' if all(x['status']=='authoritative_success' for x in results) else 'completed_with_authoritative_negative_results','manifest_sha256':mh,'worklist_sha256':sha(WORKLIST),'case_count':4,'successful_case_count':sum(x['status']=='authoritative_success' for x in results),'authoritative_negative_case_count':sum(x['status']=='authoritative_negative' for x in results),'case_results':results,'raw_provider_responses_stored':False,'held_out_accessed':False,'boundary_correction_performed':False,'coverage_qa_rerun':False,'boundary_gold_frozen':False,'support_review_allowed':False}
    write_once(RESULT,out); print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if out['status']=='completed' else 4

def finalize()->int:
    if not RESULT.exists(): raise ValueError('execution_result_missing')
    r=load(RESULT); w=load(WORKLIST); cks=[load(cpath(c['case_id'])) for c in w['cases'] if cpath(c['case_id']).exists()]
    if r.get('status')!='completed' or len(cks)!=4 or any(x.get('status')!='authoritative_success' for x in cks): raise ValueError('cannot_finalize_incomplete_or_negative_execution')
    ds=[x['decision'] for x in sorted(cks,key=lambda x:int(x['case_id'].split('-')[1]))]
    sub={'schema_version':1,'submission_id':'phase7.3.3-d1-b4-boundary-omission-resolution-submission-v2','status':'completed_boundary_omission_resolution','label_status':'boundary_omission_resolution_frozen_correction_pending','manifest_sha256':sha(MANIFEST),'protocol_sha256':sha(PROTOCOL),'worklist_sha256':sha(WORKLIST),'b3_submission_sha256':sha(B3_SUBMISSION),'b4_v1_readiness_sha256':sha(B4_V1_READINESS),'case_count':4,'decision_count':4,'decisions':ds,'raw_provider_responses_stored':False,'held_out_accessed':False,'boundary_correction_performed':False,'coverage_qa_rerun':False,'boundary_gold_frozen':False,'support_review_allowed':False}
    subh=write_once(SUBMISSION,sub)
    confirmed=[d for d in ds if d['resolution']=='confirmed_boundary_omission']
    correction={'schema_version':1,'worklist_id':'phase7.3.3-d1-boundary-correction-worklist-v2','status':'pending_boundary_correction','source_submission_sha256':subh,'automatic_correction_authorized':False,'coverage_qa_rerun_in_this_stage':False,'boundary_gold_freeze_in_this_stage':False,'held_out_accessed':False,'candidate_count':len(confirmed),'candidates':[{'gap_id':d['gap_id'],'case_id':next(c['source_case_id'] for c in w['cases'] if c['gap_id']==d['gap_id']),'resolution':d['resolution'],'severity':d['severity'],'rationale':d['rationale'],'correction_status':'pending_boundary_correction'} for d in confirmed]}
    corrh=write_once(CORRECTION,correction)
    ready={'schema_version':10,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v10','status':'boundary_omission_resolution_complete_awaiting_boundary_correction','artifact_lineage':{'b2_packet_sha256':sha(B2_PACKET),'b3_worklist_sha256':sha(B3_WORKLIST),'b3_submission_sha256':sha(B3_SUBMISSION),'b3_readiness_v8_sha256':sha(B3_READINESS),'b4_v1_readiness_v9_sha256':sha(B4_V1_READINESS),'b4_protocol_sha256':sha(PROTOCOL),'b4_policy_sha256':sha(POLICY),'b4_prompt_sha256':sha(PROMPT),'b4_worklist_sha256':sha(WORKLIST),'b4_fixtures_sha256':sha(FIXTURES),'b4_manifest_sha256':sha(MANIFEST),'b4_result_sha256':sha(RESULT),'b4_submission_sha256':subh,'boundary_correction_worklist_sha256':corrh},'gates':{'dual_blind_gap_review_completed':True,'agreement_computed':True,'disagreements_resolved':True,'explicit_non_claim_accounting_frozen':True,'boundary_omission_resolution_completed':True,'boundary_correction_required':len(confirmed)>0,'coverage_qa_rerun_allowed':False,'coverage_qa_passed':False,'boundary_gold_frozen':False,'support_review_allowed':False,'held_out_accessed':False},'gap_count':84,'adjudicated_gap_count':16,'boundary_omission_candidate_count':4,'confirmed_boundary_omission_count':len(confirmed),'resolved_as_non_claim_count':4-len(confirmed),'next_authorized_stage':'boundary_correction','automatic_boundary_repair_performed':False,'coverage_qa_rerun_performed':False}
    rh=write_once(READINESS,ready)
    print(json.dumps({'status':ready['status'],'submission_sha256':subh,'boundary_correction_worklist_sha256':corrh,'readiness_v10_sha256':rh,'confirmed_boundary_omission_count':len(confirmed),'resolved_as_non_claim_count':4-len(confirmed),'coverage_qa_rerun_allowed':False,'boundary_gold_frozen':False,'support_review_allowed':False,'held_out_accessed':False},ensure_ascii=False,indent=2)); return 0

def verify()->None:
    w=load(WORKLIST); f=load(FIXTURES); checks={'case_count_4':w.get('case_count')==4,'gap_count_4':w.get('gap_count')==4,'target_gap_set_exact':{x['gap_id'] for x in w.get('cases',[])}==TARGET,'fixtures_11_of_11':f.get('fixture_count')==11 and f.get('fixtures_passed')==11 and f.get('all_fixtures_passed') is True,'provider_called_false':f.get('provider_called') is False,'held_out_false':w.get('held_out_accessed') is False and f.get('held_out_accessed') is False,'manifest_consistent':not MANIFEST.exists() or load(MANIFEST)==expected_manifest()}
    print(json.dumps({'all_passed':all(checks.values()),'checks':checks,'hashes':{'adapter':sha(Path(__file__)),'protocol':sha(PROTOCOL),'policy':sha(POLICY),'prompt':sha(PROMPT),'worklist':sha(WORKLIST),'fixtures':sha(FIXTURES)}},ensure_ascii=False,indent=2))
    if not all(checks.values()): raise ValueError('prepared_artifact_verification_failed')

def main()->int:
    p=argparse.ArgumentParser(); g=p.add_mutually_exclusive_group(required=True); g.add_argument('--prepare',action='store_true'); g.add_argument('--verify-prepared',action='store_true'); g.add_argument('--freeze-manifest',action='store_true'); g.add_argument('--execute',action='store_true'); g.add_argument('--finalize',action='store_true'); a=p.parse_args()
    if a.prepare: prepare(); return 0
    if a.verify_prepared: verify(); return 0
    if a.freeze_manifest: freeze_manifest(); return 0
    if a.execute: return execute()
    return finalize()

if __name__=='__main__': raise SystemExit(main())
