"""Phase 4.5 Cognitive Competition Stability Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase4_cognitive_competition_stability(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "phase4_cognitive_competition_stability",
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
            "phase4_cognitive_competition_stability failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
                result.stdout, result.stderr
            )
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def validate_report(report: dict) -> None:
    metrics = report["metrics"]
    checks = [
        ("dominance_stability", metrics["dominance_stability"] == 1.0),
        ("noise_resistance", metrics["noise_resistance"] >= 0.90),
        ("transition_consistency", metrics["transition_consistency"] == 1.0),
        ("oscillation_rate", metrics["oscillation_rate"] == 0.0),
        ("core_changed", report["core_changed"] is False),
        ("memory_written", report["memory_written"] is False),
        ("runtime_weight_changed", report["runtime_weight_changed"] is False),
        ("pass", report["pass"] is True),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise RuntimeError("Phase 4.5 validation failed: {}".format(", ".join(failed)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 4.5 cognitive competition stability evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root()
        / "crates/eval/reports/phase4_cognitive_competition_stability.json",
    )
    parser.add_argument("--tag", default="phase4-cognitive-competition-stability")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase4_cognitive_competition_stability(args.output_path, args.tag)
    validate_report(report)
    print("OK report exists")
    print("OK metrics >= threshold")
    print("OK no core change")
    print("OK no memory mutation")
    print(
        "summary: dominance={:.4f} noise={:.4f} transition={:.4f} oscillation={:.4f} pass={}".format(
            report["metrics"]["dominance_stability"],
            report["metrics"]["noise_resistance"],
            report["metrics"]["transition_consistency"],
            report["metrics"]["oscillation_rate"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
