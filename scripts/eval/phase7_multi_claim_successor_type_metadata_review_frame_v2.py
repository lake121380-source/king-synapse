#!/usr/bin/env python3
"""Prepare and execute independent Type/Metadata Reviews for successor frame v2."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,tempfile,urllib.error,urllib.request
from pathlib import Path
from phase7_execution_attempt_log import append_event,read_entries
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
BOUND=D/'phase7_3_3_d_multi_claim_successor_boundary_reference_candidate_frame_v2.json';BSEAL=R/'phase7_3_3_d_multi_claim_successor_boundary_reference_seal_frame_v2.json';SI=D/'phase7_3_3_d_support_stage_state_v70.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v81.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_type_metadata_review_protocol_frame_v2.json';SCH=C/'phase7_3_3_d_multi_claim_successor_type_metadata_review_schema_frame_v2.json';POL=C/'phase7_3_3_d_multi_claim_successor_type_metadata_review_policy_frame_v2.json';PROMPT=C/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_prompt_frame_v2.md';PKT=D/'phase7_3_3_d_multi_claim_successor_type_metadata_blind_packet_frame_v2.json';FIX=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_fixtures_frame_v2.json';PM=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_prepare_manifest_frame_v2.json';PR=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_prepare_receipt_frame_v2.json';LOG=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_attempts_frame_v2.jsonl';SP=D/'phase7_3_3_d_support_stage_state_v71.json';RP=R/'phase7_3_3_d1_reference_construction_readiness_v82.json'
EXP={BOUND:'55b4ed55e23c778bfc2cfdb525bf7bf49c78790a030a96e85fd3f4b0947f41d5',BSEAL:'a5e09580f5f196aa26550c20e50af175c1775baba9803f2cdfc8fdf34056e26d',SI:'2f1b035e58914844430c9100fb69af85701813ee7736693e40e0a57425efc3e4',RI:'f3a5012463feb1308ae4ac0dd81d887722c8a4786593f3c352db062d6966d801'}
CUR='construct_multi_claim_successor_type_metadata_review_frame_v2';EXA='execute_multi_claim_successor_type_metadata_reviewer_a_frame_v2';EXB='execute_multi_claim_successor_type_metadata_reviewer_b_frame_v2';AGREE='construct_multi_claim_successor_type_metadata_agreement_frame_v2';FAIL='design_new_type_metadata_review_version_after_authoritative_negative';MODELS={'a':'gpt-4.1','b':'gpt-5.4'};BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';ROLES={'anchor','support','qualification','boundary','prediction','exception'};TYPES={'proposition','causal','prediction','scope','falsifiability','limitation','condition','exception'};ORIGINS={'explicit'}
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
def packet():return {'schema_version':2,'packet_id':'phase7.3.3-d-type-metadata-blind-packet-frame-v2','status':'frozen_boundary_only_no_evidence_no_support','case_count':40,'claim_count':240,'cases':[{'case_id':c['case_id'],'candidate_text':c['candidate_text'],'claims':[{k:copy.deepcopy(q[k]) for k in ['reference_claim_id','claim_index','source_span','source_excerpt']} for q in c['claims']]} for c in load(BOUND)['cases']],'evidence_present':False,'support_labels_present':False,'generation_roles_present':False,'other_reviewer_visible':False,'arm_outputs_present':False}
def prompt():return '''# Independent Claim Type and Structural Metadata Reviewer — Frame v2

## System message

Classify only the frozen Claims supplied in one Candidate. Do not change, merge, split, delete, reorder, or rewrite Claims. Do not judge evidence, support, correctness, citations, material error, or centrality.

For each Claim choose exactly one claim_role from: anchor, support, qualification, boundary, prediction, exception. Choose exactly one claim_type from: proposition, causal, prediction, scope, falsifiability, limitation, condition, exception. claim_origin must be explicit because all Claims are exact source spans.

Role describes structural function in the Candidate: anchor is the main assertion; support supplies a supporting assertion; qualification narrows an assertion; boundary states scope/limit; prediction states an anticipated outcome; exception states an exception. Type describes semantic form, independently of Role.

Return bare JSON with exactly one root key decisions. Each item must contain exactly reference_claim_id, claim_role, claim_type, claim_origin. Copy every reference_claim_id exactly and return each supplied Claim exactly once. No rationale, confidence, Markdown, or extra keys.

## User message template

Classify this frozen Candidate. Return bare JSON only.

{{CASE_JSON}}
'''
def schema():return {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['decisions'],'properties':{'decisions':{'type':'array','minItems':1,'items':{'type':'object','required':['reference_claim_id','claim_role','claim_type','claim_origin'],'properties':{'reference_claim_id':{'type':'string'},'claim_role':{'enum':sorted(ROLES)},'claim_type':{'enum':sorted(TYPES)},'claim_origin':{'enum':['explicit']}},'additionalProperties':False}}},'additionalProperties':False}
def protocol():return {'schema_version':2,'protocol_id':'phase7.3.3-d-type-metadata-review-protocol-frame-v2','status':'frozen_before_provider_call','boundary_reference_sha256':sha(BOUND),'reviewers':MODELS,'case_count':40,'claim_count':240,'boundary_mutation_allowed':False,'evidence_visible':False,'support_visible':False,'generation_roles_visible':False,'first_provider_content_authoritative':True,'same_version_semantic_retry_allowed':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def policy():return {'schema_version':2,'policy_id':'phase7.3.3-d-type-metadata-review-policy-frame-v2','case_isolation':True,'temperature':0,'top_p':1,'max_tokens':3000,'response_format':{'type':'json_object'},'raw_provider_content_stored':False,'transport_failure_resume_same_manifest':True,'invalid_content_authoritative_negative':True}
def parse(case,o):
 if not isinstance(o,dict) or set(o)!={'decisions'} or not isinstance(o['decisions'],list):raise ValueError('root_invalid')
 ids=[x['reference_claim_id'] for x in case['claims']];rows=o['decisions']
 if len(rows)!=len(ids):raise ValueError('decision_count_mismatch')
 if any(not isinstance(x,dict) or set(x)!={'reference_claim_id','claim_role','claim_type','claim_origin'} for x in rows):raise ValueError('decision_keys_invalid')
 if [x['reference_claim_id'] for x in rows]!=ids:raise ValueError('claim_ids_or_order_mismatch')
 if any(x['claim_role'] not in ROLES or x['claim_type'] not in TYPES or x['claim_origin'] not in ORIGINS for x in rows):raise ValueError('enum_invalid')
 return copy.deepcopy(rows)
def fixtures():
 c=packet()['cases'][0];base={'decisions':[{'reference_claim_id':q['reference_claim_id'],'claim_role':'anchor','claim_type':'proposition','claim_origin':'explicit'} for q in c['claims']]};xs=[]
 for name,o,want in [('valid',base,True),('missing',{'decisions':base['decisions'][:-1]},False),('extra_key',{'decisions':[dict(base['decisions'][0],extra=True),*base['decisions'][1:]]},False),('bad_role',{'decisions':[dict(base['decisions'][0],claim_role='bad'),*base['decisions'][1:]]},False)]:
  try:parse(c,o);ok=True
  except ValueError:ok=False
  xs.append({'fixture_id':name,'passed':ok==want})
 return {'schema_version':2,'fixtures_id':'phase7.3.3-d-type-metadata-review-fixtures-frame-v2','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def manifest_path(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_manifest_frame_v2.json'
def sub_path(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_submission_frame_v2.json'
def res_path(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_result_frame_v2.json'
def rec_path(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_receipt_frame_v2.json'
def neg_path(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_negative_frame_v2.json'
def cp_path(r,c):return R/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_cases_frame_v2'/r/(c+'.json')
def manifest(r):return {'schema_version':2,'manifest_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-manifest-frame-v2','status':'frozen_not_started','reviewer':r,'provider':'api.gpt.ge','model_requested':MODELS[r],'temperature':0,'top_p':1,'max_tokens':3000,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'schema_sha256':sha(SCH),'policy_sha256':sha(POL),'prompt_sha256':sha(PROMPT),'packet_sha256':sha(PKT),'fixtures_sha256':sha(FIX),'case_count':40,'claim_count':240,'first_provider_content_authoritative':True,'semantic_retry_authorized':False,'raw_provider_content_stored':False}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'boundary_sealed':s['multi_claim_successor_boundary_reference_frame_v2_sealed'] is True,'case_claim_count':load(BOUND)['case_count']==40 and load(BOUND)['claim_count']==240,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,SCH,POL,PROMPT,PKT,FIX,PM,PR,SP,RP,manifest_path('a'),manifest_path('b')])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def prepare():
 p=preflight()
 if p['status']!='PASS':return p
 ph=once(PRO,protocol());sh=once(SCH,schema());poh=once(POL,policy());prh=once(PROMPT,prompt().encode());pkh=once(PKT,packet());fh=once(FIX,fixtures());ah=once(manifest_path('a'),manifest('a'));bh=once(manifest_path('b'),manifest('b'));pm={'schema_version':2,'manifest_id':'phase7.3.3-d-type-metadata-review-prepare-manifest-frame-v2','status':'frozen_before_any_provider_call','adapter_sha256':sha(SELF),'artifacts':{rel(p):sha(p) for p in [PRO,SCH,POL,PROMPT,PKT,FIX,manifest_path('a'),manifest_path('b')]},'both_manifests_frozen_before_a':True,'next_authorized_stage':EXA};pmh=once(PM,pm);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_type_metadata_review_prepare_manifest_frame_v2_sha256':pmh};u={'status':'multi_claim_successor_type_metadata_review_frame_v2_frozen_reviewer_a_authorized','next_authorized_stage':EXA,'multi_claim_successor_type_metadata_review_frame_v2_frozen':True,'multi_claim_successor_type_metadata_reviewer_a_frame_v2_completed':False,'multi_claim_successor_type_metadata_reviewer_b_frame_v2_completed':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':71,'state_id':'phase7.3.3-d-support-stage-state-v71'});r.update({'schema_version':82,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v82'});sth=once(SP,s);r['artifact_lineage']['support_stage_state_v71_sha256']=sth;rrh=once(RP,r);rec={'schema_version':2,'receipt_id':'phase7.3.3-d-type-metadata-review-prepare-receipt-frame-v2','status':'PASS','prepare_manifest_sha256':pmh,'reviewer_a_manifest_sha256':ah,'reviewer_b_manifest_sha256':bh,'state_sha256':sth,'readiness_sha256':rrh,'fixtures':f"{fixtures()['passed_count']}/{fixtures()['fixture_count']}",'next_authorized_stage':EXA};rch=once(PR,rec);return {'status':'PASS','packet_sha256':pkh,'prepare_manifest_sha256':pmh,'receipt_sha256':rch,'state_sha256':sth,'readiness_sha256':rrh,'next_authorized_stage':EXA}
def call(key,model,system,user):
 payload={'model':model,'temperature':0,'top_p':1,'max_tokens':3000,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=600) as resp:return resp.read()
def split_prompt():
 x=PROMPT.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];return [q.strip() for q in x.split('\n## User message template\n\n',1)]
def canonical(req,got):
 if not isinstance(got,str):raise ValueError('model_missing')
 t=got.lower().rsplit('/',1)[-1];q=req.lower()
 if t==q or t.startswith(q+'-'):return req
 raise ValueError('model_family_mismatch')
def states(r):return (SP,RP,D/'phase7_3_3_d_support_stage_state_v72.json',R/'phase7_3_3_d1_reference_construction_readiness_v83.json',EXA,EXB) if r=='a' else (D/'phase7_3_3_d_support_stage_state_v72.json',R/'phase7_3_3_d1_reference_construction_readiness_v83.json',D/'phase7_3_3_d_support_stage_state_v73.json',R/'phase7_3_3_d1_reference_construction_readiness_v84.json',EXB,AGREE)
def finalize_state(r,status,nxt,subh,resh):
 si,ri,so,ro,_,_=states(r);s=copy.deepcopy(load(si));rd=copy.deepcopy(load(ri));sv=72 if r=='a' else 73;rv=83 if r=='a' else 84;line={f'multi_claim_successor_type_metadata_reviewer_{r}_submission_frame_v2_sha256':subh,f'multi_claim_successor_type_metadata_reviewer_{r}_result_frame_v2_sha256':resh};u={'status':status,'next_authorized_stage':nxt,f'multi_claim_successor_type_metadata_reviewer_{r}_frame_v2_completed':status.endswith('_completed'),'multi_claim_successor_type_metadata_review_frame_v2_provider_called':True,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,rd]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':sv,'state_id':f'phase7.3.3-d-support-stage-state-v{sv}'});rd.update({'schema_version':rv,'readiness_id':f'phase7.3.3-d1-reference-construction-readiness-v{rv}'});sth=once(so,s);rd['artifact_lineage'][f'support_stage_state_v{sv}_sha256']=sth;rrh=once(ro,rd);return sth,rrh
def execute(r):
 si,ri,_,_,stage,nxt=states(r)
 if load(si)['next_authorized_stage']!=stage or load(ri)['next_authorized_stage']!=stage:raise RuntimeError('stage_not_authorized')
 man=load(manifest_path(r));mh=sha(manifest_path(r))
 for p,k in [(SELF,'adapter_sha256'),(PRO,'protocol_sha256'),(SCH,'schema_sha256'),(POL,'policy_sha256'),(PROMPT,'prompt_sha256'),(PKT,'packet_sha256'),(FIX,'fixtures_sha256')]:
  if sha(p)!=man[k]:raise RuntimeError('manifest_hash_mismatch:'+rel(p))
 if res_path(r).exists():return {'status':'PASS','terminal_outcome':'already_completed','next_authorized_stage':load(res_path(r))['next_authorized_stage']}
 if neg_path(r).exists():return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','next_authorized_stage':FAIL}
 key=os.environ.get(CRED)
 if not key:raise RuntimeError('credential_missing:'+CRED)
 system,ut=split_prompt();done=[]
 for case in load(PKT)['cases']:
  cp=cp_path(r,case['case_id'])
  if cp.exists():done.append(load(cp));continue
  append_event({'event_type':'type_metadata_attempt_started','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'response_received':False,'authoritative_result':False},LOG)
  try:raw=call(key,MODELS[r],system,ut.replace('{{CASE_JSON}}',json.dumps(case,ensure_ascii=False,indent=2)))
  except (urllib.error.URLError,TimeoutError,OSError) as e:append_event({'event_type':'type_metadata_transport_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_type':type(e).__name__,'response_received':False,'same_manifest_resume_allowed':True},LOG);return {'status':'TRANSPORT_FAILURE_RESUMABLE','completed_case_count':len(done),'failed_case_id':case['case_id']}
  eh=hb(raw);content=None
  try:env=json.loads(raw.decode());got=env.get('model');content=env['choices'][0]['message']['content'];ch=hb(content.encode());can=canonical(MODELS[r],got);rows=parse(case,json.loads(content))
  except Exception as e:
   ch=hb(content.encode()) if isinstance(content,str) else None;append_event({'event_type':'type_metadata_contract_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_code':type(e).__name__+':'+str(e),'provider_envelope_sha256':eh,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);nh=once(neg_path(r),{'schema_version':2,'negative_result_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-negative-frame-v2','status':'authoritative_negative_result','failed_case_id':case['case_id'],'completed_case_count':len(done),'failure_code':type(e).__name__+':'+str(e),'manifest_sha256':mh,'same_version_retry_allowed':False,'capability_conclusion_authorized':False,'next_authorized_stage':FAIL});return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':nh,'next_authorized_stage':FAIL}
  z={'schema_version':2,'checkpoint_id':f'type-metadata-{r}-{case["case_id"]}','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'provider_reported_model':got,'canonical_model_family':can,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'decisions':rows,'boundary_mutation_performed':False,'support_judgment_performed':False};cph=once(cp,z);append_event({'event_type':'type_metadata_attempt_completed','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'decision_count':len(rows),'checkpoint_sha256':cph,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);done.append(z)
 cases=[{'case_id':x['case_id'],'decisions':x['decisions']} for x in done];sub={'schema_version':2,'submission_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-submission-frame-v2','status':'completed_independent_type_metadata_review','reviewer':r,'manifest_sha256':mh,'case_count':40,'decision_count':sum(len(x['decisions']) for x in done),'cases':cases,'boundary_mutation_performed':False,'support_judgment_performed':False,'completed':True};subh=once(sub_path(r),sub);res={'schema_version':2,'result_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-result-frame-v2','status':'completed','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':subh,'case_count':40,'decision_count':sub['decision_count'],'next_authorized_stage':nxt};resh=once(res_path(r),res);sth,rrh=finalize_state(r,'multi_claim_successor_type_metadata_reviewer_frame_v2_completed',nxt,subh,resh);rec={'schema_version':2,'receipt_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-receipt-frame-v2','status':'PASS','submission_sha256':subh,'result_sha256':resh,'state_sha256':sth,'readiness_sha256':rrh,'next_authorized_stage':nxt};rch=once(rec_path(r),rec);return {'status':'PASS','reviewer':r,'case_count':40,'decision_count':sub['decision_count'],'submission_sha256':subh,'result_sha256':resh,'receipt_sha256':rch,'state_sha256':sth,'readiness_sha256':rrh,'next_authorized_stage':nxt}
def verify():
 ps=[PRO,SCH,POL,PROMPT,PKT,FIX,PM,PR,SP,RP,manifest_path('a'),manifest_path('b')];z={'exists:'+rel(p):p.exists() for p in ps};z.update({'packet_replay':PKT.exists() and load(PKT)==packet(),'protocol_replay':PRO.exists() and load(PRO)==protocol(),'fixtures_replay':FIX.exists() and load(FIX)==fixtures(),'manifests_replay':all(manifest_path(r).exists() and load(manifest_path(r))==manifest(r) for r in MODELS)})
 for r in MODELS:
  if res_path(r).exists():sub=load(sub_path(r));z[f'{r}_40_cases']=sub['case_count']==len(sub['cases'])==40;z[f'{r}_240_decisions']=sub['decision_count']==sum(len(x['decisions']) for x in sub['cases'])==240;z[f'{r}_no_boundary_mutation']=sub['boundary_mutation_performed'] is False
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'terminal':{r:'completed' if res_path(r).exists() else 'negative' if neg_path(r).exists() else None for r in MODELS},'next_authorized_stage':load(D/'phase7_3_3_d_support_stage_state_v73.json')['next_authorized_stage'] if (D/'phase7_3_3_d_support_stage_state_v73.json').exists() else load(SP)['next_authorized_stage'] if SP.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','prepare','execute-a','execute-b','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else prepare() if a.prepare else execute('a') if getattr(a,'execute_a') else execute('b') if getattr(a,'execute_b') else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE','AUTHORITATIVE_NEGATIVE_RESULT'} else 1
if __name__=='__main__':raise SystemExit(main())
