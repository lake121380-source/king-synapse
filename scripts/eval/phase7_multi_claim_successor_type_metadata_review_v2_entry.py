#!/usr/bin/env python3
"""Freeze the v1 failure classification and authorize representation-only v2."""
from __future__ import annotations
import argparse,copy,hashlib,json
from pathlib import Path
from typing import Any
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];CONFIG=ROOT/'crates/eval/config';PATTERN=ROOT/'crates/eval/datasets/pattern_extraction';REPORTS=ROOT/'crates/eval/reports'
STATE_IN=PATTERN/'phase7_3_3_d_support_stage_state_v40.json';READY_IN=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v51.json';NEG=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_b_negative_result_v1.json';A_SUB=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_a_submission_v1.json';V1_PROTOCOL=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_review_protocol_v1.json';V1_POLICY=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_review_execution_policy_v1.json'
CLASS=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_reviewer_b_failure_classification_v1.json';ENTRY=CONFIG/'phase7_3_3_d_multi_claim_successor_type_metadata_review_v2_entry_protocol_v1.json';MANIFEST=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_review_v2_entry_manifest_v1.json';RECEIPT=REPORTS/'phase7_3_3_d_multi_claim_successor_type_metadata_review_v2_entry_receipt_v1.json';STATE_OUT=PATTERN/'phase7_3_3_d_support_stage_state_v41.json';READY_OUT=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v52.json'
NEXT='construct_multi_claim_successor_type_metadata_review_v2'
EXPECTED={STATE_IN:'5a9b158c5b147193ecfffe94c6bc58c38efe416a1972d61a026108524c837101',READY_IN:'7ce8289a8b1c17f764843fed99f1f1f004fb9c5de8afd42fcaf5f5b3ca146d57',NEG:'a204992d8b72f7220dc5cb7169b6c2096efd0f73e723a55cfa70d25549df12cf',A_SUB:'96cb3352fc8a2231b44b07ba57cb8981a6a711da73aff219b1958def796b0a44',V1_PROTOCOL:'75a151448ddafeed4b06a4cf22156d9569c7220c54b9ac5feb50f2d45c10bbe9',V1_POLICY:'bc66885edea87e79525eb8cfca7cd07ab4cb054ebf003f857e1f36df0fb3c9ff'}
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def jb(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def rel(p):return p.relative_to(ROOT).as_posix()
def once(p,x):
 b=jb(x)
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_artifact_mismatch:'+rel(p))
  return sha(p)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return hb(b)
def documents():
 n=load(NEG)
 classification={'schema_version':1,'classification_id':'phase7.3.3-d-multi-claim-successor-type-metadata-reviewer-b-failure-classification-v1','status':'frozen_authoritative_negative_result','reviewer':'b','negative_result_sha256':sha(NEG),'primary_failure_level':'level_1_provider_output_representation_contract','failure_subclass':'serialization_failure_invalid_incomplete_json','failure_code':n['failure_code'],'response_received':True,'boundary_capability_conclusion_authorized':False,'type_metadata_capability_conclusion_authorized':False,'same_version_retry_authorized':False,'reviewer_a_v1_submission_preserved':True,'reviewer_b_v1_submission_created':False}
 entry={'schema_version':1,'protocol_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-v2-entry-protocol-v1','status':'frozen_after_v1_authoritative_negative_before_v2_provider_call','predecessor_protocol_sha256':sha(V1_PROTOCOL),'failure_classification_sha256':hb(jb(classification)),'controlled_hypothesis':'long copied claim identifiers and free object serialization may be a representation bottleneck','v2_single_changed_factor':'output representation','v2_representation':{'model_returns_short_claim_index':True,'adapter_maps_claim_index_to_frozen_claim_id':True,'model_copies_claim_id':False,'model_copies_excerpt':False},'semantic_invariants':['same frozen boundary reference','same claim_role enum','same claim_type enum','same reviewer models','same provider','same blind inputs','same case isolation'],'reviewer_a_v1_reused':False,'reason':'both reviewers must be measured under the same v2 representation','same_version_retry':False,'new_version_authorized':True,'next_authorized_stage':NEXT}
 manifest={'schema_version':1,'manifest_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-v2-entry-manifest-v1','status':'frozen','adapter_sha256':sha(SELF),'input_sha256':{rel(p):sha(p) for p in EXPECTED},'classification_sha256':hb(jb(classification)),'entry_protocol_sha256':hb(jb(entry)),'provider_called':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':NEXT}
 return classification,entry,manifest
def preflight():
 missing=[rel(p) for p in EXPECTED if not p.exists()];bad={rel(p):{'expected':d,'actual':sha(p)} for p,d in EXPECTED.items() if p.exists() and sha(p)!=d};s=load(STATE_IN) if STATE_IN.exists() else {};r=load(READY_IN) if READY_IN.exists() else {};n=load(NEG) if NEG.exists() else {}
 checks={'inputs':not missing,'hashes':not bad,'state_blocked':s.get('next_authorized_stage')=='blocked_authoritative_negative_result','readiness_blocked':r.get('next_authorized_stage')=='blocked_authoritative_negative_result','negative_authoritative':n.get('status')=='authoritative_negative_result' and n.get('same_version_retry_authorized') is False,'response_received':n.get('response_received') is True,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False,'runtime_unauthorized':s.get('runtime_integration_authorized') is False};failed=[k for k,v in checks.items() if not v];return {'status':'PASS' if not failed else 'FAIL','failed':failed,'missing':missing,'mismatch':bad}
def run():
 if preflight()['status']!='PASS':raise ValueError('preflight_failed')
 classification,entry,manifest=documents();csha=once(CLASS,classification);esha=once(ENTRY,entry);msha=once(MANIFEST,manifest)
 line={'multi_claim_successor_type_metadata_reviewer_b_failure_classification_v1_sha256':csha,'multi_claim_successor_type_metadata_review_v2_entry_protocol_v1_sha256':esha,'multi_claim_successor_type_metadata_review_v2_entry_manifest_v1_sha256':msha}
 s=copy.deepcopy(load(STATE_IN));r=copy.deepcopy(load(READY_IN));s.setdefault('artifact_lineage',{}).update(line);r.setdefault('artifact_lineage',{}).update(line)
 s.update({'schema_version':41,'state_id':'phase7.3.3-d-support-stage-state-v41','status':'multi_claim_successor_type_metadata_review_v2_authorized','next_authorized_stage':NEXT,'successor_type_metadata_review_v1_authoritative_negative_preserved':True,'successor_type_metadata_review_v2_authorized':True,'successor_type_metadata_review_v2_provider_called':False,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False})
 r.update({'schema_version':52,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v52','status':'multi_claim_successor_type_metadata_review_v2_authorized','next_authorized_stage':NEXT,'successor_type_metadata_review_v1_authoritative_negative_preserved':True,'successor_type_metadata_review_v2_authorized':True,'successor_type_metadata_review_v2_provider_called':False,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False})
 ssha=once(STATE_OUT,s);rsha=once(READY_OUT,r);receipt={'schema_version':1,'receipt_id':'phase7.3.3-d-multi-claim-successor-type-metadata-review-v2-entry-receipt-v1','status':'PASS','classification_sha256':csha,'entry_protocol_sha256':esha,'entry_manifest_sha256':msha,'state_sha256':ssha,'readiness_sha256':rsha,'provider_called':False,'next_authorized_stage':NEXT};rcsha=once(RECEIPT,receipt)
 return {'status':'PASS','failure_classification':'serialization_failure_invalid_incomplete_json','same_version_retry_authorized':False,'v2_authorized':True,'receipt_sha256':rcsha,'state_sha256':ssha,'readiness_sha256':rsha,'next_authorized_stage':NEXT}
def verify():
 classification,entry,manifest=documents();expected={CLASS:classification,ENTRY:entry,MANIFEST:manifest};checks={rel(p):p.exists() and p.read_bytes()==jb(x) for p,x in expected.items()};checks.update({'receipt':RECEIPT.exists() and load(RECEIPT).get('status')=='PASS','state':STATE_OUT.exists() and load(STATE_OUT).get('next_authorized_stage')==NEXT,'readiness':READY_OUT.exists() and load(READY_OUT).get('next_authorized_stage')==NEXT});failed=[k for k,v in checks.items() if not v];return {'status':'PASS' if not failed else 'FAIL','checks':len(checks),'failed':failed}
def main():
 p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args();x=preflight() if a.preflight else run() if a.execute else verify();print(json.dumps(x,ensure_ascii=False,indent=2));return 0 if x['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
