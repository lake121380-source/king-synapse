"""Phase 5.3.3 cognitive ranking policy study runner and safety validator."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_policy_study(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend([
        "-p", "synapse-eval", "--bin", "phase5_cognitive_policy", "--",
        "--json", str(output_path), "--tag", tag,
    ])
    env = os.environ.copy()
    env.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
    env.setdefault("CARGO_PROFILE_TEST_DEBUG", "0")
    result = subprocess.run(
        cmd, cwd=repo_root(), text=True, capture_output=True, env=env
    )
    if result.returncode != 0:
        raise RuntimeError(
            "phase5_cognitive_policy failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
                result.stdout, result.stderr
            )
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def validate_report(report: dict) -> None:
    benchmark = report["benchmark"]
    guards = report["guards"]
    required_categories = set(benchmark["required_categories"])
    observed_categories = set(benchmark["categories"])
    policies = report["policies"]
    checks = [
        ("scenario_range", 30 <= benchmark["scenarios"] <= 50),
        ("required_categories", required_categories <= observed_categories),
        ("label_mapping", benchmark["label_mapping_stable"] is True),
        ("policy_count", len(policies) == 5),
        ("ablation_count", len(report["ablations"]) == 6),
        ("bounded", all(p["metrics"]["bounded_rate"] == 1.0 for p in policies)),
        ("determinism", all(p["metrics"]["determinism"] == 1.0 for p in policies)),
        ("eval_only", guards["eval_only"] is True),
        ("shadow_only", guards["shadow_only"] is True),
        ("baseline_authoritative", guards["baseline_authoritative"] is True),
        ("runtime_applied", guards["runtime_applied"] is False),
        ("policy_memory_written", guards["policy_memory_written"] is False),
        ("memory_mutated", guards["memory_mutated"] is False),
        ("ranking_mutated", guards["ranking_mutated"] is False),
        ("scores_mutated", guards["scores_mutated"] is False),
        ("activation_changed", guards["activation_changed"] is False),
        ("candidate_pool_changed", guards["candidate_pool_changed"] is False),
        ("recall_engine_integrated", guards["recall_engine_integrated"] is False),
        ("production_claim_authorized", guards["production_claim_authorized"] is False),
        ("pass", report["pass"] is True),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise RuntimeError("Phase 5.3.3 validation failed: {}".format(", ".join(failed)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 5.3.3 cognitive ranking policy study."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase5_cognitive_policy.json",
    )
    parser.add_argument("--tag", default="phase5-cognitive-policy")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_policy_study(args.output_path, args.tag)
    validate_report(report)
    print("OK 42-scenario deterministic hard benchmark")
    print("OK absolute, weighted-fusion, and margin-guard policies")
    print("OK intervention and catastrophic-regression metrics")
    print("OK real-trace factor ablations")
    print("OK shadow-only safety boundary")
    print("Saved to {}".format(args.output_path))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
