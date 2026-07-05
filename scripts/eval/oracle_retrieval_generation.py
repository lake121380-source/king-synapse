"""Oracle retrieval experiment: feed the correct chunk directly to the
generator, bypassing retrieval entirely. This measures the generation
ceiling — if the generator can't answer correctly even with the right
chunk, the ceiling is data/task-bound, not retrieval-bound.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import (
    DMR_FILE,
    DMR_REPO,
    default_cache_root,
    default_fastembed_cache_dir,
    download_dataset,
    read_jsonl,
    repo_root,
    stable_hash,
)

from official_dmr_eval import (
    build_official_dmr_dataset,
    generate_deepseek_synthesize_answer,
    generate_top_context_extractive_answer,
    judge_deepseek,
    lexical_scores,
)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Oracle retrieval + generation upper bound test.")
    parser.add_argument("--output", type=Path,
                        default=repo_root() / "crates/eval/reports/oracle-retrieval-generation.json")
    parser.add_argument("--generator", choices=("top-context-extractive", "deepseek-synthesize"),
                        default="deepseek-synthesize")
    parser.add_argument("--generator-model", default="deepseek-v4-flash")
    parser.add_argument("--generator-base-url", default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--generator-top-k", type=int, default=3)
    parser.add_argument("--generator-max-tokens", type=int, default=256)
    parser.add_argument("--llm-judge", choices=("none", "deepseek"), default="deepseek")
    parser.add_argument("--judge-model", default="deepseek-v4-flash")
    parser.add_argument("--judge-base-url", default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--dmr-answer-match", default="significant_token_containment")
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    args = parser.parse_args()

    os.environ["HF_ENDPOINT"] = args.endpoint
    os.environ["FASTEMBED_CACHE_DIR"] = str(args.fastembed_cache_dir)
    os.environ["HF_HUB_OFFLINE"] = "1"

    # Load DMR dataset
    dmr_cache = args.cache_root / "dmr-msc-self-instruct"
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
    rows = read_jsonl(dmr_path)
    memories, queries, examples, skipped = build_official_dmr_dataset(
        rows, args.sample_size, args.dmr_answer_match
    )
    memory_by_key = {m["key"]: m["content"] for m in memories}
    print(f"Loaded {len(memories)} memories, {len(queries)} queries")

    # For each sample, feed ONLY the relevant chunks to the generator
    per_query = []
    judge_counts: Counter[str] = Counter()
    started = time.perf_counter()

    for index, (query, example) in enumerate(zip(queries, examples)):
        question = query["query"]
        relevant_keys = query["relevant"]
        # Oracle: use relevant chunks as the ONLY contexts
        contexts = [memory_by_key[k] for k in relevant_keys if k in memory_by_key]
        if not contexts:
            continue

        if args.generator == "deepseek-synthesize":
            prediction, generation_trace = generate_deepseek_synthesize_answer(
                question, contexts,
                base_url=args.generator_base_url,
                model=args.generator_model,
                top_k=min(args.generator_top_k, len(contexts)),
                max_tokens=args.generator_max_tokens,
            )
        else:
            prediction, generation_trace = generate_top_context_extractive_answer(question, contexts)

        lexical = lexical_scores(prediction, example["gold_answer"])

        if args.llm_judge == "deepseek":
            judge_result = judge_deepseek(
                base_url=args.judge_base_url,
                model=args.judge_model,
                question=question,
                prediction=prediction,
                gold=example["gold_answer"],
            )
        else:
            judge_result = {"status": "not_requested"}

        judge_counts[str(judge_result.get("status"))] += 1

        per_query.append({
            "sample_id": example["sample_id"],
            "source_session_count": example["source_session_count"],
            "relevant_count": example["relevant_count"],
            "gold_answer_sha256": example["gold_answer_sha256"],
            "gold_answer_length": example["gold_answer_length"],
            "generated_answer_sha256": stable_hash(prediction, 64),
            "generated_answer_length": len(prediction),
            "oracle_context_count": len(contexts),
            "generation_trace": generation_trace,
            "scores": lexical,
            "llm_judge": judge_result,
        })

        if (len(per_query) % 50) == 0:
            elapsed = time.perf_counter() - started
            judged_correct = sum(1 for p in per_query if p["llm_judge"].get("correct"))
            print(f"  processed {len(per_query)}/{len(queries)} ({elapsed:.0f}s) correct={judged_correct}")

    elapsed_ms = (time.perf_counter() - started) * 1000
    n = len(per_query) or 1

    judged_correct = [p for p in per_query if p["llm_judge"].get("status") == "judged" and p["llm_judge"].get("correct")]
    judged_total = [p for p in per_query if p["llm_judge"].get("status") == "judged"]

    aggregate = {
        "n_queries": len(per_query),
        "exact_accuracy": sum(1 for p in per_query if p["scores"]["exact_match"]) / n,
        "punctuation_accuracy": sum(1 for p in per_query if p["scores"]["punctuation_match"]) / n,
        "answer_substring_accuracy": sum(1 for p in per_query if p["scores"]["answer_substring_match"]) / n,
        "rouge_l_precision_mean": sum(p["scores"]["rouge_l"]["precision"] for p in per_query) / n,
        "rouge_l_recall_mean": sum(p["scores"]["rouge_l"]["recall"] for p in per_query) / n,
        "rouge_l_f1_mean": sum(p["scores"]["rouge_l"]["f1"] for p in per_query) / n,
        "llm_judge_status_counts": dict(sorted(judge_counts.items())),
        "llm_judge_accuracy": (len(judged_correct) / len(judged_total)) if judged_total else None,
        "generation_wall_ms": elapsed_ms,
    }

    output = {
        "schema_version": "king-synapse.oracle-retrieval-generation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/oracle_retrieval_generation.py",
        "description": "Oracle retrieval: feed only relevant chunks to generator, bypassing retrieval. Measures generation ceiling.",
        "generator": {
            "policy": args.generator,
            "model": args.generator_model if args.generator == "deepseek-synthesize" else None,
            "top_k": args.generator_top_k,
        },
        "llm_judge": {
            "policy": args.llm_judge,
            "model": args.judge_model,
            "api_key_recorded": False,
        },
        "answer_match_policy": args.dmr_answer_match,
        "sample_size_used": len(per_query),
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "generated_answers_committed": False,
        "answer_generation": {
            "aggregate": aggregate,
            "per_query": per_query,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. {len(per_query)} samples in {elapsed_ms:.0f}ms")
    print(f"Oracle judge accuracy: {aggregate['llm_judge_accuracy']}")
    print(f"Substring accuracy: {aggregate['answer_substring_accuracy']}")
    print(f"ROUGE-L F1 mean: {aggregate['rouge_l_f1_mean']}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
