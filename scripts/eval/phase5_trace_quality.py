"""Phase 5.2 Cognitive Trace Quality Evaluation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import eval_cargo_profile, repo_root


def run_phase5_trace_quality(output_path: Path, tag: str) -> dict:
    cargo_profile = eval_cargo_profile()
    cmd = ["cargo", "run"]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
            "-p",
            "synapse-eval",
            "--bin",
            "phase5_trace_quality",
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
            "phase5_trace_quality failed\nSTDOUT:\n{}\nSTDERR:\n{}".format(
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
    thresholds = report["thresholds"]
    guards = report["guards"]
    judge = report["judge_protocol"]
    checks = [
        (
            "explanation_completeness",
            metrics["explanation_completeness"]
            >= thresholds["explanation_completeness"],
        ),
        (
            "factor_faithfulness",
            metrics["factor_faithfulness"] >= thresholds["factor_faithfulness"],
        ),
        (
            "trace_preference_rate",
            metrics["trace_preference_rate"] >= thresholds["trace_preference_rate"],
        ),
        ("determinism", metrics["determinism"] >= thresholds["determinism"]),
        ("eval_only", guards["eval_only"] is True),
        ("ranking_changed", guards["recall_ranking_changed"] is False),
        ("memory_written", guards["memory_written"] is False),
        ("activation_changed", guards["activation_changed"] is False),
        ("booster_enabled", guards["booster_enabled"] is False),
        ("external_judge_ready", judge["external_judge_ready"] is True),
        ("pass", report["pass"] is True),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise RuntimeError("Phase 5.2 validation failed: {}".format(", ".join(failed)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 5.2 cognitive trace quality evaluation."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=repo_root() / "crates/eval/reports/phase5_trace_quality.json",
    )
    parser.add_argument("--tag", default="phase5-trace-quality")
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_phase5_trace_quality(args.output_path, args.tag)
    validate_report(report)
    print("OK explanation completeness")
    print("OK factor faithfulness")
    print("OK deterministic preference rubric")
    print("OK trace determinism")
    print("OK eval-only guards")
    print(
        "summary: scenarios={} completeness={:.4f} faithfulness={:.4f} preference={:.4f} determinism={:.4f} information_gain={:+.4f} pass={}".format(
            report["scenarios"],
            report["metrics"]["explanation_completeness"],
            report["metrics"]["factor_faithfulness"],
            report["metrics"]["trace_preference_rate"],
            report["metrics"]["determinism"],
            report["metrics"]["explanation_information_gain"],
            report["pass"],
        )
    )
    print(f"Saved to {args.output_path}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
