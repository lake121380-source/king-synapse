"""Phase 1c-7: Governance Positive-Control & Recovery Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_governance_bias_eval(dataset_path: Path, output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-governance-bias-eval",
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
            f"kr-governance-bias-eval failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 1c-7 governance positive-control evaluation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=repo_root() / "crates/eval/datasets/governance_bias.toml",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase1c-governance-bias.json",
    )
    parser.add_argument("--tag", default="phase1c-governance-bias")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_governance_bias_eval(args.dataset, args.output_path, args.tag)
    print(
        "summary: detection={:.4f} suppression_gain={:.4f} recall_preservation={:.4f} over_suppression={:.4f} recovery={:.4f} pass={}".format(
            report.get("harmful_edge_detection_rate", 0.0),
            report.get("suppression_gain", 0.0),
            report.get("normal_recall_preservation", 0.0),
            report.get("over_suppression_rate", 0.0),
            report.get("recovery_score", 0.0),
            report.get("pass", False),
        )
    )
    print(f"Saved to {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
