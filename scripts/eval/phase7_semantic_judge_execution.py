#!/usr/bin/env python3
"""Execute the frozen Phase 7.3.2 semantic Judge on ten design Candidates.

Credentials are read from PHASE7_SEMANTIC_JUDGE_API_KEY (preferred),
PHASE7_REVIEW_API_KEY, or DEEPSEEK_API_KEY. They are never persisted. Each
request contains one frozen design Evidence bundle and Candidate only; Silver,
reviewer, adjudication, old-Judge, reference-Candidate, and held-out artifacts
are never loaded by this adapter. Raw provider responses are never stored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "crates/eval/datasets/pattern_extraction/phase7_2_pattern_extraction_design.json"
CANDIDATES = ROOT / "crates/eval/reports/phase7_2_3_real_provider_execution.json"
PROTOCOL = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_2_semantic_judge_redesign_protocol.json"
PROMPT = ROOT / "crates/eval/config/phase7_3_2_semantic_judge_prompt_v1.md"
OUTPUT = ROOT / "crates/eval/reports/phase7_3_2_semantic_judge_execution.json"
CHECKPOINT = ROOT / "target/phase7/phase7_3_2_semantic_judge_checkpoint.json"

TOP_FIELDS = {"case_id", "support_label", "cited_evidence_ids", "reason_codes", "rationale", "confidence"}
SUPPORT_LABELS = {"supported", "partially_supported", "unsupported", "not_assessable"}
CONFIDENCE = {"low", "medium", "high"}
REASON_CODES = {
    "direct_evidence_match", "conservative_entailment", "reasonable_bridging_inference",
    "scope_preserved", "counterexample_preserved", "scope_expansion", "certainty_escalation",
    "causal_leap", "prediction_overcommitment", "unsupported_detail", "counterexample_ignored",
    "central_proposition_unsupported", "insufficient_evidence",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def split_prompt(text: str) -> tuple[str, str]:
    system_marker = "## System message\n"
    user_marker = "## User message template\n"
    if system_marker not in text or user_marker not in text:
        raise ValueError("prompt_markers_missing")
    system = text.split(system_marker, 1)[1].split(user_marker, 1)[0].strip()
    user = text.split(user_marker, 1)[1].strip()
    return system, user


def atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
        temp = Path(f.name)
    temp.replace(path)


def load_checkpoint() -> dict[str, Any]:
    if not CHECKPOINT.exists():
        return {"schema_version": 1, "decisions": []}
    return json.loads(CHECKPOINT.read_text(encoding="utf-8"))


def request_json(base_url: str, key: str, model: str, system: str, user: str, timeout: int) -> tuple[dict[str, Any], str | None]:
    payload = {
        "model": model,
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    raw = body["choices"][0]["message"]["content"]
    return json.loads(raw), body.get("model")


def validate_decision(case: dict[str, Any], obj: dict[str, Any]) -> dict[str, Any]:
    if set(obj) != TOP_FIELDS:
        raise ValueError(f"strict_fields_invalid:{sorted(set(obj) ^ TOP_FIELDS)}")
    if obj["case_id"] != case["case_id"]:
        raise ValueError("case_id_mismatch")
    if obj["support_label"] not in SUPPORT_LABELS:
        raise ValueError("support_label_invalid")
    if obj["confidence"] not in CONFIDENCE:
        raise ValueError("confidence_invalid")
    if not isinstance(obj["cited_evidence_ids"], list) or not isinstance(obj["reason_codes"], list):
        raise ValueError("list_fields_invalid")
    valid_ids = {item["memory_id"] for item in case["evidence_input"]["experiences"]}
    if any(item not in valid_ids for item in obj["cited_evidence_ids"]):
        raise ValueError("unknown_evidence_id")
    if any(item not in REASON_CODES for item in obj["reason_codes"]):
        raise ValueError("reason_code_invalid")
    if not str(obj["rationale"]).strip():
        raise ValueError("rationale_required")
    if obj["support_label"] == "not_assessable" and "insufficient_evidence" not in obj["reason_codes"]:
        raise ValueError("abstention_requires_insufficient_evidence")
    return {
        "case_id": obj["case_id"],
        "candidate_response_sha256": case["candidate_response_sha256"],
        "support_label": obj["support_label"],
        "unsupported_warning": obj["support_label"] in {"partially_supported", "unsupported"},
        "cited_evidence_ids": sorted(set(obj["cited_evidence_ids"])),
        "reason_codes": sorted(set(obj["reason_codes"])),
        "rationale": obj["rationale"].strip(),
        "confidence": obj["confidence"],
        "abstained": obj["support_label"] == "not_assessable",
    }


def build_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset = json.loads(DESIGN.read_text(encoding="utf-8"))
    execution = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    candidates = {item["case_id"]: item for item in execution["outputs"]}
    cases: list[dict[str, Any]] = []
    for item in dataset["cases"]:
        case_id = item["id"]
        output = candidates[case_id]
        cases.append({
            "case_id": case_id,
            "source_domain": item["input"]["source_domain"],
            "objective": item["input"]["objective"],
            "evidence_input": item["input"],
            "candidate": output["candidate"],
            "candidate_response_sha256": output["response_sha256"],
        })
    if len(cases) != 10 or len(candidates) != 10:
        raise ValueError("exactly_ten_design_cases_required")
    return cases, execution


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("PHASE7_SEMANTIC_JUDGE_MODEL", "gpt-4.1"))
    parser.add_argument("--base-url", default=os.environ.get("PHASE7_SEMANTIC_JUDGE_BASE_URL", "https://api.gpt.ge/v1"))
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    key = (os.environ.get("PHASE7_SEMANTIC_JUDGE_API_KEY") or os.environ.get("PHASE7_REVIEW_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        print("BLOCKED: PHASE7_SEMANTIC_JUDGE_API_KEY is not present")
        return 2

    cases, candidate_execution = build_cases()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8-sig"))
    prompt_text = PROMPT.read_text(encoding="utf-8-sig")
    system, user_template = split_prompt(prompt_text)
    checkpoint = {"schema_version": 1, "decisions": []} if args.fresh else load_checkpoint()
    decisions = {item["case_id"]: item for item in checkpoint.get("decisions", [])}
    resolved_model: str | None = checkpoint.get("resolved_model")

    for index, case in enumerate(cases, start=1):
        if case["case_id"] in decisions:
            print(f"[{index}/10] {case['case_id']}: checkpoint")
            continue
        safe_case = {key: value for key, value in case.items() if key != "candidate_response_sha256"}
        user = user_template.replace("{{CASE_JSON}}", json.dumps(safe_case, ensure_ascii=False, indent=2))
        try:
            obj, resolved = request_json(args.base_url, key, args.model, system, user, args.timeout)
            decision = validate_decision(case, obj)
        except urllib.error.HTTPError as error:
            detail = error.read(500).decode("utf-8", "replace")
            print(f"[{index}/10] {case['case_id']}: HTTP {error.code}: {detail}")
            return 3
        except Exception as error:
            print(f"[{index}/10] {case['case_id']}: {type(error).__name__}: {error}")
            return 4
        resolved_model = resolved or resolved_model
        decisions[case["case_id"]] = decision
        atomic_write(CHECKPOINT, {"schema_version": 1, "resolved_model": resolved_model, "decisions": list(decisions.values())})
        print(f"[{index}/10] {case['case_id']}: {decision['support_label']}")

    ordered = [decisions[case["case_id"]] for case in cases]
    execution = {
        "schema_version": 1,
        "execution_id": "phase7.3.2-semantic-judge-design-execution-v1",
        "phase": "Phase 7.3.2 Semantic Judge Redesign",
        "status": "completed",
        "provider_name": args.base_url,
        "model_requested": args.model,
        "resolved_model": resolved_model,
        "prompt_version": "PatternSemanticJudgePrompt-v1",
        "prompt_sha256": sha256_file(PROMPT),
        "protocol_sha256": sha256_file(PROTOCOL),
        "design_dataset_sha256": sha256_file(DESIGN),
        "candidate_execution_sha256": sha256_file(CANDIDATES),
        "adapter_sha256": sha256_file(Path(__file__)),
        "temperature": 0,
        "top_p": 1,
        "strict_parser": True,
        "automatic_repair": False,
        "selective_retry": False,
        "case_isolation": True,
        "silver_labels_visible": False,
        "reviewer_annotations_visible": False,
        "adjudication_visible": False,
        "old_judge_visible": False,
        "reference_candidates_visible": False,
        "held_out_accessed": False,
        "api_key_recorded": False,
        "raw_provider_responses_stored": False,
        "design_case_count": 10,
        "completed_case_count": len(ordered),
        "decisions": ordered,
        "protocol_id": protocol["protocol_id"],
    }
    atomic_write(OUTPUT, execution)
    print(f"completed: {len(ordered)}/10; resolved_model={resolved_model}")
    print(f"execution: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
