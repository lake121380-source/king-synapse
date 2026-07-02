#!/usr/bin/env python
"""Mem0 adapter for kr-external-eval.

The Rust harness calls this script with one argument: an adapter-input JSON
path. The script prints one ExternalSystemRun JSON object to stdout.

This adapter uses the Mem0 OSS Python SDK when it is installed and configured.
By default Mem0 OSS requires OpenAI credentials; a custom SDK config can be
provided through MEM0_CONFIG_JSON or MEM0_CONFIG_PATH. If a real Mem0 path is
not available, the adapter returns not_configured instead of fabricating
benchmark numbers.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from importlib import metadata
from pathlib import Path
from typing import Any


METRIC_NAMES = [
    "visible_seed_found",
    "hidden_influence_found",
    "hidden_influence_dominant",
    "suppressed_alternatives_visible",
    "evidence_path_available",
    "future_continuation_found",
    "reinforcement_isolated",
]


def metric(status: str, value: float | None = None, note: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status, "value": value}
    if note:
        result["note"] = note
    return result


def all_metrics(status: str, note: str) -> dict[str, dict[str, Any]]:
    return {name: metric(status, None, note) for name in METRIC_NAMES}


def expected(chain: dict[str, Any]) -> dict[str, str]:
    return {
        "visible_seed": chain["seed"],
        "hidden_influence": chain["hidden"],
        "future_influence": chain["future"],
    }


def empty_reinforcement(note: str) -> dict[str, Any]:
    return {
        "attempted": False,
        "supported": False,
        "isolated_after_report": False,
        "expected_edges": 0,
        "reinforced_edges": 0,
        "edge_weights_before": {},
        "edge_weights_after": {},
        "notes": [note],
    }


def aggregate(chains: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = {
        name: {
            "hit": 0,
            "miss": 0,
            "unsupported": 0,
            "not_configured": 0,
            "failed": 0,
        }
        for name in METRIC_NAMES
    }
    measured_latencies = []
    for chain in chains:
        if chain["status"] == "measured":
            measured_latencies.append(chain["latency_ms"])
        for name, result in chain["metrics"].items():
            metrics[name][result["status"]] += 1
    mean_latency_ms = (
        sum(measured_latencies) / len(measured_latencies) if measured_latencies else 0.0
    )
    return {
        "chains": len(chains),
        "mean_latency_ms": mean_latency_ms,
        "metrics": metrics,
    }


def run_status(chains: list[dict[str, Any]]) -> str:
    statuses = {chain["status"] for chain in chains}
    if statuses == {"measured"}:
        return "measured"
    if statuses == {"not_configured"}:
        return "not_configured"
    if "failed" in statuses:
        return "failed"
    return "measured"


def system_run(
    status: str,
    chains: list[dict[str, Any]],
    notes: list[str],
    version: str = "unknown",
    capabilities: dict[str, str] | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = {
        "system": "Mem0",
        "kind": "mem0",
        "version": version,
        "status": status,
        "capabilities": capabilities
        or {
            "retrieval": "unknown",
            "trace": "unknown",
            "prediction": "unknown",
            "reinforcement": "unknown",
            "evidence_paths": "unknown",
        },
        "aggregate": aggregate(chains),
        "chains": chains,
        "notes": notes,
    }
    if raw is not None:
        run["raw"] = raw
    return run


def placeholder_chain(chain: dict[str, Any], status: str, metric_status: str, note: str) -> dict[str, Any]:
    return {
        "label": chain["label"],
        "query": chain["query"],
        "expected": expected(chain),
        "status": status,
        "latency_ms": 0.0,
        "returned": [],
        "evidence_paths": [],
        "dominant": None,
        "suppressed": [],
        "prediction_candidates": [],
        "reinforcement": empty_reinforcement(note),
        "metrics": all_metrics(metric_status, note),
        "notes": [note],
    }


def not_configured(input_data: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    note = "; ".join(notes)
    chains = [
        placeholder_chain(chain, "not_configured", "not_configured", note)
        for chain in input_data["chains"]
    ]
    return system_run("not_configured", chains, notes, version=mem0_version())


def failed(input_data: dict[str, Any], note: str) -> dict[str, Any]:
    chains = [placeholder_chain(chain, "failed", "failed", note) for chain in input_data["chains"]]
    return system_run("failed", chains, [note], version=mem0_version())


def mem0_version() -> str:
    try:
        return metadata.version("mem0ai")
    except metadata.PackageNotFoundError:
        return "unknown"


def mem0_installed() -> bool:
    try:
        __import__("mem0")
        return True
    except ImportError:
        return False


def has_custom_config() -> bool:
    return bool(os.getenv("MEM0_CONFIG_JSON") or os.getenv("MEM0_CONFIG_PATH"))


def missing_configuration() -> list[str]:
    notes: list[str] = []
    if not mem0_installed():
        notes.append("mem0ai is not installed")
    if not has_custom_config() and not os.getenv("OPENAI_API_KEY"):
        notes.append(
            "OPENAI_API_KEY is not set; Mem0 OSS defaults require OpenAI unless "
            "MEM0_CONFIG_JSON or MEM0_CONFIG_PATH is provided"
        )
    return notes


def load_mem0_config() -> dict[str, Any] | None:
    raw_json = os.getenv("MEM0_CONFIG_JSON")
    if raw_json:
        return json.loads(raw_json)

    raw_path = os.getenv("MEM0_CONFIG_PATH")
    if not raw_path:
        return None

    path = Path(raw_path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)

    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required for non-JSON MEM0_CONFIG_PATH files") from exc
    return yaml.safe_load(text)


def normalized_tokens(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return {token for token in cleaned.split() if token}


def contains_expected(hits: list[dict[str, Any]], expected_text: str) -> bool:
    expected_tokens = normalized_tokens(expected_text)
    if not expected_tokens:
        return False
    for hit in hits:
        hit_tokens = normalized_tokens(hit["content"])
        if expected_tokens.issubset(hit_tokens) or expected_text.lower() in hit["content"].lower():
            return True
    return False


def matched_terms(query: str, content: str) -> list[str]:
    return sorted(normalized_tokens(query) & normalized_tokens(content))


def result_items(raw: Any) -> list[Any]:
    if isinstance(raw, dict):
        for key in ["results", "memories", "data"]:
            value = raw.get(key)
            if isinstance(value, list):
                return value
        return []
    if isinstance(raw, list):
        return raw
    return []


def result_content(result: Any) -> str:
    if isinstance(result, dict):
        for key in ["memory", "content", "text", "summary"]:
            value = result.get(key)
            if isinstance(value, str) and value:
                return value
        return json.dumps(result, sort_keys=True, default=str)

    for attr in ["memory", "content", "text", "summary"]:
        value = getattr(result, attr, None)
        if isinstance(value, str) and value:
            return value
    return str(result)


def result_id(result: Any, rank: int) -> str:
    if isinstance(result, dict):
        for key in ["id", "memory_id", "uuid"]:
            value = result.get(key)
            if value:
                return str(value)

    for attr in ["id", "memory_id", "uuid"]:
        value = getattr(result, attr, None)
        if value:
            return str(value)
    return f"mem0-result-{rank}"


def result_score(result: Any) -> float | None:
    value = None
    if isinstance(result, dict):
        value = result.get("score")
    else:
        value = getattr(result, "score", None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mem0_hit(result: Any, rank: int, query: str) -> dict[str, Any]:
    content = result_content(result)
    return {
        "id": result_id(result, rank),
        "content": content,
        "source": "mem0_search",
        "rank": rank,
        "score": result_score(result),
        "matched_terms": matched_terms(query, content),
        "path": [],
    }


def fixture_message(chain: dict[str, Any]) -> list[dict[str, str]]:
    content = "\n".join(
        [
            "Store these memory facts for an external cognitive-memory comparison:",
            f"- visible seed: {chain['seed']}",
            f"- visible distractor: {chain['visible_distractor']}",
            f"- hidden influence: {chain['hidden']}",
            f"- hidden distractor: {chain['hidden_distractor']}",
            f"- future continuation: {chain['future']}",
            f"- future distractor: {chain['future_distractor']}",
            f"- relation: {chain['seed']} activates {chain['hidden']}",
            f"- relation: {chain['hidden']} continues into {chain['future']}",
        ]
    )
    return [{"role": "user", "content": content}]


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def run_real_mem0(input_data: dict[str, Any]) -> dict[str, Any]:
    from mem0 import Memory

    config = load_mem0_config()
    memory = Memory.from_config(config) if config is not None else Memory()
    run_id = os.getenv("MEM0_EVAL_USER_PREFIX") or f"king-synapse-eval-{uuid.uuid4().hex}"
    unsupported_note = (
        "Mem0 OSS search measures memory add/search retrieval; it does not expose "
        "King Synapse dominant/suppressed/predict/reinforce semantics."
    )
    path_note = "Mem0 OSS search results do not expose graph/path evidence for this fixture."
    chains: list[dict[str, Any]] = []

    for chain in input_data["chains"]:
        started = time.perf_counter()
        user_id = f"{run_id}-{chain['label']}"
        add_result = memory.add(fixture_message(chain), user_id=user_id)
        raw_results = memory.search(chain["query"], filters={"user_id": user_id}, top_k=10)
        returned = [
            mem0_hit(result, idx + 1, chain["query"])
            for idx, result in enumerate(result_items(raw_results))
        ]
        visible_found = contains_expected(returned, chain["seed"])
        hidden_found = contains_expected(returned, chain["hidden"])
        latency_ms = (time.perf_counter() - started) * 1000.0

        chains.append(
            {
                "label": chain["label"],
                "query": chain["query"],
                "expected": expected(chain),
                "status": "measured",
                "latency_ms": latency_ms,
                "returned": returned,
                "evidence_paths": [],
                "dominant": None,
                "suppressed": [],
                "prediction_candidates": [],
                "reinforcement": empty_reinforcement(unsupported_note),
                "metrics": {
                    "visible_seed_found": metric(
                        "hit" if visible_found else "miss", 1.0 if visible_found else 0.0
                    ),
                    "hidden_influence_found": metric(
                        "hit" if hidden_found else "miss", 1.0 if hidden_found else 0.0
                    ),
                    "hidden_influence_dominant": metric("unsupported", None, unsupported_note),
                    "suppressed_alternatives_visible": metric(
                        "unsupported", None, unsupported_note
                    ),
                    "evidence_path_available": metric("unsupported", None, path_note),
                    "future_continuation_found": metric("unsupported", None, unsupported_note),
                    "reinforcement_isolated": metric("unsupported", None, unsupported_note),
                },
                "notes": [unsupported_note, path_note],
                "raw": {
                    "user_id": user_id,
                    "add_result": json_safe(add_result),
                    "search_result": json_safe(raw_results),
                },
            }
        )

    notes = [
        "Measured through the Mem0 OSS Python SDK using Memory.add and Memory.search.",
        "Each chain uses a fresh user_id namespace for isolation.",
    ]
    if config is not None:
        notes.append("Mem0 configuration was loaded from MEM0_CONFIG_JSON or MEM0_CONFIG_PATH.")
    else:
        notes.append("Mem0 ran with its default OSS configuration.")

    return system_run(
        run_status(chains),
        chains,
        notes,
        version=mem0_version(),
        capabilities={
            "retrieval": "supported",
            "trace": "unsupported",
            "prediction": "unsupported",
            "reinforcement": "unsupported",
            "evidence_paths": "unsupported",
        },
        raw={"mode": "oss_sdk"},
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: mem0_adapter.py <adapter-input.json>", file=sys.stderr)
        return 2

    input_path = Path(sys.argv[1])
    input_data = json.loads(input_path.read_text(encoding="utf-8"))
    missing = missing_configuration()
    if missing:
        print(json.dumps(not_configured(input_data, missing), indent=2))
        return 0

    try:
        report = run_real_mem0(input_data)
    except Exception as exc:  # pragma: no cover - depends on external services.
        report = failed(input_data, f"Mem0 adapter failed: {exc}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
