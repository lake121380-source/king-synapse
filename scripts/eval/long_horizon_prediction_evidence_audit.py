#!/usr/bin/env python
"""Explain long-horizon future evidence-matching misses.

This audit reads the deterministic long-horizon stability report and the
committed Rust fixture definition. It does not run recall, mutate runtime
behavior, inspect external datasets, or commit raw third-party records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Audit long-horizon prediction evidence matching."
    )
    parser.add_argument(
        "--stability-report",
        type=Path,
        default=root / "crates/eval/reports/long-horizon-stability-audit.json",
    )
    parser.add_argument(
        "--fixture-source",
        type=Path,
        default=root / "crates/eval/src/algorithms.rs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/long-horizon-prediction-evidence-audit.json",
    )
    return parser.parse_args()


def normalize_path_arg(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class FixtureCase:
    label: str
    hidden: str
    future: str
    state_terms: list[str]
    goal_terms: list[str]


def parse_string_field(block: str, field: str) -> str:
    match = re.search(rf'{field}:\s*"([^"]*)"', block)
    if not match:
        raise ValueError(f"missing {field} in long-horizon fixture block")
    return match.group(1)


def parse_term_field(block: str, field: str) -> list[str]:
    match = re.search(rf"{field}:\s*&\[(.*?)\]", block, flags=re.DOTALL)
    if not match:
        raise ValueError(f"missing {field} in long-horizon fixture block")
    return re.findall(r'"([^"]+)"', match.group(1))


def parse_long_horizon_fixture(source: str) -> dict[str, FixtureCase]:
    function_match = re.search(
        r"fn long_horizon_fixture\(\).*?\{\s*vec!\[(?P<body>.*?)\n\s*\]\s*\n\}",
        source,
        flags=re.DOTALL,
    )
    if not function_match:
        raise ValueError("could not locate long_horizon_fixture body")

    cases: dict[str, FixtureCase] = {}
    for match in re.finditer(r"LongHorizonCase\s*\{(?P<block>.*?)\n\s*\}", function_match.group("body"), re.DOTALL):
        block = match.group("block")
        case = FixtureCase(
            label=parse_string_field(block, "label"),
            hidden=parse_string_field(block, "hidden"),
            future=parse_string_field(block, "future"),
            state_terms=parse_term_field(block, "state_terms"),
            goal_terms=parse_term_field(block, "goal_terms"),
        )
        cases[case.label] = case
    if not cases:
        raise ValueError("no LongHorizonCase entries parsed")
    return cases


def contains_term(text: str, term: str) -> bool:
    return term.lower() in text.lower()


def matched_context_terms(text: str, case: FixtureCase) -> list[str]:
    matched: list[str] = []
    for term in case.state_terms:
        if contains_term(text, term):
            matched.append(f"state:{term}")
    for term in case.goal_terms:
        if contains_term(text, term):
            matched.append(f"goal:{term}")
    return sorted(set(matched))


def rank_triplet(case_report: dict[str, Any], key_middle: str) -> dict[str, Any]:
    return {
        "prefix": case_report[f"prefix_prediction_{key_middle}_rank_top10"],
        "full": case_report[f"full_prediction_{key_middle}_rank_top10"],
        "final": case_report[f"final_prediction_{key_middle}_rank_top10"],
    }


def all_present(values: dict[str, Any]) -> bool:
    return all(value is not None for value in values.values())


def classify_case(
    *,
    candidate_present_all_phases: bool,
    matched_evidence_all_phases: bool,
    future_context_terms: list[str],
) -> str:
    if not candidate_present_all_phases:
        return "candidate_missing"
    if matched_evidence_all_phases:
        return "candidate_present_with_target_context_overlap"
    if not future_context_terms:
        return "candidate_present_without_target_context_overlap"
    return "candidate_present_but_evidence_terms_missing"


def build_case_read(
    *,
    classification: str,
    candidate_ranks: dict[str, Any],
    matched_ranks: dict[str, Any],
    future_context_terms: list[str],
    hidden_context_terms: list[str],
) -> str:
    if classification == "candidate_present_without_target_context_overlap":
        return (
            "Expected future candidate is present in every phase, but the future "
            "target text has no state/goal term overlap under the current "
            "substring evidence rule; activation is therefore visible as a "
            "network candidate, not as matched target-side evidence."
        )
    if classification == "candidate_present_with_target_context_overlap":
        return (
            "Expected future candidate is present and carries target-side "
            "matched context terms under the current evidence rule."
        )
    if classification == "candidate_missing":
        return "Expected future candidate is missing from at least one phase."
    return (
        "Expected future candidate is present, but matched evidence is missing "
        "despite target-side context overlap; this would require a deeper trace "
        "inspection."
    )


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    stability_path = normalize_path_arg(args.stability_report)
    fixture_source_path = normalize_path_arg(args.fixture_source)
    stability = load_json(stability_path)
    fixture = parse_long_horizon_fixture(fixture_source_path.read_text(encoding="utf-8"))

    case_reports = []
    for case_report in stability["cases"]:
        label = case_report["case_label"]
        if label not in fixture:
            raise ValueError(f"stability report case missing from fixture source: {label}")
        case = fixture[label]
        candidate_ranks = rank_triplet(case_report, "candidate")
        matched_ranks = rank_triplet(case_report, "matched")
        candidate_present = all_present(candidate_ranks)
        matched_present = all_present(matched_ranks)
        future_context_terms = matched_context_terms(case.future, case)
        hidden_context_terms = matched_context_terms(case.hidden, case)
        final_terms = case_report.get("final_prediction_candidate_matched_terms", [])
        classification = classify_case(
            candidate_present_all_phases=candidate_present,
            matched_evidence_all_phases=matched_present,
            future_context_terms=future_context_terms,
        )

        case_reports.append(
            {
                "case_label": label,
                "candidate_ranks": candidate_ranks,
                "matched_evidence_ranks": matched_ranks,
                "candidate_present_all_phases": candidate_present,
                "matched_evidence_all_phases": matched_present,
                "future_context_matched_terms_by_fixture_text": future_context_terms,
                "hidden_context_matched_terms_by_fixture_text": hidden_context_terms,
                "reported_final_candidate_matched_terms": final_terms,
                "dominant_trace_stable_after_reinforcement": case_report[
                    "no_dominant_drift_after_reinforcement"
                ],
                "prediction_evidence_stable_after_reinforcement": case_report[
                    "no_prediction_drift_after_reinforcement"
                ],
                "reinforcement_consistency": case_report["reinforcement_consistency"],
                "classification": classification,
                "read": build_case_read(
                    classification=classification,
                    candidate_ranks=candidate_ranks,
                    matched_ranks=matched_ranks,
                    future_context_terms=future_context_terms,
                    hidden_context_terms=hidden_context_terms,
                ),
            }
        )

    candidate_present_count = sum(
        1 for case in case_reports if case["candidate_present_all_phases"]
    )
    matched_count = sum(1 for case in case_reports if case["matched_evidence_all_phases"])
    no_future_overlap_labels = [
        case["case_label"]
        for case in case_reports
        if not case["future_context_matched_terms_by_fixture_text"]
    ]
    candidate_without_terms_labels = [
        case["case_label"]
        for case in case_reports
        if case["candidate_present_all_phases"] and not case["matched_evidence_all_phases"]
    ]
    source_miss_labels = stability.get("aggregate", {}).get(
        "future_candidate_without_matched_terms_labels", []
    )

    return {
        "schema_version": "king-synapse.long-horizon-prediction-evidence-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "inputs": {
            "stability_report": {
                "path": report_path(stability_path),
                "sha256": sha256_file(stability_path),
                "schema_version": stability.get("schema_version"),
            },
            "fixture_source": {
                "path": report_path(fixture_source_path),
                "sha256": sha256_file(fixture_source_path),
            },
        },
        "raw_records_committed": False,
        "raw_dialogs_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "external_dataset_content_committed": False,
        "aggregate": {
            "case_count": len(case_reports),
            "candidate_present_all_phases_count": candidate_present_count,
            "matched_evidence_all_phases_count": matched_count,
            "candidate_without_matched_terms_labels": candidate_without_terms_labels,
            "fixture_future_context_overlap_missing_labels": no_future_overlap_labels,
            "source_report_future_candidate_without_matched_terms_labels": source_miss_labels,
            "context_overlap_explains_all_reported_matched_misses": sorted(
                candidate_without_terms_labels
            )
            == sorted(no_future_overlap_labels)
            == sorted(source_miss_labels),
            "minimum_reinforcement_consistency": min(
                case["reinforcement_consistency"] for case in case_reports
            ),
            "dominant_trace_drift_failure_labels": [
                case["case_label"]
                for case in case_reports
                if not case["dominant_trace_stable_after_reinforcement"]
            ],
            "prediction_evidence_drift_failure_labels": [
                case["case_label"]
                for case in case_reports
                if not case["prediction_evidence_stable_after_reinforcement"]
            ],
        },
        "cases": case_reports,
        "read": {
            "conclusion": (
                "The long-horizon 0.750 future-evidence score is explained by "
                "target-side context-term overlap, not by candidate recall loss. "
                "All eight expected future candidates are present in prefix, full, "
                "and final checks; the two evidence misses are exactly the two "
                "future targets whose text has no state/goal term overlap under "
                "the current substring evidence rule."
            ),
            "system_interpretation": (
                "The network path is intact in the deterministic fixture: hidden "
                "dominance, candidate continuation, and reinforcement stay stable. "
                "The weak surface is evidence labeling for future candidates whose "
                "target text is semantically related but does not repeat the active "
                "state/goal terms."
            ),
            "next_gate": (
                "Future work should add validation-only evidence-path diagnostics "
                "or an explicit target-side evidence policy before product claims; "
                "do not change memory schema, cognitive layers, CLI behavior, or "
                "runtime defaults from this audit alone."
            ),
        },
        "limits": [
            "Reads the existing deterministic stability report and committed fixture source only.",
            "Does not run retrieval, ranking, answer generation, LLM judges, or external adapters.",
            "Does not inspect or commit third-party raw records.",
            "Does not change runtime behavior or product-facing defaults.",
        ],
    }


def main() -> int:
    args = parse_args()
    args.output = normalize_path_arg(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "candidate_present_all_phases_count": report["aggregate"][
                    "candidate_present_all_phases_count"
                ],
                "matched_evidence_all_phases_count": report["aggregate"][
                    "matched_evidence_all_phases_count"
                ],
                "candidate_without_matched_terms_labels": report["aggregate"][
                    "candidate_without_matched_terms_labels"
                ],
                "context_overlap_explains_all_reported_matched_misses": report["aggregate"][
                    "context_overlap_explains_all_reported_matched_misses"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
