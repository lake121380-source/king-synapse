#!/usr/bin/env python
"""Sanitized DeepSeek judge preflight for Phase 6 DMR validation.

The official DMR answer-generation runner can compute exact, punctuation, and
ROUGE-L locally. LLM judge scoring still depends on an external DeepSeek chat
completion call. This preflight verifies only that the configured judge endpoint
can return one JSON judgement. It does not read DMR data and does not write API
keys, prompt text, raw responses, or generated text to the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a sanitized DeepSeek judge preflight.")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/official-dmr-judge-preflight.json",
    )
    parser.add_argument("--judge-model", default=os.environ.get("DEEPSEEK_JUDGE_MODEL", "deepseek-chat"))
    parser.add_argument("--judge-base-url", default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def judge_preflight(*, base_url: str, model: str, timeout_seconds: float) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {
            "models_probe": {"status": "not_configured", "reason": "DEEPSEEK_API_KEY is not set"},
            "status": "not_configured",
            "reason": "DEEPSEEK_API_KEY is not set",
        }

    def run_request(url: str, payload: dict[str, Any] | None = None) -> tuple[int | None, str, dict[str, Any]]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST" if payload is not None else "GET",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                return response.status, body, {
                    "wall_ms": (time.perf_counter() - started) * 1000.0,
                }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, body, {
                "wall_ms": (time.perf_counter() - started) * 1000.0,
                "reason": str(exc.reason or exc)[:120],
                "response_body_hash": stable_hash(body, 16) if body else None,
            }
        except (urllib.error.URLError, TimeoutError) as exc:
            return None, "", {
                "wall_ms": (time.perf_counter() - started) * 1000.0,
                "reason": str(exc)[:120],
            }

    models_status, models_body, models_meta = run_request(base_url.rstrip("/") + "/models", None)
    models_probe: dict[str, Any]
    if models_status is None:
        models_probe = {"status": "error", **models_meta}
    elif models_status == 200:
        try:
            parsed = json.loads(models_body)
            models_count = len(parsed.get("data", [])) if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            models_count = None
        models_probe = {
            "status": "ok",
            "http_status": models_status,
            "models_count": models_count,
            "response_body_hash": stable_hash(models_body, 16),
            **models_meta,
        }
    else:
        models_probe = {"status": "http_error", "http_status": models_status, **models_meta}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a strict answer correctness judge."},
            {
                "role": "user",
                "content": (
                    "Judge whether the predicted answer contains the same fact as the gold answer.\n"
                    "Return exactly one JSON object and nothing else.\n"
                    "Use exactly two keys: correct (boolean) and reason (short string).\n"
                    "If the prediction states the same fact with different wording, mark correct true.\n"
                    "Example: {\"correct\": true, \"reason\": \"same fact\"}\n\n"
                    "Question: What color is the sky in the test fact?\n"
                    "Gold answer: blue\n"
                    "Predicted answer: blue\n"
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 80,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    data = json.dumps(payload).encode("utf-8")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                base_url.rstrip("/") + "/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            ),
            timeout=timeout_seconds,
        ) as response:
            body = response.read().decode("utf-8", errors="replace")
            http_status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = "authorization_error" if exc.code in {401, 403} else "http_error"
        return {
            "models_probe": models_probe,
            "status": status,
            "http_status": exc.code,
            "reason": str(exc.reason or exc)[:120],
            "response_body_hash": stable_hash(body, 16) if body else None,
            "wall_ms": (time.perf_counter() - started) * 1000.0,
        }
    except (urllib.error.URLError, TimeoutError) as exc:
        return {
            "models_probe": models_probe,
            "status": "error",
            "reason": str(exc)[:120],
            "wall_ms": (time.perf_counter() - started) * 1000.0,
        }

    try:
        parsed = json.loads(body)
        message = parsed["choices"][0]["message"]
        content = (message.get("content") or message.get("reasoning_content") or "").strip()
        if not content:
            raise ValueError("empty judge content")
        judged = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        return {
            "models_probe": models_probe,
            "status": "error",
            "http_status": http_status,
            "reason": f"invalid judge response: {exc}"[:120],
            "response_body_hash": stable_hash(body, 16),
            "wall_ms": (time.perf_counter() - started) * 1000.0,
        }

    return {
        "models_probe": models_probe,
        "status": "judged",
        "http_status": http_status,
        "correct": bool(judged.get("correct")),
        "reason_hash": stable_hash(str(judged.get("reason", "")), 16),
        "response_body_hash": stable_hash(body, 16),
        "wall_ms": (time.perf_counter() - started) * 1000.0,
    }


def main() -> int:
    args = parse_args()
    result = judge_preflight(
        base_url=args.judge_base_url,
        model=args.judge_model,
        timeout_seconds=args.timeout_seconds,
    )
    report = {
        "schema_version": "king-synapse.deepseek-judge-preflight.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/deepseek_judge_preflight.py",
        "llm_judge": {
            "policy": "deepseek",
            "model": args.judge_model,
            "base_url_recorded": bool(args.judge_base_url),
            "api_key_present": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "api_key_recorded": False,
        },
        "prompt_text_recorded": False,
        "raw_response_committed": False,
        "raw_records_committed": False,
        "result": result,
        "decision": (
            "ready_for_official_dmr_judge_rerun"
            if result.get("status") == "judged"
            else "judge_configuration_still_blocked"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": result.get("status"),
                "http_status": result.get("http_status"),
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
