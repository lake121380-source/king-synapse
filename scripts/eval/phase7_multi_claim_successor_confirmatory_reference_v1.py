#!/usr/bin/env python3
"""Open selected confirmatory content, freeze mechanical Gold, and gate structure."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
import tempfile
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import phase7_multi_claim_successor_confirmatory_inventory_v1 as inventory_adapter


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets"
PATTERN = DATA / "pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

SOURCE = DATA / "memory_intelligence/agent_memory_benchmark.toml"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_worklist_v1.json"
GATE_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_report_v1.json"
GATE_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_opening_gate_receipt_v1.json"
PREREG = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_preregistration_v1.json"
STATE_102 = PATTERN / "phase7_3_3_d_support_stage_state_v102.json"
READY_113 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v113.json"
INVENTORY_ADAPTER = ROOT / "scripts/eval/phase7_multi_claim_successor_confirmatory_inventory_v1.py"

OPEN_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_content_open_protocol_v1.json"
DATASET = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_selected_dataset_v1.json"
COMMITMENT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_commitment_audit_v1.json"
OPEN_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_open_fixtures_v1.json"
OPEN_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_open_manifest_v1.json"
OPEN_OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_open_outcome_v1.json"
OPEN_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_open_audit_v1.jsonl"
OPEN_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_content_open_receipt_v1.json"
STATE_103 = PATTERN / "phase7_3_3_d_support_stage_state_v103.json"
READY_114 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v114.json"

REFERENCE_POLICY = CONFIG / "phase7_3_3_d_multi_claim_successor_confirmatory_reference_gold_policy_v1.json"
GOLD = PATTERN / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_v1.json"
GOLD_SEAL = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_seal_v1.json"
GOLD_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_fixtures_v1.json"
GOLD_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_manifest_v1.json"
GOLD_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_report_v1.json"
GOLD_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_audit_v1.jsonl"
GOLD_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_support_gold_receipt_v1.json"
STATE_104 = PATTERN / "phase7_3_3_d_support_stage_state_v104.json"
READY_115 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v115.json"

IDENT_POLICY = CONFIG / "phase7_3_3_d_multi_claim_identifiability_policy_v1.json"
STRUCT_FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_fixtures_v1.json"
STRUCT_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_manifest_v1.json"
STRUCT_REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_report_v1.json"
STRUCT_NEGATIVE = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_negative_result_v1.json"
STRUCT_AUDIT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_audit_v1.jsonl"
STRUCT_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_confirmatory_structural_identifiability_receipt_v1.json"
STATE_105 = PATTERN / "phase7_3_3_d_support_stage_state_v105.json"
READY_116 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v116.json"

OPEN_CUR = "open_selected_confirmatory_dataset_v1"
GOLD_CUR = "freeze_confirmatory_support_gold_v1"
STRUCT_CUR = "evaluate_confirmatory_structural_identifiability_v1"
PASS_NEXT = "freeze_confirmatory_candidate_atomic_execution_environment_v1"
FAIL_NEXT = "blocked_confirmatory_structural_identifiability_v1_authoritative_negative"


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
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
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


def source_scenarios() -> dict[str, dict[str, Any]]:
    document = tomllib.loads(SOURCE.read_text(encoding="utf-8"))
    return {row["id"]: row for row in document["scenario"] if row["split"] == "test"}


def open_protocol() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-confirmatory-content-open-v1",
        "status": "frozen_at_explicit_opening_gate",
        "entry_gate_report_sha256": sha(GATE_REPORT),
        "opening_scope": "selected_40_only",
        "source_mapping": "frozen_confirmatory_composition_contract_v1",
        "selected_hash_replay_required": True,
        "support_labels_present_in_opened_dataset": False,
        "reference_content_present_in_opened_dataset": False,
        "arm_outputs_present": False,
        "unselected_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": GOLD_CUR,
    }


def opened_cases() -> list[dict[str, Any]]:
    worklist = load(WORKLIST)
    scenarios = source_scenarios()
    cases = []
    for item in sorted(worklist["items"], key=lambda row: row["confirmatory_index"]):
        scenario = scenarios[item["source_scenario_id"]]
        constructed = inventory_adapter.constructed_case(scenario)
        if constructed["candidate_id"] != item["candidate_id"]:
            raise RuntimeError("candidate_id_commitment_mismatch:" + item["candidate_id"])
        if constructed["candidate_sha256"] != item["candidate_sha256"]:
            raise RuntimeError("candidate_sha256_commitment_mismatch:" + item["candidate_id"])
        if constructed["evidence_bundle_sha256"] != item["evidence_bundle_sha256"]:
            raise RuntimeError("evidence_sha256_commitment_mismatch:" + item["candidate_id"])
        evidence = copy.deepcopy(constructed["evidence_bundle"])
        cases.append({
            "confirmatory_index": item["confirmatory_index"],
            "candidate_id": item["candidate_id"],
            "source_scenario_id": item["source_scenario_id"],
            "source_identity": item["source_identity"],
            "source_category": item["source_category"],
            "template_variant": item["template_variant"],
            "candidate_sha256": constructed["candidate_sha256"],
            "candidate_text": constructed["candidate_text"],
            "evidence_bundle_sha256": constructed["evidence_bundle_sha256"],
            "evidence_bundle": evidence,
            "valid_evidence_ids": [row["evidence_id"] for row in evidence],
            "support_labels_present": False,
            "reference_claims_present": False,
            "arm_outputs_present": False,
        })
    return cases


def open_documents() -> dict[Path, Any]:
    cases = opened_cases()
    dataset = {
        "schema_version": 1,
        "dataset_id": "phase7.3.3-d-multi-claim-successor-confirmatory-selected-dataset-v1",
        "status": "selected_confirmatory_content_open_reference_and_arms_not_started",
        "source_dataset_path": rel(SOURCE),
        "source_dataset_sha256": sha(SOURCE),
        "selected_worklist_sha256": sha(WORKLIST),
        "opening_gate_report_sha256": sha(GATE_REPORT),
        "case_count": len(cases),
        "cases": cases,
        "support_labels_present": False,
        "reference_claims_present": False,
        "arm_outputs_present": False,
        "unselected_content_opened": False,
        "confirmatory_dataset_opened": True,
        "runtime_integration_authorized": False,
    }
    replay = []
    selected = {row["candidate_id"]: row for row in load(WORKLIST)["items"]}
    for case in cases:
        item = selected[case["candidate_id"]]
        replay.append({
            "candidate_id": case["candidate_id"],
            "candidate_sha256_expected": item["candidate_sha256"],
            "candidate_sha256_actual": hb(case["candidate_text"].encode("utf-8")),
            "candidate_sha256_match": item["candidate_sha256"] == hb(case["candidate_text"].encode("utf-8")),
            "evidence_bundle_sha256_expected": item["evidence_bundle_sha256"],
            "evidence_bundle_sha256_actual": canonical_sha(case["evidence_bundle"]),
            "evidence_bundle_sha256_match": item["evidence_bundle_sha256"] == canonical_sha(case["evidence_bundle"]),
        })
    commitment = {
        "schema_version": 1,
        "audit_id": "phase7.3.3-d-multi-claim-successor-confirmatory-content-commitment-audit-v1",
        "status": "PASS" if all(row["candidate_sha256_match"] and row["evidence_bundle_sha256_match"] for row in replay) else "FAIL",
        "selected_count": len(replay),
        "candidate_hash_matches": sum(row["candidate_sha256_match"] for row in replay),
        "evidence_hash_matches": sum(row["evidence_bundle_sha256_match"] for row in replay),
        "rows": replay,
        "unselected_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
    }
    return {OPEN_PROTOCOL: open_protocol(), DATASET: dataset, COMMITMENT: commitment}


def open_fixtures() -> dict[str, Any]:
    documents = open_documents()
    dataset, commitment = documents[DATASET], documents[COMMITMENT]
    cases = dataset["cases"]
    checks = [
        ("selected_40", len(cases) == dataset["case_count"] == 40),
        ("unique_ids", len({case["candidate_id"] for case in cases}) == 40),
        ("six_lines", all(len(case["candidate_text"].splitlines()) == 6 for case in cases)),
        ("six_evidence", all(len(case["evidence_bundle"]) == 6 for case in cases)),
        ("all_commitments_match", commitment["candidate_hash_matches"] == commitment["evidence_hash_matches"] == 40),
        ("labels_absent", all(case["support_labels_present"] is False and case["reference_claims_present"] is False for case in cases)),
        ("arm_outputs_absent", all(case["arm_outputs_present"] is False for case in cases)),
        ("unselected_closed", dataset["unselected_content_opened"] is False),
        ("runtime_off", dataset["runtime_integration_authorized"] is False),
    ]
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-content-open-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def open_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-content-open-manifest-v1",
        "status": "frozen_selected_content_opened",
        "adapter_sha256": sha(SELF),
        "inventory_adapter_sha256": sha(INVENTORY_ADAPTER),
        "frozen_inputs": {rel(path): sha(path) for path in [SOURCE, WORKLIST, GATE_REPORT, GATE_RECEIPT, PREREG, STATE_102, READY_113]},
        "opened_artifacts": {rel(path): sha(path) for path in [OPEN_PROTOCOL, DATASET, COMMITMENT, OPEN_FIXTURES]},
        "selected_content_opened": True,
        "unselected_content_opened": False,
        "reference_started": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": GOLD_CUR,
    }


def open_preflight() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in [SOURCE, WORKLIST, GATE_REPORT, GATE_RECEIPT, PREREG, STATE_102, READY_113, INVENTORY_ADAPTER]}
    if all(checks.values()):
        state, readiness = load(STATE_102), load(READY_113)
        checks.update({
            "state_gate": state["next_authorized_stage"] == OPEN_CUR,
            "readiness_gate": readiness["next_authorized_stage"] == OPEN_CUR,
            "opening_explicitly_authorized": state["confirmatory_opening_authorized"] is True and readiness["confirmatory_opening_authorized"] is True and load(GATE_REPORT)["confirmatory_opening_authorized"] is True,
            "dataset_not_yet_open": state["confirmatory_dataset_opened"] is False and readiness["confirmatory_dataset_opened"] is False,
            "unselected_closed": state["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": state["runtime_integration_authorized"] is False and readiness["runtime_integration_authorized"] is False,
            "gate_lineage": load(GATE_RECEIPT)["report_sha256"] == sha(GATE_REPORT) and load(GATE_RECEIPT)["state_sha256"] == sha(STATE_102),
        })
    outputs = [OPEN_PROTOCOL, DATASET, COMMITMENT, OPEN_FIXTURES, OPEN_MANIFEST, OPEN_OUTCOME, OPEN_AUDIT, OPEN_RECEIPT, STATE_103, READY_114]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def open_selected() -> dict[str, Any]:
    checked = open_preflight()
    if checked["status"] != "PASS":
        return checked
    for path, document in open_documents().items():
        once(path, document)
    fixture_hash = once(OPEN_FIXTURES, open_fixtures())
    manifest_hash = once(OPEN_MANIFEST, open_manifest())
    outcome_hash = once(OPEN_OUTCOME, {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-confirmatory-content-open-outcome-v1",
        "status": "PASS_selected_40_open_reference_gold_authorized",
        "manifest_sha256": manifest_hash,
        "fixtures_sha256": fixture_hash,
        "dataset_sha256": sha(DATASET),
        "selected_content_opened": True,
        "unselected_content_opened": False,
        "support_labels_present": False,
        "arm_outputs_present": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": GOLD_CUR,
    })
    audit_hash = append_single_event(OPEN_AUDIT, {"event_id": "confirmatory-selected-content-v1-opened", "event_type": "authorized_selected_content_open", "manifest_sha256": manifest_hash, "outcome_sha256": outcome_hash, "selected_count": 40, "unselected_opened": False, "provider_called": False})
    state, readiness = copy.deepcopy(load(STATE_102)), copy.deepcopy(load(READY_113))
    lineage = {
        "multi_claim_successor_confirmatory_selected_dataset_v1_sha256": sha(DATASET),
        "multi_claim_successor_confirmatory_content_commitment_audit_v1_sha256": sha(COMMITMENT),
        "multi_claim_successor_confirmatory_content_open_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_content_open_outcome_v1_sha256": outcome_hash,
        "multi_claim_successor_confirmatory_content_open_audit_v1_sha256": audit_hash,
    }
    update = {
        "status": "confirmatory_selected_dataset_v1_open_reference_gold_authorized",
        "next_authorized_stage": GOLD_CUR,
        "multi_claim_successor_confirmatory_selected_content_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "multi_claim_successor_confirmatory_reference_frozen": False,
        "multi_claim_successor_confirmatory_arm_execution_started": False,
        "confirmatory_opening_authorized": True,
        "confirmatory_dataset_opened": True,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 103, "state_id": "phase7.3.3-d-support-stage-state-v103"})
    readiness.update({"schema_version": 114, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v114"})
    state_hash = once(STATE_103, state)
    readiness["artifact_lineage"]["support_stage_state_v103_sha256"] = state_hash
    readiness_hash = once(READY_114, readiness)
    receipt_hash = once(OPEN_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-content-open-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "dataset_sha256": sha(DATASET),
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "selected_content_opened": True,
        "unselected_content_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": GOLD_CUR,
    })
    return {"status": "PASS", "selected_count": 40, "dataset_sha256": sha(DATASET), "manifest_sha256": manifest_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": GOLD_CUR}


def verify_open() -> dict[str, Any]:
    paths = [OPEN_PROTOCOL, DATASET, COMMITMENT, OPEN_FIXTURES, OPEN_MANIFEST, OPEN_OUTCOME, OPEN_AUDIT, OPEN_RECEIPT, STATE_103, READY_114]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        documents = open_documents()
        checks.update({"replay:" + rel(path): load(path) == document for path, document in documents.items()})
        checks.update({
            "fixtures_replay": load(OPEN_FIXTURES) == open_fixtures(),
            "manifest_replay": load(OPEN_MANIFEST) == open_manifest(),
            "receipt_lineage": load(OPEN_RECEIPT)["dataset_sha256"] == sha(DATASET) and load(OPEN_RECEIPT)["state_sha256"] == sha(STATE_103) and load(OPEN_RECEIPT)["readiness_sha256"] == sha(READY_114),
            "state_gate": load(STATE_103)["next_authorized_stage"] == load(READY_114)["next_authorized_stage"] == GOLD_CUR,
            "selected_opened": load(STATE_103)["confirmatory_dataset_opened"] is True and load(READY_114)["confirmatory_dataset_opened"] is True,
            "unselected_closed": load(STATE_103)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_103)["runtime_integration_authorized"] is False and load(READY_114)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_103)["next_authorized_stage"] if STATE_103.exists() else None}


def reference_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "phase7.3.3-d-multi-claim-successor-confirmatory-reference-gold-policy-v1",
        "status": "frozen_before_reference_gold_materialization",
        "reference_unit": "each_of_six_frozen_LF_delimited_candidate_lines",
        "boundary_rule": "exact_unicode_character_span_of_line_excluding_LF_separator",
        "support_contract": {
            "direct_top_memory": "supported_by_exact_source_memory",
            "direct_background_memory": "supported_by_exact_source_memory",
            "scope_overclaim": "partially_supported_exact_memory_plus_unlicensed_universal_scope",
            "contradicted_absence": "unsupported_because_named_memory_is_present",
            "priority_overclaim": "partially_supported_exact_memory_plus_unlicensed_exclusive_priority",
            "invented_category_assertion": "unsupported_no_evidence_item_contains_benchmark_category_metadata",
        },
        "reference_origin": "mechanical_precommitted_composition_contract_not_model_or_human_review",
        "support_label_recomputation_allowed": False,
        "boundary_rewrite_allowed": False,
        "reference_visible_during_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": STRUCT_CUR,
    }


def line_spans(text: str) -> list[dict[str, int]]:
    rows, cursor = [], 0
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        rows.append({"claim_index": index, "start": cursor, "end": cursor + len(line)})
        cursor += len(line) + (1 if index < len(lines) else 0)
    return rows


def gold_document() -> dict[str, Any]:
    dataset_cases = {case["source_scenario_id"]: case for case in load(DATASET)["cases"]}
    scenarios = source_scenarios()
    gold_cases = []
    label_counts: Counter[str] = Counter()
    for source_id, opened in sorted(dataset_cases.items(), key=lambda pair: pair[1]["confirmatory_index"]):
        constructed = inventory_adapter.constructed_case(scenarios[source_id])
        if constructed["candidate_text"] != opened["candidate_text"]:
            raise RuntimeError("gold_candidate_replay_mismatch:" + opened["candidate_id"])
        spans = line_spans(opened["candidate_text"])
        claims = []
        for span, committed in zip(spans, constructed["claims"]):
            excerpt = opened["candidate_text"][span["start"]:span["end"]]
            if excerpt != committed["text"]:
                raise RuntimeError("gold_span_replay_mismatch:" + opened["candidate_id"])
            label_counts[committed["support_label"]] += 1
            claims.append({
                "claim_id": f"{opened['candidate_id']}-claim-{span['claim_index']:02d}",
                "claim_index": span["claim_index"],
                "source_span": {"start": span["start"], "end": span["end"]},
                "source_excerpt": excerpt,
                "claim_role": committed["claim_role"],
                "support_label": committed["support_label"],
                "support_witness_evidence_ids": committed["evidence_ids"],
                "gold_fields": ["source_span", "support_label"],
            })
        gold_cases.append({"case_id": opened["candidate_id"], "candidate_sha256": opened["candidate_sha256"], "claim_count": len(claims), "claims": claims})
    return {
        "schema_version": 1,
        "support_gold_id": "phase7.3.3-d-multi-claim-successor-confirmatory-support-gold-v1",
        "status": "frozen_mechanical_precommitted_reference_gold_not_human_or_model_gold",
        "reference_policy_sha256": sha(REFERENCE_POLICY),
        "selected_dataset_sha256": sha(DATASET),
        "case_count": len(gold_cases),
        "claim_count": sum(case["claim_count"] for case in gold_cases),
        "label_counts": {label: label_counts.get(label, 0) for label in ["supported", "partially_supported", "unsupported", "not_assessable"]},
        "gold_fields": ["source_span", "support_label"],
        "cases": gold_cases,
        "support_gold_frozen": True,
        "support_label_recomputation_performed": False,
        "provider_called_during_gold_freeze": False,
        "reference_visible_during_arm_execution": False,
        "unselected_content_opened": False,
        "confirmatory_dataset_opened": True,
        "runtime_integration_authorized": False,
    }


def gold_fixtures() -> dict[str, Any]:
    gold = gold_document()
    cases = gold["cases"]
    labels = [claim["support_label"] for case in cases for claim in case["claims"]]
    checks = [
        ("gold_40_240", gold["case_count"] == len(cases) == 40 and gold["claim_count"] == len(labels) == 240),
        ("six_claims_per_case", all(case["claim_count"] == len(case["claims"]) == 6 for case in cases)),
        ("label_distribution_80_each", gold["label_counts"] == {"supported": 80, "partially_supported": 80, "unsupported": 80, "not_assessable": 0}),
        ("within_case_heterogeneity", all(len({claim["support_label"] for claim in case["claims"]}) == 3 for case in cases)),
        ("span_order_nonoverlap", all(all(left["source_span"]["end"] < right["source_span"]["start"] for left, right in zip(case["claims"], case["claims"][1:])) for case in cases)),
        ("excerpt_span_replay", all(all(claim["source_excerpt"] == next(row for row in load(DATASET)["cases"] if row["candidate_id"] == case["case_id"])["candidate_text"][claim["source_span"]["start"]:claim["source_span"]["end"]] for claim in case["claims"]) for case in cases)),
        ("provider_not_called", gold["provider_called_during_gold_freeze"] is False),
        ("unselected_closed", gold["unselected_content_opened"] is False),
        ("runtime_off", gold["runtime_integration_authorized"] is False),
    ]
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks]
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-support-gold-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def gold_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-support-gold-manifest-v1",
        "status": "frozen_before_structural_identifiability_evaluation",
        "adapter_sha256": sha(SELF),
        "inventory_adapter_sha256": sha(INVENTORY_ADAPTER),
        "frozen_inputs": {rel(path): sha(path) for path in [SOURCE, WORKLIST, PREREG, DATASET, OPEN_RECEIPT, STATE_103, READY_114]},
        "reference_artifacts": {rel(path): sha(path) for path in [REFERENCE_POLICY, GOLD, GOLD_FIXTURES]},
        "provider_called": False,
        "reference_visible_to_arms": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": STRUCT_CUR,
    }


def gold_preflight() -> dict[str, Any]:
    checks = {"open_verify": verify_open()["status"] == "PASS"}
    checks.update({
        "state_gate": STATE_103.exists() and load(STATE_103)["next_authorized_stage"] == GOLD_CUR,
        "readiness_gate": READY_114.exists() and load(READY_114)["next_authorized_stage"] == GOLD_CUR,
        "selected_opened": STATE_103.exists() and load(STATE_103)["confirmatory_dataset_opened"] is True,
        "unselected_closed": STATE_103.exists() and load(STATE_103)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
        "arm_execution_not_started": STATE_103.exists() and load(STATE_103)["multi_claim_successor_confirmatory_arm_execution_started"] is False,
        "runtime_off": STATE_103.exists() and load(STATE_103)["runtime_integration_authorized"] is False,
    })
    outputs = [REFERENCE_POLICY, GOLD, GOLD_SEAL, GOLD_FIXTURES, GOLD_MANIFEST, GOLD_REPORT, GOLD_AUDIT, GOLD_RECEIPT, STATE_104, READY_115]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def freeze_gold() -> dict[str, Any]:
    checked = gold_preflight()
    if checked["status"] != "PASS":
        return checked
    once(REFERENCE_POLICY, reference_policy())
    gold_hash = once(GOLD, gold_document())
    fixture_hash = once(GOLD_FIXTURES, gold_fixtures())
    manifest_hash = once(GOLD_MANIFEST, gold_manifest())
    seal_hash = once(GOLD_SEAL, {
        "schema_version": 1,
        "seal_id": "phase7.3.3-d-multi-claim-successor-confirmatory-support-gold-seal-v1",
        "status": "sealed_immutable_before_arm_execution",
        "support_gold_sha256": gold_hash,
        "reference_policy_sha256": sha(REFERENCE_POLICY),
        "manifest_sha256": manifest_hash,
        "case_count": 40,
        "claim_count": 240,
        "provider_called": False,
        "reference_visible_to_arms": False,
        "runtime_integration_authorized": False,
    })
    report_hash = once(GOLD_REPORT, {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-confirmatory-support-gold-report-v1",
        "status": "PASS_support_gold_frozen_structural_gate_authorized",
        "manifest_sha256": manifest_hash,
        "support_gold_sha256": gold_hash,
        "support_gold_seal_sha256": seal_hash,
        "fixtures_sha256": fixture_hash,
        "case_count": 40,
        "claim_count": 240,
        "label_counts": load(GOLD)["label_counts"],
        "provider_called": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": STRUCT_CUR,
    })
    audit_hash = append_single_event(GOLD_AUDIT, {"event_id": "confirmatory-support-gold-v1-frozen", "event_type": "immutable_reference_gold_freeze", "manifest_sha256": manifest_hash, "gold_sha256": gold_hash, "seal_sha256": seal_hash, "provider_called": False})
    state, readiness = copy.deepcopy(load(STATE_103)), copy.deepcopy(load(READY_114))
    lineage = {
        "multi_claim_successor_confirmatory_reference_gold_policy_v1_sha256": sha(REFERENCE_POLICY),
        "multi_claim_successor_confirmatory_support_gold_v1_sha256": gold_hash,
        "multi_claim_successor_confirmatory_support_gold_seal_v1_sha256": seal_hash,
        "multi_claim_successor_confirmatory_support_gold_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_support_gold_report_v1_sha256": report_hash,
        "multi_claim_successor_confirmatory_support_gold_audit_v1_sha256": audit_hash,
    }
    update = {
        "status": "confirmatory_support_gold_v1_frozen_structural_gate_authorized",
        "next_authorized_stage": STRUCT_CUR,
        "multi_claim_successor_confirmatory_reference_frozen": True,
        "multi_claim_successor_confirmatory_support_gold_frozen": True,
        "multi_claim_successor_confirmatory_support_gold_sha256": gold_hash,
        "multi_claim_successor_confirmatory_structural_identifiability_evaluated": False,
        "multi_claim_successor_confirmatory_arm_execution_authorized": False,
        "confirmatory_dataset_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 104, "state_id": "phase7.3.3-d-support-stage-state-v104"})
    readiness.update({"schema_version": 115, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v115"})
    state_hash = once(STATE_104, state)
    readiness["artifact_lineage"]["support_stage_state_v104_sha256"] = state_hash
    readiness_hash = once(READY_115, readiness)
    receipt_hash = once(GOLD_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-support-gold-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "report_sha256": report_hash,
        "audit_log_sha256": audit_hash,
        "support_gold_sha256": gold_hash,
        "support_gold_seal_sha256": seal_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "provider_called": False,
        "reference_visible_to_arms": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": STRUCT_CUR,
    })
    return {"status": "PASS", "case_count": 40, "claim_count": 240, "gold_sha256": gold_hash, "seal_sha256": seal_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": STRUCT_CUR}


def verify_gold() -> dict[str, Any]:
    paths = [REFERENCE_POLICY, GOLD, GOLD_SEAL, GOLD_FIXTURES, GOLD_MANIFEST, GOLD_REPORT, GOLD_AUDIT, GOLD_RECEIPT, STATE_104, READY_115]
    checks = {"exists:" + rel(path): path.exists() for path in paths}
    if all(checks.values()):
        receipt = load(GOLD_RECEIPT)
        checks.update({
            "policy_replay": load(REFERENCE_POLICY) == reference_policy(),
            "gold_replay": load(GOLD) == gold_document(),
            "fixtures_replay": load(GOLD_FIXTURES) == gold_fixtures(),
            "manifest_replay": load(GOLD_MANIFEST) == gold_manifest(),
            "seal_lineage": load(GOLD_SEAL)["support_gold_sha256"] == sha(GOLD),
            "receipt_lineage": receipt["support_gold_sha256"] == sha(GOLD) and receipt["support_gold_seal_sha256"] == sha(GOLD_SEAL) and receipt["state_sha256"] == sha(STATE_104) and receipt["readiness_sha256"] == sha(READY_115),
            "state_gate": load(STATE_104)["next_authorized_stage"] == load(READY_115)["next_authorized_stage"] == STRUCT_CUR,
            "reference_invisible": receipt["reference_visible_to_arms"] is False,
            "unselected_closed": load(STATE_104)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_104)["runtime_integration_authorized"] is False and load(READY_115)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_104)["next_authorized_stage"] if STATE_104.exists() else None}


def structural_metrics() -> dict[str, Any]:
    gold, dataset = load(GOLD), load(DATASET)
    cases = gold["cases"]
    labels = [claim["support_label"] for case in cases for claim in case["claims"]]
    counts = Counter(labels)
    claim_counts = [len(case["claims"]) for case in cases]
    heterogeneous = sum(len({claim["support_label"] for claim in case["claims"]}) > 1 for case in cases)
    mixed = sum(any(claim["support_label"] == "supported" for claim in case["claims"]) and any(claim["support_label"] in {"partially_supported", "unsupported"} for claim in case["claims"]) for case in cases)
    candidate_hashes = [case["candidate_sha256"] for case in dataset["cases"]]
    return {
        "selected_candidate_count": len(cases),
        "unique_candidate_rate": len(set(candidate_hashes)) / len(candidate_hashes),
        "median_reference_claims_per_candidate": statistics.median(claim_counts),
        "multi_claim_candidate_rate": sum(count >= 2 for count in claim_counts) / len(claim_counts),
        "reference_claim_to_candidate_ratio": len(labels) / len(cases),
        "within_candidate_label_heterogeneity_rate": heterogeneous / len(cases),
        "supported_plus_material_error_candidate_rate": mixed / len(cases),
        "material_error_claim_rate": (counts["partially_supported"] + counts["unsupported"]) / len(labels),
        "unsupported_claim_rate": counts["unsupported"] / len(labels),
        "partially_supported_claim_rate": counts["partially_supported"] / len(labels),
        "maximum_single_label_share": max(counts.values()) / len(labels),
        "eligible_gap_characters": 0,
        "overlap_characters": 0,
        "case_count": len(cases),
        "claim_count": len(labels),
        "label_counts": {label: counts.get(label, 0) for label in ["supported", "partially_supported", "unsupported", "not_assessable"]},
    }


def structural_checks(metrics: dict[str, Any]) -> dict[str, bool]:
    threshold = load(IDENT_POLICY)["structural_reference_gate"]
    return {
        "minimum_selected_candidate_count": metrics["selected_candidate_count"] >= threshold["minimum_selected_candidate_count"],
        "target_selected_candidate_count": metrics["selected_candidate_count"] == threshold["target_selected_candidate_count"],
        "unique_candidate_rate_min": metrics["unique_candidate_rate"] >= threshold["unique_candidate_rate_min"],
        "median_reference_claims_per_candidate_min": metrics["median_reference_claims_per_candidate"] >= threshold["median_reference_claims_per_candidate_min"],
        "multi_claim_candidate_rate_min": metrics["multi_claim_candidate_rate"] >= threshold["multi_claim_candidate_rate_min"],
        "reference_claim_to_candidate_ratio_min": metrics["reference_claim_to_candidate_ratio"] >= threshold["reference_claim_to_candidate_ratio_min"],
        "within_candidate_label_heterogeneity_rate_min": metrics["within_candidate_label_heterogeneity_rate"] >= threshold["within_candidate_label_heterogeneity_rate_min"],
        "supported_plus_material_error_candidate_rate_min": metrics["supported_plus_material_error_candidate_rate"] >= threshold["supported_plus_material_error_candidate_rate_min"],
        "material_error_claim_rate_min": metrics["material_error_claim_rate"] >= threshold["material_error_claim_rate_min"],
        "unsupported_claim_rate_min": metrics["unsupported_claim_rate"] >= threshold["unsupported_claim_rate_min"],
        "partially_supported_claim_rate_min": metrics["partially_supported_claim_rate"] >= threshold["partially_supported_claim_rate_min"],
        "maximum_single_label_share": metrics["maximum_single_label_share"] <= threshold["maximum_single_label_share"],
        "eligible_gap_characters_required": metrics["eligible_gap_characters"] == threshold["eligible_gap_characters_required"],
        "overlap_characters_required": metrics["overlap_characters"] == threshold["overlap_characters_required"],
    }


def structural_fixtures() -> dict[str, Any]:
    metrics = structural_metrics()
    checks = structural_checks(metrics)
    rows = [{"fixture_id": key, "passed": passed} for key, passed in checks.items()]
    rows.extend([
        {"fixture_id": "gold_sealed", "passed": load(GOLD_SEAL)["support_gold_sha256"] == sha(GOLD)},
        {"fixture_id": "reference_invisible_to_arms", "passed": load(GOLD)["reference_visible_during_arm_execution"] is False},
        {"fixture_id": "runtime_off", "passed": load(GOLD)["runtime_integration_authorized"] is False},
    ])
    return {"schema_version": 1, "fixtures_id": "phase7.3.3-d-confirmatory-structural-identifiability-fixtures-v1", "fixture_count": len(rows), "passed_count": sum(row["passed"] for row in rows), "all_fixtures_passed": all(row["passed"] for row in rows), "fixtures": rows}


def structural_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-confirmatory-structural-identifiability-manifest-v1",
        "status": "frozen_before_structural_gate_evaluation",
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): sha(path) for path in [IDENT_POLICY, DATASET, GOLD, GOLD_SEAL, GOLD_MANIFEST, GOLD_RECEIPT, STATE_104, READY_115]},
        "fixtures_sha256": sha(STRUCT_FIXTURES),
        "provider_called": False,
        "confirmatory_dataset_opened": True,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }


def structural_preflight() -> dict[str, Any]:
    checks = {"gold_verify": verify_gold()["status"] == "PASS", "ident_policy_exists": IDENT_POLICY.exists()}
    checks.update({
        "state_gate": STATE_104.exists() and load(STATE_104)["next_authorized_stage"] == STRUCT_CUR,
        "readiness_gate": READY_115.exists() and load(READY_115)["next_authorized_stage"] == STRUCT_CUR,
        "gold_sealed": GOLD_SEAL.exists() and load(GOLD_SEAL)["support_gold_sha256"] == sha(GOLD),
        "arm_execution_not_authorized": STATE_104.exists() and load(STATE_104)["multi_claim_successor_confirmatory_arm_execution_authorized"] is False,
        "unselected_closed": STATE_104.exists() and load(STATE_104)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
        "runtime_off": STATE_104.exists() and load(STATE_104)["runtime_integration_authorized"] is False,
    })
    outputs = [STRUCT_FIXTURES, STRUCT_MANIFEST, STRUCT_REPORT, STRUCT_NEGATIVE, STRUCT_AUDIT, STRUCT_RECEIPT, STATE_105, READY_116]
    checks["outputs_absent"] = all(not path.exists() for path in outputs)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def evaluate_structural() -> dict[str, Any]:
    checked = structural_preflight()
    if checked["status"] != "PASS":
        return checked
    fixture_hash = once(STRUCT_FIXTURES, structural_fixtures())
    manifest_hash = once(STRUCT_MANIFEST, structural_manifest())
    metrics = structural_metrics()
    checks = structural_checks(metrics)
    passed = all(checks.values())
    next_stage = PASS_NEXT if passed else FAIL_NEXT
    report_hash = once(STRUCT_REPORT, {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-confirmatory-structural-identifiability-report-v1",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT",
        "manifest_sha256": manifest_hash,
        "fixtures_sha256": fixture_hash,
        "target_estimand": load(IDENT_POLICY)["target_estimand"],
        "metrics": metrics,
        "thresholds": load(IDENT_POLICY)["structural_reference_gate"],
        "checks": checks,
        "failed_checks": [key for key, value in checks.items() if not value],
        "all_checks_required": True,
        "structural_estimand_identifiable": passed,
        "confirmatory_arm_execution_authorized": passed,
        "provider_called": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    negative_hash = None
    if not passed:
        negative_hash = once(STRUCT_NEGATIVE, {
            "schema_version": 1,
            "negative_result_id": "phase7.3.3-d-multi-claim-successor-confirmatory-structural-identifiability-negative-v1",
            "status": "authoritative_structural_identifiability_negative_result",
            "report_sha256": report_hash,
            "failed_checks": [key for key, value in checks.items() if not value],
            "same_version_retry_allowed": False,
            "arm_execution_authorized": False,
            "runtime_integration_authorized": False,
            "next_authorized_stage": FAIL_NEXT,
        })
    audit_hash = append_single_event(STRUCT_AUDIT, {"event_id": "confirmatory-structural-identifiability-v1-evaluated", "event_type": "authoritative_structural_gate_decision", "manifest_sha256": manifest_hash, "report_sha256": report_hash, "gate_passed": passed, "provider_called": False})
    state, readiness = copy.deepcopy(load(STATE_104)), copy.deepcopy(load(READY_115))
    lineage = {
        "multi_claim_successor_confirmatory_structural_identifiability_manifest_v1_sha256": manifest_hash,
        "multi_claim_successor_confirmatory_structural_identifiability_report_v1_sha256": report_hash,
        "multi_claim_successor_confirmatory_structural_identifiability_audit_v1_sha256": audit_hash,
    }
    if negative_hash:
        lineage["multi_claim_successor_confirmatory_structural_identifiability_negative_v1_sha256"] = negative_hash
    update = {
        "status": "confirmatory_structural_identifiability_v1_passed_execution_freeze_authorized" if passed else "confirmatory_structural_identifiability_v1_authoritative_negative",
        "next_authorized_stage": next_stage,
        "multi_claim_successor_confirmatory_structural_identifiability_evaluated": True,
        "multi_claim_successor_confirmatory_structural_identifiability_passed": passed,
        "multi_claim_successor_confirmatory_arm_execution_authorized": passed,
        "multi_claim_successor_confirmatory_same_version_retry_allowed": False,
        "confirmatory_dataset_opened": True,
        "multi_claim_successor_confirmatory_unselected_content_opened": False,
        "runtime_integration_authorized": False,
    }
    for document in [state, readiness]:
        document.setdefault("artifact_lineage", {}).update(lineage)
        document.update(update)
    state.update({"schema_version": 105, "state_id": "phase7.3.3-d-support-stage-state-v105"})
    readiness.update({"schema_version": 116, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v116"})
    state_hash = once(STATE_105, state)
    readiness["artifact_lineage"]["support_stage_state_v105_sha256"] = state_hash
    readiness_hash = once(READY_116, readiness)
    receipt_hash = once(STRUCT_RECEIPT, {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-confirmatory-structural-identifiability-receipt-v1",
        "status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT",
        "manifest_sha256": manifest_hash,
        "report_sha256": report_hash,
        "negative_result_sha256": negative_hash,
        "audit_log_sha256": audit_hash,
        "state_sha256": state_hash,
        "readiness_sha256": readiness_hash,
        "structural_estimand_identifiable": passed,
        "confirmatory_arm_execution_authorized": passed,
        "same_version_retry_allowed": False,
        "unselected_content_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    })
    return {"status": "PASS" if passed else "AUTHORITATIVE_NEGATIVE_RESULT", "structural_estimand_identifiable": passed, "arm_execution_authorized": passed, "report_sha256": report_hash, "receipt_sha256": receipt_hash, "state_sha256": state_hash, "readiness_sha256": readiness_hash, "next_authorized_stage": next_stage}


def verify_structural() -> dict[str, Any]:
    required = [STRUCT_FIXTURES, STRUCT_MANIFEST, STRUCT_REPORT, STRUCT_AUDIT, STRUCT_RECEIPT, STATE_105, READY_116]
    checks = {"exists:" + rel(path): path.exists() for path in required}
    if all(checks.values()):
        report, receipt = load(STRUCT_REPORT), load(STRUCT_RECEIPT)
        passed = report["structural_estimand_identifiable"]
        checks.update({
            "fixtures_replay": load(STRUCT_FIXTURES) == structural_fixtures(),
            "manifest_replay": load(STRUCT_MANIFEST) == structural_manifest(),
            "metrics_replay": report["metrics"] == structural_metrics(),
            "checks_replay": report["checks"] == structural_checks(structural_metrics()),
            "all_checks_pass": passed and not report["failed_checks"],
            "receipt_lineage": receipt["report_sha256"] == sha(STRUCT_REPORT) and receipt["state_sha256"] == sha(STATE_105) and receipt["readiness_sha256"] == sha(READY_116),
            "state_gate": load(STATE_105)["next_authorized_stage"] == load(READY_116)["next_authorized_stage"] == PASS_NEXT,
            "arm_execution_authorized": load(STATE_105)["multi_claim_successor_confirmatory_arm_execution_authorized"] is True,
            "unselected_closed": load(STATE_105)["multi_claim_successor_confirmatory_unselected_content_opened"] is False,
            "runtime_off": load(STATE_105)["runtime_integration_authorized"] is False and load(READY_116)["runtime_integration_authorized"] is False,
        })
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "next_authorized_stage": load(STATE_105)["next_authorized_stage"] if STATE_105.exists() else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ["open-preflight", "open", "verify-open", "gold-preflight", "freeze-gold", "verify-gold", "structural-preflight", "evaluate-structural", "verify-structural"]:
        group.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    if args.open_preflight:
        outcome = open_preflight()
    elif args.open:
        outcome = open_selected()
    elif args.verify_open:
        outcome = verify_open()
    elif args.gold_preflight:
        outcome = gold_preflight()
    elif args.freeze_gold:
        outcome = freeze_gold()
    elif args.verify_gold:
        outcome = verify_gold()
    elif args.structural_preflight:
        outcome = structural_preflight()
    elif args.evaluate_structural:
        outcome = evaluate_structural()
    else:
        outcome = verify_structural()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 2 if outcome.get("status") == "AUTHORITATIVE_NEGATIVE_RESULT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
