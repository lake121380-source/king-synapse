#!/usr/bin/env python3
"""Create or verify the immutable Phase 7.3.3-A execution manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
EXECUTION_ADAPTER = ROOT / "scripts/eval/phase7_atomic_claim_execution.py"
OUTPUT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest.json"
RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_receipt.json"


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


def verify_core_hashes(policy: dict[str, Any]) -> None:
    actual = {
        "protocol": sha256_file(PROTOCOL),
        "prompt": sha256_file(PROMPT),
        "original_balanced_controls": sha256_file(CONTROLS),
        "partial_claim_supplement": sha256_file(SUPPLEMENT),
        "partial_claim_supplement_manifest": sha256_file(SUPPLEMENT_MANIFEST),
    }
    expected = policy["frozen_core_artifact_sha256"]
    for key, digest in expected.items():
        if actual.get(key) != digest:
            raise ValueError(f"frozen_core_hash_mismatch:{key}")


def build_manifest(base_url: str, model: str) -> dict[str, Any]:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8-sig"))
    verify_core_hashes(policy)
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-a-first-real-atomic-judge-execution-manifest-v1",
        "execution_id": "phase7.3.3-a-first-real-atomic-judge-controls-v1",
        "phase": "Phase 7.3.3-A First Real Atomic Judge Control Execution",
        "status": "frozen_execution_pending",
        "manifest_frozen_at": now(),
        "execution_started_at": None,
        "execution_started_at_recorded_in_final_report": True,
        "execution_config": {
            "provider_base_url": base_url,
            "judge_model": model,
            "temperature": 0,
            "top_p": 1,
            "response_format": "json_object",
            "case_isolation": True,
            "original_control_count": 16,
            "diagnostics_supplement_count": 4,
        },
        "artifact_sha256": {
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
        },
        "authoritative_result_policy": policy["authoritative_result_policy"],
        "post_execution_prohibitions": policy["post_execution_prohibitions"],
        "entry_criteria": policy["entry_criteria"],
        "data_handling": policy["data_handling"],
        "guards": {
            "protocol_modified": False,
            "prompt_modified": False,
            "original_controls_modified": False,
            "supplement_modified": False,
            "aggregator_modified": False,
            "thresholds_modified": False,
            "design_cases_authorized": False,
            "held_out_authorized": False,
            "runtime_authorized": False,
            "memory_write_authorized": False,
        },
    }


def verify_existing() -> str:
    if not OUTPUT.exists() or not RECEIPT.exists():
        raise ValueError("manifest_or_receipt_missing")
    digest = sha256_file(OUTPUT)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("execution_manifest_sha256") != digest:
        raise ValueError("manifest_receipt_hash_mismatch")
    manifest = json.loads(OUTPUT.read_text(encoding="utf-8"))
    for key, path in {
        "execution_policy": POLICY,
        "protocol": PROTOCOL,
        "prompt": PROMPT,
        "original_balanced_controls": CONTROLS,
        "partial_claim_supplement": SUPPLEMENT,
        "partial_claim_supplement_manifest": SUPPLEMENT_MANIFEST,
        "diagnostics_manifest": DIAGNOSTICS_MANIFEST,
        "aggregator_implementation": MEASUREMENT_SOURCE,
        "diagnostics_evaluator": DIAGNOSTICS_SOURCE,
        "execution_adapter": EXECUTION_ADAPTER,
    }.items():
        if manifest["artifact_sha256"][key] != sha256_file(path):
            raise ValueError(f"manifest_artifact_changed:{key}")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8-sig"))
    if manifest["artifact_sha256"]["aggregator_policy"] != canonical_sha256(protocol["aggregation_policy"]):
        raise ValueError("aggregator_policy_changed")
    if manifest["artifact_sha256"]["strict_parser_contract"] != canonical_sha256(protocol["atomic_claim_schema"]):
        raise ValueError("strict_parser_contract_changed")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("PHASE7_ATOMIC_JUDGE_BASE_URL", "https://api.gpt.ge/v1"))
    parser.add_argument("--model", default=os.environ.get("PHASE7_ATOMIC_JUDGE_MODEL", "gpt-4.1"))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify or OUTPUT.exists() or RECEIPT.exists():
        digest = verify_existing()
        print(f"execution manifest verified: {digest}")
        print("execution remains pending; manifest was not rewritten")
        return 0

    manifest = build_manifest(args.base_url, args.model)
    atomic_write(OUTPUT, manifest)
    digest = sha256_file(OUTPUT)
    atomic_write(RECEIPT, {
        "schema_version": 1,
        "manifest_id": manifest["manifest_id"],
        "execution_manifest_sha256": digest,
        "receipt_created_at": now(),
        "manifest_mutation_authorized": False,
    })
    print(f"execution manifest frozen: {digest}")
    print(f"manifest: {OUTPUT}")
    print(f"receipt: {RECEIPT}")
    print("real provider execution: not started")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
