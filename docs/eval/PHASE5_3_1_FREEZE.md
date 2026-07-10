# Phase 5.3.1 Freeze: Bounded Cognitive Booster Interface

Date: 2026-07-10

Status: **Frozen**

Mode: Interface-only, shadow-only, OFF by default

## 1. Freeze Statement

Phase 5.3.1 freezes the safety container for future cognitive ranking
experiments.

The frozen capability is:

```text
immutable RecallHit candidates
        +
CognitiveCompetitionTrace
        |
        v
CognitiveBooster
        |
        v
bounded shadow proposal
        |
        v
not applied to runtime
```

This phase does not freeze or authorize a cognitive scoring algorithm. It
freezes only the interface, configuration, proposal, and safety boundaries
required before Phase 5.3.2 can compare a baseline ranking with a shadow
ranking.

## 2. Frozen Interface Surface

The experimental public surface is:

```text
CognitiveBooster
CognitiveBoosterConfig
CognitiveBoosterConfigError
CognitiveBoosterInput
CognitiveBoosterMode
CognitiveAdjustedScore
CognitiveBoosterOutput
NoOpCognitiveBooster
MAX_COGNITIVE_BOOSTER_BONUS
```

The implementation lives under:

```text
crates/core/src/adaptive/cognitive_booster/
```

The detailed design is recorded in:

```text
docs/PHASE5_3_1_BOUNDED_COGNITIVE_BOOSTER_INTERFACE.md
```

## 3. Frozen Safety Boundary

### Input authority

`CognitiveBooster` receives immutable references only:

```text
&[RecallHit]
&CognitiveCompetitionTrace
&CognitiveBoosterConfig
```

It receives no mutable hit slice, `Store`, `RecallEngine`, retriever, reranker,
working-memory writer, or memory mutation handle.

### Configuration authority

Default configuration remains:

```text
enabled = false
max_bonus = 0.0
candidate_limit = 0
```

Explicit shadow configuration must validate both construction and
deserialization. The absolute proposal cap remains:

```text
MAX_COGNITIVE_BOOSTER_BONUS = 0.10
```

### Output authority

The system reconstructs baseline rank and score from immutable `RecallHit`
input. Booster implementations cannot establish their own baseline evidence.
Unknown candidates and candidates outside the eligible prefix are excluded.

Output construction preserves:

```text
bounded = true
runtime_applied = false
memory_mutated = false
```

These fields remain private and read-only to callers.

## 4. Runtime Non-Authority

At this freeze point there is:

```text
RecallEngine integration      false
RecallBooster integration     false
runtime score mutation        false
activation_bonus mutation     false
runtime ranking mutation      false
candidate creation            false
memory write                  false
schema change                 false
working-memory mutation       false
```

Baseline recall remains authoritative. A shadow proposal has no code path that
can overwrite the returned recall result.

## 5. Evidence

Dedicated interface validation:

```text
cargo test -p synapse-core --test cognitive_booster_interface_test

9 passed
0 failed
```

Core regression validation:

```text
cargo test -p synapse-core

217 passed
0 failed
```

Additional checks:

```text
cargo fmt --all -- --check     passed
cargo check -p synapse-core    passed
cargo check --workspace        passed
cargo doc -p synapse-core      passed
git diff --check               passed
```

`cargo clippy -p synapse-core --all-targets` completes with ten existing
warnings in pre-existing cognitive-trace and hypothesis files. No warning is
reported from the new `adaptive/cognitive_booster` module or its integration
test.

## 6. Claims Explicitly Not Made

Phase 5.3.1 does not prove or claim:

- improved Recall@K
- improved MRR
- reduced ranking regression
- acceptable production latency
- human preference for boosted rankings
- LLM preference for boosted rankings
- production safety of a concrete cognitive scoring policy
- authorization to enable any booster at runtime

No A/B ranking result exists in this phase.

## 7. Freeze Decision

Phase 5.3.1 is frozen as:

```text
Interface                  frozen
Safety boundary            frozen
Default state              disabled
Runtime behavior           unchanged
Decision authority         not granted
Shadow experiment          authorized as next design step
Runtime booster            not authorized
```

The next permitted stage is Phase 5.3.2 Shadow Ranking Experiment. It may
produce baseline-versus-shadow comparison reports, rank-movement diagnostics,
proposal coverage, bound checks, and offline metrics when ground truth exists.
It must not replace, mutate, or return the shadow ranking as the runtime recall
result.
