#!/usr/bin/env python3
"""Create or verify the immutable Phase 7.3.3-C execution Manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase7_execution_attempt_log import append_event, read_entries

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "crates/eval/config/phase7_3_3_c_execution_policy_v1.json"
PROTOCOL = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_c_segmentation_controlled_classification_protocol_v1.json"
PROMPT = ROOT / "crates/eval/config/phase7_3_3_c_atomic_claim_classifier_prompt_v1.md"
PACKETS = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_c_segmentation_controlled_claim_controls_v1.json"
ORIGINAL_CONTROLS = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_atomic_claim_controls.json"
SUPPLEMENT = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_a_partial_atomic_claim_supplement_v1.json"
NEGATIVE_ANALYSIS = ROOT / "crates/eval/reports/phase7_3_3_a_negative_result_analysis.json"
READINESS = ROOT / "crates/eval/reports/phase7_3_3_c_segmentation_controlled_readiness.json"
CONTROL_GENERATOR = ROOT / "scripts/eval/phase7_segmentation_controlled_controls.py"
RUST_EVALUATOR = ROOT / "crates/eval/src/phase7_segmentation_controlled_classification.rs"
AGGREGATOR = ROOT / "crates/eval/src/phase7_atomic_claim_measurement.rs"
DIAGNOSTICS = ROOT / "crates/eval/src/phase7_atomic_claim_diagnostics.rs"
EXECUTION_ADAPTER = ROOT / "scripts/eval/phase7_segmentation_controlled_execution.py"
ATTEMPT_LOG_ADAPTER = ROOT / "scripts/eval/phase7_execution_attempt_log.py"
PRIOR_MANIFEST = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_v2.json"
PRIOR_RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_v2_receipt.json"
PRIOR_REPORT = ROOT / "crates/eval/reports/phase7_3_3_a_atomic_judge_control_execution.json"
OUTPUT = ROOT / "crates/eval/reports/phase7_3_3_c_execution_manifest_v1.json"
RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_c_execution_manifest_v1_receipt.json"
ATTEMPT_LOG = ROOT / "crates/eval/reports/phase7_3_3_c_execution_attempts.jsonl"
CREDENTIAL_ENV_NAME = "PHASE7_ATOMIC_JUDGE_API_KEY"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(encoded)


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp = Path(handle.name)
    temp.replace(path)


def load_prior() -> tuple[dict[str, Any], str]:
    if not PRIOR_MANIFEST.exists() or not PRIOR_RECEIPT.exists() or not PRIOR_REPORT.exists():
        raise ValueError("prior_phase_a_artifact_missing")
    digest = sha256_file(PRIOR_MANIFEST)
    receipt = json.loads(PRIOR_RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("execution_manifest_sha256") != digest:
        raise ValueError("prior_manifest_receipt_hash_mismatch")
    return json.loads(PRIOR_MANIFEST.read_text(encoding="utf-8")), digest


def parser_contract(protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        **protocol["judge_output_schema"],
        "unknown_top_fields_forbidden": True,
        "unknown_judgment_fields_forbidden": True,
        "missing_required_fields_forbidden": True,
        "empty_reason_codes_list_allowed": True,
        "empty_reason_code_string_forbidden": True,
        "empty_rationale_forbidden": True,
        "unknown_evidence_ids_forbidden": True,
    }


def artifact_hashes(protocol: dict[str, Any]) -> dict[str, str]:
    return {
        "execution_policy": sha256_file(POLICY),
        "protocol": sha256_file(PROTOCOL),
        "classifier_prompt": sha256_file(PROMPT),
        "provider_visible_controls": sha256_file(PACKETS),
        "original_balanced_controls": sha256_file(ORIGINAL_CONTROLS),
        "partial_claim_supplement": sha256_file(SUPPLEMENT),
        "originating_negative_result_analysis": sha256_file(NEGATIVE_ANALYSIS),
        "offline_readiness_report": sha256_file(READINESS),
        "control_packet_generator": sha256_file(CONTROL_GENERATOR),
        "rust_output_validator": sha256_file(RUST_EVALUATOR),
        "aggregator_policy": canonical_sha256(protocol["aggregation_policy"]),
        "aggregator_implementation": sha256_file(AGGREGATOR),
        "diagnostics_evaluator": sha256_file(DIAGNOSTICS),
        "strict_parser_contract": canonical_sha256(parser_contract(protocol)),
        "execution_adapter": sha256_file(EXECUTION_ADAPTER),
        "attempt_log_adapter": sha256_file(ATTEMPT_LOG_ADAPTER),
        "prior_phase_a_manifest": sha256_file(PRIOR_MANIFEST),
        "prior_phase_a_report": sha256_file(PRIOR_REPORT),
    }


def build_manifest() -> dict[str, Any]:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    prior, prior_digest = load_prior()
    prior_config = prior["execution_config"]
    execution_config = {
        "provider_base_url": "https://api.gpt.ge/v1",
        "judge_model": "gpt-4.1",
        "temperature": 0,
        "top_p": 1,
        "response_format": "json_object",
        "case_isolation": True,
        "original_control_count": 16,
        "diagnostics_supplement_count": 4,
        "credential_env_name": CREDENTIAL_ENV_NAME,
    }
    comparison_fields = ["provider_base_url", "judge_model", "temperature", "top_p", "response_format", "case_isolation"]
    comparison = {field: execution_config[field] == prior_config[field] for field in comparison_fields}
    if not all(comparison.values()):
        raise ValueError("phase_a_phase_c_execution_config_mismatch")
    hashes = artifact_hashes(protocol)
    embedded = protocol["frozen_artifact_sha256"]
    embedded_mapping = {
        "original_balanced_controls": "original_balanced_controls",
        "partial_claim_supplement": "partial_claim_supplement",
        "provider_visible_controls": "provider_visible_controls",
        "classifier_prompt": "classifier_prompt",
        "originating_negative_result_analysis": "originating_negative_result_analysis",
    }
    for protocol_key, manifest_key in embedded_mapping.items():
        if embedded[protocol_key] != hashes[manifest_key]:
            raise ValueError(f"protocol_embedded_hash_mismatch:{protocol_key}")
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    if readiness.get("decision") != "segmentation_controlled_classifier_manifest_may_be_prepared":
        raise ValueError("offline_readiness_not_satisfied")
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-c-first-segmentation-controlled-classifier-execution-manifest-v1",
        "execution_id": "phase7.3.3-c-first-real-segmentation-controlled-classifier-control-execution",
        "phase": "Phase 7.3.3-C Segmentation-Controlled Atomic Claim Classification",
        "status": "frozen_execution_pending",
        "manifest_frozen_at": now(),
        "execution_started_at": None,
        "execution_started_at_recorded_in_final_report": True,
        "execution_config": execution_config,
        "artifact_sha256": hashes,
        "strict_parser_contract": parser_contract(protocol),
        "authoritative_result_policy": policy["authoritative_result_policy"],
        "post_execution_prohibitions": policy["post_execution_prohibitions"],
        "entry_criteria": policy["entry_criteria"],
        "data_handling": policy["data_handling"],
        "comparison_to_phase7_3_3_a": {
            "prior_manifest_sha256": prior_digest,
            "prior_report_sha256": sha256_file(PRIOR_REPORT),
            "provider_configuration_equal": comparison,
            "all_provider_configuration_fields_equal": all(comparison.values()),
            "measurement_change_only": "protocol_owned_segmentation_replaces_judge_owned_segmentation",
            "same_manifest_retry": False,
            "prior_negative_result_overwritten": False,
        },
        "guards": {
            "prompt_frozen": True,
            "parser_frozen": True,
            "aggregator_frozen": True,
            "thresholds_frozen": True,
            "extractor_modified": False,
            "design_cases_authorized": False,
            "held_out_authorized": False,
            "runtime_authorized": False,
            "memory_write_authorized": False,
            "pattern_promotion_authorized": False,
            "credential_fallback_authorized": False,
        },
    }


def verify_existing() -> tuple[str, dict[str, Any]]:
    if not OUTPUT.exists() or not RECEIPT.exists():
        raise ValueError("manifest_or_receipt_missing")
    digest = sha256_file(OUTPUT)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("execution_manifest_sha256") != digest:
        raise ValueError("manifest_receipt_hash_mismatch")
    manifest = json.loads(OUTPUT.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if manifest.get("status") != "frozen_execution_pending":
        raise ValueError("manifest_status_changed")
    if manifest.get("artifact_sha256") != artifact_hashes(protocol):
        raise ValueError("frozen_artifact_hash_changed")
    prior, prior_digest = load_prior()
    comparison = manifest["comparison_to_phase7_3_3_a"]
    if comparison["prior_manifest_sha256"] != prior_digest:
        raise ValueError("prior_manifest_reference_changed")
    for field in ["provider_base_url", "judge_model", "temperature", "top_p", "response_format", "case_isolation"]:
        if manifest["execution_config"][field] != prior["execution_config"][field]:
            raise ValueError(f"provider_configuration_changed:{field}")
    return digest, manifest


def ensure_frozen_event(digest: str) -> None:
    entries = read_entries(ATTEMPT_LOG)
    if any(entry.get("event_type") == "manifest_frozen" and entry.get("manifest_sha256") == digest for entry in entries):
        return
    append_event({
        "event_type": "manifest_frozen",
        "manifest_sha256": digest,
        "status": "frozen_execution_pending",
        "response_received": False,
        "authoritative_result": False,
        "experimental_configuration_changed": False,
    }, ATTEMPT_LOG)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify or OUTPUT.exists() or RECEIPT.exists():
        digest, _ = verify_existing()
        ensure_frozen_event(digest)
        print(f"Phase 7.3.3-C execution manifest verified: {digest}")
        return 0
    manifest = build_manifest()
    atomic_write(OUTPUT, manifest)
    digest = sha256_file(OUTPUT)
    atomic_write(RECEIPT, {
        "schema_version": 1,
        "manifest_id": manifest["manifest_id"],
        "execution_manifest_sha256": digest,
        "receipt_created_at": now(),
        "manifest_mutation_authorized": False,
    })
    ensure_frozen_event(digest)
    print(f"Phase 7.3.3-C execution manifest frozen: {digest}")
    print("real provider execution: pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
