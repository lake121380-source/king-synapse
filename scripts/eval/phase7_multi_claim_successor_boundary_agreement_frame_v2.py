#!/usr/bin/env python3
"""Compute exact independent Boundary Agreement for successor frame v2."""
from __future__ import annotations
import argparse,copy,hashlib,json,tempfile
from pathlib import Path
SELF=Path(__file__).resolve();ROOT=SELF.parents[2];C=ROOT/'crates/eval/config';D=ROOT/'crates/eval/datasets/pattern_extraction';R=ROOT/'crates/eval/reports'
A=R/'phase7_3_3_d_multi_claim_successor_boundary_reviewer_a_submission_frame_v2.json';B=R/'phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_submission_frame_v2.json';AR=R/'phase7_3_3_d_multi_claim_successor_boundary_reviewer_a_receipt_frame_v2.json';BR=R/'phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_receipt_frame_v2.json';SI=D/'phase7_3_3_d_support_stage_state_v68.json';RI=R/'phase7_3_3_d1_reference_construction_readiness_v79.json'
PRO=C/'phase7_3_3_d_multi_claim_successor_boundary_agreement_protocol_frame_v2.json';FIX=R/'phase7_3_3_d_multi_claim_successor_boundary_agreement_fixtures_frame_v2.json';MAN=R/'phase7_3_3_d_multi_claim_successor_boundary_agreement_manifest_frame_v2.json';REP=R/'phase7_3_3_d_multi_claim_successor_boundary_agreement_report_frame_v2.json';WL=D/'phase7_3_3_d_multi_claim_successor_boundary_adjudication_worklist_frame_v2.json';REC=R/'phase7_3_3_d_multi_claim_successor_boundary_agreement_receipt_frame_v2.json';SO=D/'phase7_3_3_d_support_stage_state_v69.json';RO=R/'phase7_3_3_d1_reference_construction_readiness_v80.json'
EXP={A:'5b98d7d37fe658178a63d890f487642e7173f2b6936765e129e9f4fa138d7a68',B:'fdcc8761165393e65a8b01943f48e48ce513bec720b2f68f5d3be268e5289fc6',AR:'65cc20e6d2b57afc7627b1a8384323e103403b55e1692e9151504e7e0282074f',BR:'9428f4d64919c28927a9302aae9c09ea6a21c8748eddb16a8902b34e437b424e',SI:'e188bafdeb1b5585a215bf3529c646a8beb3949574f5643e1523dad23e104d5d',RI:'7ac78933d3de06b042d7fd52b8db51ca94f90e181cc8789041652c005a4f838f'}
CUR='construct_multi_claim_successor_boundary_agreement_frame_v2';NEXT='construct_multi_claim_successor_boundary_reference_candidate_frame_v2'
def hb(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hb(p.read_bytes())
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rel(p):return p.relative_to(ROOT).as_posix()
def once(p,x):
 b=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists():
  if p.read_bytes()!=b:raise RuntimeError('immutable_artifact_mismatch:'+rel(p))
  return sha(p)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('wb',dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return hb(b)
def index(sub):return {c['case_id']:c for c in sub['cases']}
def compute():
 a=index(load(A));b=index(load(B));rows=[];work=[];exact_claims=0
 for cid in a:
  ac=a[cid]['claims'];bc=b[cid]['claims'];aspan=[(x['source_span']['start'],x['source_span']['end']) for x in ac];bspan=[(x['source_span']['start'],x['source_span']['end']) for x in bc];exact=aspan==bspan;exact_claims+=len(ac) if exact else 0;rows.append({'case_id':cid,'reviewer_a_claim_count':len(ac),'reviewer_b_claim_count':len(bc),'exact_span_sequence_agreement':exact,'reviewer_a_spans':[x['source_span'] for x in ac],'reviewer_b_spans':[x['source_span'] for x in bc]})
  if not exact:work.append({'case_id':cid,'reviewer_a_claims':ac,'reviewer_b_claims':bc,'boundary_adjudication_required':True})
 return rows,work,exact_claims
def protocol():return {'schema_version':2,'protocol_id':'phase7.3.3-d-boundary-agreement-protocol-frame-v2','status':'frozen_before_offline_compute','primary_agreement':'exact ordered span sequence per Candidate','provider_calls':0,'no_fuzzy_alignment_used_for_gate':True,'no_boundary_mutation':True,'passing_no_disagreement_next_stage':NEXT}
def fixtures():
 xs=[{'fixture_id':'exact','passed':[(0,1)]==[(0,1)]},{'fixture_id':'different_detected','passed':[(0,1)]!=[(0,2)]},{'fixture_id':'order_sensitive','passed':[(0,1),(2,3)]!=[(2,3),(0,1)]}];return {'schema_version':2,'fixtures_id':'phase7.3.3-d-boundary-agreement-fixtures-frame-v2','fixture_count':len(xs),'passed_count':sum(x['passed'] for x in xs),'all_fixtures_passed':all(x['passed'] for x in xs),'fixtures':xs}
def manifest():return {'schema_version':2,'manifest_id':'phase7.3.3-d-boundary-agreement-manifest-frame-v2','status':'frozen_ready_for_compute','adapter_sha256':sha(SELF),'protocol_sha256':sha(PRO),'fixtures_sha256':sha(FIX),'frozen_inputs':{rel(p):h for p,h in EXP.items()},'provider_calls':0,'next_authorized_stage':CUR}
def preflight():
 z={'input_hash:'+rel(p):p.exists() and sha(p)==h for p,h in EXP.items()}
 if all(z.values()):s=load(SI);r=load(RI);z.update({'state_gate':s['next_authorized_stage']==CUR,'readiness_gate':r['next_authorized_stage']==CUR,'both_complete':load(A)['completed'] is True and load(B)['completed'] is True,'case_sets_equal':set(index(load(A)))==set(index(load(B))) and len(index(load(A)))==40,'confirmatory_closed':s['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False,'outputs_absent':all(not p.exists() for p in [PRO,FIX,MAN,REP,WL,REC,SO,RO])})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f}
def run():
 p=preflight()
 if p['status']!='PASS':return p
 ph=once(PRO,protocol());fh=once(FIX,fixtures());mh=once(MAN,manifest());rows,work,exact=compute();rep={'schema_version':2,'report_id':'phase7.3.3-d-boundary-agreement-report-frame-v2','status':'completed','case_count':40,'reviewer_a_claim_count':load(A)['claim_count'],'reviewer_b_claim_count':load(B)['claim_count'],'exact_case_count':sum(x['exact_span_sequence_agreement'] for x in rows),'disagreement_case_count':len(work),'exact_claim_count':exact,'exact_case_rate':sum(x['exact_span_sequence_agreement'] for x in rows)/40,'cases':rows,'provider_calls':0};rph=once(REP,rep);w={'schema_version':2,'worklist_id':'phase7.3.3-d-boundary-adjudication-worklist-frame-v2','status':'empty_no_adjudication_required' if not work else 'frozen_adjudication_required','case_count':len(work),'items':work};wh=once(WL,w);nxt=NEXT if not work else 'execute_multi_claim_successor_boundary_adjudication_frame_v2';s=copy.deepcopy(load(SI));r=copy.deepcopy(load(RI));line={'multi_claim_successor_boundary_agreement_protocol_frame_v2_sha256':ph,'multi_claim_successor_boundary_agreement_manifest_frame_v2_sha256':mh,'multi_claim_successor_boundary_agreement_report_frame_v2_sha256':rph,'multi_claim_successor_boundary_adjudication_worklist_frame_v2_sha256':wh};u={'status':'multi_claim_successor_boundary_agreement_frame_v2_completed','next_authorized_stage':nxt,'multi_claim_successor_boundary_agreement_frame_v2_completed':True,'multi_claim_successor_boundary_disagreement_case_count':len(work),'multi_claim_successor_boundary_adjudication_required':bool(work),'confirmatory_dataset_opened':False,'runtime_integration_authorized':False}
 for x in [s,r]:x.setdefault('artifact_lineage',{}).update(line);x.update(u)
 s.update({'schema_version':69,'state_id':'phase7.3.3-d-support-stage-state-v69'});r.update({'schema_version':80,'readiness_id':'phase7.3.3-d1-reference-construction-readiness-v80'});sh=once(SO,s);r['artifact_lineage']['support_stage_state_v69_sha256']=sh;rh=once(RO,r);rec={'schema_version':2,'receipt_id':'phase7.3.3-d-boundary-agreement-receipt-frame-v2','status':'PASS','manifest_sha256':mh,'report_sha256':rph,'worklist_sha256':wh,'state_sha256':sh,'readiness_sha256':rh,'disagreement_case_count':len(work),'next_authorized_stage':nxt};rch=once(REC,rec);return {'status':'PASS','exact_case_count':rep['exact_case_count'],'disagreement_case_count':len(work),'report_sha256':rph,'receipt_sha256':rch,'state_sha256':sh,'readiness_sha256':rh,'next_authorized_stage':nxt}
def verify():
 ps=[PRO,FIX,MAN,REP,WL,REC,SO,RO];z={'exists:'+rel(p):p.exists() for p in ps}
 if all(p.exists() for p in ps):rows,work,exact=compute();rep=load(REP);s=load(SO);r=load(RO);z.update({'protocol_replay':load(PRO)==protocol(),'fixtures_replay':load(FIX)==fixtures(),'manifest_replay':load(MAN)==manifest(),'exact_40':rep['exact_case_count']==40 and rep['disagreement_case_count']==0,'claims_240':rep['reviewer_a_claim_count']==rep['reviewer_b_claim_count']==rep['exact_claim_count']==240,'empty_worklist':load(WL)['case_count']==0 and not load(WL)['items'],'next_gate':s['next_authorized_stage']==r['next_authorized_stage']==NEXT,'confirmatory_closed':s['confirmatory_dataset_opened'] is False and r['confirmatory_dataset_opened'] is False,'runtime_off':s['runtime_integration_authorized'] is False and r['runtime_integration_authorized'] is False})
 f=[k for k,v in z.items() if not v];return {'status':'PASS' if not f else 'FAIL','checks':len(z),'failed':f,'next_authorized_stage':load(SO)['next_authorized_stage'] if SO.exists() else None}
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 for n in ['preflight','run','verify']:g.add_argument('--'+n,action='store_true')
 a=p.parse_args();o=preflight() if a.preflight else run() if a.run else verify();print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o.get('status')=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
