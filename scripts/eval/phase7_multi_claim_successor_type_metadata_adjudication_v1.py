#!/usr/bin/env python3
"""Freeze and execute operation-based Type/Metadata adjudication for A v2/C v1 disagreements."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,tempfile,urllib.error,urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];CONFIG=ROOT/'crates/eval/config';PATTERN=ROOT/'crates/eval/datasets/pattern_extraction';REPORTS=ROOT/'crates/eval/reports'
STATE_IN=PATTERN/'phase7_3_3_d_support_stage_state_v47.json';READY_IN=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v58.json';SUB_A=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_a_submission_v2.json';SUB_C=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_c_submission_v1.json';BASE_WORK=PATTERN/'phase7_3_3_d_multi_claim_successor_type_metadata_blind_worklist_v2.json';ADJ_WORK=PATTERN/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_blind_worklist_a_v2_c_v1.json';AGREE_METRICS=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_agreement_a_v2_c_v1_metrics_v1.json';AGREE_RESULT=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_agreement_a_v2_c_v1_result_v1.json'
PROTOCOL=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_protocol_v1.json';SCHEMA=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_output_schema_v1.json';POLICY=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_execution_policy_v1.json';PROMPT=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudicator_prompt_v1.md';FIX=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_contract_fixtures_v1.json';MANIFEST=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_execution_manifest_v1.json';PREP_OUT=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_prepare_outcome_v1.json';PREP_REC=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_prepare_receipt_v1.json';ATTEMPTS=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_attempts_v1.jsonl';CASES=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_cases_v1';SUB=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_submission_v1.json';DECISIONS=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_decision_log_v1.json';REFERENCE=PATTERN/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_candidate_v1.json';RESULT=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_execution_result_v1.json';OUTCOME=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_execution_outcome_v1.json';RECEIPT=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_execution_receipt_v1.json';NEGATIVE=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_negative_result_v1.json';STATE_PREP=PATTERN/'phase7_3_3_d_support_stage_state_v48.json';READY_PREP=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v59.json';STATE_OUT=PATTERN/'phase7_3_3_d_support_stage_state_v49.json';READY_OUT=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v60.json'
BASE_URL='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';MODEL='gpt-5.4';CURRENT='construct_multi_claim_successor_type_metadata_adjudication_a_v2_c_v1';EXEC='execute_multi_claim_successor_type_metadata_adjudication_v1';NEXT='verify_multi_claim_successor_type_metadata_reference_candidate_v1';ROLES={'anchor','support','qualification','boundary','prediction','exception'};TYPES={'proposition','causal','prediction','scope','falsifiability','limitation','condition','exception'};CHOICES={'submission_a','submission_c'}
EXPECTED={STATE_IN:'3ad4143c17758e31b11f5bce2da5fb33e6186350b71572f126bb7ab57ff31fff',READY_IN:'4bc6679a2b1e5eaf9e1e41046acfbdc62680b8e8e76903d625e9093cbbd3cfe2',SUB_A:'2d8c7a21e04f1971becae4abc609d8da9f376f8f44c239d4a74f42abc838a53f',SUB_C:'bd44885bb6af1a27165b6fdc17560a1ac5b58fac3896d78ba81072c939e531e1',BASE_WORK:'22256af0efe38d04502760c396f259dd2f4efaba4fb0e30073994bca7c0c1dfb',ADJ_WORK:'652a6d461e0119f9fe8013fd90113b6993ae359f192174fa44dca7ad7fd34873',AGREE_METRICS:'b11fc6f17dc17769671c9a1967fa8dd526e78f80c20e6c4e7f0365b469bff6c3',AGREE_RESULT:'c80438f40b63c358bcc433e943c6b509c0572ea712eb7b1e71e2a109c2e27f15'}
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def jb(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def rel(p):return p.relative_to(ROOT).as_posix()
def once(p,x):
 b=jb(x)
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_artifact_mismatch:'+rel(p))
  return sha(p)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return hb(b)
def once_text(p,text):
 b=text.encode('utf-8')
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_artifact_mismatch:'+rel(p))
  return sha(p)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return hb(b)
def append(x):
 ATTEMPTS.parent.mkdir(parents=True,exist_ok=True)
 with ATTEMPTS.open('ab') as f:f.write(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()+b'\n')
def events():return [] if not ATTEMPTS.exists() else [json.loads(x) for x in ATTEMPTS.read_text(encoding='utf-8').splitlines() if x.strip()]
def strict(s):
 def pairs(xs):
  d={}
  for k,v in xs:
   if k in d:raise ValueError('duplicate_json_key:'+k)
   d[k]=v
  return d
 return json.loads(s,object_pairs_hook=pairs)
def canonical(got):
 if got==MODEL or got.startswith(MODEL+'-'):return MODEL
 raise ValueError('provider_reported_model_outside_requested_family:'+MODEL+':'+got)
def protocol():return {'schema_version':1,'protocol_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-protocol-v1','status':'frozen_before_provider_call','input_pair_anonymized':['submission_a','submission_c'],'unit':'frozen_boundary_reference_claim','adjudication_case_count':89,'case_isolation':True,'operation_representation':{'model_selects_submission_per_field':True,'model_copies_claim_id':False,'model_copies_excerpt':False,'adapter_reconstructs_labels_and_claim_id':True},'authorized_decision_fields':['claim_role','claim_type'],'choice_enum':['submission_a','submission_c'],'new_label_creation_authorized':False,'boundary_mutation_authorized':False,'claim_text_mutation_authorized':False,'support_or_evidence_visible':False,'first_provider_content_authoritative':True,'semantic_retry_authorized':False,'next_authorized_stage':EXEC,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def schema():return {'$schema':'https://json-schema.org/draft/2020-12/schema','title':'TypeMetadataAdjudicationOperationsV1','type':'object','additionalProperties':False,'required':['decisions'],'properties':{'decisions':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['claim_index','claim_role_choice','claim_type_choice'],'properties':{'claim_index':{'type':'integer','minimum':1},'claim_role_choice':{'enum':['submission_a','submission_c']},'claim_type_choice':{'enum':['submission_a','submission_c']}}}}}}
def policy():return {'schema_version':1,'policy_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-execution-policy-v1','authoritative_result_policy':{'first_returned_provider_response_per_case_is_authoritative':True,'invalid_json_or_schema_is_negative_result':True,'automatic_repair_authorized':False,'semantic_retry_authorized':False,'transport_failure_before_provider_content_may_resume':True},'model_requested':MODEL,'temperature':0,'top_p':1,'max_tokens':1600,'response_format':{'type':'json_object'},'case_isolation':True,'raw_provider_content_stored':False}
def prompt():return '''# Phase 7.3.3-D Multi-claim Successor Type/Metadata Adjudicator Prompt v1

## System message

You adjudicate only frozen claim_role and claim_type disagreements. Candidate text and claim excerpts are immutable. Evidence, support labels, old gold, arm outputs, and reviewer model identities are unavailable. For every disputed claim, choose submission_a or submission_c independently for claim_role and claim_type. Do not create a new label. Return one strict JSON object with exactly key decisions. Each decision must contain exactly claim_index, claim_role_choice, claim_type_choice. Include every disputed claim_index exactly once and no other index. No markdown or commentary.

Role meanings: anchor = primary asserted proposition; support = reason, mechanism, evidence-like premise, or subordinate supporting assertion; qualification = hedge or epistemic qualification; boundary = explicit applicability boundary; prediction = forward-looking role; exception = contradiction, reversal, failure case, or exception role.

Type meanings: proposition = general assertion/action/recommendation; causal = cause/effect; prediction = future or expected outcome; scope = domain/entity/time/quantity/applicability limit; falsifiability = observable test/refutation criterion; limitation = uncertainty, insufficiency, staleness, risk, inability to conclude; condition = prerequisite or if/when condition; exception = counterexample, contradiction, reversal, failure case, exception.

Example: {"decisions":[{"claim_index":2,"claim_role_choice":"submission_a","claim_type_choice":"submission_c"}]}

## User message template

Adjudicate this frozen Candidate and its disputed Type/Metadata fields.

{{CASE_JSON}}
'''
def normalize(case,payload):
 if not isinstance(payload,dict) or set(payload)!={'decisions'}:raise ValueError('root_must_contain_exactly_decisions')
 ds=payload['decisions'];items=case['disputed_items'];index={x['claim_index']:x for x in items}
 if not isinstance(ds,list) or len(ds)!=len(items):raise ValueError('decision_count_mismatch')
 seen=set();out=[]
 for i,x in enumerate(ds):
  if not isinstance(x,dict) or set(x)!={'claim_index','claim_role_choice','claim_type_choice'}:raise ValueError('decision_fields_invalid:'+str(i))
  idx=x['claim_index'];rc=x['claim_role_choice'];tc=x['claim_type_choice']
  if type(idx) is not int or idx not in index:raise ValueError('unknown_claim_index:'+str(idx))
  if idx in seen:raise ValueError('duplicate_claim_index:'+str(idx))
  if rc not in CHOICES or tc not in CHOICES:raise ValueError('invalid_choice:'+str(idx))
  item=index[idx];choice_to_source={'submission_a':'reviewer_a_v2','submission_c':'reviewer_c_v1'};role=item[choice_to_source[rc]]['claim_role'];typ=item[choice_to_source[tc]]['claim_type']
  if role not in ROLES or typ not in TYPES:raise ValueError('reconstructed_label_invalid:'+str(idx))
  seen.add(idx);out.append({'case_id':case['case_id'],'claim_index':idx,'claim_id':item['claim_id'],'source_span':item['source_span'],'source_excerpt':item['source_excerpt'],'disputed_fields':item['disputed_fields'],'claim_role_choice':rc,'claim_type_choice':tc,'claim_role':role,'claim_type':typ})
 if seen!=set(index):raise ValueError('claim_index_set_mismatch')
 out.sort(key=lambda x:x['claim_index']);return out
def build_cases():
 w=load(BASE_WORK);a=load(ADJ_WORK);by={}
 for x in a['items']:by.setdefault(x['case_id'],[]).append(x)
 out=[]
 for case in w['cases']:
  if case['case_id'] not in by:continue
  items=sorted(by[case['case_id']],key=lambda x:x['claim_index']);out.append({'case_id':case['case_id'],'candidate_text':case['candidate_text'],'frozen_claims':[{'claim_index':x['claim_index'],'source_excerpt':x['source_excerpt']} for x in case['claims']],'disputed_items':items,'valid_claim_indices':[x['claim_index'] for x in items]})
 if len(out)!=38 or sum(len(x['disputed_items']) for x in out)!=89:raise ValueError('adjudication_case_cardinality_invalid')
 return out
def fixtures():
 c={'case_id':'f','disputed_items':[{'claim_index':1,'claim_id':'c1','source_span':{'start':0,'end':1},'source_excerpt':'a','disputed_fields':['claim_role'],'reviewer_a_v2':{'claim_role':'anchor','claim_type':'proposition'},'reviewer_c_v1':{'claim_role':'support','claim_type':'proposition'}}]};g={'decisions':[{'claim_index':1,'claim_role_choice':'submission_a','claim_type_choice':'submission_c'}]};tests=[]
 def t(n,want,fn):
  ok=True;e=None
  try:fn()
  except Exception as x:ok=False;e=str(x)
  tests.append({'name':n,'expected_pass':want,'observed_pass':ok,'status':'PASS' if ok==want else 'FAIL','error':e})
 t('valid_operation',True,lambda:normalize(c,g));t('wrong_root',False,lambda:normalize(c,{'annotations':[]}));t('missing_decision',False,lambda:normalize(c,{'decisions':[]}));t('unknown_index',False,lambda:normalize(c,{'decisions':[{**g['decisions'][0],'claim_index':2}]}));t('invalid_choice',False,lambda:normalize(c,{'decisions':[{**g['decisions'][0],'claim_role_choice':'new'}]}));t('extra_field',False,lambda:normalize(c,{'decisions':[{**g['decisions'][0],'reason':'x'}]}));t('duplicate_json_key',False,lambda:strict('{"decisions":[],"decisions":[]}'));return {'schema_version':1,'fixture_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-contract-fixtures-v1','passed':sum(x['status']=='PASS' for x in tests),'total':len(tests),'status':'PASS' if all(x['status']=='PASS' for x in tests) else 'FAIL','results':tests}
def preflight():
 c={'exists:'+rel(p):p.exists() for p in EXPECTED}
 for p,d in EXPECTED.items():
  if p.exists():c['sha256:'+rel(p)]=sha(p)==d
 if STATE_IN.exists() and READY_IN.exists():c.update({'state_gate':load(STATE_IN).get('next_authorized_stage')==CURRENT,'readiness_gate':load(READY_IN).get('next_authorized_stage')==CURRENT})
 try:cases=build_cases();c.update({'38_cases':len(cases)==38,'89_items':sum(len(x['disputed_items']) for x in cases)==89})
 except Exception:c['case_build']=False
 f=[k for k,v in c.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(c),'failed':f}
def manifest():return {'schema_version':1,'manifest_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-execution-manifest-v1','status':'frozen_not_started','provider':'api.gpt.ge','provider_base_url':BASE_URL,'model_requested':MODEL,'temperature':0,'top_p':1,'max_tokens':1600,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(SELF),'protocol_sha256':sha(PROTOCOL),'schema_sha256':sha(SCHEMA),'policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'fixtures_sha256':sha(FIX),'reviewer_a_v2_submission_sha256':sha(SUB_A),'reviewer_c_v1_submission_sha256':sha(SUB_C),'base_worklist_sha256':sha(BASE_WORK),'adjudication_worklist_sha256':sha(ADJ_WORK),'agreement_metrics_sha256':sha(AGREE_METRICS),'agreement_result_sha256':sha(AGREE_RESULT),'case_count':38,'claim_count':89,'operation_representation':True,'first_provider_content_authoritative':True,'semantic_retry_authorized':False,'raw_provider_content_stored':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def prepare():
 p=preflight()
 if p['status']!='PASS':raise ValueError('preflight_failed:'+','.join(p['failed']))
 f=fixtures()
 if f['status']!='PASS':raise ValueError('fixtures_failed')
 psha=once(PROTOCOL,protocol());ssha=once(SCHEMA,schema());esha=once(POLICY,policy());prsha=once_text(PROMPT,prompt());fsha=once(FIX,f);msha=once(MANIFEST,manifest());s=copy.deepcopy(load(STATE_IN));r=copy.deepcopy(load(READY_IN));line={'multi_claim_successor_type_metadata_adjudication_protocol_v1_sha256':psha,'multi_claim_successor_type_metadata_adjudication_output_schema_v1_sha256':ssha,'multi_claim_successor_type_metadata_adjudication_execution_policy_v1_sha256':esha,'multi_claim_successor_type_metadata_adjudicator_prompt_v1_sha256':prsha,'multi_claim_successor_type_metadata_adjudication_contract_fixtures_v1_sha256':fsha,'multi_claim_successor_type_metadata_adjudication_execution_manifest_v1_sha256':msha};s.setdefault('artifact_lineage',{}).update(line);r.setdefault('artifact_lineage',{}).update(line);u={'status':'multi_claim_successor_type_metadata_adjudication_prepared','next_authorized_stage':EXEC,'successor_type_metadata_adjudication_protocol_frozen':True,'successor_type_metadata_adjudication_manifest_frozen':True,'successor_type_metadata_adjudication_provider_called':False,'successor_type_metadata_adjudication_completed':False,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};s.update(u);r.update(u);s.update({'schema_version':48,'state_id':'phase7.3.3-d-support-stage-state-v48'});r.update({'schema_version':59,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v59'});st=once(STATE_PREP,s);rd=once(READY_PREP,r);o={'schema_version':1,'outcome_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-prepare-outcome-v1','status':'PASS','manifest_sha256':msha,'state_sha256':st,'readiness_sha256':rd,'next_authorized_stage':EXEC,'provider_called':False};osha=once(PREP_OUT,o);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-prepare-receipt-v1','status':'PASS','outcome_sha256':osha,'manifest_sha256':msha,'state_sha256':st,'readiness_sha256':rd,'next_authorized_stage':EXEC};return {'status':'PASS','manifest_sha256':msha,'prepare_receipt_sha256':once(PREP_REC,rec),'state_sha256':st,'readiness_sha256':rd,'next_authorized_stage':EXEC}
def verify_prepare():
 ps=[PROTOCOL,SCHEMA,POLICY,PROMPT,FIX,MANIFEST,PREP_OUT,PREP_REC,STATE_PREP,READY_PREP];c={'exists:'+rel(p):p.exists() for p in ps}
 if all(c.values()):m=load(MANIFEST);s=load(STATE_PREP);r=load(READY_PREP);c.update({'adapter':m.get('adapter_sha256')==sha(SELF),'protocol':m.get('protocol_sha256')==sha(PROTOCOL),'schema':m.get('schema_sha256')==sha(SCHEMA),'policy':m.get('policy_sha256')==sha(POLICY),'prompt':m.get('prompt_sha256')==sha(PROMPT),'38_89':m.get('case_count')==38 and m.get('claim_count')==89,'state_gate':s.get('next_authorized_stage')==EXEC,'readiness_gate':r.get('next_authorized_stage')==EXEC,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_unauthorized':s.get('runtime_integration_authorized') is False})
 f=[k for k,v in c.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(c),'failed':f}
def split_prompt():
 x=PROMPT.read_text(encoding='utf-8-sig');sm='## System message\n';um='## User message template\n';return x.split(sm,1)[1].split(um,1)[0].strip(),x.split(um,1)[1].strip()
def request(key,system,user):
 p={'model':MODEL,'messages':[{'role':'system','content':system},{'role':'user','content':user}],'temperature':0,'top_p':1,'max_tokens':1600,'response_format':{'type':'json_object'}};q=urllib.request.Request(BASE_URL+'/chat/completions',data=json.dumps(p,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(q,timeout=300) as r:return r.read()
def cp(cid):return CASES/f'{cid}.json'
def seen(ms,cid):return any(x.get('manifest_sha256')==ms and x.get('case_id')==cid and x.get('response_received') is True and x.get('authoritative_result') is True for x in events())
def finalize(status,nxt,subsha=None,resha=None,refsha=None,negsha=None):
 s=copy.deepcopy(load(STATE_PREP));r=copy.deepcopy(load(READY_PREP));line={}
 for k,v in [('multi_claim_successor_type_metadata_adjudication_submission_v1_sha256',subsha),('multi_claim_successor_type_metadata_adjudication_execution_result_v1_sha256',resha),('multi_claim_successor_type_metadata_reference_candidate_v1_sha256',refsha),('multi_claim_successor_type_metadata_adjudication_negative_result_v1_sha256',negsha)]:
  if v:line[k]=v
 s.setdefault('artifact_lineage',{}).update(line);r.setdefault('artifact_lineage',{}).update(line);done=status=='multi_claim_successor_type_metadata_adjudication_completed';u={'status':status,'next_authorized_stage':nxt,'successor_type_metadata_adjudication_provider_called':True,'successor_type_metadata_adjudication_completed':done,'successor_type_metadata_reference_candidate_created':done,'successor_type_metadata_reference_frozen':False,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};s.update(u);r.update(u);s.update({'schema_version':49,'state_id':'phase7.3.3-d-support-stage-state-v49'});r.update({'schema_version':60,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v60'});return once(STATE_OUT,s),once(READY_OUT,r)
def execute():
 v=verify_prepare()
 if v['status']!='PASS':raise ValueError('prepare_not_verified:'+','.join(v['failed']))
 key=os.environ.get(CRED)
 if not key:raise ValueError('missing_credential:'+CRED)
 m=load(MANIFEST);ms=sha(MANIFEST);frozen={SELF:m['adapter_sha256'],PROTOCOL:m['protocol_sha256'],SCHEMA:m['schema_sha256'],POLICY:m['policy_sha256'],PROMPT:m['prompt_sha256'],FIX:m['fixtures_sha256'],SUB_A:m['reviewer_a_v2_submission_sha256'],SUB_C:m['reviewer_c_v1_submission_sha256'],BASE_WORK:m['base_worklist_sha256'],ADJ_WORK:m['adjudication_worklist_sha256'],AGREE_METRICS:m['agreement_metrics_sha256'],AGREE_RESULT:m['agreement_result_sha256']}
 for p,d in frozen.items():
  if sha(p)!=d:raise ValueError('manifest_hash_mismatch:'+rel(p))
 system,ut=split_prompt();results=[];allrows=[];models=set()
 for case in build_cases():
  cid=case['case_id'];p=cp(cid)
  if p.exists():d=load(p);rows=normalize(case,{'decisions':[{k:x[k] for k in ['claim_index','claim_role_choice','claim_type_choice']} for x in d['decisions']]});results.append(d['case_result']);allrows.extend(rows);models.add(d['provider_reported_model']);continue
  if seen(ms,cid):raise ValueError('authoritative_content_seen_without_checkpoint:'+cid)
  visible={'case_id':cid,'candidate_text':case['candidate_text'],'frozen_claims':case['frozen_claims'],'disputed_claims':[{'claim_index':x['claim_index'],'source_excerpt':x['source_excerpt'],'disputed_fields':x['disputed_fields'],'submission_a':x['reviewer_a_v2'],'submission_c':x['reviewer_c_v1']} for x in case['disputed_items']]};user=ut.replace('{{CASE_JSON}}',json.dumps(visible,ensure_ascii=False,indent=2));raw=None;esha=None;csha=None
  try:
   raw=request(key,system,user);esha=hb(raw);env=json.loads(raw.decode());content=env.get('choices',[{}])[0].get('message',{}).get('content')
   if not isinstance(content,str):raise ValueError('provider_content_not_string')
   csha=hb(content.encode());append({'event_type':'multi_claim_type_metadata_adjudication_provider_content_received','manifest_sha256':ms,'case_id':cid,'response_received':True,'authoritative_result':True,'provider_envelope_sha256':esha,'provider_content_sha256':csha});reported=env.get('model') or 'unknown';canon=canonical(reported);rows=normalize(case,strict(content));cr={'case_id':cid,'decision_count':len(rows),'provider_reported_model':reported,'canonical_model_family':canon,'provider_envelope_sha256':esha,'provider_content_sha256':csha,'normalized_decisions_sha256':hb(jb(rows)),'status':'PASS'};doc={'schema_version':1,'checkpoint_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-{cid}-v1','manifest_sha256':ms,'case_id':cid,'provider_reported_model':reported,'case_result':cr,'decisions':rows,'raw_provider_content_stored':False};once(p,doc);results.append(cr);allrows.extend(rows);models.add(reported)
  except urllib.error.HTTPError as e:append({'event_type':'multi_claim_type_metadata_adjudication_transport_failure','manifest_sha256':ms,'case_id':cid,'status':f'http_{e.code}','response_received':False,'authoritative_result':False});return {'status':'TRANSPORT_FAILURE_RESUMABLE','case_id':cid,'http_status':e.code}
  except Exception as e:
   received=raw is not None;append({'event_type':'multi_claim_type_metadata_adjudication_experimental_failure' if received else 'multi_claim_type_metadata_adjudication_adapter_failure','manifest_sha256':ms,'case_id':cid,'status':type(e).__name__,'failure_code':str(e)[:300],'response_received':received,'authoritative_result':received,'provider_envelope_sha256':esha,'provider_content_sha256':csha})
   if not received:raise
   neg={'schema_version':1,'negative_result_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-negative-result-v1','status':'authoritative_negative_result','manifest_sha256':ms,'case_id':cid,'failure_type':type(e).__name__,'failure_code':str(e)[:300],'response_received':True,'provider_envelope_sha256':esha,'provider_content_sha256':csha,'raw_provider_content_stored':False,'same_version_retry_authorized':False,'type_metadata_adjudication_capability_conclusion_authorized':False};ns=once(NEGATIVE,neg);ss,rs=finalize('authoritative_negative_result','blocked_authoritative_negative_result',negsha=ns);return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','case_id':cid,'negative_result_sha256':ns,'state_sha256':ss,'readiness_sha256':rs,'same_version_retry_authorized':False}
 if {canonical(x) for x in models}!={MODEL} or len(results)!=38 or len(allrows)!=89:raise ValueError('completed_cardinality_or_model_invalid')
 sub={'schema_version':1,'submission_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-submission-v1','status':'completed','manifest_sha256':ms,'completed_case_count':38,'decision_count':89,'operation_representation':True,'decisions':allrows};subsha=once(SUB,sub);A={x['claim_id']:x for x in load(SUB_A)['annotations']};C={x['claim_id']:x for x in load(SUB_C)['annotations']};D={x['claim_id']:x for x in allrows};w=load(BASE_WORK);claims=[]
 for case in w['cases']:
  for x in case['claims']:
   cid=x['claim_id'];a=A[cid];c=C[cid]
   if a['claim_role']==c['claim_role'] and a['claim_type']==c['claim_type']:role=a['claim_role'];typ=a['claim_type'];prov='reviewer_agreement'
   else:
    if cid not in D:raise ValueError('missing_adjudication_decision:'+cid)
    role=D[cid]['claim_role'];typ=D[cid]['claim_type'];prov='model_adjudication_operation_choice'
   claims.append({'case_id':case['case_id'],'claim_index':x['claim_index'],'reference_claim_id':cid,'source_span':x['source_span'],'source_excerpt':x['source_excerpt'],'claim_role':role,'claim_type':typ,'claim_origin':'explicit','decision_provenance':prov})
 if len(claims)!=240 or len({x['reference_claim_id'] for x in claims})!=240:raise ValueError('reference_cardinality_invalid')
 log={'schema_version':1,'decision_log_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-decision-log-v1','decision_count':89,'claim_role_choice_counts':dict(Counter(x['claim_role_choice'] for x in allrows)),'claim_type_choice_counts':dict(Counter(x['claim_type_choice'] for x in allrows)),'decisions':allrows};logsha=once(DECISIONS,log);ref={'schema_version':1,'reference_id':'phase7.3.3-d-multi-claim-successor-type-metadata-reference-candidate-v1','status':'model_adjudicated_type_metadata_reference_candidate_not_gold','boundary_reference_immutable':True,'claim_count':240,'agreement_claim_count':151,'adjudicated_claim_count':89,'adjudication_submission_sha256':subsha,'adjudication_decision_log_sha256':logsha,'claims':claims,'support_labels_present':False,'evidence_present':False};refsha=once(REFERENCE,ref);res={'schema_version':1,'result_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-execution-result-v1','status':'PASS','manifest_sha256':ms,'submission_sha256':subsha,'decision_log_sha256':logsha,'reference_candidate_sha256':refsha,'completed_case_count':38,'decision_count':89,'reference_claim_count':240,'provider_reported_models':sorted(models),'canonical_model_family':MODEL,'case_results':results};resha=once(RESULT,res);out={'schema_version':1,'outcome_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-execution-outcome-v1','status':'PASS','execution_result_sha256':resha,'reference_candidate_sha256':refsha,'next_authorized_stage':NEXT,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};osha=once(OUTCOME,out);ss,rs=finalize('multi_claim_successor_type_metadata_adjudication_completed',NEXT,subsha,resha,refsha);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-multi-claim-successor-type-metadata-adjudication-execution-receipt-v1','status':'PASS','manifest_sha256':ms,'submission_sha256':subsha,'decision_log_sha256':logsha,'reference_candidate_sha256':refsha,'execution_result_sha256':resha,'execution_outcome_sha256':osha,'state_sha256':ss,'readiness_sha256':rs,'next_authorized_stage':NEXT};return {'status':'PASS','completed_case_count':38,'decision_count':89,'reference_claim_count':240,'submission_sha256':subsha,'reference_candidate_sha256':refsha,'execution_result_sha256':resha,'receipt_sha256':once(RECEIPT,rec),'state_sha256':ss,'readiness_sha256':rs,'next_authorized_stage':NEXT}
def verify_execution():
 ps=[MANIFEST,SUB,DECISIONS,REFERENCE,RESULT,OUTCOME,RECEIPT,STATE_OUT,READY_OUT];c={'exists:'+rel(p):p.exists() for p in ps}
 if all(c.values()):m=load(MANIFEST);sub=load(SUB);ref=load(REFERENCE);res=load(RESULT);out=load(OUTCOME);rec=load(RECEIPT);s=load(STATE_OUT);r=load(READY_OUT);c.update({'adapter':m.get('adapter_sha256')==sha(SELF),'38_89':sub.get('completed_case_count')==res.get('completed_case_count')==38 and sub.get('decision_count')==res.get('decision_count')==89,'reference_240':ref.get('claim_count')==len(ref.get('claims',[]))==240 and len({x['reference_claim_id'] for x in ref['claims']})==240,'boundary_replay':all(x['source_excerpt']==case['candidate_text'][x['source_span']['start']:x['source_span']['end']] for case in load(BASE_WORK)['cases'] for x in ref['claims'] if x['case_id']==case['case_id']),'lineage':res.get('submission_sha256')==rec.get('submission_sha256')==sha(SUB) and res.get('reference_candidate_sha256')==out.get('reference_candidate_sha256')==sha(REFERENCE),'state_gate':s.get('next_authorized_stage')==NEXT,'readiness_gate':r.get('next_authorized_stage')==NEXT,'not_gold':ref.get('status')=='model_adjudicated_type_metadata_reference_candidate_not_gold','confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_unauthorized':s.get('runtime_integration_authorized') is False})
 f=[k for k,v in c.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(c),'failed':f}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--preflight',action='store_true');g.add_argument('--fixtures',action='store_true');g.add_argument('--prepare',action='store_true');g.add_argument('--verify-prepare',action='store_true');g.add_argument('--execute',action='store_true');g.add_argument('--verify-execution',action='store_true');a=p.parse_args();x=preflight() if a.preflight else fixtures() if a.fixtures else prepare() if a.prepare else verify_prepare() if a.verify_prepare else execute() if a.execute else verify_execution();print(json.dumps(x,ensure_ascii=False,indent=2));return 0 if x.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE'} else 1
if __name__=='__main__':raise SystemExit(main())
