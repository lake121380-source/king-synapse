"""Phase 1c-13: Governance Influence Regulation Boundary Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_governance_regulation_boundary_eval(
    dataset_path: Path, output_path: Path, tag: str
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
            "kr-governance-regulation-boundary-eval",
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
            f"kr-governance-regulation-boundary-eval failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 1c-13 governance influence regulation boundary evaluation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=repo_root() / "crates/eval/datasets/governance_regulation_boundary.toml",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root()
        / "crates/eval/reports/phase1c-governance-regulation-boundary.json",
    )
    parser.add_argument("--tag", default="phase1c-governance-regulation-boundary")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_governance_regulation_boundary_eval(
        args.dataset, args.output_path, args.tag
    )
    print(
        "summary: precision={:.4f} recall={:.4f} restraint={:.4f} exploration={:.4f} boundary={:.4f} pass={}".format(
            report["intervention_precision"],
            report["intervention_recall"],
            report["intervention_restraint"],
            report["exploration_preservation"],
            report["regulation_boundary_score"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
