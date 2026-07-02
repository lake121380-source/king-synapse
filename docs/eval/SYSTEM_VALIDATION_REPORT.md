# System Validation Report

Date: 2026-07-02

Status: scoped validation passed.

This report answers only the three system-validation questions. It does not
claim that LongMemEval, DMR, hosted Graphiti, hosted Mem0, or a live Letta
endpoint have been fully measured.

## 1. Is The System Stable?

Answer: yes for the exported cognitive-session fixture and internal evaluation
surface.

Evidence:

- `cargo fmt --all -- --check` passed.
- `cargo test -p synapse-eval` passed with `40 passed; 0 failed`.
- `cargo bench -p synapse-eval --bench exported_cognitive_session` reported:

```json
{
  "RecallAt10": 1.0,
  "HebbianConsistency": 1.0,
  "CognitiveTraceDominance": 1.0
}
```

The King Synapse external harness was then run five times against the same
fixture. Every run produced the same scored behavior:

| Metric | Result |
| --- | ---: |
| Visible seed recall | 8/8 in every run |
| Hidden influence retrieval | 8/8 in every run |
| Dominant trace selection | 8/8 in every run |
| Suppressed alternatives visible | 8/8 in every run |
| Evidence path availability | 8/8 in every run |
| Future continuation | 8/8 in every run |
| Reinforcement isolation | 8/8 in every run |

Observed mean-latency range for the five repeatability runs:

```text
4.52 ms .. 4.70 ms
```

Stability conclusion: stable on the current deterministic cognitive fixture.
Not yet proven on LongMemEval, DMR, or hosted external systems.

## 2. Is The System Internally Consistent?

Answer: yes for the validated fixture.

The current validation did not observe contradiction between recall, latent
trace evidence, prediction, or reinforcement isolation:

- visible recall found the visible seed in every chain;
- hidden influence retrieval found the intended hidden memory in every chain;
- dominant trace selection matched the intended hidden influence in every
  chain;
- suppressed alternatives remained visible instead of disappearing from the
  report;
- evidence paths were available for every chain;
- future continuation was found for every chain;
- reinforcement stayed isolated after the report and did not mutate the
  already-scored result.

Consistency conclusion: the system's main cognitive-memory layers agree with
each other under the exported cognitive-session fixture. This is enough to say
the core design is coherent in the validated scope, but not enough to claim
long-horizon real-world consistency yet.

## 3. Does King Synapse Expose More Cognitive-Trace Ability?

Answer: yes in the checked external-comparison fixture.

The latest external comparison measured King Synapse, Graphiti/Zep local Kuzu
mode, and Mem0 OSS with DeepSeek plus local Qdrant. Letta remained unmeasured:
the SDK was installed later, but `LETTA_ENVIRONMENT=local` failed with a
connection error because no local Letta endpoint was reachable.

| System | Visible | Hidden | Dominant trace | Suppressed alternatives | Evidence paths | Future continuation | Reinforcement isolation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| King Synapse | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| Graphiti/Zep local | 8/8 | 8/8 | unsupported | unsupported | 8/8 | unsupported | unsupported |
| Mem0 OSS + DeepSeek | 8/8 | 8/8 | unsupported | unsupported | unsupported | unsupported | unsupported |
| Letta | not measured | not measured | not measured | not measured | not measured | not measured | not measured |

Comparative conclusion: King Synapse currently exposes the richest
cognitive-trace surface in this fixture. Graphiti/Zep can surface graph-style
evidence paths in local deterministic mode, but the adapter does not expose
dominant/suppressed trace competition, future continuation, or reinforcement
isolation. Mem0 retrieves visible and hidden facts in this run, but does not
expose path evidence, trace competition, prediction, or reinforcement
isolation through the measured adapter.

This is not a claim that King Synapse is better at every long-memory task. It
is a narrower claim: for the cognitive-trace behavior this project is designed
to validate, King Synapse exposes more inspectable structure than the measured
competitor adapters.

## Final Judgment

King Synapse is valid enough to leave feature-building mode and remain in
system validation mode.

The project has crossed the basic bar for:

1. stable deterministic fixture behavior;
2. internally consistent recall, trace, prediction, and reinforcement reports;
3. visible comparative value on cognitive-trace introspection.

The project has not yet crossed the bar for:

1. LongMemEval / DMR smoke results;
2. hosted Graphiti or hosted Mem0 comparison;
3. live Letta endpoint measurement;
4. production-readiness claims.

Next required action: keep feature growth frozen and run the Stage 6
LongMemEval / DMR smoke path described in
`docs/eval/LONGMEM_DMR_DATA_PLAN.md`.
