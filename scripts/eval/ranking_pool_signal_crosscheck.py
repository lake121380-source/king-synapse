#!/usr/bin/env python
"""Cross-check conditional reranker-pool triggers across datasets.

This is a sanitized post-processing audit. It compares control and candidate
reranker-pool runs from an existing signal report and simulates conditional
use of the larger pool from answer-free ranking signals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ranking_pool_signal_trigger_audit import (
    build_cases,
    compact_run,
    evaluate_trigger,
    repo_root,
    runs_by_pool,
    trigger_definitions,
)


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Cross-check conditional pool triggers.")
    parser.add_argument(
        "--signal-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-longmem-50-reranker-pool-signal.json",
    )
    parser.add_argument("--control-pool", type=int, default=50)
    parser.add_argument("--candidate-pool", type=int, default=100)
    parser.add_argument(
        "--focus-trigger",
        default="top1_single_source",
        help="Trigger id to highlight in the top-level summary.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-pool-signal-crosscheck-dmr-longmem-50.json",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def transition_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(case["transition"] for case in cases).items()))


def compact_evaluation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "description": item["description"],
        "triggered_count": item["triggered_count"],
        "triggered_fraction": item["triggered_fraction"],
        "triggered_transition_counts": item["triggered_transition_counts"],
        "projected": item["projected"],
        "deltas_vs_control": item["deltas_vs_control"],
    }


def audit_dataset(
    dataset: dict[str, Any],
    *,
    control_pool: int,
    candidate_pool: int,
    focus_trigger: str,
) -> dict[str, Any]:
    runs = runs_by_pool({"datasets": [dataset]})
    if control_pool not in runs:
        raise ValueError(f"{dataset.get('id')} missing control pool {control_pool}")
    if candidate_pool not in runs:
        raise ValueError(f"{dataset.get('id')} missing candidate pool {candidate_pool}")

    control = runs[control_pool]
    candidate = runs[candidate_pool]
    cases = build_cases(control, candidate)
    triggers = trigger_definitions(cases)
    evaluations = [evaluate_trigger(cases, trigger, control, {}) for trigger in triggers]
    evaluations.sort(
        key=lambda item: (
            item["deltas_vs_control"]["recall_at_10"],
            item["deltas_vs_control"]["mrr_at_10"],
            -item["triggered_count"],
        ),
        reverse=True,
    )
    focus = next((item for item in evaluations if item["id"] == focus_trigger), None)
    if focus is None:
        raise ValueError(f"missing focus trigger: {focus_trigger}")

    return {
        "id": dataset.get("id"),
        "name": dataset.get("name"),
        "sample_size": dataset.get("sample_size_used"),
        "control": compact_run(control),
        "candidate": compact_run(candidate),
        "candidate_transition_counts": transition_counts(cases),
        "focus_trigger": compact_evaluation(focus),
        "best_by_recall_trigger": compact_evaluation(evaluations[0]),
        "top_trigger_evaluations": [compact_evaluation(item) for item in evaluations[:5]],
    }


def main() -> int:
    args = parse_args()
    args.signal_report = args.signal_report if args.signal_report.is_absolute() else repo_root() / args.signal_report
    args.output = args.output if args.output.is_absolute() else repo_root() / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    signal_report = load_json(args.signal_report)
    datasets = [
        audit_dataset(
            dataset,
            control_pool=args.control_pool,
            candidate_pool=args.candidate_pool,
            focus_trigger=args.focus_trigger,
        )
        for dataset in signal_report.get("datasets", [])
    ]

    report = {
        "schema_version": "king-synapse.ranking-pool-signal-crosscheck.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/ranking_pool_signal_crosscheck.py",
        "inputs": {
            "signal_report": {
                "path": report_path(args.signal_report),
                "sha256": sha256_file(args.signal_report),
            }
        },
        "control_pool": args.control_pool,
        "candidate_pool": args.candidate_pool,
        "focus_trigger_id": args.focus_trigger,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "datasets": datasets,
        "limits": [
            "Uses sanitized per-query ranks, metrics, and score summaries only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Simulates conditional use of the candidate reranker pool; it does not change retrieval or ranking behavior.",
            "Projected latency uses per-query wall-clock latency from existing reports and is an estimate.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(args.output),
                "focus_trigger_id": args.focus_trigger,
                "datasets": {
                    dataset["id"]: {
                        "control": dataset["control"],
                        "candidate": dataset["candidate"],
                        "focus_trigger": dataset["focus_trigger"],
                        "best_by_recall_trigger": dataset["best_by_recall_trigger"]["id"],
                    }
                    for dataset in datasets
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
