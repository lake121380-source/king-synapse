"""Phase 5.3.4 locked-policy cognitive generalization validation runner."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_generalization(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend([
        "-p", "synapse-eval", "--bin", "phase5_cognitive_generalization", "--",
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
            "phase5_cognitive_generalization failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
    guards = report["guards"]
    decision = report["hidden_test_decision"]
    splits = {split_report["split"]: split_report for split_report in report["splits"]}
    expected_counts = {"train": 30, "validation": 12, "test": 21}
    checks = [
        ("split_names", set(splits) == set(expected_counts)),
        ("split_counts", all(
            splits[name]["benchmark"]["scenarios"] == count
            for name, count in expected_counts.items()
        )),
        ("four_policies", all(len(split["policies"]) == 4 for split in splits.values())),
        ("dataset_hashes", all(len(split["dataset_sha256"]) == 64 for split in splits.values())),
        ("locked_parameters", report["policy_lock"]["locked_before_hidden_test"] is True),
        ("no_hidden_search", report["policy_lock"]["hidden_test_parameter_search_performed"] is False),
        ("controlled_generalization", decision["controlled_generalization_supported"] is True),
        ("no_runtime_authorization", decision["runtime_authorization"] is False),
        ("no_end_to_end_claim", decision["end_to_end_generalization_proven"] is False),
        ("factor_interactions", len(report["factor_interactions"]) == 7),
        ("determinism", all(
            policy["metrics"]["determinism"] == 1.0
            for split in splits.values() for policy in split["policies"]
        )),
        ("bounded", all(
            policy["metrics"]["bounded_rate"] == 1.0
            for split in splits.values() for policy in split["policies"]
        )),
        ("candidate_pool_preserved", all(
            policy["candidate_pool_preserved"] is True
            for split in splits.values() for policy in split["policies"]
        )),
        ("policy_runtime_applied", all(
            policy["runtime_applied"] is False
            for split in splits.values() for policy in split["policies"]
        )),
        ("eval_only", guards["eval_only"] is True),
        ("shadow_only", guards["shadow_only"] is True),
        ("split_ids_disjoint", guards["split_ids_disjoint"] is True),
        ("hidden_not_tuned", guards["hidden_test_used_for_tuning"] is False),
        ("runtime_applied", guards["runtime_applied"] is False),
        ("memory_mutated", guards["memory_mutated"] is False),
        ("ranking_mutated", guards["ranking_mutated"] is False),
        ("scores_mutated", guards["scores_mutated"] is False),
        ("activation_changed", guards["activation_changed"] is False),
        ("candidate_pool_changed", guards["candidate_pool_changed"] is False),
        ("recall_engine_integrated", guards["recall_engine_integrated"] is False),
        ("production_claim", guards["production_claim_authorized"] is False),
        ("end_to_end_claim", guards["end_to_end_claim_authorized"] is False),
        ("pass", report["pass"] is True),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise RuntimeError("Phase 5.3.4 validation failed: {}".format(", ".join(failed)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 5.3.4 cognitive policy generalization validation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase5_cognitive_generalization.json",
    )
    parser.add_argument("--tag", default="phase5-cognitive-generalization")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_generalization(args.output_path, args.tag)
    validate_report(report)
    decision = report["hidden_test_decision"]
    print("OK locked 30/12/21 train-validation-hidden split")
    print("OK retrieval, metadata, recency, and margin-guard comparison")
    print("OK hidden Margin Guard MRR {:.4f}".format(decision["hidden_margin_guard_mrr"]))
    print("OK factor interaction study")
    print("OK shadow-only safety boundary")
    print("Saved to {}".format(args.output_path))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
