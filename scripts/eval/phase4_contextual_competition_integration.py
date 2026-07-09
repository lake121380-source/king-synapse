"""Phase 4.4 Contextual Competition Integration Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase4_contextual_competition_integration(
    output_path: Path, tag: str
) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "phase4_contextual_competition_integration",
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
            "phase4_contextual_competition_integration failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
    metric = report["metric"]
    checks = [
        ("context_flip_rate", metric["context_flip_rate"] >= 0.8),
        ("dominance_consistency", metric["dominance_consistency"] == 1.0),
        ("suppression_correctness", metric["suppression_correctness"] >= 0.9),
        ("ranking_stability", metric["ranking_stability"] == 1.0),
        ("core_changed", report["core_changed"] is False),
        ("memory_written", report["memory_written"] is False),
        ("runtime_weight_changed", report["runtime_weight_changed"] is False),
        ("pass", report["pass"] is True),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise RuntimeError("Phase 4.4 validation failed: {}".format(", ".join(failed)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 4.4 contextual competition integration evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root()
        / "crates/eval/reports/phase4_contextual_competition_integration.json",
    )
    parser.add_argument(
        "--tag", default="phase4-contextual-competition-integration"
    )
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase4_contextual_competition_integration(args.output_path, args.tag)
    validate_report(report)
    print("OK report generated")
    print("OK metrics valid")
    print("OK core unchanged")
    print("OK no memory mutation")
    print(
        "summary: scenarios={} context_flips={}/{} flip_rate={:.4f} dominance_consistency={:.4f} suppression_correctness={:.4f} ranking_stability={:.4f} pass={}".format(
            report["scenarios"],
            report["context_flips"]["changed"],
            report["context_flips"]["total"],
            report["metric"]["context_flip_rate"],
            report["metric"]["dominance_consistency"],
            report["metric"]["suppression_correctness"],
            report["metric"]["ranking_stability"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
