"""Phase 4.2 Cognitive Competition Model."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase4_cognitive_competition(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-phase4-cognitive-competition",
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
            "kr-phase4-cognitive-competition failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
                result.stdout, result.stderr
            )
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 4.2 cognitive competition evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase4-cognitive-competition.json",
    )
    parser.add_argument("--tag", default="phase4-cognitive-competition")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase4_cognitive_competition(args.output_path, args.tag)
    print(
        "summary: scenarios={} dominant={:.4f} convergence={:.4f} suppression={:.4f} stability={:.4f} explanation={:.4f} core_changed={} memory_written={} runtime_activation_changed={} pass={}".format(
            report["scenarios"],
            report["metrics"]["dominant_selection_accuracy"],
            report["metrics"]["competition_convergence"],
            report["metrics"]["suppression_quality"],
            report["metrics"]["activation_stability"],
            report["metrics"]["explanation_quality"],
            report["safety"]["core_changed"],
            report["safety"]["memory_written"],
            report["safety"]["runtime_activation_changed"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    if report["pass"] and report["mode"] == "evaluation_only":
        print("Phase 4.2 Cognitive Competition Model Completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
