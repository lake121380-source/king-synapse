"""Phase 2.6 Temporal Influence Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase2_temporal_influence_eval(
    dataset_dir: Path, output_path: Path, tag: str
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
            "kr-phase2-temporal-influence-eval",
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
            "kr-phase2-temporal-influence-eval failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
        description="Run Phase 2.6 temporal influence evaluation."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=repo_root() / "crates/eval/datasets/cognitive_memory",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase2-temporal-influence-eval.json",
    )
    parser.add_argument("--tag", default="phase2-temporal-influence-eval")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase2_temporal_influence_eval(
        args.dataset_dir, args.output_path, args.tag
    )
    print(
        "summary: cases={} baseline={:.4f} temporal={:.4f} temporal_update={:.4f} obsolete_detection={:.4f} preservation={:.4f} causal_transition={:.4f} pass={}".format(
            report["case_count"],
            report["baseline"]["score"],
            report["temporal"]["score"],
            report["metrics"]["temporal_update_accuracy"],
            report["metrics"]["obsolete_memory_detection"],
            report["metrics"]["historical_preservation"],
            report["metrics"]["causal_transition_accuracy"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    if report["pass"] and report["case_count"] == 200:
        print("Phase 2.6 Temporal Influence Evaluation Completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
