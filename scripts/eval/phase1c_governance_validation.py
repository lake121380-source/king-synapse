"""Phase 1c-6: Governance Validation.

Builds a DMR-derived TOML dataset and runs the independent
`kr-governance-eval` harness. The output is a standalone
GovernanceEvaluationReport, not the general recall benchmark report.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ["HF_HUB_OFFLINE"] = "1"

from longmem_dmr_smoke import (
    DMR_FILE,
    DMR_REPO,
    configure_accelerator_environment,
    default_cache_root,
    default_fastembed_cache_dir,
    download_dataset,
    eval_cargo_profile,
    read_jsonl,
    repo_root,
    write_toml_dataset,
)
from official_dmr_eval import build_official_dmr_dataset


def run_governance_eval(
    dataset_path: Path,
    output_path: Path,
    *,
    tag: str,
    k: int,
    vectors: bool,
    rerank: bool,
    rerank_pool: int,
    semantic_judge: str,
    semantic_edge_mode: str,
    semantic_judge_cache: bool,
    semantic_judge_cache_path: Path | None,
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
            "kr-governance-eval",
            "--",
            "--dataset",
            str(dataset_path),
            "--k",
            str(k),
            "--tag",
            tag,
            "--json",
            str(output_path),
            "--semantic-edge-mode",
            semantic_edge_mode,
            "--semantic-judge",
            semantic_judge,
        ]
    )
    if vectors:
        cmd.append("--vectors")
    if rerank:
        cmd.extend(["--rerank", "--rerank-pool", str(rerank_pool)])
    if not semantic_judge_cache:
        cmd.append("--no-semantic-judge-cache")
    if semantic_judge_cache_path is not None:
        cmd.extend(["--semantic-judge-cache-path", str(semantic_judge_cache_path)])

    result = subprocess.run(cmd, cwd=repo_root(), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"kr-governance-eval failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["cargo_profile"] = cargo_profile
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 1c governance validation.")
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--rerank-pool", type=int, default=10)
    parser.add_argument("--endpoint", default="https://huggingface.co")
    parser.add_argument("--semantic-judge", choices=("heuristic", "deepseek"), default="heuristic")
    parser.add_argument("--semantic-edge-mode", choices=("filter", "classify"), default="classify")
    parser.add_argument("--no-semantic-judge-cache", action="store_true")
    parser.add_argument("--semantic-judge-cache-path", type=Path)
    parser.add_argument("--output-path", type=Path)
    parser.add_argument("--no-vectors", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    args = parser.parse_args()

    cache = default_cache_root()
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, cache / "dmr-msc-self-instruct")
    rows = read_jsonl(dmr_path)
    memories, queries, _examples, _skipped = build_official_dmr_dataset(
        rows, args.sample_size, "significant_token_containment"
    )

    tmpdir = Path(tempfile.mkdtemp(prefix="phase1c-governance-"))
    dataset_path = tmpdir / f"dmr-{args.sample_size}.toml"
    write_toml_dataset(dataset_path, memories, queries)

    fastembed_dir = default_fastembed_cache_dir()
    fastembed_dir.mkdir(parents=True, exist_ok=True)
    configure_accelerator_environment(
        argparse.Namespace(
            accelerator="cpu",
            cuda_device_id=None,
            cuda_runtime_root=None,
            directml_device_id=None,
            fastembed_cache_dir=fastembed_dir,
            embed_batch_size=32,
            embed_max_length=256,
            rerank_batch_size=32,
            rerank_max_length=256,
        )
    )

    out_path = args.output_path or repo_root() / "crates/eval/reports/phase1c-governance-validation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = run_governance_eval(
        dataset_path,
        out_path,
        tag=f"phase1c-governance-validation-{args.sample_size}",
        k=args.k,
        vectors=not args.no_vectors,
        rerank=not args.no_rerank,
        rerank_pool=args.rerank_pool,
        semantic_judge=args.semantic_judge,
        semantic_edge_mode=args.semantic_edge_mode,
        semantic_judge_cache=not args.no_semantic_judge_cache,
        semantic_judge_cache_path=args.semantic_judge_cache_path,
    )
    print(
        "summary: detection={:.4f} intervention_gain={:.4f} regression_rate={:.4f} stability={:.4f}".format(
            report.get("detection_score", 0.0),
            report.get("intervention_gain", 0.0),
            report.get("regression_rate", 0.0),
            report.get("stability_score", 0.0),
        )
    )
    print(f"Saved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
