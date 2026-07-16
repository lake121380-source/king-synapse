#!/usr/bin/env python3
"""Build the frozen Boundary adjudication worklist from A/E blind submissions."""
import argparse, hashlib, json
from collections import defaultdict, deque
from pathlib import Path

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def overlap(a,b): return min(a['end'],b['end'])>max(a['start'],b['start'])
def public_claim(c):
    return {k:c[k] for k in ('reviewer_claim_id','source_span','claim_text','claim_type','material','claim_origin','boundary_rationale','annotation_confidence')}
def components(ac,ec):
    nodes={('a',c['reviewer_claim_id']):c for c in ac}|{('e',c['reviewer_claim_id']):c for c in ec}
    adj={k:set() for k in nodes}
    for ak,a in [(k,c) for k,c in nodes.items() if k[0]=='a']:
        for ek,e in [(k,c) for k,c in nodes.items() if k[0]=='e']:
            if overlap(a['source_span'],e['source_span']): adj[ak].add(ek); adj[ek].add(ak)
    out=[]; seen=set()
    for start in sorted(nodes):
        if start in seen: continue
        q=deque([start]); seen.add(start); comp=[]
        while q:
            n=q.popleft(); comp.append(n)
            for nxt in sorted(adj[n]):
                if nxt not in seen: seen.add(nxt); q.append(nxt)
        aa=[nodes[n] for n in comp if n[0]=='a']; ee=[nodes[n] for n in comp if n[0]=='e']
        aa.sort(key=lambda c:(c['source_span']['start'],c['source_span']['end'],c['reviewer_claim_id']))
        ee.sort(key=lambda c:(c['source_span']['start'],c['source_span']['end'],c['reviewer_claim_id']))
        aset={(c['source_span']['start'],c['source_span']['end']) for c in aa}; eset={(c['source_span']['start'],c['source_span']['end']) for c in ee}
        if len(aa)==1 and len(ee)==1 and aset==eset: relation='exact_one_to_one'
        elif len(aa)==1 and len(ee)==1: relation='boundary_shift_one_to_one'
        elif len(aa)==1 and len(ee)>1: relation='a_one_to_many_e'
        elif len(aa)>1 and len(ee)==1: relation='e_one_to_many_a'
        elif aa and ee: relation='many_to_many'
        elif aa: relation='a_only'
        else: relation='e_only'
        spans=[c['source_span'] for c in aa+ee]
        out.append({'relation':relation,'range':{'start':min(s['start'] for s in spans),'end':max(s['end'] for s in spans)},
                    'reviewer_a_claim_ids':[c['reviewer_claim_id'] for c in aa],
                    'reviewer_e_claim_ids':[c['reviewer_claim_id'] for c in ee],
                    'span_sets_equal':aset==eset,'claim_type_sets_equal':sorted(c['claim_type'] for c in aa)==sorted(c['claim_type'] for c in ee)})
    out.sort(key=lambda c:(c['range']['start'],c['range']['end'],c['relation']))
    for i,c in enumerate(out,1): c['component_index']=i
    return out

def build(protocol,packet,a,e):
    by_a=defaultdict(list); by_e=defaultdict(list)
    for c in a['claims']: by_a[(c['case_id'],c['anchor_id'])].append(c)
    for c in e['claims']: by_e[(c['case_id'],c['anchor_id'])].append(c)
    cases=[]; relation_counts=defaultdict(int)
    for case in packet['cases']:
        anchors=[]
        for anchor in case['source_anchors']:
            key=(case['case_id'],anchor['anchor_id']); ac=sorted(by_a[key],key=lambda c:(c['source_span']['start'],c['source_span']['end'],c['reviewer_claim_id'])); ec=sorted(by_e[key],key=lambda c:(c['source_span']['start'],c['source_span']['end'],c['reviewer_claim_id']))
            comps=components(ac,ec)
            for x in comps: relation_counts[x['relation']]+=1
            anchors.append({'anchor_id':anchor['anchor_id'],'source_field':anchor['source_field'],'source_index':anchor['source_index'],
                'source_text':anchor['source_text'],'source_text_sha256':anchor['source_text_sha256'],
                'reviewer_a_claims':[public_claim(c) for c in ac],'reviewer_e_claims':[public_claim(c) for c in ec],
                'component_diagnostics':comps})
        cases.append({'case_id':case['case_id'],'response_sha256':case['response_sha256'],'source_anchors':anchors})
    return {'schema_version':3,'worklist_id':'phase7.3.3-d1-a-boundary-adjudication-worklist-a-e-v3','status':'frozen_ready_for_adjudication',
      'protocol_id':protocol['protocol_id'],'artifact_lineage':protocol['artifact_lineage'],'case_count':len(cases),
      'reviewer_a_claim_count':len(a['claims']),'reviewer_e_claim_count':len(e['claims']),
      'component_relation_counts':dict(sorted(relation_counts.items())),'cases':cases,
      'support_labels_included':False,'candidate_gold_or_silver_included':False,'evidence_bundle_included':False,'held_out_accessed':False}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--protocol',type=Path,required=True); ap.add_argument('--packet',type=Path,required=True); ap.add_argument('--reviewer-a',type=Path,required=True); ap.add_argument('--reviewer-e',type=Path,required=True); ap.add_argument('--agreement',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--verify',action='store_true'); x=ap.parse_args()
    p=load(x.protocol); assert p['status']=='frozen_before_adjudication'; lin=p['artifact_lineage']
    assert lin['boundary_packet_sha256']==sha(x.packet) and lin['reviewer_a_submission_sha256']==sha(x.reviewer_a) and lin['reviewer_e_submission_sha256']==sha(x.reviewer_e) and lin['agreement_report_sha256']==sha(x.agreement) and lin['worklist_script_sha256']==sha(Path(__file__))
    result=build(p,load(x.packet),load(x.reviewer_a),load(x.reviewer_e))
    if x.verify:
        assert load(x.output)==result; print(f'worklist verified: {x.output} sha256={sha(x.output)}'); return
    if x.output.exists(): raise SystemExit(f'refusing to overwrite frozen worklist: {x.output}')
    x.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n'); print(f'worklist written: {x.output}\nsha256={sha(x.output)}')
if __name__=='__main__': main()