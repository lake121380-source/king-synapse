"""Phase 3.5 Lesson Lifecycle Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase3_lesson_lifecycle(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-phase3-lesson-lifecycle",
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
            "kr-phase3-lesson-lifecycle failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
        description="Run Phase 3.5 lesson lifecycle evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase3-lesson-lifecycle.json",
    )
    parser.add_argument("--tag", default="phase3-lesson-lifecycle")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase3_lesson_lifecycle(args.output_path, args.tag)
    print(
        "summary: scenarios={} active={} challenged={} superseded={} candidate={} transition={:.4f} contradiction={:.4f} supersession={:.4f} reinforcement={:.4f} protection={:.4f} safety={:.4f} pass={}".format(
            report["scenarios"],
            report["states"]["active"],
            report["states"]["challenged"],
            report["states"]["superseded"],
            report["states"]["candidate"],
            report["metrics"]["lifecycle_transition_accuracy"],
            report["metrics"]["contradiction_response_score"],
            report["metrics"]["supersession_score"],
            report["metrics"]["reinforcement_score"],
            report["metrics"]["false_lesson_protection_score"],
            report["metrics"]["lifecycle_safety"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    if report["pass"] and report["mode"] == "evaluation_only":
        print("Phase 3.5 Lesson Lifecycle Evaluation Completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
