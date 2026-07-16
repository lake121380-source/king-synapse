#!/usr/bin/env python3
"""Freeze, execute, and verify Phase 7.3.3-D successor Support label adjudication v1."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,re,urllib.error,urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event,read_entries
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
AP=C/'phase7_3_3_d_multi_claim_successor_support_agreement_protocol_v1.json';AF=R/'phase7_3_3_d_multi_claim_successor_support_agreement_contract_fixtures_v1.json';AM=R/'phase7_3_3_d_multi_claim_successor_support_agreement_manifest_v1.json';AR=R/'phase7_3_3_d_multi_claim_successor_support_agreement_report_v1.json';AO=R/'phase7_3_3_d_multi_claim_successor_support_agreement_outcome_v1.json';AC=R/'phase7_3_3_d_multi_claim_successor_support_agreement_receipt_v1.json';WL=D/'phase7_3_3_d_multi_claim_successor_support_label_disagreement_worklist_v1.json';DWL=D/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_worklist_v1.json';SI=D/'phase7_3_3_d_support_stage_state_v55.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v66.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_protocol_v1.json';POL=C/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_execution_policy_v1.json';SCH=C/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_schema_v1.json';PRM=C/'phase7_3_3_d_multi_claim_successor_support_label_adjudicator_prompt_v1.md';PKT=D/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_packet_v1.json';MAP=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_private_option_mapping_v1.json';FIX=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_contract_fixtures_v1.json';MAN=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_execution_manifest_v1.json';LOG=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_attempts_v1.jsonl';CASES=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_cases_v1';SUB=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_completed_submission_v1.json';RES=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_result_v1.json';NEG=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_negative_result_v1.json';REC=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_receipt_v1.json';SO=D/'phase7_3_3_d_support_stage_state_v56.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v67.json'
EXP={AP:'045a50265cecc04502b002803a3bf2ece063e0ffa587eecb888d70724b269e9c',AF:'a8a771f818f35a7e2fd57f32abb9b683f1d279cc4ae49d48c10ff20ec00d15bb',AM:'278d20a3a4d38a943e1c86290daa55ebd23915c4b274c1c8bf0bbbf05403b371',AR:'7a4795d268f6b00659451f2323ce30c8145810d948037764cbf4f4ae4e9c4a91',AO:'9bb7fed86362f620019a93a7d9745a6b8b49f412074ae68d9379d30b3bf33d20',AC:'94511a35c392420c65a586f22180a369494c164f47263d67f505580d4decf7d1',WL:'6f67ad3c848034f692eb881a6aac62bef55b3264bafe7e36df83b5603b6abc36',DWL:'6f57fd74618999fff13d7677e632717762744e5c0ff5740e9a49756d35d9d289',SI:'c4b1b5312079822e080c98397eefc50828795ba425b5b95b70392d5f00a8e29b',RI:'7aa27dbbd5b0b888e46d745cd572994ce542aaf584b713520d4666ad86e036b5'}
CUR='adjudicate_multi_claim_successor_support_label_disagreements_v1';NEXT='construct_multi_claim_successor_support_reference_candidate_v1';DEFER='resolve_multi_claim_successor_support_adjudication_deferrals_v1';NEXTNEG='design_new_multi_claim_successor_support_label_adjudication_version_if_research_continues';BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';MODEL='gpt-5.4';TEMP=0;TOPP=1;MAXTOK=4000;TIMEOUT=600;RF={'type':'json_object'};SEED='phase7.3.3-d-multi-claim-successor-support-label-adjudication-option-balance-v1';OPS={'select_option_1','select_option_2','defer_for_human_review'};CONF={'low','medium','high'};KEYS={'case_id','work_item_id','reference_claim_id','operation','decision_rationale','adjudication_confidence'}
class CF(ValueError):
 def __init__(self,code,level,subtype,eh=None,ch=None,reported=None):super().__init__(code);self.code=code;self.level=level;self.subtype=subtype;self.eh=eh;self.ch=ch;self.reported=reported
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
def csha(x):return hb(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rel(p):return p.relative_to(ROOT).as_posix()
def once(p,x):
 b=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists() and p.read_bytes()!=b:raise RuntimeError('refuse_to_overwrite_different_artifact:'+rel(p))
 if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 return sha(p)
def text_once(p,x):
 b=x.encode()
 if p.exists() and p.read_bytes()!=b:raise RuntimeError('refuse_to_overwrite_different_artifact:'+rel(p))
 if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 return sha(p)
def input_checks():return {'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
def view(x):return {k:copy.deepcopy(x[k]) for k in ['support_label','cited_evidence_ids','reason_codes','support_rationale','annotation_confidence']}
def build():
 items=load(WL)['items'];rank=sorted(items,key=lambda x:hashlib.sha256((SEED+'|'+x['work_item_id']).encode()).hexdigest());aset={x['work_item_id'] for x in rank[:len(rank)//2]};pub=[];private=[]
 for x in items:
  s1='reviewer_a' if x['work_item_id'] in aset else 'reviewer_b';s2='reviewer_b' if s1=='reviewer_a' else 'reviewer_a'
  pub.append({k:copy.deepcopy(x[k]) for k in ['case_id','work_item_id','reference_claim_id','claim_index','source_span','source_excerpt','claim_role','claim_type','claim_origin','evidence_bundle']}|{'option_1':view(x[s1]),'option_2':view(x[s2]),'authorization':{'select_immutable_option_only':True,'defer_allowed':True,'replacement_label_allowed':False,'boundary_change_allowed':False,'claim_change_allowed':False,'reviewer_submission_mutation_allowed':False}})
  private.append({'case_id':x['case_id'],'work_item_id':x['work_item_id'],'reference_claim_id':x['reference_claim_id'],'option_1_source':s1,'option_2_source':s2,'reviewer_a_decision_sha256':csha(view(x['reviewer_a'])),'reviewer_b_decision_sha256':csha(view(x['reviewer_b']))})
 return ({'schema_version':1,'packet_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-packet-v1','status':'frozen_blinded_minimal_authorization_packet','item_count':len(pub),'source_reviewer_identity_visible':False,'aggregate_agreement_metrics_visible':False,'diagnostic_followup_items_included':False,'support_gold_visible':False,'items':pub},{'schema_version':1,'mapping_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-private-option-mapping-v1','status':'frozen_private_mapping_not_visible_to_adjudicator','option_seed':SEED,'item_count':len(private),'option_1_source_counts':dict(sorted(Counter(x['option_1_source'] for x in private).items())),'items':private})
def schema_doc():return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-schema-v1','type':'object','additionalProperties':False,'required':sorted(KEYS),'properties':{'case_id':{'type':'string','minLength':1},'work_item_id':{'type':'string','minLength':1},'reference_claim_id':{'type':'string','minLength':1},'operation':{'enum':sorted(OPS)},'decision_rationale':{'type':'string','minLength':1,'maxLength':2000},'adjudication_confidence':{'enum':sorted(CONF)}}}
def prompt_doc():return '''# Phase 7.3.3-D Multi-claim Successor Support Label Adjudicator Prompt v1

## System message

You are a blinded Support-label adjudicator. You receive exactly one frozen Atomic Claim, its same-case evidence bundle, and two immutable reviewer options. Decide only which existing option is better supported by the evidence under conservative entailment, or defer if neither option can be responsibly selected.

Contract:
- Return one bare JSON object and no Markdown.
- Copy case_id, work_item_id, and reference_claim_id exactly.
- operation MUST be exactly select_option_1, select_option_2, or defer_for_human_review.
- You MUST NOT emit a replacement Support label, rewrite either option, modify the Claim, modify its Boundary or metadata, add/delete/split/merge Claims, or use information outside the supplied item.
- Prefer direct evidence and conservative entailment. Do not infer current preference from stale evidence when contrary current evidence is supplied. Do not treat keyword overlap alone as entailment. Preserve scope, uncertainty, conditions, exceptions, and counterexamples.
- Use defer_for_human_review only when neither immutable option can be responsibly selected under the supplied evidence.
- decision_rationale must briefly explain the choice without introducing new evidence.
- adjudication_confidence MUST be low, medium, or high.

Required JSON keys: case_id, work_item_id, reference_claim_id, operation, decision_rationale, adjudication_confidence.

## User message template

Adjudicate this one frozen item. Return bare JSON only.

ITEM_JSON:
{{ITEM_JSON}}
'''
def policy_doc():return {'schema_version':1,'policy_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-execution-policy-v1','authoritative_result_policy':{'first_provider_content_authoritative':True,'invalid_json_schema_or_semantics_authoritative_negative':True,'post_content_same_version_retry_allowed':False,'transport_failure_before_content_resume_same_manifest':True},'execution_controls':{'one_isolated_claim_per_request':True,'model':MODEL,'temperature':TEMP,'top_p':TOPP,'max_tokens':MAXTOK,'response_format':RF,'timeout_seconds':TIMEOUT},'minimal_authorization':{'allowed_operations':sorted(OPS),'replacement_label_allowed':False,'selected_decision_reconstructed_by_adapter':True,'diagnostic_followup_label_change_allowed':False},'data_handling':{'credential_env_name':CRED,'raw_provider_response_stored':False,'envelope_hash_recorded':True,'content_hash_recorded_before_parse':True,'support_gold_visible':False,'held_out_loaded':False},'execution_not_authorized_by_prepare_alone':True}
def protocol_doc():return {'schema_version':1,'protocol_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-protocol-v1','phase':'Phase 7.3.3-D Multi-claim Successor Support Label Adjudication','status':'frozen_before_first_provider_execution','research_object':'adjudication of exactly 28 frozen Support-label disagreements without changing Claim boundaries or reviewer submissions','entry_gate':{'agreement_completed':True,'claim_count':240,'label_disagreement_count':28,'diagnostic_followup_count':47,'next_authorized_stage':CUR},'allowed_operations':sorted(OPS),'selection_semantics':'select one immutable blinded reviewer option or defer; never generate a replacement label','selected_decision_reconstruction':'adapter deterministically copies the complete selected frozen reviewer decision through the private mapping','immutable_fields':['case_id','reference_claim_id','claim_index','source_span','source_excerpt','claim_role','claim_type','claim_origin','evidence_bundle','reviewer_a_submission','reviewer_b_submission'],'forbidden_actions':['create_claim','delete_claim','split_claim','merge_claim','modify_boundary','rewrite_claim_text','emit_new_support_label','rewrite_reviewer_submission','adjudicate_diagnostic_followup_label','access_support_gold','access_confirmatory_dataset','access_runtime_integration'],'adjudicator_visibility':{'visible':['immutable_claim_metadata','same_case_evidence_bundle','option_1','option_2'],'prohibited':['source_reviewer_identity','private_option_mapping','aggregate_agreement_metrics','diagnostic_followup_items','historical_gold_or_silver','held_out_cases']},'completion_gate':{'all_28_items_require_terminal_results':True,'any_defer_blocks_reference_candidate_construction':True,'adapter_replay_required':True,'support_reference_candidate_created_in_this_stage':False,'support_gold_created_in_this_stage':False},'guards':{'boundary_mutation_allowed':False,'new_claim_creation_allowed':False,'claim_deletion_allowed':False,'reviewer_submission_mutation_allowed':False,'diagnostic_followup_label_change_allowed':False,'support_reference_candidate_creation_allowed':False,'support_gold_creation_allowed':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False},'next_authorized_stage':'execute_multi_claim_successor_support_label_adjudication_v1'}
def parse_obj(o,item):
 if not isinstance(o,dict):raise CF('adjudication_output_not_object','level_1_provider_representation','schema_failure')
 if set(o)!=KEYS:raise CF('adjudication_output_keys_invalid','level_1_provider_representation','schema_failure')
 for k in ['case_id','work_item_id','reference_claim_id']:
  if o.get(k)!=item[k]:raise CF(k+'_mismatch','level_2_support_contract','provenance_failure')
 if o.get('operation') not in OPS:raise CF('operation_invalid','level_2_support_contract','semantic_decision_failure')
 q=o.get('decision_rationale')
 if not isinstance(q,str) or not q.strip() or len(q)>2000:raise CF('decision_rationale_invalid','level_1_provider_representation','schema_failure')
 if o.get('adjudication_confidence') not in CONF:raise CF('adjudication_confidence_invalid','level_1_provider_representation','schema_failure')
 return {'case_id':o['case_id'],'work_item_id':o['work_item_id'],'reference_claim_id':o['reference_claim_id'],'operation':o['operation'],'decision_rationale':q.strip(),'adjudication_confidence':o['adjudication_confidence']}
def reconstruct(item,m,d):
 z=copy.deepcopy(d);op=d['operation']
 if op=='defer_for_human_review':z.update({'selected_option':None,'selected_source_reviewer':None,'selected_decision':None});return z
 so='option_1' if op=='select_option_1' else 'option_2';z.update({'selected_option':so,'selected_source_reviewer':m[so+'_source'],'selected_decision':copy.deepcopy(item[so])});return z
def fixture_doc():
 p,m=build();item=p['items'][0];rows=[]
 def rec(name,expected,fn):
  actual='PASS';code=None
  try:fn()
  except CF as e:actual='REJECT';code=e.code
  rows.append({'name':name,'expected':expected,'actual':actual,'failure_code':code,'passed':actual==expected})
 b={'case_id':item['case_id'],'work_item_id':item['work_item_id'],'reference_claim_id':item['reference_claim_id'],'operation':'select_option_1','decision_rationale':'Option 1 is more conservatively supported.','adjudication_confidence':'high'}
 rec('valid_select_option_1','PASS',lambda:parse_obj(copy.deepcopy(b),item));x=copy.deepcopy(b);x['operation']='select_option_2';rec('valid_select_option_2','PASS',lambda:parse_obj(x,item));x=copy.deepcopy(b);x['operation']='defer_for_human_review';rec('valid_defer','PASS',lambda:parse_obj(x,item));x=copy.deepcopy(b);x['replacement_label']='supported';rec('reject_extra_replacement_label','REJECT',lambda:parse_obj(x,item));x=copy.deepcopy(b);x['work_item_id']='wrong';rec('reject_work_item_mismatch','REJECT',lambda:parse_obj(x,item));x=copy.deepcopy(b);x['operation']='emit_new_label';rec('reject_invalid_operation','REJECT',lambda:parse_obj(x,item));x=copy.deepcopy(b);x['decision_rationale']='';rec('reject_empty_rationale','REJECT',lambda:parse_obj(x,item));mm={x['work_item_id']:x for x in m['items']}[item['work_item_id']];ok=reconstruct(item,mm,parse_obj(b,item))['selected_decision']==item['option_1'];rows.append({'name':'selected_option_reconstruction_exact','expected':'PASS','actual':'PASS' if ok else 'REJECT','failure_code':None,'passed':ok})
 return {'schema_version':1,'fixtures_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-contract-fixtures-v1','fixture_count':len(rows),'fixtures_passed':sum(x['passed'] for x in rows),'all_fixtures_passed':all(x['passed'] for x in rows),'fixtures':rows}
def preflight_checks():
 z=input_checks()
 if all(z.values()):
  w=load(WL);d=load(DWL);a=load(AR);o=load(AO);s=load(SI);r=load(RI);xs=w.get('items',[]);ds=d.get('items',[]);wi=[x.get('work_item_id') for x in xs];ci=[x.get('reference_claim_id') for x in xs];di=[x.get('reference_claim_id') for x in ds];p,m=build()
  z.update({'agreement_claim_count_240':a.get('claim_count')==240,'agreement_disagreement_count_28':a.get('label_agreement',{}).get('disagreement_count')==28,'agreement_diagnostic_count_47':a.get('adjudication_candidates',{}).get('diagnostic_followup_count')==47,'outcome_gate':o.get('next_authorized_stage')==CUR,'state_gate':s.get('next_authorized_stage')==CUR,'readiness_gate':r.get('next_authorized_stage')==CUR,'worklist_count_28':w.get('work_item_count')==28 and len(xs)==28,'diagnostic_count_47':d.get('work_item_count')==47 and len(ds)==47,'work_ids_unique':len(set(wi))==28 and None not in wi,'claim_ids_unique':len(set(ci))==28 and None not in ci,'worklists_disjoint_by_claim':set(ci).isdisjoint(di),'each_item_is_label_disagreement':all(x.get('reviewer_a',{}).get('support_label')!=x.get('reviewer_b',{}).get('support_label') for x in xs),'minimal_authorization':all(x.get('label_adjudication_required') is True and x.get('boundary_change_authorized') is False and x.get('type_change_authorized') is False and x.get('metadata_change_authorized') is False and x.get('reviewer_submission_mutation_authorized') is False for x in xs),'diagnostics_no_label_change':all(x.get('support_label_adjudication_required') is False and x.get('label_change_authorized') is False for x in ds),'packet_count_28':p['item_count']==28,'mapping_count_28':m['item_count']==28,'option_1_balanced':m['option_1_source_counts']=={'reviewer_a':14,'reviewer_b':14},'provider_not_called_by_preflight':not LOG.exists(),'confirmatory_closed':s.get('confirmatory_dataset_opened') is False and r.get('confirmatory_dataset_opened') is False,'runtime_off':s.get('runtime_integration_authorized') is False and r.get('runtime_integration_authorized') is False})
 return z
def preflight():
 z=preflight_checks();f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'provider_called':False}
def expected_manifest():
 p,m=build();paths=[AP,AF,AM,AR,AO,AC,WL,DWL,SI,RI,PRO,POL,SCH,PRM,PKT,MAP,FIX];return {'schema_version':1,'manifest_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-execution-manifest-v1','status':'frozen_ready_for_first_execution','adapter_sha256':sha(SELF),'model':MODEL,'temperature':TEMP,'top_p':TOPP,'max_tokens':MAXTOK,'response_format':RF,'timeout_seconds':TIMEOUT,'credential_env_name':CRED,'item_count':p['item_count'],'option_1_source_counts':m['option_1_source_counts'],'one_isolated_claim_per_request':True,'source_reviewer_identity_visible':False,'diagnostic_followup_items_visible':False,'aggregate_agreement_metrics_visible':False,'first_provider_content_authoritative':True,'post_content_same_version_retry_allowed':False,'raw_provider_responses_stored':False,'support_reference_candidate_created':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'frozen_artifacts':{rel(x):{'sha256':sha(x)} for x in paths},'execution_started':False,'provider_called':False,'next_authorized_stage':'execute_multi_claim_successor_support_label_adjudication_v1'}
def prepare():
 g=preflight()
 if g['status']!='PASS':raise RuntimeError('preflight_failed:'+repr(g['failed']))
 p,m=build();f=fixture_doc()
 if not f['all_fixtures_passed']:raise RuntimeError('fixtures_failed')
 h={'protocol_sha256':once(PRO,protocol_doc()),'execution_policy_sha256':once(POL,policy_doc()),'schema_sha256':once(SCH,schema_doc()),'prompt_sha256':text_once(PRM,prompt_doc()),'packet_sha256':once(PKT,p),'private_mapping_sha256':once(MAP,m),'fixtures_sha256':once(FIX,f)};h['manifest_sha256']=once(MAN,expected_manifest());return {'status':'PASS','prepared':True,'fixtures':f"{f['fixtures_passed']}/{f['fixture_count']}",**h,'provider_called':False}
def verify_prepare():
 z=input_checks();ps=[PRO,POL,SCH,PRM,PKT,MAP,FIX,MAN];z.update({'exists:'+rel(p):p.exists() for p in ps})
 if all(p.exists() for p in ps):
  p,m=build();z.update({'protocol_replay':load(PRO)==protocol_doc(),'policy_replay':load(POL)==policy_doc(),'schema_replay':load(SCH)==schema_doc(),'prompt_replay':PRM.read_text(encoding='utf-8-sig')==prompt_doc(),'packet_replay':load(PKT)==p,'mapping_replay':load(MAP)==m,'fixtures_replay':load(FIX)==fixture_doc(),'fixtures_pass':load(FIX).get('all_fixtures_passed') is True,'manifest_replay':load(MAN)==expected_manifest(),'terminal_absent':not RES.exists() and not NEG.exists() and not SUB.exists(),'provider_not_called':not LOG.exists()})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'hashes':{n:sha(p) if p.exists() else None for n,p in [('adapter',SELF),('protocol',PRO),('policy',POL),('schema',SCH),('prompt',PRM),('packet',PKT),('mapping',MAP),('fixtures',FIX),('manifest',MAN)]},'provider_called':LOG.exists()}
def canonical(reported):
 if not isinstance(reported,str) or not reported.strip():raise CF('provider_reported_model_missing','level_1_provider_representation','identity_failure')
 t=reported.strip().lower().rsplit('/',1)[-1];q=MODEL.lower()
 if t==q:return MODEL
 if t.startswith(q+'-') and re.fullmatch(r'[a-z0-9][a-z0-9._-]*',t[len(q)+1:]):return MODEL
 raise CF('provider_reported_model_family_mismatch','level_1_provider_representation','identity_failure',reported=reported)
def split_prompt():
 x=PRM.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];s,u=x.split('\n## User message template\n\n',1);return s.strip(),u.strip()
def call(key,system,user):
 payload={'model':MODEL,'temperature':TEMP,'top_p':TOPP,'max_tokens':MAXTOK,'response_format':RF,'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as resp:return resp.read()
def parse_response(raw,item):
 eh=hb(raw)
 try:env=json.loads(raw.decode())
 except Exception as e:raise CF('provider_envelope_json_invalid:'+type(e).__name__,'level_1_provider_representation','envelope_parse_failure',eh=eh) from e
 if not isinstance(env,dict):raise CF('provider_envelope_not_object','level_1_provider_representation','envelope_parse_failure',eh=eh)
 reported=env.get('model');choices=env.get('choices')
 if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):raise CF('provider_choices_invalid','level_1_provider_representation','envelope_parse_failure',eh=eh,reported=reported if isinstance(reported,str) else None)
 msg=choices[0].get('message')
 if not isinstance(msg,dict):raise CF('provider_message_invalid','level_1_provider_representation','envelope_parse_failure',eh=eh,reported=reported if isinstance(reported,str) else None)
 content=msg.get('content')
 if not isinstance(content,str) or not content.strip():raise CF('provider_content_missing','level_1_provider_representation','content_missing',eh=eh,reported=reported if isinstance(reported,str) else None)
 ch=hb(content.encode())
 try:can=canonical(reported)
 except CF as e:e.eh=eh;e.ch=ch;e.reported=e.reported or (reported if isinstance(reported,str) else None);raise
 try:o=json.loads(content)
 except Exception as e:raise CF('provider_content_json_invalid:'+type(e).__name__,'level_1_provider_representation','content_parse_failure',eh,ch,reported if isinstance(reported,str) else None) from e
 try:d=parse_obj(o,item)
 except CF as e:e.eh=eh;e.ch=ch;e.reported=reported if isinstance(reported,str) else None;raise
 return d,{'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':reported,'canonical_model_family':can}
def checkpoint(wid):return CASES/(wid+'.json')
def terminal():return 'completed' if RES.exists() else 'authoritative_negative_result' if NEG.exists() else None
def negative(item,e,done,mh):
 n={'schema_version':1,'negative_result_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-negative-result-v1','status':'authoritative_negative_result','failure_level':e.level,'failure_subtype':e.subtype,'failure_code':e.code,'failed_case_id':item['case_id'],'failed_work_item_id':item['work_item_id'],'completed_item_count':done,'total_item_count':28,'provider_envelope_sha256':e.eh,'provider_content_sha256':e.ch,'provider_reported_model':e.reported,'manifest_sha256':mh,'first_provider_content_authoritative':True,'same_version_retry_allowed':False,'partial_execution_evidence_only':done>0,'support_reference_candidate_created':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'capability_conclusion_authorized':False,'next_authorized_stage':NEXTNEG};nh=once(NEG,n);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_support_label_adjudication_manifest_sha256':mh,'multi_claim_successor_support_label_adjudication_negative_result_sha256':nh,'multi_claim_successor_support_label_adjudication_attempt_log_sha256':sha(LOG)};common={'multi_claim_successor_support_label_adjudication_protocol_frozen':True,'multi_claim_successor_support_label_adjudication_provider_called':True,'multi_claim_successor_support_label_adjudication_completed':False,'multi_claim_successor_support_label_adjudication_authoritative_negative_preserved':True,'multi_claim_successor_support_label_adjudication_same_version_retry_allowed':False,'multi_claim_successor_support_reference_candidate_created':False,'multi_claim_successor_support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':NEXTNEG}
 for x,v,i in [(s,56,'phase7.3.3-d-support-stage-state-v56'),(r,67,'phase7.3.3-d1-reference-construction-readiness-v67')]:
  x.setdefault('artifact_lineage',{}).update(line);x.update(common);x['schema_version']=v
  if x is s:x['state_id']=i
  else:x['readiness_id']=i;x['status']='multi_claim_successor_support_label_adjudication_authoritative_negative'
 sh=once(SO,s);r.setdefault('artifact_lineage',{})['support_stage_state_v56_sha256']=sh;rh=once(RO,r);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-receipt-v1','status':'authoritative_negative_result','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'negative_result_sha256':nh,'state_sha256':sh,'readiness_sha256':rh,'support_reference_candidate_created':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':NEXTNEG};return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':nh,'receipt_sha256':once(REC,rec),'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':NEXTNEG}
def execute():
 if not MAN.exists() or load(MAN)!=expected_manifest():raise RuntimeError('manifest_missing_or_invalid')
 t=terminal()
 if t=='completed':return {'status':'PASS','terminal_outcome':'already_completed','result_sha256':sha(RES),'next_authorized_stage':load(RES)['next_authorized_stage']}
 if t=='authoritative_negative_result':return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','terminal_outcome':'already_authoritative_negative','negative_result_sha256':sha(NEG),'next_authorized_stage':load(NEG)['next_authorized_stage']}
 key=os.environ.get(CRED)
 if not key:raise RuntimeError('credential_missing:'+CRED)
 mh=sha(MAN);p=load(PKT);maps={x['work_item_id']:x for x in load(MAP)['items']};system,ut=split_prompt();CASES.mkdir(parents=True,exist_ok=True);done=[]
 for item in p['items']:
  cp=checkpoint(item['work_item_id'])
  if cp.exists():
   x=load(cp)
   if x.get('manifest_sha256')!=mh or x.get('work_item_id')!=item['work_item_id']:raise RuntimeError('checkpoint_lineage_mismatch:'+item['work_item_id'])
   done.append(x);continue
  an=1+sum(1 for e in read_entries(LOG) if e.get('work_item_id')==item['work_item_id'] and e.get('event_type')=='attempt_started');append_event({'event_type':'attempt_started','manifest_sha256':mh,'attempt_number':an,'case_id':item['case_id'],'work_item_id':item['work_item_id'],'reference_claim_id':item['reference_claim_id'],'model':MODEL,'response_received':False,'authoritative_result':False},LOG);user=ut.replace('{{ITEM_JSON}}',json.dumps(item,ensure_ascii=False,indent=2))
  try:raw=call(key,system,user)
  except (urllib.error.URLError,TimeoutError,OSError) as e:
   append_event({'event_type':'attempt_transport_failure','manifest_sha256':mh,'attempt_number':an,'case_id':item['case_id'],'work_item_id':item['work_item_id'],'reference_claim_id':item['reference_claim_id'],'status':'transport_failure','failure_type':type(e).__name__,'response_received':False,'authoritative_result':False,'same_manifest_resume_allowed':True,'completed_item_count':len(done)},LOG);return {'status':'TRANSPORT_FAILURE_RESUMABLE','failed_work_item_id':item['work_item_id'],'completed_item_count':len(done),'attempt_log_sha256':sha(LOG),'same_manifest_resume_allowed':True}
  try:d,meta=parse_response(raw,item)
  except CF as e:
   append_event({'event_type':'attempt_contract_failure','manifest_sha256':mh,'attempt_number':an,'case_id':item['case_id'],'work_item_id':item['work_item_id'],'reference_claim_id':item['reference_claim_id'],'status':'authoritative_negative_result','failure_level':e.level,'failure_subtype':e.subtype,'failure_code':e.code,'provider_envelope_sha256':e.eh,'provider_content_sha256':e.ch,'provider_reported_model':e.reported,'response_received':True,'authoritative_result':True,'same_version_retry_allowed':False,'completed_item_count':len(done)},LOG);return negative(item,e,len(done),mh)
  z={'schema_version':1,'checkpoint_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-'+item['work_item_id'],'manifest_sha256':mh,'case_id':item['case_id'],'work_item_id':item['work_item_id'],'reference_claim_id':item['reference_claim_id'],**reconstruct(item,maps[item['work_item_id']],d),**meta,'boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False,'diagnostic_followup_label_change_performed':False,'support_reference_candidate_created':False,'support_gold_created':False};ch=once(cp,z);append_event({'event_type':'attempt_completed','manifest_sha256':mh,'attempt_number':an,'case_id':item['case_id'],'work_item_id':item['work_item_id'],'reference_claim_id':item['reference_claim_id'],'status':'completed','operation':d['operation'],'provider_envelope_sha256':meta['provider_envelope_sha256'],'provider_content_sha256':meta['provider_content_sha256'],'provider_reported_model':meta['provider_reported_model'],'canonical_model_family':meta['canonical_model_family'],'checkpoint_sha256':ch,'response_received':True,'authoritative_result':True},LOG);done.append(z)
 if len(done)!=28:raise RuntimeError('completed_item_count_invalid')
 return finalize(done,mh)
def finalize(done,mh):
 oc=Counter(x['operation'] for x in done);sc=Counter(x['selected_source_reviewer'] for x in done if x['selected_source_reviewer']);deferred=[x for x in done if x['operation']=='defer_for_human_review'];sub={'schema_version':1,'submission_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-completed-submission-v1','status':'completed_with_no_deferrals' if not deferred else 'completed_with_deferrals','manifest_sha256':mh,'item_count':28,'selected_count':28-len(deferred),'deferred_count':len(deferred),'operation_counts':dict(sorted(oc.items())),'selected_source_reviewer_counts':dict(sorted(sc.items())),'adjudications':done,'boundary_mutation_performed':False,'claim_creation_or_deletion_performed':False,'reviewer_submission_mutation_performed':False,'diagnostic_followup_items_processed':0,'diagnostic_followup_label_change_performed':False,'support_reference_candidate_created':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};subh=once(SUB,sub);nxt=NEXT if not deferred else DEFER;res={'schema_version':1,'result_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-result-v1','status':'completed_reference_candidate_construction_authorized' if not deferred else 'completed_deferrals_block_reference_candidate','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'attempt_log_tail_sha256':read_entries(LOG)[-1]['entry_sha256'],'submission_sha256':subh,'item_count':28,'selected_count':28-len(deferred),'deferred_count':len(deferred),'operation_counts':dict(sorted(oc.items())),'selected_source_reviewer_counts':dict(sorted(sc.items())),'support_label_adjudication_completed':not deferred,'support_reference_candidate_creation_authorized':not deferred,'support_reference_candidate_created':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':nxt};resh=once(RES,res);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_support_label_adjudication_protocol_sha256':sha(PRO),'multi_claim_successor_support_label_adjudication_manifest_sha256':mh,'multi_claim_successor_support_label_adjudication_attempt_log_sha256':sha(LOG),'multi_claim_successor_support_label_adjudication_submission_sha256':subh,'multi_claim_successor_support_label_adjudication_result_sha256':resh};common={'multi_claim_successor_support_label_adjudication_protocol_frozen':True,'multi_claim_successor_support_label_adjudication_provider_called':True,'multi_claim_successor_support_label_adjudication_completed':not deferred,'multi_claim_successor_support_label_adjudication_deferred_count':len(deferred),'multi_claim_successor_support_reference_candidate_creation_authorized':not deferred,'multi_claim_successor_support_reference_candidate_created':False,'multi_claim_successor_support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':nxt}
 for x,v,i in [(s,56,'phase7.3.3-d-support-stage-state-v56'),(r,67,'phase7.3.3-d1-reference-construction-readiness-v67')]:
  x.setdefault('artifact_lineage',{}).update(line);x.update(common);x['schema_version']=v
  if x is s:x['state_id']=i
  else:x['readiness_id']=i;x['status']='multi_claim_successor_support_label_adjudication_completed_reference_candidate_authorized' if not deferred else 'multi_claim_successor_support_label_adjudication_deferrals_pending'
 sh=once(SO,s);r.setdefault('artifact_lineage',{})['support_stage_state_v56_sha256']=sh;rh=once(RO,r);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-multi-claim-successor-support-label-adjudication-receipt-v1','status':res['status'],'protocol_sha256':sha(PRO),'execution_policy_sha256':sha(POL),'schema_sha256':sha(SCH),'prompt_sha256':sha(PRM),'packet_sha256':sha(PKT),'private_mapping_sha256':sha(MAP),'fixtures_sha256':sha(FIX),'manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':subh,'result_sha256':resh,'state_sha256':sh,'readiness_sha256':rh,'deferred_count':len(deferred),'support_reference_candidate_created':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':nxt};return {'status':'PASS','item_count':28,'selected_count':28-len(deferred),'deferred_count':len(deferred),'operation_counts':dict(sorted(oc.items())),'selected_source_reviewer_counts':dict(sorted(sc.items())),'submission_sha256':subh,'result_sha256':resh,'receipt_sha256':once(REC,rec),'state_sha256':sh,'readiness_sha256':rh,'support_reference_candidate_created':False,'next_authorized_stage':nxt}
def verify():
 z=input_checks();z.update({'prepared_manifest_exists':MAN.exists(),'exactly_one_terminal_outcome':RES.exists()^NEG.exists(),'attempt_log_exists':LOG.exists(),'receipt_exists':REC.exists(),'state_v56_exists':SO.exists(),'readiness_v67_exists':RO.exists()})
 if MAN.exists():z['manifest_replay']=load(MAN)==expected_manifest()
 if LOG.exists():
  try:z['attempt_log_chain_valid']=bool(read_entries(LOG))
  except Exception:z['attempt_log_chain_valid']=False
 if RES.exists():
  r=load(RES);s=load(SUB) if SUB.exists() else {};p=load(PKT);ads=s.get('adjudications',[]);dc=r.get('deferred_count');nxt=NEXT if dc==0 else DEFER
  z.update({'submission_exists':SUB.exists(),'result_manifest_lineage':r.get('manifest_sha256')==sha(MAN),'result_attempt_log_lineage':r.get('attempt_log_sha256')==sha(LOG),'result_submission_lineage':SUB.exists() and r.get('submission_sha256')==sha(SUB),'receipt_result_lineage':load(REC).get('result_sha256')==sha(RES),'receipt_state_lineage':load(REC).get('state_sha256')==sha(SO),'receipt_readiness_lineage':load(REC).get('readiness_sha256')==sha(RO),'checkpoint_count_28':len(list(CASES.glob('*.json')))==28,'submission_count_28':len(ads)==28 and s.get('item_count')==28,'submission_order_exact':[x.get('work_item_id') for x in ads]==[x.get('work_item_id') for x in p['items']],'all_operations_allowed':all(x.get('operation') in OPS for x in ads),'selected_decisions_present':all((x.get('selected_decision') is None)==(x.get('operation')=='defer_for_human_review') for x in ads),'no_boundary_mutation':s.get('boundary_mutation_performed') is False,'no_reviewer_mutation':s.get('reviewer_submission_mutation_performed') is False,'no_diagnostic_processing':s.get('diagnostic_followup_items_processed')==0 and s.get('diagnostic_followup_label_change_performed') is False,'reference_candidate_absent':r.get('support_reference_candidate_created') is False,'support_gold_absent':r.get('support_gold_created') is False,'confirmatory_closed':r.get('confirmatory_dataset_opened') is False,'runtime_off':r.get('runtime_integration_authorized') is False,'next_stage_consistent':r.get('next_authorized_stage')==nxt and load(SO).get('next_authorized_stage')==nxt and load(RO).get('next_authorized_stage')==nxt})
 if NEG.exists():
  n=load(NEG);z.update({'negative_authoritative':n.get('status')=='authoritative_negative_result','negative_same_version_retry_false':n.get('same_version_retry_allowed') is False,'negative_capability_claim_false':n.get('capability_conclusion_authorized') is False,'negative_reference_candidate_false':n.get('support_reference_candidate_created') is False,'negative_gold_false':n.get('support_gold_created') is False,'negative_next_stage':n.get('next_authorized_stage')==NEXTNEG})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'terminal_outcome':'completed' if RES.exists() else 'authoritative_negative_result' if NEG.exists() else None,'hashes':{n:sha(p) if p.exists() else None for n,p in [('adapter',SELF),('manifest',MAN),('attempt_log',LOG),('submission',SUB),('result',RES),('negative',NEG),('receipt',REC),('state',SO),('readiness',RO)]},'next_authorized_stage':load(SO).get('next_authorized_stage') if SO.exists() else None}
def main():
 a=argparse.ArgumentParser();g=a.add_mutually_exclusive_group(required=True);g.add_argument('--preflight',action='store_true');g.add_argument('--fixtures',action='store_true');g.add_argument('--prepare',action='store_true');g.add_argument('--verify-prepare',action='store_true');g.add_argument('--execute',action='store_true');g.add_argument('--verify',action='store_true');x=a.parse_args()
 if x.preflight:o=preflight()
 elif x.fixtures:o=fixture_doc();o['status']='PASS' if o['all_fixtures_passed'] else 'FAIL'
 elif x.prepare:o=prepare()
 elif x.verify_prepare:o=verify_prepare()
 elif x.execute:o=execute()
 else:o=verify()
 print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status') in {'PASS','AUTHORITATIVE_NEGATIVE_RESULT','TRANSPORT_FAILURE_RESUMABLE'} else 1
if __name__=='__main__':raise SystemExit(main())
