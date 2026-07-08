"""Phase 1c-12.5: Governance Soft Dominance & Influence Inertia."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_governance_soft_dominance_eval(
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
            "kr-governance-soft-dominance-eval",
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
            f"kr-governance-soft-dominance-eval failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 1c-12.5 governance soft dominance and influence inertia evaluation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=repo_root() / "crates/eval/datasets/governance_soft_dominance.toml",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root()
        / "crates/eval/reports/phase1c-governance-soft-dominance.json",
    )
    parser.add_argument("--tag", default="phase1c-governance-soft-dominance")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_governance_soft_dominance_eval(
        args.dataset, args.output_path, args.tag
    )
    print(
        "summary: dominance={:.4f}->{:.4f} gain={:+.4f} flexibility={:.4f} inertia_gain={:.4f} boundary_miss={:.4f} pass={}".format(
            report["baseline_dominance_score"],
            report["governed_dominance_score"],
            report["dominance_gain"],
            report["dominance_flexibility"],
            report["inertia_drag_reduction"],
            report["boundary_miss_rate"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
