#!/usr/bin/env python3
"""Run the frozen Phase 7.3.3-A Atomic Judge on controls only.

The immutable execution manifest selects every artifact and model parameter.
Credentials are read from PHASE7_ATOMIC_JUDGE_API_KEY,
PHASE7_SEMANTIC_JUDGE_API_KEY, PHASE7_REVIEW_API_KEY, or DEEPSEEK_API_KEY and
are never persisted. Gold Claim labels, expected Candidate labels, design cases,
and held-out cases are never sent to the provider. A returned invalid model
output is an authoritative negative result: it is hashed, classified, and never
repaired or semantically retried. Transport failures before a model output may
be resumed from the checkpoint.
"""
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

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest.json"
RECEIPT = ROOT / "crates/eval/reports/phase7_3_3_a_execution_manifest_receipt.json"
POLICY = ROOT / "crates/eval/config/phase7_3_3_a_execution_policy_v1.json"
PROMPT = ROOT / "crates/eval/config/phase7_3_3_atomic_claim_judge_prompt_v1.md"
CONTROLS = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_atomic_claim_controls.json"
SUPPLEMENT = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_a_partial_atomic_claim_supplement_v1.json"
OUTPUT = ROOT / "crates/eval/reports/phase7_3_3_a_atomic_judge_control_execution.json"
CHECKPOINT = ROOT / "target/phase7/phase7_3_3_a_atomic_judge_checkpoint.json"

TOP_FIELDS = {"case_id", "claims"}
CLAIM_FIELDS = {
    "claim_id", "source_span", "claim_text", "claim_type", "centrality",
    "material", "claim_origin", "support_label", "evidence_ids",
    "reason_codes", "rationale",
}
CLAIM_TYPES = {
    "proposition", "scope", "prediction", "causal", "counterexample",
    "limitation", "falsifiability",
}
CENTRALITIES = {"central", "material"}
CLAIM_ORIGINS = {"explicit", "inferred", "synthesized"}
SUPPORT_LABELS = {
    "supported", "partially_supported", "unsupported", "not_assessable",
}


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


def load_and_verify_manifest() -> tuple[dict[str, Any], str]:
    if not MANIFEST.exists() or not RECEIPT.exists():
        raise ValueError("execution_manifest_or_receipt_missing")
    manifest_bytes = MANIFEST.read_bytes()
    manifest_hash = sha256_bytes(manifest_bytes)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("execution_manifest_sha256") != manifest_hash:
        raise ValueError("execution_manifest_receipt_hash_mismatch")
    manifest = json.loads(manifest_bytes)
    if manifest.get("status") != "frozen_execution_pending":
        raise ValueError("execution_manifest_not_frozen_pending")
    paths = {
        "execution_policy": POLICY,
        "prompt": PROMPT,
        "original_balanced_controls": CONTROLS,
        "partial_claim_supplement": SUPPLEMENT,
        "execution_adapter": Path(__file__),
    }
    for key, path in paths.items():
        expected = manifest["artifact_sha256"][key]
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"artifact_hash_mismatch:{key}")
    return manifest, manifest_hash


def provider_case(case: dict[str, Any], lane: str) -> dict[str, Any]:
    return {
        "case_id": case["control_id"],
        "evaluation_lane": lane,
        "evidence": case["evidence"],
        "candidate_text": case["candidate_text"],
    }


def load_cases() -> list[dict[str, Any]]:
    original = json.loads(CONTROLS.read_text(encoding="utf-8"))
    supplement = json.loads(SUPPLEMENT.read_text(encoding="utf-8"))
    cases = [provider_case(case, "original_balanced_candidate_controls") for case in original["control_cases"]]
    cases += [provider_case(case, "partial_atomic_claim_diagnostics_supplement") for case in supplement["control_cases"]]
    if len(cases) != 20 or len({case["case_id"] for case in cases}) != 20:
        raise ValueError("expected_20_unique_control_cases")
    return cases


def utf8_substring(text: str, start: int, end: int) -> str:
    encoded = text.encode("utf-8")
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or start > end or end > len(encoded):
        raise ValueError("source_span_range_invalid")
    try:
        return encoded[start:end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("source_span_utf8_boundary_invalid") from error


def validate_output(case: dict[str, Any], obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict) or set(obj) != TOP_FIELDS:
        raise ValueError("strict_top_fields_invalid")
    if obj["case_id"] != case["case_id"]:
        raise ValueError("case_id_mismatch")
    claims = obj["claims"]
    if not isinstance(claims, list) or not claims:
        raise ValueError("claims_missing_or_empty")
    evidence_ids = {row["evidence_id"] for row in case["evidence"]}
    seen_ids: set[str] = set()
    seen_spans: set[tuple[int, int]] = set()
    central_count = 0
    normalized: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != CLAIM_FIELDS:
            raise ValueError("strict_claim_fields_invalid")
        claim_id = claim["claim_id"]
        if not isinstance(claim_id, str) or not claim_id or claim_id in seen_ids:
            raise ValueError("claim_id_invalid_or_duplicate")
        seen_ids.add(claim_id)
        span = claim["source_span"]
        if not isinstance(span, dict) or set(span) != {"start", "end"}:
            raise ValueError("source_span_schema_invalid")
        start, end = span["start"], span["end"]
        span_key = (start, end)
        if span_key in seen_spans:
            raise ValueError("source_span_duplicate")
        seen_spans.add(span_key)
        if utf8_substring(case["candidate_text"], start, end) != claim["claim_text"]:
            raise ValueError("source_span_text_mismatch")
        if claim["claim_type"] not in CLAIM_TYPES:
            raise ValueError("claim_type_invalid")
        if claim["centrality"] not in CENTRALITIES:
            raise ValueError("centrality_invalid")
        central_count += int(claim["centrality"] == "central")
        if claim["material"] is not True:
            raise ValueError("material_claim_required")
        if claim["claim_origin"] not in CLAIM_ORIGINS:
            raise ValueError("claim_origin_invalid")
        if claim["support_label"] not in SUPPORT_LABELS:
            raise ValueError("support_label_invalid")
        cited = claim["evidence_ids"]
        if not isinstance(cited, list) or any(not isinstance(item, str) or item not in evidence_ids for item in cited):
            raise ValueError("evidence_ids_invalid")
        if not isinstance(claim["reason_codes"], list) or any(not isinstance(item, str) for item in claim["reason_codes"]):
            raise ValueError("reason_codes_invalid")
        if not isinstance(claim["rationale"], str) or not claim["rationale"].strip():
            raise ValueError("rationale_invalid")
        normalized.append(claim)
    if central_count != 1:
        raise ValueError("exactly_one_central_claim_required")
    return {"case_id": case["case_id"], "claims": normalized}


def request_model(base_url: str, api_key: str, model: str, prompt: str, case: dict[str, Any], timeout: int) -> tuple[str, str | None]:
    payload = {
        "model": model,
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Evaluate this frozen control case only:\n" + json.dumps(case, ensure_ascii=False, indent=2)},
        ],
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"], body.get("model")


def load_checkpoint(manifest_hash: str) -> dict[str, Any]:
    if not CHECKPOINT.exists():
        return {"schema_version": 1, "execution_manifest_sha256": manifest_hash, "results": []}
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if checkpoint.get("execution_manifest_sha256") != manifest_hash:
        raise ValueError("checkpoint_manifest_hash_mismatch")
    return checkpoint


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    manifest, manifest_hash = load_and_verify_manifest()
    cases = load_cases()
    if args.verify_only:
        print(f"manifest verified: {manifest_hash}")
        print("cases verified: 16 original + 4 diagnostics supplement")
        print("provider execution: not started")
        return 0

    api_key = (
        os.environ.get("PHASE7_ATOMIC_JUDGE_API_KEY")
        or os.environ.get("PHASE7_SEMANTIC_JUDGE_API_KEY")
        or os.environ.get("PHASE7_REVIEW_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or ""
    ).strip()
    if not api_key:
        print("BLOCKED: Atomic Judge API credential is not configured")
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

    for index, case in enumerate(cases, start=1):
        case_id = case["case_id"]
        if case_id in results:
            print(f"[{index}/20] {case_id}: authoritative checkpoint")
            continue
        try:
            raw, resolved = request_model(base_url, api_key, model, prompt, case, args.timeout)
        except urllib.error.HTTPError as error:
            print(f"[{index}/20] {case_id}: transport HTTP {error.code}; resumable before model output")
            return 3
        except Exception as error:
            print(f"[{index}/20] {case_id}: transport {type(error).__name__}; resumable before model output")
            return 3

        response_hash = sha256_bytes(raw.encode("utf-8"))
        try:
            parsed = json.loads(raw)
            normalized = validate_output(case, parsed)
            row = {
                "case_id": case_id,
                "evaluation_lane": case["evaluation_lane"],
                "status": "valid",
                "response_sha256": response_hash,
                "output": normalized,
            }
            print(f"[{index}/20] {case_id}: valid")
        except Exception as error:
            row = {
                "case_id": case_id,
                "evaluation_lane": case["evaluation_lane"],
                "status": "invalid_model_output",
                "response_sha256": response_hash,
                "failure_code": str(error).split(":", 1)[0],
                "output": None,
            }
            print(f"[{index}/20] {case_id}: authoritative negative output ({row['failure_code']})")
        resolved_model = resolved or resolved_model
        results[case_id] = row
        atomic_write(CHECKPOINT, {
            "schema_version": 1,
            "execution_manifest_sha256": manifest_hash,
            "execution_started_at": started_at,
            "resolved_model": resolved_model,
            "results": [results[c["case_id"]] for c in cases if c["case_id"] in results],
        })

    ordered = [results[case["case_id"]] for case in cases]
    invalid_count = sum(row["status"] != "valid" for row in ordered)
    report = {
        "schema_version": 1,
        "execution_id": manifest["execution_id"],
        "phase": "Phase 7.3.3-A First Real Atomic Judge Control Execution",
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
    print(f"completed: valid={20-invalid_count}, negative_outputs={invalid_count}")
    print(f"execution report: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
