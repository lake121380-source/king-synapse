#!/usr/bin/env python3
"""Reviewer B v3 successor after immutable v2 pre-content transport timeout."""
from __future__ import annotations
import argparse,hashlib,json,os,tempfile,urllib.request
from collections import Counter
from pathlib import Path
from phase7_execution_attempt_log import append_event,read_entries
import phase7_independent_pilot_reference_execution_v2 as base
ROOT=base.ROOT;CONFIG=base.CONFIG;DATA=base.DATA;REPORTS=base.REPORTS
DATASET=base.DATASET;A_SUB=base.submission('a');B_V2_NEG=base.negative('b')
PROTOCOL=CONFIG/'phase7_3_3_d_independent_pilot_reference_reviewer_b_execution_protocol_v3.json';POLICY=CONFIG/'phase7_3_3_d_independent_pilot_reference_reviewer_b_execution_policy_v3.json';PROMPT=CONFIG/'phase7_3_3_d_independent_pilot_reference_reviewer_prompt_v3.md';FIXTURES=REPORTS/'phase7_3_3_d_independent_pilot_reference_reviewer_b_contract_fixtures_v3.json';MANIFEST=REPORTS/'phase7_3_3_d_independent_pilot_reference_reviewer_b_execution_manifest_v3.json';ATTEMPTS=REPORTS/'phase7_3_3_d_independent_pilot_reference_reviewer_b_execution_attempts_v3.jsonl';CHECKS=REPORTS/'phase7_3_3_d_independent_pilot_reference_reviewer_b_cases_v3';SUB=DATA/'phase7_3_3_d_independent_pilot_reference_reviewer_b_submission_v3.json';RESULT=REPORTS/'phase7_3_3_d_independent_pilot_reference_reviewer_b_execution_result_v3.json';NEG=REPORTS/'phase7_3_3_d_independent_pilot_reference_reviewer_b_negative_result_v3.json'
BASE_URL='https://api.deepseek.com';CRED='DEEPSEEK_API_KEY';MODEL='deepseek-chat';TEMP=0;TOP_P=1;MAX_TOKENS=1600;TIMEOUT=300

def shab(b):return hashlib.sha256(b).hexdigest()
def sha(p):return shab(p.read_bytes())
def csha(v):return shab(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write_once(p,v):
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return shab(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p);return shab(b)
def write_text_once(p,t):
 b=t.encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_prompt_drift')
  return shab(b)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return shab(b)
def cp(c):return CHECKS/f'{c}.json'
def protocol_doc():return {'schema_version':3,'protocol_id':'phase7.3.3-d-independent-pilot-reference-reviewer-b-execution-protocol-v3','status':'frozen_successor_after_v2_transport_negative','predecessor_negative_sha256':sha(B_V2_NEG),'predecessor_failure':{'level':'level_0_transport','response_received':False,'completed_cases_preserved_as_partial_execution_evidence':11,'same_version_retry':False},'controlled_change':'new Reviewer B execution version using direct DeepSeek transport and model; no reuse of v2 partial semantic outputs','unchanged':['selected_dataset','whole_candidate_reference_representation','support_semantics','output_schema','case_isolation','blinding','no_repair','first_content_authoritative'],'reviewer':'b','model':MODEL,'provider':'api.deepseek.com','independence_note':'Reviewer A v2 remains frozen; Reviewer B v3 uses a different model/provider and cannot see A','reference_combination_authorized_if_b_v3_completes':True}
def policy_doc():return {'schema_version':3,'policy_id':'phase7.3.3-d-independent-pilot-reference-reviewer-b-execution-policy-v3','status':'frozen','case_count':40,'attempts_per_case':1,'provider':BASE_URL,'model':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'timeout_seconds':TIMEOUT,'response_format':{'type':'json_object'},'required_fields':sorted(base.TOP),'atomicity_required_value':'single_atomic_claim','same_case_citations_only':True,'semantic_retry':False,'output_repair':False,'raw_provider_response_stored':False,'v2_partial_outputs_used':False}
def prompt_text():return base.prompt_text().replace('Reviewer v2','Reviewer v3',1)
def fixtures():
 f=base.fixture_doc();f['schema_version']=3;f['fixture_suite_id']='phase7.3.3-d-independent-pilot-reference-reviewer-b-contract-fixtures-v3';return f
def gate():
 for p in [DATASET,A_SUB,B_V2_NEG]:
  if not p.exists():raise FileNotFoundError(p)
 n=load(B_V2_NEG)
 if n.get('failure_level')!='level_0_transport' or n.get('response_received') is not False or n.get('same_version_retry_allowed') is not False:raise ValueError('v2_negative_gate_invalid')
 if len(load(A_SUB).get('cases',[]))!=40:raise ValueError('reviewer_a_not_complete')
def prepare():
 gate();write_once(PROTOCOL,protocol_doc());write_once(POLICY,policy_doc());write_text_once(PROMPT,prompt_text());f=fixtures();write_once(FIXTURES,f);print(json.dumps({'status':f['status'],'fixtures':f'{f["passed"]}/{f["total"]}','provider_called':False,'controlled_change':'direct_deepseek_reviewer_b_v3'},indent=2))
def expected_manifest():return {'schema_version':3,'manifest_id':'phase7.3.3-d-independent-pilot-reference-reviewer-b-execution-manifest-v3','status':'frozen_not_started','reviewer':'b','provider':'api.deepseek.com','provider_base_url':BASE_URL,'model_requested':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'timeout_seconds':TIMEOUT,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(PROTOCOL),'policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'fixtures_sha256':sha(FIXTURES),'dataset_sha256':sha(DATASET),'reviewer_a_submission_sha256':sha(A_SUB),'reviewer_b_v2_negative_sha256':sha(B_V2_NEG),'case_count':40,'case_isolation':True,'other_reviewer_visible':False,'route_a_gold_visible':False,'arms_visible':False,'first_content_authoritative':True,'semantic_retry':False,'output_repair':False,'raw_provider_response_stored':False}
def freeze_manifest():print(json.dumps({'status':'PASS','manifest_sha256':write_once(MANIFEST,expected_manifest()),'provider_called':False},indent=2))
def call(key,system,user):
 payload={'model':MODEL,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE_URL+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as r:return r.read()
def parse(raw):
 env=json.loads(raw.decode());rep=env.get('model') if isinstance(env,dict) else None
 if not isinstance(rep,str) or 'deepseek' not in rep.lower():raise ValueError(f'provider_model_invalid:{rep}')
 choices=env.get('choices');msg=choices[0].get('message') if isinstance(choices,list) and choices and isinstance(choices[0],dict) else None;content=msg.get('content') if isinstance(msg,dict) else None
 if not isinstance(content,str) or not content.strip():raise ValueError('provider_content_missing')
 return rep,shab(content.encode()),json.loads(content)
def execute():
 if not MANIFEST.exists() or load(MANIFEST)!=expected_manifest():raise ValueError('manifest_invalid')
 if NEG.exists():raise ValueError('negative_exists_no_retry')
 if SUB.exists():print(json.dumps({'status':'already_completed_no_retry'},indent=2));return 0
 if read_entries(ATTEMPTS):raise ValueError('attempt_log_exists_without_terminal')
 key=os.environ.get(CRED,'').strip()
 if not key:raise ValueError('DEEPSEEK_API_KEY_missing')
 d=load(DATASET);txt=PROMPT.read_text(encoding='utf-8-sig');system=txt.split('## System message\n',1)[1].split('## User message template\n',1)[0].strip();mh=sha(MANIFEST);cases=[];models=set()
 for case in d['cases']:
  cid=case['case_id'];raw=b'';received=False
  try:
   packet={'case_id':cid,'query_context':case['query_context'],'candidate_sha256':case['candidate_sha256'],'candidate_text':case['candidate_text'],'evidence_bundle':case['evidence_bundle'],'valid_evidence_ids':case['valid_evidence_ids'],'allowed_claim_types':sorted(base.TYPES),'allowed_support_labels':sorted(base.LABELS),'allowed_reason_codes':sorted(base.REASONS)};raw=call(key,system,json.dumps(packet,ensure_ascii=False,separators=(',',':')));received=True;eh=shab(raw);rep,ch,obj=parse(raw);norm=base.normalize(case,obj,'b');write_once(cp(cid),{'schema_version':3,'status':'authoritative_success','reviewer':'b','case_id':cid,'manifest_sha256':mh,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'canonical_model_family':MODEL,'normalized_case_sha256':csha(norm),'normalized_case':norm,'raw_provider_response_stored':False});append_event({'event_type':'independent_reference_reviewer_b_v3_case_authoritative_success','manifest_sha256':mh,'reviewer':'b','case_id':cid,'response_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'normalized_output_sha256':csha(norm),'provider_reported_model':rep,'canonical_model_family':MODEL},ATTEMPTS);cases.append(norm);models.add(rep);print(f'Reference B v3 {len(cases)}/40 {cid}: {norm["candidate_reference_label"]}',flush=True)
  except Exception as e:
   reason=str(e);level='level_0_transport' if not received else ('level_1_provider_representation' if isinstance(e,json.JSONDecodeError) or reason.startswith('provider_') else 'level_2_reference_contract');append_event({'event_type':'independent_reference_reviewer_b_v3_case_authoritative_failure','manifest_sha256':mh,'reviewer':'b','case_id':cid,'response_received':received,'authoritative_result':True,'provider_envelope_sha256':shab(raw) if raw else None,'failure_level':level,'failure_reason':reason,'same_version_retry_allowed':False},ATTEMPTS);neg={'schema_version':3,'negative_result_id':'phase7.3.3-d-independent-pilot-reference-reviewer-b-negative-result-v3','status':'authoritative_negative_result','failed_case_id':cid,'completed_case_count':len(cases),'failure_level':level,'failure_reason':reason,'response_received':received,'same_version_retry_allowed':False,'reference_freeze_allowed':False};write_once(NEG,neg);print(json.dumps(neg,ensure_ascii=False,indent=2));return 4
 out={'schema_version':3,'submission_id':'phase7.3.3-d-independent-pilot-reference-reviewer-b-submission-v3','status':'completed_independent_blind_reference_review','reviewer':'b','model_requested':MODEL,'execution_manifest_sha256':mh,'case_count':40,'cases':cases,'candidate_label_counts':dict(sorted(Counter(x['candidate_reference_label'] for x in cases).items())),'total_claim_count':40,'other_reviewer_visible':False,'route_a_gold_visible':False,'arms_visible':False};write_once(SUB,out);write_once(RESULT,{'schema_version':3,'execution_id':'phase7.3.3-d-independent-pilot-reference-reviewer-b-execution-v3','status':'completed','reviewer':'b','manifest_sha256':mh,'submission_sha256':sha(SUB),'model_requested':MODEL,'provider_reported_models':sorted(models),'completed_case_count':40,'candidate_label_counts':out['candidate_label_counts'],'raw_provider_responses_stored':False});print(json.dumps({'status':'completed','cases':40,'labels':out['candidate_label_counts'],'submission_sha256':sha(SUB)},indent=2));return 0
def verify_prepared():
 gate();checks={'protocol':load(PROTOCOL)==protocol_doc(),'policy':load(POLICY)==policy_doc(),'prompt':PROMPT.read_text(encoding='utf-8-sig')==prompt_text(),'fixtures':load(FIXTURES)==fixtures(),'fixtures_pass':load(FIXTURES)['status']=='PASS'};print(json.dumps({'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks},indent=2));return all(checks.values())
def verify_execution():
 done=SUB.exists() and RESULT.exists();neg=NEG.exists();entries=read_entries(ATTEMPTS);checks={'manifest':MANIFEST.exists() and load(MANIFEST)==expected_manifest(),'terminal_xor':done!=neg,'attempts':bool(entries)}
 if done:checks.update({'cases_40':len(load(SUB).get('cases',[]))==40,'checkpoints_40':len(list(CHECKS.glob('*.json')))==40,'hash':load(RESULT).get('submission_sha256')==sha(SUB)})
 if neg:checks.update({'negative':load(NEG).get('status')=='authoritative_negative_result','no_retry':load(NEG).get('same_version_retry_allowed') is False})
 print(json.dumps({'status':'PASS' if all(checks.values()) else 'FAIL','terminal':'completed' if done else ('negative' if neg else 'missing'),'checks':checks,'attempt_entries':len(entries)},indent=2));return all(checks.values())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--verify-prepared',action='store_true');ap.add_argument('--freeze-manifest',action='store_true');ap.add_argument('--execute',action='store_true');ap.add_argument('--verify-execution',action='store_true');a=ap.parse_args()
 if sum([a.prepare,a.verify_prepared,a.freeze_manifest,a.execute,a.verify_execution])!=1:ap.error('choose one')
 if a.prepare:prepare();return 0
 if a.verify_prepared:return 0 if verify_prepared() else 1
 if a.freeze_manifest:freeze_manifest();return 0
 if a.execute:return execute()
 return 0 if verify_execution() else 1
if __name__=='__main__':raise SystemExit(main())
