#!/usr/bin/env python3
"""Execute the smallest read-only Runtime Shadow over the frozen packet.

This is a deterministic retrieval/governance probe, not a semantic model
claim. It exists to make candidate selection, exclusion, guards, and trace
regression observable before any provider or production integration is added.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import tempfile
from pathlib import Path
from typing import Any


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
DATASETS = ROOT / "crates/eval/datasets/phase8"
REPORTS = ROOT / "crates/eval/reports"
CASES = DATASETS / "phase8_lcn_v0_1_governance_regression_cases_v1.json"
E3_SCRIPT = SELF.parent / "phase8_lcn_v0_1_fresh_isolated_packet_only_proof_v1.py"
CONFIG = ROOT / "crates/eval/config/phase8/phase8_lcn_v0_1_runtime_trace_contract_v1.json"
PROFILE = DATASETS / "phase8_lcn_v0_1_canonical_company_profile_v3.json"
PACKET = DATASETS / "phase8_lcn_v0_1_private_work_task_company_introduction_retrieval_packet_v1.json"
TASK = DATASETS / "phase8_lcn_v0_1_private_work_task_company_introduction_spec_v1.json"

PREFIX = "phase8_lcn_v0_1_read_only_runtime_shadow_v1"
EXECUTION = REPORTS / f"{PREFIX}_execution.json"
VALIDATION = REPORTS / f"{PREFIX}_validation.json"
REPORT = REPORTS / f"{PREFIX}_report.json"
MANIFEST = REPORTS / f"{PREFIX}_manifest.json"
OUTCOME = REPORTS / f"{PREFIX}_outcome.json"
AUDIT = REPORTS / f"{PREFIX}_audit.jsonl"
RECEIPT = REPORTS / f"{PREFIX}_receipt.json"
OUTPUTS = [EXECUTION, VALIDATION, REPORT, MANIFEST, OUTCOME, AUDIT, RECEIPT]


def import_e3() -> Any:
    spec = importlib.util.spec_from_file_location("phase8_e3", E3_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("e3_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


E3 = import_e3()


def sha_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_body(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, body: bytes) -> str:
    if path.exists():
        raise RuntimeError("write_once_output_exists:" + path.as_posix())
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = Path(handle.name)
    temporary.replace(path)
    return sha_bytes(body)


def write_json(path: Path, value: Any) -> str:
    return write_new(path, json_body(value))


TERM_RULES: dict[str, list[str]] = {
    "canonical-company-001": ["服务多久", "服务了多久", "服务关系", "一年"],
    "canonical-company-002": ["7x24", "7×24", "7＊24", "全天", "在线"],
    "canonical-company-003": ["九个部门", "9个部门", "部门"],
    "canonical-company-004": ["试用", "首周", "免费", "内容"],
    "canonical-company-005": ["案例", "客户授权", "公开案例"],
    "canonical-company-007": ["套餐", "价格", "多少钱", "报价", "1980", "2980", "3980"],
    "canonical-company-008": ["叫什么", "品牌和主体", "公司名称", "法定主体"],
    "canonical-company-009": ["定位", "服务什么", "中小企业", "落地服务", "业务定位"],
    "canonical-company-010": ["AI员工", "员工角色", "角色", "调度", "文案", "剪辑"],
    "canonical-company-011": ["能力", "能做什么", "可以做什么", "交付", "API", "脚本"],
    "canonical-company-012": ["飞书", "企业微信", "接入", "集成"],
    "canonical-company-013": ["原则", "理念", "风格", "不卖焦虑", "务实"],
}
SUSPENDED_TERMS = ["82%", "82％", "采用率", "市场统计"]
UNKNOWN_TERMS = ["28条", "脚本批次", "批次", "交付多久", "交付周期", "具体时长"]
COMPANY_INTRO_TERMS = ["公司介绍", "介绍一下公司", "写一段公司介绍"]


def evidence_basis(entry: dict[str, Any]) -> str:
    return entry.get("evidence_basis") or E3.authority_to_basis(entry.get("authority", "unknown"))


def retrieve(query: str, packet: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    if any(term.lower() in query.lower() for term in SUSPENDED_TERMS):
        scores = {}
    elif any(term.lower() in query.lower() for term in UNKNOWN_TERMS):
        scores = {}
    elif any(term in query for term in COMPANY_INTRO_TERMS):
        special_ids = [
            "canonical-company-001", "canonical-company-002", "canonical-company-003", "canonical-company-005",
            "canonical-company-008", "canonical-company-009", "canonical-company-010", "canonical-company-011",
            "canonical-company-012", "canonical-company-013"
        ]
        scores = {entry_id: 1 for entry_id in special_ids}
    else:
        scores = {
            entry_id: sum(1 for term in terms if term.lower() in query.lower())
            for entry_id, terms in TERM_RULES.items()
        }
        scores = {entry_id: score for entry_id, score in scores.items() if score > 0}

    candidates = [
        {"entry_id": entry_id, "score": score}
        for entry_id, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]
    for term_list, entry_id, reason in [
        (SUSPENDED_TERMS, packet["suspended_blockers"][0]["entry_id"], "status_suspended"),
        (UNKNOWN_TERMS, packet["unknown_blockers"][0]["entry_id"], "status_unknown"),
    ]:
        score = sum(1 for term in term_list if term.lower() in query.lower())
        if score:
            candidates.append({"entry_id": entry_id, "score": score, "eligibility": "excluded", "exclusion_reason": reason})
    candidates.sort(key=lambda item: (-item["score"], item["entry_id"]))
    for rank, item in enumerate(candidates, start=1):
        item["rank"] = rank
        if item.get("eligibility") != "excluded":
            item["eligibility"] = "eligible"

    candidate_ids = [item["entry_id"] for item in candidates]
    selected = [item["entry_id"] for item in candidates if item["eligibility"] == "eligible"]
    excluded = [
        {"entry_id": item["entry_id"], "reason": item["exclusion_reason"]}
        for item in candidates if item["eligibility"] == "excluded"
    ]
    return candidates, selected, excluded


def guard_decisions(selected: list[str], excluded: list[dict[str, str]]) -> list[str]:
    guards: list[str] = []
    if "canonical-company-002" in selected:
        guards.append("do_not_describe_7x24_as_default_or_unconditional")
    if "canonical-company-003" in selected:
        guards.append("do_not_claim_all_nine_departments_are_fully_running")
    if "canonical-company-007" in selected:
        guards.append("binding_customer_quote_requires_human_confirmation")
    for item in excluded:
        if item["entry_id"] == "canonical-company-suspended-001":
            guards.append("do_not_use_82_percent_market_statistic")
        if item["entry_id"] == "canonical-company-unknown-001":
            guards.append("do_not_publish_specific_28_script_batch_duration")
    return guards


def compose_answer(query: str, selected: list[str], excluded: list[dict[str, str]], entries: dict[str, dict[str, Any]], guards: list[str]) -> str:
    if not selected:
        if excluded:
            return "当前问题触及知识包中的受限或未知信息，Runtime 不会给出未经确认的具体回答。"
        return "当前知识包没有与该问题匹配的可用条目，Runtime 保持不回答。"
    parts: list[str] = []
    for entry_id in selected:
        item = entries[entry_id]
        if entry_id == "canonical-company-007":
            value = item["value"]
            parts.append(
                f"当前参考套餐为起步{value['starter']:,}元/月、成长{value['growth']:,}元/月、全能{value['full']:,}元/月。"
            )
        elif entry_id == "canonical-company-004":
            parts.append(f"当前试用条件为首周免费，交付{item['value']['content_count']}条内容。")
        elif entry_id == "canonical-company-002":
            parts.append("7×24在线能力需要单独评估和部署，不是套餐默认或无条件提供。")
        elif entry_id == "canonical-company-003":
            parts.append("资料确认的是覆盖9个部门的应用场景，不代表每个部门都处于同一上线状态。")
        elif entry_id == "canonical-company-005":
            parts.append("案例对外使用仍需负责人确认和客户授权，Runtime 不据此扩大公开范围。")
        else:
            display = item.get("display_value_zh") or item.get("value") or item.get("key")
            parts.append(str(display))
    if "binding_customer_quote_requires_human_confirmation" in guards:
        parts.append("正式报价、合同范围和交付边界仍需人工确认。")
    return "".join(parts)


def run_case(case: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    entries = {item["entry_id"]: item for item in packet["selected_confirmed_entries"]}
    candidates, selected, excluded = retrieve(case["query"], packet)
    guards = guard_decisions(selected, excluded)
    answer_mode = "shadow_draft" if selected else "withheld"
    answer = compose_answer(case["query"], selected, excluded, entries, guards)
    return {
        "case_id": case["case_id"],
        "query": case["query"],
        "answer": answer,
        "trace": {
            "schema_version": 1,
            "task_id": case["case_id"],
            "packet_sha256": sha(PACKET),
            "candidate_entries": candidates,
            "selected_entries": selected,
            "excluded_entries": excluded,
            "applied_guards": guards,
            "evidence_basis": [
                {"entry_id": entry_id, "basis": evidence_basis(entries[entry_id])}
                for entry_id in selected
            ],
            "answer_mode": answer_mode,
            "lineage": [{"output_line": 1, "entry_ids": selected}] if selected else [],
            "runtime_write": False,
            "source_document_filesystem_read_during_generation": False,
            "external_provider_called": False,
            "candidate_or_network_modified": False,
            "learning_or_reflection": False,
        }
    }


def validate_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, bool]:
    trace = result["trace"]
    actual_candidates = [item["entry_id"] for item in trace["candidate_entries"]]
    actual_excluded = trace["excluded_entries"]
    return {
        "candidate_entries_exact": actual_candidates == case["expected_candidate_entry_ids"],
        "selected_entries_exact": trace["selected_entries"] == case["expected_selected_entry_ids"],
        "excluded_entries_exact": actual_excluded == case["expected_excluded_entries"],
        "guards_exact": trace["applied_guards"] == case["expected_guards"],
        "answer_mode_exact": trace["answer_mode"] == case["expected_answer_mode"],
        "trace_has_candidate_entries": isinstance(trace["candidate_entries"], list),
        "trace_has_evidence_basis": len(trace["evidence_basis"]) == len(trace["selected_entries"]),
        "trace_is_read_only": trace["runtime_write"] is False
        and trace["source_document_filesystem_read_during_generation"] is False
        and trace["external_provider_called"] is False
        and trace["candidate_or_network_modified"] is False,
    }


def execute() -> dict[str, Any]:
    profile, frozen_packet, task = E3.source_values()
    cases = load(CASES)
    if cases["case_count"] != len(cases["cases"]) or len(cases["cases"]) != 20:
        raise RuntimeError("regression_case_count_invalid")
    packet = E3.runtime_packet(profile, frozen_packet, task)
    results = [run_case(case, packet) for case in cases["cases"]]
    validations = [validate_case(case, result) for case, result in zip(cases["cases"], results)]
    execution = {
        "schema_version": 1,
        "execution_id": PREFIX + "-execution",
        "packet_sha256": sha(PACKET),
        "cases_sha256": sha(CASES),
        "results": results,
        "runtime_write": False,
        "candidate_or_network_modified": False,
    }
    execution_hash = write_json(EXECUTION, execution)
    validation = {
        "schema_version": 1,
        "validation_id": PREFIX + "-validation",
        "status": "PASS" if all(all(item.values()) for item in validations) else "FAIL",
        "phase": "Phase 8.2-D0-E4/E5",
        "case_count": len(validations),
        "case_results": [
            {
                "case_id": case["case_id"],
                "passed": all(checks.values()),
                "checks": checks,
            }
            for case, checks in zip(cases["cases"], validations)
        ],
        "all_trace_fields_regressed": all(
            all(checks[key] for key in ("candidate_entries_exact", "selected_entries_exact", "excluded_entries_exact", "guards_exact", "answer_mode_exact"))
            for checks in validations
        ),
        "runtime_write": False,
    }
    validation_hash = write_json(VALIDATION, validation)
    if validation["status"] != "PASS":
        raise RuntimeError("runtime_shadow_regression_failed")
    report = {
        "schema_version": 1,
        "report_id": PREFIX + "-report",
        "status": "PASS_READ_ONLY_RUNTIME_SHADOW_AND_TRACE_REGRESSION",
        "phase": "Phase 8.2-D0-E4/E5",
        "case_count": 20,
        "candidate_trace_regression_pass": True,
        "governance_trace_regression_pass": True,
        "answer_mode_regression_pass": True,
        "runtime_retrieval_proven": False,
        "semantic_quality_claim": False,
        "runtime_write": False,
        "next_stage": "expand_semantic_retrieval_only_after_trace_contract_remains_frozen",
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
        "cases_sha256": sha(CASES),
        "execution_sha256": execution_hash,
        "validation_sha256": validation_hash,
        "report_sha256": report_hash,
    }
    manifest_hash = write_json(MANIFEST, manifest)
    outcome = {
        "schema_version": 1,
        "outcome_id": PREFIX + "-outcome",
        "status": "PASS_TRACE_REGRESSION",
        "candidate_trace_regression_pass": True,
        "governance_trace_regression_pass": True,
        "runtime_retrieval_proven": False,
        "runtime_write": False,
        "candidate_or_network_modified": False,
        "next_stage": "semantic_retrieval_comparison_with_trace_contract_unchanged",
    }
    outcome_hash = write_json(OUTCOME, outcome)
    audit = {
        "event_id": PREFIX + "-audit",
        "event_type": "read_only_runtime_shadow_trace_regression_pass",
        "case_count": 20,
        "source_packet_sha256": sha(PACKET),
        "cases_sha256": sha(CASES),
        "execution_sha256": execution_hash,
        "validation_sha256": validation_hash,
        "report_sha256": report_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "runtime_write": False,
        "candidate_or_network_modified": False,
    }
    audit_hash = write_new(AUDIT, (canonical(audit) + "\n").encode("utf-8"))
    receipt = {
        "schema_version": 1,
        "receipt_id": PREFIX + "-receipt",
        "status": "PASS_TRACE_REGRESSION",
        "artifact_lineage": {
            "runtime_trace_contract_sha256": sha(CONFIG),
            "adapter_sha256": sha(SELF),
            "source_profile_sha256": sha(PROFILE),
            "source_packet_sha256": sha(PACKET),
            "task_sha256": sha(TASK),
            "cases_sha256": sha(CASES),
            "execution_sha256": execution_hash,
            "validation_sha256": validation_hash,
            "report_sha256": report_hash,
            "manifest_sha256": manifest_hash,
            "outcome_sha256": outcome_hash,
            "audit_sha256": audit_hash,
        },
        "candidate_trace_regression_pass": True,
        "governance_trace_regression_pass": True,
        "runtime_retrieval_proven": False,
        "runtime_write": False,
        "commit_or_push_performed": False,
    }
    receipt_hash = write_json(RECEIPT, receipt)
    return {"status": "PASS", "case_count": 20, "receipt_sha256": receipt_hash, "runtime_retrieval_proven": False}


def verify() -> dict[str, Any]:
    if not all(path.is_file() for path in OUTPUTS):
        return {"status": "FAIL", "error": "missing_runtime_shadow_artifact"}
    cases = load(CASES)
    profile, frozen_packet, task = E3.source_values()
    packet = E3.runtime_packet(profile, frozen_packet, task)
    replay = [run_case(case, packet) for case in cases["cases"]]
    execution = load(EXECUTION)
    checks = {
        "execution_replay_exact": replay == execution["results"],
        "execution_packet_hash_current": execution["packet_sha256"] == sha(PACKET),
        "execution_cases_hash_current": execution["cases_sha256"] == sha(CASES),
        "validation_pass": load(VALIDATION)["status"] == "PASS",
        "report_trace_pass": load(REPORT)["governance_trace_regression_pass"] is True,
        "outcome_runtime_closed": load(OUTCOME)["runtime_retrieval_proven"] is False
        and load(OUTCOME)["runtime_write"] is False,
        "audit_single_event": len(AUDIT.read_text(encoding="utf-8").splitlines()) == 1,
        "receipt_status_exact": load(RECEIPT)["status"] == "PASS_TRACE_REGRESSION",
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "check_count": len(checks),
        "passed_count": sum(checks.values()),
        "failed_count": sum(not value for value in checks.values()),
        "checks": checks,
    }


def status() -> dict[str, Any]:
    existing = [path.as_posix() for path in OUTPUTS if path.exists()]
    return {"status": "EXECUTED" if all(path.is_file() for path in OUTPUTS) else "READY" if not existing else "PARTIAL", "existing_outputs": existing}


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
