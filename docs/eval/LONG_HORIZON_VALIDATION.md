# Long-Horizon Cognitive Validation

Date: 2026-07-03

Status: deterministic long-horizon cognitive-memory benchmark passed.

Machine-readable report:

`crates/eval/reports/long-horizon-cognitive-memory.json`

Command:

```powershell
cargo bench -p synapse-eval --bench long_horizon_cognitive_memory
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
- state and goal terms that should pull the correct hidden influence into the
  trace.

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

## Read

Engineering result:

The long-horizon cognitive fixture passes with all fixed metrics at `1.000`.
Old day-stamped memories still participate in current queries inside a shared
store, hidden influences can still dominate over distractors, and post-trace
reinforcement remains consistent.

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
- reinforcement can update expected visible-hidden edges after the report.

This validation does not yet prove:

- real multi-day user data stability;
- resistance to uncontrolled drift after many reinforcement rounds;
- that new memories never override old memories incorrectly;
- superiority over external systems on hosted long-memory workloads.

## Decision

Keep feature growth frozen. Treat this as the current deterministic
long-horizon cognitive regression gate. Productization still waits on external
comparison gaps and broader long-horizon evidence.

## Next Work

1. Preserve `long-horizon-cognitive-memory` at `1.000` for all fixed metrics.
2. Add broader long-horizon evidence only as validation work, not product
   surface expansion.
3. Complete hosted/official external comparisons before productization claims.
