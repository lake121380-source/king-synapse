"""Phase 1b-4: Edge Precision Audit v2.

Four-category classification + counterfactual utility test.

Categories:
  1. True Cognitive Edge — genuine knowledge relation
  2. Contextual Association — not knowledge, but helpful
  3. Retrieval Artifact — frequency bias, no real relation
  4. Dangerous Edge — looks plausible but semantically wrong

Also tests: does an edge improve correct memory ranking?
"""
import json, os, sys, random, hashlib
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent))
os.environ["HF_HUB_OFFLINE"] = "1"

from longmem_dmr_smoke import (
    DMR_FILE, DMR_REPO, default_cache_root, download_dataset, read_jsonl,
)
from official_dmr_eval import build_official_dmr_dataset

# Load DMR data
cache = default_cache_root()
dmr_path = download_dataset(DMR_REPO, DMR_FILE, "https://huggingface.co", cache / "dmr-msc-self-instruct")
rows = read_jsonl(dmr_path)
memories, queries, examples, skipped = build_official_dmr_dataset(rows, 50, "significant_token_containment")
mem_by_key = {m["key"]: m["content"] for m in memories}

# Load ecology+activation report (with fixes applied)
tmpdir = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "phase1b1-y8bx9rqg"
r_eco = json.loads((tmpdir / "ecology-activation.json").read_text())
r_base = json.loads((tmpdir / "ecology.json").read_text())  # no activation, has edges but no booster

# Also load baseline (no edges at all)
r_static = json.loads((tmpdir / "baseline.json").read_text())

print("=== Phase 1b-4: Edge Precision Audit v2 ===\n")

# === 1. Extract all co-retrieval pairs with their topic contexts ===
# Build pair -> list of (query_idx, topic) from ecology run
pair_contexts = defaultdict(list)  # (keyA, keyB) -> [(qi, query_preview, topic_tag)]

for qi, q in enumerate(r_eco.get("per_query", [])):
    keys = [h.get("key", "") for h in q.get("returned_hit_diagnostics", [])]
    query_text = q["query"]
    # Extract topic from query
    topic = "unknown"
    lower = query_text.lower()
    for prefix in ["we talked about ", "we discussed ", "we chatted about ", "about your ", "about my ", "about the "]:
        if prefix in lower:
            pos = lower.find(prefix) + len(prefix)
            after = query_text[pos:]
            end = after.find("?")
            if end > 0:
                topic = after[:end].strip()[:30]
            break
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            pair = tuple(sorted([keys[i], keys[j]]))
            pair_contexts[pair].append((qi, query_text[:80], topic))

# === 2. Classify edges ===
# Heuristic classification based on:
# - Content similarity (shared topic words)
# - Co-retrieval frequency (high = possible artifact)
# - Content type (greeting/opening = artifact)

def classify_edge(content_a, content_b, co_retrieval_count, total_queries):
    """Heuristic 4-category classification."""
    a_lower = content_a.lower()[:200]
    b_lower = content_b.lower()[:200]

    # Check if both are conversation openings/greetings
    greeting_markers = ["hey how are you", "hey! how are you", "hi. good", "hello, how are you", "hi there"]
    a_is_greeting = any(g in a_lower for g in greeting_markers)
    b_is_greeting = any(g in b_lower for g in greeting_markers)

    if a_is_greeting and b_is_greeting:
        return "retrieval_artifact", "Both are conversation openings"

    # Check if one is greeting and other is content
    if a_is_greeting or b_is_greeting:
        # Greeting + content = weak association from query structure
        freq_pct = co_retrieval_count / total_queries
        if freq_pct > 0.6:
            return "retrieval_artifact", "Greeting + content, high frequency bias"
        else:
            return "contextual_association", "Greeting + content, moderate frequency"

    # Check semantic overlap (shared significant words, excluding stopwords)
    stopwords = {"the", "a", "an", "i", "you", "we", "and", "to", "of", "in", "is", "it", "was", "my", "your", "that", "this", "for", "on", "have", "do", "so", "but", "they", "he", "she", "im", "its"}
    words_a = set(w.lower().strip(".,!?;:\"'()[]") for w in content_a.split()) - stopwords
    words_b = set(w.lower().strip(".,!?;:\"'()[]") for w in content_b.split()) - stopwords
    words_a = {w for w in words_a if len(w) > 2}
    words_b = {w for w in words_b if len(w) > 2}
    overlap = words_a & words_b
    overlap_ratio = len(overlap) / max(1, min(len(words_a), len(words_b)))

    if overlap_ratio > 0.3:
        return "true_cognitive", f"Shared topic words: {', '.join(list(overlap)[:5])}"
    elif overlap_ratio > 0.1:
        return "contextual_association", f"Some overlap: {', '.join(list(overlap)[:3])}"
    else:
        # No overlap but co-retrieved - could be dangerous or just weak
        freq_pct = co_retrieval_count / total_queries
        if freq_pct > 0.4:
            return "retrieval_artifact", "No semantic overlap, high frequency"
        else:
            return "dangerous_edge", "No semantic overlap despite co-retrieval"

# === 3. Run classification on all pairs ===
total_queries = len(r_eco.get("per_query", []))
classifications = []
for pair, contexts in pair_contexts.items():
    ka, kb = pair
    ca = mem_by_key.get(ka, "[unknown]")
    cb = mem_by_key.get(kb, "[unknown]")
    count = len(contexts)
    category, reason = classify_edge(ca, cb, count, total_queries)
    classifications.append({
        "key_a": ka,
        "key_b": kb,
        "content_a": ca[:150],
        "content_b": cb[:150],
        "co_retrieval_count": count,
        "frequency_pct": round(count / total_queries * 100, 1),
        "topics": list(set(c[2] for c in contexts))[:5],
        "category": category,
        "reason": reason,
    })

# Sort by co-retrieval count descending
classifications.sort(key=lambda x: x["co_retrieval_count"], reverse=True)

# === 4. Summary ===
cat_counts = Counter(c["category"] for c in classifications)
total = len(classifications)

print(f"Total co-retrieval pairs: {total}")
print(f"\n--- Four-Category Classification ---\n")
for cat in ["true_cognitive", "contextual_association", "retrieval_artifact", "dangerous_edge"]:
    count = cat_counts.get(cat, 0)
    pct = count / total * 100 if total > 0 else 0
    print(f"  {cat:<28} {count:>4} ({pct:>5.1f}%)")

# Precision = (true_cognitive + contextual) / total
meaningful = cat_counts.get("true_cognitive", 0) + cat_counts.get("contextual_association", 0)
precision = meaningful / total * 100 if total > 0 else 0
print(f"\n  Precision (cognitive + contextual): {precision:.1f}%")
print(f"  Target: >70%")

# === 5. Topic distribution ===
print(f"\n--- Topic Distribution ---\n")
topic_counter = Counter()
for c in classifications:
    for t in c["topics"]:
        topic_counter[t] += 1
for topic, count in topic_counter.most_common(10):
    print(f"  {topic[:40]:<42} {count:>4}")

# === 6. Counterfactual Utility ===
# Compare ranking with activation (ecology+activation) vs without (ecology, no activation)
print(f"\n--- Counterfactual Utility ---\n")
print("Comparing: ecology (no activation) vs ecology+activation")
print("Does activation from graduated edges change correct memory ranking?\n")

# For each query, find the correct memory (from relevant field)
# and check if its rank changed between ecology and ecology+activation
rank_changes = []
improved = 0
worsened = 0
unchanged = 0

for qi in range(len(r_eco.get("per_query", []))):
    q_eco = r_eco["per_query"][qi]
    q_act = r_eco["per_query"][qi]  # Same run has activation bonuses
    q_noact = r_base["per_query"][qi] if qi < len(r_base.get("per_query", [])) else None

    if not q_noact:
        continue

    relevant = set(q_eco.get("relevant", []))

    # Find rank of first relevant memory in each run
    def first_relevant_rank(per_q):
        for i, h in enumerate(per_q.get("returned_hit_diagnostics", [])):
            if h.get("key", "") in relevant:
                return i + 1
        return None

    rank_noact = first_relevant_rank(q_noact)
    rank_act = first_relevant_rank(q_eco)

    if rank_noact is not None and rank_act is not None:
        delta = rank_noact - rank_act  # positive = improvement
        if delta > 0:
            improved += 1
        elif delta < 0:
            worsened += 1
        else:
            unchanged += 1
        if delta != 0:
            rank_changes.append({
                "query_idx": qi,
                "rank_no_activation": rank_noact,
                "rank_with_activation": rank_act,
                "delta": delta,
            })

print(f"Queries where activation improved correct memory rank: {improved}")
print(f"Queries where activation worsened correct memory rank: {worsened}")
print(f"Queries unchanged: {unchanged}")
print(f"Net improvement: {improved - worsened}")

if rank_changes:
    print(f"\nRank changes (non-zero):")
    for rc in rank_changes[:15]:
        direction = "↑" if rc["delta"] > 0 else "↓"
        print(f"  q{rc['query_idx']:02d}: {rc['rank_no_activation']} -> {rc['rank_with_activation']} ({direction}{abs(rc['delta'])})")

# === 7. Save ===
output = {
    "total_pairs": total,
    "classification": dict(cat_counts),
    "precision_pct": round(precision, 1),
    "topic_distribution": dict(topic_counter.most_common(15)),
    "counterfactual_utility": {
        "improved": improved,
        "worsened": worsened,
        "unchanged": unchanged,
        "net_improvement": improved - worsened,
        "rank_changes": rank_changes,
    },
    "top_pairs_sample": classifications[:30],
}
out = Path("crates/eval/reports/phase1b4-audit-v2-50.json")
out.write_text(json.dumps(output, indent=2))
print(f"\nSaved to {out}")
