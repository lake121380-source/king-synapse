#!/usr/bin/env python3
"""Independent Pilot Reference disagreement adjudication v1."""
from __future__ import annotations
import argparse, copy, hashlib, json, os, tempfile, urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event, read_entries
ROOT=Path(__file__).resolve().parents[2]; C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
WL=D/'phase7_3_3_d_independent_pilot_reference_disagreement_worklist_v2.json';AGR=R/'phase7_3_3_d_independent_pilot_reference_agreement_freeze_receipt_v2.json';REFPOL=C/'phase7_3_3_d_independent_reference_policy_v1.json';A=D/'phase7_3_3_d_independent_pilot_reference_reviewer_a_submission_v2.json';B=D/'phase7_3_3_d_independent_pilot_reference_reviewer_b_submission_v3.json';STATE_PREV=D/'phase7_3_3_d_support_stage_state_v16.json';READY_PREV=R/'phase7_3_3_d1_reference_construction_readiness_v27.json'
PROTOCOL=C/'phase7_3_3_d_independent_pilot_reference_adjudication_protocol_v1.json';POLICY=C/'phase7_3_3_d_independent_pilot_reference_adjudication_execution_policy_v1.json';PROMPT=C/'phase7_3_3_d_independent_pilot_reference_adjudicator_prompt_v1.md';SCHEMA=C/'phase7_3_3_d_independent_pilot_reference_adjudication_output_schema_v1.json';PACK=D/'phase7_3_3_d_independent_pilot_reference_adjudication_packet_v1.json';MAPPING=R/'phase7_3_3_d_independent_pilot_reference_adjudication_private_mapping_v1.json';FIXTURES=R/'phase7_3_3_d_independent_pilot_reference_adjudication_contract_fixtures_v1.json';FREEZE=R/'phase7_3_3_d_independent_pilot_reference_adjudication_freeze_manifest_v1.json';MANIFEST=R/'phase7_3_3_d_independent_pilot_reference_adjudication_execution_manifest_v1.json';LOG=R/'phase7_3_3_d_independent_pilot_reference_adjudication_attempts_v1.jsonl';CASES=R/'phase7_3_3_d_independent_pilot_reference_adjudication_cases_v1';SUB=D/'phase7_3_3_d_independent_pilot_reference_adjudication_submission_v1.json';RESULT=R/'phase7_3_3_d_independent_pilot_reference_adjudication_execution_result_v1.json';NEG=R/'phase7_3_3_d_independent_pilot_reference_adjudication_negative_result_v1.json';STATE=D/'phase7_3_3_d_support_stage_state_v17.json';READY=R/'phase7_3_3_d1_reference_construction_readiness_v28.json'
BASE='https://api.gpt.ge/v1';ENV='PHASE7_ATOMIC_JUDGE_API_KEY';MODEL='gpt-5.4';OPS={'select_option_1','select_option_2','defer_for_human_review'}
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
def csha(v):return hb(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def once(p,v):
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_artifact_conflict:'+str(p.relative_to(ROOT)))
  return hb(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p);return hb(b)
def text_once(p,t):
 b=t.encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_artifact_conflict:'+str(p.relative_to(ROOT)))
  return hb(b)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return hb(b)
def public_decision(x):return {'support_label':x['support_label'],'material':x['material'],'claim_type':x['claim_type'],'cited_evidence_ids':x['cited_evidence_ids'],'reason_codes':x['reason_codes'],'rationale':x['rationale'],'confidence':x['confidence']}
def prepare():
 for p in [WL,AGR,REFPOL,A,B,STATE_PREV,READY_PREV]:
  if not p.exists():raise FileNotFoundError(p)
 w=load(WL);items=[];maps=[]
 for idx,x in enumerate(w['items']):
  # deterministic 4/4 source balance; identities are private
  a_first=(idx%2==0)
  o1=public_decision(x['reviewer_a'] if a_first else x['reviewer_b']);o2=public_decision(x['reviewer_b'] if a_first else x['reviewer_a'])
  items.append({'adjudication_item_id':x['adjudication_item_id'],'case_id':x['case_id'],'domain':x['domain'],'candidate':x['candidate'],'candidate_sha256':x['candidate_sha256'],'context':x['context'],'evidence':x['evidence'],'disagreement_fields':x['disagreement_fields'],'option_1':o1,'option_2':o2})
  maps.append({'adjudication_item_id':x['adjudication_item_id'],'case_id':x['case_id'],'option_1_source':'reviewer_a' if a_first else 'reviewer_b','option_2_source':'reviewer_b' if a_first else 'reviewer_a','option_1_sha256':csha(o1),'option_2_sha256':csha(o2),'adjudicator_visible':False})
 protocol={'schema_version':1,'protocol_id':'phase7.3.3-d-independent-pilot-reference-adjudication-protocol-v1','status':'frozen_before_execution','purpose':'Resolve only the eight primary Independent Pilot reference disagreements after raw agreement, without access to either arm or Route A Gold.','item_count':len(items),'authorized_operations':sorted(OPS),'decision_rule':'select one complete frozen reviewer decision or defer; no synthesis','minimal_authorization':{'resolve_only_disagreement_items':True,'new_claim_creation':False,'claim_deletion':False,'boundary_mutation':False,'candidate_mutation':False,'evidence_mutation':False,'reviewer_submission_mutation':False,'diagnostic_followup_label_change':False},'visibility':{'candidate':True,'evidence':True,'anonymized_options':True,'reviewer_identity':False,'route_a_gold':False,'candidate_arm':False,'atomic_arm':False,'arm_metrics':False},'gold_policy':{'selected_support_label':True,'selected_materiality':True,'selected_claim_type':True,'selected_citations_reason_rationale_confidence':'diagnostic_only'},'defer_policy':'any deferral blocks Independent Reference freeze pending a separately frozen successor','failure_policy':{'first_provider_content_authoritative':True,'semantic_retry':False,'repair':False,'failure_is_immutable':True,'change_requires_successor_version':True}}
 policy={'schema_version':1,'policy_id':'phase7.3.3-d-independent-pilot-reference-adjudication-execution-policy-v1','status':'frozen','provider':'api.gpt.ge','model':'gpt-5.4','temperature':0,'top_p':1,'max_tokens':2500,'timeout_seconds':600,'response_format':{'type':'json_object'},'one_isolated_case_per_request':True,'authoritative_result_policy':protocol['failure_policy'],'data_handling':{'raw_provider_response_stored':False,'content_hash_before_parse':True,'envelope_hash':True,'credential_env_name':ENV,'confirmatory_opened':False}}
 prompt='''# Independent Pilot Reference Adjudicator v1\n\n## System message\nYou are the independent adjudicator for a frozen Pilot reference-construction protocol. You see one Candidate, its same-case Evidence, and two anonymized complete reviewer decisions. Select the decision best supported by the Evidence under conservative entailment. A Candidate is supported only when the Evidence supports the whole proposition without reversing the requested criterion, temporal direction, safety condition, or selection rule. Select unsupported when the available Evidence does not entail the Candidate or supports the opposite decision. Do not create a third label, rewrite the Candidate, change Evidence, change claim boundaries, combine options, or infer from hidden experiment arms. Defer only when the two frozen options cannot be resolved from the supplied Evidence. Return bare JSON only.\n\nRequired JSON:\n{"case_id":"...","adjudication_item_id":"...","decision":{"operation":"select_option_1|select_option_2|defer_for_human_review","rationale":"..."}}\n\n## User message template\nAdjudicate this isolated item:\n{{ITEM_JSON}}\n'''
 schema={'schema_version':1,'type':'object','additionalProperties':False,'required':['case_id','adjudication_item_id','decision'],'properties':{'case_id':{'type':'string'},'adjudication_item_id':{'type':'string'},'decision':{'type':'object','additionalProperties':False,'required':['operation','rationale'],'properties':{'operation':{'enum':sorted(OPS)},'rationale':{'type':'string','minLength':1}}}}}
 pack={'schema_version':1,'packet_id':'phase7.3.3-d-independent-pilot-reference-adjudication-packet-v1','status':'frozen_blind_packet','item_count':len(items),'reviewer_identity_visible':False,'route_a_gold_visible':False,'arm_outputs_visible':False,'items':items}
 mapping={'schema_version':1,'mapping_id':'phase7.3.3-d-independent-pilot-reference-adjudication-private-mapping-v1','status':'frozen_private_not_adjudicator_visible','item_count':len(maps),'option_1_source_counts':dict(Counter(x['option_1_source'] for x in maps)),'items':maps}
 ph=once(PROTOCOL,protocol);poh=once(POLICY,policy);prh=text_once(PROMPT,prompt);sch=once(SCHEMA,schema);pah=once(PACK,pack);mah=once(MAPPING,mapping)
 fixtures={'schema_version':1,'fixture_id':'phase7.3.3-d-independent-pilot-reference-adjudication-contract-fixtures-v1','status':'PASS','results':[{'id':'item_count_8','passed':len(items)==8},{'id':'option_balance_4_4','passed':Counter(x['option_1_source'] for x in maps)==Counter({'reviewer_a':4,'reviewer_b':4})},{'id':'identity_hidden','passed':not any('reviewer' in json.dumps(x,sort_keys=True).lower() for x in items)},{'id':'arms_hidden','passed':pack['route_a_gold_visible'] is False and pack['arm_outputs_visible'] is False},{'id':'lineage','passed':load(AGR)['status']=='PASS'},{'id':'minimal_authorization','passed':not any(protocol['minimal_authorization'][k] for k in ['new_claim_creation','claim_deletion','boundary_mutation','candidate_mutation','evidence_mutation'])}]}
 if not all(x['passed'] for x in fixtures['results']):raise ValueError('fixture_failure:'+','.join(x['id'] for x in fixtures['results'] if not x['passed']))
 fh=once(FIXTURES,fixtures)
 freeze={'schema_version':1,'manifest_id':'phase7.3.3-d-independent-pilot-reference-adjudication-freeze-manifest-v1','status':'frozen_ready_for_execution','artifact_sha256':{'protocol':ph,'policy':poh,'prompt':prh,'schema':sch,'packet':pah,'mapping':mah,'fixtures':fh,'agreement_receipt':sha(AGR),'reviewer_a':sha(A),'reviewer_b':sha(B),'state_v16':sha(STATE_PREV),'readiness_v27':sha(READY_PREV)},'item_count':len(items),'execution_started':False,'provider_called':False,'reference_frozen':False,'confirmatory_content_opened':False}
 frh=once(FREEZE,freeze);print(json.dumps({'status':'prepared','item_count':len(items),'fixtures':fixtures['results'],'freeze_manifest_sha256':frh},indent=2))
def checks():
 if not FREEZE.exists():return {'freeze_exists':False}
 f=load(FREEZE); p=load(PACK);m=load(MAPPING);x=load(FIXTURES)
 z={'freeze_ready':f['status']=='frozen_ready_for_execution','count_8':f['item_count']==p['item_count']==m['item_count']==8,'fixtures_pass':x['status']=='PASS' and all(i['passed'] for i in x['results']),'protocol':f['artifact_sha256']['protocol']==sha(PROTOCOL),'policy':f['artifact_sha256']['policy']==sha(POLICY),'prompt':f['artifact_sha256']['prompt']==sha(PROMPT),'schema':f['artifact_sha256']['schema']==sha(SCHEMA),'packet':f['artifact_sha256']['packet']==sha(PACK),'mapping':f['artifact_sha256']['mapping']==sha(MAPPING),'agreement':f['artifact_sha256']['agreement_receipt']==sha(AGR),'balanced':m['option_1_source_counts']=={'reviewer_a':4,'reviewer_b':4},'blind':p['reviewer_identity_visible'] is False and p['route_a_gold_visible'] is False and p['arm_outputs_visible'] is False,'not_started':f['execution_started'] is False and f['provider_called'] is False,'confirmatory_closed':f['confirmatory_content_opened'] is False}
 return z
def execution_manifest():
 z=checks()
 if not all(z.values()):raise ValueError('frozen_checks_failed:'+','.join(k for k,v in z.items() if not v))
 return {'schema_version':1,'manifest_id':'phase7.3.3-d-independent-pilot-reference-adjudication-execution-manifest-v1','status':'frozen_before_first_provider_call','decision_environment':{'provider':'api.gpt.ge','provider_base_url':BASE,'model_requested':MODEL,'canonical_model_family_expected':MODEL,'temperature':0,'top_p':1,'max_tokens':2500,'timeout_seconds':600,'response_format':{'type':'json_object'},'credential_env_name':ENV,'one_isolated_case_per_request':True},'artifact_lineage':{'adapter_sha256':sha(Path(__file__)),'freeze_manifest_sha256':sha(FREEZE),'protocol_sha256':sha(PROTOCOL),'policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'schema_sha256':sha(SCHEMA),'packet_sha256':sha(PACK),'mapping_sha256':sha(MAPPING),'agreement_receipt_sha256':sha(AGR)},'authoritative_result_policy':load(POLICY)['authoritative_result_policy'],'item_count':8,'execution_started':False,'provider_called':False,'reference_frozen':False,'confirmatory_content_opened':False}
def freeze_manifest():print(json.dumps({'status':'execution_manifest_frozen','manifest_sha256':once(MANIFEST,execution_manifest()),'provider_called':False},indent=2))
def prompt_parts():
 t=PROMPT.read_text(encoding='utf-8-sig');a=t.split('## System message\n',1)[1];s,u=a.split('\n## User message template\n',1);return s.strip(),u.strip()
def call(key,s,u):
 q={'model':MODEL,'temperature':0,'top_p':1,'max_tokens':2500,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':s},{'role':'user','content':u}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(q,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=600) as h:raw=h.read()
 return json.loads(raw.decode()),raw
def extract(env):
 if not isinstance(env,dict):raise ValueError('provider_envelope_not_object')
 rep=env.get('model');choices=env.get('choices')
 if not isinstance(rep,str) or not rep:raise ValueError('provider_reported_model_missing')
 if not (rep==MODEL or rep.startswith(MODEL+'-')):raise ValueError('provider_model_family_mismatch:'+rep)
 if not isinstance(choices,list) or len(choices)!=1:raise ValueError('provider_choices_invalid')
 msg=choices[0].get('message');content=msg.get('content') if isinstance(msg,dict) else None
 if not isinstance(content,str) or not content.strip():raise ValueError('provider_content_missing')
 return rep,content
def validate(v,i):
 if not isinstance(v,dict) or set(v)!={'case_id','adjudication_item_id','decision'}:raise ValueError('output_top_shape_invalid')
 if v['case_id']!=i['case_id'] or v['adjudication_item_id']!=i['adjudication_item_id']:raise ValueError('output_identity_mismatch')
 d=v['decision']
 if not isinstance(d,dict) or set(d)!={'operation','rationale'} or d.get('operation') not in OPS or not isinstance(d.get('rationale'),str) or not d['rationale'].strip():raise ValueError('output_decision_invalid')
 return {'case_id':i['case_id'],'adjudication_item_id':i['adjudication_item_id'],'decision':{'operation':d['operation'],'rationale':d['rationale'].strip()}}
def execute():
 z=checks()
 if not all(z.values()):raise ValueError('frozen_checks_failed')
 if not MANIFEST.exists() or load(MANIFEST)!=execution_manifest():raise ValueError('manifest_missing_or_invalid')
 if RESULT.exists() or NEG.exists():raise ValueError('terminal_artifact_exists')
 key=os.environ.get(ENV)
 if not key:raise ValueError('credential_env_missing:'+ENV)
 s,ut=prompt_parts();p=load(PACK);maps={x['adjudication_item_id']:x for x in load(MAPPING)['items']};out=[];models=set();mh=sha(MANIFEST)
 append_event({'event_type':'independent_reference_adjudication_invocation','manifest_sha256':mh,'status':'started','response_received':False,'authoritative_result':False},LOG)
 for idx,i in enumerate(p['items'],1):
  cp=CASES/f"{i['case_id']}.json"
  if cp.exists():raise ValueError('unexpected_preexisting_checkpoint:'+i['case_id'])
  received=False;content=None;env=None
  try:
   user=ut.replace('{{ITEM_JSON}}',json.dumps(i,ensure_ascii=False,indent=2));env,raw=call(key,s,user);received=True;eh=hb(raw);rep,content=extract(env);ch=hb(content.encode());v=validate(json.loads(content),i);mp=maps[i['adjudication_item_id']];op=v['decision']['operation'];row={'case_id':i['case_id'],'adjudication_item_id':i['adjudication_item_id'],'operation':op,'adjudicator_rationale':v['decision']['rationale'],'status':'deferred_for_human_review' if op=='defer_for_human_review' else 'selected_frozen_reviewer_decision','selected_option':None,'selected_source_reviewer':None,'selected_frozen_decision':None,'boundary_mutation_performed':False,'candidate_mutation_performed':False,'evidence_mutation_performed':False,'reviewer_submission_mutation_performed':False}
   if op!='defer_for_human_review':
    k='option_1' if op=='select_option_1' else 'option_2';row['selected_option']=k;row['selected_source_reviewer']=mp[k+'_source'];row['selected_frozen_decision']=copy.deepcopy(i[k]);row['selected_frozen_decision_sha256']=csha(i[k])
   checkpoint={'schema_version':1,'status':'completed','manifest_sha256':mh,'provider_reported_model':rep,'envelope_sha256':eh,'content_sha256':ch,'usage':env.get('usage'),'result':row};once(cp,checkpoint);out.append(row);models.add(rep)
   append_event({'event_type':'independent_reference_adjudication_case','manifest_sha256':mh,'case_id':i['case_id'],'status':'completed','response_received':True,'authoritative_result':True,'provider_reported_model':rep,'envelope_sha256':eh,'content_sha256':ch,'checkpoint_sha256':sha(cp)},LOG);print(f"Adjudication {idx}/8 {i['case_id']}: {op}",flush=True)
  except Exception as e:
   neg={'schema_version':1,'negative_result_id':'phase7.3.3-d-independent-pilot-reference-adjudication-negative-result-v1','status':'authoritative_negative_result','manifest_sha256':mh,'failed_case_id':i['case_id'],'completed_case_count':len(out),'failure_level':'level_0_transport' if not received else 'level_1_or_2_contract','failure_reason':str(e),'response_received':received,'content_sha256':hb(content.encode()) if isinstance(content,str) else None,'same_version_retry_allowed':False,'reference_freeze_allowed':False,'confirmatory_content_opened':False};once(NEG,neg);append_event({'event_type':'independent_reference_adjudication_terminal','manifest_sha256':mh,'case_id':i['case_id'],'status':'authoritative_negative_result','response_received':received,'authoritative_result':True,'failure_reason':str(e),'negative_result_sha256':sha(NEG)},LOG);print(json.dumps(neg,indent=2));return 2
 deferred=[x for x in out if x['operation']=='defer_for_human_review'];sub={'schema_version':1,'submission_id':'phase7.3.3-d-independent-pilot-reference-adjudication-submission-v1','status':'completed' if not deferred else 'completed_with_deferrals','manifest_sha256':mh,'case_count':len(out),'adjudications':out,'operation_counts':dict(Counter(x['operation'] for x in out)),'selected_source_counts':dict(Counter(x['selected_source_reviewer'] for x in out if x['selected_source_reviewer'])),'deferred_count':len(deferred),'boundary_mutation_performed':False,'candidate_mutation_performed':False,'evidence_mutation_performed':False,'reviewer_submission_mutation_performed':False,'route_a_gold_visible':False,'arm_outputs_visible':False,'confirmatory_content_opened':False};sh=once(SUB,sub);append_event({'event_type':'independent_reference_adjudication_terminal','manifest_sha256':mh,'status':'completed','response_received':True,'authoritative_result':True,'submission_sha256':sh},LOG);ents=read_entries(LOG)
 res={'schema_version':1,'result_id':'phase7.3.3-d-independent-pilot-reference-adjudication-execution-result-v1','status':'completed' if not deferred else 'completed_with_deferrals','manifest_sha256':mh,'submission_sha256':sh,'attempt_log_sha256':sha(LOG),'attempt_entry_count':len(ents),'checkpoint_count':len(list(CASES.glob('*.json'))),'provider_reported_models':sorted(models),'operation_counts':sub['operation_counts'],'selected_source_counts':sub['selected_source_counts'],'deferred_count':len(deferred),'independent_reference_freeze_allowed':not deferred,'route_a_gold_visible':False,'arm_outputs_visible':False,'confirmatory_content_opened':False};rh=once(RESULT,res)
 prev=load(STATE_PREV);state=dict(prev);state.update({'schema_version':17,'state_id':'phase7.3.3-d-support-stage-state-v17','independent_replication_state':'independent_pilot_reference_adjudication_completed' if not deferred else 'independent_pilot_reference_adjudication_deferrals_pending','independent_reference_adjudication_completed':not deferred,'independent_reference_adjudication_deferred_count':len(deferred),'next_authorized_stage':'freeze_independent_pilot_reference_v1' if not deferred else 'freeze_bounded_human_independent_reference_adjudication_successor','confirmatory_dataset_opened':False});state['artifact_lineage']=dict(prev['artifact_lineage']);state['artifact_lineage'].update({'support_stage_state_v16_sha256':sha(STATE_PREV),'readiness_v27_sha256':sha(READY_PREV),'independent_reference_adjudication_manifest_v1_sha256':mh,'independent_reference_adjudication_result_v1_sha256':rh})
 sth=once(STATE,state);ready={'schema_version':28,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v28','status':res['status'],'artifact_lineage':{'readiness_v27_sha256':sha(READY_PREV),'support_stage_state_v16_sha256':sha(STATE_PREV),'adjudication_result_sha256':rh,'support_stage_state_v17_sha256':sth},'reference_status':'independent_pilot_adjudication_completed_not_frozen' if not deferred else 'independent_pilot_adjudication_deferrals_block_freeze','next_authorized_stage':state['next_authorized_stage'],'independent_reference_adjudication_completed':not deferred,'independent_reference_frozen':False,'independent_dual_arm_execution_started':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};rdh=once(READY,ready);print(json.dumps({'status':res['status'],'submission_sha256':sh,'result_sha256':rh,'deferred_count':len(deferred),'state_v17_sha256':sth,'readiness_v28_sha256':rdh,'next_authorized_stage':state['next_authorized_stage']},indent=2));return 0
def verify():
 z=checks();z['manifest']=MANIFEST.exists() and load(MANIFEST)==execution_manifest();z['terminal_xor']=not(RESULT.exists() and NEG.exists())
 if RESULT.exists():
  r=load(RESULT);s=load(SUB);e=read_entries(LOG);z.update({'result_submission':r['submission_sha256']==sha(SUB),'result_log':r['attempt_log_sha256']==sha(LOG),'cases_8':len(s['adjudications'])==8,'checkpoints_8':len(list(CASES.glob('*.json')))==8,'no_mutation':not any(s[k] for k in ['boundary_mutation_performed','candidate_mutation_performed','evidence_mutation_performed','reviewer_submission_mutation_performed']),'blind':s['route_a_gold_visible'] is False and s['arm_outputs_visible'] is False,'confirmatory_closed_result':s['confirmatory_content_opened'] is False,'attempts_valid':bool(e),'state_ready':STATE.exists() and READY.exists()})
 if NEG.exists():z.update({'negative_authoritative':load(NEG)['status']=='authoritative_negative_result','negative_no_retry':load(NEG)['same_version_retry_allowed'] is False})
 print(json.dumps({'status':'PASS' if all(z.values()) else 'FAIL','checks':z,'hashes':{'adapter':sha(Path(__file__)),'manifest':sha(MANIFEST) if MANIFEST.exists() else None,'log':sha(LOG) if LOG.exists() else None,'submission':sha(SUB) if SUB.exists() else None,'result':sha(RESULT) if RESULT.exists() else None,'negative':sha(NEG) if NEG.exists() else None}},indent=2));
 if not all(z.values()):raise SystemExit(1)
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--freeze-manifest',action='store_true');g.add_argument('--execute',action='store_true');g.add_argument('--verify',action='store_true');x=ap.parse_args()
 if x.prepare:prepare()
 elif x.freeze_manifest:freeze_manifest()
 elif x.execute:raise SystemExit(execute())
 else:verify()
if __name__=='__main__':main()

