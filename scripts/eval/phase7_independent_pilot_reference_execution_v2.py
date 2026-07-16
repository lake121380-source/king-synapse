#!/usr/bin/env python3
"""Successor v2: whole-Candidate operation for the single-proposition Pilot frame."""
from __future__ import annotations
import argparse, hashlib, json, os, tempfile, urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event,read_entries
ROOT=Path(__file__).resolve().parents[2];CONFIG=ROOT/'crates/eval/config';DATA=ROOT/'crates/eval/datasets/pattern_extraction';REPORTS=ROOT/'crates/eval/reports'
DATASET=DATA/'phase7_3_3_d_independent_pilot_selected_dataset_v1.json';CONTENT_RECEIPT=REPORTS/'phase7_3_3_d_independent_pilot_content_open_receipt_v1.json';V1_NEG=REPORTS/'phase7_3_3_d_independent_pilot_reference_reviewer_a_negative_result_v1.json';STATE=DATA/'phase7_3_3_d_support_stage_state_v15.json';READY=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v26.json';REF_POLICY=CONFIG/'phase7_3_3_d_independent_reference_policy_v1.json'
PROTOCOL=CONFIG/'phase7_3_3_d_independent_pilot_reference_execution_protocol_v2.json';POLICY=CONFIG/'phase7_3_3_d_independent_pilot_reference_execution_policy_v2.json';PROMPT=CONFIG/'phase7_3_3_d_independent_pilot_reference_reviewer_prompt_v2.md';AUDIT=REPORTS/'phase7_3_3_d_independent_pilot_single_proposition_frame_audit_v1.json';FIXTURES=REPORTS/'phase7_3_3_d_independent_pilot_reference_execution_contract_fixtures_v2.json'
BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';TEMP=0;TOP_P=1;MAX_TOKENS=1600;TIMEOUT=600;RF={'type':'json_object'}
REVIEWERS={'a':{'model':'gpt-4.1'},'b':{'model':'qwen3.5-plus'}}
TYPES={'proposition','causal','scope','prediction','falsifiability','qualification','boundary','preference','temporal_update','selection_rule','other'};LABELS={'supported','partially_supported','unsupported','not_assessable'};CONF={'low','medium','high'};REASONS={'direct_evidence_match','conservative_entailment','reasonable_bridging_inference','scope_preserved','scope_expansion','certainty_escalation','causal_leap','prediction_overcommitment','unsupported_detail','counterexample_ignored','insufficient_evidence','conflicting_evidence','temporal_resolution','reliability_resolution','context_constraint_match'}
TOP={'case_id','atomicity_status','claim_type','material','support_label','cited_evidence_ids','reason_codes','rationale','confidence'}
def manifest(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_execution_manifest_v2.json'
def attempts(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_execution_attempts_v2.jsonl'
def checkpoint_dir(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_cases_v2'
def checkpoint(r,c):return checkpoint_dir(r)/f'{c}.json'
def submission(r):return DATA/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_submission_v2.json'
def result(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_execution_result_v2.json'
def negative(r):return REPORTS/f'phase7_3_3_d_independent_pilot_reference_reviewer_{r}_negative_result_v2.json'
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
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return shab(b)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return shab(b)
def protocol_doc():return {'schema_version':2,'protocol_id':'phase7.3.3-d-independent-pilot-reference-execution-protocol-v2','status':'frozen_successor_after_v1_negative','predecessor':{'protocol':'phase7.3.3-d-independent-pilot-reference-execution-protocol-v1','reviewer_a_negative_result_sha256':sha(V1_NEG),'v1_failure':'token_partition_incomplete','v1_same_version_retry':False},'controlled_change':'replace mandatory token partition serialization with whole_candidate_claim operation plus explicit atomicity validation','unchanged':{'dataset':True,'evidence':True,'reviewers':True,'models':True,'support_semantics':True,'blinding':True,'failure_policy':True},'frame_hypothesis':'selected Candidates are each representable as one comparative or selection proposition','reviewer_task':{'validate_single_atomic_claim':True,'judge_materiality':True,'judge_support':True,'cite_same_case_evidence':True},'adapter_outputs':{'claim_span':'entire_candidate','non_claim_spans':[],'candidate_reference_label':'support_label','material_error_span':'entire_candidate_if_material_and_not_supported'},'failure':{'atomicity_not_single_blocks_v2_reference':True,'first_content_authoritative':True,'semantic_retry':False,'repair':False},'provider':{'base_url':BASE,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'case_isolation':True},'blinding':{'other_reviewer_visible':False,'route_a_gold_visible':False,'historical_labels_visible':False,'arms_visible':False},'runtime':{'integration':False,'memory_write':False}}
def policy_doc():return {'schema_version':2,'policy_id':'phase7.3.3-d-independent-pilot-reference-execution-policy-v2','status':'frozen','case_count':40,'reviewer_count':2,'attempts_per_case':1,'required_fields':sorted(TOP),'atomicity_required_value':'single_atomic_claim','claim_type_enum':sorted(TYPES),'support_label_enum':sorted(LABELS),'confidence_enum':sorted(CONF),'reason_code_enum':sorted(REASONS),'same_case_citations_only':True,'full_candidate_span_only':True,'first_content_authoritative':True,'semantic_retry':False,'output_repair':False,'raw_provider_response_stored':False,'provider_hashes_stored':True}
def prompt_text():return '''# Phase 7.3.3-D Independent Pilot Reference Reviewer v2\n\n## System message\nYou are one independent blind Reference reviewer. Use only the supplied Candidate, query context, and same-case Evidence. You cannot see another reviewer, Route A Gold, historical labels, or either evaluation arm. Return one bare JSON object and no markdown.\n\nThis successor protocol removes token-index serialization. For this frozen Pilot frame, evaluate whether the entire Candidate is one atomic comparative/selection proposition. `atomicity_status` MUST be `single_atomic_claim` if the whole Candidate expresses one independently judgeable proposition. If it does not, return `requires_segmentation`; that is an authoritative v2 failure and must not be hidden. Do not rewrite or quote the Candidate.\n\nWhen it is a single Atomic Claim, judge the whole Candidate conservatively against the Evidence. `supported` requires support for the complete scope, certainty, temporal/reliability comparison, and selection relation. `partially_supported` means a material portion is supported but the whole is not. `unsupported` means support is absent or contradicted. Cite only supplied evidence IDs.\n\nReturn exactly these keys:\n{"case_id":"...","atomicity_status":"single_atomic_claim","claim_type":"selection_rule","material":true,"support_label":"supported","cited_evidence_ids":["..."],"reason_codes":["direct_evidence_match"],"rationale":"...","confidence":"high"}\n\n## User message template\n{CASE_PACKET_JSON}\n'''
def frame_audit():
 d=load(DATASET);texts=[c['candidate_text'] for c in d['cases']];unique=sorted(set(texts));items=[]
 for t in unique:items.append({'candidate_sha256':shab(t.encode()),'occurrence_count':texts.count(t),'unicode_character_count':len(t),'terminal_punctuation_present':bool(t and t[-1] in '.!?;:'),'newline_present':'\n' in t,'candidate_text_emitted':False})
 return {'schema_version':1,'audit_id':'phase7.3.3-d-independent-pilot-single-proposition-frame-audit-v1','status':'descriptive_structural_audit_not_semantic_gold','case_count':len(texts),'unique_candidate_text_count':len(unique),'duplicate_candidate_count':len(texts)-len(unique),'all_single_line':all(not x['newline_present'] for x in items),'candidate_texts_emitted':False,'semantic_atomicity_must_be_independently_validated':True,'items':items}
def exact(o):
 if not isinstance(o,dict) or set(o)!=TOP:raise ValueError('response_fields_invalid')
def normalize(case,o,r):
 exact(o)
 if o['case_id']!=case['case_id']:raise ValueError('case_id_mismatch')
 if o['atomicity_status']!='single_atomic_claim':raise ValueError(f'atomicity_requires_segmentation:{o["atomicity_status"]}')
 if o['claim_type'] not in TYPES or not isinstance(o['material'],bool) or o['support_label'] not in LABELS or o['confidence'] not in CONF:raise ValueError('decision_enum_invalid')
 valid=set(case['valid_evidence_ids'])
 if not isinstance(o['cited_evidence_ids'],list) or len(o['cited_evidence_ids'])!=len(set(o['cited_evidence_ids'])) or any(x not in valid for x in o['cited_evidence_ids']):raise ValueError('citation_invalid')
 if not isinstance(o['reason_codes'],list) or any(x not in REASONS for x in o['reason_codes']):raise ValueError('reason_invalid')
 if not isinstance(o['rationale'],str) or not o['rationale'].strip():raise ValueError('rationale_required')
 span={'start':0,'end':len(case['candidate_text'])};cid=f'{case["case_id"]}-{r}-claim-01'
 claim={'reference_claim_id':cid,'source_span':span,'source_text_sha256':case['candidate_sha256'],'claim_type':o['claim_type'],'material':o['material'],'support_label':o['support_label'],'cited_evidence_ids':o['cited_evidence_ids'],'reason_codes':o['reason_codes'],'rationale':o['rationale'].strip(),'confidence':o['confidence']}
 return {'case_id':case['case_id'],'candidate_sha256':case['candidate_sha256'],'atomicity_status':'single_atomic_claim','claims':[claim],'explicit_non_claim_spans':[],'candidate_reference_label':o['support_label'],'material_error_spans':[{'reference_claim_id':cid,'source_span':span,'support_label':o['support_label']}] if o['material'] and o['support_label']!='supported' else [],'coverage_complete':True}
def fixture_doc():
 c={'case_id':'f','candidate_text':'alpha','candidate_sha256':shab(b'alpha'),'valid_evidence_ids':['e1']};good={'case_id':'f','atomicity_status':'single_atomic_claim','claim_type':'proposition','material':True,'support_label':'supported','cited_evidence_ids':['e1'],'reason_codes':['direct_evidence_match'],'rationale':'ok','confidence':'high'};tests=[]
 def t(n,o,expected=True):
  try:normalize(c,o,'x');ok=True
  except:ok=False
  tests.append({'fixture_id':n,'status':'PASS' if ok==expected else 'FAIL'})
 t('valid',good);x=dict(good);x['atomicity_status']='requires_segmentation';t('reject_requires_segmentation',x,False);x=dict(good);x['cited_evidence_ids']=['bad'];t('reject_bad_citation',x,False);x=dict(good);x['support_label']='maybe';t('reject_bad_label',x,False);x=dict(good);x['extra']=1;t('reject_extra',x,False);return {'schema_version':2,'fixture_suite_id':'phase7.3.3-d-independent-pilot-reference-execution-contract-fixtures-v2','status':'PASS' if all(x['status']=='PASS' for x in tests) else 'FAIL','passed':sum(x['status']=='PASS' for x in tests),'total':len(tests),'fixtures':tests}
def gate():
 for p in [DATASET,CONTENT_RECEIPT,V1_NEG,STATE,READY,REF_POLICY]:
  if not p.exists():raise FileNotFoundError(p)
 if load(V1_NEG).get('same_version_retry_allowed') is not False:raise ValueError('v1_negative_not_immutable')
 if load(DATASET).get('case_count')!=40 or load(STATE).get('next_authorized_stage')!='freeze_independent_pilot_reference_execution_protocol_v1':raise ValueError('entry_gate_invalid')
def prepare():
 gate();write_once(PROTOCOL,protocol_doc());write_once(POLICY,policy_doc());write_text_once(PROMPT,prompt_text());write_once(AUDIT,frame_audit());f=fixture_doc();write_once(FIXTURES,f);print(json.dumps({'status':f['status'],'controlled_change':'whole_candidate_operation','unique_candidate_texts':load(AUDIT)['unique_candidate_text_count'],'duplicate_candidates':load(AUDIT)['duplicate_candidate_count'],'fixtures':f'{f["passed"]}/{f["total"]}','provider_called':False},indent=2))
def expected_manifest(r):
 gate();return {'schema_version':2,'manifest_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-execution-manifest-v2','status':'frozen_not_started','reviewer':r,'provider':'api.gpt.ge','provider_base_url':BASE,'model_requested':REVIEWERS[r]['model'],'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'credential_env_name':CRED,'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(PROTOCOL),'execution_policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'frame_audit_sha256':sha(AUDIT),'fixtures_sha256':sha(FIXTURES),'dataset_sha256':sha(DATASET),'content_receipt_sha256':sha(CONTENT_RECEIPT),'v1_negative_sha256':sha(V1_NEG),'case_count':40,'case_isolation':True,'first_content_authoritative':True,'semantic_retry':False,'output_repair':False,'other_reviewer_visible':False,'route_a_gold_visible':False,'arms_visible':False,'confirmatory_visible':False,'raw_provider_responses_stored':False}
def freeze_manifest(r):print(json.dumps({'status':'PASS','reviewer':r,'manifest_sha256':write_once(manifest(r),expected_manifest(r)),'provider_called':False},indent=2))
def canonical(req,rep):
 tail=rep.strip().lower().rsplit('/',1)[-1];q=req.lower()
 if tail==q or (q=='gpt-4.1' and tail.startswith('gpt-4.1-')) or (q=='qwen3.5-plus' and tail.startswith('qwen3.5-plus')):return req
 raise ValueError(f'provider_model_outside_requested_family:{rep}')
def call(key,model,system,user):
 payload={'model':model,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as resp:return resp.read()
def parse(raw,requested):
 env=json.loads(raw.decode());rep=env.get('model') if isinstance(env,dict) else None
 if not isinstance(rep,str) or not rep.strip():raise ValueError('provider_reported_model_missing')
 can=canonical(requested,rep);choices=env.get('choices');msg=choices[0].get('message') if isinstance(choices,list) and choices and isinstance(choices[0],dict) else None;content=msg.get('content') if isinstance(msg,dict) else None
 if not isinstance(content,str) or not content.strip():raise ValueError('provider_content_missing')
 return rep,can,shab(content.encode()),json.loads(content)
def execute(r):
 if not manifest(r).exists() or load(manifest(r))!=expected_manifest(r):raise ValueError('manifest_invalid')
 if negative(r).exists():raise ValueError('negative_exists_no_retry')
 if submission(r).exists():print(json.dumps({'status':'already_completed_no_retry','reviewer':r},indent=2));return 0
 if read_entries(attempts(r)):raise ValueError('attempt_log_exists_without_terminal_no_retry')
 key=os.environ.get(CRED,'').strip()
 if not key:raise ValueError(f'{CRED}_missing')
 d=load(DATASET);txt=PROMPT.read_text(encoding='utf-8-sig');system=txt.split('## System message\n',1)[1].split('## User message template\n',1)[0].strip();mh=sha(manifest(r));cases=[];reported=set();families=set()
 for case in d['cases']:
  raw=b'';received=False;cid=case['case_id']
  try:
   packet={'case_id':cid,'query_context':case['query_context'],'candidate_sha256':case['candidate_sha256'],'candidate_text':case['candidate_text'],'evidence_bundle':case['evidence_bundle'],'valid_evidence_ids':case['valid_evidence_ids'],'allowed_claim_types':sorted(TYPES),'allowed_support_labels':sorted(LABELS),'allowed_reason_codes':sorted(REASONS)};raw=call(key,REVIEWERS[r]['model'],system,json.dumps(packet,ensure_ascii=False,separators=(',',':')));received=True;eh=shab(raw);rep,can,ch,obj=parse(raw,REVIEWERS[r]['model']);norm=normalize(case,obj,r);write_once(checkpoint(r,cid),{'schema_version':2,'status':'authoritative_success','reviewer':r,'case_id':cid,'manifest_sha256':mh,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'canonical_model_family':can,'normalized_case_sha256':csha(norm),'normalized_case':norm,'raw_provider_response_stored':False});append_event({'event_type':'independent_reference_v2_case_authoritative_success','manifest_sha256':mh,'reviewer':r,'case_id':cid,'response_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'normalized_output_sha256':csha(norm),'provider_reported_model':rep,'canonical_model_family':can},attempts(r));cases.append(norm);reported.add(rep);families.add(can);print(f'Reference v2 {r.upper()} {len(cases)}/40 {cid}: {norm["candidate_reference_label"]}',flush=True)
  except Exception as e:
   reason=str(e);level='level_0_transport' if not received else ('level_1_provider_representation' if isinstance(e,json.JSONDecodeError) or reason.startswith('provider_') else 'level_2_reference_contract');sub='atomicity_failure' if reason.startswith('atomicity_') else ('transport_failure' if not received else 'schema_or_support_failure');append_event({'event_type':'independent_reference_v2_case_authoritative_failure','manifest_sha256':mh,'reviewer':r,'case_id':cid,'response_received':received,'authoritative_result':True,'provider_envelope_sha256':shab(raw) if raw else None,'failure_level':level,'failure_subtype':sub,'failure_reason':reason,'same_version_retry_allowed':False},attempts(r));neg={'schema_version':2,'negative_result_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-negative-result-v2','status':'authoritative_negative_result','reviewer':r,'failed_case_id':cid,'completed_case_count':len(cases),'manifest_sha256':mh,'failure_level':level,'failure_subtype':sub,'failure_reason':reason,'response_received':received,'provider_envelope_sha256':shab(raw) if raw else None,'same_version_retry_allowed':False,'reference_freeze_allowed':False,'raw_provider_response_stored':False};write_once(negative(r),neg);print(json.dumps(neg,ensure_ascii=False,indent=2));return 4
 out={'schema_version':2,'submission_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-submission-v2','status':'completed_independent_blind_reference_review','reviewer':r,'model_requested':REVIEWERS[r]['model'],'execution_manifest_sha256':mh,'case_count':40,'cases':cases,'candidate_label_counts':dict(sorted(Counter(x['candidate_reference_label'] for x in cases).items())),'total_claim_count':40,'other_reviewer_visible':False,'route_a_gold_visible':False,'arms_visible':False};write_once(submission(r),out);res={'schema_version':2,'execution_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-execution-v2','status':'completed','reviewer':r,'manifest_sha256':mh,'submission_sha256':sha(submission(r)),'model_requested':REVIEWERS[r]['model'],'canonical_model_family':next(iter(families)),'provider_reported_models':sorted(reported),'completed_case_count':40,'candidate_label_counts':out['candidate_label_counts'],'raw_provider_responses_stored':False};write_once(result(r),res);print(json.dumps({'status':'completed','reviewer':r,'cases':40,'labels':out['candidate_label_counts'],'submission_sha256':sha(submission(r))},indent=2));return 0
def verify_prepared():
 gate();checks={'protocol':load(PROTOCOL)==protocol_doc(),'policy':load(POLICY)==policy_doc(),'prompt':PROMPT.read_text(encoding='utf-8-sig')==prompt_text(),'audit':load(AUDIT)==frame_audit(),'fixtures':load(FIXTURES)==fixture_doc(),'fixtures_pass':load(FIXTURES)['status']=='PASS'};print(json.dumps({'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'provider_called':False},indent=2));return all(checks.values())
def verify_execution(r):
 done=submission(r).exists() and result(r).exists();neg=negative(r).exists();entries=read_entries(attempts(r));checks={'manifest':manifest(r).exists() and load(manifest(r))==expected_manifest(r),'terminal_xor':done!=neg,'attempts_nonempty':bool(entries)}
 if done:checks.update({'cases_40':len(load(submission(r)).get('cases',[]))==40,'checkpoints_40':len(list(checkpoint_dir(r).glob('*.json')))==40,'hash':load(result(r)).get('submission_sha256')==sha(submission(r))})
 if neg:checks.update({'negative':load(negative(r)).get('status')=='authoritative_negative_result','no_retry':load(negative(r)).get('same_version_retry_allowed') is False})
 out={'status':'PASS' if all(checks.values()) else 'FAIL','reviewer':r,'terminal':'completed' if done else ('authoritative_negative_result' if neg else 'missing'),'checks':checks,'attempt_entries':len(entries)};print(json.dumps(out,indent=2));return all(checks.values())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--verify-prepared',action='store_true');ap.add_argument('--freeze-manifest',choices=sorted(REVIEWERS));ap.add_argument('--execute',choices=sorted(REVIEWERS));ap.add_argument('--verify-execution',choices=sorted(REVIEWERS));a=ap.parse_args();acts=[a.prepare,a.verify_prepared,a.freeze_manifest is not None,a.execute is not None,a.verify_execution is not None]
 if sum(bool(x) for x in acts)!=1:ap.error('choose one')
 if a.prepare:prepare();return 0
 if a.verify_prepared:return 0 if verify_prepared() else 1
 if a.freeze_manifest:freeze_manifest(a.freeze_manifest);return 0
 if a.execute:return execute(a.execute)
 return 0 if verify_execution(a.verify_execution) else 1
if __name__=='__main__':raise SystemExit(main())
