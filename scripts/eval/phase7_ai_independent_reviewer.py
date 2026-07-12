#!/usr/bin/env python3
"""Execute one blind AI reviewer for Phase 7.3.1.

The adapter reads only the frozen blind packet, reviewer guide, and canonical AI
reviewer prompt. It performs ten isolated design-case calls, never reads held-out
or judge artifacts, never stores credentials/raw provider responses, and applies
only exact unique-excerpt to Unicode half-open span normalization.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, urllib.request, urllib.error
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'crates/eval/datasets/pattern_extraction/phase7_3_1_blind_review_packet.json'
GUIDE=ROOT/'docs/eval/PHASE7_3_1_REVIEWER_GUIDE.md'
PROMPT=ROOT/'crates/eval/config/phase7_3_1_ai_reviewer_prompt_v1.md'
BASE_URL='https://api.gpt.ge/v1'

TOP={'claims'}
CLAIM={'anchor_id','source_excerpt','claim_text','claim_origin','claimed_evidence_ids','human_support_label','dimension_labels','failure_kinds','reviewer_rationale','annotation_confidence'}
DIMS={'scope','causal_strength','prediction_support','counterexample_handling','falsifiability'}
ORIGINS={'explicit','inferred','synthesized'}
SUPPORT={'supported','partially_supported','unsupported','not_assessable'}
SCOPE={'preserved','expanded','not_assessable'}
CAUSAL={'supported','overstated','not_present','not_assessable'}
PRED={'supported','partially_supported','unsupported','not_present','not_assessable'}
COUNTER={'preserved','ignored','not_present','not_assessable'}
FALS={'direct_in_scope','structural_only','invalid','not_assessable'}
CONF={'low','medium','high'}
FAIL={'unsupported_generalization','scope_expansion','missing_evidence','weak_evidence','prediction_without_support','causal_leap','over_abstraction','counterexample_ignored','ambiguous_pattern','duplicate_pattern','other'}

def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def split_prompt(text:str)->tuple[str,str]:
    sm='## System message\n'; um='## User message template\n'
    return text.split(sm,1)[1].split(um,1)[0].strip(), text.split(um,1)[1].strip()
def exact(obj:Any, keys:set[str], label:str):
    if not isinstance(obj,dict) or set(obj)!=keys: raise ValueError(f'{label}_fields_invalid')
def request(key:str, model:str, system:str, user:str)->dict[str,Any]:
    payload={'model':model,'temperature':0,'top_p':1,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]}
    req=urllib.request.Request(BASE_URL+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=300) as r: return json.loads(r.read().decode('utf-8'))
def normalize_case(case:dict[str,Any], raw_obj:dict[str,Any], prefix:str, start_index:int)->tuple[list[dict[str,Any]],int]:
    exact(raw_obj,TOP,'response'); raw_claims=raw_obj['claims']
    if not isinstance(raw_claims,list) or not raw_claims: raise ValueError('claims_required')
    anchors={a['anchor_id']:a for a in case['claim_source_anchors']}; seen=set(); out=[]; idx=start_index
    valid_evidence={x['memory_id'] for x in case['evidence_input']['experiences']}
    for c in raw_claims:
        exact(c,CLAIM,'claim'); exact(c['dimension_labels'],DIMS,'dimension_labels')
        aid=c['anchor_id']; excerpt=c['source_excerpt']
        if aid not in anchors: raise ValueError(f'unknown_anchor:{aid}')
        text=anchors[aid]['source_text']
        if not isinstance(excerpt,str) or not excerpt: raise ValueError(f'empty_excerpt:{aid}')
        if text.count(excerpt)!=1: raise ValueError(f'excerpt_not_unique:{aid}:{excerpt[:60]}')
        start=text.index(excerpt); end=start+len(excerpt)
        if c['claim_origin'] not in ORIGINS or c['human_support_label'] not in SUPPORT or c['annotation_confidence'] not in CONF: raise ValueError(f'enum_invalid:{aid}')
        d=c['dimension_labels']
        if d['scope'] not in SCOPE or d['causal_strength'] not in CAUSAL or d['prediction_support'] not in PRED or d['counterexample_handling'] not in COUNTER or d['falsifiability'] not in FALS: raise ValueError(f'dimension_enum_invalid:{aid}')
        if not isinstance(c['claimed_evidence_ids'],list) or any(x not in valid_evidence for x in c['claimed_evidence_ids']): raise ValueError(f'evidence_id_invalid:{aid}')
        if not isinstance(c['failure_kinds'],list) or any(x not in FAIL for x in c['failure_kinds']): raise ValueError(f'failure_kind_invalid:{aid}')
        if not str(c['claim_text']).strip() or not str(c['reviewer_rationale']).strip(): raise ValueError(f'text_required:{aid}')
        idx+=1; seen.add(aid)
        out.append({'claim_id':f'{prefix}-claim-{idx:03d}','case_id':case['case_id'],'response_sha256':case['response_sha256'],'anchor_id':aid,'source_span':{'start_char':start,'end_char':end,'source_excerpt':excerpt},'claim_text':c['claim_text'],'claim_origin':c['claim_origin'],'claimed_evidence_ids':c['claimed_evidence_ids'],'human_support_label':c['human_support_label'],'dimension_labels':d,'failure_kinds':c['failure_kinds'],'reviewer_rationale':c['reviewer_rationale'],'annotation_confidence':c['annotation_confidence']})
    missing=set(anchors)-seen
    if missing: raise ValueError('anchors_without_claims:'+','.join(sorted(missing)))
    return out,idx

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--reviewer',choices=['a','b'],required=True); ap.add_argument('--model',required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--manifest',type=Path,required=True); args=ap.parse_args()
    key=os.environ.get('PHASE7_REVIEW_API_KEY','').strip()
    if not key: print('PHASE7_REVIEW_API_KEY is required',file=sys.stderr); return 2
    packet=json.loads(PACKET.read_text(encoding='utf-8')); system,user_t=split_prompt(PROMPT.read_text(encoding='utf-8-sig'))
    claims=[]; idx=0; resolved=None; per_case=[]
    for case in packet['cases']:
        user=user_t.replace('{{CASE_JSON}}',json.dumps(case,ensure_ascii=False,indent=2))
        try:
            response=request(key,args.model,system,user); resolved=response.get('model',resolved); raw=response['choices'][0]['message']['content']; obj=json.loads(raw)
            normalized,idx=normalize_case(case,obj,f'reviewer-{args.reviewer}',idx); claims.extend(normalized); per_case.append({'case_id':case['case_id'],'status':'completed','claim_count':len(normalized)})
            print(f"{args.reviewer.upper()} {case['case_id']}: {len(normalized)} claims",flush=True)
        except Exception as e:
            print(f"{args.reviewer.upper()} {case['case_id']}: blocked: {type(e).__name__}: {e}",file=sys.stderr); return 3
    submission={'schema_version':1,'submission_id':f'phase7.3.1-ai-reviewer-{args.reviewer}-v1','reviewer_id':f'ai_reviewer_{args.reviewer}_{args.model}','reviewer_role':'independent_semantic_reviewer','source_execution_id':packet['source_execution_id'],'protocol_id':packet['protocol_id'],'completed':True,'blind_to_other_reviewer':True,'blind_to_frozen_judge':True,'blind_to_phase7_3_aggregates':True,'held_out_accessed':False,'claims':claims}
    manifest={'schema_version':1,'reviewer_id':submission['reviewer_id'],'reviewer_type':'ai_model','provider':'api.gpt.ge','model_requested':args.model,'resolved_model':resolved,'temperature':0,'top_p':1,'response_format':{'type':'json_object'},'adapter_sha256':sha(Path(__file__)),'prompt_sha256':sha(PROMPT),'review_packet_sha256':sha(PACKET),'reviewer_guide_sha256':sha(GUIDE),'span_normalization':'exact_unique_excerpt_to_unicode_scalar_half_open','case_isolation':True,'other_reviewer_visible':False,'frozen_judge_visible':False,'phase7_3_aggregates_visible':False,'external_tools_enabled':False,'web_access_enabled':False,'memory_enabled':False,'held_out_accessed':False,'raw_provider_responses_stored':False,'case_results':per_case,'claim_count':len(claims)}
    args.output.write_text(json.dumps(submission,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'completed reviewer {args.reviewer}: {len(claims)} claims; resolved_model={resolved}')
    return 0
if __name__=='__main__': raise SystemExit(main())
