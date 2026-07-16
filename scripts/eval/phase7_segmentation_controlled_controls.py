#!/usr/bin/env python3
"""Build the provider-visible, segmentation-controlled Phase 7.3.3-C controls."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_atomic_claim_controls.json"
SUPPLEMENT = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_a_partial_atomic_claim_supplement_v1.json"
OUTPUT = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_3_c_segmentation_controlled_claim_controls_v1.json"
CLAIM_INPUT_FIELDS = (
    "claim_id", "source_span", "claim_text", "claim_type", "centrality", "material", "claim_origin",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp = Path(handle.name)
    temp.replace(path)


def packet(case: dict[str, Any], lane: str) -> dict[str, Any]:
    return {
        "case_id": case["control_id"],
        "evaluation_lane": lane,
        "evidence": case["evidence"],
        "candidate_text": case["candidate_text"],
        "atomic_claims": [
            {field: claim[field] for field in CLAIM_INPUT_FIELDS}
            for claim in case["claims"]
        ],
    }


def build() -> dict[str, Any]:
    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    supplement = json.loads(SUPPLEMENT.read_text(encoding="utf-8"))
    packets = [packet(case, "original_balanced_candidate_controls") for case in original["control_cases"]]
    packets += [packet(case, "partial_atomic_claim_diagnostics_supplement") for case in supplement["control_cases"]]
    if len(packets) != 20 or len({row["case_id"] for row in packets}) != 20:
        raise ValueError("expected_20_unique_packets")
    forbidden = {"expected_support_label", "expected_candidate_label"}
    serialized = json.dumps(packets, ensure_ascii=False)
    if any(field in serialized for field in forbidden):
        raise ValueError("gold_label_leakage")
    return {
        "schema_version": 1,
        "dataset_id": "phase7.3.3-c-segmentation-controlled-claim-controls-v1",
        "phase": "Phase 7.3.3-C Segmentation-Controlled Atomic Claim Classification",
        "purpose": "Provider-visible control packets with protocol-owned exact Claim boundaries and no gold support labels.",
        "source_artifact_sha256": {
            "original_balanced_controls": sha256_file(ORIGINAL),
            "partial_claim_supplement": sha256_file(SUPPLEMENT),
        },
        "packet_count": 20,
        "original_candidate_gate_packet_count": 16,
        "diagnostics_only_supplement_packet_count": 4,
        "provider_packets": packets,
        "guards": {
            "expected_claim_labels_included": False,
            "expected_candidate_labels_included": False,
            "gold_evidence_attributions_included": False,
            "claim_boundaries_provider_mutable": False,
            "design_cases_included": False,
            "held_out_included": False,
        },
    }


def main() -> int:
    expected = build()
    if OUTPUT.exists():
        actual = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError("frozen_provider_packet_dataset_changed")
        print(f"segmentation-controlled controls verified: {sha256_file(OUTPUT)}")
        return 0
    atomic_write(OUTPUT, expected)
    print(f"segmentation-controlled controls frozen: {sha256_file(OUTPUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
