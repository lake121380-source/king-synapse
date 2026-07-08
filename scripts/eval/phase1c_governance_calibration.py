"""Phase 1c-7.6: Governance Risk Calibration Sweep."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_governance_calibration_eval(dataset_path: Path, output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-governance-calibration-eval",
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
            f"kr-governance-calibration-eval failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 1c-7.6 governance risk calibration sweep."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=repo_root() / "crates/eval/datasets/governance_stress.toml",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase1c-governance-calibration.json",
    )
    parser.add_argument("--tag", default="phase1c-governance-calibration")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_governance_calibration_eval(args.dataset, args.output_path, args.tag)
    best = report.get("best_candidate")
    if best:
        best_summary = (
            f"{best['name']} detection={best['harmful_detection_rate']:.4f} "
            f"fp={best['false_positive_rate']:.4f} "
            f"preservation={best['normal_recall_preservation']:.4f} "
            f"over={best['over_suppression_rate']:.4f}"
        )
    else:
        best_summary = "<none>"
    print(
        "summary: baseline_detection={:.4f} baseline_fp={:.4f} best={} frontier={}".format(
            report["baseline"]["harmful_detection_rate"],
            report["baseline"]["false_positive_rate"],
            best_summary,
            len(report.get("pareto_frontier", [])),
        )
    )
    print(f"Saved to {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
