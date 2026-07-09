"""Phase 2.8 Temporal Stress Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase2_temporal_stress_eval(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-phase2-temporal-stress-eval",
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
            "kr-phase2-temporal-stress-eval failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
        description="Run Phase 2.8 temporal stress evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase2-temporal-stress-eval.json",
    )
    parser.add_argument("--tag", default="phase2-temporal-stress-eval")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase2_temporal_stress_eval(args.output_path, args.tag)
    print(
        "summary: scenarios={} oscillation={:.4f} delayed={:.4f} false_contradiction={:.4f} recovery_signal={:.4f} state_recovery={:.4f} preservation={:.4f} stability={:.4f} pass={}".format(
            report["scenario_count"],
            report["metrics"]["oscillation_resistance"],
            report["metrics"]["delayed_contradiction_handling"],
            report["metrics"]["false_contradiction_restraint"],
            report["metrics"]["memory_recovery_signal"],
            report["metrics"]["state_recovery"],
            report["metrics"]["historical_preservation"],
            report["metrics"]["stability_score"],
            report["pass"],
        )
    )
    if report["limitations"]:
        print("limitations:")
        for limitation in report["limitations"]:
            print(f"- {limitation}")
    print(f"Saved to {args.output_path}")
    if report["pass"] and report["scenario_count"] == 4:
        print("Phase 2.8 Temporal Stress Evaluation Completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
