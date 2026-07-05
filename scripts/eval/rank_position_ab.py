"""Rank-position A/B: does query expansion change the actual ranking of the
relevant chunk among ALL memory chunks, not just its cosine similarity?

For each of the 174 no-rank samples:
1. Embed all 2165 memory chunks (once)
2. Embed three query variants: original, hyde, category_expansion
3. For each variant, compute cosine similarity to ALL chunks, find the rank
   of the relevant chunk
4. Compare ranks across variants

This directly measures whether expansion changes the relevant chunk's
position in the ranking, which is what actually determines retrieval accuracy.
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
    build_dialog_chunk,
    default_cache_root,
    default_fastembed_cache_dir,
    dmr_answer_matches,
    download_dataset,
    read_jsonl,
    repo_root,
    stable_hash,
)

from official_dmr_eval import build_official_dmr_dataset


def generate_variant(*, base_url, model, question, variant_type):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return ""
    if variant_type == "hyde":
        prompt = (
            f"Answer this question in one or two sentences as if you are the person being asked. "
            f"Use specific, concrete language. Even if you're guessing, give a confident answer.\n\n"
            f"Question: {question}\n\nAnswer:"
        )
    elif variant_type == "category_expansion":
        prompt = (
            f"Given this question, generate a list of specific instances and related terms "
            f"that the answer might be about. Include both the category (hypernym) and "
            f"possible specific instances (hyponyms).\n\n"
            f"Question: {question}\n\n"
            f"Return a comma-separated list of terms (no explanation):"
        )
    else:
        return question
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 100,
        "thinking": {"type": "disabled"},
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8", errors="replace"))
        content = body["choices"][0]["message"].get("content", "").strip()
        if not content:
            content = body["choices"][0]["message"].get("reasoning_content", "").strip()
        return content or ""
    except Exception:
        return ""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rank-position A/B for query expansion.")
    parser.add_argument("--classification-report", type=Path,
                        default=repo_root() / "crates/eval/reports/dmr-no-rank-failure-classification.json")
    parser.add_argument("--synth-report", type=Path,
                        default=repo_root() / "crates/eval/reports/official-dmr-500-deepseek-synthesize.json")
    parser.add_argument("--output", type=Path,
                        default=repo_root() / "crates/eval/reports/rank-position-ab.json")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--dmr-answer-match", default="significant_token_containment")
    parser.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", "https://huggingface.co"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--fastembed-cache-dir", type=Path, default=default_fastembed_cache_dir())
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    os.environ["HF_ENDPOINT"] = args.endpoint
    os.environ["FASTEMBED_CACHE_DIR"] = str(args.fastembed_cache_dir)
    os.environ["HF_HUB_OFFLINE"] = "1"

    # Load classification
    cls_report = json.loads(args.classification_report.read_text(encoding="utf-8"))
    cls_by_id = {c["sample_id"]: c["classification"]["category"] for c in cls_report["classifications"]}

    # Load synth report for no-rank IDs
    synth = json.loads(args.synth_report.read_text(encoding="utf-8"))
    no_rank_ids = {
        item["sample_id"] for item in synth["answer_generation"]["per_query"]
        if item["first_relevant_rank"] is None
    }

    # Load DMR dataset
    dmr_cache = args.cache_root / "dmr-msc-self-instruct"
    dmr_path = download_dataset(DMR_REPO, DMR_FILE, args.endpoint, dmr_cache)
    rows = read_jsonl(dmr_path)
    memories, queries, examples, skipped = build_official_dmr_dataset(
        rows, 500, args.dmr_answer_match
    )
    memory_by_key = {m["key"]: m["content"] for m in memories}

    print(f"Total memories: {len(memories)}")
    print(f"No-rank samples: {len(no_rank_ids)}")

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

    session = ort.InferenceSession(
        str(model_onnx),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_padding(length=256)
    tokenizer.enable_truncation(max_length=256)
    print(f"Providers: {session.get_providers()}")

    def embed_batch(texts, batch_size=32):
        all_vecs = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            encoded = [tokenizer.encode(t) for t in batch]
            input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            outputs = session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})
            hidden = outputs[0]
            mask_expanded = np.expand_dims(attention_mask, -1).astype(hidden.dtype)
            summed = np.sum(hidden * mask_expanded, axis=1)
            counts = np.clip(np.sum(attention_mask, axis=1, keepdims=True), 1, None).astype(hidden.dtype)
            emb = summed / counts
            norms = np.linalg.norm(emb, axis=1, keepdims=True)
            norms = np.clip(norms, 1e-12, None)
            emb = emb / norms
            all_vecs.append(emb)
        return np.vstack(all_vecs)

    # Step 1: Embed all memory chunks (truncate to 512 chars for embedding)
    print("Embedding all memory chunks...")
    chunk_texts = [m["content"][:512] for m in memories]
    chunk_keys = [m["key"] for m in memories]
    chunk_embeddings = embed_batch(chunk_texts, batch_size=32)
    print(f"Chunk embeddings shape: {chunk_embeddings.shape}")

    # Step 2: For each no-rank sample, embed 3 variants and compute ranks
    results = []
    started = time.perf_counter()

    for idx, (query, example) in enumerate(zip(queries, examples)):
        if example["sample_id"] not in no_rank_ids:
            continue
        if args.limit and len(results) >= args.limit:
            break

        sid = example["sample_id"]
        category = cls_by_id.get(sid, "unknown")
        question = query["query"]
        relevant_keys = set(query["relevant"])

        # Generate variants
        hyde_text = generate_variant(base_url=args.base_url, model=args.model, question=question, variant_type="hyde")
        cat_text = generate_variant(base_url=args.base_url, model=args.model, question=question, variant_type="category_expansion")

        # Embed variants
        variant_texts = [question, hyde_text, cat_text]
        variant_embs = embed_batch(variant_texts, batch_size=3)

        # Compute cosine similarity to all chunks
        # chunk_embeddings: [N, 768], variant_embs: [3, 768]
        sims = chunk_embeddings @ variant_embs.T  # [N, 3]

        # For each variant, find the rank of the best relevant chunk
        ranks = []
        for v in range(3):
            col = sims[:, v]
            # Sort descending, find rank of first relevant chunk
            sorted_indices = np.argsort(-col)
            rank = None
            for r, chunk_idx in enumerate(sorted_indices, start=1):
                if chunk_keys[chunk_idx] in relevant_keys:
                    rank = r
                    break
            ranks.append(rank)

        orig_rank, hyde_rank, cat_rank = ranks

        result = {
            "sample_id": sid,
            "category": category,
            "orig_rank": orig_rank,
            "hyde_rank": hyde_rank,
            "cat_rank": cat_rank,
            "hyde_rank_improved": (hyde_rank or 9999) < (orig_rank or 9999),
            "cat_rank_improved": (cat_rank or 9999) < (orig_rank or 9999),
            "hyde_rank_delta": (orig_rank or 9999) - (hyde_rank or 9999) if hyde_rank else None,
            "cat_rank_delta": (orig_rank or 9999) - (cat_rank or 9999) if cat_rank else None,
        }
        results.append(result)

        if (len(results) % 20) == 0:
            elapsed = time.perf_counter() - started
            print(f"  processed {len(results)}/{len(no_rank_ids)} ({elapsed:.0f}s)")

    elapsed_ms = (time.perf_counter() - started) * 1000

    # Aggregate
    def rank_stats(ranks_list):
        valid = [r for r in ranks_list if r is not None]
        return {
            "n_found": len(valid),
            "n_total": len(ranks_list),
            "found_rate": round(len(valid) / len(ranks_list), 4) if ranks_list else 0,
            "rank_mean": round(sum(valid) / len(valid), 1) if valid else None,
            "rank_median": int(np.median(valid)) if valid else None,
            "rank_le_10": sum(1 for r in valid if r <= 10),
            "rank_le_50": sum(1 for r in valid if r <= 50),
            "rank_le_100": sum(1 for r in valid if r <= 100),
            "rank_gt_100": sum(1 for r in valid if r > 100),
        }

    by_category = {}
    for cat in ("semantic_gap", "terminology_mismatch", "chunk_boundary"):
        sub = [r for r in results if r["category"] == cat]
        by_category[cat] = {
            "n": len(sub),
            "orig": rank_stats([r["orig_rank"] for r in sub]),
            "hyde": rank_stats([r["hyde_rank"] for r in sub]),
            "cat": rank_stats([r["cat_rank"] for r in sub]),
            "hyde_improved_count": sum(1 for r in sub if r["hyde_rank_improved"]),
            "cat_improved_count": sum(1 for r in sub if r["cat_rank_improved"]),
            "hyde_improved_rate": round(sum(1 for r in sub if r["hyde_rank_improved"]) / len(sub), 4) if sub else 0,
            "cat_improved_rate": round(sum(1 for r in sub if r["cat_rank_improved"]) / len(sub), 4) if sub else 0,
        }

    overall = {
        "n": len(results),
        "orig": rank_stats([r["orig_rank"] for r in results]),
        "hyde": rank_stats([r["hyde_rank"] for r in results]),
        "cat": rank_stats([r["cat_rank"] for r in results]),
        "hyde_improved_count": sum(1 for r in results if r["hyde_rank_improved"]),
        "cat_improved_count": sum(1 for r in results if r["cat_rank_improved"]),
        "hyde_improved_rate": round(sum(1 for r in results if r["hyde_rank_improved"]) / len(results), 4) if results else 0,
        "cat_improved_rate": round(sum(1 for r in results if r["cat_rank_improved"]) / len(results), 4) if results else 0,
    }

    output = {
        "schema_version": "king-synapse.rank-position-ab.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/eval/rank_position_ab.py",
        "model": args.model,
        "embedding_model": "intfloat/multilingual-e5-base (same as system, via onnxruntime)",
        "total_chunks": len(memories),
        "total_samples": len(results),
        "elapsed_ms": round(elapsed_ms),
        "overall": overall,
        "by_category": by_category,
        "raw_questions_committed": False,
        "raw_answers_committed": False,
        "raw_dialogs_committed": False,
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. {len(results)} samples in {elapsed_ms:.0f}ms")
    print(f"\nOverall:")
    o = overall
    print(f"  orig: found={o['orig']['n_found']}/{o['n']} median_rank={o['orig']['rank_median']} le_10={o['orig']['rank_le_10']} le_50={o['orig']['rank_le_50']} le_100={o['orig']['rank_le_100']}")
    print(f"  hyde: found={o['hyde']['n_found']}/{o['n']} median_rank={o['hyde']['rank_median']} le_10={o['hyde']['rank_le_10']} le_50={o['hyde']['rank_le_50']} le_100={o['hyde']['rank_le_100']} improved={o['hyde_improved_count']}/{o['n']} ({o['hyde_improved_rate']})")
    print(f"  cat:  found={o['cat']['n_found']}/{o['n']} median_rank={o['cat']['rank_median']} le_10={o['cat']['rank_le_10']} le_50={o['cat']['rank_le_50']} le_100={o['cat']['rank_le_100']} improved={o['cat_improved_count']}/{o['n']} ({o['cat_improved_rate']})")
    print(f"\nBy category:")
    for cat, a in by_category.items():
        print(f"  {cat} (n={a['n']}):")
        print(f"    orig: median={a['orig']['rank_median']} le_10={a['orig']['rank_le_10']} le_50={a['orig']['rank_le_50']}")
        print(f"    hyde: median={a['hyde']['rank_median']} le_10={a['hyde']['rank_le_10']} improved={a['hyde_improved_count']}/{a['n']} ({a['hyde_improved_rate']})")
        print(f"    cat:  median={a['cat']['rank_median']} le_10={a['cat']['rank_le_10']} improved={a['cat_improved_count']}/{a['n']} ({a['cat_improved_rate']})")
    print(f"\nOutput: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
