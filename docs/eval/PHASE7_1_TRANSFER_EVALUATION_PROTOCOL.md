# Phase 7.1 Transfer Evaluation Protocol

Status: **implementation complete; protocol and dataset frozen; transfer outcomes not yet measured.**

## Purpose

Phase 7.1 defines the test standard that future Pattern Discovery work must pass. It does not implement Pattern Mining and does not claim that a Pattern improves an agent.

The research question is:

> Does an evidence-grounded Pattern help solve an unseen target problem better than model priors, raw memories, or ordinary summaries, while reducing harmful transfer?

## Scope and safety boundary

```text
eval-only                         true
shadow-only                       true
RecallEngine modified             false
memory schema modified            false
Pattern persistence authorized    false
Pattern Discovery implemented     false
Hermes authorized                 false
runtime authorized                false
autonomous promotion authorized   false
```

Phase 7.1 freezes the protocol before any Pattern algorithm can observe the held-out cases.

## Dataset

Frozen dataset:

```text
crates/eval/datasets/transfer/phase7_1_transfer_benchmark.json
```

Summary:

```text
scenarios       30
design          10
held_out        20
categories       6
```

Each scenario contains:

- source and target domains;
- multiple supporting experiences with outcome provenance;
- at least one counterexample or limiting experience;
- a candidate proposition;
- applicability scope and exclusions;
- evidence-lineage edges;
- a target problem;
- an expected apply/withhold decision;
- an expected bounded strategy;
- a dangerous-transfer description.

The categories are:

1. `direct_transfer`
2. `cross_domain_transfer`
3. `negative_transfer`
4. `scope_boundary`
5. `counterexample_sensitive`
6. `no_transfer`

The held-out split is reserved for future Pattern Discovery evaluation. It must not be used to tune induction prompts, thresholds, or confidence rules.

## Experimental arms

The protocol freezes six comparisons:

| Arm | Information supplied |
|---|---|
| LLM Only | Target problem only |
| Raw Memories | Target problem and source experiences |
| Memory Summary | Compressed memory summary without a promoted Pattern |
| Pattern Candidate | Proposition-only Pattern Candidate |
| Pattern + Scope + Counterexamples | Pattern with applicability and limiting evidence |
| Pattern + Evidence Graph | Full Pattern package with provenance and memory lineage |

`outcome_performance_measured=false` remains explicit for every arm. Phase 7.1 establishes what will be compared; it does not fabricate model outputs or treat information availability as transfer success.

## Frozen metrics

Quality:

```text
pattern_grounding
abstraction_correctness
scope_precision
counterexample_coverage
strategy_quality_delta
```

Transfer behavior:

```text
transfer_success_rate
useful_transfer_rate
withholding_accuracy
negative_transfer_rate
dangerous_transfer_rate
hallucinated_rule_rate
```

Representation:

```text
pattern_compression_ratio
explanation_dependency
```

Compression must never be interpreted independently of grounding and scope retention.

## Failure taxonomy

Phase 7.1 freezes these failure classes:

```text
unsupported_abstraction
scope_overreach
counterexample_ignored
literal_surface_copy
causal_confusion
negative_transfer
missed_transfer
confidence_without_outcome
```

Negative transfer, scope overreach, ignored counterexamples, causal confusion, and confidence without outcomes are safety-critical.

## Validation

Commands:

```powershell
cargo fmt --all -- --check
cargo test -p synapse-eval --test phase7_transfer_evaluation_protocol_test --jobs 1 -- --test-threads=1
cargo check --workspace --jobs 1
python scripts/eval/phase7_transfer_evaluation_protocol.py
```

The deterministic gate validates dataset completeness, split reservation, category coverage, all six arms, all metrics, failure taxonomy, and runtime isolation.

## Scientific boundary

Phase 7.1 proves:

- a transfer benchmark exists;
- both useful-transfer and must-withhold cases exist;
- evidence, scope, counterexamples, and lineage are represented;
- comparison arms and metrics are frozen;
- invalid transfer scenarios are rejected deterministically.

Phase 7.1 does **not** prove:

- an LLM can discover valid Patterns;
- Pattern Candidates improve transfer;
- Evidence Graph input improves strategy quality;
- compression preserves all useful knowledge;
- the system can autonomously promote knowledge;
- runtime integration is safe or useful.

## Decision

```text
Transfer protocol                  frozen
Held-out cases                     reserved
Baseline comparison protocol       complete
Transfer outcome evaluation        pending
Pattern Discovery                  blocked
Pattern persistence                blocked
Hermes                             blocked
Runtime                            blocked
```

The next authorized work is a bounded Pattern Discovery prototype evaluated first on the design split. The held-out split remains sealed until the algorithm, prompts, and decision rules are frozen.
