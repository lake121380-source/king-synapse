"""Phase 3.4 Future Influence Experiment."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase3_future_influence(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-phase3-future-influence",
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
            "kr-phase3-future-influence failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
        description="Run Phase 3.4 future influence evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase3-future-influence.json",
    )
    parser.add_argument("--tag", default="phase3-future-influence")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase3_future_influence(args.output_path, args.tag)
    print(
        "summary: scenarios={} helpful={} neutral={} rejected={} gain={:.4f} decision={:.4f} failure_reduction={:.4f} usefulness={:.4f} safety={:.4f} pass={}".format(
            report["scenarios"],
            report["results"]["helpful_lessons"],
            report["results"]["neutral_lessons"],
            report["results"]["rejected_influence"],
            report["metrics"]["influence_gain_score"],
            report["metrics"]["decision_improvement_score"],
            report["metrics"]["failure_reduction_score"],
            report["metrics"]["lesson_usefulness_score"],
            report["metrics"]["no_write_safety"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    if report["pass"] and report["mode"] == "evaluation_only":
        print("Phase 3.4 Future Influence Experiment Completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
