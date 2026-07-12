#!/usr/bin/env python3
"""Run a third-model adjudicator over frozen Phase 7.3.1 AI reviews.

The adapter reads the frozen blind packet, both completed reviewer submissions,
and the frozen Agreement Report. It never reads the frozen Judge, Phase 7.3 seed
labels, held-out data, or provider raw responses. Credentials are read only from
PHASE7_REVIEW_API_KEY. Raw adjudicator responses are never persisted.
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
PACKET = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_blind_review_packet.json"
REVIEWER_A = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_reviewer_a_template.json"
REVIEWER_B = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_reviewer_b_template.json"
AGREEMENT = ROOT / "crates/eval/reports/phase7_inter_reviewer_agreement.json"
PROMPT = ROOT / "crates/eval/config/phase7_3_1_ai_adjudicator_prompt_v1.md"
OUTPUT = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_adjudication_template.json"
MANIFEST = ROOT / "crates/eval/reports/phase7_3_1_ai_adjudicator_manifest.json"
CHECKPOINT = ROOT / "target/phase7/phase7_3_1_ai_adjudicator_checkpoint.json"
BASE_URL = "https://api.gpt.ge/v1"
EXPECTED_CASE_COUNT = 10
EXPECTED_GROUP_COUNT = 77

TOP_FIELDS = {"decisions"}
DECISION_FIELDS = {
    "group_id",
    "final_support_label",
    "final_claim_origin",
    "adjudication_rationale",
}
SUPPORT = {"supported", "partially_supported", "unsupported", "not_assessable"}
ORIGINS = {"explicit", "inferred", "synthesized"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_prompt(text: str) -> tuple[str, str]:
    system_marker = "## System message\n"
    user_marker = "## User message template\n"
    system = text.split(system_marker, 1)[1].split(user_marker, 1)[0].strip()
    user = text.split(user_marker, 1)[1].strip()
    return system, user


def exact_fields(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label}_fields_invalid")


def request(key: str, model: str, system: str, user: str) -> dict[str, Any]:
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
        BASE_URL + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def support_distance(a: str, b: str) -> int | None:
    order = {"supported": 0, "partially_supported": 1, "unsupported": 2}
    if a not in order or b not in order:
        return None
    return abs(order[a] - order[b])


def deterministic_disagreements(
    a_claims: list[dict[str, Any]],
    b_claims: list[dict[str, Any]],
    exact_boundary: bool,
) -> list[str]:
    out: set[str] = set()
    if not a_claims or not b_claims or not exact_boundary:
        out.add("segmentation_disagreement")
    if a_claims and b_claims:
        a = a_claims[0]
        b = b_claims[0]
        distance = support_distance(a["human_support_label"], b["human_support_label"])
        if distance == 1:
            out.add("boundary_disagreement")
        elif distance == 2:
            out.add("fundamental_disagreement")
        if a["claim_origin"] != b["claim_origin"]:
            out.add("provenance_disagreement")
        if set(a["claimed_evidence_ids"]) != set(b["claimed_evidence_ids"]):
            out.add("evidence_disagreement")
        if set(a["failure_kinds"]) != set(b["failure_kinds"]):
            out.add("taxonomy_disagreement")
        if a["annotation_confidence"] != b["annotation_confidence"]:
            out.add("confidence_disagreement")
    return sorted(out)


def build_groups(
    reviewer_a: dict[str, Any],
    reviewer_b: dict[str, Any],
    agreement: dict[str, Any],
) -> list[dict[str, Any]]:
    a_by_id = {claim["claim_id"]: claim for claim in reviewer_a["claims"]}
    b_by_id = {claim["claim_id"]: claim for claim in reviewer_b["claims"]}
    groups: list[dict[str, Any]] = []
    used_a: set[str] = set()
    used_b: set[str] = set()

    for index, alignment in enumerate(agreement["metrics"]["alignments"], 1):
        aid = alignment["reviewer_a_claim_id"]
        bid = alignment["reviewer_b_claim_id"]
        used_a.add(aid)
        used_b.add(bid)
        groups.append(
            {
                "group_id": f"adjudication-group-{index:03}",
                "case_id": alignment["case_id"],
                "anchor_id": alignment["anchor_id"],
                "reviewer_a_claims": [a_by_id[aid]],
                "reviewer_b_claims": [b_by_id[bid]],
                "span_iou": alignment["span_iou"],
                "exact_boundary_match": alignment["exact_boundary_match"],
            }
        )

    next_index = len(groups) + 1
    for claim in reviewer_a["claims"]:
        if claim["claim_id"] not in used_a:
            groups.append(
                {
                    "group_id": f"adjudication-group-{next_index:03}",
                    "case_id": claim["case_id"],
                    "anchor_id": claim["anchor_id"],
                    "reviewer_a_claims": [claim],
                    "reviewer_b_claims": [],
                    "span_iou": None,
                    "exact_boundary_match": False,
                }
            )
            next_index += 1
    for claim in reviewer_b["claims"]:
        if claim["claim_id"] not in used_b:
            groups.append(
                {
                    "group_id": f"adjudication-group-{next_index:03}",
                    "case_id": claim["case_id"],
                    "anchor_id": claim["anchor_id"],
                    "reviewer_a_claims": [],
                    "reviewer_b_claims": [claim],
                    "span_iou": None,
                    "exact_boundary_match": False,
                }
            )
            next_index += 1
    return groups


def validate_decisions(raw: dict[str, Any], expected_ids: set[str]) -> list[dict[str, Any]]:
    exact_fields(raw, TOP_FIELDS, "response")
    decisions = raw["decisions"]
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("decisions_required")
    seen: set[str] = set()
    for decision in decisions:
        exact_fields(decision, DECISION_FIELDS, "decision")
        group_id = decision["group_id"]
        if not isinstance(group_id, str) or group_id in seen:
            raise ValueError(f"duplicate_or_invalid_group:{group_id}")
        seen.add(group_id)
        if decision["final_support_label"] not in SUPPORT:
            raise ValueError(f"support_enum_invalid:{group_id}")
        if decision["final_claim_origin"] not in ORIGINS:
            raise ValueError(f"origin_enum_invalid:{group_id}")
        rationale = decision["adjudication_rationale"]
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"rationale_required:{group_id}")
    if seen != expected_ids:
        raise ValueError("decision_group_set_mismatch")
    return decisions


def validate_checkpoint(
    checkpoint: dict[str, Any],
    identity: dict[str, str],
    groups_by_case: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], str | None]:
    if checkpoint.get("identity") != identity:
        raise ValueError("checkpoint_identity_mismatch")
    decisions = checkpoint.get("decisions")
    case_results = checkpoint.get("case_results")
    resolved_model = checkpoint.get("resolved_model")
    if not isinstance(decisions, dict) or not isinstance(case_results, list):
        raise ValueError("checkpoint_shape_invalid")
    if resolved_model is not None and not isinstance(resolved_model, str):
        raise ValueError("checkpoint_resolved_model_invalid")

    completed_cases: set[str] = set()
    expected_completed_groups: set[str] = set()
    for result in case_results:
        if not isinstance(result, dict) or set(result) != {
            "case_id", "success", "attempts", "decision_count"
        }:
            raise ValueError("checkpoint_case_result_invalid")
        case_id = result["case_id"]
        if (
            case_id not in groups_by_case
            or result["success"] is not True
            or not isinstance(result["attempts"], int)
            or result["attempts"] < 1
            or result["decision_count"] != len(groups_by_case[case_id])
            or case_id in completed_cases
        ):
            raise ValueError("checkpoint_case_result_invalid")
        completed_cases.add(case_id)
        expected_completed_groups.update(
            group["group_id"] for group in groups_by_case[case_id]
        )

    if set(decisions) != expected_completed_groups:
        raise ValueError("checkpoint_decision_set_mismatch")
    for case_id in completed_cases:
        expected_ids = {group["group_id"] for group in groups_by_case[case_id]}
        raw = {"decisions": [decisions[group_id] for group_id in sorted(expected_ids)]}
        validate_decisions(raw, expected_ids)
    return decisions, case_results, resolved_model


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(payload)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="grok-4.1")
    parser.add_argument("--case", help="Run one case as a non-persisting readiness probe")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--reset-checkpoint", action="store_true")
    args = parser.parse_args()
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be at least 1")

    key = os.environ.get("PHASE7_REVIEW_API_KEY", "")
    if not key:
        raise SystemExit("PHASE7_REVIEW_API_KEY is required")

    if args.reset_checkpoint and CHECKPOINT.exists():
        CHECKPOINT.unlink()

    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    reviewer_a = json.loads(REVIEWER_A.read_text(encoding="utf-8"))
    reviewer_b = json.loads(REVIEWER_B.read_text(encoding="utf-8"))
    agreement = json.loads(AGREEMENT.read_text(encoding="utf-8"))
    prompt_text = PROMPT.read_text(encoding="utf-8")
    system_prompt, user_template = split_prompt(prompt_text)

    if not reviewer_a["completed"] or not reviewer_b["completed"]:
        raise SystemExit("two completed reviewer submissions are required")
    if agreement["decision"] != "agreement_report_ready_adjudication_required":
        raise SystemExit("frozen Agreement Report is required")

    packet_by_case = {case["case_id"]: case for case in packet["cases"]}
    groups = build_groups(reviewer_a, reviewer_b, agreement)
    groups_by_case: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        groups_by_case.setdefault(group["case_id"], []).append(group)
    if len(groups) != EXPECTED_GROUP_COUNT or len(groups_by_case) != EXPECTED_CASE_COUNT:
        raise SystemExit(
            f"frozen adjudication shape mismatch: {len(groups_by_case)} cases, {len(groups)} groups"
        )
    if len({group["group_id"] for group in groups}) != len(groups):
        raise SystemExit("duplicate adjudication group id")

    selected_cases = [args.case] if args.case else sorted(groups_by_case)
    if any(case_id not in groups_by_case for case_id in selected_cases):
        raise SystemExit("unknown case")

    all_decisions: dict[str, dict[str, Any]] = {}
    case_results: list[dict[str, Any]] = []
    resolved_model: str | None = None
    checkpoint_identity = {
        "model_requested": args.model,
        "prompt_sha256": sha256(PROMPT),
        "blind_packet_sha256": sha256(PACKET),
        "reviewer_a_submission_sha256": sha256(REVIEWER_A),
        "reviewer_b_submission_sha256": sha256(REVIEWER_B),
        "agreement_report_sha256": sha256(AGREEMENT),
        "adapter_sha256": sha256(Path(__file__)),
    }
    if not args.case and CHECKPOINT.exists():
        try:
            checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
            all_decisions, case_results, resolved_model = validate_checkpoint(
                checkpoint, checkpoint_identity, groups_by_case
            )
        except (json.JSONDecodeError, ValueError) as error:
            raise SystemExit(f"{error}; use --reset-checkpoint") from error
        completed_cases = {item["case_id"] for item in case_results}
        selected_cases = [case_id for case_id in selected_cases if case_id not in completed_cases]

    def save_checkpoint() -> None:
        if args.case:
            return
        atomic_write_json(
            CHECKPOINT,
            {
                "identity": checkpoint_identity,
                "resolved_model": resolved_model,
                "case_results": case_results,
                "decisions": all_decisions,
            },
        )
    for case_id in selected_cases:
        def compact_claim(claim: dict[str, Any]) -> dict[str, Any]:
            return {
                "claim_id": claim["claim_id"],
                "source_excerpt": claim["source_span"]["source_excerpt"],
                "claim_text": claim["claim_text"],
                "claim_origin": claim["claim_origin"],
                "claimed_evidence_ids": claim["claimed_evidence_ids"],
                "support_label": claim["human_support_label"],
                "reviewer_rationale": claim["reviewer_rationale"],
            }

        prompt_groups = [
            {
                "group_id": group["group_id"],
                "anchor_id": group["anchor_id"],
                "exact_boundary_match": group["exact_boundary_match"],
                "reviewer_a_claims": [compact_claim(c) for c in group["reviewer_a_claims"]],
                "reviewer_b_claims": [compact_claim(c) for c in group["reviewer_b_claims"]],
            }
            for group in groups_by_case[case_id]
        ]
        case_payload = {
            "case_id": case_id,
            "evidence_input": packet_by_case[case_id]["evidence_input"],
            "candidate": packet_by_case[case_id]["candidate"],
            "claim_groups": prompt_groups,
        }
        user = user_template.replace(
            "{{CASE_JSON}}", json.dumps(case_payload, ensure_ascii=False, indent=2)
        )
        last_error: Exception | None = None
        decisions: list[dict[str, Any]] | None = None
        attempts = 0
        for attempts in range(1, args.max_attempts + 1):
            try:
                response = request(key, args.model, system_prompt, user)
                response_model = response.get("model", args.model)
                if resolved_model is not None and response_model != resolved_model:
                    raise ValueError("resolved_model_changed_between_cases")
                resolved_model = response_model
                content = response["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                expected_ids = {group["group_id"] for group in groups_by_case[case_id]}
                decisions = validate_decisions(parsed, expected_ids)
                break
            except (KeyError, ValueError, json.JSONDecodeError, urllib.error.URLError) as error:
                last_error = error
        if decisions is None:
            result = {
                "case_id": case_id,
                "success": False,
                "attempts": attempts,
                "error": type(last_error).__name__ if last_error else "UnknownError",
                "status": getattr(last_error, "code", None),
            }
            case_results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if args.case:
                return 2
            raise RuntimeError(f"adjudication_failed:{case_id}") from last_error
        for decision in decisions:
            all_decisions[decision["group_id"]] = decision
        result = {
            "case_id": case_id,
            "success": True,
            "attempts": attempts,
            "decision_count": len(decisions),
        }
        case_results.append(result)
        save_checkpoint()
        print(json.dumps(result, ensure_ascii=False), flush=True)

    if args.case:
        print(json.dumps(case_results[0], ensure_ascii=False))
        return 0

    expected_all = {group["group_id"] for group in groups}
    completed_case_ids = [item["case_id"] for item in case_results]
    if (
        set(all_decisions) != expected_all
        or len(case_results) != EXPECTED_CASE_COUNT
        or len(completed_case_ids) != len(set(completed_case_ids))
        or set(completed_case_ids) != set(groups_by_case)
    ):
        raise SystemExit("incomplete or duplicate adjudication result set")

    adjudicated_claims: list[dict[str, Any]] = []
    for index, group in enumerate(groups, 1):
        decision = all_decisions[group["group_id"]]
        a_claims = group["reviewer_a_claims"]
        b_claims = group["reviewer_b_claims"]
        adjudicated_claims.append(
            {
                "claim_id": f"model-silver-claim-{index:03}",
                "reviewer_a_claim_ids": [claim["claim_id"] for claim in a_claims],
                "reviewer_b_claim_ids": [claim["claim_id"] for claim in b_claims],
                "final_support_label": decision["final_support_label"],
                "final_claim_origin": decision["final_claim_origin"],
                "disagreements": deterministic_disagreements(
                    a_claims, b_claims, group["exact_boundary_match"]
                ),
                "judge_failures": [],
                "adjudication_rationale": decision["adjudication_rationale"].strip(),
            }
        )

    adjudication = {
        "schema_version": 1,
        "adjudication_id": "phase7.3.1-model-adjudicated-silver-candidate-v1",
        "protocol_id": reviewer_a["protocol_id"],
        "reviewer_a_submission_id": reviewer_a["submission_id"],
        "reviewer_b_submission_id": reviewer_b["submission_id"],
        "completed": True,
        "held_out_accessed": False,
        "disagreements_preserved": True,
        "lineage": {
            "reviewer_a_submission_sha256": sha256(REVIEWER_A),
            "reviewer_b_submission_sha256": sha256(REVIEWER_B),
            "agreement_report_sha256": sha256(AGREEMENT),
        },
        "claims": adjudicated_claims,
    }
    manifest = {
        "schema_version": 1,
        "adjudicator_id": "ai_adjudicator_" + args.model,
        "adjudicator_type": "ai_model",
        "label_status": "model_adjudicated_silver_candidate_not_human_gold",
        "provider": "api.gpt.ge",
        "model_requested": args.model,
        "resolved_model": resolved_model or args.model,
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
        "adapter_sha256": sha256(Path(__file__)),
        "prompt_sha256": sha256(PROMPT),
        "blind_packet_sha256": sha256(PACKET),
        "reviewer_a_submission_sha256": sha256(REVIEWER_A),
        "reviewer_b_submission_sha256": sha256(REVIEWER_B),
        "agreement_report_sha256": sha256(AGREEMENT),
        "case_isolation": True,
        "schema_failure_retry_policy": (
            f"same frozen request, maximum {args.max_attempts} attempts, "
            "accept first exact-schema response"
        ),
        "frozen_judge_visible": False,
        "phase7_3_seed_visible": False,
        "external_tools_enabled": False,
        "web_access_enabled": False,
        "memory_enabled": False,
        "held_out_accessed": False,
        "raw_provider_responses_stored": False,
        "case_results": case_results,
        "adjudicated_claim_count": len(adjudicated_claims),
    }
    atomic_write_json(OUTPUT, adjudication)
    atomic_write_json(MANIFEST, manifest)
    if CHECKPOINT.exists():
        CHECKPOINT.unlink()
    print(
        json.dumps(
            {
                "completed": True,
                "model": manifest["resolved_model"],
                "cases": len(case_results),
                "claims": len(adjudicated_claims),
                "status": manifest["label_status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
