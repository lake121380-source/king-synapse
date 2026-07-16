#!/usr/bin/env python3
"""Freeze the authoritative Phase 7.3.3-A negative-result analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase7_execution_attempt_log import read_entries

ROOT = Path(__file__).resolve().parents[2]
EXECUTION_REPORT = ROOT / "crates/eval/reports/phase7_3_3_a_atomic_judge_control_execution.json"
MANIFEST = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_v2.json"
MANIFEST_RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_v2_receipt.json"
OUTPUT = ROOT / "crates/eval/reports/phase7_3_3_a_negative_result_analysis.json"
RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_a_negative_result_analysis_receipt.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp = Path(handle.name)
    temp.replace(path)


def verify_inputs() -> tuple[dict[str, Any], dict[str, Any], str, str]:
    if not EXECUTION_REPORT.exists() or not MANIFEST.exists() or not MANIFEST_RECEIPT.exists():
        raise ValueError("authoritative_execution_artifact_missing")
    manifest_hash = sha256_file(MANIFEST)
    receipt = json.loads(MANIFEST_RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("execution_manifest_sha256") != manifest_hash:
        raise ValueError("manifest_receipt_hash_mismatch")
    report_hash = sha256_file(EXECUTION_REPORT)
    report = json.loads(EXECUTION_REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if report.get("execution_manifest_sha256") != manifest_hash:
        raise ValueError("report_manifest_hash_mismatch")
    completed = [entry for entry in read_entries() if entry.get("event_type") == "attempt_completed" and entry.get("manifest_sha256") == manifest_hash]
    if len(completed) != 1:
        raise ValueError("expected_one_completed_attempt")
    if completed[0].get("execution_report_sha256") != report_hash:
        raise ValueError("attempt_log_report_hash_mismatch")
    return report, manifest, report_hash, manifest_hash


def build_analysis() -> dict[str, Any]:
    report, manifest, report_hash, manifest_hash = verify_inputs()
    rows = report["results"]
    failure_counts = Counter(row.get("failure_code", "none") for row in rows if row.get("status") != "valid")
    lane_counts = Counter(row["evaluation_lane"] for row in rows)
    received_count = sum(bool(row.get("response_sha256")) for row in rows)
    invalid_count = sum(row.get("status") != "valid" for row in rows)
    source_span_failures = failure_counts.get("source_span_text_mismatch", 0)
    systematic = bool(rows) and source_span_failures == len(rows)
    return {
        "schema_version": 1,
        "analysis_id": "phase7.3.3-a-first-real-atomic-judge-negative-result-analysis-v1",
        "phase": "Phase 7.3.3-A First Real Atomic Judge Negative Result Analysis",
        "generated_at": now(),
        "status": "frozen_negative_result",
        "authoritative_execution": {
            "execution_report_sha256": report_hash,
            "execution_manifest_sha256": manifest_hash,
            "attempt_log_completion_verified": True,
            "provider_base_url": report["provider_base_url"],
            "model_requested": report["model_requested"],
            "resolved_model": report["resolved_model"],
            "temperature": report["temperature"],
            "top_p": report["top_p"],
            "first_returned_output_authoritative": report["first_returned_output_authoritative"],
        },
        "observations": {
            "case_count": len(rows),
            "provider_response_received_count": received_count,
            "valid_output_count": report["valid_output_count"],
            "invalid_output_count": invalid_count,
            "failure_code_counts": dict(sorted(failure_counts.items())),
            "evaluation_lane_counts": dict(sorted(lane_counts.items())),
            "systematic_source_span_text_mismatch": systematic,
            "transport_ready_for_this_execution": received_count == len(rows),
        },
        "measurement_validity": {
            "segmentation_contract_passed": False,
            "local_support_classification_assessable": False,
            "candidate_aggregation_assessable": False,
            "candidate_entry_criteria_assessable": False,
            "macro_recall_reportable": False,
            "prediction_collapse_reportable": False,
            "failure_stage": "strict_source_span_validation_before_local_label_scoring",
        },
        "supported_conclusions": [
            "The configured credential, relay transport, and requested gpt-4.1 model returned one authoritative response for every frozen control case.",
            "The frozen end-to-end protocol failed systematically at exact source-span text validation.",
            "The combined segmentation-and-classification task did not produce any scoreable Atomic Claim output.",
            "The execution infrastructure distinguished this experimental failure from the earlier HTTP 401 transport failure.",
        ],
        "prohibited_conclusions": [
            "gpt-4.1 lacks Atomic Claim support-classification capability",
            "Atomic Claim measurement does or does not improve four-label discrimination",
            "the deterministic Aggregator is accurate or inaccurate on real model judgments",
            "held-out or design-case generalization has been demonstrated",
        ],
        "identified_confound": {
            "name": "segmentation_classification_entanglement",
            "description": "The Judge was required to calculate exact UTF-8 source spans and classify evidence support in one response. Systematic span failure prevented observation of the semantic classification variable.",
        },
        "next_stage_gate": {
            "recommended_stage": "Phase 7.3.3-C Segmentation-Controlled Atomic Claim Classification",
            "required_change": "Freeze protocol-owned Atomic Claim boundaries and require the Judge to emit local support judgments only.",
            "same_manifest_retry_authorized": False,
            "original_negative_result_must_remain_immutable": True,
            "prompt_or_parser_change_requires_new_manifest": True,
            "design_cases_authorized": False,
            "held_out_authorized": False,
        },
        "guards": {
            "raw_provider_responses_stored": False,
            "api_key_recorded": False,
            "original_execution_report_modified": False,
            "original_manifest_modified": False,
            "result_driven_retry_performed": False,
        },
        "artifact_sha256": {
            "execution_report": report_hash,
            "execution_manifest": manifest_hash,
            "execution_policy": manifest["artifact_sha256"]["execution_policy"],
            "atomic_protocol": manifest["artifact_sha256"]["protocol"],
            "atomic_prompt": manifest["artifact_sha256"]["prompt"],
            "original_controls": manifest["artifact_sha256"]["original_balanced_controls"],
            "partial_supplement": manifest["artifact_sha256"]["partial_claim_supplement"],
        },
    }


def verify_existing() -> str:
    if not OUTPUT.exists() or not RECEIPT.exists():
        raise ValueError("analysis_or_receipt_missing")
    digest = sha256_file(OUTPUT)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("negative_result_analysis_sha256") != digest:
        raise ValueError("analysis_receipt_hash_mismatch")
    analysis = json.loads(OUTPUT.read_text(encoding="utf-8"))
    _, _, report_hash, manifest_hash = verify_inputs()
    if analysis["artifact_sha256"]["execution_report"] != report_hash:
        raise ValueError("analysis_execution_report_changed")
    if analysis["artifact_sha256"]["execution_manifest"] != manifest_hash:
        raise ValueError("analysis_execution_manifest_changed")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify or OUTPUT.exists() or RECEIPT.exists():
        digest = verify_existing()
        print(f"negative result analysis verified: {digest}")
        return 0
    analysis = build_analysis()
    atomic_write(OUTPUT, analysis)
    digest = sha256_file(OUTPUT)
    atomic_write(RECEIPT, {
        "schema_version": 1,
        "analysis_id": analysis["analysis_id"],
        "negative_result_analysis_sha256": digest,
        "receipt_created_at": now(),
        "analysis_mutation_authorized": False,
    })
    print(f"negative result analysis frozen: {digest}")
    print("decision: segmentation/classification separation required before another real execution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
