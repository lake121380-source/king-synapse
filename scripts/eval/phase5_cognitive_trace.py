"""Phase 5.1 Cognitive Competition Trace Integration Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase5_cognitive_trace(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "phase5_cognitive_trace",
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
            "phase5_cognitive_trace failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
    guards = report["guards"]
    latency = report["latency"]
    checks = [
        ("trace_generation_rate", metrics["trace_generation_rate"] == 1.0),
        ("dominant_validity", metrics["dominant_validity"] == 1.0),
        ("factor_explanation_rate", metrics["factor_explanation_rate"] == 1.0),
        ("trace_determinism", metrics["trace_determinism"] == 1.0),
        ("recall_regression", metrics["recall_regression"] == 0.0),
        ("ranking_changed", guards["ranking_changed"] is False),
        ("memory_written", guards["memory_written"] is False),
        ("activation_changed", guards["activation_changed"] is False),
        ("latency_before_p50", latency["before"]["p50_ms"] >= 0.0),
        ("latency_after_p50", latency["after"]["p50_ms"] >= latency["before"]["p50_ms"]),
        ("pass", report["pass"] is True),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise RuntimeError("Phase 5.1 validation failed: {}".format(", ".join(failed)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 5.1 cognitive competition trace integration evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase5_cognitive_trace.json",
    )
    parser.add_argument("--tag", default="phase5-cognitive-trace")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase5_cognitive_trace(args.output_path, args.tag)
    validate_report(report)
    print("OK trace generated")
    print("OK recall unchanged")
    print("OK ranking unchanged")
    print("OK no memory mutation")
    print("OK latency recorded")
    print(
        "summary: scenarios={} trace_generation_rate={:.4f} dominant_validity={:.4f} factor_explanation_rate={:.4f} trace_determinism={:.4f} recall_regression={:.4f} pass={}".format(
            report["scenarios"],
            report["metrics"]["trace_generation_rate"],
            report["metrics"]["dominant_validity"],
            report["metrics"]["factor_explanation_rate"],
            report["metrics"]["trace_determinism"],
            report["metrics"]["recall_regression"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
