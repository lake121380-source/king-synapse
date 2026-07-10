"""Phase 5.3.2 Deterministic Cognitive Booster v0 shadow ranking evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase5_shadow_ranking(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "phase5_shadow_ranking",
            "--",
            "--json",
            str(output_path),
            "--tag",
            tag,
        ]
    )
    result = subprocess.run(cmd, cwd=repo_root(), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            "phase5_shadow_ranking failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
    metrics = report["metrics"]
    guards = report["guards"]
    checks = [
        ("bounded_rate", metrics["bounded_rate"] == 1.0),
        ("determinism", metrics["determinism"] == 1.0),
        ("max_bonus", metrics["max_proposed_bonus"] <= report["max_bonus"]),
        ("eval_only", guards["eval_only"] is True),
        ("shadow_only", guards["shadow_only"] is True),
        ("baseline_authoritative", guards["baseline_authoritative"] is True),
        ("runtime_applied", guards["runtime_applied"] is False),
        ("memory_written", guards["memory_written"] is False),
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
        raise RuntimeError(
            "Phase 5.3.2 validation failed: {}".format(", ".join(failed))
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 5.3.2 deterministic cognitive booster shadow ranking evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase5_shadow_ranking.json",
    )
    parser.add_argument("--tag", default="phase5-shadow-ranking")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase5_shadow_ranking(args.output_path, args.tag)
    validate_report(report)
    print("OK deterministic cognitive bonus")
    print("OK absolute bonus bound")
    print("OK baseline immutability")
    print("OK candidate-pool preservation")
    print("OK shadow-only safety guards")
    print(
        "summary: scenarios={} coverage={:.4f} changed_positions={} avg_abs_rank_delta={:.4f} recall_delta={:+.4f} mrr_delta={:+.4f} pass={}".format(
            report["scenarios"],
            report["metrics"]["proposal_coverage"],
            report["metrics"]["changed_positions"],
            report["metrics"]["avg_abs_rank_delta"],
            report["metrics"]["shadow_recall_delta"],
            report["metrics"]["shadow_mrr_delta"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
