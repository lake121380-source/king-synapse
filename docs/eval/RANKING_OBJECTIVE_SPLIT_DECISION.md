# Ranking Objective Split Decision

Date: 2026-07-04

Status: validation decision, not a runtime change

Machine-readable report:

`crates/eval/reports/ranking-objective-split-decision.json`

Runner:

`scripts/eval/ranking_objective_split_decision.py`

## Question

The LongMemEval / DMR trend-alignment audit showed a real conflict:

`Do we have a single ranking direction that improves both DMR and LongMemEval enough to become a global default?`

Current answer:

`No.`

This decision audit answers the follow-up:

`Is that conflict a core Synapse architecture failure, or a ranking-objective split?`

Current answer:

`It is a ranking-objective split.`

## Evidence Read

| Evidence | Read |
| --- | --- |
| DMR top-context significance | DMR top-context improves judged answer correctness at DMR 50, 200, and 500-request / 323-scored scale views. |
| Ranking objective conflict | Existing one-variable ranking evidence has conflict/tradeoff views and no global default candidate. |
| Pool-signal guard audit | No screened guard is ready for implementation. |
| LongMemEval / DMR trend alignment | Expanded pool-50 -> pool-100 trends are mixed across datasets. |
| DMR failure taxonomy | DMR has separate mapping, retrieval/ranking, and answer-synthesis boundaries. |
| Long-horizon task gate | Public real-world long-memory evidence is still not ready. |

## Decision

DMR and LongMemEval should be treated as separate validation objectives for
ranking work:

| Track | Primary objective | Current boundary |
| --- | --- | --- |
| DMR | Improve answer-bearing context placement and answer synthesis under local official-style DMR. | Mapping policy, retrieval top-10 misses, top-context ranking boundary, answer synthesis. |
| LongMemEval | Protect long-memory retrieval stability across expanded views. | Zero tolerated LongMemEval top-10 suppressions before runtime adoption, public long-memory evidence still open. |

This split does **not** mean Synapse can adopt a DMR-specific runtime default.
It only prevents the project from treating a cross-dataset objective conflict as
a core architecture failure.

## Not A Design Bug

The current evidence does not show that the architecture is broken:

- DMR top-context answer generation repeats a positive, statistically supported
  direction across scale views.
- Ranking changes move real retrieval metrics, so ranking is an active
  bottleneck rather than a dead subsystem.
- The same ranking changes create dataset-specific tradeoffs, especially around
  LongMemEval suppression and latency.

That means the correct Phase 6 read is:

`ranking bottleneck + objective split + no global default`

not:

`system design failed`

## Runtime Decision

Do not change runtime ranking defaults.

Do not change:

- memory schema;
- cognitive layers;
- CLI/MCP behavior;
- retrieval defaults;
- ranking defaults;
- generator defaults;
- product surfaces.

Future ranking work needs one of two paths:

1. a new answer-free ordering signal that does not suppress LongMemEval top-10
   hits; or
2. objective-specific policies that remain evaluation-only until separately
   validated.

## Phase 6 Impact

This closes the ambiguous part of the ranking question:

`DMR / LongMemEval objective split is now decided as validation-only.`

It does not close:

- hosted external comparison;
- published-comparable DMR mapping policy;
- DMR answer quality;
- public real-world long-memory validation;
- latency acceptance;
- productization.

So Phase 6 continues. Phase 7 still does not start.
