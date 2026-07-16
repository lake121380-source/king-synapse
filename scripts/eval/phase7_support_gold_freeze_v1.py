#!/usr/bin/env python3
"""Deterministic Phase 7.3.3-D4 Support Gold Freeze Gate v1."""
from __future__ import annotations
import argparse, hashlib, json, tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]; CONFIG=ROOT/'crates/eval/config'; DATA=ROOT/'crates/eval/datasets/pattern_extraction'; REPORTS=ROOT/'crates/eval/reports'
PROTOCOL=CONFIG/'phase7_3_3_d_support_gold_freeze_protocol_v1.json'
BOUNDARY_GOLD=DATA/'phase7_3_3_d_boundary_gold_v1.json'
REVIEWER_A=REPORTS/'phase7_3_3_d_support_reviewer_a_completed_submission_v2.json'; REVIEWER_B=REPORTS/'phase7_3_3_d_support_reviewer_b_completed_submission_v2.json'
AGREEMENT=REPORTS/'phase7_3_3_d_support_agreement_report_v1.json'
ADJ_SUB=REPORTS/'phase7_3_3_d_support_adjudication_submission_v1.json'; ADJ_RESULT=REPORTS/'phase7_3_3_d_support_adjudication_execution_result_v1.json'
STATE_V9=DATA/'phase7_3_3_d_support_stage_state_v9.json'; READINESS_V20=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v20.json'
FIXTURES=REPORTS/'phase7_3_3_d_support_gold_freeze_contract_fixtures_v1.json'; MANIFEST=REPORTS/'phase7_3_3_d_support_gold_freeze_manifest_v1.json'
SUPPORT_GOLD=DATA/'phase7_3_3_d_support_gold_v1.json'; RECEIPT=REPORTS/'phase7_3_3_d_support_gold_freeze_receipt_v1.json'; OUTCOME=REPORTS/'phase7_3_3_d_support_gold_freeze_outcome_v1.json'
STATE_V10=DATA/'phase7_3_3_d_support_stage_state_v10.json'; READINESS_V21=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v21.json'
ALLOWED={'supported','partially_supported','unsupported','not_assessable'}; EXPECTED_COUNTS={'supported':86,'partially_supported':26,'unsupported':6}

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def csha(v:Any)->str:return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8-sig'))
def once(p:Path,v:Any)->str:
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode(); h=hashlib.sha256(b).hexdigest()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return h
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return h

def unique(items,key,name):
 out={}
 for x in items:
  i=x.get(key)
  if not isinstance(i,str) or not i:raise ValueError(f'{name}_missing_or_invalid_id')
  if i in out:raise ValueError(f'duplicate_{name}_id:{i}')
  out[i]=x
 return out

def resolve(boundary,a,b,adj):
 cid=boundary.get('boundary_claim_id')
 if a.get('boundary_claim_id')!=cid or b.get('boundary_claim_id')!=cid:raise ValueError(f'claim_identity_mismatch:{cid}')
 la,lb=a.get('support_label'),b.get('support_label')
 if la not in ALLOWED or lb not in ALLOWED:raise ValueError(f'invalid_reviewer_label:{cid}')
 out=dict(boundary);out.update({'reviewer_a_label':la,'reviewer_b_label':lb,'diagnostic_annotation_gold_status':'not_gold_raw_reviewer_or_adjudication_provenance_only'})
 if la==lb:
  if adj is not None:raise ValueError(f'unexpected_adjudication_for_exact_agreement:{cid}')
  out.update({'support_label':la,'label_resolution_method':'exact_reviewer_agreement','adjudication_item_id':None,'adjudication_operation':None,'selected_source_reviewer':None,'selected_frozen_decision_sha256':None,'selected_frozen_decision':None,'adjudicator_rationale':None});return out
 if adj is None:raise ValueError(f'missing_adjudication_for_disagreement:{cid}')
 if adj.get('boundary_claim_id')!=cid:raise ValueError(f'adjudication_claim_identity_mismatch:{cid}')
 if adj.get('operation')=='defer_for_human_review' or adj.get('status')!='selected_frozen_reviewer_decision':raise ValueError(f'defer_or_nonselected_adjudication_rejected:{cid}')
 if adj.get('operation') not in {'select_option_1','select_option_2'}:raise ValueError(f'invalid_adjudication_operation:{cid}')
 if adj.get('final_label_authorized') is not True:raise ValueError(f'final_label_not_authorized:{cid}')
 if adj.get('boundary_mutation_performed') is not False or adj.get('reviewer_submission_mutation_performed') is not False:raise ValueError(f'mutation_detected:{cid}')
 who=adj.get('selected_source_reviewer');src=a if who=='reviewer_a' else b if who=='reviewer_b' else None
 if src is None:raise ValueError(f'invalid_selected_source_reviewer:{cid}')
 selected=adj.get('selected_frozen_decision')
 if not isinstance(selected,dict):raise ValueError(f'selected_frozen_decision_missing:{cid}')
 if selected.get('support_label') not in {la,lb}:raise ValueError(f'new_or_third_label_not_allowed:{cid}')
 if selected!=src:raise ValueError(f'selected_decision_replay_mismatch:{cid}')
 h=csha(selected)
 if adj.get('selected_frozen_decision_sha256')!=h:raise ValueError(f'selected_decision_hash_mismatch:{cid}')
 out.update({'support_label':selected['support_label'],'label_resolution_method':'adjudicated_frozen_reviewer_selection','adjudication_item_id':adj.get('adjudication_item_id'),'adjudication_operation':adj.get('operation'),'selected_source_reviewer':who,'selected_frozen_decision_sha256':h,'selected_frozen_decision':selected,'adjudicator_rationale':adj.get('adjudicator_rationale')});return out

def merge(boundaries,aclaims,bclaims,adjs,heldout=False):
 if heldout:raise ValueError('held_out_access_rejected')
 ids=[x.get('boundary_claim_id') for x in boundaries];aids=[x.get('boundary_claim_id') for x in aclaims];bids=[x.get('boundary_claim_id') for x in bclaims]
 if len(ids)!=len(set(ids)):raise ValueError('duplicate_boundary_claim_id')
 if aids!=ids:raise ValueError('reviewer_a_boundary_order_drift')
 if bids!=ids:raise ValueError('reviewer_b_boundary_order_drift')
 A=unique(aclaims,'boundary_claim_id','reviewer_a_claim');B=unique(bclaims,'boundary_claim_id','reviewer_b_claim');J=unique(adjs,'boundary_claim_id','adjudication_claim')
 agree={i for i in ids if A[i].get('support_label')==B[i].get('support_label')};disagree=set(ids)-agree
 if set(J)!=disagree:raise ValueError(f'agreement_adjudication_partition_mismatch:missing={sorted(disagree-set(J))}:unexpected={sorted(set(J)-disagree)}')
 merged=[resolve(x,A[x['boundary_claim_id']],B[x['boundary_claim_id']],J.get(x['boundary_claim_id'])) for x in boundaries]
 return merged,{'claim_count':len(merged),'exact_reviewer_agreement_count':len(agree),'adjudicated_disagreement_count':len(disagree),'label_counts':dict(sorted(Counter(x['support_label'] for x in merged).items())),'resolution_counts':dict(sorted(Counter(x['label_resolution_method'] for x in merged).items()))}

def fd(cid,label,r='fixture'):return {'boundary_claim_id':cid,'support_label':label,'cited_evidence_ids':[],'reason_codes':['direct_evidence_match'],'support_rationale':r,'annotation_confidence':'high'}
def fa(cid,selected,who='reviewer_a'):return {'adjudication_item_id':'fixture-'+cid,'boundary_claim_id':cid,'operation':'select_option_1','adjudicator_rationale':'fixture selection','final_label_authorized':True,'boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False,'selected_source_reviewer':who,'selected_frozen_decision':selected,'selected_frozen_decision_sha256':csha(selected),'status':'selected_frozen_reviewer_decision'}
def fx(name,accept,fn):
 actual=True;err=None
 try:fn()
 except ValueError as e:actual=False;err=str(e)
 return {'fixture_id':name,'expected':'accept' if accept else 'reject','actual':'accept' if actual else 'reject','observed_error':err,'passed':actual==accept}

def fixture_result():
 b=[{'boundary_claim_id':'c1'}];a=[fd('c1','supported','a')];same=[fd('c1','supported','b')];partial=[fd('c1','partially_supported','b')];valid=[fa('c1',a[0])];items=[]
 items+=[fx('exact_agreement_accepted',True,lambda:merge(b,a,a,[])),fx('diagnostic_only_disagreement_with_same_label_accepted',True,lambda:merge(b,a,same,[])),fx('valid_adjudicated_selection_accepted',True,lambda:merge(b,a,partial,valid)),fx('missing_adjudication_rejected',False,lambda:merge(b,a,partial,[]))]
 defer=fa('c1',a[0]);defer.update({'operation':'defer_for_human_review','status':'deferred_for_human_review','final_label_authorized':False});items.append(fx('defer_rejected',False,lambda:merge(b,a,partial,[defer])))
 third=fa('c1',fd('c1','not_assessable','third'));items.append(fx('third_or_new_label_rejected',False,lambda:merge(b,a,partial,[third])))
 db=[{'boundary_claim_id':'c1'},{'boundary_claim_id':'c1'}];da=[fd('c1','supported'),fd('c1','supported')];items.append(fx('duplicate_claim_id_rejected',False,lambda:merge(db,da,da,[])))
 b2=[{'boundary_claim_id':'c1'},{'boundary_claim_id':'c2'}];drift=[fd('c2','supported'),fd('c1','supported')];ok2=[fd('c1','supported'),fd('c2','supported')];items.append(fx('boundary_order_drift_rejected',False,lambda:merge(b2,drift,ok2,[])))
 bad=fa('c1',a[0]);bad['selected_frozen_decision']=dict(a[0],support_rationale='mutated');bad['selected_frozen_decision_sha256']=csha(bad['selected_frozen_decision']);items.append(fx('selected_decision_replay_mismatch_rejected',False,lambda:merge(b,a,partial,[bad])))
 items.append(fx('held_out_flag_rejected',False,lambda:merge(b,a,a,[],heldout=True)))
 b3=[{'boundary_claim_id':x} for x in ('c1','c2','c3')];a3=[fd('c1','supported','same'),fd('c2','supported','a diag'),fd('c3','unsupported','a')];b3r=[fd('c1','supported','same'),fd('c2','supported','b diag'),fd('c3','partially_supported','b')];j3=[fa('c3',b3r[2],'reviewer_b')];items.append(fx('complete_partition_accepted',True,lambda:merge(b3,a3,b3r,j3)))
 passed=all(x['passed'] for x in items);return {'schema_version':1,'fixture_suite_id':'phase7.3.3-d4-support-gold-freeze-contract-fixtures-v1','status':'all_contract_fixtures_passed' if passed else 'contract_fixture_failure','protocol_sha256':sha(PROTOCOL),'adapter_sha256':sha(Path(__file__)),'fixture_count':len(items),'passed_count':sum(x['passed'] for x in items),'failed_count':sum(not x['passed'] for x in items),'fixtures':items,'provider_called':False,'held_out_accessed':False}

def validate_inputs():
 required=(PROTOCOL,BOUNDARY_GOLD,REVIEWER_A,REVIEWER_B,AGREEMENT,ADJ_SUB,ADJ_RESULT,STATE_V9,READINESS_V20,FIXTURES)
 for p in required:
  if not p.is_file():raise ValueError(f'required_frozen_input_missing:{p.relative_to(ROOT)}')
 protocol=load(PROTOCOL);g=load(BOUNDARY_GOLD);a=load(REVIEWER_A);b=load(REVIEWER_B);r=load(AGREEMENT);s=load(ADJ_SUB);x=load(ADJ_RESULT);state=load(STATE_V9);ready=load(READINESS_V20);fixtures=load(FIXTURES)
 gc=g.get('claims',[]);ac=a.get('claims',[]);bc=b.get('claims',[]);js=s.get('adjudications',[])
 held=any([g.get('held_out_accessed'),a.get('held_out_accessed'),b.get('held_out_accessed'),r.get('guards',{}).get('held_out_accessed'),s.get('held_out_accessed'),x.get('held_out_accessed'),state.get('held_out_accessed'),ready.get('held_out_accessed')])
 merged,summary=merge(gc,ac,bc,js,heldout=held)
 ids=[z['boundary_claim_id'] for z in gc];disagree={aa['boundary_claim_id'] for aa,bb in zip(ac,bc) if aa['support_label']!=bb['support_label']};jids={z['boundary_claim_id'] for z in js};rids={z['boundary_claim_id'] for z in x.get('case_results',[])}
 la=r.get('label_agreement',{});line=r.get('artifact_lineage',{});rl=ready.get('artifact_lineage',{})
 checks={
  'protocol_is_frozen_offline_deterministic':protocol.get('status')=='frozen_before_execution' and protocol.get('execution_mode')=='offline_deterministic',
  'protocol_freezes_only_support_label_as_gold':protocol.get('gold_measurement_fields')==['support_label'],
  'protocol_disallows_provider_and_held_out':protocol.get('execution_guards',{}).get('provider_call_allowed') is False and protocol.get('execution_guards',{}).get('held_out_access_allowed') is False,
  'fixtures_all_passed_and_current':fixtures.get('status')=='all_contract_fixtures_passed' and fixtures.get('fixture_count')==fixtures.get('passed_count')==11 and fixtures.get('failed_count')==0 and fixtures.get('protocol_sha256')==sha(PROTOCOL) and fixtures.get('adapter_sha256')==sha(Path(__file__)),
  'boundary_gold_frozen_118':g.get('status')=='frozen_project_boundary_gold' and g.get('support_labels_present') is False and g.get('boundary_claim_count')==len(gc)==118,
  'boundary_ids_unique_ordered':len(ids)==len(set(ids))==118,
  'reviewer_a_completed_118':a.get('completed') is True and a.get('reviewer_id')=='reviewer_a' and a.get('support_decision_count')==len(ac)==118,
  'reviewer_b_completed_118':b.get('completed') is True and b.get('reviewer_id')=='reviewer_b' and b.get('support_decision_count')==len(bc)==118,
  'reviewer_boundary_hashes_match':a.get('boundary_gold_sha256')==sha(BOUNDARY_GOLD) and b.get('boundary_gold_sha256')==sha(BOUNDARY_GOLD),
  'reviewer_ids_and_order_match_boundary':[z['boundary_claim_id'] for z in ac]==ids and [z['boundary_claim_id'] for z in bc]==ids,
  'reviewer_submissions_blind':a.get('blind_to_other_reviewer') is True and b.get('blind_to_other_reviewer') is True,
  'agreement_completed_92_26':r.get('status')=='completed_support_agreement_analysis' and r.get('claim_count')==118 and la.get('exact_agreement_count')==92 and la.get('disagreement_count')==26,
  'agreement_lineage_matches_inputs':line.get('boundary_gold')==sha(BOUNDARY_GOLD) and line.get('reviewer_a_submission')==sha(REVIEWER_A) and line.get('reviewer_b_submission')==sha(REVIEWER_B),
  'agreement_guards_clean':r.get('guards',{}).get('raw_independent_submissions_only') is True and r.get('guards',{}).get('support_gold_generated') is False and r.get('guards',{}).get('support_gold_visible') is False,
  'adjudication_submission_complete_26_no_defer':s.get('status')=='completed_with_no_deferrals' and s.get('item_count')==s.get('selected_count')==len(js)==26 and s.get('deferred_count')==0,
  'adjudication_result_complete_and_authorizes_freeze':x.get('status')=='completed' and x.get('successful_item_count')==x.get('selected_count')==26 and x.get('deferred_count')==0 and x.get('support_adjudication_completed') is True and x.get('support_gold_freeze_protocol_allowed') is True,
  'adjudication_result_submission_hash_matches':x.get('submission_sha256')==sha(ADJ_SUB),
  'agreement_and_adjudication_exact_partition':len(disagree)==26 and disagree==jids==rids,
  'selected_decisions_replay_exactly':all(z.get('selected_frozen_decision_sha256')==csha(z.get('selected_frozen_decision')) for z in js),
  'no_boundary_or_reviewer_mutation':s.get('boundary_mutation_performed') is False and s.get('reviewer_submission_mutation_performed') is False,
  'diagnostic_followups_not_processed':s.get('diagnostic_followup_items_processed')==0 and state.get('diagnostic_followup_items_processed')==0 and ready.get('diagnostic_followup_items_processed')==0,
  'state_v9_authorizes_d4':state.get('support_state')=='support_adjudication_completed' and state.get('support_gold_freeze_protocol_allowed') is True and state.get('support_gold_frozen') is False and state.get('next_authorized_stage')=='freeze_support_gold_protocol_v1',
  'state_v9_hashes_match':state.get('boundary_gold_sha256')==sha(BOUNDARY_GOLD) and state.get('support_adjudication_submission_sha256')==sha(ADJ_SUB) and state.get('support_adjudication_result_sha256')==sha(ADJ_RESULT),
  'readiness_v20_authorizes_d4':ready.get('status')=='support_adjudication_completed_support_gold_protocol_authorized' and ready.get('support_gold_freeze_protocol_allowed') is True and ready.get('support_gold_frozen') is False and ready.get('next_authorized_stage')=='freeze_support_gold_protocol_v1',
  'readiness_v20_lineage_matches':rl.get('state_v9_sha256')==sha(STATE_V9) and rl.get('submission_sha256')==sha(ADJ_SUB) and rl.get('result_sha256')==sha(ADJ_RESULT),
  'reconstructed_partition_is_118':summary.get('claim_count')==118 and summary.get('exact_reviewer_agreement_count')==92 and summary.get('adjudicated_disagreement_count')==26,
  'reconstructed_label_counts_match_cross_check':summary.get('label_counts')==EXPECTED_COUNTS,
  'no_held_out_access':not held,
 }
 fail=[k for k,v in checks.items() if not v]
 if fail:raise ValueError('support_gold_freeze_input_validation_failed:'+','.join(fail))
 return {'protocol':protocol,'boundary_gold':g,'reviewer_a':a,'reviewer_b':b,'agreement':r,'adjudication_submission':s,'adjudication_result':x,'state_v9':state,'readiness_v20':ready,'fixtures':fixtures},{'checks':checks,'merged_claims':merged,'merge_summary':summary,'boundary_ids':ids,'disagreement_ids':sorted(disagree)}

def build_gold(inp,ctx,mh):
 g=inp['boundary_gold'];s=ctx['merge_summary']
 return {'schema_version':1,'support_gold_id':'phase7.3.3-d4-project-support-gold-v1','status':'frozen_project_support_gold','reference_status':'project_support_gold_model_adjudicated_not_human_gold','freeze_manifest_sha256':mh,'artifact_lineage':{'support_gold_freeze_protocol_sha256':sha(PROTOCOL),'support_gold_freeze_contract_fixtures_sha256':sha(FIXTURES),'boundary_gold_sha256':sha(BOUNDARY_GOLD),'reviewer_a_submission_sha256':sha(REVIEWER_A),'reviewer_b_submission_sha256':sha(REVIEWER_B),'support_agreement_report_sha256':sha(AGREEMENT),'support_adjudication_submission_sha256':sha(ADJ_SUB),'support_adjudication_result_sha256':sha(ADJ_RESULT),'support_stage_state_v9_sha256':sha(STATE_V9),'readiness_v20_sha256':sha(READINESS_V20)},'case_count':g['case_count'],'claim_count':s['claim_count'],'exact_reviewer_agreement_count':s['exact_reviewer_agreement_count'],'adjudicated_disagreement_count':s['adjudicated_disagreement_count'],'deferred_count':0,'label_counts':s['label_counts'],'resolution_counts':s['resolution_counts'],'gold_fields':['support_label'],'diagnostic_fields_gold_status':inp['protocol']['diagnostic_fields_gold_status'],'boundary_claim_fields_immutable':g['boundary_claim_fields_immutable'],'claims':ctx['merged_claims'],'support_gold_frozen':True,'boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False,'diagnostic_followup_items_processed':0,'provider_called_for_freeze':False,'held_out_accessed':False}

def expected_manifest():
 inp,ctx=validate_inputs();sources={'adapter':Path(__file__),'protocol':PROTOCOL,'contract_fixtures':FIXTURES,'boundary_gold':BOUNDARY_GOLD,'reviewer_a_submission':REVIEWER_A,'reviewer_b_submission':REVIEWER_B,'support_agreement_report':AGREEMENT,'support_adjudication_submission':ADJ_SUB,'support_adjudication_result':ADJ_RESULT,'support_stage_state_v9':STATE_V9,'readiness_v20':READINESS_V20}
 return {'schema_version':1,'manifest_id':'phase7.3.3-d4-support-gold-freeze-manifest-v1','status':'frozen_not_started','execution_mode':'offline_deterministic','artifact_lineage':{k+'_sha256':sha(v) for k,v in sources.items()},'validated_case_count':inp['boundary_gold']['case_count'],'validated_claim_count':ctx['merge_summary']['claim_count'],'validated_exact_reviewer_agreement_count':ctx['merge_summary']['exact_reviewer_agreement_count'],'validated_adjudicated_disagreement_count':ctx['merge_summary']['adjudicated_disagreement_count'],'validated_deferred_count':0,'reconstructed_label_counts':ctx['merge_summary']['label_counts'],'entry_gate_checks':ctx['checks'],'expected_outputs':{'support_gold':SUPPORT_GOLD.relative_to(ROOT).as_posix(),'freeze_receipt':RECEIPT.relative_to(ROOT).as_posix(),'freeze_outcome':OUTCOME.relative_to(ROOT).as_posix(),'support_stage_state_v10':STATE_V10.relative_to(ROOT).as_posix(),'readiness_v21':READINESS_V21.relative_to(ROOT).as_posix()},'gold_fields':['support_label'],'provider_call_allowed':False,'semantic_mutation_allowed':False,'diagnostic_followup_processing_allowed':False,'held_out_access_allowed':False}

def build_receipt(mh,gh,gold,checks):
 return {'schema_version':1,'receipt_id':'phase7.3.3-d4-support-gold-freeze-receipt-v1','status':'completed_support_gold_freeze','manifest_sha256':mh,'support_gold_sha256':gh,'entry_gate_checks':checks,'case_count':gold['case_count'],'claim_count':gold['claim_count'],'exact_reviewer_agreement_count':gold['exact_reviewer_agreement_count'],'adjudicated_disagreement_count':gold['adjudicated_disagreement_count'],'deferred_count':gold['deferred_count'],'label_counts':gold['label_counts'],'gold_fields':gold['gold_fields'],'all_claims_accounted':True,'boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False,'diagnostic_followup_items_processed':0,'provider_called':False,'held_out_accessed':False}

def build_state(mh,gh,rh,gold):
 return {'schema_version':10,'state_id':'phase7.3.3-d-support-stage-state-v10','boundary_state':'frozen_project_boundary_gold','support_state':'frozen_project_support_gold','artifact_lineage':{'support_stage_state_v9_sha256':sha(STATE_V9),'readiness_v20_sha256':sha(READINESS_V20),'support_gold_freeze_protocol_sha256':sha(PROTOCOL),'support_gold_freeze_contract_fixtures_sha256':sha(FIXTURES),'support_gold_freeze_manifest_sha256':mh,'support_gold_sha256':gh,'support_gold_freeze_receipt_sha256':rh},'boundary_gold_sha256':sha(BOUNDARY_GOLD),'boundary_claim_count':118,'support_review_completed':True,'support_agreement_computed':True,'support_label_disagreement_count':26,'support_adjudication_completed':True,'support_gold_frozen':True,'support_gold_sha256':gh,'support_gold_claim_count':gold['claim_count'],'support_gold_label_counts':gold['label_counts'],'support_gold_gold_fields':['support_label'],'diagnostic_followup_items_processed':0,'paired_evaluation_protocol_frozen':False,'paired_evaluation_started':False,'next_authorized_stage':'freeze_atomic_vs_candidate_paired_evaluation_protocol_v1','provider_called_for_freeze':False,'held_out_accessed':False}

def build_outcome(mh,gh,rh,sh,gold):
 return {'schema_version':1,'outcome_id':'phase7.3.3-d4-support-gold-freeze-outcome-v1','status':'completed_support_gold_freeze','artifact_lineage':{'manifest_sha256':mh,'support_gold_sha256':gh,'freeze_receipt_sha256':rh,'support_stage_state_v10_sha256':sh},'reference_status':gold['reference_status'],'case_count':gold['case_count'],'claim_count':gold['claim_count'],'exact_reviewer_agreement_count':gold['exact_reviewer_agreement_count'],'adjudicated_disagreement_count':gold['adjudicated_disagreement_count'],'deferred_count':0,'missing_claim_count':0,'duplicate_claim_count':0,'label_counts':gold['label_counts'],'gold_fields':['support_label'],'diagnostic_fields_promoted_to_gold':False,'boundary_mutation_performed':False,'reviewer_submission_mutation_performed':False,'diagnostic_followup_items_processed':0,'provider_called':False,'held_out_accessed':False,'next_authorized_stage':'freeze_atomic_vs_candidate_paired_evaluation_protocol_v1','paired_evaluation_executed':False}

def build_ready(mh,gh,rh,sh,oh,gold):
 return {'schema_version':21,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v21','status':'support_gold_frozen_paired_evaluation_protocol_authorized','artifact_lineage':{'readiness_v20_sha256':sha(READINESS_V20),'support_stage_state_v9_sha256':sha(STATE_V9),'support_gold_freeze_protocol_sha256':sha(PROTOCOL),'support_gold_freeze_contract_fixtures_sha256':sha(FIXTURES),'support_gold_freeze_manifest_sha256':mh,'support_gold_sha256':gh,'support_gold_freeze_receipt_sha256':rh,'support_stage_state_v10_sha256':sh,'support_gold_freeze_outcome_sha256':oh},'reference_status':{'boundary_gold_frozen':True,'boundary_claim_count':118,'support_reviews_completed':True,'support_agreement_computed':True,'support_adjudication_completed':True,'support_gold_frozen':True,'support_gold_reference_status':gold['reference_status'],'support_gold_claim_count':gold['claim_count'],'support_gold_label_counts':gold['label_counts'],'support_gold_gold_fields':['support_label']},'next_authorized_stage':'freeze_atomic_vs_candidate_paired_evaluation_protocol_v1','paired_evaluation_protocol_frozen':False,'paired_evaluation_started':False,'support_gold_frozen':True,'diagnostic_followup_items_processed':0,'provider_called_for_freeze':False,'held_out_accessed':False}

def execute():
 inp,ctx=validate_inputs()
 if not MANIFEST.is_file():raise ValueError('frozen_manifest_required_before_execution')
 if load(MANIFEST)!=expected_manifest():raise ValueError('frozen_manifest_does_not_match_current_inputs_or_adapter')
 mh=sha(MANIFEST);gold=build_gold(inp,ctx,mh);gh=once(SUPPORT_GOLD,gold);receipt=build_receipt(mh,gh,gold,ctx['checks']);rh=once(RECEIPT,receipt);state=build_state(mh,gh,rh,gold);sh=once(STATE_V10,state);out=build_outcome(mh,gh,rh,sh,gold);oh=once(OUTCOME,out);ready=build_ready(mh,gh,rh,sh,oh,gold);rdh=once(READINESS_V21,ready)
 return {'status':'completed_support_gold_freeze','manifest_sha256':mh,'support_gold_sha256':gh,'freeze_receipt_sha256':rh,'freeze_outcome_sha256':oh,'support_stage_state_v10_sha256':sh,'readiness_v21_sha256':rdh,'case_count':gold['case_count'],'claim_count':gold['claim_count'],'exact_reviewer_agreement_count':gold['exact_reviewer_agreement_count'],'adjudicated_disagreement_count':gold['adjudicated_disagreement_count'],'deferred_count':0,'label_counts':gold['label_counts'],'gold_fields':gold['gold_fields'],'provider_called':False,'held_out_accessed':False,'next_authorized_stage':ready['next_authorized_stage'],'paired_evaluation_started':False}

def verify():
 inp,ctx=validate_inputs();z=dict(ctx['checks']);z['manifest_present_and_exact']=MANIFEST.is_file() and load(MANIFEST)==expected_manifest()
 if z['manifest_present_and_exact']:
  mh=sha(MANIFEST);gold=build_gold(inp,ctx,mh);z['support_gold_present_and_exact']=SUPPORT_GOLD.is_file() and load(SUPPORT_GOLD)==gold
  if z['support_gold_present_and_exact']:
   gh=sha(SUPPORT_GOLD);receipt=build_receipt(mh,gh,gold,ctx['checks']);z['receipt_present_and_exact']=RECEIPT.is_file() and load(RECEIPT)==receipt;rh=sha(RECEIPT) if z['receipt_present_and_exact'] else ''
   state=build_state(mh,gh,rh,gold);z['state_v10_present_and_exact']=STATE_V10.is_file() and load(STATE_V10)==state;sh=sha(STATE_V10) if z['state_v10_present_and_exact'] else ''
   out=build_outcome(mh,gh,rh,sh,gold);z['outcome_present_and_exact']=OUTCOME.is_file() and load(OUTCOME)==out;oh=sha(OUTCOME) if z['outcome_present_and_exact'] else ''
   ready=build_ready(mh,gh,rh,sh,oh,gold);z['readiness_v21_present_and_exact']=READINESS_V21.is_file() and load(READINESS_V21)==ready
   z['all_118_claims_accounted']=gold['claim_count']==len(gold['claims'])==118
   z['boundary_fields_unchanged']=all(all(gg.get(k)==bb.get(k) for k in bb) for bb,gg in zip(inp['boundary_gold']['claims'],gold['claims']))
   z['only_support_label_is_gold']=gold['gold_fields']==['support_label'] and all(q['diagnostic_annotation_gold_status'].startswith('not_gold') for q in gold['claims'])
   z['no_provider_or_held_out']=gold['provider_called_for_freeze'] is False and gold['held_out_accessed'] is False
  else:
   for k in ('receipt_present_and_exact','state_v10_present_and_exact','outcome_present_and_exact','readiness_v21_present_and_exact','all_118_claims_accounted','boundary_fields_unchanged','only_support_label_is_gold','no_provider_or_held_out'):z[k]=False
 else:
  for k in ('support_gold_present_and_exact','receipt_present_and_exact','state_v10_present_and_exact','outcome_present_and_exact','readiness_v21_present_and_exact','all_118_claims_accounted','boundary_fields_unchanged','only_support_label_is_gold','no_provider_or_held_out'):z[k]=False
 ok=all(z.values());result={'status':'verified' if ok else 'failed','all_passed':ok,'checks':z,'hashes':{'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(PROTOCOL),'contract_fixtures_sha256':sha(FIXTURES) if FIXTURES.exists() else None,'manifest_sha256':sha(MANIFEST) if MANIFEST.exists() else None,'support_gold_sha256':sha(SUPPORT_GOLD) if SUPPORT_GOLD.exists() else None,'freeze_receipt_sha256':sha(RECEIPT) if RECEIPT.exists() else None,'freeze_outcome_sha256':sha(OUTCOME) if OUTCOME.exists() else None,'support_stage_state_v10_sha256':sha(STATE_V10) if STATE_V10.exists() else None,'readiness_v21_sha256':sha(READINESS_V21) if READINESS_V21.exists() else None},'provider_called':False,'held_out_accessed':False}
 if not ok:raise ValueError('support_gold_freeze_verification_failed:'+','.join(k for k,v in z.items() if not v))
 return result

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--run-contract-fixtures',action='store_true');g.add_argument('--verify-inputs',action='store_true');g.add_argument('--freeze-manifest',action='store_true');g.add_argument('--execute',action='store_true');g.add_argument('--verify',action='store_true');a=p.parse_args()
 if a.run_contract_fixtures:
  f=fixture_result()
  if f['failed_count']:raise ValueError('contract_fixture_failure')
  result={'status':f['status'],'contract_fixtures_sha256':once(FIXTURES,f),'fixture_count':f['fixture_count'],'passed_count':f['passed_count'],'provider_called':False,'held_out_accessed':False}
 elif a.verify_inputs:
  _,ctx=validate_inputs();result={'status':'support_gold_freeze_inputs_verified','all_entry_gate_checks_passed':all(ctx['checks'].values()),'entry_gate_checks':ctx['checks'],'merge_summary':ctx['merge_summary'],'provider_called':False,'held_out_accessed':False}
 elif a.freeze_manifest:
  m=expected_manifest();result={'status':'support_gold_freeze_manifest_frozen_not_started','manifest_sha256':once(MANIFEST,m),'validated_claim_count':m['validated_claim_count'],'reconstructed_label_counts':m['reconstructed_label_counts'],'provider_called':False,'held_out_accessed':False}
 elif a.execute:result=execute()
 else:result=verify()
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
