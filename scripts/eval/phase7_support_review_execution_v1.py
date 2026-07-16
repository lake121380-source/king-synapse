#!/usr/bin/env python3
from __future__ import annotations
import argparse,copy,hashlib,json,os,tempfile,urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event,read_entries
ROOT=Path(__file__).resolve().parents[2];CONFIG=ROOT/'crates/eval/config';DATA=ROOT/'crates/eval/datasets/pattern_extraction';REPORTS=ROOT/'crates/eval/reports'
PROTOCOL=CONFIG/'phase7_3_3_d_support_review_execution_protocol_v1.json';POLICY=CONFIG/'phase7_3_3_d_support_review_execution_policy_v1.json';PROMPT=CONFIG/'phase7_3_3_d_support_reviewer_prompt_v1.md';FIXTURES=REPORTS/'phase7_3_3_d_support_review_contract_fixtures_v1.json'
GOLD=DATA/'phase7_3_3_d_boundary_gold_v1.json';FREEZE=REPORTS/'phase7_3_3_d_boundary_gold_freeze_receipt_v1.json';STATE=DATA/'phase7_3_3_d_support_stage_state_v4.json';READY=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v15.json';CORRECTION=REPORTS/'phase7_3_3_d_support_lineage_correction_receipt_v1.json'
BASE='https://api.gpt.ge/v1';CRED='DEEPSEEK_API_KEY';TEMP=0;TOP_P=1;MAX_TOKENS=16000;TIMEOUT=600;RF={'type':'json_object'}
REVIEWERS={'a':{'label':'Reviewer A','model':'gpt-4.1'},'b':{'label':'Reviewer B','model':'qwen3.5-plus'}}
LABELS={'supported','partially_supported','unsupported','not_assessable'};CONF={'low','medium','high'}
REASONS={'direct_evidence_match','conservative_entailment','reasonable_bridging_inference','scope_preserved','counterexample_preserved','scope_expansion','certainty_escalation','causal_leap','prediction_overcommitment','unsupported_detail','counterexample_ignored','central_proposition_unsupported','insufficient_evidence'}
TOP={'case_id','decisions'};DKEYS={'boundary_claim_id','support_label','cited_evidence_ids','reason_codes','support_rationale','annotation_confidence'}
def packet(r):return DATA/f'phase7_3_3_d_support_reviewer_{r}_packet_v1.json'
def template(r):return DATA/f'phase7_3_3_d_support_reviewer_{r}_submission_v2.json'
def manifest(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_execution_manifest_v1.json'
def attempts(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_execution_attempts_v1.jsonl'
def checkpoint(r,c):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_cases_v1'/f'{c}.json'
def submission(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_completed_submission_v1.json'
def result(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_execution_result_v1.json'
def negative(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_negative_result_v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def shab(b):return hashlib.sha256(b).hexdigest()
def csha(v):return shab(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
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
def protocol_doc():return {'schema_version':1,'protocol_id':'phase7.3.3-d1-b-independent-support-review-execution-v1','stage':'Phase 7.3.3-D1 Independent Support Review Execution','research_object':'independent evidence support classification for immutable Boundary Gold Claims','entry_gate':{'boundary_gold_frozen':True,'boundary_claim_count':118,'support_packets_frozen':True,'lineage_correction_completed':True,'support_review_execution_authorized':True,'support_gold_frozen':False,'held_out_accessed':False},'reviewers':{'a':{'model_requested':'gpt-4.1'},'b':{'model_requested':'qwen3.5-plus'}},'independence':{'case_isolation':True,'reviewer_packet_isolation':True,'other_reviewer_submission_visible':False,'candidate_gold_or_silver_visible':False,'judge_outputs_visible':False,'boundary_adjudication_rationales_visible':False,'held_out_visible':False},'output_contract':{'one_decision_per_frozen_boundary_claim':True,'claim_order_must_match_packet':True,'required_top_level_keys':sorted(TOP),'required_decision_keys':sorted(DKEYS),'support_label_enum':sorted(LABELS),'reason_code_enum':sorted(REASONS),'confidence_enum':sorted(CONF),'same_case_citations_only':True,'citations_may_be_empty':True,'reason_codes_may_be_empty':True,'duplicates_forbidden':True,'nonempty_rationale':True,'boundary_mutation_forbidden':True},'provider_contract':{'provider':'api.gpt.ge','base_url':BASE,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'first_provider_content_authoritative':True,'no_silent_retry_after_any_failure':True,'envelope_and_content_hashes_recorded_before_content_validation':True,'raw_provider_response_stored':False},'model_identity_canonicalization':{'provider_prefix_allowed':True,'gpt_4_1_dated_snapshot_allowed':True,'canonical_family_must_equal_requested_model':True},'completion_gate':{'case_count':10,'decision_count':118,'no_missing_duplicate_unknown_ids':True,'all_fields_valid':True},'failure_policy':{'all_transport_identity_parse_schema_citation_accounting_failures_first_class':True,'same_frozen_version_retry_forbidden':True,'other_reviewer_may_still_execute':True,'agreement_requires_two_completed_submissions':True}}
def policy_doc():return {'schema_version':1,'policy_id':'phase7.3.3-d1-b-support-review-execution-policy-v1','execution_order':'independent reviewers; sequential invocation exposes no outputs','case_order':'frozen_packet_order','attempt_policy':'one authoritative provider attempt per case; any failure freezes reviewer version','checkpoint_policy':'successful case checkpoints immutable','raw_content_storage':'disabled; hashes retained','agreement_policy':'not computed here','support_gold_policy':'remains unfrozen','credential_env_name':CRED,'secret_persistence':'forbidden'}
def prompt_text():return '''# Phase 7.3.3-D1 Independent Support Reviewer Prompt v1

## System message
You are one independent Support Reviewer in a frozen scientific evaluation. Classify evidential support for every immutable Boundary Claim in the supplied single-case packet using only its frozen evidence bundle. Do not use outside knowledge, web search, memory, hidden context, or another reviewer's work. Do not create, delete, split, merge, rewrite, or reorder claims.

Labels: supported = claim strength, scope, and causal language are supported; partially_supported = core direction is supported but scope, prediction, certainty, causality, or detail is stronger than evidence; unsupported = material claim cannot be established; not_assessable = evidence or claim boundary is insufficient for stable adjudication.

Allowed reason codes: direct_evidence_match, conservative_entailment, reasonable_bridging_inference, scope_preserved, counterexample_preserved, scope_expansion, certainty_escalation, causal_leap, prediction_overcommitment, unsupported_detail, counterexample_ignored, central_proposition_unsupported, insufficient_evidence.

Return exactly one decision per boundary_claim_id in exact packet order. cited_evidence_ids may contain only same-case memory_id values and may be empty. reason_codes may contain only allowed values and may be empty. Lists must not contain duplicates. support_rationale must be concise, nonempty, and evidence-grounded. annotation_confidence must be low, medium, or high. Preserve scope/certainty/causality/prediction/qualification/counterexample distinctions. Output a bare JSON object only, without Markdown or extra keys.

Schema: {"case_id":"<exact>","decisions":[{"boundary_claim_id":"<exact>","support_label":"supported|partially_supported|unsupported|not_assessable","cited_evidence_ids":["<same-case memory_id>"],"reason_codes":["<allowed>"],"support_rationale":"<nonempty>","annotation_confidence":"low|medium|high"}]}

## User message template
Review this single frozen case packet and return every decision in exact order.

{CASE_PACKET_JSON}
'''
def split_prompt():
 t=PROMPT.read_text(encoding='utf-8-sig');sm='## System message\n';um='## User message template\n'
 if sm not in t or um not in t:raise ValueError('prompt_sections_missing')
 return t.split(sm,1)[1].split(um,1)[0].strip(),t.split(um,1)[1].strip()
def normalize(case,obj):
 if not isinstance(obj,dict) or set(obj)!=TOP:raise ValueError('response_top_level_schema_invalid')
 if obj.get('case_id')!=case['case_id']:raise ValueError('response_case_id_mismatch')
 ds=obj.get('decisions');ids=[x['boundary_claim_id'] for x in case['boundary_claims']];valid=set(case['valid_evidence_ids'])
 if not isinstance(ds,list) or len(ds)!=len(ids):raise ValueError('decision_count_mismatch')
 out=[];seen=set()
 for i,d in enumerate(ds):
  if not isinstance(d,dict) or set(d)!=DKEYS:raise ValueError(f'decision_schema_invalid:{i}')
  cid=d.get('boundary_claim_id')
  if cid!=ids[i]:raise ValueError(f'claim_order_or_identity_mismatch:{i}')
  if cid in seen:raise ValueError(f'duplicate_boundary_claim_id:{cid}')
  seen.add(cid);lab=d.get('support_label');cit=d.get('cited_evidence_ids');rea=d.get('reason_codes');rat=d.get('support_rationale');con=d.get('annotation_confidence')
  if lab not in LABELS:raise ValueError(f'support_label_invalid:{cid}')
  if not isinstance(cit,list) or any(not isinstance(x,str) for x in cit):raise ValueError(f'cited_evidence_ids_invalid:{cid}')
  if len(set(cit))!=len(cit):raise ValueError(f'duplicate_cited_evidence_id:{cid}')
  bad=sorted(set(cit)-valid)
  if bad:raise ValueError(f'citation_outside_case:{cid}:{bad}')
  if not isinstance(rea,list) or any(not isinstance(x,str) for x in rea):raise ValueError(f'reason_codes_invalid:{cid}')
  if len(set(rea))!=len(rea):raise ValueError(f'duplicate_reason_code:{cid}')
  bad=sorted(set(rea)-REASONS)
  if bad:raise ValueError(f'reason_code_unknown:{cid}:{bad}')
  if not isinstance(rat,str) or not rat.strip():raise ValueError(f'support_rationale_missing:{cid}')
  if con not in CONF:raise ValueError(f'annotation_confidence_invalid:{cid}')
  out.append({'boundary_claim_id':cid,'support_label':lab,'cited_evidence_ids':cit,'reason_codes':rea,'support_rationale':rat.strip(),'annotation_confidence':con})
 return out
def fixtures_doc():
 case={'case_id':'fixture','valid_evidence_ids':['e1','e2'],'boundary_claims':[{'boundary_claim_id':'c1'},{'boundary_claim_id':'c2'}]};d1={'boundary_claim_id':'c1','support_label':'supported','cited_evidence_ids':['e1'],'reason_codes':['direct_evidence_match'],'support_rationale':'Direct.','annotation_confidence':'high'};d2={'boundary_claim_id':'c2','support_label':'unsupported','cited_evidence_ids':[],'reason_codes':['insufficient_evidence'],'support_rationale':'Absent.','annotation_confidence':'medium'};v={'case_id':'fixture','decisions':[d1,d2]}
 fs=[('valid',v,1),('empty_reasons',{'case_id':'fixture','decisions':[{**d1,'reason_codes':[]},d2]},1),('extra_top',{**v,'x':1},0),('wrong_case',{**v,'case_id':'x'},0),('missing',{'case_id':'fixture','decisions':[d1]},0),('reorder',{'case_id':'fixture','decisions':[d2,d1]},0),('bad_label',{'case_id':'fixture','decisions':[{**d1,'support_label':'not_supported'},d2]},0),('bad_citation',{'case_id':'fixture','decisions':[{**d1,'cited_evidence_ids':['e3']},d2]},0),('bad_reason',{'case_id':'fixture','decisions':[{**d1,'reason_codes':['x']},d2]},0),('blank',{'case_id':'fixture','decisions':[{**d1,'support_rationale':' '},d2]},0),('bad_conf',{'case_id':'fixture','decisions':[{**d1,'annotation_confidence':'certain'},d2]},0),('extra_field',{'case_id':'fixture','decisions':[{**d1,'claim_text':'x'},d2]},0),('dup_citation',{'case_id':'fixture','decisions':[{**d1,'cited_evidence_ids':['e1','e1']},d2]},0),('dup_reason',{'case_id':'fixture','decisions':[{**d1,'reason_codes':['direct_evidence_match']*2},d2]},0)]
 rs=[]
 for n,p,w in fs:
  ok=1;err=None
  try:normalize(case,p)
  except Exception as e:ok=0;err=str(e)
  rs.append({'fixture':n,'expected_pass':bool(w),'observed_pass':bool(ok),'fixture_passed':ok==w,'observed_error':err})
 return {'schema_version':1,'report_id':'phase7.3.3-d1-b-support-review-contract-fixtures-v1','fixture_count':len(rs),'fixtures_passed':sum(x['fixture_passed'] for x in rs),'all_fixtures_passed':all(x['fixture_passed'] for x in rs),'provider_called':False,'held_out_accessed':False,'results':rs}
def entry_gate():
 req=[GOLD,FREEZE,STATE,READY,CORRECTION]+[packet(r) for r in REVIEWERS]+[template(r) for r in REVIEWERS];missing=[str(x.relative_to(ROOT)) for x in req if not x.exists()]
 if missing:raise ValueError(f'missing:{missing}')
 s=load(STATE);rd=load(READY);cr=load(CORRECTION);checks={'state_v4':s.get('schema_version')==4,'gold_hash':s.get('boundary_gold_sha256')==sha(GOLD),'receipt_hash':s.get('boundary_gold_freeze_receipt_sha256')==sha(FREEZE),'correction':cr.get('status')=='completed_support_lineage_correction' and cr.get('support_stage_state_v4_sha256')==sha(STATE),'authorized':rd.get('next_authorized_stage')=='independent_support_review_execution','allowed':s.get('support_review_allowed') is True and rd.get('support_review_allowed') is True,'not_started':s.get('support_review_started') is False and rd.get('support_review_started') is False,'not_frozen':s.get('support_gold_frozen') is False and rd.get('support_gold_frozen') is False,'claims_118':s.get('boundary_claim_count')==118,'held_out_false':s.get('held_out_accessed') is False and rd.get('held_out_accessed') is False}
 for r in REVIEWERS:
  p=load(packet(r));t=load(template(r));checks[f'{r}_packet_hash']=s.get(f'reviewer_{r}_packet_sha256')==sha(packet(r));checks[f'{r}_template_hash']=s.get(f'reviewer_{r}_submission_template_sha256')==sha(template(r));checks[f'{r}_packet_118']=p.get('boundary_claim_count')==118;checks[f'{r}_template_empty']=len(t.get('claims',[]))==118 and all(x.get('support_label') is None for x in t['claims']);checks[f'{r}_blind']=p.get('blind_to_other_reviewer') is True and p.get('blind_to_candidate_gold_or_silver') is True and p.get('held_out_accessed') is False
 if not all(checks.values()):raise ValueError(f'entry_gate_failed:{[k for k,v in checks.items() if not v]}')
 return checks
def prepare():
 checks=entry_gate();hs={'protocol_sha256':write_once(PROTOCOL,protocol_doc()),'policy_sha256':write_once(POLICY,policy_doc()),'prompt_sha256':write_text_once(PROMPT,prompt_text()),'fixtures_sha256':write_once(FIXTURES,fixtures_doc())};f=load(FIXTURES)
 if not f.get('all_fixtures_passed'):raise ValueError('fixtures_failed')
 print(json.dumps({'status':'prepared_offline',**hs,'fixtures':f"{f['fixtures_passed']}/{f['fixture_count']}",'entry_gate_checks':checks,'provider_called':False,'held_out_accessed':False},indent=2))
def expected_manifest(r):
 entry_gate();cfg=REVIEWERS[r];p=load(packet(r));t=load(template(r));f=load(FIXTURES)
 if not f.get('all_fixtures_passed'):raise ValueError('fixtures_not_passed')
 return {'schema_version':1,'manifest_id':f'phase7.3.3-d1-b-support-reviewer-{r}-execution-v1','status':'frozen_not_started','reviewer':r,'reviewer_label':cfg['label'],'reviewer_type':'ai_model','provider':'api.gpt.ge','provider_base_url':BASE,'model_requested':cfg['model'],'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'credential_env_name':CRED,'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(PROTOCOL),'execution_policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'contract_fixtures_sha256':sha(FIXTURES),'boundary_gold_sha256':sha(GOLD),'boundary_gold_freeze_receipt_sha256':sha(FREEZE),'support_stage_state_v4_sha256':sha(STATE),'readiness_v15_sha256':sha(READY),'lineage_correction_receipt_sha256':sha(CORRECTION),'review_packet_sha256':sha(packet(r)),'submission_template_sha256':sha(template(r)),'packet_id':p['packet_id'],'case_count':p['case_count'],'boundary_claim_count':p['boundary_claim_count'],'evidence_item_count':p['evidence_item_count'],'packet_template_decision_count':len(t['claims']),'case_isolation':True,'other_reviewer_visible':False,'candidate_gold_or_silver_visible':False,'judge_outputs_visible':False,'boundary_adjudication_rationales_visible':False,'held_out_accessed':False,'external_tools_enabled':False,'web_access_enabled':False,'memory_enabled':False,'raw_provider_responses_stored':False,'first_provider_content_authoritative':True,'silent_retry_allowed':False,'model_identity_policy':'provider prefix accepted; gpt-4.1 dated snapshot accepted; canonical family equals requested'}
def freeze_manifest(r):print(json.dumps({'status':'manifest_frozen_not_started','reviewer':r,'model_requested':REVIEWERS[r]['model'],'manifest_sha256':write_once(manifest(r),expected_manifest(r)),'provider_called':False,'held_out_accessed':False},indent=2))
def canonical(requested,reported):
 tail=reported.strip().lower().rsplit('/',1)[-1];q=requested.lower()
 if tail==q or (q=='gpt-4.1' and tail.startswith('gpt-4.1-')):return requested
 raise ValueError(f'provider_model_outside_requested_family:{reported}')
def call(key,model,system,user):
 payload={'model':model,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RF,'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as resp:return resp.read()
def parse_envelope(raw,requested):
 env=json.loads(raw.decode());reported=env.get('model') if isinstance(env,dict) else None
 if not isinstance(reported,str) or not reported.strip():raise ValueError('provider_reported_model_missing')
 can=canonical(requested,reported);choices=env.get('choices')
 if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):raise ValueError('provider_choices_invalid')
 msg=choices[0].get('message')
 if not isinstance(msg,dict):raise ValueError('provider_message_invalid')
 content=msg.get('content')
 if not isinstance(content,str) or not content.strip():raise ValueError('provider_content_missing')
 ch=shab(content.encode());return reported,can,ch,json.loads(content)
def classify_failure(e,got):
 c=str(e)
 if not got:return 'level_0_transport','transport_failure'
 if c.startswith('provider_model') or c.startswith('provider_reported'):return 'level_1_provider_representation','identity_failure'
 if isinstance(e,json.JSONDecodeError) or c.startswith('provider_'):return 'level_1_provider_representation','parse_or_envelope_failure'
 if c.startswith(('response_','decision_','claim_order','duplicate_boundary')):return 'level_1_schema','schema_or_accounting_failure'
 if c.startswith(('citation_','cited_','duplicate_cited')):return 'level_2_support_contract','citation_failure'
 return 'level_2_support_contract','support_contract_failure'
def execute(r):
 if not manifest(r).exists():raise ValueError('manifest_not_frozen')
 if load(manifest(r))!=expected_manifest(r):raise ValueError('manifest_verification_failed')
 mh=sha(manifest(r))
 if negative(r).exists():raise ValueError('authoritative_negative_result_exists_no_retry')
 if submission(r).exists():print(json.dumps({'reviewer':r,'status':'already_completed_no_retry','submission_sha256':sha(submission(r))},indent=2));return 0
 if read_entries(attempts(r)):raise ValueError('existing_attempt_log_without_terminal_artifact_no_retry')
 key=os.environ.get(CRED,'').strip()
 if not key:raise ValueError(f'credential_env_missing:{CRED}')
 system,ut=split_prompt();p=load(packet(r));cfg=REVIEWERS[r];all_ds=[];case_rs=[];reported=set();families=set();append_event({'event_type':'support_review_execution_invocation','manifest_sha256':mh,'reviewer':r,'status':'started','response_received':False,'authoritative_result':False},attempts(r))
 for case in p['cases']:
  raw=None;eh=None;ch=None
  try:
   user=ut.replace('{CASE_PACKET_JSON}',json.dumps(case,ensure_ascii=False,separators=(',',':')));raw=call(key,cfg['model'],system,user);eh=shab(raw);rep,can,ch,obj=parse_envelope(raw,cfg['model']);ds=normalize(case,obj);saved={'schema_version':1,'checkpoint_id':f"phase7.3.3-d1-b-support-{r}-{case['case_id']}-v1",'status':'authoritative_success','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'canonical_model_family':can,'normalized_decisions_sha256':csha(ds),'decisions':ds,'case_result':{'case_id':case['case_id'],'status':'completed','decision_count':len(ds)},'raw_provider_response_stored':False,'held_out_accessed':False};write_once(checkpoint(r,case['case_id']),saved);append_event({'event_type':'support_review_case_authoritative_success','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'status':'completed','response_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'normalized_output_sha256':csha(ds),'decision_count':len(ds),'provider_reported_model':rep,'canonical_model_family':can},attempts(r));all_ds+=ds;case_rs.append(saved['case_result']);reported.add(rep);families.add(can);print(f"Reviewer {r.upper()} {case['case_id']}: {len(ds)} decisions",flush=True)
  except Exception as e:
   got=raw is not None;level,sub=classify_failure(e,got);append_event({'event_type':'support_review_case_authoritative_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'status':'authoritative_negative_result','failure_level':level,'failure_subtype':sub,'failure_type':type(e).__name__,'failure_code':str(e)[:500],'response_received':got,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'completed_case_count_before_failure':len(case_rs),'completed_decision_count_before_failure':len(all_ds)},attempts(r));neg={'schema_version':1,'result_id':f'phase7.3.3-d1-b-support-reviewer-{r}-negative-v1','status':'authoritative_negative_result','reviewer':r,'model_requested':cfg['model'],'manifest_sha256':mh,'failed_case_id':case['case_id'],'failure_level':level,'failure_subtype':sub,'failure_type':type(e).__name__,'failure_code':str(e)[:500],'response_received':got,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'completed_case_count_before_failure':len(case_rs),'completed_decision_count_before_failure':len(all_ds),'support_capability_conclusion_authorized':level=='level_2_support_contract','same_version_retry_allowed':False,'other_reviewer_execution_allowed':True,'agreement_allowed':False,'raw_provider_response_stored':False,'held_out_accessed':False};write_once(negative(r),neg);print(json.dumps(neg,ensure_ascii=False,indent=2));return 4
 if len(case_rs)!=p['case_count'] or len(all_ds)!=p['boundary_claim_count']:raise ValueError('completed_accounting_mismatch')
 if families!={cfg['model']}:raise ValueError(f'canonical_model_family_drift:{families}')
 ids=[x['boundary_claim_id'] for c in p['cases'] for x in c['boundary_claims']]
 if [x['boundary_claim_id'] for x in all_ds]!=ids:raise ValueError('global_claim_order_mismatch')
 out=copy.deepcopy(load(template(r)));out.update({'status':'completed_independent_support_review','completed':True,'blocked_reason':None,'claims':all_ds,'execution_manifest_sha256':mh,'reviewer_model_requested':cfg['model'],'completed_case_count':len(case_rs),'support_decision_count':len(all_ds)});write_once(submission(r),out);res={'schema_version':1,'execution_id':f'phase7.3.3-d1-b-support-reviewer-{r}-execution-v1','status':'completed','reviewer':r,'manifest_sha256':mh,'submission_sha256':sha(submission(r)),'model_requested':cfg['model'],'canonical_model_family':next(iter(families)),'provider_reported_models':sorted(reported),'completed_case_count':len(case_rs),'decision_count':len(all_ds),'support_label_counts':dict(sorted(Counter(x['support_label'] for x in all_ds).items())),'confidence_counts':dict(sorted(Counter(x['annotation_confidence'] for x in all_ds).items())),'case_results':case_rs,'raw_provider_responses_stored':False,'held_out_accessed':False,'agreement_computed':False,'support_gold_frozen':False};write_once(result(r),res);print(json.dumps({'reviewer':r,'status':'completed','model_requested':cfg['model'],'cases':len(case_rs),'decisions':len(all_ds),'support_label_counts':res['support_label_counts'],'submission_sha256':sha(submission(r))},indent=2));return 0
def verify_prepared():
 checks={'protocol':load(PROTOCOL)==protocol_doc(),'policy':load(POLICY)==policy_doc(),'prompt':PROMPT.read_text(encoding='utf-8-sig')==prompt_text(),'fixtures':load(FIXTURES)==fixtures_doc(),'fixtures_pass':load(FIXTURES).get('all_fixtures_passed') is True,**entry_gate()};print(json.dumps({'all_passed':all(checks.values()),'checks':checks,'hashes':{'adapter':sha(Path(__file__)),'protocol':sha(PROTOCOL),'policy':sha(POLICY),'prompt':sha(PROMPT),'fixtures':sha(FIXTURES)},'provider_called':False,'held_out_accessed':False},indent=2));
 if not all(checks.values()):raise ValueError('prepared_verification_failed')
def verify_execution(r):
 entries=read_entries(attempts(r));done=submission(r).exists() and result(r).exists();neg=negative(r).exists();checks={'manifest':manifest(r).exists() and load(manifest(r))==expected_manifest(r),'terminal_xor':done!=neg,'log_nonempty':bool(entries)}
 if done:
  p=load(packet(r));s=load(submission(r));res=load(result(r));ids=[x['boundary_claim_id'] for c in p['cases'] for x in c['boundary_claims']];checks.update({'submission_completed':s.get('completed') is True,'decisions_118':len(s.get('claims',[]))==118,'ids_exact':[x.get('boundary_claim_id') for x in s['claims']]==ids,'result_completed':res.get('status')=='completed','result_hash':res.get('submission_sha256')==sha(submission(r)),'checkpoints_10':len(list((REPORTS/f'phase7_3_3_d_support_reviewer_{r}_cases_v1').glob('*.json')))==10,'held_out_false':s.get('held_out_accessed') is False and res.get('held_out_accessed') is False})
 if neg:
  n=load(negative(r));checks.update({'negative_authoritative':n.get('status')=='authoritative_negative_result','no_retry':n.get('same_version_retry_allowed') is False,'agreement_blocked':n.get('agreement_allowed') is False,'held_out_false':n.get('held_out_accessed') is False})
 out={'reviewer':r,'status':'verified' if all(checks.values()) else 'failed','terminal_outcome':'completed' if done else ('authoritative_negative_result' if neg else 'missing'),'checks':checks,'attempt_log_entry_count':len(entries),'attempt_log_tail_sha256':entries[-1]['entry_sha256'] if entries else None};print(json.dumps(out,indent=2));
 if out['status']!='verified':raise ValueError('execution_verification_failed')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--verify-prepared',action='store_true');ap.add_argument('--freeze-manifest',choices=sorted(REVIEWERS));ap.add_argument('--execute',choices=sorted(REVIEWERS));ap.add_argument('--verify-execution',choices=sorted(REVIEWERS));a=ap.parse_args()
 if sum(bool(x) for x in [a.prepare,a.verify_prepared,a.freeze_manifest,a.execute,a.verify_execution])!=1:ap.error('choose one action')
 if a.prepare:prepare()
 elif a.verify_prepared:verify_prepared()
 elif a.freeze_manifest:freeze_manifest(a.freeze_manifest)
 elif a.execute:return execute(a.execute)
 else:verify_execution(a.verify_execution)
 return 0
if __name__=='__main__':raise SystemExit(main())
