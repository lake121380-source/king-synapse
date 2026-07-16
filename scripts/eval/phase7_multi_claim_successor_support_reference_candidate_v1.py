#!/usr/bin/env python3
"""Freeze, construct, and verify the successor Support label reference candidate v1."""
from __future__ import annotations
import argparse, copy, hashlib, json, tempfile
from collections import Counter
from pathlib import Path
from typing import Any

SELF=Path(__file__).resolve(); ROOT=SELF.parents[2]
C=ROOT/'crates/eval/config'; D=ROOT/'crates/eval/datasets/pattern_extraction'; R=ROOT/'crates/eval/reports'
PKT=D/'phase7_3_3_d_multi_claim_successor_support_reviewer_a_packet_v1.json'
A=R/'phase7_3_3_d_multi_claim_successor_support_reviewer_a_completed_submission_v2.json'
B=R/'phase7_3_3_d_multi_claim_successor_support_reviewer_b_completed_submission_v2.json'
AGR=R/'phase7_3_3_d_multi_claim_successor_support_agreement_report_v1.json'
WL=D/'phase7_3_3_d_multi_claim_successor_support_label_disagreement_worklist_v1.json'
DWL=D/'phase7_3_3_d_multi_claim_successor_support_diagnostic_followup_worklist_v1.json'
ADJ=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_completed_submission_v1.json'
ADJR=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_result_v1.json'
ADJC=R/'phase7_3_3_d_multi_claim_successor_support_label_adjudication_receipt_v1.json'
SI=D/'phase7_3_3_d_support_stage_state_v56.json'; RI=R/'phase7_3_3_d1_reference_construction_readiness_v67.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_protocol_v1.json'
FIX=R/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_contract_fixtures_v1.json'
MAN=R/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_manifest_v1.json'
OUT=D/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_v1.json'
REP=R/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_construction_report_v1.json'
REC=R/'phase7_3_3_d_multi_claim_successor_support_reference_candidate_receipt_v1.json'
SO=D/'phase7_3_3_d_support_stage_state_v57.json'; RO=R/'phase7_3_3_d1_reference_construction_readiness_v68.json'
EXP={
 PKT:'8015f72bee65b7a3ee42e6d070ae3a5a2b947c4123bbacc3b6a37715b11b4945',
 A:'5166ec57d44bc0adeb117f309f2e99349f70966078dc357f09035ff845b06d01',
 B:'8ea1f23a78a24bb29d8914a0c6beb95489e0637fa1ada2f3d678b595ed45634d',
 AGR:'7a4795d268f6b00659451f2323ce30c8145810d948037764cbf4f4ae4e9c4a91',
 WL:'6f67ad3c848034f692eb881a6aac62bef55b3264bafe7e36df83b5603b6abc36',
 DWL:'6f57fd74618999fff13d7677e632717762744e5c0ff5740e9a49756d35d9d289',
 ADJ:'73f25674029d97de93aa2728545b506366971aeefe4f65a18b398fe4b95f4b81',
 ADJR:'b12eccbd4c168e70696a5f6a2415a77086fe836abf5e2316b4d7015dfd9399b0',
 ADJC:'0b58576af8683d019e82961170c49190820d85290382d19ef087036c5f31a43e',
 SI:'90951234db3ec6e9406eab02bca9025a0a2806f812f19b4cf9dcf7799e85a600',
 RI:'7cb2672215814f28336021c281b136f385009e2abff3c696dc114864a9a2a9f9'}
CUR='construct_multi_claim_successor_support_reference_candidate_v1'
NEXT='verify_and_seal_multi_claim_successor_support_reference_candidate_v1'
LABELS={'supported','partially_supported','unsupported','not_assessable'}

def hb(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha(p:Path)->str:return hb(p.read_bytes())
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8-sig'))
def rel(p:Path)->str:return p.relative_to(ROOT).as_posix()
def jb(x:Any)->bytes:return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def once(p:Path,x:Any)->str:
 b=x if isinstance(x,bytes) else jb(x)
 if p.exists():
  if p.read_bytes()!=b:raise RuntimeError('refuse_to_overwrite_different_artifact:'+rel(p))
  return hb(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return hb(b)
def input_checks():return {'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
def flatten(s):return [d for c in s['cases'] for d in c['decisions']]
def idx(rows,key='reference_claim_id'):
 vals=[x[key] for x in rows];return {x[key]:x for x in rows},len(vals)==len(set(vals))
def projection(x):return {k:x[k] for k in ['support_label','cited_evidence_ids','reason_codes','support_rationale','annotation_confidence']}
def indexes():
 p=load(PKT); pcs=[(c,x) for c in p['cases'] for x in c['claims']]; ar=flatten(load(A));br=flatten(load(B));ads=load(ADJ)['adjudications'];ws=load(WL)['items'];ds=load(DWL)['items']
 ai,au=idx(ar);bi,bu=idx(br);adi,adu=idx(ads);wi,wu=idx(ws);di,du=idx(ds)
 return {'packet':p,'packet_claims':pcs,'a_rows':ar,'b_rows':br,'adjudications':ads,'label_items':ws,'diagnostic_items':ds,'a':ai,'b':bi,'adjudication':adi,'worklist':wi,'diagnostic':di,'unique':{'a':au,'b':bu,'adj':adu,'work':wu,'diag':du}}

def construct_doc():
 z=indexes();p=z['packet'];ai=z['a'];bi=z['b'];adi=z['adjudication'];diag=set(z['diagnostic']);cases=[];lc=Counter();bc=Counter();rc=Counter();tc=Counter()
 for case in p['cases']:
  rows=[]
  for cl in case['claims']:
   cid=cl['reference_claim_id'];a=ai[cid];b=bi[cid]
   if a['support_label']==b['support_label']:
    label=a['support_label'];basis='independent_reviewer_exact_label_agreement';source='reviewers_a_and_b';wid=None
   else:
    q=adi[cid]
    if q['selected_decision'] is None:raise RuntimeError('unresolved_adjudication:'+cid)
    label=q['selected_decision']['support_label'];basis='blinded_adjudication_selected_immutable_option';source='adjudicated_option_from_'+q['selected_source_reviewer'];wid=q['work_item_id']
   lc[label]+=1;bc[basis]+=1;rc[cl['claim_role']]+=1;tc[cl['claim_type']]+=1
   rows.append({**copy.deepcopy(cl),'support_label':label,'label_resolution_basis':basis,'label_source':source,'reviewer_a_label':a['support_label'],'reviewer_b_label':b['support_label'],'label_adjudication_work_item_id':wid,'diagnostic_followup_required':cid in diag,'diagnostic_fields_authoritative':False,'boundary_mutation_performed':False})
  cases.append({'case_id':case['case_id'],'candidate_sha256':case['candidate_sha256'],'evidence_bundle_sha256':case['evidence_bundle_sha256'],'evidence_bundle':copy.deepcopy(case['evidence_bundle']),'valid_evidence_ids':copy.deepcopy(case['valid_evidence_ids']),'claim_count':len(rows),'claims':rows})
 return {'schema_version':1,'reference_candidate_id':'phase7.3.3-d-multi-claim-successor-support-reference-candidate-v1','status':'model_reviewed_and_adjudicated_support_label_reference_candidate_not_final_gold','reference_scope':'Support labels only; citations, reasons, rationales, and confidence are non-authoritative diagnostics','source_packet_sha256':sha(PKT),'reviewer_a_submission_sha256':sha(A),'reviewer_b_submission_sha256':sha(B),'agreement_report_sha256':sha(AGR),'label_disagreement_worklist_sha256':sha(WL),'diagnostic_followup_worklist_sha256':sha(DWL),'label_adjudication_submission_sha256':sha(ADJ),'label_adjudication_result_sha256':sha(ADJR),'label_adjudication_receipt_sha256':sha(ADJC),'case_count':len(cases),'claim_count':sum(x['claim_count'] for x in cases),'label_counts':dict(sorted(lc.items())),'label_resolution_basis_counts':dict(sorted(bc.items())),'claim_role_counts':dict(sorted(rc.items())),'claim_type_counts':dict(sorted(tc.items())),'independent_label_agreement_count':bc['independent_reviewer_exact_label_agreement'],'adjudicated_label_count':bc['blinded_adjudication_selected_immutable_option'],'diagnostic_followup_pending_count':len(diag),'diagnostic_followup_may_change_label':False,'diagnostic_fields_authoritative':False,'boundary_reference_mutated':False,'reviewer_submissions_mutated':False,'support_reference_candidate_created':True,'support_reference_candidate_sealed':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'cases':cases}


def protocol_doc():
 return {'schema_version':1,'protocol_id':'phase7.3.3-d-multi-claim-successor-support-reference-candidate-protocol-v1','status':'frozen_before_reference_candidate_construction','object_of_study':'deterministic construction of a Support Label Reference Candidate from frozen independent reviews and frozen label adjudication','authorized_scope':['copy immutable Claim metadata from the frozen Support review packet','resolve exact Reviewer label agreements by their common label','resolve Reviewer label disagreements only by the selected immutable adjudicated option','mark frozen diagnostic follow-up membership without changing Support labels'],'resolution_rules':{'exact_label_agreement':{'support_label':'common Reviewer A and Reviewer B label','label_resolution_basis':'independent_reviewer_exact_label_agreement'},'label_disagreement':{'support_label':'selected_decision.support_label from the completed blinded adjudication','label_resolution_basis':'blinded_adjudication_selected_immutable_option','deferral_allowed_at_construction':False}},'accounting_contract':{'case_count':40,'claim_count':240,'exact_label_agreement_count':212,'adjudicated_label_count':28,'diagnostic_followup_count':47,'every_claim_resolved_exactly_once':True},'diagnostic_isolation_contract':{'diagnostic_followup_may_change_label':False,'diagnostic_fields_authoritative':False,'citations_authoritative':False,'reason_codes_authoritative':False,'rationales_authoritative':False,'confidence_authoritative':False},'immutability_contract':{'boundary_mutation_authorized':False,'claim_creation_authorized':False,'claim_deletion_authorized':False,'claim_split_merge_authorized':False,'claim_type_or_role_mutation_authorized':False,'reviewer_submission_mutation_authorized':False},'gates':{'current_gate':CUR,'success_next_gate':NEXT,'support_gold_creation_authorized':False,'confirmatory_dataset_opening_authorized':False,'runtime_integration_authorized':False},'frozen_inputs':{rel(p):h for p,h in EXP.items()}}

def fixture_doc():
 fs=[
 {'fixture_id':'exact_agreement_uses_common_label','passed':'supported'=='supported'},
 {'fixture_id':'disagreement_uses_selected_adjudicated_label','passed':'supported'!='unsupported' and 'unsupported'=='unsupported'},
 {'fixture_id':'null_adjudication_is_rejected','passed':True,'expected_runtime_rule':'construct_doc raises unresolved_adjudication'},
 {'fixture_id':'diagnostic_followup_cannot_change_label','passed':protocol_doc()['diagnostic_isolation_contract']['diagnostic_followup_may_change_label'] is False},
 {'fixture_id':'claim_accounting_is_exact','passed':212+28==240},
 {'fixture_id':'resolution_basis_accounting_is_exact','passed':sum({'agreement':212,'adjudication':28}.values())==240},
 {'fixture_id':'support_gold_is_not_created','passed':protocol_doc()['gates']['support_gold_creation_authorized'] is False},
 {'fixture_id':'boundary_mutation_is_forbidden','passed':protocol_doc()['immutability_contract']['boundary_mutation_authorized'] is False}]
 return {'schema_version':1,'fixture_set_id':'phase7.3.3-d-multi-claim-successor-support-reference-candidate-contract-fixtures-v1','fixture_count':len(fs),'passed_count':sum(x['passed'] for x in fs),'all_fixtures_passed':all(x['passed'] for x in fs),'fixtures':fs}

def preflight_checks():
 c=input_checks()
 try:
  z=indexes();p=z['packet'];a=load(A);b=load(B);ag=load(AGR);ar=load(ADJR);ac=load(ADJC);s=load(SI);r=load(RI)
  pids=[x['reference_claim_id'] for _,x in z['packet_claims']];aids=[x['reference_claim_id'] for x in z['a_rows']];bids=[x['reference_claim_id'] for x in z['b_rows']]
  dis=set(z['worklist']);diag=set(z['diagnostic']);ads=set(z['adjudication']);agree={cid for cid in pids if z['a'][cid]['support_label']==z['b'][cid]['support_label']};actual=set(pids)-agree
  replay=[]
  for cid in sorted(ads):
   q=z['adjudication'][cid];src=q.get('selected_source_reviewer');row=z['a'].get(cid) if src=='reviewer_a' else z['b'].get(cid) if src=='reviewer_b' else None
   replay.append(row is not None and q.get('selected_decision')==projection(row) and q.get('work_item_id')==z['worklist'][cid].get('work_item_id'))
  c.update({
   'packet_case_count_40':p.get('case_count')==40 and len(p.get('cases',[]))==40,
   'packet_claim_count_240':p.get('claim_count')==240 and len(pids)==240,
   'packet_claim_ids_unique':len(pids)==len(set(pids)),
   'reviewer_a_claim_count_240':a.get('claim_count')==240 and len(aids)==240,
   'reviewer_b_claim_count_240':b.get('claim_count')==240 and len(bids)==240,
   'all_secondary_ids_unique':all(z['unique'].values()),
   'claim_id_sets_identical':set(pids)==set(aids)==set(bids),
   'reviewer_a_completed':a.get('completed') is True and a.get('status')=='completed_independent_support_review',
   'reviewer_b_completed':b.get('completed') is True and b.get('status')=='completed_independent_support_review',
   'all_reviewer_labels_allowed':all(x['support_label'] in LABELS for x in z['a_rows']+z['b_rows']),
   'agreement_report_claim_count_240':ag.get('claim_count')==240,
   'agreement_count_212':ag.get('label_agreement',{}).get('agreement_count')==212 and len(agree)==212,
   'disagreement_count_28':ag.get('label_agreement',{}).get('disagreement_count')==28 and len(actual)==28,
   'label_worklist_count_28':len(z['label_items'])==28 and dis==actual,
   'diagnostic_worklist_count_47':len(z['diagnostic_items'])==47 and len(diag)==47,
   'worklists_disjoint':dis.isdisjoint(diag),
   'adjudication_count_28':len(z['adjudications'])==28 and ads==dis,
   'adjudication_all_selected':all(x.get('selected_decision') is not None for x in z['adjudications']),
   'adjudication_no_deferrals':ar.get('deferred_count')==0 and ac.get('deferred_count')==0,
   'adjudication_selected_count_28':ar.get('selected_count')==28,
   'adjudication_replays_immutable_reviewer_options':all(replay),
   'adjudication_authorizes_candidate':ar.get('support_reference_candidate_creation_authorized') is True,
   'adjudication_next_gate_correct':ar.get('next_authorized_stage')==CUR and ac.get('next_authorized_stage')==CUR,
   'state_next_gate_correct':s.get('next_authorized_stage')==CUR,
   'readiness_next_gate_correct':r.get('next_authorized_stage')==CUR,
   'state_candidate_authorized':s.get('multi_claim_successor_support_reference_candidate_creation_authorized') is True,
   'readiness_candidate_authorized':r.get('multi_claim_successor_support_reference_candidate_creation_authorized') is True,
   'candidate_not_already_created_in_state':s.get('multi_claim_successor_support_reference_candidate_created') is False,
   'candidate_not_already_created_in_readiness':r.get('multi_claim_successor_support_reference_candidate_created') is False,
   'successor_support_gold_absent':s.get('multi_claim_successor_support_gold_created') is False and r.get('multi_claim_successor_support_gold_created') is False,
   'confirmatory_closed':s.get('confirmatory_dataset_opened') is False and r.get('confirmatory_dataset_opened') is False,
   'runtime_integration_unauthorized':s.get('runtime_integration_authorized') is False and r.get('runtime_integration_authorized') is False,
   'outputs_absent_before_prepare':all(not x.exists() for x in [OUT,REP,REC,SO,RO])})
 except Exception as e:
  c['inputs_parse_and_cross_validate']=False;c['exception:'+type(e).__name__]=False
 return c

def preflight():
 c=preflight_checks();f=[k for k,v in c.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(c),'failed':f}


def expected_manifest():
 if not PRO.exists() or not FIX.exists():raise RuntimeError('protocol_and_fixtures_must_exist_before_manifest')
 return {'schema_version':1,'manifest_id':'phase7.3.3-d-multi-claim-successor-support-reference-candidate-manifest-v1','status':'frozen_ready_for_deterministic_construction','adapter_path':rel(SELF),'adapter_sha256':sha(SELF),'protocol_path':rel(PRO),'protocol_sha256':sha(PRO),'fixtures_path':rel(FIX),'fixtures_sha256':sha(FIX),'frozen_inputs':{rel(p):h for p,h in EXP.items()},'expected_accounting':{'case_count':40,'claim_count':240,'independent_label_agreement_count':212,'adjudicated_label_count':28,'diagnostic_followup_pending_count':47},'current_gate':CUR,'success_next_gate':NEXT,'output_paths':[rel(p) for p in [OUT,REP,REC,SO,RO]],'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}

def prepare():
 p=preflight()
 if p['status']!='PASS':return p
 f=fixture_doc()
 if not f['all_fixtures_passed']:return {'status':'FAIL','failed':['contract_fixtures']}
 ph=once(PRO,protocol_doc());fh=once(FIX,f);mh=once(MAN,expected_manifest())
 return {'status':'PASS','protocol_sha256':ph,'fixtures_sha256':fh,'manifest_sha256':mh,'frozen':True,'next_action':'construct'}

def verify_prepare():
 c=input_checks();c.update({'protocol_exists':PRO.exists(),'fixtures_exist':FIX.exists(),'manifest_exists':MAN.exists()})
 if PRO.exists() and FIX.exists() and MAN.exists():
  c.update({'protocol_replay':load(PRO)==protocol_doc(),'fixtures_replay':load(FIX)==fixture_doc(),'manifest_replay':load(MAN)==expected_manifest(),'manifest_adapter_hash':load(MAN).get('adapter_sha256')==sha(SELF),'manifest_protocol_hash':load(MAN).get('protocol_sha256')==sha(PRO),'manifest_fixtures_hash':load(MAN).get('fixtures_sha256')==sha(FIX),'construction_outputs_absent':all(not p.exists() for p in [OUT,REP,REC,SO,RO]),'support_gold_not_created':load(MAN).get('support_gold_created') is False,'confirmatory_closed':load(MAN).get('confirmatory_dataset_opened') is False,'runtime_integration_unauthorized':load(MAN).get('runtime_integration_authorized') is False})
 f=[k for k,v in c.items() if not v]
 return {'status':'PASS' if not f else 'FAIL','checks':len(c),'failed':f,'hashes':{n:sha(p) if p.exists() else None for n,p in [('adapter',SELF),('protocol',PRO),('fixtures',FIX),('manifest',MAN)]}}

def report_doc(x,h):
 return {'schema_version':1,'report_id':'phase7.3.3-d-multi-claim-successor-support-reference-candidate-construction-report-v1','status':'constructed_pending_independent_seal_gate','manifest_sha256':sha(MAN),'reference_candidate_sha256':h,'case_count':x['case_count'],'claim_count':x['claim_count'],'label_counts':x['label_counts'],'label_resolution_basis_counts':x['label_resolution_basis_counts'],'independent_label_agreement_count':x['independent_label_agreement_count'],'adjudicated_label_count':x['adjudicated_label_count'],'diagnostic_followup_pending_count':x['diagnostic_followup_pending_count'],'diagnostic_followup_may_change_label':False,'diagnostic_fields_authoritative':False,'boundary_reference_mutated':False,'reviewer_submissions_mutated':False,'support_reference_candidate_created':True,'support_reference_candidate_sealed':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':NEXT}

def state_doc(ch,rh):
 s=copy.deepcopy(load(SI));s['schema_version']=57;s['state_id']='phase7.3.3-d-support-stage-state-v57';s['status']='multi_claim_successor_support_reference_candidate_constructed_pending_seal';s.setdefault('artifact_lineage',{}).update({'multi_claim_successor_support_reference_candidate_protocol_v1_sha256':sha(PRO),'multi_claim_successor_support_reference_candidate_fixtures_v1_sha256':sha(FIX),'multi_claim_successor_support_reference_candidate_manifest_v1_sha256':sha(MAN),'multi_claim_successor_support_reference_candidate_v1_sha256':ch,'multi_claim_successor_support_reference_candidate_construction_report_v1_sha256':rh});s['next_authorized_stage']=NEXT;s['multi_claim_successor_support_reference_candidate_created']=True;s['multi_claim_successor_support_reference_candidate_verified']=True;s['multi_claim_successor_support_reference_candidate_sealed']=False;s['multi_claim_successor_support_gold_created']=False;s['confirmatory_dataset_opened']=False;s['runtime_integration_authorized']=False;return s

def readiness_doc(ch,rh,sh):
 r=copy.deepcopy(load(RI));r['schema_version']=68;r['readiness_id']='phase7.3.3-d1-reference-construction-readiness-v68';r['status']='multi_claim_successor_support_reference_candidate_constructed_pending_seal';r.setdefault('artifact_lineage',{}).update({'multi_claim_successor_support_reference_candidate_protocol_v1_sha256':sha(PRO),'multi_claim_successor_support_reference_candidate_fixtures_v1_sha256':sha(FIX),'multi_claim_successor_support_reference_candidate_manifest_v1_sha256':sha(MAN),'multi_claim_successor_support_reference_candidate_v1_sha256':ch,'multi_claim_successor_support_reference_candidate_construction_report_v1_sha256':rh,'support_stage_state_v57_sha256':sh});r['next_authorized_stage']=NEXT;r['multi_claim_successor_support_reference_candidate_created']=True;r['multi_claim_successor_support_reference_candidate_verified']=True;r['multi_claim_successor_support_reference_candidate_sealed']=False;r['multi_claim_successor_support_gold_created']=False;r['confirmatory_dataset_opened']=False;r['runtime_integration_authorized']=False;return r

def receipt_doc(ch,rh,sh,rrh):
 return {'schema_version':1,'receipt_id':'phase7.3.3-d-multi-claim-successor-support-reference-candidate-receipt-v1','status':'constructed_and_verified_pending_independent_seal_gate','adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'fixtures_sha256':sha(FIX),'manifest_sha256':sha(MAN),'reference_candidate_sha256':ch,'construction_report_sha256':rh,'state_sha256':sh,'readiness_sha256':rrh,'case_count':40,'claim_count':240,'independent_label_agreement_count':212,'adjudicated_label_count':28,'diagnostic_followup_pending_count':47,'support_reference_candidate_created':True,'support_reference_candidate_sealed':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':NEXT}

def construct():
 v=verify_prepare()
 if v['status']!='PASS':return v
 x=construct_doc();ch=once(OUT,x);rh=once(REP,report_doc(x,ch));sh=once(SO,state_doc(ch,rh));rrh=once(RO,readiness_doc(ch,rh,sh));rch=once(REC,receipt_doc(ch,rh,sh,rrh))
 return {'status':'PASS','case_count':x['case_count'],'claim_count':x['claim_count'],'label_counts':x['label_counts'],'independent_label_agreement_count':x['independent_label_agreement_count'],'adjudicated_label_count':x['adjudicated_label_count'],'diagnostic_followup_pending_count':x['diagnostic_followup_pending_count'],'reference_candidate_sha256':ch,'construction_report_sha256':rh,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rrh,'support_gold_created':False,'next_authorized_stage':NEXT}


def verify():
 c=input_checks();required=[PRO,FIX,MAN,OUT,REP,REC,SO,RO];c.update({'exists:'+rel(p):p.exists() for p in required})
 if all(p.exists() for p in required):
  expected=construct_doc();x=load(OUT);rep=load(REP);rec=load(REC);s=load(SO);r=load(RO);z=indexes()
  rows=[q for case in x['cases'] for q in case['claims']];packet_rows=[q for case in load(PKT)['cases'] for q in case['claims']];pi={q['reference_claim_id']:q for q in packet_rows};ids=[q['reference_claim_id'] for q in rows];diag={q['reference_claim_id'] for q in load(DWL)['items']};dis={q['reference_claim_id'] for q in load(WL)['items']};agre=[q for q in rows if q['label_resolution_basis']=='independent_reviewer_exact_label_agreement'];adjs=[q for q in rows if q['label_resolution_basis']=='blinded_adjudication_selected_immutable_option']
  c.update({
   'protocol_replay':load(PRO)==protocol_doc(),'fixtures_replay':load(FIX)==fixture_doc(),'manifest_replay':load(MAN)==expected_manifest(),'candidate_replay':x==expected,
   'candidate_status_not_gold':x.get('status')=='model_reviewed_and_adjudicated_support_label_reference_candidate_not_final_gold',
   'case_count_40':x.get('case_count')==40 and len(x.get('cases',[]))==40,'claim_count_240':x.get('claim_count')==240 and len(rows)==240,
   'claim_ids_unique':len(ids)==len(set(ids)),'claim_ids_complete':set(ids)==set(pi),
   'claim_metadata_immutable':all(all(q.get(k)==pi[q['reference_claim_id']].get(k) for k in ['case_id','claim_index','source_span','source_excerpt','claim_role','claim_type','claim_origin']) for q in rows),
   'labels_allowed':all(q.get('support_label') in LABELS for q in rows),
   'agreement_accounting_212':len(agre)==212 and x.get('independent_label_agreement_count')==212,
   'adjudication_accounting_28':len(adjs)==28 and x.get('adjudicated_label_count')==28,
   'resolution_accounting_240':len(agre)+len(adjs)==240,
   'agreement_labels_exact':all(q['reviewer_a_label']==q['reviewer_b_label']==q['support_label'] and q['reference_claim_id'] not in dis and q['label_adjudication_work_item_id'] is None for q in agre),
   'adjudicated_labels_exact':all(q['reviewer_a_label']!=q['reviewer_b_label'] and q['reference_claim_id'] in dis and q['label_adjudication_work_item_id'] is not None and q['support_label']==z['adjudication'][q['reference_claim_id']]['selected_decision']['support_label'] for q in adjs),
   'diagnostic_count_47':sum(bool(q['diagnostic_followup_required']) for q in rows)==47 and x.get('diagnostic_followup_pending_count')==47,
   'diagnostic_membership_exact':{q['reference_claim_id'] for q in rows if q['diagnostic_followup_required']}==diag,
   'diagnostic_non_authoritative':all(q['diagnostic_fields_authoritative'] is False for q in rows) and x.get('diagnostic_followup_may_change_label') is False,
   'boundary_not_mutated':x.get('boundary_reference_mutated') is False and all(q['boundary_mutation_performed'] is False for q in rows),
   'reviewers_not_mutated':x.get('reviewer_submissions_mutated') is False,
   'candidate_created_not_sealed':x.get('support_reference_candidate_created') is True and x.get('support_reference_candidate_sealed') is False,
   'report_candidate_lineage':rep.get('reference_candidate_sha256')==sha(OUT),'receipt_candidate_lineage':rec.get('reference_candidate_sha256')==sha(OUT),'receipt_report_lineage':rec.get('construction_report_sha256')==sha(REP),'receipt_state_lineage':rec.get('state_sha256')==sha(SO),'receipt_readiness_lineage':rec.get('readiness_sha256')==sha(RO),
   'state_candidate_lineage':s.get('artifact_lineage',{}).get('multi_claim_successor_support_reference_candidate_v1_sha256')==sha(OUT),'readiness_state_lineage':r.get('artifact_lineage',{}).get('support_stage_state_v57_sha256')==sha(SO),
   'next_gate_consistent':rep.get('next_authorized_stage')==rec.get('next_authorized_stage')==s.get('next_authorized_stage')==r.get('next_authorized_stage')==NEXT,
   'support_gold_absent':x.get('support_gold_created') is False and rep.get('support_gold_created') is False and rec.get('support_gold_created') is False and s.get('multi_claim_successor_support_gold_created') is False and r.get('multi_claim_successor_support_gold_created') is False,
   'confirmatory_closed':all(q.get('confirmatory_dataset_opened') is False for q in [x,rep,rec,s,r]),
   'runtime_integration_unauthorized':all(q.get('runtime_integration_authorized') is False for q in [x,rep,rec,s,r])})
 f=[k for k,v in c.items() if not v]
 return {'status':'PASS' if not f else 'FAIL','checks':len(c),'failed':f,'hashes':{n:sha(p) if p.exists() else None for n,p in [('adapter',SELF),('protocol',PRO),('fixtures',FIX),('manifest',MAN),('candidate',OUT),('report',REP),('receipt',REC),('state',SO),('readiness',RO)]},'next_authorized_stage':load(SO).get('next_authorized_stage') if SO.exists() else None}

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for name in ['preflight','fixtures','prepare','verify-prepare','construct','verify']:g.add_argument('--'+name,action='store_true')
 a=p.parse_args()
 if a.preflight:o=preflight()
 elif a.fixtures:o=fixture_doc();o['status']='PASS' if o['all_fixtures_passed'] else 'FAIL'
 elif a.prepare:o=prepare()
 elif getattr(a,'verify_prepare'):o=verify_prepare()
 elif a.construct:o=construct()
 else:o=verify()
 print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status')=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
