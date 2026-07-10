# Phase 5.3.1 Bounded Cognitive Booster Interface

Date: 2026-07-10

Status: Frozen interface; runtime integration not started

Freeze record: `docs/eval/PHASE5_3_1_FREEZE.md`

## 1. Purpose

Phase 5.3.1 defines the contract for a future cognitive score experiment. It
allows an implementation to inspect existing recall candidates and an existing
`CognitiveCompetitionTrace`, then return a bounded **shadow proposal**.

It does not grant decision authority to the cognitive layer.

```text
RecallHit candidates + CognitiveCompetitionTrace
                    |
                    v
          CognitiveBooster interface
                    |
                    v
       CognitiveBoosterOutput proposal
                    |
                    v
          not applied to runtime
```

The baseline recall result remains the only runtime result in this phase.

## 2. Explicit Non-Goals

Phase 5.3.1 does not:

- register a cognitive booster with `RecallEngine`
- implement a production cognitive scoring algorithm
- modify `RecallHit::score`
- modify `RecallHit::activation_bonus`
- reorder recall candidates
- replace a reranker or retrieval score
- create or remove candidates
- read or write through `Store`
- mutate memory, working memory, or memory edges
- change a storage schema or serialized memory schema
- run an A/B recall experiment
- claim Recall@K, MRR, latency, or regression improvement

## 3. Why This Is Not `RecallBooster`

The existing `RecallBooster` contract receives `&mut [RecallHit]` and may add a
bounded value to `RecallHit::activation_bonus`. That is a runtime mutation
surface.

`CognitiveBooster` is intentionally separate:

```rust
pub trait CognitiveBooster {
    fn name(&self) -> &'static str;

    fn boost(
        &self,
        input: CognitiveBoosterInput<'_>,
    ) -> CognitiveBoosterOutput;
}
```

Its input contains only immutable references:

```text
&[RecallHit]
&CognitiveCompetitionTrace
&CognitiveBoosterConfig
```

It receives no mutable candidate slice, `Store`, retriever, reranker, memory
writer, or `RecallEngine` handle.

## 4. OFF-by-Default Configuration

`CognitiveBoosterConfig::default()` is strictly disabled:

```text
enabled = false
max_bonus = 0.0
candidate_limit = 0
```

Shadow mode must be requested explicitly:

```rust
CognitiveBoosterConfig::shadow(max_bonus, candidate_limit)
```

The interface rejects:

- non-finite, zero, or negative bonus limits
- bonus limits above `MAX_COGNITIVE_BOOSTER_BONUS`
- zero candidate limits
- deserialized configuration values that bypass constructor invariants

The Phase 5.3.1 absolute proposal cap is:

```text
MAX_COGNITIVE_BOOSTER_BONUS = 0.10
```

This cap is a proposal bound only. No value is written to recall.

## 5. Bounded Proposal Contract

The configured candidate limit defines an eligible prefix of the immutable
baseline candidate list. `CognitiveBoosterOutput::shadow` reconstructs output
from that input and enforces the boundary:

- proposals for candidates outside the eligible prefix are ignored
- proposals for unknown candidate ids are ignored
- baseline rank and score are copied from the immutable `RecallHit` input
- requested bonuses are normalized to finite, non-negative values
- bonuses are capped by both the validated run limit and the absolute interface cap
- duplicate proposals use the first proposal deterministically
- confidence is normalized to `[0.0, 1.0]`

The output records:

```text
mode
candidate_count
eligible_candidate_count
adjusted_scores
confidence
changed_candidates
max_bonus
bounded
runtime_applied
memory_mutated
```

The safety fields are constructor-controlled and remain:

```text
bounded = true
runtime_applied = false
memory_mutated = false
```

Output fields are private and exposed through read-only accessors. Implementers
cannot construct an output that claims runtime application or memory mutation.
The serialized report retains stable field names for later shadow comparison.

## 6. No-Op and Reversibility

`NoOpCognitiveBooster` is the inert default implementation. It returns a
disabled, empty output even if a caller supplies an explicitly enabled shadow
configuration.

Reversibility in Phase 5.3.1 is structural:

- no engine registration exists
- no runtime branch consumes the proposal
- removing the interface leaves baseline recall untouched
- the baseline candidate list is borrowed immutably

## 7. Validation

Dedicated integration coverage uses the real local `Store`, `RecallEngine`,
returned `RecallHit` candidates, and `CognitiveTraceEvaluator` while keeping
access recording disabled.

The tests verify:

1. default configuration is strictly disabled
2. explicit shadow limits and deserialization are validated
3. candidate eligibility is bounded
4. the no-op implementation is deterministic and object-safe
5. candidate ids, scores, and activation bonuses remain unchanged
6. proposed bonuses are capped
7. untrusted baseline fields and out-of-bound candidate proposals are ignored
8. disabled input cannot produce shadow mode
9. output serialization includes all safety fields

Commands:

```bash
cargo test -p synapse-core --test cognitive_booster_interface_test
cargo check -p synapse-core
```

## 8. Phase Boundary

Phase 5.3.1 completes interface design only:

```text
Interface design              complete
Default-off configuration     complete
Bounded shadow output         complete
RecallEngine integration      not started
Runtime score mutation        not authorized
Shadow ranking experiment     pending Phase 5.3.2
A/B evaluation                pending Phase 5.3.3
Booster authorization         pending Phase 5.3.4
```

The next permitted step is Phase 5.3.2 Shadow Ranking Experiment. It must keep
both baseline and proposed rankings, measure deltas without overwriting the
baseline result, and preserve rollback and default-off behavior.
