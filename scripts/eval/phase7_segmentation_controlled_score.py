#!/usr/bin/env python3
"""Run the frozen Rust scorer for Phase 7.3.3-C."""
from __future__ import annotations
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
raise SystemExit(subprocess.call(["cargo", "run", "-p", "synapse-eval", "--bin", "phase7_segmentation_controlled_score"], cwd=ROOT))
