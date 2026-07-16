#!/usr/bin/env python3
"""Freeze the prospective Boundary Review v2 successor after Reviewer B v1 serialization failure."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
STATE_IN = PATTERN / "phase7_3_3_d_support_stage_state_v31.json"
READY_IN = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v42.json"
NEGATIVE = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_negative_result_v1.json"
NEGATIVE_OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_execution_outcome_v1.json"
A_SUBMISSION = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_a_submission_v1.json"
A_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_a_execution_receipt_v1.json"
TAXONOMY = CONFIG / "phase7_3_3_d_failure_taxonomy_v2.json"
V1_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_review_protocol_v1.json"
V1_SCHEMA = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_review_output_schema_v1.json"
V1_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_execution_policy_v1.json"
V1_PROMPT = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_prompt_v1.md"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_boundary_blind_worklist_v1.json"
V1_ADAPTER = ROOT / "scripts/eval/phase7_multi_claim_successor_boundary_reviewer_v1.py"
ENTRY_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_review_v2_entry_protocol_v1.json"
CLASSIFICATION = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_failure_classification_v1.json"
ENTRY_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_review_v2_entry_manifest_v1.json"
ENTRY_OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_review_v2_entry_outcome_v1.json"
STATE_OUT = PATTERN / "phase7_3_3_d_support_stage_state_v32.json"
READY_OUT = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v43.json"
ENTRY_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_review_v2_entry_receipt_v1.json"
NEXT_STAGE = "construct_multi_claim_successor_boundary_review_v2"
EXPECTED = {
    STATE_IN: "0ead98efa455b53d8398dcfe9e762adf9c624c8402f548e716bea677b075eed8",
    READY_IN: "926397d87eeb8116e0179e9788c6c77841f81c03d6553562a935294eae61c8e7",
    NEGATIVE: "c37e599bf0d006f90ca239dfdda7d2258fb630eceadcee811337689b3374e608",
    NEGATIVE_OUTCOME: "a5f0af8dbffedd1ea09a8f15b84df4be582ff2be42cd2c293da6870b61070a1d",
    A_SUBMISSION: "ae0a16951be5595a8d4f34f17c0370e7b147c8d2b77c95b198844b4f39712795",
    A_RECEIPT: "415a70c02dabc80ccc2f2966b03dd76bbf5fbdcaf4302795a6410020eee21aca",
    TAXONOMY: "5def03716fc695e4165682cfa6dbb1c9c5400764ecad7e181812b72261e1f24a",
    V1_PROTOCOL: "c1fc720a6b156652822754937a8ec36e4a76d97cd7980a26812327c9a51a3a21",
    V1_SCHEMA: "a62483511be951c3a699471f36b069cb6469f0b683b26bc4e9e8b94925391c6c",
    V1_POLICY: "5c23c26c1a0bbee7ff5a442c08b27a60f02a0db61b140522799d63bd037322f7",
    V1_PROMPT: "7e3ddc05c9748a7be7f727cd7dd29eefdb9475e01492bba38dd684ce7ccbfe6c",
    WORKLIST: "13656be468d8c48c36967c689de4d0fdad09cd7f9ba9efe619682863659a2405",
    V1_ADAPTER: "bfdb0e380f6660fd2226cd84c92729c4b4c9bbd2fcacb81c0475f695e8f8325c",
}


def hb(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def sha(path: Path) -> str: return hb(path.read_bytes())
def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8-sig"))
def rel(path: Path) -> str: return str(path.relative_to(ROOT)).replace("\\", "/")
def jbytes(value: Any) -> bytes: return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_once(path: Path, payload: bytes) -> str:
    if path.exists():
        if path.read_bytes() != payload: raise ValueError(f"immutable_artifact_exists_with_different_content:{rel(path)}")
        return hb(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload); temporary=Path(handle.name)
    temporary.replace(path); return hb(payload)


def outputs() -> list[Path]: return [ENTRY_PROTOCOL,CLASSIFICATION,ENTRY_MANIFEST,ENTRY_OUTCOME,STATE_OUT,READY_OUT,ENTRY_RECEIPT]


def preflight() -> dict[str, Any]:
    missing=[rel(p) for p in EXPECTED if not p.exists()]
    mismatch={rel(p):{"expected":d,"actual":sha(p)} for p,d in EXPECTED.items() if p.exists() and sha(p)!=d}
    state=load(STATE_IN) if STATE_IN.exists() else {}; ready=load(READY_IN) if READY_IN.exists() else {}; neg=load(NEGATIVE) if NEGATIVE.exists() else {}; outcome=load(NEGATIVE_OUTCOME) if NEGATIVE_OUTCOME.exists() else {}; a=load(A_SUBMISSION) if A_SUBMISSION.exists() else {}
    checks={
        "required_inputs_present":not missing,
        "input_hashes_match":not mismatch,
        "v1_terminal_negative":state.get("status")=="boundary_reviewer_authoritative_negative_result" and ready.get("status")=="boundary_reviewer_authoritative_negative_result",
        "v1_no_next_stage":state.get("next_authorized_stage") is None and ready.get("next_authorized_stage") is None,
        "reviewer_b_level1_evidence":neg.get("status")=="authoritative_negative_result" and neg.get("response_received") is True and neg.get("failure_type")=="JSONDecodeError",
        "same_version_retry_forbidden":outcome.get("same_version_retry_authorized") is False,
        "boundary_capability_not_assessable":neg.get("boundary_capability_conclusion_authorized") is False,
        "reviewer_a_v1_preserved":a.get("completed") is True and a.get("completed_case_count")==40,
        "confirmatory_closed":state.get("confirmatory_dataset_opened") is False and ready.get("confirmatory_dataset_opened") is False,
        "runtime_unauthorized":state.get("runtime_integration_authorized") is False and ready.get("runtime_integration_authorized") is False,
        "outputs_absent":all(not p.exists() for p in outputs()),
    }
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"missing":missing,"mismatches":mismatch}


def build() -> dict[Path, bytes]:
    neg=load(NEGATIVE)
    protocol={
        "schema_version":1,
        "protocol_id":"phase7.3.3-d-multi-claim-successor-boundary-review-v2-entry-protocol-v1",
        "status":"prospectively_frozen_successor_authorization",
        "predecessor_result":"reviewer_b_v1_authoritative_level_1_serialization_failure",
        "predecessor_negative_result_sha256":sha(NEGATIVE),
        "same_version_retry_authorized":False,
        "successor_version":"boundary_review_v2",
        "successor_hypothesis":"compact operation-only output can remove the v1 invalid-JSON serialization bottleneck without changing Boundary semantics",
        "controlled_invariants":["selected_40_cases","frozen_v1_worklist","boundary_semantics","operation_based_exact_span_reconstruction","provider","reviewer_models","temperature","top_p","max_tokens","blindness"],
        "single_intended_change":"output representation removes rationale and confidence and returns only compact boundary operations",
        "reviewer_a_v1_reused_as_v2_submission":False,
        "reviewer_a_and_b_v2_both_must_run_under_v2":True,
        "v1_artifacts_modified":False,
        "confirmatory_opening_authorized":False,
        "runtime_integration_authorized":False,
    }
    classification={
        "schema_version":1,
        "classification_id":"phase7.3.3-d-multi-claim-successor-boundary-reviewer-b-failure-classification-v1",
        "status":"frozen_authoritative_negative_result_classification",
        "taxonomy_sha256":sha(TAXONOMY),
        "negative_result_sha256":sha(NEGATIVE),
        "primary_failure":{"level":1,"code":"provider_representation_contract","subclass":"serialization","subtype":"invalid_json_unterminated_string"},
        "failure_attribution":{"primary":"provider","subtype":"returned_content_invalid_under_frozen_json_contract","confidence":"high","evidence":["provider content bytes were received and hashed before content JSON parsing","JSONDecodeError: "+str(neg.get("failure_code")),"17 prior v1 cases completed before the failing case"],"counterevidence":["raw provider content is intentionally not stored, so model generation versus intermediary truncation cannot be distinguished","char 1024 is suggestive but does not prove a fixed provider character cap"]},
        "delivery_transport":"PASS",
        "boundary_capability":"not_assessable",
        "agreement":"not_authorized",
        "same_version_retry_authorized":False,
    }
    protocol_b=jbytes(protocol); class_b=jbytes(classification)
    fixed={ENTRY_PROTOCOL:protocol_b,CLASSIFICATION:class_b}
    fixed_hash={rel(p):hb(b) for p,b in fixed.items()}
    manifest={
        "schema_version":1,
        "manifest_id":"phase7.3.3-d-multi-claim-successor-boundary-review-v2-entry-manifest-v1",
        "status":"frozen_before_v2_adapter_execution",
        "adapter":rel(Path(__file__)),
        "adapter_sha256":sha(Path(__file__)),
        "input_sha256":{rel(p):sha(p) for p in EXPECTED},
        "artifact_sha256":fixed_hash,
        "provider_called":False,
        "confirmatory_dataset_opened":False,
        "runtime_integration_authorized":False,
    }
    manifest_b=jbytes(manifest)
    outcome={
        "schema_version":1,
        "outcome_id":"phase7.3.3-d-multi-claim-successor-boundary-review-v2-entry-outcome-v1",
        "status":"boundary_review_v2_successor_authorized",
        "same_version_retry_performed":False,
        "v1_negative_result_preserved":True,
        "next_authorized_stage":NEXT_STAGE,
        "confirmatory_dataset_opened":False,
        "runtime_integration_authorized":False,
    }
    lineage={
        "multi_claim_successor_boundary_reviewer_b_failure_classification_v1_sha256":hb(class_b),
        "multi_claim_successor_boundary_review_v2_entry_protocol_v1_sha256":hb(protocol_b),
        "multi_claim_successor_boundary_review_v2_entry_manifest_v1_sha256":hb(manifest_b),
    }
    state=copy.deepcopy(load(STATE_IN)); state.setdefault("artifact_lineage",{}).update(lineage); state.update({"schema_version":32,"state_id":"phase7.3.3-d-support-stage-state-v32","status":"boundary_review_v2_successor_authorized","next_authorized_stage":NEXT_STAGE,"multi_claim_successor_boundary_review_v1_negative_preserved":True,"multi_claim_successor_boundary_review_v2_authorized":True,"multi_claim_successor_boundary_review_v2_provider_called":False,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
    ready=copy.deepcopy(load(READY_IN)); ready.setdefault("artifact_lineage",{}).update(lineage); ready.update({"schema_version":43,"readiness_id":"phase7.3.3-d1-reference-construction-readiness-v43","status":"boundary_review_v2_successor_authorized","next_authorized_stage":NEXT_STAGE,"successor_boundary_review_v1_negative_preserved":True,"successor_boundary_review_v2_authorized":True,"provider_called":False,"confirmatory_opening_authorized":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False})
    return {**fixed,ENTRY_MANIFEST:manifest_b,ENTRY_OUTCOME:jbytes(outcome),STATE_OUT:jbytes(state),READY_OUT:jbytes(ready)}


def freeze() -> dict[str, Any]:
    check=preflight()
    if check["status"]!="PASS": raise ValueError("successor_entry_preflight_failed")
    built=build(); hashes={rel(p):write_once(p,b) for p,b in built.items()}
    receipt={"schema_version":1,"receipt_id":"phase7.3.3-d-multi-claim-successor-boundary-review-v2-entry-receipt-v1","status":"PASS","artifact_sha256":hashes,"same_version_retry_performed":False,"v1_negative_result_preserved":True,"provider_called":False,"confirmatory_dataset_opened":False,"runtime_integration_authorized":False,"next_authorized_stage":NEXT_STAGE}
    rsha=write_once(ENTRY_RECEIPT,jbytes(receipt))
    return {"status":"PASS","classification_sha256":sha(CLASSIFICATION),"entry_manifest_sha256":sha(ENTRY_MANIFEST),"receipt_sha256":rsha,"state_sha256":sha(STATE_OUT),"readiness_sha256":sha(READY_OUT),"next_authorized_stage":NEXT_STAGE}


def verify() -> dict[str, Any]:
    expected=build(); checks={rel(p):p.exists() and p.read_bytes()==b for p,b in expected.items()}
    checks[rel(ENTRY_RECEIPT)]=ENTRY_RECEIPT.exists() and load(ENTRY_RECEIPT).get("status")=="PASS"
    state=load(STATE_OUT) if STATE_OUT.exists() else {}; ready=load(READY_OUT) if READY_OUT.exists() else {}
    checks.update({"state_next_stage":state.get("next_authorized_stage")==NEXT_STAGE,"readiness_next_stage":ready.get("next_authorized_stage")==NEXT_STAGE,"v1_negative_unchanged":sha(NEGATIVE)==EXPECTED[NEGATIVE],"same_version_retry_not_performed":load(ENTRY_OUTCOME).get("same_version_retry_performed") is False,"provider_not_called":state.get("multi_claim_successor_boundary_review_v2_provider_called") is False,"confirmatory_closed":state.get("confirmatory_dataset_opened") is False,"runtime_unauthorized":state.get("runtime_integration_authorized") is False})
    failed=[k for k,v in checks.items() if not v]
    return {"status":"PASS" if not failed else "FAIL","checks":len(checks),"failed":failed,"next_authorized_stage":state.get("next_authorized_stage")}


def main() -> int:
    parser=argparse.ArgumentParser(); group=parser.add_mutually_exclusive_group(required=True); group.add_argument("--preflight",action="store_true"); group.add_argument("--freeze",action="store_true"); group.add_argument("--verify",action="store_true"); args=parser.parse_args()
    result=preflight() if args.preflight else freeze() if args.freeze else verify()
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result.get("status")=="PASS" else 1


if __name__=="__main__": raise SystemExit(main())
