# DMR No-Rank Failure Mode Classification

Date: 2026-07-05
Dataset: MemGPT/MSC-Self-Instruct (cached locally)
Classifier: deepseek-v4-flash, temperature=0, thinking disabled
Source: 174 samples from DMR 500 where gold-answer chunk was not in top-10
retrieval results (first_relevant_rank is null)

## Purpose

Classify the 174 retrieval failures to determine which recall optimization
strategy is most appropriate. Avoid guessing the cause before measuring.

## Method

For each of the 174 no-rank samples, the DeepSeek LLM was given the question,
gold answer, and the relevant chunk content (the chunk that contains the
answer but was not retrieved). The LLM classified the failure into one of:

- **semantic_gap**: Question and relevant chunk share little lexical or
  semantic overlap. The embedding model cannot connect them.
- **terminology_mismatch**: Question uses different vocabulary than the chunk
  for the same concept (e.g., "pet" vs "cow", "job" vs "custodian").
- **chunk_boundary**: Answer is split across two chunks due to dialog
  segmentation.
- **multi_hop**: Answer requires combining information from multiple chunks.
- **other**: Does not fit above categories.

No raw questions, answers, or chunk content was committed. Only category
counts and sanitized metadata are persisted.

## Results

| Failure type | Count | Share |
| --- | ---: | ---: |
| semantic_gap | 127 | 73.0% |
| terminology_mismatch | 40 | 23.0% |
| chunk_boundary | 7 | 4.0% |
| multi_hop | 0 | 0.0% |
| **Total** | **174** | **100%** |

### Characteristics by failure type

| Type | n | Gold answer length (mean) | Relevant chunk length (mean) | Sessions (mean) |
| --- | ---: | ---: | ---: | ---: |
| semantic_gap | 127 | 20.1 | 4067 | 5.0 |
| terminology_mismatch | 40 | 18.7 | 3895 | 5.0 |
| chunk_boundary | 7 | 25.3 | 3756 | 5.0 |

Gold answer length and chunk length do not differ significantly across
failure types. The distinguishing factor is semantic, not structural.

## Analysis

### 73% of failures are semantic gap

The dominant failure mode is that the question and the relevant memory chunk
use entirely different phrasing for the same topic. The current embedding
model (multilingual-e5-base) cannot bridge this gap because it relies on
lexical and shallow semantic similarity.

Example pattern (paraphrased, not raw data):
- Question asks "What do I do for work?"
- Memory chunk says "I've been a custodian for 10 years. It pays the bills"
- No shared significant tokens between question and chunk

### 23% are terminology mismatch

The question and chunk refer to the same concept with different vocabulary.
This is a subset of semantic gap but more specific: the concepts are related,
but the surface forms diverge.

Example pattern:
- Question asks "What pet do I have?"
- Memory chunk says "My cow keeps me company"
- "pet" and "cow" are semantically related but lexically disjoint

### 4% are chunk boundary issues

A small number of failures are caused by the answer being split across two
chunks. This is a structural issue addressable by chunk size/overlap tuning.

### 0% multi-hop

No failures were classified as multi-hop. This is expected for DMR: the
dataset is designed so that the answer exists in a single chunk, not
requiring cross-chunk reasoning.

## Conclusions

### The bottleneck is embedding-level semantic matching, not retrieval architecture

96% of no-rank failures (semantic_gap + terminology_mismatch) are caused by
the embedding model's inability to match questions to memory chunks that use
different phrasing. This is not a retrieval algorithm problem (RRF, reranker
pool, etc.) — it is a representation quality problem.

### Recommended next steps (ranked by expected impact)

1. **Query expansion** (addresses semantic_gap + terminology_mismatch):
   Use an LLM to expand the query with synonyms, paraphrases, and related
   concepts before retrieval. Expected to help with 167/174 failures (96%).

2. **HyDE (Hypothetical Document Embeddings)** (addresses semantic_gap):
   Generate a hypothetical answer to the question, embed it, and use it
   as an additional retrieval vector. Expected to help with 127/174 (73%).

3. **Better embedding model** (addresses all types):
   The current multilingual-e5-base may be too small. A larger model
   (e.g., bge-large-en-v1.5) could improve semantic matching.

4. **Chunk overlap tuning** (addresses chunk_boundary only):
   Would fix at most 7/174 (4%) failures. Low priority.

### What NOT to do

- **Multi-hop retrieval / query decomposition**: 0% of failures are multi-hop.
  This would add complexity without addressing the actual bottleneck.
- **Reranker pool expansion**: The reranker can only rerank what retrieval
  returns. If the relevant chunk is not in the candidate set, a larger pool
  does not help.

## Reproducibility

- Classifier: deepseek-v4-flash, temperature=0, thinking disabled
- Source report: `official-dmr-500-deepseek-synthesize.json`
- Classification script: `scripts/eval/dmr_no_rank_failure_classification.py`
- Output: `crates/eval/reports/dmr-no-rank-failure-classification.json`
- No raw questions, answers, dialogs, or API keys committed
