#!/usr/bin/env python3
"""Freeze and execute the Independent Pilot paired analysis after both v4 arms complete."""
from __future__ import annotations
import argparse, hashlib, json, math, random, tempfile
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; C=ROOT/'crates/eval/config'; D=ROOT/'crates/eval/datasets/pattern_extraction'; R=ROOT/'crates/eval/reports'
PLAN=C/'phase7_3_3_d_independent_replication_analysis_plan_v1.json'; DATASET=D/'phase7_3_3_d_independent_pilot_selected_dataset_v1.json'; REFERENCE=D/'phase7_3_3_d_independent_pilot_reference_v1.json'; SEAL=R/'phase7_3_3_d_independent_pilot_reference_seal_v1.json'; FRAME=R/'phase7_3_3_d_independent_pilot_single_proposition_frame_audit_v1.json'; CSUB=D/'phase7_3_3_d_independent_pilot_candidate_arm_submission_v4.json'; ASUB=D/'phase7_3_3_d_independent_pilot_atomic_arm_submission_v4.json'; DUAL=R/'phase7_3_3_d_independent_pilot_dual_arm_execution_result_v4.json'; STATE_PREV=D/'phase7_3_3_d_support_stage_state_v19.json'; READY_PREV=R/'phase7_3_3_d1_reference_construction_readiness_v30.json'
PROTOCOL=C/'phase7_3_3_d_independent_pilot_analysis_protocol_v1.json'; FREEZE=R/'phase7_3_3_d_independent_pilot_analysis_freeze_manifest_v1.json'; MAN=R/'phase7_3_3_d_independent_pilot_analysis_execution_manifest_v1.json'; CASES=D/'phase7_3_3_d_independent_pilot_paired_analysis_cases_v1.json'; REPORT=R/'phase7_3_3_d_independent_pilot_analysis_report_v1.json'; RECEIPT=R/'phase7_3_3_d_independent_pilot_analysis_freeze_receipt_v1.json'; STATE=D/'phase7_3_3_d_support_stage_state_v20.json'; READY=R/'phase7_3_3_d1_reference_construction_readiness_v31.json'
BOOT_SEED=733041; BOOT_REPS=20000; LABEL_ORDER={'supported':0,'partially_supported':1,'unsupported':2}
def hb(b): return hashlib.sha256(b).hexdigest()
def sha(p): return hb(p.read_bytes())
def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def once(p,v):
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b: raise ValueError('immutable_artifact_conflict:'+str(p.relative_to(ROOT)))
  return hb(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h: h.write(b); t=Path(h.name)
 t.replace(p); return hb(b)
def preflight():
 for p in [PLAN,DATASET,REFERENCE,SEAL,FRAME,CSUB,ASUB,DUAL,STATE_PREV,READY_PREV]:
  if not p.exists(): raise FileNotFoundError(p)
 d=load(DUAL); c=load(CSUB); a=load(ASUB); seal=load(SEAL); ref=load(REFERENCE)
 z={'dual_complete_unscored':d['status']=='completed_equal_resource_paired_pilot_unscored' and d['pilot_scored'] is False,'submissions_complete':c['status']==a['status']=='completed' and c['case_count']==a['case_count']==40,'requests_80':d['request_count']==80 and c['request_count']==a['request_count']==40,'hashes_match':d['candidate_submission_sha256']==sha(CSUB) and d['atomic_submission_sha256']==sha(ASUB),'reference_sealed':seal['reference_sha256']==sha(REFERENCE) and ref['status']=='frozen_model_adjudicated_independent_pilot_reference_not_human_gold','reference_not_used_by_arms':not d['reference_content_loaded'] and not d['reference_labels_loaded'],'single_claim_frame':d['single_proposition_frame'] is True and a['claim_count']==40 and a['segmentation_operation_counts']=={'whole_candidate_claim':40},'analysis_outputs_absent':not any(p.exists() for p in [CASES,REPORT,RECEIPT,STATE,READY]),'confirmatory_closed':not d['confirmatory_content_opened'] and not ref['confirmatory_content_opened']}
 print(json.dumps({'status':'PASS' if all(z.values()) else 'FAIL','checks':z},indent=2))
 if not all(z.values()): raise SystemExit(1)
def prepare():
 preflight()
 protocol={'schema_version':1,'protocol_id':'phase7.3.3-d-independent-pilot-analysis-protocol-v1','status':'frozen_before_reference_opening_for_scoring','study_scope':'paired exploratory Pilot; no confirmatory p-values and no generalization claim','case_count':40,'cluster_unit':'candidate_sha256','unique_candidate_clusters':10,'structural_limitation':'one full-Candidate material claim per case; Atomic localization estimand is structurally degenerate if the Atomic arm also emits whole_candidate_claim','primary_endpoints':{'candidate_level_exact_correctness':'arm aggregate label equals sealed Independent Reference label; not_assessable is incorrect unless Reference is not_assessable','material_error_detection':'binary presence of any material partially_supported or unsupported span; not_assessable is an abstention and predicts no localized material error','diagnostic_localization_precision_recall_f1':'micro character-level overlap of material error spans across all 40 cases'},'secondary_endpoints':['ordinal_distance','unsupported_masking','partial_localization','final_version_failure_rate','candidate_atomic_label_agreement','tokens','latency'],'missingness':{'all_40_cases_required':True,'failures_not_dropped':True,'final_submission_missing_is_incorrect_and_reported':True,'predecessor_version_partial_outputs_excluded':True},'uncertainty':{'primary':'candidate_sha256 cluster bootstrap percentile interval','secondary':'case bootstrap percentile interval','seed':BOOT_SEED,'replicates':BOOT_REPS,'interval':[0.025,0.975],'confirmatory_p_values':False},'paired_effect_direction':'atomic_minus_candidate','cost_policy':{'token_and_latency_measured':True,'pricing_method_frozen':False,'cost_usd':None},'reference_opening_authorized_only_after_manifest_freeze':True,'confirmatory_content_opened':False}
 ph=once(PROTOCOL,protocol); freeze={'schema_version':1,'manifest_id':'phase7.3.3-d-independent-pilot-analysis-freeze-manifest-v1','status':'frozen_ready_to_score','artifact_sha256':{'analysis_plan':sha(PLAN),'protocol':ph,'dataset':sha(DATASET),'reference_seal':sha(SEAL),'reference':sha(REFERENCE),'frame_audit':sha(FRAME),'candidate_submission':sha(CSUB),'atomic_submission':sha(ASUB),'dual_arm_result':sha(DUAL),'state_v19':sha(STATE_PREV),'readiness_v30':sha(READY_PREV)},'reference_content_loaded_during_freeze':False,'scoring_started':False,'confirmatory_content_opened':False}
 print(json.dumps({'status':'analysis_protocol_frozen','freeze_manifest_sha256':once(FREEZE,freeze),'reference_opened_for_scoring':False},indent=2))
def checks():
 if not FREEZE.exists(): return {'freeze_exists':False}
 f=load(FREEZE); p=load(PROTOCOL)
 return {'freeze':f['status']=='frozen_ready_to_score','plan':f['artifact_sha256']['analysis_plan']==sha(PLAN),'protocol':f['artifact_sha256']['protocol']==sha(PROTOCOL),'dataset':f['artifact_sha256']['dataset']==sha(DATASET),'reference':f['artifact_sha256']['reference']==sha(REFERENCE),'seal':f['artifact_sha256']['reference_seal']==sha(SEAL),'frame':f['artifact_sha256']['frame_audit']==sha(FRAME),'submissions':f['artifact_sha256']['candidate_submission']==sha(CSUB) and f['artifact_sha256']['atomic_submission']==sha(ASUB),'dual':f['artifact_sha256']['dual_arm_result']==sha(DUAL),'bootstrap':p['uncertainty']['seed']==BOOT_SEED and p['uncertainty']['replicates']==BOOT_REPS,'not_started':f['scoring_started'] is False and f['reference_content_loaded_during_freeze'] is False,'confirmatory_closed':f['confirmatory_content_opened'] is False}
def manifest_doc():
 z=checks()
 if not all(z.values()): raise ValueError('analysis_freeze_checks_failed')
 return {'schema_version':1,'manifest_id':'phase7.3.3-d-independent-pilot-analysis-execution-manifest-v1','status':'frozen_before_reference_scoring','artifact_lineage':{'adapter_sha256':sha(Path(__file__)),'freeze_manifest_sha256':sha(FREEZE),'protocol_sha256':sha(PROTOCOL),'reference_sha256':sha(REFERENCE),'candidate_submission_sha256':sha(CSUB),'atomic_submission_sha256':sha(ASUB),'dual_arm_result_sha256':sha(DUAL)},'bootstrap_seed':BOOT_SEED,'bootstrap_replicates':BOOT_REPS,'reference_content_loaded':False,'scoring_started':False,'confirmatory_content_opened':False}
def freeze_manifest(): print(json.dumps({'status':'analysis_manifest_frozen','manifest_sha256':once(MAN,manifest_doc()),'scoring_started':False},indent=2))
def chars(spans):
 out=set()
 for x in spans:
  sp=x['source_span']; out.update(range(sp['start'],sp['end']))
 return out
def ratio(n,d): return None if d==0 else n/d
def prf(tp,fp,fn):
 p=ratio(tp,tp+fp); r=ratio(tp,tp+fn); f=None if p is None or r is None or p+r==0 else 2*p*r/(p+r)
 return {'precision':p,'recall':r,'f1':f}
def arm_metrics(rows,prefix):
 exact=sum(x[prefix+'_correct'] for x in rows); tp=sum(x[prefix+'_error_positive'] and x['reference_error_positive'] for x in rows); tn=sum((not x[prefix+'_error_positive']) and (not x['reference_error_positive']) for x in rows); fp=sum(x[prefix+'_error_positive'] and not x['reference_error_positive'] for x in rows); fn=sum((not x[prefix+'_error_positive']) and x['reference_error_positive'] for x in rows); ctp=sum(x[prefix+'_char_tp'] for x in rows); cfp=sum(x[prefix+'_char_fp'] for x in rows); cfn=sum(x[prefix+'_char_fn'] for x in rows); assess=[x[prefix+'_ordinal_distance'] for x in rows if x[prefix+'_ordinal_distance'] is not None]
 return {'exact_correct_count':exact,'exact_accuracy':exact/len(rows),'material_error_detection':{'tp':tp,'tn':tn,'fp':fp,'fn':fn,'accuracy':(tp+tn)/len(rows),**prf(tp,fp,fn)},'diagnostic_localization_micro_characters':{'tp':ctp,'fp':cfp,'fn':cfn,**prf(ctp,cfp,cfn)},'ordinal_distance':{'assessable_count':len(assess),'not_assessable_count':len(rows)-len(assess),'mean_absolute_distance':sum(assess)/len(assess) if assess else None},'unsupported_masking_count':sum(x['reference_label']=='unsupported' and x[prefix+'_label']=='supported' for x in rows),'not_assessable_count':sum(x[prefix+'_label']=='not_assessable' for x in rows)}
def percentile(values,q):
 v=sorted(values); pos=(len(v)-1)*q; lo=math.floor(pos); hi=math.ceil(pos)
 return v[lo] if lo==hi else v[lo]+(v[hi]-v[lo])*(pos-lo)
def bootstrap(rows,clustered):
 rng=random.Random(BOOT_SEED+(0 if clustered else 1)); vals=[]
 if clustered:
  groups=defaultdict(list)
  for x in rows: groups[x['candidate_sha256']].append(x)
  keys=sorted(groups)
  for _ in range(BOOT_REPS):
   sample=[]
   for __ in keys: sample.extend(groups[rng.choice(keys)])
   vals.append(sum(x['atomic_correct']-x['candidate_correct'] for x in sample)/len(sample))
 else:
  for _ in range(BOOT_REPS):
   sample=[rng.choice(rows) for __ in rows]; vals.append(sum(x['atomic_correct']-x['candidate_correct'] for x in sample)/len(sample))
 return {'method':'candidate_sha256_cluster_bootstrap' if clustered else 'case_bootstrap','seed':BOOT_SEED+(0 if clustered else 1),'replicates':BOOT_REPS,'lower_2_5':percentile(vals,.025),'upper_97_5':percentile(vals,.975)}
def score():
 z=checks()
 if not all(z.values()): raise ValueError('analysis_freeze_checks_failed')
 if not MAN.exists() or load(MAN)!=manifest_doc(): raise ValueError('analysis_manifest_missing_or_invalid')
 if any(p.exists() for p in [CASES,REPORT,RECEIPT,STATE,READY]): raise ValueError('analysis_terminal_artifact_exists')
 ref=load(REFERENCE); c=load(CSUB); a=load(ASUB); ds=load(DATASET); mh=sha(MAN)
 refs={x['case_id']:x for x in ref['cases']}; cs={x['case_id']:x for x in c['cases']}; ats={x['case_id']:x for x in a['cases']}; dss={x['case_id']:x for x in ds['cases']}
 ids=set(refs)
 if ids!=set(cs) or ids!=set(ats) or ids!=set(dss) or len(ids)!=40: raise ValueError('paired_case_identity_mismatch')
 rows=[]
 for case_id in sorted(ids,key=lambda x:refs[x]['pilot_index']):
  rr=refs[case_id]; cc=cs[case_id]; aa=ats[case_id]; dd=dss[case_id]
  if rr['candidate_sha256']!=dd['candidate_sha256']: raise ValueError('candidate_lineage_mismatch:'+case_id)
  rchars=chars(rr['material_error_spans']); cchars=chars(cc['material_error_spans']); achars=chars(aa['material_error_spans']); rl=rr['candidate_reference_label']; cl=cc['support_label']; al=aa['candidate_reference_label']
  row={'pilot_index':rr['pilot_index'],'case_id':case_id,'domain':rr['domain'],'candidate_sha256':rr['candidate_sha256'],'reference_label':rl,'candidate_label':cl,'atomic_label':al,'reference_error_positive':bool(rchars),'candidate_error_positive':bool(cchars),'atomic_error_positive':bool(achars),'candidate_correct':cl==rl,'atomic_correct':al==rl,'candidate_char_tp':len(cchars&rchars),'candidate_char_fp':len(cchars-rchars),'candidate_char_fn':len(rchars-cchars),'atomic_char_tp':len(achars&rchars),'atomic_char_fp':len(achars-rchars),'atomic_char_fn':len(rchars-achars),'candidate_ordinal_distance':None if cl not in LABEL_ORDER or rl not in LABEL_ORDER else abs(LABEL_ORDER[cl]-LABEL_ORDER[rl]),'atomic_ordinal_distance':None if al not in LABEL_ORDER or rl not in LABEL_ORDER else abs(LABEL_ORDER[al]-LABEL_ORDER[rl]),'candidate_atomic_label_agree':cl==al,'atomic_claim_count':len(aa['claims']),'atomic_operation':aa['segmentation_operation']}
  rows.append(row)
 cm=arm_metrics(rows,'candidate'); am=arm_metrics(rows,'atomic'); both=sum(x['candidate_correct'] and x['atomic_correct'] for x in rows); conly=sum(x['candidate_correct'] and not x['atomic_correct'] for x in rows); aonly=sum(x['atomic_correct'] and not x['candidate_correct'] for x in rows); neither=40-both-conly-aonly; effect=am['exact_accuracy']-cm['exact_accuracy']
 case_art={'schema_version':1,'dataset_id':'phase7.3.3-d-independent-pilot-paired-analysis-cases-v1','status':'frozen_scored_paired_cases','manifest_sha256':mh,'case_count':40,'unique_candidate_cluster_count':len({x['candidate_sha256'] for x in rows}),'cases':rows,'confirmatory_content_opened':False}; case_hash=once(CASES,case_art)
 report={'schema_version':1,'report_id':'phase7.3.3-d-independent-pilot-analysis-report-v1','status':'frozen_exploratory_pilot_result','manifest_sha256':mh,'paired_cases_sha256':case_hash,'reference_sha256':sha(REFERENCE),'case_count':40,'unique_candidate_cluster_count':len({x['candidate_sha256'] for x in rows}),'reference_label_counts':dict(Counter(x['reference_label'] for x in rows)),'arm_metrics':{'candidate':cm,'atomic':am},'paired_primary_effect':{'estimand':'exact_accuracy_atomic_minus_candidate','estimate':effect,'discordant_pairs':{'both_correct':both,'candidate_only_correct':conly,'atomic_only_correct':aonly,'both_wrong':neither},'cluster_bootstrap_95_interval':bootstrap(rows,True),'case_bootstrap_95_interval_secondary':bootstrap(rows,False),'confirmatory_p_value':None},'arm_label_agreement':{'count':sum(x['candidate_atomic_label_agree'] for x in rows),'rate':sum(x['candidate_atomic_label_agree'] for x in rows)/40},'structural_diagnostics':{'reference_claim_count':ref['claim_count'],'atomic_claim_count':a['claim_count'],'all_atomic_operations_whole_candidate':all(x['atomic_operation']=='whole_candidate_claim' for x in rows),'general_atomic_localization_superiority_estimable':False,'localization_estimand_status':'degenerate_representation_equivalent_single_claim_frame','partial_localization_estimable':False},'missingness_and_failures':{'selected_cases':40,'candidate_final_missing':0,'atomic_final_missing':0,'paired_cases_dropped':0,'final_version_failure_rate':{'candidate':0.0,'atomic':0.0},'predecessor_partial_outputs_used':False},'resources':{'candidate':c['resource_usage'],'atomic':a['resource_usage'],'differences_atomic_minus_candidate':{'prompt_tokens':a['resource_usage']['prompt_tokens']-c['resource_usage']['prompt_tokens'],'completion_tokens':a['resource_usage']['completion_tokens']-c['resource_usage']['completion_tokens'],'total_tokens':a['resource_usage']['total_tokens']-c['resource_usage']['total_tokens'],'latency_ms_total':a['resource_usage']['latency_ms_total']-c['resource_usage']['latency_ms_total'],'latency_ms_mean':a['resource_usage']['latency_ms_mean']-c['resource_usage']['latency_ms_mean'],'cost_usd':None},'cost_status':'provider_billing_price_not_frozen'},'scientific_conclusion_scope':'This Pilot estimates paired semantic and representation feasibility on a frozen single-proposition frame. It cannot establish general Atomic localization superiority.','confirmatory_content_opened':False,'runtime_integration_authorized':False}
 rh=once(REPORT,report)
 receipt={'schema_version':1,'receipt_id':'phase7.3.3-d-independent-pilot-analysis-freeze-receipt-v1','status':'frozen_exploratory_pilot_analysis_completed','artifact_sha256':{'analysis_protocol':sha(PROTOCOL),'freeze_manifest':sha(FREEZE),'execution_manifest':mh,'paired_analysis_cases':case_hash,'analysis_report':rh,'reference':sha(REFERENCE),'candidate_submission':sha(CSUB),'atomic_submission':sha(ASUB)},'paired_primary_effect':report['paired_primary_effect'],'missingness_and_failures':report['missingness_and_failures'],'structural_diagnostics':report['structural_diagnostics'],'confirmatory_content_opened':False,'runtime_integration_authorized':False}
 receipt_hash=once(RECEIPT,receipt)
 prev_state=load(STATE_PREV); state_lineage=dict(prev_state['artifact_lineage']); state_lineage.update({'support_stage_state_v19_sha256':sha(STATE_PREV),'readiness_v30_sha256':sha(READY_PREV),'independent_pilot_analysis_protocol_v1_sha256':sha(PROTOCOL),'independent_pilot_analysis_freeze_manifest_v1_sha256':sha(FREEZE),'independent_pilot_analysis_execution_manifest_v1_sha256':mh,'independent_pilot_paired_analysis_cases_v1_sha256':case_hash,'independent_pilot_analysis_report_v1_sha256':rh,'independent_pilot_analysis_freeze_receipt_v1_sha256':receipt_hash})
 state={'schema_version':20,'state_id':'phase7.3.3-d-support-stage-state-v20','boundary_state':prev_state['boundary_state'],'support_state':prev_state['support_state'],'artifact_lineage':state_lineage,'boundary_gold_sha256':prev_state['boundary_gold_sha256'],'support_gold_sha256':prev_state['support_gold_sha256'],'runtime_integration_authorized':False,'independent_replication_state':'independent_pilot_analysis_frozen_exploratory','independent_pilot_selected_count':40,'independent_reference_frozen':True,'independent_dual_arm_execution_completed':True,'independent_pilot_analysis_completed':True,'independent_pilot_effect_frozen':True,'independent_pilot_missingness_frozen':True,'independent_pilot_exact_effect_atomic_minus_candidate':effect,'independent_pilot_localization_estimand_status':'degenerate_representation_equivalent_single_claim_frame','general_atomic_localization_superiority_estimable':False,'next_authorized_stage':'freeze_independent_pilot_power_method_v1','confirmatory_dataset_opened':False}
 state_hash=once(STATE,state)
 prev_ready=load(READY_PREV); ready_lineage=dict(prev_ready['artifact_lineage']); ready_lineage.update({'readiness_v30_sha256':sha(READY_PREV),'support_stage_state_v19_sha256':sha(STATE_PREV),'analysis_protocol_v1_sha256':sha(PROTOCOL),'analysis_freeze_manifest_v1_sha256':sha(FREEZE),'analysis_execution_manifest_v1_sha256':mh,'paired_analysis_cases_v1_sha256':case_hash,'analysis_report_v1_sha256':rh,'analysis_freeze_receipt_v1_sha256':receipt_hash,'support_stage_state_v20_sha256':state_hash})
 ready={'schema_version':41,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v31','status':'independent_pilot_analysis_frozen_structurally_degenerate_localization_estimand','artifact_lineage':ready_lineage,'reference_status':'frozen_and_sealed','dual_arm_status':'v4_completed_equal_resource_scored','analysis_status':'frozen_exploratory_pilot_result','general_atomic_localization_superiority_estimable':False,'localization_estimand_status':'degenerate_representation_equivalent_single_claim_frame','next_authorized_stage':'freeze_independent_pilot_power_method_v1','confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 ready_hash=once(READY,ready)
 print(json.dumps({'status':'frozen_exploratory_pilot_analysis_completed','analysis_report_sha256':rh,'paired_cases_sha256':case_hash,'receipt_sha256':receipt_hash,'state_v20_sha256':state_hash,'readiness_v31_sha256':ready_hash,'paired_exact_effect_atomic_minus_candidate':effect,'general_atomic_localization_superiority_estimable':False,'confirmatory_dataset_opened':False},indent=2))
def verify():
 required=[PROTOCOL,FREEZE,MAN,CASES,REPORT,RECEIPT,STATE,READY]
 if not all(p.exists() for p in required):
  print(json.dumps({'status':'FAIL','missing':[str(p.relative_to(ROOT)) for p in required if not p.exists()]},indent=2)); raise SystemExit(1)
 f=load(FREEZE); m=load(MAN); cases=load(CASES); report=load(REPORT); receipt=load(RECEIPT); state=load(STATE); ready=load(READY); c=load(CSUB); a=load(ASUB); ref=load(REFERENCE); dual=load(DUAL); rows=cases['cases']
 cluster_count=len({x['candidate_sha256'] for x in rows}); cm=arm_metrics(rows,'candidate'); am=arm_metrics(rows,'atomic'); effect=am['exact_accuracy']-cm['exact_accuracy']
 checks_v={
  'freeze_checks':all(checks().values()),
  'manifest_exact':m==manifest_doc(),
  'manifest_pre_scoring':m['reference_content_loaded'] is False and m['scoring_started'] is False,
  'artifact_hashes':report['manifest_sha256']==sha(MAN) and report['paired_cases_sha256']==sha(CASES) and receipt['artifact_sha256']['analysis_report']==sha(REPORT) and receipt['artifact_sha256']['paired_analysis_cases']==sha(CASES),
  'reference_seal':load(SEAL)['reference_sha256']==sha(REFERENCE) and report['reference_sha256']==sha(REFERENCE),
  'paired_rows_40':cases['case_count']==report['case_count']==len(rows)==40,
  'case_identity':{x['case_id'] for x in rows}=={x['case_id'] for x in ref['cases']}=={x['case_id'] for x in c['cases']}=={x['case_id'] for x in a['cases']},
  'clusters_10':cases['unique_candidate_cluster_count']==report['unique_candidate_cluster_count']==cluster_count==10,
  'submissions_lineage':receipt['artifact_sha256']['candidate_submission']==sha(CSUB) and receipt['artifact_sha256']['atomic_submission']==sha(ASUB) and dual['candidate_submission_sha256']==sha(CSUB) and dual['atomic_submission_sha256']==sha(ASUB),
  'no_missing_or_drop':report['missingness_and_failures']['candidate_final_missing']==0 and report['missingness_and_failures']['atomic_final_missing']==0 and report['missingness_and_failures']['paired_cases_dropped']==0 and report['missingness_and_failures']['predecessor_partial_outputs_used'] is False,
  'metrics_replay':report['arm_metrics']['candidate']==cm and report['arm_metrics']['atomic']==am and report['paired_primary_effect']['estimate']==effect,
  'bootstrap_frozen':report['paired_primary_effect']['cluster_bootstrap_95_interval']['seed']==BOOT_SEED and report['paired_primary_effect']['cluster_bootstrap_95_interval']['replicates']==BOOT_REPS and report['paired_primary_effect']['case_bootstrap_95_interval_secondary']['seed']==BOOT_SEED+1 and report['paired_primary_effect']['case_bootstrap_95_interval_secondary']['replicates']==BOOT_REPS,
  'whole_candidate_atomic_40':a['claim_count']==40 and a['segmentation_operation_counts']=={'whole_candidate_claim':40} and all(x['atomic_claim_count']==1 and x['atomic_operation']=='whole_candidate_claim' for x in rows),
  'structural_degeneracy_recorded':report['structural_diagnostics']['general_atomic_localization_superiority_estimable'] is False and report['structural_diagnostics']['localization_estimand_status']=='degenerate_representation_equivalent_single_claim_frame' and receipt['structural_diagnostics']==report['structural_diagnostics'],
  'cost_not_imputed':report['resources']['candidate']['cost_usd'] is None and report['resources']['atomic']['cost_usd'] is None and report['resources']['differences_atomic_minus_candidate']['cost_usd'] is None and report['resources']['cost_status']=='provider_billing_price_not_frozen',
  'no_confirmatory_p':report['paired_primary_effect']['confirmatory_p_value'] is None,
  'confirmatory_closed':not any([f['confirmatory_content_opened'],m['confirmatory_content_opened'],cases['confirmatory_content_opened'],report['confirmatory_content_opened'],receipt['confirmatory_content_opened'],state['confirmatory_dataset_opened'],ready['confirmatory_dataset_opened']]),
  'state_v20':state['independent_pilot_analysis_completed'] is True and state['independent_pilot_effect_frozen'] is True and state['independent_pilot_missingness_frozen'] is True and state['next_authorized_stage']=='freeze_independent_pilot_power_method_v1',
  'readiness_v31':ready['analysis_status']=='frozen_exploratory_pilot_result' and ready['next_authorized_stage']=='freeze_independent_pilot_power_method_v1',
  'runtime_unauthorized':report['runtime_integration_authorized'] is False and receipt['runtime_integration_authorized'] is False and state['runtime_integration_authorized'] is False and ready['runtime_integration_authorized'] is False
 }
 ok=all(checks_v.values()); print(json.dumps({'status':'PASS' if ok else 'FAIL','checks':checks_v,'hashes':{'protocol':sha(PROTOCOL),'freeze_manifest':sha(FREEZE),'execution_manifest':sha(MAN),'paired_cases':sha(CASES),'analysis_report':sha(REPORT),'receipt':sha(RECEIPT),'state_v20':sha(STATE),'readiness_v31':sha(READY)},'effect':effect},indent=2))
 if not ok: raise SystemExit(1)
def main():
 ap=argparse.ArgumentParser(); g=ap.add_mutually_exclusive_group(required=True); g.add_argument('--preflight',action='store_true'); g.add_argument('--prepare',action='store_true'); g.add_argument('--freeze-manifest',action='store_true'); g.add_argument('--score',action='store_true'); g.add_argument('--verify',action='store_true'); x=ap.parse_args()
 if x.preflight: preflight()
 elif x.prepare: prepare()
 elif x.freeze_manifest: freeze_manifest()
 elif x.score: score()
 else: verify()
if __name__=='__main__': main()
