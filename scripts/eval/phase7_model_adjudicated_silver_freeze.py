#!/usr/bin/env python3
"""Build and verify the immutable Phase 7.3.1-D model-adjudicated Silver artifact."""
from __future__ import annotations
import hashlib, json, os, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_model_adjudicated_silver_labels.json"
ADJUDICATION = ROOT / "crates/eval/datasets/pattern_extraction/phase7_3_1_adjudication_template.json"
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main() -> int:
    env = os.environ.copy(); env["CARGO_PROFILE_DEV_DEBUG"]="0"; env["CARGO_BUILD_JOBS"]="1"
    subprocess.run(["cargo","run","-p","synapse-eval","--bin","phase7_model_adjudicated_silver_freeze"],cwd=ROOT,env=env,check=True)
    artifact=json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert artifact["frozen"] is True
    assert artifact["label_status"] == "model_adjudicated_silver_not_human_gold"
    assert artifact["human_gold"] is False
    assert artifact["held_out_accessed"] is False
    assert artifact["claim_count"] == len(artifact["claims"]) == 77
    assert artifact["candidate_count"] == len(artifact["candidates"]) == 10
    assert artifact["lineage"]["adjudication_sha256"] == sha256(ADJUDICATION)
    assert artifact["scope_labels_adjudicated"] is False
    assert artifact["scope_calibration_available"] is False
    print("Phase: Phase 7.3.1-D Model-Adjudicated Silver Label Freeze")
    print("Frozen: 77 claims / 10 candidate aggregates")
    print("Status: model-adjudicated Silver, not human Gold")
    print("Scope calibration: unavailable")
    print("Held-out/runtime/Hermes/memory: blocked")
    print("PASS")
    return 0
if __name__ == "__main__": raise SystemExit(main())
