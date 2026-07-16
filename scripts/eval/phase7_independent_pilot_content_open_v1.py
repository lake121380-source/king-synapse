#!/usr/bin/env python3
"""Open only the frozen selected Pilot content and construct blind Reference packets."""
from __future__ import annotations
import argparse, copy, hashlib, json, tempfile, tomllib
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'crates/eval/config'; DATA=ROOT/'crates/eval/datasets'; PATTERN=DATA/'pattern_extraction'; REPORTS=ROOT/'crates/eval/reports'
SOURCE=DATA/'memory_intelligence/agent_memory_benchmark.toml'
WORKLIST=PATTERN/'phase7_3_3_d_independent_pilot_selected_worklist_v1.json'
SAMPLING_RECEIPT=REPORTS/'phase7_3_3_d_independent_pilot_sampling_freeze_receipt_v1.json'
POLICY=CONFIG/'phase7_3_3_d_independent_reference_policy_v1.json'
STATE_IN=PATTERN/'phase7_3_3_d_support_stage_state_v14.json'; READY_IN=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v25.json'
PROTOCOL=CONFIG/'phase7_3_3_d_independent_pilot_content_open_protocol_v1.json'
DATASET=PATTERN/'phase7_3_3_d_independent_pilot_selected_dataset_v1.json'
PACKET_A=PATTERN/'phase7_3_3_d_independent_pilot_reference_reviewer_a_packet_v1.json'
PACKET_B=PATTERN/'phase7_3_3_d_independent_pilot_reference_reviewer_b_packet_v1.json'
TEMPLATE_A=PATTERN/'phase7_3_3_d_independent_pilot_reference_reviewer_a_submission_template_v1.json'
TEMPLATE_B=PATTERN/'phase7_3_3_d_independent_pilot_reference_reviewer_b_submission_template_v1.json'
FIXTURES=REPORTS/'phase7_3_3_d_independent_pilot_content_open_contract_fixtures_v1.json'
MANIFEST=REPORTS/'phase7_3_3_d_independent_pilot_content_open_manifest_v1.json'
RECEIPT=REPORTS/'phase7_3_3_d_independent_pilot_content_open_receipt_v1.json'
OUTCOME=REPORTS/'phase7_3_3_d_independent_pilot_content_open_outcome_v1.json'
STATE_OUT=PATTERN/'phase7_3_3_d_support_stage_state_v15.json'; READY_OUT=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v26.json'

def shab(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha(p:Path)->str:return shab(p.read_bytes())
def cb(v:Any)->bytes:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def csha(v:Any)->str:return shab(cb(v))
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8-sig'))
def write_once(p:Path,v:Any)->str:
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return shab(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p);return shab(b)

def protocol_doc():
 return {'schema_version':1,'protocol_id':'phase7.3.3-d-independent-pilot-content-open-protocol-v1','status':'frozen_by_adapter','entry_gate':{'sampling_frame_frozen':True,'selected_ids_hashes_frozen':True,'next_authorized_stage':'open_independent_pilot_selected_content_v1'},'scope':{'open_selected_count':40,'unselected_content_opened':False,'confirmatory_content_opened':False},'source_mapping':{'candidate_text':'scenario.expected_reason','query_context':'scenario.query','evidence_bundle':'scenario.memory','forbidden_fields':['expected_top','intervention_required','expected_reason_as_reference','historical_outcomes','route_a_gold','arm_outputs']},'reference_blinding':{'reviewer_packets_identical_except_reviewer_identity':True,'other_reviewer_visible':False,'route_a_gold_visible':False,'arm_outputs_visible':False,'historical_labels_visible':False},'lineage':{'candidate_hash_replay':True,'evidence_hash_replay':True,'source_identity_replay':True},'provider_called':False,'runtime_integration_authorized':False}

def verify_inputs():
 for p in [SOURCE,WORKLIST,SAMPLING_RECEIPT,POLICY,STATE_IN,READY_IN]:
  if not p.exists():raise FileNotFoundError(p)
 w=load(WORKLIST);s=load(STATE_IN);r=load(READY_IN)
 if w.get('status')!='frozen_ids_hashes_content_sealed' or w.get('selected_count')!=40:raise ValueError('worklist_gate_invalid')
 if s.get('next_authorized_stage')!='open_independent_pilot_selected_content_v1' or r.get('next_authorized_stage')!='open_independent_pilot_selected_content_v1':raise ValueError('state_gate_invalid')
 return {'status':'PASS','selected_count':40,'provider_called':False,'confirmatory_opened':False}

def build_cases():
 w=load(WORKLIST); source=tomllib.loads(SOURCE.read_text(encoding='utf-8'))
 by={x['id']:x for x in source['scenario']}; cases=[]
 for item in sorted(w['items'],key=lambda x:x['pilot_index']):
  s=by.get(item['candidate_id'])
  if s is None:raise ValueError(f'selected_id_missing:{item["candidate_id"]}')
  candidate=s['expected_reason']; evidence=s['memory']
  if shab(candidate.encode())!=item['candidate_sha256']:raise ValueError(f'candidate_hash_mismatch:{item["candidate_id"]}')
  if csha(evidence)!=item['evidence_bundle_sha256']:raise ValueError(f'evidence_hash_mismatch:{item["candidate_id"]}')
  normalized=[]
  for index,m in enumerate(evidence,start=1):
   normalized.append({'evidence_id':f'{item["candidate_id"]}-evidence-{index:02d}','source_index':index-1,'content':m['content'],'kind':m['kind'],'confidence':m['confidence'],'importance':m['importance'],'recently_accessed':m['recently_accessed'],'relevant':m['relevant'],'turn':m['turn'],'role':m['role']})
  cases.append({'pilot_index':item['pilot_index'],'case_id':item['candidate_id'],'source_identity':item['source_identity'],'domain':item['domain'],'source_family':item['source_family'],'candidate_sha256':item['candidate_sha256'],'source_evidence_bundle_sha256':item['evidence_bundle_sha256'],'candidate_text':candidate,'query_context':s['query'],'evidence_bundle':normalized,'normalized_evidence_bundle_sha256':csha(normalized),'valid_evidence_ids':[x['evidence_id'] for x in normalized]})
 return cases

def template(reviewer:str,cases:list[dict[str,Any]]):
 return {'schema_version':1,'submission_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{reviewer}-submission-v1','status':'template_not_executed','reviewer':reviewer,'case_count':len(cases),'cases':[{'case_id':c['case_id'],'claims':[],'explicit_non_claim_spans':[],'candidate_reference_label':None,'material_error_spans':[],'case_review_complete':False} for c in cases], 'other_reviewer_visible':False,'arm_outputs_visible':False,'route_a_gold_visible':False}

def fixtures(cases):
 ids=[c['case_id'] for c in cases]
 tests=[('selected_count',len(cases)==40),('unique_case_ids',len(ids)==len(set(ids))),('candidate_hash_replay',all(shab(c['candidate_text'].encode())==c['candidate_sha256'] for c in cases)),('evidence_ids_unique',all(len(c['valid_evidence_ids'])==len(set(c['valid_evidence_ids'])) for c in cases)),('six_evidence_items',all(len(c['evidence_bundle'])==6 for c in cases)),('forbidden_expected_top_absent',all('expected_top' not in c for c in cases)),('arm_outputs_absent',all(not any(k in c for k in ['candidate_arm','atomic_arm','arm_metrics']) for c in cases)),('route_a_gold_absent',all(not any(k in c for k in ['boundary_gold','support_gold','historical_label']) for c in cases))]
 return [{'fixture_id':n,'status':'PASS' if ok else 'FAIL'} for n,ok in tests]

def outputs():
 verify_inputs(); cases=build_cases(); fs=fixtures(cases)
 if any(x['status']!='PASS' for x in fs):raise ValueError('fixture_failure')
 protocol=protocol_doc()
 dataset={'schema_version':1,'dataset_id':'phase7.3.3-d-independent-pilot-selected-dataset-v1','status':'selected_content_open_reference_only_arms_sealed','source_dataset_path':str(SOURCE.relative_to(ROOT)).replace('\\','/'),'source_dataset_sha256':sha(SOURCE),'selected_worklist_sha256':sha(WORKLIST),'case_count':len(cases),'cases':cases,'unselected_content_opened':False,'confirmatory_content_opened':False,'arm_outputs_present':False}
 def packet(r):return {'schema_version':1,'packet_id':f'phase7.3.3-d-independent-pilot-reference-reviewer-{r}-packet-v1','status':'frozen_blind_packet','reviewer':r,'case_count':len(cases),'cases':cases,'blinding':{'other_reviewer_visible':False,'route_a_boundary_gold_visible':False,'route_a_support_gold_visible':False,'historical_labels_visible':False,'candidate_arm_visible':False,'atomic_arm_visible':False}}
 pa=packet('a');pb=packet('b');ta=template('a',cases);tb=template('b',cases)
 fdoc={'schema_version':1,'fixture_suite_id':'phase7.3.3-d-independent-pilot-content-open-contract-fixtures-v1','status':'PASS','passed':len(fs),'total':len(fs),'fixtures':fs}
 manifest={'schema_version':1,'manifest_id':'phase7.3.3-d-independent-pilot-content-open-manifest-v1','status':'frozen_selected_content_open_reference_packets_ready','frozen_date':'2026-07-15','adapter_path':str(Path(__file__).resolve().relative_to(ROOT)).replace('\\','/'),'adapter_sha256':sha(Path(__file__).resolve()),'inputs':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [SOURCE,WORKLIST,SAMPLING_RECEIPT,POLICY,STATE_IN,READY_IN]},'protocol_canonical_sha256':csha(protocol),'dataset_canonical_sha256':csha(dataset),'packet_a_canonical_sha256':csha(pa),'packet_b_canonical_sha256':csha(pb),'template_a_canonical_sha256':csha(ta),'template_b_canonical_sha256':csha(tb),'fixtures_canonical_sha256':csha(fdoc),'selected_content_opened':True,'unselected_content_opened':False,'confirmatory_content_opened':False,'provider_called':False,'arm_execution_authorized':False}
 state=copy.deepcopy(load(STATE_IN));state.update({'schema_version':15,'state_id':'phase7.3.3-d-support-stage-state-v15','next_authorized_stage':'freeze_independent_pilot_reference_execution_protocol_v1','independent_replication_state':'independent_pilot_selected_content_open_reference_packets_frozen','independent_pilot_dataset_opened':True,'independent_reference_started':False,'independent_dual_arm_execution_started':False,'confirmatory_dataset_opened':False,'provider_called_for_independent_replication':False})
 ready=copy.deepcopy(load(READY_IN));ready.update({'schema_version':26,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v26','status':'independent_pilot_selected_content_open_reference_packets_frozen','next_authorized_stage':'freeze_independent_pilot_reference_execution_protocol_v1','independent_replication_state':'independent_pilot_selected_content_open_reference_packets_frozen','independent_pilot_dataset_opened':True,'independent_reference_started':False,'independent_dual_arm_execution_started':False,'confirmatory_dataset_opened':False,'provider_called_for_independent_replication':False})
 outcome={'schema_version':1,'outcome_id':'phase7.3.3-d-independent-pilot-content-open-outcome-v1','status':'independent_pilot_selected_content_open_reference_packets_frozen','selected_count':len(cases),'candidate_hashes_replayed':len(cases),'evidence_hashes_replayed':len(cases),'unselected_content_opened':False,'confirmatory_content_opened':False,'provider_called':False,'next_authorized_stage':'freeze_independent_pilot_reference_execution_protocol_v1'}
 return {PROTOCOL:protocol,DATASET:dataset,PACKET_A:pa,PACKET_B:pb,TEMPLATE_A:ta,TEMPLATE_B:tb,FIXTURES:fdoc,MANIFEST:manifest,STATE_OUT:state,READY_OUT:ready,OUTCOME:outcome}

def freeze():
 os=outputs();hs={str(p.relative_to(ROOT)).replace('\\','/'):write_once(p,v) for p,v in os.items()};receipt={'schema_version':1,'receipt_id':'phase7.3.3-d-independent-pilot-content-open-receipt-v1','status':'PASS','artifact_sha256':hs,'selected_count':40,'candidate_hashes_replayed':40,'evidence_hashes_replayed':40,'unselected_content_opened':False,'confirmatory_content_opened':False,'provider_called':False};rs=write_once(RECEIPT,receipt);return {'status':'PASS','selected_content_opened':40,'fixtures':'8/8','receipt_sha256':rs,'next':'freeze_independent_pilot_reference_execution_protocol_v1'}
def verify():
 os=outputs();checks=[]
 for p,v in os.items():checks.append(p.exists() and p.read_bytes()==(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
 if RECEIPT.exists():
  for rel,d in load(RECEIPT).get('artifact_sha256',{}).items():checks.append((ROOT/rel).exists() and sha(ROOT/rel)==d)
 else:checks.append(False)
 return {'status':'PASS' if all(checks) else 'FAIL','checks':len(checks),'passed':sum(checks),'confirmatory_content_opened':False,'provider_called':False}
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--verify-inputs',action='store_true');g.add_argument('--run-contract-fixtures',action='store_true');g.add_argument('--freeze',action='store_true');g.add_argument('--verify',action='store_true');a=ap.parse_args()
 if a.verify_inputs:r=verify_inputs()
 elif a.run_contract_fixtures:
  fs=fixtures(build_cases());r={'status':'PASS' if all(x['status']=='PASS' for x in fs) else 'FAIL','passed':sum(x['status']=='PASS' for x in fs),'total':len(fs),'fixtures':fs}
 elif a.freeze:r=freeze()
 else:r=verify()
 print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if r['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
