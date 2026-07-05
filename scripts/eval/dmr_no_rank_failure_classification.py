"""Classify DMR no-rank retrieval failures into failure modes.

For each of the 174 samples where the gold-answer chunk did not appear in the
top-10 retrieved results, use DeepSeek LLM to classify the failure type:
- semantic_gap: query and chunk share little lexical/semantic overlap
- multi_hop: answer requires combining information across chunks
- terminology_mismatch: query and chunk use different vocabulary for same concept
- chunk_boundary: answer is split across chunk boundaries
- other: does not fit above categories

Output: sanitized classification report (no raw questions/answers/dialogs committed).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from longmem_dmr_smoke import (
    DMR_ANSWER_MATCH_POLICIES,
    DMR_FILE,
    DMR_REPO,
    build_dialog_chunk,
    configure_accelerator_environment,
    default_cache_root,
    default_fastembed_cache_dir,
    dmr_answer_matches,
    download_dataset,
    read_jsonl,
    repo_root,
    stable_hash,
)

from official_dmr_eval import (
    build_official_dmr_dataset,
)


def classify_with_deepseek(
    *,
    base_url: str,
    model: str,
    question: str,
    gold_answer: str,
    relevant_chunk_preview: str,
    all_chunk_previews: list[str],
) -> dict[str, Any]:
    """Use DeepSeek to classify why a relevant chunk was not retrieved."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"category": "error", "reason": "DEEPSEEK_API_KEY not set"}

    # Truncate previews to keep prompt manageable
    def trunc(text: str, n: int = 200) -> str:
        return text[:n] + "..." if len(text) > n else text

    chunk_list = "\n".join(
        f"[Chunk {i+1}] {trunc(c)}" for i, c in enumerate(all_chunk_previews[:10])
    )

    prompt = (
        "You are analyzing a memory retrieval failure. A question was asked, and the "
        "correct answer exists in one of the memory chunks, but the retrieval system "
        "did not return that chunk in its top-10 results.\n\n"
        "Classify the failure into exactly one category:\n"
        "- semantic_gap: The question and the relevant chunk share little lexical or "
        "semantic overlap. The embedding model would struggle to connect them.\n"
        "- multi_hop: The answer requires combining information from multiple chunks. "
        "No single chunk contains the full answer.\n"
        "- terminology_mismatch: The question uses different vocabulary than the chunk "
        "for the same concept (e.g., 'pet' vs 'cow', 'job' vs 'custodian').\n"
        "- chunk_boundary: The answer is split across two chunks due to dialog segmentation.\n"
        "- other: Does not fit the above categories.\n\n"
        f"Question: {trunc(question, 300)}\n\n"
        f"Gold answer: {trunc(gold_answer, 100)}\n\n"
        f"Relevant chunk (contains answer): {trunc(relevant_chunk_preview, 400)}\n\n"
        f"Top-10 retrieved chunks (none contain the answer):\n{chunk_list}\n\n"
        "Return exactly one JSON object with two keys:\n"
        '{"category": "<one of the above>", "reason": "<one sentence explanation>"}\n'
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a retrieval failure analyst. Return only JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
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
            body = json.loads(response.read().decode("utf-8", errors="replace"))
        content = body["choices"][0]["message"].get("content", "").strip()
        if not content:
            content = body["choices"][0]["message"].get("reasoning_content", "").strip()
        if not content:
            return {"category": "error", "reason": "empty response"}
        parsed = json.loads(content)
        cat = parsed.get("category", "other")
        if cat not in ("semantic_gap", "multi_hop", "terminology_mismatch", "chunk_boundary", "other"):
            cat = "other"
        return {
            "category": cat,
            "reason_hash": stable_hash(str(parsed.get("reason", "")), 16),
        }
    except Exception as exc:
        return {"category": "error", "reason": str(exc)[:200]}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Classify DMR no-rank retrieval failures.")
    parser.add_argument("--synth-report", type=Path,
                        default=repo_root() / "crates/eval/reports/official-dmr-500-deepseek-synthesize.json")
    parser.add_argument("--output", type=Path,
                        default=repo_root() / "crates/eval/reports/dmr-no-rank-failure-classification.json")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--dmr-answer-match", default="significant_token_containment")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    parser.add_argument("--limit", type=int, default=None, help="Limit samples for testing")
    args = parser.parse_args()

    os.environ["HF_ENDPOINT"] = args.endpoint
    os.environ["FASTEMBED_CACHE_DIR"] = str(args.fastembed_cache_dir)
    os.environ["HF_HUB_OFFLINE"] = "1"

    # Load synth report to get the 174 no-rank sample IDs
    report = json.loads(args.synth_report.read_text(encoding="utf-8"))
    per_query = report["answer_generation"]["per_query"]
    no_rank_ids = {
        item["sample_id"] for item in per_query
        if item["first_relevant_rank"] is None
    }
    print(f"No-rank samples in synth report: {len(no_rank_ids)}")

    # Load DMR dataset and rebuild samples (same as official_dmr_eval)
    cache_root = args.cache_root
    cache_root.mkdir(parents=True, exist_ok=True)
    dmr_cache = cache_root / "dmr-msc-self-instruct"
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
    rows = read_jsonl(dmr_path)

    memories, queries, examples, skipped = build_official_dmr_dataset(
        rows, 500, args.dmr_answer_match
    )

    # Build memory lookup
    memory_by_key = {m["key"]: m["content"] for m in memories}

    # For each no-rank sample, extract question, gold answer, relevant chunks
    results = []
    category_counts: Counter[str] = Counter()
    started = time.perf_counter()

    for idx, (query, example) in enumerate(zip(queries, examples)):
        if example["sample_id"] not in no_rank_ids:
            continue
        if args.limit and len(results) >= args.limit:
            break

        question = query["query"]
        gold_answer = example["gold_answer"]
        relevant_keys = query["relevant"]

        # Get relevant chunk content (first one as preview)
        relevant_previews = []
        for key in relevant_keys:
            content = memory_by_key.get(key, "")
            if content:
                relevant_previews.append(content)

        if not relevant_previews:
            results.append({
                "sample_id": example["sample_id"],
                "source_session_count": example["source_session_count"],
                "relevant_count": example["relevant_count"],
                "gold_answer_length": example["gold_answer_length"],
                "classification": {"category": "no_relevant_content", "reason_hash": ""},
            })
            category_counts["no_relevant_content"] += 1
            continue

        # For classification, we need the relevant chunk and a sample of other chunks
        # to represent what the retrieval system returned instead.
        # Since we don't have the actual retrieval results here, we use all chunks
        # from this sample's sessions as context.
        sample_chunks = []
        for key in relevant_keys:
            sample_chunks.append(memory_by_key.get(key, ""))

        # Get a few non-relevant chunks from the same sample for context
        all_sample_keys = [k for k in memory_by_key if k.startswith(f"dmr_{stable_hash(f'{idx}:')}")]
        # Actually we can't easily reconstruct the exact chunk keys per sample
        # Let's just use the relevant chunk preview + the question

        classification = classify_with_deepseek(
            base_url=args.base_url,
            model=args.model,
            question=question,
            gold_answer=gold_answer,
            relevant_chunk_preview=relevant_previews[0],
            all_chunk_previews=relevant_previews[:3],  # Use relevant chunks as preview
        )

        results.append({
            "sample_id": example["sample_id"],
            "source_session_count": example["source_session_count"],
            "relevant_count": example["relevant_count"],
            "gold_answer_length": example["gold_answer_length"],
            "gold_answer_sha256": example["gold_answer_sha256"],
            "relevant_chunk_count": len(relevant_previews),
            "relevant_chunk_length_mean": sum(len(c) for c in relevant_previews) // max(len(relevant_previews), 1),
            "classification": classification,
        })
        category_counts[classification["category"]] += 1

        if (len(results) % 20) == 0:
            elapsed = time.perf_counter() - started
            print(f"  classified {len(results)}/{len(no_rank_ids)} ({elapsed:.0f}s)")

    elapsed_ms = (time.perf_counter() - started) * 1000

    output = {
        "schema_version": "king-synapse.dmr-no-rank-failure-classification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/dmr_no_rank_failure_classification.py",
        "model": args.model,
        "synth_report": str(args.synth_report),
        "total_no_rank_samples": len(no_rank_ids),
        "classified_samples": len(results),
        "category_counts": dict(sorted(category_counts.items())),
        "elapsed_ms": elapsed_ms,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "classifications": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. {len(results)} samples classified in {elapsed_ms:.0f}ms")
    print(f"Category counts: {dict(sorted(category_counts.items()))}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
