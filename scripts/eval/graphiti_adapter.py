#!/usr/bin/env python
"""Graphiti adapter for kr-external-eval.

The Rust harness calls this script with one argument: an adapter-input JSON
path. The script prints one ExternalSystemRun JSON object to stdout.

This adapter follows the official Graphiti quickstart shape: graphiti-core,
OpenAI credentials, and a Neo4j backend. If any required piece is missing, it
returns a not_configured report instead of fabricating benchmark numbers.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
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
        "system": "Graphiti/Zep",
        "kind": "graphiti",
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
    return system_run("not_configured", chains, notes)


def failed(input_data: dict[str, Any], note: str) -> dict[str, Any]:
    chains = [placeholder_chain(chain, "failed", "failed", note) for chain in input_data["chains"]]
    return system_run("failed", chains, [note])


def graphiti_version() -> str:
    try:
        return metadata.version("graphiti-core")
    except metadata.PackageNotFoundError:
        return "unknown"


def missing_configuration() -> list[str]:
    notes: list[str] = []
    try:
        __import__("graphiti_core")
    except ImportError:
        notes.append("graphiti-core is not installed")

    for name in ["OPENAI_API_KEY", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]:
        if not os.getenv(name):
            notes.append(f"{name} is not set")
    return notes


def result_content(result: Any) -> str:
    for attr in ["fact", "content", "name", "summary"]:
        value = getattr(result, attr, None)
        if value:
            return str(value)
    return str(result)


def result_id(result: Any, rank: int) -> str:
    for attr in ["uuid", "id"]:
        value = getattr(result, attr, None)
        if value:
            return str(value)
    return f"graphiti-result-{rank}"


def result_path(result: Any) -> list[str]:
    path = []
    for attr in ["source_node_uuid", "target_node_uuid"]:
        value = getattr(result, attr, None)
        if value:
            path.append(str(value))
    return path


def contains_expected(results: list[dict[str, Any]], expected_text: str) -> bool:
    needle = expected_text.lower()
    return any(needle in result["content"].lower() for result in results)


def graphiti_hit(result: Any, rank: int) -> dict[str, Any]:
    return {
        "id": result_id(result, rank),
        "content": result_content(result),
        "source": "graphiti_search",
        "rank": rank,
        "score": None,
        "matched_terms": [],
        "path": result_path(result),
    }


async def add_episode(graphiti: Any, name: str, body: str, reference_time: datetime) -> None:
    from graphiti_core.nodes import EpisodeType

    await graphiti.add_episode(
        name=name,
        episode_body=body,
        source=EpisodeType.text,
        source_description="king-synapse external comparison fixture",
        reference_time=reference_time,
    )


async def run_real_graphiti(input_data: dict[str, Any]) -> dict[str, Any]:
    from graphiti_core import Graphiti

    os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")
    graphiti = Graphiti(
        os.environ["NEO4J_URI"],
        os.environ["NEO4J_USER"],
        os.environ["NEO4J_PASSWORD"],
    )
    chains: list[dict[str, Any]] = []
    try:
        await graphiti.build_indices_and_constraints()
        for chain in input_data["chains"]:
            started = time.perf_counter()
            reference_time = datetime(2026, 7, 2, tzinfo=timezone.utc)
            episode_texts = [
                chain["seed"],
                chain["visible_distractor"],
                chain["hidden"],
                chain["hidden_distractor"],
                chain["future"],
                chain["future_distractor"],
            ]
            for index, text in enumerate(episode_texts):
                await add_episode(
                    graphiti,
                    f"{chain['label']}-{index}",
                    text,
                    reference_time,
                )

            raw_results = await graphiti.search(chain["query"])
            returned = [graphiti_hit(result, idx + 1) for idx, result in enumerate(raw_results)]
            evidence_paths = [
                {
                    "source_id": hit["path"][0] if hit["path"] else "",
                    "source_content": None,
                    "target_id": hit["path"][-1] if hit["path"] else hit["id"],
                    "target_content": hit["content"],
                    "path": hit["path"],
                    "score": hit["score"],
                    "matched_terms": hit["matched_terms"],
                }
                for hit in returned
                if hit["path"]
            ]

            visible_found = contains_expected(returned, chain["seed"])
            hidden_found = contains_expected(returned, chain["hidden"])
            path_available = bool(evidence_paths)
            latency_ms = (time.perf_counter() - started) * 1000.0
            unsupported_note = (
                "Graphiti search does not expose King Synapse cognitive "
                "dominant/suppressed/predict/reinforce semantics through this adapter."
            )
            chains.append(
                {
                    "label": chain["label"],
                    "query": chain["query"],
                    "expected": expected(chain),
                    "status": "measured",
                    "latency_ms": latency_ms,
                    "returned": returned,
                    "evidence_paths": evidence_paths,
                    "dominant": None,
                    "suppressed": [],
                    "prediction_candidates": [],
                    "reinforcement": empty_reinforcement(unsupported_note),
                    "metrics": {
                        "visible_seed_found": metric("hit" if visible_found else "miss", 1.0 if visible_found else 0.0),
                        "hidden_influence_found": metric("hit" if hidden_found else "miss", 1.0 if hidden_found else 0.0),
                        "hidden_influence_dominant": metric("unsupported", None, unsupported_note),
                        "suppressed_alternatives_visible": metric("unsupported", None, unsupported_note),
                        "evidence_path_available": metric("hit" if path_available else "miss", 1.0 if path_available else 0.0),
                        "future_continuation_found": metric("unsupported", None, unsupported_note),
                        "reinforcement_isolated": metric("unsupported", None, unsupported_note),
                    },
                    "notes": [unsupported_note],
                    "raw": {"result_count": len(returned)},
                }
            )
    finally:
        close = getattr(graphiti, "close", None)
        if close is not None:
            maybe = close()
            if hasattr(maybe, "__await__"):
                await maybe

    return system_run(
        run_status(chains),
        chains,
        [
            "Measured through graphiti-core search against the exported cognitive fixture.",
            "Dominant/suppressed cognitive trace metrics are marked unsupported unless Graphiti exposes an equivalent surface.",
        ],
        version=graphiti_version(),
        capabilities={
            "retrieval": "supported",
            "trace": "unsupported",
            "prediction": "unsupported",
            "reinforcement": "unsupported",
            "evidence_paths": "partial",
        },
    )


async def main() -> int:
    if len(sys.argv) != 2:
        print("usage: graphiti_adapter.py <adapter-input.json>", file=sys.stderr)
        return 2

    input_path = Path(sys.argv[1])
    input_data = json.loads(input_path.read_text(encoding="utf-8"))
    missing = missing_configuration()
    if missing:
        print(json.dumps(not_configured(input_data, missing), indent=2))
        return 0

    try:
        report = await run_real_graphiti(input_data)
    except Exception as exc:  # pragma: no cover - depends on external service.
        report = failed(input_data, f"Graphiti adapter failed: {exc}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
