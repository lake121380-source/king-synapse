#!/usr/bin/env python3
"""Freeze Support Review frame-v3 semantic-label representation failure."""
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports';NEG=R/'phase7_3_3_d_multi_claim_successor_support_reviewer_a_negative_frame_v3.json';MAN=R/'phase7_3_3_d_multi_claim_successor_support_reviewer_a_manifest_frame_v3.json';LOG=R/'phase7_3_3_d_multi_claim_successor_support_review_attempts_frame_v3.jsonl';SI=D/'phase7_3_3_d_support_stage_state_v81.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v92.json';OUT=R/'phase7_3_3_d_multi_claim_successor_support_v3_failure_classification.json';REC=R/'phase7_3_3_d_multi_claim_successor_support_v3_failure_classification_receipt.json';SO=D/'phase7_3_3_d_support_stage_state_v82.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v93.json'
EXP={NEG:'5b71635fac70ca6377bae173c49a09432382567edcbdbc93f8b44894fbafdc90',MAN:'0b31de5ecbf97cce7b7216748104fdf18282f72fd7dd449906439ceed2b9deb3',LOG:'ced53d6876074436e24e91895bd6c722719aff270db91a38daa1704cf48bb989',SI:'bef9acae585bc1127136acee802c584fc69aba97f1cb0ed64b70fe5bfc1fc74b',RI:'e0a527b580a935ff18f8c09b85c1e4086da8eca2658d6c7b6e25b84e6f914b86'};NEXT='design_multi_claim_successor_support_review_frame_v4_label_code_representation'
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
 n=load(NEG);out={'schema_version':1,'classification_id':'phase7.3.3-d-support-v3-failure-classification','status':'frozen_authoritative_negative_classification','failure_level':'level_1_provider_representation_contract','failure_subtype':'semantic_label_serialization_failure','failure_code':n['failure_code'],'failed_case_id':n['failed_case_id'],'completed_case_count':0,'support_capability_conclusion_authorized':False,'same_version_retry_allowed':False,'v4_single_intended_change':'fixed 0-3 label_codes plus unchanged citation masks; diagnostics remain excluded','next_authorized_stage':NEXT};oh=once(OUT,out);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_support_v3_negative_sha256':sha(NEG),'multi_claim_successor_support_v3_failure_classification_sha256':oh};u={'status':'multi_claim_successor_support_v3_authoritative_negative_v4_representation_authorized','next_authorized_stage':NEXT,'multi_claim_successor_support_v3_negative_preserved':True,'multi_claim_successor_support_v3_same_version_retry_allowed':False,'multi_claim_successor_support_v3_capability_conclusion_authorized':False,'multi_claim_successor_support_reviewer_a_frame_v3_completed':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':82,'state_id':'phase7.3.3-d-support-stage-state-v82'});r.update({'schema_version':93,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v93'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v82_sha256']=sh;rh=once(RO,r);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-support-v3-failure-classification-receipt','status':'PASS','classification_sha256':oh,'state_sha256':sh,'readiness_sha256':rh,'same_version_retry_allowed':False,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','classification_sha256':oh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':NEXT}
def verify():
 z={p.name:p.exists() for p in [OUT,REC,SO,RO]}
 if all(z.values()):z.update({'classification':load(OUT)['failure_subtype']=='semantic_label_serialization_failure','no_capability_claim':load(OUT)['support_capability_conclusion_authorized'] is False,'same_version_retry_false':load(OUT)['same_version_retry_allowed'] is False,'next_gate':load(SO)['next_authorized_stage']==load(RO)['next_authorized_stage']==NEXT})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();o=verify() if a.verify else run();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
