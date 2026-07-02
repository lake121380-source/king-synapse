# DMR Mapping Audit

Date: 2026-07-02

Status: completed as an anonymized mapping audit. This is not a retrieval
benchmark and does not change the Phase 6 feature freeze.

Machine-readable report:

`crates/eval/reports/dmr-mapping-audit.json`

Runner:

`scripts/eval/dmr_mapping_audit.py`

## Scope

The audit checks why the DMR 50 validation skipped `278` rows before selecting
50 evaluable rows.

It uses the same source and current exact-match selection rule as
`scripts/eval/longmem_dmr_smoke.py`:

```text
casefold + whitespace-normalized full answer substring in generated memory chunks
```

The report excludes raw questions, answers, dialogs, personas, summaries, and
retrieved text.

## Source

| Field | Value |
| --- | --- |
| Dataset | `MemGPT/MSC-Self-Instruct` |
| Revision | `5138f416f8fa76b75b2e080da87e8a8e346e1500` |
| File | `msc_self_instruct.jsonl` |
| SHA-256 | `d3dbea36848b41dc46c0f1548d0ebf74eeaf6390d6f3fe9318e8480dc984495e` |
| Rows audited | 500 |
| Raw cache retained | No |

## Selection Result

| Item | Count |
| --- | ---: |
| Rows with question and answer | 500 |
| Rows with generated memory chunks | 500 |
| Rows accepted by current exact rule | 82 |
| Rows skipped by current exact rule | 418 |
| Rows skipped before first 50 valid rows | 278 |

All audited rows produced five memory chunks. The skip is therefore not caused
by empty chunk generation.

## Accepted Row Source

| Exact-match source | Rows |
| --- | ---: |
| Previous dialog only | 54 |
| Current dialog/summary only | 5 |
| Both previous and current | 23 |

Most currently accepted rows are answer-string matches in previous dialogs.

## Skipped Row Diagnostics

These diagnostic checks are not scored as DMR hits. They only locate why the
current selection rule filters rows.

| Diagnostic | Count |
| --- | ---: |
| Skipped rows recovered by punctuation-insensitive exact match | 241 |
| Skipped rows with all significant answer tokens in one chunk | 362 |
| Skipped rows with any significant answer token in memory | 414 |
| Skipped rows with no significant answer tokens | 2 |

Answer-token bucket among skipped rows:

| Answer token bucket | Rows |
| --- | ---: |
| 1-3 | 200 |
| 4-8 | 164 |
| 9-16 | 49 |
| 17-32 | 5 |

Maximum significant-token overlap among skipped rows:

| Overlap bucket | Rows |
| --- | ---: |
| 0 | 4 |
| 0.25-0.49 | 7 |
| 0.50-0.74 | 18 |
| 0.75-0.99 | 27 |
| 1.00 | 362 |

## Read

The `278` skipped rows in the DMR 50 validation are mainly a mapping/scoring
boundary, not evidence that Synapse failed to store or chunk the source.

Current DMR candidate selection is too strict for many rows because it requires
the complete generated answer string to appear verbatim after only whitespace
and case normalization. The audit shows that many skipped rows still have the
answer tokens or punctuation-normalized answer form in memory.

This means DMR should remain a candidate benchmark until the mapping policy is
pinned against an official harness or a clearly documented answer-matching
policy. It does not justify changing Synapse's memory architecture.

## Next Validation Work

1. Decide whether DMR candidate mapping should use punctuation-normalized exact
   match, significant-token containment, an official DMR label, or an LLM judge.
2. Rebuild the DMR 50 candidate set after that policy is pinned.
3. Re-run DMR 50 on GPU across baseline, vector, and vector + reranker.
4. Keep the current DMR 50 numbers as the strict-string baseline until a new
   mapping policy is documented.
