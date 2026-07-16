#!/usr/bin/env python3
"""Freeze and execute independent Type/Metadata Review v2."""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, os, sys, urllib.error, urllib.request
from pathlib import Path
from typing import Any

SELF=Path(__file__).resolve(); ROOT=SELF.parents[2]
CONFIG=ROOT/'crates/eval/config'; PATTERN=ROOT/'crates/eval/datasets/pattern_extraction'; REPORTS=ROOT/'crates/eval/reports'
STATE_IN=PATTERN/'phase7_3_3_d_support_stage_state_v41.json'; READY_IN=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v52.json'
REFERENCE=PATTERN/'phase7_3_3_d_multi_claim_successor_boundary_reference_candidate_v1.json'; SOURCE=PATTERN/'phase7_3_3_d_multi_claim_successor_boundary_blind_worklist_v1.json'
SCOPE=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_scope_decision_v1.json'; PROTOCOL=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_review_protocol_v2.json'
SCHEMA=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_review_output_schema_v2.json'; POLICY=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_review_execution_policy_v2.json'
PROMPT=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_prompt_v2.md'; WORKLIST=PATTERN/'phase7_3_3_d_multi_claim_successor_type_metadata_blind_worklist_v2.json'
FIXTURES=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_review_contract_fixtures_v2.json'; PREP_MANIFEST=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_review_prepare_manifest_v2.json'
PREP_OUTCOME=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_review_prepare_outcome_v2.json'; PREP_RECEIPT=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_review_prepare_receipt_v2.json'
STATE_PREP=PATTERN/'phase7_3_3_d_support_stage_state_v42.json'; READY_PREP=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v53.json'
ATTEMPT_LOG=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_attempts_v2.jsonl'
CURRENT='construct_multi_claim_successor_type_metadata_review_v2'; EXEC_A='execute_multi_claim_successor_independent_type_metadata_review_a_v2'; EXEC_B='execute_multi_claim_successor_independent_type_metadata_review_b_v2'; AGREEMENT='construct_multi_claim_successor_type_metadata_agreement_v2'
BASE_URL='https://api.gpt.ge/v1'; CRED='PHASE7_ATOMIC_JUDGE_API_KEY'; REVIEWERS={'a':'gpt-4.1','b':'gemini-2.5-pro'}
ROLES={'anchor','support','qualification','boundary','prediction','exception'}; TYPES={'proposition','causal','prediction','scope','falsifiability','limitation','condition','exception'}
ENTRY_PROTOCOL=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_review_v2_entry_protocol_v1.json'; FAILURE_CLASS=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_b_failure_classification_v1.json'; ENTRY_RECEIPT=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_review_v2_entry_receipt_v1.json'
EXPECTED={STATE_IN:'83e003afbbb7938cba6e0ff7dc07eac18cedc861dbc3bfc08b4d89d28a7dbe72',READY_IN:'1ed6c9f24033c896770747ca8343c1c4d09447514e7a4e44bee1acddd0930125',REFERENCE:'e93abf01b54a6276a4f5ae2e370fd891548218a96022129a20030280e034b2ac',SOURCE:'13656be468d8c48c36967c689de4d0fdad09cd7f9ba9efe619682863659a2405',ENTRY_PROTOCOL:'c93b79f02a14f595941369aa9b40acceac6cb4f70cf1385d54e0c16e288bb65e',FAILURE_CLASS:'ff06ec52418a0c39e7d42fefc670dfbd3b881369f54907842fefeeca6a064b0f',ENTRY_RECEIPT:'607ecfb07d13c9f519a047bfefd16f6d5dbbd86ebd3e3119666d9fddaedb2595'}

def hb(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha(p:Path)->str:return hb(p.read_bytes())
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8-sig'))
def jb(x:Any)->bytes:return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def rel(p:Path)->str:return p.relative_to(ROOT).as_posix()
def write_once(p:Path,x:Any)->str:
 b=x if isinstance(x,bytes) else jb(x)
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'refusing_to_overwrite_frozen_artifact:{p.name}')
  return sha(p)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return hb(b)
def append_event(x:dict[str,Any])->None:
 ATTEMPT_LOG.parent.mkdir(parents=True,exist_ok=True)
 with ATTEMPT_LOG.open('ab') as f:f.write((json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n').encode());f.flush();os.fsync(f.fileno())
def events()->list[dict[str,Any]]:
 return [] if not ATTEMPT_LOG.exists() else [json.loads(x) for x in ATTEMPT_LOG.read_text(encoding='utf-8').splitlines() if x.strip()]

def scope_doc():
 return {'schema_version':1,'decision_id':'phase7.3.3-d-multi-claim-successor-type-metadata-scope-decision-v1','status':'frozen_before_any_type_metadata_provider_call','reviewed_fields':['claim_role','claim_type'],'deterministic_fields':{'claim_origin':'explicit','basis':'every frozen claim is an exact contiguous excerpt'},'deferred_fields':{'material_error':'derived after Support adjudication'},'out_of_scope_fields':{'anchor_group':'not in successor reference schema v1','support_label':'Support Review','citation':'Support Review','evidence':'blind'},'boundary_mutation_authorized':False}
def protocol_doc():
 return {'schema_version':1,'protocol_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-protocol-v2','status':'frozen_before_any_type_metadata_provider_call','object_of_study':'claim_role_and_claim_type_on_frozen_atomic_boundaries','boundary_reference_candidate_sha256':sha(REFERENCE),'reviewed_fields':['claim_role','claim_type'],'claim_role_enum':sorted(ROLES),'claim_type_enum':sorted(TYPES),'review_design':{'independent_reviewers':2,'models':REVIEWERS,'case_isolation':True,'both_manifests_frozen_before_reviewer_a':True},'representation':{'model_copies_excerpt':False,'model_references_frozen_claim_id':True,'each_claim_exactly_once':True},'next_stage':AGREEMENT}
def schema_doc():
 return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-output-schema-v2','type':'object','required':['annotations'],'properties':{'annotations':{'type':'array','minItems':1,'items':{'type':'object','required':['claim_index','claim_role','claim_type'],'properties':{'claim_id':{'type':'string','minLength':1},'claim_role':{'enum':sorted(ROLES)},'claim_type':{'enum':sorted(TYPES)}},'additionalProperties':False}}},'additionalProperties':False}
def policy_doc():
 return {'schema_version':1,'policy_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-execution-policy-v2','status':'frozen_before_any_type_metadata_provider_call','provider':'api.gpt.ge','provider_base_url':BASE_URL,'credential_env_name':CRED,'temperature':0,'top_p':1,'max_tokens':1600,'response_format':{'type':'json_object'},'case_isolation':True,'first_provider_content_authoritative':True,'same_version_retry_after_content_authorized':False,'transport_retry_before_content_authorized':True,'raw_provider_content_stored':False,'hashes_stored':['provider_envelope_sha256','provider_content_sha256']}
def prompt_text():return '''# Phase 7.3.3-D Multi-claim Successor Type/Metadata Reviewer Prompt v1

## System message

You are an independent Claim Type and Structural Role Reviewer. Atomic Claim boundaries are frozen. Classify every supplied claim exactly once. Do not merge, split, delete, add, paraphrase, or reproduce Claim text. Do not judge support, correctness, material error, citations, evidence, or Boundary quality.

Return strict compact JSON with exactly one root field `annotations`. Every item must contain exactly `claim_id`, `claim_role`, and `claim_type`. Copy each supplied claim_id exactly. Return no Markdown, rationale, confidence, excerpts, spans, or extra fields.

Claim role: anchor = primary situation, decision, request, or conclusion (multiple allowed); support = observation, prior event, preference, or reason bearing on another Claim; qualification = narrows entity, time, applicability, priority, or context; boundary = insufficiency, uncertainty, non-applicability, caution, prohibition, or limiting negative boundary; prediction = future or expected outcome; exception = counterexample, reversal, failure, or contrary case.

Claim type: proposition = fact, preference, request, recommendation, decision, or general assertion not better classified below; causal = explicit cause, influence, explanation, or responsibility; prediction = future or expected outcome; scope = explicit domain, entity-set, time, quantity, or applicability limit/generalization; falsifiability = observable test, success criterion, or refutation criterion; limitation = uncertainty, missing information, insufficiency, staleness, risk, or inability to conclude; condition = prerequisite or if/when condition; exception = counterexample, contradiction, reversal, failure case, or exception.

Role and type are independent. Use proposition as fallback. Recommendations and imperative-like decision tokens are propositions unless they explicitly encode another type. For snake_case Claims, classify only semantic content encoded by the token; do not invent details.

Example: {"annotations":[{"claim_id":"claim-001","claim_role":"anchor","claim_type":"proposition"}]}

## User message template

Classify this frozen Candidate and its frozen Atomic Claims.

{{CASE_JSON}}
'''

def make_worklist():
 ref=load(REFERENCE);src=load(SOURCE);by={}
 for x in ref['claims']:by.setdefault(x['case_id'],[]).append(x)
 out=[]
 for c in src['cases']:
  cs=sorted(by[c['case_id']],key=lambda x:(x['source_span']['start'],x['source_span']['end']))
  claims=[]
  for x in cs:
   s,e=x['source_span']['start'],x['source_span']['end']
   if c['candidate_text'][s:e]!=x['source_excerpt']:raise ValueError('excerpt_replay_failed:'+x['reference_claim_id'])
   claims.append({'claim_id':x['reference_claim_id'],'source_span':x['source_span'],'source_excerpt':x['source_excerpt']})
  out.append({'successor_index':c['successor_index'],'case_id':c['case_id'],'candidate_text':c['candidate_text'],'candidate_sha256':c['candidate_sha256'],'claims':claims,'valid_claim_ids':[x['claim_id'] for x in claims]})
 if len(out)!=40 or sum(len(x['claims']) for x in out)!=240:raise ValueError('worklist_cardinality_invalid')
 return {'schema_version':1,'worklist_id':'phase7.3.3-d-multi-claim-successor-type-metadata-blind-worklist-v1','status':'frozen_type_metadata_review_only','boundary_reference_candidate_sha256':sha(REFERENCE),'case_count':40,'claim_count':240,'cases':out,'evidence_present':False,'support_labels_present':False,'old_gold_present':False,'arm_outputs_present':False,'other_reviewer_output_present':False,'boundary_mutation_authorized':False}
def strict_load(s:str)->Any:
 def hook(pairs):
  d={}
  for k,v in pairs:
   if k in d:raise ValueError('duplicate_json_key:'+k)
   d[k]=v
  return d
 return json.loads(s,object_pairs_hook=hook)
def normalize(case,payload,reviewer):
 if not isinstance(payload,dict) or set(payload)!={'annotations'}:raise ValueError('root_must_contain_exactly_annotations')
 a=payload['annotations'];expected=case['valid_claim_ids'];index={x['claim_id']:x for x in case['claims']}
 if not isinstance(a,list):raise ValueError('annotations_must_be_array')
 if len(a)!=len(expected):raise ValueError('annotation_count_mismatch')
 seen=set();out=[]
 for i,x in enumerate(a):
  if not isinstance(x,dict) or set(x)!={'claim_id','claim_role','claim_type'}:raise ValueError(f'annotation_fields_invalid:{i}')
  cid=x['claim_id'];role=x['claim_role'];typ=x['claim_type']
  if cid not in index:raise ValueError(f'unknown_claim_id:{i}')
  if cid in seen:raise ValueError('duplicate_claim_id:'+cid)
  if role not in ROLES:raise ValueError(f'invalid_claim_role:{cid}:{role}')
  if typ not in TYPES:raise ValueError(f'invalid_claim_type:{cid}:{typ}')
  seen.add(cid);src=index[cid];out.append({'case_id':case['case_id'],'claim_id':cid,'source_span':src['source_span'],'source_excerpt':src['source_excerpt'],'claim_role':role,'claim_type':typ,'claim_origin':'explicit','reviewer':reviewer})
 if seen!=set(expected):raise ValueError('claim_id_set_mismatch')
 order={x:i for i,x in enumerate(expected)};out.sort(key=lambda x:order[x['claim_id']]);return out

def fixtures():
 c={'case_id':'f','claims':[{'claim_id':'c1','source_span':{'start':0,'end':1},'source_excerpt':'a'},{'claim_id':'c2','source_span':{'start':2,'end':3},'source_excerpt':'b'}],'valid_claim_ids':['c1','c2']}
 g={'annotations':[{'claim_id':'c1','claim_role':'anchor','claim_type':'proposition'},{'claim_id':'c2','claim_role':'boundary','claim_type':'limitation'}]}
 tests=[('valid',g,True),('wrong_root',{'claims':g['annotations']},False),('extra_root',{**g,'x':1},False),('missing',{'annotations':g['annotations'][:1]},False),('duplicate',{'annotations':[g['annotations'][0],g['annotations'][0]]},False),('unknown',{'annotations':[{**g['annotations'][0],'claim_id':'c3'},g['annotations'][1]]},False),('extra_field',{'annotations':[{**g['annotations'][0],'reason':'x'},g['annotations'][1]]},False),('bad_role',{'annotations':[{**g['annotations'][0],'claim_role':'central'},g['annotations'][1]]},False),('bad_type',{'annotations':[{**g['annotations'][0],'claim_type':'opinion'},g['annotations'][1]]},False),('non_array',{'annotations':{}},False)]
 rows=[]
 for n,p,want in tests:
  ok=True;err=None
  try:normalize(c,p,'f')
  except Exception as e:ok=False;err=str(e)
  rows.append({'name':n,'expected_pass':want,'observed_pass':ok,'status':'PASS' if ok==want else 'FAIL','error':err})
 dup=False
 try:strict_load('{"annotations":[],"annotations":[]}')
 except Exception:dup=True
 rows.append({'name':'duplicate_json_key','expected_pass':False,'observed_pass':not dup,'status':'PASS' if dup else 'FAIL'})
 return {'schema_version':1,'fixture_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-contract-fixtures-v2','passed':sum(x['status']=='PASS' for x in rows),'total':len(rows),'status':'PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL','results':rows}
def manifest_path(r):return REPORTS/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_execution_manifest_v2.json'
def checkpoint(r,c):return REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_cases_v2'/r/f'{c}.json'
def submission(r):return REPORTS/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_submission_v2.json'
def result_path(r):return REPORTS/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_execution_result_v2.json'
def outcome_path(r):return REPORTS/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_execution_outcome_v2.json'
def receipt_path(r):return REPORTS/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_execution_receipt_v2.json'
def negative_path(r):return REPORTS/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_negative_result_v2.json'
def manifest_doc(r):
 return {'schema_version':1,'manifest_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-reviewer-{r}-execution-manifest-v2','status':'frozen_not_started','reviewer':r,'provider':'api.gpt.ge','provider_base_url':BASE_URL,'model_requested':REVIEWERS[r],'temperature':0,'top_p':1,'max_tokens':1600,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(SELF),'scope_decision_sha256':sha(SCOPE),'protocol_sha256':sha(PROTOCOL),'schema_sha256':sha(SCHEMA),'policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'worklist_sha256':sha(WORKLIST),'fixtures_sha256':sha(FIXTURES),'boundary_reference_candidate_sha256':sha(REFERENCE),'case_count':40,'claim_count':240,'case_isolation':True,'first_provider_content_authoritative':True,'semantic_retry_authorized':False,'raw_provider_content_stored':False,'evidence_visible':False,'support_labels_visible':False,'other_reviewer_visible':False,'boundary_mutation_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def preflight():
 missing=[rel(p) for p in EXPECTED if not p.exists()];mismatch={rel(p):{'expected':d,'actual':sha(p)} for p,d in EXPECTED.items() if p.exists() and sha(p)!=d};s=load(STATE_IN) if STATE_IN.exists() else {};r=load(READY_IN) if READY_IN.exists() else {};ref=load(REFERENCE) if REFERENCE.exists() else {}
 checks={'inputs_present':not missing,'hashes_match':not mismatch,'state_authorized':s.get('next_authorized_stage')==CURRENT,'readiness_authorized':r.get('next_authorized_stage')==CURRENT,'reference_40_240':ref.get('case_count')==40 and ref.get('claim_count')==240 and len(ref.get('claims',[]))==240,'reference_not_gold':ref.get('boundary_gold_frozen') is False,'type_metadata_pending':ref.get('type_metadata_review_completed') is False,'support_absent':ref.get('support_labels_present') is False,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_unauthorized':s.get('runtime_integration_authorized') is False}
 failed=[k for k,v in checks.items() if not v];return {'status':'PASS' if not failed else 'FAIL','checks':checks,'failed':failed,'missing':missing,'mismatch':mismatch}
def prepare_run():
 pf=preflight()
 if pf['status']!='PASS':raise ValueError('preflight_failed:'+str(pf['failed']))
 write_once(SCOPE,scope_doc());write_once(PROTOCOL,protocol_doc());write_once(SCHEMA,schema_doc());write_once(POLICY,policy_doc());write_once(PROMPT,prompt_text().encode('utf-8'));write_once(WORKLIST,make_worklist())
 fx=fixtures()
 if fx['status']!='PASS':raise ValueError('fixtures_failed')
 write_once(FIXTURES,fx);write_once(manifest_path('a'),manifest_doc('a'));write_once(manifest_path('b'),manifest_doc('b'))
 artifacts=[SCOPE,PROTOCOL,SCHEMA,POLICY,PROMPT,WORKLIST,FIXTURES,manifest_path('a'),manifest_path('b')]
 pm={'schema_version':1,'manifest_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-prepare-manifest-v2','status':'frozen','adapter_sha256':sha(SELF),'input_sha256':{rel(p):sha(p) for p in EXPECTED},'artifact_sha256':{rel(p):sha(p) for p in artifacts},'both_reviewer_manifests_frozen_before_first_provider_call':True,'provider_called':False,'next_authorized_stage':EXEC_A}
 write_once(PREP_MANIFEST,pm)
 lineage={'multi_claim_successor_type_metadata_scope_decision_v1_sha256':sha(SCOPE),'multi_claim_successor_type_metadata_review_protocol_v1_sha256':sha(PROTOCOL),'multi_claim_successor_type_metadata_review_output_schema_v1_sha256':sha(SCHEMA),'multi_claim_successor_type_metadata_review_execution_policy_v1_sha256':sha(POLICY),'multi_claim_successor_type_metadata_reviewer_prompt_v2_sha256':sha(PROMPT),'multi_claim_successor_type_metadata_blind_worklist_v2_sha256':sha(WORKLIST),'multi_claim_successor_type_metadata_review_contract_fixtures_v1_sha256':sha(FIXTURES),'multi_claim_successor_type_metadata_reviewer_a_manifest_v1_sha256':sha(manifest_path('a')),'multi_claim_successor_type_metadata_reviewer_b_manifest_v1_sha256':sha(manifest_path('b')),'multi_claim_successor_type_metadata_review_prepare_manifest_v1_sha256':sha(PREP_MANIFEST)}
 s=copy.deepcopy(load(STATE_IN));r=copy.deepcopy(load(READY_IN));s.setdefault('artifact_lineage',{}).update(lineage);r.setdefault('artifact_lineage',{}).update(lineage)
 s.update({'schema_version':42,'state_id':'phase7.3.3-d-support-stage-state-v42','status':'multi_claim_successor_type_metadata_review_v2_prepared','next_authorized_stage':EXEC_A,'successor_type_metadata_review_v2_frozen':True,'successor_type_metadata_reviewer_a_manifest_frozen':True,'successor_type_metadata_reviewer_b_manifest_frozen':True,'successor_type_metadata_review_v2_provider_called':False,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False})
 r.update({'schema_version':53,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v53','status':'multi_claim_successor_type_metadata_review_v2_prepared','next_authorized_stage':EXEC_A,'successor_type_metadata_review_v2_frozen':True,'successor_type_metadata_reviewer_a_manifest_frozen':True,'successor_type_metadata_reviewer_b_manifest_frozen':True,'successor_type_metadata_review_v2_provider_called':False,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False})
 ssha=write_once(STATE_PREP,s);rsha=write_once(READY_PREP,r)
 outcome={'schema_version':1,'outcome_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-prepare-outcome-v2','status':'PASS','case_count':40,'claim_count':240,'provider_called':False,'next_authorized_stage':EXEC_A};write_once(PREP_OUTCOME,outcome)
 receipt={'schema_version':1,'receipt_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-prepare-receipt-v2','status':'PASS','prepare_manifest_sha256':sha(PREP_MANIFEST),'prepare_outcome_sha256':sha(PREP_OUTCOME),'state_sha256':ssha,'readiness_sha256':rsha,'artifact_sha256':{rel(p):sha(p) for p in artifacts},'fixtures_passed':fx['passed'],'fixtures_total':fx['total'],'both_reviewer_manifests_frozen_before_first_provider_call':True,'provider_called':False,'next_authorized_stage':EXEC_A};write_once(PREP_RECEIPT,receipt)
 return {'status':'PASS','case_count':40,'claim_count':240,'fixtures':f"{fx['passed']}/{fx['total']}",'prepare_manifest_sha256':sha(PREP_MANIFEST),'reviewer_a_manifest_sha256':sha(manifest_path('a')),'reviewer_b_manifest_sha256':sha(manifest_path('b')),'state_sha256':ssha,'readiness_sha256':rsha,'next_authorized_stage':EXEC_A}
def verify_prepare():
 paths=[SCOPE,PROTOCOL,SCHEMA,POLICY,PROMPT,WORKLIST,FIXTURES,PREP_MANIFEST,PREP_OUTCOME,PREP_RECEIPT,STATE_PREP,READY_PREP,manifest_path('a'),manifest_path('b')];checks={f'exists:{p.name}':p.exists() for p in paths}
 if all(checks.values()):
  pm=load(PREP_MANIFEST);w=load(WORKLIST);fx=load(FIXTURES);s=load(STATE_PREP);r=load(READY_PREP)
  checks.update({'adapter':pm.get('adapter_sha256')==sha(SELF),'40_240':w.get('case_count')==40 and w.get('claim_count')==240 and sum(len(c['claims']) for c in w['cases'])==240,'blind':all(w.get(k) is False for k in ['evidence_present','support_labels_present','old_gold_present','arm_outputs_present','other_reviewer_output_present']),'fixtures':fx.get('status')=='PASS' and fx.get('passed')==fx.get('total')==12,'state_gate':s.get('next_authorized_stage')==EXEC_A,'readiness_gate':r.get('next_authorized_stage')==EXEC_A,'provider_not_called':s.get('successor_type_metadata_review_v2_provider_called') is False,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_unauthorized':s.get('runtime_integration_authorized') is False})
  for n,d in pm.get('artifact_sha256',{}).items():checks['hash:'+n]=(ROOT/n).exists() and sha(ROOT/n)==d
 failed=[k for k,v in checks.items() if not v];return {'status':'PASS' if not failed else 'FAIL','checks':len(checks),'failed':failed,'next_authorized_stage':load(STATE_PREP).get('next_authorized_stage') if STATE_PREP.exists() else None}

def split_prompt():
 t=PROMPT.read_text(encoding='utf-8-sig');sm='## System message\n';um='## User message template\n'
 if sm not in t or um not in t:raise ValueError('prompt_sections_missing')
 return t.split(sm,1)[1].split(um,1)[0].strip(),t.split(um,1)[1].strip()
def request(key,model,system,user):
 payload={'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':user}],'temperature':0,'top_p':1,'max_tokens':1600,'response_format':{'type':'json_object'}}
 req=urllib.request.Request(BASE_URL+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=300) as resp:return resp.read()
def envelope(raw):
 try:x=json.loads(raw.decode('utf-8'))
 except Exception as e:raise ValueError('provider_envelope_invalid_json') from e
 if not isinstance(x,dict):raise ValueError('provider_envelope_not_object')
 return x
def canonical(want,got):
 if got==want or got.startswith(want+'-'):return want
 raise ValueError(f'provider_reported_model_outside_requested_family:{want}:{got}')
def exec_paths(r):
 if r=='a':return STATE_PREP,READY_PREP,PATTERN/'phase7_3_3_d_support_stage_state_v43.json',REPORTS/'phase7_3_3_d1_reference_construction_readiness_v54.json',EXEC_A
 return PATTERN/'phase7_3_3_d_support_stage_state_v43.json',REPORTS/'phase7_3_3_d1_reference_construction_readiness_v54.json',PATTERN/'phase7_3_3_d_support_stage_state_v44.json',REPORTS/'phase7_3_3_d1_reference_construction_readiness_v55.json',EXEC_B
def seen(m,r,c):return any(e.get('manifest_sha256')==m and e.get('reviewer')==r and e.get('case_id')==c and e.get('response_received') is True and e.get('authoritative_result') is True for e in events())
def finalize(r,status,nxt,subsha=None,resha=None):
 si,ri,so,ro,_=exec_paths(r);s=copy.deepcopy(load(si));q=copy.deepcopy(load(ri));sv=43 if r=='a' else 44;rv=54 if r=='a' else 55;line={}
 if subsha:line[f'multi_claim_successor_type_metadata_reviewer_{r}_submission_v2_sha256']=subsha
 if resha:line[f'multi_claim_successor_type_metadata_reviewer_{r}_execution_result_v2_sha256']=resha
 s.setdefault('artifact_lineage',{}).update(line);q.setdefault('artifact_lineage',{}).update(line);completed=status.endswith('completed')
 s.update({'schema_version':sv,'state_id':f'phase7.3.3-d-support-stage-state-v{sv}','status':status,'next_authorized_stage':nxt,'successor_type_metadata_review_v2_provider_called':True,f'successor_type_metadata_reviewer_{r}_v2_completed':completed,'successor_type_metadata_review_v2_completed':r=='b' and completed,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False})
 q.update({'schema_version':rv,'readiness_id':f'phase7.3.3-d1-reference-construction-readiness-v{rv}','status':status,'next_authorized_stage':nxt,'successor_type_metadata_review_v2_provider_called':True,f'successor_type_metadata_reviewer_{r}_v2_completed':completed,'successor_type_metadata_review_v2_completed':r=='b' and completed,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False})
 return write_once(so,s),write_once(ro,q)
def execute(r):
 if verify_prepare()['status']!='PASS':raise ValueError('prepare_not_verified')
 si,ri,_,_,required=exec_paths(r);s=load(si);q=load(ri)
 if s.get('next_authorized_stage')!=required or q.get('next_authorized_stage')!=required:raise ValueError('stage_not_authorized:'+r)
 mp=manifest_path(r);m=load(mp);msha=sha(mp)
 frozen={SELF:m['adapter_sha256'],SCOPE:m['scope_decision_sha256'],PROTOCOL:m['protocol_sha256'],SCHEMA:m['schema_sha256'],POLICY:m['policy_sha256'],PROMPT:m['prompt_sha256'],WORKLIST:m['worklist_sha256'],FIXTURES:m['fixtures_sha256'],REFERENCE:m['boundary_reference_candidate_sha256']}
 for p,d in frozen.items():
  if sha(p)!=d:raise ValueError('manifest_hash_mismatch:'+rel(p))
 key=os.environ.get(CRED)
 if not key:raise ValueError('missing_credential:'+CRED)
 system,user_template=split_prompt();w=load(WORKLIST);case_results=[];allrows=[];models=set()
 for case in w['cases']:
  cid=case['case_id'];cp=checkpoint(r,cid)
  if cp.exists():
   d=load(cp)
   if d.get('manifest_sha256')!=msha:raise ValueError('checkpoint_lineage_mismatch:'+cid)
   rows=normalize(case,{'annotations':[{k:x[k] for k in ['claim_index','claim_role','claim_type']} for x in d['annotations']]},r);case_results.append(d['case_result']);allrows.extend(rows);models.add(d['provider_reported_model']);continue
  if seen(msha,r,cid):raise ValueError('authoritative_content_seen_without_checkpoint:'+cid)
  case_json={'case_id':cid,'candidate_text':case['candidate_text'],'claims':[{'claim_index':x['claim_index'],'source_excerpt':x['source_excerpt']} for x in case['claims']]};user=user_template.replace('{{CASE_JSON}}',json.dumps(case_json,ensure_ascii=False,indent=2))
  raw=None;esha=None;csha=None
  try:
   raw=request(key,m['model_requested'],system,user);esha=hb(raw);env=envelope(raw);content=env.get('choices',[{}])[0].get('message',{}).get('content')
   if not isinstance(content,str):raise ValueError('provider_content_not_string')
   csha=hb(content.encode('utf-8'));append_event({'event_type':'multi_claim_type_metadata_provider_content_received','manifest_sha256':msha,'reviewer':r,'case_id':cid,'response_received':True,'authoritative_result':True,'provider_envelope_sha256':esha,'provider_content_sha256':csha})
   reported=env.get('model') or 'unknown';canon=canonical(m['model_requested'],reported);rows=normalize(case,strict_load(content),r);nsha=hb(jb(rows))
   cr={'case_id':cid,'annotation_count':len(rows),'provider_reported_model':reported,'canonical_model_family':canon,'provider_envelope_sha256':esha,'provider_content_sha256':csha,'normalized_annotations_sha256':nsha,'status':'PASS'}
   cpdoc={'schema_version':1,'checkpoint_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-{r}-{cid}-v2','manifest_sha256':msha,'reviewer':r,'case_id':cid,'provider_reported_model':reported,'case_result':cr,'annotations':rows,'raw_provider_content_stored':False};write_once(cp,cpdoc);case_results.append(cr);allrows.extend(rows);models.add(reported)
  except urllib.error.HTTPError as e:
   append_event({'event_type':'multi_claim_type_metadata_transport_failure','manifest_sha256':msha,'reviewer':r,'case_id':cid,'status':f'http_{e.code}','response_received':False,'authoritative_result':False});return {'status':'TRANSPORT_FAILURE_RESUMABLE','reviewer':r,'case_id':cid,'http_status':e.code}
  except Exception as e:
   received=raw is not None;append_event({'event_type':'multi_claim_type_metadata_experimental_failure' if received else 'multi_claim_type_metadata_adapter_failure','manifest_sha256':msha,'reviewer':r,'case_id':cid,'status':type(e).__name__,'failure_code':str(e)[:300],'response_received':received,'authoritative_result':received,'provider_envelope_sha256':esha,'provider_content_sha256':csha})
   if not received:raise
   neg={'schema_version':1,'negative_result_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-reviewer-{r}-negative-result-v2','reviewer':r,'manifest_sha256':msha,'case_id':cid,'status':'authoritative_negative_result','failure_type':type(e).__name__,'failure_code':str(e)[:300],'response_received':True,'provider_envelope_sha256':esha,'provider_content_sha256':csha,'raw_provider_content_stored':False,'same_version_retry_authorized':False,'type_metadata_capability_conclusion_authorized':False};nsha=write_once(negative_path(r),neg);state_sha,ready_sha=finalize(r,'authoritative_negative_result','blocked_authoritative_negative_result')
   return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','reviewer':r,'case_id':cid,'negative_result_sha256':nsha,'state_sha256':state_sha,'readiness_sha256':ready_sha,'same_version_retry_authorized':False}
 wanted=m['model_requested']
 if {canonical(wanted,x) for x in models}!={wanted}:raise ValueError('canonical_model_family_drift')
 if len(case_results)!=40 or len(allrows)!=240:raise ValueError('completed_cardinality_invalid')
 sub={'schema_version':1,'submission_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-reviewer-{r}-submission-v2','reviewer':r,'reviewer_role':'independent_type_metadata_reviewer','manifest_sha256':msha,'worklist_sha256':sha(WORKLIST),'completed':True,'completed_case_count':40,'annotation_count':240,'blind_to_evidence':True,'blind_to_support_labels':True,'blind_to_other_reviewer':True,'blind_to_old_gold':True,'boundary_mutation_authorized':False,'reviewed_fields':['claim_role','claim_type'],'annotations':allrows};subsha=write_once(submission(r),sub)
 res={'schema_version':1,'result_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-reviewer-{r}-execution-result-v2','status':'PASS','reviewer':r,'manifest_sha256':msha,'submission_sha256':subsha,'completed_case_count':40,'annotation_count':240,'provider_reported_models':sorted(models),'canonical_model_family':wanted,'case_results':case_results};resha=write_once(result_path(r),res)
 nxt=EXEC_B if r=='a' else AGREEMENT;out={'schema_version':1,'outcome_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-reviewer-{r}-execution-outcome-v2','status':'PASS','reviewer':r,'submission_sha256':subsha,'execution_result_sha256':resha,'next_authorized_stage':nxt,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};osha=write_once(outcome_path(r),out);state_sha,ready_sha=finalize(r,'multi_claim_successor_type_metadata_review_v2_completed',nxt,subsha,resha)
 rec={'schema_version':1,'receipt_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-reviewer-{r}-execution-receipt-v2','status':'PASS','reviewer':r,'manifest_sha256':msha,'submission_sha256':subsha,'execution_result_sha256':resha,'execution_outcome_sha256':osha,'state_sha256':state_sha,'readiness_sha256':ready_sha,'completed_case_count':40,'annotation_count':240,'next_authorized_stage':nxt};recsha=write_once(receipt_path(r),rec)
 return {'status':'PASS','reviewer':r,'completed_case_count':40,'annotation_count':240,'submission_sha256':subsha,'execution_result_sha256':resha,'receipt_sha256':recsha,'state_sha256':state_sha,'readiness_sha256':ready_sha,'next_authorized_stage':nxt}

def verify_reviewer(r):
 _,_,so,ro,_=exec_paths(r);paths=[manifest_path(r),submission(r),result_path(r),outcome_path(r),receipt_path(r),so,ro];checks={f'exists:{p.name}':p.exists() for p in paths}
 if all(checks.values()):
  m=load(manifest_path(r));sub=load(submission(r));res=load(result_path(r));out=load(outcome_path(r));rec=load(receipt_path(r));s=load(so);q=load(ro);w=load(WORKLIST);ids=[];replay=True
  for c in w['cases']:
   p=checkpoint(r,c['case_id'])
   if not p.exists():replay=False;continue
   d=load(p)
   try:
    rows=normalize(c,{'annotations':[{k:x[k] for k in ['claim_index','claim_role','claim_type']} for x in d['annotations']]},r);replay=replay and rows==d['annotations'];ids.extend(x['claim_id'] for x in rows)
   except Exception:replay=False
  expected=EXEC_B if r=='a' else AGREEMENT
  checks.update({'adapter':m.get('adapter_sha256')==sha(SELF),'lineage':res.get('submission_sha256')==rec.get('submission_sha256')==sha(submission(r)) and out.get('execution_result_sha256')==sha(result_path(r)),'40_240':sub.get('completed_case_count')==res.get('completed_case_count')==40 and sub.get('annotation_count')==res.get('annotation_count')==240 and len(sub.get('annotations',[]))==240,'ids_once':len(ids)==len(set(ids))==240 and set(ids)=={x for c in w['cases'] for x in c['valid_claim_ids']},'checkpoint_replay':replay,'state_gate':s.get('next_authorized_stage')==expected,'readiness_gate':q.get('next_authorized_stage')==expected,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_unauthorized':s.get('runtime_integration_authorized') is False})
 failed=[k for k,v in checks.items() if not v];return {'status':'PASS' if not failed else 'FAIL','checks':len(checks),'failed':failed}
# v2 representation overrides: the model emits short claim_index values.
def protocol_doc():
 return {'schema_version':2,'protocol_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-protocol-v2','status':'frozen_before_any_v2_provider_call','predecessor_entry_protocol_sha256':sha(ENTRY_PROTOCOL),'predecessor_failure_classification_sha256':sha(FAILURE_CLASS),'object_of_study':'claim_role_and_claim_type_on_frozen_atomic_boundaries','semantic_rules_unchanged_from_v1':True,'boundary_reference_candidate_sha256':sha(REFERENCE),'reviewed_fields':['claim_role','claim_type'],'claim_role_enum':sorted(ROLES),'claim_type_enum':sorted(TYPES),'review_design':{'independent_reviewers':2,'models':REVIEWERS,'case_isolation':True,'both_manifests_frozen_before_reviewer_a':True,'reviewer_a_v1_reused':False},'representation':{'model_returns_claim_index':True,'adapter_maps_index_to_frozen_claim_id':True,'model_copies_claim_id':False,'model_copies_excerpt':False,'each_index_exactly_once':True},'controlled_change_from_v1':'output_representation_only','next_stage':AGREEMENT}
def schema_doc():
 return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-output-schema-v2','type':'object','required':['annotations'],'properties':{'annotations':{'type':'array','minItems':1,'items':{'type':'object','required':['claim_index','claim_role','claim_type'],'properties':{'claim_index':{'type':'integer','minimum':1},'claim_role':{'enum':sorted(ROLES)},'claim_type':{'enum':sorted(TYPES)}},'additionalProperties':False}}},'additionalProperties':False}
def policy_doc():
 d={'schema_version':2,'policy_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-execution-policy-v2','status':'frozen_before_any_v2_provider_call','provider':'api.gpt.ge','provider_base_url':BASE_URL,'credential_env_name':CRED,'temperature':0,'top_p':1,'max_tokens':1600,'response_format':{'type':'json_object'},'case_isolation':True,'first_provider_content_authoritative':True,'same_version_retry_after_content_authorized':False,'transport_retry_before_content_authorized':True,'raw_provider_content_stored':False,'hashes_stored':['provider_envelope_sha256','provider_content_sha256'],'representation_adapter':'claim_index_to_frozen_claim_id'};return d
def prompt_text():return '''# Phase 7.3.3-D Multi-claim Successor Type/Metadata Reviewer Prompt v2

## System message

You are an independent Claim Type and Structural Role Reviewer. Atomic Claim boundaries are frozen. Classify every supplied claim exactly once. Do not merge, split, delete, add, paraphrase, or reproduce Claim text. Do not judge support, correctness, material error, citations, evidence, or Boundary quality.

Return compact strict JSON with exactly one root field `annotations`. Every item must contain exactly `claim_index`, `claim_role`, and `claim_type`. Copy each supplied integer claim_index exactly once. Do not return claim_id, excerpts, spans, Markdown, rationale, confidence, or extra fields.

Claim role: anchor = primary situation, decision, request, or conclusion (multiple allowed); support = observation, prior event, preference, or reason bearing on another Claim; qualification = narrows entity, time, applicability, priority, or context; boundary = insufficiency, uncertainty, non-applicability, caution, prohibition, or limiting negative boundary; prediction = future or expected outcome; exception = counterexample, reversal, failure, or contrary case.

Claim type: proposition = fact, preference, request, recommendation, decision, or general assertion not better classified below; causal = explicit cause, influence, explanation, or responsibility; prediction = future or expected outcome; scope = explicit domain, entity-set, time, quantity, or applicability limit/generalization; falsifiability = observable test, success criterion, or refutation criterion; limitation = uncertainty, missing information, insufficiency, staleness, risk, or inability to conclude; condition = prerequisite or if/when condition; exception = counterexample, contradiction, reversal, failure case, or exception.

Role and type are independent. Use proposition as fallback. Recommendations and imperative-like decision tokens are propositions unless they explicitly encode another type. For snake_case Claims, classify only semantic content encoded by the token; do not invent details.

Example: {"annotations":[{"claim_index":1,"claim_role":"anchor","claim_type":"proposition"}]}

## User message template

Classify this frozen Candidate and its frozen Atomic Claims.

{{CASE_JSON}}
'''
def make_worklist():
 ref=load(REFERENCE);src=load(SOURCE);by={}
 for x in ref['claims']:by.setdefault(x['case_id'],[]).append(x)
 out=[]
 for c in src['cases']:
  cs=sorted(by[c['case_id']],key=lambda x:(x['source_span']['start'],x['source_span']['end']));claims=[]
  for idx,x in enumerate(cs,1):
   s,e=x['source_span']['start'],x['source_span']['end']
   if c['candidate_text'][s:e]!=x['source_excerpt']:raise ValueError('excerpt_replay_failed:'+x['reference_claim_id'])
   claims.append({'claim_index':idx,'claim_id':x['reference_claim_id'],'source_span':x['source_span'],'source_excerpt':x['source_excerpt']})
  out.append({'successor_index':c['successor_index'],'case_id':c['case_id'],'candidate_text':c['candidate_text'],'candidate_sha256':c['candidate_sha256'],'claims':claims,'valid_claim_indices':[x['claim_index'] for x in claims],'valid_claim_ids':[x['claim_id'] for x in claims]})
 if len(out)!=40 or sum(len(x['claims']) for x in out)!=240:raise ValueError('worklist_cardinality_invalid')
 return {'schema_version':2,'worklist_id':'phase7.3.3-d-multi-claim-successor-type-metadata-blind-worklist-v2','status':'frozen_type_metadata_review_only','boundary_reference_candidate_sha256':sha(REFERENCE),'case_count':40,'claim_count':240,'cases':out,'evidence_present':False,'support_labels_present':False,'old_gold_present':False,'arm_outputs_present':False,'other_reviewer_output_present':False,'boundary_mutation_authorized':False,'model_visible_identifier':'claim_index','adapter_reconstructs_claim_id':True}
def normalize(case,payload,reviewer):
 if not isinstance(payload,dict) or set(payload)!={'annotations'}:raise ValueError('root_must_contain_exactly_annotations')
 a=payload['annotations'];expected=case['valid_claim_indices'];index={x['claim_index']:x for x in case['claims']}
 if not isinstance(a,list):raise ValueError('annotations_must_be_array')
 if len(a)!=len(expected):raise ValueError('annotation_count_mismatch')
 seen=set();out=[]
 for i,x in enumerate(a):
  if not isinstance(x,dict) or set(x)!={'claim_index','claim_role','claim_type'}:raise ValueError(f'annotation_fields_invalid:{i}')
  idx=x['claim_index'];role=x['claim_role'];typ=x['claim_type']
  if type(idx) is not int or idx not in index:raise ValueError(f'unknown_claim_index:{i}')
  if idx in seen:raise ValueError('duplicate_claim_index:'+str(idx))
  if role not in ROLES:raise ValueError(f'invalid_claim_role:{idx}:{role}')
  if typ not in TYPES:raise ValueError(f'invalid_claim_type:{idx}:{typ}')
  seen.add(idx);src=index[idx];out.append({'case_id':case['case_id'],'claim_index':idx,'claim_id':src['claim_id'],'source_span':src['source_span'],'source_excerpt':src['source_excerpt'],'claim_role':role,'claim_type':typ,'claim_origin':'explicit','reviewer':reviewer})
 if seen!=set(expected):raise ValueError('claim_index_set_mismatch')
 order={x['claim_id']:x['claim_index'] for x in case['claims']};out.sort(key=lambda x:order[x['claim_id']]);return out
def fixtures():
 c={'case_id':'f','claims':[{'claim_index':1,'claim_id':'long-c1','source_span':{'start':0,'end':1},'source_excerpt':'a'},{'claim_index':2,'claim_id':'long-c2','source_span':{'start':2,'end':3},'source_excerpt':'b'}],'valid_claim_indices':[1,2],'valid_claim_ids':['long-c1','long-c2']};g={'annotations':[{'claim_index':1,'claim_role':'anchor','claim_type':'proposition'},{'claim_index':2,'claim_role':'boundary','claim_type':'limitation'}]}
 tests=[('valid',g,True),('wrong_root',{'claims':g['annotations']},False),('extra_root',{**g,'x':1},False),('missing',{'annotations':g['annotations'][:1]},False),('duplicate',{'annotations':[g['annotations'][0],g['annotations'][0]]},False),('unknown',{'annotations':[{**g['annotations'][0],'claim_index':3},g['annotations'][1]]},False),('claim_id_forbidden',{'annotations':[{'claim_id':'long-c1','claim_role':'anchor','claim_type':'proposition'},g['annotations'][1]]},False),('extra_field',{'annotations':[{**g['annotations'][0],'reason':'x'},g['annotations'][1]]},False),('bad_role',{'annotations':[{**g['annotations'][0],'claim_role':'central'},g['annotations'][1]]},False),('bad_type',{'annotations':[{**g['annotations'][0],'claim_type':'opinion'},g['annotations'][1]]},False),('non_array',{'annotations':{}},False)]
 rows=[]
 for n,p,want in tests:
  ok=True;err=None
  try:normalize(c,p,'f')
  except Exception as e:ok=False;err=str(e)
  rows.append({'name':n,'expected_pass':want,'observed_pass':ok,'status':'PASS' if ok==want else 'FAIL','error':err})
 dup=False
 try:strict_load('{"annotations":[],"annotations":[]}')
 except Exception:dup=True
 rows.append({'name':'duplicate_json_key','expected_pass':False,'observed_pass':not dup,'status':'PASS' if dup else 'FAIL'})
 return {'schema_version':2,'fixture_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-contract-fixtures-v2','passed':sum(x['status']=='PASS' for x in rows),'total':len(rows),'status':'PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL','results':rows}
def manifest_doc(r):
 return {'schema_version':2,'manifest_id':f'phase7.3.3-d-multi-claim-successor-type-metadata-reviewer-{r}-execution-manifest-v2','status':'frozen_not_started','reviewer':r,'provider':'api.gpt.ge','provider_base_url':BASE_URL,'model_requested':REVIEWERS[r],'temperature':0,'top_p':1,'max_tokens':1600,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(SELF),'scope_decision_sha256':sha(SCOPE),'protocol_sha256':sha(PROTOCOL),'schema_sha256':sha(SCHEMA),'policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'worklist_sha256':sha(WORKLIST),'fixtures_sha256':sha(FIXTURES),'entry_protocol_sha256':sha(ENTRY_PROTOCOL),'failure_classification_sha256':sha(FAILURE_CLASS),'boundary_reference_candidate_sha256':sha(REFERENCE),'case_count':40,'claim_count':240,'case_isolation':True,'claim_index_representation':True,'first_provider_content_authoritative':True,'semantic_retry_authorized':False,'raw_provider_content_stored':False,'evidence_visible':False,'support_labels_visible':False,'other_reviewer_visible':False,'boundary_mutation_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--preflight-prepare',action='store_true');g.add_argument('--fixtures',action='store_true');g.add_argument('--prepare',action='store_true');g.add_argument('--verify-prepare',action='store_true');g.add_argument('--execute-reviewer',choices=sorted(REVIEWERS));g.add_argument('--verify-reviewer',choices=sorted(REVIEWERS));a=p.parse_args()
 if a.preflight_prepare:x=preflight()
 elif a.fixtures:x=fixtures()
 elif a.prepare:x=prepare_run()
 elif a.verify_prepare:x=verify_prepare()
 elif a.execute_reviewer:x=execute(a.execute_reviewer)
 else:x=verify_reviewer(a.verify_reviewer)
 print(json.dumps(x,ensure_ascii=False,indent=2));return 0 if x.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE'} else 1
if __name__=='__main__':raise SystemExit(main())





