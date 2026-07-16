#!/usr/bin/env python3
"""Type/Metadata Review v3 with fixed-length numeric representation."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,tempfile,urllib.error,urllib.request
from pathlib import Path
from phase7_execution_attempt_log import append_event
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
BOUND=D/'phase7_3_3_d_multi_claim_successor_boundary_reference_candidate_frame_v2.json';BSEAL=R/'phase7_3_3_d_multi_claim_successor_boundary_reference_seal_frame_v2.json';CLASS=R/'phase7_3_3_d_multi_claim_successor_type_metadata_v2_failure_classification.json';V2NEG=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_a_negative_frame_v2.json';SI=D/'phase7_3_3_d_support_stage_state_v72.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v83.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_type_metadata_review_protocol_frame_v3.json';SCH=C/'phase7_3_3_d_multi_claim_successor_type_metadata_review_schema_frame_v3.json';POL=C/'phase7_3_3_d_multi_claim_successor_type_metadata_review_policy_frame_v3.json';PROMPT=C/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_prompt_frame_v3.md';PKT=D/'phase7_3_3_d_multi_claim_successor_type_metadata_blind_packet_frame_v3.json';FIX=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_fixtures_frame_v3.json';PM=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_prepare_manifest_frame_v3.json';PR=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_prepare_receipt_frame_v3.json';LOG=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_attempts_frame_v3.jsonl';SP=D/'phase7_3_3_d_support_stage_state_v73.json';RP=R/'phase7_3_3_d1_reference_construction_readiness_v84.json'
EXP={BOUND:'55b4ed55e23c778bfc2cfdb525bf7bf49c78790a030a96e85fd3f4b0947f41d5',BSEAL:'a5e09580f5f196aa26550c20e50af175c1775baba9803f2cdfc8fdf34056e26d',CLASS:'401f737eb16aad64a64f375fa6059c277b48725bebc06874fd0cc026065360f1',V2NEG:'e0eb0dc53a88ba8676ed740ca11009d45e289d06ad681c8eb297af185c6ced91',SI:'09440e330c433f172c09afa1bcc9e6d6be95ac2aa21fc6bc9a4521a6ffc340ec',RI:'5d72b8b9db7976a379a25acc58cb7b38c8b0b9c8bbe76ceae3f0208de6d12d30'}
CUR='design_multi_claim_successor_type_metadata_review_frame_v3_representation';EXA='execute_multi_claim_successor_type_metadata_reviewer_a_frame_v3';EXB='execute_multi_claim_successor_type_metadata_reviewer_b_frame_v3';AGREE='construct_multi_claim_successor_type_metadata_agreement_frame_v3';FAIL='design_new_type_metadata_review_version_after_v3_negative';MODELS={'a':'gpt-4.1','b':'gpt-5.4'};BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';ROLE=['anchor','support','qualification','boundary','prediction','exception'];TYPE=['proposition','causal','prediction','scope','falsifiability','limitation','condition','exception']
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
def packet():return {'schema_version':3,'packet_id':'phase7.3.3-d-type-metadata-blind-packet-frame-v3','status':'frozen_boundary_only_fixed_order','case_count':40,'claim_count':240,'role_codebook':{str(i):x for i,x in enumerate(ROLE)},'type_codebook':{str(i):x for i,x in enumerate(TYPE)},'cases':[{'case_id':c['case_id'],'candidate_text':c['candidate_text'],'claim_count':len(c['claims']),'claims':[{'claim_position':i,'reference_claim_id':q['reference_claim_id'],'source_excerpt':q['source_excerpt']} for i,q in enumerate(c['claims'])]} for c in load(BOUND)['cases']],'evidence_present':False,'support_labels_present':False,'generation_roles_present':False,'v2_outputs_present':False}
def prompt():return '''# Type/Metadata Reviewer — Fixed Code Representation v3

## System message

Classify the six frozen Claims in their supplied order. Do not change Claims and do not judge evidence or support.

Return bare JSON with exactly two keys: role_codes and type_codes. Each value must be an array of exactly six integers. Position i classifies Claim position i.

Role codes: 0=anchor, 1=support, 2=qualification, 3=boundary, 4=prediction, 5=exception.
Type codes: 0=proposition, 1=causal, 2=prediction, 3=scope, 4=falsifiability, 5=limitation, 6=condition, 7=exception.

All claim_origin values are reconstructed as explicit by the Adapter and must not be output. Do not output Claim IDs, labels, rationale, confidence, Markdown, or extra keys.

## User message template

Classify this frozen ordered Claim list. Return bare JSON only.

{{CASE_JSON}}
'''
def schema():return {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['role_codes','type_codes'],'properties':{'role_codes':{'type':'array','minItems':6,'maxItems':6,'items':{'type':'integer','minimum':0,'maximum':5}},'type_codes':{'type':'array','minItems':6,'maxItems':6,'items':{'type':'integer','minimum':0,'maximum':7}}},'additionalProperties':False}
def protocol():return {'schema_version':3,'protocol_id':'phase7.3.3-d-type-metadata-review-protocol-frame-v3','status':'frozen_before_provider_call','predecessor_v2_negative_sha256':sha(V2NEG),'single_intended_change':'fixed-length numeric role/type arrays and deterministic explicit origin reconstruction','boundary_semantics_unchanged':True,'models':MODELS,'case_count':40,'claim_count':240,'evidence_visible':False,'support_visible':False,'first_provider_content_authoritative':True,'same_version_retry_allowed':False}
def policy():return {'schema_version':3,'policy_id':'phase7.3.3-d-type-metadata-review-policy-frame-v3','case_isolation':True,'temperature':0,'top_p':1,'max_tokens':1000,'response_format':{'type':'json_object'},'origin_reconstructed_by_adapter':'explicit','raw_provider_content_stored':False,'invalid_content_authoritative_negative':True,'transport_failure_resume_same_manifest':True}
def parse(case,o):
 if not isinstance(o,dict) or set(o)!={'role_codes','type_codes'}:raise ValueError('root_invalid')
 rc=o['role_codes'];tc=o['type_codes'];n=case['claim_count']
 if not isinstance(rc,list) or not isinstance(tc,list) or len(rc)!=n or len(tc)!=n:raise ValueError('fixed_length_mismatch')
 if any(type(x) is not int or x<0 or x>=len(ROLE) for x in rc) or any(type(x) is not int or x<0 or x>=len(TYPE) for x in tc):raise ValueError('code_invalid')
 return [{'reference_claim_id':q['reference_claim_id'],'claim_role':ROLE[rc[i]],'claim_type':TYPE[tc[i]],'claim_origin':'explicit','role_code':rc[i],'type_code':tc[i]} for i,q in enumerate(case['claims'])]
def fixtures():
 c=packet()['cases'][0];base={'role_codes':[0,1,2,3,4,5],'type_codes':[0,1,2,3,4,5]};xs=[]
 for name,o,want in [('valid',base,True),('short',{'role_codes':[0]*5,'type_codes':[0]*6},False),('bad_code',{'role_codes':[9]*6,'type_codes':[0]*6},False),('extra',dict(base,extra=1),False)]:
  try:parse(c,o);ok=True
  except ValueError:ok=False
  xs.append({'fixture_id':name,'passed':ok==want})
 return {'schema_version':3,'fixtures_id':'phase7.3.3-d-type-metadata-review-fixtures-frame-v3','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def mp(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_manifest_frame_v3.json'
def subp(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_submission_frame_v3.json'
def resp(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_result_frame_v3.json'
def recp(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_receipt_frame_v3.json'
def negp(r):return R/f'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_{r}_negative_frame_v3.json'
def cpp(r,c):return R/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_cases_frame_v3'/r/(c+'.json')
def manifest(r):return {'schema_version':3,'manifest_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-manifest-frame-v3','status':'frozen_not_started','reviewer':r,'model_requested':MODELS[r],'temperature':0,'top_p':1,'max_tokens':1000,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'schema_sha256':sha(SCH),'policy_sha256':sha(POL),'prompt_sha256':sha(PROMPT),'packet_sha256':sha(PKT),'fixtures_sha256':sha(FIX),'case_count':40,'claim_count':240,'first_provider_content_authoritative':True,'semantic_retry_authorized':False}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'v2_negative_preserved':s['multi_claim_successor_type_metadata_v2_negative_preserved'] is True,'same_version_retry_false':s['multi_claim_successor_type_metadata_v2_same_version_retry_allowed'] is False,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,SCH,POL,PROMPT,PKT,FIX,PM,PR,SP,RP,mp('a'),mp('b')])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def prepare():
 p=preflight()
 if p['status']!='PASS':return p
 once(PRO,protocol());once(SCH,schema());once(POL,policy());once(PROMPT,prompt().encode());pkh=once(PKT,packet());once(FIX,fixtures());ah=once(mp('a'),manifest('a'));bh=once(mp('b'),manifest('b'));pm={'schema_version':3,'manifest_id':'phase7.3.3-d-type-metadata-review-prepare-manifest-frame-v3','status':'frozen_before_any_v3_provider_call','adapter_sha256':sha(SELF),'artifacts':{rel(p):sha(p) for p in [PRO,SCH,POL,PROMPT,PKT,FIX,mp('a'),mp('b')]},'v2_negative_preserved':True,'next_authorized_stage':EXA};pmh=once(PM,pm);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_type_metadata_review_prepare_manifest_frame_v3_sha256':pmh};u={'status':'multi_claim_successor_type_metadata_review_frame_v3_frozen_reviewer_a_authorized','next_authorized_stage':EXA,'multi_claim_successor_type_metadata_review_frame_v3_frozen':True,'multi_claim_successor_type_metadata_reviewer_a_frame_v3_completed':False,'multi_claim_successor_type_metadata_reviewer_b_frame_v3_completed':False,'multi_claim_successor_type_metadata_v2_negative_preserved':True,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':73,'state_id':'phase7.3.3-d-support-stage-state-v73'});r.update({'schema_version':84,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v84'});sh=once(SP,s);r['artifact_lineage']['support_stage_state_v73_sha256']=sh;rh=once(RP,r);rec={'schema_version':3,'receipt_id':'phase7.3.3-d-type-metadata-review-prepare-receipt-frame-v3','status':'PASS','prepare_manifest_sha256':pmh,'reviewer_a_manifest_sha256':ah,'reviewer_b_manifest_sha256':bh,'state_sha256':sh,'readiness_sha256':rh,'fixtures':f"{fixtures()['passed_count']}/{fixtures()['fixture_count']}",'next_authorized_stage':EXA};rch=once(PR,rec);return {'status':'PASS','packet_sha256':pkh,'prepare_manifest_sha256':pmh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':EXA}
def call(key,model,system,user):
 payload={'model':model,'temperature':0,'top_p':1,'max_tokens':1000,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=600) as resp:return resp.read()
def split_prompt():
 x=PROMPT.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];return [q.strip() for q in x.split('\n## User message template\n\n',1)]
def canonical(req,got):
 if not isinstance(got,str):raise ValueError('model_missing')
 t=got.lower().rsplit('/',1)[-1];q=req.lower()
 if t==q or t.startswith(q+'-'):return req
 raise ValueError('model_family_mismatch')
def states(r):return (SP,RP,D/'phase7_3_3_d_support_stage_state_v74.json',R/'phase7_3_3_d1_reference_construction_readiness_v85.json',EXA,EXB) if r=='a' else (D/'phase7_3_3_d_support_stage_state_v74.json',R/'phase7_3_3_d1_reference_construction_readiness_v85.json',D/'phase7_3_3_d_support_stage_state_v75.json',R/'phase7_3_3_d1_reference_construction_readiness_v86.json',EXB,AGREE)
def finalize_state(r,nxt,subh,resh):
 si,ri,so,ro,_,_=states(r);s=copy.deepcopy(load(si));rd=copy.deepcopy(load(ri));sv=74 if r=='a' else 75;rv=85 if r=='a' else 86;line={f'multi_claim_successor_type_metadata_reviewer_{r}_submission_frame_v3_sha256':subh,f'multi_claim_successor_type_metadata_reviewer_{r}_result_frame_v3_sha256':resh};u={'status':'multi_claim_successor_type_metadata_reviewer_frame_v3_completed','next_authorized_stage':nxt,f'multi_claim_successor_type_metadata_reviewer_{r}_frame_v3_completed':True,'multi_claim_successor_type_metadata_review_frame_v3_provider_called':True,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,rd]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':sv,'state_id':f'phase7.3.3-d-support-stage-state-v{sv}'});rd.update({'schema_version':rv,'readiness_id':f'phase7.3.3-d1-reference-construction-readiness-v{rv}'});sh=once(so,s);rd['artifact_lineage'][f'support_stage_state_v{sv}_sha256']=sh;rh=once(ro,rd);return sh,rh
def execute(r):
 si,ri,_,_,stage,nxt=states(r)
 if load(si)['next_authorized_stage']!=stage or load(ri)['next_authorized_stage']!=stage:raise RuntimeError('stage_not_authorized')
 man=load(mp(r));mh=sha(mp(r))
 for p,k in [(SELF,'adapter_sha256'),(PRO,'protocol_sha256'),(SCH,'schema_sha256'),(POL,'policy_sha256'),(PROMPT,'prompt_sha256'),(PKT,'packet_sha256'),(FIX,'fixtures_sha256')]:
  if sha(p)!=man[k]:raise RuntimeError('manifest_hash_mismatch:'+rel(p))
 if resp(r).exists():return {'status':'PASS','terminal_outcome':'already_completed','next_authorized_stage':load(resp(r))['next_authorized_stage']}
 if negp(r).exists():return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','next_authorized_stage':FAIL}
 key=os.environ.get(CRED)
 if not key:raise RuntimeError('credential_missing:'+CRED)
 system,ut=split_prompt();done=[]
 for case in load(PKT)['cases']:
  cp=cpp(r,case['case_id'])
  if cp.exists():done.append(load(cp));continue
  append_event({'event_type':'type_metadata_v3_attempt_started','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'response_received':False,'authoritative_result':False},LOG)
  try:raw=call(key,MODELS[r],system,ut.replace('{{CASE_JSON}}',json.dumps(case,ensure_ascii=False,indent=2)))
  except (urllib.error.URLError,TimeoutError,OSError) as e:append_event({'event_type':'type_metadata_v3_transport_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_type':type(e).__name__,'response_received':False,'same_manifest_resume_allowed':True},LOG);return {'status':'TRANSPORT_FAILURE_RESUMABLE','completed_case_count':len(done),'failed_case_id':case['case_id']}
  eh=hb(raw);content=None
  try:env=json.loads(raw.decode());got=env.get('model');content=env['choices'][0]['message']['content'];ch=hb(content.encode());can=canonical(MODELS[r],got);rows=parse(case,json.loads(content))
  except Exception as e:
   ch=hb(content.encode()) if isinstance(content,str) else None;append_event({'event_type':'type_metadata_v3_contract_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_code':type(e).__name__+':'+str(e),'provider_envelope_sha256':eh,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);nh=once(negp(r),{'schema_version':3,'negative_result_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-negative-frame-v3','status':'authoritative_negative_result','failed_case_id':case['case_id'],'completed_case_count':len(done),'failure_code':type(e).__name__+':'+str(e),'manifest_sha256':mh,'same_version_retry_allowed':False,'capability_conclusion_authorized':False,'next_authorized_stage':FAIL});return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':nh,'next_authorized_stage':FAIL}
  z={'schema_version':3,'checkpoint_id':f'type-metadata-v3-{r}-{case["case_id"]}','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'provider_reported_model':got,'canonical_model_family':can,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'decisions':rows,'origin_reconstructed_by_adapter':True,'boundary_mutation_performed':False};cph=once(cp,z);append_event({'event_type':'type_metadata_v3_attempt_completed','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'decision_count':len(rows),'checkpoint_sha256':cph,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);done.append(z)
 cases=[{'case_id':x['case_id'],'decisions':x['decisions']} for x in done];sub={'schema_version':3,'submission_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-submission-frame-v3','status':'completed_independent_type_metadata_review','reviewer':r,'manifest_sha256':mh,'case_count':40,'decision_count':sum(len(x['decisions']) for x in done),'cases':cases,'origin_reconstructed_by_adapter':True,'boundary_mutation_performed':False,'completed':True};subh=once(subp(r),sub);res={'schema_version':3,'result_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-result-frame-v3','status':'completed','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':subh,'case_count':40,'decision_count':sub['decision_count'],'next_authorized_stage':nxt};resh=once(resp(r),res);sh,rh=finalize_state(r,nxt,subh,resh);rec={'schema_version':3,'receipt_id':f'phase7.3.3-d-type-metadata-reviewer-{r}-receipt-frame-v3','status':'PASS','submission_sha256':subh,'result_sha256':resh,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt};rch=once(recp(r),rec);return {'status':'PASS','reviewer':r,'case_count':40,'decision_count':sub['decision_count'],'submission_sha256':subh,'result_sha256':resh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt}
def verify():
 ps=[PRO,SCH,POL,PROMPT,PKT,FIX,PM,PR,SP,RP,mp('a'),mp('b')];z={'exists:'+rel(p):p.exists() for p in ps};z.update({'packet_replay':PKT.exists() and load(PKT)==packet(),'protocol_replay':PRO.exists() and load(PRO)==protocol(),'fixtures_replay':FIX.exists() and load(FIX)==fixtures(),'manifests_replay':all(mp(r).exists() and load(mp(r))==manifest(r) for r in MODELS)})
 for r in MODELS:
  if resp(r).exists():sub=load(subp(r));z[f'{r}_40_cases']=sub['case_count']==len(sub['cases'])==40;z[f'{r}_240_decisions']=sub['decision_count']==sum(len(x['decisions']) for x in sub['cases'])==240;z[f'{r}_origin_reconstructed']=sub['origin_reconstructed_by_adapter'] is True
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'terminal':{r:'completed' if resp(r).exists() else 'negative' if negp(r).exists() else None for r in MODELS},'next_authorized_stage':load(D/'phase7_3_3_d_support_stage_state_v75.json')['next_authorized_stage'] if (D/'phase7_3_3_d_support_stage_state_v75.json').exists() else load(SP)['next_authorized_stage'] if SP.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','prepare','execute-a','execute-b','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else prepare() if a.prepare else execute('a') if getattr(a,'execute_a') else execute('b') if getattr(a,'execute_b') else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE','AUTHORITATIVE_NEGATIVE_RESULT'} else 1
if __name__=='__main__':raise SystemExit(main())
