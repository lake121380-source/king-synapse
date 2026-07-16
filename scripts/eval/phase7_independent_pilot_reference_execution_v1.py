#!/usr/bin/env python3
"""Freeze and execute two blind Independent Pilot Reference reviewers v1."""
from __future__ import annotations
import argparse, copy, hashlib, json, os, re, tempfile, urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event, read_entries

ROOT=Path(__file__).resolve().parents[2];CONFIG=ROOT/'crates/eval/config';DATA=ROOT/'crates/eval/datasets/pattern_extraction';REPORTS=ROOT/'crates/eval/reports'
REFERENCE_POLICY=CONFIG/'phase7_3_3_d_independent_reference_policy_v1.json';DATASET=DATA/'phase7_3_3_d_independent_pilot_selected_dataset_v1.json';CONTENT_RECEIPT=REPORTS/'phase7_3_3_d_independent_pilot_content_open_receipt_v1.json';STATE=DATA/'phase7_3_3_d_support_stage_state_v15.json';READY=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v26.json'
PROTOCOL=CONFIG/'phase7_3_3_d_independent_pilot_reference_execution_protocol_v1.json';EXEC_POLICY=CONFIG/'phase7_3_3_d_independent_pilot_reference_execution_policy_v1.json';PROMPT=CONFIG/'phase7_3_3_d_independent_pilot_reference_reviewer_prompt_v1.md';FIXTURES=REPORTS/'phase7_3_3_d_independent_pilot_reference_execution_contract_fixtures_v1.json'
BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';TEMP=0;TOP_P=1;MAX_TOKENS=4000;TIMEOUT=600;RF={'type':'json_object'}
REVIEWERS={'a':{'label':'Independent Reference Reviewer A','model':'gpt-4.1'},'b':{'label':'Independent Reference Reviewer B','model':'qwen3.5-plus'}}
KINDS={'atomic_claim','explicit_non_claim'};CLAIM_TYPES={'proposition','causal','scope','prediction','falsifiability','qualification','boundary','preference','temporal_update','selection_rule','other'};LABELS={'supported','partially_supported','unsupported','not_assessable'};CONF={'low','medium','high'}
SUPPORT_REASONS={'direct_evidence_match','conservative_entailment','reasonable_bridging_inference','scope_preserved','scope_expansion','certainty_escalation','causal_leap','prediction_overcommitment','unsupported_detail','counterexample_ignored','insufficient_evidence','conflicting_evidence','temporal_resolution','reliability_resolution','context_constraint_match'}
NONCLAIM_REASONS={'connector_only','discourse_marker','punctuation_or_formatting','non_assertive_fragment','other_non_claim'}
TOP={'case_id','segments'};SEG={'segment_kind','start_token_index','end_token_index_exclusive','claim_type','material','support_label','cited_evidence_ids','reason_codes','rationale','confidence'}

def manifest(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_execution_manifest_v1.json'
def attempts(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_execution_attempts_v1.jsonl'
def checkpoint_dir(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_cases_v1'
def checkpoint(r,c):return checkpoint_dir(r)/f'{c}.json'
def submission(r):return DATA/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_submission_v1.json'
def result(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_execution_result_v1.json'
def negative(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_negative_result_v1.json'
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
def write_text_once(p,text):
 b=text.encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return shab(b)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return shab(b)
def tokens(text):return [{'token_index':i,'text':m.group(),'source_start':m.start(),'source_end':m.end()} for i,m in enumerate(re.finditer(r'\S+',text))]

def protocol_doc():
 return {'schema_version':1,'protocol_id':'phase7.3.3-d-independent-pilot-reference-execution-protocol-v1','status':'frozen','stage':'pilot_reference_construction','research_object':'independent token-partition Atomic Claim and Support Reference','entry_gate':{'selected_content_opened':True,'reference_packets_frozen':True,'arm_execution_started':False,'confirmatory_dataset_opened':False},'reviewers':{'a':{'model_requested':'gpt-4.1'},'b':{'model_requested':'qwen3.5-plus'}},'representation':{'candidate_tokenization':'unicode_regex_non_whitespace_tokens','segments_half_open_token_indices':True,'all_tokens_partitioned_exactly_once':True,'claim_text_reconstructed_deterministically':True,'inter_segment_whitespace_accounted_by_adapter':True},'review_scope':{'boundary':True,'claim_type':True,'materiality':True,'support':True,'citations':True,'non_claim_accounting':True,'candidate_reference_label_computed_by_adapter':True,'material_error_spans_computed_by_adapter':True},'blinding':{'other_reviewer_visible':False,'route_a_gold_visible':False,'historical_labels_visible':False,'candidate_arm_visible':False,'atomic_arm_visible':False},'failure':{'first_provider_content_authoritative':True,'semantic_retry':False,'repair':False,'partial_success_not_reference':True},'provider':{'base_url':BASE,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'case_isolation':True},'runtime':{'integration':False,'memory_write':False}}
def policy_doc():
 return {'schema_version':1,'policy_id':'phase7.3.3-d-independent-pilot-reference-execution-policy-v1','status':'frozen','case_count':40,'reviewer_count':2,'one_provider_request_per_case_per_reviewer':True,'attempts_per_case':1,'first_content_authoritative':True,'infrastructure_retry_before_content_only':True,'semantic_retry':False,'output_repair':False,'required_top_level_keys':sorted(TOP),'required_segment_keys':sorted(SEG),'segment_kind_enum':sorted(KINDS),'claim_type_enum':sorted(CLAIM_TYPES),'support_label_enum':sorted(LABELS),'confidence_enum':sorted(CONF),'support_reason_enum':sorted(SUPPORT_REASONS),'nonclaim_reason_enum':sorted(NONCLAIM_REASONS),'all_tokens_partitioned_exactly_once':True,'same_case_citations_only':True,'raw_provider_response_stored':False,'provider_envelope_hash_stored':True,'provider_content_hash_stored':True,'arm_outputs_visible':False,'confirmatory_visible':False}
def prompt_text():
 return '''# Phase 7.3.3-D Independent Pilot Reference Reviewer v1\n\n## System message\nYou are one independent blind Reference reviewer. Build a token-partition Atomic Claim and evidence-support annotation using only the supplied Candidate, query context, and same-case Evidence. You cannot see another reviewer, Route A Gold, historical labels, or either evaluation arm. Return one bare JSON object and no markdown.\n\nThe Candidate is supplied with immutable zero-based tokens. Partition every token exactly once, in order, into contiguous half-open segments [start_token_index, end_token_index_exclusive). A segment is either `atomic_claim` or `explicit_non_claim`. Do not overlap, omit, reorder, duplicate, or invent tokens. The adapter reconstructs text; do not copy source excerpts.\n\nFor `atomic_claim`: claim_type must be one allowed claim type; material is true or false; support_label must be supported, partially_supported, unsupported, or not_assessable; cited_evidence_ids must contain only supplied IDs; reason_codes use allowed support reasons. For `explicit_non_claim`: claim_type and support_label must be null, material must be false, cited_evidence_ids must be [], and reason_codes use allowed non-claim reasons. Every rationale must be concise and evidence-grounded.\n\nSupport is conservative: `supported` requires the Evidence to support the whole Atomic Claim at its stated scope/certainty/causality; `partially_supported` means a material part is supported but not the whole claim; `unsupported` means the Evidence does not support the claim or contradicts it; `not_assessable` is only for genuinely unjudgeable content.\n\nOutput exactly:\n{"case_id":"...","segments":[{"segment_kind":"atomic_claim","start_token_index":0,"end_token_index_exclusive":3,"claim_type":"proposition","material":true,"support_label":"supported","cited_evidence_ids":["..."],"reason_codes":["direct_evidence_match"],"rationale":"...","confidence":"high"}]}\n\n## User message template\n{CASE_PACKET_JSON}\n'''

def packet_case(c):return {'case_id':c['case_id'],'query_context':c['query_context'],'candidate_sha256':c['candidate_sha256'],'candidate_tokens':tokens(c['candidate_text']),'evidence_bundle':c['evidence_bundle'],'valid_evidence_ids':c['valid_evidence_ids'],'allowed_claim_types':sorted(CLAIM_TYPES),'allowed_support_labels':sorted(LABELS),'allowed_support_reason_codes':sorted(SUPPORT_REASONS),'allowed_nonclaim_reason_codes':sorted(NONCLAIM_REASONS),'required_partition':'all candidate token indices exactly once'}
def exact(o,keys,label):
 if not isinstance(o,dict) or set(o)!=keys:raise ValueError(f'{label}_fields_invalid')
def aggregate_label(claims):
 material=[x for x in claims if x['material']]
 if not material:return 'not_assessable'
 labels=[x['support_label'] for x in material]
 if all(x=='supported' for x in labels):return 'supported'
 if all(x=='unsupported' for x in labels):return 'unsupported'
 if all(x=='not_assessable' for x in labels):return 'not_assessable'
 return 'partially_supported'
def normalize(case,raw,r):
 exact(raw,TOP,'response')
 if raw['case_id']!=case['case_id']:raise ValueError('case_id_mismatch')
 segs=raw['segments'];toks=tokens(case['candidate_text']);n=len(toks)
 if not isinstance(segs,list) or not segs:raise ValueError('segments_required')
 out=[];cursor=0;claim_i=0;non_i=0;valid=set(case['valid_evidence_ids'])
 for s in segs:
  exact(s,SEG,'segment');kind=s['segment_kind'];start=s['start_token_index'];end=s['end_token_index_exclusive']
  if kind not in KINDS:raise ValueError('segment_kind_invalid')
  if not isinstance(start,int) or not isinstance(end,int) or start!=cursor or end<=start or end>n:raise ValueError('token_partition_invalid')
  if s['confidence'] not in CONF or not isinstance(s['rationale'],str) or not s['rationale'].strip():raise ValueError('segment_diagnostic_invalid')
  char_start=toks[start]['source_start'];char_end=toks[end-1]['source_end'];base={'segment_kind':kind,'start_token_index':start,'end_token_index_exclusive':end,'source_span':{'start':char_start,'end':char_end},'source_text_sha256':shab(case['candidate_text'][char_start:char_end].encode()),'confidence':s['confidence'],'rationale':s['rationale'].strip()}
  if kind=='atomic_claim':
   claim_i+=1
   if s['claim_type'] not in CLAIM_TYPES or not isinstance(s['material'],bool) or s['support_label'] not in LABELS:raise ValueError('claim_semantics_invalid')
   if not isinstance(s['cited_evidence_ids'],list) or len(s['cited_evidence_ids'])!=len(set(s['cited_evidence_ids'])) or any(x not in valid for x in s['cited_evidence_ids']):raise ValueError('citation_invalid')
   if not isinstance(s['reason_codes'],list) or any(x not in SUPPORT_REASONS for x in s['reason_codes']):raise ValueError('support_reason_invalid')
   base.update({'reference_claim_id':f'{case["case_id"]}-{r}-claim-{claim_i:02d}','claim_type':s['claim_type'],'material':s['material'],'support_label':s['support_label'],'cited_evidence_ids':s['cited_evidence_ids'],'reason_codes':s['reason_codes']})
  else:
   non_i+=1
   if s['claim_type'] is not None or s['material'] is not False or s['support_label'] is not None or s['cited_evidence_ids']!=[]:raise ValueError('nonclaim_fields_invalid')
   if not isinstance(s['reason_codes'],list) or not s['reason_codes'] or any(x not in NONCLAIM_REASONS for x in s['reason_codes']):raise ValueError('nonclaim_reason_invalid')
   base.update({'reference_nonclaim_id':f'{case["case_id"]}-{r}-nonclaim-{non_i:02d}','claim_type':None,'material':False,'support_label':None,'cited_evidence_ids':[],'reason_codes':s['reason_codes']})
  out.append(base);cursor=end
 if cursor!=n:raise ValueError('token_partition_incomplete')
 claims=[x for x in out if x['segment_kind']=='atomic_claim']
 if not claims:raise ValueError('atomic_claim_required')
 return {'case_id':case['case_id'],'candidate_sha256':case['candidate_sha256'],'token_count':n,'segments':out,'claim_count':len(claims),'explicit_non_claim_count':len(out)-len(claims),'candidate_reference_label':aggregate_label(claims),'material_error_spans':[{'reference_claim_id':x['reference_claim_id'],'source_span':x['source_span'],'support_label':x['support_label']} for x in claims if x['material'] and x['support_label']!='supported'],'coverage_complete':True}

def fixtures_doc():
 c={'case_id':'fixture','candidate_text':'alpha beta gamma','candidate_sha256':shab(b'alpha beta gamma'),'valid_evidence_ids':['e1'],'evidence_bundle':[]}
 good={'case_id':'fixture','segments':[{'segment_kind':'atomic_claim','start_token_index':0,'end_token_index_exclusive':3,'claim_type':'proposition','material':True,'support_label':'supported','cited_evidence_ids':['e1'],'reason_codes':['direct_evidence_match'],'rationale':'evidence','confidence':'high'}]}
 tests=[]
 def test(name,obj,ok_expected=True):
  try:normalize(c,obj,'x');ok=True
  except Exception:ok=False
  tests.append({'fixture_id':name,'status':'PASS' if ok==ok_expected else 'FAIL'})
 test('valid_whole_claim',good);bad=copy.deepcopy(good);bad['segments'][0]['start_token_index']=1;test('reject_initial_gap',bad,False);bad=copy.deepcopy(good);bad['segments'][0]['end_token_index_exclusive']=4;test('reject_out_of_range',bad,False);bad=copy.deepcopy(good);bad['segments'][0]['cited_evidence_ids']=['bad'];test('reject_unknown_citation',bad,False);bad=copy.deepcopy(good);bad['segments'][0]['support_label']='maybe';test('reject_label_enum',bad,False);bad=copy.deepcopy(good);bad['segments'][0]['invented']=1;test('reject_extra_field',bad,False);bad=copy.deepcopy(good);bad['segments'][0].update({'segment_kind':'explicit_non_claim','claim_type':None,'material':False,'support_label':None,'cited_evidence_ids':[],'reason_codes':['connector_only']});test('reject_no_claim',bad,False);return {'schema_version':1,'fixture_suite_id':'phase7.3.3-d-independent-pilot-reference-execution-contract-fixtures-v1','status':'PASS' if all(x['status']=='PASS' for x in tests) else 'FAIL','passed':sum(x['status']=='PASS' for x in tests),'total':len(tests),'fixtures':tests}
def entry_gate():
 for p in [REFERENCE_POLICY,DATASET,CONTENT_RECEIPT,STATE,READY]:
  if not p.exists():raise FileNotFoundError(p)
 d=load(DATASET);s=load(STATE);r=load(READY)
 checks={'dataset_40':d.get('case_count')==40,'arms_absent':d.get('arm_outputs_present') is False,'state_gate':s.get('next_authorized_stage')=='freeze_independent_pilot_reference_execution_protocol_v1','ready_gate':r.get('next_authorized_stage')=='freeze_independent_pilot_reference_execution_protocol_v1','confirmatory_closed':s.get('confirmatory_dataset_opened') is False}
 if not all(checks.values()):raise ValueError(f'entry_gate_failed:{checks}')
 return checks
def prepare():
 entry_gate();write_once(PROTOCOL,protocol_doc());write_once(EXEC_POLICY,policy_doc());write_text_once(PROMPT,prompt_text());f=fixtures_doc();write_once(FIXTURES,f);print(json.dumps({'status':'PASS' if f['status']=='PASS' else 'FAIL','protocol_sha256':sha(PROTOCOL),'policy_sha256':sha(EXEC_POLICY),'prompt_sha256':sha(PROMPT),'fixtures':f'{f["passed"]}/{f["total"]}','provider_called':False},indent=2))
def expected_manifest(r):
 entry_gate();d=load(DATASET);cfg=REVIEWERS[r]
 return {'schema_version':1,'manifest_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-execution-manifest-v1','status':'frozen_not_started','reviewer':r,'reviewer_label':cfg['label'],'provider':'api.gpt.ge','provider_base_url':BASE,'model_requested':cfg['model'],'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'credential_env_name':CRED,'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(PROTOCOL),'execution_policy_sha256':sha(EXEC_POLICY),'prompt_sha256':sha(PROMPT),'contract_fixtures_sha256':sha(FIXTURES),'dataset_sha256':sha(DATASET),'content_open_receipt_sha256':sha(CONTENT_RECEIPT),'state_v15_sha256':sha(STATE),'readiness_v26_sha256':sha(READY),'case_count':d['case_count'],'case_isolation':True,'other_reviewer_visible':False,'route_a_gold_visible':False,'arm_outputs_visible':False,'confirmatory_visible':False,'first_provider_content_authoritative':True,'semantic_retry_allowed':False,'output_repair_allowed':False,'raw_provider_responses_stored':False,'provider_envelope_sha256_stored':True,'provider_content_sha256_stored':True}
def freeze_manifest(r):
 print(json.dumps({'status':'PASS','reviewer':r,'manifest_sha256':write_once(manifest(r),expected_manifest(r)),'provider_called':False},indent=2))
def canonical(requested,reported):
 tail=reported.strip().lower().rsplit('/',1)[-1];q=requested.lower()
 if tail==q or (q=='gpt-4.1' and tail.startswith('gpt-4.1-')) or (q=='qwen3.5-plus' and tail.startswith('qwen3.5-plus')):return requested
 raise ValueError(f'provider_model_outside_requested_family:{reported}')
def call(key,model,system,user):
 payload={'model':model,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as resp:return resp.read()
def parse_envelope(raw,requested):
 env=json.loads(raw.decode());reported=env.get('model') if isinstance(env,dict) else None
 if not isinstance(reported,str) or not reported.strip():raise ValueError('provider_reported_model_missing')
 can=canonical(requested,reported);choices=env.get('choices')
 if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):raise ValueError('provider_choices_invalid')
 msg=choices[0].get('message');content=msg.get('content') if isinstance(msg,dict) else None
 if not isinstance(content,str) or not content.strip():raise ValueError('provider_content_missing')
 return reported,can,shab(content.encode()),json.loads(content)
def classify(e,received):
 s=str(e)
 if not received:return 'level_0_transport','transport_failure'
 if s.startswith(('provider_model','provider_reported')):return 'level_1_provider_representation','identity_failure'
 if isinstance(e,json.JSONDecodeError) or s.startswith('provider_'):return 'level_1_provider_representation','parse_or_envelope_failure'
 if s.startswith(('response_','segment_','token_partition','case_id','atomic_claim','claim_semantics','nonclaim_')):return 'level_2_reference_contract','segmentation_or_schema_failure'
 if s.startswith(('citation','support_reason')):return 'level_2_reference_contract','support_contract_failure'
 return 'level_2_reference_contract','reference_contract_failure'
def execute(r):
 if not manifest(r).exists() or load(manifest(r))!=expected_manifest(r):raise ValueError('manifest_not_frozen_or_drift')
 if negative(r).exists():raise ValueError('authoritative_negative_exists_no_retry')
 if submission(r).exists():print(json.dumps({'status':'already_completed_no_retry','reviewer':r,'submission_sha256':sha(submission(r))},indent=2));return 0
 if read_entries(attempts(r)):raise ValueError('attempt_log_exists_without_terminal_no_retry')
 key=os.environ.get(CRED,'').strip()
 if not key:raise ValueError(f'{CRED}_missing')
 d=load(DATASET);text=PROMPT.read_text(encoding='utf-8-sig');system=text.split('## System message\n',1)[1].split('## User message template\n',1)[0].strip();mh=sha(manifest(r));all_cases=[];case_results=[];reported=set();families=set()
 for case in d['cases']:
  received=False;raw=b'';cid=case['case_id']
  try:
   user=json.dumps(packet_case(case),ensure_ascii=False,separators=(',',':'));raw=call(key,REVIEWERS[r]['model'],system,user);received=True;eh=shab(raw);rep,can,ch,obj=parse_envelope(raw,REVIEWERS[r]['model']);norm=normalize(case,obj,r)
   cp={'schema_version':1,'checkpoint_id':f'{cid}-{r}-reference-v1','status':'authoritative_success','manifest_sha256':mh,'reviewer':r,'case_id':cid,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'canonical_model_family':can,'normalized_case_sha256':csha(norm),'normalized_case':norm,'raw_provider_response_stored':False}
   write_once(checkpoint(r,cid),cp);append_event({'event_type':'independent_reference_case_authoritative_success','manifest_sha256':mh,'reviewer':r,'case_id':cid,'response_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'normalized_output_sha256':csha(norm),'provider_reported_model':rep,'canonical_model_family':can},attempts(r));all_cases.append(norm);case_results.append({'case_id':cid,'status':'completed','claim_count':norm['claim_count'],'candidate_reference_label':norm['candidate_reference_label']});reported.add(rep);families.add(can);print(f'Reference {r.upper()} {len(all_cases)}/40 {cid}: {norm["claim_count"]} claims {norm["candidate_reference_label"]}',flush=True)
  except Exception as e:
   level,sub=classify(e,received);event={'event_type':'independent_reference_case_authoritative_failure','manifest_sha256':mh,'reviewer':r,'case_id':cid,'response_received':received,'authoritative_result':True,'provider_envelope_sha256':shab(raw) if raw else None,'failure_level':level,'failure_subtype':sub,'failure_reason':str(e),'same_version_retry_allowed':False};append_event(event,attempts(r));neg={'schema_version':1,'negative_result_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-negative-result-v1','status':'authoritative_negative_result','reviewer':r,'failed_case_id':cid,'completed_case_count':len(all_cases),'manifest_sha256':mh,'failure_level':level,'failure_subtype':sub,'failure_reason':str(e),'response_received':received,'provider_envelope_sha256':shab(raw) if raw else None,'provider_content_sha256':None,'same_version_retry_allowed':False,'agreement_allowed':False,'reference_freeze_allowed':False,'boundary_capability_conclusion_authorized':level=='level_2_reference_contract','raw_provider_response_stored':False};write_once(negative(r),neg);print(json.dumps(neg,ensure_ascii=False,indent=2));return 4
 if len(all_cases)!=40:raise ValueError('case_accounting_mismatch')
 out={'schema_version':1,'submission_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-submission-v1','status':'completed_independent_blind_reference_review','reviewer':r,'model_requested':REVIEWERS[r]['model'],'execution_manifest_sha256':mh,'case_count':40,'cases':all_cases,'candidate_label_counts':dict(sorted(Counter(x['candidate_reference_label'] for x in all_cases).items())),'total_claim_count':sum(x['claim_count'] for x in all_cases),'other_reviewer_visible':False,'route_a_gold_visible':False,'arm_outputs_visible':False,'confirmatory_visible':False};write_once(submission(r),out)
 res={'schema_version':1,'execution_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-execution-v1','status':'completed','reviewer':r,'manifest_sha256':mh,'submission_sha256':sha(submission(r)),'model_requested':REVIEWERS[r]['model'],'canonical_model_family':next(iter(families)),'provider_reported_models':sorted(reported),'completed_case_count':40,'total_claim_count':out['total_claim_count'],'candidate_label_counts':out['candidate_label_counts'],'case_results':case_results,'raw_provider_responses_stored':False};write_once(result(r),res);print(json.dumps({'status':'completed','reviewer':r,'cases':40,'claims':out['total_claim_count'],'labels':out['candidate_label_counts'],'submission_sha256':sha(submission(r))},indent=2));return 0
def verify_prepared():
 checks={'protocol':PROTOCOL.exists() and load(PROTOCOL)==protocol_doc(),'policy':EXEC_POLICY.exists() and load(EXEC_POLICY)==policy_doc(),'prompt':PROMPT.exists() and PROMPT.read_text(encoding='utf-8-sig')==prompt_text(),'fixtures':FIXTURES.exists() and load(FIXTURES)==fixtures_doc(),'fixtures_pass':FIXTURES.exists() and load(FIXTURES)['status']=='PASS',**entry_gate()};out={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'provider_called':False};print(json.dumps(out,indent=2));return out['status']=='PASS'
def verify_execution(r):
 done=submission(r).exists() and result(r).exists();neg=negative(r).exists();entries=read_entries(attempts(r));checks={'manifest':manifest(r).exists() and load(manifest(r))==expected_manifest(r),'terminal_xor':done!=neg,'attempt_log_nonempty':bool(entries)}
 if done:
  s=load(submission(r));res=load(result(r));checks.update({'submission_cases_40':len(s.get('cases',[]))==40,'result_completed':res.get('status')=='completed','submission_hash':res.get('submission_sha256')==sha(submission(r)),'checkpoints_40':len(list(checkpoint_dir(r).glob('*.json')))==40,'blind':s.get('other_reviewer_visible') is False and s.get('arm_outputs_visible') is False})
 if neg:checks.update({'negative_authoritative':load(negative(r)).get('status')=='authoritative_negative_result','no_retry':load(negative(r)).get('same_version_retry_allowed') is False})
 out={'status':'PASS' if all(checks.values()) else 'FAIL','reviewer':r,'terminal':'completed' if done else ('authoritative_negative_result' if neg else 'missing'),'checks':checks,'attempt_entries':len(entries)};print(json.dumps(out,indent=2));return out['status']=='PASS'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--verify-prepared',action='store_true');ap.add_argument('--freeze-manifest',choices=sorted(REVIEWERS));ap.add_argument('--execute',choices=sorted(REVIEWERS));ap.add_argument('--verify-execution',choices=sorted(REVIEWERS));a=ap.parse_args();acts=[a.prepare,a.verify_prepared,a.freeze_manifest is not None,a.execute is not None,a.verify_execution is not None]
 if sum(bool(x) for x in acts)!=1:ap.error('choose one action')
 if a.prepare:prepare();return 0
 if a.verify_prepared:return 0 if verify_prepared() else 1
 if a.freeze_manifest:freeze_manifest(a.freeze_manifest);return 0
 if a.execute:return execute(a.execute)
 return 0 if verify_execution(a.verify_execution) else 1
if __name__=='__main__':raise SystemExit(main())
