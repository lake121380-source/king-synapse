#!/usr/bin/env python3
"""Deterministic frozen Boundary Agreement for Phase 7.3.3-D Reviewer A/E."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math
from collections import Counter, defaultdict
from pathlib import Path


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def iou(x,y):
    inter=max(0,min(x["end"],y["end"])-max(x["start"],y["start"]))
    union=max(x["end"],y["end"])-min(x["start"],y["start"])
    return inter/union if union else 0.0
def overlaps(x,y): return min(x["end"],y["end"])>max(x["start"],y["start"])
def avg(v): return sum(v)/len(v) if v else None


def pearson(xs,ys):
    if len(xs)<2: return {"defined":False,"value":None,"reason":"insufficient_pairs"}
    mx,my=sum(xs)/len(xs),sum(ys)/len(ys)
    dx,dy=[x-mx for x in xs],[y-my for y in ys]
    den=math.sqrt(sum(x*x for x in dx)*sum(y*y for y in dy))
    return ({"defined":True,"value":sum(x*y for x,y in zip(dx,dy))/den,"reason":None}
            if den else {"defined":False,"value":None,"reason":"zero_variance"})


def category(pairs,field):
    n=len(pairs)
    if not n:
        return {"field":field,"matched_pair_count":0,"agreement_count":0,"raw_agreement":None,
                "cohen_kappa":{"defined":False,"value":None,"reason":"no_matched_pairs"},"confusion":[]}
    av=[a[field] for a,_,_ in pairs]; ev=[e[field] for _,e,_ in pairs]
    agree=sum(a==e for a,e in zip(av,ev)); ca,ce=Counter(av),Counter(ev)
    cats=set(ca)|set(ce); po=agree/n; pe=sum(ca[c]/n*ce[c]/n for c in cats)
    k=({"defined":False,"value":None,"reason":"degenerate_marginals"} if math.isclose(pe,1.0)
       else {"defined":True,"value":(po-pe)/(1-pe),"reason":None})
    cm=Counter(zip(av,ev))
    return {"field":field,"matched_pair_count":n,"agreement_count":agree,"raw_agreement":po,"cohen_kappa":k,
            "confusion":[{"reviewer_a":a,"reviewer_e":e,"count":cm[(a,e)]}
                         for a,e in sorted(cm,key=lambda x:(str(x[0]),str(x[1])))]}


def validate(s,protocol_id):
    assert s["schema_version"]==3 and s["protocol_id"]==protocol_id and s["completed"] is True
    assert s["blind_to_other_reviewer"] and s["blind_to_support_labels"] and s["blind_to_candidate_gold_or_silver"]
    assert s["held_out_accessed"] is False
    req={"reviewer_claim_id","case_id","anchor_id","source_span","claim_type","claim_role","anchor_group","material","claim_origin"}
    for c in s["claims"]:
        assert not req-set(c)
        assert 0<=c["source_span"]["start"]<c["source_span"]["end"]


def indexed(claims):
    out=defaultdict(list)
    for c in claims: out[(c["case_id"],c["anchor_id"])].append(c)
    for v in out.values(): v.sort(key=lambda c:(c["source_span"]["start"],c["source_span"]["end"],c["reviewer_claim_id"]))
    return out


def compute(p,a,e,recorded_at):
    ai,ei=indexed(a["claims"]),indexed(e["claims"]); groups=sorted(set(ai)|set(ei))
    threshold=float(p["alignment_policy"]["minimum_iou"])
    pairs=[]; ua_all=[]; ue_all=[]; split_ids=[]; merge_ids=[]
    pc=defaultdict(lambda:{"anchors":0,"a":0,"e":0,"pairs":[],"ua":[],"ue":[],"split":0,"merge":0})
    for case_id,anchor_id in groups:
        ac,ec=ai.get((case_id,anchor_id),[]),ei.get((case_id,anchor_id),[]); c=pc[case_id]
        c["anchors"]+=1; c["a"]+=len(ac); c["e"]+=len(ec)
        oa={x["reviewer_claim_id"]:[] for x in ac}; oe={x["reviewer_claim_id"]:[] for x in ec}; cand=[]
        for x in ac:
            for y in ec:
                if overlaps(x["source_span"],y["source_span"]):
                    oa[x["reviewer_claim_id"]].append(y["reviewer_claim_id"]); oe[y["reviewer_claim_id"]].append(x["reviewer_claim_id"])
                score=iou(x["source_span"],y["source_span"])
                if score>=threshold: cand.append((-score,x["reviewer_claim_id"],y["reviewer_claim_id"],x,y))
        ss=sorted(k for k,v in oa.items() if len(v)>=2); mm=sorted(k for k,v in oe.items() if len(v)>=2)
        split_ids+=ss; merge_ids+=mm; c["split"]+=len(ss); c["merge"]+=len(mm)
        ma=set(); me=set()
        for neg,aid,eid,x,y in sorted(cand):
            if aid in ma or eid in me: continue
            ma.add(aid); me.add(eid); pair=(x,y,-neg); pairs.append(pair); c["pairs"].append(pair)
        ua=[x for x in ac if x["reviewer_claim_id"] not in ma]; ue=[y for y in ec if y["reviewer_claim_id"] not in me]
        ua_all+=ua; ue_all+=ue; c["ua"] += [x["reviewer_claim_id"] for x in ua]; c["ue"] += [x["reviewer_claim_id"] for x in ue]
    an,en=len(a["claims"]),len(e["claims"]); mn=len(pairs); total=an+en
    exact=sum(x["source_span"]==y["source_span"] for x,y,_ in pairs); scores=[z for _,_,z in pairs]
    cases=sorted(pc); acount=[pc[x]["a"] for x in cases]; ecount=[pc[x]["e"] for x in cases]
    fields=["claim_type","material","claim_origin","claim_role","anchor_group"]
    per=[]
    for cid in cases:
        c=pc[cid]; cp=c["pairs"]; ex=sum(x["source_span"]==y["source_span"] for x,y,_ in cp)
        per.append({"case_id":cid,"anchor_count":c["anchors"],"reviewer_a_claim_count":c["a"],"reviewer_e_claim_count":c["e"],
          "absolute_claim_count_difference":abs(c["a"]-c["e"]),"matched_pair_count":len(cp),"exact_span_match_count":ex,
          "exact_boundary_agreement_rate_among_matched":ex/len(cp) if cp else None,"matched_span_mean_iou":avg([z for _,_,z in cp]),
          "unmatched_reviewer_a_count":len(c["ua"]),"unmatched_reviewer_e_count":len(c["ue"]),
          "a_one_to_many_e_count":c["split"],"e_one_to_many_a_count":c["merge"],
          "claim_type_raw_agreement":category(cp,"claim_type")["raw_agreement"],
          "material_raw_agreement":category(cp,"material")["raw_agreement"],
          "claim_origin_raw_agreement":category(cp,"claim_origin")["raw_agreement"],
          "claim_role_raw_agreement":category(cp,"claim_role")["raw_agreement"],
          "unmatched_reviewer_a_claim_ids":c["ua"],"unmatched_reviewer_e_claim_ids":c["ue"]})
    return {"schema_version":3,"report_id":"phase7.3.3-d1-a-boundary-agreement-a-e-v3","recorded_at":recorded_at,
      "status":"completed_frozen_before_adjudication","protocol_id":p["protocol_id"],"agreement_protocol_sha256":p["_sha"],"inputs":p["inputs"],
      "alignment_summary":{"grouping_keys":p["alignment_policy"]["grouping_keys"],"pair_score":p["alignment_policy"]["pair_score"],
        "matching":p["alignment_policy"]["matching"],"minimum_iou":threshold,"claim_text_similarity_used":False,
        "matched_pair_count":mn,"exact_span_match_count":exact},
      "claim_count_metrics":{"reviewer_a_claim_count":an,"reviewer_e_claim_count":en,"absolute_claim_count_difference":abs(an-en),
        "claim_count_ratio_min_over_max":min(an,en)/max(an,en) if max(an,en) else None,
        "per_case_exact_claim_count_agreement_rate":sum(x==y for x,y in zip(acount,ecount))/len(cases) if cases else None,
        "per_case_claim_count_pearson_correlation":pearson(acount,ecount)},
      "segmentation_metrics":{"exact_boundary_agreement_rate_among_matched":exact/mn if mn else None,"matched_span_mean_iou":avg(scores),
        "overlap_alignment_rate_symmetric":2*mn/total if total else None,"unmatched_claim_rate_symmetric":(len(ua_all)+len(ue_all))/total if total else None,
        "reviewer_a_matched_claim_rate":mn/an if an else None,"reviewer_e_matched_claim_rate":mn/en if en else None,
        "unmatched_reviewer_a_claim_count":len(ua_all),"unmatched_reviewer_e_claim_count":len(ue_all),
        "a_one_to_many_e_count":len(split_ids),"e_one_to_many_a_count":len(merge_ids),
        "a_one_to_many_e_claim_ids":split_ids,"e_one_to_many_a_claim_ids":merge_ids},
      "attribute_agreement_on_matched_pairs":{f:category(pairs,f) for f in fields},"per_case_diagnostics":per,
      "unmatched_claims":{"reviewer_a_claim_ids":[x["reviewer_claim_id"] for x in ua_all],"reviewer_e_claim_ids":[x["reviewer_claim_id"] for x in ue_all]},
      "measurement_limits":["Attribute agreement is conditional on deterministic IoU-aligned pairs and does not erase unmatched segmentation disagreements.",
        "One-to-many and many-to-one overlap structures are reported independently of one-to-one matching.",
        "No adjudicated label, Support label, Candidate gold/silver label, or held-out case was used.",
        "This report measures independent Boundary agreement; it does not freeze Boundary Gold."],
      "agreement_computed_before_adjudication":True,"adjudication_used":False,"coverage_qa_used":False,"support_labels_used":False,"held_out_accessed":False}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--protocol",type=Path,required=True); ap.add_argument("--reviewer-a",type=Path,required=True)
    ap.add_argument("--reviewer-e",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--verify",action="store_true")
    x=ap.parse_args(); p=load(x.protocol)
    assert p["status"]=="frozen_before_agreement_computation" and p["agreement_input"]=="raw_blind_reviewer_submissions_only"
    assert p["inputs"]["reviewer_a_submission_sha256"]==sha(x.reviewer_a) and p["inputs"]["reviewer_e_submission_sha256"]==sha(x.reviewer_e)
    assert p["inputs"]["agreement_script_sha256"]==sha(Path(__file__))
    p["_sha"]=sha(x.protocol); a,e=load(x.reviewer_a),load(x.reviewer_e)
    validate(a,p["boundary_reference_protocol_id"]); validate(e,p["boundary_reference_protocol_id"])
    assert a["boundary_packet_sha256"]==e["boundary_packet_sha256"]==p["inputs"]["boundary_packet_sha256"] and a["reviewer_id"]!=e["reviewer_id"]
    if x.verify:
        old=load(x.output); new=compute(p,a,e,old["recorded_at"])
        if old!=new: raise SystemExit("agreement verification failed")
        print(f"agreement verified: {x.output} sha256={sha(x.output)}"); return
    if x.output.exists(): raise SystemExit(f"refusing to overwrite frozen Agreement report: {x.output}")
    report=compute(p,a,e,dt.datetime.now(dt.timezone.utc).isoformat())
    x.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(f"agreement written: {x.output}\nsha256={sha(x.output)}")
if __name__=="__main__": main()