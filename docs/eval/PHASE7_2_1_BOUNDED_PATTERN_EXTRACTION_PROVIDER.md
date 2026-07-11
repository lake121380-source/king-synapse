# Phase 7.2.1 Bounded Pattern Extraction Provider

Status: frozen design evaluation.

## Objective

Phase 7.2.1 permits one extractor implementation to run for the first time while preserving the distinction:

```text
provider output
!= valid Pattern knowledge
!= transfer value
!= persistence authority
!= runtime authority
```

The objective is to prove that an extractor can be executed behind the Phase 7.2 contract and that invalid outputs receive explicit, deterministic rejection reasons.

## Frozen provider

```text
provider_id             deterministic_bounded_pattern_extractor_v0
provider_kind           deterministic transparent weak baseline
model_id                 none
prompt/ruleset           deterministic_ruleset_v0_no_model_prompt
candidate limit          1
confidence cap           0.60
output repair            reject only; no automatic repair
design cases             10
held-out access          false
persistence              false
runtime                  false
```

The provider is intentionally transparent and weak. It performs no model call and does not use the reference candidate as extraction input. It:

1. separates supporting experiences from supplied counterexamples;
2. preserves every evidence identifier and provenance field;
3. selects recurring grounded terms deterministically;
4. emits domain-bounded applicability conditions;
5. converts supplied counterexamples into exclusion conditions;
6. emits one prediction and one falsification condition;
7. leaves the candidate in `PatternStatus::Proposed`.

This provider is a reproducible extraction baseline, not a claim of semantic Pattern discovery.

## Contract acceptance versus extraction quality

The evaluator reports two separate layers.

### Contract layer

A candidate is rejected when it violates the Phase 7.0/7.2 boundary, including fabricated evidence, missing counterexamples, premature status, fabricated validation, or candidate-count overflow.

A structurally valid output receives only:

```text
accepted_contract_only
```

It never receives `validated`, `supported`, `active`, or `knowledge` status.

### Quality diagnostics layer

Contract-valid output is separately measured for:

```text
pattern_completeness
evidence_attribution_accuracy
evidence_coverage
scope_retention
counterexample_handling
abstraction_distance_score
design_reference_token_recall
unsupported_claim_rate
compression_ratio
```

`design_reference_token_recall` is a design-only diagnostic. The reference proposition is not exposed to the provider. It is not treated as the only correct abstraction and is not a production acceptance gate.

## Result

```text
design cases                       10
provider executions                10
candidates produced                10
contract accepted                  10
contract rejected                   0
cases with quality diagnostics      9
fault injections rejected           6 / 6
pattern completeness mean           1.0
evidence attribution mean           1.0
scope retention mean                1.0
counterexample handling mean        1.0
design reference token recall      ~0.064
```

The important result is not `10/10 contract accepted`. The weak provider preserves structural safety while showing low design-reference alignment and quality warnings on nine cases.

This demonstrates:

```text
format and provenance correctness
!= useful abstraction quality
```

The system can now execute an extractor, accept only its bounded artifact shape, and explain why the abstraction still requires review.

## Fault-injection gate

The evaluator injects and rejects:

```text
hallucinated evidence ID
omitted supplied counterexample
premature Active status
fabricated validation outcome
candidate limit exceeded
empty provider output
```

Every rejection contains the observed violation codes. No automatic repair is attempted because silent repair would blur provider behavior and validator behavior.

## Safety boundary

```text
eval-only                         true
design-only                       true
held-out cases touched            false
automatic repair                  false
Pattern persistence               false
knowledge promotion               false
transfer value claimed            false
Hermes                            false
runtime                           false
```

No changes are made to RecallEngine, storage, schema, candidate generation, ranking, CLI recall, MCP runtime behavior, or Cognitive Booster behavior.

## Validation

```powershell
cargo fmt --all -- --check
cargo test -p synapse-eval --test phase7_bounded_pattern_extraction_provider_test --jobs 1 -- --test-threads=1
cargo test -p synapse-eval --test phase7_pattern_extraction_protocol_test --jobs 1 -- --test-threads=1
cargo test -p synapse-eval --test phase7_transfer_evaluation_protocol_test --jobs 1 -- --test-threads=1
cargo check --workspace --jobs 1
python scripts/eval/phase7_bounded_pattern_extraction_provider.py
```

Generated report:

```text
crates/eval/reports/phase7_bounded_pattern_extraction_provider.json
```

## Scientific conclusion

Phase 7.2.1 proves:

- a frozen provider can execute only against the ten design inputs;
- identical inputs produce identical candidates;
- evidence provenance and supplied counterexamples are preserved;
- contract-invalid provider output is rejected with explicit reasons;
- contract acceptance and semantic quality diagnostics are separate;
- no output can self-promote, persist, or enter runtime.

Phase 7.2.1 does not prove:

- the deterministic provider extracts useful semantic Patterns;
- low lexical alignment means a candidate is necessarily wrong;
- a model-backed extractor will generalize;
- extracted candidates improve transfer;
- Pattern validation is solved;
- knowledge promotion or runtime use is authorized.

## Next bounded step

The next step should compare a frozen model-backed or stronger extraction provider against this transparent weak baseline on the same ten design cases. Provider identity, model version, prompt, decoding, retry policy, and output repair policy must be frozen before execution.

The Phase 7.1 held-out split must remain closed until provider and evaluation policy are frozen.
