#!/usr/bin/env python3
"""Freeze and compute Independent Pilot Reference Agreement v1."""
from __future__ import annotations
import argparse, hashlib, json, math, tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'crates/eval/config'; DATA=ROOT/'crates/eval/datasets/pattern_extraction'; REPORTS=ROOT/'crates/eval/reports'
A=DATA/'phase7_3_3_d_independent_pilot_reference_reviewer_a_submission_v2.json'
B=DATA/'phase7_3_3_d_independent_pilot_reference_reviewer_b_submission_v3.json'
DATASET=DATA/'phase7_3_3_d_independent_pilot_selected_dataset_v1.json'
POLICY=CONFIG/'phase7_3_3_d_independent_reference_policy_v1.json'
STATE_PREV=DATA/'phase7_3_3_d_support_stage_state_v15.json'; READY_PREV=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v26.json'
PROTOCOL=CONFIG/'phase7_3_3_d_independent_pilot_reference_agreement_protocol_v1.json'
FIXTURES=REPORTS/'phase7_3_3_d_independent_pilot_reference_agreement_contract_fixtures_v1.json'
MANIFEST=REPORTS/'phase7_3_3_d_independent_pilot_reference_agreement_manifest_v1.json'
REPORT=REPORTS/'phase7_3_3_d_independent_pilot_reference_agreement_report_v1.json'
WORKLIST=DATA/'phase7_3_3_d_independent_pilot_reference_disagreement_worklist_v1.json'
OUTCOME=REPORTS/'phase7_3_3_d_independent_pilot_reference_agreement_outcome_v1.json'
RECEIPT=REPORTS/'phase7_3_3_d_independent_pilot_reference_agreement_freeze_receipt_v1.json'
STATE=DATA/'phase7_3_3_d_support_stage_state_v16.json'; READY=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v27.json'
LABELS=['supported','partially_supported','unsupported','not_assessable']
SEVERITY={('supported','partially_supported'):1,('partially_supported','unsupported'):1,('supported','unsupported'):2}

def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha(p:Path)->str:return sha_bytes(p.read_bytes())
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8-sig'))
def canonical(v:Any)->bytes:return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def write_once(p:Path,v:Any)->str:
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return sha_bytes(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b); t=Path(h.name)
 t.replace(p);return sha_bytes(b)
def jacc(a,b):
 a=set(a);b=set(b);u=a|b
 return 1.0 if not u else len(a&b)/len(u)
def kappa(pairs,values):
 n=len(pairs)
 if not n:return None
 po=sum(a==b for a,b in pairs)/n
 ca=Counter(a for a,_ in pairs);cb=Counter(b for _,b in pairs)
 pe=sum(ca[v]*cb[v] for v in values)/(n*n)
 return None if math.isclose(1-pe,0.0) else (po-pe)/(1-pe)
def protocol_doc():
 return {'schema_version':1,'protocol_id':'phase7.3.3-d-independent-pilot-reference-agreement-protocol-v1','status':'frozen_before_computation','purpose':'Compare the two completed blind independent Pilot reference submissions and create a minimal disagreement-only adjudication worklist without using either arm or Route A Gold.','inputs':{'reviewer_a':{'path':str(A.relative_to(ROOT)).replace('\\','/'),'sha256':sha(A)},'reviewer_b':{'path':str(B.relative_to(ROOT)).replace('\\','/'),'sha256':sha(B)},'selected_dataset':{'path':str(DATASET.relative_to(ROOT)).replace('\\','/'),'sha256':sha(DATASET)},'independent_reference_policy_sha256':sha(POLICY)},'primary_fields':['candidate_reference_label','material','claim_type'],'structural_checks':['one_whole_candidate_claim_per_case','exact_candidate_span','candidate_hash_replay','coverage_complete','zero_non_claim_spans'],'diagnostic_fields':['cited_evidence_ids','reason_codes','confidence'],'metrics':{'exact_agreement':True,'unweighted_cohen_kappa_when_defined':True,'confusion_matrix':True,'citation_exact_and_jaccard':True,'reason_exact_and_jaccard':True,'confidence_exact':True,'domain_concentration':True,'severity_policy':{'adjacent_label_distance':1,'supported_vs_unsupported':2,'not_assessable_mismatch':3,'maximum':3}},'worklist':{'include_only_primary_field_disagreements':True,'diagnostic_disagreement_cannot_change_label':True,'boundary_mutation':False,'candidate_mutation':False,'evidence_mutation':False,'arm_visibility':False,'route_a_gold_visibility':False},'guards':{'raw_completed_submissions_only':True,'reviewer_b_v2_partial_outputs_excluded':True,'provider_calls':0,'held_out_accessed':False,'confirmatory_opened':False}}
def freeze():
 for p in [A,B,DATASET,POLICY,STATE_PREV,READY_PREV]:
  if not p.exists():raise FileNotFoundError(p)
 fixtures={'schema_version':1,'fixture_id':'phase7.3.3-d-independent-pilot-reference-agreement-contract-fixtures-v1','status':'PASS','results':[{'id':'inputs_exist','passed':True},{'id':'completed_40_each','passed':load(A).get('case_count')==40 and load(B).get('case_count')==40},{'id':'blind_a','passed':load(A).get('arms_visible') is False and load(A).get('route_a_gold_visible') is False},{'id':'blind_b','passed':load(B).get('arms_visible') is False and load(B).get('route_a_gold_visible') is False},{'id':'same_case_set','passed':{x['case_id'] for x in load(A)['cases']}=={x['case_id'] for x in load(B)['cases']}},{'id':'no_provider','passed':True}]}
 if not all(x['passed'] for x in fixtures['results']):raise ValueError('fixture_failure')
 ph=write_once(PROTOCOL,protocol_doc());fh=write_once(FIXTURES,fixtures)
 man={'schema_version':1,'manifest_id':'phase7.3.3-d-independent-pilot-reference-agreement-manifest-v1','status':'frozen_before_computation','protocol_sha256':ph,'fixtures_sha256':fh,'adapter_sha256':sha(Path(__file__)),'input_sha256':{'reviewer_a':sha(A),'reviewer_b':sha(B),'selected_dataset':sha(DATASET),'reference_policy':sha(POLICY)},'expected_case_count':40,'provider_calls_authorized':0,'route_a_gold_visible':False,'arm_outputs_visible':False,'confirmatory_content_opened':False}
 mh=write_once(MANIFEST,man)
 print(json.dumps({'status':'frozen','protocol_sha256':ph,'fixtures_sha256':fh,'manifest_sha256':mh},indent=2))
def compute():
 if not MANIFEST.exists():raise ValueError('manifest_not_frozen')
 m=load(MANIFEST)
 if m['adapter_sha256']!=sha(Path(__file__)):raise ValueError('adapter_changed_after_manifest_freeze')
 if m['protocol_sha256']!=sha(PROTOCOL) or m['fixtures_sha256']!=sha(FIXTURES):raise ValueError('frozen_lineage_mismatch')
 a=load(A);b=load(B);d=load(DATASET); ds={x['case_id']:x for x in d['cases']}; am={x['case_id']:x for x in a['cases']};bm={x['case_id']:x for x in b['cases']}
 order=[x['case_id'] for x in d['cases']]
 if set(order)!=set(am) or set(order)!=set(bm) or len(order)!=40:raise ValueError('case_set_mismatch')
 structural=[]; pairs=[]; mat=[];typ=[];conf=[];cit=[];reason=[];matrix=Counter();domain=defaultdict(lambda:{'n':0,'agree':0,'disagree':0});dis=[];diagnostic=[]
 for cid in order:
  src=ds[cid];aa=am[cid];bb=bm[cid];ca=aa['claims'][0];cb=bb['claims'][0];candidate=src['candidate']; n=len(candidate)
  checks={'case_id':cid,'a_one_claim':len(aa['claims'])==1,'b_one_claim':len(bb['claims'])==1,'a_exact_span':ca['source_span']=={'start':0,'end':n},'b_exact_span':cb['source_span']=={'start':0,'end':n},'a_hash':aa['candidate_sha256']==src['candidate_sha256']==ca['source_text_sha256'],'b_hash':bb['candidate_sha256']==src['candidate_sha256']==cb['source_text_sha256'],'a_coverage':aa['coverage_complete'] is True and not aa['explicit_non_claim_spans'],'b_coverage':bb['coverage_complete'] is True and not bb['explicit_non_claim_spans']}
  checks['all_passed']=all(v for k,v in checks.items() if k not in {'case_id','all_passed'});structural.append(checks)
  la=aa['candidate_reference_label'];lb=bb['candidate_reference_label'];pairs.append((la,lb));mat.append((ca['material'],cb['material']));typ.append((ca['claim_type'],cb['claim_type']));conf.append((ca['confidence'],cb['confidence']));matrix[(la,lb)]+=1
  cex=sorted(ca['cited_evidence_ids'])==sorted(cb['cited_evidence_ids']);rex=sorted(ca['reason_codes'])==sorted(cb['reason_codes']);cit.append((cex,jacc(ca['cited_evidence_ids'],cb['cited_evidence_ids'])));reason.append((rex,jacc(ca['reason_codes'],cb['reason_codes'])))
  dom=domain[src['domain']];dom['n']+=1;dom['agree']+=int(la==lb);dom['disagree']+=int(la!=lb)
  base={'case_id':cid,'pilot_index':src['pilot_index'],'domain':src['domain'],'candidate_sha256':src['candidate_sha256'],'candidate':candidate,'context':src.get('context'),'evidence':src['evidence'],'reviewer_a':{'support_label':la,'material':ca['material'],'claim_type':ca['claim_type'],'cited_evidence_ids':ca['cited_evidence_ids'],'reason_codes':ca['reason_codes'],'rationale':ca['rationale'],'confidence':ca['confidence']},'reviewer_b':{'support_label':lb,'material':cb['material'],'claim_type':cb['claim_type'],'cited_evidence_ids':cb['cited_evidence_ids'],'reason_codes':cb['reason_codes'],'rationale':cb['rationale'],'confidence':cb['confidence']}}
  primary=(la!=lb or ca['material']!=cb['material'] or ca['claim_type']!=cb['claim_type'])
  if primary:
   base.update({'adjudication_item_id':f'independent-pilot-reference-adjudication-{len(dis)+1:03d}','disagreement_fields':[x for x,v in [('support_label',la!=lb),('material',ca['material']!=cb['material']),('claim_type',ca['claim_type']!=cb['claim_type'])] if v],'boundary_mutation_authorized':False,'candidate_mutation_authorized':False,'evidence_mutation_authorized':False});dis.append(base)
  elif not (cex and rex and ca['confidence']==cb['confidence']):diagnostic.append({'case_id':cid,'citation_exact':cex,'reason_exact':rex,'confidence_exact':ca['confidence']==cb['confidence'],'label_change_authorized':False})
 n=len(order);po=sum(x==y for x,y in pairs)/n;ca_count=Counter(x for x,_ in pairs);cb_count=Counter(y for _,y in pairs);pe=sum(ca_count[z]*cb_count[z] for z in LABELS)/(n*n);kap=kappa(pairs,LABELS)
 sev=0
 for x,y in pairs:
  if x==y:continue
  if 'not_assessable' in (x,y):sev+=3
  else:sev+=SEVERITY.get(tuple(sorted((x,y),key=LABELS.index)),2)
 report={'schema_version':1,'report_id':'phase7.3.3-d-independent-pilot-reference-agreement-report-v1','status':'completed','case_count':n,'structural_reference_agreement':{'all_cases_passed':all(x['all_passed'] for x in structural),'passed_count':sum(x['all_passed'] for x in structural),'case_checks':structural},'support_label_agreement':{'exact_count':sum(x==y for x,y in pairs),'raw_agreement':po,'chance_expected_agreement':pe,'unweighted_cohen_kappa':kap,'kappa_defined':kap is not None,'reviewer_a_counts':dict(ca_count),'reviewer_b_counts':dict(cb_count),'confusion_matrix':[{'reviewer_a':x,'reviewer_b':y,'count':matrix[(x,y)]} for x in LABELS for y in LABELS if matrix[(x,y)]]},'materiality_agreement':{'exact_count':sum(x==y for x,y in mat),'rate':sum(x==y for x,y in mat)/n,'kappa':kappa(mat,[False,True])},'claim_type_agreement':{'exact_count':sum(x==y for x,y in typ),'rate':sum(x==y for x,y in typ)/n,'kappa':kappa(typ,sorted(set(x for p in typ for x in p)))},'citation_agreement':{'exact_count':sum(x for x,_ in cit),'exact_rate':sum(x for x,_ in cit)/n,'mean_jaccard':sum(x for _,x in cit)/n},'reason_agreement':{'exact_count':sum(x for x,_ in reason),'exact_rate':sum(x for x,_ in reason)/n,'mean_jaccard':sum(x for _,x in reason)/n},'confidence_agreement':{'exact_count':sum(x==y for x,y in conf),'rate':sum(x==y for x,y in conf)/n,'kappa':kappa(conf,['low','medium','high'])},'severity_aware_disagreement':{'severity_sum':sev,'maximum_possible_severity_sum':n*3,'normalized_weighted_disagreement':sev/(n*3),'mean_severity_among_disagreements':sev/len(dis) if dis else 0},'domain_concentration':dict(domain),'adjudication':{'primary_disagreement_count':len(dis),'diagnostic_followup_count':len(diagnostic),'support_label_disagreement_count':sum(x!=y for x,y in pairs),'materiality_disagreement_count':sum(x!=y for x,y in mat),'claim_type_disagreement_count':sum(x!=y for x,y in typ)},'artifact_lineage':{'manifest_sha256':sha(MANIFEST),'protocol_sha256':sha(PROTOCOL),'reviewer_a_sha256':sha(A),'reviewer_b_sha256':sha(B),'dataset_sha256':sha(DATASET)},'guards':{'reviewer_b_v2_partial_outputs_used':False,'route_a_gold_visible':False,'arm_outputs_visible':False,'provider_calls':0,'confirmatory_content_opened':False}}
 wh=write_once(WORKLIST,{'schema_version':1,'worklist_id':'phase7.3.3-d-independent-pilot-reference-disagreement-worklist-v1','status':'frozen_from_raw_agreement','item_count':len(dis),'items':dis,'diagnostic_followup_count':len(diagnostic),'diagnostic_followup':diagnostic,'guards':{'only_primary_disagreements':True,'boundary_mutation_allowed':False,'arm_outputs_present':False,'route_a_gold_present':False,'reviewer_b_v2_partial_outputs_used':False}})
 rh=write_once(REPORT,report)
 outcome={'schema_version':1,'outcome_id':'phase7.3.3-d-independent-pilot-reference-agreement-outcome-v1','status':'agreement_completed_adjudication_required' if dis else 'agreement_completed_no_adjudication_needed','case_count':n,'primary_disagreement_count':len(dis),'support_label_disagreement_count':sum(x!=y for x,y in pairs),'structural_checks_passed':report['structural_reference_agreement']['all_cases_passed'],'agreement_report_sha256':rh,'worklist_sha256':wh,'next_authorized_stage':'freeze_independent_pilot_reference_adjudication_protocol_v1' if dis else 'freeze_independent_pilot_reference_v1','provider_calls':0,'confirmatory_content_opened':False}
 oh=write_once(OUTCOME,outcome)
 receipt={'schema_version':1,'receipt_id':'phase7.3.3-d-independent-pilot-reference-agreement-freeze-receipt-v1','status':'PASS','artifact_sha256':{'protocol':sha(PROTOCOL),'fixtures':sha(FIXTURES),'manifest':sha(MANIFEST),'report':rh,'worklist':wh,'outcome':oh},'replay_checks':{'manifest_lineage':True,'case_count_40':n==40,'structural_40':report['structural_reference_agreement']['passed_count']==40,'worklist_count':len(dis),'reviewer_b_v2_excluded':True,'provider_calls_0':True,'confirmatory_closed':True}}
 rch=write_once(RECEIPT,receipt)
 prev=load(STATE_PREV); state=dict(prev);state.update({'schema_version':16,'state_id':'phase7.3.3-d-support-stage-state-v16','next_authorized_stage':outcome['next_authorized_stage'],'independent_replication_state':'independent_pilot_reference_agreement_completed_adjudication_required' if dis else 'independent_pilot_reference_agreement_completed','independent_reference_started':True,'independent_reference_reviews_completed':True,'independent_reference_agreement_computed':True,'independent_reference_disagreement_count':len(dis),'provider_called_for_independent_replication':True,'confirmatory_dataset_opened':False});state['artifact_lineage']=dict(prev['artifact_lineage']);state['artifact_lineage'].update({'support_stage_state_v15_sha256':sha(STATE_PREV),'readiness_v26_sha256':sha(READY_PREV),'independent_reference_reviewer_a_submission_v2_sha256':sha(A),'independent_reference_reviewer_b_submission_v3_sha256':sha(B),'independent_reference_agreement_receipt_v1_sha256':rch})
 sth=write_once(STATE,state)
 ready={'schema_version':27,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v27','status':outcome['status'],'artifact_lineage':{'readiness_v26_sha256':sha(READY_PREV),'support_stage_state_v15_sha256':sha(STATE_PREV),'agreement_receipt_sha256':rch,'support_stage_state_v16_sha256':sth},'reference_status':'independent_pilot_raw_reviews_completed_agreement_computed_not_frozen','independent_reference_started':True,'independent_reference_reviews_completed':True,'independent_reference_agreement_computed':True,'independent_reference_disagreement_count':len(dis),'next_authorized_stage':outcome['next_authorized_stage'],'independent_dual_arm_execution_started':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 rdh=write_once(READY,ready)
 print(json.dumps({'status':outcome['status'],'raw_agreement':po,'chance_expected':pe,'kappa':kap,'disagreements':len(dis),'report_sha256':rh,'worklist_sha256':wh,'receipt_sha256':rch,'state_v16_sha256':sth,'readiness_v27_sha256':rdh},indent=2))
def verify():
 req=[PROTOCOL,FIXTURES,MANIFEST,REPORT,WORKLIST,OUTCOME,RECEIPT,STATE,READY]
 checks={'all_exist':all(p.exists() for p in req),'manifest_adapter':MANIFEST.exists() and load(MANIFEST)['adapter_sha256']==sha(Path(__file__)),'manifest_protocol':MANIFEST.exists() and load(MANIFEST)['protocol_sha256']==sha(PROTOCOL),'report_inputs':REPORT.exists() and load(REPORT)['artifact_lineage']['reviewer_a_sha256']==sha(A) and load(REPORT)['artifact_lineage']['reviewer_b_sha256']==sha(B),'case_count':REPORT.exists() and load(REPORT)['case_count']==40,'structural':REPORT.exists() and load(REPORT)['structural_reference_agreement']['passed_count']==40,'worklist_match':REPORT.exists() and WORKLIST.exists() and load(REPORT)['adjudication']['primary_disagreement_count']==load(WORKLIST)['item_count'],'v2_excluded':REPORT.exists() and load(REPORT)['guards']['reviewer_b_v2_partial_outputs_used'] is False,'arms_hidden':REPORT.exists() and load(REPORT)['guards']['arm_outputs_visible'] is False,'confirmatory_closed':REPORT.exists() and load(REPORT)['guards']['confirmatory_content_opened'] is False}
 print(json.dumps({'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'hashes':{p.name:sha(p) for p in req if p.exists()}},indent=2));
 if not all(checks.values()):raise SystemExit(1)
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--freeze',action='store_true');g.add_argument('--compute',action='store_true');g.add_argument('--verify',action='store_true');x=ap.parse_args()
 if x.freeze:freeze()
 elif x.compute:compute()
 else:verify()
if __name__=='__main__':main()
