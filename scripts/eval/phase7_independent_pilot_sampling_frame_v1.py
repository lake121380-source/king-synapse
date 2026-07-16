#!/usr/bin/env python3
"""Freeze the Phase 7.3.3-D independent Pilot Sampling Frame v1.

This adapter performs sealed mechanical extraction of IDs, hashes, and pre-outcome
metadata from the frozen Phase 6 memory-intelligence validation split. It never
emits Candidate or Evidence content and does not call a Provider. Selected
content remains sealed for a successor Gate.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import tempfile
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets"
PATTERN = DATA / "pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

POLICY = CONFIG / "phase7_3_3_d_independent_pilot_sampling_policy_v1.json"
REPLICATION = CONFIG / "phase7_3_3_d_independent_replication_protocol_v1.json"
FREEZE_MANIFEST = REPORTS / "phase7_3_3_d_independent_replication_protocol_freeze_manifest_v1.json"
STATE_IN = PATTERN / "phase7_3_3_d_support_stage_state_v13.json"
READY_IN = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v24.json"
SOURCE = DATA / "memory_intelligence/agent_memory_benchmark.toml"
SOURCE_REPORT = REPORTS / "phase6_memory_intelligence_benchmark.json"
ROUTE_A_DESIGN = PATTERN / "phase7_2_pattern_extraction_design.json"
ROUTE_A_PACKET = PATTERN / "phase7_3_3_d_support_blind_review_packet_v1.json"

PROTOCOL = CONFIG / "phase7_3_3_d_independent_pilot_sampling_frame_protocol_v1.json"
INVENTORY = REPORTS / "phase7_3_3_d_independent_pilot_source_inventory_v1.json"
ELIGIBILITY = REPORTS / "phase7_3_3_d_independent_pilot_eligibility_audit_v1.json"
OVERLAP = REPORTS / "phase7_3_3_d_independent_pilot_overlap_audit_v1.json"
ELIGIBLE = REPORTS / "phase7_3_3_d_independent_pilot_eligible_inventory_v1.json"
WORKLIST = PATTERN / "phase7_3_3_d_independent_pilot_selected_worklist_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_independent_pilot_sampling_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_independent_pilot_sampling_manifest_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_independent_pilot_sampling_freeze_receipt_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_independent_pilot_sampling_freeze_outcome_v1.json"
STATE_OUT = PATTERN / "phase7_3_3_d_support_stage_state_v14.json"
READY_OUT = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v25.json"

SEED = "phase7.3.3-d-pilot-v1-20260715"
SOURCE_FAMILY = "agent_memory_benchmark_expected_reason"
SOURCE_SPLIT = "validation"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha_bytes(canonical_bytes(value))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_once(path: Path, value: Any) -> str:
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{path.relative_to(ROOT)}")
        return sha_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)
    return sha_bytes(payload)


def candidate_length_band(length: int) -> str:
    if length < 80:
        return "short_lt_80"
    if length < 160:
        return "medium_80_159"
    return "long_ge_160"


def evidence_count_band(count: int) -> str:
    if count <= 3:
        return "small_1_3"
    if count <= 6:
        return "medium_4_6"
    return "large_ge_7"


def protocol_doc() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-independent-pilot-sampling-frame-protocol-v1",
        "status": "frozen_by_sampling_adapter",
        "stage": "construct_independent_pilot_sampling_frame_v1",
        "entry_gate": {
            "independent_replication_protocol_frozen": True,
            "next_authorized_stage": "construct_independent_pilot_sampling_frame_v1",
            "pilot_dataset_content_opened": False,
            "confirmatory_dataset_opened": False,
        },
        "source": {
            "dataset_path": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
            "dataset_split": SOURCE_SPLIT,
            "candidate_field": "expected_reason",
            "evidence_field": "memory",
            "context_fields_not_scored_as_evidence": ["query"],
            "source_family": SOURCE_FAMILY,
            "pre_existing_frozen_dataset": True,
        },
        "sealed_mechanical_processing": {
            "candidate_and_evidence_bytes_read_only_for_hash_length_and_count": True,
            "candidate_text_emitted": False,
            "evidence_content_emitted": False,
            "human_semantic_content_access": False,
            "provider_content_access": False,
        },
        "eligibility": {
            "required_split": SOURCE_SPLIT,
            "candidate_nonempty": True,
            "evidence_bundle_nonempty": True,
            "candidate_id_unique": True,
            "lineage_complete": True,
            "route_a_design_case_overlap_excluded": True,
            "candidate_hash_overlap_excluded": True,
            "evidence_hash_overlap_excluded": True,
            "source_identity_overlap_excluded_when_available": True,
            "calibration_fixture_excluded": True,
        },
        "strata": {
            "domain": "scenario.category",
            "source_family": SOURCE_FAMILY,
            "candidate_length_band": {"short_lt_80": [0, 79], "medium_80_159": [80, 159], "long_ge_160": [160, None]},
            "evidence_count_band": {"small_1_3": [1, 3], "medium_4_6": [4, 6], "large_ge_7": [7, None]},
        },
        "selection": {
            "target": 40,
            "minimum": 30,
            "maximum": 50,
            "method": "sha256_ranked_stratified",
            "allocation": "proportional_largest_remainder_over_composite_strata",
            "allocation_tie_breaker": "composite_stratum_key",
            "rank_material": "seed|composite_stratum_key|candidate_id|candidate_sha256|evidence_bundle_sha256",
            "rank_tie_breaker": "candidate_id",
            "seed": SEED,
        },
        "opening": {
            "selected_ids_and_hashes_frozen_before_content_open": True,
            "selected_content_open_authorized_by_successor_gate_only": True,
            "unselected_content_remains_sealed": True,
        },
        "failure": {
            "minimum_shortfall_is_immutable_failure": True,
            "silent_replacement": False,
            "post_opening_replacement": False,
            "outcome_dependent_selection": False,
        },
        "runtime": {"provider_called": False, "runtime_integration": False, "memory_write": False},
    }


def route_a_fingerprints() -> dict[str, set[str]]:
    design = load_json(ROUTE_A_DESIGN)
    packet = load_json(ROUTE_A_PACKET)
    candidate_hashes: set[str] = set()
    evidence_hashes: set[str] = set()
    sources: set[str] = set()
    case_ids: set[str] = set()
    for case in design.get("cases", []):
        case_ids.add(str(case.get("id")))
        source_id = case.get("source_transfer_scenario_id")
        if source_id:
            sources.add(str(source_id))
        if "reference_candidate" in case:
            candidate_hashes.add(canonical_sha(case["reference_candidate"]))
        if "input" in case:
            evidence_hashes.add(canonical_sha(case["input"]))
    for case in packet.get("cases", []):
        case_ids.add(str(case.get("case_id")))
        identity = case.get("candidate_identity")
        if identity is not None:
            candidate_hashes.add(canonical_sha(identity))
        evidence = case.get("evidence_bundle") or case.get("evidence_input")
        if evidence is not None:
            evidence_hashes.add(canonical_sha(evidence))
    return {"candidate_hashes": candidate_hashes, "evidence_hashes": evidence_hashes, "source_identities": sources, "case_ids": case_ids}


def build_inventory() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset = tomllib.loads(SOURCE.read_text(encoding="utf-8"))
    source_report = load_json(SOURCE_REPORT)
    declared_sha = source_report["protocol"]["dataset_sha256"]
    actual_sha = sha(SOURCE)
    if declared_sha != actual_sha:
        raise ValueError("source_dataset_sha256_mismatch")
    rows: list[dict[str, Any]] = []
    validation = [x for x in dataset.get("scenario", []) if x.get("split") == SOURCE_SPLIT]
    for scenario in validation:
        candidate = scenario.get("expected_reason")
        evidence = scenario.get("memory")
        candidate_id = scenario.get("id")
        candidate_bytes = str(candidate).encode("utf-8") if isinstance(candidate, str) else b""
        evidence_sha = canonical_sha(evidence)
        source_identity = f"agent_memory_benchmark:{candidate_id}"
        domain = str(scenario.get("category"))
        row = {
            "candidate_id": candidate_id,
            "source_identity": source_identity,
            "source_dataset_sha256": actual_sha,
            "source_split": scenario.get("split"),
            "domain": domain,
            "source_family": SOURCE_FAMILY,
            "candidate_sha256": sha_bytes(candidate_bytes),
            "candidate_utf8_byte_count": len(candidate_bytes),
            "candidate_unicode_character_count": len(candidate) if isinstance(candidate, str) else 0,
            "candidate_length_band": candidate_length_band(len(candidate) if isinstance(candidate, str) else 0),
            "evidence_bundle_sha256": evidence_sha,
            "evidence_item_count": len(evidence) if isinstance(evidence, list) else 0,
            "evidence_count_band": evidence_count_band(len(evidence) if isinstance(evidence, list) else 0),
            "lineage_complete": bool(candidate_id and isinstance(candidate, str) and candidate.strip() and isinstance(evidence, list) and evidence),
            "candidate_content_emitted": False,
            "evidence_content_emitted": False,
        }
        row["composite_stratum_key"] = "|".join([row["domain"], row["source_family"], row["candidate_length_band"], row["evidence_count_band"]])
        rows.append(row)
    metadata = {
        "source_scenario_count": len(dataset.get("scenario", [])),
        "source_split_counts": dict(sorted(Counter(x.get("split") for x in dataset.get("scenario", [])).items())),
        "validation_inventory_count": len(rows),
        "validation_domain_counts": dict(sorted(Counter(x["domain"] for x in rows).items())),
        "source_dataset_sha256": actual_sha,
        "source_report_sha256": sha(SOURCE_REPORT),
        "candidate_or_evidence_content_emitted": False,
    }
    return rows, metadata


def eligibility_and_overlap(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    fp = route_a_fingerprints()
    ids = Counter(x["candidate_id"] for x in rows)
    audits: list[dict[str, Any]] = []
    overlaps: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for row in rows:
        reasons: list[str] = []
        if row["source_split"] != SOURCE_SPLIT:
            reasons.append("wrong_split")
        if not row["lineage_complete"]:
            reasons.append("lineage_incomplete")
        if ids[row["candidate_id"]] != 1:
            reasons.append("candidate_id_not_unique")
        candidate_overlap = row["candidate_sha256"] in fp["candidate_hashes"]
        evidence_overlap = row["evidence_bundle_sha256"] in fp["evidence_hashes"]
        raw_source_id = str(row["candidate_id"])
        source_overlap = raw_source_id in fp["source_identities"] or row["source_identity"] in fp["source_identities"]
        design_id_overlap = row["candidate_id"] in fp["case_ids"]
        if candidate_overlap:
            reasons.append("route_a_candidate_hash_overlap")
        if evidence_overlap:
            reasons.append("route_a_evidence_hash_overlap")
        if source_overlap:
            reasons.append("route_a_source_identity_overlap")
        if design_id_overlap:
            reasons.append("route_a_design_case_id_overlap")
        record = {
            "candidate_id": row["candidate_id"],
            "eligible": not reasons,
            "exclusion_reasons": reasons,
            "lineage_complete": row["lineage_complete"],
            "candidate_id_unique": ids[row["candidate_id"]] == 1,
        }
        audits.append(record)
        overlaps.append({
            "candidate_id": row["candidate_id"],
            "candidate_hash_overlap": candidate_overlap,
            "evidence_hash_overlap": evidence_overlap,
            "source_identity_overlap": source_overlap,
            "design_case_id_overlap": design_id_overlap,
            "excluded_for_overlap": any([candidate_overlap, evidence_overlap, source_overlap, design_id_overlap]),
        })
        if not reasons:
            eligible.append(copy.deepcopy(row))
    return audits, overlaps, eligible


def allocate_and_select(rows: list[dict[str, Any]], target: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by[row["composite_stratum_key"]].append(row)
    total = len(rows)
    allocation: list[dict[str, Any]] = []
    assigned = 0
    for key in sorted(by):
        exact = len(by[key]) * target / total
        floor = math.floor(exact)
        allocation.append({"composite_stratum_key": key, "eligible_count": len(by[key]), "exact_quota": exact, "floor_quota": floor, "remainder": exact - floor, "selected_quota": floor})
        assigned += floor
    remaining = target - assigned
    for item in sorted(allocation, key=lambda x: (-x["remainder"], x["composite_stratum_key"])):
        if remaining <= 0:
            break
        if item["selected_quota"] < item["eligible_count"]:
            item["selected_quota"] += 1
            remaining -= 1
    if remaining:
        raise ValueError("allocation_capacity_shortfall")
    selected: list[dict[str, Any]] = []
    quotas = {x["composite_stratum_key"]: x["selected_quota"] for x in allocation}
    for key in sorted(by):
        ranked = []
        for row in by[key]:
            material = "|".join([SEED, key, row["candidate_id"], row["candidate_sha256"], row["evidence_bundle_sha256"]])
            item = copy.deepcopy(row)
            item["selection_rank_sha256"] = sha_bytes(material.encode("utf-8"))
            ranked.append(item)
        ranked.sort(key=lambda x: (x["selection_rank_sha256"], x["candidate_id"]))
        for within_rank, item in enumerate(ranked[:quotas[key]], start=1):
            item["within_stratum_rank"] = within_rank
            selected.append(item)
    selected.sort(key=lambda x: (x["composite_stratum_key"], x["within_stratum_rank"], x["candidate_id"]))
    for index, item in enumerate(selected, start=1):
        item["pilot_index"] = index
    return allocation, selected


def fixture_results() -> list[dict[str, Any]]:
    synthetic = []
    for domain in ["a", "b"]:
        for i in range(4):
            cid = f"{domain}-{i}"
            row = {
                "candidate_id": cid, "candidate_sha256": sha_bytes(cid.encode()), "evidence_bundle_sha256": sha_bytes((cid+"e").encode()),
                "composite_stratum_key": f"{domain}|f|short_lt_80|medium_4_6",
            }
            synthetic.append(row)
    allocation, selected = allocate_and_select(synthetic, 4)
    rerun = allocate_and_select(copy.deepcopy(synthetic), 4)[1]
    tests = [
        ("deterministic_replay", canonical_sha(selected) == canonical_sha(rerun)),
        ("target_count", len(selected) == 4),
        ("proportional_allocation", sorted(x["selected_quota"] for x in allocation) == [2, 2]),
        ("candidate_content_absent", all("candidate_text" not in x for x in selected)),
        ("evidence_content_absent", all("evidence_bundle" not in x for x in selected)),
        ("rank_present", all(len(x["selection_rank_sha256"]) == 64 for x in selected)),
        ("unique_selection", len({x["candidate_id"] for x in selected}) == len(selected)),
        ("pre_outcome_strata_only", all(not any(k in x for k in ["support_label", "mixed_support", "arm_correctness", "agreement", "effect_size"]) for x in selected)),
    ]
    return [{"fixture_id": name, "status": "PASS" if ok else "FAIL"} for name, ok in tests]


def verify_inputs() -> dict[str, Any]:
    required = [POLICY, REPLICATION, FREEZE_MANIFEST, STATE_IN, READY_IN, SOURCE, SOURCE_REPORT, ROUTE_A_DESIGN, ROUTE_A_PACKET]
    missing = [str(x.relative_to(ROOT)) for x in required if not x.exists()]
    if missing:
        raise FileNotFoundError(f"missing_inputs:{missing}")
    policy = load_json(POLICY)
    state = load_json(STATE_IN)
    ready = load_json(READY_IN)
    if policy.get("status") != "frozen" or policy.get("target") != 40 or policy.get("minimum") != 30:
        raise ValueError("sampling_policy_gate_invalid")
    if state.get("next_authorized_stage") != "construct_independent_pilot_sampling_frame_v1":
        raise ValueError("state_gate_invalid")
    if ready.get("next_authorized_stage") != "construct_independent_pilot_sampling_frame_v1":
        raise ValueError("readiness_gate_invalid")
    return {"required_inputs": len(required), "missing": missing, "state_gate": "PASS", "provider_called": False, "confirmatory_opened": False}


def build_outputs() -> dict[Path, Any]:
    verify_inputs()
    protocol = protocol_doc()
    rows, metadata = build_inventory()
    audits, overlaps, eligible = eligibility_and_overlap(rows)
    policy = load_json(POLICY)
    target = min(policy["target"], len(eligible))
    shortfall = len(eligible) < policy["minimum"]
    allocation: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    if not shortfall:
        allocation, selected = allocate_and_select(eligible, target)
    fixtures = fixture_results()
    if any(x["status"] != "PASS" for x in fixtures):
        raise ValueError("contract_fixture_failure")
    inventory_doc = {"schema_version": 1, "inventory_id": "phase7.3.3-d-independent-pilot-source-inventory-v1", "status": "sealed_metadata_only", "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"), "metadata": metadata, "items": rows, "candidate_content_included": False, "evidence_content_included": False}
    eligibility_doc = {"schema_version": 1, "audit_id": "phase7.3.3-d-independent-pilot-eligibility-audit-v1", "status": "completed", "inventory_sha256": canonical_sha(inventory_doc), "audited_count": len(audits), "eligible_count": len(eligible), "excluded_count": len(rows)-len(eligible), "exclusion_counts": dict(sorted(Counter(reason for x in audits for reason in x["exclusion_reasons"]).items())), "items": audits}
    overlap_doc = {"schema_version": 1, "audit_id": "phase7.3.3-d-independent-pilot-overlap-audit-v1", "status": "PASS" if not any(x["excluded_for_overlap"] for x in overlaps) else "overlap_detected_and_excluded", "route_a_sources": {"design": str(ROUTE_A_DESIGN.relative_to(ROOT)).replace("\\", "/"), "blind_packet": str(ROUTE_A_PACKET.relative_to(ROOT)).replace("\\", "/")}, "audited_count": len(overlaps), "overlap_count": sum(x["excluded_for_overlap"] for x in overlaps), "items": overlaps}
    eligible_doc = {"schema_version": 1, "inventory_id": "phase7.3.3-d-independent-pilot-eligible-inventory-v1", "status": "frozen_pre_outcome_eligible_inventory", "eligible_count": len(eligible), "items": eligible, "candidate_content_included": False, "evidence_content_included": False}
    worklist_doc = {"schema_version": 1, "worklist_id": "phase7.3.3-d-independent-pilot-selected-worklist-v1", "status": "frozen_ids_hashes_content_sealed" if not shortfall else "not_created_minimum_shortfall", "selection_method": "sha256_ranked_stratified", "seed": SEED, "target": policy["target"], "minimum": policy["minimum"], "maximum": policy["maximum"], "eligible_count": len(eligible), "selected_count": len(selected), "allocation": allocation, "items": selected, "candidate_content_included": False, "evidence_content_included": False}
    fixtures_doc = {"schema_version": 1, "fixture_suite_id": "phase7.3.3-d-independent-pilot-sampling-contract-fixtures-v1", "status": "PASS", "passed": len(fixtures), "total": len(fixtures), "fixtures": fixtures}
    # Hashes below are canonical prospective hashes; on-disk file hashes are added to receipt after write.
    manifest_doc = {"schema_version": 1, "manifest_id": "phase7.3.3-d-independent-pilot-sampling-manifest-v1", "status": "frozen_before_selected_content_open", "frozen_date": "2026-07-15", "adapter_path": str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/"), "adapter_sha256": sha(Path(__file__).resolve()), "input_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in [POLICY, REPLICATION, FREEZE_MANIFEST, STATE_IN, READY_IN, SOURCE, SOURCE_REPORT, ROUTE_A_DESIGN, ROUTE_A_PACKET]}, "protocol_canonical_sha256": canonical_sha(protocol), "inventory_canonical_sha256": canonical_sha(inventory_doc), "eligibility_canonical_sha256": canonical_sha(eligibility_doc), "overlap_canonical_sha256": canonical_sha(overlap_doc), "eligible_inventory_canonical_sha256": canonical_sha(eligible_doc), "selected_worklist_canonical_sha256": canonical_sha(worklist_doc), "fixtures_canonical_sha256": canonical_sha(fixtures_doc), "selected_count": len(selected), "selected_content_opened": False, "unselected_content_opened": False, "provider_called": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    outcome_status = "independent_pilot_sampling_frame_frozen_content_not_opened" if not shortfall and len(selected) >= policy["minimum"] else "independent_pilot_sampling_frame_minimum_shortfall"
    state = copy.deepcopy(load_json(STATE_IN)); state.update({"schema_version": 14, "state_id": "phase7.3.3-d-support-stage-state-v14", "next_authorized_stage": "open_independent_pilot_selected_content_v1" if not shortfall else "investigate_independent_pilot_inventory_shortfall_v1", "independent_replication_started": True, "independent_replication_state": outcome_status, "independent_pilot_sampling_frame_frozen": not shortfall, "independent_pilot_dataset_opened": False, "independent_pilot_eligible_count": len(eligible), "independent_pilot_selected_count": len(selected), "confirmatory_dataset_opened": False, "provider_called_for_independent_replication": False})
    ready = copy.deepcopy(load_json(READY_IN)); ready.update({"schema_version": 25, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v25", "status": outcome_status, "next_authorized_stage": state["next_authorized_stage"], "independent_replication_started": True, "independent_replication_state": outcome_status, "independent_pilot_sampling_frame_frozen": not shortfall, "independent_pilot_dataset_opened": False, "independent_pilot_eligible_count": len(eligible), "independent_pilot_selected_count": len(selected), "confirmatory_dataset_opened": False, "provider_called_for_independent_replication": False})
    outcome_doc = {"schema_version": 1, "outcome_id": "phase7.3.3-d-independent-pilot-sampling-freeze-outcome-v1", "status": outcome_status, "eligible_count": len(eligible), "selected_count": len(selected), "minimum_required": policy["minimum"], "target": policy["target"], "content_opened": False, "provider_called": False, "confirmatory_dataset_opened": False, "next_authorized_stage": state["next_authorized_stage"]}
    return {PROTOCOL: protocol, INVENTORY: inventory_doc, ELIGIBILITY: eligibility_doc, OVERLAP: overlap_doc, ELIGIBLE: eligible_doc, WORKLIST: worklist_doc, FIXTURES: fixtures_doc, MANIFEST: manifest_doc, STATE_OUT: state, READY_OUT: ready, OUTCOME: outcome_doc}


def freeze() -> dict[str, Any]:
    outputs = build_outputs()
    hashes: dict[str, str] = {}
    for path, value in outputs.items():
        hashes[str(path.relative_to(ROOT)).replace("\\", "/")] = write_once(path, value)
    receipt = {"schema_version": 1, "receipt_id": "phase7.3.3-d-independent-pilot-sampling-freeze-receipt-v1", "status": "PASS" if load_json(OUTCOME)["status"].endswith("content_not_opened") else "FAIL", "artifact_sha256": hashes, "selected_count": load_json(WORKLIST)["selected_count"], "eligible_count": load_json(ELIGIBLE)["eligible_count"], "fixtures_passed": load_json(FIXTURES)["passed"], "fixtures_total": load_json(FIXTURES)["total"], "candidate_content_opened": False, "evidence_content_opened": False, "provider_called": False, "confirmatory_dataset_opened": False}
    receipt_sha = write_once(RECEIPT, receipt)
    return {"status": receipt["status"], "eligible": receipt["eligible_count"], "selected": receipt["selected_count"], "fixtures": f"{receipt['fixtures_passed']}/{receipt['fixtures_total']}", "receipt_sha256": receipt_sha, "next": load_json(OUTCOME)["next_authorized_stage"]}


def verify() -> dict[str, Any]:
    expected = build_outputs()
    checks: list[dict[str, Any]] = []
    for path, value in expected.items():
        payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        ok = path.exists() and path.read_bytes() == payload
        checks.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "status": "PASS" if ok else "FAIL"})
    if not RECEIPT.exists():
        checks.append({"path": str(RECEIPT.relative_to(ROOT)).replace("\\", "/"), "status": "FAIL"})
    else:
        receipt = load_json(RECEIPT)
        for rel, digest in receipt.get("artifact_sha256", {}).items():
            path = ROOT / rel
            checks.append({"path": rel + "#receipt_hash", "status": "PASS" if path.exists() and sha(path) == digest else "FAIL"})
    failed = [x for x in checks if x["status"] != "PASS"]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed, "provider_called": False, "selected_content_opened": False, "confirmatory_dataset_opened": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-inputs", action="store_true")
    group.add_argument("--run-contract-fixtures", action="store_true")
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify_inputs:
        result = verify_inputs()
    elif args.run_contract_fixtures:
        fixtures = fixture_results(); result = {"status": "PASS" if all(x["status"] == "PASS" for x in fixtures) else "FAIL", "passed": sum(x["status"] == "PASS" for x in fixtures), "total": len(fixtures), "fixtures": fixtures}
    elif args.freeze:
        result = freeze()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
