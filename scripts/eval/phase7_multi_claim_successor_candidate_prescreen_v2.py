#!/usr/bin/env python3
"""Run deterministic non-Gold candidate prescreen for successor v2."""
from __future__ import annotations
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
DATA=D/'phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json';OMAN=R/'phase7_3_3_d_multi_claim_successor_content_open_manifest_v2.json';OREC=R/'phase7_3_3_d_multi_claim_successor_content_open_receipt_v2.json';SI=D/'phase7_3_3_d_support_stage_state_v64.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v75.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_candidate_prescreen_protocol_v2.json';FIX=R/'phase7_3_3_d_multi_claim_successor_candidate_prescreen_fixtures_v2.json';MAN=R/'phase7_3_3_d_multi_claim_successor_candidate_prescreen_manifest_v2.json';REP=R/'phase7_3_3_d_multi_claim_successor_candidate_prescreen_report_v2.json';REC=R/'phase7_3_3_d_multi_claim_successor_candidate_prescreen_receipt_v2.json';SO=D/'phase7_3_3_d_support_stage_state_v65.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v76.json'
EXP={DATA:'788a8180d47d29ba8ee33bfa1113f204cc2cca0a5abda0af0748b088e60b8ebe',OMAN:'e42431e7246d0ca2963d1471b905fc632fe0fd9f3dbfa1bc8bdb7dd8608ea2b5',OREC:'1b05961f718d9fda30cbf69d6a5304bc9ea8694c0d531857a1fa6895240c5226',SI:'7dba0e14c7aa706997a7893b96264b705566ab31f63363a856677675473786c7',RI:'1a01e6790b75c376de4ffcc9774b4721416b0d938ec3c3897e8b5bdf37d723b0'}
CUR='run_multi_claim_successor_candidate_prescreen_v2';NEXT='construct_multi_claim_successor_independent_boundary_review_a_v2'
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
def inspect(c):
 units=c['candidate_text'].split('\n');ev={x['content'] for x in c['evidence_bundle']};exact=sum(x in ev for x in units);return {'case_id':c['candidate_id'],'candidate_sha256':c['candidate_sha256'],'unit_count':len(units),'unique_unit_count':len(set(units)),'nonempty_unit_count':sum(bool(x) for x in units),'evidence_count':len(ev),'exact_overlap_count':exact,'exact_nonoverlap_count':len(units)-exact,'candidate_hash_verified':hb(c['candidate_text'].encode())==c['candidate_sha256'],'evidence_hash_verified':csha(c['evidence_bundle'])==c['evidence_bundle_sha256'],'multi_unit_proxy':len(units)>=2 and len(set(units))==len(units) and all(units),'mixed_overlap_proxy':exact>=1 and exact<len(units),'boundary_emitted':False,'support_label_emitted':False}
def report():
 rows=[inspect(c) for c in load(DATA)['cases']];checks={'case_count_40':len(rows)==40,'all_six_units':all(x['unit_count']==6 for x in rows),'all_units_unique_nonempty':all(x['unique_unit_count']==x['nonempty_unit_count']==6 for x in rows),'all_hashes_verified':all(x['candidate_hash_verified'] and x['evidence_hash_verified'] for x in rows),'all_multi_unit':all(x['multi_unit_proxy'] for x in rows),'all_mixed_overlap':all(x['mixed_overlap_proxy'] for x in rows),'no_boundary_or_support_output':all(not x['boundary_emitted'] and not x['support_label_emitted'] for x in rows)};return {'schema_version':2,'report_id':'phase7.3.3-d-multi-claim-successor-candidate-prescreen-report-v2','status':'PASS' if all(checks.values()) else 'FAIL','interpretation':'structural_proxy_not_boundary_gold_not_support_gold','case_count':40,'checks':checks,'cases':rows,'provider_calls':0,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def protocol():return {'schema_version':2,'protocol_id':'phase7.3.3-d-multi-claim-successor-candidate-prescreen-protocol-v2','status':'frozen_before_prescreen','unitization':'exact_LF_split_without_normalization','multi_unit_proxy':'at least two unique nonempty LF units','mixed_overlap_proxy':'at least one exact evidence-overlap unit and one non-overlap unit','proxy_is_gold':False,'boundary_or_support_output_authorized':False,'case_drop_authorized':False,'provider_call_authorized':False,'next_authorized_stage':NEXT}
def fixtures():
 d=load(DATA)['cases'][0];x=inspect(d);xs=[{'fixture_id':'six_units','passed':x['unit_count']==6},{'fixture_id':'mixed_overlap','passed':x['exact_overlap_count']==2 and x['exact_nonoverlap_count']==4},{'fixture_id':'hashes','passed':x['candidate_hash_verified'] and x['evidence_hash_verified']},{'fixture_id':'no_gold','passed':not x['boundary_emitted'] and not x['support_label_emitted']}];return {'schema_version':2,'fixtures_id':'phase7.3.3-d-multi-claim-successor-candidate-prescreen-fixtures-v2','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'selected_content_open':s['multi_claim_successor_v2_selected_content_opened'] is True,'unselected_closed':s['multi_claim_successor_v2_unselected_content_opened'] is False,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,FIX,MAN,REP,REC,SO,RO])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def manifest():return {'schema_version':2,'manifest_id':'phase7.3.3-d-multi-claim-successor-candidate-prescreen-manifest-v2','status':'frozen_ready_for_offline_prescreen','adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'fixtures_sha256':sha(FIX),'frozen_inputs':{rel(p):h for p,h in EXP.items()},'expected_report_sha256':hb((json.dumps(report(),ensure_ascii=False,indent=2)+'\n').encode()),'provider_calls':0,'next_authorized_stage':CUR}
def run():
 p=preflight()
 if p['status']!='PASS':return p
 ph=once(PRO,protocol());fh=once(FIX,fixtures());mh=once(MAN,manifest());rep=report();rh=once(REP,rep)
 if rep['status']!='PASS':raise RuntimeError('prescreen_failed')
 s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_candidate_prescreen_protocol_v2_sha256':ph,'multi_claim_successor_candidate_prescreen_manifest_v2_sha256':mh,'multi_claim_successor_candidate_prescreen_report_v2_sha256':rh};u={'status':'multi_claim_successor_v2_candidate_prescreen_pass_boundary_review_a_authorized','next_authorized_stage':NEXT,'multi_claim_successor_v2_candidate_prescreen_completed':True,'multi_claim_successor_v2_candidate_prescreen_status':'PASS','multi_claim_successor_v2_boundary_review_a_authorized':True,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':65,'state_id':'phase7.3.3-d-support-stage-state-v65'});r.update({'schema_version':76,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v76'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v65_sha256']=sh;rrh=once(RO,r);rec={'schema_version':2,'receipt_id':'phase7.3.3-d-multi-claim-successor-candidate-prescreen-receipt-v2','status':'PASS','manifest_sha256':mh,'report_sha256':rh,'state_sha256':sh,'readiness_sha256':rrh,'case_count':40,'boundary_or_support_output':False,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','report_sha256':rh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rrh,'next_authorized_stage':NEXT}
def verify():
 ps=[PRO,FIX,MAN,REP,REC,SO,RO];z={'exists:'+rel(p):p.exists() for p in ps}
 if all(p.exists() for p in ps):s=load(SO);r=load(RO);z.update({'protocol_replay':load(PRO)==protocol(),'fixtures_replay':load(FIX)==fixtures(),'manifest_replay':load(MAN)==manifest(),'report_replay':load(REP)==report(),'report_pass':load(REP)['status']=='PASS','next_gate':s['next_authorized_stage']==r['next_authorized_stage']==NEXT,'confirmatory_closed':s['confirmatory_dataset_opened'] is False and r['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False and r['runtime_integration_authorized'] is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'hashes':{p.name:sha(p) if p.exists() else None for p in ps},'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','run','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else run() if a.run else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status')=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
