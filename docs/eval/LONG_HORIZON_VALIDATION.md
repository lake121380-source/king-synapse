# Long-Horizon Cognitive Validation

Date: 2026-07-03

Status: deterministic long-horizon cognitive-memory benchmark passed; detailed
stability audit is now recorded and exposes a future evidence-matching gap.

Machine-readable report:

`crates/eval/reports/long-horizon-cognitive-memory.json`

Detailed stability audit:

`crates/eval/reports/long-horizon-stability-audit.json`

Command:

```powershell
cargo bench -p synapse-eval --bench long_horizon_cognitive_memory
```

Detailed audit command:

```powershell
cargo bench -p synapse-eval --bench long_horizon_stability_audit
```

## Scope

This validation checks the cognitive-memory design in one shared long-session
store. It is not a LongMemEval retrieval benchmark and does not use external
data.

The fixture writes eight day-stamped cognitive chains into the same in-memory
store. Each chain has:

- a visible seed memory;
- a visible distractor;
- an expected hidden influence;
- a hidden distractor;
- an expected future continuation;
- a future distractor;
- state and goal terms that should pull the correct hidden influence into the
  trace and continuation.

The eight chain families are:

| Case | Theme |
| --- | --- |
| `day01-hydration-commute` | body state -> commute attention |
| `day02-pressure-review` | social pressure -> subconscious review avoidance |
| `day03-charger-demo` | missing tool -> task failure risk |
| `day04-past-bug` | past failure -> future decision attention |
| `day05-trust-message` | social emotion -> communication decision |
| `day06-hunger-incident` | hunger state -> operational mistake risk |
| `day07-social-feedback` | preference memory -> communication friction |
| `day08-complex-review` | repeated bug -> subconscious avoidance |

## Result

| Metric | Value | Meaning |
| --- | ---: | --- |
| Recall@10 | 1.000 | Each final query recalls the expected visible seed. |
| CognitiveTraceDominance | 1.000 | The expected hidden influence wins the trace. |
| HebbianConsistency | 1.000 | Post-trace reinforcement strengthens the expected visible-hidden edges. |

## Stability Audit

The detailed audit keeps the same eight-case fixture but checks more than the
frozen benchmark contract:

- prefix store vs full store, to see whether later memories override earlier
  ones;
- older four cases vs newer four cases;
- hidden trace dominance in the full store;
- expected future continuation;
- three reinforcement rounds per case, to check trace drift.

| Audit check | Value | Read |
| --- | ---: | --- |
| Visible seed retention | 1.000 | Every case still recalls the expected visible seed in top 10. |
| Old memory preservation | 1.000 | The first four cases keep visible recall and dominant hidden trace after later writes. |
| Newer memory addressability | 1.000 | The last four cases remain addressable despite older memories already being present. |
| Hidden trace dominance | 1.000 | The expected hidden influence wins in all eight cases. |
| Future candidate presence | 1.000 | Every expected future candidate appears in continuation top 10. |
| Future prediction stability | 0.750 | Six of eight cases attach matched evidence terms to the expected future continuation. |
| Dominant drift resistance | 1.000 | Dominant hidden traces do not drift after three reinforcement rounds. |
| Prediction drift resistance | 0.750 | The same two matched-evidence misses remain after reinforcement. |
| Reinforcement consistency | 1.000 | Expected visible-hidden edges strengthen during reinforcement. |

The two future-continuation misses are `day03-charger-demo` and
`day05-trust-message`. They do not break visible recall or hidden trace
dominance, but they show that the future-prediction part of the long-horizon
story is weaker than the trace part. The rank-localization fields in
`long-horizon-stability-audit.json` now split candidate rank from matched rank.
For those two cases, the expected future candidate is present at rank 1 in the
prefix store, the full store, and after three reinforcement rounds, but its
matched rank is `null`. This is therefore a context/evidence-matching miss,
not a continuation-candidate miss.

## Read

Engineering result:

The long-horizon cognitive fixture passes with all fixed metrics at `1.000`.
Old day-stamped memories still participate in current queries inside a shared
store, hidden influences can still dominate over distractors, and post-trace
reinforcement remains consistent.

The detailed audit adds a sharper read: visible recall, older/newer memory
separation, hidden trace dominance, and dominant-trace drift resistance are
stable on this fixture. Future candidate recall is also stable at `8/8`, but
future matched evidence is weaker at `6/8`. The two misses are candidate-present
but evidence-missing cases.

Research interpretation:

This supports the core Synapse thesis in the deterministic cognitive fixture:
memory is behaving like a network where visible cues, hidden influences, and
future-facing reinforcement can remain connected across a longer session.

It does not prove real-world long-horizon robustness by itself. The fixture is
small, deterministic, and hand-shaped. It should be treated as a regression
gate for the cognitive model, not as a substitute for LongMemEval / DMR public
benchmark evidence.

## Boundary

This validation proves:

- old visible memories can still be recalled in a shared long-session store;
- hidden influences can still dominate the trace despite distractors;
- reinforcement can update expected visible-hidden edges after the report;
- repeated reinforcement does not move the dominant trace away from the
  expected hidden influence in this fixture.

This validation does not yet prove:

- real multi-day user data stability;
- full future-prediction stability;
- resistance to uncontrolled drift after many reinforcement rounds beyond the
  three-round audit;
- that new memories never override old memories incorrectly outside this
  deterministic fixture;
- superiority over external systems on hosted long-memory workloads.

## Decision

Keep feature growth frozen. Treat `long-horizon-cognitive-memory` as the
current deterministic regression gate, and treat
`long-horizon-stability-audit` as the sharper diagnostic baseline. The next
long-horizon weakness to investigate is future evidence matching, not visible
recall, hidden trace dominance, or candidate recall.

## Next Work

1. Preserve `long-horizon-cognitive-memory` at `1.000` for all fixed metrics.
2. Explain the two future-continuation evidence misses in the stability audit
   without changing product-facing behavior.
3. Add broader long-horizon evidence only as validation work, not product
   surface expansion.
4. Complete hosted/official external comparisons before productization claims.
