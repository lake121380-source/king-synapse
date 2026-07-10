#!/usr/bin/env python3
"""Run and validate the Phase 6.2 Recall Score Distribution Study."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path


EXPECTED_THRESHOLDS = [0.01, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_command(command: list[str]) -> None:
    env = os.environ.copy()
    env.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
    env.setdefault("CARGO_PROFILE_TEST_DEBUG", "0")
    result = subprocess.run(
        command,
        cwd=repo_root(),
        text=True,
        capture_output=True,
        env=env,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError("command failed: {}".format(" ".join(command)))


def run(output_path: Path, tag: str) -> dict:
    run_command([
        sys.executable,
        "scripts/eval/generate_phase6_memory_intelligence_benchmark.py",
        "--check",
    ])
    run_command([
        "cargo", "run", "-p", "synapse-eval", "--bin",
        "phase6_recall_score_distribution", "--",
        "--json", str(output_path), "--tag", tag,
    ])
    return json.loads(output_path.read_text(encoding="utf-8"))


def assert_summary(summary: dict, expected_count: int) -> None:
    assert summary["count"] == expected_count
    for key in ("min", "max", "mean", "median", "p50", "p90", "p95", "p99", "standard_deviation"):
        assert math.isfinite(summary[key]), (key, summary[key])
    assert summary["min"] <= summary["p50"] <= summary["p90"]
    assert summary["p90"] <= summary["p95"] <= summary["p99"]
    assert summary["p99"] <= summary["max"]
    assert abs(summary["median"] - summary["p50"]) <= 1e-12


def validate(report: dict) -> None:
    protocol = report["protocol"]
    dataset = report["dataset"]
    candidate_count = report["candidate_count"]
    score_distribution = report["score_distribution"]
    adjacent = report["adjacent_gaps"]
    coverages = report["margin_coverage"]
    decision = report["decision"]
    guards = report["guards"]

    assert report["phase"] == "Phase 6.2 Recall Score Distribution Study"
    assert report["status"] == "PASS"
    assert report["pass"] is True
    assert dataset["scenarios"] == 320
    assert dataset["memories"] == 1920
    assert dataset["categories"] == 10
    assert protocol["candidate_limit"] == 5
    assert protocol["locked_margin_threshold"] == 0.08
    assert protocol["locked_policy_alpha"] == 0.20
    assert protocol["analyzed_thresholds"] == EXPECTED_THRESHOLDS
    assert protocol["threshold_policy"] == "descriptive_only_no_threshold_selection_or_tuning"

    assert candidate_count["scenarios"] == 320
    assert candidate_count["histogram"] == {"5": 320}
    assert_summary(candidate_count["summary"], 320)
    assert abs(candidate_count["summary"]["mean"] - 5.0) <= 1e-12

    assert_summary(score_distribution["all_candidates"], 1600)
    assert len(score_distribution["by_rank"]) == 5
    for index, item in enumerate(score_distribution["by_rank"], start=1):
        assert item["rank"] == index
        assert_summary(item["summary"], 320)

    assert len(adjacent) == 4
    for index, item in enumerate(adjacent, start=1):
        assert item["left_rank"] == index
        assert item["right_rank"] == index + 1
        assert_summary(item["raw_gap"], 320)
        assert_summary(item["adjacent_normalized_gap"], 320)
        assert_summary(item["top_relative_gap"], 320)
        assert item["raw_gap"]["min"] >= 0.0
        assert item["adjacent_normalized_gap"]["min"] >= 0.0

    assert [item["threshold"] for item in coverages] == EXPECTED_THRESHOLDS
    assert all(item["scenarios"] == 320 for item in coverages)
    assert all(
        left["eligible_scenarios"] <= right["eligible_scenarios"]
        for left, right in zip(coverages, coverages[1:])
    )
    locked = next(item for item in coverages if item["is_locked_margin"])
    assert locked["threshold"] == 0.08
    assert locked["eligible_scenarios"] == 0
    assert locked["eligible_rate"] == 0.0
    assert decision["locked_margin_eligible_scenarios"] == 0
    assert decision["locked_margin_eligible_rate"] == 0.0
    assert decision["observed_minimum_top1_top2_normalized_gap"] > 0.08
    assert decision["current_margin_below_observed_minimum_gap"] is True
    assert decision["current_margin_has_authority"] is False
    assert decision["threshold_selection_performed"] is False
    assert decision["margin_redesign_authorized"] is False
    assert decision["cognitive_value_evaluated"] is False
    assert decision["cognitive_failure_inferred"] is False
    assert decision["hermes_shadow_integration_recommended"] is False
    assert decision["runtime_authorization"] is False
    assert decision["production_claim_authorized"] is False

    required_true = (
        "eval_only",
        "distribution_study_only",
        "real_recall_engine_used",
        "source_phase6_benchmark_passed",
    )
    required_false = (
        "recall_engine_modified",
        "cognitive_booster_modified",
        "cognitive_algorithm_executed",
        "threshold_modified",
        "alpha_modified",
        "threshold_selected_from_results",
        "ranking_modified",
        "retrieval_scores_mutated",
        "candidate_generation_modified",
        "candidate_pool_changed",
        "memory_written",
        "memory_mutated",
        "memory_schema_changed",
        "runtime_applied",
        "hermes_integration_performed",
        "runtime_authorization",
        "production_claim_authorized",
    )
    assert all(guards[key] is True for key in required_true)
    assert all(guards[key] is False for key in required_false)
    assert len(report["scenarios"]) == 320
    assert all(item["score_order_valid"] for item in report["scenarios"])
    assert all(item["retrieval_deterministic"] for item in report["scenarios"])
    assert all(not item["locked_margin_triggered"] for item in report["scenarios"])


def print_summary(report: dict) -> None:
    top12 = report["adjacent_gaps"][0]["top_relative_gap"]
    print("Phase:", report["phase"])
    print(
        "Dataset: queries={} memories={} candidates={}".format(
            report["dataset"]["scenarios"],
            report["dataset"]["memories"],
            report["score_distribution"]["all_candidates"]["count"],
        )
    )
    print(
        "Top1-Top2 normalized gap: min={:.6f} mean={:.6f} median={:.6f} P90={:.6f} P95={:.6f} P99={:.6f}".format(
            top12["min"], top12["mean"], top12["median"],
            top12["p90"], top12["p95"], top12["p99"],
        )
    )
    print("Margin coverage:")
    for item in report["margin_coverage"]:
        print(
            "  {:.2f}: {:>3}/{} ({:.4f})".format(
                item["threshold"], item["eligible_scenarios"],
                item["scenarios"], item["eligible_rate"],
            )
        )
    print("Hermes shadow integration recommended: false")
    print("Runtime authorized: false")
    print("PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase6_recall_score_distribution.json",
    )
    parser.add_argument("--tag", default="phase6-recall-score-distribution")
    args = parser.parse_args()
    output_path = args.json.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run(output_path, args.tag)
    validate(report)
    print_summary(report)
    print("Saved to", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
