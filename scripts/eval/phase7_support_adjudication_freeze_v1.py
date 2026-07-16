#!/usr/bin/env python3
"""Freeze Phase 7.3.3-D3 Support Adjudication Protocol v1 without executing a provider."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

INPUTS = {
    "boundary_gold": ("crates/eval/datasets/pattern_extraction/phase7_3_3_d_boundary_gold_v1.json", "233c51af2a3c537be57a8838a8697444affea5b5b80e0835f98bab4ea567f1a0"),
    "reviewer_a_submission": ("crates/eval/reports/phase7_3_3_d_support_reviewer_a_completed_submission_v2.json", "2449858a296e48bd761686263dddaf4f90afdcdbc874b588e68f92c4f141c896"),
    "reviewer_b_submission": ("crates/eval/reports/phase7_3_3_d_support_reviewer_b_completed_submission_v2.json", "0e82057a80b67a7e0f7e389f6febd5d4f1379f7bbdc364eab344fb65d41c8db0"),
    "support_agreement_protocol": ("crates/eval/config/phase7_3_3_d_support_agreement_protocol_v1.json", "f4d9906e661cf16b02cdc1b1595349ebffe3f2a2c3940ae349692d3d41861d60"),
    "support_agreement_report": ("crates/eval/reports/phase7_3_3_d_support_agreement_report_v1.json", "973b09fc49c9492bd34e7413f3348b4c8e8310787aa4d59c5cdaef79da338372"),
    "support_disagreement_worklist": ("crates/eval/datasets/pattern_extraction/phase7_3_3_d_support_disagreement_worklist_v1.json", "1f5809cde1d15fec96be19ba7bbf6626e379da212ac0ba57605f9e0f9277ff81"),
    "support_agreement_outcome": ("crates/eval/reports/phase7_3_3_d_support_agreement_outcome_v1.json", "9164241713ad612336146438c0d059198c6ec34b37c8d920983a8d419717bcbc"),
    "support_stage_state_v7": ("crates/eval/datasets/pattern_extraction/phase7_3_3_d_support_stage_state_v7.json", "96a54550526ae020f41acdb4154bfc63da240fd4d0ccf325651bdb57db9e4d11"),
    "readiness_v18": ("crates/eval/reports/phase7_3_3_d1_reference_construction_readiness_v18.json", "91f73ab3c1f16d421a4ba7554d8311de3e07201a384a1b45a5d96f31060ae968"),
}

OUTPUTS = {
    "policy": "crates/eval/config/phase7_3_3_d_support_adjudication_execution_policy_v1.json",
    "prompt": "crates/eval/config/phase7_3_3_d_support_adjudicator_prompt_v1.md",
    "schema": "crates/eval/config/phase7_3_3_d_support_adjudication_output_schema_v1.json",
    "packet": "crates/eval/datasets/pattern_extraction/phase7_3_3_d_support_adjudication_packet_v1.json",
    "mapping": "crates/eval/reports/phase7_3_3_d_support_adjudication_private_option_mapping_v1.json",
    "protocol": "crates/eval/config/phase7_3_3_d_support_adjudication_protocol_v1.json",
    "fixtures": "crates/eval/reports/phase7_3_3_d_support_adjudication_contract_fixtures_v1.json",
    "manifest": "crates/eval/reports/phase7_3_3_d_support_adjudication_freeze_manifest_v1.json",
    "state": "crates/eval/datasets/pattern_extraction/phase7_3_3_d_support_stage_state_v8.json",
    "readiness": "crates/eval/reports/phase7_3_3_d1_reference_construction_readiness_v19.json",
}

OPTION_SEED = "phase7.3.3-d3-support-adjudication-option-order-v1"
ALLOWED_OPERATIONS = ["select_option_1", "select_option_2", "defer_for_human_review"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def write_frozen(path: Path, content: bytes, verify: bool) -> None:
    if verify:
        if not path.exists() or path.read_bytes() != content:
            raise RuntimeError(f"deterministic_replay_mismatch:{path}")
        return
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"refuse_to_overwrite_different_artifact:{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def verify_inputs() -> dict[str, dict[str, str]]:
    lineage: dict[str, dict[str, str]] = {}
    for key, (relative, expected) in INPUTS.items():
        path = ROOT / relative
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"frozen_input_hash_mismatch:{key}:expected={expected}:actual={actual}")
        lineage[key] = {"path": relative, "sha256": actual}
    return lineage


def output_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "phase7.3.3-d3-support-adjudication-output-schema-v1",
        "type": "object",
        "additionalProperties": False,
        "required": ["case_id", "adjudication_item_id", "boundary_claim_id", "decision"],
        "properties": {
            "case_id": {"type": "string", "minLength": 1},
            "adjudication_item_id": {"type": "string", "minLength": 1},
            "boundary_claim_id": {"type": "string", "minLength": 1},
            "decision": {
                "type": "object",
                "additionalProperties": False,
                "required": ["operation", "rationale"],
                "properties": {
                    "operation": {"enum": ALLOWED_OPERATIONS},
                    "rationale": {"type": "string", "minLength": 1},
                },
            },
        },
    }


def execution_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d3-support-adjudication-execution-policy-v1",
        "authoritative_result_policy": {
            "first_provider_content_authoritative": True,
            "invalid_json_schema_or_semantics_authoritative_negative": True,
            "semantic_retry": False,
            "transport_failure_before_content_resume_same_manifest": True,
        },
        "execution_controls": {
            "one_isolated_claim_per_request": True,
            "model": "gpt-5.4",
            "temperature": 0,
            "top_p": 1,
            "max_tokens": 4000,
            "response_format": {"type": "json_object"},
        },
        "data_handling": {
            "credential_env_name": "PHASE7_ATOMIC_JUDGE_API_KEY",
            "raw_provider_response_stored": False,
            "envelope_hash_recorded": True,
            "content_hash_recorded_before_parse": True,
            "held_out_loaded": False,
        },
        "execution_not_authorized_by_this_freeze": True,
    }


def prompt_text() -> str:
    return """# Phase 7.3.3-D3 Support Label Adjudicator Prompt v1

## System message
You adjudicate one frozen Support-label disagreement. The Boundary Claim, case evidence bundle, and both reviewer options are immutable. Use only the supplied claim and same-case evidence. Do not use outside knowledge, web search, memory, aggregate Agreement metrics, hidden option mapping, historical Gold/Silver labels, or held-out cases.

Choose exactly one operation:
- select_option_1: option_1 is better supported under the frozen Support definitions.
- select_option_2: option_2 is better supported under the frozen Support definitions.
- defer_for_human_review: neither option can be selected stably from the supplied evidence and frozen definitions.

Selection is operation-based. Do not emit or rewrite a Support label, citation, reason code, rationale, confidence, Claim text, Boundary span, or metadata. The deterministic adapter will copy the selected frozen reviewer decision. Do not prefer an option because of its position. Do not create, delete, split, merge, or modify Claims. Do not adjudicate same-label diagnostic follow-up items.

Return bare JSON only, with exactly these keys:
{"case_id":"<exact>","adjudication_item_id":"<exact>","boundary_claim_id":"<exact>","decision":{"operation":"select_option_1|select_option_2|defer_for_human_review","rationale":"<concise evidence-grounded explanation>"}}

## User message template
Adjudicate this single frozen label disagreement. Return bare JSON only.

ADJUDICATION_ITEM_JSON:
{ADJUDICATION_ITEM_JSON}
"""


def build_packet_and_mapping(worklist: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    label_items = worklist["label_adjudication_items"]
    if len(label_items) != 26 or worklist["summary"]["label_adjudication_count"] != 26:
        raise RuntimeError("expected_exactly_26_label_adjudication_items")
    if len(worklist["diagnostic_followup_items"]) != 46:
        raise RuntimeError("expected_46_diagnostic_followup_items")

    packet_items: list[dict[str, Any]] = []
    mapping_items: list[dict[str, Any]] = []
    first_counts = {"reviewer_a": 0, "reviewer_b": 0}
    seen_claims: set[str] = set()
    for position, source in enumerate(label_items, start=1):
        claim_id = source["boundary_claim_id"]
        if claim_id in seen_claims:
            raise RuntimeError(f"duplicate_adjudication_claim:{claim_id}")
        seen_claims.add(claim_id)
        digest = hashlib.sha256((OPTION_SEED + "\0" + claim_id).encode("utf-8")).digest()
        a_first = digest[0] % 2 == 0
        first_reviewer = "reviewer_a" if a_first else "reviewer_b"
        second_reviewer = "reviewer_b" if a_first else "reviewer_a"
        first_counts[first_reviewer] += 1
        option_1 = source["reviewer_a_decision"] if a_first else source["reviewer_b_decision"]
        option_2 = source["reviewer_b_decision"] if a_first else source["reviewer_a_decision"]
        item_id = f"support-adjudication-{position:03d}"
        packet_items.append(
            {
                "adjudication_item_id": item_id,
                "case_id": source["case_id"],
                "boundary_claim_id": claim_id,
                "immutable_claim_metadata": source["immutable_claim_metadata"],
                "same_case_evidence_bundle": source["same_case_evidence_bundle"],
                "option_1": option_1,
                "option_2": option_2,
            }
        )
        mapping_items.append(
            {
                "adjudication_item_id": item_id,
                "boundary_claim_id": claim_id,
                "option_1_source_reviewer": first_reviewer,
                "option_2_source_reviewer": second_reviewer,
                "option_order_digest_sha256": hashlib.sha256(
                    (OPTION_SEED + "\0" + claim_id).encode("utf-8")
                ).hexdigest(),
            }
        )
    if first_counts != {"reviewer_a": 13, "reviewer_b": 13}:
        raise RuntimeError(f"unexpected_option_balance:{first_counts}")

    packet = {
        "schema_version": 1,
        "packet_id": "phase7.3.3-d3-support-adjudication-packet-v1",
        "status": "frozen_reviewer_blind_packet_execution_not_started",
        "source_worklist_sha256": INPUTS["support_disagreement_worklist"][1],
        "item_count": len(packet_items),
        "one_isolated_claim_per_request": True,
        "reviewer_identity_visible": False,
        "priority_rank_visible": False,
        "aggregate_agreement_metrics_visible": False,
        "diagnostic_followup_visible": False,
        "support_gold_visible": False,
        "held_out_accessed": False,
        "allowed_output_operations": ALLOWED_OPERATIONS,
        "items": packet_items,
    }
    mapping = {
        "schema_version": 1,
        "mapping_id": "phase7.3.3-d3-support-adjudication-private-option-mapping-v1",
        "status": "frozen_adapter_only_not_adjudicator_visible",
        "option_order_algorithm": "sha256(seed + NUL + boundary_claim_id) first-byte parity",
        "option_order_seed": OPTION_SEED,
        "source_worklist_sha256": INPUTS["support_disagreement_worklist"][1],
        "item_count": len(mapping_items),
        "option_1_source_counts": first_counts,
        "adjudicator_visible": False,
        "items": mapping_items,
    }
    return packet, mapping


def protocol(lineage: dict[str, dict[str, str]], generated: dict[str, str]) -> dict[str, Any]:
    all_lineage = copy.deepcopy(lineage)
    for key, relative in OUTPUTS.items():
        if key in generated:
            all_lineage[key] = {"path": relative, "sha256": generated[key]}
    all_lineage["freeze_script"] = {
        "path": "scripts/eval/phase7_support_adjudication_freeze_v1.py",
        "sha256": sha256(Path(__file__)),
    }
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d3-support-label-adjudication-protocol-v1",
        "phase": "Phase 7.3.3-D3 Support Label Adjudication",
        "status": "frozen_before_contract_fixtures_and_execution",
        "research_object": "adjudication of exactly 26 frozen Support-label disagreements from D2",
        "entry_gate": {
            "d2_agreement_computed": True,
            "claim_count_analyzed": 118,
            "label_disagreement_count": 26,
            "diagnostic_followup_count": 46,
            "boundary_gold_frozen": True,
            "support_gold_frozen": False,
            "held_out_accessed": False,
        },
        "artifact_lineage": all_lineage,
        "minimal_authorization": {
            "allowed_operations": ALLOWED_OPERATIONS,
            "selection_semantics": "select one immutable reviewer option or defer; adjudicator never emits a replacement label",
            "selected_decision_reconstruction": "deterministically copy the complete selected frozen reviewer decision through the private option mapping",
            "defer_semantics": "no final Support label is authorized until bounded human review resolves the item",
        },
        "immutable_fields": [
            "boundary_claim_id",
            "case_id",
            "claim_text",
            "claim_type",
            "claim_role",
            "source_field",
            "source_index",
            "source_span",
            "source_occurrence_index",
            "anchor_id",
            "anchor_group",
            "material",
            "claim_origin",
            "reviewer_a_submission",
            "reviewer_b_submission",
        ],
        "forbidden_actions": [
            "create_claim",
            "delete_claim",
            "split_claim",
            "merge_claim",
            "modify_boundary",
            "rewrite_claim_text",
            "emit_new_support_label",
            "rewrite_reviewer_submission",
            "adjudicate_same_label_diagnostic_followup",
            "access_support_gold",
            "access_held_out_cases",
        ],
        "adjudicator_visibility": {
            "visible": ["immutable_claim_metadata", "same_case_evidence_bundle", "option_1", "option_2"],
            "prohibited": [
                "source_reviewer_identity",
                "private_option_mapping",
                "priority_rank",
                "aggregate_agreement_metrics",
                "diagnostic_followup_items",
                "historical_gold_or_silver",
                "held_out_cases",
            ],
        },
        "execution_contract": {
            "one_isolated_claim_per_request": True,
            "bare_json_only": True,
            "exact_item_case_and_claim_ids_required": True,
            "first_provider_content_authoritative": True,
            "semantic_retry": False,
            "execution_not_started_by_protocol_freeze": True,
        },
        "completion_gate": {
            "all_26_items_require_terminal_results": True,
            "any_defer_blocks_support_gold_freeze": True,
            "adapter_replay_required": True,
            "support_gold_freeze_in_this_stage": False,
        },
        "guards": {
            "boundary_mutation_allowed": False,
            "new_claim_creation_allowed": False,
            "claim_deletion_allowed": False,
            "reviewer_submission_mutation_allowed": False,
            "diagnostic_followup_label_change_allowed": False,
            "support_gold_freeze_allowed": False,
            "held_out_accessed": False,
        },
        "next_authorized_stage": "execute_support_adjudication_v1",
    }


def validate_output(content: str, item: dict[str, Any]) -> tuple[bool, str]:
    try:
        value = json.loads(content)
    except Exception:
        return False, "invalid_json"
    if not isinstance(value, dict):
        return False, "top_level_not_object"
    if set(value) != {"case_id", "adjudication_item_id", "boundary_claim_id", "decision"}:
        return False, "top_level_keys_invalid"
    if value["case_id"] != item["case_id"]:
        return False, "case_id_mismatch"
    if value["adjudication_item_id"] != item["adjudication_item_id"]:
        return False, "adjudication_item_id_mismatch"
    if value["boundary_claim_id"] != item["boundary_claim_id"]:
        return False, "boundary_claim_id_mismatch"
    decision = value["decision"]
    if not isinstance(decision, dict) or set(decision) != {"operation", "rationale"}:
        return False, "decision_keys_invalid"
    if decision["operation"] not in ALLOWED_OPERATIONS:
        return False, "operation_invalid"
    if not isinstance(decision["rationale"], str) or not decision["rationale"].strip():
        return False, "rationale_invalid"
    return True, "pass"


def run_fixtures(packet: dict[str, Any], protocol_sha: str, schema_sha: str) -> dict[str, Any]:
    item = packet["items"][0]
    base = {
        "case_id": item["case_id"],
        "adjudication_item_id": item["adjudication_item_id"],
        "boundary_claim_id": item["boundary_claim_id"],
        "decision": {"operation": "select_option_1", "rationale": "Option 1 better preserves the evidence-supported scope."},
    }
    fixtures: list[tuple[str, str, bool, str]] = []
    for name, operation in [
        ("valid_select_option_1", "select_option_1"),
        ("valid_select_option_2", "select_option_2"),
        ("valid_defer", "defer_for_human_review"),
    ]:
        value = copy.deepcopy(base)
        value["decision"]["operation"] = operation
        fixtures.append((name, json.dumps(value), True, "pass"))
    invalids: list[tuple[str, Any, str]] = []
    value = copy.deepcopy(base); value["case_id"] = "wrong"; invalids.append(("wrong_case", value, "case_id_mismatch"))
    value = copy.deepcopy(base); value["adjudication_item_id"] = "wrong"; invalids.append(("wrong_item", value, "adjudication_item_id_mismatch"))
    value = copy.deepcopy(base); value["boundary_claim_id"] = "wrong"; invalids.append(("wrong_claim", value, "boundary_claim_id_mismatch"))
    value = copy.deepcopy(base); value["decision"]["operation"] = "supported"; invalids.append(("new_label_as_operation", value, "operation_invalid"))
    value = copy.deepcopy(base); value["decision"]["rationale"] = ""; invalids.append(("empty_rationale", value, "rationale_invalid"))
    value = copy.deepcopy(base); value["support_label"] = "supported"; invalids.append(("extra_support_label", value, "top_level_keys_invalid"))
    value = copy.deepcopy(base); value["decision"]["support_label"] = "supported"; invalids.append(("decision_rewrite_field", value, "decision_keys_invalid"))
    value = copy.deepcopy(base); value["boundary_span"] = {"start": 0, "end": 1}; invalids.append(("boundary_mutation_field", value, "top_level_keys_invalid"))
    for name, value, reason in invalids:
        fixtures.append((name, json.dumps(value), False, reason))
    fixtures.append(("markdown_fence_rejected", "```json\n" + json.dumps(base) + "\n```", False, "invalid_json"))

    rows = []
    for name, content, expected_valid, expected_reason in fixtures:
        actual_valid, actual_reason = validate_output(content, item)
        passed = actual_valid == expected_valid and actual_reason == expected_reason
        rows.append({
            "fixture_id": name,
            "expected_valid": expected_valid,
            "expected_reason": expected_reason,
            "actual_valid": actual_valid,
            "actual_reason": actual_reason,
            "pass": passed,
        })
    passed_count = sum(row["pass"] for row in rows)
    if passed_count != len(rows):
        raise RuntimeError("support_adjudication_contract_fixture_failure")
    return {
        "schema_version": 1,
        "fixture_report_id": "phase7.3.3-d3-support-adjudication-contract-fixtures-v1",
        "status": "all_pass",
        "protocol_sha256": protocol_sha,
        "output_schema_sha256": schema_sha,
        "fixture_count": len(rows),
        "passed_count": passed_count,
        "failed_count": 0,
        "fixtures": rows,
        "execution_authorized_after_fixtures": True,
        "provider_called": False,
        "held_out_accessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify = args.verify

    lineage = verify_inputs()
    worklist = load_json(ROOT / INPUTS["support_disagreement_worklist"][0])
    report = load_json(ROOT / INPUTS["support_agreement_report"][0])
    state_v7 = load_json(ROOT / INPUTS["support_stage_state_v7"][0])
    readiness_v18 = load_json(ROOT / INPUTS["readiness_v18"][0])
    if report["label_agreement"]["disagreement_count"] != 26:
        raise RuntimeError("agreement_report_disagreement_count_not_26")
    if state_v7["next_authorized_stage"] != "freeze_support_adjudication_protocol_v1":
        raise RuntimeError("state_v7_does_not_authorize_protocol_freeze")
    if readiness_v18["next_authorized_stage"] != "freeze_support_adjudication_protocol_v1":
        raise RuntimeError("readiness_v18_does_not_authorize_protocol_freeze")

    policy = execution_policy()
    schema = output_schema()
    packet, mapping = build_packet_and_mapping(worklist)
    prompt = prompt_text().encode("utf-8")

    preliminary = {
        "policy": json_bytes(policy),
        "prompt": prompt,
        "schema": json_bytes(schema),
        "packet": json_bytes(packet),
        "mapping": json_bytes(mapping),
    }
    for key, content in preliminary.items():
        write_frozen(ROOT / OUTPUTS[key], content, verify)
    generated = {key: sha256(ROOT / OUTPUTS[key]) for key in preliminary}

    protocol_value = protocol(lineage, generated)
    write_frozen(ROOT / OUTPUTS["protocol"], json_bytes(protocol_value), verify)
    protocol_sha = sha256(ROOT / OUTPUTS["protocol"])

    fixtures = run_fixtures(packet, protocol_sha, generated["schema"])
    write_frozen(ROOT / OUTPUTS["fixtures"], json_bytes(fixtures), verify)
    fixtures_sha = sha256(ROOT / OUTPUTS["fixtures"])

    manifest = {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d3-support-adjudication-freeze-manifest-v1",
        "status": "frozen_ready_for_first_execution",
        "protocol_sha256": protocol_sha,
        "execution_policy_sha256": generated["policy"],
        "prompt_sha256": generated["prompt"],
        "output_schema_sha256": generated["schema"],
        "adjudication_packet_sha256": generated["packet"],
        "private_option_mapping_sha256": generated["mapping"],
        "contract_fixtures_sha256": fixtures_sha,
        "freeze_script_sha256": sha256(Path(__file__)),
        "frozen_inputs": lineage,
        "item_count": 26,
        "priority_execution_summary": {
            "supported_vs_unsupported": 5,
            "partially_supported_vs_unsupported": 3,
            "supported_vs_partially_supported": 18,
            "not_assessable_mismatch": 0,
        },
        "option_1_source_balance": mapping["option_1_source_counts"],
        "execution_started": False,
        "provider_called": False,
        "support_gold_frozen": False,
        "held_out_accessed": False,
        "next_authorized_stage": "execute_support_adjudication_v1",
    }
    write_frozen(ROOT / OUTPUTS["manifest"], json_bytes(manifest), verify)
    manifest_sha = sha256(ROOT / OUTPUTS["manifest"])

    state = copy.deepcopy(state_v7)
    state["schema_version"] = 8
    state["state_id"] = "phase7.3.3-d1-b-support-stage-state-v8"
    state["support_state"] = "support_adjudication_protocol_v1_frozen_execution_authorized"
    state["blocked_reason"] = None
    state["support_agreement_allowed"] = False
    state["support_agreement_computed"] = True
    state["support_adjudication_allowed"] = True
    state["support_adjudication_started"] = False
    state["support_adjudication_completed"] = False
    state["support_gold_frozen"] = False
    state["support_gold_sha256"] = None
    state["next_authorized_stage"] = "execute_support_adjudication_v1"
    state["support_adjudication_protocol_v1"] = {
        "protocol_sha256": protocol_sha,
        "execution_policy_sha256": generated["policy"],
        "prompt_sha256": generated["prompt"],
        "output_schema_sha256": generated["schema"],
        "packet_sha256": generated["packet"],
        "private_option_mapping_sha256": generated["mapping"],
        "contract_fixtures_sha256": fixtures_sha,
        "freeze_manifest_sha256": manifest_sha,
        "label_adjudication_item_count": 26,
        "diagnostic_followup_item_count": 46,
        "option_1_source_balance": mapping["option_1_source_counts"],
        "execution_started": False,
        "support_gold_frozen": False,
    }
    write_frozen(ROOT / OUTPUTS["state"], json_bytes(state), verify)
    state_sha = sha256(ROOT / OUTPUTS["state"])

    readiness = copy.deepcopy(readiness_v18)
    readiness["schema_version"] = 19
    readiness["readiness_id"] = "phase7.3.3-d1-reference-construction-readiness-v19"
    readiness["status"] = "support_adjudication_protocol_v1_frozen_execution_authorized"
    readiness["artifact_lineage"]["readiness_v18_sha256"] = INPUTS["readiness_v18"][1]
    readiness["artifact_lineage"]["support_stage_state_v7_sha256"] = INPUTS["support_stage_state_v7"][1]
    readiness["artifact_lineage"]["support_adjudication_protocol_v1_sha256"] = protocol_sha
    readiness["artifact_lineage"]["support_adjudication_execution_policy_v1_sha256"] = generated["policy"]
    readiness["artifact_lineage"]["support_adjudicator_prompt_v1_sha256"] = generated["prompt"]
    readiness["artifact_lineage"]["support_adjudication_output_schema_v1_sha256"] = generated["schema"]
    readiness["artifact_lineage"]["support_adjudication_packet_v1_sha256"] = generated["packet"]
    readiness["artifact_lineage"]["support_adjudication_private_option_mapping_v1_sha256"] = generated["mapping"]
    readiness["artifact_lineage"]["support_adjudication_contract_fixtures_v1_sha256"] = fixtures_sha
    readiness["artifact_lineage"]["support_adjudication_freeze_manifest_v1_sha256"] = manifest_sha
    readiness["artifact_lineage"]["support_stage_state_v8_sha256"] = state_sha
    readiness["reference_status"]["support_adjudication_protocol_frozen"] = True
    readiness["reference_status"]["support_adjudication_started"] = False
    readiness["reference_status"]["support_adjudication_completed"] = False
    readiness["reference_status"]["support_gold_frozen"] = False
    readiness["next_authorized_stage"] = "execute_support_adjudication_v1"
    readiness["support_review_allowed"] = False
    readiness["support_agreement_allowed"] = False
    readiness["support_adjudication_allowed"] = True
    readiness["support_gold_frozen"] = False
    readiness["held_out_accessed"] = False
    write_frozen(ROOT / OUTPUTS["readiness"], json_bytes(readiness), verify)

    print("Phase 7.3.3-D3 Support Adjudication Protocol v1 frozen")
    for key in OUTPUTS:
        print(f"{key}: {OUTPUTS[key]} sha256={sha256(ROOT / OUTPUTS[key])}")
    print(f"contract_fixtures: {fixtures['passed_count']}/{fixtures['fixture_count']} PASS")
    print("provider_called: false")
    print("next_authorized_stage: execute_support_adjudication_v1")


if __name__ == "__main__":
    main()
