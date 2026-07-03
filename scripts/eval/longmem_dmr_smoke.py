#!/usr/bin/env python
"""LongMemEval / DMR smoke runner for system validation.

This script downloads external datasets into a user cache, builds temporary
TOML datasets for the existing `kr-eval` binary, and writes a sanitized
aggregate report. It must not commit raw third-party records.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download


LONGMEM_REPO = "xiaowu0162/longmemeval-cleaned"
LONGMEM_FILE = "longmemeval_s_cleaned.json"
DMR_REPO = "MemGPT/MSC-Self-Instruct"
DMR_FILE = "msc_self_instruct.jsonl"
DMR_ANSWER_MATCH_POLICIES = {
    "strict": "casefold + whitespace-normalized full answer substring",
    "punctuation": "casefold + punctuation-normalized full answer substring",
}
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


def default_fastembed_cache_dir() -> Path:
    raw = os.environ.get("FASTEMBED_CACHE_DIR")
    if raw:
        return Path(raw)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "king-synapse" / "fastembed-cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "king-synapse" / "fastembed-cache"


def eval_cargo_profile() -> str:
    raw = os.environ.get("KING_SYNAPSE_EVAL_CARGO_PROFILE", "debug").strip().lower()
    aliases = {
        "dev": "debug",
        "debug": "debug",
        "release": "release",
    }
    if raw not in aliases:
        raise ValueError("KING_SYNAPSE_EVAL_CARGO_PROFILE must be debug or release")
    return aliases[raw]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LongMemEval / DMR smoke validation.")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    parser.add_argument("--output", type=Path, default=repo_root() / "crates/eval/reports/longmem-dmr-smoke-latest.json")
    parser.add_argument(
        "--modes",
        default="all",
        help="Comma-separated smoke modes: all, baseline-rrf, vectors, vectors-rerank.",
    )
    parser.add_argument(
        "--datasets",
        default="all",
        help="Comma-separated datasets: all, longmem, dmr.",
    )
    parser.add_argument("--longmem-sample-size", type=int, default=10)
    parser.add_argument("--dmr-sample-size", type=int, default=20)
    parser.add_argument(
        "--dmr-answer-match",
        choices=tuple(DMR_ANSWER_MATCH_POLICIES),
        default="strict",
        help="DMR answer-to-memory mapping policy. Default keeps the original strict baseline.",
    )
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--embed-batch-size", type=int, default=None)
    parser.add_argument("--embed-max-length", type=int, default=None)
    parser.add_argument("--rerank-batch-size", type=int, default=None)
    parser.add_argument("--rerank-max-length", type=int, default=None)
    parser.add_argument(
        "--accelerator",
        choices=("env", "cpu", "cuda", "directml"),
        default="env",
        help="Execution provider for vector/rerank model inference. 'env' keeps KING_SYNAPSE_ACCELERATOR unchanged.",
    )
    parser.add_argument("--cuda-device-id", default=None)
    parser.add_argument(
        "--cuda-runtime-root",
        type=Path,
        default=None,
        help="Optional root containing NVIDIA CUDA runtime wheel DLL directories.",
    )
    parser.add_argument("--directml-device-id", default=None)
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


def parse_dataset_selection(raw: str) -> set[str]:
    aliases = {
        "all": "all",
        "longmem": "longmem",
        "longmemeval": "longmem",
        "lm": "longmem",
        "dmr": "dmr",
    }
    requested = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not requested:
        requested = ["all"]
    selected: set[str] = set()
    for part in requested:
        if part not in aliases:
            raise ValueError(f"unknown dataset: {part}")
        canonical = aliases[part]
        if canonical == "all":
            return {"longmem", "dmr"}
        selected.add(canonical)
    if not selected:
        raise ValueError("no datasets selected")
    return selected


def configure_accelerator_environment(args: argparse.Namespace) -> dict[str, Any]:
    if args.accelerator != "env":
        os.environ["KING_SYNAPSE_ACCELERATOR"] = args.accelerator
    if args.cuda_device_id is not None:
        os.environ["KING_SYNAPSE_CUDA_DEVICE_ID"] = str(args.cuda_device_id)
    if args.directml_device_id is not None:
        os.environ["KING_SYNAPSE_DIRECTML_DEVICE_ID"] = str(args.directml_device_id)

    cuda_runtime = configure_cuda_runtime_path(args)
    embedding = configure_embedding_environment(args)
    rerank_batch = configure_rerank_batch_environment(args)
    rerank_max_length = configure_rerank_max_length_environment(args)

    return {
        "requested": args.accelerator,
        "king_synapse_accelerator": os.environ.get("KING_SYNAPSE_ACCELERATOR"),
        "cuda_device_id": os.environ.get("KING_SYNAPSE_CUDA_DEVICE_ID"),
        "cuda_runtime": cuda_runtime,
        "embedding": embedding,
        "rerank_batch": rerank_batch,
        "rerank_max_length": rerank_max_length,
        "directml_device_id": os.environ.get("KING_SYNAPSE_DIRECTML_DEVICE_ID"),
    }


def default_cuda_runtime_root() -> Path | None:
    raw = os.environ.get("KING_SYNAPSE_CUDA_RUNTIME_ROOT")
    if raw:
        return Path(raw)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "king-synapse" / "cuda-runtime-py313"
    return None


def configure_cuda_runtime_path(args: argparse.Namespace) -> dict[str, Any]:
    accelerator = os.environ.get("KING_SYNAPSE_ACCELERATOR", "").strip().lower()
    if accelerator != "cuda":
        return {"path_added": False, "reason": "accelerator is not cuda"}

    runtime_root = args.cuda_runtime_root or default_cuda_runtime_root()
    if runtime_root is None:
        return {"path_added": False, "reason": "no cuda runtime root configured"}

    runtime_root = runtime_root.expanduser()
    exists = runtime_root.exists()
    dll_dirs: list[str] = []
    if exists:
        dll_dirs = sorted({str(path.parent) for path in runtime_root.rglob("*.dll")})
    if dll_dirs:
        os.environ["PATH"] = os.pathsep.join(dll_dirs + [os.environ.get("PATH", "")])

    return {
        "path_added": bool(dll_dirs),
        "root_recorded": False,
        "root_exists": exists,
        "dll_dir_count": len(dll_dirs),
    }


def configure_rerank_batch_environment(args: argparse.Namespace) -> dict[str, Any]:
    if args.rerank_batch_size is not None:
        os.environ["KING_SYNAPSE_RERANK_BATCH_SIZE"] = str(args.rerank_batch_size)
        return {
            "value": str(args.rerank_batch_size),
            "source": "argument",
        }

    existing = os.environ.get("KING_SYNAPSE_RERANK_BATCH_SIZE")
    if existing:
        return {
            "value": existing,
            "source": "environment",
        }

    accelerator = os.environ.get("KING_SYNAPSE_ACCELERATOR", "").strip().lower()
    if accelerator == "cuda":
        os.environ["KING_SYNAPSE_RERANK_BATCH_SIZE"] = "8"
        return {
            "value": "8",
            "source": "cuda_default",
        }

    return {
        "value": None,
        "source": "unset",
    }


def configure_embedding_environment(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "batch_size": configure_model_env_value(
            arg_value=args.embed_batch_size,
            env_name="KING_SYNAPSE_EMBED_BATCH_SIZE",
            cuda_default="32",
        ),
        "max_length": configure_model_env_value(
            arg_value=args.embed_max_length,
            env_name="KING_SYNAPSE_EMBED_MAX_LENGTH",
            cuda_default="256",
        ),
    }


def configure_model_env_value(
    *,
    arg_value: int | None,
    env_name: str,
    cuda_default: str,
) -> dict[str, Any]:
    if arg_value is not None:
        os.environ[env_name] = str(arg_value)
        return {
            "value": str(arg_value),
            "source": "argument",
        }

    existing = os.environ.get(env_name)
    if existing:
        return {
            "value": existing,
            "source": "environment",
        }

    accelerator = os.environ.get("KING_SYNAPSE_ACCELERATOR", "").strip().lower()
    if accelerator == "cuda":
        os.environ[env_name] = cuda_default
        return {
            "value": cuda_default,
            "source": "cuda_default",
        }

    return {
        "value": None,
        "source": "unset",
    }


def configure_rerank_max_length_environment(args: argparse.Namespace) -> dict[str, Any]:
    if args.rerank_max_length is not None:
        os.environ["KING_SYNAPSE_RERANK_MAX_LENGTH"] = str(args.rerank_max_length)
        return {
            "value": str(args.rerank_max_length),
            "source": "argument",
        }

    existing = os.environ.get("KING_SYNAPSE_RERANK_MAX_LENGTH")
    if existing:
        return {
            "value": existing,
            "source": "environment",
        }

    accelerator = os.environ.get("KING_SYNAPSE_ACCELERATOR", "").strip().lower()
    if accelerator == "cuda":
        os.environ["KING_SYNAPSE_RERANK_MAX_LENGTH"] = "256"
        return {
            "value": "256",
            "source": "cuda_default",
        }

    return {
        "value": None,
        "source": "unset",
    }


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


def normalize_whitespace(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def normalize_punctuation(value: Any) -> str:
    return " ".join(re.findall(r"[\w]+", str(value).casefold()))


def dmr_answer_matches(answer: Any, content: str, policy: str) -> bool:
    if policy == "strict":
        answer_text = normalize_whitespace(answer)
        return bool(answer_text and answer_text in normalize_whitespace(content))
    if policy == "punctuation":
        answer_text = normalize_punctuation(answer)
        return bool(answer_text and answer_text in normalize_punctuation(content))
    raise ValueError(f"unknown DMR answer match policy: {policy}")


def dmr_tag_base(answer_match_policy: str) -> str:
    if answer_match_policy == "strict":
        return "dmr-candidate-smoke"
    return f"dmr-candidate-{answer_match_policy}-smoke"


def build_dmr_dataset(
    rows: list[dict[str, Any]],
    sample_size: int,
    answer_match_policy: str,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
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

        relevant_keys = [
            chunk["key"]
            for chunk in chunks
            if dmr_answer_matches(answer, chunk["content"], answer_match_policy)
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


def process_tree_pids(root_pid: int) -> list[int]:
    parent_by_pid = windows_parent_map() if os.name == "nt" else procfs_parent_map()
    children_by_parent: dict[int, list[int]] = {}
    for pid, parent in parent_by_pid.items():
        children_by_parent.setdefault(parent, []).append(pid)

    tree: list[int] = []
    stack = [root_pid]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        tree.append(pid)
        stack.extend(children_by_parent.get(pid, []))
    return tree


def windows_parent_map() -> dict[int, int]:
    import ctypes.wintypes as wintypes

    class ProcessEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    kernel32.Process32First.restype = wintypes.BOOL
    kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    kernel32.Process32Next.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return {}
    try:
        entry = ProcessEntry32()
        entry.dwSize = ctypes.sizeof(ProcessEntry32)
        parents: dict[int, int] = {}
        if not kernel32.Process32First(snapshot, ctypes.byref(entry)):
            return parents
        while True:
            parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                break
        return parents
    finally:
        kernel32.CloseHandle(snapshot)


def procfs_parent_map() -> dict[int, int]:
    proc = Path("/proc")
    if not proc.exists():
        return {}
    parents: dict[int, int] = {}
    for child in proc.iterdir():
        if not child.name.isdigit():
            continue
        try:
            stat = (child / "stat").read_text(encoding="utf-8", errors="replace")
            after_comm = stat.rsplit(")", 1)[1].strip().split()
            parents[int(child.name)] = int(after_comm[1])
        except (OSError, IndexError, ValueError):
            continue
    return parents


def process_snapshot(pid: int) -> dict[str, float | int | None] | None:
    return windows_process_snapshot(pid) if os.name == "nt" else procfs_process_snapshot(pid)


def windows_process_snapshot(pid: int) -> dict[str, float | int | None] | None:
    import ctypes.wintypes as wintypes

    class FileTime(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    class ProcessMemoryCountersEx(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    def filetime_seconds(value: FileTime) -> float:
        ticks = (int(value.dwHighDateTime) << 32) + int(value.dwLowDateTime)
        return ticks / 10_000_000.0

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCountersEx),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        return None
    try:
        mem = ProcessMemoryCountersEx()
        mem.cb = ctypes.sizeof(ProcessMemoryCountersEx)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(mem), mem.cb):
            return None
        creation = FileTime()
        exit_time = FileTime()
        kernel = FileTime()
        user = FileTime()
        cpu_seconds = None
        if kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            cpu_seconds = filetime_seconds(kernel) + filetime_seconds(user)
        return {
            "working_set_bytes": int(mem.WorkingSetSize),
            "peak_working_set_bytes": int(mem.PeakWorkingSetSize),
            "private_bytes": int(mem.PrivateUsage),
            "cpu_seconds": cpu_seconds,
        }
    finally:
        kernel32.CloseHandle(handle)


def procfs_process_snapshot(pid: int) -> dict[str, float | int | None] | None:
    stat_path = Path("/proc") / str(pid) / "stat"
    try:
        stat = stat_path.read_text(encoding="utf-8", errors="replace")
        after_comm = stat.rsplit(")", 1)[1].strip().split()
        ticks_per_second = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        page_size = os.sysconf(os.sysconf_names["SC_PAGE_SIZE"])
        user_ticks = int(after_comm[11])
        kernel_ticks = int(after_comm[12])
        rss_pages = int(after_comm[21])
        rss_bytes = max(0, rss_pages) * page_size
        return {
            "working_set_bytes": rss_bytes,
            "peak_working_set_bytes": None,
            "private_bytes": None,
            "cpu_seconds": (user_ticks + kernel_ticks) / ticks_per_second,
        }
    except (OSError, KeyError, IndexError, ValueError):
        return None


def sample_process_tree(root_pid: int) -> dict[str, Any] | None:
    pids = process_tree_pids(root_pid)
    snapshots = [(pid, process_snapshot(pid)) for pid in pids]
    snapshots = [(pid, snap) for pid, snap in snapshots if snap is not None]
    if not snapshots:
        return None
    working_set = sum(int(snap.get("working_set_bytes") or 0) for _, snap in snapshots)
    private_values = [snap.get("private_bytes") for _, snap in snapshots]
    private_bytes = (
        sum(int(value or 0) for value in private_values)
        if all(value is not None for value in private_values)
        else None
    )
    return {
        "pids": [pid for pid, _ in snapshots],
        "process_count": len(snapshots),
        "working_set_bytes": working_set,
        "private_bytes": private_bytes,
        "cpu_seconds_by_pid": {
            str(pid): snap.get("cpu_seconds")
            for pid, snap in snapshots
            if snap.get("cpu_seconds") is not None
        },
    }


def gpu_process_memory_snapshot(pids: list[int]) -> dict[str, Any]:
    if os.name != "nt":
        return {
            "available": False,
            "unavailable_reason": "GPU process memory counters are currently implemented for Windows only",
        }
    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    if powershell is None:
        fallback = (
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        if fallback.exists():
            powershell = str(fallback)
    if powershell is None:
        return {
            "available": False,
            "unavailable_reason": "powershell.exe was not found for GPU process memory counter sampling",
        }
    unique_pids = sorted({int(pid) for pid in pids if int(pid) > 0})
    if not unique_pids:
        return {"available": False, "unavailable_reason": "no process ids to sample"}

    unique_pid_set = set(unique_pids)
    counters = [
        r"\GPU Process Memory(*)\Dedicated Usage",
        r"\GPU Process Memory(*)\Shared Usage",
    ]
    ps_paths = "@(" + ",".join(powershell_single_quote(counter) for counter in counters) + ")"
    script = (
        "$ErrorActionPreference = 'SilentlyContinue'; "
        f"$paths = {ps_paths}; "
        "$samples = (Get-Counter -Counter $paths -ErrorAction SilentlyContinue).CounterSamples | "
        "Select-Object Path,CookedValue; "
        "$samples | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-Command", script],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return {
            "available": False,
            "unavailable_reason": "GPU Process Memory counter query failed",
            "stderr": result.stderr.strip()[:500],
        }

    output = result.stdout.strip()
    if not output:
        return {
            "available": False,
            "unavailable_reason": "GPU Process Memory counters returned no samples",
        }
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return {
            "available": False,
            "unavailable_reason": "GPU Process Memory counters returned non-JSON output",
            "stdout": output[:500],
        }
    samples = parsed if isinstance(parsed, list) else [parsed]
    dedicated_bytes = 0
    shared_bytes = 0
    matched_pids: set[int] = set()
    matched_sample_count = 0
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        path = str(sample.get("Path") or "").lower()
        value = int(float(sample.get("CookedValue") or 0))
        pid_match = re.search(r"pid_(\d+)", path)
        if not pid_match:
            continue
        pid = int(pid_match.group(1))
        if pid not in unique_pid_set:
            continue
        matched_pids.add(pid)
        matched_sample_count += 1
        if "dedicated usage" in path:
            dedicated_bytes += value
        elif "shared usage" in path:
            shared_bytes += value

    if not matched_pids:
        return {
            "available": False,
            "unavailable_reason": "GPU Process Memory counters had no samples for monitored process ids",
            "sampled_pids": unique_pids,
            "raw_sample_count": len(samples),
        }

    return {
        "available": True,
        "provider": "windows_performance_counter_gpu_process_memory",
        "sampled_pids": unique_pids,
        "matched_pids": sorted(matched_pids),
        "raw_sample_count": len(samples),
        "sample_count": matched_sample_count,
        "dedicated_bytes": dedicated_bytes,
        "shared_bytes": shared_bytes,
        "total_bytes": dedicated_bytes + shared_bytes,
    }


def powershell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def profiled_subprocess_run(cmd: list[str], cwd: Path) -> tuple[subprocess.CompletedProcess, dict[str, Any]]:
    sample_interval_s = 0.1
    gpu_sample_interval_s = 5.0
    started = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    sample_count = 0
    peak_working_set_bytes = 0
    peak_private_bytes: int | None = None
    max_process_count = 0
    first_cpu_by_pid: dict[str, float] = {}
    last_cpu_by_pid: dict[str, float] = {}
    available = True
    unavailable_reason = None
    next_gpu_sample_at = started
    gpu_sample_count = 0
    gpu_available = os.name == "nt"
    gpu_unavailable_reason = None if gpu_available else "GPU memory sampling is implemented for Windows only"
    peak_gpu_dedicated_bytes: int | None = None
    peak_gpu_shared_bytes: int | None = None
    peak_gpu_total_bytes: int | None = None
    gpu_provider = None

    stdout = ""
    stderr = ""
    while True:
        now = time.perf_counter()
        sample = sample_process_tree(proc.pid)
        if sample is None:
            if sample_count == 0:
                available = False
                unavailable_reason = "process metrics unavailable on this platform or process ended before first sample"
        else:
            available = True
            unavailable_reason = None
            sample_count += 1
            max_process_count = max(max_process_count, int(sample["process_count"]))
            peak_working_set_bytes = max(peak_working_set_bytes, int(sample["working_set_bytes"]))
            private_bytes = sample.get("private_bytes")
            if private_bytes is not None:
                peak_private_bytes = max(peak_private_bytes or 0, int(private_bytes))
            for pid, cpu_seconds in sample["cpu_seconds_by_pid"].items():
                value = float(cpu_seconds)
                first_cpu_by_pid.setdefault(pid, value)
                last_cpu_by_pid[pid] = value
            if now >= next_gpu_sample_at:
                gpu_sample = gpu_process_memory_snapshot(sample["pids"])
                gpu_sample_count += 1
                if gpu_sample.get("available"):
                    gpu_provider = gpu_sample.get("provider")
                    gpu_available = True
                    gpu_unavailable_reason = None
                    dedicated_bytes = int(gpu_sample.get("dedicated_bytes") or 0)
                    shared_bytes = int(gpu_sample.get("shared_bytes") or 0)
                    total_bytes = int(gpu_sample.get("total_bytes") or 0)
                    peak_gpu_dedicated_bytes = max(peak_gpu_dedicated_bytes or 0, dedicated_bytes)
                    peak_gpu_shared_bytes = max(peak_gpu_shared_bytes or 0, shared_bytes)
                    peak_gpu_total_bytes = max(peak_gpu_total_bytes or 0, total_bytes)
                else:
                    gpu_unavailable_reason = gpu_sample.get("unavailable_reason")
                next_gpu_sample_at = now + gpu_sample_interval_s
        try:
            stdout, stderr = proc.communicate(timeout=sample_interval_s)
            break
        except subprocess.TimeoutExpired:
            continue

    cpu_seconds = sum(
        max(0.0, last_cpu_by_pid[pid] - first_cpu_by_pid.get(pid, last_cpu_by_pid[pid]))
        for pid in last_cpu_by_pid
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if gpu_available and peak_gpu_total_bytes is None and gpu_unavailable_reason is None:
        gpu_unavailable_reason = "process ended before GPU memory sample"
    process_metrics = {
        "available": available,
        "unavailable_reason": unavailable_reason,
        "platform": os.name,
        "sample_interval_ms": sample_interval_s * 1000.0,
        "sample_count": sample_count,
        "elapsed_wall_ms": elapsed_ms,
        "max_process_count": max_process_count,
        "peak_working_set_bytes": peak_working_set_bytes if available else None,
        "peak_private_bytes": peak_private_bytes if available else None,
        "cpu_seconds": cpu_seconds if available else None,
        "process_tree_includes_cargo_wrapper": True,
        "gpu_memory": {
            "available": gpu_available and peak_gpu_total_bytes is not None,
            "unavailable_reason": gpu_unavailable_reason,
            "provider": gpu_provider,
            "sample_interval_ms": gpu_sample_interval_s * 1000.0,
            "sample_count": gpu_sample_count,
            "peak_dedicated_bytes": peak_gpu_dedicated_bytes,
            "peak_shared_bytes": peak_gpu_shared_bytes,
            "peak_total_bytes": peak_gpu_total_bytes,
        },
    }
    result = subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
    )
    return result, process_metrics


def run_kr_eval(
    dataset_path: Path,
    output_path: Path,
    tag: str,
    k: int,
    *,
    vectors: bool = False,
    rerank: bool = False,
    rerank_pool: int = 50,
    rrf_k: float | None = None,
    fts_weight: float | None = None,
    entity_weight: float | None = None,
    vector_weight: float | None = None,
) -> dict[str, Any]:
    cargo_profile = eval_cargo_profile()
    cmd = [
        "cargo",
        "run",
    ]
    if cargo_profile == "release":
        cmd.append("--release")
    cmd.extend(
        [
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
    )
    if vectors:
        cmd.append("--vectors")
    if rerank:
        cmd.extend(["--rerank", "--rerank-pool", str(rerank_pool)])
    if rrf_k is not None:
        cmd.extend(["--rrf-k", str(rrf_k)])
    if fts_weight is not None:
        cmd.extend(["--fts-weight", str(fts_weight)])
    if entity_weight is not None:
        cmd.extend(["--entity-weight", str(entity_weight)])
    if vector_weight is not None:
        cmd.extend(["--vector-weight", str(vector_weight)])
    result, process_metrics = profiled_subprocess_run(cmd, repo_root())
    if result.returncode != 0:
        raise RuntimeError(
            f"kr-eval failed for {tag}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    raw = json.loads(output_path.read_text(encoding="utf-8"))
    raw["cargo_profile"] = cargo_profile
    process_metrics["cargo_profile"] = cargo_profile
    raw["process_metrics"] = process_metrics
    return raw


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
        print(f"running {tag}...", flush=True)
        raw = run_kr_eval(
            dataset_path,
            raw_output,
            tag,
            k,
            vectors=config["vectors"],
            rerank=config["rerank"],
            rerank_pool=config["rerank_pool"],
            rrf_k=60.0,
            fts_weight=1.0,
            entity_weight=1.0,
            vector_weight=1.0,
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


def first_relevant_rank(returned: list[str], relevant: set[str]) -> int | None:
    for index, key in enumerate(returned, start=1):
        if key in relevant:
            return index
    return None


def rank_bucket(rank: int | None) -> str:
    if rank is None:
        return "absent"
    if rank == 1:
        return "top_1"
    if rank <= 10:
        return "top_10"
    if rank <= 50:
        return "top_50"
    return "after_top_50"


def failure_type_for_rank(rank: int | None) -> str:
    if rank is None:
        return "retrieval_miss"
    if rank == 1:
        return "hit_top_1"
    if rank <= 10:
        return "top_10_not_top_1"
    return "wrong_rank"


def compact_hit_diagnostic(hit: dict[str, Any] | None) -> dict[str, Any] | None:
    if not hit:
        return None
    branch_ranks = [
        value
        for value in (
            hit.get("fts_rank"),
            hit.get("entity_rank"),
            hit.get("vector_rank"),
        )
        if value is not None
    ]
    return {
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "rrf_score": hit.get("rrf_score"),
        "rerank_score": hit.get("rerank_score"),
        "activation_bonus": hit.get("activation_bonus"),
        "source_count": len(hit.get("sources") or []),
        "sources": sorted(hit.get("sources") or []),
        "best_branch_rank": min(branch_ranks) if branch_ranks else None,
        "fts_rank": hit.get("fts_rank"),
        "entity_rank": hit.get("entity_rank"),
        "vector_rank": hit.get("vector_rank"),
        "entity_hits": hit.get("entity_hits"),
    }


def safe_numeric_delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def ranking_signal_summary(query_result: dict[str, Any], relevant: set[str]) -> dict[str, Any]:
    diagnostics = query_result.get("returned_hit_diagnostics") or []
    top1 = diagnostics[0] if len(diagnostics) >= 1 else None
    top2 = diagnostics[1] if len(diagnostics) >= 2 else None
    relevant_hits = [hit for hit in diagnostics if hit.get("key") in relevant]
    first_relevant = relevant_hits[0] if relevant_hits else None
    return {
        "available": bool(diagnostics),
        "top1": compact_hit_diagnostic(top1),
        "top2": compact_hit_diagnostic(top2),
        "top1_top2_score_margin": safe_numeric_delta(
            (top1 or {}).get("score"), (top2 or {}).get("score")
        ),
        "top1_top2_rerank_margin": safe_numeric_delta(
            (top1 or {}).get("rerank_score"), (top2 or {}).get("rerank_score")
        ),
        "top1_top2_rrf_margin": safe_numeric_delta(
            (top1 or {}).get("rrf_score"), (top2 or {}).get("rrf_score")
        ),
        "first_relevant": compact_hit_diagnostic(first_relevant),
        "first_relevant_score_gap_vs_top1": safe_numeric_delta(
            (top1 or {}).get("score"), (first_relevant or {}).get("score")
        ),
    }


def sanitize_eval_report(raw: dict[str, Any], examples: list[dict[str, Any]]) -> dict[str, Any]:
    per_query = []
    for index, query_result in enumerate(raw.get("per_query", [])):
        example = examples[index]
        relevant = set(query_result.get("relevant", []))
        returned = query_result.get("returned", [])
        first_rank = first_relevant_rank(returned, relevant)
        per_query.append(
            {
                "sample_id": example["sample_id"],
                "category": example["category"],
                "source_session_count": example["source_session_count"],
                "relevant_count": example["relevant_count"],
                "returned_relevant_count": sum(1 for key in returned if key in relevant),
                "returned_count": len(returned),
                "first_relevant_rank": first_rank,
                "rank_bucket": rank_bucket(first_rank),
                "failure_type": failure_type_for_rank(first_rank),
                "recall_at_5": query_result.get("recall_at_5"),
                "recall_at_10": query_result.get("recall_at_10"),
                "rr": query_result.get("rr"),
                "ndcg_at_10": query_result.get("ndcg_at_10"),
                "latency_ms": query_result.get("latency_ms"),
                "profile": query_result.get("profile"),
                "ranking_signal_summary": ranking_signal_summary(query_result, relevant),
            }
        )
    return {
        "tag": raw.get("tag"),
        "k": raw.get("k"),
        "vectors_enabled": raw.get("vectors_enabled"),
        "rerank_enabled": raw.get("rerank_enabled"),
        "rerank_pool": raw.get("rerank_pool"),
        "rrf_k": raw.get("rrf_k"),
        "rrf_weights": raw.get("rrf_weights"),
        "n_memories": raw.get("n_memories"),
        "n_queries": raw.get("n_queries"),
        "recall_at_5": raw.get("recall_at_5"),
        "recall_at_10": raw.get("recall_at_10"),
        "mrr_at_10": raw.get("mrr_at_10"),
        "ndcg_at_10": raw.get("ndcg_at_10"),
        "p50_latency_ms": raw.get("p50_latency_ms"),
        "p95_latency_ms": raw.get("p95_latency_ms"),
        "total_ms": raw.get("total_ms"),
        "timing": raw.get("timing"),
        "process_metrics": raw.get("process_metrics"),
        "cargo_profile": raw.get("cargo_profile"),
        "per_query": per_query,
        "rank_bucket_counts": dict(sorted(Counter(item["rank_bucket"] for item in per_query).items())),
        "failure_type_counts": dict(sorted(Counter(item["failure_type"] for item in per_query).items())),
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
    dataset_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    categories = Counter(example["category"] for example in examples)
    if not kr_eval_runs:
        raise RuntimeError(f"{name} smoke report has no kr-eval runs.")
    report = {
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
    if dataset_metadata:
        report.update(dataset_metadata)
    return report


def main() -> int:
    args = parse_args()
    root = repo_root()
    os.environ["HF_ENDPOINT"] = args.endpoint
    os.environ["FASTEMBED_CACHE_DIR"] = str(args.fastembed_cache_dir)
    args.output = args.output if args.output.is_absolute() else root / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    args.fastembed_cache_dir.mkdir(parents=True, exist_ok=True)
    selected_configs = parse_smoke_modes(args.modes)
    selected_datasets = parse_dataset_selection(args.datasets)
    accelerator = configure_accelerator_environment(args)

    api = HfApi(endpoint=args.endpoint)
    datasets: list[dict[str, Any]] = []
    cleanup_paths: list[Path] = []

    if "longmem" in selected_datasets:
        longmem_info = dataset_info(api, LONGMEM_REPO)
        longmem_cache = args.cache_root / "longmemeval-cleaned"
        cleanup_paths.append(longmem_cache)
        longmem_path = download_dataset(LONGMEM_REPO, LONGMEM_FILE, args.endpoint, longmem_cache)
        longmem_rows = json.loads(longmem_path.read_text(encoding="utf-8"))
        longmem_memories, longmem_queries, longmem_examples, longmem_skipped = build_longmem_dataset(
            longmem_rows, args.longmem_sample_size
        )
        if not longmem_queries:
            raise RuntimeError("LongMemEval smoke sample is empty.")
        datasets.append(
            {
                "id": "longmem",
                "name": "LongMemEval cleaned smoke",
                "source": source_file_report(LONGMEM_REPO, LONGMEM_FILE, longmem_path, longmem_info),
                "sample_size_requested": args.longmem_sample_size,
                "memories": longmem_memories,
                "queries": longmem_queries,
                "examples": longmem_examples,
                "skipped": longmem_skipped,
                "toml_name": "longmemeval-smoke.toml",
                "tag_base": "longmemeval-smoke",
            }
        )

    if "dmr" in selected_datasets:
        dmr_info = dataset_info(api, DMR_REPO)
        dmr_cache = args.cache_root / "dmr-msc-self-instruct"
        cleanup_paths.append(dmr_cache)
        dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
        dmr_rows = read_jsonl(dmr_path)
        dmr_memories, dmr_queries, dmr_examples, dmr_skipped = build_dmr_dataset(
            dmr_rows, args.dmr_sample_size, args.dmr_answer_match
        )
        if not dmr_queries:
            raise RuntimeError("DMR smoke sample is empty.")
        datasets.append(
            {
                "id": "dmr",
                "name": "DMR candidate MSC-Self-Instruct smoke",
                "source": source_file_report(DMR_REPO, DMR_FILE, dmr_path, dmr_info),
                "sample_size_requested": args.dmr_sample_size,
                "memories": dmr_memories,
                "queries": dmr_queries,
                "examples": dmr_examples,
                "skipped": dmr_skipped,
                "toml_name": "dmr-smoke.toml",
                "tag_base": dmr_tag_base(args.dmr_answer_match),
                "metadata": {
                    "answer_match_policy": args.dmr_answer_match,
                    "answer_match_policy_description": DMR_ANSWER_MATCH_POLICIES[args.dmr_answer_match],
                },
            }
        )

    with tempfile.TemporaryDirectory(prefix="king-synapse-longmem-dmr-") as temp:
        temp_dir = Path(temp)
        for dataset in datasets:
            dataset_path = temp_dir / dataset["toml_name"]
            write_toml_dataset(dataset_path, dataset["memories"], dataset["queries"])
            dataset["kr_eval_runs"] = run_smoke_configs(
                dataset_path=dataset_path,
                output_dir=temp_dir,
                tag_base=dataset["tag_base"],
                examples=dataset["examples"],
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
            "fastembed_cache_dir_recorded": False,
            "fastembed_cache_configured": True,
            "raw_cache_retained": not args.cleanup_cache,
            "raw_records_committed": False,
        },
        "selected_modes": [config["id"] for config in selected_configs],
        "selected_datasets": sorted(selected_datasets),
        "dmr_answer_match_policy": args.dmr_answer_match,
        "accelerator": accelerator,
        "scoring_mode": "existing kr-eval RecallEngine compared across selected retrieval branches",
        "datasets": [
            dataset_smoke_report(
                name=dataset["name"],
                source=dataset["source"],
                sample_size_requested=dataset["sample_size_requested"],
                memories=dataset["memories"],
                queries=dataset["queries"],
                examples=dataset["examples"],
                skipped=dataset["skipped"],
                kr_eval_runs=dataset["kr_eval_runs"],
                dataset_metadata=dataset.get("metadata"),
            )
            for dataset in datasets
        ],
        "limits": [
            "Small smoke sample only; not a full benchmark run.",
            "DMR source is treated as a candidate until the original DMR harness is pinned.",
            "Report excludes raw questions, answers, dialogs, and session text.",
            "DMR answer matching is an answer-to-memory mapping policy, not an LLM judge.",
            "Comparison covers baseline RRF, vector branch, and vector-plus-reranker branch only.",
            "No LLM judge or hosted external systems are used.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.cleanup_cache:
        for path in cleanup_paths:
            if path.exists():
                shutil.rmtree(path)

    print(json.dumps({
        "output": str(args.output),
        "selected_modes": [config["id"] for config in selected_configs],
        "selected_datasets": sorted(selected_datasets),
        "accelerator": accelerator,
        "dataset_queries": {dataset["id"]: len(dataset["queries"]) for dataset in datasets},
        "kr_eval_runs_per_dataset": len(selected_configs),
        "cleanup_cache": args.cleanup_cache,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
