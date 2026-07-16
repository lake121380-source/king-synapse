#!/usr/bin/env python3
"""Execute the frozen Phase 7.3.3-C classification-only control experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase7_execution_attempt_log import append_event, next_attempt_number

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "crates/eval/reports/phase7_3_3_c_execution_manifest_v1.json"
RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_c_execution_manifest_v1_receipt.json"
POLICY = ROOT / "crates/eval/config/phase7_3_3_c_execution_policy_v1.json"
PROMPT = ROOT / "crates/eval/config/phase7_3_3_c_atomic_claim_classifier_prompt_v1.md"
PACKETS = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_c_segmentation_controlled_claim_controls_v1.json"
ATTEMPT_LOG = ROOT / "crates/eval/reports/phase7_3_3_c_execution_attempts.jsonl"
OUTPUT = ROOT / "crates/eval/reports/phase7_3_3_c_atomic_claim_classifier_control_execution.json"
CHECKPOINT = ROOT / "target/phase7/phase7_3_3_c_atomic_claim_classifier_checkpoint.json"

TOP_FIELDS = {"case_id", "claim_judgments"}
JUDGMENT_FIELDS = {"claim_id", "support_label", "evidence_ids", "reason_codes", "rationale"}
SUPPORT_LABELS = {"supported", "partially_supported", "unsupported", "not_assessable"}


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


def load_and_verify_manifest() -> tuple[dict[str, Any], str]:
    if not MANIFEST.exists() or not RECEIPT.exists():
        raise ValueError("execution_manifest_or_receipt_missing")
    digest = sha256_file(MANIFEST)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("execution_manifest_sha256") != digest:
        raise ValueError("manifest_receipt_hash_mismatch")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status") != "frozen_execution_pending":
        raise ValueError("manifest_not_frozen_pending")
    for key, path in {
        "execution_policy": POLICY,
        "classifier_prompt": PROMPT,
        "provider_visible_controls": PACKETS,
        "execution_adapter": Path(__file__),
        "attempt_log_adapter": ROOT / "scripts/eval/phase7_execution_attempt_log.py",
    }.items():
        if manifest["artifact_sha256"].get(key) != sha256_file(path):
            raise ValueError(f"artifact_hash_mismatch:{key}")
    return manifest, digest


def load_packets() -> list[dict[str, Any]]:
    dataset = json.loads(PACKETS.read_text(encoding="utf-8"))
    packets = dataset["provider_packets"]
    if len(packets) != 20 or len({packet["case_id"] for packet in packets}) != 20:
        raise ValueError("expected_20_unique_packets")
    return packets


def validate_output(packet: dict[str, Any], obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict) or set(obj) != TOP_FIELDS:
        raise ValueError("strict_top_fields_invalid")
    if obj["case_id"] != packet["case_id"]:
        raise ValueError("case_id_mismatch")
    judgments = obj["claim_judgments"]
    claims = packet["atomic_claims"]
    if not isinstance(judgments, list) or len(judgments) != len(claims):
        raise ValueError("claim_judgment_count_mismatch")
    valid_evidence_ids = {row["evidence_id"] for row in packet["evidence"]}
    normalized = []
    seen = set()
    for claim, judgment in zip(claims, judgments):
        if not isinstance(judgment, dict) or set(judgment) != JUDGMENT_FIELDS:
            raise ValueError("strict_judgment_fields_invalid")
        claim_id = judgment["claim_id"]
        if claim_id != claim["claim_id"]:
            raise ValueError("claim_order_or_id_mismatch")
        if claim_id in seen:
            raise ValueError("duplicate_claim_id")
        seen.add(claim_id)
        if judgment["support_label"] not in SUPPORT_LABELS:
            raise ValueError("support_label_invalid")
        evidence_ids = judgment["evidence_ids"]
        if not isinstance(evidence_ids, list) or any(not isinstance(item, str) or item not in valid_evidence_ids for item in evidence_ids):
            raise ValueError("evidence_ids_invalid")
        reason_codes = judgment["reason_codes"]
        if not isinstance(reason_codes, list) or any(not isinstance(item, str) or not item.strip() for item in reason_codes):
            raise ValueError("reason_codes_invalid")
        if not isinstance(judgment["rationale"], str) or not judgment["rationale"].strip():
            raise ValueError("rationale_invalid")
        normalized.append(judgment)
    return {"case_id": packet["case_id"], "claim_judgments": normalized}


def strict_parser_self_test(packet: dict[str, Any]) -> None:
    """Freeze the parser's accept/reject boundary before the Manifest is created."""
    claims = packet["atomic_claims"]
    evidence_ids = [row["evidence_id"] for row in packet["evidence"]]
    valid = {
        "case_id": packet["case_id"],
        "claim_judgments": [
            {
                "claim_id": claim["claim_id"],
                "support_label": "not_assessable",
                "evidence_ids": evidence_ids[:1],
                "reason_codes": [],
                "rationale": "Strict parser boundary probe.",
            }
            for claim in claims
        ],
    }
    validate_output(packet, valid)

    invalid_probes: list[tuple[str, dict[str, Any]]] = []
    missing_top = dict(valid)
    del missing_top["case_id"]
    invalid_probes.append(("missing_top_field", missing_top))
    unknown_top = {**valid, "candidate_label": "supported"}
    invalid_probes.append(("unknown_top_field", unknown_top))

    missing_judgment = json.loads(json.dumps(valid))
    del missing_judgment["claim_judgments"][0]["rationale"]
    invalid_probes.append(("missing_judgment_field", missing_judgment))
    unknown_judgment = json.loads(json.dumps(valid))
    unknown_judgment["claim_judgments"][0]["claim_text"] = claims[0]["claim_text"]
    invalid_probes.append(("unknown_judgment_field", unknown_judgment))
    wrong_order = json.loads(json.dumps(valid))
    if len(wrong_order["claim_judgments"]) > 1:
        wrong_order["claim_judgments"][0], wrong_order["claim_judgments"][1] = (
            wrong_order["claim_judgments"][1],
            wrong_order["claim_judgments"][0],
        )
        invalid_probes.append(("claim_order", wrong_order))

    for name, probe in invalid_probes:
        try:
            validate_output(packet, probe)
        except ValueError:
            continue
        raise ValueError(f"strict_parser_self_test_failed:{name}")


def request_provider(base_url: str, api_key: str, model: str, prompt: str, packet: dict[str, Any], timeout: int) -> bytes:
    payload = {
        "model": model,
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Classify this frozen segmentation-controlled packet only:\n" + json.dumps(packet, ensure_ascii=False, indent=2)},
        ],
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def extract_content(body: bytes) -> tuple[str, str | None]:
    envelope = json.loads(body.decode("utf-8"))
    content = envelope["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("provider_content_not_string")
    return content, envelope.get("model")


def load_checkpoint(manifest_hash: str) -> dict[str, Any]:
    if not CHECKPOINT.exists():
        return {"schema_version": 1, "execution_manifest_sha256": manifest_hash, "results": []}
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if checkpoint.get("execution_manifest_sha256") != manifest_hash:
        raise ValueError("checkpoint_manifest_hash_mismatch")
    return checkpoint


def log(event: dict[str, Any]) -> None:
    append_event(event, ATTEMPT_LOG)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    manifest, manifest_hash = load_and_verify_manifest()
    packets = load_packets()
    strict_parser_self_test(packets[0])
    if args.verify_only:
        print(f"manifest verified: {manifest_hash}")
        print("strict parser self-test: passed")
        print("packets verified: 16 original + 4 diagnostics supplement")
        print("provider execution: not started")
        return 0

    credential_env_name = manifest["execution_config"]["credential_env_name"]
    if credential_env_name != "PHASE7_ATOMIC_JUDGE_API_KEY":
        raise ValueError("unexpected_credential_env_name")
    api_key = (os.environ.get(credential_env_name) or "").strip()
    if not api_key:
        print(f"BLOCKED: credential environment variable {credential_env_name} is not configured")
        return 2
    if OUTPUT.exists():
        print("BLOCKED: authoritative execution report already exists")
        return 5

    prompt = PROMPT.read_text(encoding="utf-8-sig")
    checkpoint = load_checkpoint(manifest_hash)
    results = {row["case_id"]: row for row in checkpoint["results"]}
    started_at = checkpoint.get("execution_started_at") or now()
    resolved_model = checkpoint.get("resolved_model")
    model = manifest["execution_config"]["judge_model"]
    base_url = manifest["execution_config"]["provider_base_url"]
    attempt_number = next_attempt_number(manifest_hash, ATTEMPT_LOG)
    attempt_returned_count = 0
    log({
        "event_type": "attempt_started",
        "manifest_sha256": manifest_hash,
        "attempt_number": attempt_number,
        "attempt_occurred_at": now(),
        "occurrence_time_status": "recorded_by_phase7_3_3_c_adapter",
        "status": "in_progress",
        "response_received": False,
        "authoritative_result": False,
        "resumed_authoritative_case_count": len(results),
    })

    for index, packet in enumerate(packets, start=1):
        case_id = packet["case_id"]
        if case_id in results:
            print(f"[{index}/20] {case_id}: authoritative checkpoint", flush=True)
            continue
        try:
            body = request_provider(base_url, api_key, model, prompt, packet, args.timeout)
        except urllib.error.HTTPError as error:
            log({
                "event_type": "attempt_transport_failure", "manifest_sha256": manifest_hash,
                "attempt_number": attempt_number, "attempt_occurred_at": now(),
                "occurrence_time_status": "recorded_by_phase7_3_3_c_adapter",
                "status": "transport_failure", "failure_type": f"http_{error.code}",
                "case_id": case_id, "response_received": attempt_returned_count > 0,
                "authoritative_result": attempt_returned_count > 0,
                "completed_case_count": len(results), "returned_output_case_count": attempt_returned_count,
            })
            print(f"[{index}/20] {case_id}: transport HTTP {error.code}; resumable", flush=True)
            return 3
        except Exception as error:
            log({
                "event_type": "attempt_transport_failure", "manifest_sha256": manifest_hash,
                "attempt_number": attempt_number, "attempt_occurred_at": now(),
                "occurrence_time_status": "recorded_by_phase7_3_3_c_adapter",
                "status": "transport_failure", "failure_type": type(error).__name__,
                "case_id": case_id, "response_received": attempt_returned_count > 0,
                "authoritative_result": attempt_returned_count > 0,
                "completed_case_count": len(results), "returned_output_case_count": attempt_returned_count,
            })
            print(f"[{index}/20] {case_id}: transport {type(error).__name__}; resumable", flush=True)
            return 3

        attempt_returned_count += 1
        body_hash = sha256_bytes(body)
        try:
            raw, resolved = extract_content(body)
            response_hash = sha256_bytes(raw.encode("utf-8"))
            parsed = json.loads(raw)
            normalized = validate_output(packet, parsed)
            row = {
                "case_id": case_id, "evaluation_lane": packet["evaluation_lane"],
                "status": "valid", "response_sha256": response_hash, "output": normalized,
            }
            resolved_model = resolved or resolved_model
            print(f"[{index}/20] {case_id}: valid", flush=True)
        except Exception as error:
            row = {
                "case_id": case_id, "evaluation_lane": packet["evaluation_lane"],
                "status": "invalid_model_output", "response_sha256": body_hash,
                "failure_code": str(error).split(":", 1)[0], "output": None,
            }
            print(f"[{index}/20] {case_id}: authoritative negative output ({row['failure_code']})", flush=True)

        results[case_id] = row
        atomic_write(CHECKPOINT, {
            "schema_version": 1, "execution_manifest_sha256": manifest_hash,
            "execution_started_at": started_at, "resolved_model": resolved_model,
            "results": [results[p["case_id"]] for p in packets if p["case_id"] in results],
        })
        log({
            "event_type": "attempt_experimental_output_received", "manifest_sha256": manifest_hash,
            "attempt_number": attempt_number, "attempt_occurred_at": now(),
            "occurrence_time_status": "recorded_by_phase7_3_3_c_adapter",
            "status": row["status"], "case_id": case_id, "response_received": True,
            "authoritative_result": True, "response_sha256": row["response_sha256"],
        })

    ordered = [results[packet["case_id"]] for packet in packets]
    invalid_count = sum(row["status"] != "valid" for row in ordered)
    report = {
        "schema_version": 1,
        "execution_id": manifest["execution_id"],
        "phase": manifest["phase"],
        "status": "completed" if invalid_count == 0 else "completed_with_negative_outputs",
        "execution_manifest_sha256": manifest_hash,
        "execution_policy_sha256": sha256_file(POLICY),
        "execution_started_at": started_at,
        "execution_completed_at": now(),
        "provider_base_url": base_url,
        "model_requested": model,
        "resolved_model": resolved_model,
        "temperature": 0,
        "top_p": 1,
        "first_returned_output_authoritative": True,
        "automatic_repair": False,
        "semantic_retry": False,
        "api_key_recorded": False,
        "raw_provider_responses_stored": False,
        "gold_labels_visible_to_provider": False,
        "design_cases_accessed": False,
        "held_out_accessed": False,
        "original_control_count": 16,
        "supplement_control_count": 4,
        "valid_output_count": 20 - invalid_count,
        "invalid_output_count": invalid_count,
        "results": ordered,
    }
    atomic_write(OUTPUT, report)
    log({
        "event_type": "attempt_completed", "manifest_sha256": manifest_hash,
        "attempt_number": attempt_number, "attempt_occurred_at": now(),
        "occurrence_time_status": "recorded_by_phase7_3_3_c_adapter",
        "status": report["status"], "response_received": attempt_returned_count > 0,
        "authoritative_result": True, "completed_case_count": len(results),
        "returned_output_case_count": attempt_returned_count,
        "execution_report_sha256": sha256_file(OUTPUT),
    })
    print(f"completed: valid={20-invalid_count}, negative_outputs={invalid_count}", flush=True)
    print(f"execution report: {OUTPUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
