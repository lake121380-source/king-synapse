#!/usr/bin/env python3
"""Phase 7.3.3-D1-B2 dual-blind explicit Non-Claim accounting v1."""
from __future__ import annotations
import argparse, hashlib, json, os, tempfile, urllib.error, urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event, read_entries

ROOT=Path(__file__).resolve().parents[2]; CONFIG=ROOT/'crates/eval/config'; DATA=ROOT/'crates/eval/datasets/pattern_extraction'; REPORTS=ROOT/'crates/eval/reports'
SOURCE_PACKET=DATA/'phase7_3_3_d_boundary_blind_review_packet_v1.json'
V4_SUBMISSION=REPORTS/'phase7_3_3_d_boundary_adjudicator_submission_v4.json'
COVERAGE_MANIFEST=REPORTS/'phase7_3_3_d_boundary_coverage_execution_manifest_v4.json'
COVERAGE_REPORT=REPORTS/'phase7_3_3_d_boundary_coverage_report_v4.json'
GAP_WORKLIST=REPORTS/'phase7_3_3_d_boundary_coverage_gap_worklist_v1.json'
COVERAGE_POLICY=CONFIG/'phase7_3_3_d_boundary_coverage_policy_v1.json'
PROTOCOL=CONFIG/'phase7_3_3_d_non_claim_accounting_protocol_v1.json'
POLICY=CONFIG/'phase7_3_3_d_non_claim_accounting_execution_policy_v1.json'
PROMPT=CONFIG/'phase7_3_3_d_non_claim_accounting_prompt_v1.md'
REVIEW_PACKET=DATA/'phase7_3_3_d_non_claim_accounting_review_packet_v1.json'
FIXTURES=REPORTS/'phase7_3_3_d_non_claim_accounting_contract_fixtures_v1.json'
AGREEMENT=REPORTS/'phase7_3_3_d_non_claim_accounting_agreement_q_g_v1.json'
READINESS_V7=REPORTS/'phase7_3_3_d1_reference_construction_readiness_v7.json'
BASE_URL='https://api.gpt.ge/v1'; CREDENTIAL_ENV='PHASE7_ATOMIC_JUDGE_API_KEY'
TEMPERATURE=0; TOP_P=1; MAX_TOKENS=10000; TIMEOUT_SECONDS=600; RESPONSE_FORMAT={'type':'json_object'}
REVIEWERS={'q':{'model':'qwen3.5-plus','label':'Reviewer Q'},'g':{'model':'gemini-2.5-pro','label':'Reviewer G'}}
CLASSIFICATIONS={'explicit_non_claim','boundary_omission_candidate'}
NON_CLAIM_REASONS={'punctuation_only','formatting_only','list_delimiter','non_assertive_connector','metadata_not_a_claim','other_explained_non_claim'}
TOP_LEVEL_KEYS={'case_id','decisions'}; DECISION_KEYS={'gap_id','classification','reason_code','rationale'}

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def canonical_sha(v:Any)->str:return sha_bytes(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8'))
def write_once(p:Path,v:Any)->str:
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return sha_bytes(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p);return sha_bytes(b)
def write_text_once(p:Path,text:str)->str:
 b=text.encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return sha_bytes(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p);return sha_bytes(b)

def protocol_document()->dict[str,Any]:
 return {'schema_version':1,'protocol_id':'phase7.3.3-d1-b2-explicit-non-claim-accounting-v1','phase':'Phase 7.3.3-D1-B2 Explicit Non-Claim Accounting and Boundary-Omission Triage','research_object':'semantic accounting of frozen eligible Boundary coverage gaps','core_principle':'not_covered_by_claim_does_not_imply_non_claim','frozen_input':{'gap_ids_and_spans_protocol_owned':True,'gap_count':84,'eligible_non_whitespace_character_count':206,'reviewer_may_edit_or_create_spans':False,'whitespace_already_deterministically_excluded':True,'protocol_excluded_is_not_an_allowed_reviewer_outcome':True},'allowed_outcomes':{'explicit_non_claim':{'definition':'The complete frozen Gap carries no independently assertive semantic content and may be explicitly accounted as non-Claim.','reason_code_required':True,'allowed_reason_codes':sorted(NON_CLAIM_REASONS),'nonempty_rationale_required':True},'boundary_omission_candidate':{'definition':'Some or all of the frozen Gap may carry claim-bearing, qualifying, conditional, limiting, falsifying, predictive, or otherwise assertive content omitted by the current Boundary Reference Candidate.','reason_code_must_be_null':True,'nonempty_rationale_required':True,'automatic_boundary_correction_authorized':False}},'review_design':{'dual_blind_ai_review':True,'reviewers':['qwen3.5-plus','gemini-2.5-pro'],'same_prompt_and_packet':True,'case_isolation':True,'reviewer_outputs_mutually_hidden':True,'support_labels_visible':False,'candidate_gold_or_silver_visible':False,'evidence_visible':False,'historical_judge_visible':False,'held_out_visible':False},'agreement_statuses':['exact_agreement','classification_agreement_reason_disagreement','classification_disagreement'],'post_review_policy':{'automatic_adjudication':False,'automatic_boundary_repair':False,'coverage_rerun_before_resolution':False,'boundary_gold_freeze_before_coverage_pass':False,'support_review_before_boundary_gold_freeze':False}}

def execution_policy_document()->dict[str,Any]:
 return {'schema_version':1,'policy_id':'phase7.3.3-d1-b2-non-claim-accounting-execution-policy-v1','authoritative_result_policy':{'first_returned_provider_content_per_case_is_authoritative':True,'invalid_json_schema_or_semantics_is_experimental_negative_result':True,'automatic_repair_authorized':False,'semantic_retry_authorized':False,'selective_retry_authorized':False,'transport_failure_before_provider_content_may_resume_same_manifest':True},'execution_controls':{'case_isolation':True,'temperature':TEMPERATURE,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESPONSE_FORMAT,'web_tools_enabled':False,'external_memory_enabled':False},'data_handling':{'credential_env_name':CREDENTIAL_ENV,'credential_recorded':False,'raw_provider_envelope_recorded':False,'raw_provider_content_recorded':False,'provider_envelope_sha256_recorded':True,'provider_content_sha256_recorded':True,'normalized_decisions_recorded':True,'held_out_loaded':False},'prohibitions':['no_gap_span_modification','no_new_gap_creation','no_prompt_or_parser_modification_after_manifest_freeze','no_result_replacement','no_semantic_retry','no_automatic_adjudication','no_coverage_rerun_in_this_stage','no_boundary_gold_freeze','no_support_review','no_held_out_access']}

def prompt_text()->str:
 return '''# Phase 7.3.3-D1-B2 Explicit Non-Claim Accounting Prompt v1

## System message
You are an independent blind reviewer performing semantic accounting of frozen Boundary coverage Gaps.

The Gap IDs, source spans, and text are protocol-owned and immutable. You must not edit a span, create a new span, split a Gap, merge Gaps, or propose replacement text.

For every Gap in the supplied Case packet, choose exactly one classification:
1. `explicit_non_claim`: the entire Gap has no independently assertive semantic content and can be explicitly accounted as non-Claim.
2. `boundary_omission_candidate`: some or all of the Gap may carry claim-bearing, qualifying, conditional, limiting, falsifying, predictive, or otherwise assertive meaning omitted by the current claims.

`explicit_non_claim` requires exactly one reason code from: `punctuation_only`, `formatting_only`, `list_delimiter`, `non_assertive_connector`, `metadata_not_a_claim`, `other_explained_non_claim`.
`boundary_omission_candidate` requires `reason_code: null`.

Every decision requires a concise nonempty rationale grounded only in the frozen source anchor, current claim spans, and Gap text. When uncertain whether a Gap contains semantically material content, use `boundary_omission_candidate`; this stage does not repair the Boundary.

Return one bare JSON object only, without Markdown fences, with exactly this schema and Gap order:
{"case_id":"extract_01","decisions":[{"gap_id":"coverage-gap-001","classification":"explicit_non_claim","reason_code":"punctuation_only","rationale":"..."}]}

Do not mention or infer Support labels, Candidate labels, Gold/Silver status, evidence, other reviewers, or held-out data.

## User message template
Classify every frozen eligible Gap in this isolated Case packet under the protocol. Return bare JSON only.

CASE_PACKET_JSON:
{CASE_PACKET_JSON}
'''
def build_review_packet()->dict[str,Any]:
 sp=load(SOURCE_PACKET); wl=load(GAP_WORKLIST); sub=load(V4_SUBMISSION)
 if sp.get('held_out_accessed') is not False:raise ValueError('source_packet_held_out_state_invalid')
 if wl.get('gap_count')!=84 or wl.get('eligible_gap_character_count')!=206 or wl.get('semantic_classification_performed') is not False:raise ValueError('gap_worklist_state_invalid')
 if sub.get('claim_count')!=118 or sub.get('boundary_gold_frozen') is not False:raise ValueError('v4_submission_state_invalid')
 anchors={}
 for case in sp['cases']:
  for a in case['source_anchors']:anchors[a['anchor_id']]={'case_id':case['case_id'],**a}
 claims=defaultdict(list)
 for c in sub['claims']:
  claims[c['anchor_id']].append({'adjudicated_claim_id':c['adjudicated_claim_id'],'source_span':c['source_span'],'claim_text':c['claim_text'],'claim_type':c['claim_type'],'claim_role':c['claim_role']})
 for vs in claims.values():vs.sort(key=lambda x:(x['source_span']['start'],x['source_span']['end'],x['adjudicated_claim_id']))
 gaps=defaultdict(list)
 for g in wl['gaps']:
  a=anchors.get(g['anchor_id']); s,e=g['source_span']['start'],g['source_span']['end']
  if a is None or a['case_id']!=g['case_id']:raise ValueError(f"gap_anchor_lineage_invalid:{g['gap_id']}")
  if a['source_text'][s:e]!=g['gap_text']:raise ValueError(f"gap_text_source_mismatch:{g['gap_id']}")
  if sha_bytes(g['gap_text'].encode())!=g['gap_text_sha256']:raise ValueError(f"gap_text_hash_mismatch:{g['gap_id']}")
  gaps[g['case_id']].append({'gap_id':g['gap_id'],'anchor_id':g['anchor_id'],'source_span':g['source_span'],'gap_text':g['gap_text'],'eligible_non_whitespace_count':g['eligible_non_whitespace_count']})
 cases=[]
 for cid in sorted(gaps):
  gs=gaps[cid]; aids=sorted({g['anchor_id'] for g in gs}); ans=[]
  for aid in aids:
   a=anchors[aid];ans.append({'anchor_id':aid,'source_field':a['source_field'],'source_index':a['source_index'],'source_text':a['source_text'],'current_claims':claims.get(aid,[])})
  cases.append({'case_id':cid,'anchors':ans,'gaps':gs})
 gc=sum(len(c['gaps']) for c in cases); ec=sum(g['eligible_non_whitespace_count'] for c in cases for g in c['gaps']); ac=len({g['anchor_id'] for c in cases for g in c['gaps']})
 if (len(cases),ac,gc,ec)!=(10,38,84,206):raise ValueError(f'review_packet_accounting_invalid:{len(cases)}:{ac}:{gc}:{ec}')
 return {'schema_version':1,'packet_id':'phase7.3.3-d1-b2-non-claim-accounting-review-packet-v1','protocol_id':'phase7.3.3-d1-b2-explicit-non-claim-accounting-v1','packet_role':'dual_blind_gap_semantic_accounting','case_count':10,'anchor_count':38,'gap_count':84,'eligible_non_whitespace_character_count':206,'blind_to_support_labels':True,'blind_to_candidate_gold_or_silver':True,'blind_to_evidence':True,'blind_to_historical_judge':True,'blind_to_other_reviewer':True,'held_out_accessed':False,'artifact_lineage':{'source_boundary_packet_sha256':sha(SOURCE_PACKET),'v4_submission_sha256':sha(V4_SUBMISSION),'coverage_manifest_sha256':sha(COVERAGE_MANIFEST),'coverage_report_sha256':sha(COVERAGE_REPORT),'gap_worklist_sha256':sha(GAP_WORKLIST),'coverage_policy_sha256':sha(COVERAGE_POLICY)},'cases':cases}

def split_prompt()->tuple[str,str]:
 t=PROMPT.read_text(encoding='utf-8-sig');sm='## System message\n';um='## User message template\n'
 if sm not in t or um not in t:raise ValueError('prompt_sections_missing')
 return t.split(sm,1)[1].split(um,1)[0].strip(),t.split(um,1)[1].strip()

def normalize_case(case:dict[str,Any],obj:Any)->list[dict[str,Any]]:
 if not isinstance(obj,dict) or set(obj)!=TOP_LEVEL_KEYS:raise ValueError('response_top_level_schema_invalid')
 if obj.get('case_id')!=case['case_id']:raise ValueError('response_case_id_mismatch')
 ds=obj.get('decisions'); expected=[g['gap_id'] for g in case['gaps']]
 if not isinstance(ds,list) or len(ds)!=len(expected):raise ValueError('decision_count_mismatch')
 out=[];seen=set()
 for i,d in enumerate(ds):
  if not isinstance(d,dict) or set(d)!=DECISION_KEYS:raise ValueError(f'decision_schema_invalid:{i}')
  gid=d.get('gap_id')
  if gid!=expected[i]:raise ValueError(f'gap_order_or_identity_mismatch:{i}')
  if gid in seen:raise ValueError(f'duplicate_gap_id:{gid}')
  seen.add(gid);cl=d.get('classification');rc=d.get('reason_code');rat=d.get('rationale')
  if cl not in CLASSIFICATIONS:raise ValueError(f'classification_invalid:{gid}')
  if not isinstance(rat,str) or not rat.strip():raise ValueError(f'rationale_missing:{gid}')
  if cl=='explicit_non_claim' and rc not in NON_CLAIM_REASONS:raise ValueError(f'explicit_non_claim_reason_invalid:{gid}')
  if cl=='boundary_omission_candidate' and rc is not None:raise ValueError(f'boundary_omission_reason_must_be_null:{gid}')
  out.append({'case_id':case['case_id'],'gap_id':gid,'classification':cl,'reason_code':rc,'rationale':rat.strip()})
 return out

def run_contract_fixtures()->dict[str,Any]:
 case={'case_id':'fixture_case','gaps':[{'gap_id':'fixture-gap-001'},{'gap_id':'fixture-gap-002'}]}
 valid={'case_id':'fixture_case','decisions':[{'gap_id':'fixture-gap-001','classification':'explicit_non_claim','reason_code':'punctuation_only','rationale':'Only punctuation.'},{'gap_id':'fixture-gap-002','classification':'boundary_omission_candidate','reason_code':None,'rationale':'May carry omitted condition semantics.'}]}
 fs=[('valid_mixed_decisions',valid,True),('reject_unknown_classification',{**valid,'decisions':[valid['decisions'][0],{**valid['decisions'][1],'classification':'protocol_excluded'}]},False),('reject_missing_nonclaim_reason',{**valid,'decisions':[{**valid['decisions'][0],'reason_code':None},valid['decisions'][1]]},False),('reject_reason_on_omission',{**valid,'decisions':[valid['decisions'][0],{**valid['decisions'][1],'reason_code':'punctuation_only'}]},False),('reject_invalid_reason',{**valid,'decisions':[{**valid['decisions'][0],'reason_code':'whitespace'},valid['decisions'][1]]},False),('reject_blank_rationale',{**valid,'decisions':[{**valid['decisions'][0],'rationale':' '},valid['decisions'][1]]},False),('reject_missing_gap',{**valid,'decisions':[valid['decisions'][0]]},False),('reject_duplicate_gap',{**valid,'decisions':[valid['decisions'][0],valid['decisions'][0]]},False),('reject_extra_field',{**valid,'decisions':[{**valid['decisions'][0],'edited_span':[0,1]},valid['decisions'][1]]},False)]
 rs=[]
 for name,payload,want in fs:
  ok=True;err=None
  try:normalize_case(case,payload)
  except Exception as e:ok=False;err=str(e)
  rs.append({'fixture':name,'expected_pass':want,'observed_pass':ok,'fixture_passed':ok==want,'observed_error':err})
 return {'schema_version':1,'report_id':'phase7.3.3-d1-b2-non-claim-accounting-contract-fixtures-v1','fixture_count':len(rs),'fixtures_passed':sum(x['fixture_passed'] for x in rs),'all_fixtures_passed':all(x['fixture_passed'] for x in rs),'provider_called':False,'held_out_accessed':False,'results':rs}

def prepare()->None:
 hs={'protocol_sha256':write_once(PROTOCOL,protocol_document()),'execution_policy_sha256':write_once(POLICY,execution_policy_document()),'prompt_sha256':write_text_once(PROMPT,prompt_text()),'contract_fixtures_sha256':write_once(FIXTURES,run_contract_fixtures())}
 if load(FIXTURES).get('all_fixtures_passed') is not True:raise ValueError('contract_fixtures_failed')
 hs['review_packet_sha256']=write_once(REVIEW_PACKET,build_review_packet());p=load(REVIEW_PACKET)
 print(json.dumps({'status':'prepared_offline',**hs,'case_count':p['case_count'],'anchor_count':p['anchor_count'],'gap_count':p['gap_count'],'eligible_non_whitespace_character_count':p['eligible_non_whitespace_character_count'],'fixtures':f"{load(FIXTURES)['fixtures_passed']}/{load(FIXTURES)['fixture_count']}",'provider_called':False,'held_out_accessed':False},indent=2))
def manifest_path(r:str)->Path:return REPORTS/f'phase7_3_3_d_non_claim_accounting_reviewer_{r}_execution_manifest_v1.json'
def attempt_log_path(r:str)->Path:return REPORTS/f'phase7_3_3_d_non_claim_accounting_reviewer_{r}_execution_attempts_v1.jsonl'
def checkpoint_path(r:str,cid:str)->Path:return REPORTS/f'phase7_3_3_d_non_claim_accounting_reviewer_{r}_cases_v1'/f'{cid}.json'
def submission_path(r:str)->Path:return REPORTS/f'phase7_3_3_d_non_claim_accounting_reviewer_{r}_submission_v1.json'
def result_path(r:str)->Path:return REPORTS/f'phase7_3_3_d_non_claim_accounting_reviewer_{r}_execution_result_v1.json'
def negative_path(r:str)->Path:return REPORTS/f'phase7_3_3_d_non_claim_accounting_reviewer_{r}_negative_result_v1.json'

def expected_manifest(r:str)->dict[str,Any]:
 if r not in REVIEWERS:raise ValueError('unknown_reviewer')
 cfg=REVIEWERS[r];p=load(REVIEW_PACKET);f=load(FIXTURES)
 if f.get('all_fixtures_passed') is not True:raise ValueError('fixtures_not_passed')
 return {'schema_version':1,'manifest_id':f'phase7.3.3-d1-b2-non-claim-accounting-reviewer-{r}-execution-v1','reviewer':r,'reviewer_label':cfg['label'],'reviewer_type':'ai_model','provider':'api.gpt.ge','provider_base_url':BASE_URL,'model_requested':cfg['model'],'temperature':TEMPERATURE,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESPONSE_FORMAT,'credential_env_name':CREDENTIAL_ENV,'adapter_sha256':sha(Path(__file__)),'protocol_sha256':sha(PROTOCOL),'execution_policy_sha256':sha(POLICY),'prompt_sha256':sha(PROMPT),'review_packet_sha256':sha(REVIEW_PACKET),'contract_fixtures_sha256':sha(FIXTURES),'source_gap_worklist_sha256':sha(GAP_WORKLIST),'source_v4_submission_sha256':sha(V4_SUBMISSION),'case_count':p['case_count'],'gap_count':p['gap_count'],'case_isolation':True,'other_reviewer_visible':False,'support_labels_visible':False,'candidate_gold_or_silver_visible':False,'evidence_visible':False,'historical_judge_visible':False,'held_out_accessed':False,'raw_provider_responses_stored':False,'first_provider_content_authoritative':True,'status':'frozen_not_started'}

def freeze_manifest(r:str)->None:
 if not all(x.exists() for x in [PROTOCOL,POLICY,PROMPT,REVIEW_PACKET,FIXTURES]):raise ValueError('prepare_required_before_manifest_freeze')
 h=write_once(manifest_path(r),expected_manifest(r));print(json.dumps({'status':'manifest_frozen_not_started','reviewer':r,'model_requested':REVIEWERS[r]['model'],'manifest_sha256':h,'provider_called':False,'held_out_accessed':False},indent=2))

def canonical_model_family(requested:str,reported:str)->str:
 n=reported.strip().lower();q=requested.lower()
 if n==q or n.endswith('/'+q):return requested
 raise ValueError(f'provider_model_outside_requested_family:{reported}')

def provider_request(key:str,model:str,system:str,user:str)->bytes:
 payload={'model':model,'temperature':TEMPERATURE,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESPONSE_FORMAT,'messages':[{'role':'system','content':system},{'role':'user','content':user}]}
 req=urllib.request.Request(BASE_URL+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT_SECONDS) as resp:return resp.read()

def parse_provider_envelope(raw:bytes,requested:str)->tuple[str,str,str,Any]:
 env=json.loads(raw.decode())
 if not isinstance(env,dict):raise ValueError('provider_envelope_not_object')
 reported=env.get('model')
 if not isinstance(reported,str) or not reported.strip():raise ValueError('provider_reported_model_missing')
 canonical=canonical_model_family(requested,reported);choices=env.get('choices')
 if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):raise ValueError('provider_choices_invalid')
 msg=choices[0].get('message')
 if not isinstance(msg,dict):raise ValueError('provider_message_invalid')
 content=msg.get('content')
 if not isinstance(content,str) or not content.strip():raise ValueError('provider_content_missing')
 return reported,canonical,sha_bytes(content.encode()),json.loads(content)

def execute(r:str)->int:
 mf=manifest_path(r)
 if not mf.exists():raise ValueError('manifest_not_frozen')
 if load(mf)!=expected_manifest(r):raise ValueError('frozen_manifest_verification_failed')
 mh=sha(mf)
 if negative_path(r).exists():raise ValueError('authoritative_negative_result_exists_no_retry')
 if submission_path(r).exists():print(json.dumps({'reviewer':r,'status':'already_completed_no_retry','submission_sha256':sha(submission_path(r))},indent=2));return 0
 key=os.environ.get(CREDENTIAL_ENV)
 if not key:raise ValueError(f'credential_env_missing:{CREDENTIAL_ENV}')
 system,user_template=split_prompt();packet=load(REVIEW_PACKET);log=attempt_log_path(r);read_entries(log)
 append_event({'event_type':'non_claim_accounting_execution_invocation','manifest_sha256':mh,'reviewer':r,'status':'started_or_resumed','response_received':False,'authoritative_result':False},log)
 all_ds=[];case_rs=[];reported_models=set();canonical_models=set();cfg=REVIEWERS[r]
 for case in packet['cases']:
  cp=checkpoint_path(r,case['case_id'])
  if cp.exists():
   saved=load(cp)
   if saved.get('manifest_sha256')!=mh or saved.get('status')!='authoritative_success':raise ValueError(f"checkpoint_invalid:{case['case_id']}")
   all_ds+=saved['decisions'];case_rs.append(saved['case_result']);reported_models.add(saved['provider_reported_model']);canonical_models.add(saved['canonical_model_family']);print(f"Reviewer {r.upper()} {case['case_id']}: checkpoint preserved",flush=True);continue
  raw=None;eh=None;ch=None
  try:
   user=user_template.replace('{CASE_PACKET_JSON}',json.dumps(case,ensure_ascii=False,separators=(',',':')))
   raw=provider_request(key,cfg['model'],system,user);eh=sha_bytes(raw);reported,canonical,ch,obj=parse_provider_envelope(raw,cfg['model']);ds=normalize_case(case,obj)
   saved={'schema_version':1,'checkpoint_id':f"phase7.3.3-d1-b2-{r}-{case['case_id']}-v1",'status':'authoritative_success','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':reported,'canonical_model_family':canonical,'normalized_decisions_sha256':canonical_sha(ds),'decisions':ds,'case_result':{'case_id':case['case_id'],'status':'completed','decision_count':len(ds)},'raw_provider_response_stored':False,'held_out_accessed':False}
   write_once(cp,saved);append_event({'event_type':'non_claim_accounting_case_authoritative_success','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'status':'completed','response_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'normalized_output_sha256':canonical_sha(ds),'decision_count':len(ds),'provider_reported_model':reported,'canonical_model_family':canonical},log)
   all_ds+=ds;case_rs.append(saved['case_result']);reported_models.add(reported);canonical_models.add(canonical);print(f"Reviewer {r.upper()} {case['case_id']}: {len(ds)} Gaps",flush=True)
  except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
   status=f'http_{e.code}' if isinstance(e,urllib.error.HTTPError) else type(e).__name__;append_event({'event_type':'non_claim_accounting_case_transport_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'status':status,'response_received':False,'authoritative_result':False},log);print(f"TRANSPORT FAILURE Reviewer {r.upper()} {case['case_id']}: {status}");return 3
  except Exception as e:
   got=raw is not None;append_event({'event_type':'non_claim_accounting_case_experimental_failure' if got else 'non_claim_accounting_case_adapter_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'status':type(e).__name__,'failure_code':str(e)[:300],'response_received':got,'authoritative_result':got,'provider_envelope_sha256':eh,'provider_content_sha256':ch},log)
   if got:
    write_once(negative_path(r),{'schema_version':1,'result_id':f'phase7.3.3-d1-b2-non-claim-accounting-reviewer-{r}-negative-v1','status':'authoritative_negative_result','reviewer':r,'manifest_sha256':mh,'case_id':case['case_id'],'failure_type':type(e).__name__,'failure_code':str(e)[:300],'response_received':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'raw_provider_response_stored':False,'boundary_capability_conclusion_authorized':False,'held_out_accessed':False});print(f"AUTHORITATIVE EXPERIMENTAL FAILURE Reviewer {r.upper()} {case['case_id']}: {type(e).__name__}: {e}");return 4
   raise
 if len(case_rs)!=packet['case_count'] or len(all_ds)!=packet['gap_count']:raise ValueError('completed_accounting_count_mismatch')
 if canonical_models!={cfg['model']}:raise ValueError(f'canonical_model_family_drift:{sorted(canonical_models)}')
 sub={'schema_version':1,'submission_id':f'phase7.3.3-d1-b2-non-claim-accounting-reviewer-{r}-submission-v1','status':'completed_independent_gap_review','reviewer':r,'reviewer_model_requested':cfg['model'],'manifest_sha256':mh,'protocol_sha256':sha(PROTOCOL),'review_packet_sha256':sha(REVIEW_PACKET),'case_count':len(case_rs),'decision_count':len(all_ds),'blind_to_other_reviewer':True,'blind_to_support_labels':True,'blind_to_candidate_gold_or_silver':True,'blind_to_evidence':True,'held_out_accessed':False,'decisions':all_ds};write_once(submission_path(r),sub)
 res={'schema_version':1,'execution_id':f'phase7.3.3-d1-b2-non-claim-accounting-reviewer-{r}-execution-v1','status':'completed','reviewer':r,'manifest_sha256':mh,'submission_sha256':sha(submission_path(r)),'model_requested':cfg['model'],'canonical_model_family':next(iter(canonical_models)),'provider_reported_models':sorted(reported_models),'completed_case_count':len(case_rs),'decision_count':len(all_ds),'classification_counts':dict(sorted(Counter(x['classification'] for x in all_ds).items())),'case_results':case_rs,'raw_provider_responses_stored':False,'held_out_accessed':False};write_once(result_path(r),res)
 print(json.dumps({'reviewer':r,'status':'completed','model_requested':cfg['model'],'cases':len(case_rs),'decisions':len(all_ds),'classification_counts':res['classification_counts'],'submission_sha256':sha(submission_path(r))},indent=2));return 0
def compute_agreement()->None:
 subs={}
 for r in REVIEWERS:
  p=submission_path(r)
  if not p.exists():raise ValueError(f'reviewer_submission_missing:{r}')
  subs[r]=load(p)
 q={x['gap_id']:x for x in subs['q']['decisions']};g={x['gap_id']:x for x in subs['g']['decisions']};expected=[x['gap_id'] for c in load(REVIEW_PACKET)['cases'] for x in c['gaps']]
 if set(q)!=set(expected) or set(g)!=set(expected):raise ValueError('agreement_gap_set_mismatch')
 rows=[];sc=Counter();matrix=Counter()
 for gid in expected:
  a,b=q[gid],g[gid]
  status='classification_disagreement' if a['classification']!=b['classification'] else ('classification_agreement_reason_disagreement' if a['reason_code']!=b['reason_code'] else 'exact_agreement')
  sc[status]+=1;matrix[(a['classification'],b['classification'])]+=1;rows.append({'gap_id':gid,'case_id':a['case_id'],'agreement_status':status,'reviewer_q':{'classification':a['classification'],'reason_code':a['reason_code'],'rationale':a['rationale']},'reviewer_g':{'classification':b['classification'],'reason_code':b['reason_code'],'rationale':b['rationale']},'automatic_adjudication_performed':False})
 ds=[x for x in rows if x['agreement_status']!='exact_agreement']
 report={'schema_version':1,'report_id':'phase7.3.3-d1-b2-non-claim-accounting-agreement-q-g-v1','status':'completed_awaiting_adjudication' if ds else 'completed_full_exact_agreement','protocol_sha256':sha(PROTOCOL),'review_packet_sha256':sha(REVIEW_PACKET),'reviewer_q_submission_sha256':sha(submission_path('q')),'reviewer_g_submission_sha256':sha(submission_path('g')),'gap_count':len(rows),'agreement_status_counts':dict(sorted(sc.items())),'exact_agreement_rate':sc['exact_agreement']/len(rows),'classification_agreement_rate':(sc['exact_agreement']+sc['classification_agreement_reason_disagreement'])/len(rows),'classification_matrix':[{'reviewer_q':k[0],'reviewer_g':k[1],'count':v} for k,v in sorted(matrix.items())],'disagreement_count':len(ds),'automatic_adjudication_performed':False,'rows':rows,'held_out_accessed':False};write_once(AGREEMENT,report)
 ready={'schema_version':7,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v7','status':'non_claim_accounting_review_complete_awaiting_adjudication' if ds else 'non_claim_accounting_review_complete_exact_agreement_not_yet_consolidated','artifact_lineage':{'coverage_report_v4_sha256':sha(COVERAGE_REPORT),'gap_worklist_v1_sha256':sha(GAP_WORKLIST),'non_claim_protocol_v1_sha256':sha(PROTOCOL),'review_packet_v1_sha256':sha(REVIEW_PACKET),'reviewer_q_submission_v1_sha256':sha(submission_path('q')),'reviewer_g_submission_v1_sha256':sha(submission_path('g')),'agreement_q_g_v1_sha256':sha(AGREEMENT)},'gates':{'dual_blind_gap_review_completed':True,'agreement_computed':True,'disagreements_resolved':len(ds)==0,'explicit_non_claim_accounting_frozen':False,'coverage_qa_rerun_allowed':False,'coverage_qa_passed':False,'boundary_gold_frozen':False,'support_review_allowed':False,'held_out_accessed':False},'gap_count':len(rows),'disagreement_count':len(ds),'next_authorized_stage':'frozen_non_claim_accounting_adjudication_protocol' if ds else 'deterministic_non_claim_accounting_consolidation','automatic_adjudication_performed':False};write_once(READINESS_V7,ready)
 print(json.dumps({'status':report['status'],'gap_count':len(rows),'agreement_status_counts':report['agreement_status_counts'],'exact_agreement_rate':report['exact_agreement_rate'],'classification_agreement_rate':report['classification_agreement_rate'],'agreement_sha256':sha(AGREEMENT),'readiness_v7_sha256':sha(READINESS_V7),'boundary_gold_frozen':False,'support_review_allowed':False,'held_out_accessed':False},indent=2))

def verify_prepared()->None:
 p=load(REVIEW_PACKET);f=load(FIXTURES);checks={'case_count_10':p.get('case_count')==10,'anchor_count_38':p.get('anchor_count')==38,'gap_count_84':p.get('gap_count')==84,'eligible_chars_206':p.get('eligible_non_whitespace_character_count')==206,'fixtures_9_of_9':f.get('fixture_count')==9 and f.get('fixtures_passed')==9 and f.get('all_fixtures_passed') is True,'provider_called_false':f.get('provider_called') is False,'held_out_false':p.get('held_out_accessed') is False and f.get('held_out_accessed') is False}
 print(json.dumps({'all_passed':all(checks.values()),'checks':checks,'hashes':{'adapter':sha(Path(__file__)),'protocol':sha(PROTOCOL),'policy':sha(POLICY),'prompt':sha(PROMPT),'packet':sha(REVIEW_PACKET),'fixtures':sha(FIXTURES)}},indent=2))
 if not all(checks.values()):raise ValueError('prepared_artifact_verification_failed')

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--verify-prepared',action='store_true');ap.add_argument('--freeze-manifest',choices=sorted(REVIEWERS));ap.add_argument('--execute',choices=sorted(REVIEWERS));ap.add_argument('--agreement',action='store_true');a=ap.parse_args()
 if sum(bool(x) for x in [a.prepare,a.verify_prepared,a.freeze_manifest,a.execute,a.agreement])!=1:ap.error('choose exactly one action')
 if a.prepare:prepare()
 elif a.verify_prepared:verify_prepared()
 elif a.freeze_manifest:freeze_manifest(a.freeze_manifest)
 elif a.execute:return execute(a.execute)
 else:compute_agreement()
 return 0
if __name__=='__main__':raise SystemExit(main())