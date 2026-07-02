#!/usr/bin/env python
"""LongMemEval / DMR smoke runner for system validation.

This script downloads external datasets into a user cache, builds temporary
TOML datasets for the existing `kr-eval` binary, and writes a sanitized
aggregate report. It must not commit raw third-party records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download


LONGMEM_REPO = "xiaowu0162/longmemeval-cleaned"
LONGMEM_FILE = "longmemeval_s_cleaned.json"
DMR_REPO = "MemGPT/MSC-Self-Instruct"
DMR_FILE = "msc_self_instruct.jsonl"
SMOKE_CONFIGS = (
    {
        "id": "baseline-rrf",
        "label": "baseline RRF",
        "tag_suffix": "",
        "vectors": False,
        "rerank": False,
        "rerank_pool": 50,
    },
    {
        "id": "vectors",
        "label": "RRF + vectors",
        "tag_suffix": "-vectors",
        "vectors": True,
        "rerank": False,
        "rerank_pool": 50,
    },
    {
        "id": "vectors-rerank",
        "label": "RRF + vectors + reranker",
        "tag_suffix": "-vectors-rerank",
        "vectors": True,
        "rerank": True,
        "rerank_pool": 50,
    },
)

SMOKE_CONFIG_ALIASES = {
    "baseline": "baseline-rrf",
    "rrf": "baseline-rrf",
    "baseline-rrf": "baseline-rrf",
    "vector": "vectors",
    "vectors": "vectors",
    "vector-rerank": "vectors-rerank",
    "vectors-rerank": "vectors-rerank",
    "vector+rerank": "vectors-rerank",
    "all": "all",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_cache_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "king-synapse" / "eval"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "king-synapse" / "eval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LongMemEval / DMR smoke validation.")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--output", type=Path, default=repo_root() / "crates/eval/reports/longmem-dmr-smoke-latest.json")
    parser.add_argument(
        "--modes",
        default="all",
        help="Comma-separated smoke modes: all, baseline-rrf, vectors, vectors-rerank.",
    )
    parser.add_argument("--longmem-sample-size", type=int, default=10)
    parser.add_argument("--dmr-sample-size", type=int, default=20)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--cleanup-cache", action="store_true")
    return parser.parse_args()


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_info(api: HfApi, repo_id: str) -> dict[str, Any]:
    info = api.dataset_info(repo_id)
    card = getattr(info, "card_data", None)
    license_name = None
    if card is not None:
        try:
            license_name = card.get("license")
        except AttributeError:
            license_name = getattr(card, "license", None)
    return {
        "repo_id": repo_id,
        "revision": getattr(info, "sha", None),
        "license": license_name,
    }


def download_dataset(repo_id: str, filename: str, endpoint: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            endpoint=endpoint,
            local_dir=cache_dir,
        )
    )


def parse_smoke_modes(raw: str) -> list[dict[str, Any]]:
    requested = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not requested:
        requested = ["all"]
    canonical: list[str] = []
    for part in requested:
        if part not in SMOKE_CONFIG_ALIASES:
            raise ValueError(f"unknown smoke mode: {part}")
        canonical_name = SMOKE_CONFIG_ALIASES[part]
        if canonical_name == "all":
            return list(SMOKE_CONFIGS)
        canonical.append(canonical_name)
    seen: set[str] = set()
    selected: list[dict[str, Any]] = []
    for config in SMOKE_CONFIGS:
        if config["id"] in canonical and config["id"] not in seen:
            selected.append(config)
            seen.add(config["id"])
    if not selected:
        raise ValueError("no smoke modes selected")
    return selected


def flatten_text(value: Any) -> str:
    parts: list[str] = []

    def visit(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            text = " ".join(node.split())
            if text:
                parts.append(text)
            return
        if isinstance(node, (int, float, bool)):
            parts.append(str(node))
            return
        if isinstance(node, dict):
            for key in sorted(node):
                visit(node[key])
            return
        if isinstance(node, list):
            for item in node:
                visit(item)

    visit(value)
    return "\n".join(parts)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_toml_dataset(path: Path, memories: list[dict[str, str]], queries: list[dict[str, Any]]) -> None:
    lines = [
        "# Generated temporary smoke dataset.",
        "# Contains third-party records and must not be committed.",
        "",
    ]
    for memory in memories:
        lines.extend(
            [
                "[[memories]]",
                f"key = {toml_string(memory['key'])}",
                'kind = "fact"',
                'scope = "global"',
                f"content = {toml_string(memory['content'])}",
                "",
            ]
        )
    for query in queries:
        relevant = ", ".join(toml_string(item) for item in query["relevant"])
        lines.extend(
            [
                "[[queries]]",
                f"query = {toml_string(query['query'])}",
                f"relevant = [{relevant}]",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def select_longmem_rows(rows: list[dict[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    valid = [
        row
        for row in rows
        if row.get("question")
        and row.get("question_id")
        and row.get("haystack_sessions")
        and row.get("haystack_session_ids")
        and row.get("answer_session_ids")
    ]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for row in valid:
        by_type.setdefault(str(row.get("question_type", "unknown")), []).append(row)
    for group in by_type.values():
        group.sort(key=lambda item: str(item.get("question_id", "")))

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for question_type in sorted(by_type):
        row = by_type[question_type][0]
        qid = str(row["question_id"])
        selected.append(row)
        seen.add(qid)
        if len(selected) >= sample_size:
            return selected

    for row in sorted(valid, key=lambda item: str(item.get("question_id", ""))):
        qid = str(row["question_id"])
        if qid in seen:
            continue
        selected.append(row)
        if len(selected) >= sample_size:
            break
    return selected


def build_longmem_dataset(rows: list[dict[str, Any]], sample_size: int) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    memories: list[dict[str, str]] = []
    queries: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()

    for row in select_longmem_rows(rows, sample_size * 2):
        qid = str(row["question_id"])
        answer_session_ids = {str(item) for item in row.get("answer_session_ids", [])}
        session_ids = [str(item) for item in row.get("haystack_session_ids", [])]
        sessions = row.get("haystack_sessions", [])
        if len(session_ids) != len(sessions):
            skipped["session_id_mismatch"] += 1
            continue

        relevant_keys: list[str] = []
        local_memories: list[dict[str, str]] = []
        for index, (session_id, session) in enumerate(zip(session_ids, sessions)):
            key = f"lm_{stable_hash(qid)}_{index:03d}"
            content = flatten_text(session)
            if not content:
                continue
            local_memories.append({"key": key, "content": content})
            if session_id in answer_session_ids:
                relevant_keys.append(key)

        if not relevant_keys:
            skipped["no_relevant_session"] += 1
            continue

        memories.extend(local_memories)
        queries.append({"query": str(row["question"]), "relevant": relevant_keys})
        examples.append(
            {
                "sample_id": stable_hash(f"{LONGMEM_REPO}:{qid}"),
                "category": str(row.get("question_type", "unknown")),
                "source_session_count": len(local_memories),
                "relevant_count": len(relevant_keys),
            }
        )
        if len(queries) >= sample_size:
            break

    return memories, queries, examples, skipped


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_dialog_chunk(row_token: str, label: str, payload: Any) -> dict[str, str]:
    return {
        "key": f"dmr_{stable_hash(row_token)}_{stable_hash(label, 8)}",
        "content": flatten_text(payload),
    }


def build_dmr_dataset(rows: list[dict[str, Any]], sample_size: int) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    memories: list[dict[str, str]] = []
    queries: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()

    for row_index, row in enumerate(rows):
        instruct = row.get("self_instruct") or {}
        question = instruct.get("B")
        answer = instruct.get("A")
        if not question or not answer:
            skipped["missing_question_or_answer"] += 1
            continue
        metadata = row.get("metadata") or {}
        row_id = str(metadata.get("session_id") or metadata.get("initial_data_id") or row_index)
        row_token = f"{row_index}:{row_id}:{stable_hash(str(question) + str(answer))}"

        chunks: list[dict[str, str]] = []
        for prev_index, previous in enumerate(row.get("previous_dialogs") or []):
            chunk = build_dialog_chunk(row_token, f"previous_{prev_index}", previous)
            if chunk["content"]:
                chunks.append(chunk)
        current_payload = {
            "personas": row.get("personas"),
            "dialog": row.get("dialog"),
            "summary_speaker_1": row.get("summary_speaker_1"),
            "summary_speaker_2": row.get("summary_speaker_2"),
        }
        current_chunk = build_dialog_chunk(row_token, "current", current_payload)
        if current_chunk["content"]:
            chunks.append(current_chunk)

        answer_text = " ".join(str(answer).casefold().split())
        relevant_keys = [
            chunk["key"]
            for chunk in chunks
            if answer_text and answer_text in " ".join(chunk["content"].casefold().split())
        ]
        if not relevant_keys:
            skipped["answer_not_found_in_memory_chunks"] += 1
            continue

        memories.extend(chunks)
        queries.append({"query": str(question), "relevant": relevant_keys})
        examples.append(
            {
                "sample_id": stable_hash(f"{DMR_REPO}:{row_token}"),
                "category": "dmr-candidate",
                "source_session_count": len(chunks),
                "relevant_count": len(relevant_keys),
            }
        )
        if len(queries) >= sample_size:
            break

    return memories, queries, examples, skipped


def run_kr_eval(
    dataset_path: Path,
    output_path: Path,
    tag: str,
    k: int,
    *,
    vectors: bool = False,
    rerank: bool = False,
    rerank_pool: int = 50,
) -> dict[str, Any]:
    cmd = [
        "cargo",
        "run",
        "-p",
        "synapse-eval",
        "--bin",
        "kr-eval",
        "--",
        "--dataset",
        str(dataset_path),
        "--k",
        str(k),
        "--tag",
        tag,
        "--json",
        str(output_path),
    ]
    if vectors:
        cmd.append("--vectors")
    if rerank:
        cmd.extend(["--rerank", "--rerank-pool", str(rerank_pool)])
    result = subprocess.run(cmd, cwd=repo_root(), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"kr-eval failed for {tag}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


def run_smoke_configs(
    *,
    dataset_path: Path,
    output_dir: Path,
    tag_base: str,
    examples: list[dict[str, Any]],
    k: int,
    configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for config in configs:
        tag = tag_base if not config["tag_suffix"] else f"{tag_base}{config['tag_suffix']}"
        raw_output = output_dir / f"{tag_base}-{config['id']}-raw-report.json"
        raw = run_kr_eval(
            dataset_path,
            raw_output,
            tag,
            k,
            vectors=config["vectors"],
            rerank=config["rerank"],
            rerank_pool=config["rerank_pool"],
        )
        run = sanitize_eval_report(raw, examples)
        run.update(
            {
                "mode": config["id"],
                "label": config["label"],
                "tag": raw.get("tag"),
            }
        )
        runs.append(run)
    return runs


def sanitize_eval_report(raw: dict[str, Any], examples: list[dict[str, Any]]) -> dict[str, Any]:
    per_query = []
    for index, query_result in enumerate(raw.get("per_query", [])):
        example = examples[index]
        relevant = set(query_result.get("relevant", []))
        returned = query_result.get("returned", [])
        per_query.append(
            {
                "sample_id": example["sample_id"],
                "category": example["category"],
                "source_session_count": example["source_session_count"],
                "relevant_count": example["relevant_count"],
                "returned_relevant_count": sum(1 for key in returned if key in relevant),
                "recall_at_5": query_result.get("recall_at_5"),
                "recall_at_10": query_result.get("recall_at_10"),
                "rr": query_result.get("rr"),
                "ndcg_at_10": query_result.get("ndcg_at_10"),
                "latency_ms": query_result.get("latency_ms"),
            }
        )
    return {
        "tag": raw.get("tag"),
        "k": raw.get("k"),
        "vectors_enabled": raw.get("vectors_enabled"),
        "rerank_enabled": raw.get("rerank_enabled"),
        "rerank_pool": raw.get("rerank_pool"),
        "n_memories": raw.get("n_memories"),
        "n_queries": raw.get("n_queries"),
        "recall_at_5": raw.get("recall_at_5"),
        "recall_at_10": raw.get("recall_at_10"),
        "mrr_at_10": raw.get("mrr_at_10"),
        "ndcg_at_10": raw.get("ndcg_at_10"),
        "p50_latency_ms": raw.get("p50_latency_ms"),
        "p95_latency_ms": raw.get("p95_latency_ms"),
        "total_ms": raw.get("total_ms"),
        "per_query": per_query,
    }


def source_file_report(repo_id: str, filename: str, path: Path, info: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo_id": repo_id,
        "revision": info.get("revision"),
        "license": info.get("license"),
        "filename": filename,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def dataset_smoke_report(
    *,
    name: str,
    source: dict[str, Any],
    sample_size_requested: int,
    memories: list[dict[str, str]],
    queries: list[dict[str, Any]],
    examples: list[dict[str, Any]],
    skipped: Counter[str],
    kr_eval_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    categories = Counter(example["category"] for example in examples)
    if not kr_eval_runs:
        raise RuntimeError(f"{name} smoke report has no kr-eval runs.")
    return {
        "name": name,
        "source": source,
        "sample_size_requested": sample_size_requested,
        "sample_size_used": len(queries),
        "selection_policy": "deterministic category-first sample, then stable source order",
        "skipped": dict(sorted(skipped.items())),
        "category_counts": dict(sorted(categories.items())),
        "temporary_dataset_committed": False,
        "raw_records_committed": False,
        "memory_chunks": len(memories),
        "kr_eval": kr_eval_runs[0],
        "kr_eval_runs": kr_eval_runs,
    }


def main() -> int:
    args = parse_args()
    root = repo_root()
    os.environ["HF_ENDPOINT"] = args.endpoint
    args.output = args.output if args.output.is_absolute() else root / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    selected_configs = parse_smoke_modes(args.modes)

    api = HfApi(endpoint=args.endpoint)
    longmem_info = dataset_info(api, LONGMEM_REPO)
    dmr_info = dataset_info(api, DMR_REPO)

    longmem_cache = args.cache_root / "longmemeval-cleaned"
    dmr_cache = args.cache_root / "dmr-msc-self-instruct"
    longmem_path = download_dataset(LONGMEM_REPO, LONGMEM_FILE, args.endpoint, longmem_cache)
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)

    longmem_rows = json.loads(longmem_path.read_text(encoding="utf-8"))
    dmr_rows = read_jsonl(dmr_path)
    longmem_memories, longmem_queries, longmem_examples, longmem_skipped = build_longmem_dataset(
        longmem_rows, args.longmem_sample_size
    )
    dmr_memories, dmr_queries, dmr_examples, dmr_skipped = build_dmr_dataset(
        dmr_rows, args.dmr_sample_size
    )

    if not longmem_queries:
        raise RuntimeError("LongMemEval smoke sample is empty.")
    if not dmr_queries:
        raise RuntimeError("DMR smoke sample is empty.")

    with tempfile.TemporaryDirectory(prefix="king-synapse-longmem-dmr-") as temp:
        temp_dir = Path(temp)
        longmem_toml = temp_dir / "longmemeval-smoke.toml"
        dmr_toml = temp_dir / "dmr-smoke.toml"

        write_toml_dataset(longmem_toml, longmem_memories, longmem_queries)
        write_toml_dataset(dmr_toml, dmr_memories, dmr_queries)
        longmem_runs = run_smoke_configs(
            dataset_path=longmem_toml,
            output_dir=temp_dir,
            tag_base="longmemeval-smoke",
            examples=longmem_examples,
            k=args.k,
            configs=selected_configs,
        )
        dmr_runs = run_smoke_configs(
            dataset_path=dmr_toml,
            output_dir=temp_dir,
            tag_base="dmr-candidate-smoke",
            examples=dmr_examples,
            k=args.k,
            configs=selected_configs,
        )

    report = {
        "schema_version": "king-synapse.longmem-dmr-smoke.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/longmem_dmr_smoke.py",
        "endpoint": args.endpoint,
        "cache_policy": {
            "cache_root_recorded": False,
            "raw_cache_retained": not args.cleanup_cache,
            "raw_records_committed": False,
        },
        "selected_modes": [config["id"] for config in selected_configs],
        "scoring_mode": "existing kr-eval RecallEngine compared across selected retrieval branches",
        "datasets": [
            dataset_smoke_report(
                name="LongMemEval cleaned smoke",
                source=source_file_report(LONGMEM_REPO, LONGMEM_FILE, longmem_path, longmem_info),
                sample_size_requested=args.longmem_sample_size,
                memories=longmem_memories,
                queries=longmem_queries,
                examples=longmem_examples,
                skipped=longmem_skipped,
                kr_eval_runs=longmem_runs,
            ),
            dataset_smoke_report(
                name="DMR candidate MSC-Self-Instruct smoke",
                source=source_file_report(DMR_REPO, DMR_FILE, dmr_path, dmr_info),
                sample_size_requested=args.dmr_sample_size,
                memories=dmr_memories,
                queries=dmr_queries,
                examples=dmr_examples,
                skipped=dmr_skipped,
                kr_eval_runs=dmr_runs,
            ),
        ],
        "limits": [
            "Small smoke sample only; not a full benchmark run.",
            "DMR source is treated as a candidate until the original DMR harness is pinned.",
            "Report excludes raw questions, answers, dialogs, and session text.",
            "Comparison covers baseline RRF, vector branch, and vector-plus-reranker branch only.",
            "No LLM judge or hosted external systems are used.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.cleanup_cache:
        for path in [longmem_cache, dmr_cache]:
            if path.exists():
                shutil.rmtree(path)

    print(json.dumps({
        "output": str(args.output),
        "selected_modes": [config["id"] for config in selected_configs],
        "longmem_queries": len(longmem_queries),
        "dmr_queries": len(dmr_queries),
        "kr_eval_runs_per_dataset": len(selected_configs),
        "cleanup_cache": args.cleanup_cache,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
