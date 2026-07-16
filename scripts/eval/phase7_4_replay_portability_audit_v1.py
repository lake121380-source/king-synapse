#!/usr/bin/env python3
"""Freeze and verify the Phase 7.4.1 descendant-commit replay policy."""
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
PATTERN = ROOT / "crates/eval/datasets/pattern_extraction"
REPORTS = ROOT / "crates/eval/reports"
DOCS = ROOT / "docs"

PLAN = DOCS / "KING_SYNAPSE_LONG_TERM_COMPLETION_PLAN.md"
CONTRACT = CONFIG / "project_completion_contract_v1.json"
POLICY = CONFIG / "phase7_4_replay_portability_policy_v1.json"

PROTOCOL_RECEIPT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_protocol_freeze_receipt_v1.json"
V1_MANIFEST = REPORTS / "phase7_4_atomic_evidence_shadow_implementation_manifest_v1.json"
V1_FIXTURES = REPORTS / "phase7_4_atomic_evidence_shadow_implementation_fixtures_v1.json"
V1_GATE = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_report_v1.json"
V1_AUDIT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_audit_v1.jsonl"
V1_RECEIPT = REPORTS / "phase7_4_atomic_evidence_shadow_prototype_gate_receipt_v1.json"
STATE_V2 = PATTERN / "phase7_4_stage_state_v2.json"
READINESS_V2 = REPORTS / "phase7_4_readiness_v2.json"

REPORT = REPORTS / "phase7_4_replay_portability_report_v1.json"
MANIFEST = REPORTS / "phase7_4_replay_portability_manifest_v1.json"
AUDIT = REPORTS / "phase7_4_replay_portability_audit_v1.jsonl"
STATE_V3 = PATTERN / "phase7_4_stage_state_v3.json"
READINESS_V3 = REPORTS / "phase7_4_readiness_v3.json"
RECEIPT = REPORTS / "phase7_4_m0_governance_freeze_receipt_v1.json"

RECORDED_HEAD = "3c99170854743f65bd1d5334aeaea94f748c1809"
ENTRY = "phase7_4_1_shadow_prototype_gate_passed_offline_retrieval_protocol_authorized"
NEXT = "freeze_phase7_4_offline_retrieval_evaluation_protocol_v1"

EXPECTED_M0_INPUTS = {
    PLAN: "eb20101e78f01726a3d9ebe5ce7f7ec2777c300647cf52aae98936ddeb9602bf",
    CONTRACT: "63831b2886346d047413656155eb95a960e04061eb5f161992439c1081d1f924",
    POLICY: "fa60781834ef98e8985f962f81cab7deb0a2f8e62924585968ca25d583e93a9d",
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


def git_text(*args: str) -> str:
    result = run(["git", *args])
    if result.returncode != 0:
        raise RuntimeError("git_command_failed:" + "_".join(args) + ":" + result.stderr.strip())
    return result.stdout.strip()


def git_head() -> str:
    return git_text("rev-parse", "HEAD")


def is_ancestor(ancestor: str, descendant: str) -> bool:
    return run(["git", "merge-base", "--is-ancestor", ancestor, descendant]).returncode == 0


def git_blob(commit: str, path: str) -> bytes | None:
    result = run(["git", "show", f"{commit}:{path}"], text=False)
    return result.stdout if result.returncode == 0 else None


def git_blob_sha(commit: str, path: str) -> str | None:
    value = git_blob(commit, path)
    return hb(value) if value is not None else None


def changed_paths_between(older: str, newer: str) -> list[str]:
    if older == newer:
        return []
    output = git_text("diff", "--name-only", older, newer)
    return sorted(line.replace("\\", "/") for line in output.splitlines() if line)


def working_changed_paths() -> list[str]:
    result = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    if result.returncode != 0:
        return ["<git-status-unavailable>"]
    paths = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return sorted(paths)


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


def validate_fixed_inputs() -> dict[str, bool]:
    checks = {
        "m0_input_hash:" + rel(path): path.exists() and sha(path) == digest
        for path, digest in EXPECTED_M0_INPUTS.items()
    }
    checks.update(
        {
            "v1_root_hash:" + rel(path): path.exists() and sha(path) == digest
            for path, digest in EXPECTED_V1_ROOTS.items()
        }
    )
    if all(checks.values()):
        policy = load(POLICY)
        contract = load(CONTRACT)
        state = load(STATE_V2)
        readiness = load(READINESS_V2)
        receipt = load(V1_RECEIPT)
        checks.update(
            {
                "policy_recorded_head": policy["recorded_execution_head"] == RECORDED_HEAD,
                "policy_plan_hash": policy["frozen_m0_inputs"][rel(PLAN)] == sha(PLAN),
                "policy_contract_hash": policy["frozen_m0_inputs"][rel(CONTRACT)] == sha(CONTRACT),
                "contract_plan_hash": contract["completion_plan"]["sha256"] == sha(PLAN),
                "contract_m0_authority": contract["current_authority"]["authorized_stage"]
                == "freeze_m0_governance_and_replay_portability_v1",
                "state_entry": state["status"] == ENTRY and state["next_authorized_stage"] == NEXT,
                "readiness_entry": readiness["next_authorized_stage"] == NEXT,
                "receipt_entry": receipt["status"] == "PASS"
                and receipt["next_authorized_stage"] == NEXT,
                "effect_dataset_closed": state["phase7_4_effect_dataset_opened"] is False,
                "provider_not_called": state["phase7_4_effect_provider_called"] is False,
                "runtime_not_authorized": state["runtime_integration_authorized"] is False,
            }
        )
        manifest = load(V1_MANIFEST)
        checks["v1_manifest_recorded_head"] = (
            manifest["execution_environment"]["git_head"] == RECORDED_HEAD
        )
        checks["working_implementation_bytes_exact"] = all(
            (ROOT / path).exists() and sha(ROOT / path) == digest
            for path, digest in manifest["implementation_artifacts"].items()
        )
    return checks


def preflight() -> dict[str, Any]:
    checks = validate_fixed_inputs()
    paths = working_changed_paths()
    checks.update(
        {
            "recorded_execution_head_is_current": git_head() == RECORDED_HEAD,
            "outputs_absent": all(not path.exists() for path in OUTPUTS),
            "portability_verifier_present": SELF.exists(),
            "working_tree_has_no_core_change": all(
                not path.startswith("crates/core/") for path in paths
            ),
            "working_tree_has_no_phase7_3_3_d_change": all(
                "phase7_3_3_d" not in path for path in paths
            ),
        }
    )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "recorded_execution_head": RECORDED_HEAD,
        "current_head": git_head(),
        "checkpoint_commit_ready": not failed,
        "effect_dataset_opened": False,
        "runtime_integration_authorized": False,
    }


def checkpoint_report(checkpoint_head: str, verifier_head: str) -> dict[str, Any]:
    manifest = load(V1_MANIFEST)
    policy = load(POLICY)
    changed = changed_paths_between(RECORDED_HEAD, checkpoint_head)
    implementation_checks = {
        path: git_blob_sha(checkpoint_head, path) == digest
        for path, digest in manifest["implementation_artifacts"].items()
    }
    root_checks = {
        rel(path): git_blob_sha(checkpoint_head, rel(path)) == digest
        for path, digest in EXPECTED_V1_ROOTS.items()
    }
    owned_paths = policy["future_replay_rules"]["future_exact_owned_implementation_paths"]
    owned_working_checks = {
        path: (ROOT / path).exists()
        and sha(ROOT / path) == manifest["implementation_artifacts"][path]
        for path in owned_paths
    }
    checks = {
        "recorded_head_is_checkpoint_ancestor": is_ancestor(RECORDED_HEAD, checkpoint_head),
        "checkpoint_is_verifier_head_or_ancestor": is_ancestor(checkpoint_head, verifier_head),
        "checkpoint_changed_paths_version_isolated": bool(changed)
        and all(checkpoint_path_allowed(path) for path in changed),
        "checkpoint_has_no_core_change": all(
            not path.startswith("crates/core/") for path in changed
        ),
        "checkpoint_has_no_phase7_3_3_d_change": all(
            "phase7_3_3_d" not in path for path in changed
        ),
        "checkpoint_contains_policy": git_blob_sha(checkpoint_head, rel(POLICY)) == sha(POLICY),
        "checkpoint_contains_verifier": git_blob_sha(checkpoint_head, rel(SELF)) == sha(SELF),
        "checkpoint_implementation_bytes_exact": all(implementation_checks.values()),
        "checkpoint_v1_governance_roots_exact": all(root_checks.values()),
        "working_owned_implementation_bytes_exact": all(owned_working_checks.values()),
        "m0_inputs_exact": all(
            path.exists() and sha(path) == digest for path, digest in EXPECTED_M0_INPUTS.items()
        ),
        "effect_dataset_closed": load(STATE_V2)["phase7_4_effect_dataset_opened"] is False,
        "provider_not_called": load(STATE_V2)["phase7_4_effect_provider_called"] is False,
        "runtime_not_authorized": load(STATE_V2)["runtime_integration_authorized"] is False,
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "report_id": "phase7.4.1-replay-portability-report-v1",
        "status": "PASS_descendant_commit_replay_portable"
        if passed
        else "FAIL_replay_portability_not_established",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": checkpoint_head,
        "checkpoint_changed_paths": changed,
        "implementation_blob_check_count": len(implementation_checks),
        "implementation_blob_checks": implementation_checks,
        "v1_governance_root_check_count": len(root_checks),
        "v1_governance_root_checks": root_checks,
        "future_owned_working_check_count": len(owned_working_checks),
        "future_owned_working_checks": owned_working_checks,
        "checks": checks,
        "all_checks_passed": passed,
        "recorded_head_equality_with_future_verifier_required": False,
        "same_version_semantic_retry_allowed": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT if passed else "freeze_replay_portability_negative_result",
    }


def manifest_document(checkpoint_head: str, report_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4.1-replay-portability-manifest-v1",
        "status": "frozen_descendant_commit_replay_policy",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": checkpoint_head,
        "adapter_sha256": sha(SELF),
        "policy_sha256": sha(POLICY),
        "completion_plan_sha256": sha(PLAN),
        "completion_contract_sha256": sha(CONTRACT),
        "replay_portability_report_sha256": report_hash,
        "frozen_phase7_4_1_roots": {
            rel(path): digest for path, digest in EXPECTED_V1_ROOTS.items()
        },
        "checkpoint_implementation_artifacts": load(V1_MANIFEST)["implementation_artifacts"],
        "future_owned_exact_paths": load(POLICY)["future_replay_rules"]
        ["future_exact_owned_implementation_paths"],
        "checkpoint_only_evolving_context_paths": load(POLICY)["future_replay_rules"]
        ["checkpoint_only_evolving_context_paths"],
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(checkpoint_head: str, report_hash: str, manifest_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4.1-replay-portability-v1-frozen",
        "event_type": "immutable_descendant_commit_replay_policy",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": checkpoint_head,
        "report_sha256": report_hash,
        "manifest_sha256": manifest_hash,
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
        "phase7_4_replay_portability_policy_v1_sha256": sha(POLICY),
        "phase7_4_replay_portability_report_v1_sha256": report_hash,
        "phase7_4_replay_portability_manifest_v1_sha256": manifest_hash,
        "phase7_4_replay_portability_audit_v1_sha256": audit_hash,
    }


def state_document(
    checkpoint_head: str, report_hash: str, manifest_hash: str, audit_hash: str
) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "state_id": "phase7.4-stage-state-v3",
        "status": "m0_governance_baseline_frozen_phase7_4_2_protocol_freeze_authorized",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": checkpoint_head,
        "artifact_lineage": lineage(report_hash, manifest_hash, audit_hash),
        "phase7_4_1_replay_portable_across_descendant_commits": True,
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
    checkpoint_head: str,
    report_hash: str,
    manifest_hash: str,
    audit_hash: str,
    state_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "readiness_id": "phase7.4-readiness-v3",
        "status": "PASS_m0_governance_and_replay_portability_frozen",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": checkpoint_head,
        "artifact_lineage": {
            **lineage(report_hash, manifest_hash, audit_hash),
            "phase7_4_stage_state_v3_sha256": state_hash,
        },
        "checks": {
            "phase7_4_1_checkpoint_frozen": True,
            "descendant_commit_replay_portable": True,
            "completion_plan_frozen": True,
            "completion_contract_frozen": True,
            "predecessor_read_only": True,
            "effect_dataset_closed": True,
            "provider_not_called": True,
            "runtime_not_authorized": True,
        },
        "phase7_4_2_protocol_freeze_authorized": True,
        "phase7_4_effect_execution_authorized": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def receipt_document(
    checkpoint_head: str,
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
        "phase7_4_1_checkpoint_head": checkpoint_head,
        "report_sha256": report_hash,
        "manifest_sha256": manifest_hash,
        "audit_log_sha256": audit_hash,
        "state_v3_sha256": state_hash,
        "readiness_v3_sha256": readiness_hash,
        "completion_plan_sha256": sha(PLAN),
        "completion_contract_sha256": sha(CONTRACT),
        "same_version_semantic_retry_allowed": False,
        "phase7_4_effect_dataset_opened": False,
        "phase7_4_effect_provider_called": False,
        "runtime_integration_authorized": False,
        "productization_authorized": False,
        "release_authorized": False,
        "next_authorized_stage": NEXT,
    }


def freeze() -> dict[str, Any]:
    if any(path.exists() for path in OUTPUTS):
        return {"status": "FAIL", "failed": ["outputs_must_be_absent_before_freeze"]}
    fixed = validate_fixed_inputs()
    checkpoint_head = git_head()
    report = checkpoint_report(checkpoint_head, checkpoint_head)
    fixed_failed = [key for key, passed in fixed.items() if not passed]
    if fixed_failed or not report["all_checks_passed"]:
        return {
            "status": "FAIL",
            "failed": fixed_failed
            + [key for key, passed in report["checks"].items() if not passed],
        }
    report_hash = once(REPORT, report)
    manifest_hash = once(MANIFEST, manifest_document(checkpoint_head, report_hash))
    audit_hash = append_single_event(
        AUDIT, audit_event(checkpoint_head, report_hash, manifest_hash)
    )
    state_hash = once(
        STATE_V3,
        state_document(checkpoint_head, report_hash, manifest_hash, audit_hash),
    )
    readiness_hash = once(
        READINESS_V3,
        readiness_document(
            checkpoint_head, report_hash, manifest_hash, audit_hash, state_hash
        ),
    )
    receipt_hash = once(
        RECEIPT,
        receipt_document(
            checkpoint_head,
            report_hash,
            manifest_hash,
            audit_hash,
            state_hash,
            readiness_hash,
        ),
    )
    return {
        "status": "PASS",
        "recorded_execution_head": RECORDED_HEAD,
        "phase7_4_1_checkpoint_head": checkpoint_head,
        "report_sha256": report_hash,
        "manifest_sha256": manifest_hash,
        "audit_sha256": audit_hash,
        "state_v3_sha256": state_hash,
        "readiness_v3_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "phase7_4_effect_dataset_opened": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in OUTPUTS}
    if all(checks.values()):
        manifest = load(MANIFEST)
        checkpoint_head = manifest["phase7_4_1_checkpoint_head"]
        report_hash = sha(REPORT)
        manifest_hash = sha(MANIFEST)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V3)
        readiness_hash = sha(READINESS_V3)
        replay_report = checkpoint_report(checkpoint_head, git_head())
        checks.update(
            {
                "fixed_inputs": all(validate_fixed_inputs().values()),
                "current_head_descends_from_checkpoint": is_ancestor(
                    checkpoint_head, git_head()
                ),
                "report_replay": load(REPORT) == replay_report,
                "manifest_replay": manifest
                == manifest_document(checkpoint_head, report_hash),
                "audit_replay": AUDIT.read_bytes()
                == (
                    canonical(audit_event(checkpoint_head, report_hash, manifest_hash))
                    + "\n"
                ).encode("utf-8"),
                "state_v3_replay": load(STATE_V3)
                == state_document(
                    checkpoint_head, report_hash, manifest_hash, audit_hash
                ),
                "readiness_v3_replay": load(READINESS_V3)
                == readiness_document(
                    checkpoint_head,
                    report_hash,
                    manifest_hash,
                    audit_hash,
                    state_hash,
                ),
                "receipt_replay": load(RECEIPT)
                == receipt_document(
                    checkpoint_head,
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
        "current_head": git_head(),
        "phase7_4_1_checkpoint_head": load(MANIFEST).get("phase7_4_1_checkpoint_head")
        if MANIFEST.exists()
        else None,
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
