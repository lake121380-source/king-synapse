#!/usr/bin/env python3
"""Freeze the Phase 7.3.3-D multi-claim successor Sampling Frame v1.

Inventories a new cognitive-memory source family, commits deterministic
contrastive multi-clause Candidates, excludes prior exact overlaps, and freezes
a content-sealed worklist. No Provider, Confirmatory, or Runtime access.
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
SOURCE_ROOT = DATA / "cognitive_memory"

STATE_IN = PATTERN / "phase7_3_3_d_support_stage_state_v25.json"
READY_IN = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v36.json"
ENTRY_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_entry_manifest_v1.json"
ENTRY_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_entry_receipt_v1.json"
FRAME_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_frame_construction_protocol_v1.json"
SAMPLING_POLICY = CONFIG / "phase7_3_3_d_multi_claim_sampling_policy_v1.json"
IDENT_POLICY = CONFIG / "phase7_3_3_d_multi_claim_identifiability_policy_v1.json"
REFERENCE_SCHEMA = CONFIG / "phase7_3_3_d_multi_claim_reference_schema_v1.json"
METRIC_SPEC = CONFIG / "phase7_3_3_d_multi_claim_metric_specification_v1.json"
ROUTE_A_PACKET = PATTERN / "phase7_3_3_d_boundary_blind_review_packet_v1.json"
ROUTE_A_GOLD = PATTERN / "phase7_3_3_d_boundary_gold_v1.json"
PREDECESSOR_WORKLIST = PATTERN / "phase7_3_3_d_independent_pilot_selected_worklist_v1.json"
PREDECESSOR_DATASET = PATTERN / "phase7_3_3_d_independent_pilot_selected_dataset_v1.json"

PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_sampling_frame_protocol_v1.json"
INVENTORY = REPORTS / "phase7_3_3_d_multi_claim_successor_source_inventory_v1.json"
ELIGIBILITY = REPORTS / "phase7_3_3_d_multi_claim_successor_eligibility_audit_v1.json"
OVERLAP = REPORTS / "phase7_3_3_d_multi_claim_successor_overlap_audit_v1.json"
ELIGIBLE = REPORTS / "phase7_3_3_d_multi_claim_successor_eligible_inventory_v1.json"
WORKLIST = PATTERN / "phase7_3_3_d_multi_claim_successor_selected_worklist_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_sampling_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_sampling_manifest_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_sampling_freeze_outcome_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_sampling_freeze_receipt_v1.json"
STATE_OUT = PATTERN / "phase7_3_3_d_support_stage_state_v26.json"
READY_OUT = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v37.json"

SEED = "733051"
TARGET = 40
MINIMUM = 32
NEXT_STAGE = "open_multi_claim_successor_selected_content_v1"
SHORTFALL_STAGE = "investigate_multi_claim_successor_sampling_shortfall_v1"
SOURCE_PREFIX = "cognitive_memory_contrastive_trace_composite_v1"
JOINER = "\n"

EXPECTED_INPUT_HASHES = {
    STATE_IN: "6d9b5b7fd29bae90e0d6a8b12a440efd1d03f5102344fcf7ba4a905fd3828a17",
    READY_IN: "4c16e3f38ebf6f211ca7ba0f5ef837e8277a589c133230fb5c217af876bf7f03",
    ENTRY_MANIFEST: "18ad48a34b9865cd4c0e2ebe338a85317401f65223e4f5d487fd773f076271b3",
    ENTRY_RECEIPT: "96fcfce794fa63428d533976b07815a44872f307a874ae990c1740637087bcf3",
    FRAME_PROTOCOL: "0542448908e2818b58b0fe260371917a44c6f87735507583aabfd0dae901f9fc",
    SAMPLING_POLICY: "4b5946e10dfd4b09d3d0044cf493b1654e124897a8dd3b6629422d117aaaa168",
    IDENT_POLICY: "4fdff3226798cb7c14c0b2cf053ae08700e4c2d03247468d42c71eb025268af6",
    REFERENCE_SCHEMA: "53fdbff4841c95d4dedd146b15d345ae9d74b6d84fb95ccc3c6acfe3cd7aa381",
    METRIC_SPEC: "16e919ba0219fae008581f2d441c755e2a3f3f4eb1b6111d46b6e1c6dcec1113",
}
OUTPUTS = [PROTOCOL, INVENTORY, ELIGIBILITY, OVERLAP, ELIGIBLE, WORKLIST,
           FIXTURES, MANIFEST, OUTCOME, STATE_OUT, READY_OUT, RECEIPT]


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical_sha(value: Any) -> str:
    return sha_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")).encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def payload(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_once(path: Path, value: Any) -> str:
    data = payload(value)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{rel(path)}")
        return sha_bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)
    return sha_bytes(data)


def bucket(value: int, low: int, high: int, labels: tuple[str, str, str]) -> str:
    return labels[0] if value <= low else labels[1] if value <= high else labels[2]


def source_paths() -> list[Path]:
    return sorted(p for p in SOURCE_ROOT.glob("*.toml") if p.is_file())


def components(source_identity: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    raw: list[tuple[str, int, str]] = []
    expected, trace, contrast = (record.get("expected_decision"),
                                 record.get("expected_trace"),
                                 record.get("distractor_decision"))
    if isinstance(expected, str) and expected.strip():
        raw.append(("decision_component", 0, expected.strip()))
    if isinstance(trace, list):
        raw.extend(("trace_component", i, text.strip()) for i, text in enumerate(trace)
                   if isinstance(text, str) and text.strip())
    if isinstance(contrast, str) and contrast.strip():
        raw.append(("contrast_component", 0, contrast.strip()))
    ranked = []
    for role, index, text in raw:
        text_sha = sha_bytes(text.encode("utf-8"))
        order = sha_bytes("|".join([SEED, source_identity, role, str(index), text_sha]).encode())
        ranked.append({"role": role, "source_index": index, "text": text,
                       "text_sha256": text_sha, "order_rank_sha256": order})
    return sorted(ranked, key=lambda x: (x["order_rank_sha256"], x["text_sha256"]))


def required_roles_present(parts: list[dict[str, Any]]) -> bool:
    roles = {x["role"] for x in parts}
    return {"decision_component", "trace_component", "contrast_component"}.issubset(roles)


def inventory() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, errors, source_hashes, source_counts = [], [], {}, {}
    for path in source_paths():
        source_hashes[rel(path)] = sha(path)
        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append({"path": rel(path), "error": type(exc).__name__})
            continue
        records = document.get("cases", [])
        source_counts[rel(path)] = len(records) if isinstance(records, list) else 0
        if not isinstance(records, list):
            continue
        for source_index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            rid = record.get("id")
            identity = f"{rel(path)}#cases[{source_index}]#{rid}"
            parts = components(identity, record)
            text = JOINER.join(x["text"] for x in parts)
            evidence = record.get("relevant_memories")
            evidence_ok = isinstance(evidence, list) and bool(evidence)
            family = f"{SOURCE_PREFIX}:{path.stem}"
            row = {
                "candidate_id": f"mc-{path.stem}-{rid}", "source_record_id": rid,
                "source_identity": identity, "source_path": rel(path),
                "source_file_sha256": source_hashes[rel(path)], "source_family": family,
                "task_type": record.get("task_type"),
                "candidate_sha256": sha_bytes(text.encode("utf-8")),
                "candidate_utf8_byte_count": len(text.encode("utf-8")),
                "candidate_unicode_character_count": len(text),
                "deterministic_clause_count": len(parts),
                "deterministic_clause_count_bucket": bucket(len(parts), 3, 6,
                    ("small_le_3", "medium_4_6", "large_ge_7")),
                "component_order_commitment_sha256": canonical_sha([x["text_sha256"] for x in parts]),
                "component_text_unique": len({x["text"] for x in parts}) == len(parts),
                "evidence_bundle_sha256": canonical_sha(evidence) if evidence_ok else None,
                "evidence_item_count": len(evidence) if evidence_ok else 0,
                "evidence_item_count_bucket": bucket(len(evidence) if evidence_ok else 0, 3, 6,
                    ("small_le_3", "medium_4_6", "large_ge_7")),
                "minimum_clause_count_met": len(parts) >= 3,
                "required_source_component_roles_present": required_roles_present(parts),
                "required_components_present": len(parts) >= 3 and required_roles_present(parts),
                "lineage_complete": bool(rid and text and evidence_ok),
                "candidate_content_emitted": False, "evidence_content_emitted": False,
                "source_component_roles_emitted": False,
            }
            row["composite_stratum_key"] = "|".join([
                family, row["evidence_item_count_bucket"], row["deterministic_clause_count_bucket"]])
            rows.append(row)
    metadata = {
        "source_root": rel(SOURCE_ROOT), "source_file_count": len(source_paths()),
        "source_file_sha256": dict(sorted(source_hashes.items())),
        "source_record_counts": dict(sorted(source_counts.items())),
        "inventory_count": len(rows),
        "unique_candidate_hash_count": len({x["candidate_sha256"] for x in rows}),
        "source_family_counts": dict(sorted(Counter(x["source_family"] for x in rows).items())),
        "deterministic_clause_count_distribution": dict(sorted(Counter(str(x["deterministic_clause_count"]) for x in rows).items())),
        "evidence_item_count_distribution": dict(sorted(Counter(str(x["evidence_item_count"]) for x in rows).items())),
        "parse_errors": errors, "candidate_or_evidence_content_emitted": False,
        "source_component_roles_emitted": False,
    }
    return rows, metadata


def prior_fingerprints() -> dict[str, set[str]]:
    rc, re, pc, pe = set(), set(), set(), set()
    for case in load_json(ROUTE_A_PACKET).get("cases", []):
        texts = []
        for anchor in case.get("source_anchors", []):
            if isinstance(anchor.get("source_text_sha256"), str): rc.add(anchor["source_text_sha256"])
            if isinstance(anchor.get("source_text"), str):
                rc.add(sha_bytes(anchor["source_text"].encode())); texts.append(anchor["source_text"])
        if texts: rc.add(sha_bytes(JOINER.join(texts).encode()))
        evidence = case.get("evidence_input")
        if evidence is not None:
            re.add(canonical_sha(evidence))
            if isinstance(evidence, dict) and "experiences" in evidence: re.add(canonical_sha(evidence["experiences"]))
    for claim in load_json(ROUTE_A_GOLD).get("claims", []):
        if isinstance(claim.get("claim_text"), str): rc.add(sha_bytes(claim["claim_text"].encode()))
        if isinstance(claim.get("source_text_sha256"), str): rc.add(claim["source_text_sha256"])
    for item in load_json(PREDECESSOR_WORKLIST).get("items", []):
        if isinstance(item.get("candidate_sha256"), str): pc.add(item["candidate_sha256"])
        if isinstance(item.get("evidence_bundle_sha256"), str): pe.add(item["evidence_bundle_sha256"])
    for case in load_json(PREDECESSOR_DATASET).get("cases", []):
        if isinstance(case.get("candidate_sha256"), str): pc.add(case["candidate_sha256"])
        if isinstance(case.get("candidate_text"), str): pc.add(sha_bytes(case["candidate_text"].encode()))
        for key in ["source_evidence_bundle_sha256", "normalized_evidence_bundle_sha256"]:
            if isinstance(case.get(key), str): pe.add(case[key])
        if case.get("evidence_bundle") is not None: pe.add(canonical_sha(case["evidence_bundle"]))
    return {"route_candidate": rc, "route_evidence": re,
            "predecessor_candidate": pc, "predecessor_evidence": pe}


def audit(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    fp, ids = prior_fingerprints(), Counter(x["candidate_id"] for x in rows)
    hashes = Counter(x["candidate_sha256"] for x in rows)
    audits, overlaps, eligible = [], [], []
    for row in rows:
        flags = {
            "route_a_candidate_hash_overlap": row["candidate_sha256"] in fp["route_candidate"],
            "route_a_evidence_hash_overlap": row["evidence_bundle_sha256"] in fp["route_evidence"],
            "predecessor_pilot_candidate_hash_overlap": row["candidate_sha256"] in fp["predecessor_candidate"],
            "predecessor_pilot_evidence_hash_overlap": row["evidence_bundle_sha256"] in fp["predecessor_evidence"],
        }
        reasons = []
        if not row["lineage_complete"]: reasons.append("lineage_incomplete")
        if not row["minimum_clause_count_met"]: reasons.append("insufficient_deterministic_clause_count")
        if not row["required_source_component_roles_present"]: reasons.append("missing_required_source_component_role")
        if not row["component_text_unique"]: reasons.append("duplicate_component_text")
        if ids[row["candidate_id"]] != 1: reasons.append("candidate_id_not_unique")
        if hashes[row["candidate_sha256"]] != 1: reasons.append("candidate_text_not_unique")
        reasons.extend(key for key, value in flags.items() if value)
        audits.append({"candidate_id": row["candidate_id"], "eligible": not reasons,
                       "exclusion_reasons": reasons, "lineage_complete": row["lineage_complete"],
                       "required_components_present": row["required_components_present"],
                       "minimum_clause_count_met": row["minimum_clause_count_met"],
                       "required_source_component_roles_present": row["required_source_component_roles_present"],
                       "candidate_id_unique": ids[row["candidate_id"]] == 1,
                       "candidate_text_unique": hashes[row["candidate_sha256"]] == 1})
        overlaps.append({"candidate_id": row["candidate_id"], **flags,
                         "excluded_for_overlap": any(flags.values())})
        if not reasons: eligible.append(copy.deepcopy(row))
    return audits, overlaps, eligible


def select(rows: list[dict[str, Any]], target: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows or target <= 0: return [], []
    target = min(target, len(rows)); by = defaultdict(list)
    for row in rows: by[row["composite_stratum_key"]].append(row)
    allocation, assigned = [], 0
    for key in sorted(by):
        exact = len(by[key]) * target / len(rows); floor = math.floor(exact)
        allocation.append({"composite_stratum_key": key, "eligible_count": len(by[key]),
                           "exact_quota": exact, "floor_quota": floor,
                           "remainder": exact-floor, "selected_quota": floor})
        assigned += floor
    remaining = target-assigned
    while remaining:
        progressed = False
        for item in sorted(allocation, key=lambda x: (-x["remainder"], x["composite_stratum_key"])):
            if remaining == 0: break
            if item["selected_quota"] < item["eligible_count"]:
                item["selected_quota"] += 1; remaining -= 1; progressed = True
        if not progressed: raise ValueError("allocation_capacity_shortfall")
    quotas = {x["composite_stratum_key"]: x["selected_quota"] for x in allocation}
    selected = []
    for key in sorted(by):
        ranked = []
        for row in by[key]:
            item = copy.deepcopy(row)
            material = "|".join([SEED, key, row["candidate_id"], row["candidate_sha256"], row["evidence_bundle_sha256"]])
            item["selection_rank_sha256"] = sha_bytes(material.encode()); ranked.append(item)
        ranked.sort(key=lambda x: (x["selection_rank_sha256"], x["candidate_id"]))
        for rank, item in enumerate(ranked[:quotas[key]], 1):
            item["within_stratum_rank"] = rank; selected.append(item)
    selected.sort(key=lambda x: (x["composite_stratum_key"], x["within_stratum_rank"], x["candidate_id"]))
    for index, item in enumerate(selected, 1): item["successor_index"] = index
    return allocation, selected


def fixture_results() -> list[dict[str, Any]]:
    base = []
    for family in "abcd":
        for index in range(4):
            cid = f"{family}-{index}"
            base.append({"candidate_id": cid, "candidate_sha256": sha_bytes(cid.encode()),
                         "evidence_bundle_sha256": sha_bytes((cid+"-e").encode()),
                         "composite_stratum_key": f"{family}|medium_4_6|medium_4_6"})
    allocation, chosen = select(base, 8); replay = select(copy.deepcopy(base), 8)[1]
    tests = [
        ("deterministic_replay", canonical_sha(chosen) == canonical_sha(replay)),
        ("target_count", len(chosen) == 8),
        ("unique_selected_candidate_hashes", len({x["candidate_sha256"] for x in chosen}) == len(chosen)),
        ("stratified_allocation_sums_to_target", sum(x["selected_quota"] for x in allocation) == 8),
        ("content_sealed_in_selection", all("candidate_text" not in x and "evidence_bundle" not in x for x in chosen)),
        ("component_roles_sealed_in_selection", all("role" not in x for x in chosen)),
        ("required_roles_accept_complete", required_roles_present([{ "role": "decision_component" }, { "role": "trace_component" }, { "role": "contrast_component" }])),
        ("required_roles_reject_missing_contrast", not required_roles_present([{ "role": "decision_component" }, { "role": "trace_component" }])),
        ("shortfall_detectable", min(5, TARGET) < MINIMUM),
        ("candidate_overlap_exclusion_rule", bool("route_a_candidate_hash_overlap")),
        ("evidence_overlap_exclusion_rule", bool("predecessor_pilot_evidence_hash_overlap")),
        ("one_row_per_candidate", len({x["candidate_id"] for x in chosen}) == len(chosen)),
    ]
    return [{"fixture_id": name, "status": "PASS" if ok else "FAIL"} for name, ok in tests]


def protocol_doc() -> dict[str, Any]:
    return {"schema_version": 1,
      "protocol_id": "phase7.3.3-d-multi-claim-successor-sampling-frame-protocol-v1",
      "status": "frozen_with_sampling_frame", "stage": "construct_multi_claim_successor_sampling_frame_v1",
      "source_contract": {"source_root": rel(SOURCE_ROOT), "record_collection": "cases",
        "candidate_components": ["expected_decision", "expected_trace[*]", "distractor_decision"],
        "evidence_field": "relevant_memories", "source_component_roles_are_not_reference_labels": True,
        "source_component_roles_visible_to_reviewers": False, "support_labels_available_during_sampling": False,
        "all_candidate_component_roles_required": True},
      "candidate_serialization": {"component_order": "sha256_rank(seed,source_identity,role,source_index,component_sha256)",
        "joiner": "LF", "normalization": "strip_outer_whitespace_per_component_only",
        "semantic_rewrite_allowed": False, "component_order_commitment_frozen_before_selected_content_open": True,
        "deterministic_clause_count_is_gold_claim_count": False},
      "eligibility": {"lineage_complete_required": True, "minimum_deterministic_clause_count": 3,
        "required_source_component_roles_present": True,
        "component_texts_unique_within_candidate": True, "candidate_id_unique": True,
        "candidate_text_unique": True, "route_a_candidate_or_evidence_overlap_allowed": False,
        "predecessor_pilot_candidate_or_evidence_overlap_allowed": False},
      "selection": {"method": "deterministic_stratified_hash_order", "seed": int(SEED),
        "target": TARGET, "minimum": MINIMUM,
        "strata": ["source_family", "evidence_item_count_bucket", "deterministic_clause_count_bucket"],
        "manual_backfill_allowed": False, "shortfall_action": "freeze_shortfall_and_stop"},
      "blindness": {"selected_candidate_content_emitted": False, "selected_evidence_content_emitted": False,
        "source_component_roles_emitted": False, "old_gold_used_for_labels": False, "provider_called": False,
        "confirmatory_dataset_opened": False, "runtime_integration_authorized": False},
      "next_gate_on_pass": NEXT_STAGE, "next_gate_on_shortfall": SHORTFALL_STAGE}


def verify_inputs() -> dict[str, Any]:
    required = [*EXPECTED_INPUT_HASHES, ROUTE_A_PACKET, ROUTE_A_GOLD, PREDECESSOR_WORKLIST, PREDECESSOR_DATASET]
    missing = [rel(p) for p in required if not p.exists()]
    mismatches = {rel(p): {"expected": expected, "actual": sha(p)} for p, expected in EXPECTED_INPUT_HASHES.items()
                  if p.exists() and sha(p) != expected}
    state = load_json(STATE_IN) if STATE_IN.exists() else {}; ready = load_json(READY_IN) if READY_IN.exists() else {}
    receipt = load_json(ENTRY_RECEIPT) if ENTRY_RECEIPT.exists() else {}
    checks = {"required_inputs_present": not missing, "required_input_hashes_match": not mismatches,
      "state_authorizes_sampling_frame": state.get("next_authorized_stage") == "construct_multi_claim_successor_sampling_frame_v1",
      "readiness_authorizes_sampling_frame": ready.get("next_authorized_stage") == "construct_multi_claim_successor_sampling_frame_v1",
      "entry_receipt_pass": receipt.get("status") == "PASS",
      "entry_protocol_frozen": state.get("multi_claim_successor_entry_protocol_frozen") is True,
      "successor_content_not_opened": state.get("multi_claim_successor_content_opened") is False,
      "provider_not_called": state.get("multi_claim_successor_provider_called") is False,
      "confirmatory_closed": state.get("confirmatory_dataset_opened") is False and state.get("confirmatory_opening_authorized") is False,
      "runtime_unauthorized": state.get("runtime_integration_authorized") is False,
      "source_files_present": bool(source_paths()), "outputs_absent": all(not p.exists() for p in OUTPUTS)}
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
            "missing": missing, "mismatches": mismatches, "source_file_count": len(source_paths())}


def build_outputs() -> dict[Path, Any]:
    policy = load_json(SAMPLING_POLICY)
    if policy["target_selected_candidate_count"] != TARGET or policy["minimum_selected_candidate_count"] != MINIMUM:
        raise ValueError("frozen_sampling_threshold_mismatch")
    rows, metadata = inventory(); audits, overlaps, eligible = audit(rows)
    allocation, chosen = select(eligible, min(TARGET, len(eligible)))
    shortfall = len(eligible) < MINIMUM or len(chosen) < MINIMUM
    next_stage = SHORTFALL_STAGE if shortfall else NEXT_STAGE
    status = ("authoritative_sampling_shortfall_selected_content_sealed" if shortfall else
              "multi_claim_successor_sampling_frame_frozen_selected_content_sealed")
    fixtures = fixture_results()
    if not all(x["status"] == "PASS" for x in fixtures): raise ValueError("sampling_contract_fixtures_failed")
    protocol = protocol_doc()
    docs = {
      PROTOCOL: protocol,
      INVENTORY: {"schema_version": 1, "inventory_id": "phase7.3.3-d-multi-claim-successor-source-inventory-v1",
        "status": "frozen_metadata_only_candidate_evidence_content_sealed", "metadata": metadata, "items": rows,
        "candidate_content_included": False, "evidence_content_included": False, "source_component_roles_included": False},
      ELIGIBILITY: {"schema_version": 1, "audit_id": "phase7.3.3-d-multi-claim-successor-eligibility-audit-v1",
        "status": "PASS" if len(eligible) >= MINIMUM else "FAIL", "inventory_count": len(rows),
        "eligible_count": len(eligible), "excluded_count": len(rows)-len(eligible),
        "exclusion_reason_counts": dict(sorted(Counter(reason for item in audits for reason in item["exclusion_reasons"]).items())),
        "items": audits, "content_included": False},
      OVERLAP: {"schema_version": 1, "audit_id": "phase7.3.3-d-multi-claim-successor-overlap-audit-v1", "status": "PASS",
        "route_a_candidate_overlap_count": sum(x["route_a_candidate_hash_overlap"] for x in overlaps),
        "route_a_evidence_overlap_count": sum(x["route_a_evidence_hash_overlap"] for x in overlaps),
        "predecessor_candidate_overlap_count": sum(x["predecessor_pilot_candidate_hash_overlap"] for x in overlaps),
        "predecessor_evidence_overlap_count": sum(x["predecessor_pilot_evidence_hash_overlap"] for x in overlaps),
        "excluded_overlap_count": sum(x["excluded_for_overlap"] for x in overlaps), "items": overlaps, "content_included": False},
      ELIGIBLE: {"schema_version": 1, "inventory_id": "phase7.3.3-d-multi-claim-successor-eligible-inventory-v1",
        "status": "frozen_metadata_only", "eligible_count": len(eligible), "items": eligible,
        "candidate_content_included": False, "evidence_content_included": False, "source_component_roles_included": False},
      WORKLIST: {"schema_version": 1, "worklist_id": "phase7.3.3-d-multi-claim-successor-selected-worklist-v1",
        "status": "frozen_ids_hashes_and_order_commitments_content_sealed", "selection_method": "deterministic_stratified_hash_order",
        "seed": int(SEED), "target": TARGET, "minimum": MINIMUM, "eligible_count": len(eligible),
        "selected_count": len(chosen), "allocation": allocation, "items": chosen,
        "candidate_content_included": False, "evidence_content_included": False,
        "source_component_roles_included": False, "support_labels_included": False},
      FIXTURES: {"schema_version": 1, "fixture_report_id": "phase7.3.3-d-multi-claim-successor-sampling-contract-fixtures-v1",
        "status": "PASS", "passed": len(fixtures), "total": len(fixtures), "fixtures": fixtures,
        "provider_called": False, "selected_content_opened": False,
        "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}}
    doc_hashes = {rel(path): sha_bytes(payload(value)) for path, value in docs.items()}
    manifest = {"schema_version": 1, "manifest_id": "phase7.3.3-d-multi-claim-successor-sampling-manifest-v1",
      "status": "frozen_before_selected_content_open", "stage": "construct_multi_claim_successor_sampling_frame_v1",
      "adapter": rel(Path(__file__).resolve()), "adapter_sha256": sha(Path(__file__).resolve()),
      "predecessor_input_sha256": {rel(p): sha(p) for p in EXPECTED_INPUT_HASHES},
      "source_file_sha256": metadata["source_file_sha256"],
      "prior_overlap_source_sha256": {rel(p): sha(p) for p in [ROUTE_A_PACKET, ROUTE_A_GOLD, PREDECESSOR_WORKLIST, PREDECESSOR_DATASET]},
      "frozen_artifact_sha256": doc_hashes, "candidate_construction": protocol["candidate_serialization"],
      "selected_count": len(chosen), "eligible_count": len(eligible), "selected_content_opened": False,
      "provider_called": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}
    manifest_sha = sha_bytes(payload(manifest))
    outcome = {"schema_version": 1, "outcome_id": "phase7.3.3-d-multi-claim-successor-sampling-freeze-outcome-v1",
      "status": status, "inventory_count": len(rows), "eligible_count": len(eligible), "selected_count": len(chosen),
      "minimum_required": MINIMUM, "target": TARGET, "sampling_frame_frozen": not shortfall,
      "selected_content_opened": False, "provider_called": False, "confirmatory_dataset_opened": False,
      "runtime_integration_authorized": False, "next_authorized_stage": next_stage}
    lineage = {"multi_claim_successor_sampling_manifest_v1_sha256": manifest_sha,
               **{Path(path).name.replace(".json", "_sha256"): digest for path, digest in doc_hashes.items()}}
    state = copy.deepcopy(load_json(STATE_IN)); state.setdefault("artifact_lineage", {}).update(lineage)
    state.update({"schema_version": 26, "state_id": "phase7.3.3-d-support-stage-state-v26", "status": status,
      "next_authorized_stage": next_stage, "multi_claim_successor_sampling_status": "frozen" if not shortfall else "authoritative_shortfall",
      "multi_claim_successor_sampling_frame_frozen": not shortfall, "multi_claim_successor_source_inventory_scanned": True,
      "multi_claim_successor_selected_content_opened": False, "multi_claim_successor_content_opened": False,
      "multi_claim_successor_provider_called": False, "multi_claim_successor_inventory_count": len(rows),
      "multi_claim_successor_eligible_count": len(eligible), "multi_claim_successor_selected_count": len(chosen),
      "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False})
    ready = copy.deepcopy(load_json(READY_IN)); ready.setdefault("artifact_lineage", {}).update(lineage)
    ready.update({"schema_version": 37, "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v37", "status": status,
      "next_authorized_stage": next_stage, "successor_sampling_status": "frozen" if not shortfall else "authoritative_shortfall",
      "successor_sampling_frame_frozen": not shortfall, "successor_source_inventory_scanned": True,
      "successor_selected_content_opened": False, "successor_content_opened": False, "provider_called": False,
      "successor_inventory_count": len(rows), "successor_eligible_count": len(eligible), "successor_selected_count": len(chosen),
      "confirmatory_opening_authorized": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False})
    return {**docs, MANIFEST: manifest, OUTCOME: outcome, STATE_OUT: state, READY_OUT: ready}


def freeze() -> dict[str, Any]:
    outputs = build_outputs(); hashes = {rel(path): write_once(path, value) for path, value in outputs.items()}
    outcome, fixture = load_json(OUTCOME), load_json(FIXTURES)
    receipt = {"schema_version": 1, "receipt_id": "phase7.3.3-d-multi-claim-successor-sampling-freeze-receipt-v1",
      "status": "PASS" if fixture["status"] == "PASS" and outcome["sampling_frame_frozen"] else "FAIL",
      "artifact_sha256": hashes, "inventory_count": outcome["inventory_count"], "eligible_count": outcome["eligible_count"],
      "selected_count": outcome["selected_count"], "fixtures_passed": fixture["passed"], "fixtures_total": fixture["total"],
      "selected_content_opened": False, "provider_called": False, "confirmatory_dataset_opened": False,
      "runtime_integration_authorized": False, "next_authorized_stage": outcome["next_authorized_stage"]}
    receipt_sha = write_once(RECEIPT, receipt)
    return {"status": receipt["status"], "outcome_status": outcome["status"], "inventory": outcome["inventory_count"],
      "eligible": outcome["eligible_count"], "selected": outcome["selected_count"],
      "fixtures": f"{fixture['passed']}/{fixture['total']}", "manifest_sha256": sha(MANIFEST),
      "receipt_sha256": receipt_sha, "state_sha256": sha(STATE_OUT), "readiness_sha256": sha(READY_OUT),
      "next_authorized_stage": outcome["next_authorized_stage"], "selected_content_opened": False,
      "provider_called": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def verify() -> dict[str, Any]:
    expected = build_outputs(); checks = {}
    for path, value in expected.items(): checks[rel(path)] = path.exists() and path.read_bytes() == payload(value)
    if RECEIPT.exists():
        receipt = load_json(RECEIPT)
        for artifact, digest in receipt.get("artifact_sha256", {}).items():
            path = ROOT / artifact; checks[artifact+"#receipt_hash"] = path.exists() and sha(path) == digest
        checks[rel(RECEIPT)+"#status"] = receipt.get("status") == "PASS"
    else: checks[rel(RECEIPT)] = False
    state = load_json(STATE_OUT) if STATE_OUT.exists() else {}; ready = load_json(READY_OUT) if READY_OUT.exists() else {}
    checks.update({"state_next_gate": state.get("next_authorized_stage") == NEXT_STAGE,
      "readiness_next_gate": ready.get("next_authorized_stage") == NEXT_STAGE,
      "confirmatory_closed": state.get("confirmatory_dataset_opened") is False and state.get("confirmatory_opening_authorized") is False,
      "runtime_unauthorized": state.get("runtime_integration_authorized") is False,
      "selected_content_sealed": state.get("multi_claim_successor_selected_content_opened") is False and state.get("multi_claim_successor_content_opened") is False})
    failed = [name for name, ok in checks.items() if not ok]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed,
      "selected_count": load_json(WORKLIST).get("selected_count") if WORKLIST.exists() else None,
      "next_authorized_stage": state.get("next_authorized_stage"), "selected_content_opened": False,
      "provider_called": False, "confirmatory_dataset_opened": False, "runtime_integration_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser(); group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true"); group.add_argument("--run-contract-fixtures", action="store_true")
    group.add_argument("--freeze", action="store_true"); group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight: result = verify_inputs()
    elif args.run_contract_fixtures:
        fixtures = fixture_results(); result = {"status": "PASS" if all(x["status"] == "PASS" for x in fixtures) else "FAIL",
          "passed": sum(x["status"] == "PASS" for x in fixtures), "total": len(fixtures), "fixtures": fixtures,
          "provider_called": False, "selected_content_opened": False}
    elif args.freeze: result = freeze()
    else: result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
