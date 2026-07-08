"""Phase 1 Final Validation: Cognitive Memory Benchmark."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


VERSION = "v0.6.0-cognitive-validation"
STATUS = "frozen"
PHASE = "phase1_complete"


def run_phase1_final_validation(dataset_dir: Path, output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "kr-cognitive-memory-benchmark",
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
            f"kr-cognitive-memory-benchmark failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def write_phase1_summary(report: dict, summary_path: Path) -> dict:
    summary = {
        "version": VERSION,
        "status": STATUS,
        "cases": report["case_count"],
        "score": round(report["full_synapse_score"], 4),
        "baseline": round(report["best_rag_score"], 4),
        "gain": round(report["full_over_best_rag_gain"], 4),
        "retrieval_failures": report["error_analysis"]["retrieval_failure_count"],
        "reasoning_failures": report["error_analysis"]["reasoning_failure_count"],
        "phase": PHASE,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 1 final cognitive memory validation benchmark."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=repo_root() / "crates/eval/datasets/cognitive_memory",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase1-final-validation.json",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase1-summary.json",
    )
    parser.add_argument("--tag", default="phase1-final-validation")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase1_final_validation(args.dataset_dir, args.output_path, args.tag)
    summary = write_phase1_summary(report, args.summary_path)
    print(
        "summary: stage={} cases={} challenges={} failed={} retrieval_fail={} reasoning_fail={} influence_gain={:+.4f} full={:.4f} best_rag={}:{:.4f} gain={:+.4f} trace={:.4f} contradiction={:.4f} multi_hop={:.4f} longitudinal={:.4f} pass={}".format(
            report["validation_stage"],
            report["case_count"],
            report["challenge_count"],
            len(report["failed_cases"]),
            report["error_analysis"]["retrieval_failure_count"],
            report["error_analysis"]["reasoning_failure_count"],
            report["memory_influence_attribution"]["full_over_best_rag_influence_gain"],
            report["full_synapse_score"],
            report["best_rag_method"],
            report["best_rag_score"],
            report["full_over_best_rag_gain"],
            report["trace_quality"]["score"],
            report["trace_quality"]["contradiction_handling"],
            report["multi_hop_reasoning_score"],
            report["longitudinal_influence_score"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    print(f"Summary saved to {args.summary_path}")
    if summary["phase"] == PHASE and report["pass"]:
        print("Phase 1 Closure Completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
