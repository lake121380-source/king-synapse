#!/usr/bin/env python3
"""Phase 7.3.3-D1-B3 Non-Claim Accounting Adjudication v1."""
from __future__ import annotations
import argparse, hashlib, json, os, tempfile, urllib.error, urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event, next_attempt_number, read_entries
ROOT=Path(__file__).resolve().parents[2]; CONFIG=ROOT/'crates/eval/config'; DATA=ROOT/'crates/eval/datasets/pattern_extraction'; REPORTS=ROOT/'crates/eval/reports'
B2_PROTOCOL=CONFIG/'phase7_3_3_d_non_claim_accounting_protocol_v1.json'; B2_PACKET=DATA/'phase7_3_3_d_non_claim_accounting_review_packet_v1.json'; B2_AGREEMENT=REPORTS/'phase7_3_3_d_non_claim_accounting_agreement_q_g_v1.json'; B2_READINESS=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v7.json'
PROTOCOL=CONFIG/'phase7_3_3_d_non_claim_adjudication_protocol_v1.json'; POLICY=CONFIG/'phase7_3_3_d_non_claim_adjudication_execution_policy_v1.json'; PROMPT=CONFIG/'phase7_3_3_d_non_claim_adjudication_prompt_v1.md'; WORKLIST=DATA/'phase7_3_3_d_non_claim_adjudication_worklist_v1.json'; FIXTURES=REPORTS/'phase7_3_3_d_non_claim_adjudication_contract_fixtures_v1.json'; MANIFEST=REPORTS/'phase7_3_3_d_non_claim_adjudication_execution_manifest_v1.json'; ATTEMPT_LOG=REPORTS/'phase7_3_3_d_non_claim_adjudication_attempts_v1.jsonl'; CASE_DIR=REPORTS/'phase7_3_3_d_non_claim_adjudication_cases_v1'; SUBMISSION=REPORTS/'phase7_3_3_d_non_claim_adjudication_submission_v1.json'; RESULT=REPORTS/'phase7_3_3_d_non_claim_adjudication_execution_result_v1.json'; RESOLUTION=REPORTS/'phase7_3_3_d_boundary_omission_resolution_worklist_v1.json'; READINESS=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v8.json'
BASE_URL='https://api.gpt.ge/v1'; CREDENTIAL_ENV='PHASE7_ATOMIC_JUDGE_API_KEY'; MODEL='gpt-5.4'; TEMP=0; TOP_P=1; MAX_TOKENS=8000; TIMEOUT=600; RESP={'type':'json_object'}
CLASSES={'explicit_non_claim','boundary_omission_candidate'}; REASONS={'punctuation_only','formatting_only','list_delimiter','non_assertive_connector','metadata_not_a_claim','other_explained_non_claim'}
CLASS_DIS={'coverage-gap-002','coverage-gap-005','coverage-gap-010','coverage-gap-046','coverage-gap-054','coverage-gap-064','coverage-gap-066','coverage-gap-082'}; REASON_DIS={'coverage-gap-011','coverage-gap-013','coverage-gap-021','coverage-gap-022','coverage-gap-024','coverage-gap-025','coverage-gap-027','coverage-gap-032'}; TARGET=CLASS_DIS|REASON_DIS
GROUPS={'coverage-gap-002':'contrastive_or_concessive_connector','coverage-gap-005':'conditional_operator','coverage-gap-010':'conditional_operator','coverage-gap-011':'connector_vs_delimiter_taxonomy','coverage-gap-013':'connector_vs_delimiter_taxonomy','coverage-gap-021':'punctuation_vs_list_delimiter_taxonomy','coverage-gap-022':'punctuation_vs_list_delimiter_taxonomy','coverage-gap-024':'punctuation_vs_list_delimiter_taxonomy','coverage-gap-025':'punctuation_vs_list_delimiter_taxonomy','coverage-gap-027':'punctuation_vs_list_delimiter_taxonomy','coverage-gap-032':'punctuation_vs_list_delimiter_taxonomy','coverage-gap-046':'contrastive_or_concessive_connector','coverage-gap-054':'contrastive_or_concessive_connector','coverage-gap-064':'contrastive_or_concessive_connector','coverage-gap-066':'contrastive_or_concessive_connector','coverage-gap-082':'lexical_boundary_integrity'}

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def sb(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def csha(v:Any)->str:return sb(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8'))
def write_once(p:Path,v:Any)->str:
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return sb(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p);return sb(b)
def text_once(p:Path,s:str)->str:
 b=s.encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return sb(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p);return sb(b)

def protocol()->dict[str,Any]:return {'schema_version':1,'protocol_id':'phase7.3.3-d1-b3-non-claim-accounting-adjudication-v1','research_object':'adjudication of the 16 non-exact-agreement decisions from frozen D1-B2 Gap review','input_gap_count':16,'classification_disagreement_count':8,'reason_disagreement_count':8,'allowed_changes':['final_classification','final_reason_code','rationale'],'forbidden_changes':['create_gap','delete_gap','split_gap','merge_gap','change_gap_id','change_gap_span','change_gap_text','change_case','change_anchor','boundary_repair','support_labeling'],'output_contract':{'one_isolated_case_per_request':True,'bare_json_only':True,'exact_gap_order_required':True,'top_level_keys':['case_id','decisions'],'decision_keys':['gap_id','final_classification','final_reason_code','rationale']},'reason_codes':sorted(REASONS),'post_adjudication':{'automatic_boundary_repair':False,'coverage_qa_rerun':False,'boundary_gold_freeze':False,'support_review_allowed':False,'held_out_accessed':False}}
def policy()->dict[str,Any]:return {'schema_version':1,'policy_id':'phase7.3.3-d1-b3-non-claim-adjudication-execution-policy-v1','authoritative_result_policy':{'first_provider_content_authoritative':True,'invalid_json_schema_or_semantics_authoritative_negative':True,'semantic_retry':False,'transport_failure_before_content_resume_same_manifest':True},'execution_controls':{'case_isolation':True,'model':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESP},'data_handling':{'credential_env_name':CREDENTIAL_ENV,'raw_provider_response_stored':False,'envelope_hash_recorded':True,'content_hash_recorded':True,'held_out_loaded':False}}
def prompt()->str:return '''# Phase 7.3.3-D1-B3 Non-Claim Accounting Adjudication Prompt v1

## System message
You adjudicate one frozen non-claim accounting disagreement. Gap ID, source span, Gap text, source anchor, and current claims are immutable. Change only final_classification, final_reason_code, and rationale. Never create, delete, split, merge, rename, or relocate a Gap. Do not perform Boundary repair or Support labeling.

For classification_disagreement choose explicit_non_claim or boundary_omission_candidate. explicit_non_claim requires one allowed reason; boundary_omission_candidate requires null reason. For reason_disagreement classification is fixed as explicit_non_claim; choose one allowed reason. Allowed reasons: punctuation_only, formatting_only, list_delimiter, non_assertive_connector, metadata_not_a_claim, other_explained_non_claim.

Use only the supplied packet and the two blind reviewer decisions. Return bare JSON only, with exactly the supplied case ID and one decision:
{"case_id":"b3-001-coverage-gap-002","decisions":[{"gap_id":"coverage-gap-002","final_classification":"boundary_omission_candidate","final_reason_code":null,"rationale":"..."}]}

## User message template
Adjudicate the existing Gap. Do not modify its set or span. Return bare JSON only.

CASE_PACKET_JSON:
{CASE_PACKET_JSON}
'''

def inputs():
 p=load(B2_PACKET); a=load(B2_AGREEMENT)
 if p.get('held_out_accessed') is not False or a.get('held_out_accessed') is not False:raise ValueError('held_out_state_invalid')
 if a.get('gap_count')!=84 or a.get('disagreement_count')!=16:raise ValueError('b2_counts_invalid')
 anchors={x['anchor_id']:{'case_id':c['case_id'],**x} for c in p['cases'] for x in c['anchors']}; rows={x['gap_id']:x for x in a['rows']}; gaps={x['gap_id']:{'case_id':c['case_id'],**x} for c in p['cases'] for x in c['gaps']}
 actual={gid for gid,x in rows.items() if x['agreement_status']!='exact_agreement'}
 if actual!=TARGET:raise ValueError(f'target_gap_set_mismatch:{sorted(actual)}')
 return p,anchors,rows,gaps

def worklist()->dict[str,Any]:
 _,anchors,rows,gaps=inputs(); cases=[]
 for i,gid in enumerate(sorted(TARGET,key=lambda x:int(x.rsplit('-',1)[1])),1):
  g=gaps[gid];an=anchors[g['anchor_id']];s,e=g['source_span']['start'],g['source_span']['end']
  if an['case_id']!=g['case_id'] or an['source_text'][s:e]!=g['gap_text']:raise ValueError(f'gap_lineage_invalid:{gid}')
  kind='classification_disagreement' if gid in CLASS_DIS else 'reason_disagreement'; row=rows[gid]
  expected='classification_agreement_reason_disagreement' if kind=='reason_disagreement' else kind
  if row['agreement_status']!=expected:raise ValueError(f'agreement_kind_invalid:{gid}')
  cases.append({'case_id':f'b3-{i:03d}-{gid}','source_case_id':g['case_id'],'gap_id':gid,'disagreement_kind':kind,'phenomenon_group':GROUPS[gid],'anchor':{'anchor_id':an['anchor_id'],'source_field':an['source_field'],'source_index':an['source_index'],'source_text':an['source_text'],'current_claims':an['current_claims']},'gap':{'gap_id':gid,'source_span':g['source_span'],'gap_text':g['gap_text'],'eligible_non_whitespace_count':g['eligible_non_whitespace_count']},'blind_reviewer_decisions':{'reviewer_q':row['reviewer_q'],'reviewer_g':row['reviewer_g']}})
 if len(cases)!=16:raise ValueError('worklist_count_invalid')
 return {'schema_version':1,'worklist_id':'phase7.3.3-d1-b3-non-claim-adjudication-worklist-v1','status':'frozen_input_worklist','case_count':16,'gap_count':16,'case_isolation':True,'held_out_accessed':False,'artifact_lineage':{'b2_protocol_sha256':sha(B2_PROTOCOL),'b2_packet_sha256':sha(B2_PACKET),'b2_agreement_sha256':sha(B2_AGREEMENT),'b2_readiness_sha256':sha(B2_READINESS)},'cases':cases}

def normalize(case:dict[str,Any],obj:Any)->dict[str,Any]:
 if not isinstance(obj,dict) or set(obj)!={'case_id','decisions'} or obj['case_id']!=case['case_id']:raise ValueError('response_top_level_or_case_id_invalid')
 ds=obj['decisions']
 if not isinstance(ds,list) or len(ds)!=1:raise ValueError('decision_count_invalid')
 d=ds[0]
 if not isinstance(d,dict) or set(d)!={'gap_id','final_classification','final_reason_code','rationale'}:raise ValueError('decision_fields_invalid')
 if d['gap_id']!=case['gap_id'] or d['final_classification'] not in CLASSES or not isinstance(d['rationale'],str) or not d['rationale'].strip():raise ValueError('decision_identity_classification_or_rationale_invalid')
 if case['disagreement_kind']=='reason_disagreement' and d['final_classification']!='explicit_non_claim':raise ValueError('reason_disagreement_must_be_explicit_non_claim')
 if d['final_classification']=='explicit_non_claim' and d['final_reason_code'] not in REASONS:raise ValueError('explicit_non_claim_reason_invalid')
 if d['final_classification']=='boundary_omission_candidate' and d['final_reason_code'] is not None:raise ValueError('omission_reason_must_be_null')
 return {'case_id':case['case_id'],'gap_id':case['gap_id'],'final_classification':d['final_classification'],'final_reason_code':d['final_reason_code'],'rationale':d['rationale'].strip()}

def fixtures()->dict[str,Any]:
 c={'case_id':'fixture-1','gap_id':'coverage-gap-002','disagreement_kind':'classification_disagreement'};v={'case_id':'fixture-1','decisions':[{'gap_id':'coverage-gap-002','final_classification':'boundary_omission_candidate','final_reason_code':None,'rationale':'Possible omitted claim-bearing relation.'}]};r=[]
 tests=[('valid',c,v,True),('unknown_class',c,{**v,'decisions':[dict(v['decisions'][0],final_classification='bad')]},False),('reason_missing',c,{**v,'decisions':[dict(v['decisions'][0],final_classification='explicit_non_claim',final_reason_code=None)]},False),('reason_on_omission',c,{**v,'decisions':[dict(v['decisions'][0],final_reason_code='list_delimiter')]},False),('wrong_gap',c,{**v,'decisions':[dict(v['decisions'][0],gap_id='x')]},False),('extra_field',c,{**v,'decisions':[dict(v['decisions'][0],edited_span=[1,2])]},False),('blank_rationale',c,{**v,'decisions':[dict(v['decisions'][0],rationale=' ')]},False)]
 rc={'case_id':'fixture-2','gap_id':'coverage-gap-011','disagreement_kind':'reason_disagreement'};rv={'case_id':'fixture-2','decisions':[{'gap_id':'coverage-gap-011','final_classification':'explicit_non_claim','final_reason_code':'non_assertive_connector','rationale':'No independent assertion.'}]};tests += [('valid_reason',rc,rv,True),('reason_reclassified',rc,{**rv,'decisions':[dict(rv['decisions'][0],final_classification='boundary_omission_candidate',final_reason_code=None)]},False)]
 for n,cc,p,w in tests:
  ok=True;err=None
  try:normalize(cc,p)
  except Exception as e:ok=False;err=str(e)
  r.append({'fixture':n,'expected_pass':w,'observed_pass':ok,'fixture_passed':ok==w,'observed_error':err})
 return {'schema_version':1,'report_id':'phase7.3.3-d1-b3-non-claim-adjudication-contract-fixtures-v1','fixture_count':len(r),'fixtures_passed':sum(x['fixture_passed'] for x in r),'all_fixtures_passed':all(x['fixture_passed'] for x in r),'provider_called':False,'held_out_accessed':False,'results':r}

def prepare():
 h={'protocol_sha256':write_once(PROTOCOL,protocol()),'policy_sha256':write_once(POLICY,policy()),'prompt_sha256':text_once(PROMPT,prompt()),'worklist_sha256':write_once(WORKLIST,worklist()),'fixtures_sha256':write_once(FIXTURES,fixtures())};f=load(FIXTURES)
 if not f['all_fixtures_passed']:raise ValueError('contract_fixtures_failed')
 w=load(WORKLIST);print(json.dumps({'status':'prepared_offline',**h,'case_count':w['case_count'],'gap_count':w['gap_count'],'fixtures':f"{f['fixtures_passed']}/{f['fixture_count']}",'provider_called':False,'held_out_accessed':False},ensure_ascii=False,indent=2))

def expected_manifest()->dict[str,Any]:
 if not all(p.exists() for p in [PROTOCOL,POLICY,PROMPT,WORKLIST,FIXTURES]):raise ValueError('prepare_required')
 if not load(FIXTURES)['all_fixtures_passed']:raise ValueError('fixtures_not_passed')
 return {'schema_version':1,'manifest_id':'phase7.3.3-d1-b3-non-claim-adjudication-execution-v1','status':'frozen_not_started','provider':'api.gpt.ge','provider_base_url':BASE_URL,'model_requested':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESP,'credential_env_name':CREDENTIAL_ENV,'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(PROTOCOL),'execution_policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'worklist_sha256':sha(WORKLIST),'contract_fixtures_sha256':sha(FIXTURES),'b2_agreement_sha256':sha(B2_AGREEMENT),'case_count':load(WORKLIST)['case_count'],'gap_count':load(WORKLIST)['gap_count'],'case_isolation':True,'first_provider_content_authoritative':True,'transport_resume_same_manifest_only':True,'semantic_retry_authorized':False,'raw_provider_responses_stored':False,'held_out_accessed':False}
def freeze_manifest():
 h=write_once(MANIFEST,expected_manifest());print(json.dumps({'status':'manifest_frozen_not_started','manifest_sha256':h,'provider_called':False,'held_out_accessed':False},indent=2))
def prompt_parts():
 t=PROMPT.read_text(encoding='utf-8-sig');sm='## System message\n';um='## User message template\n'
 if sm not in t or um not in t:raise ValueError('prompt_sections_missing')
 return t.split(sm,1)[1].split(um,1)[0].strip(),t.split(um,1)[1].strip()
def model_family(reported:str)->str:
 n=reported.strip().lower()
 if n==MODEL.lower() or n.endswith('/'+MODEL.lower()):return MODEL
 raise ValueError(f'provider_model_outside_requested_family:{reported}')
def request(key:str,system:str,user:str)->bytes:
 payload={'model':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESP,'messages':[{'role':'system','content':system},{'role':'user','content':user}]}
 req=urllib.request.Request(BASE_URL+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as r:return r.read()
def parse(raw:bytes):
 try:e=json.loads(raw.decode())
 except Exception as x:raise ValueError('provider_envelope_invalid_json') from x
 if not isinstance(e,dict):raise ValueError('provider_envelope_not_object')
 reported=e.get('model')
 if not isinstance(reported,str) or not reported.strip():raise ValueError('provider_reported_model_missing')
 canonical=model_family(reported);cs=e.get('choices')
 if not isinstance(cs,list) or not cs or not isinstance(cs[0],dict):raise ValueError('provider_choices_invalid')
 msg=cs[0].get('message')
 if not isinstance(msg,dict) or not isinstance(msg.get('content'),str) or not msg['content'].strip():raise ValueError('provider_content_missing')
 content=msg['content']
 try:obj=json.loads(content)
 except Exception as x:raise ValueError('provider_content_invalid_json') from x
 return reported,canonical,sb(content.encode()),obj

def cpath(cid:str)->Path:return CASE_DIR/(cid+'.json')
def run_case(case,manifest_sha,key,system,template):
 cp=cpath(case['case_id'])
 if cp.exists():
  x=load(cp)
  if x.get('manifest_sha256')!=manifest_sha:raise ValueError('checkpoint_manifest_mismatch')
  return x.get('status'),x
 n=next_attempt_number(manifest_sha,ATTEMPT_LOG);raw=None;eh=None;ch=None
 try:
  raw=request(key,system,template.replace('{CASE_PACKET_JSON}',json.dumps(case,ensure_ascii=False,separators=(',',':'))));eh=sb(raw);reported,canonical,ch,obj=parse(raw);d=normalize(case,obj)
  x={'schema_version':1,'checkpoint_id':'phase7.3.3-d1-b3-'+case['case_id']+'-v1','status':'authoritative_success','manifest_sha256':manifest_sha,'case_id':case['case_id'],'gap_id':case['gap_id'],'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':reported,'canonical_model_family':canonical,'decision':d,'decision_sha256':csha(d),'raw_provider_response_stored':False,'held_out_accessed':False};write_once(cp,x)
  append_event({'event_type':'d1_b3_case_authoritative_success','manifest_sha256':manifest_sha,'attempt_number':n,'case_id':case['case_id'],'status':'completed','response_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'normalized_output_sha256':csha(d),'provider_reported_model':reported,'canonical_model_family':canonical},ATTEMPT_LOG);return 'authoritative_success',x
 except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
  st=f'http_{e.code}' if isinstance(e,urllib.error.HTTPError) else type(e).__name__;append_event({'event_type':'d1_b3_case_transport_failure','manifest_sha256':manifest_sha,'attempt_number':n,'case_id':case['case_id'],'status':st,'response_received':False,'authoritative_result':False},ATTEMPT_LOG);return 'transport_failure',None
 except Exception as e:
  got=raw is not None;st='authoritative_negative' if got else 'adapter_failure';x={'schema_version':1,'checkpoint_id':'phase7.3.3-d1-b3-'+case['case_id']+'-v1','status':st,'manifest_sha256':manifest_sha,'case_id':case['case_id'],'gap_id':case['gap_id'],'failure_type':type(e).__name__,'failure_code':str(e)[:500],'response_received':got,'authoritative_result':got,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'raw_provider_response_stored':False,'boundary_capability_conclusion_authorized':False,'held_out_accessed':False}
  if got:write_once(cp,x)
  append_event({'event_type':'d1_b3_case_authoritative_negative' if got else 'd1_b3_case_adapter_failure','manifest_sha256':manifest_sha,'attempt_number':n,'case_id':case['case_id'],'status':st,'failure_type':type(e).__name__,'failure_code':str(e)[:500],'response_received':got,'authoritative_result':got,'provider_envelope_sha256':eh,'provider_content_sha256':ch},ATTEMPT_LOG);return st,x if got else None

def execute()->int:
 if not MANIFEST.exists():raise ValueError('manifest_not_frozen')
 m=load(MANIFEST)
 if m!=expected_manifest():raise ValueError('frozen_manifest_verification_failed')
 mh=sha(MANIFEST);key=os.environ.get(CREDENTIAL_ENV)
 if not key:raise ValueError(f'credential_env_missing:{CREDENTIAL_ENV}')
 system,template=prompt_parts();w=load(WORKLIST);read_entries(ATTEMPT_LOG);append_event({'event_type':'d1_b3_execution_invocation','manifest_sha256':mh,'status':'started_or_resumed','response_received':False,'authoritative_result':False},ATTEMPT_LOG);results=[]
 for case in w['cases']:
  st,x=run_case(case,mh,key,system,template);results.append({'case_id':case['case_id'],'gap_id':case['gap_id'],'status':st});print(json.dumps(results[-1],ensure_ascii=False),flush=True)
  if st=='transport_failure':return 3
 out={'schema_version':1,'execution_id':'phase7.3.3-d1-b3-non-claim-adjudication-execution-v1','status':'completed' if all(x['status']=='authoritative_success' for x in results) else 'completed_with_authoritative_negative_results','manifest_sha256':mh,'worklist_sha256':sha(WORKLIST),'case_count':16,'successful_case_count':sum(x['status']=='authoritative_success' for x in results),'authoritative_negative_case_count':sum(x['status']=='authoritative_negative' for x in results),'case_results':results,'raw_provider_responses_stored':False,'held_out_accessed':False};write_once(RESULT,out);print(json.dumps(out,ensure_ascii=False,indent=2));return 0 if out['status']=='completed' else 4

def finalize()->int:
 if not RESULT.exists():raise ValueError('execution_result_missing')
 r=load(RESULT);w=load(WORKLIST);cks=[load(cpath(c['case_id'])) for c in w['cases'] if cpath(c['case_id']).exists()]
 if r.get('status')!='completed' or len(cks)!=16 or any(x.get('status')!='authoritative_success' for x in cks):raise ValueError('cannot_finalize_incomplete_or_negative_execution')
 ds=[x['decision'] for x in sorted(cks,key=lambda x:int(x['case_id'].split('-')[1]))]
 sub={'schema_version':1,'submission_id':'phase7.3.3-d1-b3-non-claim-adjudication-submission-v1','status':'completed_non_claim_accounting_adjudication','label_status':'non_claim_accounting_frozen_boundary_omission_candidates_unresolved','manifest_sha256':sha(MANIFEST),'protocol_sha256':sha(PROTOCOL),'worklist_sha256':sha(WORKLIST),'agreement_sha256':sha(B2_AGREEMENT),'case_count':16,'decision_count':16,'decisions':ds,'raw_provider_responses_stored':False,'held_out_accessed':False,'boundary_repair_performed':False,'coverage_qa_rerun':False,'boundary_gold_frozen':False,'support_review_allowed':False};subh=write_once(SUBMISSION,sub)
 a=load(B2_AGREEMENT);all_final=[];by_dec={x['gap_id']:x for x in ds}
 for row in a['rows']:
  if row['gap_id'] in by_dec:d=by_dec[row['gap_id']];st='adjudicated';cl=d['final_classification'];rc=d['final_reason_code'];rat=d['rationale']
  else:src=row['reviewer_q'];st='frozen_exact_or_reason_agreement';cl=src['classification'];rc=src['reason_code'];rat=src['rationale']
  all_final.append({'gap_id':row['gap_id'],'case_id':row['case_id'],'original_agreement_status':row['agreement_status'],'final_classification':cl,'final_reason_code':rc,'adjudication_status':st,'rationale':rat})
 p=load(B2_PACKET);gaps={x['gap_id']:{'case_id':c['case_id'],**x} for c in p['cases'] for x in c['gaps']};om=[]
 for row in all_final:
  if row['final_classification']=='boundary_omission_candidate':
   g=gaps[row['gap_id']];om.append({'gap_id':row['gap_id'],'case_id':g['case_id'],'anchor_id':g['anchor_id'],'source_span':g['source_span'],'gap_text':g['gap_text'],'final_reason_code':None,'source_stage':'D1-B3 non-claim accounting adjudication','resolution_status':'pending_boundary_omission_resolution'})
 rh=write_once(RESOLUTION,{'schema_version':1,'worklist_id':'phase7.3.3-d-boundary-omission-resolution-worklist-v1','status':'pending_boundary_omission_resolution','source_submission_sha256':subh,'source_agreement_sha256':sha(B2_AGREEMENT),'automatic_boundary_repair_authorized':False,'coverage_qa_rerun_in_this_stage':False,'boundary_gold_freeze_in_this_stage':False,'held_out_accessed':False,'omission_candidate_count':len(om),'omission_candidates':om})
 ready={'schema_version':8,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v8','status':'non_claim_accounting_adjudication_complete_awaiting_boundary_omission_resolution','artifact_lineage':{'b2_protocol_sha256':sha(B2_PROTOCOL),'b2_packet_sha256':sha(B2_PACKET),'b2_agreement_sha256':sha(B2_AGREEMENT),'b2_readiness_v7_sha256':sha(B2_READINESS),'b3_protocol_sha256':sha(PROTOCOL),'b3_policy_sha256':sha(POLICY),'b3_prompt_sha256':sha(PROMPT),'b3_worklist_sha256':sha(WORKLIST),'b3_manifest_sha256':sha(MANIFEST),'b3_submission_sha256':subh,'boundary_omission_resolution_worklist_sha256':rh},'gates':{'dual_blind_gap_review_completed':True,'agreement_computed':True,'disagreements_resolved':True,'explicit_non_claim_accounting_frozen':True,'coverage_qa_rerun_allowed':False,'coverage_qa_passed':False,'boundary_gold_frozen':False,'support_review_allowed':False,'held_out_accessed':False},'gap_count':84,'adjudicated_gap_count':16,'boundary_omission_candidate_count':len(om),'next_authorized_stage':'boundary_omission_resolution','automatic_boundary_repair_performed':False,'coverage_qa_rerun_performed':False};vh=write_once(READINESS,ready)
 print(json.dumps({'status':ready['status'],'submission_sha256':subh,'omission_resolution_worklist_sha256':rh,'readiness_v8_sha256':vh,'adjudicated_gap_count':16,'boundary_omission_candidate_count':len(om),'boundary_gold_frozen':False,'support_review_allowed':False,'held_out_accessed':False},ensure_ascii=False,indent=2));return 0

def verify():
 w=load(WORKLIST);f=load(FIXTURES);checks={'case_count_16':w.get('case_count')==16,'gap_count_16':w.get('gap_count')==16,'target_gap_set_exact':{x['gap_id'] for x in w.get('cases',[])}==TARGET,'fixtures_9_of_9':f.get('fixture_count')==9 and f.get('fixtures_passed')==9 and f.get('all_fixtures_passed') is True,'provider_called_false':f.get('provider_called') is False,'held_out_false':w.get('held_out_accessed') is False and f.get('held_out_accessed') is False,'manifest_consistent':not MANIFEST.exists() or load(MANIFEST)==expected_manifest()};print(json.dumps({'all_passed':all(checks.values()),'checks':checks,'hashes':{'adapter':sha(Path(__file__)),'protocol':sha(PROTOCOL),'policy':sha(POLICY),'prompt':sha(PROMPT),'worklist':sha(WORKLIST),'fixtures':sha(FIXTURES)}},ensure_ascii=False,indent=2));
 if not all(checks.values()):raise ValueError('prepared_artifact_verification_failed')

def main()->int:
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--verify-prepared',action='store_true');g.add_argument('--freeze-manifest',action='store_true');g.add_argument('--execute',action='store_true');g.add_argument('--finalize',action='store_true');a=p.parse_args()
 if a.prepare:prepare();return 0
 if a.verify_prepared:verify();return 0
 if a.freeze_manifest:freeze_manifest();return 0
 if a.execute:return execute()
 return finalize()
if __name__=='__main__':raise SystemExit(main())
