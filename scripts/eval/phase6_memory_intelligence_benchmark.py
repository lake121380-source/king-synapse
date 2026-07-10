#!/usr/bin/env python3
"""Run and validate the Phase 6.0 Memory Intelligence Benchmark gate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
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
    return result


def run(output_path: Path, tag: str) -> dict:
    run_command([
        sys.executable,
        "scripts/eval/generate_phase6_memory_intelligence_benchmark.py",
        "--check",
    ])
    run_command([
        "cargo", "run", "-p", "synapse-eval", "--bin",
        "phase6_memory_intelligence_benchmark", "--",
        "--json", str(output_path), "--tag", tag,
    ])
    return json.loads(output_path.read_text(encoding="utf-8"))


def validate(report: dict) -> None:
    dataset = report["dataset"]
    retrieval = report["retrieval"]
    guards = report["guards"]
    checks = [
        ("pass", report["pass"] is True),
        ("scenario_count", dataset["scenarios"] == 320),
        ("memory_count", dataset["memories"] == 1920),
        ("category_count", dataset["categories"] == 10),
        ("unique_queries", dataset["unique_queries"] == 320),
        ("template_variants", dataset["template_variants"] == 4),
        ("split_shape", dataset["split_counts"] == {"train": 160, "validation": 80, "test": 80}),
        ("intervention_mix", dataset["intervention_required"] == 224 and dataset["no_intervention"] == 96),
        ("expected_retrieved", retrieval["expected_candidate_retrieval_rate"] == 1.0),
        ("recall_at_3", retrieval["recall_at_3"] == 1.0),
        ("recall_at_5", retrieval["recall_at_5"] == 1.0),
        ("determinism", retrieval["determinism"] == 1.0),
        ("store_unchanged", retrieval["store_unchanged_rate"] == 1.0),
        ("label_alignment", retrieval["label_intent_alignment"] == 1.0),
        ("entity_neutral", retrieval["entity_candidates"] == 0),
        ("real_recall", guards["real_recall_engine_used"] is True),
        ("no_manual_scores", guards["artificial_baseline_scores_used"] is False),
        ("benchmark_only", guards["benchmark_only"] is True),
        ("no_algorithm_comparison", guards["algorithm_comparison_performed"] is False),
        ("no_cognitive_claim", guards["independent_cognitive_value_claimed"] is False),
        ("no_runtime", guards["runtime_authorization"] is False),
        ("no_production_claim", guards["production_claim_authorized"] is False),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise RuntimeError("Phase 6.0 gate failed: {}".format(", ".join(failed)))

    print("OK 320 deterministic Agent-memory scenarios / 1920 memories")
    print("OK fixed 160/80/80 split with 10 balanced categories")
    print("OK real RecallEngine scores; expected candidate reachability = 1.0000")
    print("OK benchmark-only: no cognitive comparison or runtime authorization")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase6_memory_intelligence_benchmark.json",
    )
    parser.add_argument("--tag", default="phase6-memory-intelligence-benchmark")
    args = parser.parse_args()
    report = run(args.output, args.tag)
    validate(report)
    print(f"Saved to {args.output}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
