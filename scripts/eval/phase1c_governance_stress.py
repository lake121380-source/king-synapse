"""Phase 1c-7.5: Mixed Reality Governance Stress Test."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_governance_stress_eval(dataset_path: Path, output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-governance-stress-eval",
            "--",
            "--dataset",
            str(dataset_path),
            "--json",
            str(output_path),
            "--tag",
            tag,
        ]
    )
    result = subprocess.run(cmd, cwd=repo_root(), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"kr-governance-stress-eval failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 1c-7.5 mixed reality governance stress test."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=repo_root() / "crates/eval/datasets/governance_stress.toml",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase1c-governance-stress.json",
    )
    parser.add_argument("--tag", default="phase1c-governance-stress")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_governance_stress_eval(args.dataset, args.output_path, args.tag)
    print(
        "summary: harmful_detection={:.4f} false_positive={:.4f} ambiguous_calibration={:.4f} longitudinal_recovery={:.4f} recall_preservation={:.4f} over_suppression={:.4f} pass={}".format(
            report.get("harmful_detection_rate", 0.0),
            report.get("false_positive_rate", 0.0),
            report.get("ambiguous_calibration_score", 0.0),
            report.get("longitudinal_recovery_score", 0.0),
            report.get("normal_recall_preservation", 0.0),
            report.get("over_suppression_rate", 0.0),
            report.get("pass", False),
        )
    )
    print(f"Saved to {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
