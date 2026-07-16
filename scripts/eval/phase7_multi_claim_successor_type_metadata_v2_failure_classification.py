#!/usr/bin/env python3
"""Classify and freeze the frame-v2 Type/Metadata representation failure."""
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
NEG=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_a_negative_frame_v2.json';MAN=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_a_manifest_frame_v2.json';LOG=R/'phase7_3_3_d_multi_claim_successor_type_metadata_review_attempts_frame_v2.jsonl';SI=D/'phase7_3_3_d_support_stage_state_v71.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v82.json';OUT=R/'phase7_3_3_d_multi_claim_successor_type_metadata_v2_failure_classification.json';REC=R/'phase7_3_3_d_multi_claim_successor_type_metadata_v2_failure_classification_receipt.json';SO=D/'phase7_3_3_d_support_stage_state_v72.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v83.json'
EXP={NEG:'e0eb0dc53a88ba8676ed740ca11009d45e289d06ad681c8eb297af185c6ced91',MAN:'8902d9371a8f42a917661f9326f06219dd95df9e72ed0dd4c7aaf237e922d816',LOG:'5f80b3c7d76b5ca2053f915ccbca6d1ed3ea6242dca7783f2c4099e63a86484a',SI:'88aff669341927b464187bf3baf49fe022bef058bd142911305be7288030469b',RI:'c8a69b5333587c9cdab52ae04dd78e6288965813b8402571ebd6ddc6f998f51f'}
NEXT='design_multi_claim_successor_type_metadata_review_frame_v3_representation'
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
 n=load(NEG);out={'schema_version':1,'classification_id':'phase7.3.3-d-type-metadata-v2-failure-classification','status':'frozen_authoritative_negative_classification','failure_level':'level_1_provider_representation_contract','failure_subtype':'enum_serialization_failure','failure_code':n['failure_code'],'failed_case_id':n['failed_case_id'],'completed_case_count':n['completed_case_count'],'provider_content_sha256_recorded':True,'raw_provider_content_stored':False,'exact_invalid_field_identifiable':False,'type_metadata_capability_conclusion_authorized':False,'partial_execution_reference_authorized':False,'same_version_retry_allowed':False,'v3_single_intended_change':'fixed-length numeric role/type code arrays; origin reconstructed by adapter','next_authorized_stage':NEXT};oh=once(OUT,out);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_type_metadata_v2_negative_sha256':sha(NEG),'multi_claim_successor_type_metadata_v2_failure_classification_sha256':oh};u={'status':'multi_claim_successor_type_metadata_v2_authoritative_negative_v3_representation_authorized','next_authorized_stage':NEXT,'multi_claim_successor_type_metadata_v2_negative_preserved':True,'multi_claim_successor_type_metadata_v2_same_version_retry_allowed':False,'multi_claim_successor_type_metadata_v2_capability_conclusion_authorized':False,'multi_claim_successor_type_metadata_reviewer_a_frame_v2_completed':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':72,'state_id':'phase7.3.3-d-support-stage-state-v72'});r.update({'schema_version':83,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v83'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v72_sha256']=sh;rh=once(RO,r);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-type-metadata-v2-failure-classification-receipt','status':'PASS','classification_sha256':oh,'state_sha256':sh,'readiness_sha256':rh,'same_version_retry_allowed':False,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','classification_sha256':oh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':NEXT}
def verify():
 ps=[OUT,REC,SO,RO];z={p.name:p.exists() for p in ps}
 if all(z.values()):z.update({'classification':load(OUT)['failure_subtype']=='enum_serialization_failure','no_capability_claim':load(OUT)['type_metadata_capability_conclusion_authorized'] is False,'same_version_retry_false':load(OUT)['same_version_retry_allowed'] is False,'next_gate':load(SO)['next_authorized_stage']==load(RO)['next_authorized_stage']==NEXT})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();o=verify() if a.verify else run();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
