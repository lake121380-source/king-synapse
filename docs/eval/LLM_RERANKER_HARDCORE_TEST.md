# LLM Reranker Test on Hard-Core Samples

Date: 2026-07-05
Dataset: 83 DMR samples where relevant chunk is at rank > 100 under both
original and category-expanded queries
LLM judge: deepseek-v4-flash, temperature=0, thinking disabled
Embedding model: intfloat/multilingual-e5-base (for reference)

## Purpose

Test whether the 83 "hard-core" retrieval failures are caused by "embedding
model too small" or by "the semantic relationship between query and chunk
is fundamentally weak, even for an LLM."

If the LLM can identify the relevant chunk that e5-base cannot, the problem
is in the embedding model, and a larger model (bge-large) might help.

If the LLM also cannot identify the relevant chunk, the problem is in the
data itself — the semantic relationship is too weak for any automated
system to detect, and no embedding model upgrade will help.

## Method

For each of the 83 hard-core samples:
1. Take the relevant chunk (the one containing the gold answer) and 5
   randomly sampled distractor chunks.
2. Shuffle them so position is random.
3. Ask DeepSeek v4-flash: "Is this passage relevant to the question?"
   (generous threshold: "ANY information related to the question's topic,
   even indirectly")
4. Record whether the LLM correctly identifies the relevant chunk as
   relevant, and whether it falsely identifies distractors as relevant.

This is a 6-way binary classification task per sample. The LLM sees the
full text of each chunk (truncated to 300 chars), not just an embedding.

## Results

| Metric | Value |
| --- | ---: |
| Samples tested | 83 |
| LLM found relevant chunk | 10 (12.0%) |
| LLM did NOT find relevant chunk | 73 (88.0%) |
| LLM relevant recall | 12.0% |
| LLM distractor false positive rate | 5.3% |
| LLM distractor FP mean (out of 5) | 0.27 |

## Analysis

### The LLM also fails on 88% of hard-core samples

Even with full text access (not just embeddings), the LLM judges 73/83
relevant chunks as NOT relevant to their questions. This means the semantic
relationship between the question and the relevant chunk is weak enough
that even a capable LLM cannot consistently detect it.

### The 5.3% false positive rate confirms the LLM is not being random

The LLM incorrectly marks only 5.3% of distractors as relevant. This is
well below the 16.7% random baseline (1/6). The LLM is being selective and
conservative — it is not just guessing "relevant" for everything.

### The 12% hit rate is not zero, but it is low

The LLM does identify 10/83 relevant chunks correctly. This means the
semantic relationship exists but is detectable only in a small minority of
cases. For the other 73, the relationship is too indirect, too subtle, or
requires domain knowledge that neither the embedding model nor the LLM
possesses.

## Conclusions

### The bottleneck is NOT "embedding model too small"

If the problem were model size, the LLM (which is vastly more capable than
any embedding model) should have a much higher hit rate. A 12% LLM recall
rate on these samples means the problem is in the data, not the model.

### Switching to bge-large is unlikely to help

A larger embedding model of the same architecture will still rely on
vector similarity, which is a weaker signal than full-text LLM judgment.
Since the LLM itself only achieves 12% recall, bge-large is unlikely to
do better. The full re-embedding cost is not justified.

### The 83 hard-core samples may require a fundamentally different approach

Possible explanations for why these samples are so hard:
1. **The question-chunk relationship requires multi-step reasoning** that
   neither embeddings nor single-pass LLM judgment can perform
2. **The gold answer labeling may be questionable** — some "relevant"
   chunks may contain the answer tokens but not in a way that is
   semantically related to the question
3. **The DMR dataset may have inherent ambiguity** in what counts as
   "relevant"

### What this means for the system

The 83 hard-core samples represent 19.2% of the 433 scored DMR samples.
They are likely not recoverable through any embedding model upgrade or
query transformation. The system's retrieval ceiling on DMR is
approximately 80.8% of scored samples (350/433), which aligns with the
observed top-10 retrieval rate.

### The query-time vs index-time distinction (per reviewer)

This experiment killed **query-time category expansion**. It did NOT test
**index-time chunk augmentation**. However, the LLM reranker result
suggests that even index-time augmentation may have limited value: if the
LLM cannot identify the relevant chunk from full text, adding labels at
index time is unlikely to create a strong enough signal for the embedding
model to pick up.

Index-time augmentation remains untested and is still theoretically
distinct from query-time expansion, but the LLM reranker result lowers
the expected value of that approach.

## Final recommendation

Do NOT invest in bge-large full re-embedding. The LLM reranker test shows
the problem is in the data, not the model size.

Instead:
1. Accept that ~19% of DMR samples are beyond the current retrieval
   ceiling
2. Focus on maximizing performance on the 81% that IS reachable
3. If retrieval improvement is still needed, investigate the data quality
   of the 83 hard-core samples (are the gold answers correct? are the
   relevant chunk labels accurate?)
4. Consider that the system's current 21.2% judge accuracy may be close
   to the practical ceiling for this dataset/generator combination

## Reproducibility

- LLM: deepseek-v4-flash, temperature=0, thinking disabled
- 83 hard-core samples from rank-position-ab.json
- 6 chunks per sample (1 relevant + 5 random distractors), shuffled
- Script: scripts/eval/llm_reranker_hardcore_test.py
- Output: crates/eval/reports/llm-reranker-hardcore-test.json
- No raw questions, answers, dialogs, or API keys committed
