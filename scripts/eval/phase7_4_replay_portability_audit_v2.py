#!/usr/bin/env python3
"""Freeze Phase 7.4.1 replay portability with bounded Git EOL handling."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
DOCS = ROOT / "docs"

V1_ADAPTER = ROOT / "scripts/eval/phase7_4_replay_portability_audit_v1.py"
V1_SPEC = importlib.util.spec_from_file_location("phase7_4_portability_v1", V1_ADAPTER)
if V1_SPEC is None or V1_SPEC.loader is None:
    raise RuntimeError("v1_portability_adapter_import_failed")
V1 = importlib.util.module_from_spec(V1_SPEC)
V1_SPEC.loader.exec_module(V1)

PLAN = DOCS / "KING_SYNAPSE_LONG_TERM_COMPLETION_PLAN.md"
CONTRACT = CONFIG / "project_completion_contract_v1.json"
POLICY_V1 = CONFIG / "phase7_4_replay_portability_policy_v1.json"
POLICY_V2 = CONFIG / "phase7_4_replay_portability_policy_v2.json"
ATTEMPTS = REPORTS / "phase7_4_replay_portability_preflight_attempts_v1.jsonl"

PROTOCOL_RECEIPT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_receipt_v1.json"
V1_FIXTURES = REPORTS / "phase7_4_atomic_evidence_shadow_implementation_fixtures_v1.json"
V1_MANIFEST = REPORTS / "phase7_4_atomic_evidence_shadow_implementation_manifest_v1.json"
V1_GATE = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_report_v1.json"
V1_AUDIT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_audit_v1.jsonl"
V1_RECEIPT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_receipt_v1.json"
STATE_V2 = PATTERN / "phase7_4_stage_state_v2.json"
READINESS_V2 = REPORTS / "phase7_4_readiness_v2.json"

REPORT = REPORTS / "phase7_4_replay_portability_report_v2.json"
MANIFEST = REPORTS / "phase7_4_replay_portability_manifest_v2.json"
AUDIT = REPORTS / "phase7_4_replay_portability_audit_v2.jsonl"
STATE_V3 = PATTERN / "phase7_4_stage_state_v3.json"
READINESS_V3 = REPORTS / "phase7_4_readiness_v3.json"
RECEIPT = REPORTS / "phase7_4_m0_governance_freeze_receipt_v1.json"

RECORDED_HEAD = "3c99170854743f65bd1d5334aeaea94f748c1809"
CHECKPOINT_HEAD = "d289c3aa019f37a9de19e57de3870ff32ffaca74"
ENTRY = "phase7_4_1_shadow_prototype_gate_passed_offline_retrieval_protocol_authorized"
NEXT = "freeze_phase7_4_offline_retrieval_evaluation_protocol_v1"

EXPECTED_INPUTS = {
    PLAN: "eb20101e78f01726a3d9ebe5ce7f7ec2777c300647cf52aae98936ddeb9602bf",
    CONTRACT: "63831b2886346d047413656155eb95a960e04061eb5f161992439c1081d1f924",
    POLICY_V1: "fa60781834ef98e8985f962f81cab7deb0a2f8e62924585968ca25d583e93a9d",
    V1_ADAPTER: "121675feba5b937c3b8d8bab6e8425521b49765742a30eada08a903c5181dcd4",
    ATTEMPTS: "8eddff7cc391793bdf2144001c33bd35db8c8078cbd4e57fc9ebeed0eba506be",
    POLICY_V2: "09ce6c84636dcb575d682b6f2b27cd74c6e3c73f2443f4eba3471ae645dc8a1b",
}

EXPECTED_V1_ROOTS = {
    PROTOCOL_RECEIPT: "88b564d65e436cbc10eb76f3022686196a3c0ca7ef6c46e7f2891e142727202c",
    V1_FIXTURES: "d712275a7f9c5d062839850393b8d76b50f0d96cbfa12db3350eaf9055743452",
    V1_MANIFEST: "448a7384d6108c1ff7c2b774f907f16a804883c8cceb772af95e47b76b46eb04",
    V1_GATE: "55fc9d0f0f7b2037a27371c49be6afbe117b4123552afa5a3fc5017bb4b8bcf6",
    V1_AUDIT: "f91f38c63bd95c941c87725fdc003cdded7123e54593a875f8cc4307462e88c6",
    STATE_V2: "85d46f0de581fdc4e87e30695614cd760a0c63e09a1bac7320f6aaae86279e58",
    READINESS_V2: "222da9722dfb8d97cb82ea013c28c03522ffede1b17e6dbef1f13fa90d017748",
    V1_RECEIPT: "a7ab56c1fb9f064143cd8a07932bef968d8c1fe66cc014c695efd97b404816c6",
}

V1_OUTPUTS = [V1.REPORT, V1.MANIFEST, V1.AUDIT]
OUTPUTS = [REPORT, MANIFEST, AUDIT, STATE_V3, READINESS_V3, RECEIPT]


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


def run(command: list[str], text: bool = True) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        check=False,
    )


def git_head() -> str:
    result = run(["git", "rev-parse", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError("git_head_unavailable")
    return result.stdout.strip()


def is_ancestor(ancestor: str, descendant: str) -> bool:
    return run(["git", "merge-base", "--is-ancestor", ancestor, descendant]).returncode == 0


def git_blob(commit: str, path: str) -> bytes | None:
    result = run(["git", "show", f"{commit}:{path}"], text=False)
    return result.stdout if result.returncode == 0 else None


def git_blob_sha(commit: str, path: str) -> str | None:
    value = git_blob(commit, path)
    return hb(value) if value is not None else None


def git_changed_paths(older: str, newer: str) -> list[str]:
    result = run(["git", "diff", "--name-only", older, newer])
    if result.returncode != 0:
        return ["<git-diff-unavailable>"]
    return sorted(line.replace("\\", "/") for line in result.stdout.splitlines() if line)


def checkpoint_path_allowed(path: str) -> bool:
    if path == "crates/eval/src/lib.rs":
        return True
    if path.startswith("crates/eval/") and "phase7_4" in path:
        return True
    if path.startswith("scripts/eval/phase7_4"):
        return True
    if path == "docs/PHASE7_4_ATOMIC_EVIDENCE_SUBSTRATE_DESIGN.md":
        return True
    if path == "docs/eval/PHASE7_4_1_ATOMIC_EVIDENCE_SHADOW_PROTOTYPE_PROTOCOL.md":
        return True
    return False


def normalize_git_eol(value: bytes) -> bytes:
    return value.replace(bytes([13, 10]), bytes([10]))


def fixed_input_checks() -> dict[str, bool]:
    checks = {
        "input_hash:" + rel(path): path.exists() and sha(path) == digest
        for path, digest in EXPECTED_INPUTS.items()
    }
    checks.update(
        {
            "v1_root_hash:" + rel(path): path.exists() and sha(path) == digest
            for path, digest in EXPECTED_V1_ROOTS.items()
        }
    )
    checks["v1_authoritative_outputs_absent"] = all(not path.exists() for path in V1_OUTPUTS)
    if all(checks.values()):
        policy = load(POLICY_V2)
        attempt = ATTEMPTS.read_text(encoding="utf-8").splitlines()
        checks.update(
            {
                "policy_successor_identity": policy["supersedes_for_m0_freeze"]
                == "phase7.4.1-replay-portability-policy-v1",
                "policy_recorded_head": policy["recorded_execution_head"] == RECORDED_HEAD,
                "policy_checkpoint_head": policy["phase7_4_1_checkpoint_head"] == CHECKPOINT_HEAD,
                "attempt_log_single_retained_failure": len(attempt) == 1
                and json.loads(attempt[0])["classified_failure"]
                == "checkpoint_context_eol_normalization_mismatch",
                "state_entry": load(STATE_V2)["status"] == ENTRY,
                "state_next_gate": load(STATE_V2)["next_authorized_stage"] == NEXT,
                "effect_dataset_closed": load(STATE_V2)["phase7_4_effect_dataset_opened"]
                is False,
                "provider_not_called": load(STATE_V2)["phase7_4_effect_provider_called"]
                is False,
                "runtime_not_authorized": load(STATE_V2)["runtime_integration_authorized"]
                is False,
            }
        )
    return checks


def replay_report(verifier_head: str) -> dict[str, Any]:
    policy = load(POLICY_V2)
    v1_manifest = load(V1_MANIFEST)
    changed = git_changed_paths(RECORDED_HEAD, CHECKPOINT_HEAD)
    raw_paths = policy["raw_exact_checkpoint_paths"]
    normalized_paths = policy["git_eol_normalized_checkpoint_paths"]
    owned_paths = policy["future_exact_owned_implementation_paths"]
    raw_checks = {
        path: git_blob_sha(CHECKPOINT_HEAD, path)
        == v1_manifest["implementation_artifacts"][path]
        for path in raw_paths
    }
    normalized_checks: dict[str, dict[str, Any]] = {}
    for path in normalized_paths:
        working = (ROOT / path).read_bytes()
        checkpoint_blob = git_blob(CHECKPOINT_HEAD, path)
        diff = git_changed_paths(RECORDED_HEAD, CHECKPOINT_HEAD)
        path_changed = path in diff
        normalized_checks[path] = {
            "recorded_working_sha256_exact": sha(ROOT / path)
            == v1_manifest["implementation_artifacts"][path],
            "normalized_working_sha256": hb(normalize_git_eol(working)),
            "checkpoint_blob_sha256": hb(checkpoint_blob) if checkpoint_blob is not None else None,
            "normalized_working_equals_checkpoint_blob": checkpoint_blob is not None
            and normalize_git_eol(working) == checkpoint_blob,
            "recorded_head_to_checkpoint_path_diff_empty": not path_changed,
            "working_crlf_count": working.count(bytes([13, 10])),
        }
    normalized_pass = all(
        row["recorded_working_sha256_exact"]
        and row["normalized_working_equals_checkpoint_blob"]
        and row["recorded_head_to_checkpoint_path_diff_empty"]
        for row in normalized_checks.values()
    )
    root_checks = {
        rel(path): git_blob_sha(CHECKPOINT_HEAD, rel(path)) == digest
        for path, digest in EXPECTED_V1_ROOTS.items()
    }
    owned_checks = {
        path: (ROOT / path).exists()
        and sha(ROOT / path) == v1_manifest["implementation_artifacts"][path]
        for path in owned_paths
    }
    checks = {
        "recorded_head_is_checkpoint_ancestor": is_ancestor(RECORDED_HEAD, CHECKPOINT_HEAD),
        "checkpoint_is_verifier_head_or_ancestor": is_ancestor(CHECKPOINT_HEAD, verifier_head),
        "checkpoint_changed_paths_version_isolated": bool(changed)
        and all(checkpoint_path_allowed(path) for path in changed),
        "checkpoint_has_no_core_change": all(
            not path.startswith("crates/core/") for path in changed
        ),
        "checkpoint_has_no_phase7_3_3_d_change": all(
            "phase7_3_3_d" not in path for path in changed
        ),
        "checkpoint_contains_v1_policy": git_blob_sha(CHECKPOINT_HEAD, rel(POLICY_V1))
        == sha(POLICY_V1),
        "checkpoint_contains_v1_verifier": git_blob_sha(CHECKPOINT_HEAD, rel(V1_ADAPTER))
        == sha(V1_ADAPTER),
        "checkpoint_raw_implementation_bytes_exact": all(raw_checks.values()),
        "checkpoint_eol_normalized_context_exact": normalized_pass,
        "checkpoint_v1_governance_roots_exact": all(root_checks.values()),
        "future_owned_working_bytes_exact": all(owned_checks.values()),
        "m0_inputs_exact": all(fixed_input_checks().values()),
        "effect_dataset_closed": load(STATE_V2)["phase7_4_effect_dataset_opened"] is False,
        "provider_not_called": load(STATE_V2)["phase7_4_effect_provider_called"] is False,
        "runtime_not_authorized": load(STATE_V2)["runtime_integration_authorized"] is False,
    }
    passed = all(checks.values())
    return {
        "schema_version": 2,
        "report_id": "phase7.4.1-replay-portability-report-v2",
        "status": "PASS_descendant_commit_replay_portable_with_bounded_git_eol_rule"
        if passed
        else "FAIL_replay_portability_not_established",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "checkpoint_changed_paths": changed,
        "raw_exact_checkpoint_checks": raw_checks,
        "git_eol_normalized_checkpoint_checks": normalized_checks,
        "v1_governance_root_checks": root_checks,
        "future_owned_working_checks": owned_checks,
        "retained_failed_attempt_sha256": sha(ATTEMPTS),
        "checks": checks,
        "all_checks_passed": passed,
        "recorded_head_equality_with_future_verifier_required": False,
        "same_version_semantic_retry_allowed": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT if passed else "freeze_replay_portability_negative_result",
    }


def manifest_document(report_hash: str) -> dict[str, Any]:
    policy = load(POLICY_V2)
    return {
        "schema_version": 2,
        "manifest_id": "phase7.4.1-replay-portability-manifest-v2",
        "status": "frozen_descendant_commit_replay_policy_with_bounded_git_eol_rule",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "adapter_sha256": sha(SELF),
        "policy_v1_sha256": sha(POLICY_V1),
        "verifier_v1_sha256": sha(V1_ADAPTER),
        "retained_failed_attempt_sha256": sha(ATTEMPTS),
        "policy_v2_sha256": sha(POLICY_V2),
        "completion_plan_sha256": sha(PLAN),
        "completion_contract_sha256": sha(CONTRACT),
        "replay_portability_report_v2_sha256": report_hash,
        "frozen_phase7_4_1_roots": {
            rel(path): digest for path, digest in EXPECTED_V1_ROOTS.items()
        },
        "checkpoint_implementation_artifacts": load(V1_MANIFEST)["implementation_artifacts"],
        "raw_exact_checkpoint_paths": policy["raw_exact_checkpoint_paths"],
        "git_eol_normalized_checkpoint_paths": policy["git_eol_normalized_checkpoint_paths"],
        "future_owned_exact_paths": policy["future_exact_owned_implementation_paths"],
        "future_evolving_context_paths": policy["future_evolving_context_paths"],
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(report_hash: str, manifest_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4.1-replay-portability-v2-frozen",
        "event_type": "immutable_descendant_commit_replay_policy_successor",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "report_sha256": report_hash,
        "manifest_sha256": manifest_hash,
        "policy_v1_retained": True,
        "failed_attempt_retained_sha256": sha(ATTEMPTS),
        "policy_v2_sha256": sha(POLICY_V2),
        "completion_plan_sha256": sha(PLAN),
        "completion_contract_sha256": sha(CONTRACT),
        "effect_dataset_opened": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(report_hash: str, manifest_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v2_sha256": sha(STATE_V2),
        "phase7_4_readiness_v2_sha256": sha(READINESS_V2),
        "phase7_4_prototype_gate_receipt_v1_sha256": sha(V1_RECEIPT),
        "long_term_completion_plan_sha256": sha(PLAN),
        "project_completion_contract_v1_sha256": sha(CONTRACT),
        "phase7_4_replay_portability_policy_v1_sha256": sha(POLICY_V1),
        "phase7_4_replay_portability_verifier_v1_sha256": sha(V1_ADAPTER),
        "phase7_4_replay_portability_failed_attempts_v1_sha256": sha(ATTEMPTS),
        "phase7_4_replay_portability_policy_v2_sha256": sha(POLICY_V2),
        "phase7_4_replay_portability_report_v2_sha256": report_hash,
        "phase7_4_replay_portability_manifest_v2_sha256": manifest_hash,
        "phase7_4_replay_portability_audit_v2_sha256": audit_hash,
    }


def state_document(report_hash: str, manifest_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "state_id": "phase7.4-stage-state-v3",
        "status": "m0_governance_baseline_frozen_phase7_4_2_protocol_freeze_authorized",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "artifact_lineage": lineage(report_hash, manifest_hash, audit_hash),
        "phase7_4_1_replay_portable_across_descendant_commits": True,
        "bounded_git_eol_normalization_applied_to_checkpoint_context_only": True,
        "v1_failed_attempt_retained": True,
        "long_term_completion_plan_frozen": True,
        "project_completion_contract_frozen": True,
        "phase7_4_effect_dataset_opened": False,
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
    report_hash: str, manifest_hash: str, audit_hash: str, state_hash: str
) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "readiness_id": "phase7.4-readiness-v3",
        "status": "PASS_m0_governance_and_replay_portability_frozen",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "artifact_lineage": {
            **lineage(report_hash, manifest_hash, audit_hash),
            "phase7_4_stage_state_v3_sha256": state_hash,
        },
        "checks": {
            "phase7_4_1_checkpoint_frozen": True,
            "descendant_commit_replay_portable": True,
            "bounded_git_eol_rule_audited": True,
            "failed_attempt_retained": True,
            "completion_plan_frozen": True,
            "completion_contract_frozen": True,
            "predecessor_read_only": True,
            "effect_dataset_closed": True,
            "provider_not_called": True,
            "runtime_not_authorized": True
        },
        "phase7_4_2_protocol_freeze_authorized": True,
        "phase7_4_effect_execution_authorized": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT
    }


def receipt_document(
    report_hash: str,
    manifest_hash: str,
    audit_hash: str,
    state_hash: str,
    readiness_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_id": "phase7.4-m0-governance-freeze-receipt-v1",
        "status": "PASS",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "report_v2_sha256": report_hash,
        "manifest_v2_sha256": manifest_hash,
        "audit_log_v2_sha256": audit_hash,
        "state_v3_sha256": state_hash,
        "readiness_v3_sha256": readiness_hash,
        "completion_plan_sha256": sha(PLAN),
        "completion_contract_sha256": sha(CONTRACT),
        "retained_failed_attempt_sha256": sha(ATTEMPTS),
        "same_version_semantic_retry_allowed": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "productization_authorized": False,
        "release_authorized": False,
        "next_authorized_stage": NEXT,
    }


def preflight() -> dict[str, Any]:
    checks = fixed_input_checks()
    report = replay_report(git_head())
    checks.update({"replay_check:" + key: value for key, value in report["checks"].items()})
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "current_head": git_head(),
        "effect_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def freeze() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    report_hash = once(REPORT, replay_report(git_head()))
    manifest_hash = once(MANIFEST, manifest_document(report_hash))
    audit_hash = append_single_event(AUDIT, audit_event(report_hash, manifest_hash))
    state_hash = once(STATE_V3, state_document(report_hash, manifest_hash, audit_hash))
    readiness_hash = once(
        READINESS_V3,
        readiness_document(report_hash, manifest_hash, audit_hash, state_hash),
    )
    receipt_hash = once(
        RECEIPT,
        receipt_document(
            report_hash, manifest_hash, audit_hash, state_hash, readiness_hash
        ),
    )
    return {
        "status": "PASS",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "report_v2_sha256": report_hash,
        "manifest_v2_sha256": manifest_hash,
        "audit_v2_sha256": audit_hash,
        "state_v3_sha256": state_hash,
        "readiness_v3_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "retained_failed_attempt_sha256": sha(ATTEMPTS),
        "phase7_4_effect_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in OUTPUTS}
    if all(checks.values()):
        report_hash = sha(REPORT)
        manifest_hash = sha(MANIFEST)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V3)
        readiness_hash = sha(READINESS_V3)
        checks.update(
            {
                "fixed_inputs": all(fixed_input_checks().values()),
                "current_head_descends_from_checkpoint": is_ancestor(
                    CHECKPOINT_HEAD, git_head()
                ),
                "report_replay": load(REPORT) == replay_report(git_head()),
                "manifest_replay": load(MANIFEST) == manifest_document(report_hash),
                "audit_replay": AUDIT.read_bytes()
                == (canonical(audit_event(report_hash, manifest_hash)) + "\n").encode(
                    "utf-8"
                ),
                "state_v3_replay": load(STATE_V3)
                == state_document(report_hash, manifest_hash, audit_hash),
                "readiness_v3_replay": load(READINESS_V3)
                == readiness_document(
                    report_hash, manifest_hash, audit_hash, state_hash
                ),
                "receipt_replay": load(RECEIPT)
                == receipt_document(
                    report_hash,
                    manifest_hash,
                    audit_hash,
                    state_hash,
                    readiness_hash,
                ),
                "next_gate_consistent": load(STATE_V3)["next_authorized_stage"]
                == load(READINESS_V3)["next_authorized_stage"]
                == load(RECEIPT)["next_authorized_stage"]
                == NEXT,
                "effect_dataset_closed": load(STATE_V3)["phase7_4_effect_dataset_opened"]
                is False,
                "provider_not_called": load(STATE_V3)["phase7_4_effect_provider_called"]
                is False,
                "runtime_not_authorized": load(STATE_V3)["runtime_integration_authorized"]
                is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": CHECKPOINT_HEAD,
        "current_head": git_head(),
        "phase7_4_effect_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT if not failed else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        outcome = preflight()
    elif args.freeze:
        outcome = freeze()
    else:
        outcome = verify()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
