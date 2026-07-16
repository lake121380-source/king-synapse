#!/usr/bin/env python3
"""Open only the frozen multi-claim successor selection for Reference Construction."""
from __future__ import annotations
import argparse, copy, hashlib, json, tempfile, tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"; DATA = ROOT / "crates/eval/datasets"
PATTERN = DATA / "pattern_extraction"; REPORTS = ROOT / "crates/eval/reports"
SOURCE_ROOT = DATA / "cognitive_memory"
STATE_IN = PATTERN / "phase7_3_3_d_support_stage_state_v26.json"
READY_IN = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v37.json"
SAMPLING_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_sampling_frame_protocol_v1.json"
SAMPLING_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_sampling_manifest_v1.json"
SAMPLING_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_sampling_freeze_receipt_v1.json"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_selected_worklist_v1.json"
PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_content_open_protocol_v1.json"
DATASET = PATTERN / "phase7_3_3_d_multi_claim_successor_selected_dataset_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_content_open_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_content_open_manifest_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_content_open_outcome_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_content_open_receipt_v1.json"
STATE_OUT = PATTERN / "phase7_3_3_d_support_stage_state_v27.json"
READY_OUT = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v38.json"
SEED = "733051"; JOINER = "\n"; NEXT_STAGE = "run_multi_claim_successor_candidate_prescreen_v1"
EXPECTED = {
 STATE_IN:"f9737483a775db0d9a59ee234f111bc3470f94d4e61c6ac6a953c827534f5ff5",
 READY_IN:"6b0396a8a82408455385f23a35f0bbfdd839edb185b9691ced33da0eb11e1454",
 SAMPLING_MANIFEST:"218b9f7101a67b1b059cf2ae795c501c039c5fd046f57f7a953942f86b862779",
 SAMPLING_RECEIPT:"2af2f1ae93827373a1db08165348193b22e4fecb24e44e54a17e1dace7f501c3",
}
OUTPUTS=[PROTOCOL,DATASET,FIXTURES,MANIFEST,OUTCOME,STATE_OUT,READY_OUT,RECEIPT]

def hb(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha(p:Path)->str:return hb(p.read_bytes())
def csha(v:Any)->str:return hb(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
def load(p:Path)->Any:return json.loads(p.read_text(encoding="utf-8-sig"))
def rel(p:Path)->str:return str(p.relative_to(ROOT)).replace("\\","/")
def body(v:Any)->bytes:return (json.dumps(v,ensure_ascii=False,indent=2)+"\n").encode()
def write_once(p:Path,v:Any)->str:
 b=body(v)
 if p.exists():
  if p.read_bytes()!=b:raise ValueError(f"immutable_artifact_exists_with_different_content:{rel(p)}")
  return hb(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile("wb",dir=p.parent,delete=False) as f:f.write(b);t=Path(f.name)
 t.replace(p);return hb(b)

def ordered_parts(identity:str,r:dict[str,Any])->list[dict[str,Any]]:
 raw=[]
 if isinstance(r.get("expected_decision"),str) and r["expected_decision"].strip():raw.append(("decision_component",0,r["expected_decision"].strip()))
 if isinstance(r.get("expected_trace"),list):
  raw.extend(("trace_component",i,x.strip()) for i,x in enumerate(r["expected_trace"]) if isinstance(x,str) and x.strip())
 if isinstance(r.get("distractor_decision"),str) and r["distractor_decision"].strip():raw.append(("contrast_component",0,r["distractor_decision"].strip()))
 out=[]
 for role,index,text in raw:
  ts=hb(text.encode()); rank=hb("|".join([SEED,identity,role,str(index),ts]).encode())
  out.append({"role":role,"source_index":index,"text":text,"text_sha256":ts,"order_rank_sha256":rank})
 return sorted(out,key=lambda x:(x["order_rank_sha256"],x["text_sha256"]))

def source_records()->dict[str,dict[str,Any]]:
 found={}; declared=load(SAMPLING_MANIFEST)["source_file_sha256"]
 for path_text,digest in declared.items():
  path=ROOT/path_text
  if sha(path)!=digest:raise ValueError(f"source_hash_mismatch:{path_text}")
  doc=tomllib.loads(path.read_text(encoding="utf-8"))
  for i,r in enumerate(doc.get("cases",[])):
   identity=f"{path_text}#cases[{i}]#{r.get('id')}"; cid=f"mc-{path.stem}-{r.get('id')}"
   found[cid]={"identity":identity,"record":r,"source_path":path_text}
 return found

def open_cases()->list[dict[str,Any]]:
 source=source_records(); work=load(WORKLIST); cases=[]
 for item in work["items"]:
  cid=item["candidate_id"]
  if cid not in source:raise ValueError(f"selected_source_record_not_found:{cid}")
  raw=source[cid]; parts=ordered_parts(raw["identity"],raw["record"]); text=JOINER.join(x["text"] for x in parts)
  evidence=raw["record"].get("relevant_memories")
  if hb(text.encode())!=item["candidate_sha256"]:raise ValueError(f"candidate_commitment_mismatch:{cid}")
  if csha([x["text_sha256"] for x in parts])!=item["component_order_commitment_sha256"]:raise ValueError(f"order_commitment_mismatch:{cid}")
  if csha(evidence)!=item["evidence_bundle_sha256"]:raise ValueError(f"evidence_commitment_mismatch:{cid}")
  normalized=[{"evidence_id":f"{cid}-evidence-{i:03d}","source_index":i-1,"content":content}
              for i,content in enumerate(evidence,1)]
  cases.append({"successor_index":item["successor_index"],"case_id":cid,"source_family":item["source_family"],
    "candidate_sha256":item["candidate_sha256"],"component_order_commitment_sha256":item["component_order_commitment_sha256"],
    "candidate_text":text,"source_evidence_bundle_sha256":item["evidence_bundle_sha256"],
    "evidence_bundle":normalized,"normalized_evidence_bundle_sha256":csha(normalized),
    "valid_evidence_ids":[x["evidence_id"] for x in normalized]})
 cases.sort(key=lambda x:x["successor_index"]);return cases

def fixtures()->list[dict[str,Any]]:
 identity="x#0"; r={"expected_decision":"A.","expected_trace":["B.","C."],"distractor_decision":"D."}
 p=ordered_parts(identity,r); text=JOINER.join(x["text"] for x in p); commitment=csha([x["text_sha256"] for x in p])
 checks=[("deterministic_candidate_replay",text==JOINER.join(x["text"] for x in ordered_parts(identity,r))),
  ("order_commitment_replay",commitment==csha([x["text_sha256"] for x in ordered_parts(identity,r)])),
  ("hash_mismatch_detectable",hb((text+"x").encode())!=hb(text.encode())),
  ("source_roles_not_serialized",all(x not in text for x in ["decision_component","trace_component","contrast_component"])),
  ("support_labels_not_serialized",all(x not in text for x in ["supported","unsupported","partially_supported"])),
  ("newline_representation_preserved",text.count("\n")==3)]
 return [{"fixture_id":n,"status":"PASS" if ok else "FAIL"} for n,ok in checks]

def protocol()->dict[str,Any]:
 return {"schema_version":1,"protocol_id":"phase7.3.3-d-multi-claim-successor-content-open-protocol-v1",
  "status":"frozen_with_selected_content_open","stage":"open_multi_claim_successor_selected_content_v1",
  "scope":"selected_40_reference_construction_cases_only","replay":{"candidate_hash_required":True,
   "component_order_commitment_required":True,"source_evidence_hash_required":True,"source_file_hash_required":True},
  "visibility":{"candidate_text":True,"evidence_content":True,"source_component_roles":False,"source_support_roles":False,
   "old_boundary_or_support_gold":False,"old_arm_outputs":False,"confirmatory_content":False},
  "normalization":{"evidence_ids":"deterministic_case_local_ids","candidate_semantic_rewrite":False},
  "provider_called":False,"runtime_integration_authorized":False,"next_authorized_stage":NEXT_STAGE}

def preflight()->dict[str,Any]:
 required=[*EXPECTED,SAMPLING_PROTOCOL,WORKLIST];missing=[rel(p) for p in required if not p.exists()]
 mismatch={rel(p):{"expected":e,"actual":sha(p)} for p,e in EXPECTED.items() if p.exists() and sha(p)!=e}
 s=load(STATE_IN) if STATE_IN.exists() else {};r=load(READY_IN) if READY_IN.exists() else {};w=load(WORKLIST) if WORKLIST.exists() else {}
 checks={"required_inputs_present":not missing,"input_hashes_match":not mismatch,
  "state_authorizes_content_open":s.get("next_authorized_stage")=="open_multi_claim_successor_selected_content_v1",
  "readiness_authorizes_content_open":r.get("next_authorized_stage")=="open_multi_claim_successor_selected_content_v1",
  "sampling_frame_frozen":s.get("multi_claim_successor_sampling_frame_frozen") is True,
  "selected_count_40":w.get("selected_count")==40,"selected_content_still_sealed":s.get("multi_claim_successor_selected_content_opened") is False,
  "provider_not_called":s.get("multi_claim_successor_provider_called") is False,
  "confirmatory_closed":s.get("confirmatory_dataset_opened") is False and s.get("confirmatory_opening_authorized") is False,
  "runtime_unauthorized":s.get("runtime_integration_authorized") is False,"outputs_absent":all(not p.exists() for p in OUTPUTS)}
 return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"missing":missing,"mismatches":mismatch}

def build()->dict[Path,Any]:
 cases=open_cases();fx=fixtures()
 if len(cases)!=40:raise ValueError("selected_case_count_not_40")
 if not all(x["status"]=="PASS" for x in fx):raise ValueError("contract_fixture_failure")
 proto=protocol();dataset={"schema_version":1,"dataset_id":"phase7.3.3-d-multi-claim-successor-selected-dataset-v1",
  "status":"selected_content_open_reference_construction_only","sampling_worklist_sha256":sha(WORKLIST),
  "case_count":len(cases),"cases":cases,"source_component_roles_present":False,"support_labels_present":False,
  "old_gold_present":False,"arm_outputs_present":False,"unselected_content_opened":False,"confirmatory_content_opened":False}
 fdoc={"schema_version":1,"fixture_report_id":"phase7.3.3-d-multi-claim-successor-content-open-contract-fixtures-v1",
  "status":"PASS","passed":len(fx),"total":len(fx),"fixtures":fx,"provider_called":False,"confirmatory_dataset_opened":False}
 docs={PROTOCOL:proto,DATASET:dataset,FIXTURES:fdoc}; hashes={rel(p):hb(body(v)) for p,v in docs.items()}
 manifest={"schema_version":1,"manifest_id":"phase7.3.3-d-multi-claim-successor-content-open-manifest-v1",
  "status":"frozen_with_selected_content_open","adapter":rel(Path(__file__).resolve()),"adapter_sha256":sha(Path(__file__).resolve()),
  "input_sha256":{rel(p):sha(p) for p in [STATE_IN,READY_IN,SAMPLING_PROTOCOL,SAMPLING_MANIFEST,SAMPLING_RECEIPT,WORKLIST]},
  "source_file_sha256":load(SAMPLING_MANIFEST)["source_file_sha256"],"artifact_sha256":hashes,
  "selected_count":len(cases),"unselected_content_opened":False,"provider_called":False,
  "confirmatory_dataset_opened":False,"runtime_integration_authorized":False}
 msha=hb(body(manifest));outcome={"schema_version":1,"outcome_id":"phase7.3.3-d-multi-claim-successor-content-open-outcome-v1",
  "status":"selected_content_open_commitments_replayed","selected_count":len(cases),"candidate_commitments_verified":len(cases),
  "evidence_commitments_verified":len(cases),"source_component_roles_exposed":False,"support_labels_exposed":False,
  "unselected_content_opened":False,"provider_called":False,"confirmatory_dataset_opened":False,
  "runtime_integration_authorized":False,"next_authorized_stage":NEXT_STAGE}
 lineage={"multi_claim_successor_content_open_manifest_v1_sha256":msha,**{Path(k).name.replace('.json','_sha256'):v for k,v in hashes.items()}}
 state=copy.deepcopy(load(STATE_IN));state.setdefault("artifact_lineage",{}).update(lineage);state.update({"schema_version":27,
  "state_id":"phase7.3.3-d-support-stage-state-v27","status":outcome["status"],"next_authorized_stage":NEXT_STAGE,
  "multi_claim_successor_selected_content_opened":True,"multi_claim_successor_content_opened":True,
  "multi_claim_successor_unselected_content_opened":False,"multi_claim_successor_provider_called":False,
  "multi_claim_successor_selected_dataset_status":"open_reference_construction_only","confirmatory_opening_authorized":False,
  "confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
 ready=copy.deepcopy(load(READY_IN));ready.setdefault("artifact_lineage",{}).update(lineage);ready.update({"schema_version":38,
  "readiness_id":"phase7.3.3-d1-reference-construction-readiness-v38","status":outcome["status"],
  "next_authorized_stage":NEXT_STAGE,"successor_selected_content_opened":True,"successor_content_opened":True,
  "successor_unselected_content_opened":False,"provider_called":False,"successor_selected_dataset_status":"open_reference_construction_only",
  "confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
 return {**docs,MANIFEST:manifest,OUTCOME:outcome,STATE_OUT:state,READY_OUT:ready}

def freeze()->dict[str,Any]:
 out=build();hs={rel(p):write_once(p,v) for p,v in out.items()};o=load(OUTCOME);f=load(FIXTURES)
 receipt={"schema_version":1,"receipt_id":"phase7.3.3-d-multi-claim-successor-content-open-receipt-v1","status":"PASS",
  "artifact_sha256":hs,"selected_count":o["selected_count"],"fixtures_passed":f["passed"],"fixtures_total":f["total"],
  "unselected_content_opened":False,"provider_called":False,"confirmatory_dataset_opened":False,
  "runtime_integration_authorized":False,"next_authorized_stage":NEXT_STAGE}
 rs=write_once(RECEIPT,receipt);return {"status":"PASS","selected":o["selected_count"],"fixtures":f"{f['passed']}/{f['total']}",
  "manifest_sha256":sha(MANIFEST),"receipt_sha256":rs,"state_sha256":sha(STATE_OUT),"readiness_sha256":sha(READY_OUT),
  "next_authorized_stage":NEXT_STAGE,"provider_called":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False}

def verify()->dict[str,Any]:
 expected=build();checks={rel(p):p.exists() and p.read_bytes()==body(v) for p,v in expected.items()}
 if RECEIPT.exists():
  r=load(RECEIPT)
  for name,digest in r.get("artifact_sha256",{}).items():p=ROOT/name;checks[name+"#receipt_hash"]=p.exists() and sha(p)==digest
  checks[rel(RECEIPT)+"#status"]=r.get("status")=="PASS"
 else:checks[rel(RECEIPT)]=False
 s=load(STATE_OUT) if STATE_OUT.exists() else {};d=load(DATASET) if DATASET.exists() else {}
 checks.update({"next_gate":s.get("next_authorized_stage")==NEXT_STAGE,"selected_only":d.get("unselected_content_opened") is False,
  "roles_blind":d.get("source_component_roles_present") is False,"labels_blind":d.get("support_labels_present") is False,
  "confirmatory_closed":s.get("confirmatory_dataset_opened") is False,"runtime_unauthorized":s.get("runtime_integration_authorized") is False})
 failed=[k for k,v in checks.items() if not v];return {"status":"PASS" if not failed else "FAIL","checks":len(checks),"failed":failed,
  "selected_count":d.get("case_count"),"next_authorized_stage":s.get("next_authorized_stage")}

def main()->int:
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 g.add_argument("--preflight",action="store_true");g.add_argument("--run-contract-fixtures",action="store_true");g.add_argument("--freeze",action="store_true");g.add_argument("--verify",action="store_true");a=p.parse_args()
 if a.preflight:r=preflight()
 elif a.run_contract_fixtures:
  x=fixtures();r={"status":"PASS" if all(i["status"]=="PASS" for i in x) else "FAIL","passed":sum(i["status"]=="PASS" for i in x),"total":len(x),"fixtures":x}
 elif a.freeze:r=freeze()
 else:r=verify()
 print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if r.get("status")=="PASS" else 1
if __name__=="__main__":raise SystemExit(main())
