#!/usr/bin/env python3
"""Run and validate the Phase 6.1 Cognitive vs Simple Baseline gate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


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
        "phase6_cognitive_baseline_comparison", "--",
        "--json", str(output_path), "--tag", tag,
    ])
    return json.loads(output_path.read_text(encoding="utf-8"))


def validate(report: dict) -> None:
    policies = {policy["policy"]: policy for policy in report["policies"]}
    ablations = {item["ablation"]: item for item in report["factor_ablations"]}
    decision = report["decision"]
    guards = report["guards"]
    expected_policies = {
        "retrieval_baseline",
        "confidence_only_margin_guarded",
        "recency_only_margin_guarded",
        "failure_only_margin_guarded",
        "simple_combined_margin_guarded",
        "margin_guard_cognitive",
    }
    expected_ablations = {
        "full_cognitive",
        "without_temporal",
        "without_failure",
        "without_reliability",
        "without_preference",
        "without_context",
    }
    simple_candidates = (
        policies["confidence_only_margin_guarded"],
        policies["recency_only_margin_guarded"],
        policies["failure_only_margin_guarded"],
        policies["simple_combined_margin_guarded"],
    )
    best_simple = policies[decision["best_simple_baseline"]]
    best_simple_metric = max(
        (item["metrics"]["mrr_at_5"], item["metrics"]["recall_at_1"])
        for item in simple_candidates
    )
    cognitive = policies["margin_guard_cognitive"]
    checks = [
        ("pass", report["pass"] is True),
        ("dataset_shape", report["dataset"]["scenarios"] == 320 and report["dataset"]["memories"] == 1920),
        ("policy_set", set(policies) == expected_policies),
        ("ablation_set", set(ablations) == expected_ablations),
        ("locked_alpha", report["protocol"]["policy_alpha"] == 0.20),
        ("locked_margin", report["protocol"]["margin_threshold"] == 0.08),
        ("deterministic", all(item["metrics"]["determinism"] == 1.0 for item in policies.values())),
        ("same_pool", all(item["candidate_pool_preserved"] is True for item in policies.values())),
        ("ablation_deterministic", all(item["metrics"]["determinism"] == 1.0 for item in ablations.values())),
        ("best_simple", (best_simple["metrics"]["mrr_at_5"], best_simple["metrics"]["recall_at_1"]) == best_simple_metric),
        ("mrr_gain", decision["cognitive_gain_vs_best_simple_baseline"] == cognitive["metrics"]["mrr_at_5"] - best_simple["metrics"]["mrr_at_5"]),
        ("recall_gain", decision["cognitive_recall_at_1_gain_vs_best_simple_baseline"] == cognitive["metrics"]["recall_at_1"] - best_simple["metrics"]["recall_at_1"]),
        ("observed_outcome", decision["outcome"] == "B_cognitive_matches_best_simple"),
        ("zero_authority", decision["zero_intervention_authority"] is True),
        ("attribution_unresolved", decision["attribution_resolved"] is False),
        ("no_independent_claim", decision["independent_value_supported"] is False),
        ("no_metadata_overclaim", decision["metadata_aggregation_only"] is False),
        ("no_hermes", decision["hermes_shadow_integration_recommended"] is False),
        ("eval_only", guards["eval_only"] is True and guards["shadow_only"] is True),
        ("baseline_authoritative", guards["baseline_authoritative"] is True),
        ("no_score_mutation", guards["retrieval_scores_mutated"] is False),
        ("no_candidate_change", guards["candidate_pool_changed"] is False),
        ("no_memory_mutation", guards["memory_mutated"] is False and guards["policy_memory_written"] is False),
        ("no_runtime", guards["runtime_applied"] is False and decision["runtime_authorization"] is False),
        ("no_production_claim", guards["production_claim_authorized"] is False),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise RuntimeError("Phase 6.1 gate failed: {}".format(", ".join(failed)))

    print("OK six fixed policies over 320 real-RecallEngine scenarios")
    print("OK five single-factor removals through the unchanged cognitive booster")
    print("OBSERVED Cognitive MRR@5 equals best simple baseline: {:.4f}".format(cognitive["metrics"]["mrr_at_5"]))
    print("OBSERVED locked Margin Guard competition-eligible rate = {:.4f}".format(cognitive["metrics"]["competition_eligible_rate"]))
    print("CONCLUSION independent value attribution unresolved; Hermes shadow integration not recommended")
    print("OK eval-only / shadow-only / no runtime authorization")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase6_cognitive_baseline_comparison.json",
    )
    parser.add_argument("--tag", default="phase6-cognitive-baseline-comparison")
    args = parser.parse_args()
    report = run(args.output, args.tag)
    validate(report)
    print(f"Saved to {args.output}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
