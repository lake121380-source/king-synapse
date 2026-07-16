#!/usr/bin/env python3
"""Freeze and audit the sealed Phase 7.3.3-D confirmatory successor inventory.

The inventory path is deliberately metadata-only.  Candidate and Evidence
content is constructed in memory solely to compute commitments; it is never
serialized by this adapter.  A separate successor adapter may open only the
selected commitments after the explicit opening gate passes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets"
PATTERN = DATA / "pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

SOURCE = DATA / "memory_intelligence/agent_memory_benchmark.toml"
STATE_99 = PATTERN / "phase7_3_3_d_support_stage_state_v99.json"
READY_110 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v110.json"
FINAL_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_final_audit_receipt_frame_v2_1.json"
POWER_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_power_gate_report_frame_v2.json"
SAMPLE_SIZE = REPORTS / "phase7_3_3_d_multi_claim_successor_sample_size_freeze_frame_v2.json"

DESIGN_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_design_protocol_v1.json"
COMPOSITION = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_composition_contract_v1.json"
SAMPLING_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_sampling_policy_v1.json"
DESIGN_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_design_fixtures_v1.json"
DESIGN_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_design_manifest_v1.json"
DESIGN_OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_design_outcome_v1.json"
DESIGN_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_design_audit_v1.jsonl"
DESIGN_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_design_receipt_v1.json"
STATE_100 = PATTERN / "phase7_3_3_d_support_stage_state_v100.json"
READY_111 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v111.json"

INVENTORY = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_source_inventory_v1.json"
ELIGIBILITY = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_eligibility_audit_v1.json"
OVERLAP = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_overlap_audit_v1.json"
ELIGIBLE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_eligible_inventory_v1.json"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_worklist_v1.json"
INVENTORY_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_fixtures_v1.json"
INVENTORY_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_manifest_v1.json"
INVENTORY_OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_outcome_v1.json"
INVENTORY_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_audit_v1.jsonl"
INVENTORY_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_inventory_receipt_v1.json"
STATE_101 = PATTERN / "phase7_3_3_d_support_stage_state_v101.json"
READY_112 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v112.json"

PREREG = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_preregistration_v1.json"
OPEN_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_dataset_opening_policy_v1.json"
GATE_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_fixtures_v1.json"
GATE_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_manifest_v1.json"
GATE_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_report_v1.json"
GATE_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_audit_v1.jsonl"
GATE_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_receipt_v1.json"
STATE_102 = PATTERN / "phase7_3_3_d_support_stage_state_v102.json"
READY_113 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v113.json"

PILOT_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_pilot_protocol_frame_v2.json"
PILOT_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_pilot_execution_policy_frame_v2.json"
CANDIDATE_PROMPT = CONFIG / "phase7_3_3_d_multi_claim_successor_candidate_arm_prompt_frame_v2.md"
ATOMIC_PROMPT = CONFIG / "phase7_3_3_d_multi_claim_successor_atomic_arm_prompt_frame_v2.md"
CANDIDATE_SCHEMA = CONFIG / "phase7_3_3_d_multi_claim_successor_candidate_arm_schema_frame_v2.json"
ATOMIC_SCHEMA = CONFIG / "phase7_3_3_d_multi_claim_successor_atomic_arm_schema_frame_v2.json"

OVERLAP_INPUTS = [
    REPORTS / "phase7_3_3_d_independent_pilot_source_inventory_v1.json",
    PATTERN / "phase7_3_3_d_independent_pilot_selected_dataset_v1.json",
    REPORTS / "phase7_3_3_d_multi_claim_successor_source_inventory_v1.json",
    PATTERN / "phase7_3_3_d_multi_claim_successor_selected_dataset_v1.json",
    REPORTS / "phase7_3_3_d_multi_claim_successor_source_inventory_v2.json",
    PATTERN / "phase7_3_3_d_multi_claim_successor_selected_dataset_v2.json",
]

SOURCE_SHA256 = "592e9f8cd5c893bc1b88e141fe6963a810ad70919bcd40b53203d642629a4cc3"
STATE_99_SHA256 = "bd2cb269e4a3e18546bd00e50c374b3f999e8dde9bc2619f564b8b986cf41752"
READY_110_SHA256 = "9cb5a408d47fda2b8ef948c7e568c52a95296d19b83fe93c19725c8d6e538a90"
FINAL_RECEIPT_SHA256 = "2f7f5558fc33ead9ebed727f4e2a73bc046def2f791ffd72c6c98c1ede2cc333"
POWER_REPORT_SHA256 = "6959dc0604a1c54d7723dcb4fc27867fa6c237174fa8d8eaa422dcb989bba289"

DESIGN_CUR = "design_sealed_confirmatory_inventory_successor_after_authoritative_shortfall"
INVENTORY_CUR = "construct_metadata_only_confirmatory_inventory_v1"
GATE_CUR = "preregister_and_evaluate_confirmatory_dataset_opening_gate_v1"
OPEN_NEXT = "open_selected_confirmatory_dataset_v1"
BLOCK_NEXT = "blocked_confirmatory_inventory_opening_gate_v1_authoritative_negative"
SEED = "phase7.3.3-d-multi-claim-confirmatory-v1-20260716"
LABELS = ["supported", "partially_supported", "unsupported", "not_assessable"]
CATEGORIES = [
    "contextual_constraint",
    "failure_override",
    "failure_vs_recency_failure_wins",
    "failure_vs_recency_recency_wins",
    "no_intervention",
    "preference_evolution",
    "reliability_conflict",
    "reliability_vs_recency_recency_wins",
    "reliability_vs_recency_reliability_wins",
    "temporal_update",
]


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return hb(canonical_bytes(value))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def once(path: Path, value: Any) -> str:
    body = value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("immutable_artifact_mismatch:" + rel(path))
        return hb(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hb(body)


def append_single_event(path: Path, event: dict[str, Any]) -> str:
    body = (json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("append_only_audit_mismatch:" + rel(path))
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(body)
    return hb(body)


def normalized_evidence(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, item in enumerate(scenario["memory"], start=1):
        rows.append({
            "evidence_id": f"{scenario['id']}-evidence-{index:02d}",
            "source_index": index - 1,
            "content": item["content"],
            "kind": item["kind"],
            "confidence": item["confidence"],
            "importance": item["importance"],
            "recently_accessed": item["recently_accessed"],
            "relevant": item["relevant"],
            "turn": item["turn"],
            "role": item["role"],
        })
    return rows


def compact(value: str) -> str:
    return " ".join(value.split())


def constructed_case(scenario: dict[str, Any]) -> dict[str, Any]:
    """Mechanically construct content without emitting it from this adapter."""
    evidence = normalized_evidence(scenario)
    by_role = {item["role"]: item for item in evidence}
    top = next(item for item, raw in zip(evidence, scenario["memory"]) if raw["label"] == scenario["expected_top"])
    background = by_role["background_state"]
    competitor = by_role["competing_prior"]
    source_category = scenario["category"]
    wrong_category = CATEGORIES[(CATEGORIES.index(source_category) + 1 + int(scenario["template_variant"])) % len(CATEGORIES)]
    claims = [
        {
            "claim_role": "direct_top_memory",
            "text": f"At turn {top['turn']}, the evidence records: {compact(top['content'])}",
            "support_label": "supported",
            "evidence_ids": [top["evidence_id"]],
        },
        {
            "claim_role": "direct_background_memory",
            "text": f"A source-specific background memory states: {compact(background['content'])}",
            "support_label": "supported",
            "evidence_ids": [background["evidence_id"]],
        },
        {
            "claim_role": "scope_overclaim",
            "text": f"The evidence records {compact(top['content'])}; this alone establishes the same result for every context and every future time.",
            "support_label": "partially_supported",
            "evidence_ids": [top["evidence_id"]],
        },
        {
            "claim_role": "contradicted_absence",
            "text": f"No evidence item records the following source-specific observation: {compact(top['content'])}",
            "support_label": "unsupported",
            "evidence_ids": [top["evidence_id"]],
        },
        {
            "claim_role": "priority_overclaim",
            "text": f"The evidence includes {compact(competitor['content'])}; therefore this one item conclusively determines the answer regardless of all other memories.",
            "support_label": "partially_supported",
            "evidence_ids": [competitor["evidence_id"]],
        },
        {
            "claim_role": "invented_category_assertion",
            "text": f"An evidence item explicitly identifies the scenario category as {wrong_category}.",
            "support_label": "unsupported",
            "evidence_ids": [],
        },
    ]
    permutations = [
        [0, 3, 2, 1, 5, 4],
        [1, 2, 5, 0, 4, 3],
        [2, 0, 4, 3, 1, 5],
        [5, 1, 3, 4, 0, 2],
    ]
    ordered = [claims[index] for index in permutations[int(scenario["template_variant"])]]
    candidate = "\n".join(claim["text"] for claim in ordered)
    return {
        "candidate_id": "mc-confirmatory-" + scenario["id"],
        "source_scenario_id": scenario["id"],
        "source_identity": "agent_memory_benchmark:test:" + scenario["id"],
        "source_category": source_category,
        "template_variant": scenario["template_variant"],
        "timeline_length": scenario["timeline_length"],
        "candidate_text": candidate,
        "candidate_sha256": hb(candidate.encode("utf-8")),
        "evidence_bundle": evidence,
        "evidence_bundle_sha256": canonical_sha(evidence),
        "claims": ordered,
    }


def test_cases() -> list[dict[str, Any]]:
    document = tomllib.loads(SOURCE.read_text(encoding="utf-8"))
    scenarios = [row for row in document["scenario"] if row["split"] == "test"]
    return [constructed_case(row) for row in scenarios]


def design_protocol() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-confirmatory-inventory-design-v1",
        "status": "frozen_before_metadata_inventory_construction",
        "entry_gate": DESIGN_CUR,
        "study_role": "independent_confirmatory_successor_after_authoritative_exploratory_inventory_shortfall",
        "source_lineage": {
            "dataset_path": rel(SOURCE),
            "dataset_sha256": SOURCE_SHA256,
            "split": "test",
            "phase7_multi_claim_pilot_usage": False,
            "phase7_independent_pilot_split": "validation",
            "prior_phase6_benchmark_usage_disclosed": True,
            "generality_claim_beyond_this_confirmatory_replication_allowed": False,
        },
        "sealed_processing": {
            "permitted_before_opening_gate": ["id", "sha256", "length", "count", "category", "template_variant", "stratum", "overlap_boolean"],
            "candidate_content_serialization": False,
            "evidence_content_serialization": False,
            "selected_content_opening": "explicit_successor_gate_only",
            "unselected_content_opening": False,
        },
        "required_sequence": [
            "freeze_inventory_design",
            "construct_metadata_only_inventory",
            "audit_eligibility_and_overlap",
            "freeze_selected_ids_and_hashes",
            "freeze_confirmatory_preregistration",
            "evaluate_opening_gate",
            "open_selected_content_only_if_gate_passes",
        ],
        "failure_discipline": {
            "inventory_shortfall": "authoritative_negative_no_manual_backfill",
            "post_selection_replacement": False,
            "outcome_dependent_selection": False,
            "frozen_artifact_mutation": False,
        },
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": INVENTORY_CUR,
    }


def composition_contract() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract_id": "phase7.3.3-d-multi-claim-successor-confirmatory-composition-contract-v1",
        "status": "frozen_before_test_split_parameter_instantiation",
        "source_specific": True,
        "source_fields_used": ["scenario.id", "scenario.category", "scenario.template_variant", "scenario.timeline_length", "scenario.expected_top", "scenario.memory"],
        "source_fields_not_emitted_before_gate": ["query", "expected_reason", "expected_top", "memory.content"],
        "candidate_unit_count": 6,
        "candidate_serialization": "six LF-delimited natural-language claims",
        "evidence_serialization": "canonical JSON of six normalized source memories",
        "claim_families": ["direct_top_memory", "direct_background_memory", "scope_overclaim", "contradicted_absence", "priority_overclaim", "invented_category_assertion"],
        "position_permutation": "frozen_by_source_template_variant_0_to_3",
        "not_v2_signal_template_family": True,
        "mechanical_reference_labels": {"supported": 2, "partially_supported": 2, "unsupported": 2, "not_assessable": 0},
        "reference_labels_are_not_serialized_in_inventory": True,
        "semantic_rewrite_or_manual_backfill_allowed": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def sampling_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d-multi-claim-successor-confirmatory-sampling-policy-v1",
        "status": "frozen_before_inventory_construction",
        "inventory_target": 80,
        "selected_target": 40,
        "required_confirmatory_clusters": 40,
        "selection_unit": "unique_source_specific_composite_candidate",
        "eligibility": {
            "source_split": "test",
            "unique_candidate_id": True,
            "six_claim_lines": True,
            "six_evidence_items": True,
            "candidate_hash_unique": True,
            "evidence_hash_unique": True,
            "prior_phase7_candidate_hash_overlap": False,
            "prior_phase7_evidence_hash_overlap": False,
            "prior_phase7_source_identity_overlap": False,
        },
        "stratification": "exactly_four_selected_per_each_of_ten_source_categories",
        "within_stratum_rank": "sha256(seed|category|candidate_id|candidate_sha256|evidence_bundle_sha256)",
        "rank_seed": SEED,
        "selection_before_content_open": True,
        "selection_before_outcomes": True,
        "shortfall_action": "freeze_authoritative_negative_and_do_not_open",
        "unselected_content_opened": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def design_fixtures() -> dict[str, Any]:
    docs = [design_protocol(), composition_contract(), sampling_policy()]
    checks = [
        ("source_hash_pinned", SOURCE.exists() and sha(SOURCE) == SOURCE_SHA256),
        ("source_specific_not_v2_template", docs[1]["source_specific"] and docs[1]["not_v2_signal_template_family"]),
        ("metadata_only_before_gate", docs[0]["sealed_processing"]["candidate_content_serialization"] is False and docs[0]["sealed_processing"]["evidence_content_serialization"] is False),
        ("power_sample_size_inherited", docs[2]["required_confirmatory_clusters"] == 40),
        ("exact_category_allocation", docs[2]["stratification"].startswith("exactly_four")),
        ("no_manual_backfill", docs[2]["shortfall_action"].startswith("freeze_authoritative_negative")),
        ("phase6_lineage_disclosed", docs[0]["source_lineage"]["prior_phase6_benchmark_usage_disclosed"] is True),
        ("confirmatory_closed", all(doc["confirmatory_dataset_opened"] is False for doc in docs)),
        ("runtime_off", all(doc["runtime_integration_authorized"] is False for doc in docs)),
    ]
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-inventory-design-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def immutable_input_checks() -> dict[str, bool]:
    expected = {
        SOURCE: SOURCE_SHA256,
        STATE_99: STATE_99_SHA256,
        READY_110: READY_110_SHA256,
        FINAL_RECEIPT: FINAL_RECEIPT_SHA256,
        POWER_REPORT: POWER_REPORT_SHA256,
    }
    checks = {"input_hash:" + rel(path): path.exists() and sha(path) == digest for path, digest in expected.items()}
    checks["sample_size_exists"] = SAMPLE_SIZE.exists()
    checks.update({"overlap_input_exists:" + rel(path): path.exists() for path in OVERLAP_INPUTS})
    if all(checks.values()):
        state, readiness = load(STATE_99), load(READY_110)
        checks.update({
            "state_gate": state["next_authorized_stage"] == DESIGN_CUR,
            "readiness_gate": readiness["next_authorized_stage"] == DESIGN_CUR,
            "authoritative_shortfall": state["multi_claim_successor_confirmatory_inventory_shortfall_authoritative"] is True,
            "required_clusters_40": load(SAMPLE_SIZE)["sample_size_clusters"] == 40,
            "confirmatory_closed": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
        })
    return checks


def design_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-inventory-design-manifest-v1",
        "status": "frozen_before_metadata_inventory_construction",
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): sha(path) for path in [SOURCE, STATE_99, READY_110, FINAL_RECEIPT, POWER_REPORT, SAMPLE_SIZE, *OVERLAP_INPUTS]},
        "frozen_design_artifacts": {rel(path): sha(path) for path in [DESIGN_PROTOCOL, COMPOSITION, SAMPLING_POLICY, DESIGN_FIXTURES]},
        "candidate_or_evidence_content_emitted": False,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": INVENTORY_CUR,
    }


def design_preflight() -> dict[str, Any]:
    checks = immutable_input_checks()
    outputs = [DESIGN_PROTOCOL, COMPOSITION, SAMPLING_POLICY, DESIGN_FIXTURES, DESIGN_MANIFEST, DESIGN_OUTCOME, DESIGN_AUDIT, DESIGN_RECEIPT, STATE_100, READY_111]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def freeze_design() -> dict[str, Any]:
    checked = design_preflight()
    if checked["status"] != "PASS":
        return checked
    once(DESIGN_PROTOCOL, design_protocol())
    once(COMPOSITION, composition_contract())
    once(SAMPLING_POLICY, sampling_policy())
    fixture_hash = once(DESIGN_FIXTURES, design_fixtures())
    manifest_hash = once(DESIGN_MANIFEST, design_manifest())
    outcome_hash = once(DESIGN_OUTCOME, {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-confirmatory-inventory-design-outcome-v1",
        "status": "PASS_design_frozen_metadata_inventory_authorized",
        "manifest_sha256": manifest_hash,
        "fixtures_sha256": fixture_hash,
        "candidate_or_evidence_content_emitted": False,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": INVENTORY_CUR,
    })
    audit_hash = append_single_event(DESIGN_AUDIT, {
        "event_id": "confirmatory-inventory-design-v1-frozen",
        "event_type": "immutable_design_freeze",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "content_emitted": False,
        "provider_called": False,
    })
    state, readiness = copy.deepcopy(load(STATE_99)), copy.deepcopy(load(READY_110))
    lineage = {
        "multi_claim_successor_confirmatory_inventory_design_protocol_v1_sha256": sha(DESIGN_PROTOCOL),
        "multi_claim_successor_confirmatory_composition_contract_v1_sha256": sha(COMPOSITION),
        "multi_claim_successor_confirmatory_sampling_policy_v1_sha256": sha(SAMPLING_POLICY),
        "multi_claim_successor_confirmatory_inventory_design_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_inventory_design_outcome_v1_sha256": outcome_hash,
        "multi_claim_successor_confirmatory_inventory_design_audit_v1_sha256": audit_hash,
    }
    update = {
        "status": "confirmatory_inventory_design_v1_frozen_metadata_inventory_authorized",
        "next_authorized_stage": INVENTORY_CUR,
        "multi_claim_successor_confirmatory_inventory_design_v1_frozen": True,
        "multi_claim_successor_confirmatory_inventory_metadata_constructed": False,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 100, "state_id": "phase7.3.3-d-support-stage-state-v100"})
    readiness.update({"schema_version": 111, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v111"})
    state_hash = once(STATE_100, state)
    readiness["artifact_lineage"]["support_stage_state_v100_sha256"] = state_hash
    readiness_hash = once(READY_111, readiness)
    receipt_hash = once(DESIGN_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-inventory-design-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "candidate_or_evidence_content_emitted": False,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": INVENTORY_CUR,
    })
    return {"status": "PASS", "manifest_sha256": manifest_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": INVENTORY_CUR}


def verify_design() -> dict[str, Any]:
    paths = [DESIGN_PROTOCOL, COMPOSITION, SAMPLING_POLICY, DESIGN_FIXTURES, DESIGN_MANIFEST, DESIGN_OUTCOME, DESIGN_AUDIT, DESIGN_RECEIPT, STATE_100, READY_111]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        checks.update({
            "design_protocol_replay": load(DESIGN_PROTOCOL) == design_protocol(),
            "composition_replay": load(COMPOSITION) == composition_contract(),
            "sampling_policy_replay": load(SAMPLING_POLICY) == sampling_policy(),
            "fixtures_replay": load(DESIGN_FIXTURES) == design_fixtures(),
            "manifest_replay": load(DESIGN_MANIFEST) == design_manifest(),
            "receipt_lineage": load(DESIGN_RECEIPT)["state_sha256"] == sha(STATE_100) and load(DESIGN_RECEIPT)["readiness_sha256"] == sha(READY_111),
            "state_gate": load(STATE_100)["next_authorized_stage"] == load(READY_111)["next_authorized_stage"] == INVENTORY_CUR,
            "confirmatory_closed": load(STATE_100)["confirmatory_dataset_opened"] is False and load(READY_111)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(STATE_100)["runtime_integration_authorized"] is False and load(READY_111)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_100)["next_authorized_stage"] if STATE_100.exists() else None}


def collect_prior_fingerprints() -> dict[str, set[str]]:
    candidate_hashes: set[str] = set()
    evidence_hashes: set[str] = set()
    source_identities: set[str] = set()

    def visit(value: Any, key: str = "") -> None:
        lower = key.lower()
        if isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, child_key)
        elif isinstance(value, list):
            for child in value:
                visit(child, key)
        elif isinstance(value, str):
            if "candidate" in lower and "sha256" in lower and len(value) == 64:
                candidate_hashes.add(value)
            if "evidence" in lower and "sha256" in lower and len(value) == 64:
                evidence_hashes.add(value)
            if lower in {"source_identity", "source_scenario_id", "source_record_id"}:
                source_identities.add(value)

    for path in OVERLAP_INPUTS:
        visit(load(path))
    return {"candidate_hashes": candidate_hashes, "evidence_hashes": evidence_hashes, "source_identities": source_identities}


def inventory_rows() -> list[dict[str, Any]]:
    rows = []
    for case in test_cases():
        length = len(case["candidate_text"])
        row = {
            "candidate_id": case["candidate_id"],
            "source_scenario_id": case["source_scenario_id"],
            "source_identity": case["source_identity"],
            "source_dataset_sha256": SOURCE_SHA256,
            "source_split": "test",
            "source_category": case["source_category"],
            "template_variant": case["template_variant"],
            "timeline_length": case["timeline_length"],
            "candidate_sha256": case["candidate_sha256"],
            "candidate_unicode_character_count": length,
            "candidate_utf8_byte_count": len(case["candidate_text"].encode("utf-8")),
            "candidate_length_band": "short_lt_600" if length < 600 else "medium_600_899" if length < 900 else "long_ge_900",
            "candidate_line_count": len(case["candidate_text"].splitlines()),
            "evidence_bundle_sha256": case["evidence_bundle_sha256"],
            "evidence_item_count": len(case["evidence_bundle"]),
            "composite_stratum_key": f"{case['source_category']}|variant_{case['template_variant']}",
            "candidate_content_included": False,
            "evidence_content_included": False,
        }
        rows.append(row)
    return rows


def audited_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = inventory_rows()
    prior = collect_prior_fingerprints()
    id_counts = Counter(row["candidate_id"] for row in rows)
    candidate_counts = Counter(row["candidate_sha256"] for row in rows)
    evidence_counts = Counter(row["evidence_bundle_sha256"] for row in rows)
    eligibility_rows, overlap_rows, eligible = [], [], []
    for row in rows:
        raw_source_ids = {row["source_scenario_id"], row["source_identity"], "agent_memory_benchmark:" + row["source_scenario_id"]}
        candidate_overlap = row["candidate_sha256"] in prior["candidate_hashes"]
        evidence_overlap = row["evidence_bundle_sha256"] in prior["evidence_hashes"]
        source_overlap = bool(raw_source_ids & prior["source_identities"])
        reasons = []
        if row["source_split"] != "test": reasons.append("wrong_source_split")
        if id_counts[row["candidate_id"]] != 1: reasons.append("candidate_id_not_unique")
        if candidate_counts[row["candidate_sha256"]] != 1: reasons.append("candidate_hash_not_unique")
        if evidence_counts[row["evidence_bundle_sha256"]] != 1: reasons.append("evidence_hash_not_unique")
        if row["candidate_line_count"] != 6: reasons.append("candidate_line_count_not_six")
        if row["evidence_item_count"] != 6: reasons.append("evidence_item_count_not_six")
        if candidate_overlap: reasons.append("prior_phase7_candidate_hash_overlap")
        if evidence_overlap: reasons.append("prior_phase7_evidence_hash_overlap")
        if source_overlap: reasons.append("prior_phase7_source_identity_overlap")
        passed = not reasons
        eligibility_rows.append({"candidate_id": row["candidate_id"], "eligible": passed, "exclusion_reasons": reasons})
        overlap_rows.append({"candidate_id": row["candidate_id"], "candidate_hash_overlap": candidate_overlap, "evidence_hash_overlap": evidence_overlap, "source_identity_overlap": source_overlap, "any_overlap": candidate_overlap or evidence_overlap or source_overlap})
        if passed:
            eligible.append(row)
    return rows, eligibility_rows, overlap_rows, eligible


def selected_rows(eligible: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen = []
    for category in CATEGORIES:
        candidates = [row for row in eligible if row["source_category"] == category]
        ranked = sorted(candidates, key=lambda row: (hb((SEED + "|" + category + "|" + row["candidate_id"] + "|" + row["candidate_sha256"] + "|" + row["evidence_bundle_sha256"]).encode("utf-8")), row["candidate_id"]))
        chosen.extend(ranked[:4])
    chosen.sort(key=lambda row: (CATEGORIES.index(row["source_category"]), row["candidate_id"]))
    return chosen


def inventory_documents() -> dict[Path, Any]:
    rows, eligibility_rows, overlap_rows, eligible = audited_inventory()
    selected = selected_rows(eligible)
    inventory = {
        "schema_version": 1,
        "inventory_id": "phase7.3.3-d-multi-claim-successor-confirmatory-source-inventory-v1",
        "status": "metadata_only_content_sealed",
        "source_dataset_path": rel(SOURCE),
        "source_dataset_sha256": SOURCE_SHA256,
        "source_split": "test",
        "inventory_count": len(rows),
        "category_counts": dict(sorted(Counter(row["source_category"] for row in rows).items())),
        "items": rows,
        "candidate_content_included": False,
        "evidence_content_included": False,
        "confirmatory_dataset_opened": False,
    }
    eligibility = {
        "schema_version": 1,
        "audit_id": "phase7.3.3-d-multi-claim-successor-confirmatory-eligibility-audit-v1",
        "status": "PASS" if len(eligible) >= 40 else "FAIL_authoritative_shortfall",
        "inventory_count": len(rows),
        "eligible_count": len(eligible),
        "excluded_count": len(rows) - len(eligible),
        "rows": eligibility_rows,
        "candidate_content_included": False,
        "evidence_content_included": False,
        "confirmatory_dataset_opened": False,
    }
    overlap = {
        "schema_version": 1,
        "audit_id": "phase7.3.3-d-multi-claim-successor-confirmatory-overlap-audit-v1",
        "status": "PASS" if not any(row["any_overlap"] for row in overlap_rows) else "FAIL",
        "overlap_corpus": {rel(path): sha(path) for path in OVERLAP_INPUTS},
        "prior_candidate_fingerprint_count": len(collect_prior_fingerprints()["candidate_hashes"]),
        "prior_evidence_fingerprint_count": len(collect_prior_fingerprints()["evidence_hashes"]),
        "prior_source_identity_count": len(collect_prior_fingerprints()["source_identities"]),
        "candidate_hash_overlap_count": sum(row["candidate_hash_overlap"] for row in overlap_rows),
        "evidence_hash_overlap_count": sum(row["evidence_hash_overlap"] for row in overlap_rows),
        "source_identity_overlap_count": sum(row["source_identity_overlap"] for row in overlap_rows),
        "rows": overlap_rows,
        "candidate_content_included": False,
        "evidence_content_included": False,
        "confirmatory_dataset_opened": False,
    }
    eligible_doc = {
        "schema_version": 1,
        "inventory_id": "phase7.3.3-d-multi-claim-successor-confirmatory-eligible-inventory-v1",
        "status": "eligible_metadata_only_content_sealed",
        "eligible_count": len(eligible),
        "items": eligible,
        "candidate_content_included": False,
        "evidence_content_included": False,
        "confirmatory_dataset_opened": False,
    }
    items = []
    for index, row in enumerate(selected, start=1):
        items.append({
            "confirmatory_index": index,
            "candidate_id": row["candidate_id"],
            "source_scenario_id": row["source_scenario_id"],
            "source_identity": row["source_identity"],
            "source_category": row["source_category"],
            "template_variant": row["template_variant"],
            "candidate_sha256": row["candidate_sha256"],
            "evidence_bundle_sha256": row["evidence_bundle_sha256"],
            "first_arm": "candidate" if index % 2 else "atomic",
            "second_arm": "atomic" if index % 2 else "candidate",
            "candidate_content_included": False,
            "evidence_content_included": False,
        })
    worklist = {
        "schema_version": 1,
        "worklist_id": "phase7.3.3-d-multi-claim-successor-confirmatory-selected-worklist-v1",
        "status": "frozen_ids_hashes_content_sealed",
        "selection_method": sampling_policy()["within_stratum_rank"],
        "selection_seed": SEED,
        "selected_count": len(items),
        "category_counts": dict(sorted(Counter(item["source_category"] for item in items).items())),
        "first_arm_counts": dict(sorted(Counter(item["first_arm"] for item in items).items())),
        "items": items,
        "candidate_content_included": False,
        "evidence_content_included": False,
        "confirmatory_dataset_opened": False,
    }
    return {INVENTORY: inventory, ELIGIBILITY: eligibility, OVERLAP: overlap, ELIGIBLE: eligible_doc, WORKLIST: worklist}


def inventory_fixtures() -> dict[str, Any]:
    docs = inventory_documents()
    inventory, eligibility, overlap, worklist = docs[INVENTORY], docs[ELIGIBILITY], docs[OVERLAP], docs[WORKLIST]
    checks = [
        ("inventory_80", inventory["inventory_count"] == 80),
        ("ten_categories_eight_each", len(inventory["category_counts"]) == 10 and set(inventory["category_counts"].values()) == {8}),
        ("eligible_at_least_40", eligibility["eligible_count"] >= 40),
        ("zero_prior_overlap", overlap["candidate_hash_overlap_count"] == overlap["evidence_hash_overlap_count"] == overlap["source_identity_overlap_count"] == 0),
        ("selected_40", worklist["selected_count"] == 40),
        ("four_per_category", len(worklist["category_counts"]) == 10 and set(worklist["category_counts"].values()) == {4}),
        ("counterbalanced_20_20", worklist["first_arm_counts"] == {"atomic": 20, "candidate": 20}),
        ("unique_selected_hashes", len({row["candidate_sha256"] for row in worklist["items"]}) == len({row["evidence_bundle_sha256"] for row in worklist["items"]}) == 40),
        ("content_not_emitted", all(doc.get("candidate_content_included") is False and doc.get("evidence_content_included") is False for doc in docs.values())),
        ("confirmatory_closed", all(doc["confirmatory_dataset_opened"] is False for doc in docs.values())),
    ]
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-inventory-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def inventory_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-inventory-manifest-v1",
        "status": "frozen_metadata_only_selected_ids_hashes_content_sealed",
        "adapter_sha256": sha(SELF),
        "design_receipt_sha256": sha(DESIGN_RECEIPT),
        "state_v100_sha256": sha(STATE_100),
        "readiness_v111_sha256": sha(READY_111),
        "source_dataset_sha256": sha(SOURCE),
        "overlap_corpus": {rel(path): sha(path) for path in OVERLAP_INPUTS},
        "inventory_artifacts": {rel(path): sha(path) for path in [INVENTORY, ELIGIBILITY, OVERLAP, ELIGIBLE, WORKLIST, INVENTORY_FIXTURES]},
        "candidate_or_evidence_content_emitted": False,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": GATE_CUR,
    }


def inventory_preflight() -> dict[str, Any]:
    checks = {"design_verify": verify_design()["status"] == "PASS"}
    checks.update({
        "state_gate": STATE_100.exists() and load(STATE_100)["next_authorized_stage"] == INVENTORY_CUR,
        "readiness_gate": READY_111.exists() and load(READY_111)["next_authorized_stage"] == INVENTORY_CUR,
        "confirmatory_closed": STATE_100.exists() and load(STATE_100)["confirmatory_dataset_opened"] is False,
        "runtime_off": STATE_100.exists() and load(STATE_100)["runtime_integration_authorized"] is False,
    })
    outputs = [INVENTORY, ELIGIBILITY, OVERLAP, ELIGIBLE, WORKLIST, INVENTORY_FIXTURES, INVENTORY_MANIFEST, INVENTORY_OUTCOME, INVENTORY_AUDIT, INVENTORY_RECEIPT, STATE_101, READY_112]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def freeze_inventory() -> dict[str, Any]:
    checked = inventory_preflight()
    if checked["status"] != "PASS":
        return checked
    docs = inventory_documents()
    for path, document in docs.items():
        once(path, document)
    fixture_hash = once(INVENTORY_FIXTURES, inventory_fixtures())
    manifest_hash = once(INVENTORY_MANIFEST, inventory_manifest())
    eligible_count = load(ELIGIBILITY)["eligible_count"]
    selected_count = load(WORKLIST)["selected_count"]
    passed = eligible_count >= 40 and selected_count == 40 and load(OVERLAP)["status"] == "PASS"
    outcome_hash = once(INVENTORY_OUTCOME, {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-confirmatory-inventory-outcome-v1",
        "status": "PASS_metadata_inventory_frozen_preregistration_authorized" if passed else "AUTHORITATIVE_NEGATIVE_inventory_shortfall_or_overlap",
        "manifest_sha256": manifest_hash,
        "fixtures_sha256": fixture_hash,
        "inventory_count": load(INVENTORY)["inventory_count"],
        "eligible_count": eligible_count,
        "selected_count": selected_count,
        "overlap_count": sum(load(OVERLAP)[key] for key in ["candidate_hash_overlap_count", "evidence_hash_overlap_count", "source_identity_overlap_count"]),
        "candidate_or_evidence_content_emitted": False,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": GATE_CUR if passed else BLOCK_NEXT,
    })
    audit_hash = append_single_event(INVENTORY_AUDIT, {
        "event_id": "confirmatory-inventory-v1-frozen",
        "event_type": "metadata_only_inventory_freeze",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "inventory_count": load(INVENTORY)["inventory_count"],
        "eligible_count": eligible_count,
        "selected_count": selected_count,
        "content_emitted": False,
        "provider_called": False,
    })
    state, readiness = copy.deepcopy(load(STATE_100)), copy.deepcopy(load(READY_111))
    lineage = {
        "multi_claim_successor_confirmatory_source_inventory_v1_sha256": sha(INVENTORY),
        "multi_claim_successor_confirmatory_eligibility_audit_v1_sha256": sha(ELIGIBILITY),
        "multi_claim_successor_confirmatory_overlap_audit_v1_sha256": sha(OVERLAP),
        "multi_claim_successor_confirmatory_selected_worklist_v1_sha256": sha(WORKLIST),
        "multi_claim_successor_confirmatory_inventory_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_inventory_outcome_v1_sha256": outcome_hash,
        "multi_claim_successor_confirmatory_inventory_audit_v1_sha256": audit_hash,
    }
    next_stage = GATE_CUR if passed else BLOCK_NEXT
    update = {
        "status": "confirmatory_metadata_inventory_v1_frozen_preregistration_authorized" if passed else "confirmatory_inventory_v1_authoritative_negative",
        "next_authorized_stage": next_stage,
        "multi_claim_successor_confirmatory_inventory_metadata_constructed": True,
        "multi_claim_successor_confirmatory_inventory_count": load(INVENTORY)["inventory_count"],
        "multi_claim_successor_confirmatory_eligible_count": eligible_count,
        "multi_claim_successor_confirmatory_selected_count": selected_count,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 101, "state_id": "phase7.3.3-d-support-stage-state-v101"})
    readiness.update({"schema_version": 112, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v112"})
    state_hash = once(STATE_101, state)
    readiness["artifact_lineage"]["support_stage_state_v101_sha256"] = state_hash
    readiness_hash = once(READY_112, readiness)
    receipt_hash = once(INVENTORY_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-inventory-receipt-v1",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "inventory_count": load(INVENTORY)["inventory_count"],
        "eligible_count": eligible_count,
        "selected_count": selected_count,
        "candidate_or_evidence_content_emitted": False,
        "provider_called": False,
        "same_version_retry_allowed": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    return {"status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT", "inventory_count": load(INVENTORY)["inventory_count"], "eligible_count": eligible_count, "selected_count": selected_count, "manifest_sha256": manifest_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": next_stage}


def verify_inventory() -> dict[str, Any]:
    paths = [INVENTORY, ELIGIBILITY, OVERLAP, ELIGIBLE, WORKLIST, INVENTORY_FIXTURES, INVENTORY_MANIFEST, INVENTORY_OUTCOME, INVENTORY_AUDIT, INVENTORY_RECEIPT, STATE_101, READY_112]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        docs = inventory_documents()
        checks.update({"replay:" + rel(path): load(path) == document for path, document in docs.items()})
        checks.update({
            "fixtures_replay": load(INVENTORY_FIXTURES) == inventory_fixtures(),
            "manifest_replay": load(INVENTORY_MANIFEST) == inventory_manifest(),
            "receipt_lineage": load(INVENTORY_RECEIPT)["state_sha256"] == sha(STATE_101) and load(INVENTORY_RECEIPT)["readiness_sha256"] == sha(READY_112),
            "gate": load(STATE_101)["next_authorized_stage"] == load(READY_112)["next_authorized_stage"] == GATE_CUR,
            "content_absent": all(load(path).get("candidate_content_included") is False and load(path).get("evidence_content_included") is False for path in [INVENTORY, ELIGIBILITY, OVERLAP, ELIGIBLE, WORKLIST]),
            "confirmatory_closed": load(STATE_101)["confirmatory_dataset_opened"] is False and load(READY_112)["confirmatory_dataset_opened"] is False,
            "runtime_off": load(STATE_101)["runtime_integration_authorized"] is False and load(READY_112)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_101)["next_authorized_stage"] if STATE_101.exists() else None}


def preregistration() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "preregistration_id": "phase7.3.3-d-multi-claim-successor-confirmatory-preregistration-v1",
        "status": "frozen_before_confirmatory_content_opening_and_before_any_confirmatory_provider_call",
        "study_role": "confirmatory_replication_limited_to_frozen_phase6_test_source_composites",
        "source_lineage_limit": "Phase 6 test split was previously benchmarked; no general system-performance claim is authorized",
        "primary_estimand": "paired_mean_material_error_span_iou_atomic_minus_candidate",
        "paired_unit": "unique_candidate",
        "sample_size_candidates": 40,
        "hypotheses": {"null": "mean_atomic_minus_candidate_lte_0", "alternative": "mean_atomic_minus_candidate_gt_0"},
        "alpha_one_sided": 0.05,
        "primary_test": {
            "method": "one_sided_paired_sign_flip_randomization_monte_carlo",
            "replicates": 200000,
            "seed": 733071,
            "p_value": "(one_plus_count_permuted_mean_gte_observed_mean)/(replicates_plus_one)",
        },
        "uncertainty": {"method": "unique_candidate_nonparametric_bootstrap", "replicates": 20000, "seed": 733072, "interval": 0.95},
        "success_gate": {
            "structural_identifiability_pass": True,
            "realized_identifiability_pass": True,
            "paired_cases_dropped": 0,
            "estimate_gt_zero": True,
            "one_sided_p_value_lt_alpha": True,
        },
        "arms": {
            "candidate": "one whole-Candidate support label",
            "atomic": "six newline-delimited local atomic-unit support labels with adapter-derived immutable spans",
            "provider": "api.gpt.ge",
            "model": "gpt-5.4",
            "temperature": 0,
            "top_p": 1,
            "max_tokens": 800,
            "counterbalance": "20 candidate-first and 20 atomic-first",
            "prompt_and_schema_hashes_inherited_exactly": {rel(path): sha(path) for path in [CANDIDATE_PROMPT, ATOMIC_PROMPT, CANDIDATE_SCHEMA, ATOMIC_SCHEMA]},
        },
        "missingness": {"no_silent_drop": True, "all_40_pairs_required": True, "transport_failure_resume_same_manifest": True},
        "failure_discipline": {"first_provider_content_authoritative": True, "semantic_retry": False, "repair": False, "same_version_retry_after_content_failure": False},
        "no_result_dependent_replanning": True,
        "runtime_integration_authorized": False,
    }


def opening_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d-multi-claim-successor-confirmatory-dataset-opening-policy-v1",
        "status": "frozen_before_opening_gate_evaluation",
        "required_checks": ["inventory_80", "eligible_at_least_40", "selected_exactly_40", "four_per_category", "zero_prior_phase7_overlap", "selection_content_sealed", "preregistration_frozen", "same_arms_and_model", "authoritative_power_gate_lineage"],
        "on_pass": OPEN_NEXT,
        "on_failure": BLOCK_NEXT,
        "opening_scope_on_pass": "selected_40_only",
        "unselected_content_opening": False,
        "post_open_replacement": False,
        "provider_call_before_open_and_reference_freeze": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def gate_checks() -> dict[str, bool]:
    worklist, overlap = load(WORKLIST), load(OVERLAP)
    return {
        "inventory_80": load(INVENTORY)["inventory_count"] == 80,
        "eligible_at_least_40": load(ELIGIBILITY)["eligible_count"] >= 40,
        "selected_exactly_40": worklist["selected_count"] == 40,
        "four_per_category": len(worklist["category_counts"]) == 10 and set(worklist["category_counts"].values()) == {4},
        "counterbalance_20_20": worklist["first_arm_counts"] == {"atomic": 20, "candidate": 20},
        "zero_candidate_overlap": overlap["candidate_hash_overlap_count"] == 0,
        "zero_evidence_overlap": overlap["evidence_hash_overlap_count"] == 0,
        "zero_source_identity_overlap": overlap["source_identity_overlap_count"] == 0,
        "selection_content_sealed": worklist["candidate_content_included"] is False and worklist["evidence_content_included"] is False,
        "source_test_split": load(INVENTORY)["source_split"] == "test",
        "source_hash_pinned": load(INVENTORY)["source_dataset_sha256"] == sha(SOURCE) == SOURCE_SHA256,
        "phase6_lineage_disclosed": design_protocol()["source_lineage"]["prior_phase6_benchmark_usage_disclosed"] is True,
        "power_gate_lineage": sha(POWER_REPORT) == POWER_REPORT_SHA256 and load(SAMPLE_SIZE)["sample_size_clusters"] == 40,
        "exploratory_effect_gate": load(POWER_REPORT)["observed_paired_effect"] > 0 and load(POWER_REPORT)["bootstrap_lower_bound"] > 0,
        "same_provider_model": load(PILOT_PROTOCOL)["resource_equality"]["model"] == preregistration()["arms"]["model"] == "gpt-5.4" and load(PILOT_POLICY)["provider"] == preregistration()["arms"]["provider"],
        "same_prompt_schema_hashes": preregistration()["arms"]["prompt_and_schema_hashes_inherited_exactly"] == {rel(path): sha(path) for path in [CANDIDATE_PROMPT, ATOMIC_PROMPT, CANDIDATE_SCHEMA, ATOMIC_SCHEMA]},
        "confirmatory_still_closed": load(STATE_101)["confirmatory_dataset_opened"] is False and load(READY_112)["confirmatory_dataset_opened"] is False,
        "runtime_off": load(STATE_101)["runtime_integration_authorized"] is False and load(READY_112)["runtime_integration_authorized"] is False,
    }


def gate_fixtures() -> dict[str, Any]:
    checks = gate_checks()
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks.items()]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-opening-gate-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def gate_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-opening-gate-manifest-v1",
        "status": "frozen_before_dataset_opening_gate_evaluation",
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): sha(path) for path in [INVENTORY, ELIGIBILITY, OVERLAP, ELIGIBLE, WORKLIST, INVENTORY_MANIFEST, INVENTORY_RECEIPT, STATE_101, READY_112, POWER_REPORT, SAMPLE_SIZE, PILOT_PROTOCOL, PILOT_POLICY, CANDIDATE_PROMPT, ATOMIC_PROMPT, CANDIDATE_SCHEMA, ATOMIC_SCHEMA]},
        "frozen_protocols": {rel(PREREG): sha(PREREG), rel(OPEN_POLICY): sha(OPEN_POLICY), rel(GATE_FIXTURES): sha(GATE_FIXTURES)},
        "candidate_or_evidence_content_loaded": False,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def gate_preflight() -> dict[str, Any]:
    checks = {"inventory_verify": verify_inventory()["status"] == "PASS"}
    checks.update({
        "state_gate": STATE_101.exists() and load(STATE_101)["next_authorized_stage"] == GATE_CUR,
        "readiness_gate": READY_112.exists() and load(READY_112)["next_authorized_stage"] == GATE_CUR,
        "prompt_inputs_exist": all(path.exists() for path in [PILOT_PROTOCOL, PILOT_POLICY, CANDIDATE_PROMPT, ATOMIC_PROMPT, CANDIDATE_SCHEMA, ATOMIC_SCHEMA]),
        "confirmatory_closed": STATE_101.exists() and load(STATE_101)["confirmatory_dataset_opened"] is False,
        "runtime_off": STATE_101.exists() and load(STATE_101)["runtime_integration_authorized"] is False,
    })
    outputs = [PREREG, OPEN_POLICY, GATE_FIXTURES, GATE_MANIFEST, GATE_REPORT, GATE_AUDIT, GATE_RECEIPT, STATE_102, READY_113]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def evaluate_gate() -> dict[str, Any]:
    checked = gate_preflight()
    if checked["status"] != "PASS":
        return checked
    prereg_hash = once(PREREG, preregistration())
    policy_hash = once(OPEN_POLICY, opening_policy())
    fixture_hash = once(GATE_FIXTURES, gate_fixtures())
    manifest_hash = once(GATE_MANIFEST, gate_manifest())
    checks = gate_checks()
    passed = all(checks.values())
    next_stage = OPEN_NEXT if passed else BLOCK_NEXT
    report_hash = once(GATE_REPORT, {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-confirmatory-opening-gate-report-v1",
        "status": "PASS_open_selected_confirmatory_dataset_authorized" if passed else "AUTHORITATIVE_NEGATIVE_opening_not_authorized",
        "manifest_sha256": manifest_hash,
        "preregistration_sha256": prereg_hash,
        "opening_policy_sha256": policy_hash,
        "fixtures_sha256": fixture_hash,
        "checks": checks,
        "failed_checks": [key for key, value in checks.items() if not value],
        "inventory_count": load(INVENTORY)["inventory_count"],
        "eligible_count": load(ELIGIBILITY)["eligible_count"],
        "selected_count": load(WORKLIST)["selected_count"],
        "confirmatory_opening_authorized": passed,
        "confirmatory_dataset_opened": False,
        "unselected_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "same_version_retry_allowed": False,
        "next_authorized_stage": next_stage,
    })
    audit_hash = append_single_event(GATE_AUDIT, {
        "event_id": "confirmatory-opening-gate-v1-evaluated",
        "event_type": "authoritative_opening_gate_decision",
        "manifest_sha256": manifest_hash,
        "report_sha256": report_hash,
        "gate_passed": passed,
        "content_loaded": False,
        "provider_called": False,
    })
    state, readiness = copy.deepcopy(load(STATE_101)), copy.deepcopy(load(READY_112))
    lineage = {
        "multi_claim_successor_confirmatory_preregistration_v1_sha256": prereg_hash,
        "multi_claim_successor_confirmatory_dataset_opening_policy_v1_sha256": policy_hash,
        "multi_claim_successor_confirmatory_opening_gate_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_opening_gate_report_v1_sha256": report_hash,
        "multi_claim_successor_confirmatory_opening_gate_audit_v1_sha256": audit_hash,
    }
    update = {
        "status": "confirmatory_opening_gate_v1_passed_selected_dataset_open_authorized" if passed else "confirmatory_opening_gate_v1_authoritative_negative",
        "next_authorized_stage": next_stage,
        "multi_claim_successor_confirmatory_preregistration_v1_frozen": True,
        "multi_claim_successor_confirmatory_opening_gate_v1_evaluated": True,
        "multi_claim_successor_confirmatory_opening_gate_v1_passed": passed,
        "confirmatory_opening_authorized": passed,
        "confirmatory_dataset_opened": False,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 102, "state_id": "phase7.3.3-d-support-stage-state-v102"})
    readiness.update({"schema_version": 113, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v113"})
    state_hash = once(STATE_102, state)
    readiness["artifact_lineage"]["support_stage_state_v102_sha256"] = state_hash
    readiness_hash = once(READY_113, readiness)
    receipt_hash = once(GATE_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-opening-gate-receipt-v1",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT",
        "manifest_sha256": manifest_hash,
        "report_sha256": report_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "confirmatory_opening_authorized": passed,
        "confirmatory_dataset_opened": False,
        "unselected_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "same_version_retry_allowed": False,
        "next_authorized_stage": next_stage,
    })
    return {"status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT", "gate_passed": passed, "confirmatory_opening_authorized": passed, "confirmatory_dataset_opened": False, "report_sha256": report_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": next_stage}


def verify_gate() -> dict[str, Any]:
    paths = [PREREG, OPEN_POLICY, GATE_FIXTURES, GATE_MANIFEST, GATE_REPORT, GATE_AUDIT, GATE_RECEIPT, STATE_102, READY_113]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        report, receipt = load(GATE_REPORT), load(GATE_RECEIPT)
        checks.update({
            "preregistration_replay": load(PREREG) == preregistration(),
            "opening_policy_replay": load(OPEN_POLICY) == opening_policy(),
            "fixtures_replay": load(GATE_FIXTURES) == gate_fixtures(),
            "manifest_replay": load(GATE_MANIFEST) == gate_manifest(),
            "checks_replay": report["checks"] == gate_checks(),
            "gate_pass": report["confirmatory_opening_authorized"] is True and not report["failed_checks"],
            "receipt_lineage": receipt["report_sha256"] == sha(GATE_REPORT) and receipt["state_sha256"] == sha(STATE_102) and receipt["readiness_sha256"] == sha(READY_113),
            "next_gate": load(STATE_102)["next_authorized_stage"] == load(READY_113)["next_authorized_stage"] == OPEN_NEXT,
            "content_still_closed": load(STATE_102)["confirmatory_dataset_opened"] is False and load(READY_113)["confirmatory_dataset_opened"] is False,
            "unselected_closed": load(STATE_102)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_102)["runtime_integration_authorized"] is False and load(READY_113)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "confirmatory_opening_authorized": load(STATE_102).get("confirmatory_opening_authorized") if STATE_102.exists() else False, "confirmatory_dataset_opened": load(STATE_102).get("confirmatory_dataset_opened") if STATE_102.exists() else False, "next_authorized_stage": load(STATE_102)["next_authorized_stage"] if STATE_102.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["design-preflight", "freeze-design", "verify-design", "inventory-preflight", "freeze-inventory", "verify-inventory", "gate-preflight", "evaluate-gate", "verify-gate"]:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    if args.design_preflight:
        outcome = design_preflight()
    elif args.freeze_design:
        outcome = freeze_design()
    elif args.verify_design:
        outcome = verify_design()
    elif args.inventory_preflight:
        outcome = inventory_preflight()
    elif args.freeze_inventory:
        outcome = freeze_inventory()
    elif args.verify_inventory:
        outcome = verify_inventory()
    elif args.gate_preflight:
        outcome = gate_preflight()
    elif args.evaluate_gate:
        outcome = evaluate_gate()
    else:
        outcome = verify_gate()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 2 if outcome.get("status") == "AUTHORITATIVE_NEGATIVE_RESULT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
