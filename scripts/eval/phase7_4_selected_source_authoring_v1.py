#!/usr/bin/env python3
"""Author and freeze the deterministic Phase 7.4 selected synthetic sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
CONFIG = ROOT / "crates/eval/config"
DATASETS = ROOT / "crates/eval/datasets"
PATTERN = DATASETS / "pattern_extraction"
PHASE_DATA = DATASETS / "phase7_4"
REPORTS = ROOT / "crates/eval/reports"
DOCS = ROOT / "docs"

DOC = DOCS / "eval/PHASE7_4_2_SELECTED_SOURCE_AUTHORING_PROTOCOL.md"
SCHEMA = CONFIG / "phase7_4_source_authoring_case_schema_v1.json"
CONTRACT = CONFIG / "phase7_4_selected_source_authoring_contract_v1.json"
PROTOCOL = CONFIG / "phase7_4_offline_retrieval_evaluation_protocol_v1.json"
PLAN = PHASE_DATA / "phase7_4_selected_source_authoring_plan_v1.json"
STATE_V6 = PATTERN / "phase7_4_stage_state_v6.json"
READINESS_V6 = REPORTS / "phase7_4_readiness_v6.json"
CONTRACT_RECEIPT = REPORTS / "phase7_4_selected_source_authoring_contract_receipt_v1.json"

DATASET = PHASE_DATA / "phase7_4_selected_source_cases_v1.json"
FIXTURES = REPORTS / "phase7_4_selected_source_authoring_fixtures_v1.json"
MANIFEST = REPORTS / "phase7_4_selected_source_authoring_manifest_v1.json"
OUTCOME = REPORTS / "phase7_4_selected_source_authoring_outcome_v1.json"
AUDIT = REPORTS / "phase7_4_selected_source_authoring_audit_v1.jsonl"
STATE_V7 = PATTERN / "phase7_4_stage_state_v7.json"
READINESS_V7 = REPORTS / "phase7_4_readiness_v7.json"
RECEIPT = REPORTS / "phase7_4_selected_source_authoring_receipt_v1.json"

ENTRY_HEAD = "07d575f09964153432461630be48f44c6c9568af"
ENTRY = "phase7_4_selected_source_authoring_contract_frozen_source_authoring_authorized"
AUTHORIZED = "author_phase7_4_selected_source_cases_v1"
NEXT = "freeze_phase7_4_query_blind_atomic_segmentation_protocol_v1"

EXPECTED = {
    DOC: "3d74f71073702db6f6eac073108ac17efedc26e449beca0f20293ab55849276a",
    SCHEMA: "4ff8342c706bd779e761ce7278556e173c7b8b612cc7150eea23deffbb346630",
    CONTRACT: "d0b7b46c07f946a27ce411d5fc658586563ca4e4001ab4fd607ccb61fa68cc24",
    PROTOCOL: "adc48017a40a1ae7685ce5b8868f2bdff623cf845aa845c8ca7e7986ecdac8fb",
    PLAN: "88b0c0f338a6e5037a81eacc37470a67c4953fced73efb41cc5bc8964474ccdd",
    STATE_V6: "90f5ccccd1192386eda0998010fd0b8f5eb5c669200f1d6c24cf5f6cda7e9825",
    READINESS_V6: "ad39b8a759e1828b75382f9c2c7504d17fcde9758c6719f1914f550e73a85051",
    CONTRACT_RECEIPT: "7b29c28b16f81b873658d1655d22a39f893fdca40fa4bdddbf17f0ce0bf2869b",
}

OUTPUTS = [
    DATASET,
    FIXTURES,
    MANIFEST,
    OUTCOME,
    AUDIT,
    STATE_V7,
    READINESS_V7,
    RECEIPT,
]


DOMAIN_VARIANTS: dict[str, list[dict[str, str]]] = {
    "software_delivery": [
        {
            "subject": "Lumen Deployment",
            "actor": "Rowan Release Team",
            "old": "Batch Lane",
            "new": "Canary Lane",
            "metric": "rollback incidents",
            "constraint": "a two-hour maintenance window",
        },
        {
            "subject": "Juniper Mobile",
            "actor": "Amber Delivery Group",
            "old": "Monthly Bundle",
            "new": "Staged Ring",
            "metric": "crash reports",
            "constraint": "a limited beta cohort",
        },
        {
            "subject": "Nimbus Firmware",
            "actor": "Cedar Device Crew",
            "old": "Fleet Push",
            "new": "Segmented Push",
            "metric": "recovery events",
            "constraint": "an overnight device window",
        },
    ],
    "data_operations": [
        {
            "subject": "Harbor Pipeline",
            "actor": "Quartz Data Crew",
            "old": "Nightly Rebuild",
            "new": "Incremental Checkpoint",
            "metric": "late records",
            "constraint": "a six-hour freshness target",
        },
        {
            "subject": "Mosaic Ledger",
            "actor": "Indigo Quality Unit",
            "old": "Full Scan",
            "new": "Change Scan",
            "metric": "duplicate rows",
            "constraint": "a fixed compute quota",
        },
        {
            "subject": "Tide Catalog",
            "actor": "Olive Metadata Team",
            "old": "Manual Merge",
            "new": "Validated Merge",
            "metric": "schema mismatches",
            "constraint": "a daily publication cutoff",
        },
    ],
    "customer_support": [
        {
            "subject": "Ember Support Queue",
            "actor": "Mica Service Team",
            "old": "Scripted Triage",
            "new": "Context Review",
            "metric": "reopened tickets",
            "constraint": "a ten-minute first response target",
        },
        {
            "subject": "Pine Account Desk",
            "actor": "Coral Care Group",
            "old": "Single Reply",
            "new": "Follow-up Loop",
            "metric": "repeat contacts",
            "constraint": "a weekday staffing cap",
        },
        {
            "subject": "Vale Incident Line",
            "actor": "Silver Response Unit",
            "old": "Generic Macro",
            "new": "Issue Checklist",
            "metric": "escalation requests",
            "constraint": "a rotating on-call schedule",
        },
    ],
    "procurement": [
        {
            "subject": "Alder Sourcing",
            "actor": "Cobalt Buying Group",
            "old": "Lowest-Bid Route",
            "new": "Verified-Service Route",
            "metric": "emergency purchases",
            "constraint": "a quarterly budget ceiling",
        },
        {
            "subject": "Birch Vendor Desk",
            "actor": "Saffron Contract Team",
            "old": "Annual Bundle",
            "new": "Usage Schedule",
            "metric": "unused licenses",
            "constraint": "a one-year commitment limit",
        },
        {
            "subject": "Delta Supply Board",
            "actor": "Teal Review Panel",
            "old": "Single Supplier",
            "new": "Qualified Pair",
            "metric": "delivery exceptions",
            "constraint": "a fourteen-day lead time",
        },
    ],
    "team_process": [
        {
            "subject": "Willow Workflow",
            "actor": "Opal Coordination Team",
            "old": "Single-Owner Handoff",
            "new": "Paired Handoff",
            "metric": "missed handoffs",
            "constraint": "a distributed workday",
        },
        {
            "subject": "Kite Planning Board",
            "actor": "Marble Program Group",
            "old": "Weekly Batch Review",
            "new": "Daily Triage",
            "metric": "blocked tasks",
            "constraint": "a thirty-minute meeting budget",
        },
        {
            "subject": "Brook Hiring Loop",
            "actor": "Copper People Team",
            "old": "Sequential Interview",
            "new": "Parallel Panel",
            "metric": "late decisions",
            "constraint": "a five-day candidate window",
        },
    ],
    "research_planning": [
        {
            "subject": "Cirrus Study",
            "actor": "Flint Research Unit",
            "old": "Single-Pass Review",
            "new": "Replicated Review",
            "metric": "measurement variance",
            "constraint": "a twelve-session sample",
        },
        {
            "subject": "Orchid Trial",
            "actor": "Slate Methods Group",
            "old": "Open Comparison",
            "new": "Blocked Comparison",
            "metric": "unexplained spread",
            "constraint": "a fixed instrument schedule",
        },
        {
            "subject": "Beacon Survey",
            "actor": "Ivory Analysis Team",
            "old": "Convenience Sample",
            "new": "Balanced Sample",
            "metric": "response imbalance",
            "constraint": "a limited outreach window",
        },
    ],
    "personal_workflow": [
        {
            "subject": "Meadow Workspace",
            "actor": "Sable Planning Profile",
            "old": "Weekly Batch",
            "new": "Daily Review",
            "metric": "overdue tasks",
            "constraint": "a forty-minute morning block",
        },
        {
            "subject": "Aurora Notes",
            "actor": "Umber Study Profile",
            "old": "Topic Folders",
            "new": "Linked Notes",
            "metric": "missed references",
            "constraint": "an offline-first routine",
        },
        {
            "subject": "Fern Travel Plan",
            "actor": "Pearl Itinerary Profile",
            "old": "Fixed Schedule",
            "new": "Flexible Blocks",
            "metric": "rescheduled stops",
            "constraint": "a variable arrival window",
        },
    ],
}


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


def validate_schema_definition() -> bool:
    try:
        Draft202012Validator.check_schema(load(SCHEMA))
        return True
    except Exception:
        return False


def tagged_profile(case_plan: dict[str, Any]) -> dict[str, str]:
    base = DOMAIN_VARIANTS[case_plan["domain"]][case_plan["scenario_variant"] - 1]
    tag = case_plan["case_id"].removeprefix("p74-").upper()
    profile = dict(base)
    for key in ["subject", "actor", "old", "new"]:
        profile[key] = f"{profile[key]} {tag}"
    profile["tag"] = tag
    profile["baseline"] = str(8 + case_plan["scenario_variant"])
    profile["improved"] = str(3 + case_plan["scenario_variant"])
    return profile


def material_temporal(p: dict[str, str]) -> dict[str, Any]:
    events = [
        ("decision", [1, 2, 3], f"{p['actor']} selected {p['old']} for {p['subject']} while {p['constraint']} was the active operating limit."),
        ("observation", [1, 3], f"The first monitoring window for {p['subject']} using {p['old']} recorded {p['baseline']} {p['metric']}."),
        ("revision", [1, 2], f"A later planning record for {p['subject']} replaced the earlier limit with a stricter service objective."),
        ("action", [1, 2, 4], f"{p['actor']} ran {p['new']} on {p['subject']} under the revised objective without changing the observation window."),
        ("outcome", [1, 4], f"The verified trial for {p['new']} recorded {p['improved']} {p['metric']} for {p['subject']}."),
        ("decision", [1, 2, 4], f"The most recent decision record made {p['new']} the current approach for {p['subject']} and archived the earlier choice."),
    ]
    evidence = [
        ([1], [1, 2, 3], "synthetic_decision_record", f"Initial decision: {p['subject']} will use {p['old']} because {p['constraint']} is currently binding."),
        ([2], [1, 3], "synthetic_system_log", f"Baseline log: {p['old']} produced {p['baseline']} {p['metric']} during the first complete window for {p['subject']}."),
        ([3], [1, 2], "synthetic_observation", f"Planning update: the operating objective for {p['subject']} changed after the baseline window; the initial constraint is no longer current."),
        ([4], [1, 2, 4], "synthetic_system_log", f"Trial log: {p['new']} was activated for {p['subject']} with the same measurement interval and no skipped observations."),
        ([5], [1, 4], "synthetic_outcome_record", f"Outcome record: the {p['new']} window ended with {p['improved']} {p['metric']}, below the earlier {p['old']} count."),
        ([6], [1, 2, 4], "synthetic_decision_record", f"Current decision: retain {p['new']} for {p['subject']}; keep {p['old']} only in the archived rollback instructions."),
        ([1, 6], [1, 3], "synthetic_unverified_report", f"An undated handoff note still calls {p['old']} the standard path for {p['subject']}, but it does not cite the later trial."),
        ([3], [2, 3], "synthetic_observation", f"A training index repeats both approach names for {p['actor']} and does not state which one is current for {p['subject']}."),
    ]
    memories = [
        (f"{p['subject']} began with {p['old']} under {p['constraint']}", f"The baseline window recorded {p['baseline']} {p['metric']}; this snapshot predates the later objective change", [1, 2], [1, 2]),
        (f"{p['new']} is the latest recorded approach for {p['subject']}", f"Its verified window ended with {p['improved']} {p['metric']} and the subsequent decision retained it", [5, 6], [5, 6]),
        (f"the operating objective changed before {p['new']} was tried", f"The trial used the revised objective and preserved the measurement interval", [3, 4], [3, 4]),
        (f"{p['old']} remains the standard approach for {p['subject']}", f"An undated handoff repeats the old name even though it does not cite the later decision", [1, 7], [1, 6]),
        (f"{p['new']} increased {p['metric']} for {p['subject']}", f"This note claims the trial was worse than baseline and gives no matching outcome record", [4], [4]),
        (f"both approach names appear in {p['actor']}'s training index", f"The index explains terminology but does not identify a current choice for {p['subject']}", [8], [3]),
        (f"{p['subject']} moved from {p['old']} to {p['new']}", f"The earlier decision and the latest retained decision describe different points in the timeline", [1, 6], [1, 6]),
        (f"future performance of {p['new']} outside the observed window is not yet measured", f"The verified result covers one bounded trial and should not be expanded beyond it", [5], [5]),
        (f"recent dated decisions should supersede undated handoff notes for {p['subject']}", f"The latest decision explicitly archives the earlier approach", [6, 7], [6]),
        (f"{p['actor']} never ran {p['new']} on {p['subject']}", f"This snapshot overlooks the preserved trial log and records only the initial plan", [1, 4], [1, 4]),
    ]
    return {"query": f"Which approach is currently recorded for {p['subject']} after the latest verified outcome, and which records establish that state?", "events": events, "evidence": evidence, "memories": memories}


def material_contradiction(p: dict[str, str]) -> dict[str, Any]:
    events = [
        ("decision", [1, 2, 3, 4], f"{p['actor']} approved a controlled comparison of {p['old']} and {p['new']} for {p['subject']}."),
        ("statement", [1, 2, 4], f"A direct operator statement said {p['new']} reduced {p['metric']} for {p['subject']}."),
        ("observation", [1, 3, 4], f"The complete system log measured {p['baseline']} {p['metric']} with {p['old']} and {p['improved']} with {p['new']}."),
        ("statement", [1, 4], f"An unverified summary instead claimed that {p['new']} raised {p['metric']} above baseline."),
        ("revision", [1, 2, 3, 4], f"A provenance audit found that the unverified summary mixed a different window into the {p['subject']} comparison."),
        ("decision", [1, 2, 4], f"The adjudicated operating note retained {p['new']} for {p['subject']} and marked the mixed-window summary unresolved."),
    ]
    evidence = [
        ([1], [1, 2, 3, 4], "synthetic_decision_record", f"Comparison plan: measure {p['old']} and {p['new']} for {p['subject']} under the same {p['constraint']}."),
        ([2], [1, 2, 4], "synthetic_direct_statement", f"Operator statement: {p['new']} produced fewer {p['metric']} than {p['old']} for {p['subject']}."),
        ([3], [1, 3, 4], "synthetic_system_log", f"Complete log: {p['old']} recorded {p['baseline']} {p['metric']}; {p['new']} recorded {p['improved']} for the matched window."),
        ([4], [1, 4], "synthetic_unverified_report", f"Unverified summary: {p['new']} allegedly produced {int(p['baseline']) + 3} {p['metric']} for {p['subject']}."),
        ([5], [1, 2, 3, 4], "synthetic_observation", f"Audit note: the higher count came from an unmatched window and cannot be attributed to the controlled {p['new']} run."),
        ([6], [1, 2, 4], "synthetic_decision_record", f"Operating decision: retain {p['new']} for {p['subject']} on the matched evidence; keep the conflicting summary as unresolved provenance."),
        ([3, 5], [1, 3], "synthetic_outcome_record", f"Recomputed outcome: after excluding the unmatched window, the logged comparison remains {p['baseline']} versus {p['improved']} {p['metric']}."),
        ([4], [2, 4], "synthetic_unverified_report", f"A copied message repeats the higher count but supplies no timestamp, run identifier, or complete log for {p['subject']}."),
    ]
    memories = [
        (f"the matched log favors {p['new']} for {p['subject']}", f"It records {p['improved']} {p['metric']} against {p['baseline']} for {p['old']}", [1, 3], [1, 3]),
        (f"an unverified summary says {p['new']} was worse", f"The summary reports a higher count but provides no matched run identifier", [4, 8], [4]),
        (f"the provenance audit traced the high count to another window", f"That finding prevents the copied summary from overturning the complete system log", [5, 7], [5]),
        (f"{p['actor']} retained {p['new']} after reviewing the conflict", f"The decision cites matched evidence and leaves the contrary summary unresolved", [6], [6]),
        (f"all records agree that {p['new']} reduced {p['metric']}", f"This overstates agreement because two unverified records make the opposite claim", [2, 4], [2, 4]),
        (f"the higher count conclusively proves {p['new']} failed", f"This interpretation ignores the audit finding that the count came from an unmatched window", [4, 5], [4, 5]),
        (f"the direct statement and complete log point in the same direction", f"Both associate {p['new']} with fewer {p['metric']} for the bounded comparison", [2, 3], [2, 3]),
        (f"the conflicting copied message lacks timestamp and run identity", f"Its provenance remains weaker than the complete matched record", [8], [4]),
        (f"future windows may differ from the controlled comparison", f"The available evidence supports the tested condition rather than every possible setting", [1, 7], [1, 5]),
        (f"{p['old']} is the retained operating choice for {p['subject']}", f"This snapshot reverses the adjudicated decision while citing only the initial comparison plan", [1, 6], [1, 6]),
    ]
    return {"query": f"Given the conflicting records for {p['subject']}, what conclusion about {p['new']} is supported by the strongest matched provenance?", "events": events, "evidence": evidence, "memories": memories}


def material_preference(p: dict[str, str]) -> dict[str, Any]:
    events = [
        ("statement", [1, 2, 3], f"{p['actor']} initially stated a preference for {p['old']} on {p['subject']} because of {p['constraint']}."),
        ("outcome", [1, 3], f"A complete window using {p['old']} recorded {p['baseline']} {p['metric']} for {p['subject']}."),
        ("action", [1, 2, 4], f"{p['actor']} agreed to a bounded trial of {p['new']} without changing the measurement window."),
        ("outcome", [1, 4], f"The trial using {p['new']} recorded {p['improved']} {p['metric']} and met the active constraint."),
        ("revision", [1, 2, 3, 4], f"After reviewing the outcome, {p['actor']} explicitly revised the saved preference from {p['old']} to {p['new']}."),
        ("decision", [1, 2, 4], f"The current preference record for {p['subject']} was saved as {p['new']} with the trial outcome attached."),
    ]
    evidence = [
        ([1], [1, 2, 3], "synthetic_direct_statement", f"Initial preference: {p['actor']} favors {p['old']} for {p['subject']} while {p['constraint']} remains important."),
        ([2], [1, 3], "synthetic_outcome_record", f"Old-method outcome: {p['old']} ended with {p['baseline']} {p['metric']} for {p['subject']}."),
        ([3], [1, 2, 4], "synthetic_decision_record", f"Trial authorization: test {p['new']} for one matched window before changing any saved preference."),
        ([4], [1, 4], "synthetic_system_log", f"New-method log: {p['new']} ended with {p['improved']} {p['metric']} for {p['subject']}."),
        ([5], [1, 2, 3, 4], "synthetic_direct_statement", f"Preference revision: after the matched result, {p['actor']} now favors {p['new']} rather than {p['old']} for {p['subject']}."),
        ([6], [1, 2, 4], "synthetic_decision_record", f"Current preference state: {p['new']} is saved for {p['subject']}; the earlier {p['old']} note is historical."),
        ([1, 6], [1, 3], "synthetic_unverified_report", f"An old summary still says {p['old']} is preferred, but it has no revision timestamp and omits the trial outcome."),
        ([4], [1, 4], "synthetic_observation", f"The matched outcome covers the active constraint and does not establish a preference for unrelated settings."),
    ]
    memories = [
        (f"{p['actor']} originally preferred {p['old']} for {p['subject']}", f"That preference was recorded before the matched trial and remains useful as historical context", [1], [1]),
        (f"{p['new']} produced {p['improved']} {p['metric']} in the bounded trial", f"The result was reviewed before the preference record changed", [3, 4], [3, 4]),
        (f"the saved preference now names {p['new']} for {p['subject']}", f"The explicit revision and current state both distinguish it from the earlier note", [5, 6], [5, 6]),
        (f"{p['old']} is still the current preference", f"An undated summary repeats the initial choice while omitting the later revision", [1, 7], [1, 6]),
        (f"the trial automatically changed every future preference", f"The evidence only records a bounded revision for {p['subject']} under the active constraint", [4, 8], [4]),
        (f"the revised preference lacks any observed outcome", f"This snapshot overlooks the matched system log attached to the revision", [4, 5], [4, 5]),
        (f"the old outcome helps explain why the preference changed", f"It records {p['baseline']} {p['metric']} before the {p['new']} trial", [2, 5], [2, 5]),
        (f"the new preference should be applied only to the recorded setting", f"The scope note does not support unrelated environments", [6, 8], [6]),
        (f"dated preference revisions supersede undated historical summaries", f"The current state includes a revision timestamp and linked outcome", [6, 7], [6]),
        (f"{p['actor']} rejected {p['new']} after the trial", f"This statement conflicts with the explicit revision that names {p['new']}", [4, 5], [4, 5]),
    ]
    return {"query": f"What is {p['actor']}'s current recorded preference for {p['subject']}, and what changed it from the earlier choice?", "events": events, "evidence": evidence, "memories": memories}


def material_failure(p: dict[str, str]) -> dict[str, Any]:
    events = [
        ("decision", [1, 2, 3], f"{p['actor']} planned to use {p['old']} for {p['subject']} under {p['constraint']}."),
        ("action", [1, 2, 3], f"The planned {p['old']} action was executed on {p['subject']} with the standard checklist."),
        ("outcome", [1, 3], f"The action ended with {int(p['baseline']) + 4} {p['metric']} and missed the operating target."),
        ("observation", [1, 2, 3], f"Inspection linked the failure to an interaction between {p['old']} and {p['constraint']}, not to a missing checklist step."),
        ("action", [1, 2, 4], f"{p['actor']} applied {p['new']} as a bounded mitigation while preserving the same target."),
        ("outcome", [1, 4], f"The mitigation window ended with {p['improved']} {p['metric']} and no repeat of the observed failure mode."),
    ]
    evidence = [
        ([1], [1, 2, 3], "synthetic_decision_record", f"Execution plan: apply {p['old']} to {p['subject']} while operating under {p['constraint']}."),
        ([2], [1, 2, 3], "synthetic_system_log", f"Action log: every standard step for {p['old']} completed before the outcome was measured."),
        ([3], [1, 3], "synthetic_outcome_record", f"Failure outcome: {p['old']} ended with {int(p['baseline']) + 4} {p['metric']} and breached the target for {p['subject']}."),
        ([4], [1, 2, 3], "synthetic_observation", f"Inspection finding: the observed failure mode occurs when {p['old']} meets {p['constraint']}; no omitted step was found."),
        ([5], [1, 2, 4], "synthetic_decision_record", f"Mitigation record: use {p['new']} for the next bounded window and keep the same target."),
        ([6], [1, 4], "synthetic_outcome_record", f"Mitigation outcome: {p['new']} ended with {p['improved']} {p['metric']} and the prior failure mode did not recur."),
        ([3, 4], [1, 3], "synthetic_unverified_report", f"A brief summary blames an omitted checklist step, although the complete action log shows every step completed."),
        ([6], [1, 4], "synthetic_observation", f"The mitigation result covers one matched window and has not been tested outside {p['constraint']}."),
    ]
    memories = [
        (f"{p['old']} was executed with every checklist step for {p['subject']}", f"The run still ended with {int(p['baseline']) + 4} {p['metric']}", [1, 2, 3], [1, 2, 3]),
        (f"the observed failure involved {p['old']} under {p['constraint']}", f"Inspection found an interaction with the constraint rather than a missing step", [3, 4], [3, 4]),
        (f"{p['new']} was the bounded mitigation after the failure", f"Its matched outcome recorded {p['improved']} {p['metric']} without the prior failure mode", [5, 6], [5, 6]),
        (f"an omitted checklist step caused the failure", f"A brief summary says this even though the complete action log records every step", [2, 7], [2, 4]),
        (f"{p['old']} should never be used in any setting", f"The available diagnosis is limited to its interaction with the recorded constraint", [4, 8], [4, 6]),
        (f"{p['new']} permanently eliminates all {p['metric']}", f"The evidence covers one bounded mitigation window rather than every future run", [6, 8], [6]),
        (f"future runs matching {p['constraint']} should avoid the diagnosed interaction", f"The inspection and mitigation outcome provide the grounded basis for that caution", [4, 6], [4, 6]),
        (f"the failure happened before the mitigation decision", f"The event order separates diagnosis from the later {p['new']} outcome", [3, 5], [3, 5]),
        (f"failure records should preserve both execution completeness and context", f"Removing either detail would turn the diagnosis into an unsupported generalization", [2, 4], [2, 4]),
        (f"the {p['old']} run met the operating target", f"This snapshot conflicts with the recorded outcome of {int(p['baseline']) + 4} {p['metric']}", [3], [3]),
    ]
    return {"query": f"Which evidence from {p['subject']} grounds a future failure-avoidance lesson under {p['constraint']}, without overgeneralizing beyond the observed run?", "events": events, "evidence": evidence, "memories": memories}


def material_causal(p: dict[str, str]) -> dict[str, Any]:
    events = [
        ("observation", [1, 3], f"An observational window linked {p['old']} with {p['baseline']} {p['metric']} for {p['subject']}."),
        ("observation", [1, 2], f"Reviewers found that workload changed during the same window, leaving the initial association confounded."),
        ("action", [1, 2, 4], f"{p['actor']} introduced {p['new']} while holding workload and {p['constraint']} stable."),
        ("outcome", [1, 4], f"During the controlled intervention, {p['metric']} fell from {p['baseline']} to {p['improved']} for {p['subject']}."),
        ("action", [1, 2, 3, 4], f"A planned reversal removed {p['new']} and restored {p['old']} while the controls remained stable."),
        ("outcome", [1, 3], f"After reversal, {p['metric']} returned to {p['baseline']}, completing the bounded causal check."),
    ]
    evidence = [
        ([1], [1, 3], "synthetic_observation", f"Observational record: {p['old']} coincided with {p['baseline']} {p['metric']} for {p['subject']}."),
        ([2], [1, 2], "synthetic_observation", f"Confound note: workload changed during the observational window, so timing alone cannot identify a cause."),
        ([3], [1, 2, 4], "synthetic_decision_record", f"Intervention plan: introduce {p['new']} while holding workload and {p['constraint']} constant."),
        ([4], [1, 4], "synthetic_system_log", f"Intervention log: with controls stable, {p['metric']} fell from {p['baseline']} to {p['improved']} after {p['new']} began."),
        ([5], [1, 2, 3, 4], "synthetic_decision_record", f"Reversal plan: remove {p['new']}, restore {p['old']}, and preserve the same controls for one window."),
        ([6], [1, 3], "synthetic_outcome_record", f"Reversal outcome: {p['metric']} returned to {p['baseline']} after {p['new']} was removed."),
        ([1, 2], [1, 2, 3], "synthetic_unverified_report", f"A summary attributes the original {p['baseline']} count entirely to {p['old']} without mentioning the workload change."),
        ([3, 6], [1, 3, 4], "synthetic_observation", f"Scope note: the intervention and reversal identify an effect for the controlled setting, not for every possible workload."),
    ]
    memories = [
        (f"the initial association between {p['old']} and {p['metric']} was confounded", f"Workload changed during the same observational window", [1, 2], [1, 2]),
        (f"{p['new']} was introduced while workload and the active constraint stayed stable", f"The controlled log then recorded a decrease from {p['baseline']} to {p['improved']}", [3, 4], [3, 4]),
        (f"removing {p['new']} restored the earlier {p['metric']} count", f"The planned reversal strengthens the bounded causal interpretation", [5, 6], [5, 6]),
        (f"timing alone proves {p['old']} caused every observed count", f"This claim omits the documented workload confound", [1, 7], [1, 2]),
        (f"the controlled intervention supports an effect of {p['new']} for {p['subject']}", f"The reversal supplies a second direction of change under stable controls", [4, 6], [4, 6]),
        (f"{p['new']} will reduce {p['metric']} under any workload", f"The scope record limits the finding to the controlled setting", [4, 8], [4, 6]),
        (f"workload was held stable only during the intervention and reversal", f"That distinction separates the controlled evidence from the initial observation", [2, 3, 5], [2, 3, 5]),
        (f"the reversal never restored {p['old']}", f"This statement conflicts with the planned reversal and recorded return to baseline", [5, 6], [5, 6]),
        (f"causal summaries should retain the confound, intervention, and reversal sequence", f"Dropping any part changes the strength or scope of the conclusion", [2, 4, 6], [2, 4, 6]),
        (f"the available records show only an unexplained correlation", f"This snapshot ignores both controlled directions of change", [1, 4, 6], [1, 4, 6]),
    ]
    return {"query": f"Which records for {p['subject']} support a bounded causal effect of {p['new']} on {p['metric']}, rather than a correlation alone?", "events": events, "evidence": evidence, "memories": memories}


def material_multi_entity(p: dict[str, str]) -> dict[str, Any]:
    events = [
        ("decision", [1, 2, 3], f"{p['actor']} assigned {p['old']} to {p['subject']} for the initial matched window."),
        ("outcome", [1, 3], f"The {p['subject']} window using {p['old']} recorded {p['baseline']} {p['metric']}."),
        ("action", [1, 2, 4], f"{p['actor']} then assigned {p['new']} to the same {p['subject']} without changing {p['constraint']}."),
        ("outcome", [1, 4], f"The {p['subject']} window using {p['new']} recorded {p['improved']} {p['metric']}."),
        ("observation", [2, 3], f"A separate training exercise for {p['actor']} mentioned {p['old']} and a higher count but did not involve {p['subject']}."),
        ("decision", [1, 2, 4], f"The current subject-specific record retained {p['new']} for {p['subject']} based on its own outcome."),
    ]
    evidence = [
        ([1], [1, 2, 3], "synthetic_decision_record", f"Assignment record: {p['actor']} placed {p['old']} on {p['subject']} for the initial window."),
        ([2], [1, 3], "synthetic_system_log", f"Subject log: {p['subject']} with {p['old']} recorded {p['baseline']} {p['metric']}."),
        ([3], [1, 2, 4], "synthetic_decision_record", f"Reassignment record: {p['new']} replaced {p['old']} on {p['subject']} under the same constraint."),
        ([4], [1, 4], "synthetic_outcome_record", f"Subject outcome: {p['subject']} with {p['new']} recorded {p['improved']} {p['metric']}."),
        ([5], [2, 3], "synthetic_observation", f"Training record: {p['actor']} practiced terminology for {p['old']}; this exercise has no {p['subject']} run identifier."),
        ([6], [1, 2, 4], "synthetic_decision_record", f"Current subject decision: retain {p['new']} for {p['subject']} after its own matched outcome."),
        ([4, 5], [1, 2, 3, 4], "synthetic_unverified_report", f"A merged summary assigns the training exercise's higher count to {p['subject']}, despite the different entity set."),
        ([2, 4], [1, 3, 4], "synthetic_observation", f"Entity audit: both valid outcome rows name {p['subject']}; the training row names {p['actor']} and {p['old']} only."),
    ]
    memories = [
        (f"{p['old']} was initially assigned to {p['subject']} by {p['actor']}", f"The subject-specific log recorded {p['baseline']} {p['metric']}", [1, 2], [1, 2]),
        (f"{p['new']} later replaced {p['old']} on {p['subject']}", f"The subject-specific outcome recorded {p['improved']} {p['metric']}", [3, 4], [3, 4]),
        (f"the current decision for {p['subject']} retains {p['new']}", f"It cites the outcome carrying the same subject and approach identities", [4, 6], [4, 6]),
        (f"the training exercise's higher count belongs to {p['subject']}", f"A merged summary makes this attribution even though the training row lacks the subject identifier", [5, 7], [5]),
        (f"the entity audit separates subject outcomes from actor training", f"Only the matched outcome rows include {p['subject']}", [7, 8], [4, 5]),
        (f"{p['actor']} itself recorded {p['improved']} {p['metric']}", f"This snapshot confuses the operating actor with the measured subject", [4, 5], [4, 5]),
        (f"{p['old']} and {p['new']} are distinct approach entities", f"Their assignments should not be merged merely because one training note names both terms", [3, 5], [3, 5]),
        (f"{p['subject']} never used {p['new']}", f"This statement conflicts with the reassignment and subject-specific outcome", [3, 4], [3, 4]),
        (f"entity-qualified retrieval should keep run identities attached to counts", f"The audit demonstrates the harm of moving a count across entities", [7, 8], [4, 5]),
        (f"the two valid subject windows changed from {p['baseline']} to {p['improved']} {p['metric']}", f"Both rows name {p['subject']} and their respective approaches", [2, 4], [2, 4]),
    ]
    return {"query": f"Which approach and outcome belong specifically to {p['subject']}, rather than to the separate {p['actor']} training record?", "events": events, "evidence": evidence, "memories": memories}


def material_uncertainty(p: dict[str, str]) -> dict[str, Any]:
    events = [
        ("decision", [1, 2, 4], f"{p['actor']} approved a two-window pilot of {p['new']} for {p['subject']} under {p['constraint']}."),
        ("outcome", [1, 4], f"The first pilot window recorded {p['improved']} {p['metric']} for {p['subject']}."),
        ("observation", [1, 4], f"The second pilot window lost part of its measurement record and cannot produce a complete count."),
        ("statement", [1, 2, 4], f"An unverified message described {p['new']} as universally successful after seeing only the first window."),
        ("observation", [1, 2, 3, 4], f"Reviewers noted that the pilot lacks replication and that the available {p['old']} baseline used a different window."),
        ("decision", [1, 2, 4], f"The decision record kept {p['new']} in limited pilot status and declined a broad replacement of {p['old']}."),
    ]
    evidence = [
        ([1], [1, 2, 4], "synthetic_decision_record", f"Pilot plan: evaluate {p['new']} for two complete windows before replacing {p['old']} on {p['subject']}."),
        ([2], [1, 4], "synthetic_outcome_record", f"First window: {p['new']} recorded {p['improved']} {p['metric']} for {p['subject']}."),
        ([3], [1, 4], "synthetic_system_log", f"Second window: the measurement stream is incomplete, so no full {p['metric']} count is available."),
        ([4], [1, 2, 4], "synthetic_unverified_report", f"Unverified message: {p['new']} is declared successful for every future use after the first window."),
        ([5], [1, 2, 3, 4], "synthetic_observation", f"Review note: one positive window and one incomplete window do not satisfy the planned replication requirement."),
        ([5], [1, 3], "synthetic_observation", f"Baseline note: the available {p['old']} count came from a different observation window and is not a matched comparator."),
        ([6], [1, 2, 4], "synthetic_decision_record", f"Current decision: continue a limited {p['new']} pilot; do not claim broad superiority or replace {p['old']} yet."),
        ([2, 3], [1, 4], "synthetic_observation", f"Evidence summary: the pilot contains one complete positive result and one result that is not assessable."),
    ]
    memories = [
        (f"the first {p['new']} window recorded {p['improved']} {p['metric']}", f"This is a complete positive observation for {p['subject']}", [1, 2], [1, 2]),
        (f"the second {p['new']} window is not assessable", f"Its measurement stream is incomplete and cannot supply a full count", [3, 8], [3]),
        (f"the planned replication requirement has not been met", f"One complete result and one incomplete result do not establish a repeated effect", [5, 8], [5]),
        (f"{p['new']} is universally successful for {p['subject']}", f"An unverified message makes this claim after observing only the first window", [2, 4], [2, 4]),
        (f"the available {p['old']} count is a matched baseline", f"The review note instead says it came from a different window", [6], [5]),
        (f"the current decision keeps {p['new']} in limited pilot status", f"It explicitly declines broad replacement of {p['old']}", [7], [6]),
        (f"the pilot proves {p['new']} is worse than {p['old']}", f"No matched comparison or complete second window supports that conclusion", [3, 6], [3, 5]),
        (f"a calibrated summary should report one positive and one incomplete result", f"It should preserve the missing replication rather than convert it into success or failure", [5, 8], [5]),
        (f"additional matched windows are required before a broad preference changes", f"The pilot plan and current decision retain that boundary", [1, 7], [1, 6]),
        (f"the second window confirmed the first result", f"This snapshot treats an incomplete measurement stream as a successful replication", [2, 3], [2, 3]),
    ]
    return {"query": f"What is the strongest warranted conclusion about {p['new']} for {p['subject']} given one complete result, one incomplete window, and no matched baseline?", "events": events, "evidence": evidence, "memories": memories}


def material_adversarial(p: dict[str, str]) -> dict[str, Any]:
    events = [
        ("decision", [1, 2, 3], f"An archived plan used {p['old']} for {p['subject']} and repeated the formal {p['metric']} target."),
        ("observation", [2, 3, 4], f"A terminology exercise for {p['actor']} repeated {p['subject']}, {p['new']}, and {p['metric']} without recording an operating choice."),
        ("statement", [1, 2, 3, 4], f"A later direct note described moving {p['subject']} from the single pass to the gradual path under {p['constraint']}."),
        ("outcome", [1, 4], f"The gradual-path run ended with {p['improved']} {p['metric']} for {p['subject']}."),
        ("decision", [1, 2, 4], f"The current decision retained the gradual path, whose formal catalog name is {p['new']}, for {p['subject']}."),
        ("observation", [2, 3, 4], f"A separate training record repeated every catalog term and metric but carried no {p['subject']} run identity."),
    ]
    evidence = [
        ([1], [1, 2, 3], "synthetic_decision_record", f"Archived operating plan for {p['subject']}: use {p['old']} and track the {p['metric']} target under {p['constraint']}."),
        ([2], [2, 3, 4], "synthetic_observation", f"Keyword exercise: {p['subject']} {p['new']} {p['metric']} {p['old']} current target; this line is training text, not a decision."),
        ([3], [1, 2, 3, 4], "synthetic_direct_statement", f"Later note: move the subject from the single pass to the gradual path while retaining the same constraint and measurement window."),
        ([4], [1, 4], "synthetic_system_log", f"Gradual-path outcome for {p['subject']}: {p['improved']} {p['metric']} in the complete matched window."),
        ([5], [1, 2, 4], "synthetic_decision_record", f"Current catalog mapping: the gradual path is {p['new']}; retain it for {p['subject']} after the matched outcome."),
        ([6], [2, 3, 4], "synthetic_unverified_report", f"Training-only phrase: current {p['subject']} {p['new']} {p['metric']} {p['old']} target decision outcome, with no run or decision identifier."),
        ([1, 5], [1, 2, 3, 4], "synthetic_observation", f"Timeline index: the archived {p['old']} plan precedes the later gradual-path decision mapped to {p['new']}."),
        ([2, 6], [2, 3, 4], "synthetic_observation", f"Provenance index: the high-overlap keyword lines are training artifacts and do not own an operating decision for {p['subject']}."),
    ]
    memories = [
        (f"current {p['subject']} {p['new']} {p['metric']} {p['old']} target decision outcome", f"This high-overlap snapshot comes from a terminology exercise and has no operating identifier", [2, 8], [2]),
        (f"{p['subject']} moved from the single pass to the gradual path", f"The later catalog mapping identifies that gradual path as {p['new']}", [3, 5], [3, 5]),
        (f"the gradual-path run recorded {p['improved']} {p['metric']}", f"The complete log carries the {p['subject']} run identity", [4], [4]),
        (f"{p['old']} is the archived approach for {p['subject']}", f"Its plan contains many query terms but predates the later mapped decision", [1, 7], [1, 5]),
        (f"the current operating decision retains {p['new']}", f"The decision uses a paraphrase in one record and the formal catalog name in another", [3, 5], [3, 5]),
        (f"a training-only phrase proves {p['new']} is current", f"The phrase repeats all catalog terms but supplies neither run identity nor decision provenance", [6, 8], [6]),
        (f"the archived {p['old']} plan is newer than the gradual-path decision", f"The timeline index records the opposite order", [1, 7], [1, 5]),
        (f"lexical overlap alone cannot establish an operating choice", f"The provenance index marks both high-overlap lines as training artifacts", [2, 6, 8], [2, 6]),
        (f"the relevant outcome uses the paraphrase gradual path", f"Linking it to the catalog mapping reconstructs the {p['new']} evidence without relying on keyword density", [4, 5], [4, 5]),
        (f"{p['subject']} has no recorded outcome for the later approach", f"This snapshot overlooks the complete gradual-path system log", [3, 4], [3, 4]),
    ]
    return {"query": f"What is the current approach for {p['subject']} after the verified {p['metric']} outcome, despite the high-overlap training records?", "events": events, "evidence": evidence, "memories": memories}


MATERIAL_BUILDERS = {
    "temporal_update": material_temporal,
    "contradiction": material_contradiction,
    "preference_evolution": material_preference,
    "failure_learning": material_failure,
    "causal_reasoning": material_causal,
    "multi_entity_reasoning": material_multi_entity,
    "uncertainty_boundary": material_uncertainty,
    "adversarial_lexical_overlap": material_adversarial,
}


def memory_content(kind: str, headline: str, detail: str) -> str:
    labels = {
        "fact": "Recorded fact",
        "preference": "Saved preference",
        "failure": "Failure note",
        "playbook": "Playbook note",
        "state": "State snapshot",
    }
    return f"{labels[kind]}: {headline}. {detail}."


def source_memory_hash(memory: dict[str, Any]) -> str:
    projection = {
        "source_memory_id": memory["source_memory_id"],
        "source_memory_kind": memory["source_memory_kind"],
        "source_memory_content_sha256": memory["source_memory_content_sha256"],
        "source_evidence_ids_sorted": sorted(memory["source_evidence_ids"]),
        "source_event_ids_sorted": sorted(memory["source_event_ids"]),
    }
    return hb(canonical(projection).encode("utf-8"))


def authored_case(case_plan: dict[str, Any]) -> dict[str, Any]:
    p = tagged_profile(case_plan)
    material = MATERIAL_BUILDERS[case_plan["stratum"]](p)
    if not (
        len(material["events"]) == 6
        and len(material["evidence"]) == 8
        and len(material["memories"]) == 10
    ):
        raise RuntimeError("authoring_material_count_failure:" + case_plan["case_id"])

    entity_slots = case_plan["entity_slots"]
    entity_names = [p["subject"], p["actor"], p["old"], p["new"]]
    entities = [
        {"entity_id": slot["entity_id"], "display_name": name}
        for slot, name in zip(entity_slots, entity_names, strict=True)
    ]

    event_slots = case_plan["source_event_slots"]
    events = []
    for slot, (event_type, entity_ordinals, description) in zip(
        event_slots, material["events"], strict=True
    ):
        events.append(
            {
                "source_event_id": slot["source_event_id"],
                "logical_time": slot["logical_time"],
                "entity_ids": [
                    entity_slots[ordinal - 1]["entity_id"]
                    for ordinal in entity_ordinals
                ],
                "event_type": event_type,
                "description": description,
                "description_sha256": hb(description.encode("utf-8")),
            }
        )

    evidence_slots = case_plan["source_evidence_slots"]
    evidence = []
    for slot, (event_ordinals, entity_ordinals, provenance, observed_text) in zip(
        evidence_slots, material["evidence"], strict=True
    ):
        evidence_id = slot["source_evidence_id"]
        evidence.append(
            {
                "source_evidence_id": evidence_id,
                "source_event_ids": [
                    event_slots[ordinal - 1]["source_event_id"]
                    for ordinal in event_ordinals
                ],
                "entity_ids": [
                    entity_slots[ordinal - 1]["entity_id"]
                    for ordinal in entity_ordinals
                ],
                "provenance_kind": provenance,
                "provenance_locator": f"phase7_4_independent_v1:{evidence_id}",
                "observed_text": observed_text,
                "observed_text_sha256": hb(observed_text.encode("utf-8")),
            }
        )

    memory_slots = case_plan["candidate_memory_slots"]
    memories = []
    for slot, (headline, detail, evidence_ordinals, event_ordinals) in zip(
        memory_slots, material["memories"], strict=True
    ):
        content = memory_content(slot["source_memory_kind"], headline, detail)
        memory = {
            "memory_authoring_ordinal": slot["memory_authoring_ordinal"],
            "pool_ordinal": slot["pool_ordinal"],
            "source_memory_id": slot["source_memory_id"],
            "source_memory_kind": slot["source_memory_kind"],
            "source_memory_content": content,
            "source_memory_content_sha256": hb(content.encode("utf-8")),
            "source_memory_sha256": "",
            "source_evidence_ids": [
                evidence_slots[ordinal - 1]["source_evidence_id"]
                for ordinal in evidence_ordinals
            ],
            "source_event_ids": [
                event_slots[ordinal - 1]["source_event_id"]
                for ordinal in event_ordinals
            ],
        }
        memory["source_memory_sha256"] = source_memory_hash(memory)
        memories.append(memory)

    query = material["query"]
    return {
        "schema_version": 1,
        "case_id": case_plan["case_id"],
        "stratum": case_plan["stratum"],
        "domain": case_plan["domain"],
        "scenario_variant": case_plan["scenario_variant"],
        "content_language": "en",
        "query": {
            "query_id": case_plan["query_slot"]["query_id"],
            "text": query,
            "text_sha256": hb(query.encode("utf-8")),
        },
        "entities": entities,
        "source_events": events,
        "source_evidence": evidence,
        "candidate_memories": memories,
        "synthetic_content": True,
        "gold_fields_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "phase7_3_3_d_lineage_used": False,
        "provider_called": False,
    }


def dataset_document() -> dict[str, Any]:
    plan = load(PLAN)
    cases = [authored_case(case_plan) for case_plan in plan["cases"]]
    return {
        "schema_version": 1,
        "dataset_id": "phase7.4-selected-source-cases-v1",
        "status": "frozen_synthetic_selected_source_cases_before_atomic_segmentation",
        "authoring_plan_sha256": sha(PLAN),
        "authoring_contract_sha256": sha(CONTRACT),
        "source_case_schema_sha256": sha(SCHEMA),
        "case_count": len(cases),
        "cases": cases,
        "source_content_authored": True,
        "source_content_frozen": True,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "network_used": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
    }


def normalized_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def word_five_grams(value: str) -> set[tuple[str, ...]]:
    words = normalized_words(value)
    if len(words) < 5:
        return {tuple(words)} if words else set()
    return {tuple(words[index : index + 5]) for index in range(len(words) - 4)}


def authored_text_rows(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for case in dataset["cases"]:
        case_id = case["case_id"]
        rows.append({"text_id": case["query"]["query_id"], "case_id": case_id, "text_type": "query", "text": case["query"]["text"]})
        rows.extend({"text_id": row["source_event_id"], "case_id": case_id, "text_type": "event", "text": row["description"]} for row in case["source_events"])
        rows.extend({"text_id": row["source_evidence_id"], "case_id": case_id, "text_type": "evidence", "text": row["observed_text"]} for row in case["source_evidence"])
        rows.extend({"text_id": row["source_memory_id"], "case_id": case_id, "text_type": "memory", "text": row["source_memory_content"]} for row in case["candidate_memories"])
    return rows


def high_similarity_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grams_by_index: list[set[tuple[str, ...]]] = []
    inverted: dict[tuple[str, ...], list[int]] = defaultdict(list)
    pairs = []
    for index, row in enumerate(rows):
        grams = word_five_grams(row["text"])
        candidates: set[int] = set()
        for gram in grams:
            candidates.update(inverted[gram])
        for other_index in candidates:
            other = rows[other_index]
            if other["case_id"] == row["case_id"]:
                continue
            other_grams = grams_by_index[other_index]
            union = grams | other_grams
            score = len(grams & other_grams) / len(union) if union else 0.0
            if score >= 0.85:
                pairs.append(
                    {
                        "left_text_id": other["text_id"],
                        "right_text_id": row["text_id"],
                        "left_case_id": other["case_id"],
                        "right_case_id": row["case_id"],
                        "five_gram_jaccard": score,
                    }
                )
        grams_by_index.append(grams)
        for gram in grams:
            inverted[gram].append(index)
    return pairs


def validate_case_against_plan(
    case: dict[str, Any], case_plan: dict[str, Any]
) -> bool:
    if any(
        [
            case["case_id"] != case_plan["case_id"],
            case["stratum"] != case_plan["stratum"],
            case["domain"] != case_plan["domain"],
            case["scenario_variant"] != case_plan["scenario_variant"],
            case["query"]["query_id"] != case_plan["query_slot"]["query_id"],
            [row["entity_id"] for row in case["entities"]]
            != [row["entity_id"] for row in case_plan["entity_slots"]],
            [row["source_event_id"] for row in case["source_events"]]
            != [row["source_event_id"] for row in case_plan["source_event_slots"]],
            [row["source_evidence_id"] for row in case["source_evidence"]]
            != [row["source_evidence_id"] for row in case_plan["source_evidence_slots"]],
        ]
    ):
        return False
    expected_memories = [
        (
            row["memory_authoring_ordinal"],
            row["pool_ordinal"],
            row["source_memory_id"],
            row["source_memory_kind"],
        )
        for row in case_plan["candidate_memory_slots"]
    ]
    actual_memories = [
        (
            row["memory_authoring_ordinal"],
            row["pool_ordinal"],
            row["source_memory_id"],
            row["source_memory_kind"],
        )
        for row in case["candidate_memories"]
    ]
    return actual_memories == expected_memories


def dataset_checks(dataset: dict[str, Any]) -> tuple[list[tuple[str, bool]], dict[str, Any]]:
    schema = load(SCHEMA)
    validator = Draft202012Validator(schema)
    plan = load(PLAN)
    cases = dataset["cases"]
    case_by_id = {case["case_id"]: case for case in cases}
    plan_by_id = {case["case_id"]: case for case in plan["cases"]}
    schema_errors = [
        {"case_id": case["case_id"], "errors": [error.message for error in validator.iter_errors(case)]}
        for case in cases
        if not validator.is_valid(case)
    ]
    all_entity_ids = {row["entity_id"] for case in cases for row in case["entities"]}
    all_event_ids = {row["source_event_id"] for case in cases for row in case["source_events"]}
    all_evidence_ids = {row["source_evidence_id"] for case in cases for row in case["source_evidence"]}
    all_memory_ids = {row["source_memory_id"] for case in cases for row in case["candidate_memories"]}
    hash_replay = True
    reference_closure = True
    all_evidence_used = True
    logical_times_exact = True
    stratum_semantics = True
    for case in cases:
        entity_ids = {row["entity_id"] for row in case["entities"]}
        event_ids = {row["source_event_id"] for row in case["source_events"]}
        evidence_ids = {row["source_evidence_id"] for row in case["source_evidence"]}
        referenced_evidence = set()
        hash_replay = hash_replay and case["query"]["text_sha256"] == hb(case["query"]["text"].encode("utf-8"))
        logical_times_exact = logical_times_exact and sorted(row["logical_time"] for row in case["source_events"]) == list(range(1, 7))
        for row in case["source_events"]:
            hash_replay = hash_replay and row["description_sha256"] == hb(row["description"].encode("utf-8"))
            reference_closure = reference_closure and set(row["entity_ids"]) <= entity_ids
        for row in case["source_evidence"]:
            hash_replay = hash_replay and row["observed_text_sha256"] == hb(row["observed_text"].encode("utf-8"))
            reference_closure = reference_closure and set(row["entity_ids"]) <= entity_ids and set(row["source_event_ids"]) <= event_ids
        for row in case["candidate_memories"]:
            hash_replay = hash_replay and row["source_memory_content_sha256"] == hb(row["source_memory_content"].encode("utf-8")) and row["source_memory_sha256"] == source_memory_hash(row)
            reference_closure = reference_closure and set(row["source_evidence_ids"]) <= evidence_ids and set(row["source_event_ids"]) <= event_ids
            referenced_evidence.update(row["source_evidence_ids"])
        all_evidence_used = all_evidence_used and referenced_evidence == evidence_ids
        active_entities = set().union(*(set(row["entity_ids"]) for row in case["source_events"]))
        if case["stratum"] == "multi_entity_reasoning":
            stratum_semantics = stratum_semantics and len(active_entities) >= 3
        if case["stratum"] in {"temporal_update", "preference_evolution"}:
            stratum_semantics = stratum_semantics and any(row["event_type"] == "revision" for row in case["source_events"])
        if case["stratum"] in {"failure_learning", "causal_reasoning"}:
            stratum_semantics = stratum_semantics and any(row["event_type"] == "outcome" for row in case["source_events"])

    forbidden = set(load(CONTRACT)["forbidden_authored_fields"])

    def contains_forbidden(value: Any) -> bool:
        if isinstance(value, dict):
            return any(key in forbidden or contains_forbidden(item) for key, item in value.items())
        if isinstance(value, list):
            return any(contains_forbidden(item) for item in value)
        return False

    text_rows = authored_text_rows(dataset)
    normalized = [" ".join(normalized_words(row["text"])) for row in text_rows]
    exact_duplicate_count = len(normalized) - len(set(normalized))
    similar = high_similarity_pairs(text_rows)
    checks = [
        ("schema_definition_valid", validate_schema_definition()),
        ("all_168_cases_schema_valid", len(schema_errors) == 0 and len(cases) == 168),
        ("case_ids_exact_and_unique", [case["case_id"] for case in cases] == [case["case_id"] for case in plan["cases"]] and len(case_by_id) == 168),
        ("all_cases_match_frozen_plan", all(validate_case_against_plan(case_by_id[case_id], plan_by_id[case_id]) for case_id in plan_by_id)),
        ("entity_id_count_and_uniqueness", len(all_entity_ids) == 672),
        ("event_id_count_and_uniqueness", len(all_event_ids) == 1008),
        ("evidence_id_count_and_uniqueness", len(all_evidence_ids) == 1344),
        ("memory_id_count_and_uniqueness", len(all_memory_ids) == 1680),
        ("logical_times_exact", logical_times_exact),
        ("all_hashes_replay", hash_replay),
        ("all_references_case_local_and_resolved", reference_closure),
        ("all_evidence_referenced", all_evidence_used),
        ("stratum_construction_signals_present", stratum_semantics),
        ("no_forbidden_gold_atomic_arm_or_rationale_fields", not contains_forbidden(dataset)),
        ("no_exact_cross_case_normalized_text_duplicates", exact_duplicate_count == 0),
        ("no_unresolved_high_similarity_pairs", len(similar) == 0),
        ("source_content_frozen", dataset["source_content_authored"] is True and dataset["source_content_frozen"] is True),
        ("gold_atomic_arm_absent", dataset["gold_or_reference_labels_present"] is False and dataset["atomic_overlay_present"] is False and dataset["arm_output_present"] is False),
        ("phase7_3_content_not_loaded", dataset["phase7_3_3_d_content_loaded"] is False),
        ("provider_and_network_unused", dataset["provider_called"] is False and dataset["network_used"] is False),
        ("effect_dataset_closed_to_arms", dataset["selected_effect_dataset_opened_for_arm_execution"] is False),
        ("runtime_not_authorized", dataset["runtime_integration_authorized"] is False),
    ]
    diagnostics = {
        "schema_error_case_count": len(schema_errors),
        "schema_error_examples": schema_errors[:5],
        "authored_text_count": len(text_rows),
        "exact_normalized_text_duplicate_count": exact_duplicate_count,
        "high_similarity_pair_count": len(similar),
        "high_similarity_pair_examples": similar[:20],
    }
    return checks, diagnostics


def fixture_document() -> dict[str, Any]:
    dataset = load(DATASET)
    checks, diagnostics = dataset_checks(dataset)
    rows = [{"fixture_id": name, "passed": passed} for name, passed in checks]
    return {
        "schema_version": 1,
        "fixtures_id": "phase7.4-selected-source-authoring-fixtures-v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "fixture_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "fixtures": rows,
        "diagnostics": diagnostics,
        "all_fixtures_passed": all(row["passed"] for row in rows),
        "source_content_authored": True,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
    }


def case_hashes() -> list[dict[str, str]]:
    return [
        {"case_id": case["case_id"], "case_sha256": hb(canonical(case).encode("utf-8"))}
        for case in load(DATASET)["cases"]
    ]


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "phase7.4-selected-source-authoring-manifest-v1",
        "status": "frozen_selected_synthetic_source_cases",
        "entry_head": ENTRY_HEAD,
        "adapter_sha256": sha(SELF),
        "frozen_inputs": {rel(path): digest for path, digest in EXPECTED.items()},
        "outputs": {rel(DATASET): sha(DATASET), rel(FIXTURES): sha(FIXTURES)},
        "case_hashes": case_hashes(),
        "case_count": 168,
        "source_content_authored": True,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "network_used": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def outcome_document(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "outcome_id": "phase7.4-selected-source-authoring-outcome-v1",
        "status": "PASS_selected_source_cases_frozen_segmentation_protocol_freeze_authorized",
        "manifest_sha256": manifest_hash,
        "dataset_sha256": sha(DATASET),
        "fixtures_sha256": sha(FIXTURES),
        "case_count": 168,
        "source_content_authored": True,
        "source_content_frozen": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "provider_called": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def audit_event(manifest_hash: str, outcome_hash: str) -> dict[str, Any]:
    return {
        "event_id": "phase7.4-selected-source-authoring-v1-frozen",
        "event_type": "immutable_selected_synthetic_source_content_freeze",
        "entry_head": ENTRY_HEAD,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "dataset_sha256": sha(DATASET),
        "authoring_plan_sha256": sha(PLAN),
        "case_count": 168,
        "source_content_authored": True,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
        "phase7_3_3_d_content_loaded": False,
        "provider_called": False,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def lineage(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, str]:
    return {
        "phase7_4_stage_state_v6_sha256": sha(STATE_V6),
        "phase7_4_readiness_v6_sha256": sha(READINESS_V6),
        "phase7_4_selected_source_authoring_contract_receipt_v1_sha256": sha(CONTRACT_RECEIPT),
        "phase7_4_selected_source_authoring_plan_v1_sha256": sha(PLAN),
        "phase7_4_selected_source_cases_v1_sha256": sha(DATASET),
        "phase7_4_selected_source_authoring_fixtures_v1_sha256": sha(FIXTURES),
        "phase7_4_selected_source_authoring_manifest_v1_sha256": manifest_hash,
        "phase7_4_selected_source_authoring_outcome_v1_sha256": outcome_hash,
        "phase7_4_selected_source_authoring_audit_v1_sha256": audit_hash,
    }


def state_document(manifest_hash: str, outcome_hash: str, audit_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 7,
        "state_id": "phase7.4-stage-state-v7",
        "status": "phase7_4_selected_source_cases_frozen_atomic_segmentation_protocol_freeze_authorized",
        "artifact_lineage": lineage(manifest_hash, outcome_hash, audit_hash),
        "source_slot_inventory_frozen": True,
        "sampling_frame_frozen": True,
        "selected_source_authoring_contract_frozen": True,
        "selected_source_content_authoring_authorized": True,
        "selected_source_content_authored": True,
        "selected_source_content_frozen": True,
        "selected_case_count": 168,
        "atomic_segmentation_protocol_freeze_authorized": True,
        "atomic_segmentation_execution_authorized": False,
        "atomic_overlay_constructed": False,
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
    manifest_hash: str, outcome_hash: str, audit_hash: str, state_hash: str
) -> dict[str, Any]:
    return {
        "schema_version": 7,
        "readiness_id": "phase7.4-readiness-v7",
        "status": "PASS_selected_source_cases_frozen",
        "artifact_lineage": {
            **lineage(manifest_hash, outcome_hash, audit_hash),
            "phase7_4_stage_state_v7_sha256": state_hash,
        },
        "checks": {
            "selected_case_count_exact": True,
            "source_case_schema_valid": True,
            "blank_plan_identity_exact": True,
            "all_text_and_memory_hashes_replay": True,
            "all_references_resolved": True,
            "all_source_evidence_used": True,
            "no_forbidden_labels_or_outputs": True,
            "no_exact_or_high_similarity_cross_case_duplicates": True,
            "phase7_3_3_d_content_not_loaded": True,
            "provider_and_network_unused": True,
            "effect_dataset_closed_to_arms": True,
            "runtime_not_authorized": True,
        },
        "atomic_segmentation_protocol_freeze_authorized": True,
        "atomic_segmentation_execution_authorized": False,
        "reference_review_authorized": False,
        "selected_effect_dataset_opening_for_arm_execution_authorized": False,
        "arm_execution_authorized": False,
        "effect_scoring_authorized": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def receipt_document(
    manifest_hash: str,
    outcome_hash: str,
    audit_hash: str,
    state_hash: str,
    readiness_hash: str,
) -> dict[str, Any]:
    fixtures = load(FIXTURES)
    return {
        "schema_version": 1,
        "receipt_id": "phase7.4-selected-source-authoring-receipt-v1",
        "status": "PASS",
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_log_sha256": audit_hash,
        "state_v7_sha256": state_hash,
        "readiness_v7_sha256": readiness_hash,
        "dataset_sha256": sha(DATASET),
        "fixtures_sha256": sha(FIXTURES),
        "case_count": 168,
        "authored_text_count": fixtures["diagnostics"]["authored_text_count"],
        "exact_normalized_text_duplicate_count": fixtures["diagnostics"]["exact_normalized_text_duplicate_count"],
        "high_similarity_pair_count": fixtures["diagnostics"]["high_similarity_pair_count"],
        "source_content_frozen": True,
        "gold_or_reference_labels_present": False,
        "atomic_overlay_present": False,
        "arm_output_present": False,
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
    diagnostics: dict[str, Any] = {}
    if all(checks.values()):
        state = load(STATE_V6)
        contract = load(CONTRACT)
        checks.update(
            {
                "entry_head_exact": git_head() == ENTRY_HEAD,
                "entry_state_exact": state["status"] == ENTRY,
                "entry_authority_exact": state["next_authorized_stage"] == AUTHORIZED,
                "contract_next_exact": contract["next_authorized_stage_after_pass"] == AUTHORIZED,
                "authoring_authorized": state["selected_source_content_authoring_authorized"] is True,
                "source_not_already_authored": state["selected_source_content_authored"] is False,
                "atomic_reference_and_arms_closed": state["atomic_segmentation_authorized"] is False and state["reference_review_started"] is False and state["arm_execution_started"] is False,
                "effect_dataset_closed": state["selected_effect_dataset_opened_for_arm_execution"] is False,
                "provider_not_called": state["phase7_4_effect_provider_called"] is False,
                "runtime_off": state["runtime_integration_authorized"] is False,
            }
        )
        if all(checks.values()):
            draft = dataset_document()
            draft_checks, diagnostics = dataset_checks(draft)
            checks.update({"draft:" + name: passed for name, passed in draft_checks})
    checks["outputs_absent"] = all(not path.exists() for path in OUTPUTS)
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "draft_diagnostics": diagnostics,
    }


def author() -> dict[str, Any]:
    checked = preflight()
    if checked["status"] != "PASS":
        return checked
    dataset_hash = once(DATASET, dataset_document())
    fixtures_hash = once(FIXTURES, fixture_document())
    if not load(FIXTURES)["all_fixtures_passed"]:
        raise RuntimeError("selected_source_authoring_fixture_failure")
    manifest_hash = once(MANIFEST, manifest_document())
    outcome_hash = once(OUTCOME, outcome_document(manifest_hash))
    audit_hash = append_single_event(AUDIT, audit_event(manifest_hash, outcome_hash))
    state_hash = once(STATE_V7, state_document(manifest_hash, outcome_hash, audit_hash))
    readiness_hash = once(
        READINESS_V7,
        readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
    )
    receipt_hash = once(
        RECEIPT,
        receipt_document(
            manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash
        ),
    )
    return {
        "status": "PASS",
        "dataset_sha256": dataset_hash,
        "fixtures_sha256": fixtures_hash,
        "manifest_sha256": manifest_hash,
        "outcome_sha256": outcome_hash,
        "audit_sha256": audit_hash,
        "state_v7_sha256": state_hash,
        "readiness_v7_sha256": readiness_hash,
        "receipt_sha256": receipt_hash,
        "case_count": 168,
        "authored_text_count": load(FIXTURES)["diagnostics"]["authored_text_count"],
        "exact_normalized_text_duplicate_count": load(FIXTURES)["diagnostics"]["exact_normalized_text_duplicate_count"],
        "high_similarity_pair_count": load(FIXTURES)["diagnostics"]["high_similarity_pair_count"],
        "source_content_frozen": True,
        "selected_effect_dataset_opened_for_arm_execution": False,
        "runtime_integration_authorized": False,
        "next_authorized_stage": NEXT,
    }


def verify() -> dict[str, Any]:
    checks = {"exists:" + rel(path): path.exists() for path in OUTPUTS}
    if all(checks.values()):
        manifest_hash = sha(MANIFEST)
        outcome_hash = sha(OUTCOME)
        audit_hash = sha(AUDIT)
        state_hash = sha(STATE_V7)
        readiness_hash = sha(READINESS_V7)
        checks.update(
            {
                "entry_head_is_ancestor": entry_head_is_ancestor(),
                "input_hashes": all(path.exists() and sha(path) == digest for path, digest in EXPECTED.items()),
                "dataset_replay": load(DATASET) == dataset_document(),
                "fixtures_replay": load(FIXTURES) == fixture_document(),
                "manifest_replay": load(MANIFEST) == manifest_document(),
                "outcome_replay": load(OUTCOME) == outcome_document(manifest_hash),
                "audit_replay": AUDIT.read_bytes() == (canonical(audit_event(manifest_hash, outcome_hash)) + "\n").encode("utf-8"),
                "state_v7_replay": load(STATE_V7) == state_document(manifest_hash, outcome_hash, audit_hash),
                "readiness_v7_replay": load(READINESS_V7) == readiness_document(manifest_hash, outcome_hash, audit_hash, state_hash),
                "receipt_replay": load(RECEIPT) == receipt_document(manifest_hash, outcome_hash, audit_hash, state_hash, readiness_hash),
                "fixtures_pass": load(FIXTURES)["all_fixtures_passed"] is True,
                "next_gate_consistent": load(STATE_V7)["next_authorized_stage"] == load(READINESS_V7)["next_authorized_stage"] == load(RECEIPT)["next_authorized_stage"] == NEXT,
                "source_content_frozen": load(STATE_V7)["selected_source_content_frozen"] is True,
                "effect_dataset_closed_to_arms": load(STATE_V7)["selected_effect_dataset_opened_for_arm_execution"] is False,
                "provider_not_called": load(STATE_V7)["phase7_4_effect_provider_called"] is False,
                "runtime_off": load(STATE_V7)["runtime_integration_authorized"] is False,
            }
        )
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": len(checks),
        "failed": failed,
        "entry_head": ENTRY_HEAD,
        "current_head": git_head(),
        "source_content_frozen": load(STATE_V7).get("selected_source_content_frozen") if STATE_V7.exists() else None,
        "selected_effect_dataset_opened_for_arm_execution": load(STATE_V7).get("selected_effect_dataset_opened_for_arm_execution") if STATE_V7.exists() else None,
        "runtime_integration_authorized": load(STATE_V7).get("runtime_integration_authorized") if STATE_V7.exists() else None,
        "next_authorized_stage": load(STATE_V7).get("next_authorized_stage") if STATE_V7.exists() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--author", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
    elif args.author:
        result = author()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
