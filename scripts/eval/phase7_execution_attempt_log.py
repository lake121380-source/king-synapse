#!/usr/bin/env python3
"""Append-only, hash-chained audit log for Phase 7.3.3-A execution attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG = ROOT / "crates/eval/reports/phase7_3_3_a_execution_attempts.jsonl"
V1_MANIFEST = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest.json"
V1_RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_receipt.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def entry_digest(entry_without_digest: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(entry_without_digest))


def read_entries(path: Path = DEFAULT_LOG) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            raise ValueError(f"attempt_log_blank_line:{line_number}")
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"attempt_log_invalid_json:{line_number}") from error
        if not isinstance(entry, dict):
            raise ValueError(f"attempt_log_entry_not_object:{line_number}")
        entries.append(entry)
    verify_entries(entries)
    return entries


def verify_entries(entries: list[dict[str, Any]]) -> None:
    previous_digest: str | None = None
    for index, entry in enumerate(entries, start=1):
        if entry.get("schema_version") != 1:
            raise ValueError(f"attempt_log_schema_invalid:{index}")
        if entry.get("event_index") != index:
            raise ValueError(f"attempt_log_event_index_invalid:{index}")
        if entry.get("previous_entry_sha256") != previous_digest:
            raise ValueError(f"attempt_log_chain_invalid:{index}")
        recorded_digest = entry.get("entry_sha256")
        if not isinstance(recorded_digest, str) or len(recorded_digest) != 64:
            raise ValueError(f"attempt_log_digest_missing:{index}")
        unsigned = dict(entry)
        del unsigned["entry_sha256"]
        actual_digest = entry_digest(unsigned)
        if recorded_digest != actual_digest:
            raise ValueError(f"attempt_log_digest_invalid:{index}")
        previous_digest = recorded_digest


def append_event(event: dict[str, Any], path: Path = DEFAULT_LOG) -> dict[str, Any]:
    entries = read_entries(path)
    entry = {
        "schema_version": 1,
        "event_index": len(entries) + 1,
        "recorded_at": now(),
        **event,
        "previous_entry_sha256": entries[-1]["entry_sha256"] if entries else None,
    }
    if "entry_sha256" in event:
        raise ValueError("entry_sha256_is_computed")
    entry["entry_sha256"] = entry_digest(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    read_entries(path)
    return entry


def next_attempt_number(manifest_sha256: str, path: Path = DEFAULT_LOG) -> int:
    attempts = {
        entry.get("attempt_number")
        for entry in read_entries(path)
        if entry.get("manifest_sha256") == manifest_sha256 and isinstance(entry.get("attempt_number"), int)
    }
    return max(attempts, default=0) + 1


def verify_manifest_receipt(manifest: Path, receipt: Path) -> str:
    if not manifest.exists() or not receipt.exists():
        raise ValueError("manifest_or_receipt_missing")
    digest = sha256_bytes(manifest.read_bytes())
    receipt_obj = json.loads(receipt.read_text(encoding="utf-8"))
    if receipt_obj.get("execution_manifest_sha256") != digest:
        raise ValueError("manifest_receipt_hash_mismatch")
    return digest


def record_v1_http_401(path: Path) -> dict[str, Any]:
    manifest_digest = verify_manifest_receipt(V1_MANIFEST, V1_RECEIPT)
    entries = read_entries(path)
    already_recorded = [
        entry for entry in entries
        if entry.get("manifest_sha256") == manifest_digest
        and entry.get("attempt_number") == 1
        and entry.get("event_type") == "attempt_transport_failure"
    ]
    if already_recorded:
        return already_recorded[0]
    return append_event({
        "event_type": "attempt_transport_failure",
        "manifest_sha256": manifest_digest,
        "attempt_number": 1,
        "attempt_occurred_at": None,
        "occurrence_time_status": "not_recorded_by_v1_adapter",
        "status": "transport_failure",
        "failure_type": "http_401",
        "case_id": "atomic_control_supported_01",
        "response_received": False,
        "authoritative_result": False,
        "completed_case_count": 0,
        "returned_output_case_count": 0,
        "historical_record": True,
        "note": "Recorded after the v1 adapter attempt; the exact occurrence timestamp was not captured and is not reconstructed.",
    }, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--record-v1-http-401", action="store_true")
    args = parser.parse_args()

    if args.record_v1_http_401:
        entry = record_v1_http_401(args.log)
        print(f"v1 transport failure recorded: event={entry['event_index']} hash={entry['entry_sha256']}")
    entries = read_entries(args.log)
    if args.verify or not args.record_v1_http_401:
        tail = entries[-1]["entry_sha256"] if entries else None
        print(f"attempt log verified: entries={len(entries)} tail={tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
