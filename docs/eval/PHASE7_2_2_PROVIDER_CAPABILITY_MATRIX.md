# Phase 7.2.2 Frozen Provider Capability Matrix

Status: comparison protocol frozen; model execution blocked by authorization.

## Objective

Phase 7.2.2 freezes a reproducible provider-comparison surface before any held-out transfer evaluation. It compares provider behavior, not writing style, under one fixed extraction protocol:

```text
same 10 design inputs
same Pattern Candidate contract
same canonical prompt version
same strict parser
same reject-only repair policy
same evidence-grounded scorer
```

Permanent principle:

> Never reward linguistic sophistication. Reward only evidence-grounded abstraction.

## Frozen artifacts

```text
canonical prompt       PatternExtractorPrompt-v1
parser                 strict_pattern_candidate_json_v1
repair                  reject only; no automatic repair
scorer                  evidence_grounded_extraction_scorer_v1
primary safety metric  unsupported_claim_rate
design dataset          phase7.2-pattern-extraction-design-v1
held-out access         false
```

The provider manifest records provider/model versions, temperature, top-p, prompt version, prompt/parser/scorer/dataset SHA-256 values, repair policy, dataset version, and execution status.

## Capability matrix

| Provider | Status | Design completed | Contract validity | Evidence attribution | Scope preservation | Counterexample retention | Unsupported claim rate | Abstraction distance |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deterministic bounded weak baseline v0 | completed | 10/10 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0442 | 0.3828 |
| DeepSeek model-backed provider v1 | blocked_authorization | 0/10 | not measured | not measured | not measured | not measured | not measured | not measured |

The DeepSeek preflight returned HTTP `401` on July 11, 2026. The sanitized artifact records the authorization blocker without recording the API key or raw response text. No design calls were performed after the failed preflight and no model metrics were fabricated.

Therefore this phase does **not** complete a weak-baseline-versus-model capability comparison. It freezes the experiment needed to perform that comparison once authorization is valid.

## Strict parsing behavior

The parser accepts exactly one JSON object and rejects:

```text
Markdown fences
leading or trailing commentary
multiple JSON values
unknown top-level fields
schema mismatches
```

There is no Markdown stripping, JSON repair, parse retry, or silent coercion. A model parse failure remains provider evidence rather than being hidden by the evaluator.

## Model adapter

`scripts/eval/phase7_model_pattern_extraction.py` is network-disabled by default. Design execution requires the explicit `--execute-design` flag. The adapter:

- uses only the ten Phase 7.2 design inputs;
- does not include `reference_candidate` in prompts;
- does not access Phase 7.1 held-out cases;
- fixes temperature to `0` and top-p to `1`;
- performs no retry after parser failure;
- stores only parsed candidates and response hashes after successful parsing;
- never stores API credentials or raw response text;
- preserves a blocked execution artifact on authorization failure.

The adapter was not executed against the ten design cases because the provider authorization preflight failed.

## Claim boundary

Phase 7.2.2 establishes:

```text
reproducible provider manifests            yes
canonical prompt frozen                    yes
strict parser behavior tested              yes
repair policy frozen                       yes
scorer policy frozen                       yes
weak baseline row measured                 yes
model row represented without fabrication  yes
```

It does not establish:

```text
LLM extraction quality             no
model superiority                  no
transfer improvement               no
held-out generalization            no
Pattern validation                 no
knowledge formation                no
persistence authority              no
Hermes integration                 no
runtime authority                  no
```

## Artifacts

```text
crates/eval/config/phase7_2_2_canonical_prompt_v1.md
crates/eval/config/phase7_2_2_parser_policy_v1.json
crates/eval/config/phase7_2_2_scorer_policy_v1.json
crates/eval/config/phase7_2_2_provider_manifests.json
crates/eval/reports/phase7_2_2_deepseek_preflight.json
crates/eval/reports/phase7_2_2_model_provider_execution.json
crates/eval/reports/phase7_pattern_provider_comparison.json
crates/eval/src/phase7_pattern_provider_comparison.rs
crates/eval/tests/phase7_pattern_provider_comparison_test.rs
scripts/eval/phase7_model_pattern_extraction.py
scripts/eval/phase7_pattern_provider_comparison.py
```

## Validation

```powershell
cargo test -p synapse-eval --test phase7_pattern_provider_comparison_test --jobs 1 -- --test-threads=1
python scripts/eval/phase7_pattern_provider_comparison.py
```

Expected decision while authorization remains blocked:

```text
comparison_protocol_frozen_model_execution_blocked
```
