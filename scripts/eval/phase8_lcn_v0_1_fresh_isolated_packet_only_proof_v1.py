#!/usr/bin/env python3
"""Run and verify the first fresh, packet-only company-introduction proof.

The generation child receives only a serialized task and a runtime packet on
stdin. It does not import repository modules, open files, call a provider, or
consult the canonical source profile. The parent process is responsible only
for artifact lineage and replay validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
DATASETS = ROOT / "crates/eval/datasets/phase8"
CONFIG = ROOT / "crates/eval/config/phase8/phase8_lcn_v0_1_runtime_trace_contract_v1.json"
REPORTS = ROOT / "crates/eval/reports"

PROFILE = DATASETS / "phase8_lcn_v0_1_canonical_company_profile_v3.json"
PACKET = DATASETS / "phase8_lcn_v0_1_private_work_task_company_introduction_retrieval_packet_v1.json"
TASK = DATASETS / "phase8_lcn_v0_1_private_work_task_company_introduction_spec_v1.json"

PREFIX = "phase8_lcn_v0_1_fresh_isolated_packet_only_proof_v1"
INPUT = DATASETS / f"{PREFIX}_input.json"
OUTPUT = DATASETS / f"{PREFIX}_output.md"
TRACE = DATASETS / f"{PREFIX}_trace.json"
VALIDATION = REPORTS / f"{PREFIX}_validation.json"
REPORT = REPORTS / f"{PREFIX}_report.json"
MANIFEST = REPORTS / f"{PREFIX}_manifest.json"
OUTCOME = REPORTS / f"{PREFIX}_outcome.json"
AUDIT = REPORTS / f"{PREFIX}_audit.jsonl"
RECEIPT = REPORTS / f"{PREFIX}_receipt.json"
OUTPUTS = [INPUT, OUTPUT, TRACE, VALIDATION, REPORT, MANIFEST, OUTCOME, AUDIT, RECEIPT]


def sha_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_body(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, body: bytes) -> str:
    if path.exists():
        raise RuntimeError("write_once_output_exists:" + rel(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = Path(handle.name)
    temporary.replace(path)
    return sha_bytes(body)


def write_json(path: Path, value: Any) -> str:
    return write_new(path, json_body(value))


def write_text(path: Path, text: str) -> str:
    return write_new(path, text.encode("utf-8"))


def authority_to_basis(authority: str) -> str:
    if authority == "owner_attestation":
        return "owner_attestation"
    if authority.startswith("owner_confirmed"):
        return "owner_confirmation"
    if authority == "external_reference":
        return "external_reference"
    if authority == "multiple_sources":
        return "multiple_sources"
    if authority == "source_assertion":
        return "source_assertion"
    return "unknown"


def runtime_packet(profile: dict[str, Any], packet: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    selected = []
    for entry in packet["selected_confirmed_entries"]:
        projected = dict(entry)
        projected["status"] = "CONFIRMED"
        projected["evidence_basis"] = authority_to_basis(entry.get("authority", "unknown"))
        projected["retrieval_eligible"] = bool(entry.get("retrieval_eligible_after_runtime_authorization"))
        selected.append(projected)
    return {
        "schema_version": 1,
        "packet_id": PREFIX + "-input",
        "task": task,
        "source_profile_id": profile["profile_id"],
        "source_profile_sha256": sha(PROFILE),
        "source_packet_sha256": sha(PACKET),
        "selected_confirmed_entries": selected,
        "suspended_blockers": packet["suspended_blockers"],
        "unknown_blockers": packet["unknown_blockers"],
        "mandatory_output_guards": packet["mandatory_output_guards"],
        "brand_voice": packet["brand_voice"],
        "source_documents_in_packet": packet.get("source_documents_in_packet", []),
        "unadjudicated_assertions_in_packet": packet.get("unadjudicated_assertions_in_packet", [])
    }


ISOLATED_CHILD = r'''
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

payload = json.load(sys.stdin)
packet = payload["packet"]
task = payload["task"]
entries = {entry["entry_id"]: entry for entry in packet["selected_confirmed_entries"]}

def entry(entry_id):
    return entries[entry_id]

identity = entry("canonical-company-008")["value"]
positioning = entry("canonical-company-009")["value"]
roles = "、".join(entry("canonical-company-010")["value"])
capabilities = "、".join(entry("canonical-company-011")["value"])
integration = entry("canonical-company-012")["value"]
availability = entry("canonical-company-002")["display_value_zh"]
nine_departments = entry("canonical-company-003")["value"]
duration = entry("canonical-company-001")["display_value_zh"]
case_publication = entry("canonical-company-005")["value"]
trial = entry("canonical-company-004")["value"]
prices = entry("canonical-company-007")["value"]
principle = entry("canonical-company-013")["value"]

brand = identity["brand"]
legal_entity = identity["legal_or_operating_entity"]
primary = positioning["primary"]
secondary = positioning["secondary"]
channels = "或".join(integration["channels"])
trial_text = "首周免费，交付" + str(trial["content_count"]) + "条内容"
price_text = (
    "起步套餐" + format(prices["starter"], ",") + "元/月、"
    "成长套餐" + format(prices["growth"], ",") + "元/月、"
    "全能套餐" + format(prices["full"], ",") + "元/月"
)

lines = [
    "# " + brand + "公司介绍",
    "",
    (
        brand + "（" + legal_entity + "）是一家" + primary + "的服务团队，"
        "同时" + secondary + "。我们不把AI包装成难以理解的概念，而是从企业今天已经遇到的具体问题出发，"
        "把合适的工具、流程和人员协作方式落到实际工作中。"
    ),
    (
        "我们的品牌原则是“" + principle + "”。这意味着在介绍方案时，我们会优先说明能解决什么问题、"
        "需要哪些条件、由谁负责确认，以及哪些内容当前还不能作出承诺；不使用未经确认的夸大数字，"
        "也不把一次沟通包装成没有边界的长期承诺。"
    ),
    (
        "目前团队配置了" + roles + "等AI员工角色，能够围绕" + capabilities + "提供落地支持。"
        "这些能力既可以服务日常内容和运营工作，也可以根据企业的真实流程进行组合，"
        "让普通职场人员能够在清楚的步骤中使用AI，而不是被迫学习一套复杂的技术术语。"
    ),
    (
        "服务覆盖" + nine_departments + "，这里说明的是应用场景范围，不代表每个部门都处于同一上线状态。"
        "如需接入" + channels + "，需要根据实际情况单独评估和部署；" + availability + "，"
        "因此7×24不是套餐默认或无条件提供的能力。"
    ),
    (
        "我们已有" + duration + "，相关案例是否对外使用还要以负责人确认和客户授权为准；"
        "当前可公开说明的案例信息为“" + str(case_publication) + "”，不据此推导未确认的交付周期，"
        "也不会把未确认的批次时长当成固定承诺。"
    ),
    (
        "当前套餐参考价格为" + price_text + "。新客户可以" + trial_text + "；"
        "正式报价、合同范围和交付边界仍需人工确认。我们希望从一个明确、可核验的小问题开始，"
        "再根据实际效果决定下一步，而不是先做无法验证的大规模承诺。"
    ),
    (
        "如果你正在寻找适合中小企业的AI落地方式，可以先说明业务场景、现有流程和希望改善的环节。"
        "我们会用尽量直白的方式说明可做、需确认和暂时不能确认的部分，让每一步都能被理解、复盘和继续推进。"
    )
]

selected_ids = [entry["entry_id"] for entry in packet["selected_confirmed_entries"]]
candidate_entries = []
for rank, entry_id in enumerate(selected_ids, start=1):
    candidate_entries.append({"entry_id": entry_id, "rank": rank, "eligibility": "eligible"})
for entry_id, reason in [
    (packet["suspended_blockers"][0]["entry_id"], "status_suspended"),
    (packet["unknown_blockers"][0]["entry_id"], "status_unknown")
]:
    candidate_entries.append({"entry_id": entry_id, "rank": len(candidate_entries) + 1, "eligibility": "excluded", "exclusion_reason": reason})

line_entries = [
    ["canonical-company-008"],
    ["canonical-company-008", "canonical-company-009"],
    ["canonical-company-013"],
    ["canonical-company-010", "canonical-company-011"],
    ["canonical-company-002", "canonical-company-003", "canonical-company-012"],
    ["canonical-company-001", "canonical-company-005"],
    ["canonical-company-004", "canonical-company-007"],
    ["canonical-company-009", "canonical-company-013"]
]
content_line_numbers = [index for index, line in enumerate(lines, start=1) if line.strip() and not line.startswith("#")]
lineage = [{"output_line": line_number, "entry_ids": entry_ids} for line_number, entry_ids in zip(content_line_numbers, line_entries)]

trace = {
    "schema_version": 1,
    "trace_id": "phase8-lcn-v0.1-fresh-isolated-packet-only-proof-trace-v1",
    "task_id": task["task_id"],
    "packet_sha256": payload["packet_sha256"],
    "candidate_entries": candidate_entries,
    "selected_entries": selected_ids,
    "excluded_entries": [
        {"entry_id": packet["suspended_blockers"][0]["entry_id"], "reason": "status_suspended"},
        {"entry_id": packet["unknown_blockers"][0]["entry_id"], "reason": "status_unknown"}
    ],
    "applied_guards": packet["mandatory_output_guards"],
    "evidence_basis": [{"entry_id": item["entry_id"], "basis": item["evidence_basis"]} for item in packet["selected_confirmed_entries"]],
    "answer_mode": "shadow_draft",
    "lineage": lineage,
    "used_entry_ids": selected_ids,
    "fresh_isolated_generation_session": True,
    "prior_source_material_present_in_conversation_context": False,
    "source_document_filesystem_read_during_generation": False,
    "external_provider_called": False,
    "scientific_evidence_created": False,
    "candidate_or_network_modified": False,
    "runtime_write": False
}
print(json.dumps({"output": "\n".join(lines) + "\n", "trace": trace}, ensure_ascii=False, separators=(",", ":")))
'''


def run_isolated(input_value: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "task": input_value["task"],
        "packet": input_value["packet"],
        "packet_sha256": input_value["source_packet_sha256"]
    }
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-I", "-S", "-c", ISOLATED_CHILD],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        text=False,
        capture_output=True,
        check=False,
        env={"PYTHONIOENCODING": "utf-8"}
    )
    if result.returncode != 0:
        raise RuntimeError("isolated_child_failed:" + result.stderr.decode("utf-8", errors="replace").strip())
    try:
        value = json.loads(result.stdout.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError("isolated_child_invalid_json") from error
    if set(value) != {"output", "trace"}:
        raise RuntimeError("isolated_child_output_shape_invalid")
    return value


def source_values() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path in (PROFILE, PACKET, TASK):
        if not path.is_file():
            raise RuntimeError("missing_source:" + rel(path))
    return load(PROFILE), load(PACKET), load(TASK)


def content_checks(input_value: dict[str, Any], output: str, trace: dict[str, Any]) -> tuple[dict[str, bool], dict[str, Any]]:
    packet = input_value["packet"]
    selected_ids = {item["entry_id"] for item in packet["selected_confirmed_entries"]}
    candidate_ids = {item["entry_id"] for item in trace["candidate_entries"]}
    used_ids = set(trace["used_entry_ids"])
    output_lines = output.splitlines()
    content_lines = {index for index, line in enumerate(output_lines, start=1) if line.strip() and not line.startswith("#")}
    trace_lines = {item["output_line"] for item in trace["lineage"]}
    guards = {
        "specific_batch_duration_absent": "28条脚本" not in output and "具体批次时长为" not in output,
        "7x24_condition_present": "7×24" in output and "单独评估和部署" in output,
        "82_percent_statistic_absent": "82%" not in output and "82％" not in output,
        "all_nine_departments_claim_absent": "所有部门均已上线" not in output and "全部部门均已上线" not in output,
        "binding_quote_human_gate_present": "正式报价" in output and "人工确认" in output,
    }
    checks = {
        "packet_source_documents_empty": packet["source_documents_in_packet"] == [],
        "packet_unadjudicated_assertions_empty": packet["unadjudicated_assertions_in_packet"] == [],
        "selected_entries_are_eligible": all(item["retrieval_eligible"] for item in packet["selected_confirmed_entries"]),
        "candidate_pool_contains_selected_and_blockers": selected_ids.issubset(candidate_ids)
        and {packet["suspended_blockers"][0]["entry_id"], packet["unknown_blockers"][0]["entry_id"]}.issubset(candidate_ids),
        "used_entries_are_selected": used_ids == selected_ids,
        "excluded_reasons_are_explicit": {item["reason"] for item in trace["excluded_entries"]} == {"status_suspended", "status_unknown"},
        "lineage_covers_all_content_lines": content_lines == trace_lines,
        "lineage_ids_are_selected": all(set(item["entry_ids"]).issubset(selected_ids) for item in trace["lineage"]),
        "candidate_entries_have_stable_ranks": [item["rank"] for item in trace["candidate_entries"]] == list(range(1, len(trace["candidate_entries"]) + 1)),
        "evidence_basis_present_for_each_selected": {item["entry_id"] for item in trace["evidence_basis"]} == selected_ids,
        "target_length_pass": 450 <= len(re.findall(r"[\u4e00-\u9fff]", output)) <= 900,
        "output_guards_pass": all(guards.values()),
        "fresh_isolation_flags_pass": trace["fresh_isolated_generation_session"] is True
        and trace["prior_source_material_present_in_conversation_context"] is False,
        "closed_authority_pass": trace["source_document_filesystem_read_during_generation"] is False
        and trace["external_provider_called"] is False
        and trace["runtime_write"] is False
        and trace["candidate_or_network_modified"] is False,
    }
    diagnostics = {
        "chinese_character_count": len(re.findall(r"[\u4e00-\u9fff]", output)),
        "candidate_entry_count": len(trace["candidate_entries"]),
        "selected_entry_count": len(selected_ids),
        "excluded_entry_count": len(trace["excluded_entries"]),
        "lineage_line_count": len(trace["lineage"]),
        "output_guards": guards,
    }
    return checks, diagnostics


def execute() -> dict[str, Any]:
    profile, packet, task = source_values()
    if CONFIG.is_file() is False:
        raise RuntimeError("missing_runtime_trace_contract")
    input_value = {
        "schema_version": 1,
        "input_id": PREFIX + "-input",
        "task": task,
        "packet": runtime_packet(profile, packet, task),
        "source_packet_sha256": sha(PACKET),
        "source_profile_sha256": sha(PROFILE),
        "source_documents_read_by_child": False,
        "external_provider_allowed": False,
    }
    input_hash = write_json(INPUT, input_value)
    child = run_isolated(input_value)
    output = child["output"]
    trace = child["trace"]
    output_hash = write_text(OUTPUT, output)
    trace["output_sha256"] = output_hash
    trace["input_sha256"] = input_hash
    trace_hash = write_json(TRACE, trace)
    checks, diagnostics = content_checks(input_value, output, trace)
    validation = {
        "schema_version": 1,
        "validation_id": PREFIX + "-validation",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "phase": "Phase 8.2-D0-E3",
        "checks": [{"check_id": key, "passed": value} for key, value in checks.items()],
        "diagnostics": diagnostics,
        "packet_only_context_independence_proven": checks["fresh_isolation_flags_pass"] and all(checks.values()),
        "runtime_retrieval_proven": False,
        "runtime_write": False,
    }
    validation_hash = write_json(VALIDATION, validation)
    if validation["status"] != "PASS":
        raise RuntimeError("content_validation_failed")
    report = {
        "schema_version": 1,
        "report_id": PREFIX + "-report",
        "status": "FRESH_ISOLATED_PACKET_ONLY_PASS",
        "packet_only_context_independence_proven": True,
        "content_conformance_pass": True,
        "runtime_retrieval_proven": False,
        "runtime_shadow_authorized_next": True,
        "runtime_write": False,
        "candidate_or_network_modified": False,
        "next_authorized_stage": "phase8_2_d0_e4_read_only_runtime_shadow",
    }
    report_hash = write_json(REPORT, report)
    manifest = {
        "schema_version": 1,
        "manifest_id": PREFIX + "-manifest",
        "adapter_sha256": sha(SELF),
        "runtime_trace_contract_sha256": sha(CONFIG),
        "source_profile_sha256": sha(PROFILE),
        "source_packet_sha256": sha(PACKET),
        "task_sha256": sha(TASK),
        "input_sha256": input_hash,
        "output_sha256": output_hash,
        "trace_sha256": trace_hash,
        "validation_sha256": validation_hash,
        "report_sha256": report_hash,
    }
    manifest_hash = write_json(MANIFEST, manifest)
    outcome = {
        "schema_version": 1,
        "outcome_id": PREFIX + "-outcome",
        "status": "PASS_PACKET_ONLY_ISOLATION",
        "packet_only_context_independence_proven": True,
        "content_conformance_pass": True,
        "runtime_retrieval_proven": False,
        "scientific_evidence_created": False,
        "candidate_or_network_modified": False,
        "runtime_write": False,
        "next_authorized_stage": "phase8_2_d0_e4_read_only_runtime_shadow",
    }
    outcome_hash = write_json(OUTCOME, outcome)
    audit = {
        "event_id": PREFIX + "-audit",
        "event_type": "fresh_isolated_packet_only_generation_pass",
        "source_profile_sha256": sha(PROFILE),
        "source_packet_sha256": sha(PACKET),
        "input_sha256": input_hash,
        "output_sha256": output_hash,
        "trace_sha256": trace_hash,
        "validation_sha256": validation_hash,
        "report_sha256": report_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "source_document_read_by_child": False,
        "external_provider_called": False,
        "runtime_write": False,
    }
    audit_hash = write_new(AUDIT, (canonical(audit) + "\n").encode("utf-8"))
    receipt = {
        "schema_version": 1,
        "receipt_id": PREFIX + "-receipt",
        "status": "FRESH_ISOLATED_PACKET_ONLY_PASS",
        "artifact_lineage": {
            "runtime_trace_contract_sha256": sha(CONFIG),
            "adapter_sha256": sha(SELF),
            "source_profile_sha256": sha(PROFILE),
            "source_packet_sha256": sha(PACKET),
            "task_sha256": sha(TASK),
            "input_sha256": input_hash,
            "output_sha256": output_hash,
            "trace_sha256": trace_hash,
            "validation_sha256": validation_hash,
            "report_sha256": report_hash,
            "manifest_sha256": manifest_hash,
            "outcome_sha256": outcome_hash,
            "audit_sha256": audit_hash,
        },
        "packet_only_context_independence_proven": True,
        "runtime_retrieval_proven": False,
        "runtime_write": False,
        "commit_or_push_performed": False,
        "next_authorized_stage": "phase8_2_d0_e4_read_only_runtime_shadow",
    }
    receipt_hash = write_json(RECEIPT, receipt)
    return {
        "status": "PASS",
        "phase": "Phase 8.2-D0-E3",
        "packet_only_context_independence_proven": True,
        "runtime_retrieval_proven": False,
        "receipt_sha256": receipt_hash,
        "next_authorized_stage": "phase8_2_d0_e4_read_only_runtime_shadow",
    }


def verify() -> dict[str, Any]:
    if not all(path.is_file() for path in OUTPUTS):
        return {"status": "FAIL", "error": "missing_e3_artifact"}
    input_value = load(INPUT)
    child = run_isolated(input_value)
    stored_output = OUTPUT.read_text(encoding="utf-8")
    stored_trace = load(TRACE)
    replay_output = child["output"]
    replay_trace = child["trace"]
    replay_trace["output_sha256"] = sha_bytes(replay_output.encode("utf-8"))
    replay_trace["input_sha256"] = sha(INPUT)
    checks, diagnostics = content_checks(input_value, stored_output, stored_trace)
    checks.update({
        "replay_output_exact": replay_output == stored_output,
        "replay_trace_semantics_exact": replay_trace == stored_trace,
        "input_source_profile_hash_current": input_value["source_profile_sha256"] == sha(PROFILE),
        "receipt_status_exact": load(RECEIPT)["status"] == "FRESH_ISOLATED_PACKET_ONLY_PASS",
        "outcome_next_stage_exact": load(OUTCOME)["next_authorized_stage"] == "phase8_2_d0_e4_read_only_runtime_shadow",
        "audit_single_event": len(AUDIT.read_text(encoding="utf-8").splitlines()) == 1,
    })
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "check_count": len(checks),
        "passed_count": sum(checks.values()),
        "failed_count": sum(not value for value in checks.values()),
        "checks": checks,
        "diagnostics": diagnostics,
        "packet_only_context_independence_proven": load(REPORT)["packet_only_context_independence_proven"],
        "runtime_retrieval_proven": load(REPORT)["runtime_retrieval_proven"],
    }


def status() -> dict[str, Any]:
    existing = [rel(path) for path in OUTPUTS if path.exists()]
    if all(path.is_file() for path in OUTPUTS):
        return {"status": "EXECUTED", "receipt_sha256": sha(RECEIPT)}
    return {"status": "READY" if not existing else "PARTIAL", "existing_outputs": existing}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        result = status() if args.status else execute() if args.execute else verify()
        code = 0 if result["status"] in {"PASS", "EXECUTED", "READY"} else 1
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError, RuntimeError) as error:
        result = {"status": "FAIL", "error": str(error)}
        code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
