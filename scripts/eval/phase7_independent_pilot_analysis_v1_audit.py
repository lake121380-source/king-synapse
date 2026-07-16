#!/usr/bin/env python3
"""Retrospectively audit and freeze the Analysis v1 implementation defect."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "crates/eval/reports"
C = ROOT / "crates/eval/config"
D = ROOT / "crates/eval/datasets/pattern_extraction"
TARGET = ROOT / "scripts/eval/phase7_independent_pilot_analysis_v1.py"
PROTOCOL = C / "phase7_3_3_d_independent_pilot_analysis_protocol_v1.json"
FREEZE = R / "phase7_3_3_d_independent_pilot_analysis_freeze_manifest_v1.json"
MANIFEST = R / "phase7_3_3_d_independent_pilot_analysis_execution_manifest_v1.json"
CASES = D / "phase7_3_3_d_independent_pilot_paired_analysis_cases_v1.json"
REPORT = R / "phase7_3_3_d_independent_pilot_analysis_report_v1.json"
RECEIPT = R / "phase7_3_3_d_independent_pilot_analysis_freeze_receipt_v1.json"
POWER_REPORT = R / "phase7_3_3_d_independent_pilot_power_gate_report_v1.json"
POWER_SAMPLE = R / "phase7_3_3_d_independent_pilot_sample_size_freeze_v1.json"
NEGATIVE = R / "phase7_3_3_d_independent_pilot_analysis_negative_result_v1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, value) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable_artifact_conflict:{path.relative_to(ROOT)}")
        return hashlib.sha256(data).hexdigest()
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)
    return hashlib.sha256(data).hexdigest()


def evidence():
    tree = ast.parse(TARGET.read_text(encoding="utf-8-sig"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    preflight = functions["preflight"]
    prepare = functions["prepare"]
    reference_load_lines = []
    for node in ast.walk(preflight):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "load"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "REFERENCE"
        ):
            reference_load_lines.append(node.lineno)
    prepare_calls_preflight = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "preflight"
        for node in ast.walk(prepare)
    )
    return {
        "preflight_load_reference_ast_detected": bool(reference_load_lines),
        "reference_load_source_lines": reference_load_lines,
        "prepare_calls_preflight_before_freeze_creation": prepare_calls_preflight,
    }


def build():
    required = [TARGET, PROTOCOL, FREEZE, MANIFEST, CASES, REPORT, RECEIPT, POWER_REPORT, POWER_SAMPLE]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)
    proof = evidence()
    if not all(
        [
            proof["preflight_load_reference_ast_detected"],
            proof["prepare_calls_preflight_before_freeze_creation"],
        ]
    ):
        raise ValueError("expected_analysis_v1_defect_not_detected")
    negative = {
        "schema_version": 1,
        "negative_result_id": "phase7.3.3-d-independent-pilot-analysis-negative-result-v1",
        "status": "authoritative_implementation_negative_result",
        "failure_level": "analysis_freeze_order_and_lineage_contract",
        "failure_reason": "reference_content_loaded_during_pre_manifest_preflight",
        "evidence": proof,
        "artifact_sha256": {
            "audit_adapter": sha(Path(__file__)),
            "analysis_v1_adapter": sha(TARGET),
            "analysis_v1_protocol": sha(PROTOCOL),
            "analysis_v1_freeze_manifest": sha(FREEZE),
            "analysis_v1_execution_manifest": sha(MANIFEST),
            "analysis_v1_paired_cases": sha(CASES),
            "analysis_v1_report": sha(REPORT),
            "analysis_v1_receipt": sha(RECEIPT),
            "power_gate_v1_report": sha(POWER_REPORT),
            "power_gate_v1_sample_size_freeze": sha(POWER_SAMPLE),
        },
        "analysis_v1_scientific_conclusion_authorized": False,
        "analysis_v1_outputs_retained_as_immutable_execution_evidence": True,
        "analysis_v1_outputs_eligible_for_final_pilot_conclusion": False,
        "power_gate_v1_inherited_lineage_eligible_for_final_conclusion": False,
        "dual_arm_v4_outputs_invalidated": False,
        "independent_reference_invalidated": False,
        "same_version_retry_allowed": False,
        "successor_analysis_v2_authorized": True,
        "required_successor_change": "Before the scoring manifest is frozen, verify Reference only by file existence and SHA256 equality to the sealed hash; do not parse Reference content until scoring begins after manifest freeze.",
        "confirmatory_dataset_opened": False,
        "runtime_integration_authorized": False,
    }
    negative_hash = write_once(NEGATIVE, negative)
    print(
        json.dumps(
            {
                "status": negative["status"],
                "negative_result_sha256": negative_hash,
                "analysis_v1_scientific_conclusion_authorized": False,
                "power_gate_v1_eligible_for_final_conclusion": False,
                "successor_analysis_v2_authorized": True,
            },
            indent=2,
        )
    )


def verify():
    if not NEGATIVE.exists():
        raise FileNotFoundError(NEGATIVE)
    result = json.loads(NEGATIVE.read_text(encoding="utf-8-sig"))
    proof = evidence()
    checks = {
        "negative_authoritative": result["status"] == "authoritative_implementation_negative_result",
        "defect_replays": proof == result["evidence"] and proof["preflight_load_reference_ast_detected"],
        "target_adapter_hash": result["artifact_sha256"]["analysis_v1_adapter"] == sha(TARGET),
        "audit_adapter_hash": result["artifact_sha256"]["audit_adapter"] == sha(Path(__file__)),
        "v1_excluded": result["analysis_v1_outputs_eligible_for_final_pilot_conclusion"] is False,
        "power_v1_excluded": result["power_gate_v1_inherited_lineage_eligible_for_final_conclusion"] is False,
        "upstream_preserved": result["dual_arm_v4_outputs_invalidated"] is False
        and result["independent_reference_invalidated"] is False,
        "no_retry": result["same_version_retry_allowed"] is False,
        "successor_authorized": result["successor_analysis_v2_authorized"] is True,
        "confirmatory_closed": result["confirmatory_dataset_opened"] is False,
        "runtime_unauthorized": result["runtime_integration_authorized"] is False,
    }
    ok = all(checks.values())
    print(json.dumps({"status": "PASS" if ok else "FAIL", "checks": checks, "negative_result_sha256": sha(NEGATIVE)}, indent=2))
    if not ok:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze-negative", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.freeze_negative:
        build()
    else:
        verify()


if __name__ == "__main__":
    main()
