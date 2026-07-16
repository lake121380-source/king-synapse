#!/usr/bin/env python3
"""Deterministic Phase 7.3.3-D1 Coverage QA Rerun v1."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import phase7_boundary_coverage_v4 as base

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
REPORTS = ROOT / "crates/eval/reports"

PROTOCOL = CONFIG / "phase7_3_3_d_boundary_coverage_rerun_protocol_v1.json"
POLICY = CONFIG / "phase7_3_3_d_boundary_coverage_policy_v1.json"
INITIAL_REPORT = REPORTS / "phase7_3_3_d_boundary_coverage_report_v4.json"
GAP_WORKLIST = REPORTS / "phase7_3_3_d_boundary_coverage_gap_worklist_v1.json"
AGREEMENT = REPORTS / "phase7_3_3_d_non_claim_accounting_agreement_q_g_v1.json"
REVIEWER_Q = REPORTS / "phase7_3_3_d_non_claim_accounting_reviewer_q_submission_v1.json"
REVIEWER_G = REPORTS / "phase7_3_3_d_non_claim_accounting_reviewer_g_submission_v1.json"
B3_SUBMISSION = REPORTS / "phase7_3_3_d_non_claim_adjudication_submission_v1.json"
B4_SUBMISSION = REPORTS / "phase7_3_3_d_boundary_omission_resolution_submission_v2.json"
CORRECTION_WORKLIST = REPORTS / "phase7_3_3_d_boundary_correction_worklist_v2.json"
CORRECTION_SUBMISSION = REPORTS / "phase7_3_3_d_boundary_correction_noop_submission_v1.json"
READINESS_V11 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v11.json"

MANIFEST = REPORTS / "phase7_3_3_d_boundary_coverage_rerun_manifest_v1.json"
ACCOUNTING = REPORTS / "phase7_3_3_d_explicit_non_claim_accounting_v1.json"
REPORT = REPORTS / "phase7_3_3_d_boundary_coverage_rerun_report_v1.json"
RESIDUAL = REPORTS / "phase7_3_3_d_boundary_coverage_rerun_gap_worklist_v1.json"
READINESS_V12 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v12.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: Any) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{path.relative_to(ROOT)}")
        return hashlib.sha256(data).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hashlib.sha256(data).hexdigest()


def indexed(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        value = item.get(key)
        if not isinstance(value, str) or not value or value in result:
            raise ValueError(f"invalid_or_duplicate_{key}:{value}")
        result[value] = item
    return result


def validate_and_construct() -> tuple[dict[str, Any], dict[str, Any]]:
    paths = (
        PROTOCOL, POLICY, INITIAL_REPORT, GAP_WORKLIST, AGREEMENT, REVIEWER_Q,
        REVIEWER_G, B3_SUBMISSION, B4_SUBMISSION, CORRECTION_WORKLIST,
        CORRECTION_SUBMISSION, READINESS_V11, base.PACKET, base.WORKLIST,
        base.SUBMISSION, base.DECISION_LOG, base.EXECUTION_RESULT,
    )
    for path in paths:
        if not path.is_file():
            raise ValueError(f"required_frozen_input_missing:{path.relative_to(ROOT)}")

    protocol = load(PROTOCOL)
    initial = load(INITIAL_REPORT)
    worklist = load(GAP_WORKLIST)
    agreement = load(AGREEMENT)
    reviewer_q = load(REVIEWER_Q)
    reviewer_g = load(REVIEWER_G)
    b3 = load(B3_SUBMISSION)
    b4 = load(B4_SUBMISSION)
    correction_worklist = load(CORRECTION_WORKLIST)
    correction = load(CORRECTION_SUBMISSION)
    readiness = load(READINESS_V11)

    gaps = indexed(worklist.get("gaps", []), "gap_id")
    rows = indexed(agreement.get("rows", []), "gap_id")
    q_decisions = indexed(reviewer_q.get("decisions", []), "gap_id")
    g_decisions = indexed(reviewer_g.get("decisions", []), "gap_id")
    b3_decisions = indexed(b3.get("decisions", []), "gap_id")
    b4_decisions = indexed(b4.get("decisions", []), "gap_id")
    non_exact_ids = {gap_id for gap_id, row in rows.items() if row.get("agreement_status") != "exact_agreement"}

    base_hashes = base.verify_hashes()
    packet = base.load(base.PACKET)
    boundary_worklist = base.load(base.WORKLIST)
    boundary_submission = base.load(base.SUBMISSION)
    order, anchors, worklist_anchors = base.indexes(packet, boundary_worklist)
    claims_by, structural = base.validate(order, anchors, worklist_anchors, boundary_submission)

    checks = {
        "protocol_offline_deterministic": protocol.get("execution_mode") == "offline_deterministic",
        "initial_coverage_failed_only_for_non_claim_accounting": initial.get("status") == "failed_non_claim_accounting_required" and initial.get("freeze_gate_failures") == ["eligible_gap_characters"],
        "initial_gap_worklist_hash_matches": worklist.get("coverage_report_sha256") == sha256(INITIAL_REPORT),
        "initial_gap_count_is_84": worklist.get("gap_count") == 84 and len(gaps) == 84,
        "initial_eligible_gap_characters_is_206": worklist.get("eligible_gap_character_count") == 206,
        "agreement_hashes_match_reviewers": agreement.get("reviewer_q_submission_sha256") == sha256(REVIEWER_Q) and agreement.get("reviewer_g_submission_sha256") == sha256(REVIEWER_G),
        "agreement_gap_set_matches_worklist": set(rows) == set(gaps) and agreement.get("gap_count") == 84,
        "reviewer_gap_sets_match_worklist": set(q_decisions) == set(gaps) and set(g_decisions) == set(gaps),
        "agreement_rows_replay_reviewer_submissions": all(row.get("reviewer_q", {}).get("classification") == q_decisions[gap_id].get("classification") and row.get("reviewer_q", {}).get("reason_code") == q_decisions[gap_id].get("reason_code") and row.get("reviewer_g", {}).get("classification") == g_decisions[gap_id].get("classification") and row.get("reviewer_g", {}).get("reason_code") == g_decisions[gap_id].get("reason_code") for gap_id, row in rows.items()),
        "non_exact_gap_count_is_16": len(non_exact_ids) == 16,
        "b3_decision_set_equals_non_exact_set": set(b3_decisions) == non_exact_ids and b3.get("decision_count") == 16,
        "b3_agreement_hash_matches": b3.get("agreement_sha256") == sha256(AGREEMENT),
        "b4_b3_submission_hash_matches": b4.get("b3_submission_sha256") == sha256(B3_SUBMISSION),
        "correction_worklist_source_hash_matches_b4": correction_worklist.get("source_submission_sha256") == sha256(B4_SUBMISSION),
        "correction_worklist_is_empty": correction_worklist.get("candidate_count") == 0 and correction_worklist.get("candidates") == [],
        "correction_submission_is_verified_noop": correction.get("status") == "completed_noop_boundary_correction" and correction.get("source_b4_submission_sha256") == sha256(B4_SUBMISSION) and correction.get("source_worklist_sha256") == sha256(CORRECTION_WORKLIST) and correction.get("zero_candidate_lineage_validated") is True and correction.get("input_candidate_count") == 0 and correction.get("corrected_candidate_count") == 0 and correction.get("boundary_changes_performed") is False,
        "readiness_v11_authorizes_rerun": readiness.get("next_authorized_stage") == "coverage_qa_rerun" and readiness.get("gates", {}).get("coverage_qa_rerun_allowed") is True and readiness.get("gates", {}).get("boundary_gold_frozen") is False and readiness.get("gates", {}).get("support_review_allowed") is False,
        "readiness_v11_correction_hash_matches": readiness.get("artifact_lineage", {}).get("boundary_correction_submission_sha256") == sha256(CORRECTION_SUBMISSION),
        "boundary_claim_structural_validation_clean": all(structural.get(name) == 0 for name in ("invalid_span_count", "blank_or_zero_length_claim_count", "claim_text_mismatch_count", "source_occurrence_mismatch_count", "unknown_anchor_count", "missing_anchor_count", "unknown_reviewer_claim_id_count", "source_metadata_mismatch_count", "duplicate_adjudicated_claim_id_count", "sequential_claim_id_failure_count", "overlap_characters")),
        "held_out_not_accessed": reviewer_q.get("held_out_accessed") is False and reviewer_g.get("held_out_accessed") is False and b3.get("held_out_accessed") is False and b4.get("held_out_accessed") is False and correction.get("held_out_accessed") is False and readiness.get("held_out_accessed") is False,
    }

    pre_b4: dict[str, dict[str, Any]] = {}
    for gap_id in gaps:
        row = rows[gap_id]
        status = row.get("agreement_status")
        if status == "exact_agreement":
            q = row["reviewer_q"]
            g = row["reviewer_g"]
            if q.get("classification") != g.get("classification") or q.get("reason_code") != g.get("reason_code"):
                raise ValueError(f"invalid_exact_agreement:{gap_id}")
            pre_b4[gap_id] = {
                "classification": q.get("classification"),
                "reason_code": q.get("reason_code"),
                "rationale": f"Reviewer Q: {q.get('rationale')} Reviewer G: {g.get('rationale')}",
                "source": "exact_agreement",
            }
        else:
            decision = b3_decisions[gap_id]
            pre_b4[gap_id] = {
                "classification": decision.get("final_classification"),
                "reason_code": decision.get("final_reason_code"),
                "rationale": decision.get("rationale"),
                "source": "b3_adjudication",
            }

    pre_b4_candidates = {gap_id for gap_id, item in pre_b4.items() if item["classification"] == "boundary_omission_candidate"}
    checks["pre_b4_candidate_count_is_4"] = len(pre_b4_candidates) == 4
    checks["b4_decision_set_equals_pre_b4_candidates"] = set(b4_decisions) == pre_b4_candidates and b4.get("decision_count") == 4
    checks["b4_resolves_all_candidates_as_non_claim"] = all(item.get("resolution") == "resolved_as_non_claim" and item.get("severity") is None for item in b4_decisions.values())

    spans: list[dict[str, Any]] = []
    source_counts = Counter()
    for gap_id, gap in gaps.items():
        key = (gap.get("case_id"), gap.get("anchor_id"))
        anchor = anchors.get(key)
        span = gap.get("source_span", {})
        start, end = span.get("start"), span.get("end")
        if anchor is None or not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or start < 0 or end <= start or end > len(anchor["source_text"]):
            raise ValueError(f"invalid_frozen_gap_span:{gap_id}")
        exact = anchor["source_text"][start:end]
        if exact != gap.get("gap_text") or text_sha256(exact) != gap.get("gap_text_sha256"):
            raise ValueError(f"frozen_gap_text_mismatch:{gap_id}")
        if gap_id in b4_decisions:
            final = {
                "classification": "explicit_non_claim",
                "reason_code": "other_explained_non_claim",
                "rationale": b4_decisions[gap_id].get("rationale"),
                "source": "b4_resolved_as_non_claim",
                "reason_code_derivation": "deterministic_fallback_for_b4_resolution_without_reason_code",
            }
        else:
            final = pre_b4[gap_id]
            if final["classification"] != "explicit_non_claim":
                raise ValueError(f"unresolved_boundary_omission_candidate:{gap_id}")
        if final.get("reason_code") is None or not isinstance(final.get("rationale"), str) or not final["rationale"].strip():
            raise ValueError(f"invalid_final_non_claim_metadata:{gap_id}")
        source_counts[final["source"]] += 1
        spans.append({
            "gap_id": gap_id,
            "case_id": gap["case_id"],
            "anchor_id": gap["anchor_id"],
            "source_field": gap["source_field"],
            "source_index": gap["source_index"],
            "source_text_sha256": gap["source_text_sha256"],
            "source_span": gap["source_span"],
            "gap_text": gap["gap_text"],
            "gap_text_sha256": gap["gap_text_sha256"],
            "classification": "explicit_non_claim",
            "reason_code": final["reason_code"],
            "rationale": final["rationale"],
            "accounting_source": final["source"],
            **({"reason_code_derivation": final["reason_code_derivation"]} if "reason_code_derivation" in final else {}),
        })

    checks["all_84_gaps_resolved_as_explicit_non_claim"] = len(spans) == 84 and all(item["classification"] == "explicit_non_claim" for item in spans)
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise ValueError("coverage_rerun_lineage_validation_failed:" + ",".join(failures))

    accounting = {
        "schema_version": 1,
        "accounting_id": "phase7.3.3-d1-explicit-non-claim-accounting-v1",
        "status": "deterministically_constructed_from_frozen_reviews_and_resolutions",
        "source_gap_worklist_sha256": sha256(GAP_WORKLIST),
        "source_agreement_sha256": sha256(AGREEMENT),
        "source_b3_submission_sha256": sha256(B3_SUBMISSION),
        "source_b4_submission_sha256": sha256(B4_SUBMISSION),
        "source_boundary_correction_submission_sha256": sha256(CORRECTION_SUBMISSION),
        "span_count": len(spans),
        "accounting_source_counts": dict(sorted(source_counts.items())),
        "b4_reason_code_fallback": "other_explained_non_claim",
        "spans": spans,
        "semantic_inference_during_construction": False,
        "provider_called": False,
        "held_out_accessed": False,
    }
    context = {
        "checks": checks,
        "base_hashes": base_hashes,
        "order": order,
        "anchors": anchors,
        "claims_by": claims_by,
        "structural": structural,
    }
    return accounting, context


def protocol_exclusions(order: list[tuple[str, str]], anchors: dict[tuple[str, str], dict[str, Any]], claims_by: dict[tuple[str, str], list[dict[str, Any]]], nonclaims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int, int]:
    nc_by: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in nonclaims:
        nc_by[(row["case_id"], row["anchor_id"])].append(row)
    exclusions: list[dict[str, Any]] = []
    unclassified = 0
    nonclaim_overlap = 0
    accounted = 0
    for key in order:
        anchor = anchors[key]
        text = anchor["source_text"]
        cd = [0] * len(text)
        nd = [0] * len(text)
        for claim in claims_by.get(key, []):
            for index in range(claim["source_span"]["start"], claim["source_span"]["end"]):
                cd[index] += 1
        for row in nc_by.get(key, []):
            for index in range(row["source_span"]["start"], row["source_span"]["end"]):
                nd[index] += 1
        nonclaim_overlap += sum(depth > 1 for depth in nd)
        cursor = 0
        while cursor < len(text):
            if cd[cursor] or nd[cursor]:
                accounted += 1
                cursor += 1
                continue
            start = cursor
            while cursor < len(text) and cd[cursor] == 0 and nd[cursor] == 0:
                cursor += 1
            segment = text[start:cursor]
            eligible = sum(not character.isspace() for character in segment)
            if eligible:
                unclassified += len(segment)
            else:
                accounted += len(segment)
                exclusions.append({
                    "case_id": key[0],
                    "anchor_id": key[1],
                    "source_text_sha256": anchor["source_text_sha256"],
                    "source_span": {"start": start, "end": cursor},
                    "excluded_text": segment,
                    "character_count": len(segment),
                    "reason_code": "whitespace_only_protocol_excluded",
                })
    return exclusions, unclassified, nonclaim_overlap, accounted


def expected_manifest() -> dict[str, Any]:
    accounting, context = validate_and_construct()
    source_paths = {
        "adapter": Path(__file__),
        "base_coverage_adapter": Path(base.__file__),
        "protocol": PROTOCOL,
        "coverage_policy": POLICY,
        "initial_coverage_report": INITIAL_REPORT,
        "initial_gap_worklist": GAP_WORKLIST,
        "agreement": AGREEMENT,
        "reviewer_q_submission": REVIEWER_Q,
        "reviewer_g_submission": REVIEWER_G,
        "b3_submission": B3_SUBMISSION,
        "b4_submission": B4_SUBMISSION,
        "boundary_correction_worklist": CORRECTION_WORKLIST,
        "boundary_correction_submission": CORRECTION_SUBMISSION,
        "readiness_v11": READINESS_V11,
        "boundary_packet": base.PACKET,
        "boundary_adjudication_worklist": base.WORKLIST,
        "boundary_adjudication_submission": base.SUBMISSION,
    }
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d1-boundary-coverage-rerun-manifest-v1",
        "status": "frozen_not_started",
        "execution_mode": "offline_deterministic",
        "artifact_lineage": {name + "_sha256": sha256(path) for name, path in source_paths.items()},
        "validated_input_gap_count": accounting["span_count"],
        "validated_claim_count": context["structural"]["claim_count"],
        "lineage_checks": context["checks"],
        "expected_outputs": {
            "explicit_non_claim_accounting": ACCOUNTING.relative_to(ROOT).as_posix(),
            "coverage_rerun_report": REPORT.relative_to(ROOT).as_posix(),
            "residual_gap_worklist": RESIDUAL.relative_to(ROOT).as_posix(),
            "readiness_v12": READINESS_V12.relative_to(ROOT).as_posix(),
        },
        "provider_call_allowed": False,
        "new_semantic_classification_allowed": False,
        "boundary_mutation_allowed": False,
        "boundary_gold_freeze_allowed_in_this_stage": False,
        "support_review_allowed": False,
        "held_out_access_allowed": False,
    }


def execute() -> dict[str, Any]:
    accounting, context = validate_and_construct()
    if not MANIFEST.is_file():
        raise ValueError("frozen_manifest_required_before_execution")
    if load(MANIFEST) != expected_manifest():
        raise ValueError("frozen_manifest_does_not_match_current_inputs_or_adapter")
    manifest_hash = sha256(MANIFEST)
    accounting = {**accounting, "coverage_rerun_manifest_sha256": manifest_hash}
    accounting_hash = write_once(ACCOUNTING, accounting)

    coverage, residual_gaps = base.coverage(context["order"], context["anchors"], context["claims_by"], accounting["spans"])
    exclusions, unclassified, nonclaim_overlap, accounted = protocol_exclusions(context["order"], context["anchors"], context["claims_by"], accounting["spans"])
    metrics = coverage["metrics"]
    structural = context["structural"]
    lineage_failure_count = sum(not passed for passed in context["checks"].values())
    gate_values = {
        "invalid_claim_span_count": structural["invalid_span_count"],
        "claim_text_mismatch_count": structural["claim_text_mismatch_count"],
        "claim_overlap_characters": structural["overlap_characters"],
        "invalid_non_claim_span_count": coverage["invalid_nonclaim_span_count"],
        "invalid_non_claim_metadata_count": coverage["invalid_nonclaim_metadata_count"],
        "invalid_non_claim_reason_code_count": coverage["invalid_nonclaim_reason_code_count"],
        "non_claim_overlap_characters": nonclaim_overlap,
        "claim_non_claim_conflict_characters": metrics["claim_non_claim_conflict_characters"],
        "eligible_gap_characters": metrics["eligible_gap_characters"],
        "unclassified_characters": unclassified,
        "lineage_failure_count": lineage_failure_count,
    }
    failures = [name for name, value in gate_values.items() if value != 0]
    passed = not failures
    total = metrics["total_anchor_characters"]
    report = {
        "schema_version": 1,
        "report_id": "phase7.3.3-d1-boundary-coverage-rerun-report-v1",
        "status": "passed" if passed else "failed",
        "protocol_id": load(PROTOCOL)["protocol_id"],
        "coverage_rerun_manifest_sha256": manifest_hash,
        "explicit_non_claim_accounting_sha256": accounting_hash,
        "artifact_lineage": load(MANIFEST)["artifact_lineage"],
        "lineage_checks": context["checks"],
        "structural_validation": structural,
        "coverage": coverage,
        "three_class_accounting": {
            "total_anchor_characters": total,
            "claim_characters": metrics["covered_characters"],
            "explicit_non_claim_characters": metrics["declared_non_claim_characters"],
            "protocol_excluded_characters": sum(item["character_count"] for item in exclusions),
            "protocol_excluded_span_count": len(exclusions),
            "protocol_excluded_spans": exclusions,
            "unclassified_characters": unclassified,
            "accounted_characters": accounted,
            "accounting_ratio": accounted / total if total else 1.0,
        },
        "freeze_gate_values": gate_values,
        "freeze_gate_failures": failures,
        "freeze_gates_passed": passed,
        "coverage_qa_rerun_completed": True,
        "coverage_qa_passed": passed,
        "boundary_gold_freeze_allowed": passed,
        "boundary_gold_frozen": False,
        "support_review_allowed": False,
        "provider_called": False,
        "new_semantic_classification_performed": False,
        "held_out_accessed": False,
    }
    report_hash = write_once(REPORT, report)
    residual = {
        "schema_version": 1,
        "worklist_id": "phase7.3.3-d1-boundary-coverage-rerun-gap-worklist-v1",
        "status": "no_unaccounted_eligible_gaps" if passed else "coverage_rerun_failures_require_review",
        "coverage_rerun_manifest_sha256": manifest_hash,
        "coverage_rerun_report_sha256": report_hash,
        "residual_gap_count": len(residual_gaps),
        "eligible_gap_character_count": metrics["eligible_gap_characters"],
        "gaps": residual_gaps,
        "automatic_repair_performed": False,
        "provider_called": False,
        "held_out_accessed": False,
    }
    residual_hash = write_once(RESIDUAL, residual)
    readiness = {
        "schema_version": 12,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v12",
        "status": "coverage_qa_rerun_passed_boundary_gold_freeze_authorized" if passed else "coverage_qa_rerun_failed_boundary_gold_blocked",
        "artifact_lineage": {
            **load(READINESS_V11)["artifact_lineage"],
            "readiness_v11_sha256": sha256(READINESS_V11),
            "coverage_rerun_protocol_sha256": sha256(PROTOCOL),
            "coverage_rerun_manifest_sha256": manifest_hash,
            "explicit_non_claim_accounting_sha256": accounting_hash,
            "coverage_rerun_report_sha256": report_hash,
            "coverage_rerun_residual_worklist_sha256": residual_hash,
        },
        "gates": {
            **load(READINESS_V11)["gates"],
            "coverage_qa_rerun_allowed": True,
            "coverage_qa_rerun_completed": True,
            "coverage_qa_passed": passed,
            "boundary_gold_freeze_allowed": passed,
            "boundary_gold_frozen": False,
            "support_review_allowed": False,
            "held_out_accessed": False,
        },
        "coverage_metrics": {
            "total_anchor_characters": total,
            "eligible_non_whitespace_characters": metrics["eligible_non_whitespace_characters"],
            "claim_characters": metrics["covered_characters"],
            "explicit_non_claim_characters": metrics["declared_non_claim_characters"],
            "protocol_excluded_characters": sum(item["character_count"] for item in exclusions),
            "eligible_gap_characters": metrics["eligible_gap_characters"],
            "unclassified_characters": unclassified,
            "overlap_conflicts": structural["overlap_characters"] + nonclaim_overlap + metrics["claim_non_claim_conflict_characters"],
            "lineage_failures": lineage_failure_count,
            "accounting_ratio": accounted / total if total else 1.0,
        },
        "next_authorized_stage": "boundary_gold_freeze" if passed else "coverage_qa_failure_review",
        "coverage_qa_rerun_performed": True,
        "automatic_boundary_repair_performed": False,
        "boundary_changes_performed": False,
        "boundary_gold_frozen": False,
        "support_review_allowed": False,
        "held_out_accessed": False,
    }
    readiness_hash = write_once(READINESS_V12, readiness)
    return {
        "status": report["status"],
        "manifest_sha256": manifest_hash,
        "explicit_non_claim_accounting_sha256": accounting_hash,
        "coverage_rerun_report_sha256": report_hash,
        "residual_gap_worklist_sha256": residual_hash,
        "readiness_v12_sha256": readiness_hash,
        "metrics": readiness["coverage_metrics"],
        "freeze_gate_failures": failures,
        "boundary_gold_freeze_allowed": passed,
        "boundary_gold_frozen": False,
        "support_review_allowed": False,
        "provider_called": False,
        "held_out_accessed": False,
    }


def verify() -> dict[str, Any]:
    accounting, context = validate_and_construct()
    coverage, residual = base.coverage(context["order"], context["anchors"], context["claims_by"], accounting["spans"])
    exclusions, unclassified, nonclaim_overlap, accounted = protocol_exclusions(context["order"], context["anchors"], context["claims_by"], accounting["spans"])
    manifest_matches = not MANIFEST.exists() or load(MANIFEST) == expected_manifest()
    output_hashes = {name: sha256(path) if path.exists() else None for name, path in {"manifest": MANIFEST, "accounting": ACCOUNTING, "report": REPORT, "residual": RESIDUAL, "readiness_v12": READINESS_V12}.items()}
    return {
        "status": "verified",
        "all_lineage_checks_passed": all(context["checks"].values()),
        "projected_explicit_non_claim_span_count": accounting["span_count"],
        "projected_metrics": {
            **coverage["metrics"],
            "protocol_excluded_characters": sum(item["character_count"] for item in exclusions),
            "unclassified_characters": unclassified,
            "non_claim_overlap_characters": nonclaim_overlap,
            "accounted_characters": accounted,
            "residual_gap_count": len(residual),
        },
        "manifest_matches_current_inputs": manifest_matches,
        "output_hashes": output_hashes,
        "provider_called": False,
        "held_out_accessed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-inputs", action="store_true")
    group.add_argument("--freeze-manifest", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.verify_inputs:
        result = verify()
    elif args.freeze_manifest:
        manifest = expected_manifest()
        result = {
            "status": "coverage_qa_rerun_manifest_frozen_not_started",
            "manifest_sha256": write_once(MANIFEST, manifest),
            "validated_input_gap_count": manifest["validated_input_gap_count"],
            "provider_called": False,
            "held_out_accessed": False,
        }
    else:
        result = execute()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())