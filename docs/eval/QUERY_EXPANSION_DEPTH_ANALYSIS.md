# Query Expansion Depth Analysis: Improvement Distribution and Overlap

Date: 2026-07-05
Follow-up to: RANK_POSITION_AB.md
Dataset: 174 DMR no-rank samples

## Purpose

A reviewer pointed out that "60.3% improved" is a binary metric that hides
the distribution of improvement magnitude. This analysis breaks down:
1. Where do "improved" samples actually end up?
2. How much overlap exists between category expansion and reranker pool
   expansion?
3. What is the net top-10 change (accounting for samples kicked out)?

## 1. Improvement distribution for category expansion

Of 174 no-rank samples, 105 improved rank under category expansion:

| Where they ended up | Count | Share of "improved" | Actually useful? |
| --- | ---: | ---: | --- |
| Entered top-10 | 16 | 15.2% | Yes |
| Entered rank 11-50 | 19 | 18.1% | Reranker reachable |
| Entered rank 51-100 | 16 | 15.2% | Pool=100 reachable |
| Still at rank >100 | 54 | 51.4% | No |

**51.4% of "improvements" are cosmetic** — the rank moved from e.g. 300 to
250, which has no practical effect. Only 48.6% of improvements (51 samples)
brought the relevant chunk into a usable range (top-100).

### Net top-10 movement

| Movement | Count |
| --- | ---: |
| Entered top-10 (were outside, now inside) | 11 |
| Left top-10 (were inside, now outside) | 8 |
| Stayed in top-10 | 6 |
| **Net change** | **+3** |

Category expansion is **not a pure gain**. It helps 11 samples enter top-10
but pushes 8 out. The net top-10 improvement is +3 (14 to 17).

## 2. Overlap between category expansion and pool expansion

| Method | Samples reaching top-100 (from outside top-10) |
| --- | ---: |
| Pool expansion alone (orig rank 11-100) | 54 |
| Category expansion alone (cat rank ≤ 100, orig > 10) | 58 |
| Both methods cover the same sample | **35** |
| Category expansion only (orig > 100, cat ≤ 100) | 23 |
| Pool expansion only (orig 11-100, cat > 100) | 19 |
| **Combined unique** | **77** |

The two methods have 35 overlapping samples. Combined, they recover 77
unique samples into top-100 (vs 54 or 58 alone), but this is NOT 54+58=112.

### Combined top-10

| Metric | Count |
| --- | ---: |
| Original query top-10 | 14 |
| Category expansion top-10 | 17 |
| **Combined (either method in top-10)** | **25** |

Combined, 25 of 174 samples (14.4%) would have the relevant chunk in top-10,
up from 14 (8.0%). This is a meaningful improvement but still leaves 149
samples (85.6%) without top-10 retrieval.

## 3. The 106 samples at rank > 100 (the hard core)

106 samples have the relevant chunk at rank > 100 under the original query.
Category expansion brings 23 of these into top-100, leaving 83 still
unreachable.

These 83 samples represent the true embedding model limitation: the
embedding space does not connect the query to the relevant chunk at all.
No amount of query expansion or pool expansion will help these — they
require a fundamentally better embedding model or index-time augmentation.

## 4. Honest assessment of "category expansion is worth implementing"

### The case FOR

- Net top-10 gain of +3 (14 to 17) and combined with pool expansion, +11
  (14 to 25)
- 60.3% of samples see some rank improvement
- Low cost: one LLM call per query
- Helps across all failure types uniformly

### The case AGAINST

- 51.4% of "improvements" are cosmetic (still > rank 100)
- 8 samples are kicked OUT of top-10 (net is +3, not +11)
- 83 samples (47.7%) remain completely unreachable
- The +3 net top-10 gain on 174 samples is a 1.7% absolute improvement
- Has not been validated end-to-end (generator + judge)

### Verdict

Category expansion provides a **modest but real** retrieval improvement.
It should be validated end-to-end before being committed to the main
pipeline. The improvement is not large enough to be the sole solution —
it needs to be combined with pool expansion and potentially a better
embedding model for the hard-core 83 samples.

## 5. Open questions (require further experiments)

1. **End-to-end validation**: Does the +3 net top-10 improvement translate
   to measurable judge accuracy improvement when run through the full
   pipeline (retrieval → generation → judge)?

2. **Trigger logic**: If implemented in production, should expansion fire
   on every query (cost: 1 extra LLM call per query) or only when the
   top-1 similarity is below a threshold?

3. **Embedding model upgrade**: Would bge-large or another model reduce
   the 83 hard-core samples that no query expansion can reach?

4. **Index-time augmentation**: Would adding semantic labels to chunks at
   storage time help the 83 unreachable samples without the per-query
   cost of expansion?

## Reproducibility

- Source data: `crates/eval/reports/rank-position-ab.json`
- Analysis: this document
- No new experiments were run; this is a re-analysis of existing data
- No raw questions, answers, dialogs, or API keys committed
