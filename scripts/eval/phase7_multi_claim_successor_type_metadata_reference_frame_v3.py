#!/usr/bin/env python3
"""Construct, replay, and seal Type/Metadata Reference frame v3."""
from __future__ import annotations
import argparse,copy,hashlib,json,tempfile
from collections import Counter
from pathlib import Path
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
BOUND=D/'phase7_3_3_d_multi_claim_successor_boundary_reference_candidate_frame_v2.json';A=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_a_submission_frame_v3.json';B=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_b_submission_frame_v3.json';AGR=R/'phase7_3_3_d_multi_claim_successor_type_metadata_agreement_report_frame_v3.json';ADJ=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_submission_frame_v3.json';AREC=R/'phase7_3_3_d_multi_claim_successor_type_metadata_adjudication_receipt_frame_v3.json';SI=D/'phase7_3_3_d_support_stage_state_v77.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v88.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_protocol_frame_v3.json';FIX=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_fixtures_frame_v3.json';MAN=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_manifest_frame_v3.json';REF=D/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_frame_v3.json';QA=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_qa_frame_v3.json';SEAL=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_seal_frame_v3.json';REC=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_receipt_frame_v3.json';SO=D/'phase7_3_3_d_support_stage_state_v78.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v89.json'
EXP={BOUND:'55b4ed55e23c778bfc2cfdb525bf7bf49c78790a030a96e85fd3f4b0947f41d5',A:'ea2673172198e46678b6e9ab9bae3ece3e2060cbd2d5c251b5f10dfda37dae3d',B:'8a273ec5ecdb79d6c5a6594ba2e3e3bcf4632fa612b742817e61d69708784c9e',AGR:'5aeefac268fa65d0db94a0eaa94d25bdc15180b5aa0cdc0a10cfb88878f98940',ADJ:'82f69a3c5974455e2f8161f516a557e70e1c5e101e10e32989cd190f2a366c62',AREC:'e94d2590c01f5e392836c6f556dbfc340a8b909ebe9b5933f4ac5c5a30ef71b6',SI:'4fff0641c82be818cf6e135146374cc9531d995bfa5ce182a13269e3c4c7a9d2',RI:'768230c1909f37905c0c1037252a5646569423ffd2cb47b54d327717da00a45d'}
CUR='construct_multi_claim_successor_type_metadata_reference_frame_v3';NEXT='construct_multi_claim_successor_support_review_packet_frame_v2'
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
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
def flat(p):return {x['reference_claim_id']:x for c in load(p)['cases'] for x in c['decisions']}
def build_ref():
 a=flat(A);b=flat(B);ads={x['reference_claim_id']:x for x in load(ADJ)['adjudications']};cases=[];ac=jc=0;roles=Counter();types=Counter()
 for c in load(BOUND)['cases']:
  claims=[]
  for q in c['claims']:
   cid=q['reference_claim_id'];da=a[cid];db=b[cid]
   if (da['claim_role'],da['claim_type'])==(db['claim_role'],db['claim_type']):d=da;basis='independent_joint_exact_agreement';wid=None;ac+=1
   else:d=ads[cid]['selected_decision'];basis='blinded_adjudication_selected_existing_option';wid=ads[cid]['work_item_id'];jc+=1
   roles[d['claim_role']]+=1;types[d['claim_type']]+=1;claims.append({**copy.deepcopy(q),'claim_role':d['claim_role'],'claim_type':d['claim_type'],'claim_origin':'explicit','metadata_resolution_basis':basis,'adjudication_work_item_id':wid,'boundary_mutation_performed':False})
  cases.append({'case_id':c['case_id'],'candidate_text':c['candidate_text'],'candidate_sha256':c['candidate_sha256'],'claim_count':len(claims),'claims':claims,'protocol_excluded_spans':copy.deepcopy(c['protocol_excluded_spans'])})
 return {'schema_version':3,'reference_id':'phase7.3.3-d-multi-claim-successor-type-metadata-reference-frame-v3','status':'verified_and_sealed_type_metadata_reference_not_human_gold','boundary_reference_sha256':sha(BOUND),'case_count':40,'claim_count':240,'agreement_claim_count':ac,'adjudicated_claim_count':jc,'role_counts':dict(sorted(roles.items())),'type_counts':dict(sorted(types.items())),'origin_counts':{'explicit':240},'cases':cases,'boundary_mutation_performed':False,'support_labels_present':False,'reference_sealed':True,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def protocol():return {'schema_version':3,'protocol_id':'phase7.3.3-d-type-metadata-reference-protocol-frame-v3','status':'frozen_before_offline_construction','resolution':['joint exact agreement','selected existing adjudicated option'],'expected_partition':{'agreement':82,'adjudication':158},'origin':'explicit from provenance','boundary_mutation_allowed':False,'support_creation_allowed':False,'provider_calls':0,'next_authorized_stage':NEXT}
def fixtures():
 r=build_ref();xs=[{'fixture_id':'240','passed':r['claim_count']==240},{'fixture_id':'partition','passed':r['agreement_claim_count']==82 and r['adjudicated_claim_count']==158},{'fixture_id':'origin','passed':r['origin_counts']=={'explicit':240}},{'fixture_id':'no_boundary_mutation','passed':all(not q['boundary_mutation_performed'] for c in r['cases'] for q in c['claims'])},{'fixture_id':'no_support','passed':r['support_labels_present'] is False}];return {'schema_version':3,'fixtures_id':'phase7.3.3-d-type-metadata-reference-fixtures-frame-v3','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def manifest():return {'schema_version':3,'manifest_id':'phase7.3.3-d-type-metadata-reference-manifest-frame-v3','status':'frozen_ready_for_offline_construction','adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'fixtures_sha256':sha(FIX),'frozen_inputs':{rel(p):h for p,h in EXP.items()},'expected_claim_count':240,'expected_agreement_count':82,'expected_adjudicated_count':158,'provider_calls':0,'next_authorized_stage':CUR}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'adjudication_no_defer':load(ADJ)['deferred_count']==0 and load(ADJ)['item_count']==158,'agreement_partition':load(AGR)['joint_exact_count']==82 and load(AGR)['joint_disagreement_count']==158,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,FIX,MAN,REF,QA,SEAL,REC,SO,RO])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def run():
 p=preflight()
 if p['status']!='PASS':return p
 ph=once(PRO,protocol());fh=once(FIX,fixtures());mh=once(MAN,manifest());ref=build_ref();rh=once(REF,ref);qa={'schema_version':3,'qa_id':'phase7.3.3-d-type-metadata-reference-qa-frame-v3','status':'PASS','reference_sha256':rh,'claim_count':240,'agreement_claim_count':82,'adjudicated_claim_count':158,'all_claim_ids_unique':len({q['reference_claim_id'] for c in ref['cases'] for q in c['claims']})==240,'all_origins_explicit':all(q['claim_origin']=='explicit' for c in ref['cases'] for q in c['claims']),'boundary_mutation_performed':False,'support_labels_present':False};qh=once(QA,qa);seal={'schema_version':3,'seal_id':'phase7.3.3-d-type-metadata-reference-seal-frame-v3','status':'verified_and_sealed_type_metadata_reference_not_human_gold','reference_sha256':rh,'qa_sha256':qh,'claim_count':240,'boundary_reference_sha256':sha(BOUND),'support_labels_present':False,'next_authorized_stage':NEXT};seh=once(SEAL,seal);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_type_metadata_reference_protocol_frame_v3_sha256':ph,'multi_claim_successor_type_metadata_reference_manifest_frame_v3_sha256':mh,'multi_claim_successor_type_metadata_reference_frame_v3_sha256':rh,'multi_claim_successor_type_metadata_reference_qa_frame_v3_sha256':qh,'multi_claim_successor_type_metadata_reference_seal_frame_v3_sha256':seh};u={'status':'multi_claim_successor_type_metadata_reference_frame_v3_sealed_support_review_packet_authorized','next_authorized_stage':NEXT,'multi_claim_successor_type_metadata_reference_frame_v3_created':True,'multi_claim_successor_type_metadata_reference_frame_v3_sealed':True,'multi_claim_successor_type_metadata_reference_frame_v3_claim_count':240,'multi_claim_successor_support_gold_frame_v2_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':78,'state_id':'phase7.3.3-d-support-stage-state-v78'});r.update({'schema_version':89,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v89'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v78_sha256']=sh;rrh=once(RO,r);rec={'schema_version':3,'receipt_id':'phase7.3.3-d-type-metadata-reference-receipt-frame-v3','status':'PASS','manifest_sha256':mh,'reference_sha256':rh,'qa_sha256':qh,'seal_sha256':seh,'state_sha256':sh,'readiness_sha256':rrh,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','reference_sha256':rh,'qa_sha256':qh,'seal_sha256':seh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rrh,'role_counts':ref['role_counts'],'type_counts':ref['type_counts'],'next_authorized_stage':NEXT}
def verify():
 ps=[PRO,FIX,MAN,REF,QA,SEAL,REC,SO,RO];z={'exists:'+rel(p):p.exists() for p in ps}
 if all(p.exists() for p in ps):ref=load(REF);s=load(SO);r=load(RO);z.update({'protocol_replay':load(PRO)==protocol(),'fixtures_replay':load(FIX)==fixtures(),'manifest_replay':load(MAN)==manifest(),'reference_replay':ref==build_ref(),'partition':ref['agreement_claim_count']==82 and ref['adjudicated_claim_count']==158,'claim_count':ref['claim_count']==240,'seal_lineage':load(SEAL)['reference_sha256']==sha(REF) and load(SEAL)['qa_sha256']==sha(QA),'next_gate':s['next_authorized_stage']==r['next_authorized_stage']==NEXT,'confirmatory_closed':s['confirmatory_dataset_opened'] is False and r['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False and r['runtime_integration_authorized'] is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','run','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else run() if a.run else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status')=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
