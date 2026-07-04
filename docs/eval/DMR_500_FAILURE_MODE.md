# DMR 500 Failure Mode Gate

Date: 2026-07-04

Status: validation evidence, not a runtime change

Machine-readable report:

`crates/eval/reports/dmr-500-failure-mode-gate.json`

Runner:

`scripts/eval/dmr_500_failure_mode_gate.py`

## Question

Can all 500 requested DMR rows be classified into mutually exclusive failure
modes from committed sanitized reports, without rerunning retrieval,
generation, judging, or raw benchmark data?

## Inputs

This gate reads only committed sanitized reports:

- `crates/eval/reports/official-dmr-500.json`
- `crates/eval/reports/official-dmr-500-top-context-judge.json`
- `crates/eval/reports/dmr-mapping-policy-review.json`
- `crates/eval/reports/dmr-failure-mode-taxonomy.json`

It does not read or commit raw questions, answers, dialogs, sessions, memory
content, generated answers, prompts, raw judge responses, or API keys.

## Result

The 500 requested DMR rows are classified into 5 mutually exclusive primary
categories plus one non-exclusive diagnostic. The gate passes because the
classification is complete, not because DMR performance is good.

| Primary category | Count | Share of requested | Class |
| --- | ---: | ---: | --- |
| mapping_rejected | 177 | 35.40% | engineering_optimizable |
| retrieval_top10_miss | 109 | 21.80% | engineering_optimizable |
| ranking_not_top1 | 80 | 16.00% | engineering_optimizable |
| answer_synthesis_failure | 83 | 16.60% | engineering_optimizable |
| judge_correct_success | 51 | 10.20% | success |
| **Total** | **500** | **100.00%** | |

Secondary non-exclusive diagnostic:

| Diagnostic | Count | Share of scored | Class |
| --- | ---: | ---: | --- |
| judge_lexical_mismatch | 14 | 4.33% | design_boundary_scoring_policy |

The diagnostic breaks down as `13` substring_false_judge_true (judge accepts
but lexical scoring rejects) plus `1` substring_true_judge_false (lexical
accepts but judge rejects). It overlaps the primary categories and is not part
of the 500-row partition.

## Classification

`mapping_rejected` (177, engineering_optimizable): the answer was not found in
memory chunks under the pinned punctuation full-answer policy. Source is the
baseline `skipped.answer_not_found_in_memory_chunks` count cross-checked
against the mapping policy review `rejected_by_punctuation`.

`retrieval_top10_miss` (109, engineering_optimizable): the judge is incorrect
and `first_relevant_rank` is None. No relevant context reached the top 10, so
the generator cannot recover these rows. The engineering surface is retrieval.

`ranking_not_top1` (80, engineering_optimizable): the judge is incorrect and
`first_relevant_rank >= 2`. A relevant context exists in the top 10 but was not
ranked first. The engineering surface is ranking.

`answer_synthesis_failure` (83, engineering_optimizable): the judge is
incorrect and `first_relevant_rank == 1`. The relevant context was already rank
1, so this is the cleanest answer-generation optimization surface.

`judge_correct_success` (51, success): `llm_judge.correct` is True regardless
of rank or substring.

`judge_lexical_mismatch` (14, design_boundary_scoring_policy): non-exclusive
cases where the lexical substring policy and the LLM judge disagree. This is a
scoring-policy design boundary, not a primary failure mode.

## Conclusion

DMR 500 failure modes are now classified. The primary bottleneck is mapping
policy (177/500), followed by retrieval (109), answer synthesis (83), and
ranking (80). This is not an architecture failure; it is a set of
engineering-optimizable bottlenecks concentrated in mapping, retrieval, and
generation.

Gate status:

- `dmr_500_failure_mode_gate_passed`: true (classification complete, not a
  performance endorsement)
- `architecture_failure_supported`: false
- `engineering_optimizable_count`: 449
- `design_boundary_count`: 14
- `success_count`: 51
- `productization_allowed`: false
- `runtime_default_change_allowed`: false

## Next Action

Keep feature freeze. Use this classification to guide DMR mapping policy
review and ranking optimization. Do not change runtime defaults from this
report alone.
