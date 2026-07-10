# Phase 7.0 Cognitive Architecture Reorientation

Status: **Contract implementation complete; Pattern discovery, persistence, promotion, strategy execution, Hermes, and runtime remain unauthorized.**

## Purpose

Phase 7.0 changes the research mainline from retrieval-score intervention to evidence-grounded Experience-to-Pattern learning.

It does not claim that King Synapse can already discover or transfer knowledge. It defines the artifact contract, lifecycle, evidence requirements, authority boundary, and next valid experiment.

## North Star

```text
Experience
    -> Evidence
    -> Pattern Candidate
    -> Validated Pattern
    -> Strategy Candidate
    -> Transfer
    -> Outcome Feedback
    -> Knowledge Evolution
```

King Recall remains the evidence substrate. Cognitive learning becomes the system responsible for abstraction, falsification, transfer, and outcome-driven revision.

See `docs/COGNITIVE_ARCHITECTURE_NORTH_STAR.md`.

## Eval-only PatternCandidate contract

The Phase 7.0 contract is implemented in `synapse-eval`, not `synapse-core`:

```rust
PatternCandidate {
    id,
    proposition,
    supporting_evidence,
    counterexamples,
    counterexample_search_performed,
    applicability_conditions,
    exclusion_conditions,
    source_domains,
    predictions,
    falsification_conditions,
    validation_outcome_ids,
    confidence,
    status,
}
```

A structurally valid candidate requires:

1. a non-empty identity and proposition;
2. at least two distinct supporting memories;
3. source and experience provenance;
4. explicit counterexample search;
5. applicability conditions;
6. at least one source domain;
7. a testable prediction;
8. a falsification condition;
9. bounded finite confidence;
10. validation outcomes before any non-proposed lifecycle status.

The checked canonical candidate is deliberately `Proposed`. It has no decision or runtime authority.

## Negative contract cases

The deterministic gate verifies rejection of:

```text
missing supporting evidence
missing applicability scope
missing falsification condition
counterexample search not performed
invalid confidence
premature Active status without validation outcomes
```

These are contract tests only; they are not Pattern-quality or transfer-quality results.

## Confidence boundary

Allowed future confidence inputs:

```text
new independent supporting evidence
new counterexample
observed transfer outcome
explicit human or evaluator review
```

Prohibited inputs:

```text
retrieval count
usage count without outcome
model self-assertion
generated explanation without evidence
```

This prevents a self-confirming loop in which a generated pattern becomes more trusted merely because the same system repeatedly retrieves or uses it.

## Lifecycle boundary

The declared lifecycle is:

```text
Proposed -> Supported
Supported -> Active
Active -> Challenged
Challenged -> Refined
Refined -> Active
Active -> Superseded
Proposed -> Rejected
```

Every transition is non-autonomous and requires an explicit evaluation gate. Phase 7.0 performs no transition and writes no pattern.

## Safety boundary

The report records:

```text
eval_only                         = true
contract_only                     = true
recall_engine_modified            = false
cognitive_booster_modified        = false
memory_schema_changed             = false
memory_written                    = false
pattern_persisted                 = false
pattern_algorithm_implemented     = false
autonomous_pattern_promotion      = false
strategy_execution_performed      = false
runtime_applied                   = false
hermes_integration_performed      = false
production_claim_authorized       = false
```

## What PASS means

`PASS` means:

- the canonical PatternCandidate satisfies the structural contract;
- malformed candidates fail for the expected reasons;
- all lifecycle transitions require explicit evaluation;
- no artifact has runtime authority;
- confidence cannot grow from usage alone;
- the Experience-to-Pattern research mainline is explicitly recorded.

`PASS` does not mean:

```text
Pattern discovery works
Patterns improve task performance
Cross-domain transfer works
A knowledge graph is ready
Autonomous learning is safe
Hermes integration is ready
Runtime execution is authorized
```

## Artifacts

```text
docs/COGNITIVE_ARCHITECTURE_NORTH_STAR.md
crates/eval/src/phase7_cognitive_architecture_contract.rs
crates/eval/src/bin/phase7_cognitive_architecture_contract.rs
crates/eval/tests/phase7_cognitive_architecture_contract_test.rs
scripts/eval/phase7_cognitive_architecture_contract.py
crates/eval/reports/phase7_cognitive_architecture_contract.json
```

Run:

```bash
python scripts/eval/phase7_cognitive_architecture_contract.py
```

## Validation

Executed on July 10, 2026:

```text
cargo fmt --all -- --check
    PASS

cargo test -p synapse-eval --test phase7_cognitive_architecture_contract_test --jobs 1 -- --test-threads=1
    9 passed; 0 failed

cargo check --workspace --jobs 1
    PASS

python scripts/eval/phase7_cognitive_architecture_contract.py
    PASS
```

Runtime isolation was also checked with:

```text
git diff -- crates/core crates/cli crates/mcp-server
```

Result: no runtime, storage, CLI, or MCP implementation diff.
## Decision

```text
Experience-to-Pattern mainline        authorized
Pattern contract                      established
Pattern discovery algorithm           not authorized
Pattern persistence                   not authorized
Knowledge Graph                       not authorized
Autonomous self-improvement            not authorized
Hermes                                not authorized
Runtime                               not authorized
```

The next valid step is **Phase 7.1 Transfer Benchmark Design**. It must compare LLM-only, raw-memory, memory-summary, Pattern, and Pattern-with-counterexamples conditions on held-out target problems, and it must measure both successful transfer and harmful negative transfer before implementing an autonomous pattern-learning path.
