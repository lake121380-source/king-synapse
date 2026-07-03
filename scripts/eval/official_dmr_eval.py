#!/usr/bin/env python
"""Answer-generation DMR evaluation for Phase 6 validation.

This runner keeps raw DMR records in a temporary/cache location, retrieves
candidate memories through `kr-eval`, generates an answer from returned memory
chunks, and writes only sanitized scoring evidence. The output must not contain
raw questions, answers, dialogs, sessions, or generated answer text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

from longmem_dmr_smoke import (
    DMR_ANSWER_MATCH_POLICIES,
    DMR_FILE,
    DMR_REPO,
    SMOKE_CONFIGS,
    build_dialog_chunk,
    configure_accelerator_environment,
    default_cache_root,
    default_fastembed_cache_dir,
    dmr_answer_matches,
    download_dataset,
    read_jsonl,
    repo_root,
    run_kr_eval,
    sanitize_eval_report,
    sha256_file,
    source_file_report,
    stable_hash,
    write_toml_dataset,
)


GENERATOR_POLICIES = {
    "extractive": "deterministic sentence/window selection from returned chunks; no gold-answer access",
    "top-context-extractive": "deterministic sentence/window selection restricted to the top returned chunk; no gold-answer access",
}

JUDGE_POLICIES = {
    "none": "no LLM judge; report lexical and ROUGE-L metrics only",
    "deepseek": "DeepSeek chat judge through DEEPSEEK_API_KEY",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sanitized answer-generation DMR evaluation.")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "crates/eval/reports/official-dmr-5-extractive.json",
    )
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument(
        "--dmr-answer-match",
        choices=tuple(DMR_ANSWER_MATCH_POLICIES),
        default="punctuation",
        help="Policy for selecting rows whose gold answer appears in temporary memory chunks.",
    )
    parser.add_argument(
        "--mode",
        choices=("baseline-rrf", "vectors", "vectors-rerank"),
        default="vectors-rerank",
    )
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--generator", choices=tuple(GENERATOR_POLICIES), default="extractive")
    parser.add_argument("--llm-judge", choices=tuple(JUDGE_POLICIES), default="none")
    parser.add_argument("--judge-model", default="deepseek-chat")
    parser.add_argument("--judge-base-url", default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--embed-batch-size", type=int, default=None)
    parser.add_argument("--embed-max-length", type=int, default=None)
    parser.add_argument("--rerank-batch-size", type=int, default=None)
    parser.add_argument("--rerank-max-length", type=int, default=None)
    parser.add_argument(
        "--accelerator",
        choices=("env", "cpu", "cuda", "directml"),
        default="cuda",
        help="Default is cuda because Phase 6 long-memory validation is GPU-first.",
    )
    parser.add_argument("--cuda-device-id", default="0")
    parser.add_argument("--cuda-runtime-root", type=Path, default=None)
    parser.add_argument("--directml-device-id", default=None)
    parser.add_argument("--cleanup-cache", action="store_true")
    return parser.parse_args()


def config_for_mode(mode: str) -> dict[str, Any]:
    for config in SMOKE_CONFIGS:
        if config["id"] == mode:
            return dict(config)
    raise ValueError(f"unknown mode: {mode}")


def build_official_dmr_dataset(
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
                "category": "dmr-answer-generation",
                "source_session_count": len(chunks),
                "relevant_count": len(relevant_keys),
                "gold_answer": str(answer),
                "gold_answer_sha256": stable_hash(str(answer), 64),
                "gold_answer_length": len(str(answer)),
            }
        )
        if len(queries) >= sample_size:
            break

    return memories, queries, examples, skipped


def normalize_whitespace(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def normalized_tokens(value: Any) -> list[str]:
    return re.findall(r"[\w]+", str(value).casefold())


def normalize_punctuation(value: Any) -> str:
    return " ".join(normalized_tokens(value))


def sentence_candidates(text: str) -> list[str]:
    pieces: list[str] = []
    for line in text.splitlines():
        for part in re.split(r"(?<=[.!?。！？])\s+|\s{2,}", line):
            cleaned = " ".join(part.split())
            if cleaned:
                pieces.append(cleaned)
    if pieces:
        return pieces
    cleaned = " ".join(text.split())
    return [cleaned] if cleaned else []


def query_terms(question: str) -> set[str]:
    stop = {
        "a",
        "an",
        "and",
        "are",
        "did",
        "does",
        "for",
        "from",
        "how",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
    }
    return {token for token in normalized_tokens(question) if len(token) > 2 and token not in stop}


def generate_extractive_answer(question: str, contexts: list[str], max_chars: int = 320) -> tuple[str, dict[str, Any]]:
    terms = query_terms(question)
    best_text = ""
    best_score = float("-inf")
    best_context_rank = None
    best_sentence_rank = None

    for context_rank, context in enumerate(contexts, start=1):
        for sentence_rank, sentence in enumerate(sentence_candidates(context), start=1):
            tokens = normalized_tokens(sentence)
            if not tokens:
                continue
            overlap = sum(1 for token in tokens if token in terms)
            score = overlap * 5.0
            score += min(len(set(tokens) & terms), 5)
            score -= context_rank * 0.05
            score -= sentence_rank * 0.01
            if score > best_score:
                best_score = score
                best_text = sentence
                best_context_rank = context_rank
                best_sentence_rank = sentence_rank

    if not best_text and contexts:
        best_text = " ".join(contexts[0].split())
        best_context_rank = 1
        best_sentence_rank = 1

    answer = best_text[:max_chars].strip()
    return answer, {
        "policy": "extractive",
        "context_count": len(contexts),
        "selected_context_rank": best_context_rank,
        "selected_sentence_rank": best_sentence_rank,
        "query_term_count": len(terms),
        "max_chars": max_chars,
    }


def generate_top_context_extractive_answer(
    question: str, contexts: list[str], max_chars: int = 320
) -> tuple[str, dict[str, Any]]:
    answer, trace = generate_extractive_answer(question, contexts[:1], max_chars=max_chars)
    trace.update(
        {
            "policy": "top-context-extractive",
            "context_count": len(contexts),
            "candidate_context_count": min(len(contexts), 1),
            "search_scope": "top_returned_context_only",
        }
    )
    return answer, trace


def lcs_length(left: list[str], right: list[str]) -> int:
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    for l_token in left:
        current = [0]
        for index, r_token in enumerate(right, start=1):
            if l_token == r_token:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def rouge_l(prediction: str, gold: str) -> dict[str, float]:
    pred_tokens = normalized_tokens(prediction)
    gold_tokens = normalized_tokens(gold)
    if not pred_tokens or not gold_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    lcs = lcs_length(pred_tokens, gold_tokens)
    precision = lcs / len(pred_tokens)
    recall = lcs / len(gold_tokens)
    f1 = 0.0 if precision + recall == 0.0 else (2 * precision * recall) / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def lexical_scores(prediction: str, gold: str) -> dict[str, Any]:
    exact = normalize_whitespace(prediction) == normalize_whitespace(gold)
    punctuation_exact = normalize_punctuation(prediction) == normalize_punctuation(gold)
    normalized_prediction = normalize_punctuation(prediction)
    normalized_gold = normalize_punctuation(gold)
    answer_substring = bool(normalized_gold and normalized_gold in normalized_prediction)
    rouge = rouge_l(prediction, gold)
    return {
        "exact_match": exact,
        "punctuation_match": punctuation_exact,
        "answer_substring_match": answer_substring,
        "rouge_l": rouge,
    }


def judge_deepseek(
    *,
    base_url: str,
    model: str,
    question: str,
    prediction: str,
    gold: str,
) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"status": "not_configured", "reason": "DEEPSEEK_API_KEY is not set"}

    prompt = (
        "You are judging whether a predicted answer correctly answers a DMR question.\n"
        "Return exactly one JSON object and nothing else. Do not use markdown, code fences, "
        "or commentary. The JSON object must have exactly two keys: correct (boolean) and "
        "reason (short string).\n"
        "Do not require exact wording if the predicted answer contains the same fact.\n\n"
        f"Question:\n{question}\n\nGold answer:\n{gold}\n\nPredicted answer:\n{prediction}\n"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a strict answer correctness judge."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 120,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = "authorization_error" if exc.code in {401, 403} else "http_error"
        return {
            "status": status,
            "http_status": exc.code,
            "reason": str(exc.reason or exc)[:300],
        }
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status": "error", "reason": str(exc)[:300]}

    try:
        parsed = json.loads(body)
        content = parsed["choices"][0]["message"]["content"]
        judged = parse_judge_content(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        return {"status": "error", "reason": f"invalid judge response: {exc}"[:300]}

    return {
        "status": "judged",
        "correct": bool(judged.get("correct")),
        "reason_hash": stable_hash(str(judged.get("reason", "")), 16),
    }


def parse_judge_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].lstrip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def score_answers(
    *,
    raw_report: dict[str, Any],
    memories: list[dict[str, str]],
    examples: list[dict[str, Any]],
    generator: str,
    llm_judge: str,
    judge_model: str,
    judge_base_url: str,
) -> dict[str, Any]:
    memory_by_key = {memory["key"]: memory["content"] for memory in memories}
    per_query: list[dict[str, Any]] = []
    judge_counts: Counter[str] = Counter()
    started = time.perf_counter()

    for index, query_result in enumerate(raw_report.get("per_query", [])):
        example = examples[index]
        returned_keys = query_result.get("returned", [])
        contexts = [memory_by_key[key] for key in returned_keys if key in memory_by_key]
        if generator == "extractive":
            prediction, generation_trace = generate_extractive_answer(query_result.get("query", ""), contexts)
        elif generator == "top-context-extractive":
            prediction, generation_trace = generate_top_context_extractive_answer(
                query_result.get("query", ""), contexts
            )
        else:
            raise ValueError(f"unknown generator: {generator}")

        lexical = lexical_scores(prediction, example["gold_answer"])
        judge_result: dict[str, Any]
        if llm_judge == "deepseek":
            judge_result = judge_deepseek(
                base_url=judge_base_url,
                model=judge_model,
                question=query_result.get("query", ""),
                prediction=prediction,
                gold=example["gold_answer"],
            )
        else:
            judge_result = {"status": "not_requested"}
        judge_counts[str(judge_result.get("status"))] += 1

        first_rank = first_rank_for_relevant(returned_keys, set(query_result.get("relevant", [])))
        per_query.append(
            {
                "sample_id": example["sample_id"],
                "category": example["category"],
                "source_session_count": example["source_session_count"],
                "relevant_count": example["relevant_count"],
                "gold_answer_sha256": example["gold_answer_sha256"],
                "gold_answer_length": example["gold_answer_length"],
                "generated_answer_sha256": stable_hash(prediction, 64),
                "generated_answer_length": len(prediction),
                "retrieved_context_count": len(contexts),
                "first_relevant_rank": first_rank,
                "generation_trace": generation_trace,
                "scores": lexical,
                "llm_judge": judge_result,
            }
        )

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    n = len(per_query) or 1
    judged_correct = [
        item["llm_judge"].get("correct")
        for item in per_query
        if item["llm_judge"].get("status") == "judged"
    ]
    aggregate = {
        "n_queries": len(per_query),
        "exact_accuracy": sum(1 for item in per_query if item["scores"]["exact_match"]) / n,
        "punctuation_accuracy": sum(1 for item in per_query if item["scores"]["punctuation_match"]) / n,
        "answer_substring_accuracy": sum(1 for item in per_query if item["scores"]["answer_substring_match"]) / n,
        "rouge_l_precision_mean": sum(item["scores"]["rouge_l"]["precision"] for item in per_query) / n,
        "rouge_l_recall_mean": sum(item["scores"]["rouge_l"]["recall"] for item in per_query) / n,
        "rouge_l_f1_mean": sum(item["scores"]["rouge_l"]["f1"] for item in per_query) / n,
        "llm_judge_status_counts": dict(sorted(judge_counts.items())),
        "llm_judge_accuracy": (
            sum(1 for value in judged_correct if value) / len(judged_correct)
            if judged_correct
            else None
        ),
        "generation_wall_ms": elapsed_ms,
    }
    return {"aggregate": aggregate, "per_query": per_query}


def first_rank_for_relevant(returned: list[str], relevant: set[str]) -> int | None:
    for index, key in enumerate(returned, start=1):
        if key in relevant:
            return index
    return None


def sanitized_generation_report(scored: dict[str, Any]) -> dict[str, Any]:
    return scored


def main() -> int:
    args = parse_args()
    root = repo_root()
    os.environ["HF_ENDPOINT"] = args.endpoint
    os.environ["FASTEMBED_CACHE_DIR"] = str(args.fastembed_cache_dir)
    args.output = args.output if args.output.is_absolute() else root / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    args.fastembed_cache_dir.mkdir(parents=True, exist_ok=True)

    accelerator = configure_accelerator_environment(args)
    mode_config = config_for_mode(args.mode)
    api = HfApi(endpoint=args.endpoint)

    dmr_info = api.dataset_info(DMR_REPO)
    info = {
        "repo_id": DMR_REPO,
        "revision": getattr(dmr_info, "sha", None),
        "license": (
            dmr_info.card_data.get("license")
            if getattr(dmr_info, "card_data", None) is not None and hasattr(dmr_info.card_data, "get")
            else None
        ),
    }
    dmr_cache = args.cache_root / "dmr-msc-self-instruct"
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
    rows = read_jsonl(dmr_path)
    memories, queries, examples, skipped = build_official_dmr_dataset(
        rows, args.sample_size, args.dmr_answer_match
    )
    if not queries:
        raise RuntimeError("official DMR answer-generation sample is empty")

    with tempfile.TemporaryDirectory(prefix="king-synapse-official-dmr-") as temp:
        temp_dir = Path(temp)
        dataset_path = temp_dir / "official-dmr.toml"
        raw_report_path = temp_dir / "official-dmr-raw-report.json"
        write_toml_dataset(dataset_path, memories, queries)
        tag = f"official-dmr-{args.generator}-{args.mode}"
        raw_report = run_kr_eval(
            dataset_path,
            raw_report_path,
            tag,
            args.k,
            vectors=bool(mode_config["vectors"]),
            rerank=bool(mode_config["rerank"]),
            rerank_pool=int(mode_config["rerank_pool"]),
        )
        retrieval_report = sanitize_eval_report(raw_report, examples)
        retrieval_report.update(
            {
                "mode": mode_config["id"],
                "label": mode_config["label"],
                "tag": raw_report.get("tag"),
            }
        )
        scored = score_answers(
            raw_report=raw_report,
            memories=memories,
            examples=examples,
            generator=args.generator,
            llm_judge=args.llm_judge,
            judge_model=args.judge_model,
            judge_base_url=args.judge_base_url,
        )

    report = {
        "schema_version": "king-synapse.official-dmr-answer-eval.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/official_dmr_eval.py",
        "endpoint": args.endpoint,
        "source": source_file_report(DMR_REPO, DMR_FILE, dmr_path, info),
        "cache_policy": {
            "cache_root_recorded": False,
            "fastembed_cache_dir_recorded": False,
            "fastembed_cache_configured": True,
            "raw_cache_retained": not args.cleanup_cache,
            "raw_records_committed": False,
        },
        "sample_size_requested": args.sample_size,
        "sample_size_used": len(queries),
        "selection_policy": "stable source order after answer-to-memory mapping policy",
        "answer_match_policy": args.dmr_answer_match,
        "answer_match_policy_description": DMR_ANSWER_MATCH_POLICIES[args.dmr_answer_match],
        "accelerator": accelerator,
        "retrieval_mode": mode_config["id"],
        "generator": {
            "policy": args.generator,
            "description": GENERATOR_POLICIES[args.generator],
        },
        "llm_judge": {
            "policy": args.llm_judge,
            "description": JUDGE_POLICIES[args.llm_judge],
            "model": args.judge_model if args.llm_judge != "none" else None,
            "base_url_recorded": bool(args.judge_base_url and args.llm_judge != "none"),
            "api_key_recorded": False,
        },
        "temporary_dataset_committed": False,
        "raw_records_committed": False,
        "raw_answers_committed": False,
        "generated_answers_committed": False,
        "memory_chunks": len(memories),
        "skipped": dict(sorted(skipped.items())),
        "retrieval": retrieval_report,
        "answer_generation": sanitized_generation_report(scored),
        "limits": [
            "This is an answer-generation DMR evaluation shape, but the default extractive generator is not a published DMR agent policy.",
            "Exact, punctuation-normalized, and ROUGE-L metrics are computed locally.",
            "LLM judge scores are included only when explicitly requested and configured.",
            "Report excludes raw questions, answers, dialogs, sessions, and generated answer text.",
            "Small samples should not be compared with published DMR results.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.cleanup_cache and dmr_cache.exists():
        shutil.rmtree(dmr_cache)

    print(
        json.dumps(
            {
                "output": str(args.output),
                "sample_size_used": len(queries),
                "retrieval_mode": mode_config["id"],
                "generator": args.generator,
                "llm_judge": args.llm_judge,
                "accelerator": accelerator,
                "answer_metrics": report["answer_generation"]["aggregate"],
                "cleanup_cache": args.cleanup_cache,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
