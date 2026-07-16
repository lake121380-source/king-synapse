#!/usr/bin/env python3
"""Construct and freeze the content-sealed Multi-claim Successor Sampling Frame v2."""
from __future__ import annotations
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
DES=C/'phase7_3_3_d_multi_claim_successor_sampling_frame_v2_design_protocol.json';POL=C/'phase7_3_3_d_multi_claim_successor_sampling_policy_v2.json';TPL=C/'phase7_3_3_d_multi_claim_successor_candidate_template_contract_v2.json';DMAN=R/'phase7_3_3_d_multi_claim_successor_sampling_frame_v2_design_manifest.json';SI=D/'phase7_3_3_d_support_stage_state_v62.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v73.json';V1=D/'phase7_3_3_d_multi_claim_successor_selected_dataset_v1.json';PRED=D/'phase7_3_3_d_independent_pilot_selected_dataset_v1.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_sampling_frame_protocol_v2.json';INV=R/'phase7_3_3_d_multi_claim_successor_source_inventory_v2.json';OVER=R/'phase7_3_3_d_multi_claim_successor_overlap_audit_v2.json';WORK=D/'phase7_3_3_d_multi_claim_successor_selected_worklist_v2.json';FIX=R/'phase7_3_3_d_multi_claim_successor_sampling_contract_fixtures_v2.json';MAN=R/'phase7_3_3_d_multi_claim_successor_sampling_manifest_v2.json';OUT=R/'phase7_3_3_d_multi_claim_successor_sampling_freeze_outcome_v2.json';REC=R/'phase7_3_3_d_multi_claim_successor_sampling_freeze_receipt_v2.json';SO=D/'phase7_3_3_d_support_stage_state_v63.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v74.json'
EXP={DES:'57accb3fffcd30f65cfaa05222a90c01606c2043a9a20d3d5cdac7fdcc57ed71',POL:'be5ab22c809be73b43d7e10bc2c85cca89ff9b295ed570d693b8e2159e3f21dc',TPL:'d4b623248f2956ef01b81a4246d55afc9ec9bc7beba636d7fe137588067a4493',DMAN:'5fb645b28be00cdd389335d0eff5ad0db26c0f0dca3d5ec10e548c6fe48bdcb8',SI:'ebe10307e5ea7524cb0c53612fc5cde67c3065a426653a2bb82aec715d5ee168',RI:'39f679fd7761165f88639ab60a9dcc41c1d62de3a0b6426d878aad13ea3ee085',V1:'858c60201f25a97e9787e96ef0554c05b3bf36b80c76f86406b520ecb203d3ca',PRED:'f278c5a27f9c241e306cc1200e3224deb3b3ea4bdff71b6490525218fd1eab62'}
CUR='construct_multi_claim_successor_sampling_frame_v2';NEXT='open_multi_claim_successor_selected_content_v2';SEED='733052'
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
 slots=load(TPL)['slot_contracts'];units=[];evidence=[]
 for i,s in enumerate(slots,1):
  units.append(s['candidate_form'].format(n=f'{n:03d}'));evidence.append({'evidence_id':f'v2-case-{n:03d}-evidence-{i:03d}','source_index':i-1,'content':s['evidence_form'].format(n=f'{n:03d}')})
 text='\n'.join(units);return {'candidate_id':f'mc-v2-enrichment-{n:03d}','source_family':'identifiability_enrichment_synthetic_v2','candidate_text':text,'candidate_sha256':hb(text.encode()),'candidate_unicode_character_count':len(text),'unit_count':len(units),'component_order_commitment_sha256':csha([hb(x.encode()) for x in units]),'evidence_bundle':evidence,'evidence_bundle_sha256':csha(evidence),'valid_evidence_ids':[x['evidence_id'] for x in evidence]}
def all_rows():return [generated(i) for i in range(1,49)]
def prior_hashes():
 ch=set();eh=set()
 for p in [V1,PRED]:
  for c in load(p)['cases']:
   if c.get('candidate_sha256'):ch.add(c['candidate_sha256'])
   for k in ['evidence_bundle_sha256','source_evidence_bundle_sha256','normalized_evidence_bundle_sha256']:
    if c.get(k):eh.add(c[k])
   if c.get('evidence_bundle') is not None:eh.add(csha(c['evidence_bundle']))
 return ch,eh
def build():
 rows=all_rows();ch,eh=prior_hashes();aud=[]
 for x in rows:aud.append({'candidate_id':x['candidate_id'],'candidate_sha256':x['candidate_sha256'],'evidence_bundle_sha256':x['evidence_bundle_sha256'],'v1_or_predecessor_candidate_overlap':x['candidate_sha256'] in ch,'v1_or_predecessor_evidence_overlap':x['evidence_bundle_sha256'] in eh,'eligible':x['candidate_sha256'] not in ch and x['evidence_bundle_sha256'] not in eh})
 eligible=[x for x,a in zip(rows,aud) if a['eligible']]
 ranked=sorted(eligible,key=lambda x:(hb((SEED+'|'+x['candidate_id']+'|'+x['candidate_sha256']+'|'+x['evidence_bundle_sha256']).encode()),x['candidate_id']))[:40];chosen=[]
 for i,x in enumerate(ranked,1):chosen.append({'successor_v2_index':i,'candidate_id':x['candidate_id'],'source_family':x['source_family'],'candidate_sha256':x['candidate_sha256'],'evidence_bundle_sha256':x['evidence_bundle_sha256'],'component_order_commitment_sha256':x['component_order_commitment_sha256'],'unit_count':x['unit_count'],'selection_rank_sha256':hb((SEED+'|'+x['candidate_id']+'|'+x['candidate_sha256']+'|'+x['evidence_bundle_sha256']).encode()),'candidate_content_included':False,'evidence_content_included':False})
 inv={'schema_version':2,'inventory_id':'phase7.3.3-d-multi-claim-successor-source-inventory-v2','status':'frozen_metadata_only_content_sealed','inventory_count':48,'source_family':'identifiability_enrichment_synthetic_v2','items':[{'candidate_id':x['candidate_id'],'source_family':x['source_family'],'candidate_sha256':x['candidate_sha256'],'candidate_unicode_character_count':x['candidate_unicode_character_count'],'unit_count':x['unit_count'],'component_order_commitment_sha256':x['component_order_commitment_sha256'],'evidence_bundle_sha256':x['evidence_bundle_sha256'],'evidence_item_count':len(x['evidence_bundle']),'candidate_content_included':False,'evidence_content_included':False} for x in rows]}
 over={'schema_version':2,'audit_id':'phase7.3.3-d-multi-claim-successor-overlap-audit-v2','status':'PASS' if all(x['eligible'] for x in aud) else 'FAIL','inventory_count':48,'eligible_count':sum(x['eligible'] for x in aud),'candidate_overlap_count':sum(x['v1_or_predecessor_candidate_overlap'] for x in aud),'evidence_overlap_count':sum(x['v1_or_predecessor_evidence_overlap'] for x in aud),'items':aud}
 work={'schema_version':2,'worklist_id':'phase7.3.3-d-multi-claim-successor-selected-worklist-v2','status':'frozen_ids_hashes_and_order_commitments_content_sealed','selection_method':'deterministic_hash_order','seed':int(SEED),'inventory_count':48,'eligible_count':len(eligible),'target':40,'selected_count':len(chosen),'items':chosen,'candidate_content_included':False,'evidence_content_included':False,'support_labels_included':False}
 return inv,over,work
def protocol():return {'schema_version':2,'protocol_id':'phase7.3.3-d-multi-claim-successor-sampling-frame-protocol-v2','status':'frozen_with_content_sealed_frame','source_family':'identifiability_enrichment_synthetic_v2','inventory_count':48,'selection':{'method':'deterministic_hash_order','seed':int(SEED),'target':40,'manual_backfill_allowed':False},'content_state':{'candidate_content_opened':False,'evidence_content_opened':False,'template_roles_visible_to_reviewers':False,'support_labels_available':False},'overlap_contract':{'v1_and_predecessor_candidate_overlap_allowed':False,'v1_and_predecessor_evidence_overlap_allowed':False},'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':NEXT}
def fixtures():
 a=generated(1);b=generated(2);inv,over,w=build();xs=[{'fixture_id':'deterministic_generation','passed':a==generated(1)},{'fixture_id':'unique_candidate_hashes','passed':a['candidate_sha256']!=b['candidate_sha256']},{'fixture_id':'six_units','passed':a['unit_count']==6},{'fixture_id':'inventory_48','passed':inv['inventory_count']==48},{'fixture_id':'selected_40','passed':w['selected_count']==40},{'fixture_id':'zero_overlap','passed':over['candidate_overlap_count']==over['evidence_overlap_count']==0},{'fixture_id':'content_sealed','passed':not w['candidate_content_included'] and not w['evidence_content_included']}];return {'schema_version':2,'fixtures_id':'phase7.3.3-d-multi-claim-successor-sampling-fixtures-v2','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s.get('next_authorized_stage')==CUR,'readiness_gate':r.get('next_authorized_stage')==CUR,'v2_design_frozen':s.get('multi_claim_successor_v2_design_frozen') is True,'v1_negative_preserved':s.get('multi_claim_successor_v1_structural_negative_preserved') is True,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_off':s.get('runtime_integration_authorized') is False,'outputs_absent':all(not p.exists() for p in [PRO,INV,OVER,WORK,FIX,MAN,OUT,REC,SO,RO])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def manifest():
 inv,over,w=build();return {'schema_version':2,'manifest_id':'phase7.3.3-d-multi-claim-successor-sampling-manifest-v2','status':'frozen_before_selected_content_open','adapter_sha256':sha(SELF),'frozen_inputs':{rel(p):h for p,h in EXP.items()},'frozen_artifacts':{rel(PRO):sha(PRO),rel(INV):sha(INV),rel(OVER):sha(OVER),rel(WORK):sha(WORK),rel(FIX):sha(FIX)},'inventory_count':48,'eligible_count':over['eligible_count'],'selected_count':w['selected_count'],'candidate_content_opened':False,'evidence_content_opened':False,'provider_calls':0,'next_authorized_stage':NEXT}
def freeze():
 p=preflight()
 if p['status']!='PASS':return p
 inv,over,w=build();ph=once(PRO,protocol());ih=once(INV,inv);oh=once(OVER,over);wh=once(WORK,w);f=fixtures();fh=once(FIX,f);mh=once(MAN,manifest());out={'schema_version':2,'outcome_id':'phase7.3.3-d-multi-claim-successor-sampling-freeze-outcome-v2','status':'sampling_frame_v2_frozen_selected_content_sealed','inventory_count':48,'eligible_count':48,'selected_count':40,'candidate_content_opened':False,'evidence_content_opened':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':NEXT};outh=once(OUT,out);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_sampling_frame_protocol_v2_sha256':ph,'multi_claim_successor_source_inventory_v2_sha256':ih,'multi_claim_successor_overlap_audit_v2_sha256':oh,'multi_claim_successor_selected_worklist_v2_sha256':wh,'multi_claim_successor_sampling_manifest_v2_sha256':mh,'multi_claim_successor_sampling_outcome_v2_sha256':outh};u={'status':'multi_claim_successor_sampling_frame_v2_frozen_selected_content_open_authorized','next_authorized_stage':NEXT,'multi_claim_successor_v2_sampling_frame_frozen':True,'multi_claim_successor_v2_inventory_count':48,'multi_claim_successor_v2_selected_count':40,'multi_claim_successor_v2_content_opened':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':63,'state_id':'phase7.3.3-d-support-stage-state-v63'});r.update({'schema_version':74,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v74'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v63_sha256']=sh;rh=once(RO,r);rec={'schema_version':2,'receipt_id':'phase7.3.3-d-multi-claim-successor-sampling-freeze-receipt-v2','status':'PASS','manifest_sha256':mh,'outcome_sha256':outh,'state_sha256':sh,'readiness_sha256':rh,'inventory_count':48,'selected_count':40,'candidate_content_opened':False,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','protocol_sha256':ph,'inventory_sha256':ih,'overlap_sha256':oh,'worklist_sha256':wh,'fixtures_sha256':fh,'manifest_sha256':mh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':NEXT}
def verify():
 ps=[PRO,INV,OVER,WORK,FIX,MAN,OUT,REC,SO,RO];z={'exists:'+rel(p):p.exists() for p in ps}
 if all(p.exists() for p in ps):inv,over,w=build();s=load(SO);r=load(RO);z.update({'protocol_replay':load(PRO)==protocol(),'inventory_replay':load(INV)==inv,'overlap_replay':load(OVER)==over,'worklist_replay':load(WORK)==w,'fixtures_replay':load(FIX)==fixtures(),'manifest_replay':load(MAN)==manifest(),'zero_overlap':over['candidate_overlap_count']==over['evidence_overlap_count']==0,'selected_40':w['selected_count']==40,'content_sealed':s['multi_claim_successor_v2_content_opened'] is False,'next_gate':s['next_authorized_stage']==r['next_authorized_stage']==NEXT,'confirmatory_closed':s['confirmatory_dataset_opened'] is False and r['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False and r['runtime_integration_authorized'] is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'hashes':{p.name:sha(p) if p.exists() else None for p in ps},'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','fixtures','freeze','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else fixtures() if a.fixtures else freeze() if a.freeze else verify()
 if a.fixtures:o['status']='PASS' if o['all_fixtures_passed'] else 'FAIL'
 print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status')=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
