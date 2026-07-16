#!/usr/bin/env python3
"""Execute blinded selection-only Type/Metadata Adjudication frame v3."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,tempfile,urllib.error,urllib.request
from collections import Counter,defaultdict
from pathlib import Path
from phase7_execution_attempt_log import append_event
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
WL=D/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_worklist_frame_v3.json';MAP=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_private_mapping_frame_v3.json';AGR=R/'phase7_3_3_d_multi_claim_successor_type_metadata_agreement_report_frame_v3.json';AREC=R/'phase7_3_3_d_multi_claim_successor_type_metadata_agreement_receipt_frame_v3.json';SI=D/'phase7_3_3_d_support_stage_state_v76.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v87.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_protocol_frame_v3.json';SCH=C/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_schema_frame_v3.json';POL=C/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_policy_frame_v3.json';PROMPT=C/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudicator_prompt_frame_v3.md';PKT=D/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_packet_frame_v3.json';FIX=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_fixtures_frame_v3.json';MAN=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_manifest_frame_v3.json';LOG=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_attempts_frame_v3.jsonl';CASES=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_cases_frame_v3';SUB=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_submission_frame_v3.json';RES=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_result_frame_v3.json';NEG=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_negative_frame_v3.json';REC=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_receipt_frame_v3.json';SO=D/'phase7_3_3_d_support_stage_state_v77.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v88.json'
EXP={WL:'75f4db2e3230b792f0ce161d5a5aa5debc18a6816bd65f586745bee500ed1dd2',MAP:'a57f433742e6c03af872ccd8291ee4e10dbec7b8f783875a12b44168d4da59a8',AGR:'5aeefac268fa65d0db94a0eaa94d25bdc15180b5aa0cdc0a10cfb88878f98940',AREC:'a75796e7eba23bc868ca1710dce2d049feb0b2be0d85effdc5ea89fe99135847',SI:'44abc2bda67e062970a5e79733cd4fd8cdc7d9a0d8a92e8845bec13d70912018',RI:'b2261424b8de55b944ac2e87a4a08ebf2e6991f399d4cc3bd914e873558b8743'}
CUR='execute_multi_claim_successor_type_metadata_adjudication_frame_v3';NEXT='construct_multi_claim_successor_type_metadata_reference_frame_v3';DEFER='resolve_multi_claim_successor_type_metadata_adjudication_deferrals_frame_v3';FAIL='design_new_type_metadata_adjudication_version_after_negative';MODEL='gpt-5.4';BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY'
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
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
def packet():
 by=defaultdict(list)
 for x in load(WL)['items']:by[x['case_id']].append(copy.deepcopy(x))
 return {'schema_version':3,'packet_id':'phase7.3.3-d-type-metadata-adjudication-packet-frame-v3','status':'frozen_blinded_selection_only','case_count':len(by),'item_count':sum(map(len,by.values())),'cases':[{'case_id':k,'candidate_text':v[0]['candidate_text'],'item_count':len(v),'items':[{q:copy.deepcopy(x[q]) for q in ['work_item_id','reference_claim_id','claim_index','source_excerpt','option_1','option_2','claim_origin']} for x in v]} for k,v in by.items()],'source_reviewer_identity_visible':False,'support_visible':False,'boundary_change_authorized':False}
def prompt():return '''# Blinded Type/Metadata Adjudicator — Frame v3

## System message

For each frozen disagreement item, select the better existing joint Claim Role + Claim Type option. Never create a third option and never modify Claim boundaries or text.

Roles: anchor=main assertion; support=supporting assertion; qualification=narrows another assertion; boundary=states scope or limit; prediction=anticipated outcome; exception=exception to a rule. Types: proposition, causal, prediction, scope, falsifiability, limitation, condition, exception.

Return bare JSON with exactly one key selection_codes. It must be an integer array with one entry per supplied item in order: 0 selects option_1, 1 selects option_2, 2 defers for human review. Use 2 only if neither existing option is defensible. Do not output rationale, labels, Claim IDs, Markdown, or extra keys.

## User message template

Adjudicate this frozen case. Return bare JSON only.

{{CASE_JSON}}
'''
def schema():return {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['selection_codes'],'properties':{'selection_codes':{'type':'array','minItems':1,'items':{'type':'integer','minimum':0,'maximum':2}}},'additionalProperties':False}
def protocol():return {'schema_version':3,'protocol_id':'phase7.3.3-d-type-metadata-adjudication-protocol-frame-v3','status':'frozen_before_provider_call','selection_only':True,'allowed_codes':{'0':'option_1','1':'option_2','2':'defer_for_human_review'},'item_count':158,'source_reviewer_identity_visible':False,'replacement_role_or_type_allowed':False,'boundary_mutation_allowed':False,'support_judgment_allowed':False,'first_provider_content_authoritative':True,'same_version_retry_allowed':False}
def policy():return {'schema_version':3,'policy_id':'phase7.3.3-d-type-metadata-adjudication-policy-frame-v3','case_isolation':True,'model':MODEL,'temperature':0,'top_p':1,'max_tokens':1000,'response_format':{'type':'json_object'},'raw_provider_content_stored':False,'transport_failure_resume_same_manifest':True,'invalid_content_authoritative_negative':True}
def parse(case,o):
 if not isinstance(o,dict) or set(o)!={'selection_codes'} or not isinstance(o['selection_codes'],list) or len(o['selection_codes'])!=case['item_count']:raise ValueError('selection_shape_invalid')
 if any(type(x) is not int or x not in {0,1,2} for x in o['selection_codes']):raise ValueError('selection_code_invalid')
 return o['selection_codes']
def fixtures():
 c=packet()['cases'][0];good={'selection_codes':[0]*c['item_count']};xs=[]
 for n,o,w in [('valid',good,True),('short',{'selection_codes':good['selection_codes'][:-1]},False),('bad',{'selection_codes':[9]*c['item_count']},False),('extra',dict(good,extra=1),False)]:
  try:parse(c,o);ok=True
  except ValueError:ok=False
  xs.append({'fixture_id':n,'passed':ok==w})
 return {'schema_version':3,'fixtures_id':'phase7.3.3-d-type-metadata-adjudication-fixtures-frame-v3','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def manifest():return {'schema_version':3,'manifest_id':'phase7.3.3-d-type-metadata-adjudication-manifest-frame-v3','status':'frozen_not_started','model_requested':MODEL,'temperature':0,'top_p':1,'max_tokens':1000,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'schema_sha256':sha(SCH),'policy_sha256':sha(POL),'prompt_sha256':sha(PROMPT),'packet_sha256':sha(PKT),'mapping_sha256':sha(MAP),'fixtures_sha256':sha(FIX),'case_count':packet()['case_count'],'item_count':158,'first_provider_content_authoritative':True,'same_version_retry_allowed':False}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'items_158':load(WL)['item_count']==158,'mapping_158':load(MAP)['item_count']==158,'option_balance':load(MAP)['option_1_source_counts']=={'reviewer_a':79,'reviewer_b':79},'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,SCH,POL,PROMPT,PKT,FIX,MAN,LOG,SUB,RES,NEG,REC,SO,RO])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def prepare():
 p=preflight()
 if p['status']!='PASS':return p
 once(PRO,protocol());once(SCH,schema());once(POL,policy());once(PROMPT,prompt().encode());pkh=once(PKT,packet());once(FIX,fixtures());mh=once(MAN,manifest());return {'status':'PASS','packet_sha256':pkh,'manifest_sha256':mh,'fixtures':f"{fixtures()['passed_count']}/{fixtures()['fixture_count']}"}
def call(key,system,user):
 payload={'model':MODEL,'temperature':0,'top_p':1,'max_tokens':1000,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=600) as resp:return resp.read()
def split_prompt():
 x=PROMPT.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];return [q.strip() for q in x.split('\n## User message template\n\n',1)]
def execute():
 if load(MAN)!=manifest():raise RuntimeError('manifest_invalid')
 if RES.exists():return {'status':'PASS','terminal_outcome':'already_completed','next_authorized_stage':load(RES)['next_authorized_stage']}
 if NEG.exists():return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','next_authorized_stage':FAIL}
 key=os.environ.get(CRED)
 if not key:raise RuntimeError('credential_missing:'+CRED)
 system,ut=split_prompt();mh=sha(MAN);done=[];mapping={x['work_item_id']:x for x in load(MAP)['items']}
 for case in load(PKT)['cases']:
  cp=CASES/(case['case_id']+'.json')
  if cp.exists():done.append(load(cp));continue
  append_event({'event_type':'type_metadata_adjudication_attempt_started','manifest_sha256':mh,'case_id':case['case_id'],'response_received':False,'authoritative_result':False},LOG)
  try:raw=call(key,system,ut.replace('{{CASE_JSON}}',json.dumps(case,ensure_ascii=False,indent=2)))
  except (urllib.error.URLError,TimeoutError,OSError) as e:append_event({'event_type':'type_metadata_adjudication_transport_failure','manifest_sha256':mh,'case_id':case['case_id'],'failure_type':type(e).__name__,'response_received':False,'same_manifest_resume_allowed':True},LOG);return {'status':'TRANSPORT_FAILURE_RESUMABLE','completed_case_count':len(done),'failed_case_id':case['case_id']}
  eh=hb(raw);content=None
  try:env=json.loads(raw.decode());got=env.get('model');content=env['choices'][0]['message']['content'];ch=hb(content.encode());codes=parse(case,json.loads(content))
  except Exception as e:
   ch=hb(content.encode()) if isinstance(content,str) else None;append_event({'event_type':'type_metadata_adjudication_contract_failure','manifest_sha256':mh,'case_id':case['case_id'],'failure_code':type(e).__name__+':'+str(e),'provider_envelope_sha256':eh,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);nh=once(NEG,{'schema_version':3,'negative_result_id':'phase7.3.3-d-type-metadata-adjudication-negative-frame-v3','status':'authoritative_negative_result','failed_case_id':case['case_id'],'completed_case_count':len(done),'failure_code':type(e).__name__+':'+str(e),'manifest_sha256':mh,'same_version_retry_allowed':False,'capability_conclusion_authorized':False,'next_authorized_stage':FAIL});return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':nh,'next_authorized_stage':FAIL}
  decisions=[]
  for item,code in zip(case['items'],codes):
   m=mapping[item['work_item_id']];opt=None if code==2 else 'option_1' if code==0 else 'option_2';dec=None if opt is None else copy.deepcopy(item[opt]);src=None if opt is None else m[opt+'_source'];decisions.append({'work_item_id':item['work_item_id'],'case_id':case['case_id'],'reference_claim_id':item['reference_claim_id'],'selection_code':code,'selected_option':opt,'selected_source_reviewer':src,'selected_decision':dec,'claim_origin':'explicit','boundary_mutation_performed':False,'support_judgment_performed':False})
  z={'schema_version':3,'checkpoint_id':'type-metadata-adjudication-'+case['case_id'],'manifest_sha256':mh,'case_id':case['case_id'],'provider_reported_model':got,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'decisions':decisions};cph=once(cp,z);append_event({'event_type':'type_metadata_adjudication_attempt_completed','manifest_sha256':mh,'case_id':case['case_id'],'decision_count':len(decisions),'checkpoint_sha256':cph,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);done.append(z)
 ads=[x for c in done for x in c['decisions']];defer=sum(x['selection_code']==2 for x in ads);ops=Counter(x['selection_code'] for x in ads);sub={'schema_version':3,'submission_id':'phase7.3.3-d-type-metadata-adjudication-submission-frame-v3','status':'completed_no_deferrals' if not defer else 'completed_with_deferrals','manifest_sha256':mh,'case_count':len(done),'item_count':len(ads),'deferred_count':defer,'selection_code_counts':dict(sorted(ops.items())),'adjudications':ads,'boundary_mutation_performed':False,'support_judgment_performed':False};subh=once(SUB,sub);nxt=NEXT if not defer else DEFER;res={'schema_version':3,'result_id':'phase7.3.3-d-type-metadata-adjudication-result-frame-v3','status':'completed_reference_authorized' if not defer else 'completed_deferrals_pending','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':subh,'item_count':len(ads),'deferred_count':defer,'next_authorized_stage':nxt};resh=once(RES,res);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_type_metadata_adjudication_manifest_frame_v3_sha256':mh,'multi_claim_successor_type_metadata_adjudication_submission_frame_v3_sha256':subh,'multi_claim_successor_type_metadata_adjudication_result_frame_v3_sha256':resh};u={'status':'multi_claim_successor_type_metadata_adjudication_frame_v3_completed_reference_authorized' if not defer else 'multi_claim_successor_type_metadata_adjudication_deferrals_pending','next_authorized_stage':nxt,'multi_claim_successor_type_metadata_adjudication_frame_v3_completed':not defer,'multi_claim_successor_type_metadata_adjudication_deferred_count':defer,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for q in [s,r]:q.setdefault('artifact_lineage',{}).update(line);q.update(u)
 s.update({'schema_version':77,'state_id':'phase7.3.3-d-support-stage-state-v77'});r.update({'schema_version':88,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v88'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v77_sha256']=sh;rh=once(RO,r);rec={'schema_version':3,'receipt_id':'phase7.3.3-d-type-metadata-adjudication-receipt-frame-v3','status':'PASS','manifest_sha256':mh,'submission_sha256':subh,'result_sha256':resh,'state_sha256':sh,'readiness_sha256':rh,'item_count':len(ads),'deferred_count':defer,'next_authorized_stage':nxt};rch=once(REC,rec);return {'status':'PASS','case_count':len(done),'item_count':len(ads),'deferred_count':defer,'selection_code_counts':dict(sorted(ops.items())),'submission_sha256':subh,'result_sha256':resh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt}
def verify():
 ps=[PRO,SCH,POL,PROMPT,PKT,FIX,MAN,LOG,SUB,RES,REC,SO,RO];z={'exists:'+rel(p):p.exists() for p in ps}
 if all(p.exists() for p in ps):sub=load(SUB);ads=sub['adjudications'];s=load(SO);r=load(RO);z.update({'manifest_replay':load(MAN)==manifest(),'packet_replay':load(PKT)==packet(),'fixtures_replay':load(FIX)==fixtures(),'items_158':len(ads)==sub['item_count']==158,'ids_unique':len({x['work_item_id'] for x in ads})==158,'selected_existing_only':all(x['selected_decision'] is None if x['selection_code']==2 else x['selected_decision'] in [next(i for c in load(PKT)['cases'] for i in c['items'] if i['work_item_id']==x['work_item_id'])['option_1'],next(i for c in load(PKT)['cases'] for i in c['items'] if i['work_item_id']==x['work_item_id'])['option_2']] for x in ads),'no_boundary_or_support':sub['boundary_mutation_performed'] is False and sub['support_judgment_performed'] is False,'next_gate':s['next_authorized_stage']==r['next_authorized_stage']==load(RES)['next_authorized_stage'],'confirmatory_closed':s['confirmatory_dataset_opened'] is False and r['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False and r['runtime_integration_authorized'] is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','prepare','execute','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else prepare() if a.prepare else execute() if a.execute else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE','AUTHORITATIVE_NEGATIVE_RESULT'} else 1
if __name__=='__main__':raise SystemExit(main())
