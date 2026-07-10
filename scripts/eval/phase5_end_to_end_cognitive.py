#!/usr/bin/env python3
"""Run and validate the Phase 5.4 independent end-to-end shadow experiment."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run(output_path: Path, tag: str) -> dict:
    command = [
        "cargo", "run", "-p", "synapse-eval", "--bin", "phase5_end_to_end_cognitive", "--",
        "--json", str(output_path), "--tag", tag,
    ]
    env = os.environ.copy()
    env.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
    env.setdefault("CARGO_PROFILE_TEST_DEBUG", "0")
    result = subprocess.run(command, cwd=repo_root(), text=True, capture_output=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(
            "phase5_end_to_end_cognitive failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
                result.stdout, result.stderr
            )
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return json.loads(output_path.read_text(encoding="utf-8"))


def validate(report: dict) -> None:
    policies = {policy["family"]: policy for policy in report["policies"]}
    expected = {
        "retrieval_baseline", "confidence_boost", "recency_boost",
        "failure_boost", "margin_guard_cognitive",
    }
    guards = report["guards"]
    decision = report["decision"]
    epsilon = 1e-12
    observed_value_decision = (
        decision["cognitive_beats_baseline"]
        and decision["cognitive_beats_confidence"]
        and decision["cognitive_beats_recency"]
        and decision["cognitive_beats_failure"]
        and decision["safety_preserved"]
    )
    best_control = max(
        decision["confidence_mrr_at_5"],
        decision["recency_mrr_at_5"],
        decision["failure_mrr_at_5"],
    )
    checks = [
        ("scenario_count", report["dataset"]["scenarios"] == 24),
        ("policy_set", set(policies) == expected),
        ("real_recall", guards["real_recall_engine_used"] is True),
        ("no_manual_scores", guards["artificial_baseline_scores_used"] is False),
        ("expected_retrieved", report["dataset"]["expected_candidate_retrieval_rate"] == 1.0),
        ("candidate_pool", all(policy["candidate_pool_preserved"] for policy in policies.values())),
        ("determinism", all(policy["metrics"]["determinism"] == 1.0 for policy in policies.values())),
        ("decision_consistency",
         decision["independent_end_to_end_value_supported"] is observed_value_decision),
        ("best_control_consistency",
         abs(decision["best_simple_control_mrr_at_5"] - best_control) <= epsilon),
        ("control_delta_consistency",
         abs(decision["cognitive_delta_vs_best_simple_control"]
             - (decision["cognitive_mrr_at_5"] - best_control)) <= epsilon),
        ("cognitive_safety", decision["safety_preserved"] is True),
        ("protocol_pass", report["pass"] is True),
        ("shadow_only", guards["shadow_only"] is True),
        ("runtime_applied", guards["runtime_applied"] is False),
        ("memory_mutated", guards["memory_mutated"] is False),
        ("ranking_mutated", guards["ranking_mutated"] is False),
        ("candidate_changed", guards["candidate_pool_changed"] is False),
        ("runtime_authorization", decision["runtime_authorization"] is False),
        ("production_claim", decision["production_claim_authorized"] is False),
    ]
    failed = [name for name, passed in checks if not passed]
    if failed:
        raise RuntimeError("Phase 5.4 validation failed: {}".format(", ".join(failed)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase5_end_to_end_cognitive.json",
    )
    parser.add_argument("--tag", default="phase5-end-to-end-cognitive")
    args = parser.parse_args()
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run(args.output_path, args.tag)
    validate(report)
    decision = report["decision"]
    print("OK real RecallEngine RecallHit scores; no artificial baseline_score")
    print("OK baseline plus confidence/recency/failure/cognitive controls")
    print("OK cognitive MRR@5 {:.4f}".format(decision["cognitive_mrr_at_5"]))
    print("OBSERVED independent end-to-end value supported: {}".format(
        str(decision["independent_end_to_end_value_supported"]).lower()
    ))
    print("OBSERVED cognitive delta vs best simple control: {:.4f}".format(
        decision["cognitive_delta_vs_best_simple_control"]
    ))
    print("OK shadow-only safety boundary; runtime authorization remains false")
    print("Saved to {}".format(args.output_path))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
