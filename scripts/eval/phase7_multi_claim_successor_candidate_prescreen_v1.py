#!/usr/bin/env python3
"""Run deterministic, non-Gold multi-claim candidate prescreen on the frozen successor selection."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"

STATE_IN = PATTERN / "phase7_3_3_d_support_stage_state_v27.json"
READY_IN = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v38.json"
CONTENT_MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_content_open_manifest_v1.json"
CONTENT_RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_content_open_receipt_v1.json"
DATASET = PATTERN / "phase7_3_3_d_multi_claim_successor_selected_dataset_v1.json"
IDENTIFIABILITY = CONFIG / "phase7_3_3_d_multi_claim_identifiability_policy_v1.json"
FRAME_PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_frame_construction_protocol_v1.json"

PROTOCOL = CONFIG / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_protocol_v1.json"
REPORT = REPORTS / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_report_v1.json"
FIXTURES = REPORTS / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_contract_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_manifest_v1.json"
OUTCOME = REPORTS / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_outcome_v1.json"
RECEIPT = REPORTS / "phase7_3_3_d_multi_claim_successor_candidate_prescreen_receipt_v1.json"
STATE_OUT = PATTERN / "phase7_3_3_d_support_stage_state_v28.json"
READY_OUT = REPORTS / "phase7_3_3_d1_reference_construction_readiness_v39.json"

CURRENT_STAGE = "run_multi_claim_successor_candidate_prescreen_v1"
NEXT_STAGE = "construct_multi_claim_successor_independent_boundary_review_a_v1"
EXPECTED = {
    STATE_IN: "c6c4fa16ba45d49f72d5168878636d68c2710184d2188d75f1b5174b3d7f3f5d",
    READY_IN: "ef52c2e9308b2674c09c969530192f63bfa9942d31cba57f444113834b9292c8",
    CONTENT_MANIFEST: "a15d4abd945f6615c98bfe0419386fd5b971dfe04d00b6e29ef50b1b8e6568bf",
    CONTENT_RECEIPT: "12b37cd42481f5526234b3d0aa3b95c290ee28f52e076d4ee45cda694f8d44e5",
    DATASET: "858c60201f25a97e9787e96ef0554c05b3bf36b80c76f86406b520ecb203d3ca",
    IDENTIFIABILITY: "4fdff3226798cb7c14c0b2cf053ae08700e4c2d03247468d42c71eb025268af6",
    FRAME_PROTOCOL: "0542448908e2818b58b0fe260371917a44c6f87735507583aabfd0dae901f9fc",
}
OUTPUTS = [PROTOCOL, REPORT, FIXTURES, MANIFEST, OUTCOME, STATE_OUT, READY_OUT, RECEIPT]


def hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return hash_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hash_bytes(payload.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def json_body(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_once(path: Path, value: Any) -> str:
    payload = json_body(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable_artifact_exists_with_different_content:{relative(path)}")
        return hash_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hash_bytes(payload)


def exact_units(candidate_text: str) -> list[str]:
    return candidate_text.split("\n")


def inspect_case(case: dict[str, Any]) -> dict[str, Any]:
    text = case["candidate_text"]
    units = exact_units(text)
    evidence_texts = [item["content"] for item in case["evidence_bundle"]]
    evidence_set = set(evidence_texts)
    exact_overlap = sum(unit in evidence_set for unit in units)
    exact_nonoverlap = len(units) - exact_overlap
    candidate_hash_verified = hash_bytes(text.encode("utf-8")) == case["candidate_sha256"]
    evidence_hash_verified = canonical_sha256(case["evidence_bundle"]) == case["normalized_evidence_bundle_sha256"]
    nonempty = all(unit != "" for unit in units)
    unique_count = len(set(units))
    multi_unit_proxy = len(units) >= 2 and unique_count >= 2 and nonempty
    mixed_exact_overlap_proxy = exact_overlap >= 1 and exact_nonoverlap >= 1
    case_pass = (
        candidate_hash_verified
        and evidence_hash_verified
        and len(evidence_texts) >= 1
        and multi_unit_proxy
        and mixed_exact_overlap_proxy
    )
    return {
        "successor_index": case["successor_index"],
        "case_id": case["case_id"],
        "candidate_sha256": case["candidate_sha256"],
        "deterministic_lf_unit_count": len(units),
        "unique_exact_unit_count": unique_count,
        "nonempty_exact_unit_count": sum(unit != "" for unit in units),
        "evidence_item_count": len(evidence_texts),
        "exact_candidate_unit_evidence_overlap_count": exact_overlap,
        "exact_candidate_unit_evidence_nonoverlap_count": exact_nonoverlap,
        "candidate_hash_verified": candidate_hash_verified,
        "normalized_evidence_hash_verified": evidence_hash_verified,
        "multi_unit_structural_proxy": multi_unit_proxy,
        "mixed_exact_overlap_structural_proxy": mixed_exact_overlap_proxy,
        "prescreen_pass": case_pass,
        "claim_boundary_emitted": False,
        "support_label_emitted": False,
    }


def run_prescreen() -> dict[str, Any]:
    dataset = load_json(DATASET)
    cases = dataset["cases"]
    rows = [inspect_case(case) for case in cases]
    candidate_hashes = [row["candidate_sha256"] for row in rows]
    selected_count = len(rows)
    unique_candidate_rate = len(set(candidate_hashes)) / selected_count if selected_count else 0.0
    multi_unit_rate = sum(row["multi_unit_structural_proxy"] for row in rows) / selected_count if selected_count else 0.0
    mixed_overlap_rate = sum(row["mixed_exact_overlap_structural_proxy"] for row in rows) / selected_count if selected_count else 0.0
    all_hashes_verified = all(
        row["candidate_hash_verified"] and row["normalized_evidence_hash_verified"] for row in rows
    )
    thresholds = {
        "minimum_selected_candidate_count": 32,
        "unique_candidate_rate_min": 1.0,
        "multi_unit_structural_proxy_rate_min": 0.8,
        "mixed_exact_overlap_structural_proxy_rate_min": 0.5,
    }
    checks = {
        "minimum_selected_candidate_count_met": selected_count >= thresholds["minimum_selected_candidate_count"],
        "unique_candidate_rate_met": unique_candidate_rate >= thresholds["unique_candidate_rate_min"],
        "multi_unit_structural_proxy_rate_met": multi_unit_rate >= thresholds["multi_unit_structural_proxy_rate_min"],
        "mixed_exact_overlap_structural_proxy_rate_met": mixed_overlap_rate >= thresholds["mixed_exact_overlap_structural_proxy_rate_min"],
        "all_content_commitments_replayed": all_hashes_verified,
        "no_candidate_dropped": selected_count == dataset["case_count"],
        "no_boundary_or_support_output": all(
            not row["claim_boundary_emitted"] and not row["support_label_emitted"] for row in rows
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    counts = [row["deterministic_lf_unit_count"] for row in rows]
    return {
        "schema_version": 1,
        "report_id": "phase7.3.3-d-multi-claim-successor-candidate-prescreen-report-v1",
        "status": status,
        "interpretation": "deterministic_structural_prescreen_not_boundary_gold_not_support_gold",
        "selected_count": selected_count,
        "prescreen_pass_count": sum(row["prescreen_pass"] for row in rows),
        "prescreen_fail_count": sum(not row["prescreen_pass"] for row in rows),
        "excluded_after_prescreen_count": 0,
        "unique_candidate_rate": unique_candidate_rate,
        "multi_unit_structural_proxy_rate": multi_unit_rate,
        "mixed_exact_overlap_structural_proxy_rate": mixed_overlap_rate,
        "median_deterministic_lf_unit_count": statistics.median(counts) if counts else None,
        "thresholds": thresholds,
        "frame_checks": checks,
        "cases": rows,
        "boundary_claim_count": None,
        "support_label_distribution": None,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def contract_fixtures() -> list[dict[str, Any]]:
    def fake(text: str, evidence: list[str]) -> dict[str, Any]:
        bundle = [
            {"evidence_id": f"evidence-{index + 1:03d}", "source_index": index, "content": item}
            for index, item in enumerate(evidence)
        ]
        return {
            "successor_index": 1,
            "case_id": "fixture",
            "candidate_text": text,
            "candidate_sha256": hash_bytes(text.encode("utf-8")),
            "evidence_bundle": bundle,
            "normalized_evidence_bundle_sha256": canonical_sha256(bundle),
        }

    valid = inspect_case(fake("alpha\nbeta\ngamma", ["alpha", "beta"]))
    duplicate = inspect_case(fake("alpha\nalpha", ["alpha"]))
    single = inspect_case(fake("alpha", ["alpha"]))
    blank = inspect_case(fake("alpha\n\nbeta", ["alpha"]))
    mismatch = fake("alpha\nbeta", ["alpha"])
    mismatch["candidate_sha256"] = "0" * 64
    mismatch_result = inspect_case(mismatch)
    return [
        {"fixture_id": "deterministic_lf_segmentation", "status": "PASS" if exact_units("a\nb") == ["a", "b"] else "FAIL"},
        {"fixture_id": "multi_unit_proxy_accepts_unique_nonempty_units", "status": "PASS" if valid["multi_unit_structural_proxy"] else "FAIL"},
        {"fixture_id": "single_unit_proxy_rejected", "status": "PASS" if not single["multi_unit_structural_proxy"] else "FAIL"},
        {"fixture_id": "duplicate_units_detected", "status": "PASS" if duplicate["unique_exact_unit_count"] == 1 and not duplicate["multi_unit_structural_proxy"] else "FAIL"},
        {"fixture_id": "blank_unit_detected", "status": "PASS" if blank["nonempty_exact_unit_count"] == 2 and not blank["multi_unit_structural_proxy"] else "FAIL"},
        {"fixture_id": "mixed_exact_overlap_proxy_deterministic", "status": "PASS" if valid["exact_candidate_unit_evidence_overlap_count"] == 2 and valid["exact_candidate_unit_evidence_nonoverlap_count"] == 1 else "FAIL"},
        {"fixture_id": "candidate_hash_mismatch_detected", "status": "PASS" if not mismatch_result["candidate_hash_verified"] and not mismatch_result["prescreen_pass"] else "FAIL"},
        {"fixture_id": "prescreen_emits_no_gold", "status": "PASS" if not valid["claim_boundary_emitted"] and not valid["support_label_emitted"] else "FAIL"},
    ]


def protocol_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": "phase7.3.3-d-multi-claim-successor-candidate-prescreen-protocol-v1",
        "status": "frozen_after_selected_content_open_before_boundary_review",
        "purpose": "Apply a deterministic structural proxy that detects obvious single-unit or non-heterogeneous Candidate degeneration before independent Boundary Review.",
        "scope": "selected_40_reference_construction_cases_only",
        "unitization": {
            "method": "exact_lf_split_without_normalization",
            "semantic_rewrite_allowed": False,
            "deterministic_unit_count_is_reference_claim_count": False,
            "coordination_or_component_count_is_gold": False,
        },
        "structural_proxies": {
            "multi_unit": "at least two unique non-empty exact LF units",
            "mixed_exact_overlap": "at least one exact Candidate unit appears in Evidence and at least one does not",
            "exact_overlap_is_support_label": False,
            "nonoverlap_is_unsupported_label": False,
        },
        "threshold_provenance": {
            "minimum_count_and_rates_inherited_from_pre_content_open_identifiability_policy_v1": True,
            "prescreen_is_not_structural_identifiability_gate": True,
            "final_multi_claim_and_label_heterogeneity_require_frozen_reference": True,
        },
        "outputs_forbidden": [
            "atomic_claim_boundary",
            "claim_type",
            "support_label",
            "material_error",
            "cited_evidence_ids",
            "old_gold",
            "arm_output",
        ],
        "governance": {
            "selected_cases_may_be_dropped": False,
            "provider_call_authorized": False,
            "same_version_repair_after_freeze": False,
            "silent_repair_allowed": False,
            "confirmatory_opening_authorized": False,
            "runtime_integration_authorized": False,
        },
        "on_pass": NEXT_STAGE,
        "on_failure": "freeze_prescreen_negative_result_and_stop_before_boundary_review",
    }


def preflight() -> dict[str, Any]:
    missing = [relative(path) for path in EXPECTED if not path.exists()]
    mismatches = {
        relative(path): {"expected": digest, "actual": file_sha256(path)}
        for path, digest in EXPECTED.items()
        if path.exists() and file_sha256(path) != digest
    }
    state = load_json(STATE_IN) if STATE_IN.exists() else {}
    ready = load_json(READY_IN) if READY_IN.exists() else {}
    dataset = load_json(DATASET) if DATASET.exists() else {}
    checks = {
        "required_inputs_present": not missing,
        "input_hashes_match": not mismatches,
        "state_authorizes_prescreen": state.get("next_authorized_stage") == CURRENT_STAGE,
        "readiness_authorizes_prescreen": ready.get("next_authorized_stage") == CURRENT_STAGE,
        "selected_content_open": dataset.get("status") == "selected_content_open_reference_construction_only",
        "selected_count_40": dataset.get("case_count") == 40 and len(dataset.get("cases", [])) == 40,
        "source_roles_blind": dataset.get("source_component_roles_present") is False,
        "support_labels_blind": dataset.get("support_labels_present") is False,
        "old_gold_absent": dataset.get("old_gold_present") is False,
        "arm_outputs_absent": dataset.get("arm_outputs_present") is False,
        "provider_not_called": state.get("multi_claim_successor_provider_called") is False,
        "confirmatory_closed": state.get("confirmatory_dataset_opened") is False,
        "runtime_unauthorized": state.get("runtime_integration_authorized") is False,
        "outputs_absent": all(not path.exists() for path in OUTPUTS),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "missing": missing,
        "mismatches": mismatches,
    }


def build_outputs() -> dict[Path, Any]:
    report = run_prescreen()
    fixtures = contract_fixtures()
    fixture_report = {
        "schema_version": 1,
        "fixture_report_id": "phase7.3.3-d-multi-claim-successor-candidate-prescreen-contract-fixtures-v1",
        "status": "PASS" if all(item["status"] == "PASS" for item in fixtures) else "FAIL",
        "passed": sum(item["status"] == "PASS" for item in fixtures),
        "total": len(fixtures),
        "fixtures": fixtures,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
    }
    protocol = protocol_document()
    documents = {PROTOCOL: protocol, REPORT: report, FIXTURES: fixture_report}
    input_sha256 = {relative(path): file_sha256(path) for path in EXPECTED}
    artifact_sha256 = {relative(path): hash_bytes(json_body(value)) for path, value in documents.items()}
    manifest = {
        "schema_version": 1,
        "manifest_id": "phase7.3.3-d-multi-claim-successor-candidate-prescreen-manifest-v1",
        "status": "frozen_before_independent_boundary_review",
        "adapter": relative(Path(__file__)),
        "adapter_sha256": file_sha256(Path(__file__)),
        "input_sha256": input_sha256,
        "artifact_sha256": artifact_sha256,
        "selected_count": report["selected_count"],
        "prescreen_pass_count": report["prescreen_pass_count"],
        "excluded_after_prescreen_count": 0,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    manifest_sha = hash_bytes(json_body(manifest))
    passed = report["status"] == "PASS" and fixture_report["status"] == "PASS"
    next_stage = NEXT_STAGE if passed else None
    outcome = {
        "schema_version": 1,
        "outcome_id": "phase7.3.3-d-multi-claim-successor-candidate-prescreen-outcome-v1",
        "status": "candidate_prescreen_passed_structural_proxy_only" if passed else "candidate_prescreen_failed_boundary_review_blocked",
        "selected_count": report["selected_count"],
        "prescreen_pass_count": report["prescreen_pass_count"],
        "prescreen_fail_count": report["prescreen_fail_count"],
        "excluded_after_prescreen_count": 0,
        "boundary_gold_created": False,
        "support_gold_created": False,
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": next_stage,
    }
    lineage = {
        "multi_claim_successor_candidate_prescreen_manifest_v1_sha256": manifest_sha,
        **{Path(name).name.replace(".json", "_sha256"): digest for name, digest in artifact_sha256.items()},
    }
    state = copy.deepcopy(load_json(STATE_IN))
    state.setdefault("artifact_lineage", {}).update(lineage)
    state.update({
        "schema_version": 28,
        "state_id": "phase7.3.3-d-support-stage-state-v28",
        "status": outcome["status"],
        "next_authorized_stage": next_stage,
        "multi_claim_successor_candidate_prescreen_completed": True,
        "multi_claim_successor_candidate_prescreen_status": report["status"],
        "multi_claim_successor_prescreen_pass_count": report["prescreen_pass_count"],
        "multi_claim_successor_prescreen_fail_count": report["prescreen_fail_count"],
        "multi_claim_successor_prescreen_excluded_count": 0,
        "multi_claim_successor_boundary_gold_created": False,
        "multi_claim_successor_support_gold_created": False,
        "multi_claim_successor_provider_called": False,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    })
    ready = copy.deepcopy(load_json(READY_IN))
    ready.setdefault("artifact_lineage", {}).update(lineage)
    ready.update({
        "schema_version": 39,
        "readiness_id": "phase7.3.3-d1-reference-construction-readiness-v39",
        "status": outcome["status"],
        "next_authorized_stage": next_stage,
        "successor_candidate_prescreen_completed": True,
        "successor_candidate_prescreen_status": report["status"],
        "successor_prescreen_pass_count": report["prescreen_pass_count"],
        "successor_prescreen_fail_count": report["prescreen_fail_count"],
        "successor_prescreen_excluded_count": 0,
        "successor_reference_status": "not_constructed",
        "provider_called": False,
        "confirmatory_opening_authorized": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    })
    return {
        **documents,
        MANIFEST: manifest,
        OUTCOME: outcome,
        STATE_OUT: state,
        READY_OUT: ready,
    }


def freeze() -> dict[str, Any]:
    pre = preflight()
    if pre["status"] != "PASS":
        raise ValueError("preflight_failed_refusing_to_freeze")
    outputs = build_outputs()
    hashes = {relative(path): write_once(path, value) for path, value in outputs.items()}
    outcome = load_json(OUTCOME)
    fixtures = load_json(FIXTURES)
    report = load_json(REPORT)
    receipt = {
        "schema_version": 1,
        "receipt_id": "phase7.3.3-d-multi-claim-successor-candidate-prescreen-receipt-v1",
        "status": "PASS" if outcome["next_authorized_stage"] == NEXT_STAGE else "FAIL",
        "artifact_sha256": hashes,
        "selected_count": report["selected_count"],
        "prescreen_pass_count": report["prescreen_pass_count"],
        "prescreen_fail_count": report["prescreen_fail_count"],
        "excluded_after_prescreen_count": 0,
        "fixtures_passed": fixtures["passed"],
        "fixtures_total": fixtures["total"],
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": outcome["next_authorized_stage"],
    }
    receipt_sha = write_once(RECEIPT, receipt)
    return {
        "status": receipt["status"],
        "selected": report["selected_count"],
        "prescreen_passed": report["prescreen_pass_count"],
        "fixtures": f"{fixtures['passed']}/{fixtures['total']}",
        "manifest_sha256": file_sha256(MANIFEST),
        "receipt_sha256": receipt_sha,
        "state_sha256": file_sha256(STATE_OUT),
        "readiness_sha256": file_sha256(READY_OUT),
        "next_authorized_stage": outcome["next_authorized_stage"],
        "provider_called": False,
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def verify() -> dict[str, Any]:
    expected = build_outputs()
    checks = {relative(path): path.exists() and path.read_bytes() == json_body(value) for path, value in expected.items()}
    if RECEIPT.exists():
        receipt = load_json(RECEIPT)
        for name, digest in receipt.get("artifact_sha256", {}).items():
            path = ROOT / name
            checks[name + "#receipt_hash"] = path.exists() and file_sha256(path) == digest
        checks[relative(RECEIPT) + "#status"] = receipt.get("status") == "PASS"
    else:
        checks[relative(RECEIPT)] = False
    state = load_json(STATE_OUT) if STATE_OUT.exists() else {}
    report = load_json(REPORT) if REPORT.exists() else {}
    checks.update({
        "prescreen_report_pass": report.get("status") == "PASS",
        "all_40_retained": report.get("selected_count") == 40 and report.get("excluded_after_prescreen_count") == 0,
        "no_gold_emitted": report.get("boundary_claim_count") is None and report.get("support_label_distribution") is None,
        "next_gate": state.get("next_authorized_stage") == NEXT_STAGE,
        "provider_not_called": state.get("multi_claim_successor_provider_called") is False,
        "confirmatory_closed": state.get("confirmatory_dataset_opened") is False,
        "runtime_unauthorized": state.get("runtime_integration_authorized") is False,
    })
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "selected_count": report.get("selected_count"),
        "prescreen_pass_count": report.get("prescreen_pass_count"),
        "next_authorized_stage": state.get("next_authorized_stage"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--run-contract-fixtures", action="store_true")
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
    elif args.run_contract_fixtures:
        items = contract_fixtures()
        result = {
            "status": "PASS" if all(item["status"] == "PASS" for item in items) else "FAIL",
            "passed": sum(item["status"] == "PASS" for item in items),
            "total": len(items),
            "fixtures": items,
        }
    elif args.freeze:
        result = freeze()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())