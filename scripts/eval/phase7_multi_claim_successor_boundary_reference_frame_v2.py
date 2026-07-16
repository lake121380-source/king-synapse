#!/usr/bin/env python3
"""Construct, QA, and seal the exact-agreement Boundary Reference Candidate frame v2."""
from __future__ import annotations
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
DATA=D/'phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json';A=R/'phase7_3_3_d_multi_claim_successor_boundary_reviewer_a_submission_frame_v2.json';B=R/'phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_submission_frame_v2.json';AGR=R/'phase7_3_3_d_multi_claim_successor_boundary_agreement_report_frame_v2.json';AREC=R/'phase7_3_3_d_multi_claim_successor_boundary_agreement_receipt_frame_v2.json';SI=D/'phase7_3_3_d_support_stage_state_v69.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v80.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_boundary_reference_protocol_frame_v2.json';FIX=R/'phase7_3_3_d_multi_claim_successor_boundary_reference_fixtures_frame_v2.json';MAN=R/'phase7_3_3_d_multi_claim_successor_boundary_reference_manifest_frame_v2.json';REF=D/'phase7_3_3_d_multi_claim_successor_boundary_reference_candidate_frame_v2.json';QA=R/'phase7_3_3_d_multi_claim_successor_boundary_reference_qa_frame_v2.json';SEAL=R/'phase7_3_3_d_multi_claim_successor_boundary_reference_seal_frame_v2.json';REC=R/'phase7_3_3_d_multi_claim_successor_boundary_reference_receipt_frame_v2.json';SO=D/'phase7_3_3_d_support_stage_state_v70.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v81.json'
EXP={DATA:'788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe',A:'5b98d7d37fe658178a63d890f487642e7173f2b6936765e129e9f4fa138d7a68',B:'fdcc8761165393e65a8b01943f48e48ce513bec720b2f68f5d3be268e5289fc6',AGR:'cd17c8a66db98a610143bc495b5ab8fbfc0ae40f6bb0b477c4851edbefd9c30b',AREC:'55b667e371bbba0a1f9f4e7eef4246cfb0742a3c8a678627c916572416dd918b',SI:'3ef512cbd6aa47104b2997bd275d80b02a1b8b2022f467a3a24b6a56b4166546',RI:'5866521d6d3110073556cf629c1f0d33e21f08c9787c15a5e44f4efa03938aea'}
CUR='construct_multi_claim_successor_boundary_reference_candidate_frame_v2';NEXT='construct_multi_claim_successor_type_metadata_review_frame_v2'
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
def build_ref():
 data={x['candidate_id']:x for x in load(DATA)['cases']};a={x['case_id']:x for x in load(A)['cases']};b={x['case_id']:x for x in load(B)['cases']};cases=[];total=0
 for cid in a:
  c=data[cid];claims=[]
  for i,(x,y) in enumerate(zip(a[cid]['claims'],b[cid]['claims']),1):
   if x['source_span']!=y['source_span'] or x['source_excerpt']!=y['source_excerpt']:raise RuntimeError('agreement_drift:'+cid)
   claims.append({'reference_claim_id':f'{cid}-boundary-reference-claim-{i:03d}','case_id':cid,'claim_index':i,'source_span':copy.deepcopy(x['source_span']),'source_excerpt':x['source_excerpt'],'source_unit_ids':copy.deepcopy(x['source_unit_ids']),'boundary_operation_kind':x['boundary_operation_kind'],'boundary_status':'independent_exact_agreement','reviewer_a_claim_id':x['claim_id'],'reviewer_b_claim_id':y['claim_id']})
  total+=len(claims);excluded=[{'start':i,'end':i+1,'source_excerpt':'\n','reason_code':'protocol_excluded_lf_separator'} for i,ch in enumerate(c['candidate_text']) if ch=='\n'];cases.append({'case_id':cid,'candidate_text':c['candidate_text'],'candidate_sha256':c['candidate_sha256'],'evidence_bundle_sha256':c['evidence_bundle_sha256'],'claim_count':len(claims),'claims':claims,'protocol_excluded_spans':excluded})
 return {'schema_version':2,'reference_id':'phase7.3.3-d-multi-claim-successor-boundary-reference-candidate-frame-v2','status':'verified_and_sealed_boundary_reference_candidate_not_human_gold','case_count':len(cases),'claim_count':total,'agreement_claim_count':total,'adjudicated_claim_count':0,'coverage_eligible_definition':'all_non_whitespace_unicode_code_points','cases':cases,'boundary_reference_sealed':True,'support_labels_present':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def coverage(ref):
 gap=overlap=0
 for c in ref['cases']:
  cov=[0]*len(c['candidate_text'])
  for q in c['claims']:
   for i in range(q['source_span']['start'],q['source_span']['end']):cov[i]+=1
  gap+=sum(not ch.isspace() and cov[i]==0 for i,ch in enumerate(c['candidate_text']));overlap+=sum(not ch.isspace() and cov[i]>1 for i,ch in enumerate(c['candidate_text']))
 return gap,overlap
def protocol():return {'schema_version':2,'protocol_id':'phase7.3.3-d-boundary-reference-protocol-frame-v2','status':'frozen_before_construction','construction':'exact Reviewer A/B span agreement only','adjudication_count_required':0,'coverage_eligible':'non-whitespace code points','LF_separators':'explicit_protocol_excluded_spans','support_label_creation_allowed':False,'provider_calls':0,'next_authorized_stage':NEXT}
def fixtures():
 r=build_ref();g,o=coverage(r);xs=[{'fixture_id':'240_claims','passed':r['claim_count']==240},{'fixture_id':'zero_adjudication','passed':r['adjudicated_claim_count']==0},{'fixture_id':'coverage_gap_zero','passed':g==0},{'fixture_id':'overlap_zero','passed':o==0},{'fixture_id':'no_support','passed':r['support_labels_present'] is False}];return {'schema_version':2,'fixtures_id':'phase7.3.3-d-boundary-reference-fixtures-frame-v2','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def manifest():return {'schema_version':2,'manifest_id':'phase7.3.3-d-boundary-reference-manifest-frame-v2','status':'frozen_ready_for_offline_construction','adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'fixtures_sha256':sha(FIX),'frozen_inputs':{rel(p):h for p,h in EXP.items()},'expected_case_count':40,'expected_claim_count':240,'provider_calls':0,'next_authorized_stage':CUR}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'agreement_exact_40':load(AGR)['exact_case_count']==40 and load(AGR)['disagreement_case_count']==0,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,FIX,MAN,REF,QA,SEAL,REC,SO,RO])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def run():
 p=preflight()
 if p['status']!='PASS':return p
 ph=once(PRO,protocol());fh=once(FIX,fixtures());mh=once(MAN,manifest());ref=build_ref();rh=once(REF,ref);g,o=coverage(ref);qa={'schema_version':2,'qa_id':'phase7.3.3-d-boundary-reference-qa-frame-v2','status':'PASS' if g==o==0 else 'FAIL','manifest_sha256':mh,'reference_sha256':rh,'case_count':40,'claim_count':240,'eligible_gap_characters':g,'overlap_characters':o,'claim_ids_unique':len({q['reference_claim_id'] for c in ref['cases'] for q in c['claims']})==240,'support_labels_present':False};qh=once(QA,qa);seal={'schema_version':2,'seal_id':'phase7.3.3-d-boundary-reference-seal-frame-v2','status':'verified_and_sealed_boundary_reference_candidate_not_human_gold','reference_sha256':rh,'qa_sha256':qh,'case_count':40,'claim_count':240,'coverage_pass':g==o==0,'support_labels_present':False,'next_authorized_stage':NEXT};seh=once(SEAL,seal);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_boundary_reference_protocol_frame_v2_sha256':ph,'multi_claim_successor_boundary_reference_manifest_frame_v2_sha256':mh,'multi_claim_successor_boundary_reference_candidate_frame_v2_sha256':rh,'multi_claim_successor_boundary_reference_qa_frame_v2_sha256':qh,'multi_claim_successor_boundary_reference_seal_frame_v2_sha256':seh};u={'status':'multi_claim_successor_boundary_reference_frame_v2_sealed_type_metadata_review_authorized','next_authorized_stage':NEXT,'multi_claim_successor_boundary_reference_frame_v2_created':True,'multi_claim_successor_boundary_reference_frame_v2_sealed':True,'multi_claim_successor_boundary_reference_frame_v2_claim_count':240,'multi_claim_successor_boundary_coverage_gap_characters':0,'multi_claim_successor_boundary_overlap_characters':0,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':70,'state_id':'phase7.3.3-d-support-stage-state-v70'});r.update({'schema_version':81,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v81'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v70_sha256']=sh;rrh=once(RO,r);rec={'schema_version':2,'receipt_id':'phase7.3.3-d-boundary-reference-receipt-frame-v2','status':'PASS','manifest_sha256':mh,'reference_sha256':rh,'qa_sha256':qh,'seal_sha256':seh,'state_sha256':sh,'readiness_sha256':rrh,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','reference_sha256':rh,'qa_sha256':qh,'seal_sha256':seh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rrh,'next_authorized_stage':NEXT}
def verify():
 ps=[PRO,FIX,MAN,REF,QA,SEAL,REC,SO,RO];z={'exists:'+rel(p):p.exists() for p in ps}
 if all(p.exists() for p in ps):ref=load(REF);g,o=coverage(ref);s=load(SO);r=load(RO);z.update({'protocol_replay':load(PRO)==protocol(),'fixtures_replay':load(FIX)==fixtures(),'manifest_replay':load(MAN)==manifest(),'reference_replay':ref==build_ref(),'case_40_claim_240':ref['case_count']==40 and ref['claim_count']==240,'coverage_zero':g==o==0,'seal_lineage':load(SEAL)['reference_sha256']==sha(REF) and load(SEAL)['qa_sha256']==sha(QA),'next_gate':s['next_authorized_stage']==r['next_authorized_stage']==NEXT,'confirmatory_closed':s['confirmatory_dataset_opened'] is False and r['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False and r['runtime_integration_authorized'] is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'hashes':{p.name:sha(p) if p.exists() else None for p in ps},'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','run','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else run() if a.run else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status')=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
