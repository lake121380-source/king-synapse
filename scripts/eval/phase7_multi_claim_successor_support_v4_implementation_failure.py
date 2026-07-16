#!/usr/bin/env python3
"""Freeze the pre-provider Support v4 adapter implementation failure."""
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports';AD=ROOT/'scripts/eval/phase7_multi_claim_successor_support_review_frame_v4.py';MAN=R/'phase7_3_3_d_multi_claim_successor_support_reviewer_a_manifest_frame_v4.json';SI=D/'phase7_3_3_d_support_stage_state_v83.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v94.json';OUT=R/'phase7_3_3_d_multi_claim_successor_support_v4_implementation_failure.json';REC=R/'phase7_3_3_d_multi_claim_successor_support_v4_implementation_failure_receipt.json';SO=D/'phase7_3_3_d_support_stage_state_v84.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v95.json';EXP={AD:'6d984d53d672e0396c632fea0e273be0699d19ff969bea1251876a7e4bb63fef',MAN:'185dda009a8464b3367122806eb512398c29fbe4e405914646da49f91ae87eef',SI:'788ccc5242abaed5a895652abb12471ca9318928317b1fe9e13f34a3684b872b',RI:'b77126eefcb2df0585780f5078cf29331cbd90d4c3fc926bd24e13997dd4fb7d'};NEXT='prepare_multi_claim_successor_support_review_frame_v4_1'
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
 out={'schema_version':1,'classification_id':'phase7.3.3-d-support-v4-implementation-failure','status':'frozen_pre_provider_implementation_failure','failure_level':'adapter_implementation','failure_code':'NameError:append_event_not_defined','provider_request_sent':False,'provider_content_received':False,'authoritative_model_result_exists':False,'capability_conclusion_authorized':False,'same_version_execution_allowed':False,'v4_1_single_change':'bind frozen append_event audit helper','support_protocol_changed':False,'next_authorized_stage':NEXT};oh=once(OUT,out);s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_support_v4_adapter_sha256':sha(AD),'multi_claim_successor_support_v4_implementation_failure_sha256':oh};u={'status':'multi_claim_successor_support_v4_pre_provider_implementation_failure_v4_1_authorized','next_authorized_stage':NEXT,'multi_claim_successor_support_v4_implementation_failure_preserved':True,'multi_claim_successor_support_v4_provider_called':False,'multi_claim_successor_support_v4_capability_conclusion_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':84,'state_id':'phase7.3.3-d-support-stage-state-v84'});r.update({'schema_version':95,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v95'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v84_sha256']=sh;rh=once(RO,r);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-support-v4-implementation-failure-receipt','status':'PASS','classification_sha256':oh,'state_sha256':sh,'readiness_sha256':rh,'provider_called':False,'next_authorized_stage':NEXT};rch=once(REC,rec);return {'status':'PASS','classification_sha256':oh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':NEXT}
def verify():
 z={p.name:p.exists() for p in [OUT,REC,SO,RO]}
 if all(z.values()):z.update({'pre_provider':load(OUT)['provider_request_sent'] is False,'not_model_result':load(OUT)['authoritative_model_result_exists'] is False,'next_gate':load(SO)['next_authorized_stage']==load(RO)['next_authorized_stage']==NEXT})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();o=verify() if a.verify else run();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
