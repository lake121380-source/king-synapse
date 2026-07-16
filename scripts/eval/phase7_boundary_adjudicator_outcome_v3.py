#!/usr/bin/env python3
"""Freeze the post-execution outcome of Boundary Adjudicator v3 without retry."""
from __future__ import annotations
import hashlib, json, tempfile
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import read_entries, verify_entries

ROOT=Path(__file__).resolve().parents[2]
REPORTS=ROOT/'crates/eval/reports'; CONFIG=ROOT/'crates/eval/config'
MANIFEST=REPORTS/'phase7_3_3_d_boundary_adjudicator_execution_manifest_v3.json'
ATTEMPTS=REPORTS/'phase7_3_3_d_boundary_adjudicator_execution_attempts_v3.jsonl'
NEGATIVE=REPORTS/'phase7_3_3_d_boundary_adjudicator_negative_result_v3.json'
CASES=REPORTS/'phase7_3_3_d_boundary_adjudicator_cases_v3'
WORKLIST=REPORTS/'phase7_3_3_d_boundary_adjudication_worklist_a_e_v3.json'
AGREEMENT=REPORTS/'phase7_3_3_d_boundary_agreement_a_e_v3.json'
TAXONOMY=CONFIG/'phase7_3_3_d_failure_taxonomy_v2.json'
OUTCOME=REPORTS/'phase7_3_3_d1_boundary_adjudicator_execution_outcome_v3.json'
READINESS=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v4.json'
READINESS_V3=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v3.json'

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8-sig'))
def write_once(p:Path,v:Any)->str:
    raw=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
    if p.exists():
        if p.read_bytes()!=raw:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
        return hashlib.sha256(raw).hexdigest()
    p.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(raw); t=Path(h.name)
    t.replace(p);return hashlib.sha256(raw).hexdigest()

def main()->int:
    for p in (MANIFEST,ATTEMPTS,NEGATIVE,WORKLIST,AGREEMENT,TAXONOMY,READINESS_V3):
        if not p.exists():raise ValueError(f'missing:{p.relative_to(ROOT)}')
    entries=read_entries(ATTEMPTS);verify_entries(entries)
    neg=load(NEGATIVE); work=load(WORKLIST)
    checkpoints=sorted(CASES.glob('*.json'))
    completed=[load(p) for p in checkpoints]
    completed_ids=[x['case_id'] for x in completed]
    expected=[x['case_id'] for x in work['cases']]
    incomplete=sorted(set(expected)-set(completed_ids))
    if neg.get('status')!='authoritative_negative_result' or neg.get('same_manifest_retry_authorized') is not False:
        raise ValueError('negative_result_not_frozen')
    if incomplete != [neg['case_id']]:raise ValueError(f'incomplete_case_mismatch:{incomplete}')
    last=entries[-1]
    outcome={
      'schema_version':3,'report_id':'phase7.3.3-d1-a-boundary-adjudicator-execution-outcome-v3',
      'recorded_at':last['recorded_at'],'status':'authoritative_negative_result_adjudication_incomplete',
      'model_requested':load(MANIFEST)['decision_environment']['model_requested'],
      'artifact_lineage':{'manifest_sha256':sha(MANIFEST),'attempt_log_sha256':sha(ATTEMPTS),
        'negative_result_sha256':sha(NEGATIVE),'worklist_sha256':sha(WORKLIST),
        'agreement_report_sha256':sha(AGREEMENT),'failure_taxonomy_v2_sha256':sha(TAXONOMY),
        'completed_case_checkpoint_sha256':{p.stem:sha(p) for p in checkpoints}},
      'execution_summary':{'expected_case_count':len(expected),'completed_case_count':len(completed),
        'completed_case_ids':completed_ids,'completed_claim_count':sum(len(x['claims']) for x in completed),
        'failed_case_id':neg['case_id'],'failure_code':neg['failure_code'],
        'response_received_for_failed_case':neg['response_received'],
        'provider_content_received_for_failed_case':neg['provider_content_received'],
        'raw_provider_content_stored':False,'held_out_accessed':False},
      'frozen_taxonomy_classification':neg['failure_taxonomy'],
      'classification_note':'Failure attribution is copied unchanged from the frozen execution artifact; no post-hoc reclassification was applied.',
      'scientific_interpretation':'The frozen v3 adjudicator completed nine cases but failed the Level 2 Boundary semantic contract on extract_10 because one returned source_excerpt was not an exact substring of the frozen source anchor. The full adjudication is therefore incomplete. Partial checkpoints are preserved as execution evidence but are not an adjudicated Boundary reference and cannot authorize Coverage QA.',
      'authorized_conclusions':[
        'The frozen end-to-end adjudication execution did not complete.',
        'The failure occurred after Provider content and is an experimental failure, not a transport failure.',
        'The exact-substring Boundary contract failed on extract_10.',
        'The nine completed checkpoints are auditable partial execution artifacts only.'
      ],
      'unauthorized_conclusions':[
        'Boundary Gold is frozen.','Coverage QA may begin.','Support Review may begin.',
        'The same Manifest may retry extract_10.','Partial checkpoints constitute a completed reference.'
      ],
      'immutability_policy':{'same_manifest_retry_authorized':False,'semantic_repair_authorized':False,
        'result_replacement_authorized':False,'prompt_or_parser_modified_after_execution':False},
      'gates':{'adjudication_completed':False,'coverage_qa_allowed':False,
        'boundary_gold_frozen':False,'support_review_allowed':False,'held_out_accessed':False}}
    outcome_hash=write_once(OUTCOME,outcome)
    readiness={
      'schema_version':4,'report_id':'phase7.3.3-d1-reference-construction-readiness-v4',
      'recorded_at':last['recorded_at'],'status':'authoritative_negative_adjudication_incomplete_coverage_blocked',
      'preserves_v3_sha256':sha(READINESS_V3),
      'artifact_lineage':{'manifest_sha256':sha(MANIFEST),'attempt_log_sha256':sha(ATTEMPTS),
        'negative_result_sha256':sha(NEGATIVE),'adjudicator_outcome_sha256':outcome_hash,
        'agreement_report_sha256':sha(AGREEMENT),'worklist_sha256':sha(WORKLIST)},
      'state_machine':{'boundary_agreement_available':True,'boundary_agreement_frozen_before_adjudication':True,
        'boundary_adjudication_attempt_recorded':True,'boundary_adjudication_completed':False,
        'coverage_qa_allowed':False,'coverage_qa_blocked_reason':'authoritative_adjudication_negative_result',
        'boundary_gold_frozen':False,'support_review_allowed':False,
        'support_blocked_reason':'boundary_gold_not_frozen','held_out_accessed':False},
      'next_required_action':'Preserve v3 as the authoritative negative result. Any new adjudication attempt requires an explicitly versioned new Manifest and must not be represented as a retry of v3.',
      'provider_called_for_this_state_update':False,'raw_provider_content_stored':False,
      'credential_recorded':False,'held_out_accessed':False}
    readiness_hash=write_once(READINESS,readiness)
    print(json.dumps({'outcome_sha256':outcome_hash,'readiness_v4_sha256':readiness_hash,
      'completed_cases':len(completed),'completed_claims':sum(len(x['claims']) for x in completed),
      'failed_case':neg['case_id'],'coverage_qa_allowed':False,'support_review_allowed':False},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
