"""Phase 1c-9: Governance Counterfactual Replay."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_governance_replay_eval(
    dataset_path: Path, feedback_dataset_path: Path, output_path: Path, tag: str
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
            "kr-governance-replay-eval",
            "--",
            "--dataset",
            str(dataset_path),
            "--feedback-dataset",
            str(feedback_dataset_path),
            "--json",
            str(output_path),
            "--tag",
            tag,
        ]
    )
    result = subprocess.run(cmd, cwd=repo_root(), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"kr-governance-replay-eval failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 1c-9 governance counterfactual replay evaluation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=repo_root() / "crates/eval/datasets/governance_replay.toml",
    )
    parser.add_argument(
        "--feedback-dataset",
        type=Path,
        default=repo_root() / "crates/eval/datasets/governance_feedback.toml",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase1c-governance-replay.json",
    )
    parser.add_argument("--tag", default="phase1c-governance-replay")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_governance_replay_eval(
        args.dataset, args.feedback_dataset, args.output_path, args.tag
    )
    print(
        "summary: accuracy={:.4f}->{:.4f} gain={:+.4f} regret={:.4f}->{:.4f} reduction={:+.4f} pass={}".format(
            report["baseline_accuracy"],
            report["governed_accuracy"],
            report["counterfactual_gain"],
            report["baseline_regret"],
            report["governed_regret"],
            report["regret_reduction"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
