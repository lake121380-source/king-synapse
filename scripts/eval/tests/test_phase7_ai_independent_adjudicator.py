#!/usr/bin/env python3
"""Local invariant tests for the Phase 7.3.1 AI adjudication adapter."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "phase7_ai_independent_adjudicator.py"
SPEC = importlib.util.spec_from_file_location("phase7_ai_adjudicator", RUNNER)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Phase7AiAdjudicatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reviewer_a = load(MODULE.REVIEWER_A)
        cls.reviewer_b = load(MODULE.REVIEWER_B)
        cls.agreement = load(MODULE.AGREEMENT)
        cls.groups = MODULE.build_groups(cls.reviewer_a, cls.reviewer_b, cls.agreement)
        cls.groups_by_case = {}
        for group in cls.groups:
            cls.groups_by_case.setdefault(group["case_id"], []).append(group)
        cls.identity = {
            "model_requested": "test-model",
            "prompt_sha256": MODULE.sha256(MODULE.PROMPT),
            "blind_packet_sha256": MODULE.sha256(MODULE.PACKET),
            "reviewer_a_submission_sha256": MODULE.sha256(MODULE.REVIEWER_A),
            "reviewer_b_submission_sha256": MODULE.sha256(MODULE.REVIEWER_B),
            "agreement_report_sha256": MODULE.sha256(MODULE.AGREEMENT),
            "adapter_sha256": MODULE.sha256(RUNNER),
        }

    @staticmethod
    def decision(group_id: str) -> dict:
        return {
            "group_id": group_id,
            "final_support_label": "partially_supported",
            "final_claim_origin": "inferred",
            "adjudication_rationale": "The evidence supports the direction but not stronger wording.",
        }

    def test_frozen_group_shape(self) -> None:
        self.assertEqual(len(self.groups), 77)
        self.assertEqual(len({group["group_id"] for group in self.groups}), 77)
        self.assertEqual(len(self.groups_by_case), 10)
        self.assertEqual(
            sum(bool(g["reviewer_a_claims"]) and bool(g["reviewer_b_claims"]) for g in self.groups),
            74,
        )
        self.assertEqual(
            sum(not g["reviewer_a_claims"] and bool(g["reviewer_b_claims"]) for g in self.groups),
            3,
        )

    def test_valid_partial_checkpoint_round_trip(self) -> None:
        case_id = sorted(self.groups_by_case)[0]
        ids = {group["group_id"] for group in self.groups_by_case[case_id]}
        decisions = {group_id: self.decision(group_id) for group_id in ids}
        case_results = [{
            "case_id": case_id,
            "success": True,
            "attempts": 1,
            "decision_count": len(ids),
        }]
        checkpoint = {
            "identity": self.identity,
            "resolved_model": "test-model-v1",
            "case_results": case_results,
            "decisions": decisions,
        }
        actual = MODULE.validate_checkpoint(checkpoint, self.identity, self.groups_by_case)
        self.assertEqual(actual, (decisions, case_results, "test-model-v1"))

    def test_checkpoint_rejects_decision_without_completed_case(self) -> None:
        group_id = self.groups[0]["group_id"]
        checkpoint = {
            "identity": self.identity,
            "resolved_model": "test-model-v1",
            "case_results": [],
            "decisions": {group_id: self.decision(group_id)},
        }
        with self.assertRaisesRegex(ValueError, "checkpoint_decision_set_mismatch"):
            MODULE.validate_checkpoint(checkpoint, self.identity, self.groups_by_case)

    def test_checkpoint_rejects_duplicate_completed_case(self) -> None:
        case_id = sorted(self.groups_by_case)[0]
        ids = {group["group_id"] for group in self.groups_by_case[case_id]}
        result = {
            "case_id": case_id,
            "success": True,
            "attempts": 1,
            "decision_count": len(ids),
        }
        checkpoint = {
            "identity": self.identity,
            "resolved_model": "test-model-v1",
            "case_results": [result, result],
            "decisions": {group_id: self.decision(group_id) for group_id in ids},
        }
        with self.assertRaisesRegex(ValueError, "checkpoint_case_result_invalid"):
            MODULE.validate_checkpoint(checkpoint, self.identity, self.groups_by_case)

    def test_checkpoint_rejects_upstream_or_adapter_change(self) -> None:
        bad_identity = dict(self.identity)
        bad_identity["agreement_report_sha256"] = "0" * 64
        checkpoint = {
            "identity": bad_identity,
            "resolved_model": None,
            "case_results": [],
            "decisions": {},
        }
        with self.assertRaisesRegex(ValueError, "checkpoint_identity_mismatch"):
            MODULE.validate_checkpoint(checkpoint, self.identity, self.groups_by_case)

    def test_atomic_write_json_replaces_complete_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            path.write_text("stale", encoding="utf-8")
            MODULE.atomic_write_json(path, {"complete": True, "count": 77})
            self.assertEqual(load(path), {"complete": True, "count": 77})
            self.assertEqual(list(path.parent.glob(path.name + ".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
