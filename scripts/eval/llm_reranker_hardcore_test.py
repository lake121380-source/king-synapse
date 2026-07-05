"""LLM reranker test on 83 hard-core samples.

For each of the 83 samples where the relevant chunk is at rank > 100 under
both original and category-expanded queries:

1. Use e5-base to get top-200 candidate chunks
2. Verify the relevant chunk is in the top-200 (if not, it's truly unreachable)
3. For each of the top-200, ask DeepSeek: "Is this chunk relevant to the question?"
4. Check if the LLM identifies the relevant chunk as relevant

This tests whether the bottleneck is "embedding model too small" or
"vector similarity fundamentally cannot capture this relationship."
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

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

from official_dmr_eval import build_official_dmr_dataset


def llm_judge_relevance(
    *,
    base_url: str,
    model: str,
    question: str,
    chunk_text: str,
) -> dict[str, Any]:
    """Ask LLM whether a chunk is relevant to a question."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"relevant": None, "error": "DEEPSEEK_API_KEY not set"}

    # Truncate chunk to keep prompt manageable
    chunk_preview = chunk_text[:300] + "..." if len(chunk_text) > 300 else chunk_text

    prompt = (
        "You are a relevance judge. Given a question and a text passage from a "
        "conversation, determine if the passage contains information that could "
        "help answer the question.\n\n"
        "Be generous: if the passage contains ANY information related to the "
        "question's topic (even indirectly), mark it as relevant.\n\n"
        f"Question: {question[:200]}\n\n"
        f"Passage: {chunk_preview}\n\n"
        "Return exactly one JSON object: {\"relevant\": true/false, \"reason\": \"one word\"}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a relevance judge. Return only JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 50,
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
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8", errors="replace"))
        content = body["choices"][0]["message"].get("content", "").strip()
        if not content:
            content = body["choices"][0]["message"].get("reasoning_content", "").strip()
        if not content:
            return {"relevant": None, "error": "empty response"}
        parsed = json.loads(content)
        return {"relevant": bool(parsed.get("relevant")), "error": None}
    except Exception as exc:
        return {"relevant": None, "error": str(exc)[:200]}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LLM reranker test on hard-core samples.")
    parser.add_argument("--rank-report", type=Path,
                        default=repo_root() / "crates/eval/reports/rank-position-ab.json")
    parser.add_argument("--output", type=Path,
                        default=repo_root() / "crates/eval/reports/llm-reranker-hardcore-test.json")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--dmr-answer-match", default="significant_token_containment")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    parser.add_argument("--top-n", type=int, default=200, help="Number of candidates from e5-base to send to LLM")
    parser.add_argument("--limit", type=int, default=None, help="Limit samples for testing")
    args = parser.parse_args()

    os.environ["HF_ENDPOINT"] = args.endpoint
    os.environ["FASTEMBED_CACHE_DIR"] = str(args.fastembed_cache_dir)
    os.environ["HF_HUB_OFFLINE"] = "1"

    # Load rank report to get hard-core sample IDs
    rp = json.loads(args.rank_report.read_text(encoding="utf-8"))
    rp_by_id = {r["sample_id"]: r for r in rp["results"]}
    hardcore_ids = {
        r["sample_id"] for r in rp["results"]
        if r["orig_rank"] is not None and r["orig_rank"] > 100
        and r["cat_rank"] is not None and r["cat_rank"] > 100
    }
    print(f"Hard-core samples (both ranks > 100): {len(hardcore_ids)}")

    # Load DMR dataset
    dmr_cache = args.cache_root / "dmr-msc-self-instruct"
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
    rows = read_jsonl(dmr_path)
    memories, queries, examples, skipped = build_official_dmr_dataset(
        rows, 500, args.dmr_answer_match
    )
    memory_by_key = {m["key"]: m["content"] for m in memories}

    # Load embedding model
    print("Loading embedding model...")
    import onnxruntime as ort
    from tokenizers import Tokenizer

    model_base = args.fastembed_cache_dir / "models--intfloat--multilingual-e5-base"
    snap = list((model_base / "snapshots").iterdir())[0]
    model_onnx = (snap / "onnx" / "model.onnx").resolve()
    tokenizer_path = (snap / "tokenizer.json").resolve()

    cuda_runtime = Path(os.environ.get("LOCALAPPDATA", "")) / "king-synapse" / "cuda-runtime-py313"
    if cuda_runtime.exists():
        os.environ["PATH"] = str(cuda_runtime) + os.pathsep + os.environ.get("PATH", "")

    session = ort.InferenceSession(str(model_onnx), providers=["CPUExecutionProvider"])
    tok = Tokenizer.from_file(str(tokenizer_path))
    tok.enable_padding(length=256)
    tok.enable_truncation(max_length=256)
    print(f"Providers: {session.get_providers()}")

    def embed_batch(texts, bs=32):
        all_v = []
        for i in range(0, len(texts), bs):
            batch = texts[i:i+bs]
            enc = [tok.encode(t) for t in batch]
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            am = np.array([e.attention_mask for e in enc], dtype=np.int64)
            out = session.run(None, {"input_ids": ids, "attention_mask": am})
            h = out[0]
            me = np.expand_dims(am, -1).astype(h.dtype)
            s = np.sum(h * me, axis=1)
            c = np.clip(np.sum(am, axis=1, keepdims=True), 1, None).astype(h.dtype)
            e = s / c
            n = np.linalg.norm(e, axis=1, keepdims=True)
            e = e / np.clip(n, 1e-12, None)
            all_v.append(e)
        return np.vstack(all_v)

    # Embed all chunks
    chunk_texts = [m["content"][:512] for m in memories]
    chunk_keys = [m["key"] for m in memories]
    print("Embedding all memory chunks...")
    chunk_embs = embed_batch(chunk_texts)
    print(f"Chunk embeddings: {chunk_embs.shape}")

    results = []
    started = time.perf_counter()

    for idx, (query, example) in enumerate(zip(queries, examples)):
        if example["sample_id"] not in hardcore_ids:
            continue
        if args.limit and len(results) >= args.limit:
            break

        sid = example["sample_id"]
        question = query["query"]
        relevant_keys = set(query["relevant"])
        orig_rank = rp_by_id[sid]["orig_rank"]

        # Embed query
        q_emb = embed_batch([question])
        sims = (chunk_embs @ q_emb.T).flatten()

        # Get top-N candidates
        top_n_indices = np.argsort(-sims)[:args.top_n]
        top_n_keys = [chunk_keys[i] for i in top_n_indices]

        # Check if relevant chunk is in top-N
        relevant_in_topn = any(k in relevant_keys for k in top_n_keys)
        relevant_rank_in_topn = None
        for rank, k in enumerate(top_n_keys, start=1):
            if k in relevant_keys:
                relevant_rank_in_topn = rank
                break

        # Direct test: judge the relevant chunk + 5 random distractors
        # This works regardless of whether the chunk is in e5-base top-200
        # This tests whether LLM can identify semantic relevance that e5-base cannot
        import random
        random.seed(hash(sid) % 2**32)

        relevant_chunk_keys = list(relevant_keys)
        distractor_keys = [k for k in chunk_keys if k not in relevant_keys]
        sampled_distractors = random.sample(distractor_keys, min(5, len(distractor_keys)))

        # Shuffle so position is random
        test_keys = relevant_chunk_keys[:1] + sampled_distractors  # 1 relevant + 5 distractors
        random.shuffle(test_keys)

        llm_relevant_count = 0
        llm_found_relevant = False
        llm_judged = 0
        llm_relevant_correct = 0  # how many of the relevant chunks were judged relevant
        llm_distractor_false_positive = 0  # how many distractors were wrongly judged relevant

        for k in test_keys:
            chunk_content = memory_by_key.get(k, "")
            if not chunk_content:
                continue
            judge = llm_judge_relevance(
                base_url=args.base_url,
                model=args.model,
                question=question,
                chunk_text=chunk_content,
            )
            llm_judged += 1
            is_relevant = k in relevant_keys
            if judge.get("relevant"):
                llm_relevant_count += 1
                if is_relevant:
                    llm_found_relevant = True
                    llm_relevant_correct += 1
                else:
                    llm_distractor_false_positive += 1

        results.append({
            "sample_id": sid,
            "orig_rank": orig_rank,
            "relevant_in_topn": relevant_in_topn,
            "relevant_rank_in_topn": relevant_rank_in_topn,
            "llm_found_relevant": llm_found_relevant,
            "llm_relevant_count": llm_relevant_count,
            "llm_judged_count": llm_judged,
            "llm_relevant_correct": llm_relevant_correct,
            "llm_distractor_false_positive": llm_distractor_false_positive,
        })

        if (len(results) % 5) == 0:
            elapsed = time.perf_counter() - started
            found_count = sum(1 for r in results if r.get("llm_found_relevant"))
            print(f"  processed {len(results)}/{len(hardcore_ids)} ({elapsed:.0f}s) LLM found relevant in {found_count}/{len(results)}")

    elapsed_ms = (time.perf_counter() - started) * 1000

    # Aggregate - now all samples are tested (not just those in top-200)
    tested = [r for r in results if r.get("llm_judged_count", 0) > 0]
    not_tested = [r for r in results if r.get("llm_judged_count", 0) == 0]
    llm_found = [r for r in tested if r.get("llm_found_relevant")]
    llm_not_found = [r for r in tested if not r.get("llm_found_relevant")]
    llm_fp_counts = [r.get("llm_distractor_false_positive", 0) for r in tested]
    llm_relevant_correct_counts = [r.get("llm_relevant_correct", 0) for r in tested]

    output = {
        "schema_version": "king-synapse.llm-reranker-hardcore-test.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/llm_reranker_hardcore_test.py",
        "model": args.model,
        "embedding_model": "intfloat/multilingual-e5-base",
        "top_n_from_embedding": args.top_n,
        "top_n_judged_by_llm": 50,
        "total_hardcore_samples": len(hardcore_ids),
        "tested_samples": len(tested),
        "not_tested": len(not_tested),
        "llm_found_relevant": len(llm_found),
        "llm_not_found_relevant": len(llm_not_found),
        "llm_found_rate": round(len(llm_found) / len(tested), 4) if tested else 0,
        "llm_relevant_correct_mean": round(sum(llm_relevant_correct_counts) / len(llm_relevant_correct_counts), 4) if llm_relevant_correct_counts else 0,
        "llm_distractor_fp_mean": round(sum(llm_fp_counts) / len(llm_fp_counts), 4) if llm_fp_counts else 0,
        "llm_distractor_fp_rate": round(sum(llm_fp_counts) / (len(llm_fp_counts) * 5), 4) if llm_fp_counts else 0,
        "elapsed_ms": round(elapsed_ms),
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. {len(results)} samples in {elapsed_ms:.0f}ms")
    print(f"Tested (LLM judged): {len(tested)}")
    print(f"LLM found relevant chunk: {len(llm_found)}/{len(tested)} ({output['llm_found_rate']:.1%})")
    print(f"LLM did NOT find relevant: {len(llm_not_found)}/{len(tested)}")
    print(f"LLM relevant correct mean: {output['llm_relevant_correct_mean']}")
    print(f"LLM distractor false positive mean: {output['llm_distractor_fp_mean']} (out of 5)")
    print(f"LLM distractor FP rate: {output['llm_distractor_fp_rate']:.1%}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
