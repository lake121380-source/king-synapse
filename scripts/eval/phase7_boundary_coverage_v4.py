#!/usr/bin/env python3
"""Deterministic Phase 7.3.3-D1-B Boundary Coverage QA for frozen V4 adjudication."""
from __future__ import annotations
import argparse, hashlib, json, tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'crates/eval/datasets/pattern_extraction'; CONFIG=ROOT/'crates/eval/config'; REPORTS=ROOT/'crates/eval/reports'
PACKET=DATA/'phase7_3_3_d_boundary_blind_review_packet_v1.json'
POLICY=CONFIG/'phase7_3_3_d_boundary_coverage_policy_v1.json'
WORKLIST=REPORTS/'phase7_3_3_d_boundary_adjudication_worklist_a_e_v3.json'
V4_MANIFEST=REPORTS/'phase7_3_3_d_boundary_adjudicator_execution_manifest_v4.json'
SUBMISSION=REPORTS/'phase7_3_3_d_boundary_adjudicator_submission_v4.json'
DECISION_LOG=REPORTS/'phase7_3_3_d_segmentation_decision_log_v4.json'
EXECUTION_RESULT=REPORTS/'phase7_3_3_d_boundary_adjudicator_execution_result_v4.json'
READINESS_V5=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v5.json'
COVERAGE_MANIFEST=REPORTS/'phase7_3_3_d_boundary_coverage_execution_manifest_v4.json'
COVERAGE_REPORT=REPORTS/'phase7_3_3_d_boundary_coverage_report_v4.json'
GAP_WORKLIST=REPORTS/'phase7_3_3_d_boundary_coverage_gap_worklist_v1.json'
READINESS_V6=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v6.json'
EXPECTED={
 'boundary_packet':'38fba5a20c560704c7aedfd441c39c428dcdb4774cc0395d51d84b33c507197a',
 'coverage_policy':'e3d78c1ba231b6ed097e2e1ed580aef209e29080bd43b73f24016511dc6227b4',
 'worklist':'56132cc9977ec579c4a668f30dcdaa3818c94a528f7feb16dfd5920cda67afaf',
 'v4_manifest':'b6dc0695eb70828d08b456b5429b17d21da1fa91017fd6191210c8f9eadcab73',
 'v4_submission':'308e54406a3aa8d0ba8b8526d57497ca4ca7f4c9a776e2831e7e60b4f0e40298',
 'v4_decision_log':'b045970c97230a2f95efa9af8f22a27cf9e4f507821571948aa7c2f087ab6dad',
 'v4_execution_result':'016ec926a646e19358b90a71c0d016d9e9e64390b95cc30a50ca5ce64f0f8208',
 'readiness_v5':'52e5c078a9df77569c21f463d1a38fbf6a4bba4664699f88b8f387e8d5f8c520'}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def text_sha(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()
def load(path): return json.loads(path.read_text(encoding='utf-8'))
def payload(value): return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def write_once(path,value):
 data=payload(value)
 if path.exists():
  if path.read_bytes()!=data: raise ValueError(f'frozen_artifact_changed:{path.relative_to(ROOT)}')
  return hashlib.sha256(data).hexdigest()
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=path.parent,delete=False) as handle:
  handle.write(data); temporary=Path(handle.name)
 temporary.replace(path); return hashlib.sha256(data).hexdigest()

def verify_hashes():
 paths={'boundary_packet':PACKET,'coverage_policy':POLICY,'worklist':WORKLIST,'v4_manifest':V4_MANIFEST,'v4_submission':SUBMISSION,'v4_decision_log':DECISION_LOG,'v4_execution_result':EXECUTION_RESULT,'readiness_v5':READINESS_V5}
 observed={name:sha(path) for name,path in paths.items()}
 for name,expected in EXPECTED.items():
  if observed[name]!=expected: raise ValueError(f'frozen_input_hash_mismatch:{name}:{observed[name]}:{expected}')
 return observed

def indexes(packet,worklist):
 order=[]; packet_anchors={}; worklist_anchors={}
 for case in packet['cases']:
  for anchor in case['source_anchors']:
   key=(case['case_id'],anchor['anchor_id'])
   if key in packet_anchors: raise ValueError(f'duplicate_packet_anchor:{key}')
   if text_sha(anchor['source_text'])!=anchor['source_text_sha256']: raise ValueError(f'packet_text_hash_mismatch:{key}')
   order.append(key); packet_anchors[key]=anchor
 for case in worklist['cases']:
  for anchor in case['source_anchors']:
   key=(case['case_id'],anchor['anchor_id'])
   if key in worklist_anchors: raise ValueError(f'duplicate_worklist_anchor:{key}')
   frozen=packet_anchors.get(key)
   if frozen is None: raise ValueError(f'worklist_unknown_anchor:{key}')
   for field in ('source_field','source_index','source_text','source_text_sha256'):
    if anchor[field]!=frozen[field]: raise ValueError(f'worklist_packet_mismatch:{key}:{field}')
   ids=set()
   for reviewer_key in ('reviewer_a_claims','reviewer_e_claims'):
    claims=anchor.get(reviewer_key)
    if not isinstance(claims,list): raise ValueError(f'worklist_claims_invalid:{key}:{reviewer_key}')
    for claim in claims:
     cid=claim.get('reviewer_claim_id')
     if not isinstance(cid,str) or not cid or cid in ids: raise ValueError(f'reviewer_id_invalid:{key}:{cid}')
     ids.add(cid); span=claim.get('source_span',{}); start,end=span.get('start'),span.get('end'); source=anchor['source_text']
     if not isinstance(start,int) or isinstance(start,bool) or not isinstance(end,int) or isinstance(end,bool) or start<0 or end<=start or end>len(source): raise ValueError(f'reviewer_span_invalid:{key}:{cid}')
     if claim.get('claim_text')!=source[start:end]: raise ValueError(f'reviewer_text_mismatch:{key}:{cid}')
   worklist_anchors[key]=anchor
 if set(worklist_anchors)!=set(packet_anchors): raise ValueError('worklist_packet_anchor_set_mismatch')
 return order,packet_anchors,worklist_anchors

def occurrences(source,excerpt):
 starts=[]; cursor=0
 while True:
  found=source.find(excerpt,cursor)
  if found<0:return starts
  starts.append(found);cursor=found+1

def span_set(claims): return {(c['source_span']['start'],c['source_span']['end']) for c in claims}
def category(a,e,final):
 if final==a==e:return 'consensus_exact'
 if final==a:return 'keep_a_segmentation'
 if final==e:return 'keep_e_segmentation'
 if len(final)<len(a) and len(final)<len(e):return 'merge_both'
 if len(final)>len(a) and len(final)>len(e):return 'split_both'
 return 'new_segmentation'

def replay_log(worklist,claims,manifest_hash,submission_hash):
 final_by=defaultdict(list)
 for claim in claims: final_by[claim['anchor_id']].append(claim)
 entries=[]; categories=Counter(); reasons=Counter(); per_case={}
 for case in worklist['cases']:
  cc=Counter()
  for anchor in case['source_anchors']:
   aid=anchor['anchor_id']; finals=final_by.get(aid,[])
   if not finals: raise ValueError(f'decision_log_anchor_without_claims:{aid}')
   a,e,final=span_set(anchor['reviewer_a_claims']),span_set(anchor['reviewer_e_claims']),span_set(finals)
   cat=category(a,e,final); categories[cat]+=1;cc[cat]+=1
   entry_reasons=sorted({code for claim in finals for code in claim['reason_codes']}); reasons.update(code for claim in finals for code in claim['reason_codes'])
   entries.append({'case_id':case['case_id'],'anchor_id':aid,'source_field':anchor['source_field'],'reviewer_a_claim_count':len(a),'reviewer_e_claim_count':len(e),'final_claim_count':len(final),'reviewer_a_span_set':[{'start':s,'end':x} for s,x in sorted(a)],'reviewer_e_span_set':[{'start':s,'end':x} for s,x in sorted(e)],'final_span_set':[{'start':s,'end':x} for s,x in sorted(final)],'decision_category':cat,'reason_codes':entry_reasons,'final_claim_ids':[c['adjudicated_claim_id'] for c in finals]})
  per_case[case['case_id']]=cc
 representatives={cat:[{'case_id':x['case_id'],'anchor_id':x['anchor_id']} for x in entries if x['decision_category']==cat][:3] for cat in sorted(categories)}
 submission=load(SUBMISSION)
 return {'schema_version':4,'log_id':'phase7.3.3-d1-a-segmentation-decision-log-v4','status':'deterministically_generated_from_frozen_adjudication','manifest_sha256':manifest_hash,'submission_sha256':submission_hash,'adjudication_protocol_sha256':submission['adjudication_protocol_sha256'],'agreement_report_sha256':submission['agreement_report_sha256'],'worklist_sha256':sha(WORKLIST),'classification_unit':'source_anchor','decision_count_by_category':dict(sorted(categories.items())),'reason_code_counts':dict(sorted(reasons.items())),'per_case_counts':{k:dict(sorted(v.items())) for k,v in sorted(per_case.items())},'representative_decisions':representatives,'entries':entries,'entry_count':len(entries),'provider_called_for_log_generation':False,'held_out_accessed':False}

def validate(order,anchors,worklist_anchors,submission):
 if submission.get('status')!='completed_model_adjudicated_boundary_reference_candidate': raise ValueError('submission_not_completed')
 if submission.get('held_out_accessed') is not False or submission.get('boundary_gold_frozen') is not False or submission.get('support_review_allowed') is not False: raise ValueError('submission_gate_state_invalid')
 claims=submission.get('claims')
 if not isinstance(claims,list) or not claims or submission.get('claim_count')!=len(claims): raise ValueError('submission_claims_invalid')
 by=defaultdict(list); counters=Counter(); seen=set(); ids_by_case=defaultdict(list)
 for claim in claims:
  case_id,anchor_id=claim.get('case_id'),claim.get('anchor_id'); key=(case_id,anchor_id); anchor=anchors.get(key)
  if anchor is None:counters['unknown_anchor_count']+=1;continue
  for field in ('source_field','source_index','source_text_sha256'):
   if claim.get(field)!=anchor[field]:counters['source_metadata_mismatch_count']+=1
  span=claim.get('source_span'); start=span.get('start') if isinstance(span,dict) else None;end=span.get('end') if isinstance(span,dict) else None
  if not isinstance(start,int) or isinstance(start,bool) or not isinstance(end,int) or isinstance(end,bool) or start<0 or end<=start or end>len(anchor['source_text']):
   counters['invalid_span_count']+=1
   if not isinstance(start,int) or not isinstance(end,int) or (isinstance(start,int) and isinstance(end,int) and end<=start): counters['blank_or_zero_length_claim_count']+=1
   continue
  claim_text=claim.get('claim_text')
  if not isinstance(claim_text,str) or not claim_text.strip():counters['blank_or_zero_length_claim_count']+=1
  if claim_text!=anchor['source_text'][start:end]:counters['claim_text_mismatch_count']+=1
  else:
   starts=occurrences(anchor['source_text'],claim_text); expected=starts.index(start) if start in starts else None
   if claim.get('source_occurrence_index')!=expected:counters['source_occurrence_mismatch_count']+=1
  valid_ids={c['reviewer_claim_id'] for rk in ('reviewer_a_claims','reviewer_e_claims') for c in worklist_anchors[key][rk]}
  reviewer_ids=claim.get('source_reviewer_claim_ids')
  if not isinstance(reviewer_ids,list) or not reviewer_ids or len(reviewer_ids)!=len(set(reviewer_ids)):counters['unknown_reviewer_claim_id_count']+=1
  else:counters['unknown_reviewer_claim_id_count']+=sum(item not in valid_ids for item in reviewer_ids)
  cid=claim.get('adjudicated_claim_id')
  if not isinstance(cid,str) or not cid or cid in seen:raise ValueError(f'adjudicated_id_invalid:{cid}')
  seen.add(cid);ids_by_case[case_id].append(cid);by[key].append(claim)
 counters['missing_anchor_count']=sum(not by.get(key) for key in order)
 counters['sequential_claim_id_failure_count']=sum(ids!=[f'adjudicated-{case}-claim-{i:03d}' for i in range(1,len(ids)+1)] for case,ids in ids_by_case.items())
 overlap=0; anchors_overlap=0
 for key,anchor in anchors.items():
  depth=[0]*len(anchor['source_text'])
  for claim in by.get(key,[]):
   for i in range(claim['source_span']['start'],claim['source_span']['end']):depth[i]+=1
  count=sum(x>1 for x in depth);overlap+=count;anchors_overlap+=count>0
 fields=['invalid_span_count','blank_or_zero_length_claim_count','claim_text_mismatch_count','source_occurrence_mismatch_count','unknown_anchor_count','missing_anchor_count','unknown_reviewer_claim_id_count','source_metadata_mismatch_count']
 result={'anchor_count':len(order),'claim_count':len(claims),**{f:counters[f] for f in fields},'duplicate_adjudicated_claim_id_count':len(claims)-len(seen),'sequential_claim_id_failure_count':counters['sequential_claim_id_failure_count'],'overlap_characters':overlap,'anchors_with_overlaps':anchors_overlap}
 return by,result

def gap_ranges(text,claim_depth,nonclaim_depth):
 spans=[];cursor=0
 while cursor<len(text):
  if claim_depth[cursor] or nonclaim_depth[cursor]:cursor+=1;continue
  start=cursor
  while cursor<len(text) and not claim_depth[cursor] and not nonclaim_depth[cursor]:cursor+=1
  if any(not ch.isspace() for ch in text[start:cursor]):spans.append((start,cursor))
 return spans

def coverage(order,anchors,claims_by,nonclaims):
 policy=load(POLICY);valid_reasons=set(policy['non_claim_reason_codes']);nc_by=defaultdict(list);diagnostic=Counter()
 for row in nonclaims:
  key=(row.get('case_id'),row.get('anchor_id'));anchor=anchors.get(key);span=row.get('source_span',{});start,end=span.get('start'),span.get('end')
  if anchor is None or not isinstance(start,int) or isinstance(start,bool) or not isinstance(end,int) or isinstance(end,bool) or start<0 or end<=start or end>len(anchor['source_text']):diagnostic['invalid_nonclaim_span_count']+=1;continue
  if not isinstance(row.get('rationale'),str) or not row['rationale'].strip():diagnostic['invalid_nonclaim_metadata_count']+=1
  if row.get('reason_code') not in valid_reasons:diagnostic['invalid_nonclaim_reason_code_count']+=1
  nc_by[key].append(row)
 names=['total_anchor_characters','eligible_non_whitespace_characters','covered_characters','overlap_characters','gap_characters','eligible_gap_characters','declared_non_claim_characters','claim_non_claim_conflict_characters'];totals={n:0 for n in names};per_anchor=[];gaps=[];gap_i=0;anchors_gap=0
 for key in order:
  case_id,anchor_id=key;anchor=anchors[key];text=anchor['source_text'];cd=[0]*len(text);nd=[0]*len(text)
  for claim in claims_by.get(key,[]):
   for i in range(claim['source_span']['start'],claim['source_span']['end']):cd[i]+=1
  for row in nc_by.get(key,[]):
   for i in range(row['source_span']['start'],row['source_span']['end']):nd[i]+=1
  metrics={'total_anchor_characters':len(text),'eligible_non_whitespace_characters':sum(not ch.isspace() for ch in text),'covered_characters':sum(x>=1 for x in cd),'overlap_characters':sum(x>1 for x in cd),'gap_characters':sum(c==0 and n==0 for c,n in zip(cd,nd)),'eligible_gap_characters':sum(not text[i].isspace() and cd[i]==0 and nd[i]==0 for i in range(len(text))),'declared_non_claim_characters':sum(c==0 and n>=1 for c,n in zip(cd,nd)),'claim_non_claim_conflict_characters':sum(c>=1 and n>=1 for c,n in zip(cd,nd))}
  for n,v in metrics.items():totals[n]+=v
  ranges=gap_ranges(text,cd,nd);anchors_gap+=bool(ranges)
  for start,end in ranges:
   gap_i+=1;gap=text[start:end]
   gaps.append({'gap_id':f'coverage-gap-{gap_i:03d}','case_id':case_id,'anchor_id':anchor_id,'source_field':anchor['source_field'],'source_index':anchor['source_index'],'source_text_sha256':anchor['source_text_sha256'],'source_span':{'start':start,'end':end},'gap_text':gap,'gap_text_sha256':text_sha(gap),'character_count':len(gap),'eligible_non_whitespace_count':sum(not ch.isspace() for ch in gap),'reason_code':None,'rationale':None,'semantic_classification_performed':False})
  per_anchor.append({'case_id':case_id,'anchor_id':anchor_id,'source_field':anchor['source_field'],'source_index':anchor['source_index'],'source_text_sha256':anchor['source_text_sha256'],'claim_count':len(claims_by.get(key,[])),'non_claim_span_count':len(nc_by.get(key,[])),'eligible_gap_span_count':len(ranges),**metrics})
 total=totals['total_anchor_characters'];eligible=totals['eligible_non_whitespace_characters'];totals['raw_coverage_ratio']=totals['covered_characters']/total if total else 1.0;totals['eligible_accounting_ratio']=(eligible-totals['eligible_gap_characters'])/eligible if eligible else 1.0
 return {'metrics':totals,'invalid_nonclaim_span_count':diagnostic['invalid_nonclaim_span_count'],'invalid_nonclaim_metadata_count':diagnostic['invalid_nonclaim_metadata_count'],'invalid_nonclaim_reason_code_count':diagnostic['invalid_nonclaim_reason_code_count'],'explicit_non_claim_span_count':len(nonclaims),'eligible_gap_span_count':len(gaps),'anchors_with_eligible_gaps':anchors_gap,'per_anchor':per_anchor},gaps

def make_manifest():
 observed=verify_hashes()
 return {'schema_version':1,'manifest_id':'phase7.3.3-d1-b-boundary-coverage-execution-v4','status':'frozen_not_started','object_of_study':'character_level_boundary_reference_accounting_under_frozen_policy_v1','adapter_sha256':sha(Path(__file__)),'artifact_lineage':observed,'execution_contract':{'provider_called':False,'held_out_accessed':False,'semantic_gap_classification':'forbidden','automatic_non_claim_labeling':'forbidden','submission_mutation':'forbidden','decision_log_deterministic_replay_required':True,'write_once_outputs':True},'required_checks':['all_anchors_have_claims','span_validity','claim_text_exactness','same_anchor_non_overlap','nonblank_nonzero_claims','source_occurrence_replay','same_anchor_reviewer_provenance','unique_sequential_claim_ids','decision_log_replay','frozen_input_lineage','character_level_coverage','explicit_non_claim_accounting'],'expected_output_paths':{'coverage_report':COVERAGE_REPORT.relative_to(ROOT).as_posix(),'gap_worklist':GAP_WORKLIST.relative_to(ROOT).as_posix(),'readiness_v6':READINESS_V6.relative_to(ROOT).as_posix()},'coverage_qa_started':False,'boundary_gold_frozen':False,'support_review_allowed':False}

def execute():
 observed=verify_hashes()
 if not COVERAGE_MANIFEST.exists():raise ValueError('coverage_manifest_required')
 if load(COVERAGE_MANIFEST)!=make_manifest():raise ValueError('coverage_manifest_integrity_failure')
 manifest_hash=sha(COVERAGE_MANIFEST);packet=load(PACKET);worklist=load(WORKLIST);submission=load(SUBMISSION);order,anchors,worklist_anchors=indexes(packet,worklist);claims_by,structural=validate(order,anchors,worklist_anchors,submission)
 replay_ok=replay_log(worklist,submission['claims'],submission['manifest_sha256'],observed['v4_submission'])==load(DECISION_LOG)
 if not replay_ok:raise ValueError('decision_log_replay_failure')
 nonclaims=submission.get('non_claim_spans',[])
 if not isinstance(nonclaims,list):raise ValueError('non_claim_spans_invalid')
 cov,gaps=coverage(order,anchors,claims_by,nonclaims);metrics=cov['metrics'];failures=[]
 structural_fields=['invalid_span_count','blank_or_zero_length_claim_count','claim_text_mismatch_count','source_occurrence_mismatch_count','unknown_anchor_count','missing_anchor_count','unknown_reviewer_claim_id_count','source_metadata_mismatch_count','duplicate_adjudicated_claim_id_count','sequential_claim_id_failure_count','overlap_characters']
 failures += [field for field in structural_fields if structural[field]!=0]
 failures += [field for field in ('invalid_nonclaim_span_count','invalid_nonclaim_metadata_count','invalid_nonclaim_reason_code_count') if cov[field]!=0]
 if metrics['eligible_gap_characters']!=0:failures.append('eligible_gap_characters')
 if metrics['overlap_characters']!=0 and 'overlap_characters' not in failures:failures.append('overlap_characters')
 if metrics['claim_non_claim_conflict_characters']!=0:failures.append('claim_non_claim_conflict_characters')
 passed=not failures;status='passed' if passed else ('failed_non_claim_accounting_required' if failures==['eligible_gap_characters'] else 'failed')
 report={'schema_version':4,'report_id':'phase7.3.3-d1-b-boundary-coverage-report-v4','status':status,'policy_id':load(POLICY)['policy_id'],'coverage_execution_manifest_sha256':manifest_hash,'artifact_lineage':observed,'submission_status':submission['status'],'structural_validation':structural,'decision_log_deterministic_replay_passed':replay_ok,'coverage':cov,'freeze_gate_failures':failures,'freeze_gates_passed':passed,'coverage_qa_completed':True,'coverage_qa_passed':passed,'boundary_gold_freeze_allowed':passed,'support_review_allowed':False,'failure_interpretation':None if passed else ('The frozen V4 Boundary reference candidate has uncovered eligible source characters without explicit non-claim reason codes and rationales. This is a reference-accounting failure, not evidence of Boundary model-capability failure.' if status=='failed_non_claim_accounting_required' else 'One or more frozen Coverage Policy or structural integrity gates failed.'),'provider_called':False,'semantic_gap_classification_performed':False,'held_out_accessed':False}
 report_hash=write_once(COVERAGE_REPORT,report)
 gap_worklist={'schema_version':1,'worklist_id':'phase7.3.3-d1-b-boundary-coverage-gap-worklist-v1','status':'explicit_non_claim_accounting_required' if gaps else 'no_unaccounted_eligible_gaps','coverage_execution_manifest_sha256':manifest_hash,'coverage_report_sha256':report_hash,'boundary_packet_sha256':observed['boundary_packet'],'v4_submission_sha256':observed['v4_submission'],'policy_sha256':observed['coverage_policy'],'gap_count':len(gaps),'eligible_gap_character_count':metrics['eligible_gap_characters'],'instructions':{'allowed_action':'Assign an explicit frozen-policy non_claim reason_code and a non-empty rationale, or create a separately versioned Boundary correction protocol; do not infer either automatically in this artifact.','automatic_semantic_classification':'forbidden','support_labels_visible':False,'candidate_gold_or_silver_visible':False,'held_out_visible':False},'gaps':gaps,'provider_called':False,'semantic_classification_performed':False,'held_out_accessed':False}
 gap_hash=write_once(GAP_WORKLIST,gap_worklist)
 readiness={'schema_version':6,'state_id':'phase7.3.3-d1-reference-construction-readiness-v6','status':'coverage_qa_passed_boundary_gold_freeze_allowed' if passed else 'coverage_qa_failed_non_claim_accounting_required','preserves_readiness_v5_sha256':observed['readiness_v5'],'coverage_execution_manifest_sha256':manifest_hash,'coverage_report_sha256':report_hash,'coverage_gap_worklist_sha256':gap_hash,'gates':{'agreement_frozen':True,'adjudication_completed':True,'coverage_qa_allowed':True,'coverage_qa_completed':True,'coverage_qa_passed':passed,'boundary_gold_freeze_allowed':passed,'boundary_gold_frozen':False,'explicit_non_claim_accounting_required':not passed and status=='failed_non_claim_accounting_required','support_review_allowed':False,'held_out_accessed':False},'next_required_action':'Freeze the passing Coverage Report into the separately versioned Boundary Reference artifact.' if passed else 'Complete an independently versioned explicit non-claim accounting step for the deterministic gap worklist; do not begin Support Review.','provider_called':False}
 readiness_hash=write_once(READINESS_V6,readiness)
 return {'status':status,'coverage_manifest_sha256':manifest_hash,'coverage_report_sha256':report_hash,'gap_worklist_sha256':gap_hash,'readiness_v6_sha256':readiness_hash,'anchor_count':structural['anchor_count'],'claim_count':structural['claim_count'],'metrics':metrics,'eligible_gap_span_count':cov['eligible_gap_span_count'],'anchors_with_eligible_gaps':cov['anchors_with_eligible_gaps'],'freeze_gate_failures':failures,'boundary_gold_frozen':False,'support_review_allowed':False,'held_out_accessed':False}

def main():
 parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--freeze-manifest',action='store_true');group.add_argument('--execute',action='store_true');group.add_argument('--verify-inputs',action='store_true');args=parser.parse_args()
 if args.verify_inputs:print(json.dumps({'status':'frozen_inputs_verified','hashes':verify_hashes()},indent=2));return 0
 if args.freeze_manifest:
  digest=write_once(COVERAGE_MANIFEST,make_manifest());print(json.dumps({'status':'coverage_manifest_frozen_not_started','coverage_manifest_sha256':digest,'provider_called':False,'held_out_accessed':False},indent=2));return 0
 print(json.dumps(execute(),ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
