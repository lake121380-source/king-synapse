#!/usr/bin/env python3
"""Open only the frozen selected v2 content and verify all commitments."""
from __future__ import annotations
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
TPL=C/'phase7_3_3_d_multi_claim_successor_candidate_template_contract_v2.json';WORK=D/'phase7_3_3_d_multi_claim_successor_selected_worklist_v2.json';SMAN=R/'phase7_3_3_d_multi_claim_successor_sampling_manifest_v2.json';SREC=R/'phase7_3_3_d_multi_claim_successor_sampling_freeze_receipt_v2.json';SI=D/'phase7_3_3_d_support_stage_state_v63.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v74.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_content_open_protocol_v2.json';MAN=R/'phase7_3_3_d_multi_claim_successor_content_open_manifest_v2.json';DATA=D/'phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json';REC=R/'phase7_3_3_d_multi_claim_successor_content_open_receipt_v2.json';SO=D/'phase7_3_3_d_support_stage_state_v64.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v75.json'
EXP={TPL:'d4b623248f2956ef01b81a4246d55afc9ec9bc7beba636d7fe137588067a4493',WORK:'32c5512136a28fde8706edb8b2ed761f05eed1f10e0de1b93087d9163daf41b0',SMAN:'7f9082e665234fa5ed93c7bb88848b3c3aca9904beed62a88dcc95e77d9be925',SREC:'daac21903e232e0872a9045d1e38658000dc503a46c9246f68258d8df0dfe33f',SI:'6c3fb6c26fc46002b74e8063e01a249fe8805f66d9519fb4299c2964649cde8d',RI:'c2cad4443f0aa6f36e384fb0006946d2c380aac8e486decb35fcc0a76c631cdd'}
CUR='open_multi_claim_successor_selected_content_v2';NEXT='run_multi_claim_successor_candidate_prescreen_v2'
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
def csha(x):return hb(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rel(p):return p.relative_to(ROOT).as_posix()
def once(p,x):
 b=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise RuntimeError('immutable_artifact_mismatch:'+rel(p))
  return sha(p)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return hb(b)
def generated(n):
 slots=load(TPL)['slot_contracts'];units=[];ev=[]
 for i,s in enumerate(slots,1):units.append(s['candidate_form'].format(n=f'{n:03d}'));ev.append({'evidence_id':f'v2-case-{n:03d}-evidence-{i:03d}','source_index':i-1,'content':s['evidence_form'].format(n=f'{n:03d}')})
 text='\n'.join(units);return {'candidate_id':f'mc-v2-enrichment-{n:03d}','source_family':'identifiability_enrichment_synthetic_v2','candidate_text':text,'candidate_sha256':hb(text.encode()),'component_order_commitment_sha256':csha([hb(x.encode()) for x in units]),'evidence_bundle':ev,'evidence_bundle_sha256':csha(ev),'valid_evidence_ids':[x['evidence_id'] for x in ev]}
def dataset():
 w=load(WORK);cases=[]
 for item in w['items']:
  n=int(item['candidate_id'].rsplit('-',1)[1]);x=generated(n)
  if any(x[k]!=item[k] for k in ['candidate_id','candidate_sha256','evidence_bundle_sha256','component_order_commitment_sha256']):raise RuntimeError('commitment_mismatch:'+item['candidate_id'])
  cases.append({'successor_v2_index':item['successor_v2_index'],**x})
 return {'schema_version':2,'dataset_id':'phase7.3.3-d-multi-claim-successor-selected-dataset-v2','status':'selected_content_open_reference_construction_only','selected_worklist_sha256':sha(WORK),'case_count':len(cases),'cases':cases,'template_generation_roles_present':False,'support_labels_present':False,'old_gold_present':False,'arm_outputs_present':False,'unselected_content_opened':False,'confirmatory_content_opened':False}
def protocol():return {'schema_version':2,'protocol_id':'phase7.3.3-d-multi-claim-successor-content-open-protocol-v2','status':'frozen_before_selected_content_open','scope':'selected_40_only_reference_construction','commitment_replay_required':True,'unselected_content_open_allowed':False,'generation_roles_visible_to_reviewers':False,'support_labels_present':False,'arm_outputs_present':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':NEXT}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);w=load(WORK);z.update({'state_gate':s.get('next_authorized_stage')==CUR,'readiness_gate':r.get('next_authorized_stage')==CUR,'selected_40':w.get('selected_count')==len(w['items'])==40,'content_sealed':s.get('multi_claim_successor_v2_content_opened') is False,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_off':s.get('runtime_integration_authorized') is False,'outputs_absent':all(not p.exists() for p in [PRO,MAN,DATA,REC,SO,RO])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def manifest():return {'schema_version':2,'manifest_id':'phase7.3.3-d-multi-claim-successor-content-open-manifest-v2','status':'frozen_before_selected_content_open','adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'frozen_inputs':{rel(p):h for p,h in EXP.items()},'expected_dataset_sha256':hb((json.dumps(dataset(),ensure_ascii=False,indent=2)+'\n').encode()),'selected_count':40,'unselected_content_opened':False,'provider_calls':0,'next_authorized_stage':CUR}
def prepare():
 p=preflight()
 if p['status']!='PASS':return p
 ph=once(PRO,protocol());mh=once(MAN,manifest());return {'status':'PASS','protocol_sha256':ph,'manifest_sha256':mh,'expected_dataset_sha256':load(MAN)['expected_dataset_sha256']}
def execute():
 if load(MAN)!=manifest():raise RuntimeError('manifest_invalid')
 d=dataset();dh=once(DATA,d);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_content_open_protocol_v2_sha256':sha(PRO),'multi_claim_successor_content_open_manifest_v2_sha256':sha(MAN),'multi_claim_successor_selected_dataset_v2_sha256':dh};u={'status':'multi_claim_successor_v2_selected_content_open_prescreen_authorized','next_authorized_stage':NEXT,'multi_claim_successor_v2_content_opened':True,'multi_claim_successor_v2_selected_content_opened':True,'multi_claim_successor_v2_unselected_content_opened':False,'multi_claim_successor_v2_provider_called':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':64,'state_id':'phase7.3.3-d-support-stage-state-v64'});r.update({'schema_version':75,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v75'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v64_sha256']=sh;rh=once(RO,r);rec={'schema_version':2,'receipt_id':'phase7.3.3-d-multi-claim-successor-content-open-receipt-v2','status':'PASS','manifest_sha256':sha(MAN),'dataset_sha256':dh,'state_sha256':sh,'readiness_sha256':rh,'selected_count':40,'unselected_content_opened':False,'support_labels_present':False,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','dataset_sha256':dh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':NEXT}
def verify():
 ps=[PRO,MAN,DATA,REC,SO,RO];z={'exists:'+rel(p):p.exists() for p in ps}
 if all(p.exists() for p in ps):d=load(DATA);s=load(SO);r=load(RO);z.update({'protocol_replay':load(PRO)==protocol(),'manifest_replay':load(MAN)==manifest(),'dataset_replay':d==dataset(),'dataset_hash_commitment':sha(DATA)==load(MAN)['expected_dataset_sha256'],'case_count_40':d['case_count']==len(d['cases'])==40,'commitments_replay':all(hb(c['candidate_text'].encode())==c['candidate_sha256'] and csha(c['evidence_bundle'])==c['evidence_bundle_sha256'] for c in d['cases']),'no_labels_or_arms':d['support_labels_present'] is False and d['arm_outputs_present'] is False,'unselected_closed':d['unselected_content_opened'] is False,'next_gate':s['next_authorized_stage']==r['next_authorized_stage']==NEXT,'confirmatory_closed':s['confirmatory_dataset_opened'] is False and r['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False and r['runtime_integration_authorized'] is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'hashes':{p.name:sha(p) if p.exists() else None for p in ps},'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','prepare','execute','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else prepare() if a.prepare else execute() if a.execute else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status')=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
