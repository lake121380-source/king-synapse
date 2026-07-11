#!/usr/bin/env python3
"""Bounded model-backed Pattern Candidate extraction adapter for Phase 7.2.2.

Network execution is opt-in with --execute-design. The adapter uses design inputs only,
performs no output repair or retry, never records credentials/raw text, and never reads
Phase 7.1 held-out cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
REPORTS = ROOT / "crates/eval/reports"
DATASET = ROOT / "crates/eval/datasets/pattern_extraction/phase7_2_pattern_extraction_design.json"
PROMPT = CONFIG / "phase7_2_2_canonical_prompt_v1.md"
PARSER = CONFIG / "phase7_2_2_parser_policy_v1.json"
SCORER = CONFIG / "phase7_2_2_scorer_policy_v1.json"
MANIFESTS = CONFIG / "phase7_2_2_provider_manifests.json"
OUTPUT = REPORTS / "phase7_2_2_model_provider_execution.json"

TOP_LEVEL_FIELDS = {
    "id", "proposition", "supporting_evidence", "counterexamples",
    "counterexample_search_performed", "applicability_conditions",
    "exclusion_conditions", "source_domains", "predictions",
    "falsification_conditions", "validation_outcome_ids", "confidence", "status",
}
EVIDENCE_FIELDS = {"memory_id", "experience_id", "domain", "independent_source", "observed_outcome"}
CONDITION_FIELDS = {"field", "operator", "value"}
PREDICTION_FIELDS = {"statement", "observable", "success_criterion"}
FALSIFICATION_FIELDS = {"statement", "observable"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def split_prompt(text: str) -> tuple[str, str]:
    system_marker = "## System message\n"
    user_marker = "## User message template\n"
    if system_marker not in text or user_marker not in text:
        raise ValueError("canonical prompt markers missing")
    system = text.split(system_marker, 1)[1].split(user_marker, 1)[0].strip()
    user = text.split(user_marker, 1)[1].strip()
    return system, user


def require_exact_keys(value: Any, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} fields must exactly match frozen schema")


def strict_candidate(raw: str) -> dict[str, Any]:
    # json.loads rejects fences, commentary, multiple values, and malformed JSON. No repair is attempted.
    value = json.loads(raw)
    require_exact_keys(value, TOP_LEVEL_FIELDS, "candidate")
    for item in value["supporting_evidence"] + value["counterexamples"]:
        require_exact_keys(item, EVIDENCE_FIELDS, "evidence")
    for item in value["applicability_conditions"] + value["exclusion_conditions"]:
        require_exact_keys(item, CONDITION_FIELDS, "condition")
    for item in value["predictions"]:
        require_exact_keys(item, PREDICTION_FIELDS, "prediction")
    for item in value["falsification_conditions"]:
        require_exact_keys(item, FALSIFICATION_FIELDS, "falsification")
    if value["status"] != "proposed":
        raise ValueError("status must remain proposed")
    if value["validation_outcome_ids"] != []:
        raise ValueError("validation outcomes must remain empty")
    confidence = value["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 0.60:
        raise ValueError("confidence exceeds frozen proposed-candidate bound")
    return value


def request_chat(base_url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def frozen_hashes() -> dict[str, str]:
    return {
        "prompt_sha256": sha256_bytes(PROMPT.read_bytes()),
        "parser_sha256": sha256_bytes(PARSER.read_bytes()),
        "scorer_sha256": sha256_bytes(SCORER.read_bytes()),
        "dataset_sha256": sha256_bytes(DATASET.read_bytes()),
    }


def write_artifact(
    output: Path,
    execution_id: str,
    provider: dict[str, Any],
    hashes: dict[str, str],
    **state: Any,
) -> None:
    artifact = {
        "schema_version": 1,
        "execution_id": execution_id,
        "provider_name": provider["provider_name"],
        "provider_version": provider["provider_version"],
        "model_requested": provider["model"],
        "resolved_model": state.get("resolved_model"),
        "design_case_count": 10,
        "attempted_design_cases": state.get("attempted", 0),
        "completed_design_cases": state.get("completed", 0),
        "status": state["status"],
        "blocker": state.get("blocker"),
        "api_key_recorded": False,
        "raw_response_text_recorded": False,
        "prompt_version": provider["prompt_version"],
        **hashes,
        "outputs": state.get("outputs", []),
    }
    output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def execute_design(output: Path, execution_id: str) -> int:
    manifests = load_json(MANIFESTS)
    provider = manifests["providers"][1]
    hashes = frozen_hashes()
    for key, digest in hashes.items():
        if manifests[key] != digest:
            raise RuntimeError(f"frozen {key} does not match manifest")
    if provider["prompt_sha256"] != hashes["prompt_sha256"] or provider["parser_sha256"] != hashes["parser_sha256"]:
        raise RuntimeError("provider manifest hashes do not match frozen artifacts")

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        write_artifact(output, execution_id, provider, hashes, status="blocked_configuration", blocker={
            "stage": "credential_preflight", "http_status": None, "reason": "api_key_missing"
        })
        print("BLOCKED: DEEPSEEK_API_KEY is not present", file=sys.stderr)
        return 2

    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    system, user_template = split_prompt(PROMPT.read_text(encoding="utf-8"))
    dataset = load_json(DATASET)
    cases = dataset["cases"]
    if len(cases) != 10:
        raise RuntimeError("design dataset must remain exactly 10 cases")

    outputs: list[dict[str, Any]] = []
    resolved_model: str | None = None
    attempted = 0
    for case in cases:
        # Intentionally access only case id and input. reference_candidate is never included in prompts.
        case_id = case["id"]
        authoritative_input = case["input"]
        user = user_template.replace(
            "{{PATTERN_EXTRACTION_INPUT_JSON}}",
            json.dumps(authoritative_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        payload = {
            "model": provider["model"],
            "temperature": provider["temperature"],
            "top_p": provider["top_p"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        attempted += 1
        try:
            response = request_chat(base_url, api_key, payload)
            raw = response["choices"][0]["message"]["content"]
            candidate = strict_candidate(raw)
        except urllib.error.HTTPError as error:
            status = "blocked_authorization" if error.code in (401, 403) else "blocked_provider_http"
            reason = "authorization_required" if error.code in (401, 403) else "provider_http_error"
            write_artifact(output, execution_id, provider, hashes, status=status, attempted=attempted, completed=len(outputs),
                           resolved_model=resolved_model, outputs=outputs,
                           blocker={"stage": "model_request", "http_status": error.code, "reason": reason})
            print(f"BLOCKED: provider HTTP {error.code}; raw response not recorded", file=sys.stderr)
            return 2
        except urllib.error.URLError as error:
            write_artifact(output, execution_id, provider, hashes, status="blocked_transport", attempted=attempted,
                           completed=len(outputs), resolved_model=resolved_model, outputs=outputs,
                           blocker={"stage": "model_request", "http_status": None, "reason": type(error.reason).__name__})
            print("BLOCKED: provider transport failed; raw response not recorded", file=sys.stderr)
            return 2
        except (KeyError, IndexError, TypeError, ValueError) as error:
            write_artifact(output, execution_id, provider, hashes, status="rejected_parse_error", attempted=attempted,
                           completed=len(outputs), resolved_model=resolved_model, outputs=outputs,
                           blocker={"stage": "strict_parser", "http_status": None, "reason": type(error).__name__})
            print("REJECTED: strict parser failed; no repair or retry performed", file=sys.stderr)
            return 3

        resolved_model = response.get("model", resolved_model)
        outputs.append({
            "case_id": case_id,
            "response_sha256": sha256_bytes(raw.encode("utf-8")),
            "candidate": candidate,
        })

    write_artifact(output, execution_id, provider, hashes, status="completed", attempted=10, completed=10,
                   resolved_model=resolved_model, outputs=outputs, blocker=None)
    print("Completed 10 design-only model extractions. Held-out cases were not accessed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-design", action="store_true", help="explicitly authorize ten design API calls")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="execution artifact path; use a phase-specific path to preserve frozen history",
    )
    parser.add_argument(
        "--execution-id",
        default="phase7.2.2-deepseek-design-run-v1",
        help="execution artifact identity",
    )
    args = parser.parse_args()
    if not args.execute_design:
        artifact = load_json(args.output)
        print(f"Execution status: {artifact['status']}")
        print("No network call made. Use --execute-design only after provider authorization is valid.")
        return 0
    return execute_design(args.output, args.execution_id)


if __name__ == "__main__":
    raise SystemExit(main())
