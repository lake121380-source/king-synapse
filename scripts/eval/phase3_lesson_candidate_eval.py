"""Phase 3.2 Lesson Candidate Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase3_lesson_candidate_eval(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-phase3-lesson-candidate-eval",
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
            "kr-phase3-lesson-candidate-eval failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
        description="Run Phase 3.2 lesson candidate evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase3-lesson-candidate-eval.json",
    )
    parser.add_argument("--tag", default="phase3-lesson-candidate-eval")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase3_lesson_candidate_eval(args.output_path, args.tag)
    print(
        "summary: candidates={} accepted={} observe_more={} rejected={} grounding={:.4f} scope={:.4f} contradiction={:.4f} overgeneralization={:.4f} accept_precision={:.4f} agreement={:.4f} safety={:.4f} pass={}".format(
            report["candidate_count"],
            report["accepted"],
            report["observe_more"],
            report["rejected"],
            report["metrics"]["lesson_grounding_score"],
            report["metrics"]["lesson_scope_score"],
            report["metrics"]["contradiction_resistance_score"],
            report["metrics"]["overgeneralization_guard_score"],
            report["metrics"]["candidate_accept_precision"],
            report["metrics"]["candidate_decision_agreement"],
            report["metrics"]["promotion_safety"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    if report["pass"] and report["implementation_status"] == "evaluation_only":
        print("Phase 3.2 Lesson Candidate Evaluation Completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
