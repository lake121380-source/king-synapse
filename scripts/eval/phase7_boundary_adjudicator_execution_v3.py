#!/usr/bin/env python3
"""Freeze and execute Phase 7.3.3-D1-A Boundary Adjudication v3.

Case-isolated, write-once execution. Completion content is hashed before strict
parsing and never stored raw. First returned content is authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from phase7_execution_attempt_log import append_event, read_entries, verify_entries

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
DATA = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
PROMPT = CONFIG / "phase7_3_3_d_boundary_adjudicator_prompt_v3.md"
ADJUDICATION_PROTOCOL = CONFIG / "phase7_3_3_d_boundary_adjudication_protocol_v3.json"
AGREEMENT_PROTOCOL = CONFIG / "phase7_3_3_d_boundary_agreement_protocol_v3.json"
FAILURE_TAXONOMY = CONFIG / "phase7_3_3_d_failure_taxonomy_v2.json"
RESEARCH_ROUTES = CONFIG / "phase7_3_3_d_research_routes_v1.json"
REFERENCE_PROTOCOL = DATA / "phase7_3_3_d_boundary_reference_protocol_v3.json"
BOUNDARY_PACKET = DATA / "phase7_3_3_d_boundary_blind_review_packet_v1.json"
WORKLIST = REPORTS / "phase7_3_3_d_boundary_adjudication_worklist_a_e_v3.json"
AGREEMENT_REPORT = REPORTS / "phase7_3_3_d_boundary_agreement_a_e_v3.json"
REVIEWER_A = REPORTS / "phase7_3_3_d_boundary_reviewer_a_submission_v3.json"
REVIEWER_E = REPORTS / "phase7_3_3_d_boundary_reviewer_e_submission_v3.json"
FIXTURE_REPORT = REPORTS / "phase7_3_3_d_boundary_adjudicator_contract_fixtures_v3.json"
MANIFEST = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_manifest_v3.json"
ATTEMPT_LOG = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_attempts_v3.jsonl"
CHECKPOINT_DIR = REPORTS / "phase7_3_3_d_boundary_adjudicator_cases_v3"
SUBMISSION = REPORTS / "phase7_3_3_d_boundary_adjudicator_submission_v3.json"
DECISION_LOG = REPORTS / "phase7_3_3_d_segmentation_decision_log_v3.json"
RESULT = REPORTS / "phase7_3_3_d_boundary_adjudicator_execution_result_v3.json"
NEGATIVE_RESULT = REPORTS / "phase7_3_3_d_boundary_adjudicator_negative_result_v3.json"
READINESS_V4 = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v4.json"

BASE_URL = "https://api.gpt.ge/v1"
CREDENTIAL_ENV = "PHASE7_ATOMIC_JUDGE_API_KEY"
MODEL_REQUESTED = "gpt-5.4"
TEMPERATURE, TOP_P, MAX_TOKENS, TIMEOUT_SECONDS = 0, 1, 16000, 600
RESPONSE_FORMAT = {"type": "json_object"}
CLAIM_KEYS = {
    "anchor_id", "source_excerpt", "occurrence_index", "claim_type", "material",
    "claim_origin", "boundary_decision_rationale", "type_decision_rationale",
    "reason_codes", "source_reviewer_claim_ids",
}
CLAIM_TYPES = {"proposition", "scope", "prediction", "causal", "counterexample", "limitation", "falsifiability"}
ORIGINS = {"explicit", "inferred", "synthesized"}
REASON_CODES = {
    "coordination", "nested_proposition", "scope_modifier", "temporal_qualifier",
    "prediction_clause", "evidence_attribution", "causal_relation",
    "counterexample_clause", "limitation_clause", "falsifiability_clause",
    "quantifier_or_threshold", "condition_or_exception", "independent_truth_value",
    "non_assertive_connector", "other_explained",
}
CLAIM_ROLE_BY_SOURCE_FIELD = {
    "proposition": "anchor", "prediction_statement": "prediction",
    "prediction_observable": "prediction_observable",
    "prediction_success_criterion": "prediction_criterion",
    "falsification_statement": "falsification",
    "falsification_observable": "falsification_observable",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha_bytes(raw)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_once(path: Path, value: Any) -> str:
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{path.relative_to(ROOT)}")
        return sha_bytes(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    temporary.replace(path)
    return sha_bytes(encoded)


def split_prompt() -> tuple[str, str]:
    text = PROMPT.read_text(encoding="utf-8-sig")
    sm, um = "## System message\n", "## User message template\n"
    if sm not in text or um not in text:
        raise ValueError("prompt_sections_missing")
    system = text.split(sm, 1)[1].split(um, 1)[0].strip()
    user = text.split(um, 1)[1].strip()
    if "{{CASE_JSON}}" not in user:
        raise ValueError("case_json_placeholder_missing")
    return system, user


def validate_frozen_inputs() -> dict[str, Any]:
    required = [PROMPT, ADJUDICATION_PROTOCOL, AGREEMENT_PROTOCOL, FAILURE_TAXONOMY,
                RESEARCH_ROUTES, REFERENCE_PROTOCOL, BOUNDARY_PACKET, WORKLIST,
                AGREEMENT_REPORT, REVIEWER_A, REVIEWER_E]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise ValueError("missing_frozen_inputs:" + ",".join(missing))
    protocol, worklist, agreement = load(ADJUDICATION_PROTOCOL), load(WORKLIST), load(AGREEMENT_REPORT)
    if protocol.get("status") != "frozen_before_adjudication":
        raise ValueError("adjudication_protocol_not_frozen")
    if worklist.get("status") != "frozen_ready_for_adjudication" or worklist.get("case_count") != 10:
        raise ValueError("adjudication_worklist_not_ready")
    for key in ("support_labels_included", "candidate_gold_or_silver_included", "evidence_bundle_included", "held_out_accessed"):
        if worklist.get(key) is not False:
            raise ValueError(f"adjudication_worklist_visibility_flag:{key}")
    if agreement.get("status") not in {"completed_frozen_before_adjudication"}:
        raise ValueError("agreement_report_not_completed")
    expected = {
        "boundary_packet_sha256": sha(BOUNDARY_PACKET),
        "boundary_reference_protocol_v3_sha256": sha(REFERENCE_PROTOCOL),
        "reviewer_a_submission_sha256": sha(REVIEWER_A),
        "reviewer_e_submission_sha256": sha(REVIEWER_E),
        "agreement_protocol_sha256": sha(AGREEMENT_PROTOCOL),
        "agreement_report_sha256": sha(AGREEMENT_REPORT),
    }
    for lineage_name, lineage in (("protocol", protocol.get("artifact_lineage", {})), ("worklist", worklist.get("artifact_lineage", {}))):
        for key, digest in expected.items():
            if lineage.get(key) != digest:
                raise ValueError(f"{lineage_name}_lineage_mismatch:{key}")
    return {"protocol": protocol, "worklist": worklist, "agreement": agreement}


def execution_manifest() -> dict[str, Any]:
    if load(FIXTURE_REPORT).get("all_fixtures_passed") is not True:
        raise ValueError("contract_fixtures_not_passed")
    return {
        "schema_version": 3,
        "manifest_id": "phase7.3.3-d1-a-boundary-adjudicator-execution-v3",
        "status": "frozen_not_started",
        "object_of_study": "model_adjudicated_boundary_reference_construction_under_frozen_a_e_agreement",
        "gold_status": "model_adjudicated_boundary_reference_candidate_not_human_gold",
        "decision_environment": {
            "provider": "api.gpt.ge", "provider_base_url": BASE_URL,
            "model_requested": MODEL_REQUESTED, "canonical_model_family_expected": MODEL_REQUESTED,
            "temperature": TEMPERATURE, "top_p": TOP_P,
            "seed": None, "seed_supported_by_adapter": False,
            "max_tokens": MAX_TOKENS, "stop_sequences": [],
            "response_format": RESPONSE_FORMAT, "request_timeout_seconds": TIMEOUT_SECONDS,
            "credential_env_name": CREDENTIAL_ENV, "case_isolation": True,
        },
        "artifact_lineage": {
            "adapter_sha256": sha(Path(__file__)), "prompt_sha256": sha(PROMPT),
            "adjudication_protocol_sha256": sha(ADJUDICATION_PROTOCOL),
            "agreement_protocol_sha256": sha(AGREEMENT_PROTOCOL),
            "agreement_report_sha256": sha(AGREEMENT_REPORT), "worklist_sha256": sha(WORKLIST),
            "reviewer_a_submission_sha256": sha(REVIEWER_A), "reviewer_e_submission_sha256": sha(REVIEWER_E),
            "boundary_packet_sha256": sha(BOUNDARY_PACKET),
            "boundary_reference_protocol_v3_sha256": sha(REFERENCE_PROTOCOL),
            "contract_fixtures_sha256": sha(FIXTURE_REPORT),
            "failure_taxonomy_v2_sha256": sha(FAILURE_TAXONOMY),
            "research_routes_v1_sha256": sha(RESEARCH_ROUTES),
        },
        "parser_contract": {
            "parser_version": "phase7_boundary_adjudicator_execution_v3.normalize_case.v1",
            "strict_root_schema": True, "strict_claim_fields": True,
            "exact_contiguous_source_excerpt": True, "occurrence_index_required": True,
            "all_anchors_required": True, "unknown_anchors_rejected": True,
            "overlapping_spans_rejected": True, "reason_code_enum_frozen": True,
            "source_reviewer_claim_ids_same_anchor_only": True,
            "boundary_and_type_rationales_separate": True,
            "protocol_owned_claim_role_and_anchor_group": True,
        },
        "execution_governance": {
            "first_returned_provider_content_per_case_authoritative": True,
            "provider_content_sha256_before_parse": True, "provider_envelope_sha256_recorded": True,
            "raw_provider_content_stored": False, "automatic_representation_repair": False,
            "automatic_semantic_repair": False, "semantic_retry_after_content": False,
            "selective_retry_after_content": False,
            "transport_failure_before_content_may_resume_same_manifest": True,
            "append_only_hash_chained_attempt_log": True, "write_once_case_checkpoints": True,
            "write_once_final_artifacts": True, "deterministic_segmentation_decision_log": True,
        },
        "visibility": {
            "source_anchor_text": True, "reviewer_a_boundary_submission": True,
            "reviewer_e_boundary_submission": True, "agreement_component_diagnostics": True,
            "evidence_bundle": False, "support_labels": False,
            "candidate_gold_or_silver": False, "historical_judge": False,
            "external_knowledge": False, "held_out": False,
        },
        "case_count": 10, "held_out_accessed": False,
    }


def prepare() -> None:
    validate_frozen_inputs(); split_prompt()
    if not FIXTURE_REPORT.exists() or load(FIXTURE_REPORT).get("all_fixtures_passed") is not True:
        raise ValueError("run_contract_fixtures_before_prepare")
    digest = write_once(MANIFEST, execution_manifest())
    if sha(MANIFEST) != digest:
        raise AssertionError("manifest_write_hash_mismatch")
    print(json.dumps({"status": "frozen_not_started", "manifest": str(MANIFEST.relative_to(ROOT)),
                      "manifest_sha256": digest, "model_requested": MODEL_REQUESTED,
                      "provider_called": False, "held_out_accessed": False}, indent=2))


def exact_occurrences(source: str, excerpt: str) -> list[int]:
    starts, cursor = [], 0
    while True:
        found = source.find(excerpt, cursor)
        if found < 0:
            return starts
        starts.append(found); cursor = found + 1


def normalize_case(case: dict[str, Any], response_obj: Any) -> list[dict[str, Any]]:
    if not isinstance(response_obj, dict) or set(response_obj) != {"claims"} or not isinstance(response_obj["claims"], list):
        raise ValueError("response_schema_invalid")
    if not response_obj["claims"]:
        raise ValueError("claims_empty")
    anchors = {a["anchor_id"]: a for a in case["source_anchors"]}
    anchor_order = {a["anchor_id"]: i for i, a in enumerate(case["source_anchors"])}
    permitted_ids = {
        aid: {c["reviewer_claim_id"] for key in ("reviewer_a_claims", "reviewer_e_claims") for c in anchor.get(key, [])}
        for aid, anchor in anchors.items()
    }
    if any(not ids for ids in permitted_ids.values()):
        raise ValueError("anchor_without_source_reviewer_claims")
    seen, spans_by_anchor, preliminary = set(), {aid: [] for aid in anchors}, []
    for response_index, claim in enumerate(response_obj["claims"], start=1):
        if not isinstance(claim, dict) or set(claim) != CLAIM_KEYS:
            raise ValueError(f"claim_fields_invalid:{response_index}")
        anchor_id = claim["anchor_id"]
        if anchor_id not in anchors:
            raise ValueError(f"unknown_anchor:{anchor_id}")
        anchor, excerpt = anchors[anchor_id], claim["source_excerpt"]
        source_field = anchor["source_field"]
        if source_field not in CLAIM_ROLE_BY_SOURCE_FIELD:
            raise ValueError(f"source_field_role_unmapped:{source_field}")
        if not isinstance(excerpt, str) or not excerpt.strip():
            raise ValueError(f"source_excerpt_empty:{anchor_id}:{response_index}")
        starts = exact_occurrences(anchor["source_text"], excerpt)
        if not starts:
            raise ValueError(f"source_excerpt_not_found:{anchor_id}:{response_index}")
        occurrence = claim["occurrence_index"]
        if not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence < 0 or occurrence >= len(starts):
            raise ValueError(f"source_excerpt_occurrence_out_of_range:{anchor_id}:{response_index}:{occurrence}:{len(starts)}")
        start, end = starts[occurrence], starts[occurrence] + len(excerpt)
        if any(max(start, s) < min(end, e) for s, e in spans_by_anchor[anchor_id]):
            raise ValueError(f"overlapping_claim_spans:{anchor_id}:{response_index}")
        spans_by_anchor[anchor_id].append((start, end))
        if claim["claim_type"] not in CLAIM_TYPES:
            raise ValueError(f"claim_type_invalid:{anchor_id}:{response_index}")
        if not isinstance(claim["material"], bool) or claim["claim_origin"] not in ORIGINS:
            raise ValueError(f"structural_metadata_invalid:{anchor_id}:{response_index}")
        for key in ("boundary_decision_rationale", "type_decision_rationale"):
            if not isinstance(claim[key], str) or not claim[key].strip():
                raise ValueError(f"{key}_required:{anchor_id}:{response_index}")
        reasons = claim["reason_codes"]
        if not isinstance(reasons, list) or not reasons or any(not isinstance(code, str) or code not in REASON_CODES for code in reasons):
            raise ValueError(f"reason_codes_invalid:{anchor_id}:{response_index}")
        if len(reasons) != len(set(reasons)):
            raise ValueError(f"reason_codes_duplicate:{anchor_id}:{response_index}")
        provenance = claim["source_reviewer_claim_ids"]
        if not isinstance(provenance, list) or not provenance or any(not isinstance(x, str) for x in provenance):
            raise ValueError(f"source_reviewer_claim_ids_invalid:{anchor_id}:{response_index}")
        if len(provenance) != len(set(provenance)):
            raise ValueError(f"source_reviewer_claim_ids_duplicate:{anchor_id}:{response_index}")
        unknown = sorted(set(provenance) - permitted_ids[anchor_id])
        if unknown:
            raise ValueError(f"source_reviewer_claim_ids_unknown_or_cross_anchor:{anchor_id}:{response_index}:{','.join(unknown)}")
        seen.add(anchor_id)
        preliminary.append({
            "case_id": case["case_id"], "response_sha256": case["response_sha256"],
            "anchor_id": anchor_id, "source_field": source_field, "source_index": anchor["source_index"],
            "source_text_sha256": anchor["source_text_sha256"], "source_span": {"start": start, "end": end},
            "source_occurrence_index": occurrence, "claim_text": excerpt, "claim_type": claim["claim_type"],
            "claim_role": CLAIM_ROLE_BY_SOURCE_FIELD[source_field],
            "anchor_group": f"{case['case_id']}::{source_field}", "material": claim["material"],
            "claim_origin": claim["claim_origin"],
            "boundary_decision_rationale": claim["boundary_decision_rationale"].strip(),
            "type_decision_rationale": claim["type_decision_rationale"].strip(),
            "reason_codes": reasons, "source_reviewer_claim_ids": provenance,
        })
    missing = sorted(set(anchors) - seen)
    if missing:
        raise ValueError("anchors_without_final_claims:" + ",".join(missing))
    preliminary.sort(key=lambda row: (anchor_order[row["anchor_id"]], row["source_span"]["start"], row["source_span"]["end"], row["claim_text"]))
    return [{"adjudicated_claim_id": f"adjudicated-{case['case_id']}-claim-{i:03d}", **row}
            for i, row in enumerate(preliminary, start=1)]


def span_set(claims: list[dict[str, Any]]) -> set[tuple[int, int]]:
    return {(c["source_span"]["start"], c["source_span"]["end"]) for c in claims}


def segmentation_category(a: set[tuple[int, int]], e: set[tuple[int, int]], final: set[tuple[int, int]]) -> str:
    if final == a == e: return "consensus_exact"
    if final == a: return "keep_a_segmentation"
    if final == e: return "keep_e_segmentation"
    if len(final) < len(a) and len(final) < len(e): return "merge_both"
    if len(final) > len(a) and len(final) > len(e): return "split_both"
    return "new_segmentation"


def generate_decision_log(worklist: dict[str, Any], claims: list[dict[str, Any]], manifest_hash: str, submission_hash: str) -> dict[str, Any]:
    final_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        final_by_anchor.setdefault(claim["anchor_id"], []).append(claim)
    entries, category_counts, reason_counts, per_case = [], Counter(), Counter(), {}
    for case in worklist["cases"]:
        case_counter: Counter[str] = Counter()
        for anchor in case["source_anchors"]:
            aid, finals = anchor["anchor_id"], final_by_anchor.get(anchor["anchor_id"], [])
            if not finals:
                raise ValueError(f"decision_log_anchor_without_final_claims:{aid}")
            a, e, final = span_set(anchor["reviewer_a_claims"]), span_set(anchor["reviewer_e_claims"]), span_set(finals)
            category = segmentation_category(a, e, final)
            category_counts[category] += 1; case_counter[category] += 1
            entry_reasons = sorted({code for claim in finals for code in claim["reason_codes"]})
            reason_counts.update(code for claim in finals for code in claim["reason_codes"])
            entries.append({
                "case_id": case["case_id"], "anchor_id": aid, "source_field": anchor["source_field"],
                "reviewer_a_claim_count": len(a), "reviewer_e_claim_count": len(e), "final_claim_count": len(final),
                "reviewer_a_span_set": [{"start": s, "end": x} for s, x in sorted(a)],
                "reviewer_e_span_set": [{"start": s, "end": x} for s, x in sorted(e)],
                "final_span_set": [{"start": s, "end": x} for s, x in sorted(final)],
                "decision_category": category, "reason_codes": entry_reasons,
                "final_claim_ids": [c["adjudicated_claim_id"] for c in finals],
            })
        per_case[case["case_id"]] = case_counter
    representatives = {cat: [{"case_id": x["case_id"], "anchor_id": x["anchor_id"]}
                             for x in entries if x["decision_category"] == cat][:3]
                       for cat in sorted(category_counts)}
    return {
        "schema_version": 3, "log_id": "phase7.3.3-d1-a-segmentation-decision-log-v3",
        "status": "deterministically_generated_from_frozen_adjudication",
        "manifest_sha256": manifest_hash, "submission_sha256": submission_hash,
        "adjudication_protocol_sha256": sha(ADJUDICATION_PROTOCOL),
        "agreement_report_sha256": sha(AGREEMENT_REPORT), "worklist_sha256": sha(WORKLIST),
        "classification_unit": "source_anchor", "decision_count_by_category": dict(sorted(category_counts.items())),
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "per_case_counts": {k: dict(sorted(v.items())) for k, v in sorted(per_case.items())},
        "representative_decisions": representatives, "entries": entries, "entry_count": len(entries),
        "provider_called_for_log_generation": False, "held_out_accessed": False,
    }


def fixture_case(specs: list[tuple[str, str, list[tuple[int, int]], list[tuple[int, int]]]]) -> dict[str, Any]:
    anchors = []
    for index, (aid, text, a_spans, e_spans) in enumerate(specs):
        def make(prefix: str, spans: list[tuple[int, int]]) -> list[dict[str, Any]]:
            return [{"reviewer_claim_id": f"reviewer-{prefix}-fixture-{index}-{j}",
                     "source_span": {"start": s, "end": e}, "claim_text": text[s:e],
                     "claim_type": "proposition", "material": True, "claim_origin": "explicit"}
                    for j, (s, e) in enumerate(spans)]
        anchors.append({"anchor_id": aid, "source_field": "proposition", "source_index": index,
                        "source_text": text, "source_text_sha256": sha_bytes(text.encode()),
                        "reviewer_a_claims": make("a", a_spans), "reviewer_e_claims": make("e", e_spans),
                        "component_diagnostics": []})
    return {"case_id": "fixture_case", "response_sha256": "0" * 64, "source_anchors": anchors}


def fixture_claim(anchor: dict[str, Any], excerpt: str, occurrence: int = 0) -> dict[str, Any]:
    source_id = (anchor["reviewer_a_claims"] + anchor["reviewer_e_claims"])[0]["reviewer_claim_id"]
    return {"anchor_id": anchor["anchor_id"], "source_excerpt": excerpt, "occurrence_index": occurrence,
            "claim_type": "proposition", "material": True, "claim_origin": "explicit",
            "boundary_decision_rationale": "One independently truth-evaluable assertion.",
            "type_decision_rationale": "The span states a proposition.",
            "reason_codes": ["independent_truth_value"], "source_reviewer_claim_ids": [source_id]}


def expect_reject(case: dict[str, Any], response: dict[str, Any], prefix: str) -> str:
    try:
        normalize_case(case, response)
    except ValueError as error:
        if not str(error).startswith(prefix):
            raise AssertionError(f"unexpected_fixture_error:{prefix}:{error}") from error
        return str(error)
    raise AssertionError(f"fixture_was_not_rejected:{prefix}")


def run_contract_fixtures() -> dict[str, Any]:
    validate_frozen_inputs(); split_prompt(); fixtures = []
    one = fixture_case([("fixture-1", "Alpha holds.", [(0, 12)], [(0, 12)])])
    normalized = normalize_case(one, {"claims": [fixture_claim(one["source_anchors"][0], "Alpha holds.")]})
    fixtures.append({"fixture_id": "valid_exact_claim", "expected": "pass", "actual": "pass", "claim_count": len(normalized)})
    repeated = fixture_case([("fixture-2", "Alpha holds. Alpha holds.", [(0, 12)], [(13, 25)])])
    normalized = normalize_case(repeated, {"claims": [fixture_claim(repeated["source_anchors"][0], "Alpha holds.", 1)]})
    fixtures.append({"fixture_id": "repeated_excerpt_occurrence", "expected": "pass", "actual": "pass", "start": normalized[0]["source_span"]["start"]})
    overlap = fixture_case([("fixture-3", "Alpha and Beta hold.", [(0, 14)], [(10, 20)])])
    fixtures.append({"fixture_id": "overlap_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(overlap, {"claims": [fixture_claim(overlap["source_anchors"][0], "Alpha and Beta"), fixture_claim(overlap["source_anchors"][0], "Beta hold.")]}, "overlapping_claim_spans")})
    missing = fixture_case([("fixture-4a", "Alpha holds.", [(0, 12)], [(0, 12)]), ("fixture-4b", "Beta holds.", [(0, 11)], [(0, 11)])])
    fixtures.append({"fixture_id": "missing_anchor_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(missing, {"claims": [fixture_claim(missing["source_anchors"][0], "Alpha holds.")]}, "anchors_without_final_claims")})
    provenance = fixture_case([("fixture-5", "Alpha holds.", [(0, 12)], [(0, 12)])])
    bad = fixture_claim(provenance["source_anchors"][0], "Alpha holds."); bad["source_reviewer_claim_ids"] = ["invented"]
    fixtures.append({"fixture_id": "unknown_provenance_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(provenance, {"claims": [bad]}, "source_reviewer_claim_ids_unknown_or_cross_anchor")})
    reason = fixture_case([("fixture-6", "Alpha holds.", [(0, 12)], [(0, 12)])])
    bad = fixture_claim(reason["source_anchors"][0], "Alpha holds."); bad["reason_codes"] = ["invalid"]
    fixtures.append({"fixture_id": "invalid_reason_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(reason, {"claims": [bad]}, "reason_codes_invalid")})
    excerpt = fixture_case([("fixture-7", "Alpha holds.", [(0, 12)], [(0, 12)])])
    fixtures.append({"fixture_id": "non_exact_excerpt_rejected", "expected": "reject", "actual": "reject",
                     "error_code": expect_reject(excerpt, {"claims": [fixture_claim(excerpt["source_anchors"][0], "Alpha is true.")]}, "source_excerpt_not_found")})
    examples = {
        "consensus_exact": ({(0, 1)}, {(0, 1)}, {(0, 1)}),
        "keep_a_segmentation": ({(0, 1)}, {(0, 2)}, {(0, 1)}),
        "keep_e_segmentation": ({(0, 1)}, {(0, 2)}, {(0, 2)}),
        "merge_both": ({(0, 1), (2, 3)}, {(0, 2), (2, 3)}, {(0, 3)}),
        "split_both": ({(0, 3)}, {(0, 2)}, {(0, 1), (1, 2)}),
        "new_segmentation": ({(0, 1)}, {(1, 2)}, {(2, 3)}),
    }
    actual = {expected: segmentation_category(*sets) for expected, sets in examples.items()}
    if any(k != v for k, v in actual.items()):
        raise AssertionError(f"segmentation_category_fixture_failed:{actual}")
    fixtures.append({"fixture_id": "all_segmentation_categories", "expected": "pass", "actual": "pass", "categories": actual})
    report = {"schema_version": 3, "report_id": "phase7.3.3-d1-a-boundary-adjudicator-contract-fixtures-v3",
              "adapter_sha256": sha(Path(__file__)), "prompt_sha256": sha(PROMPT),
              "adjudication_protocol_sha256": sha(ADJUDICATION_PROTOCOL), "worklist_sha256": sha(WORKLIST),
              "fixture_count": len(fixtures), "passed_fixture_count": len(fixtures),
              "all_fixtures_passed": True, "fixtures": fixtures, "provider_called": False, "held_out_accessed": False}
    write_once(FIXTURE_REPORT, report)
    return report


def request_provider(key: str, system: str, user: str) -> tuple[dict[str, Any], bytes]:
    payload = {"model": MODEL_REQUESTED, "temperature": TEMPERATURE, "top_p": TOP_P,
               "max_tokens": MAX_TOKENS, "response_format": RESPONSE_FORMAT,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    request = urllib.request.Request(BASE_URL + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")), raw


def extract_content(envelope: Any) -> tuple[str, str]:
    if not isinstance(envelope, dict): raise ValueError("provider_envelope_not_object")
    reported = envelope.get("model")
    if not isinstance(reported, str) or not reported: raise ValueError("provider_reported_model_missing")
    choices = envelope.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict): raise ValueError("provider_choices_invalid")
    message = choices[0].get("message")
    if not isinstance(message, dict): raise ValueError("provider_message_invalid")
    content = message.get("content")
    if not isinstance(content, str) or not content: raise ValueError("provider_content_missing_or_non_text")
    return reported, content


def canonical_model_family(reported: str) -> str:
    if reported == MODEL_REQUESTED or reported.startswith(MODEL_REQUESTED + "-"): return MODEL_REQUESTED
    raise ValueError(f"provider_reported_model_outside_requested_family:{MODEL_REQUESTED}:{reported}")


def checkpoint_path(case_id: str) -> Path:
    return CHECKPOINT_DIR / f"{case_id}.json"


def failure_level(error: Exception, content_received: bool) -> tuple[int, str]:
    code = str(error)
    if not content_received or isinstance(error, json.JSONDecodeError) or code.startswith(("provider_", "response_schema_invalid", "claims_empty", "claim_fields_invalid")):
        return 1, "provider_representation_contract"
    return 2, "boundary_semantic_contract"


def execute() -> int:
    state = validate_frozen_inputs()
    if not MANIFEST.exists(): raise ValueError("execution_manifest_missing_run_prepare_first")
    if load(MANIFEST) != execution_manifest(): raise ValueError("execution_manifest_verification_failed")
    manifest_hash = sha(MANIFEST)
    if ATTEMPT_LOG.exists(): verify_entries(read_entries(ATTEMPT_LOG))
    key = os.environ.get(CREDENTIAL_ENV)
    if not key: raise ValueError(f"credential_env_missing:{CREDENTIAL_ENV}")
    system_prompt, user_template = split_prompt()
    worklist, entries = state["worklist"], read_entries(ATTEMPT_LOG)
    all_claims, case_results, reported_models, canonical_models = [], [], set(), set()
    for case in worklist["cases"]:
        case_id, checkpoint = case["case_id"], checkpoint_path(case["case_id"])
        if checkpoint.exists():
            saved = load(checkpoint)
            if saved.get("manifest_sha256") != manifest_hash or saved.get("case_id") != case_id or saved.get("status") != "completed":
                raise ValueError(f"case_checkpoint_verification_failed:{case_id}")
            all_claims.extend(saved["claims"]); case_results.append(saved["case_result"])
            reported_models.add(saved["provider_reported_model"]); canonical_models.add(saved["canonical_model_family"])
            print(f"Adjudicator {case_id}: resumed immutable checkpoint ({len(saved['claims'])} Claims)", flush=True)
            continue
        prior = [x for x in entries if x.get("manifest_sha256") == manifest_hash and x.get("case_id") == case_id and x.get("response_received") is True]
        if prior: raise ValueError(f"authoritative_content_already_recorded_without_checkpoint:{case_id}")
        append_event({"event_type": "boundary_adjudication_case_attempt_started", "manifest_sha256": manifest_hash,
                      "case_id": case_id, "response_received": False, "authoritative_result": False}, ATTEMPT_LOG)
        envelope_bytes = None; envelope_hash = None; content_hash = None; content_received = False
        try:
            case_json = json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            envelope, envelope_bytes = request_provider(key, system_prompt, user_template.replace("{{CASE_JSON}}", case_json))
            envelope_hash = sha_bytes(envelope_bytes)
            reported, content = extract_content(envelope)
            content_received, content_hash = True, sha_bytes(content.encode("utf-8"))
            append_event({"event_type": "boundary_adjudication_provider_content_received", "manifest_sha256": manifest_hash,
                          "case_id": case_id, "response_received": True, "authoritative_result": True,
                          "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash,
                          "raw_provider_content_stored": False}, ATTEMPT_LOG)
            claims = normalize_case(case, json.loads(content)); canonical = canonical_model_family(reported)
            saved = {"schema_version": 3, "case_id": case_id, "status": "completed", "manifest_sha256": manifest_hash,
                     "provider_envelope_sha256": envelope_hash, "provider_content_sha256": content_hash,
                     "provider_reported_model": reported, "canonical_model_family": canonical,
                     "normalized_claims_sha256": canonical_sha(claims), "claims": claims,
                     "case_result": {"case_id": case_id, "status": "completed", "anchor_count": len(case["source_anchors"]),
                                     "claim_count": len(claims), "provider_content_sha256": content_hash},
                     "raw_provider_content_stored": False, "held_out_accessed": False}
            write_once(checkpoint, saved)
            append_event({"event_type": "boundary_adjudication_case_authoritative_success", "manifest_sha256": manifest_hash,
                          "case_id": case_id, "response_received": True, "authoritative_result": True,
                          "provider_content_sha256": content_hash, "normalized_output_sha256": canonical_sha(claims),
                          "claim_count": len(claims), "provider_reported_model": reported,
                          "canonical_model_family": canonical}, ATTEMPT_LOG)
            all_claims.extend(claims); case_results.append(saved["case_result"])
            reported_models.add(reported); canonical_models.add(canonical)
            print(f"Adjudicator {case_id}: {len(claims)} Claims", flush=True)
        except urllib.error.HTTPError as error:
            append_event({"event_type": "boundary_adjudication_case_transport_failure", "manifest_sha256": manifest_hash,
                          "case_id": case_id, "status": f"http_{error.code}", "response_received": False,
                          "authoritative_result": False}, ATTEMPT_LOG)
            print(f"TRANSPORT FAILURE {case_id}: HTTP {error.code}"); return 3
        except (urllib.error.URLError, TimeoutError) as error:
            append_event({"event_type": "boundary_adjudication_case_transport_failure", "manifest_sha256": manifest_hash,
                          "case_id": case_id, "status": type(error).__name__, "response_received": False,
                          "authoritative_result": False}, ATTEMPT_LOG)
            print(f"TRANSPORT FAILURE {case_id}: {type(error).__name__}: {error}"); return 3
        except Exception as error:
            response_received = envelope_bytes is not None
            level, level_code = failure_level(error, content_received)
            event = {"event_type": "boundary_adjudication_case_experimental_failure" if response_received else "boundary_adjudication_case_adapter_failure",
                     "manifest_sha256": manifest_hash, "case_id": case_id, "status": type(error).__name__,
                     "error_code": str(error)[:400], "response_received": response_received,
                     "provider_content_received": content_received, "authoritative_result": response_received,
                     "failure_level": level, "failure_level_code": level_code}
            if envelope_hash: event["provider_envelope_sha256"] = envelope_hash
            if content_hash: event["provider_content_sha256"] = content_hash
            append_event(event, ATTEMPT_LOG)
            write_once(NEGATIVE_RESULT, {
                "schema_version": 3, "result_id": "phase7.3.3-d1-a-boundary-adjudicator-negative-result-v3",
                "status": "authoritative_negative_result" if response_received else "adapter_failure",
                "manifest_sha256": manifest_hash, "case_id": case_id, "failure_type": type(error).__name__,
                "failure_code": str(error)[:400], "response_received": response_received,
                "provider_content_received": content_received, "provider_envelope_sha256": envelope_hash,
                "provider_content_sha256": content_hash,
                "failure_taxonomy": {"level": level, "level_code": level_code,
                    "attribution": {"primary": "provider" if response_received else "implementation",
                        "subtype": "frozen_adjudication_contract_failure" if response_received else "local_adapter_failure_before_provider_response",
                        "confidence": "high" if response_received else "medium", "evidence": [str(error)[:400]], "counterevidence": []}},
                "raw_provider_content_stored": False, "same_manifest_retry_authorized": not response_received,
                "boundary_gold_frozen": False, "support_review_allowed": False, "held_out_accessed": False})
            print(f"EXPERIMENTAL FAILURE {case_id}: {type(error).__name__}: {error}"); return 4
    if canonical_models != {MODEL_REQUESTED}: raise ValueError(f"canonical_model_family_drift:{sorted(canonical_models)}")
    submission = {"schema_version": 3, "submission_id": "phase7.3.3-d1-a-boundary-adjudicator-submission-v3",
                  "status": "completed_model_adjudicated_boundary_reference_candidate",
                  "gold_status": "model_adjudicated_boundary_reference_candidate_not_human_gold",
                  "manifest_sha256": manifest_hash, "adjudication_protocol_sha256": sha(ADJUDICATION_PROTOCOL),
                  "agreement_report_sha256": sha(AGREEMENT_REPORT), "worklist_sha256": sha(WORKLIST),
                  "case_count": len(case_results), "claim_count": len(all_claims), "claims": all_claims,
                  "boundary_gold_frozen": False, "coverage_qa_completed": False,
                  "support_review_allowed": False, "held_out_accessed": False}
    submission_hash = write_once(SUBMISSION, submission)
    decision = generate_decision_log(worklist, all_claims, manifest_hash, submission_hash)
    decision_hash = write_once(DECISION_LOG, decision)
    verify_entries(read_entries(ATTEMPT_LOG)); attempt_hash = sha(ATTEMPT_LOG)
    result = {"schema_version": 3, "execution_id": "phase7.3.3-d1-a-boundary-adjudicator-execution-v3",
              "status": "completed", "manifest_sha256": manifest_hash, "submission_sha256": submission_hash,
              "segmentation_decision_log_sha256": decision_hash, "attempt_log_sha256": attempt_hash,
              "model_requested": MODEL_REQUESTED, "canonical_model_family": MODEL_REQUESTED,
              "provider_reported_models": sorted(reported_models), "completed_case_count": len(case_results),
              "claim_count": len(all_claims), "case_results": case_results, "raw_provider_content_stored": False,
              "adjudication_completed": True, "coverage_qa_allowed": True, "coverage_qa_completed": False,
              "boundary_gold_frozen": False, "support_review_allowed": False, "held_out_accessed": False}
    result_hash = write_once(RESULT, result)
    readiness = {"schema_version": 4, "state_id": "phase7.3.3-d1-reference-construction-readiness-v4",
                 "status": "adjudication_completed_coverage_qa_allowed",
                 "preserves_v3_sha256": sha(REPORTS / "phase7_3_3_d1_reference_construction_readiness_v3.json"),
                 "manifest_sha256": manifest_hash, "adjudicator_submission_sha256": submission_hash,
                 "segmentation_decision_log_sha256": decision_hash, "execution_result_sha256": result_hash,
                 "gates": {"agreement_frozen": True, "adjudication_allowed": True, "adjudication_completed": True,
                           "coverage_qa_allowed": True, "coverage_qa_completed": False, "boundary_gold_frozen": False,
                           "support_review_allowed": False, "held_out_accessed": False}}
    readiness_hash = write_once(READINESS_V4, readiness)
    print(json.dumps({"status": "completed", "manifest_sha256": manifest_hash, "cases": len(case_results),
                      "claims": len(all_claims), "submission_sha256": submission_hash,
                      "segmentation_decision_log_sha256": decision_hash, "execution_result_sha256": result_hash,
                      "readiness_v4_sha256": readiness_hash, "decision_count_by_category": decision["decision_count_by_category"],
                      "coverage_qa_allowed": True, "boundary_gold_frozen": False,
                      "support_review_allowed": False}, ensure_ascii=False, indent=2))
    return 0


def verify() -> dict[str, Any]:
    state = validate_frozen_inputs()
    checks: dict[str, Any] = {"frozen_inputs": True, "held_out_accessed": False}
    if FIXTURE_REPORT.exists():
        fixture = load(FIXTURE_REPORT)
        checks.update({"fixtures_passed": fixture.get("all_fixtures_passed") is True,
                       "fixture_adapter_sha_matches": fixture.get("adapter_sha256") == sha(Path(__file__)),
                       "fixture_prompt_sha_matches": fixture.get("prompt_sha256") == sha(PROMPT)})
    if MANIFEST.exists():
        checks["manifest_matches_current_frozen_environment"] = load(MANIFEST) == execution_manifest()
        checks["manifest_sha256"] = sha(MANIFEST)
    if ATTEMPT_LOG.exists(): verify_entries(read_entries(ATTEMPT_LOG)); checks["attempt_log_hash_chain_valid"] = True
    if SUBMISSION.exists():
        submission = load(SUBMISSION)
        regenerated = generate_decision_log(state["worklist"], submission["claims"], sha(MANIFEST), sha(SUBMISSION))
        checks.update({"decision_log_deterministic_replay": DECISION_LOG.exists() and load(DECISION_LOG) == regenerated,
                       "submission_claim_count": len(submission["claims"]),
                       "boundary_gold_frozen": submission.get("boundary_gold_frozen"),
                       "support_review_allowed": submission.get("support_review_allowed")})
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true"); parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if sum(bool(x) for x in (args.fixtures, args.prepare, args.execute, args.verify)) != 1:
        parser.error("choose exactly one of --fixtures, --prepare, --execute, --verify")
    if args.fixtures: print(json.dumps(run_contract_fixtures(), ensure_ascii=False, indent=2)); return 0
    if args.prepare: prepare(); return 0
    if args.execute: return execute()
    print(json.dumps(verify(), ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())

