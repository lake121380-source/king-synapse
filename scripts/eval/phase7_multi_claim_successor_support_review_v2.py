#!/usr/bin/env python3
"""Frozen independent Support Review v2 using positionwise evidence citation masks."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,re,tempfile,urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from phase7_execution_attempt_log import append_event,read_entries
SELF=Path(__file__).resolve(); ROOT=SELF.parents[2]; C=ROOT/'crates/eval/config'; D=ROOT/'crates/eval/datasets/pattern_extraction'; R=ROOT/'crates/eval/reports'
STATE=D/'phase7_3_3_d_support_stage_state_v53.json'; READY=R/'phase7_3_3_d1_reference_construction_readiness_v64.json'; ENTRY_RECEIPT=R/'phase7_3_3_d_multi_claim_successor_support_review_v2_entry_receipt_v1.json'; PACKET_RECEIPT=R/'phase7_3_3_d_multi_claim_successor_support_packet_construction_receipt_v1.json'; REF_SEAL=R/'phase7_3_3_d_multi_claim_successor_type_metadata_reference_candidate_seal_v1.json'
PROTOCOL=C/'phase7_3_3_d_multi_claim_successor_support_review_protocol_v2.json'; SCHEMA=C/'phase7_3_3_d_multi_claim_successor_support_review_schema_v2.json'; PROMPT=C/'phase7_3_3_d_multi_claim_successor_support_reviewer_prompt_v2.md'; POLICY=C/'phase7_3_3_d_multi_claim_successor_support_review_execution_policy_v2.json'; FIXTURES=R/'phase7_3_3_d_multi_claim_successor_support_review_contract_fixtures_v2.json'
JOINT_REPORT=R/'phase7_3_3_d_multi_claim_successor_support_review_execution_report_v2.json'; JOINT_OUTCOME=R/'phase7_3_3_d_multi_claim_successor_support_review_execution_outcome_v2.json'; JOINT_RECEIPT=R/'phase7_3_3_d_multi_claim_successor_support_review_execution_receipt_v2.json'; STATE_OUT=D/'phase7_3_3_d_support_stage_state_v54.json'; READY_OUT=R/'phase7_3_3_d1_reference_construction_readiness_v65.json'
CURRENT='construct_multi_claim_successor_support_review_v2'; NEXT_OK='compute_multi_claim_successor_support_agreement_v1'; NEXT_NEG='design_new_multi_claim_successor_support_review_version_if_research_continues'
BASE='https://api.gpt.ge/v1'; CRED='PHASE7_ATOMIC_JUDGE_API_KEY'; TEMP=0; TOP_P=1; MAX_TOKENS=12000; TIMEOUT=600; RESPONSE_FORMAT={'type':'json_object'}
REVIEWERS={'a':{'label':'Reviewer A','model':'gpt-4.1'},'b':{'label':'Reviewer B','model':'qwen3.5-plus'}}
LABELS={'supported','partially_supported','unsupported','not_assessable'}; CONF={'low','medium','high'}
REASONS={'direct_evidence_match','conservative_entailment','reasonable_bridging_inference','scope_preserved','counterexample_preserved','scope_expansion','certainty_escalation','causal_leap','prediction_overcommitment','unsupported_detail','counterexample_ignored','central_proposition_unsupported','insufficient_evidence'}
TOP={'decisions'}; DKEYS={'claim_index','support_label','evidence_citation_mask','reason_codes','support_rationale','annotation_confidence'}
EXPECTED={STATE:'37648ce9663804f5430d804423d1702455024cda7c52936e3d63ab32a2f057da',READY:'3a19469880d072747a4921d2839ac5fb8c0e0fcc2a56decd225a4eff87388d12',ENTRY_RECEIPT:'d25af961c4359160442d5b42aca12df11edb13d2914c0f814fa04d42a9085b2b',PACKET_RECEIPT:'ad196037f6cb8c8291f2fa2e7f73524bfd8a35ee0ca15daf68eddc3811aa0fec',REF_SEAL:'d2c0d394cd11d47d5eed3352d1d74bcc16178e91049038968ccfc3c31bee1fd9'}
PACK_SHA={'a':'8015f72bee65b7a3ee42e6d070ae3a5a2b947c4123bbacc3b6a37715b11b4945','b':'f4fbf85dcba9ac21b958244cdfabaa5d7b73f638d01188f068dd9228d927fb7c'}; TEMPLATE_SHA={'a':'6d68bdef011cf09345da6a8f8db3ac50790b9bf5a5adc06054f14abca6d24024','b':'59f6663c10133f50bcb197814a55def9392bf2189a244edc14a8a939dae868a2'}
class ReviewFailure(ValueError):
 def __init__(self,code,level,subtype,envelope_sha=None,content_sha=None,reported=None):super().__init__(code);self.code=code;self.level=level;self.subtype=subtype;self.envelope_sha=envelope_sha;self.content_sha=content_sha;self.reported=reported
def attach_failure_context(e,eh,ch,rep):
 e.envelope_sha=e.envelope_sha or eh;e.content_sha=e.content_sha or ch;e.reported=e.reported or rep;return e
def packet(r):return D/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_packet_v1.json'
def template(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_submission_template_v1.json'
def manifest(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_execution_manifest_v2.json'
def attempts(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_execution_attempts_v2.jsonl'
def case_dir(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_cases_v2'
def checkpoint(r,c):return case_dir(r)/f'{c}.json'
def submission(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_completed_submission_v2.json'
def result(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_execution_result_v2.json'
def negative(r):return R/f'phase7_3_3_d_multi_claim_successor_support_reviewer_{r}_negative_result_v2.json'
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
def csha(x):return hb(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rel(p):return p.relative_to(ROOT).as_posix()
def once(p,x):
 b=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_artifact_mismatch:'+rel(p))
  return hb(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return hb(b)
def text_once(p,x):
 b=x.encode()
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_artifact_mismatch:'+rel(p))
  return hb(b)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return hb(b)
def protocol_doc():return {'schema_version':2,'protocol_id':'phase7.3.3-d-multi-claim-successor-independent-support-review-v2','stage':'Multi-claim Successor Reference Construction / Support Review','research_object':'independent evidential support classification for sealed multi-claim reference candidates','predecessor_v1_result':'authoritative_negative_cited_evidence_index_out_of_range','entry_gate':{'current_gate':CURRENT,'case_count':40,'claim_count':240,'support_packets_frozen':True,'reference_candidate_sealed':True,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False},'reviewers':{r:{'model_requested':v['model'],'independent':True} for r,v in REVIEWERS.items()},'controlled_invariants':['selected_40_cases','sealed_240_claim_reference_candidate','support_packets','support_labels','reason_codes','support_semantics','provider','reviewer_models','temperature','top_p','max_tokens','blindness'],'single_intended_experimental_change':'sparse cited_evidence_indices replaced by fixed-length binary evidence_citation_mask','representation':{'type':'operation_index_plus_positionwise_binary_mask','model_outputs_claim_index_not_reference_claim_id':True,'model_outputs_fixed_length_binary_evidence_mask':True,'mask_length_equals_case_evidence_count':True,'mask_position_one_maps_to_evidence_index_one':True,'adapter_reconstructs_immutable_ids':True,'claim_indices_one_based':True,'claim_mutation_forbidden':True},'independence':{'reviewer_packet_isolation':True,'other_reviewer_submission_visible':False,'old_gold_visible':False,'arm_outputs_visible':False,'boundary_adjudication_rationales_visible':False,'external_tools_enabled':False,'web_access_enabled':False,'memory_enabled':False},'output_contract':{'required_top_level_keys':sorted(TOP),'required_decision_keys':sorted(DKEYS),'one_decision_per_reference_claim':True,'claim_order_must_match_packet':True,'support_label_enum':sorted(LABELS),'reason_code_enum':sorted(REASONS),'confidence_enum':sorted(CONF),'evidence_citation_mask_binary_only':True,'evidence_citation_mask_exact_case_length':True,'same_case_citations_only_by_construction':True,'citations_may_be_empty_via_all_zero_mask':True,'reason_codes_may_be_empty':True,'duplicates_forbidden':True,'nonempty_rationale':True},'provider_contract':{'provider':'api.gpt.ge','base_url':BASE,'credential_env_name':CRED,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESPONSE_FORMAT,'first_provider_content_authoritative':True,'envelope_and_content_hashes_recorded':True,'raw_provider_response_stored':False},'failure_policy':{'pre_content_transport_failure_resumable_same_manifest':True,'post_content_failure_authoritative_negative':True,'post_content_same_version_retry_forbidden':True,'other_reviewer_may_continue':True,'agreement_requires_two_completed_submissions':True},'instrumentation':{'post_parse_failure_hash_propagation_corrected':True,'semantic_effect':False},'completion_gate':{'completed_case_count':40,'support_decision_count':240,'both_reviewers_required_for_agreement':True}}
def schema_doc():return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'phase7.3.3-d-multi-claim-successor-support-review-schema-v2','type':'object','additionalProperties':False,'required':['decisions'],'properties':{'decisions':{'type':'array','items':{'type':'object','additionalProperties':False,'required':sorted(DKEYS),'properties':{'claim_index':{'type':'integer','minimum':1},'support_label':{'type':'string','enum':sorted(LABELS)},'evidence_citation_mask':{'type':'string','pattern':'^[01]+$'},'reason_codes':{'type':'array','items':{'type':'string','enum':sorted(REASONS)},'uniqueItems':True},'support_rationale':{'type':'string','minLength':1},'annotation_confidence':{'type':'string','enum':sorted(CONF)}}}}}}
def prompt_doc():return '''# Phase 7.3.3-D Multi-claim Successor Independent Support Reviewer Prompt v2

## System message

You are one independent Support Reviewer in a frozen scientific evaluation. Classify evidential support for every immutable claim in the supplied single-case operation packet using only its frozen evidence. Do not use outside knowledge, web search, memory, hidden context, historical labels, arm outputs, or another reviewer's work.

The claim boundary, text, role, type, and origin are immutable. Do not create, delete, split, merge, rewrite, quote, or reorder claims. You only make Support decisions.

Labels:
- supported: evidence establishes all material content at matching scope, certainty, causality, prediction strength, qualifications, and counterexamples.
- partially_supported: the core direction is established, but material detail, scope, certainty, causality, prediction, qualification, or exception exceeds evidence.
- unsupported: the material claim cannot be established or conflicts with evidence.
- not_assessable: evidence or the immutable boundary is insufficient for a stable judgment.

Allowed reason codes: direct_evidence_match, conservative_entailment, reasonable_bridging_inference, scope_preserved, counterexample_preserved, scope_expansion, certainty_escalation, causal_leap, prediction_overcommitment, unsupported_detail, counterexample_ignored, central_proposition_unsupported, insufficient_evidence.

Return a bare JSON object only, without Markdown or extra keys. Return exactly one decision per claim in exact claim_index order. Copy only the supplied small integer claim_index.

For evidence citations, NEVER output evidence indices or evidence IDs. Instead output evidence_citation_mask as a binary string whose length is exactly evidence_count. Character 1 means cite the evidence item at that same position; character 0 means do not cite it. Example: evidence_count=4 and citations are evidence positions 1 and 3 => "1010". No citations => "0000". Do not add spaces, punctuation, prefixes, or suffixes to the mask.

reason_codes may be empty but cannot contain duplicates. support_rationale must be concise, nonempty, and evidence-grounded. annotation_confidence must be low, medium, or high.

Exact shape for a case with evidence_count=3: {"decisions":[{"claim_index":1,"support_label":"supported","evidence_citation_mask":"100","reason_codes":["direct_evidence_match"],"support_rationale":"Concise evidence-grounded reason.","annotation_confidence":"high"}]}

## User message template

Classify this frozen single-case operation packet. Return only the required JSON object. Remember: every evidence_citation_mask must contain exactly evidence_count binary characters.

{CASE_OPERATION_PACKET_JSON}
'''
def policy_doc():return {'schema_version':2,'policy_id':'phase7.3.3-d-multi-claim-successor-support-review-execution-policy-v2','execution_order':'independent reviewers; outputs never cross-exposed','case_order':'frozen packet order','checkpoint_policy':'successful case checkpoints immutable and resumable','transport_resume_policy':'pre-content failure may resume under identical frozen manifest','authoritative_failure_policy':'first Provider Content is authoritative; post-content failure permanently terminates reviewer version','raw_provider_response_storage':'forbidden; hashes only','adapter_representation':'claim index plus fixed-length binary evidence citation mask deterministically reconstruct immutable IDs','agreement_policy':'not computed here','support_gold_policy':'not created here','confirmatory_dataset_policy':'closed','runtime_integration_policy':'unauthorized','credential_env_name':CRED,'secret_persistence':'forbidden','v1_same_version_retry_performed':False}
def operation(case):return {'case_ordinal_note':'single isolated case; output omits case_id','evidence_count':len(case['evidence_bundle']),'evidence':[{'evidence_index':i,'evidence_text':x['content']} for i,x in enumerate(case['evidence_bundle'],1)],'claims':[{'claim_index':x['claim_index'],'claim_text':x['source_excerpt'],'claim_role':x['claim_role'],'claim_type':x['claim_type'],'claim_origin':x['claim_origin']} for x in case['claims']]}
def canonical(requested,reported):
 if not isinstance(reported,str) or not reported.strip():raise ReviewFailure('provider_reported_model_missing','level_1_provider_representation','identity_failure')
 tail=reported.strip().lower().rsplit('/',1)[-1];q=requested.lower()
 if tail==q:return requested
 if tail.startswith(q+'-') and re.fullmatch(r'[a-z0-9][a-z0-9._-]*',tail[len(q)+1:]):return requested
 raise ReviewFailure('provider_model_outside_requested_family:'+reported,'level_1_provider_representation','identity_failure',reported=reported)
def normalize(case,obj):
 if not isinstance(obj,dict):raise ReviewFailure('response_not_object','level_1_schema','schema_failure')
 if set(obj)!=TOP:raise ReviewFailure('response_top_level_keys_invalid','level_1_schema','schema_failure')
 ds=obj.get('decisions')
 if not isinstance(ds,list):raise ReviewFailure('decisions_not_array','level_1_schema','schema_failure')
 if len(ds)!=len(case['claims']):raise ReviewFailure('decision_cardinality_mismatch','level_1_schema','accounting_failure')
 out=[];evidence=case['evidence_bundle'];n=len(evidence)
 for claim,d in zip(case['claims'],ds,strict=True):
  if not isinstance(d,dict) or set(d)!=DKEYS:raise ReviewFailure('decision_keys_invalid','level_1_schema','schema_failure')
  i=d['claim_index']
  if isinstance(i,bool) or not isinstance(i,int):raise ReviewFailure('claim_index_not_integer','level_1_schema','index_failure')
  if i!=claim['claim_index']:raise ReviewFailure('claim_index_order_or_value_mismatch','level_1_schema','index_failure')
  label=d['support_label']
  if not isinstance(label,str) or label not in LABELS:raise ReviewFailure('support_label_invalid','level_2_support_contract','semantic_contract_failure')
  mask=d['evidence_citation_mask']
  if not isinstance(mask,str):raise ReviewFailure('evidence_citation_mask_not_string','level_1_schema','schema_failure')
  if len(mask)!=n:raise ReviewFailure('evidence_citation_mask_length_mismatch','level_1_schema','accounting_failure')
  if any(ch not in '01' for ch in mask):raise ReviewFailure('evidence_citation_mask_non_binary','level_1_schema','serialization_failure')
  cites=[j for j,ch in enumerate(mask,1) if ch=='1']
  reasons=d['reason_codes']
  if not isinstance(reasons,list) or any(not isinstance(x,str) for x in reasons):raise ReviewFailure('reason_codes_invalid_type','level_1_schema','schema_failure')
  if len(reasons)!=len(set(reasons)):raise ReviewFailure('duplicate_reason_code','level_2_support_contract','semantic_contract_failure')
  if any(x not in REASONS for x in reasons):raise ReviewFailure('reason_code_invalid','level_2_support_contract','semantic_contract_failure')
  rat=d['support_rationale'];conf=d['annotation_confidence']
  if not isinstance(rat,str) or not rat.strip():raise ReviewFailure('support_rationale_blank','level_2_support_contract','semantic_contract_failure')
  if not isinstance(conf,str) or conf not in CONF:raise ReviewFailure('annotation_confidence_invalid','level_2_support_contract','semantic_contract_failure')
  out.append({'case_id':case['case_id'],'reference_claim_id':claim['reference_claim_id'],'claim_index':i,'support_label':label,'evidence_citation_mask':mask,'cited_evidence_indices':cites,'cited_evidence_ids':[evidence[x-1]['evidence_id'] for x in cites],'reason_codes':reasons,'support_rationale':rat.strip(),'annotation_confidence':conf})
 return out
def fixture_doc():
 case={'case_id':'fixture','evidence_bundle':[{'evidence_id':'e1','content':'alpha'},{'evidence_id':'e2','content':'beta'}],'claims':[{'reference_claim_id':'c1','claim_index':1},{'reference_claim_id':'c2','claim_index':2}]};d1={'claim_index':1,'support_label':'supported','evidence_citation_mask':'10','reason_codes':['direct_evidence_match'],'support_rationale':'Direct.','annotation_confidence':'high'};d2={'claim_index':2,'support_label':'unsupported','evidence_citation_mask':'00','reason_codes':['insufficient_evidence'],'support_rationale':'Absent.','annotation_confidence':'medium'};v={'decisions':[d1,d2]}
 fs=[('valid',v,1),('empty_reasons',{'decisions':[{**d1,'reason_codes':[]},d2]},1),('all_cited',{'decisions':[{**d1,'evidence_citation_mask':'11'},d2]},1),('extra_top',{**v,'case_id':'x'},0),('missing',{'decisions':[d1]},0),('reorder',{'decisions':[d2,d1]},0),('bool_index',{'decisions':[{**d1,'claim_index':True},d2]},0),('bad_label',{'decisions':[{**d1,'support_label':'not_supported'},d2]},0),('mask_short',{'decisions':[{**d1,'evidence_citation_mask':'1'},d2]},0),('mask_long',{'decisions':[{**d1,'evidence_citation_mask':'100'},d2]},0),('mask_nonbinary',{'decisions':[{**d1,'evidence_citation_mask':'1x'},d2]},0),('mask_array',{'decisions':[{**d1,'evidence_citation_mask':[1,0]},d2]},0),('sparse_indices_forbidden',{'decisions':[{**d1,'cited_evidence_indices':[1]},d2]},0),('bad_reason',{'decisions':[{**d1,'reason_codes':['invented']},d2]},0),('dup_reason',{'decisions':[{**d1,'reason_codes':['scope_preserved']*2},d2]},0),('blank',{'decisions':[{**d1,'support_rationale':' '},d2]},0),('bad_conf',{'decisions':[{**d1,'annotation_confidence':'certain'},d2]},0),('extra_key',{'decisions':[{**d1,'reference_claim_id':'forbidden'},d2]},0)]
 rs=[]
 for n,x,w in fs:
  ok=1;err=None
  try:normalize(case,x)
  except Exception as e:ok=0;err=str(e)
  rs.append({'fixture':n,'expected_pass':bool(w),'observed_pass':bool(ok),'fixture_passed':ok==w,'observed_error':err})
 for n,q,x,w in [('identity_exact_gpt','gpt-4.1','gpt-4.1',1),('identity_prefixed_gpt','gpt-4.1','openai/gpt-4.1',1),('identity_snapshot_gpt','gpt-4.1','openai/gpt-4.1-2025-04-14',1),('identity_exact_qwen','qwen3.5-plus','qwen3.5-plus',1),('identity_prefixed_qwen','qwen3.5-plus','qwen/qwen3.5-plus',1),('identity_wrong','qwen3.5-plus','qwen/qwen-max',0)]:
  ok=1;err=None
  try:canonical(q,x)
  except Exception as e:ok=0;err=str(e)
  rs.append({'fixture':n,'expected_pass':bool(w),'observed_pass':bool(ok),'fixture_passed':ok==w,'observed_error':err})
 e=attach_failure_context(ReviewFailure('fixture','level_2_support_contract','fixture'), 'envelope-hash', 'content-hash', 'reported-model');rs.append({'fixture':'post_parse_failure_hash_context','expected_pass':True,'observed_pass':e.envelope_sha=='envelope-hash' and e.content_sha=='content-hash' and e.reported=='reported-model','fixture_passed':e.envelope_sha=='envelope-hash' and e.content_sha=='content-hash' and e.reported=='reported-model','observed_error':None})
 return {'schema_version':2,'report_id':'phase7.3.3-d-multi-claim-successor-support-review-contract-fixtures-v2','fixture_count':len(rs),'fixtures_passed':sum(x['fixture_passed'] for x in rs),'all_fixtures_passed':all(x['fixture_passed'] for x in rs),'provider_called':False,'results':rs}
def preflight_checks():
 req=list(EXPECTED)+[packet(r) for r in REVIEWERS]+[template(r) for r in REVIEWERS];z={'exists:'+rel(p):p.exists() for p in req}
 if not all(z.values()):return z
 for p,h in EXPECTED.items():z['sha:'+rel(p)]=sha(p)==h
 for r in REVIEWERS:z['packet_sha:'+r]=sha(packet(r))==PACK_SHA[r];z['template_sha:'+r]=sha(template(r))==TEMPLATE_SHA[r]
 s=load(STATE);rd=load(READY);entry=load(ENTRY_RECEIPT);rc=load(PACKET_RECEIPT);seal=load(REF_SEAL);a=load(packet('a'));b=load(packet('b'));ta=load(template('a'));tb=load(template('b'))
 z.update({'state_gate':s.get('next_authorized_stage')==CURRENT,'ready_gate':rd.get('next_authorized_stage')==CURRENT,'state_v53':s.get('schema_version')==53,'ready_v64':rd.get('schema_version')==64,'entry_receipt_pass':entry.get('status')=='PASS','v1_negative_preserved':s.get('multi_claim_successor_support_review_v1_negative_preserved') is True,'receipt_pass':rc.get('status')=='PASS','receipt_a':rc.get('reviewer_a_packet_sha256')==PACK_SHA['a'],'receipt_b':rc.get('reviewer_b_packet_sha256')==PACK_SHA['b'],'seal_pass':seal.get('status')=='verified_and_sealed_for_blind_support_review_not_gold','seal_240':seal.get('claim_count')==240,'a_counts':a.get('case_count')==40 and a.get('claim_count')==240,'b_counts':b.get('case_count')==40 and b.get('claim_count')==240,'payloads_equal':a.get('cases')==b.get('cases'),'a_blind':a.get('other_reviewer_packet_visible') is False,'b_blind':b.get('other_reviewer_packet_visible') is False,'no_prelabels':all('support_label' not in x for c in a['cases'] for x in c['claims']),'template_a_empty':ta.get('cases')==[] and ta.get('provider_called') is False,'template_b_empty':tb.get('cases')==[] and tb.get('provider_called') is False,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False and rd.get('confirmatory_dataset_opened') is False,'runtime_off':s.get('runtime_integration_authorized') is False and rd.get('runtime_integration_authorized') is False,'support_gold_absent':s.get('multi_claim_successor_support_gold_created') is False and rd.get('multi_claim_successor_support_gold_created') is False})
 ids=[x['reference_claim_id'] for c in a['cases'] for x in c['claims']];z['ids_unique_240']=len(ids)==len(set(ids))==240;z['evidence_nonempty_all_cases']=all(len(c.get('evidence_bundle',[]))>0 for c in a['cases']);z['operations_40']=len([operation(c) for c in a['cases']])==40;return z
def preflight():
 z=preflight_checks();f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'provider_called':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def expected_manifest(r):
 if not all(preflight_checks().values()):raise ValueError('entry_gate_failed')
 if not load(FIXTURES).get('all_fixtures_passed'):raise ValueError('fixtures_not_passed')
 p=load(packet(r));v=REVIEWERS[r]
 return {'schema_version':1,'manifest_id':f'phase7.3.3-d-multi-claim-successor-support-reviewer-{r}-execution-manifest-v2','status':'frozen_not_started','reviewer_id':r,'reviewer_label':v['label'],'reviewer_type':'ai_model','provider':'api.gpt.ge','provider_base_url':BASE,'model_requested':v['model'],'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESPONSE_FORMAT,'timeout_seconds':TIMEOUT,'credential_env_name':CRED,'adapter_sha256':sha(SELF),'protocol_sha256':sha(PROTOCOL),'schema_sha256':sha(SCHEMA),'prompt_sha256':sha(PROMPT),'execution_policy_sha256':sha(POLICY),'contract_fixtures_sha256':sha(FIXTURES),'support_stage_state_v53_sha256':sha(STATE),'readiness_v64_sha256':sha(READY),'successor_entry_receipt_sha256':sha(ENTRY_RECEIPT),'packet_receipt_sha256':sha(PACKET_RECEIPT),'reference_seal_sha256':sha(REF_SEAL),'review_packet_sha256':sha(packet(r)),'submission_template_sha256':sha(template(r)),'packet_id':p['packet_id'],'case_count':p['case_count'],'claim_count':p['claim_count'],'evidence_item_count':p['evidence_item_count'],'representation':'operation_index_plus_positionwise_binary_mask','id_reconstruction':'deterministic_adapter','case_isolation':True,'other_reviewer_visible':False,'old_gold_visible':False,'arm_outputs_visible':False,'boundary_adjudication_rationales_visible':False,'external_tools_enabled':False,'web_access_enabled':False,'memory_enabled':False,'raw_provider_responses_stored':False,'first_provider_content_authoritative':True,'pre_content_transport_resume_allowed':True,'post_content_same_version_retry_allowed':False,'model_identity_policy':'provider namespace and revision suffix only within requested family','confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
def prepare():
 g=preflight()
 if g['status']!='PASS':raise ValueError('preflight_failed:'+repr(g['failed']))
 f=fixture_doc()
 if not f['all_fixtures_passed']:raise ValueError('fixtures_failed')
 h={'protocol_sha256':once(PROTOCOL,protocol_doc()),'schema_sha256':once(SCHEMA,schema_doc()),'prompt_sha256':text_once(PROMPT,prompt_doc()),'policy_sha256':once(POLICY,policy_doc()),'fixtures_sha256':once(FIXTURES,f)};h['reviewer_a_manifest_sha256']=once(manifest('a'),expected_manifest('a'));h['reviewer_b_manifest_sha256']=once(manifest('b'),expected_manifest('b'));return {'status':'PASS','prepared':True,'fixtures':f"{f['fixtures_passed']}/{f['fixture_count']}",**h,'provider_called':False}
def verify_prepare():
 z=preflight_checks();ps=[PROTOCOL,SCHEMA,PROMPT,POLICY,FIXTURES,manifest('a'),manifest('b')];z.update({'exists:'+rel(p):p.exists() for p in ps})
 if all(p.exists() for p in ps):z.update({'protocol_replay':load(PROTOCOL)==protocol_doc(),'schema_replay':load(SCHEMA)==schema_doc(),'prompt_replay':PROMPT.read_text(encoding='utf-8-sig')==prompt_doc(),'policy_replay':load(POLICY)==policy_doc(),'fixtures_replay':load(FIXTURES)==fixture_doc(),'fixtures_pass':load(FIXTURES).get('all_fixtures_passed') is True,'manifest_a_replay':load(manifest('a'))==expected_manifest('a'),'manifest_b_replay':load(manifest('b'))==expected_manifest('b')})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'hashes':{x:sha(p) if p.exists() else None for x,p in [('adapter',SELF),('protocol',PROTOCOL),('schema',SCHEMA),('prompt',PROMPT),('policy',POLICY),('fixtures',FIXTURES),('manifest_a',manifest('a')),('manifest_b',manifest('b'))]},'provider_called':False}
def split_prompt():
 x=PROMPT.read_text(encoding='utf-8-sig').split('## System message\n\n',1)[1];s,u=x.split('\n## User message template\n\n',1);return s.strip(),u.strip()
def call(key,model,system,user):
 payload={'model':model,'temperature':TEMP,'top_p':TOP_P,'max_tokens':MAX_TOKENS,'response_format':RESPONSE_FORMAT,'messages':[{'role':'system','content':system},{'role':'user','content':user}]};req=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as resp:return resp.read()
def parse_content(raw,requested):
 eh=hb(raw)
 try:env=json.loads(raw.decode())
 except Exception as e:raise ReviewFailure('provider_envelope_json_invalid:'+type(e).__name__,'level_1_provider_representation','envelope_parse_failure',eh) from e
 if not isinstance(env,dict):raise ReviewFailure('provider_envelope_not_object','level_1_provider_representation','envelope_parse_failure',eh)
 choices=env.get('choices')
 if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):raise ReviewFailure('provider_choices_invalid','level_1_provider_representation','envelope_parse_failure',eh)
 msg=choices[0].get('message')
 if not isinstance(msg,dict):raise ReviewFailure('provider_message_invalid','level_1_provider_representation','envelope_parse_failure',eh)
 content=msg.get('content')
 if not isinstance(content,str) or not content.strip():raise ReviewFailure('provider_content_missing','level_1_provider_representation','content_missing',eh)
 ch=hb(content.encode());reported=env.get('model')
 try:can=canonical(requested,reported)
 except ReviewFailure as e:e.envelope_sha=eh;e.content_sha=ch;e.reported=reported if isinstance(reported,str) else None;raise
 try:obj=json.loads(content)
 except Exception as e:raise ReviewFailure('provider_content_json_invalid:'+type(e).__name__,'level_1_provider_representation','serialization_failure',eh,ch,reported) from e
 return eh,ch,reported,can,obj
def validate_checkpoint(r,case,mh):
 x=load(checkpoint(r,case['case_id']));z={'status':x.get('status')=='authoritative_success','manifest':x.get('manifest_sha256')==mh,'reviewer':x.get('reviewer_id')==r,'case':x.get('case_id')==case['case_id'],'count':x.get('decision_count')==len(case['claims']),'hash':x.get('normalized_decisions_sha256')==csha(x.get('decisions'))}
 if not all(z.values()):raise ValueError('checkpoint_verification_failed:'+case['case_id'])
 if [d.get('reference_claim_id') for d in x['decisions']]!=[c['reference_claim_id'] for c in case['claims']]:raise ValueError('checkpoint_lineage_failed:'+case['case_id'])
 return x
def checkpoint_prefix(r,p,mh):
 out=[];missing=False;known={checkpoint(r,c['case_id']) for c in p['cases']};directory=case_dir(r)
 if directory.exists() and any(x not in known for x in directory.glob('*.json')):raise ValueError('unknown_checkpoint_file')
 for c in p['cases']:
  q=checkpoint(r,c['case_id'])
  if q.exists():
   if missing:raise ValueError('non_prefix_checkpoint_set')
   out.append(validate_checkpoint(r,c,mh))
  else:missing=True
 return out
def terminal(r):
 done=submission(r).exists() and result(r).exists();neg=negative(r).exists()
 if done and neg:raise ValueError('multiple_terminal_outcomes:'+r)
 return 'completed' if done else 'authoritative_negative_result' if neg else None
def execute(r):
 if not manifest(r).exists() or load(manifest(r))!=expected_manifest(r):raise ValueError('manifest_missing_or_invalid')
 mh=sha(manifest(r));term=terminal(r)
 if term=='completed':return {'status':'PASS','reviewer':r,'terminal_outcome':'already_completed_no_retry','submission_sha256':sha(submission(r))}
 if term:raise ValueError('authoritative_negative_result_exists_same_version_retry_forbidden')
 key=os.environ.get(CRED,'').strip()
 if not key:raise ValueError('credential_env_missing:'+CRED)
 system,ut=split_prompt();p=load(packet(r));cfg=REVIEWERS[r];cps=checkpoint_prefix(r,p,mh);case_rs=[x['case_result'] for x in cps];all_ds=[d for x in cps for d in x['decisions']];reported={x['provider_reported_model'] for x in cps};families={x['canonical_model_family'] for x in cps}
 append_event({'event_type':'multi_claim_successor_support_review_invocation','manifest_sha256':mh,'reviewer':r,'status':'started_or_resumed','completed_case_count_at_start':len(cps),'response_received':False,'authoritative_result':False},attempts(r))
 for case in p['cases'][len(cps):]:
  op=operation(case);user=ut.replace('{CASE_OPERATION_PACKET_JSON}',json.dumps(op,ensure_ascii=False,separators=(',',':')))
  try:raw=call(key,cfg['model'],system,user)
  except Exception as e:
   append_event({'event_type':'multi_claim_successor_support_review_transport_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'status':'transport_failure_resumable','failure_type':type(e).__name__,'failure_code':str(e)[:500],'provider_content_received':False,'response_received':False,'authoritative_result':False,'same_manifest_resume_allowed':True,'completed_case_count_before_failure':len(case_rs),'completed_decision_count_before_failure':len(all_ds)},attempts(r));return {'status':'TRANSPORT_FAILURE_RESUMABLE','reviewer':r,'failed_case_id':case['case_id'],'failure_type':type(e).__name__,'failure_code':str(e)[:500],'completed_case_count':len(case_rs),'completed_decision_count':len(all_ds),'same_manifest_resume_allowed':True}
  eh=hb(raw);ch=None;rep=None
  try:eh,ch,rep,can,obj=parse_content(raw,cfg['model']);ds=normalize(case,obj)
  except ReviewFailure as e:
   e=attach_failure_context(e,eh,ch,rep);eh=e.envelope_sha;ch=e.content_sha;rep=e.reported;append_event({'event_type':'multi_claim_successor_support_review_authoritative_failure','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'status':'authoritative_negative_result','failure_level':e.level,'failure_subtype':e.subtype,'failure_type':type(e).__name__,'failure_code':e.code,'provider_content_received':ch is not None,'response_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'completed_case_count_before_failure':len(case_rs),'completed_decision_count_before_failure':len(all_ds)},attempts(r));n={'schema_version':1,'result_id':f'phase7.3.3-d-multi-claim-successor-support-reviewer-{r}-negative-result-v2','status':'authoritative_negative_result','reviewer_id':r,'model_requested':cfg['model'],'manifest_sha256':mh,'failed_case_id':case['case_id'],'failure_level':e.level,'failure_subtype':e.subtype,'failure_type':type(e).__name__,'failure_code':e.code,'response_received':True,'provider_content_received':ch is not None,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'completed_case_count_before_failure':len(case_rs),'completed_decision_count_before_failure':len(all_ds),'end_to_end_protocol_conclusion_authorized':True,'support_semantic_capability_conclusion_authorized':e.level=='level_2_support_contract','same_version_retry_allowed':False,'other_reviewer_execution_allowed':True,'agreement_allowed':False,'raw_provider_response_stored':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};return {'status':'AUTHORITATIVE_NEGATIVE_RESULT','reviewer':r,'negative_result_sha256':once(negative(r),n),'failure_level':e.level,'failure_subtype':e.subtype,'failure_code':e.code,'same_version_retry_allowed':False}
  cp={'schema_version':1,'checkpoint_id':f"phase7.3.3-d-multi-claim-successor-support-{r}-{case['case_id']}-v2",'status':'authoritative_success','manifest_sha256':mh,'reviewer_id':r,'case_id':case['case_id'],'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'canonical_model_family':can,'operation_packet_sha256':csha(op),'normalized_decisions_sha256':csha(ds),'decision_count':len(ds),'decisions':ds,'case_result':{'case_id':case['case_id'],'status':'completed','decision_count':len(ds)},'raw_provider_response_stored':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};cph=once(checkpoint(r,case['case_id']),cp);append_event({'event_type':'multi_claim_successor_support_review_case_authoritative_success','manifest_sha256':mh,'reviewer':r,'case_id':case['case_id'],'status':'completed','response_received':True,'provider_content_received':True,'authoritative_result':True,'provider_envelope_sha256':eh,'provider_content_sha256':ch,'provider_reported_model':rep,'canonical_model_family':can,'normalized_output_sha256':csha(ds),'checkpoint_sha256':cph,'decision_count':len(ds)},attempts(r));all_ds+=ds;case_rs.append(cp['case_result']);reported.add(rep);families.add(can);print(f"Reviewer {r.upper()} {len(case_rs)}/{p['case_count']} {case['case_id']}: {len(ds)} decisions",flush=True)
 if len(case_rs)!=p['case_count'] or len(all_ds)!=p['claim_count']:raise ValueError('completed_accounting_mismatch')
 if families!={cfg['model']}:raise ValueError('canonical_model_family_drift:'+repr(families))
 ids=[x['reference_claim_id'] for c in p['cases'] for x in c['claims']]
 if [x['reference_claim_id'] for x in all_ds]!=ids:raise ValueError('global_claim_lineage_mismatch')
 cases=[];o=0
 for c in p['cases']:
  n=len(c['claims']);cases.append({'case_id':c['case_id'],'decisions':all_ds[o:o+n]});o+=n
 sub={**copy.deepcopy(load(template(r))),'submission_id':f'phase7.3.3-d-multi-claim-successor-support-reviewer-{r}-completed-submission-v2','status':'completed_independent_support_review','completed':True,'cases':cases,'execution_manifest_sha256':mh,'reviewer_model_requested':cfg['model'],'provider_reported_models':sorted(reported),'canonical_model_family':cfg['model'],'completed_case_count':len(case_rs),'support_decision_count':len(all_ds),'provider_called':True,'raw_provider_response_stored':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};subh=once(submission(r),sub);res={'schema_version':1,'execution_id':f'phase7.3.3-d-multi-claim-successor-support-reviewer-{r}-execution-result-v2','status':'completed','reviewer_id':r,'manifest_sha256':mh,'submission_sha256':subh,'model_requested':cfg['model'],'canonical_model_family':cfg['model'],'provider_reported_models':sorted(reported),'completed_case_count':len(case_rs),'decision_count':len(all_ds),'support_label_counts':dict(sorted(Counter(x['support_label'] for x in all_ds).items())),'confidence_counts':dict(sorted(Counter(x['annotation_confidence'] for x in all_ds).items())),'case_results':case_rs,'raw_provider_responses_stored':False,'agreement_computed':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False};resh=once(result(r),res);append_event({'event_type':'multi_claim_successor_support_review_completed','manifest_sha256':mh,'reviewer':r,'status':'completed','response_received':True,'authoritative_result':True,'completed_case_count':len(case_rs),'completed_decision_count':len(all_ds),'submission_sha256':subh,'execution_result_sha256':resh},attempts(r));return {'status':'PASS','reviewer':r,'completed_case_count':len(case_rs),'decision_count':len(all_ds),'support_label_counts':res['support_label_counts'],'submission_sha256':subh,'execution_result_sha256':resh,'next_action':'execute other reviewer or finalize'}
def verify_reviewer(r):
 entries=read_entries(attempts(r));term=terminal(r);z={'manifest':manifest(r).exists() and load(manifest(r))==expected_manifest(r),'log_nonempty':bool(entries),'terminal':term is not None}
 if term=='completed':
  p=load(packet(r));s=load(submission(r));res=load(result(r));cps=checkpoint_prefix(r,p,sha(manifest(r)));ds=[d for c in s.get('cases',[]) for d in c.get('decisions',[])];ids=[x['reference_claim_id'] for c in p['cases'] for x in c['claims']];z.update({'submission_completed':s.get('completed') is True,'cases_40':len(s.get('cases',[]))==40,'decisions_240':len(ds)==240,'ids_exact':[x.get('reference_claim_id') for x in ds]==ids,'result_completed':res.get('status')=='completed','result_hash':res.get('submission_sha256')==sha(submission(r)),'checkpoints_40':len(cps)==40 and len(list(case_dir(r).glob('*.json')))==40,'canonical':res.get('canonical_model_family')==REVIEWERS[r]['model'],'agreement_false':res.get('agreement_computed') is False,'gold_false':res.get('support_gold_created') is False,'confirmatory_false':res.get('confirmatory_dataset_opened') is False,'runtime_false':res.get('runtime_integration_authorized') is False})
 elif term=='authoritative_negative_result':
  n=load(negative(r));z.update({'negative':n.get('status')=='authoritative_negative_result','no_retry':n.get('same_version_retry_allowed') is False,'agreement_blocked':n.get('agreement_allowed') is False,'other_allowed':n.get('other_reviewer_execution_allowed') is True,'confirmatory_false':n.get('confirmatory_dataset_opened') is False,'runtime_false':n.get('runtime_integration_authorized') is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','reviewer':r,'terminal_outcome':term,'checks':len(z),'failed':f,'attempt_log_entry_count':len(entries),'attempt_log_tail_sha256':entries[-1]['entry_sha256'] if entries else None}
def finalize():
 ver={r:verify_reviewer(r) for r in REVIEWERS}
 if any(x['status']!='PASS' for x in ver.values()):raise ValueError('reviewer_verification_failed')
 terms={r:terminal(r) for r in REVIEWERS};both=all(x=='completed' for x in terms.values());nxt=NEXT_OK if both else NEXT_NEG;arts={}
 for r,x in terms.items():arts[r]={'terminal_outcome':x,'manifest_sha256':sha(manifest(r)),'attempt_log_tail_sha256':read_entries(attempts(r))[-1]['entry_sha256'],'submission_sha256':sha(submission(r)) if x=='completed' else None,'execution_result_sha256':sha(result(r)) if x=='completed' else None,'negative_result_sha256':sha(negative(r)) if x=='authoritative_negative_result' else None}
 report={'schema_version':1,'report_id':'phase7.3.3-d-multi-claim-successor-support-review-execution-report-v2','status':'PASS' if both else 'AUTHORITATIVE_NEGATIVE_RESULT','both_reviewers_completed':both,'agreement_authorized':both,'reviewer_outcomes':terms,'reviewer_artifacts':arts,'case_count_per_completed_reviewer':40,'claim_count_per_completed_reviewer':240,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':nxt};rh=once(JOINT_REPORT,report);out={'schema_version':1,'outcome_id':'phase7.3.3-d-multi-claim-successor-support-review-execution-outcome-v2','status':report['status'],'execution_report_sha256':rh,'both_reviewers_completed':both,'agreement_authorized':both,'support_reference_candidate_created':False,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':nxt};oh=once(JOINT_OUTCOME,out)
 s=copy.deepcopy(load(STATE));rd=copy.deepcopy(load(READY));line={'multi_claim_successor_support_review_protocol_v2_sha256':sha(PROTOCOL),'multi_claim_successor_support_review_schema_v2_sha256':sha(SCHEMA),'multi_claim_successor_support_reviewer_prompt_v2_sha256':sha(PROMPT),'multi_claim_successor_support_review_execution_policy_v2_sha256':sha(POLICY),'multi_claim_successor_support_review_contract_fixtures_v2_sha256':sha(FIXTURES),'multi_claim_successor_support_reviewer_a_manifest_v2_sha256':sha(manifest('a')),'multi_claim_successor_support_reviewer_b_manifest_v2_sha256':sha(manifest('b')),'multi_claim_successor_support_review_execution_report_v2_sha256':rh,'multi_claim_successor_support_review_execution_outcome_v2_sha256':oh}
 for r,a in arts.items():
  for k,v in a.items():
   if k!='terminal_outcome' and v is not None:line[f'multi_claim_successor_support_reviewer_{r}_{k}']=v
 u={'status':'multi_claim_successor_independent_support_review_completed_agreement_authorized' if both else 'multi_claim_successor_support_review_authoritative_negative_agreement_blocked','next_authorized_stage':nxt,'multi_claim_successor_support_review_started':True,'multi_claim_successor_support_reviewer_a_completed':terms['a']=='completed','multi_claim_successor_support_reviewer_b_completed':terms['b']=='completed','multi_claim_successor_support_reviewer_a_terminal_outcome':terms['a'],'multi_claim_successor_support_reviewer_b_terminal_outcome':terms['b'],'multi_claim_successor_support_agreement_authorized':both,'multi_claim_successor_support_agreement_completed':False,'multi_claim_successor_support_gold_created':False,'confirmatory_opening_authorized':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,rd]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':54,'state_id':'phase7.3.3-d-support-stage-state-v54'});rd.update({'schema_version':65,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v65'});sh=once(STATE_OUT,s);rdh=once(READY_OUT,rd);rec={'schema_version':1,'receipt_id':'phase7.3.3-d-multi-claim-successor-support-review-execution-receipt-v2','status':report['status'],'protocol_sha256':sha(PROTOCOL),'schema_sha256':sha(SCHEMA),'prompt_sha256':sha(PROMPT),'execution_policy_sha256':sha(POLICY),'fixtures_sha256':sha(FIXTURES),'reviewer_a_manifest_sha256':sha(manifest('a')),'reviewer_b_manifest_sha256':sha(manifest('b')),'execution_report_sha256':rh,'execution_outcome_sha256':oh,'state_sha256':sh,'readiness_sha256':rdh,'both_reviewers_completed':both,'agreement_authorized':both,'support_gold_created':False,'confirmatory_dataset_opened':False,'runtime_integration_authorized':False,'next_authorized_stage':nxt};return {'status':report['status'],'reviewer_outcomes':terms,'both_reviewers_completed':both,'agreement_authorized':both,'execution_report_sha256':rh,'execution_outcome_sha256':oh,'receipt_sha256':once(JOINT_RECEIPT,rec),'state_sha256':sh,'readiness_sha256':rdh,'next_authorized_stage':nxt}
def verify_final():
 ps=[JOINT_REPORT,JOINT_OUTCOME,JOINT_RECEIPT,STATE_OUT,READY_OUT];z={'exists:'+rel(p):p.exists() for p in ps}
 if all(z.values()):
  report=load(JOINT_REPORT);out=load(JOINT_OUTCOME);rec=load(JOINT_RECEIPT);s=load(STATE_OUT);rd=load(READY_OUT);both=report.get('both_reviewers_completed') is True;nxt=NEXT_OK if both else NEXT_NEG;z.update({'report_outcome':out.get('execution_report_sha256')==sha(JOINT_REPORT),'receipt_report':rec.get('execution_report_sha256')==sha(JOINT_REPORT),'receipt_outcome':rec.get('execution_outcome_sha256')==sha(JOINT_OUTCOME),'receipt_state':rec.get('state_sha256')==sha(STATE_OUT),'receipt_ready':rec.get('readiness_sha256')==sha(READY_OUT),'state_v54':s.get('schema_version')==54,'ready_v65':rd.get('schema_version')==65,'state_gate':s.get('next_authorized_stage')==nxt,'ready_gate':rd.get('next_authorized_stage')==nxt,'agreement_consistent':report.get('agreement_authorized') is both and out.get('agreement_authorized') is both,'gold_absent':s.get('multi_claim_successor_support_gold_created') is False and rd.get('multi_claim_successor_support_gold_created') is False,'confirmatory_closed':s.get('confirmatory_dataset_opened') is False and rd.get('confirmatory_dataset_opened') is False,'runtime_off':s.get('runtime_integration_authorized') is False and rd.get('runtime_integration_authorized') is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'next_authorized_stage':load(STATE_OUT).get('next_authorized_stage') if STATE_OUT.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--preflight',action='store_true');g.add_argument('--fixtures',action='store_true');g.add_argument('--prepare',action='store_true');g.add_argument('--verify-prepare',action='store_true');g.add_argument('--reviewer',choices=sorted(REVIEWERS));g.add_argument('--verify-reviewer',choices=sorted(REVIEWERS));g.add_argument('--finalize',action='store_true');g.add_argument('--verify-final',action='store_true');a=p.parse_args()
 if a.preflight:x=preflight()
 elif a.fixtures:x=fixture_doc();x['status']='PASS' if x['all_fixtures_passed'] else 'FAIL'
 elif a.prepare:x=prepare()
 elif a.verify_prepare:x=verify_prepare()
 elif a.reviewer:x=execute(a.reviewer)
 elif a.verify_reviewer:x=verify_reviewer(a.verify_reviewer)
 elif a.finalize:x=finalize()
 else:x=verify_final()
 print(json.dumps(x,ensure_ascii=False,indent=2));return 0 if x.get('status') in {'PASS','AUTHORITATIVE_NEGATIVE_RESULT','TRANSPORT_FAILURE_RESUMABLE'} else 1
if __name__=='__main__':raise SystemExit(main())


