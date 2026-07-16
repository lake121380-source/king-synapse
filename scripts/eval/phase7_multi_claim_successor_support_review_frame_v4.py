#!/usr/bin/env python3
"""Support Review v4: fixed label codes plus unchanged citation masks."""
from __future__ import annotations
import argparse,copy,hashlib,importlib.util,json,os,sys,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/eval'));base=ROOT/'scripts/eval/phase7_multi_claim_successor_support_review_frame_v3.py';spec=importlib.util.spec_from_file_location('support_v3_frozen',base);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports';SELF=Path(__file__).resolve();TREF=D/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_frame_v3.json';DATA=D/'phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json';CLASS=R/'phase7_3_3_d_multi_claim_successor_support_v3_failure_classification.json';V3NEG=R/'phase7_3_3_d_multi_claim_successor_support_reviewer_a_negative_frame_v3.json';SI=D/'phase7_3_3_d_support_stage_state_v82.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v93.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_support_review_protocol_frame_v4.json';SCH=C/'phase7_3_3_d_multi_claim_successor_support_review_schema_frame_v4.json';POL=C/'phase7_3_3_d_multi_claim_successor_support_review_policy_frame_v4.json';PROMPT=C/'phase7_3_3_d_multi_claim_successor_support_reviewer_prompt_frame_v4.md';PKT=D/'phase7_3_3_d_multi_claim_successor_support_review_packet_frame_v4.json';FIX=R/'phase7_3_3_d_multi_claim_successor_support_review_fixtures_frame_v4.json';PM=R/'phase7_3_3_d_multi_claim_successor_support_review_prepare_manifest_frame_v4.json';PR=R/'phase7_3_3_d_multi_claim_successor_support_review_prepare_receipt_frame_v4.json';LOG=R/'phase7_3_3_d_multi_claim_successor_support_review_attempts_frame_v4.jsonl';SP=D/'phase7_3_3_d_support_stage_state_v83.json';RP=R/'phase7_3_3_d1_reference_construction_readiness_v94.json'
EXP={TREF:'f19845566adc324d8210a5041c5ecee2338e4bf97a549d320b257c705a6da8d8',DATA:'788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe',CLASS:'191183dfd8b733afd73e1b442341a09a7efbcaef33b747be988ed1fcfeccd4f1',V3NEG:'5b71635fac70ca6377bae173c49a09432382567edcbdbc93f8b44894fbafdc90',SI:'050884b1e2e6a795c488807aaff05a708e9b110e51f6098e348f331aba9c3108',RI:'cc98b683f01a878b53c1cf3d097af14adf42eddba544fc2f619eaabda274a8c0'}
CUR='design_multi_claim_successor_support_review_frame_v4_label_code_representation';EXA='execute_multi_claim_successor_support_reviewer_a_frame_v4';EXB='execute_multi_claim_successor_support_reviewer_b_frame_v4';AGREE='construct_multi_claim_successor_support_agreement_frame_v4';FAIL='design_new_support_review_version_after_v4_negative';MODELS={'a':'gpt-4.1','b':'gemini-2.5-pro'};LABEL=['supported','partially_supported','unsupported','not_assessable']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rel(p):return p.relative_to(ROOT).as_posix()
def packet():
 ev={x['candidate_id']:x for x in load(DATA)['cases']};cases=[]
 for c in load(TREF)['cases']:
  e=ev[c['case_id']];cases.append({'case_id':c['case_id'],'evidence_bundle':copy.deepcopy(e['evidence_bundle']),'valid_evidence_ids':copy.deepcopy(e['valid_evidence_ids']),'evidence_count':len(e['evidence_bundle']),'claim_count':len(c['claims']),'claims':[{k:copy.deepcopy(q[k]) for k in ['reference_claim_id','claim_index','source_excerpt','claim_role','claim_type','claim_origin']} for q in c['claims']]})
 return {'schema_version':4,'packet_id':'phase7.3.3-d-support-review-packet-frame-v4','status':'frozen_evidence_visible_gold_hidden','label_codebook':{str(i):x for i,x in enumerate(LABEL)},'case_count':40,'claim_count':240,'cases':cases,'support_gold_visible':False,'generation_roles_visible':False,'other_reviewer_visible':False,'diagnostic_fields_requested':False}
def prompt():return '''# Independent Support Reviewer — Label Code Representation v4

## System message

Judge Evidence support for the six frozen Claims. Return bare JSON with exactly two keys:
- label_codes: exactly six integers, where 0=supported, 1=partially_supported, 2=unsupported, 3=not_assessable.
- citation_masks: exactly six strings, each exactly six 0/1 characters selecting Evidence positions.

Supported requires whole-Claim conservative entailment. Partially supported means a substantive core is supported but full scope, temporal extent, strength, or qualification is not. Unsupported means required support is absent or contradicted. Not assessable is reserved for Claims that cannot responsibly be evaluated from supplied Evidence. Do not infer causality, universality, permanence, or wider scope from narrower evidence.

Do not output semantic labels, reason, confidence, Claim IDs, rationale, Markdown, or extra keys.

## User message template

Review this frozen case. Return bare JSON only.

{{CASE_JSON}}
'''
def schema():return {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['label_codes','citation_masks'],'properties':{'label_codes':{'type':'array','minItems':6,'maxItems':6,'items':{'type':'integer','minimum':0,'maximum':3}},'citation_masks':{'type':'array','minItems':6,'maxItems':6,'items':{'type':'string','pattern':'^[01]{6}$'}}},'additionalProperties':False}
def protocol():return {'schema_version':4,'protocol_id':'phase7.3.3-d-support-review-protocol-frame-v4','status':'frozen_before_provider_call','predecessor_v3_negative_sha256':sha(V3NEG),'single_intended_change':'fixed 0-3 label codes; citation masks unchanged; diagnostics remain excluded','support_semantics_unchanged':True,'models':MODELS,'case_count':40,'claim_count':240,'first_provider_content_authoritative':True,'same_version_retry_allowed':False}
def policy():return {'schema_version':4,'policy_id':'phase7.3.3-d-support-review-policy-frame-v4','case_isolation':True,'temperature':0,'top_p':1,'max_tokens':1000,'response_format':{'type':'json_object'},'raw_provider_content_stored':False,'transport_failure_resume_same_manifest':True,'invalid_content_authoritative_negative':True}
def parse(case,o):
 if not isinstance(o,dict) or set(o)!={'label_codes','citation_masks'}:raise ValueError('root_invalid')
 ls=o['label_codes'];ms=o['citation_masks'];n=case['claim_count'];e=case['evidence_count']
 if not isinstance(ls,list) or not isinstance(ms,list) or len(ls)!=n or len(ms)!=n:raise ValueError('fixed_length_mismatch')
 if any(type(x) is not int or x<0 or x>3 for x in ls):raise ValueError('label_code_invalid')
 if any(not isinstance(x,str) or len(x)!=e or set(x)-{'0','1'} for x in ms):raise ValueError('citation_mask_invalid')
 return [{'reference_claim_id':q['reference_claim_id'],'support_label':LABEL[ls[i]],'label_code':ls[i],'evidence_citation_mask':ms[i],'cited_evidence_ids':[case['valid_evidence_ids'][j] for j,ch in enumerate(ms[i]) if ch=='1']} for i,q in enumerate(case['claims'])]
def fixtures():
 c=packet()['cases'][0];base={'label_codes':[0,0,2,2,1,1],'citation_masks':['100000','010000','001000','000100','000010','000001']};xs=[]
 for n,o,w in [('valid',base,True),('short',dict(base,label_codes=[0]*5),False),('bad_code',dict(base,label_codes=[9]*6),False),('bad_mask',dict(base,citation_masks=['x']*6),False),('extra',dict(base,extra=1),False)]:
  try:parse(c,o);ok=True
  except ValueError:ok=False
  xs.append({'fixture_id':n,'passed':ok==w})
 return {'schema_version':4,'fixtures_id':'phase7.3.3-d-support-review-fixtures-frame-v4','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def mp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_manifest_frame_v4.json'
def subp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_submission_frame_v4.json'
def resp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_result_frame_v4.json'
def recp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_receipt_frame_v4.json'
def negp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_negative_frame_v4.json'
def cpp(r,c):return R/'phase7_3_3_d_multi_claim_successor_support_reviewer_cases_frame_v4'/r/(c+'.json')
def manifest(r):return {'schema_version':4,'manifest_id':f'phase7.3.3-d-support-reviewer-{r}-manifest-frame-v4','status':'frozen_not_started','reviewer':r,'model_requested':MODELS[r],'temperature':0,'top_p':1,'max_tokens':1000,'response_format':{'type':'json_object'},'credential_env_name':m.CRED,'adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'schema_sha256':sha(SCH),'policy_sha256':sha(POL),'prompt_sha256':sha(PROMPT),'packet_sha256':sha(PKT),'fixtures_sha256':sha(FIX),'case_count':40,'claim_count':240,'first_provider_content_authoritative':True,'same_version_retry_allowed':False}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'v3_negative_preserved':s['multi_claim_successor_support_v3_negative_preserved'] is True,'same_version_retry_false':s['multi_claim_successor_support_v3_same_version_retry_allowed'] is False,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,SCH,POL,PROMPT,PKT,FIX,PM,PR,SP,RP,mp('a'),mp('b')])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def prepare():
 p=preflight()
 if p['status']!='PASS':return p
 m.PRO=PRO;m.SCH=SCH;m.POL=POL;m.PROMPT=PROMPT;m.PKT=PKT;m.FIX=FIX
 m.once(PRO,protocol());m.once(SCH,schema());m.once(POL,policy());m.once(PROMPT,prompt().encode());pkh=m.once(PKT,packet());m.once(FIX,fixtures());ah=m.once(mp('a'),manifest('a'));bh=m.once(mp('b'),manifest('b'));pm={'schema_version':4,'manifest_id':'phase7.3.3-d-support-review-prepare-manifest-frame-v4','status':'frozen_before_any_v4_provider_call','adapter_sha256':sha(SELF),'artifacts':{rel(p):sha(p) for p in [PRO,SCH,POL,PROMPT,PKT,FIX,mp('a'),mp('b')]},'v3_negative_preserved':True,'next_authorized_stage':EXA};pmh=m.once(PM,pm);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_support_review_prepare_manifest_frame_v4_sha256':pmh};u={'status':'multi_claim_successor_support_review_frame_v4_frozen_reviewer_a_authorized','next_authorized_stage':EXA,'multi_claim_successor_support_review_frame_v4_frozen':True,'multi_claim_successor_support_reviewer_a_frame_v4_completed':False,'multi_claim_successor_support_reviewer_b_frame_v4_completed':False,'multi_claim_successor_support_v3_negative_preserved':True,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':83,'state_id':'phase7.3.3-d-support-stage-state-v83'});r.update({'schema_version':94,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v94'});sh=m.once(SP,s);r['artifact_lineage']['support_stage_state_v83_sha256']=sh;rh=m.once(RP,r);rec={'schema_version':4,'receipt_id':'phase7.3.3-d-support-review-prepare-receipt-frame-v4','status':'PASS','prepare_manifest_sha256':pmh,'reviewer_a_manifest_sha256':ah,'reviewer_b_manifest_sha256':bh,'state_sha256':sh,'readiness_sha256':rh,'fixtures':f"{fixtures()['passed_count']}/{fixtures()['fixture_count']}",'next_authorized_stage':EXA};rch=m.once(PR,rec);return {'status':'PASS','packet_sha256':pkh,'prepare_manifest_sha256':pmh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':EXA}
def states(r):return (SP,RP,D/'phase7_3_3_d_support_stage_state_v84.json',R/'phase7_3_3_d1_reference_construction_readiness_v95.json',EXA,EXB) if r=='a' else (D/'phase7_3_3_d_support_stage_state_v84.json',R/'phase7_3_3_d1_reference_construction_readiness_v95.json',D/'phase7_3_3_d_support_stage_state_v85.json',R/'phase7_3_3_d1_reference_construction_readiness_v96.json',EXB,AGREE)
def finish_state(r,nxt,subh,resh):
 si,ri,so,ro,_,_=states(r);s=copy.deepcopy(load(si));rd=copy.deepcopy(load(ri));sv=84 if r=='a' else 85;rv=95 if r=='a' else 96;line={f'multi_claim_successor_support_reviewer_{r}_submission_frame_v4_sha256':subh,f'multi_claim_successor_support_reviewer_{r}_result_frame_v4_sha256':resh};u={'status':'multi_claim_successor_support_reviewer_frame_v4_completed','next_authorized_stage':nxt,f'multi_claim_successor_support_reviewer_{r}_frame_v4_completed':True,'multi_claim_successor_support_review_frame_v4_provider_called':True,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,rd]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':sv,'state_id':f'phase7.3.3-d-support-stage-state-v{sv}'});rd.update({'schema_version':rv,'readiness_id':f'phase7.3.3-d1-reference-construction-readiness-v{rv}'});sh=m.once(so,s);rd['artifact_lineage'][f'support_stage_state_v{sv}_sha256']=sh;rh=m.once(ro,rd);return sh,rh
def call(key,model,system,user):return m.call(key,model,system,user)
def split_prompt():
 x=PROMPT.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];return [q.strip() for q in x.split('\n## User message template\n\n',1)]
def execute(r):
 si,ri,_,_,stage,nxt=states(r)
 if load(si)['next_authorized_stage']!=stage or load(ri)['next_authorized_stage']!=stage:raise RuntimeError('stage_not_authorized')
 man=load(mp(r));mh=sha(mp(r))
 for p,k in [(SELF,'adapter_sha256'),(PRO,'protocol_sha256'),(SCH,'schema_sha256'),(POL,'policy_sha256'),(PROMPT,'prompt_sha256'),(PKT,'packet_sha256'),(FIX,'fixtures_sha256')]:
  if sha(p)!=man[k]:raise RuntimeError('manifest_hash_mismatch:'+rel(p))
 if resp(r).exists():return {'status':'PASS','terminal_outcome':'already_completed','next_authorized_stage':load(resp(r))['next_authorized_stage']}
 if negp(r).exists():return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','next_authorized_stage':FAIL}
 key=os.environ.get(m.CRED)
 if not key:raise RuntimeError('credential_missing')
 system,ut=split_prompt();done=[]
 for case in load(PKT)['cases']:
  cp=cpp(r,case['case_id'])
  if cp.exists():done.append(load(cp));continue
  append_event({'event_type':'support_v4_attempt_started','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'response_received':False,'authoritative_result':False},LOG)
  try:raw=call(key,MODELS[r],system,ut.replace('{{CASE_JSON}}',json.dumps(case,ensure_ascii=False,indent=2)))
  except (urllib.error.URLError,TimeoutError,OSError) as e:append_event({'event_type':'support_v4_transport_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_type':type(e).__name__,'response_received':False,'same_manifest_resume_allowed':True},LOG);return {'status':'TRANSPORT_FAILURE_RESUMABLE','completed_case_count':len(done),'failed_case_id':case['case_id']}
  eh=m.hb(raw);content=None
  try:env=json.loads(raw.decode());got=env.get('model');content=env['choices'][0]['message']['content'];ch=m.hb(content.encode());can=m.canonical(MODELS[r],got);rows=parse(case,json.loads(content))
  except Exception as e:
   ch=m.hb(content.encode()) if isinstance(content,str) else None;append_event({'event_type':'support_v4_contract_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_code':type(e).__name__+':'+str(e),'provider_envelope_sha256':eh,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);nh=m.once(negp(r),{'schema_version':4,'negative_result_id':f'phase7.3.3-d-support-reviewer-{r}-negative-frame-v4','status':'authoritative_negative_result','failed_case_id':case['case_id'],'completed_case_count':len(done),'failure_code':type(e).__name__+':'+str(e),'manifest_sha256':mh,'same_version_retry_allowed':False,'capability_conclusion_authorized':False,'next_authorized_stage':FAIL});return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':nh,'next_authorized_stage':FAIL}
  z={'schema_version':4,'checkpoint_id':f'support-v4-{r}-{case["case_id"]}','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'provider_reported_model':got,'canonical_model_family':can,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'decisions':rows,'boundary_mutation_performed':False,'type_metadata_mutation_performed':False};cph=m.once(cp,z);append_event({'event_type':'support_v4_attempt_completed','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'decision_count':len(rows),'checkpoint_sha256':cph,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);done.append(z)
 cases=[{'case_id':x['case_id'],'decisions':x['decisions']} for x in done];sub={'schema_version':4,'submission_id':f'phase7.3.3-d-support-reviewer-{r}-submission-frame-v4','status':'completed_independent_support_review','reviewer':r,'manifest_sha256':mh,'case_count':40,'decision_count':sum(len(x['decisions']) for x in done),'cases':cases,'diagnostic_fields_present':False,'completed':True};subh=m.once(subp(r),sub);res={'schema_version':4,'result_id':f'phase7.3.3-d-support-reviewer-{r}-result-frame-v4','status':'completed','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':subh,'case_count':40,'decision_count':sub['decision_count'],'next_authorized_stage':nxt};resh=m.once(resp(r),res);sh,rh=finish_state(r,nxt,subh,resh);rec={'schema_version':4,'receipt_id':f'phase7.3.3-d-support-reviewer-{r}-receipt-frame-v4','status':'PASS','submission_sha256':subh,'result_sha256':resh,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt};rch=m.once(recp(r),rec);return {'status':'PASS','reviewer':r,'case_count':40,'decision_count':sub['decision_count'],'submission_sha256':subh,'result_sha256':resh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt}
def verify():
 ps=[PRO,SCH,POL,PROMPT,PKT,FIX,PM,PR,SP,RP,mp('a'),mp('b')];z={'exists:'+rel(p):p.exists() for p in ps};z.update({'packet_replay':PKT.exists() and load(PKT)==packet(),'protocol_replay':PRO.exists() and load(PRO)==protocol(),'fixtures_replay':FIX.exists() and load(FIX)==fixtures(),'manifests_replay':all(mp(r).exists() and load(mp(r))==manifest(r) for r in MODELS)})
 for r in MODELS:
  if resp(r).exists():sub=load(subp(r));z[f'{r}_40_cases']=sub['case_count']==len(sub['cases'])==40;z[f'{r}_240_decisions']=sub['decision_count']==sum(len(x['decisions']) for x in sub['cases'])==240
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'terminal':{r:'completed' if resp(r).exists() else 'negative' if negp(r).exists() else None for r in MODELS},'next_authorized_stage':load(D/'phase7_3_3_d_support_stage_state_v85.json')['next_authorized_stage'] if (D/'phase7_3_3_d_support_stage_state_v85.json').exists() else load(SP)['next_authorized_stage'] if SP.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','prepare','execute-a','execute-b','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else prepare() if a.prepare else execute('a') if getattr(a,'execute_a') else execute('b') if getattr(a,'execute_b') else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE','AUTHORITATIVE_NEGATIVE_RESULT'} else 1
if __name__=='__main__':raise SystemExit(main())
