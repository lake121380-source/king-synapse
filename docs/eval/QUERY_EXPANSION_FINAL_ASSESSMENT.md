# Query Expansion Final Assessment: Net Value in Global Context

Date: 2026-07-05
Follow-up to: QUERY_EXPANSION_DEPTH_ANALYSIS.md, RANK_POSITION_AB.md

## Purpose

Answer the reviewer's four final questions before deciding whether to
implement category expansion in the main pipeline:

1. What is the global value of net +3 top-10?
2. Can a routing threshold separate "should expand" from "should not"?
3. Is the 83-sample hard core addressable by a larger embedding model?
4. What end-to-end validation is needed?

## 1. Global value of net +3

The 174 no-rank samples are a subset of the 433 scored DMR samples. The
net +3 top-10 improvement (always-expand strategy) translates to:

- Best case: +3 samples correctly answered = +3/433 = +0.7% judge accuracy
- Realistic case: less than +3, because entering top-10 does not guarantee
  the generator answers correctly (rank-1 judge accuracy is only 30.1%)

At rank 2-10, judge accuracy with LLM synthesis is approximately 15-26%
(based on the A/B data: rank 2-5 = 26.0%, rank 6-10 = 3.0%). Weighted
estimate: of the 3 net new top-10 samples, roughly 0.5-1 would be answered
correctly. This is a +0.1-0.2% absolute judge accuracy improvement.

**Verdict: The global value of always-expand is negligible (+0.1-0.2%
judge accuracy). The per-query LLM call cost is not justified by this gain.**

### Threshold routing changes the picture

With orig_rank-based routing (only expand if relevant chunk is NOT in
top-10), the net top-10 becomes +11 (25 vs 14, 0 kickouts). But in
production, orig_rank is unknown — you don't know which chunk is relevant.

The top-1 similarity was tested as a routing signal:

| Group | top1_sim range | mean |
| --- | --- | ---: |
| Entered (expansion helped) | 0.823 - 0.866 | 0.845 |
| Left (expansion hurt) | 0.836 - 0.865 | 0.849 |
| Stayed (neutral) | 0.829 - 0.850 | 0.837 |

**The groups completely overlap. top1_sim cannot separate them.** No
threshold achieves "gain without kickout."

### Threshold simulation

| Threshold | Expand count | Top-10 | Gained | Kicked |
| --- | ---: | ---: | ---: | ---: |
| 0.82 | 0 | 14 | 0 | 8* |
| 0.83 | 12 | 16 | 2 | 8* |
| 0.84 | 77 | 15 | 3 | 6 |
| 0.85 | 133 | 16 | 7 | 3 |
| 0.86 | 165 | 18 | 10 | 2 |

*The "kicked" count at low thresholds includes samples that would have
been kicked if expanded — but at thresh=0.82, no samples are expanded, so
the 8 "kicked" are actually just the baseline (they were already in top-10
under original query, the count is misleading here). The real signal is
that no threshold cleanly separates gain from loss.

## 2. Routing conclusion

There is no simple pre-retrieval signal (top1_sim, query length, etc.)
that can determine when to trigger expansion. The only clean separator is
orig_rank (post-retrieval), which is not available in production.

Options for production routing:
- **Always expand**: cost = 1 extra LLM call per query, gain = +0.1-0.2%
  judge accuracy. Not worth it.
- **Never expand**: baseline. Current state.
- **Expand only when top-1 similarity is low**: does not work, groups overlap.
- **Two-pass retrieval**: run original retrieval, if top-1 is below some
  confidence threshold, run expansion and re-retrieve. Cost = 2x retrieval
  for low-confidence queries. Needs a better confidence signal than top1_sim.

**Verdict: No viable routing strategy exists with the current signals.
Category expansion should NOT be implemented in the main pipeline.**

## 3. The 83 hard-core samples

83 samples have the relevant chunk at rank > 100 under both original and
expanded queries. These represent the true embedding model limitation.

### Can a larger model help?

This is untested. The reviewer correctly notes that hypernym relationships
("pet" vs "cow") are a known weakness of many embedding models regardless
of size. A larger model of the same architecture (e5-large) may not solve
this. A different architecture (e.g., instruction-tuned embedding model)
might.

### Recommendation

Before committing to a full re-embedding with a larger model, run a small-
scale test on these 83 samples: embed query + relevant chunk + 5 random
distractor chunks with bge-large-en-v1.5, and check if the relevant chunk's
rank improves. If it does, then full re-embedding is justified. If not,
the problem is architectural and needs a different approach (e.g., 
instruction-tuned embeddings, or knowledge-graph-augmented retrieval).

## 4. End-to-end validation

Given the findings above, end-to-end validation of category expansion is
**not recommended**. The expected gain (+0.1-0.2% judge accuracy) is too
small to justify the experiment cost.

Instead, the next end-to-end experiment should test the **embedding model
upgrade** hypothesis on the 83 hard-core samples, if the small-scale test
in section 3 is positive.

## Final conclusion

**Category expansion is NOT worth implementing in the main pipeline.**

The evidence chain:
1. Net top-10 gain is +3 (always-expand) or +11 (rank-routed, but routing
   is not possible in production)
2. No viable routing signal exists (top1_sim overlaps completely)
3. Global judge accuracy impact is +0.1-0.2% (negligible)
4. Per-query LLM call cost is not justified
5. 83 samples (47.7% of no-rank) are completely unreachable by any query
   expansion strategy

The real bottleneck remains the embedding model's semantic representation
quality. The next experiment should be a small-scale embedding model
comparison on the 83 hard-core samples, not query expansion implementation.

## What was learned

This series of experiments (failure classification → query expansion A/B →
rank-position A/B → depth analysis → routing analysis) produced several
valuable findings despite the negative final conclusion:

1. **96% of retrieval failures are semantic**, not architectural
2. **Cosine similarity is a misleading proxy for ranking** — always measure
   actual rank position
3. **Binary "improved" metrics hide magnitude** — 51% of improvements were
   cosmetic
4. **"Always expand" has hidden costs** — 8 samples kicked out of top-10
5. **No routing signal exists** — top1_sim cannot separate winners from
   losers
6. **The hard core is 83 samples** at rank >100, addressable only by
   better embeddings, not query transformation

These findings save future work from pursuing query expansion further, and
correctly redirect attention to embedding model quality.

## Reproducibility

- Routing analysis: `crates/eval/reports/top1-sim-routing-analysis.json`
- Source data: `crates/eval/reports/rank-position-ab.json`
- No new experiments beyond embedding 2165 chunks for top1_sim extraction
- No raw questions, answers, dialogs, or API keys committed
