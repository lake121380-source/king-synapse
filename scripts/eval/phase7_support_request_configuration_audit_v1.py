#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'crates/eval/config'
REPORTS=ROOT/'crates/eval/reports'
POLICY=CONFIG/'phase7_3_3_d_support_review_execution_policy_v1.json'
MANIFEST_A=REPORTS/'phase7_3_3_d_support_reviewer_a_execution_manifest_v1.json'
MANIFEST_B=REPORTS/'phase7_3_3_d_support_reviewer_b_execution_manifest_v1.json'
NEG_A=REPORTS/'phase7_3_3_d_support_reviewer_a_negative_result_v1.json'
NEG_B=REPORTS/'phase7_3_3_d_support_reviewer_b_negative_result_v1.json'
OUTCOME=REPORTS/'phase7_3_3_d_support_review_execution_outcome_v1.json'
HIST_A_MANIFEST=REPORTS/'phase7_3_3_d_boundary_reviewer_a_execution_manifest_v3.json'
HIST_A_SUBMISSION=REPORTS/'phase7_3_3_d_boundary_reviewer_a_submission_v3.json'
HIST_Q_MANIFEST=REPORTS/'phase7_3_3_d_non_claim_accounting_reviewer_q_execution_manifest_v1.json'
HIST_Q_SUBMISSION=REPORTS/'phase7_3_3_d_non_claim_accounting_reviewer_q_submission_v1.json'
AUDIT=REPORTS/'phase7_3_3_d_support_request_configuration_audit_v1.json'

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path):return json.loads(p.read_text(encoding='utf-8-sig'))
def write_once(p:Path,v):
 b=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f'immutable_artifact_exists_with_different_content:{p.relative_to(ROOT)}')
  return
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as h:h.write(b);t=Path(h.name)
 t.replace(p)

def user_env_present(name:str)->bool:
 # Never read or persist a value through this audit on non-Windows hosts.
 if os.name!='nt':return False
 import winreg
 try:
  with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as key:
   value,_=winreg.QueryValueEx(key,name)
   return isinstance(value,str) and bool(value.strip())
 except FileNotFoundError:return False

req=[POLICY,MANIFEST_A,MANIFEST_B,NEG_A,NEG_B,OUTCOME,HIST_A_MANIFEST,HIST_A_SUBMISSION,HIST_Q_MANIFEST,HIST_Q_SUBMISSION]
missing=[str(p.relative_to(ROOT)) for p in req if not p.exists()]
if missing:raise ValueError(f'missing_artifacts:{missing}')
policy=load(POLICY);ma=load(MANIFEST_A);mb=load(MANIFEST_B);na=load(NEG_A);nb=load(NEG_B);out=load(OUTCOME);ha=load(HIST_A_MANIFEST);hq=load(HIST_Q_MANIFEST)
checks={
 'v1_policy_used_deepseek_key':policy.get('credential_env_name')=='DEEPSEEK_API_KEY',
 'v1_manifest_a_used_deepseek_key':ma.get('credential_env_name')=='DEEPSEEK_API_KEY',
 'v1_manifest_b_used_deepseek_key':mb.get('credential_env_name')=='DEEPSEEK_API_KEY',
 'v1_gateway_was_api_gpt_ge':ma.get('provider_base_url')=='https://api.gpt.ge/v1' and mb.get('provider_base_url')=='https://api.gpt.ge/v1',
 'v1_failed_before_provider_content':na.get('failure_code')=='HTTP Error 401: Unauthorized' and nb.get('failure_code')=='HTTP Error 401: Unauthorized' and na.get('response_received') is False and nb.get('response_received') is False,
 'v1_no_support_capability_conclusion':na.get('support_capability_conclusion_authorized') is False and nb.get('support_capability_conclusion_authorized') is False,
 'historical_gpt41_gateway_route_used_phase7_key':ha.get('provider_base_url')=='https://api.gpt.ge/v1' and ha.get('model_requested')=='gpt-4.1' and ha.get('credential_env_name')=='PHASE7_ATOMIC_JUDGE_API_KEY' and load(HIST_A_SUBMISSION).get('completed') is True,
 'historical_qwen_gateway_route_used_phase7_key':hq.get('provider_base_url')=='https://api.gpt.ge/v1' and hq.get('model_requested')=='qwen3.5-plus' and hq.get('credential_env_name')=='PHASE7_ATOMIC_JUDGE_API_KEY' and load(HIST_Q_SUBMISSION).get('status')=='completed_independent_gap_review',
 'phase7_key_present_in_windows_user_environment':user_env_present('PHASE7_ATOMIC_JUDGE_API_KEY'),
 'v1_outcome_preserved':out.get('status')=='completed_with_two_authoritative_transport_negative_results',
}
if not all(checks.values()):raise ValueError(f'audit_checks_failed:{[k for k,v in checks.items() if not v]}')
audit={
 'schema_version':1,
 'audit_id':'phase7.3.3-d1-b-support-request-configuration-audit-v1',
 'status':'confirmed_adapter_credential_routing_defect',
 'scope':'Support Review execution v1 request configuration only',
 'v1_artifacts_preserved':True,
 'finding':{
  'incorrect_v1_credential_env_name':'DEEPSEEK_API_KEY',
  'verified_gateway_credential_env_name':'PHASE7_ATOMIC_JUDGE_API_KEY',
  'provider_base_url':'https://api.gpt.ge/v1',
  'request_error':'credential intended for a different provider route was sent to the frozen api.gpt.ge gateway route',
  'provider_access_unavailable_conclusion_authorized':False,
  'support_capability_conclusion_authorized':False,
  'failure_attribution':'adapter_credential_routing',
  'failure_level':'level_0_transport',
 },
 'evidence_checks':checks,
 'lineage':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in req},
 'secret_values_read_into_artifact':False,
 'secret_values_persisted':False,
 'authorized_remediation':{
  'new_execution_version':'v2',
  'same_version_retry':False,
  'only_request_semantic_change':'credential_env_name',
  'from':'DEEPSEEK_API_KEY',
  'to':'PHASE7_ATOMIC_JUDGE_API_KEY',
  'boundary_gold_changed':False,
  'support_packets_changed':False,
  'prompt_changed':False,
  'reviewer_models_changed':False,
  'support_contract_changed':False,
 }
}
write_once(AUDIT,audit)
print(json.dumps({'status':audit['status'],'audit_sha256':sha(AUDIT),'checks_passed':sum(checks.values()),'check_count':len(checks),'secret_values_persisted':False},indent=2))

