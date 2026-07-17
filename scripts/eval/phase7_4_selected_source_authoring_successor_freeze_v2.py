#!/usr/bin/env python3
"""Classify the v1 authoring preflight failure and freeze bounded v2 authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
DATASETS = ROOT / "crates/eval/datasets"
PATTERN = DATASETS / "pattern_extraction"
PHASE_DATA = DATASETS / "phase7_4"
REPORTS = ROOT / "crates/eval/reports"
DOCS = ROOT / "docs"

DOC = DOCS / "eval/PHASE7_4_2_SELECTED_SOURCE_AUTHORING_SUCCESSOR_V2.md"
POLICY = CONFIG / "phase7_4_selected_source_authoring_successor_policy_v2.json"
V1_ADAPTER = ROOT / "scripts/eval/phase7_4_selected_source_authoring_v1.py"
ATTEMPTS = REPORTS / "phase7_4_selected_source_authoring_preflight_attempts_v1.jsonl"
CONTRACT = CONFIG / "phase7_4_selected_source_authoring_contract_v1.json"
PLAN = PHASE_DATA / "phase7_4_selected_source_authoring_plan_v1.json"
STATE_V6 = PATTERN / "phase7_4_stage_state_v6.json"
READINESS_V6 = REPORTS / "phase7_4_readiness_v6.json"
CONTRACT_RECEIPT = REPORTS / "phase7_4_selected_source_authoring_contract_receipt_v1.json"

CLASSIFICATION = REPORTS / "phase7_4_selected_source_authoring_v1_failure_classification.json"
MANIFEST = REPORTS / "phase7_4_selected_source_authoring_successor_manifest_v2.json"
OUTCOME = REPORTS / "phase7_4_selected_source_authoring_successor_outcome_v2.json"
AUDIT = REPORTS / "phase7_4_selected_source_authoring_successor_audit_v2.jsonl"
STATE_V7 = PATTERN / "phase7_4_stage_state_v7.json"
READINESS_V7 = REPORTS / "phase7_4_readiness_v7.json"
RECEIPT = REPORTS / "phase7_4_selected_source_authoring_successor_receipt_v2.json"

V1_AUTHORITATIVE_OUTPUTS = [
    PHASE_DATA / "phase7_4_selected_source_cases_v1.json",
    REPORTS / "phase7_4_selected_source_authoring_fixtures_v1.json",
    REPORTS / "phase7_4_selected_source_authoring_manifest_v1.json",
    REPORTS / "phase7_4_selected_source_authoring_outcome_v1.json",
    REPORTS / "phase7_4_selected_source_authoring_audit_v1.jsonl",
    REPORTS / "phase7_4_selected_source_authoring_receipt_v1.json",
]

ENTRY_HEAD = "07d575f09964153432461630be48f44c6c9568af"
ENTRY = "phase7_4_selected_source_authoring_contract_frozen_source_authoring_authorized"
V1_AUTHORIZED = "author_phase7_4_selected_source_cases_v1"
FREEZE_GATE = "classify_phase7_4_selected_source_authoring_v1_preflight_failure_and_freeze_v2_successor"
NEXT = "author_phase7_4_selected_source_cases_v2"

EXPECTED = {
    DOC: "eda7c71fad0afeeb1dae7952d28f7cad77e691147de5ebc82b35c2c7b3fa366a",
    POLICY: "5057e18dee0d4a4acb745e2cfbd3269df387bbf7d26acbb79d98fd5a7e2bd6e6",
    V1_ADAPTER: "2afdfc696775f23d3b8e024e7d936010086837781fd09d1e6a6b907f1e68458e",
    ATTEMPTS: "9e9a8d317d7b204598849d677c15201aa52efdbd4a2567db146fa5dc3e240aad",
    CONTRACT: "d0b7b46c07f946a27ce411d5fc658586563ca4e4001ab4fd607ccb61fa68cc24",
    PLAN: "88b0c0f338a6e5037a81eacc37470a67c4953fced73efb41cc5bc8964474ccdd",
    STATE_V6: "90f5ccccd1192386eda0998010fd0b8f5eb5c669200f1d6c24cf5f6cda7e9825",
    READINESS_V6: "ad39b8a759e1828b75382f9c2c7504d17fcde9758c6719f1914f550e73a85051",
    CONTRACT_RECEIPT: "7b29c28b16f81b873658d1655d22a39f893fdca40fa4bdddbf17f0ce0bf2869b",
}

OUTPUTS = [
    CLASSIFICATION,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V7,
    READINESS_V7,
    RECEIPT,
]


def hb(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return hb(path.read_bytes())


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
    body = (canonical(event) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("append_only_audit_mismatch:" + rel(path))
        return sha(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(body)
    return hb(body)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git_head() -> str:
    result = run(["git", "rev-parse", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError("git_head_unavailable")
    return result.stdout.strip()


def entry_head_is_ancestor() -> bool:
    return (
        run(["git", "merge-base", "--is-ancestor", ENTRY_HEAD, git_head()]).returncode
        == 0
    )


def attempt_event() -> dict[str, Any]:
    lines = ATTEMPTS.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise RuntimeError("v1_attempt_log_event_count_mismatch")
    return json.loads(lines[0])


def classification_document() -> dict[str, Any]:
    attempt = attempt_event()
    return {
        "schema_version": 1,
        "classification_id": "phase7.4-selected-source-authoring-v1-failure-classification",
        "status": "classified_pre_freeze_draft_failure_no_authoritative_dataset",
        "entry_head": ENTRY_HEAD,
        "v1_adapter_sha256": sha(V1_ADAPTER),
        "v1_attempt_log_sha256": sha(ATTEMPTS),
        "classified_failure": attempt["classified_failure"],
        "failed_checks": attempt["failed_checks"],
        "draft_authored_text_count": attempt["draft_authored_text_count"],
        "exact_normalized_text_duplicate_count": attempt[
            "exact_normalized_text_duplicate_count"
        ],
        "high_similarity_pair_count": attempt["high_similarity_pair_count"],
        "authoritative_dataset_written": False,
        "authoritative_outputs_written": False,
        "reference_or_gold_written": False,
        "atomic_or_arm_output_written": False,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "same_version_retry_allowed": False,
        "threshold_relaxation_allowed": False,
        "case_reselection_allowed": False,
        "bounded_v2_successor_authorized": True,
        "next_authorized_stage": NEXT,
    }


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "manifest_id": "phase7.4-selected-source-authoring-successor-manifest-v2",
        "status": "frozen_v1_failure_classification_and_bounded_v2_policy",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {rel(CLASSIFICATION): sha(CLASSIFICATION)},
        "v1_authoritative_outputs_absent": all(
            not path.exists() for path in V1_AUTHORITATIVE_OUTPUTS
        ),
        "similarity_threshold_unchanged": True,
        "selection_and_slots_unchanged": True,
        "source_content_authored": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(classification_hash: str, manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "outcome_id": "phase7.4-selected-source-authoring-successor-outcome-v2",
        "status": "PASS_v1_failure_retained_bounded_v2_authoring_authorized",
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "v1_attempt_log_sha256": sha(ATTEMPTS),
        "v1_authoritative_outputs_written": False,
        "v2_authoring_authorized": True,
        "source_content_authored": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(
    classification_hash: str, manifest_hash: str, outcome_hash: str
) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-selected-source-authoring-successor-v2-frozen",
        "event_type": "immutable_pre_freeze_failure_classification_and_bounded_successor",
        "entry_head": ENTRY_HEAD,
        "v1_adapter_sha256": sha(V1_ADAPTER),
        "v1_attempt_log_sha256": sha(ATTEMPTS),
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "classified_failure": "duplicate_or_similarity_failure",
        "v1_authoritative_outputs_written": False,
        "similarity_threshold_relaxed": False,
        "case_reselection_allowed": False,
        "source_content_authored": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(
    classification_hash: str,
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v6_sha256": sha(STATE_V6),
        "phase7_4_readiness_v6_sha256": sha(READINESS_V6),
        "phase7_4_selected_source_authoring_contract_receipt_v1_sha256": sha(
            CONTRACT_RECEIPT
        ),
        "phase7_4_selected_source_authoring_v1_adapter_sha256": sha(V1_ADAPTER),
        "phase7_4_selected_source_authoring_v1_attempt_log_sha256": sha(ATTEMPTS),
        "phase7_4_selected_source_authoring_successor_policy_v2_sha256": sha(POLICY),
        "phase7_4_selected_source_authoring_v1_failure_classification_sha256": classification_hash,
        "phase7_4_selected_source_authoring_successor_manifest_v2_sha256": manifest_hash,
        "phase7_4_selected_source_authoring_successor_outcome_v2_sha256": outcome_hash,
        "phase7_4_selected_source_authoring_successor_audit_v2_sha256": audit_hash,
    }


def state_document(
    classification_hash: str,
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 7,
        "state_id": "phase7.4-stage-state-v7",
        "status": "phase7_4_source_authoring_v1_preflight_failed_bounded_v2_authorized",
        "artifact_lineage": lineage(
            classification_hash, manifest_hash, outcome_hash, audit_hash
        ),
        "selected_source_authoring_contract_frozen": True,
        "selected_source_blank_authoring_plan_frozen": True,
        "v1_preflight_attempt_retained": True,
        "v1_failure_classified": True,
        "v1_classified_failure": "duplicate_or_similarity_failure",
        "v1_authoritative_outputs_written": False,
        "v1_same_version_retry_allowed": False,
        "v2_successor_policy_frozen": True,
        "v2_selected_source_content_authoring_authorized": True,
        "selected_source_content_authored": False,
        "selected_source_content_frozen": False,
        "atomic_segmentation_authorized": False,
        "reference_review_started": False,
        "gold_frozen": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "arm_execution_started": False,
        "effect_scoring_started": False,
        "phase7_4_effect_provider_called": False,
        "phase7_3_3_d_effect_data_loaded": False,
        "memory_kind_modification_authorized": False,
        "memory_schema_modification_authorized": False,
        "recall_engine_modification_authorized": False,
        "production_memory_write_authorized": False,
        "runtime_integration_authorized": False,
        "productization_authorized": False,
        "release_authorized": False,
        "next_authorized_stage": NEXT,
    }


def readiness_document(
    classification_hash: str,
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
    state_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 7,
        "readiness_id": "phase7.4-readiness-v7",
        "status": "PASS_v1_failure_classified_bounded_v2_authoring_ready",
        "artifact_lineage": {
            **lineage(
                classification_hash, manifest_hash, outcome_hash, audit_hash
            ),
            "phase7_4_stage_state_v7_sha256": state_hash,
        },
        "checks": {
            "v1_attempt_log_retained": True,
            "v1_authoritative_outputs_absent": True,
            "failure_classified": True,
            "same_version_retry_closed": True,
            "selection_and_slots_unchanged": True,
            "similarity_threshold_unchanged": True,
            "effect_dataset_closed_to_arms": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "v2_selected_source_content_authoring_authorized": True,
        "atomic_segmentation_authorized": False,
        "reference_review_authorized": False,
        "arm_execution_authorized": False,
        "effect_scoring_authorized": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def receipt_document(
    classification_hash: str,
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
    state_hash: str,
    readiness_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "receipt_id": "phase7.4-selected-source-authoring-successor-receipt-v2",
        "status": "PASS",
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v7_sha256": state_hash,
        "readiness_v7_sha256": readiness_hash,
        "v1_adapter_sha256": sha(V1_ADAPTER),
        "v1_attempt_log_sha256": sha(ATTEMPTS),
        "successor_policy_v2_sha256": sha(POLICY),
        "v1_authoritative_outputs_written": False,
        "v2_authoring_authorized": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def preflight() -> dict[str, Any]:
    checks = {
        "input_hash:" + rel(path): path.exists() and sha(path) == digest
        for path, digest in EXPECTED.items()
    }
    if all(checks.values()):
        state = load(STATE_V6)
        policy = load(POLICY)
        attempt = attempt_event()
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state_exact": state["status"] == ENTRY,
                "v1_was_authorized": state["next_authorized_stage"] == V1_AUTHORIZED,
                "policy_gate_exact": policy["entry_gate"] == FREEZE_GATE,
                "policy_next_exact": policy["next_authorized_stage_after_pass"] == NEXT,
                "attempt_class_exact": attempt["classified_failure"]
                == "duplicate_or_similarity_failure",
                "attempt_counts_exact": attempt[
                    "exact_normalized_text_duplicate_count"
                ]
                == 452
                and attempt["high_similarity_pair_count"] == 2792,
                "attempt_no_authoritative_output": attempt[
                    "authoritative_outputs_written"
                ]
                is False,
                "v1_authoritative_outputs_absent": all(
                    not path.exists() for path in V1_AUTHORITATIVE_OUTPUTS
                ),
                "threshold_not_relaxed": policy["unchanged_frozen_design"][
                    "exact_normalized_text_duplicate_count_max"
                ]
                == 0
                and policy["unchanged_frozen_design"][
                    "normalized_five_gram_jaccard_manual_review_threshold"
                ]
                == 0.85
                and policy["unchanged_frozen_design"][
                    "unresolved_high_similarity_pair_count_max"
                ]
                == 0,
                "selection_unchanged": policy["unchanged_frozen_design"][
                    "selected_case_ids_and_order_unchanged"
                ]
                is True,
                "effect_dataset_closed": state[
                    "selected_effect_dataset_opened_for_arm_execution"
                ]
                is False,
                "provider_not_called": state["phase7_4_effect_provider_called"]
                is False,
                "runtime_off": state["runtime_integration_authorized"] is False,
            }
        )
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "checks": len(checks), "failed": failed}


def freeze() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    classification_hash = once(CLASSIFICATION, classification_document())
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(
        OUTCOME, outcome_document(classification_hash, manifest_hash)
    )
    audit_hash = append_single_event(
        AUDIT, audit_event(classification_hash, manifest_hash, outcome_hash)
    )
    state_hash = once(
        STATE_V7,
        state_document(
            classification_hash, manifest_hash, outcome_hash, audit_hash
        ),
    )
    readiness_hash = once(
        READINESS_V7,
        readiness_document(
            classification_hash,
            manifest_hash,
            outcome_hash,
            audit_hash,
            state_hash,
        ),
    )
    receipt_hash = once(
        RECEIPT,
        receipt_document(
            classification_hash,
            manifest_hash,
            outcome_hash,
            audit_hash,
            state_hash,
            readiness_hash,
        ),
    )
    return {
        "status": "PASS",
        "classification_sha256": classification_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v7_sha256": state_hash,
        "readiness_v7_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "classified_failure": "duplicate_or_similarity_failure",
        "v1_authoritative_outputs_written": False,
        "v2_authoring_authorized": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in OUTPUTS}
    if all(checks.values()):
        classification_hash = sha(CLASSIFICATION)
        manifest_hash = sha(MANIFEST)
        outcome_hash = sha(OUTCOME)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V7)
        readiness_hash = sha(READINESS_V7)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(
                    path.exists() and sha(path) == digest
                    for path, digest in EXPECTED.items()
                ),
                "v1_outputs_absent": all(
                    not path.exists() for path in V1_AUTHORITATIVE_OUTPUTS
                ),
                "classification_replay": load(CLASSIFICATION)
                == classification_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME)
                == outcome_document(classification_hash, manifest_hash),
                "audit_replay": AUDIT.read_bytes()
                == (
                    canonical(
                        audit_event(
                            classification_hash, manifest_hash, outcome_hash
                        )
                    )
                    + "\n"
                ).encode("utf-8"),
                "state_v7_replay": load(STATE_V7)
                == state_document(
                    classification_hash,
                    manifest_hash,
                    outcome_hash,
                    audit_hash,
                ),
                "readiness_v7_replay": load(READINESS_V7)
                == readiness_document(
                    classification_hash,
                    manifest_hash,
                    outcome_hash,
                    audit_hash,
                    state_hash,
                ),
                "receipt_replay": load(RECEIPT)
                == receipt_document(
                    classification_hash,
                    manifest_hash,
                    outcome_hash,
                    audit_hash,
                    state_hash,
                    readiness_hash,
                ),
                "next_gate_consistent": load(STATE_V7)["next_authorized_stage"]
                == load(READINESS_V7)["next_authorized_stage"]
                == load(RECEIPT)["next_authorized_stage"]
                == NEXT,
                "source_content_not_authored": load(STATE_V7)[
                    "selected_source_content_authored"
                ]
                is False,
                "effect_dataset_closed": load(STATE_V7)[
                    "selected_effect_dataset_opened_for_arm_execution"
                ]
                is False,
                "runtime_off": load(STATE_V7)["runtime_integration_authorized"]
                is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "v1_authoritative_outputs_written": False,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V7).get(
            "selected_effect_dataset_opened_for_arm_execution"
        )
        if STATE_V7.exists()
        else None,
        "runtime_integration_authorized": load(STATE_V7).get(
            "runtime_integration_authorized"
        )
        if STATE_V7.exists()
        else None,
        "next_authorized_stage": load(STATE_V7).get("next_authorized_stage")
        if STATE_V7.exists()
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
    elif args.freeze:
        result = freeze()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
