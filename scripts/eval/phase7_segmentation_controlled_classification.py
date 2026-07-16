#!/usr/bin/env python3
"""Run Phase 7.3.3-C offline readiness validation."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    subprocess.run(
        ["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_segmentation_controlled_classification"],
        cwd=ROOT,
        check=True,
    )
    import json
    report_path = ROOT / "crates/eval/reports/phase7_3_3_c_segmentation_controlled_readiness.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["status"] != "offline_protocol_ready_real_execution_not_started":
        raise RuntimeError(f"offline readiness failed: {report['status']}")
    print("Phase 7.3.3-C segmentation-controlled protocol: offline ready")
    print("Segmentation: protocol-owned and exact")
    print("Judge responsibility: local support classification only")
    print("Design / held-out / runtime / memory: blocked")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
