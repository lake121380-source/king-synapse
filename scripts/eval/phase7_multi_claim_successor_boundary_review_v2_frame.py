#!/usr/bin/env python3
"""Prepare and execute independent operation-only Boundary Review A/B for frame v2."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,re,tempfile,urllib.error,urllib.request
from pathlib import Path
from phase7_execution_attempt_log import append_event,read_entries
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
DATA=D/'phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json';PMAN=R/'phase7_3_3_d_multi_claim_successor_candidate_prescreen_manifest_v2.json';PREP=R/'phase7_3_3_d_multi_claim_successor_candidate_prescreen_report_v2.json';PREC=R/'phase7_3_3_d_multi_claim_successor_candidate_prescreen_receipt_v2.json';SI=D/'phase7_3_3_d_support_stage_state_v65.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v76.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_boundary_review_protocol_frame_v2.json';SCH=C/'phase7_3_3_d_multi_claim_successor_boundary_review_schema_frame_v2.json';POL=C/'phase7_3_3_d_multi_claim_successor_boundary_review_policy_frame_v2.json';PROMPT=C/'phase7_3_3_d_multi_claim_successor_boundary_reviewer_prompt_frame_v2.md';WORK=D/'phase7_3_3_d_multi_claim_successor_boundary_blind_worklist_v2.json';FIX=R/'phase7_3_3_d_multi_claim_successor_boundary_review_fixtures_frame_v2.json';PM=R/'phase7_3_3_d_multi_claim_successor_boundary_review_prepare_manifest_frame_v2.json';PR=R/'phase7_3_3_d_multi_claim_successor_boundary_review_prepare_receipt_frame_v2.json';LOG=R/'phase7_3_3_d_multi_claim_successor_boundary_review_attempts_frame_v2.jsonl';SP=D/'phase7_3_3_d_support_stage_state_v66.json';RP=R/'phase7_3_3_d1_reference_construction_readiness_v77.json'
EXP={DATA:'788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe',PMAN:'82b39e9d6ae38968c8c91ee717137df2b1b69b5e49f51ae7dff123d81549b771',PREP:'57953feb2b367a1fc038e7a47cae62a9cf29462737041b4e9cd0f9d659fa38a6',PREC:'08140c1a678a71c821a379d9aab92cd5e559e6524f4b2b1b87c8d9c349228b97',SI:'44fec5a8aeedf1646a94b7404f5ff53e9467b828e5e529dfd7e40ce2e61e2d5f',RI:'e4798a851af8fe075d7f8287d373809deccbf7551633d578a7640a324f69304e'}
CUR='construct_multi_claim_successor_independent_boundary_review_a_v2';EXA='execute_multi_claim_successor_independent_boundary_review_a_v2';EXB='execute_multi_claim_successor_independent_boundary_review_b_v2';AGREE='construct_multi_claim_successor_boundary_agreement_frame_v2';FAIL='design_new_boundary_review_version_after_authoritative_negative';MODELS={'a':'gpt-4.1','b':'gemini-2.5-pro'};BASE='https://api.gpt.ge/v1';CRED='PHASE7_ATOMIC_JUDGE_API_KEY';MAXTOK=2500
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
def units(text):
 out=[];pos=0
 for i,x in enumerate(text.split('\n'),1):start=pos;end=start+len(x);out.append({'unit_id':f'unit-{i:03d}','unit_index':i-1,'start':start,'end':end,'text':x,'text_sha256':hb(x.encode())});pos=end+1
 return out
def worklist():
 cases=[]
 for c in load(DATA)['cases']:
  us=units(c['candidate_text']);cases.append({'successor_v2_index':c['successor_v2_index'],'case_id':c['candidate_id'],'candidate_text':c['candidate_text'],'candidate_sha256':c['candidate_sha256'],'offset_unit':'zero_based_unicode_code_point_end_exclusive','source_units':us,'valid_unit_ids':[x['unit_id'] for x in us]})
 return {'schema_version':2,'worklist_id':'phase7.3.3-d-multi-claim-successor-boundary-blind-worklist-v2','status':'frozen_blind_boundary_only','case_count':len(cases),'cases':cases,'evidence_present':False,'generation_roles_present':False,'support_labels_present':False,'old_gold_present':False,'other_reviewer_output_present':False,'arm_outputs_present':False,'confirmatory_content_present':False}
def prompt():return '''# Independent Atomic Claim Boundary Reviewer — Frame v2

## System message

Perform structural Atomic Claim segmentation only. Do not judge support, correctness, Claim Type, metadata, materiality, citations, or evidence. Identify every independently truth-evaluable assertion and do not overlap Claims.

Return one bare compact JSON object with exactly one root field named operations. Each operation must be one of:
{"kind":"reuse_unit","unit_id":"unit-001"}
{"kind":"merge_units","unit_ids":["unit-001","unit-002"]}
{"kind":"slice_unit","unit_id":"unit-001","relative_start":0,"relative_end":5}
{"kind":"new_span","start":0,"end":5}

Use reuse_unit whenever a complete supplied unit is one independently truth-evaluable Claim. merge_units requires consecutive units that jointly form only one assertion. slice_unit must be a proper nonempty subspan. new_span is last resort. Offsets are zero-based Unicode code points, end exclusive. Do not output rationale, confidence, excerpts, labels, types, roles, citations, or Markdown.

## User message template

Segment this frozen Candidate. Return operation-only JSON.

{{CASE_JSON}}
'''
def schema():
 variants=[]
 for kind,props in [('reuse_unit',{'unit_id':{'type':'string'}}),('merge_units',{'unit_ids':{'type':'array','minItems':2,'uniqueItems':True,'items':{'type':'string'}}}),('slice_unit',{'unit_id':{'type':'string'},'relative_start':{'type':'integer','minimum':0},'relative_end':{'type':'integer','minimum':1}}),('new_span',{'start':{'type':'integer','minimum':0},'end':{'type':'integer','minimum':1}})]:variants.append({'type':'object','required':['kind',*props],'properties':{'kind':{'const':kind},**props},'additionalProperties':False})
 return {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['operations'],'properties':{'operations':{'type':'array','minItems':1,'items':{'oneOf':variants}}},'additionalProperties':False}
def protocol():return {'schema_version':2,'protocol_id':'phase7.3.3-d-multi-claim-successor-boundary-review-protocol-frame-v2','status':'frozen_before_provider_call','object_of_study':'atomic_claim_boundary_segmentation','representation':'compact_operation_only','reviewers':MODELS,'case_count':40,'evidence_visible':False,'generation_roles_visible':False,'other_reviewer_visible':False,'support_labels_visible':False,'first_provider_content_authoritative':True,'same_version_semantic_retry_allowed':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def policy():return {'schema_version':2,'policy_id':'phase7.3.3-d-boundary-review-policy-frame-v2','first_provider_content_authoritative':True,'invalid_content_authoritative_negative':True,'transport_failure_resume_same_manifest':True,'case_isolation':True,'temperature':0,'top_p':1,'max_tokens':MAXTOK,'response_format':{'type':'json_object'},'raw_provider_content_stored':False}
def resolve(case,op):
 us={x['unit_id']:x for x in case['source_units']};kind=op.get('kind') if isinstance(op,dict) else None
 if kind=='reuse_unit' and set(op)=={'kind','unit_id'}:
  if op['unit_id'] not in us:raise ValueError('unknown_unit')
  u=us[op['unit_id']]
  return u['start'],u['end'],[u['unit_id']],kind
 if kind=='merge_units' and set(op)=={'kind','unit_ids'}:
  ids=op['unit_ids'];
  if not isinstance(ids,list) or len(ids)<2 or any(x not in us for x in ids):raise ValueError('merge_ids_invalid')
  inds=[us[x]['unit_index'] for x in ids]
  if inds!=list(range(inds[0],inds[0]+len(inds))):raise ValueError('merge_not_consecutive')
  return us[ids[0]]['start'],us[ids[-1]]['end'],ids,kind
 if kind=='slice_unit' and set(op)=={'kind','unit_id','relative_start','relative_end'}:
  if op['unit_id'] not in us:raise ValueError('unknown_unit')
  u=us[op['unit_id']];a=op['relative_start'];b=op['relative_end'];n=u['end']-u['start']
  if not isinstance(a,int) or not isinstance(b,int) or a<0 or b<=a or b>n or (a==0 and b==n):raise ValueError('slice_invalid')
  return u['start']+a,u['start']+b,[u['unit_id']],kind
 if kind=='new_span' and set(op)=={'kind','start','end'}:
  a=op['start'];b=op['end']
  if not isinstance(a,int) or not isinstance(b,int) or a<0 or b<=a or b>len(case['candidate_text']):raise ValueError('new_span_invalid')
  return a,b,[],kind
 raise ValueError('operation_schema_invalid')
def normalize(case,o,r):
 if not isinstance(o,dict) or set(o)!={'operations'} or not isinstance(o['operations'],list) or not o['operations']:raise ValueError('root_invalid')
 rows=[]
 for op in o['operations']:
  a,b,ids,kind=resolve(case,op);rows.append({'case_id':case['case_id'],'source_span':{'start':a,'end':b},'source_excerpt':case['candidate_text'][a:b],'source_unit_ids':ids,'boundary_operation_kind':kind,'reviewer':r})
 rows.sort(key=lambda x:(x['source_span']['start'],x['source_span']['end']));prev=-1;seen=set()
 for i,x in enumerate(rows,1):
  sp=(x['source_span']['start'],x['source_span']['end'])
  if sp in seen:raise ValueError('duplicate_span')
  if sp[0]<prev:raise ValueError('overlapping_spans')
  seen.add(sp);prev=sp[1];x['claim_id']=f"{case['case_id']}-{r}-claim-{i:03d}"
 return rows
def fixtures():
 c=worklist()['cases'][0];xs=[]
 for name,o in [('reuse',{'operations':[{'kind':'reuse_unit','unit_id':'unit-001'}]}),('merge',{'operations':[{'kind':'merge_units','unit_ids':['unit-001','unit-002']}]}),('slice',{'operations':[{'kind':'slice_unit','unit_id':'unit-001','relative_start':1,'relative_end':5}]}),('new',{'operations':[{'kind':'new_span','start':0,'end':5}]})]:
  try:normalize(c,o,'fixture');ok=True
  except ValueError:ok=False
  xs.append({'fixture_id':name,'passed':ok})
 for name,o in [('empty',{'operations':[]}),('unknown',{'operations':[{'kind':'reuse_unit','unit_id':'bad'}]}),('overlap',{'operations':[{'kind':'reuse_unit','unit_id':'unit-001'},{'kind':'new_span','start':1,'end':9}]})]:
  try:normalize(c,o,'fixture');ok=False
  except ValueError:ok=True
  xs.append({'fixture_id':'reject_'+name,'passed':ok})
 return {'schema_version':2,'fixtures_id':'phase7.3.3-d-boundary-review-fixtures-frame-v2','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def manifest_path(r):return R/f'phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_manifest_frame_v2.json'
def submission_path(r):return R/f'phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_submission_frame_v2.json'
def result_path(r):return R/f'phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_result_frame_v2.json'
def receipt_path(r):return R/f'phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_receipt_frame_v2.json'
def negative_path(r):return R/f'phase7_3_3_d_multi_claim_successor_boundary_reviewer_{r}_negative_frame_v2.json'
def checkpoint(r,c):return R/'phase7_3_3_d_multi_claim_successor_boundary_reviewer_cases_frame_v2'/r/(c+'.json')
def manifest(r):return {'schema_version':2,'manifest_id':f'phase7.3.3-d-boundary-reviewer-{r}-manifest-frame-v2','status':'frozen_not_started','reviewer':r,'provider':'api.gpt.ge','model_requested':MODELS[r],'temperature':0,'top_p':1,'max_tokens':MAXTOK,'response_format':{'type':'json_object'},'credential_env_name':CRED,'adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'schema_sha256':sha(SCH),'policy_sha256':sha(POL),'prompt_sha256':sha(PROMPT),'worklist_sha256':sha(WORK),'fixtures_sha256':sha(FIX),'case_count':40,'case_isolation':True,'first_provider_content_authoritative':True,'semantic_retry_authorized':False,'raw_provider_content_stored':False,'evidence_visible':False,'other_reviewer_output_visible':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):
  s=load(SI);r=load(RI)
  partial_ok=(not WORK.exists() or load(WORK)==worklist()) and (not PRO.exists() or load(PRO)==protocol()) and (not SCH.exists() or load(SCH)==schema()) and (not POL.exists() or load(POL)==policy()) and (not PROMPT.exists() or PROMPT.read_text(encoding='utf-8-sig')==prompt())
  z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'prescreen_pass':load(PREP)['status']=='PASS','case_count_40':load(DATA)['case_count']==40,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'failed_prepare_prefix_replayable':partial_ok,'terminal_prepare_outputs_absent':all(not p.exists() for p in [FIX,PM,PR,SP,RP,manifest_path('a'),manifest_path('b')])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def prepare():
 p=preflight()
 if p['status']!='PASS':return p
 wh=once(WORK,worklist());ph=once(PRO,protocol());sch=once(SCH,schema());pol=once(POL,policy());prh=once(PROMPT,prompt().encode());fh=once(FIX,fixtures());ah=once(manifest_path('a'),manifest('a'));bh=once(manifest_path('b'),manifest('b'));pm={'schema_version':2,'manifest_id':'phase7.3.3-d-boundary-review-prepare-manifest-frame-v2','status':'frozen_before_any_provider_call','adapter_sha256':sha(SELF),'artifact_sha256':{rel(p):sha(p) for p in [PRO,SCH,POL,PROMPT,WORK,FIX,manifest_path('a'),manifest_path('b')]},'both_reviewer_manifests_frozen_before_a':True,'provider_called':False,'next_authorized_stage':EXA};pmh=once(PM,pm)
 s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_boundary_review_prepare_manifest_frame_v2_sha256':pmh,'multi_claim_successor_boundary_blind_worklist_v2_sha256':wh};u={'status':'multi_claim_successor_boundary_review_frame_v2_frozen_reviewer_a_authorized','next_authorized_stage':EXA,'multi_claim_successor_boundary_review_frame_v2_frozen':True,'multi_claim_successor_boundary_reviewer_a_frame_v2_completed':False,'multi_claim_successor_boundary_reviewer_b_frame_v2_completed':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':66,'state_id':'phase7.3.3-d-support-stage-state-v66'});r.update({'schema_version':77,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v77'});sh=once(SP,s);r['artifact_lineage']['support_stage_state_v66_sha256']=sh;rh=once(RP,r);rec={'schema_version':2,'receipt_id':'phase7.3.3-d-boundary-review-prepare-receipt-frame-v2','status':'PASS','prepare_manifest_sha256':pmh,'reviewer_a_manifest_sha256':ah,'reviewer_b_manifest_sha256':bh,'state_sha256':sh,'readiness_sha256':rh,'fixtures':f"{fixtures()['passed_count']}/{fixtures()['fixture_count']}",'provider_called':False,'next_authorized_stage':EXA};rch=once(PR,rec);return {'status':'PASS','worklist_sha256':wh,'prepare_manifest_sha256':pmh,'reviewer_a_manifest_sha256':ah,'reviewer_b_manifest_sha256':bh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':EXA}
def call(key,model,system,user):
 payload={'model':model,'temperature':0,'top_p':1,'max_tokens':MAXTOK,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=600) as resp:return resp.read()
def canonical(requested,reported):
 if not isinstance(reported,str):raise ValueError('model_missing')
 q=requested.lower();t=reported.lower().rsplit('/',1)[-1]
 if t==q or t.startswith(q+'-'):return requested
 raise ValueError('model_family_mismatch')
def split_prompt():
 x=load_text=PROMPT.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];return [q.strip() for q in x.split('\n## User message template\n\n',1)]
def state_paths(r):return (SP,RP,D/'phase7_3_3_d_support_stage_state_v67.json',R/'phase7_3_3_d1_reference_construction_readiness_v78.json',EXA,EXB) if r=='a' else (D/'phase7_3_3_d_support_stage_state_v67.json',R/'phase7_3_3_d1_reference_construction_readiness_v78.json',D/'phase7_3_3_d_support_stage_state_v68.json',R/'phase7_3_3_d1_reference_construction_readiness_v79.json',EXB,AGREE)
def finalize_state(r,status,nxt,subh,resh):
 si,ri,so,ro,_,_=state_paths(r);s=copy.deepcopy(load(si));rd=copy.deepcopy(load(ri));sv=67 if r=='a' else 68;rv=78 if r=='a' else 79;line={f'multi_claim_successor_boundary_reviewer_{r}_submission_frame_v2_sha256':subh,f'multi_claim_successor_boundary_reviewer_{r}_result_frame_v2_sha256':resh};u={'status':status,'next_authorized_stage':nxt,f'multi_claim_successor_boundary_reviewer_{r}_frame_v2_completed':status.endswith('_completed'),'multi_claim_successor_boundary_review_frame_v2_provider_called':True,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,rd]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':sv,'state_id':f'phase7.3.3-d-support-stage-state-v{sv}'});rd.update({'schema_version':rv,'readiness_id':f'phase7.3.3-d1-reference-construction-readiness-v{rv}'});sh=once(so,s);rd['artifact_lineage'][f'support_stage_state_v{sv}_sha256']=sh;rh=once(ro,rd);return sh,rh
def execute(r):
 si,ri,_,_,stage,nxt=state_paths(r)
 if load(si)['next_authorized_stage']!=stage or load(ri)['next_authorized_stage']!=stage:raise RuntimeError('stage_not_authorized')
 man=load(manifest_path(r));mh=sha(manifest_path(r))
 for p,k in [(SELF,'adapter_sha256'),(PRO,'protocol_sha256'),(SCH,'schema_sha256'),(POL,'policy_sha256'),(PROMPT,'prompt_sha256'),(WORK,'worklist_sha256'),(FIX,'fixtures_sha256')]:
  if sha(p)!=man[k]:raise RuntimeError('manifest_hash_mismatch:'+rel(p))
 if result_path(r).exists():return {'status':'PASS','terminal_outcome':'already_completed','result_sha256':sha(result_path(r)),'next_authorized_stage':load(result_path(r))['next_authorized_stage']}
 if negative_path(r).exists():return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':sha(negative_path(r)),'next_authorized_stage':FAIL}
 key=os.environ.get(CRED)
 if not key:raise RuntimeError('credential_missing:'+CRED)
 system,ut=split_prompt();done=[]
 for case in load(WORK)['cases']:
  cp=checkpoint(r,case['case_id'])
  if cp.exists():done.append(load(cp));continue
  append_event({'event_type':'boundary_attempt_started','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'response_received':False,'authoritative_result':False},LOG)
  try:raw=call(key,MODELS[r],system,ut.replace('{{CASE_JSON}}',json.dumps(case,ensure_ascii=False,indent=2)))
  except (urllib.error.URLError,TimeoutError,OSError) as e:append_event({'event_type':'boundary_transport_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_type':type(e).__name__,'response_received':False,'same_manifest_resume_allowed':True},LOG);return {'status':'TRANSPORT_FAILURE_RESUMABLE','completed_case_count':len(done),'failed_case_id':case['case_id']}
  eh=hb(raw)
  try:
   env=json.loads(raw.decode());reported=env.get('model');content=env['choices'][0]['message']['content'];ch=hb(content.encode());can=canonical(MODELS[r],reported);claims=normalize(case,json.loads(content),r)
  except Exception as e:
   ch=hb(content.encode()) if 'content' in locals() and isinstance(content,str) else None;append_event({'event_type':'boundary_contract_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'failure_code':type(e).__name__+':'+str(e),'provider_envelope_sha256':eh,'provider_content_sha256':ch,'response_received':True,'authoritative_result':True},LOG);neg={'schema_version':2,'negative_result_id':f'phase7.3.3-d-boundary-reviewer-{r}-negative-frame-v2','status':'authoritative_negative_result','failed_case_id':case['case_id'],'completed_case_count':len(done),'failure_code':type(e).__name__+':'+str(e),'manifest_sha256':mh,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'same_version_retry_allowed':False,'capability_conclusion_authorized':False,'next_authorized_stage':FAIL};nh=once(negative_path(r),neg);return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','negative_result_sha256':nh,'next_authorized_stage':FAIL}
  z={'schema_version':2,'checkpoint_id':f'boundary-{r}-{case["case_id"]}','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'provider_reported_model':reported,'canonical_model_family':can,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'claims':claims,'raw_provider_content_stored':False};cph=once(cp,z);append_event({'event_type':'boundary_attempt_completed','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'claim_count':len(claims),'provider_content_sha256':ch,'checkpoint_sha256':cph,'response_received':True,'authoritative_result':True},LOG);done.append(z)
 cases=[{'case_id':x['case_id'],'claims':x['claims']} for x in done];count=sum(len(x['claims']) for x in done);sub={'schema_version':2,'submission_id':f'phase7.3.3-d-boundary-reviewer-{r}-submission-frame-v2','status':'completed_independent_boundary_review','reviewer':r,'manifest_sha256':mh,'case_count':40,'claim_count':count,'cases':cases,'evidence_visible':False,'other_reviewer_visible':False,'support_labels_present':False,'completed':True};subh=once(submission_path(r),sub);res={'schema_version':2,'result_id':f'phase7.3.3-d-boundary-reviewer-{r}-result-frame-v2','status':'completed','manifest_sha256':mh,'attempt_log_sha256':sha(LOG),'submission_sha256':subh,'case_count':40,'claim_count':count,'next_authorized_stage':nxt};resh=once(result_path(r),res);sh,rh=finalize_state(r,'multi_claim_successor_boundary_reviewer_frame_v2_completed',nxt,subh,resh);rec={'schema_version':2,'receipt_id':f'phase7.3.3-d-boundary-reviewer-{r}-receipt-frame-v2','status':'PASS','manifest_sha256':mh,'submission_sha256':subh,'result_sha256':resh,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt};rch=once(receipt_path(r),rec);return {'status':'PASS','reviewer':r,'case_count':40,'claim_count':count,'submission_sha256':subh,'result_sha256':resh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt}
def verify():
 ps=[PRO,SCH,POL,PROMPT,WORK,FIX,PM,PR,SP,RP,manifest_path('a'),manifest_path('b')];z={'exists:'+rel(p):p.exists() for p in ps}
 z.update({'worklist_replay':WORK.exists() and load(WORK)==worklist(),'protocol_replay':PRO.exists() and load(PRO)==protocol(),'schema_replay':SCH.exists() and load(SCH)==schema(),'fixtures_replay':FIX.exists() and load(FIX)==fixtures(),'manifests_replay':all(manifest_path(r).exists() and load(manifest_path(r))==manifest(r) for r in MODELS)})
 for r in MODELS:
  if result_path(r).exists():sub=load(submission_path(r));z[f'{r}_40_cases']=sub['case_count']==len(sub['cases'])==40;z[f'{r}_claims_nonempty']=all(x['claims'] for x in sub['cases']);z[f'{r}_result_lineage']=load(result_path(r))['submission_sha256']==sha(submission_path(r))
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'terminal':{r:'completed' if result_path(r).exists() else 'negative' if negative_path(r).exists() else None for r in MODELS},'next_authorized_stage':load(D/'phase7_3_3_d_support_stage_state_v68.json')['next_authorized_stage'] if (D/'phase7_3_3_d_support_stage_state_v68.json').exists() else load(SP)['next_authorized_stage'] if SP.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','prepare','execute-a','execute-b','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else prepare() if a.prepare else execute('a') if getattr(a,'execute_a') else execute('b') if getattr(a,'execute_b') else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status') in {'PASS','TRANSPORT_FAILURE_RESUMABLE','AUTHORITATIVE_NEGATIVE_RESULT'} else 1
if __name__=='__main__':raise SystemExit(main())
