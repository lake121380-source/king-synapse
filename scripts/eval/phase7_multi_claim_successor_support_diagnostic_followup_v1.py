#!/usr/bin/env python3
"""Freeze, execute, and verify Support Diagnostic Follow-up v1."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,re,tempfile,urllib.error,urllib.request
from collections import Counter
from pathlib import Path
from phase7_execution_attempt_log import append_event,read_entries

SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
WL=D/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_worklist_v1.json';REF=D/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_v1.json';SEAL=R/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_seal_v1.json';QAREC=R/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_qa_receipt_v1.json';SI=D/'phase7_3_3_d_support_stage_state_v58.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v69.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_protocol_v1.json';POL=C/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_execution_policy_v1.json';SCH=C/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_schema_v1.json';PRM=C/'phase7_3_3_d_multi_claim_successor_support_diagnostic_reviewer_prompt_v1.md';PKT=D/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_packet_v1.json';MAP=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_private_option_mapping_v1.json';FIX=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_contract_fixtures_v1.json';MAN=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_execution_manifest_v1.json';LOG=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_attempts_v1.jsonl';CASES=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_cases_v1';SUB=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_completed_submission_v1.json';RES=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_result_v1.json';NEG=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_negative_result_v1.json';REC=R/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_receipt_v1.json';SO=D/'phase7_3_3_d_support_stage_state_v59.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v70.json'
EXP={WL:'6f57fd74618999fff13d7677e632717762744e5c0ff5740e9a49756d35d9d289',REF:'ffab8847cefc5a2b9d5537a035fa7a993774bdd5f47037efa74b03b1bf3c3327',SEAL:'afeeb60a885103444722f5777a1d412bf6a330434ad0f0dcf50d85a45dc835f6',QAREC:'0e299b9e6f618ed89bdda88d4f09daec97a4020a0b517f8dbeeb26e892c4a772',SI:'b241ac773a4af55b9f9ee3591d2fbcbdb8e36275821b083e98b36d1d08b21507',RI:'3b06393adca767eb5ab24ed4c7b9882b8abff269c0dc0fbd9ac5039e71eed7d8'}
CUR='execute_multi_claim_successor_support_diagnostic_followup_v1';NEXT='freeze_multi_claim_successor_support_gold_v1';NEXTNEG='design_new_multi_claim_successor_support_diagnostic_followup_version_if_research_continues';BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';MODEL='gpt-5.4';TEMP=0;TOPP=1;MAXTOK=3000;TIMEOUT=600;RF={'type':'json_object'};SEED='phase7.3.3-d-support-diagnostic-option-balance-v1'
DIFF={'equivalent_evidence_subset','complementary_evidence','redundant_citation','reason_code_granularity','rationale_wording_only','evidence_interpretation','confidence_calibration','mixed','possible_protocol_ambiguity'};ASSESS={'option_1_more_adequate','option_2_more_adequate','equivalent','complementary','neither_adequate','not_different'};CONF={'low','medium','high'};KEYS={'case_id','work_item_id','reference_claim_id','fixed_support_label','primary_difference_class','citation_assessment','reason_assessment','confidence_assessment','diagnostic_explanation','diagnostic_confidence'}
class CF(ValueError):
 def __init__(self,code,level='level_1_provider_representation',subtype='schema_failure',eh=None,ch=None,reported=None):super().__init__(code);self.code=code;self.level=level;self.subtype=subtype;self.eh=eh;self.ch=ch;self.reported=reported
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
def csha(x):return hb(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rel(p):return p.relative_to(ROOT).as_posix()
def once(p,x):
 b=x if isinstance(x,bytes) else (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise RuntimeError('immutable_artifact_mismatch:'+rel(p))
  return sha(p)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return hb(b)
def input_checks():return {'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
def view(x):return {k:copy.deepcopy(x[k]) for k in ['support_label','cited_evidence_ids','reason_codes','support_rationale','annotation_confidence']}
def set_relation(a,b):
 a=set(a);b=set(b)
 if a==b:return 'equal'
 if a<b:return 'option_1_strict_subset'
 if b<a:return 'option_2_strict_subset'
 if a&b:return 'overlapping'
 return 'disjoint'
def build():
 xs=load(WL)['items'];ordered=sorted(xs,key=lambda x:hb((SEED+'|'+x['work_item_id']).encode()));one_a={x['work_item_id'] for x in ordered[:24]};pub=[];private=[]
 for x in xs:
  s1='reviewer_a' if x['work_item_id'] in one_a else 'reviewer_b';s2='reviewer_b' if s1=='reviewer_a' else 'reviewer_a';o1=view(x[s1]);o2=view(x[s2])
  pub.append({k:copy.deepcopy(x[k]) for k in ['case_id','work_item_id','reference_claim_id','claim_index','source_span','source_excerpt','claim_role','claim_type','claim_origin','evidence_bundle','diagnostic_difference_types']}|{'fixed_support_label':x['reviewer_a']['support_label'],'option_1':o1,'option_2':o2,'deterministic_relations':{'citation_set':set_relation(o1['cited_evidence_ids'],o2['cited_evidence_ids']),'reason_code_set':set_relation(o1['reason_codes'],o2['reason_codes']),'annotation_confidence':'equal' if o1['annotation_confidence']==o2['annotation_confidence'] else 'different'},'authorization':{'support_label_change_allowed':False,'boundary_change_allowed':False,'diagnostic_classification_only':True}})
  private.append({'work_item_id':x['work_item_id'],'reference_claim_id':x['reference_claim_id'],'option_1_source':s1,'option_2_source':s2,'fixed_support_label':x['reviewer_a']['support_label'],'reviewer_a_diagnostic_sha256':csha(view(x['reviewer_a'])),'reviewer_b_diagnostic_sha256':csha(view(x['reviewer_b']))})
 return {'schema_version':1,'packet_id':'phase7.3.3-d-multi-claim-successor-support-diagnostic-followup-packet-v1','status':'frozen_blinded_diagnostic_only_packet','item_count':47,'source_reviewer_identity_visible':False,'support_label_change_authorized':False,'support_gold_visible':False,'items':pub},{'schema_version':1,'mapping_id':'phase7.3.3-d-multi-claim-successor-support-diagnostic-followup-private-option-mapping-v1','status':'frozen_private_mapping_not_visible_to_diagnostic_reviewer','item_count':47,'option_1_source_counts':dict(sorted(Counter(x['option_1_source'] for x in private).items())),'items':private}
def protocol():return {'schema_version':1,'protocol_id':'phase7.3.3-d-multi-claim-successor-support-diagnostic-followup-protocol-v1','status':'frozen_before_first_provider_execution','research_object':'explain 47 diagnostic disagreements conditional on immutable equal Support labels','entry_gate':{'support_label_reference_candidate_sealed':True,'work_item_count':47,'next_authorized_stage':CUR},'output_scope':['difference classification','comparative citation adequacy','comparative reason adequacy','confidence calibration assessment','brief diagnostic explanation'],'forbidden_actions':['change_support_label','create_replacement_label','modify_boundary','modify_claim_metadata','modify_reviewer_submission','create_support_gold','open_confirmatory_dataset','authorize_runtime_integration'],'completion_gate':{'all_47_items_require_valid_diagnostics':True,'support_label_sha256_must_remain_unchanged':True},'next_authorized_stage':NEXT}
def policy():return {'schema_version':1,'policy_id':'phase7.3.3-d-multi-claim-successor-support-diagnostic-followup-execution-policy-v1','authoritative_result_policy':{'first_provider_content_authoritative':True,'invalid_content_authoritative_negative':True,'post_content_same_version_retry_allowed':False,'transport_failure_before_content_resume_same_manifest':True},'execution_controls':{'one_isolated_claim_per_request':True,'model':MODEL,'temperature':TEMP,'top_p':TOPP,'max_tokens':MAXTOK,'response_format':RF,'timeout_seconds':TIMEOUT},'minimal_authorization':{'support_label_change_allowed':False,'diagnostic_classification_only':True},'credential_env_name':CRED}
def schema():return {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','additionalProperties':False,'required':sorted(KEYS),'properties':{'case_id':{'type':'string'},'work_item_id':{'type':'string'},'reference_claim_id':{'type':'string'},'fixed_support_label':{'enum':['supported','partially_supported','unsupported','not_assessable']},'primary_difference_class':{'enum':sorted(DIFF)},'citation_assessment':{'enum':sorted(ASSESS)},'reason_assessment':{'enum':sorted(ASSESS)},'confidence_assessment':{'enum':sorted(ASSESS)},'diagnostic_explanation':{'type':'string','minLength':1,'maxLength':2000},'diagnostic_confidence':{'enum':sorted(CONF)}}}
def prompt():return '''# Support Diagnostic Follow-up Reviewer v1

## System message

You are a blinded diagnostic reviewer. The Support label is frozen and immutable. Explain why two reviewers who assigned the same label used different citations, reason codes, or confidence.

Return one bare JSON object. Copy case_id, work_item_id, reference_claim_id, and fixed_support_label exactly. Classify primary_difference_class using only: equivalent_evidence_subset, complementary_evidence, redundant_citation, reason_code_granularity, rationale_wording_only, evidence_interpretation, confidence_calibration, mixed, possible_protocol_ambiguity. For citation_assessment, reason_assessment, and confidence_assessment use only: option_1_more_adequate, option_2_more_adequate, equivalent, complementary, neither_adequate, not_different. diagnostic_confidence must be low, medium, or high.

Do not change or reconsider the Support label. Do not create canonical citations or reasons. Do not modify Claim text, Boundary, Type, Role, metadata, evidence, or reviewer options. Judge diagnostic adequacy only from the supplied Claim and evidence.

Required keys: case_id, work_item_id, reference_claim_id, fixed_support_label, primary_difference_class, citation_assessment, reason_assessment, confidence_assessment, diagnostic_explanation, diagnostic_confidence.

## User message template

Diagnose this one frozen item. Return bare JSON only.

ITEM_JSON:
{{ITEM_JSON}}
'''
def parse_obj(o,item):
 if not isinstance(o,dict) or set(o)!=KEYS:raise CF('diagnostic_output_keys_invalid')
 for k in ['case_id','work_item_id','reference_claim_id','fixed_support_label']:
  if o.get(k)!=item[k]:raise CF(k+'_mismatch','level_2_support_contract','provenance_failure')
 if o.get('primary_difference_class') not in DIFF:raise CF('difference_class_invalid')
 for k in ['citation_assessment','reason_assessment','confidence_assessment']:
  if o.get(k) not in ASSESS:raise CF(k+'_invalid')
 q=o.get('diagnostic_explanation')
 if not isinstance(q,str) or not q.strip() or len(q)>2000:raise CF('diagnostic_explanation_invalid')
 if o.get('diagnostic_confidence') not in CONF:raise CF('diagnostic_confidence_invalid')
 return {**{k:o[k] for k in KEYS if k!='diagnostic_explanation'},'diagnostic_explanation':q.strip()}
def fixtures():
 p,_=build();i=p['items'][0];base={'case_id':i['case_id'],'work_item_id':i['work_item_id'],'reference_claim_id':i['reference_claim_id'],'fixed_support_label':i['fixed_support_label'],'primary_difference_class':'reason_code_granularity','citation_assessment':'not_different','reason_assessment':'equivalent','confidence_assessment':'not_different','diagnostic_explanation':'The reason codes differ in granularity while preserving the frozen label.','diagnostic_confidence':'high'};rows=[]
 def check(name,expected,x):
  actual='PASS'
  try:parse_obj(x,i)
  except CF:actual='REJECT'
  rows.append({'name':name,'expected':expected,'actual':actual,'passed':expected==actual})
 check('valid','PASS',copy.deepcopy(base));x=copy.deepcopy(base);x['fixed_support_label']='unsupported' if i['fixed_support_label']!='unsupported' else 'supported';check('reject_label_change','REJECT',x);x=copy.deepcopy(base);x['new_label']='supported';check('reject_extra_label','REJECT',x);x=copy.deepcopy(base);x['primary_difference_class']='unknown';check('reject_unknown_class','REJECT',x);x=copy.deepcopy(base);x['diagnostic_explanation']='';check('reject_empty_explanation','REJECT',x)
 return {'schema_version':1,'fixtures_id':'phase7.3.3-d-support-diagnostic-followup-fixtures-v1','fixture_count':len(rows),'fixtures_passed':sum(x['passed'] for x in rows),'all_fixtures_passed':all(x['passed'] for x in rows),'fixtures':rows}
def ref_labels_hash():
 r=load(REF);return csha([(x['reference_claim_id'],x['support_label']) for c in r['cases'] for x in c['claims']])
def preflight():
 z=input_checks()
 if all(z.values()):
  w=load(WL);s=load(SI);r=load(RI);p,m=build();xs=w['items'];ref={x['reference_claim_id']:x for c in load(REF)['cases'] for x in c['claims']}
  z.update({'worklist_47':w.get('work_item_count')==47 and len(xs)==47,'ids_unique':len({x['work_item_id'] for x in xs})==47 and len({x['reference_claim_id'] for x in xs})==47,'same_labels':all(x['reviewer_a']['support_label']==x['reviewer_b']['support_label']==ref[x['reference_claim_id']]['support_label'] for x in xs),'label_change_forbidden':all(x.get('label_change_authorized') is False for x in xs),'packet_47':p['item_count']==47,'mapping_47':m['item_count']==47,'option_balance':m['option_1_source_counts']=={'reviewer_a':24,'reviewer_b':23},'state_gate':s.get('next_authorized_stage')==CUR,'readiness_gate':r.get('next_authorized_stage')==CUR,'candidate_sealed':s.get('multi_claim_successor_support_reference_candidate_sealed') is True and r.get('multi_claim_successor_support_reference_candidate_sealed') is True,'gold_absent':s.get('multi_claim_successor_support_gold_created') is False,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_off':s.get('runtime_integration_authorized') is False,'provider_not_called':not LOG.exists()})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'provider_called':LOG.exists()}
def text_once(p,x):return once(p,x.encode())
def manifest():
 ps=[WL,REF,SEAL,QAREC,SI,RI,PRO,POL,SCH,PRM,PKT,MAP,FIX];p,m=build();return {'schema_version':1,'manifest_id':'phase7.3.3-d-support-diagnostic-followup-execution-manifest-v1','status':'frozen_ready_for_first_execution','adapter_sha256':sha(SELF),'model':MODEL,'temperature':TEMP,'top_p':TOPP,'max_tokens':MAXTOK,'response_format':RF,'timeout_seconds':TIMEOUT,'credential_env_name':CRED,'item_count':47,'option_1_source_counts':m['option_1_source_counts'],'reference_label_projection_sha256':ref_labels_hash(),'support_label_change_authorized':False,'first_provider_content_authoritative':True,'post_content_same_version_retry_allowed':False,'frozen_artifacts':{rel(x):{'sha256':sha(x)} for x in ps},'next_authorized_stage':CUR}
def prepare():
 q=preflight()
 if q['status']!='PASS':return q
 p,m=build();f=fixtures();h={'protocol_sha256':once(PRO,protocol()),'policy_sha256':once(POL,policy()),'schema_sha256':once(SCH,schema()),'prompt_sha256':text_once(PRM,prompt()),'packet_sha256':once(PKT,p),'mapping_sha256':once(MAP,m),'fixtures_sha256':once(FIX,f)};h['manifest_sha256']=once(MAN,manifest());return {'status':'PASS','fixtures':f"{f['fixtures_passed']}/{f['fixture_count']}",**h}
def verify_prepare():
 z=input_checks();ps=[PRO,POL,SCH,PRM,PKT,MAP,FIX,MAN];z.update({'exists:'+rel(p):p.exists() for p in ps})
 if all(p.exists() for p in ps):p,m=build();z.update({'protocol_replay':load(PRO)==protocol(),'policy_replay':load(POL)==policy(),'schema_replay':load(SCH)==schema(),'prompt_replay':PRM.read_text(encoding='utf-8-sig')==prompt(),'packet_replay':load(PKT)==p,'mapping_replay':load(MAP)==m,'fixtures_pass':load(FIX)==fixtures() and load(FIX)['all_fixtures_passed'],'manifest_replay':load(MAN)==manifest(),'terminal_absent':not RES.exists() and not NEG.exists() and not SUB.exists(),'provider_not_called':not LOG.exists()})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'hashes':{n:sha(p) if p.exists() else None for n,p in [('adapter',SELF),('protocol',PRO),('policy',POL),('schema',SCH),('prompt',PRM),('packet',PKT),('mapping',MAP),('fixtures',FIX),('manifest',MAN)]}}
def canonical(x):
 if not isinstance(x,str) or not x.strip():raise CF('provider_reported_model_missing',subtype='identity_failure')
 t=x.strip().lower().rsplit('/',1)[-1];q=MODEL.lower()
 if t==q or (t.startswith(q+'-') and re.fullmatch(r'[a-z0-9][a-z0-9._-]*',t[len(q)+1:])):return MODEL
 raise CF('provider_reported_model_family_mismatch',subtype='identity_failure',reported=x)
def split_prompt():
 x=PRM.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];return [q.strip() for q in x.split('\n## User message template\n\n',1)]
def call(key,system,user):
 payload={'model':MODEL,'temperature':TEMP,'top_p':TOPP,'max_tokens':MAXTOK,'response_format':RF,'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as resp:return resp.read()
def parse_response(raw,item):
 eh=hb(raw)
 try:e=json.loads(raw.decode())
 except Exception as x:raise CF('provider_envelope_json_invalid:'+type(x).__name__,subtype='envelope_parse_failure',eh=eh)
 reported=e.get('model');choices=e.get('choices');msg=choices[0].get('message') if isinstance(choices,list) and choices and isinstance(choices[0],dict) else None;content=msg.get('content') if isinstance(msg,dict) else None
 if not isinstance(content,str) or not content.strip():raise CF('provider_content_missing',subtype='content_missing',eh=eh,reported=reported)
 ch=hb(content.encode());can=canonical(reported)
 try:o=json.loads(content)
 except Exception as x:raise CF('provider_content_json_invalid:'+type(x).__name__,subtype='content_parse_failure',eh=eh,ch=ch,reported=reported)
 try:d=parse_obj(o,item)
 except CF as x:x.eh=eh;x.ch=ch;x.reported=reported;raise
 return d,{'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':reported,'canonical_model_family':can}
def checkpoint(w):return CASES/(w+'.json')
def terminal():return 'completed' if RES.exists() else 'negative' if NEG.exists() else None
def negative(item,e,done,mh):
 n={'schema_version':1,'negative_result_id':'phase7.3.3-d-support-diagnostic-followup-negative-result-v1','status':'authoritative_negative_result','failure_level':e.level,'failure_subtype':e.subtype,'failure_code':e.code,'failed_work_item_id':item['work_item_id'],'completed_item_count':done,'total_item_count':47,'provider_envelope_sha256':e.eh,'provider_content_sha256':e.ch,'provider_reported_model':e.reported,'manifest_sha256':mh,'same_version_retry_allowed':False,'support_label_changed':False,'support_gold_created':False,'capability_conclusion_authorized':False,'next_authorized_stage':NEXTNEG};nh=once(NEG,n);return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':nh,'next_authorized_stage':NEXTNEG}
def execute():
 if not MAN.exists() or load(MAN)!=manifest():raise RuntimeError('manifest_missing_or_invalid')
 if terminal()=='completed':return {'status':'PASS','terminal_outcome':'already_completed','result_sha256':sha(RES),'next_authorized_stage':load(RES)['next_authorized_stage']}
 if terminal()=='negative':return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','terminal_outcome':'already_negative','negative_result_sha256':sha(NEG),'next_authorized_stage':load(NEG)['next_authorized_stage']}
 key=os.environ.get(CRED)
 if not key:raise RuntimeError('credential_missing:'+CRED)
 mh=sha(MAN);p=load(PKT);system,ut=split_prompt();CASES.mkdir(parents=True,exist_ok=True);done=[]
 for item in p['items']:
  cp=checkpoint(item['work_item_id'])
  if cp.exists():done.append(load(cp));continue
  an=1+sum(1 for x in read_entries(LOG) if x.get('work_item_id')==item['work_item_id'] and x.get('event_type')=='attempt_started');append_event({'event_type':'attempt_started','manifest_sha256':mh,'attempt_number':an,'work_item_id':item['work_item_id'],'reference_claim_id':item['reference_claim_id'],'response_received':False,'authoritative_result':False},LOG)
  try:raw=call(key,system,ut.replace('{{ITEM_JSON}}',json.dumps(item,ensure_ascii=False,indent=2)))
  except (urllib.error.URLError,TimeoutError,OSError) as e:append_event({'event_type':'attempt_transport_failure','manifest_sha256':mh,'attempt_number':an,'work_item_id':item['work_item_id'],'failure_type':type(e).__name__,'response_received':False,'same_manifest_resume_allowed':True,'completed_item_count':len(done)},LOG);return {'status':'TRANSPORT_FAILURE_RESUMABLE','completed_item_count':len(done),'failed_work_item_id':item['work_item_id']}
  try:d,meta=parse_response(raw,item)
  except CF as e:append_event({'event_type':'attempt_contract_failure','manifest_sha256':mh,'attempt_number':an,'work_item_id':item['work_item_id'],'failure_code':e.code,'provider_envelope_sha256':e.eh,'provider_content_sha256':e.ch,'response_received':True,'authoritative_result':True},LOG);return negative(item,e,len(done),mh)
  z={'schema_version':1,'checkpoint_id':'phase7.3.3-d-support-diagnostic-followup-'+item['work_item_id'],'manifest_sha256':mh,**d,**meta,'support_label_changed':False,'boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False,'support_gold_created':False};ch=once(cp,z);append_event({'event_type':'attempt_completed','manifest_sha256':mh,'attempt_number':an,'work_item_id':item['work_item_id'],'reference_claim_id':item['reference_claim_id'],'provider_content_sha256':meta['provider_content_sha256'],'checkpoint_sha256':ch,'response_received':True,'authoritative_result':True},LOG);done.append(z)
 return finalize(done,mh)
def finalize(done,mh):
 if len(done)!=47:raise RuntimeError('completed_count_invalid')
 classes=Counter(x['primary_difference_class'] for x in done);sub={'schema_version':1,'submission_id':'phase7.3.3-d-support-diagnostic-followup-completed-submission-v1','status':'completed_diagnostic_only_no_label_changes','manifest_sha256':mh,'item_count':47,'reference_label_projection_sha256_before':load(MAN)['reference_label_projection_sha256'],'reference_label_projection_sha256_after':ref_labels_hash(),'difference_class_counts':dict(sorted(classes.items())),'diagnostics':done,'support_label_change_performed':False,'boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};sh=once(SUB,sub);res={'schema_version':1,'result_id':'phase7.3.3-d-support-diagnostic-followup-result-v1','status':'completed_support_gold_freeze_authorized','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':sh,'item_count':47,'difference_class_counts':dict(sorted(classes.items())),'support_label_projection_unchanged':sub['reference_label_projection_sha256_before']==sub['reference_label_projection_sha256_after'],'support_label_change_performed':False,'support_gold_created':False,'next_authorized_stage':NEXT};rh=once(RES,res);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_support_diagnostic_followup_protocol_v1_sha256':sha(PRO),'multi_claim_successor_support_diagnostic_followup_manifest_v1_sha256':mh,'multi_claim_successor_support_diagnostic_followup_submission_v1_sha256':sh,'multi_claim_successor_support_diagnostic_followup_result_v1_sha256':rh};u={'status':'multi_claim_successor_support_diagnostic_followup_completed_support_gold_freeze_authorized','next_authorized_stage':NEXT,'multi_claim_successor_support_diagnostic_followup_authorized':True,'multi_claim_successor_support_diagnostic_followup_completed':True,'multi_claim_successor_support_diagnostic_followup_count':47,'multi_claim_successor_support_label_projection_unchanged':True,'multi_claim_successor_support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':59,'state_id':'phase7.3.3-d-support-stage-state-v59'});r.update({'schema_version':70,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v70'});ssh=once(SO,s);r['artifact_lineage']['support_stage_state_v59_sha256']=ssh;rrh=once(RO,r);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-support-diagnostic-followup-receipt-v1','status':'PASS','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':sh,'result_sha256':rh,'state_sha256':ssh,'readiness_sha256':rrh,'support_label_projection_unchanged':True,'support_gold_created':False,'next_authorized_stage':NEXT};return {'status':'PASS','item_count':47,'difference_class_counts':dict(sorted(classes.items())),'submission_sha256':sh,'result_sha256':rh,'receipt_sha256':once(REC,rec),'state_sha256':ssh,'readiness_sha256':rrh,'next_authorized_stage':NEXT}
def verify():
 z=input_checks();ps=[PRO,POL,SCH,PRM,PKT,MAP,FIX,MAN,LOG,SUB,RES,REC,SO,RO];z.update({'exists:'+rel(p):p.exists() for p in ps})
 if all(p.exists() for p in ps):sub=load(SUB);res=load(RES);s=load(SO);r=load(RO);ds=sub['diagnostics'];z.update({'manifest_replay':load(MAN)==manifest(),'attempt_chain':bool(read_entries(LOG)),'item_count_47':len(ds)==47 and sub['item_count']==47,'ids_unique':len({x['work_item_id'] for x in ds})==47,'labels_fixed':all(x['fixed_support_label']=={q['reference_claim_id']:q for c in load(REF)['cases'] for q in c['claims']}[x['reference_claim_id']]['support_label'] for x in ds),'label_projection_unchanged':sub['reference_label_projection_sha256_before']==sub['reference_label_projection_sha256_after']==ref_labels_hash() and res['support_label_projection_unchanged'] is True,'no_label_change':sub['support_label_change_performed'] is False,'no_boundary_change':sub['boundary_mutation_performed'] is False,'result_lineage':res['submission_sha256']==sha(SUB),'receipt_lineage':load(REC)['result_sha256']==sha(RES) and load(REC)['state_sha256']==sha(SO) and load(REC)['readiness_sha256']==sha(RO),'next_gate':s['next_authorized_stage']==r['next_authorized_stage']==NEXT,'gold_absent':s['multi_claim_successor_support_gold_created'] is False and r['multi_claim_successor_support_gold_created'] is False,'confirmatory_closed':s['confirmatory_dataset_opened'] is False and r['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False and r['runtime_integration_authorized'] is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'hashes':{n:sha(p) if p.exists() else None for n,p in [('adapter',SELF),('manifest',MAN),('attempt_log',LOG),('submission',SUB),('result',RES),('receipt',REC),('state',SO),('readiness',RO)]},'next_authorized_stage':s['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','fixtures','prepare','verify-prepare','execute','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else fixtures() if a.fixtures else prepare() if a.prepare else verify_prepare() if getattr(a,'verify_prepare') else execute() if a.execute else verify()
 if a.fixtures:o['status']='PASS' if o['all_fixtures_passed'] else 'FAIL'
 print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE','AUTHORITATIVE_NEGATIVE_RESULT'} else 1
if __name__=='__main__':raise SystemExit(main())
