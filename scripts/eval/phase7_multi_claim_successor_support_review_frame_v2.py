#!/usr/bin/env python3
"""Prepare and execute independent Support Reviews for successor frame v2."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,tempfile,urllib.error,urllib.request
from pathlib import Path
from phase7_execution_attempt_log import append_event
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
TREF=D/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_frame_v3.json';TSEAL=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_seal_frame_v3.json';DATA=D/'phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json';SI=D/'phase7_3_3_d_support_stage_state_v78.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v89.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_support_review_protocol_frame_v2.json';SCH=C/'phase7_3_3_d_multi_claim_successor_support_review_schema_frame_v2.json';POL=C/'phase7_3_3_d_multi_claim_successor_support_review_policy_frame_v2.json';PROMPT=C/'phase7_3_3_d_multi_claim_successor_support_reviewer_prompt_frame_v2.md';PKT=D/'phase7_3_3_d_multi_claim_successor_support_review_packet_frame_v2.json';FIX=R/'phase7_3_3_d_multi_claim_successor_support_review_fixtures_frame_v2.json';PM=R/'phase7_3_3_d_multi_claim_successor_support_review_prepare_manifest_frame_v2.json';PR=R/'phase7_3_3_d_multi_claim_successor_support_review_prepare_receipt_frame_v2.json';LOG=R/'phase7_3_3_d_multi_claim_successor_support_review_attempts_frame_v2.jsonl';SP=D/'phase7_3_3_d_support_stage_state_v79.json';RP=R/'phase7_3_3_d1_reference_construction_readiness_v90.json'
EXP={TREF:'f19845566adc324d8210a5041c5ecee2338e4bf97a549d320b257c705a6da8d8',TSEAL:'59954ada0b6454f18011d51516f7c9ee65fdc879671ea762e87c976ab561e0b1',DATA:'788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe',SI:'50b500863173a36fce3608b48ceb9c208eff8dc4517a4c718da958919bdecc09',RI:'36285e58f8ad5e28f486912e813e3650a8d41cea079128462b95ceecbfc0c31d'}
CUR='construct_multi_claim_successor_support_review_packet_frame_v2';EXA='execute_multi_claim_successor_support_reviewer_a_frame_v2';EXB='execute_multi_claim_successor_support_reviewer_b_frame_v2';AGREE='construct_multi_claim_successor_support_agreement_frame_v2';FAIL='design_new_support_review_version_after_authoritative_negative';MODELS={'a':'gpt-4.1','b':'gemini-2.5-pro'};BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';LABEL=['supported','partially_supported','unsupported','not_assessable'];REASON=['direct_evidence_match','conservative_entailment','scope_mismatch','temporal_mismatch','contradiction','insufficient_evidence','causal_overreach','other'];CONF=['low','medium','high']
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
 evidence={x['candidate_id']:x for x in load(DATA)['cases']};cases=[]
 for c in load(TREF)['cases']:
  e=evidence[c['case_id']];cases.append({'case_id':c['case_id'],'evidence_bundle':copy.deepcopy(e['evidence_bundle']),'valid_evidence_ids':copy.deepcopy(e['valid_evidence_ids']),'evidence_count':len(e['evidence_bundle']),'claim_count':len(c['claims']),'claims':[{k:copy.deepcopy(q[k]) for k in ['reference_claim_id','claim_index','source_excerpt','claim_role','claim_type','claim_origin']} for q in c['claims']]})
 return {'schema_version':2,'packet_id':'phase7.3.3-d-multi-claim-successor-support-review-packet-frame-v2','status':'frozen_evidence_visible_gold_hidden','case_count':40,'claim_count':240,'label_codebook':{str(i):x for i,x in enumerate(LABEL)},'reason_codebook':{str(i):x for i,x in enumerate(REASON)},'confidence_codebook':{str(i):x for i,x in enumerate(CONF)},'cases':cases,'support_gold_visible':False,'generation_roles_visible':False,'other_reviewer_visible':False,'arm_outputs_visible':False}
def prompt():return '''# Independent Support Reviewer — Frame v2

## System message

Judge how well the supplied Evidence supports each frozen Atomic Claim. Do not change Claim boundaries, Role, Type, Origin, Candidate text, or Evidence.

Return bare JSON with exactly four keys. Each array must contain exactly six entries aligned to the six Claims in order:
- label_codes: 0=supported, 1=partially_supported, 2=unsupported, 3=not_assessable.
- citation_masks: six strings; each string must contain exactly six characters of 0 or 1, positionally selecting Evidence items.
- reason_codes: 0=direct_evidence_match, 1=conservative_entailment, 2=scope_mismatch, 3=temporal_mismatch, 4=contradiction, 5=insufficient_evidence, 6=causal_overreach, 7=other.
- confidence_codes: 0=low, 1=medium, 2=high.

Supported means Evidence entails the whole Claim under conservative interpretation. Partially supported means Evidence supports a substantive core but not the full scope, time, strength, or qualification. Unsupported means the Claim lacks required support or is contradicted. Not assessable is reserved for a Claim whose truth cannot responsibly be evaluated from the supplied Evidence. Do not treat keyword overlap as entailment. Preserve scope, temporal extent, causality, uncertainty, exceptions, and quantifiers.

Do not output Claim IDs, rationales, Markdown, or extra keys.

## User message template

Review this frozen case. Return bare JSON only.

{{CASE_JSON}}
'''
def schema():return {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['label_codes','citation_masks','reason_codes','confidence_codes'],'properties':{'label_codes':{'type':'array','minItems':6,'maxItems':6,'items':{'type':'integer','minimum':0,'maximum':3}},'citation_masks':{'type':'array','minItems':6,'maxItems':6,'items':{'type':'string','pattern':'^[01]{6}$'}},'reason_codes':{'type':'array','minItems':6,'maxItems':6,'items':{'type':'integer','minimum':0,'maximum':7}},'confidence_codes':{'type':'array','minItems':6,'maxItems':6,'items':{'type':'integer','minimum':0,'maximum':2}}},'additionalProperties':False}
def protocol():return {'schema_version':2,'protocol_id':'phase7.3.3-d-support-review-protocol-frame-v2','status':'frozen_before_provider_call','reference_sha256':sha(TREF),'models':MODELS,'case_count':40,'claim_count':240,'labels':LABEL,'output_representation':'fixed numeric arrays plus positional citation masks','support_gold_visible':False,'generation_roles_visible':False,'other_reviewer_visible':False,'boundary_mutation_allowed':False,'first_provider_content_authoritative':True,'same_version_retry_allowed':False}
def policy():return {'schema_version':2,'policy_id':'phase7.3.3-d-support-review-policy-frame-v2','case_isolation':True,'temperature':0,'top_p':1,'max_tokens':1800,'response_format':{'type':'json_object'},'raw_provider_content_stored':False,'transport_failure_resume_same_manifest':True,'invalid_content_authoritative_negative':True}
def parse(case,o):
 keys={'label_codes','citation_masks','reason_codes','confidence_codes'}
 if not isinstance(o,dict) or set(o)!=keys:raise ValueError('root_invalid')
 n=case['claim_count'];e=case['evidence_count'];ls=o['label_codes'];ms=o['citation_masks'];rs=o['reason_codes'];cs=o['confidence_codes']
 if any(not isinstance(x,list) or len(x)!=n for x in [ls,ms,rs,cs]):raise ValueError('fixed_length_mismatch')
 if any(type(x) is not int or x<0 or x>=len(LABEL) for x in ls) or any(type(x) is not int or x<0 or x>=len(REASON) for x in rs) or any(type(x) is not int or x<0 or x>=len(CONF) for x in cs):raise ValueError('code_invalid')
 if any(not isinstance(x,str) or len(x)!=e or set(x)-{'0','1'} for x in ms):raise ValueError('citation_mask_invalid')
 rows=[]
 for i,q in enumerate(case['claims']):
  cited=[case['valid_evidence_ids'][j] for j,ch in enumerate(ms[i]) if ch=='1'];rows.append({'reference_claim_id':q['reference_claim_id'],'support_label':LABEL[ls[i]],'label_code':ls[i],'evidence_citation_mask':ms[i],'cited_evidence_ids':cited,'reason_code':REASON[rs[i]],'reason_code_index':rs[i],'annotation_confidence':CONF[cs[i]],'confidence_code':cs[i]})
 return rows
def fixtures():
 c=packet()['cases'][0];base={'label_codes':[0,0,2,2,1,1],'citation_masks':['100000','010000','001000','000100','000010','000001'],'reason_codes':[0,0,4,6,2,3],'confidence_codes':[2]*6};xs=[]
 for n,o,w in [('valid',base,True),('short',dict(base,label_codes=[0]*5),False),('bad_mask',dict(base,citation_masks=['x']*6),False),('bad_code',dict(base,label_codes=[9]*6),False),('extra',dict(base,extra=1),False)]:
  try:parse(c,o);ok=True
  except ValueError:ok=False
  xs.append({'fixture_id':n,'passed':ok==w})
 return {'schema_version':2,'fixtures_id':'phase7.3.3-d-support-review-fixtures-frame-v2','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def mp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_manifest_frame_v2.json'
def subp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_submission_frame_v2.json'
def resp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_result_frame_v2.json'
def recp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_receipt_frame_v2.json'
def negp(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_negative_frame_v2.json'
def cpp(r,c):return R/'phase7_3_3_d_multi_claim_successor_support_reviewer_cases_frame_v2'/r/(c+'.json')
def manifest(r):return {'schema_version':2,'manifest_id':f'phase7.3.3-d-support-reviewer-{r}-manifest-frame-v2','status':'frozen_not_started','reviewer':r,'model_requested':MODELS[r],'temperature':0,'top_p':1,'max_tokens':1800,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'schema_sha256':sha(SCH),'policy_sha256':sha(POL),'prompt_sha256':sha(PROMPT),'packet_sha256':sha(PKT),'fixtures_sha256':sha(FIX),'case_count':40,'claim_count':240,'first_provider_content_authoritative':True,'semantic_retry_authorized':False,'raw_provider_content_stored':False}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'type_reference_sealed':s['multi_claim_successor_type_metadata_reference_frame_v3_sealed'] is True,'case_claim_count':load(TREF)['case_count']==40 and load(TREF)['claim_count']==240,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,SCH,POL,PROMPT,PKT,FIX,PM,PR,SP,RP,mp('a'),mp('b')])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def prepare():
 p=preflight()
 if p['status']!='PASS':return p
 once(PRO,protocol());once(SCH,schema());once(POL,policy());once(PROMPT,prompt().encode());pkh=once(PKT,packet());once(FIX,fixtures());ah=once(mp('a'),manifest('a'));bh=once(mp('b'),manifest('b'));pm={'schema_version':2,'manifest_id':'phase7.3.3-d-support-review-prepare-manifest-frame-v2','status':'frozen_before_any_provider_call','adapter_sha256':sha(SELF),'artifacts':{rel(p):sha(p) for p in [PRO,SCH,POL,PROMPT,PKT,FIX,mp('a'),mp('b')]},'both_manifests_frozen_before_a':True,'next_authorized_stage':EXA};pmh=once(PM,pm);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_support_review_prepare_manifest_frame_v2_sha256':pmh};u={'status':'multi_claim_successor_support_review_frame_v2_frozen_reviewer_a_authorized','next_authorized_stage':EXA,'multi_claim_successor_support_review_frame_v2_frozen':True,'multi_claim_successor_support_reviewer_a_frame_v2_completed':False,'multi_claim_successor_support_reviewer_b_frame_v2_completed':False,'multi_claim_successor_support_gold_frame_v2_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':79,'state_id':'phase7.3.3-d-support-stage-state-v79'});r.update({'schema_version':90,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v90'});sh=once(SP,s);r['artifact_lineage']['support_stage_state_v79_sha256']=sh;rh=once(RP,r);rec={'schema_version':2,'receipt_id':'phase7.3.3-d-support-review-prepare-receipt-frame-v2','status':'PASS','prepare_manifest_sha256':pmh,'reviewer_a_manifest_sha256':ah,'reviewer_b_manifest_sha256':bh,'state_sha256':sh,'readiness_sha256':rh,'fixtures':f"{fixtures()['passed_count']}/{fixtures()['fixture_count']}",'next_authorized_stage':EXA};rch=once(PR,rec);return {'status':'PASS','packet_sha256':pkh,'prepare_manifest_sha256':pmh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':EXA}
def call(key,model,system,user):
 payload={'model':model,'temperature':0,'top_p':1,'max_tokens':1800,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=600) as resp:return resp.read()
def split_prompt():
 x=PROMPT.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];return [q.strip() for q in x.split('\n## User message template\n\n',1)]
def canonical(req,got):
 if not isinstance(got,str):raise ValueError('model_missing')
 t=got.lower().rsplit('/',1)[-1];q=req.lower()
 if t==q or t.startswith(q+'-'):return req
 raise ValueError('model_family_mismatch')
def states(r):return (SP,RP,D/'phase7_3_3_d_support_stage_state_v80.json',R/'phase7_3_3_d1_reference_construction_readiness_v91.json',EXA,EXB) if r=='a' else (D/'phase7_3_3_d_support_stage_state_v80.json',R/'phase7_3_3_d1_reference_construction_readiness_v91.json',D/'phase7_3_3_d_support_stage_state_v81.json',R/'phase7_3_3_d1_reference_construction_readiness_v92.json',EXB,AGREE)
def finalize_state(r,nxt,subh,resh):
 si,ri,so,ro,_,_=states(r);s=copy.deepcopy(load(si));rd=copy.deepcopy(load(ri));sv=80 if r=='a' else 81;rv=91 if r=='a' else 92;line={f'multi_claim_successor_support_reviewer_{r}_submission_frame_v2_sha256':subh,f'multi_claim_successor_support_reviewer_{r}_result_frame_v2_sha256':resh};u={'status':'multi_claim_successor_support_reviewer_frame_v2_completed','next_authorized_stage':nxt,f'multi_claim_successor_support_reviewer_{r}_frame_v2_completed':True,'multi_claim_successor_support_review_frame_v2_provider_called':True,'multi_claim_successor_support_gold_frame_v2_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
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
  append_event({'event_type':'support_review_attempt_started','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'response_received':False,'authoritative_result':False},LOG)
  try:raw=call(key,MODELS[r],system,ut.replace('{{CASE_JSON}}',json.dumps(case,ensure_ascii=False,indent=2)))
  except (urllib.error.URLError,TimeoutError,OSError) as e:append_event({'event_type':'support_review_transport_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_type':type(e).__name__,'response_received':False,'same_manifest_resume_allowed':True},LOG);return {'status':'TRANSPORT_FAILURE_RESUMABLE','completed_case_count':len(done),'failed_case_id':case['case_id']}
  eh=hb(raw);content=None
  try:env=json.loads(raw.decode());got=env.get('model');content=env['choices'][0]['message']['content'];ch=hb(content.encode());can=canonical(MODELS[r],got);rows=parse(case,json.loads(content))
  except Exception as e:
   ch=hb(content.encode()) if isinstance(content,str) else None;append_event({'event_type':'support_review_contract_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_code':type(e).__name__+':'+str(e),'provider_envelope_sha256':eh,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);nh=once(negp(r),{'schema_version':2,'negative_result_id':f'phase7.3.3-d-support-reviewer-{r}-negative-frame-v2','status':'authoritative_negative_result','failed_case_id':case['case_id'],'completed_case_count':len(done),'failure_code':type(e).__name__+':'+str(e),'manifest_sha256':mh,'same_version_retry_allowed':False,'capability_conclusion_authorized':False,'next_authorized_stage':FAIL});return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':nh,'next_authorized_stage':FAIL}
  z={'schema_version':2,'checkpoint_id':f'support-review-{r}-{case["case_id"]}','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'provider_reported_model':got,'canonical_model_family':can,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'decisions':rows,'boundary_mutation_performed':False,'type_metadata_mutation_performed':False};cph=once(cp,z);append_event({'event_type':'support_review_attempt_completed','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'decision_count':len(rows),'checkpoint_sha256':cph,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);done.append(z)
 cases=[{'case_id':x['case_id'],'decisions':x['decisions']} for x in done];sub={'schema_version':2,'submission_id':f'phase7.3.3-d-support-reviewer-{r}-submission-frame-v2','status':'completed_independent_support_review','reviewer':r,'manifest_sha256':mh,'case_count':40,'decision_count':sum(len(x['decisions']) for x in done),'cases':cases,'boundary_mutation_performed':False,'type_metadata_mutation_performed':False,'completed':True};subh=once(subp(r),sub);res={'schema_version':2,'result_id':f'phase7.3.3-d-support-reviewer-{r}-result-frame-v2','status':'completed','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':subh,'case_count':40,'decision_count':sub['decision_count'],'next_authorized_stage':nxt};resh=once(resp(r),res);sh,rh=finalize_state(r,nxt,subh,resh);rec={'schema_version':2,'receipt_id':f'phase7.3.3-d-support-reviewer-{r}-receipt-frame-v2','status':'PASS','submission_sha256':subh,'result_sha256':resh,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt};rch=once(recp(r),rec);return {'status':'PASS','reviewer':r,'case_count':40,'decision_count':sub['decision_count'],'submission_sha256':subh,'result_sha256':resh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt}
def verify():
 ps=[PRO,SCH,POL,PROMPT,PKT,FIX,PM,PR,SP,RP,mp('a'),mp('b')];z={'exists:'+rel(p):p.exists() for p in ps};z.update({'packet_replay':PKT.exists() and load(PKT)==packet(),'protocol_replay':PRO.exists() and load(PRO)==protocol(),'fixtures_replay':FIX.exists() and load(FIX)==fixtures(),'manifests_replay':all(mp(r).exists() and load(mp(r))==manifest(r) for r in MODELS)})
 for r in MODELS:
  if resp(r).exists():sub=load(subp(r));z[f'{r}_40_cases']=sub['case_count']==len(sub['cases'])==40;z[f'{r}_240_decisions']=sub['decision_count']==sum(len(x['decisions']) for x in sub['cases'])==240;z[f'{r}_no_mutation']=sub['boundary_mutation_performed'] is False and sub['type_metadata_mutation_performed'] is False
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'terminal':{r:'completed' if resp(r).exists() else 'negative' if negp(r).exists() else None for r in MODELS},'next_authorized_stage':load(D/'phase7_3_3_d_support_stage_state_v81.json')['next_authorized_stage'] if (D/'phase7_3_3_d_support_stage_state_v81.json').exists() else load(SP)['next_authorized_stage'] if SP.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','prepare','execute-a','execute-b','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else prepare() if a.prepare else execute('a') if getattr(a,'execute_a') else execute('b') if getattr(a,'execute_b') else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE','AUTHORITATIVE_NEGATIVE_RESULT'} else 1
if __name__=='__main__':raise SystemExit(main())
