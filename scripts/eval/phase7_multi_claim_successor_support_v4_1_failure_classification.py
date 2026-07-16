#!/usr/bin/env python3
"""Freeze Support v4.1 citation serialization failure classification."""
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports';NEG=R/'phase7_3_3_d_multi_claim_successor_support_reviewer_a_negative_frame_v4_1.json';MAN=R/'phase7_3_3_d_multi_claim_successor_support_reviewer_a_manifest_frame_v4_1.json';LOG=R/'phase7_3_3_d_multi_claim_successor_support_review_attempts_frame_v4_1.jsonl';SI=D/'phase7_3_3_d_support_stage_state_v85.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v96.json';OUT=R/'phase7_3_3_d_multi_claim_successor_support_v4_1_failure_classification.json';REC=R/'phase7_3_3_d_multi_claim_successor_support_v4_1_failure_classification_receipt.json';SO=D/'phase7_3_3_d_support_stage_state_v86.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v97.json';EXP={NEG:'26d012fae129d093a140581a00a6b803c50d0877ecf0d38d9a6a563e86073a13',MAN:'8c14a7ef7242f294acfca4c4b1d2036e9235352d58250bb1d79cadfc87102775',LOG:'3de16e5537c4e3d79a06dc74981646c28ebe63fa616ced348c160a8b588a7562',SI:'575436e6f99972e2e53869983af0dac0788d8b191ecd01f5b8972eb24b2dfec9',RI:'7605862bfba73107d89ee20f0db04f1f1d2ea935c89e09120d410dbd8de6d53b'};NEXT='design_multi_claim_successor_support_review_frame_v5_label_only'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def once(p,x):
 b=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists() and p.read_bytes()!=b:raise RuntimeError('immutable_conflict')
 if not p.exists():
  p.parent.mkdir(parents=True,exist_ok=True)
  with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
  t.replace(p)
 return sha(p)
def run():
 if any(sha(p)!=h for p,h in EXP.items()):raise RuntimeError('input_hash_mismatch')
 n=load(NEG);out={'schema_version':1,'classification_id':'phase7.3.3-d-support-v4.1-failure-classification','status':'frozen_authoritative_negative_classification','failure_level':'level_2_support_provenance_serialization','failure_subtype':'citation_mask_serialization_failure','failure_code':n['failure_code'],'failed_case_id':n['failed_case_id'],'completed_case_count':n['completed_case_count'],'support_label_code_contract_completed_before_failure':True,'support_label_capability_conclusion_authorized':False,'citation_capability_conclusion_authorized':False,'same_version_retry_allowed':False,'v5_single_intended_change':'support label codes only; citations moved to diagnostic stage','next_authorized_stage':NEXT};oh=once(OUT,out);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_support_v4_1_negative_sha256':sha(NEG),'multi_claim_successor_support_v4_1_failure_classification_sha256':oh};u={'status':'multi_claim_successor_support_v4_1_authoritative_negative_v5_label_only_authorized','next_authorized_stage':NEXT,'multi_claim_successor_support_v4_1_negative_preserved':True,'multi_claim_successor_support_v4_1_same_version_retry_allowed':False,'multi_claim_successor_support_v4_1_capability_conclusion_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':86,'state_id':'phase7.3.3-d-support-stage-state-v86'});r.update({'schema_version':97,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v97'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v86_sha256']=sh;rh=once(RO,r);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-support-v4.1-failure-classification-receipt','status':'PASS','classification_sha256':oh,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','classification_sha256':oh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':NEXT}
def verify():
 z={p.name:p.exists() for p in [OUT,REC,SO,RO]}
 if all(z.values()):z.update({'citation_failure':load(OUT)['failure_subtype']=='citation_mask_serialization_failure','no_capability_claim':load(OUT)['support_label_capability_conclusion_authorized'] is False,'next_gate':load(SO)['next_authorized_stage']==load(RO)['next_authorized_stage']==NEXT})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();o=verify() if a.verify else run();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
