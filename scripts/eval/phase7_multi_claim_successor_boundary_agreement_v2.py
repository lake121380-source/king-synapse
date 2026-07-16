#!/usr/bin/env python3
"""Freeze, compute, and verify Multi-claim Successor Boundary Agreement v2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

STATE_IN = PATTERN / "phase7_3_3_d_support_stage_state_v35.json"
READY_IN = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v46.json"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_boundary_blind_worklist_v1.json"
REVIEW_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_review_protocol_v2.json"
A_SUBMISSION = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_a_submission_v2.json"
B_SUBMISSION = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_reviewer_b_submission_v2.json"

PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_boundary_agreement_protocol_v2.json"
FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_agreement_contract_fixtures_v2.json"
MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_agreement_manifest_v2.json"
PREP_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_agreement_prepare_receipt_v2.json"
REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_agreement_report_v2.json"
ADJUDICATION_WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_boundary_adjudication_worklist_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_agreement_outcome_v2.json"
RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_boundary_agreement_receipt_v2.json"
STATE_OUT = PATTERN / "phase7_3_3_d_support_stage_state_v36.json"
READY_OUT = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v47.json"

CURRENT_STAGE = "construct_multi_claim_successor_boundary_agreement_v2"
NEXT_STAGE = "construct_multi_claim_successor_boundary_adjudication_v1"
EXPECTED = {
    STATE_IN: "1fa5f2a875a989d4de2df54d3eaf47b2f25d75d3d14e82a694ce764267c149ba",
    READY_IN: "3bc9230b944a27a1f8e5139177bf5c03176e0072632f4e5a1e6b4908a8dc27dd",
    WORKLIST: "13656be468d8c48c36967c689de4d0fdad09cd7f9ba9efe619682863659a2405",
    REVIEW_PROTOCOL: "7eb640a72db08f4357cf02dfa27924e436a4f45b478f1d1e870c6a22981261da",
    A_SUBMISSION: "a0dc02a1323942171c407055b86b8dde928b04a548f93c97051258ec27a0763a",
    B_SUBMISSION: "786dfb38557b9f7772d4165a05f793c62d9aec20aa6d9b48fdf0daa004a706e3",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hb(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jbytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_once(path: Path, data: bytes) -> str:
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"refusing_to_overwrite_frozen_artifact:{path.name}")
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hb(data)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def span_tuple(claim: dict[str, Any]) -> tuple[int, int]:
    span = claim["source_span"]
    return int(span["start"]), int(span["end"])


def iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    intersection = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return intersection / union if union else 0.0


def overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return min(a[1], b[1]) > max(a[0], b[0])


def validate_submission(submission: dict[str, Any], reviewer: str) -> None:
    if submission.get("schema_version") != 2 or submission.get("reviewer") != reviewer:
        raise ValueError(f"submission_identity_invalid:{reviewer}")
    if submission.get("completed") is not True or submission.get("completed_case_count") != 40:
        raise ValueError(f"submission_incomplete:{reviewer}")
    if not all(submission.get(key) is True for key in (
        "blind_to_evidence", "blind_to_other_reviewer", "blind_to_support_labels", "blind_to_old_gold"
    )):
        raise ValueError(f"submission_blindness_invalid:{reviewer}")
    claims = submission.get("claims")
    if not isinstance(claims, list) or len(claims) != submission.get("claim_count"):
        raise ValueError(f"submission_claim_count_invalid:{reviewer}")
    seen = set()
    for claim in claims:
        required = {
            "case_id", "claim_id", "source_span", "source_excerpt", "source_occurrence_index",
            "source_unit_ids", "boundary_operation_kind", "reviewer"
        }
        if not required.issubset(claim) or claim.get("reviewer") != reviewer:
            raise ValueError(f"claim_shape_invalid:{reviewer}")
        key = (claim["case_id"],) + span_tuple(claim)
        if key in seen:
            raise ValueError(f"duplicate_claim_span:{reviewer}:{claim['case_id']}")
        seen.add(key)


def index_claims(claims: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        result[claim["case_id"]].append(claim)
    for case_claims in result.values():
        case_claims.sort(key=lambda claim: (*span_tuple(claim), claim["claim_id"]))
    return dict(result)


def align_case(a_claims: list[dict[str, Any]], b_claims: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    overlap_a: dict[str, list[str]] = {claim["claim_id"]: [] for claim in a_claims}
    overlap_b: dict[str, list[str]] = {claim["claim_id"]: [] for claim in b_claims}
    for a_claim in a_claims:
        a_span = span_tuple(a_claim)
        for b_claim in b_claims:
            b_span = span_tuple(b_claim)
            score = iou(a_span, b_span)
            if overlap(a_span, b_span):
                overlap_a[a_claim["claim_id"]].append(b_claim["claim_id"])
                overlap_b[b_claim["claim_id"]].append(a_claim["claim_id"])
            if score > 0:
                candidates.append((-score, a_span, b_span, a_claim["claim_id"], b_claim["claim_id"], a_claim, b_claim))
    matched_a: set[str] = set()
    matched_b: set[str] = set()
    pairs = []
    for negative_score, _, _, a_id, b_id, a_claim, b_claim in sorted(candidates):
        if a_id in matched_a or b_id in matched_b:
            continue
        matched_a.add(a_id); matched_b.add(b_id)
        pairs.append({
            "reviewer_a_claim_id": a_id,
            "reviewer_b_claim_id": b_id,
            "reviewer_a_span": a_claim["source_span"],
            "reviewer_b_span": b_claim["source_span"],
            "iou": -negative_score,
            "exact_span": span_tuple(a_claim) == span_tuple(b_claim),
            "exact_excerpt": a_claim["source_excerpt"] == b_claim["source_excerpt"],
            "operation_kind_agreement": a_claim["boundary_operation_kind"] == b_claim["boundary_operation_kind"],
        })
    unmatched_a = [claim["claim_id"] for claim in a_claims if claim["claim_id"] not in matched_a]
    unmatched_b = [claim["claim_id"] for claim in b_claims if claim["claim_id"] not in matched_b]
    splits = [claim_id for claim_id, others in overlap_a.items() if len(others) >= 2]
    merges = [claim_id for claim_id, others in overlap_b.items() if len(others) >= 2]
    return {
        "pairs": pairs,
        "unmatched_reviewer_a_claim_ids": unmatched_a,
        "unmatched_reviewer_b_claim_ids": unmatched_b,
        "reviewer_a_one_to_many_claim_ids": sorted(splits),
        "reviewer_b_one_to_many_claim_ids": sorted(merges),
    }


def compute_agreement(a_submission: dict[str, Any], b_submission: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_submission(a_submission, "a")
    validate_submission(b_submission, "b")
    a_index = index_claims(a_submission["claims"])
    b_index = index_claims(b_submission["claims"])
    case_ids = sorted(set(a_index) | set(b_index))
    per_case = []
    all_pairs = []
    unmatched_a = []
    unmatched_b = []
    split_a = []
    split_b = []
    disagreement_cases = []
    for case_id in case_ids:
        aligned = align_case(a_index.get(case_id, []), b_index.get(case_id, []))
        pairs = aligned["pairs"]
        all_pairs.extend(pairs)
        unmatched_a.extend(aligned["unmatched_reviewer_a_claim_ids"])
        unmatched_b.extend(aligned["unmatched_reviewer_b_claim_ids"])
        split_a.extend(aligned["reviewer_a_one_to_many_claim_ids"])
        split_b.extend(aligned["reviewer_b_one_to_many_claim_ids"])
        exact = sum(pair["exact_span"] for pair in pairs)
        disagrees = (
            len(a_index.get(case_id, [])) != len(b_index.get(case_id, []))
            or exact != len(pairs)
            or aligned["unmatched_reviewer_a_claim_ids"]
            or aligned["unmatched_reviewer_b_claim_ids"]
            or aligned["reviewer_a_one_to_many_claim_ids"]
            or aligned["reviewer_b_one_to_many_claim_ids"]
        )
        if disagrees:
            disagreement_cases.append({
                "case_id": case_id,
                "reviewer_a_claims": a_index.get(case_id, []),
                "reviewer_b_claims": b_index.get(case_id, []),
                "alignment": aligned,
                "evidence_visible": False,
                "support_labels_visible": False,
            })
        per_case.append({
            "case_id": case_id,
            "reviewer_a_claim_count": len(a_index.get(case_id, [])),
            "reviewer_b_claim_count": len(b_index.get(case_id, [])),
            "matched_pair_count": len(pairs),
            "exact_span_match_count": exact,
            "unmatched_reviewer_a_count": len(aligned["unmatched_reviewer_a_claim_ids"]),
            "unmatched_reviewer_b_count": len(aligned["unmatched_reviewer_b_claim_ids"]),
            "reviewer_a_one_to_many_count": len(aligned["reviewer_a_one_to_many_claim_ids"]),
            "reviewer_b_one_to_many_count": len(aligned["reviewer_b_one_to_many_claim_ids"]),
            "complete_exact_agreement": not disagrees,
        })
    total_claims = len(a_submission["claims"]) + len(b_submission["claims"])
    exact_count = sum(pair["exact_span"] for pair in all_pairs)
    report = {
        "schema_version": 2,
        "report_id": "phase7.3.3-d-multi-claim-successor-boundary-agreement-v2",
        "status": "completed_frozen_before_adjudication",
        "inputs": {
            "reviewer_a_submission_sha256": sha(A_SUBMISSION),
            "reviewer_b_submission_sha256": sha(B_SUBMISSION),
            "worklist_sha256": sha(WORKLIST),
        },
        "case_count": len(case_ids),
        "reviewer_a_claim_count": len(a_submission["claims"]),
        "reviewer_b_claim_count": len(b_submission["claims"]),
        "matched_pair_count": len(all_pairs),
        "exact_span_match_count": exact_count,
        "exact_span_agreement_rate_among_matched": exact_count / len(all_pairs) if all_pairs else None,
        "symmetric_alignment_rate": 2 * len(all_pairs) / total_claims if total_claims else None,
        "unmatched_reviewer_a_claim_count": len(unmatched_a),
        "unmatched_reviewer_b_claim_count": len(unmatched_b),
        "reviewer_a_one_to_many_count": len(split_a),
        "reviewer_b_one_to_many_count": len(split_b),
        "operation_kind_agreement_count": sum(pair["operation_kind_agreement"] for pair in all_pairs),
        "exact_excerpt_agreement_count": sum(pair["exact_excerpt"] for pair in all_pairs),
        "per_case_exact_claim_count_agreement_count": sum(
            row["reviewer_a_claim_count"] == row["reviewer_b_claim_count"] for row in per_case
        ),
        "complete_exact_agreement_case_count": sum(row["complete_exact_agreement"] for row in per_case),
        "adjudication_case_count": len(disagreement_cases),
        "adjudication_required": bool(disagreement_cases),
        "per_case_diagnostics": per_case,
        "unmatched_claims": {
            "reviewer_a_claim_ids": unmatched_a,
            "reviewer_b_claim_ids": unmatched_b,
        },
        "split_merge_diagnostics": {
            "reviewer_a_one_to_many_claim_ids": split_a,
            "reviewer_b_one_to_many_claim_ids": split_b,
        },
        "measurement_limits": [
            "Agreement is computed from raw blind Reviewer A/B v2 submissions only.",
            "Agreement does not create Boundary Gold or authorize Support Review.",
            "Exact agreement does not replace the no-op Adjudication, Coverage QA, or Reference Freeze gates.",
            "No Evidence, Support label, old Gold, arm output, or confirmatory content was used.",
        ],
        "agreement_computed_before_adjudication": True,
        "adjudication_used": False,
        "coverage_qa_used": False,
        "support_labels_used": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    worklist = {
        "schema_version": 1,
        "worklist_id": "phase7.3.3-d-multi-claim-successor-boundary-adjudication-worklist-v1",
        "status": "frozen_from_boundary_agreement_v2",
        "agreement_report_sha256": None,
        "case_count": len(disagreement_cases),
        "disagreement_case_count": len(disagreement_cases),
        "cases": disagreement_cases,
        "evidence_present": False,
        "support_labels_present": False,
        "old_gold_present": False,
        "arm_outputs_present": False,
        "confirmatory_content_present": False,
    }
    return report, worklist


def run_fixtures() -> dict[str, Any]:
    def claim(reviewer: str, cid: str, n: int, start: int, end: int) -> dict[str, Any]:
        return {
            "case_id": cid, "claim_id": f"{cid}-{reviewer}-{n}", "source_span": {"start": start, "end": end},
            "source_excerpt": "x" * (end - start), "source_occurrence_index": 0, "source_unit_ids": [f"unit-{n:03d}"],
            "boundary_operation_kind": "reuse_unit", "reviewer": reviewer,
        }
    fixtures = []
    exact = align_case([claim("a", "c", 1, 0, 5)], [claim("b", "c", 1, 0, 5)])
    fixtures.append({"fixture_id": "exact", "status": "PASS" if exact["pairs"][0]["exact_span"] else "FAIL"})
    shifted = align_case([claim("a", "c", 1, 0, 5)], [claim("b", "c", 1, 1, 5)])
    fixtures.append({"fixture_id": "shifted", "status": "PASS" if shifted["pairs"][0]["iou"] == 0.8 and not shifted["pairs"][0]["exact_span"] else "FAIL"})
    unmatched = align_case([claim("a", "c", 1, 0, 5)], [claim("b", "c", 1, 6, 9)])
    fixtures.append({"fixture_id": "unmatched", "status": "PASS" if len(unmatched["pairs"]) == 0 and len(unmatched["unmatched_reviewer_a_claim_ids"]) == 1 else "FAIL"})
    split = align_case([claim("a", "c", 1, 0, 10)], [claim("b", "c", 1, 0, 5), claim("b", "c", 2, 5, 10)])
    fixtures.append({"fixture_id": "split", "status": "PASS" if len(split["reviewer_a_one_to_many_claim_ids"]) == 1 else "FAIL"})
    merge = align_case([claim("a", "c", 1, 0, 5), claim("a", "c", 2, 5, 10)], [claim("b", "c", 1, 0, 10)])
    fixtures.append({"fixture_id": "merge", "status": "PASS" if len(merge["reviewer_b_one_to_many_claim_ids"]) == 1 else "FAIL"})
    return {
        "schema_version": 2,
        "report_id": "phase7.3.3-d-multi-claim-successor-boundary-agreement-contract-fixtures-v2",
        "status": "PASS" if all(item["status"] == "PASS" for item in fixtures) else "FAIL",
        "passed": sum(item["status"] == "PASS" for item in fixtures),
        "total": len(fixtures),
        "fixtures": fixtures,
        "provider_called": False,
    }


def protocol_document() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-boundary-agreement-protocol-v2",
        "status": "frozen_before_agreement_computation",
        "object_of_measurement": "independent_atomic_claim_boundary_agreement",
        "inputs": {rel(path): sha(path) for path in EXPECTED},
        "alignment_policy": {
            "grouping_key": "case_id",
            "pair_score": "character_span_intersection_over_union",
            "candidate_pair_rule": "positive_character_overlap",
            "matching": "deterministic_greedy_descending_iou_then_spans_then_claim_ids",
            "exact_agreement": "identical_zero_based_end_exclusive_source_span",
            "split_merge_detection": "overlap_graph_degree_at_least_two",
        },
        "disagreement_worklist_policy": "any_count_span_unmatched_or_split_merge_disagreement",
        "no_adjudication_during_agreement": True,
        "no_gold_freeze_during_agreement": True,
        "evidence_visible": False,
        "support_labels_visible": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def manifest_document(protocol_sha: str, fixtures_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-boundary-agreement-manifest-v2",
        "status": "frozen_before_agreement_computation",
        "adapter": rel(SELF),
        "adapter_sha256": sha(SELF),
        "protocol_sha256": protocol_sha,
        "fixtures_sha256": fixtures_sha,
        "reviewer_a_submission_sha256": sha(A_SUBMISSION),
        "reviewer_b_submission_sha256": sha(B_SUBMISSION),
        "worklist_sha256": sha(WORKLIST),
        "provider_called": False,
        "deterministic": True,
        "adjudication_used": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def prepared_paths() -> list[Path]:
    return [PROTOCOL, FIXTURES, MANIFEST, PREP_RECEIPT]


def execution_paths() -> list[Path]:
    return [REPORT, ADJUDICATION_WORKLIST, OUTCOME, RECEIPT, STATE_OUT, READY_OUT]


def preflight() -> dict[str, Any]:
    missing = [rel(path) for path in EXPECTED if not path.exists()]
    mismatch = {rel(path): {"expected": digest, "actual": sha(path)} for path, digest in EXPECTED.items() if path.exists() and sha(path) != digest}
    state = load(STATE_IN) if STATE_IN.exists() else {}
    ready = load(READY_IN) if READY_IN.exists() else {}
    checks = {
        "required_inputs_present": not missing,
        "input_hashes_match": not mismatch,
        "state_authorizes_agreement": state.get("next_authorized_stage") == CURRENT_STAGE,
        "readiness_authorizes_agreement": ready.get("next_authorized_stage") == CURRENT_STAGE,
        "reviewers_completed": state.get("multi_claim_successor_boundary_reviewer_a_v2_completed") is True and state.get("multi_claim_successor_boundary_reviewer_b_v2_completed") is True,
        "confirmatory_closed": state.get("confirmatory_dataset_opened") is False,
        "runtime_unauthorized": state.get("runtime_integration_authorized") is False,
        "outputs_absent": all(not path.exists() for path in prepared_paths() + execution_paths()),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "missing": missing, "mismatches": mismatch}


def prepare() -> dict[str, Any]:
    before = preflight()
    if before["status"] != "PASS":
        raise ValueError("agreement_prepare_preflight_failed")
    fixtures = run_fixtures()
    if fixtures["status"] != "PASS":
        raise ValueError("agreement_fixtures_failed")
    protocol_bytes = jbytes(protocol_document())
    fixtures_bytes = jbytes(fixtures)
    protocol_sha = write_once(PROTOCOL, protocol_bytes)
    fixtures_sha = write_once(FIXTURES, fixtures_bytes)
    manifest_sha = write_once(MANIFEST, jbytes(manifest_document(protocol_sha, fixtures_sha)))
    receipt = {
        "schema_version": 2,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-boundary-agreement-prepare-receipt-v2",
        "status": "PASS",
        "protocol_sha256": protocol_sha,
        "fixtures_sha256": fixtures_sha,
        "manifest_sha256": manifest_sha,
        "fixtures_passed": fixtures["passed"],
        "fixtures_total": fixtures["total"],
        "provider_called": False,
        "next_authorized_stage": CURRENT_STAGE,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    receipt_sha = write_once(PREP_RECEIPT, jbytes(receipt))
    return {"status": "PASS", "protocol_sha256": protocol_sha, "manifest_sha256": manifest_sha, "prepare_receipt_sha256": receipt_sha}


def verify_prepare() -> dict[str, Any]:
    checks = {
        "protocol_exists": PROTOCOL.exists(),
        "fixtures_exist": FIXTURES.exists(),
        "manifest_exists": MANIFEST.exists(),
        "prepare_receipt_exists": PREP_RECEIPT.exists(),
    }
    if all(checks.values()):
        protocol = load(PROTOCOL); fixtures = load(FIXTURES); manifest = load(MANIFEST); receipt = load(PREP_RECEIPT)
        checks.update({
            "protocol_frozen": protocol.get("status") == "frozen_before_agreement_computation",
            "fixtures_pass": fixtures.get("status") == "PASS" and fixtures.get("passed") == fixtures.get("total") == 5,
            "adapter_hash": manifest.get("adapter_sha256") == sha(SELF),
            "protocol_hash": manifest.get("protocol_sha256") == sha(PROTOCOL),
            "fixtures_hash": manifest.get("fixtures_sha256") == sha(FIXTURES),
            "input_a_hash": manifest.get("reviewer_a_submission_sha256") == sha(A_SUBMISSION),
            "input_b_hash": manifest.get("reviewer_b_submission_sha256") == sha(B_SUBMISSION),
            "prepare_receipt_pass": receipt.get("status") == "PASS",
            "execution_outputs_absent": all(not path.exists() for path in execution_paths()),
        })
    failed = [name for name, ok in checks.items() if not ok]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def execute() -> dict[str, Any]:
    verified = verify_prepare()
    if verified["status"] != "PASS":
        raise ValueError("agreement_prepare_not_verified")
    state = load(STATE_IN); ready = load(READY_IN); manifest = load(MANIFEST)
    if state.get("next_authorized_stage") != CURRENT_STAGE or ready.get("next_authorized_stage") != CURRENT_STAGE:
        raise ValueError("agreement_stage_not_authorized")
    if manifest.get("adapter_sha256") != sha(SELF):
        raise ValueError("agreement_adapter_hash_mismatch")
    a_submission = load(A_SUBMISSION); b_submission = load(B_SUBMISSION)
    report, adjudication_worklist = compute_agreement(a_submission, b_submission)
    report["protocol_sha256"] = sha(PROTOCOL)
    report["manifest_sha256"] = sha(MANIFEST)
    report_sha = write_once(REPORT, jbytes(report))
    adjudication_worklist["agreement_report_sha256"] = report_sha
    worklist_sha = write_once(ADJUDICATION_WORKLIST, jbytes(adjudication_worklist))
    outcome = {
        "schema_version": 2,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-boundary-agreement-outcome-v2",
        "status": "boundary_agreement_v2_completed",
        "case_count": report["case_count"],
        "matched_pair_count": report["matched_pair_count"],
        "exact_span_match_count": report["exact_span_match_count"],
        "adjudication_case_count": report["adjudication_case_count"],
        "agreement_report_sha256": report_sha,
        "adjudication_worklist_sha256": worklist_sha,
        "boundary_gold_frozen": False,
        "next_authorized_stage": NEXT_STAGE,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    outcome_sha = write_once(OUTCOME, jbytes(outcome))
    lineage = {
        "multi_claim_successor_boundary_agreement_protocol_v2_sha256": sha(PROTOCOL),
        "multi_claim_successor_boundary_agreement_manifest_v2_sha256": sha(MANIFEST),
        "multi_claim_successor_boundary_agreement_report_v2_sha256": report_sha,
        "multi_claim_successor_boundary_adjudication_worklist_v1_sha256": worklist_sha,
        "multi_claim_successor_boundary_agreement_outcome_v2_sha256": outcome_sha,
    }
    state_out = copy.deepcopy(state)
    state_out.setdefault("artifact_lineage", {}).update(lineage)
    state_out.update({
        "schema_version": 36,
        "state_id": "phase7.3.3-d-support-stage-state-v36",
        "status": "multi_claim_successor_boundary_agreement_v2_completed",
        "next_authorized_stage": NEXT_STAGE,
        "multi_claim_successor_boundary_agreement_v2_completed": True,
        "multi_claim_successor_boundary_adjudication_case_count": report["adjudication_case_count"],
        "multi_claim_successor_boundary_gold_frozen": False,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    })
    ready_out = copy.deepcopy(ready)
    ready_out.setdefault("artifact_lineage", {}).update(lineage)
    ready_out.update({
        "schema_version": 47,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v47",
        "status": "multi_claim_successor_boundary_agreement_v2_completed",
        "next_authorized_stage": NEXT_STAGE,
        "successor_boundary_agreement_v2_completed": True,
        "successor_boundary_adjudication_case_count": report["adjudication_case_count"],
        "successor_boundary_gold_frozen": False,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    })
    state_sha = write_once(STATE_OUT, jbytes(state_out))
    ready_sha = write_once(READY_OUT, jbytes(ready_out))
    receipt = {
        "schema_version": 2,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-boundary-agreement-receipt-v2",
        "status": "PASS",
        "protocol_sha256": sha(PROTOCOL),
        "manifest_sha256": sha(MANIFEST),
        "agreement_report_sha256": report_sha,
        "adjudication_worklist_sha256": worklist_sha,
        "execution_outcome_sha256": outcome_sha,
        "state_sha256": state_sha,
        "readiness_sha256": ready_sha,
        "case_count": report["case_count"],
        "reviewer_a_claim_count": report["reviewer_a_claim_count"],
        "reviewer_b_claim_count": report["reviewer_b_claim_count"],
        "exact_span_match_count": report["exact_span_match_count"],
        "adjudication_case_count": report["adjudication_case_count"],
        "provider_called": False,
        "boundary_gold_frozen": False,
        "next_authorized_stage": NEXT_STAGE,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    receipt_sha = write_once(RECEIPT, jbytes(receipt))
    return {
        "status": "PASS",
        "cases": report["case_count"],
        "reviewer_a_claims": report["reviewer_a_claim_count"],
        "reviewer_b_claims": report["reviewer_b_claim_count"],
        "matched_pairs": report["matched_pair_count"],
        "exact_span_matches": report["exact_span_match_count"],
        "adjudication_cases": report["adjudication_case_count"],
        "agreement_report_sha256": report_sha,
        "receipt_sha256": receipt_sha,
        "state_sha256": state_sha,
        "readiness_sha256": ready_sha,
        "next_authorized_stage": NEXT_STAGE,
    }


def verify_execution() -> dict[str, Any]:
    required = execution_paths()
    checks = {f"exists:{path.name}": path.exists() for path in required}
    if all(checks.values()):
        report = load(REPORT); worklist = load(ADJUDICATION_WORKLIST); outcome = load(OUTCOME); receipt = load(RECEIPT); state = load(STATE_OUT); ready = load(READY_OUT)
        recomputed, recomputed_worklist = compute_agreement(load(A_SUBMISSION), load(B_SUBMISSION))
        recomputed["protocol_sha256"] = sha(PROTOCOL); recomputed["manifest_sha256"] = sha(MANIFEST)
        checks.update({
            "report_replay": report == recomputed,
            "worklist_report_lineage": worklist.get("agreement_report_sha256") == sha(REPORT),
            "worklist_replay": {**recomputed_worklist, "agreement_report_sha256": sha(REPORT)} == worklist,
            "perfect_exact_agreement": report.get("matched_pair_count") == report.get("exact_span_match_count") == 240,
            "no_unmatched": report.get("unmatched_reviewer_a_claim_count") == report.get("unmatched_reviewer_b_claim_count") == 0,
            "no_split_merge": report.get("reviewer_a_one_to_many_count") == report.get("reviewer_b_one_to_many_count") == 0,
            "empty_adjudication_worklist": worklist.get("case_count") == 0 and worklist.get("cases") == [],
            "outcome_not_gold": outcome.get("boundary_gold_frozen") is False,
            "receipt_pass": receipt.get("status") == "PASS" and receipt.get("agreement_report_sha256") == sha(REPORT),
            "state_next_gate": state.get("next_authorized_stage") == NEXT_STAGE and state.get("multi_claim_successor_boundary_gold_frozen") is False,
            "readiness_next_gate": ready.get("next_authorized_stage") == NEXT_STAGE and ready.get("successor_boundary_gold_frozen") is False,
            "confirmatory_closed": all(x.get("confirmatory_dataset_opened") is False for x in (report, outcome, receipt, state, ready)),
            "runtime_unauthorized": all(x.get("runtime_integration_authorized") is False for x in (report, outcome, receipt, state, ready)),
        })
    failed = [name for name, ok in checks.items() if not ok]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_OUT).get("next_authorized_stage") if STATE_OUT.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--fixtures", action="store_true")
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--verify-prepare", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--verify-execution", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
    elif args.fixtures:
        result = run_fixtures()
    elif args.prepare:
        result = prepare()
    elif args.verify_prepare:
        result = verify_prepare()
    elif args.execute:
        result = execute()
    else:
        result = verify_execution()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
