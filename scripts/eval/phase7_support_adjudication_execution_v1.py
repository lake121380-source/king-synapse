#!/usr/bin/env python3
from __future__ import annotations
import argparse,copy,hashlib,json,os,tempfile,urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event,read_entries
R=Path(__file__).resolve().parents[2];C=R/'crates/eval/config';D=R/'crates/eval/datasets/pattern_extraction';O=R/'crates/eval/reports'
P=C/'phase7_3_3_d_support_adjudication_protocol_v1.json';POL=C/'phase7_3_3_d_support_adjudication_execution_policy_v1.json';PROMPT=C/'phase7_3_3_d_support_adjudicator_prompt_v1.md';SCHEMA=C/'phase7_3_3_d_support_adjudication_output_schema_v1.json';PACK=D/'phase7_3_3_d_support_adjudication_packet_v1.json';MAP=O/'phase7_3_3_d_support_adjudication_private_option_mapping_v1.json';FIX=O/'phase7_3_3_d_support_adjudication_contract_fixtures_v1.json';FREEZE=O/'phase7_3_3_d_support_adjudication_freeze_manifest_v1.json';PS=D/'phase7_3_3_d_support_stage_state_v8.json';PR=O/'phase7_3_3_d1_reference_construction_readiness_v19.json';RA=O/'phase7_3_3_d_support_reviewer_a_completed_submission_v2.json';RB=O/'phase7_3_3_d_support_reviewer_b_completed_submission_v2.json'
MAN=O/'phase7_3_3_d_support_adjudication_execution_manifest_v1.json';LOG=O/'phase7_3_3_d_support_adjudication_attempts_v1.jsonl';CASES=O/'phase7_3_3_d_support_adjudication_cases_v1';SUB=O/'phase7_3_3_d_support_adjudication_submission_v1.json';RES=O/'phase7_3_3_d_support_adjudication_execution_result_v1.json';NEG=O/'phase7_3_3_d_support_adjudication_negative_result_v1.json';STATE=D/'phase7_3_3_d_support_stage_state_v9.json';READY=O/'phase7_3_3_d1_reference_construction_readiness_v20.json'
BASE='https://api.gpt.ge/v1';ENV='PHASE7_ATOMIC_JUDGE_API_KEY';MODEL='gpt-5.4';OPS={'select_option_1','select_option_2','defer_for_human_review'}
def sb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return sb(p.read_bytes())
def csha(v):return sb(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def once(p,v):
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_conflict:{p.relative_to(R)}')
  return sb(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p);return sb(b)
def checks():
 f=load(FREEZE);p=load(PACK);m=load(MAP);x=load(FIX);s=load(PS);r=load(PR)
 z={'freeze_ready':f.get('status')=='frozen_ready_for_first_execution','count_26':f.get('item_count')==26==p.get('item_count')==m.get('item_count') and len(p['items'])==len(m['items'])==26,'protocol':f.get('protocol_sha256')==sha(P),'policy':f.get('execution_policy_sha256')==sha(POL),'prompt':f.get('prompt_sha256')==sha(PROMPT),'schema':f.get('output_schema_sha256')==sha(SCHEMA),'packet':f.get('adjudication_packet_sha256')==sha(PACK),'mapping':f.get('private_option_mapping_sha256')==sha(MAP),'fixtures':f.get('contract_fixtures_sha256')==sha(FIX),'fixtures_12':x.get('fixture_count')==12 and x.get('passed_count')==12 and x.get('failed_count')==0 and x.get('status')=='all_pass' and x.get('execution_authorized_after_fixtures') is True,'isolated':p.get('one_isolated_claim_per_request') is True,'blind':p.get('reviewer_identity_visible') is False and p.get('diagnostic_followup_visible') is False,'mapping_private':m.get('adjudicator_visible') is False,'balance':m.get('option_1_source_counts')=={'reviewer_a':13,'reviewer_b':13},'identity':[(i['adjudication_item_id'],i['boundary_claim_id']) for i in p['items']]==[(i['adjudication_item_id'],i['boundary_claim_id']) for i in m['items']],'state':s.get('next_authorized_stage')=='execute_support_adjudication_v1','readiness':r.get('next_authorized_stage')=='execute_support_adjudication_v1','not_started':f.get('execution_started') is False and f.get('provider_called') is False,'gold_false':f.get('support_gold_frozen') is False,'heldout_false':f.get('held_out_accessed') is False}
 for n,a in f.get('frozen_inputs',{}).items():
  q=R/a['path'];z['lineage_'+n]=q.is_file() and sha(q)==a['sha256']
 return z
def manifest():
 z=checks()
 if not all(z.values()):raise ValueError('frozen_checks_failed:'+','.join(k for k,v in z.items() if not v))
 return {'schema_version':1,'manifest_id':'phase7.3.3-d3-support-adjudication-execution-manifest-v1','status':'frozen_before_first_provider_call','research_object':'operation-based adjudication of exactly 26 frozen Support-label disagreements','decision_environment':{'provider':'api.gpt.ge','provider_base_url':BASE,'model_requested':MODEL,'canonical_model_family_expected':MODEL,'temperature':0,'top_p':1,'seed':None,'seed_supported_by_adapter':False,'max_tokens':4000,'stop_sequences':[],'response_format':{'type':'json_object'},'request_timeout_seconds':600,'credential_env_name':ENV,'one_isolated_claim_per_request':True},'artifact_lineage':{'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(P),'execution_policy_sha256':sha(POL),'prompt_sha256':sha(PROMPT),'output_schema_sha256':sha(SCHEMA),'packet_sha256':sha(PACK),'mapping_sha256':sha(MAP),'fixtures_sha256':sha(FIX),'freeze_manifest_sha256':sha(FREEZE),'reviewer_a_submission_sha256':sha(RA),'reviewer_b_submission_sha256':sha(RB),'state_v8_sha256':sha(PS),'readiness_v19_sha256':sha(PR)},'authoritative_result_policy':load(POL)['authoritative_result_policy'],'data_handling':load(POL)['data_handling'],'item_count':26,'allowed_operations':sorted(OPS),'execution_started':False,'provider_called':False,'support_gold_frozen':False,'held_out_accessed':False}
def freeze():print(json.dumps({'status':'execution_manifest_frozen','manifest_sha256':once(MAN,manifest()),'adapter_sha256':sha(Path(__file__)),'provider_called':False},indent=2))
def prompt_parts():
 t=PROMPT.read_text(encoding='utf-8-sig');a=t.split('## System message\n',1)[1];s,u=a.split('\n## User message template\n',1);return s.strip(),u.strip()
def call(key,s,u):
 q={'model':MODEL,'temperature':0,'top_p':1,'max_tokens':4000,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':s},{'role':'user','content':u}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(q,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=600) as h:raw=h.read()
 return json.loads(raw.decode()),raw
def content(e):
 if not isinstance(e,dict):raise ValueError('provider_envelope_not_object')
 rep=e.get('model');cs=e.get('choices')
 if not isinstance(rep,str) or not rep:raise ValueError('provider_reported_model_missing')
 if not isinstance(cs,list) or len(cs)!=1 or not isinstance(cs[0],dict):raise ValueError('provider_choices_invalid')
 msg=cs[0].get('message');c=msg.get('content') if isinstance(msg,dict) else None
 if not isinstance(c,str) or not c:raise ValueError('provider_content_missing')
 if rep!=MODEL and not rep.startswith(MODEL+'-'):raise ValueError('provider_model_family_mismatch:'+rep)
 return rep,c
def validate(v,i):
 if not isinstance(v,dict) or set(v)!={'case_id','adjudication_item_id','boundary_claim_id','decision'}:raise ValueError('output_top_shape_invalid')
 for k in ('case_id','adjudication_item_id','boundary_claim_id'):
  if v.get(k)!=i[k]:raise ValueError('output_identity_mismatch:'+k)
 d=v.get('decision')
 if not isinstance(d,dict) or set(d)!={'operation','rationale'}:raise ValueError('output_decision_shape_invalid')
 if d.get('operation') not in OPS:raise ValueError('output_operation_invalid')
 if not isinstance(d.get('rationale'),str) or not d['rationale'].strip():raise ValueError('output_rationale_invalid')
 return {'case_id':i['case_id'],'adjudication_item_id':i['adjudication_item_id'],'boundary_claim_id':i['boundary_claim_id'],'decision':{'operation':d['operation'],'rationale':d['rationale'].strip()}}
def reconstruct(i,v,mp,submissions):
 op=v['decision']['operation'];o={'adjudication_item_id':i['adjudication_item_id'],'case_id':i['case_id'],'boundary_claim_id':i['boundary_claim_id'],'operation':op,'adjudicator_rationale':v['decision']['rationale'],'final_label_authorized':op!='defer_for_human_review','boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False}
 if op=='defer_for_human_review':return {**o,'selected_option':None,'selected_source_reviewer':None,'selected_frozen_decision':None,'status':'deferred_for_human_review'}
 k='option_1' if op=='select_option_1' else 'option_2';src=mp[k+'_source_reviewer'];d=copy.deepcopy(i[k])
 if submissions[src].get(i['boundary_claim_id'])!=d:raise ValueError('private_mapping_replay_mismatch')
 return {**o,'selected_option':k,'selected_source_reviewer':src,'selected_frozen_decision':d,'selected_frozen_decision_sha256':csha(d),'status':'selected_frozen_reviewer_decision'}
def classify(e,received,got):
 if not received:return {'level':0,'level_code':'transport','subtype':'transport_failure_before_content','attribution':'provider_interface'}
 if not got or isinstance(e,json.JSONDecodeError) or str(e).startswith(('provider_','output_')):return {'level':1,'level_code':'provider_representation_contract','subtype':'structured_output_contract_failure','attribution':'provider_output'}
 return {'level':2,'level_code':'support_adjudication_contract','subtype':'deterministic_replay_failure','attribution':'implementation'}
def execute():
 z=checks()
 if not all(z.values()):raise ValueError('frozen_checks_failed')
 if not MAN.exists() or load(MAN)!=manifest():raise ValueError('manifest_missing_or_invalid')
 if RES.exists() or NEG.exists():raise ValueError('terminal_artifact_exists')
 key=os.environ.get(ENV)
 if not key:raise ValueError('credential_env_missing:'+ENV)
 s,ut=prompt_parts();p=load(PACK);maps={x['adjudication_item_id']:x for x in load(MAP)['items']};subs={}
 for n,q in [('reviewer_a',RA),('reviewer_b',RB)]:subs[n]={x['boundary_claim_id']:x for x in load(q)['claims']}
 mh=sha(MAN);append_event({'event_type':'support_adjudication_execution_invocation','manifest_sha256':mh,'status':'started_or_resumed','response_received':False,'authoritative_result':False},LOG)
 out=[];models=set();cases=[]
 for i in p['items']:
  iid=i['adjudication_item_id'];cp=CASES/(iid+'.json')
  if cp.exists():
   x=load(cp)
   if x.get('manifest_sha256')!=mh or x.get('status')!='authoritative_success':raise ValueError('checkpoint_invalid:'+iid)
   out.append(x['adjudication']);models.add(x['provider_reported_model']);cases.append({'adjudication_item_id':iid,'case_id':i['case_id'],'boundary_claim_id':i['boundary_claim_id'],'status':'authoritative_success'});continue
  eh=ch=None;received=got=False
  try:
   u=ut.replace('{ADJUDICATION_ITEM_JSON}',json.dumps(i,ensure_ascii=False,indent=2));env,raw=call(key,s,u);received=True;eh=sb(raw);rep,c=content(env);got=True;ch=sb(c.encode());v=validate(json.loads(c),i);a=reconstruct(i,v,maps[iid],subs);x={'schema_version':1,'checkpoint_id':'phase7.3.3-d3-'+iid+'-v1','status':'authoritative_success','manifest_sha256':mh,'case_id':i['case_id'],'adjudication_item_id':iid,'boundary_claim_id':i['boundary_claim_id'],'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'canonical_model_family':MODEL,'normalized_output_sha256':csha(v),'adjudication':a,'raw_provider_response_stored':False,'held_out_accessed':False};once(cp,x);append_event({'event_type':'support_adjudication_item_authoritative_success','manifest_sha256':mh,'case_id':i['case_id'],'adjudication_item_id':iid,'boundary_claim_id':i['boundary_claim_id'],'status':'completed','response_received':True,'provider_content_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'normalized_output_sha256':x['normalized_output_sha256'],'operation':a['operation'],'selected_source_reviewer':a['selected_source_reviewer'],'final_label_authorized':a['final_label_authorized'],'provider_reported_model':rep,'canonical_model_family':MODEL},LOG);out.append(a);models.add(rep);cases.append({'adjudication_item_id':iid,'case_id':i['case_id'],'boundary_claim_id':i['boundary_claim_id'],'status':'authoritative_success'});print(json.dumps({'item':iid,'operation':a['operation'],'status':'completed'}),flush=True)
  except Exception as e:
   fc=classify(e,received,got);append_event({'event_type':'support_adjudication_item_failure','manifest_sha256':mh,'case_id':i['case_id'],'adjudication_item_id':iid,'boundary_claim_id':i['boundary_claim_id'],'status':'authoritative_negative_result' if received else 'transport_failure','failure_type':type(e).__name__,'failure_code':str(e)[:500],'failure_taxonomy':fc,'response_received':received,'provider_content_received':got,'authoritative_result':received,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'completed_item_count_before_failure':len(out)},LOG)
   if received:once(NEG,{'schema_version':1,'result_id':'phase7.3.3-d3-support-adjudication-negative-result-v1','status':'authoritative_negative_result','manifest_sha256':mh,'failed_adjudication_item_id':iid,'case_id':i['case_id'],'boundary_claim_id':i['boundary_claim_id'],'failure_type':type(e).__name__,'failure_code':str(e)[:500],'failure_taxonomy':fc,'response_received':True,'provider_content_received':got,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'completed_item_count_before_failure':len(out),'same_version_retry_allowed':False,'support_adjudication_completed':False,'support_gold_frozen':False,'raw_provider_response_stored':False,'held_out_accessed':False});print('AUTHORITATIVE NEGATIVE',iid,type(e).__name__,e);return 4
   print('TRANSPORT FAILURE',iid,type(e).__name__,e);return 3
 deferred=[x for x in out if not x['final_label_authorized']];selected=[x for x in out if x['final_label_authorized']];sub={'schema_version':1,'submission_id':'phase7.3.3-d3-support-adjudication-submission-v1','status':'completed_with_no_deferrals' if not deferred else 'completed_with_human_review_deferrals','manifest_sha256':mh,'protocol_sha256':sha(P),'packet_sha256':sha(PACK),'private_option_mapping_sha256':sha(MAP),'item_count':26,'selected_count':len(selected),'deferred_count':len(deferred),'adjudications':out,'boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False,'diagnostic_followup_items_processed':0,'support_gold_frozen':False,'raw_provider_responses_stored':False,'held_out_accessed':False};sh=once(SUB,sub);ents=read_entries(LOG);oc=dict(sorted(Counter(x['operation'] for x in out).items()));rc=dict(sorted(Counter(x['selected_source_reviewer'] for x in selected).items()));res={'schema_version':1,'execution_id':'phase7.3.3-d3-support-adjudication-execution-v1','status':'completed' if not deferred else 'completed_with_human_review_deferrals','manifest_sha256':mh,'submission_sha256':sh,'attempt_log_sha256':sha(LOG),'model_requested':MODEL,'canonical_model_family':MODEL,'provider_reported_models':sorted(models),'item_count':26,'successful_item_count':len(out),'selected_count':len(selected),'deferred_count':len(deferred),'operation_counts':oc,'selected_source_reviewer_counts':rc,'case_results':cases,'attempt_log_entry_count':len(ents),'attempt_log_tail_sha256':ents[-1]['entry_sha256'],'support_adjudication_completed':not deferred,'support_gold_freeze_protocol_allowed':not deferred,'support_gold_frozen':False,'raw_provider_responses_stored':False,'held_out_accessed':False};rh=once(RES,res);next='freeze_support_gold_protocol_v1' if not deferred else 'freeze_bounded_human_support_adjudication_successor';state={'schema_version':9,'state_id':'phase7.3.3-d-support-stage-state-v9','boundary_state':'frozen_project_boundary_gold','support_state':'support_adjudication_completed' if not deferred else 'support_adjudication_deferred_items_pending_human_review','boundary_gold_sha256':load(PS)['boundary_gold_sha256'],'boundary_claim_count':118,'support_review_completed':True,'support_agreement_computed':True,'support_label_disagreement_count':26,'support_adjudication_protocol_frozen':True,'support_adjudication_execution_completed':True,'support_adjudication_submission_sha256':sh,'support_adjudication_result_sha256':rh,'support_adjudication_selected_count':len(selected),'support_adjudication_deferred_count':len(deferred),'support_gold_freeze_protocol_allowed':not deferred,'support_gold_frozen':False,'next_authorized_stage':next,'diagnostic_followup_items_processed':0,'held_out_accessed':False};sth=once(STATE,state);ready={'schema_version':20,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v20','status':'support_adjudication_completed_support_gold_protocol_authorized' if not deferred else 'support_adjudication_completed_human_deferrals_block_support_gold','artifact_lineage':{'readiness_v19_sha256':sha(PR),'state_v8_sha256':sha(PS),'freeze_manifest_sha256':sha(FREEZE),'execution_manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':sh,'result_sha256':rh,'state_v9_sha256':sth},'reference_status':{'boundary_gold_frozen':True,'boundary_claim_count':118,'support_reviews_completed':True,'support_agreement_computed':True,'support_label_disagreement_count':26,'support_adjudication_completed':not deferred,'support_adjudication_selected_count':len(selected),'support_adjudication_deferred_count':len(deferred),'support_gold_frozen':False},'next_authorized_stage':next,'support_gold_freeze_protocol_allowed':not deferred,'support_gold_frozen':False,'diagnostic_followup_items_processed':0,'held_out_accessed':False};rdh=once(READY,ready);print(json.dumps({'status':res['status'],'result_sha256':rh,'submission_sha256':sh,'state_v9_sha256':sth,'readiness_v20_sha256':rdh,'operation_counts':oc,'selected_source_reviewer_counts':rc,'deferred_count':len(deferred),'support_gold_frozen':False,'next_authorized_stage':next},indent=2));return 0
def verify():
 z=checks();z['manifest_consistent']=not MAN.exists() or load(MAN)==manifest();z['terminal_xor']=not(RES.exists() and NEG.exists())
 if RES.exists():
  r=load(RES);s=load(SUB);p=load(PACK);e=read_entries(LOG);z.update({'result_manifest':r.get('manifest_sha256')==sha(MAN),'result_submission':r.get('submission_sha256')==sha(SUB),'result_log':r.get('attempt_log_sha256')==sha(LOG),'submission_26':len(s.get('adjudications',[]))==26,'checkpoints_26':len(list(CASES.glob('*.json')))==26,'order_exact':[x['adjudication_item_id'] for x in s['adjudications']]==[x['adjudication_item_id'] for x in p['items']],'no_mutation':s.get('boundary_mutation_performed') is False and s.get('reviewer_submission_mutation_performed') is False,'no_diagnostics':s.get('diagnostic_followup_items_processed')==0,'gold_false':r.get('support_gold_frozen') is False,'log_valid':bool(e),'state_ready':STATE.exists() and READY.exists(),'heldout_result':r.get('held_out_accessed') is False})
 if NEG.exists():
  n=load(NEG);z.update({'negative_authoritative':n.get('status')=='authoritative_negative_result','negative_no_retry':n.get('same_version_retry_allowed') is False,'negative_gold_false':n.get('support_gold_frozen') is False})
 print(json.dumps({'all_passed':all(z.values()),'checks':z,'hashes':{'adapter':sha(Path(__file__)),'manifest':sha(MAN) if MAN.exists() else None,'attempt_log':sha(LOG) if LOG.exists() else None,'submission':sha(SUB) if SUB.exists() else None,'result':sha(RES) if RES.exists() else None,'negative':sha(NEG) if NEG.exists() else None},'provider_called':LOG.exists(),'held_out_accessed':False},indent=2))
 if not all(z.values()):raise ValueError('verification_failed:'+','.join(k for k,v in z.items() if not v))
def main():
 a=argparse.ArgumentParser();g=a.add_mutually_exclusive_group(required=True);g.add_argument('--verify-prepared',action='store_true');g.add_argument('--freeze-manifest',action='store_true');g.add_argument('--execute',action='store_true');g.add_argument('--verify',action='store_true');x=a.parse_args()
 if x.freeze_manifest:freeze();return 0
 if x.execute:return execute()
 verify();return 0
if __name__=='__main__':raise SystemExit(main())

