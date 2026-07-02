#!/usr/bin/env python
"""Letta adapter for kr-external-eval.

The Rust harness calls this script with one argument: an adapter-input JSON
path. The script prints one ExternalSystemRun JSON object to stdout.

This adapter uses the official letta-client Python SDK when it is installed
and configured. Letta memory blocks are stateful agent context, not ordinary
graph/path retrieval; the adapter therefore measures block creation/retrieval
and reports unsupported cognitive-trace semantics honestly.
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
        "system": "Letta",
        "kind": "letta",
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
    return system_run("not_configured", chains, notes, version=letta_version())


def failed(input_data: dict[str, Any], note: str) -> dict[str, Any]:
    chains = [placeholder_chain(chain, "failed", "failed", note) for chain in input_data["chains"]]
    return system_run("failed", chains, [note], version=letta_version())


def letta_version() -> str:
    try:
        return metadata.version("letta-client")
    except metadata.PackageNotFoundError:
        return "unknown"


def letta_installed() -> bool:
    try:
        __import__("letta_client")
        return True
    except ImportError:
        return False


def has_letta_endpoint() -> bool:
    if os.getenv("LETTA_API_KEY") or os.getenv("LETTA_BASE_URL"):
        return True
    return os.getenv("LETTA_ENVIRONMENT", "").strip().lower() == "local"


def missing_configuration() -> list[str]:
    notes: list[str] = []
    if not letta_installed():
        notes.append("letta-client is not installed")
    if not has_letta_endpoint():
        notes.append("LETTA_API_KEY, LETTA_BASE_URL, or LETTA_ENVIRONMENT=local is required")
    return notes


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


def block_value(block: Any) -> str:
    if isinstance(block, dict):
        return str(block.get("value") or block.get("content") or "")
    return str(getattr(block, "value", "") or getattr(block, "content", "") or "")


def object_id(value: Any, fallback: str) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("uuid") or fallback)
    return str(getattr(value, "id", None) or getattr(value, "uuid", None) or fallback)


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def fixture_block_value(chain: dict[str, Any]) -> str:
    return "\n".join(
        [
            "External cognitive-memory comparison fixture.",
            f"Query: {chain['query']}",
            f"Visible seed: {chain['seed']}",
            f"Visible distractor: {chain['visible_distractor']}",
            f"Hidden influence: {chain['hidden']}",
            f"Hidden distractor: {chain['hidden_distractor']}",
            f"Future continuation: {chain['future']}",
            f"Future distractor: {chain['future_distractor']}",
            f"Relation: {chain['seed']} activates {chain['hidden']}",
            f"Relation: {chain['hidden']} continues into {chain['future']}",
        ]
    )


def make_client() -> Any:
    from letta_client import Letta

    kwargs: dict[str, Any] = {}
    if os.getenv("LETTA_API_KEY"):
        kwargs["api_key"] = os.getenv("LETTA_API_KEY")
    if os.getenv("LETTA_BASE_URL"):
        kwargs["base_url"] = os.getenv("LETTA_BASE_URL")
    if os.getenv("LETTA_ENVIRONMENT"):
        kwargs["environment"] = os.getenv("LETTA_ENVIRONMENT")
    return Letta(**kwargs)


def cleanup_agent(client: Any, agent_id: str) -> str | None:
    delete = getattr(getattr(client, "agents", None), "delete", None)
    if not callable(delete):
        return "Letta client does not expose agents.delete; cleanup skipped."
    try:
        delete(agent_id=agent_id)
        return None
    except TypeError:
        try:
            delete(agent_id)
            return None
        except Exception as exc:  # pragma: no cover - depends on external service.
            return f"Letta cleanup warning: {exc}"
    except Exception as exc:  # pragma: no cover - depends on external service.
        return f"Letta cleanup warning: {exc}"


def run_real_letta(input_data: dict[str, Any]) -> dict[str, Any]:
    client = make_client()
    run_id = os.getenv("LETTA_EVAL_AGENT_PREFIX") or f"king-synapse-eval-{uuid.uuid4().hex}"
    model = os.getenv("LETTA_MODEL", "openai/gpt-4o-mini")
    unsupported_note = (
        "Letta memory blocks measure persisted agent context; they do not expose "
        "King Synapse dominant/suppressed/predict/reinforce semantics."
    )
    path_note = "Letta memory block retrieval does not expose graph/path evidence for this fixture."
    chains: list[dict[str, Any]] = []

    for chain in input_data["chains"]:
        started = time.perf_counter()
        block_label = "cognitive_fixture"
        agent_state = client.agents.create(
            name=f"{run_id}-{chain['label']}",
            memory_blocks=[
                {
                    "label": block_label,
                    "description": "Read-only cognitive-memory comparison fixture facts.",
                    "value": fixture_block_value(chain),
                    "limit": 12000,
                    "read_only": True,
                }
            ],
            model=model,
        )
        agent_id = object_id(agent_state, f"letta-agent-{chain['label']}")
        block = client.agents.blocks.retrieve(agent_id=agent_id, block_label=block_label)
        content = block_value(block)
        block_id = object_id(block, f"letta-block-{chain['label']}")
        returned = [
            {
                "id": block_id,
                "content": content,
                "source": "letta_memory_block",
                "rank": 1,
                "score": None,
                "matched_terms": matched_terms(chain["query"], content),
                "path": [],
            }
        ]
        visible_found = contains_expected(returned, chain["seed"])
        hidden_found = contains_expected(returned, chain["hidden"])
        cleanup_note = cleanup_agent(client, agent_id)
        latency_ms = (time.perf_counter() - started) * 1000.0
        notes = [unsupported_note, path_note]
        if cleanup_note:
            notes.append(cleanup_note)

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
                "notes": notes,
                "raw": {
                    "agent_id": agent_id,
                    "block_id": block_id,
                    "agent_state": json_safe(agent_state),
                    "block": json_safe(block),
                },
            }
        )

    return system_run(
        run_status(chains),
        chains,
        [
            "Measured through the Letta Python SDK using agent memory blocks.",
            "Each chain uses a fresh agent and memory block.",
        ],
        version=letta_version(),
        capabilities={
            "retrieval": "partial",
            "trace": "unsupported",
            "prediction": "unsupported",
            "reinforcement": "unsupported",
            "evidence_paths": "unsupported",
        },
        raw={"mode": "agent_memory_blocks", "model": model},
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: letta_adapter.py <adapter-input.json>", file=sys.stderr)
        return 2

    input_path = Path(sys.argv[1])
    input_data = json.loads(input_path.read_text(encoding="utf-8"))
    missing = missing_configuration()
    if missing:
        print(json.dumps(not_configured(input_data, missing), indent=2))
        return 0

    try:
        report = run_real_letta(input_data)
    except Exception as exc:  # pragma: no cover - depends on external service.
        report = failed(input_data, f"Letta adapter failed: {exc}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
