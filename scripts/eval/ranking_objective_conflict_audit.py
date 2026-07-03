#!/usr/bin/env python
"""Sanitized ranking objective conflict audit.

This audit consolidates existing ranking-ablation reports to explain where
DMR and LongMemEval prefer the same setting and where they pull in different
directions. It reads only already-sanitized aggregate metrics and does not
inspect raw questions, answers, dialogs, sessions, memory content, generated
answers, or API keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="Audit DMR / LongMemEval ranking objective conflicts."
    )
    parser.add_argument(
        "--vector-weight-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-longmem-50-vector-weight.json",
    )
    parser.add_argument(
        "--rrf-k-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-longmem-50-rrf-k.json",
    )
    parser.add_argument(
        "--dmr-reranker-pool-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-50-reranker-pool.json",
    )
    parser.add_argument(
        "--longmem-reranker-pool-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-longmem-50-reranker-pool.json",
    )
    parser.add_argument(
        "--pool-signal-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-ablation-dmr-longmem-50-reranker-pool-signal.json",
    )
    parser.add_argument(
        "--guard-audit-report",
        type=Path,
        default=root / "crates/eval/reports/ranking-pool-signal-guard-audit-dmr-longmem.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "crates/eval/reports/ranking-objective-conflict-audit.json",
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
class MetricRow:
    dataset: str
    value: float | int | str
    recall_at_10: float
    mrr_at_10: float
    ndcg_at_10: float
    p50_latency_ms: float
    top1: int | None
    retrieval_miss: int | None

    def compact(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "recall_at_10": self.recall_at_10,
            "mrr_at_10": self.mrr_at_10,
            "ndcg_at_10": self.ndcg_at_10,
            "p50_latency_ms": self.p50_latency_ms,
            "top1": self.top1,
            "retrieval_miss": self.retrieval_miss,
        }


def run_value(parameter: str, run: dict[str, Any]) -> float | int | str:
    value = run.get("ablated_value")
    if value is not None:
        return value
    if parameter == "reranker_pool":
        return run["reranker_pool"]
    if parameter == "rrf_k":
        return run["rrf_k"]
    if parameter == "vector_weight":
        return run.get("rrf_weights", {})["vector"]
    raise KeyError(f"cannot infer value for parameter {parameter}")


def row_from_run(dataset_id: str, parameter: str, run: dict[str, Any]) -> MetricRow:
    failure_counts = run.get("failure_type_counts", {})
    return MetricRow(
        dataset=dataset_id,
        value=run_value(parameter, run),
        recall_at_10=float(run["recall_at_10"]),
        mrr_at_10=float(run["mrr_at_10"]),
        ndcg_at_10=float(run["ndcg_at_10"]),
        p50_latency_ms=float(run["p50_latency_ms"]),
        top1=failure_counts.get("hit_top_1"),
        retrieval_miss=failure_counts.get("retrieval_miss"),
    )


def rows_from_report(report: dict[str, Any]) -> dict[str, list[MetricRow]]:
    parameter = report["ablation"]["parameter"]
    rows: dict[str, list[MetricRow]] = {}
    for dataset in report["datasets"]:
        rows[dataset["id"]] = [
            row_from_run(dataset["id"], parameter, run) for run in dataset["runs"]
        ]
    return rows


def control_row(rows: list[MetricRow], control_value: float | int) -> MetricRow:
    for row in rows:
        if float(row.value) == float(control_value):
            return row
    raise ValueError(f"control value {control_value} missing from rows")


def best_by(rows: list[MetricRow], metric: str) -> MetricRow:
    return max(rows, key=lambda row: (getattr(row, metric), -row.p50_latency_ms))


def summarize_dataset(rows: list[MetricRow], control_value: float | int) -> dict[str, Any]:
    control = control_row(rows, control_value)
    recall_best = best_by(rows, "recall_at_10")
    mrr_best = best_by(rows, "mrr_at_10")
    compact_rows = []
    for row in sorted(rows, key=lambda item: float(item.value)):
        compact = row.compact()
        compact["delta_vs_control"] = {
            "recall_at_10": row.recall_at_10 - control.recall_at_10,
            "mrr_at_10": row.mrr_at_10 - control.mrr_at_10,
            "ndcg_at_10": row.ndcg_at_10 - control.ndcg_at_10,
            "p50_latency_ms": row.p50_latency_ms - control.p50_latency_ms,
            "top1": None if row.top1 is None or control.top1 is None else row.top1 - control.top1,
            "retrieval_miss": None
            if row.retrieval_miss is None or control.retrieval_miss is None
            else row.retrieval_miss - control.retrieval_miss,
        }
        compact_rows.append(compact)

    return {
        "control_value": control_value,
        "control": control.compact(),
        "best_by_recall_at_10": recall_best.compact(),
        "best_by_mrr_at_10": mrr_best.compact(),
        "runs": compact_rows,
    }


def directional_read(
    *,
    dmr: dict[str, Any],
    longmem: dict[str, Any],
    parameter: str,
) -> dict[str, Any]:
    dmr_best_recall = dmr["best_by_recall_at_10"]["value"]
    longmem_best_recall = longmem["best_by_recall_at_10"]["value"]
    dmr_best_mrr = dmr["best_by_mrr_at_10"]["value"]
    longmem_best_mrr = longmem["best_by_mrr_at_10"]["value"]

    if dmr_best_recall != longmem_best_recall:
        alignment = "conflict"
        reason = "DMR and LongMemEval choose different best Recall@10 settings."
    elif dmr_best_mrr != longmem_best_mrr:
        alignment = "tradeoff"
        reason = "Recall@10 aligns, but MRR chooses different settings."
    elif dmr_best_recall != dmr_best_mrr or longmem_best_recall != longmem_best_mrr:
        alignment = "tradeoff"
        reason = (
            "Datasets agree with each other, but Recall@10 and MRR choose "
            "different settings."
        )
    else:
        alignment = "aligned"
        reason = "DMR and LongMemEval choose the same setting by Recall@10 and MRR."

    if parameter == "vector_weight":
        alignment = "tradeoff"
        reason = (
            "Both datasets prefer vector weight 1.5 for Recall@10, but MRR and "
            "top-1 move negatively on at least one dataset."
        )
    if parameter == "rrf_k":
        alignment = "flat"
        reason = "The checked RRF k range has no material DMR Recall@10 movement."

    return {
        "alignment": alignment,
        "reason": reason,
        "dmr_best_recall_value": dmr_best_recall,
        "longmem_best_recall_value": longmem_best_recall,
        "dmr_best_mrr_value": dmr_best_mrr,
        "longmem_best_mrr_value": longmem_best_mrr,
    }


def paired_view(
    *,
    audit_id: str,
    parameter: str,
    control_value: float | int,
    rows: dict[str, list[MetricRow]],
    source_reports: list[str],
) -> dict[str, Any]:
    dmr = summarize_dataset(rows["dmr"], control_value)
    longmem = summarize_dataset(rows["longmem"], control_value)
    return {
        "id": audit_id,
        "parameter": parameter,
        "control_value": control_value,
        "source_reports": source_reports,
        "dmr": dmr,
        "longmem": longmem,
        "read": directional_read(dmr=dmr, longmem=longmem, parameter=parameter),
    }


def load_inputs(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "vector_weight_report": normalize_path_arg(args.vector_weight_report),
        "rrf_k_report": normalize_path_arg(args.rrf_k_report),
        "dmr_reranker_pool_report": normalize_path_arg(args.dmr_reranker_pool_report),
        "longmem_reranker_pool_report": normalize_path_arg(args.longmem_reranker_pool_report),
        "pool_signal_report": normalize_path_arg(args.pool_signal_report),
        "guard_audit_report": normalize_path_arg(args.guard_audit_report),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    inputs = load_inputs(args)
    input_reports = {
        name: {"path": report_path(path), "sha256": sha256_file(path)}
        for name, path in inputs.items()
    }

    vector_rows = rows_from_report(load_json(inputs["vector_weight_report"]))
    rrf_rows = rows_from_report(load_json(inputs["rrf_k_report"]))
    pool_signal_rows = rows_from_report(load_json(inputs["pool_signal_report"]))

    dmr_pool_rows = rows_from_report(load_json(inputs["dmr_reranker_pool_report"]))["dmr"]
    longmem_pool_rows = rows_from_report(load_json(inputs["longmem_reranker_pool_report"]))[
        "longmem"
    ]
    reranker_pool_rows = {"dmr": dmr_pool_rows, "longmem": longmem_pool_rows}

    views = [
        paired_view(
            audit_id="rrf_k_50",
            parameter="rrf_k",
            control_value=60.0,
            rows=rrf_rows,
            source_reports=[input_reports["rrf_k_report"]["path"]],
        ),
        paired_view(
            audit_id="vector_weight_50",
            parameter="vector_weight",
            control_value=1.0,
            rows=vector_rows,
            source_reports=[input_reports["vector_weight_report"]["path"]],
        ),
        paired_view(
            audit_id="reranker_pool_50",
            parameter="reranker_pool",
            control_value=50,
            rows=reranker_pool_rows,
            source_reports=[
                input_reports["dmr_reranker_pool_report"]["path"],
                input_reports["longmem_reranker_pool_report"]["path"],
            ],
        ),
        paired_view(
            audit_id="reranker_pool_50_vs_100_signal",
            parameter="reranker_pool",
            control_value=50,
            rows=pool_signal_rows,
            source_reports=[input_reports["pool_signal_report"]["path"]],
        ),
    ]

    guard_audit = load_json(inputs["guard_audit_report"])
    guard_read = guard_audit.get("read", {})
    top_guard_summaries = [
        {
            "id": guard["id"],
            "passes_screening_gate": guard["passes_screening_gate"],
            "negative_recall_datasets": guard.get("negative_recall_datasets", []),
            "suppression_datasets": guard.get("suppression_datasets", []),
            "latency_mean_extra_ms_per_all_queries": guard.get("latency_budget", {}).get(
                "mean_extra_ms_per_all_queries"
            ),
        }
        for guard in guard_audit.get("guard_summaries", [])[:8]
    ]

    conflict_views = [
        view["id"] for view in views if view["read"]["alignment"] in {"conflict", "tradeoff"}
    ]
    flat_views = [view["id"] for view in views if view["read"]["alignment"] == "flat"]

    return {
        "schema_version": "king-synapse.ranking-objective-conflict-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": report_path(Path(__file__)),
        "inputs": input_reports,
        "raw_records_committed": False,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "raw_memory_content_committed": False,
        "views": views,
        "guard_audit_read": {
            "best_safe_guard_id": guard_read.get("best_safe_guard_id"),
            "safe_guard_ids": guard_read.get("safe_guard_ids", []),
            "current_conclusion": guard_read.get("current_conclusion"),
            "top_guard_summaries": top_guard_summaries,
        },
        "read": {
            "conflict_or_tradeoff_views": conflict_views,
            "flat_views": flat_views,
            "global_default_candidate": None,
            "conclusion": (
                "Existing one-variable ranking evidence does not support a new "
                "global default. RRF k is mostly flat, vector weight improves "
                "coverage with MRR/top-1 tradeoffs, reranker-pool preferences "
                "diverge between DMR and LongMemEval, and pool-signal guards "
                "have no screened safe default."
            ),
            "next_ranking_gate": (
                "Future ranking work should use a new answer-free ordering "
                "signal or an explicit DMR/LongMemEval objective split, with "
                "zero LongMemEval top-10 suppressions before runtime adoption."
            ),
        },
        "limits": [
            "Reads sanitized aggregate ranking reports only.",
            "Does not inspect raw questions, answers, dialogs, sessions, memory content, or generated answer text.",
            "Does not change retrieval, ranking, memory schema, cognitive layers, CLI behavior, or runtime defaults.",
            "Views are based on existing checked sample sets; they are validation evidence, not product claims.",
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
                "conflict_or_tradeoff_views": report["read"]["conflict_or_tradeoff_views"],
                "flat_views": report["read"]["flat_views"],
                "global_default_candidate": report["read"]["global_default_candidate"],
                "guard_best_safe_guard_id": report["guard_audit_read"][
                    "best_safe_guard_id"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
