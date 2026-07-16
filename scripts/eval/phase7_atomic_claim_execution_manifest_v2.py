#!/usr/bin/env python3
"""Create or verify the execution-engineering-only Phase 7.3.3-A Manifest v2."""
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
POLICY = ROOT / "crates/eval/config/phase7_3_3_a_execution_policy_v1.json"
PROTOCOL = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_atomic_claim_measurement_protocol.json"
PROMPT = ROOT / "crates/eval/config/phase7_3_3_atomic_claim_judge_prompt_v1.md"
CONTROLS = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_atomic_claim_controls.json"
SUPPLEMENT = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_a_partial_atomic_claim_supplement_v1.json"
SUPPLEMENT_MANIFEST = ROOT / "crates/eval/config/phase7_3_3_a_partial_atomic_claim_supplement_manifest_v1.json"
DIAGNOSTICS_MANIFEST = ROOT / "crates/eval/config/phase7_3_3_a_diagnostics_manifest_v1.json"
MEASUREMENT_SOURCE = ROOT / "crates/eval/src/phase7_atomic_claim_measurement.rs"
DIAGNOSTICS_SOURCE = ROOT / "crates/eval/src/phase7_atomic_claim_diagnostics.rs"
EXECUTION_ADAPTER = ROOT / "scripts/eval/phase7_atomic_claim_execution_v2.py"
ATTEMPT_LOG_ADAPTER = ROOT / "scripts/eval/phase7_execution_attempt_log.py"
V1_MANIFEST = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest.json"
V1_RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_receipt.json"
V1_REPORT = ROOT / "crates/eval/reports/phase7_3_3_a_atomic_judge_control_execution.json"
V1_CHECKPOINT = ROOT / "target/phase7/phase7_3_3_a_atomic_judge_checkpoint.json"
OUTPUT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_v2.json"
RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_v2_receipt.json"
CREDENTIAL_ENV_NAME = "PHASE7_ATOMIC_JUDGE_API_KEY"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp = Path(handle.name)
    temp.replace(path)


def load_v1() -> tuple[dict[str, Any], str]:
    if not V1_MANIFEST.exists() or not V1_RECEIPT.exists():
        raise ValueError("v1_manifest_or_receipt_missing")
    digest = sha256_file(V1_MANIFEST)
    receipt = json.loads(V1_RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("execution_manifest_sha256") != digest:
        raise ValueError("v1_manifest_receipt_hash_mismatch")
    return json.loads(V1_MANIFEST.read_text(encoding="utf-8")), digest


def verify_v1_no_model_output(v1_digest: str) -> None:
    if V1_REPORT.exists() or V1_CHECKPOINT.exists():
        raise ValueError("v1_model_output_artifact_exists")
    matching = [entry for entry in read_entries() if entry.get("manifest_sha256") == v1_digest]
    if not matching:
        raise ValueError("v1_attempt_log_missing")
    if any(entry.get("response_received") is True or entry.get("authoritative_result") is True for entry in matching):
        raise ValueError("v1_attempt_log_indicates_model_output")
    if not any(entry.get("failure_type") == "http_401" for entry in matching):
        raise ValueError("v1_http_401_attempt_not_recorded")


def artifact_hashes(protocol: dict[str, Any]) -> dict[str, str]:
    return {
        "execution_policy": sha256_file(POLICY),
        "protocol": sha256_file(PROTOCOL),
        "prompt": sha256_file(PROMPT),
        "original_balanced_controls": sha256_file(CONTROLS),
        "partial_claim_supplement": sha256_file(SUPPLEMENT),
        "partial_claim_supplement_manifest": sha256_file(SUPPLEMENT_MANIFEST),
        "diagnostics_manifest": sha256_file(DIAGNOSTICS_MANIFEST),
        "aggregator_policy": canonical_sha256(protocol["aggregation_policy"]),
        "strict_parser_contract": canonical_sha256(protocol["atomic_claim_schema"]),
        "aggregator_implementation": sha256_file(MEASUREMENT_SOURCE),
        "diagnostics_evaluator": sha256_file(DIAGNOSTICS_SOURCE),
        "execution_adapter": sha256_file(EXECUTION_ADAPTER),
        "attempt_log_adapter": sha256_file(ATTEMPT_LOG_ADAPTER),
    }


def experimental_fingerprint(manifest: dict[str, Any]) -> str:
    config = manifest["execution_config"]
    hashes = manifest["artifact_sha256"]
    value = {
        "provider_base_url": config["provider_base_url"],
        "judge_model": config["judge_model"],
        "temperature": config["temperature"],
        "top_p": config["top_p"],
        "response_format": config["response_format"],
        "case_isolation": config["case_isolation"],
        "original_control_count": config["original_control_count"],
        "diagnostics_supplement_count": config["diagnostics_supplement_count"],
        "execution_policy": hashes["execution_policy"],
        "protocol": hashes["protocol"],
        "prompt": hashes["prompt"],
        "original_balanced_controls": hashes["original_balanced_controls"],
        "partial_claim_supplement": hashes["partial_claim_supplement"],
        "partial_claim_supplement_manifest": hashes["partial_claim_supplement_manifest"],
        "aggregator_policy": hashes["aggregator_policy"],
        "strict_parser_contract": hashes["strict_parser_contract"],
        "aggregator_implementation": hashes["aggregator_implementation"],
        "entry_criteria": manifest["entry_criteria"],
    }
    return canonical_sha256(value)


def build_manifest() -> dict[str, Any]:
    v1, v1_digest = load_v1()
    verify_v1_no_model_output(v1_digest)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8-sig"))
    hashes = artifact_hashes(protocol)
    for key, digest in policy["frozen_core_artifact_sha256"].items():
        if hashes.get(key) != digest:
            raise ValueError(f"frozen_core_hash_mismatch:{key}")
    manifest = {
        "schema_version": 2,
        "manifest_id": "phase7.3.3-a-first-real-atomic-judge-execution-manifest-v2",
        "execution_id": v1["execution_id"],
        "phase": v1["phase"],
        "status": "frozen_execution_pending",
        "manifest_frozen_at": now(),
        "execution_started_at": None,
        "execution_started_at_recorded_in_final_report": True,
        "execution_config": {
            **v1["execution_config"],
            "credential_env_name": CREDENTIAL_ENV_NAME,
        },
        "artifact_sha256": hashes,
        "authoritative_result_policy": policy["authoritative_result_policy"],
        "post_execution_prohibitions": policy["post_execution_prohibitions"],
        "entry_criteria": policy["entry_criteria"],
        "data_handling": policy["data_handling"],
        "supersession": {
            "supersedes_manifest_sha256": v1_digest,
            "supersession_reason": "execution_engineering_revision_only",
            "prior_manifest_received_model_output": False,
            "experimental_configuration_changed": False,
            "changes": [
                "hash_chained_append_only_attempt_log",
                "single_explicit_credential_environment_variable",
                "v2_adapter_records_attempt_lifecycle",
            ],
        },
        "guards": {
            **v1["guards"],
            "experimental_objects_modified": False,
            "credential_fallback_authorized": False,
        },
    }
    v1_fingerprint = experimental_fingerprint(v1)
    v2_fingerprint = experimental_fingerprint(manifest)
    if v1_fingerprint != v2_fingerprint:
        raise ValueError("experimental_configuration_changed")
    manifest["supersession"]["experimental_configuration_sha256"] = v2_fingerprint
    return manifest


def verify_existing() -> tuple[str, dict[str, Any]]:
    if not OUTPUT.exists() or not RECEIPT.exists():
        raise ValueError("manifest_v2_or_receipt_missing")
    digest = sha256_file(OUTPUT)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("execution_manifest_sha256") != digest:
        raise ValueError("manifest_v2_receipt_hash_mismatch")
    manifest = json.loads(OUTPUT.read_text(encoding="utf-8"))
    v1, v1_digest = load_v1()
    verify_v1_no_model_output(v1_digest)
    if manifest["supersession"]["supersedes_manifest_sha256"] != v1_digest:
        raise ValueError("v2_supersedes_hash_mismatch")
    if manifest["execution_config"].get("credential_env_name") != CREDENTIAL_ENV_NAME:
        raise ValueError("credential_env_name_changed")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8-sig"))
    expected_hashes = artifact_hashes(protocol)
    if manifest["artifact_sha256"] != expected_hashes:
        raise ValueError("manifest_v2_artifact_hash_changed")
    fingerprint = experimental_fingerprint(manifest)
    if fingerprint != experimental_fingerprint(v1):
        raise ValueError("v1_v2_experimental_fingerprint_mismatch")
    if manifest["supersession"]["experimental_configuration_sha256"] != fingerprint:
        raise ValueError("stored_experimental_fingerprint_mismatch")
    return digest, manifest


def ensure_transition_event(v2_digest: str, manifest: dict[str, Any]) -> None:
    v1_digest = manifest["supersession"]["supersedes_manifest_sha256"]
    existing = [
        entry for entry in read_entries()
        if entry.get("event_type") == "manifest_transition"
        and entry.get("from_manifest_sha256") == v1_digest
        and entry.get("to_manifest_sha256") == v2_digest
    ]
    if existing:
        return
    append_event({
        "event_type": "manifest_transition",
        "manifest_sha256": v2_digest,
        "from_manifest_sha256": v1_digest,
        "to_manifest_sha256": v2_digest,
        "status": "frozen_execution_pending",
        "reason": "execution_engineering_revision_only",
        "prior_manifest_received_model_output": False,
        "experimental_configuration_changed": False,
        "experimental_configuration_sha256": manifest["supersession"]["experimental_configuration_sha256"],
        "response_received": False,
        "authoritative_result": False,
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify or OUTPUT.exists() or RECEIPT.exists():
        digest, manifest = verify_existing()
        ensure_transition_event(digest, manifest)
        print(f"execution manifest v2 verified: {digest}")
        print("v1 -> v2 experimental configuration unchanged")
        return 0

    manifest = build_manifest()
    atomic_write(OUTPUT, manifest)
    digest = sha256_file(OUTPUT)
    atomic_write(RECEIPT, {
        "schema_version": 2,
        "manifest_id": manifest["manifest_id"],
        "execution_manifest_sha256": digest,
        "receipt_created_at": now(),
        "manifest_mutation_authorized": False,
        "supersedes_manifest_sha256": manifest["supersession"]["supersedes_manifest_sha256"],
    })
    ensure_transition_event(digest, manifest)
    print(f"execution manifest v2 frozen: {digest}")
    print("v1 -> v2 experimental configuration unchanged")
    print("real provider execution: pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
