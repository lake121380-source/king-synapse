#!/usr/bin/env python3
"""Phase 7.3.3-D1-A Boundary Coverage QA.

Without --boundary-gold this freezes/verifies the additive Coverage policy and a
blocked report template. With --boundary-gold it validates immutable spans against
the frozen Boundary packet and emits a deterministic Coverage Report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
CONFIG = ROOT / "crates/eval/config"
REPORTS = ROOT / "crates/eval/reports"
PACKET = DATA / "phase7_3_3_d_boundary_blind_review_packet_v1.json"
BASE_PROTOCOL = DATA / "phase7_3_3_d_boundary_reference_protocol_v1.json"
POLICY = CONFIG / "phase7_3_3_d_boundary_coverage_policy_v1.json"
TEMPLATE = REPORTS / "phase7_3_3_d_boundary_coverage_template_v1.json"
BASE_READINESS = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v2.json"
READINESS_SUPPLEMENT = REPORTS / "phase7_3_3_d1_boundary_coverage_readiness_supplement_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: Any) -> str:
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"frozen_artifact_changed:{path.relative_to(ROOT)}")
        return hashlib.sha256(encoded).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temp = Path(handle.name)
    temp.replace(path)
    return hashlib.sha256(encoded).hexdigest()


def policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d1-a-boundary-coverage-policy-v1",
        "extends_protocol_id": "phase7.3.3-d1-a-boundary-reference-protocol-v1",
        "purpose": "Account for every Candidate source-anchor character after Boundary adjudication and before Boundary Gold freeze.",
        "placement": "after_boundary_adjudication_before_boundary_gold_freeze",
        "character_unit": "UTF-8 decoded Python string code point",
        "span_semantics": "[start,end) relative to exactly one frozen source anchor",
        "metrics": [
            "total_anchor_characters", "eligible_non_whitespace_characters", "covered_characters",
            "overlap_characters", "gap_characters", "eligible_gap_characters",
            "declared_non_claim_characters", "claim_non_claim_conflict_characters",
            "raw_coverage_ratio", "eligible_accounting_ratio",
        ],
        "accounting_rule": "Every non-whitespace character must be covered by exactly one adjudicated Claim or by an explicit non_claim_span with a reason code.",
        "non_claim_reason_codes": [
            "punctuation_only", "formatting_only", "list_delimiter", "non_assertive_connector",
            "metadata_not_a_claim", "other_explained_non_claim",
        ],
        "freeze_gates": {
            "invalid_span_count": 0,
            "claim_text_mismatch_count": 0,
            "eligible_gap_characters": 0,
            "overlap_characters": 0,
            "claim_non_claim_conflict_characters": 0,
            "all_non_claim_spans_have_reason_and_rationale": True,
            "coverage_report_sha256_required_by_boundary_gold": True,
        },
        "failure_policy": "A failed gate leaves Boundary Gold unfrozen; it does not authorize changing Candidate, evidence, or support labels.",
        "held_out_access": "forbidden",
        "source_artifact_sha256": {
            "boundary_packet": sha256_file(PACKET),
            "base_boundary_protocol": sha256_file(BASE_PROTOCOL),
        },
    }


def blocked_template() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "report_id": "phase7.3.3-d1-a-boundary-coverage-v1",
        "policy_id": "phase7.3.3-d1-a-boundary-coverage-policy-v1",
        "status": "blocked",
        "blocked_reason": "completed_boundary_adjudication_required",
        "boundary_packet_sha256": sha256_file(PACKET),
        "boundary_adjudication_sha256": None,
        "metrics": {
            "total_anchor_characters": None,
            "eligible_non_whitespace_characters": None,
            "covered_characters": None,
            "overlap_characters": None,
            "gap_characters": None,
            "eligible_gap_characters": None,
            "declared_non_claim_characters": None,
            "claim_non_claim_conflict_characters": None,
            "raw_coverage_ratio": None,
            "eligible_accounting_ratio": None,
        },
        "invalid_span_count": None,
        "claim_text_mismatch_count": None,
        "per_anchor": [],
        "freeze_gates_passed": False,
        "boundary_gold_freeze_allowed": False,
        "held_out_accessed": False,
    }


def readiness_supplement(policy_hash: str, template_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "report_id": "phase7.3.3-d1-boundary-coverage-readiness-supplement-v1",
        "extends_readiness_report_sha256": sha256_file(BASE_READINESS),
        "status": "coverage_infrastructure_ready_boundary_adjudication_required",
        "coverage_policy_sha256": policy_hash,
        "coverage_blocked_template_sha256": template_hash,
        "coverage_report_available": False,
        "coverage_report_sha256": None,
        "boundary_gold_freeze_allowed": False,
        "support_stage_remains_blocked": True,
        "design_model_execution_allowed": False,
        "held_out_accessed": False,
        "provider_called": False,
        "next_required_action": "Complete independent Boundary reviews, Agreement, and adjudication; then run Coverage QA before Boundary Gold freeze.",
    }


def span_tuple(row: dict[str, Any]) -> tuple[int, int]:
    span = row.get("source_span")
    if not isinstance(span, dict) or not isinstance(span.get("start"), int) or not isinstance(span.get("end"), int):
        raise ValueError("invalid_source_span_shape")
    return span["start"], span["end"]


def compute(boundary_adjudication_path: Path) -> dict[str, Any]:
    packet = load(PACKET)
    gold = load(boundary_adjudication_path)
    if gold.get("completed") is not True or gold.get("boundary_state") not in {"agreed", "adjudicated"}:
        raise ValueError("completed_boundary_adjudication_required")
    if gold.get("held_out_accessed") is not False:
        raise ValueError("boundary_adjudication_held_out_violation")

    anchors: dict[tuple[str, str], dict[str, Any]] = {}
    for case in packet["cases"]:
        for anchor in case["source_anchors"]:
            anchors[(case["case_id"], anchor["anchor_id"])] = anchor

    claims = gold.get("adjudicated_claims", gold.get("claims", []))
    non_claim_spans = gold.get("non_claim_spans", [])
    claim_ids: set[str] = set()
    by_anchor_claims: dict[tuple[str, str], list[dict[str, Any]]] = {key: [] for key in anchors}
    by_anchor_nonclaims: dict[tuple[str, str], list[dict[str, Any]]] = {key: [] for key in anchors}
    invalid_span_count = 0
    claim_text_mismatch_count = 0
    invalid_nonclaim_metadata_count = 0

    for claim in claims:
        claim_id = claim.get("boundary_claim_id", claim.get("claim_id"))
        if not claim_id or claim_id in claim_ids:
            raise ValueError("missing_or_duplicate_boundary_claim_id")
        claim_ids.add(claim_id)
        key = (claim.get("case_id"), claim.get("anchor_id"))
        if key not in anchors:
            raise ValueError(f"unknown_claim_anchor:{key}")
        try:
            start, end = span_tuple(claim)
        except ValueError:
            invalid_span_count += 1
            continue
        text = anchors[key]["source_text"]
        if start < 0 or end <= start or end > len(text):
            invalid_span_count += 1
            continue
        if claim.get("claim_text") != text[start:end]:
            claim_text_mismatch_count += 1
        by_anchor_claims[key].append(claim)

    for row in non_claim_spans:
        key = (row.get("case_id"), row.get("anchor_id"))
        if key not in anchors:
            raise ValueError(f"unknown_non_claim_anchor:{key}")
        if not row.get("reason_code") or not row.get("rationale"):
            invalid_nonclaim_metadata_count += 1
        try:
            start, end = span_tuple(row)
        except ValueError:
            invalid_span_count += 1
            continue
        text = anchors[key]["source_text"]
        if start < 0 or end <= start or end > len(text):
            invalid_span_count += 1
            continue
        by_anchor_nonclaims[key].append(row)

    totals = {k: 0 for k in [
        "total_anchor_characters", "eligible_non_whitespace_characters", "covered_characters",
        "overlap_characters", "gap_characters", "eligible_gap_characters",
        "declared_non_claim_characters", "claim_non_claim_conflict_characters",
    ]}
    per_anchor=[]
    for key, anchor in anchors.items():
        text=anchor["source_text"]
        claim_depth=[0]*len(text)
        nonclaim_depth=[0]*len(text)
        for row in by_anchor_claims[key]:
            start,end=span_tuple(row)
            if 0 <= start < end <= len(text):
                for i in range(start,end): claim_depth[i]+=1
        for row in by_anchor_nonclaims[key]:
            start,end=span_tuple(row)
            if 0 <= start < end <= len(text):
                for i in range(start,end): nonclaim_depth[i]+=1
        m={
            "total_anchor_characters": len(text),
            "eligible_non_whitespace_characters": sum(not ch.isspace() for ch in text),
            "covered_characters": sum(d >= 1 for d in claim_depth),
            "overlap_characters": sum(d > 1 for d in claim_depth),
            "gap_characters": sum(d == 0 and n == 0 for d,n in zip(claim_depth,nonclaim_depth)),
            "eligible_gap_characters": sum((not text[i].isspace()) and claim_depth[i] == 0 and nonclaim_depth[i] == 0 for i in range(len(text))),
            "declared_non_claim_characters": sum(d == 0 and n >= 1 for d,n in zip(claim_depth,nonclaim_depth)),
            "claim_non_claim_conflict_characters": sum(d >= 1 and n >= 1 for d,n in zip(claim_depth,nonclaim_depth)),
        }
        for name,value in m.items(): totals[name]+=value
        per_anchor.append({"case_id":key[0],"anchor_id":key[1],"source_text_sha256":anchor["source_text_sha256"],**m})

    total=totals["total_anchor_characters"]
    eligible=totals["eligible_non_whitespace_characters"]
    totals["raw_coverage_ratio"] = totals["covered_characters"] / total if total else 1.0
    accounted_eligible = eligible - totals["eligible_gap_characters"]
    totals["eligible_accounting_ratio"] = accounted_eligible / eligible if eligible else 1.0
    gates_passed = (
        invalid_span_count == 0
        and claim_text_mismatch_count == 0
        and invalid_nonclaim_metadata_count == 0
        and totals["eligible_gap_characters"] == 0
        and totals["overlap_characters"] == 0
        and totals["claim_non_claim_conflict_characters"] == 0
    )
    return {
        "schema_version": 1,
        "report_id": "phase7.3.3-d1-a-boundary-coverage-v1",
        "policy_id": "phase7.3.3-d1-a-boundary-coverage-policy-v1",
        "status": "passed" if gates_passed else "failed",
        "boundary_packet_sha256": sha256_file(PACKET),
        "boundary_adjudication_sha256": sha256_file(boundary_adjudication_path),
        "metrics": totals,
        "invalid_span_count": invalid_span_count,
        "claim_text_mismatch_count": claim_text_mismatch_count,
        "invalid_nonclaim_metadata_count": invalid_nonclaim_metadata_count,
        "per_anchor": per_anchor,
        "freeze_gates_passed": gates_passed,
        "boundary_gold_freeze_allowed": gates_passed,
        "held_out_accessed": False,
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--boundary-adjudication", type=Path)
    parser.add_argument("--output", type=Path)
    args=parser.parse_args()
    policy_hash=write_once(POLICY,policy())
    template_hash=write_once(TEMPLATE,blocked_template())
    readiness_hash=write_once(READINESS_SUPPLEMENT,readiness_supplement(policy_hash,template_hash))
    if args.boundary_adjudication:
        report=compute(args.boundary_adjudication)
        if args.output:
            write_once(args.output,report)
        print(json.dumps(report,ensure_ascii=False,indent=2))
    else:
        print(json.dumps({
            "status":"coverage_infrastructure_ready_boundary_adjudication_required",
            "policy_sha256":policy_hash,
            "blocked_template_sha256":template_hash,
            "readiness_supplement_sha256":readiness_hash,
            "boundary_gold_freeze_allowed":False,
        },indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
