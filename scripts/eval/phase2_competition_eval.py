"""Phase 2.3 Competition Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase2_competition_eval(dataset_dir: Path, output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-phase2-competition-eval",
            "--",
            "--dataset-dir",
            str(dataset_dir),
            "--json",
            str(output_path),
            "--tag",
            tag,
        ]
    )
    result = subprocess.run(cmd, cwd=repo_root(), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"kr-phase2-competition-eval failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 2.3 memory competition evaluation."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=repo_root() / "crates/eval/datasets/cognitive_memory",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase2-competition-eval.json",
    )
    parser.add_argument("--tag", default="phase2-competition-eval")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase2_competition_eval(args.dataset_dir, args.output_path, args.tag)
    print(
        "summary: cases={} baseline={:.4f} competition={:.4f} decision_mismatch_delta={:+} causal_order_error_delta={:+} suppression={:.4f} influence_shift={:.4f} pass={}".format(
            report["case_count"],
            report["baseline"]["score"],
            report["competition"]["score"],
            report["delta"]["decision_mismatch"],
            report["delta"]["causal_order_error"],
            report["delta"]["suppression_correctness"],
            report["delta"]["influence_shift"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    if report["pass"] and report["case_count"] == 200:
        print("Phase 2.3 Competition Evaluation Completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
