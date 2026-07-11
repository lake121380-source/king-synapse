# Phase 7.2 Evidence-Grounded Pattern Extraction Protocol

Status: **protocol implementation complete; extraction algorithm not implemented; held-out transfer cases untouched.**

## Purpose

Phase 7.2 defines how an extractor may convert bounded Experience and Outcome evidence into a `PatternCandidate`. It deliberately separates extraction from discovery, validation, promotion, persistence, and runtime use.

The immediate question is:

> Can a future extractor compress multiple observed experiences into one grounded, scoped, counterexample-aware, predictive, and falsifiable Pattern Candidate without inventing evidence or claiming knowledge authority?

## Input boundary

The extractor input contains only:

```text
source domain
extraction objective
concrete experiences
observed outcomes
constraints
supplied counterexamples
candidate count limit
```

It explicitly excludes:

```text
target_problem
expected_transfer
held_out_cases
runtime_state
```

This prevents the extractor from reverse-engineering a desired target strategy and prevents Phase 7.1 held-out answers from becoming prompt context.

## Design fixtures

Dataset:

```text
crates/eval/datasets/pattern_extraction/phase7_2_pattern_extraction_design.json
```

Summary:

```text
design cases                 10
source Phase 7.1 scenarios   10
supporting experiences       20
counterexamples              10
held-out references           0
```

The dataset is a design-only extraction view. It does not modify the frozen Phase 7.1 transfer benchmark.

## Extractor interface

Eval-only interface:

```rust
pub trait PatternExtractionProvider {
    fn provider_id(&self) -> &str;

    fn extract(
        &self,
        input: &PatternExtractionInput,
    ) -> anyhow::Result<Vec<PatternCandidate>>;
}
```

No provider implementation is included in Phase 7.2.

## Output boundary

A valid extraction output must:

- satisfy the Phase 7.0 `PatternCandidate` contract;
- remain in `PatternStatus::Proposed`;
- cite only authoritative input evidence IDs;
- exactly preserve cited experience provenance;
- consider every supplied counterexample;
- use only source domains present in the input;
- include applicability and exclusion conditions;
- include a prediction and falsification condition;
- leave `validation_outcome_ids` empty;
- keep proposed confidence at or below `0.75`;
- produce no more than one candidate per design case.

Extraction cannot promote, validate, persist, or activate its own output.

## Frozen metrics

```text
contract_validity
evidence_grounding
evidence_coverage
scope_preservation
counterexample_handling
abstraction_specificity
compression_ratio
unsupported_claim_rate
evidence_id_hallucination_rate
boundary_loss_rate
falsifiability_rate
```

`abstraction_specificity` and `compression_ratio` must be interpreted with boundary preservation. A short generic statement is not automatically a useful Pattern.

## Deterministic rejection cases

The quality gate rejects:

```text
hallucinated evidence ID
mismatched evidence provenance
omitted supplied counterexample
premature Active status
premature confidence above 0.75
fabricated validation outcome
more than one candidate per case
```

These cases enforce the distinction:

```text
extraction output = candidate cognition artifact
extraction output != validated knowledge
```

## Safety boundary

```text
eval-only                         true
design-only                       true
held-out cases touched            false
extraction algorithm              false
model evaluation                  false
Pattern persistence               false
runtime                           false
Hermes                            false
autonomous promotion              false
```

No changes are permitted in `RecallEngine`, memory storage, production schemas, CLI recall, MCP runtime behavior, or Cognitive Booster behavior.

## Validation

```powershell
cargo fmt --all -- --check
cargo test -p synapse-eval --test phase7_pattern_extraction_protocol_test --jobs 1 -- --test-threads=1
cargo check --workspace --jobs 1
python scripts/eval/phase7_pattern_extraction_protocol.py
```

Generated report:

```text
crates/eval/reports/phase7_pattern_extraction_protocol.json
```

## Scientific boundary

Phase 7.2 proves:

- the extractor input is isolated from transfer answers and held-out cases;
- the output format is constrained by the Phase 7.0 Pattern contract;
- evidence IDs and provenance are checked automatically;
- supplied counterexamples cannot be silently dropped;
- extraction cannot self-promote or fabricate validation;
- metrics and negative cases are frozen before model execution.

Phase 7.2 does not prove:

- an LLM can extract a correct Pattern;
- the reference candidate is the only valid abstraction;
- extracted Patterns improve transfer;
- automatic semantic grounding is solved;
- Pattern validation or knowledge promotion exists;
- runtime integration is authorized.

## Decision

```text
Extraction protocol                 frozen
Design fixtures                     frozen
Reference contract gate             passed
Model/extractor implementation      blocked in this phase
Held-out transfer cases             untouched
Pattern persistence                 blocked
Runtime                             blocked
```

The next bounded step is Phase 7.2.1: implement one deterministic or model-backed extraction provider against the ten design inputs only. Prompts, provider configuration, output repair policy, and scoring must be frozen before opening the Phase 7.1 held-out split.
