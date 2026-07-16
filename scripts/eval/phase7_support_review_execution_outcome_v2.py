#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,tempfile
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];CONFIG=ROOT/'crates/eval/config';DATA=ROOT/'crates/eval/datasets/pattern_extraction';REPORTS=ROOT/'crates/eval/reports'
PROTOCOL=CONFIG/'phase7_3_3_d_support_review_execution_protocol_v2.json';POLICY=CONFIG/'phase7_3_3_d_support_review_execution_policy_v2.json';PROMPT=CONFIG/'phase7_3_3_d_support_reviewer_prompt_v1.md';FIXTURES=REPORTS/'phase7_3_3_d_support_review_contract_fixtures_v2.json';AUDIT=REPORTS/'phase7_3_3_d_support_request_configuration_audit_v1.json';PREV_STATE=DATA/'phase7_3_3_d_support_stage_state_v5.json';PREV_READY=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v16.json';GOLD=DATA/'phase7_3_3_d_boundary_gold_v1.json';FREEZE=REPORTS/'phase7_3_3_d_boundary_gold_freeze_receipt_v1.json'
def manifest(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_execution_manifest_v2.json'
def attempts(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_execution_attempts_v2.jsonl'
def submission(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_completed_submission_v2.json'
def result(r):return REPORTS/f'phase7_3_3_d_support_reviewer_{r}_execution_result_v2.json'
OUTCOME=REPORTS/'phase7_3_3_d_support_review_execution_outcome_v2.json';STATE=DATA/'phase7_3_3_d_support_stage_state_v6.json';READY=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v17.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write_once(p,v):
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p)
req=[PROTOCOL,POLICY,PROMPT,FIXTURES,AUDIT,PREV_STATE,PREV_READY,GOLD,FREEZE]+[x(r) for r in ('a','b') for x in (manifest,attempts,submission,result)]
missing=[str(p.relative_to(ROOT)) for p in req if not p.exists()]
if missing:raise ValueError(f'missing:{missing}')
subs={r:load(submission(r)) for r in ('a','b')};results={r:load(result(r)) for r in ('a','b')}
ids={r:[x['boundary_claim_id'] for x in subs[r]['claims']] for r in ('a','b')}
checks={
 'audit_confirmed':load(AUDIT).get('status')=='confirmed_adapter_credential_routing_defect',
 'protocol_v2':load(PROTOCOL).get('protocol_id')=='phase7.3.3-d1-b-independent-support-review-execution-v2',
 'fixtures_14_pass':load(FIXTURES).get('fixture_count')==14 and load(FIXTURES).get('all_fixtures_passed') is True,
 'a_completed':results['a'].get('status')=='completed' and subs['a'].get('completed') is True,
 'b_completed':results['b'].get('status')=='completed' and subs['b'].get('completed') is True,
 'a_118':len(subs['a'].get('claims',[]))==118,
 'b_118':len(subs['b'].get('claims',[]))==118,
 'claim_ids_identical':ids['a']==ids['b'],
 'result_hashes':all(results[r].get('submission_sha256')==sha(submission(r)) for r in ('a','b')),
 'held_out_false':all(subs[r].get('held_out_accessed') is False and results[r].get('held_out_accessed') is False for r in ('a','b')),
 'agreement_not_computed':all(results[r].get('agreement_computed') is False for r in ('a','b')),
 'support_gold_not_frozen':all(results[r].get('support_gold_frozen') is False for r in ('a','b')),
}
if not all(checks.values()):raise ValueError(f'checks_failed:{[k for k,v in checks.items() if not v]}')
reviewers={}
for r in ('a','b'):
 reviewers[r]={'manifest_sha256':sha(manifest(r)),'attempt_log_sha256':sha(attempts(r)),'submission_sha256':sha(submission(r)),'execution_result_sha256':sha(result(r)),'terminal_outcome':'completed','model_requested':results[r]['model_requested'],'canonical_model_family':results[r]['canonical_model_family'],'provider_reported_models':results[r]['provider_reported_models'],'completed_case_count':results[r]['completed_case_count'],'decision_count':results[r]['decision_count'],'support_label_counts':results[r]['support_label_counts'],'confidence_counts':results[r]['confidence_counts'],'held_out_accessed':False}
outcome={'schema_version':2,'outcome_id':'phase7.3.3-d1-b-support-review-execution-outcome-v2','status':'completed_with_two_independent_support_submissions','v1_outcome_preserved':True,'v1_request_configuration_audit_sha256':sha(AUDIT),'controlled_change_from_v1':{'field':'credential_env_name','from':'DEEPSEEK_API_KEY','to':'PHASE7_ATOMIC_JUDGE_API_KEY','provider_base_url_changed':False,'reviewer_models_changed':False,'prompt_changed':False,'packets_changed':False,'boundary_gold_changed':False,'support_contract_changed':False},'protocol_sha256':sha(PROTOCOL),'execution_policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'contract_fixtures_sha256':sha(FIXTURES),'reviewers':reviewers,'completion_checks':checks,'two_completed_support_submissions':True,'support_agreement_allowed':True,'support_agreement_computed':False,'support_adjudication_allowed':False,'support_gold_frozen':False,'held_out_accessed':False,'interpretation':'Correct gateway credential routing allowed both frozen independent reviewers to complete 10/10 cases and 118/118 Support decisions. This authorizes construction and freezing of the Support Agreement protocol; it does not itself establish agreement or Support Gold.','next_required_stage':'freeze_support_agreement_protocol_v1'}
write_once(OUTCOME,outcome)
prev=load(PREV_STATE)
state={
 'schema_version':6,'state_id':'phase7.3.3-d1-b-support-stage-state-v6','boundary_state':'frozen_project_boundary_gold','support_state':'two_independent_support_reviews_completed_v2','blocked_reason':None,
 'boundary_gold_sha256':sha(GOLD),'boundary_gold_freeze_receipt_sha256':sha(FREEZE),'boundary_claim_count':118,
 'support_review_packets_generated':True,'shared_packet_sha256':prev['shared_packet_sha256'],'reviewer_a_packet_sha256':prev['reviewer_a_packet_sha256'],'reviewer_b_packet_sha256':prev['reviewer_b_packet_sha256'],'reviewer_a_submission_template_sha256':prev['reviewer_a_submission_template_sha256'],'reviewer_b_submission_template_sha256':prev['reviewer_b_submission_template_sha256'],
 'support_reviewer_a_completed':True,'support_reviewer_b_completed':True,'support_agreement_available':True,'support_agreement_allowed':True,'support_agreement_computed':False,'support_adjudication_allowed':False,'support_gold_frozen':False,'support_gold_sha256':None,'support_review_allowed':False,'support_review_started':True,'next_authorized_stage':'freeze_support_agreement_protocol_v1','immutable_boundary_claim_fields':prev['immutable_boundary_claim_fields'],'held_out_accessed':False,'provider_called_for_packet_construction':False,'lineage_correction':prev['lineage_correction'],'support_execution_v1':prev['support_execution_v1'],'support_request_configuration_audit_v1_sha256':sha(AUDIT),'support_execution_v2':{'outcome_sha256':sha(OUTCOME),'reviewer_a_submission_sha256':sha(submission('a')),'reviewer_b_submission_sha256':sha(submission('b')),'reviewer_a_result_sha256':sha(result('a')),'reviewer_b_result_sha256':sha(result('b')),'case_count_each':10,'decision_count_each':118,'agreement_computed':False,'support_gold_frozen':False}
}
write_once(STATE,state)
prev_ready=load(PREV_READY)
ready={'schema_version':17,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v17','status':'two_independent_support_reviews_completed_agreement_protocol_authorized','artifact_lineage':{**prev_ready.get('artifact_lineage',{}),'support_request_configuration_audit_v1_sha256':sha(AUDIT),'support_execution_protocol_v2_sha256':sha(PROTOCOL),'support_execution_policy_v2_sha256':sha(POLICY),'support_contract_fixtures_v2_sha256':sha(FIXTURES),'support_reviewer_a_manifest_v2_sha256':sha(manifest('a')),'support_reviewer_b_manifest_v2_sha256':sha(manifest('b')),'support_reviewer_a_submission_v2_sha256':sha(submission('a')),'support_reviewer_b_submission_v2_sha256':sha(submission('b')),'support_execution_outcome_v2_sha256':sha(OUTCOME),'support_stage_state_v6_sha256':sha(STATE)},'reference_status':{'boundary_gold_frozen':True,'boundary_claim_count':118,'reviewer_a_completed':True,'reviewer_b_completed':True,'reviewer_a_decision_count':118,'reviewer_b_decision_count':118,'agreement_available':True,'agreement_computed':False,'support_adjudication_allowed':False,'support_gold_frozen':False},'next_authorized_stage':'freeze_support_agreement_protocol_v1','support_review_allowed':False,'support_agreement_allowed':True,'support_adjudication_allowed':False,'support_gold_frozen':False,'held_out_accessed':False}
write_once(READY,ready)
print(json.dumps({'status':outcome['status'],'outcome_sha256':sha(OUTCOME),'state_v6_sha256':sha(STATE),'readiness_v17_sha256':sha(READY),'reviewer_a_labels':reviewers['a']['support_label_counts'],'reviewer_b_labels':reviewers['b']['support_label_counts'],'next_authorized_stage':ready['next_authorized_stage']},indent=2))
