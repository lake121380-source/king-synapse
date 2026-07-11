# Phase 7.2.3 Real Provider Readiness Validation

Status: provider readiness complete; candidate quality review required; held-out and runtime remain closed.

## Objective

Phase 7.2.3 answers one bounded question:

> Can one real LLM provider reliably produce evaluable Pattern Candidates under the already frozen Phase 7.2.2 protocol?

It does not evaluate transfer generalization and does not authorize Pattern Candidates as learned knowledge.

The historical boundary is preserved:

```text
Phase 7.2.2  protocol frozen; DeepSeek blocked by authorization
Phase 7.2.3  same protocol; authenticated real-provider design run
```

The Phase 7.2.2 blocked artifacts remain unchanged. The successful execution is stored in independent Phase 7.2.3 artifacts.

## Frozen execution conditions

```text
provider                  deepseek_pattern_extractor_v1
model                     deepseek-v4-flash
prompt                    PatternExtractorPrompt-v1
temperature               0
Top-p                     1
parser                    strict_pattern_candidate_json_v1
repair                    reject only; no automatic repair
retry                     false
dataset                   ten Phase 7.2 design cases only
held-out access           false
primary safety metric     unsupported_claim_rate
```

The run reused the exact Phase 7.2.2 prompt, parser, scorer, dataset, and provider manifest SHA-256 identities. A sanitized preflight recorded HTTP `200` for both the official model-list endpoint and one minimal chat-completion request without recording the API key or raw response text.

## Provider readiness result

```text
design cases                        10
requests attempted                  10
requests completed                  10
strict parser acceptance            1.0000
Pattern Candidate contract validity 1.0000
automatic repair                    false
selective retry                     false
raw response persisted              false
API key recorded                    false
held-out cases accessed             false
```

This closes provider transport and structured-output readiness:

```text
real provider execution readiness  yes
stable evaluable candidate output  yes
```

It does not close cognition or knowledge readiness.

## Quality observations

| Metric | Deterministic weak baseline | DeepSeek real provider |
| --- | ---: | ---: |
| Contract validity | 1.0000 | 1.0000 |
| Evidence attribution accuracy | 1.0000 | 1.0000 |
| Scope preservation | 1.0000 | 0.7000 |
| Counterexample retention | 1.0000 | 1.0000 |
| Unsupported claim rate | 0.0442 | 0.5129 |
| Abstraction distance | 0.3828 | 0.6158 |
| Design-reference token recall | 0.0636 | 0.2604 |

The result demonstrates the permanent Phase 7 distinction:

```text
format correct != cognitively grounded != validated knowledge
```

DeepSeek used more reference-relevant language and produced more abstraction than the transparent weak baseline, but it also introduced substantially more proposition language not directly supported by the authoritative input. Scope preservation fell to `0.7000`, and every design case received at least one deterministic quality diagnostic.

The pre-existing scorer emits `unsupported_language_requires_review` above `0.20`. The observed aggregate rate is `0.5129`, so the report decision is:

```text
provider_ready_candidates_require_quality_review
```

This is a quality diagnostic, not a post-hoc held-out threshold and not a model-ranking claim.

## Claim boundary

Phase 7.2.3 establishes:

```text
real provider authentication                 yes
real provider design execution               yes
strict parser compatibility                  yes
Pattern Candidate contract compatibility     yes
reproducible provider readiness artifact      yes
evaluation framework detects scope loss       yes
evaluation framework detects unsupported text yes
```

It does not establish:

```text
Pattern correctness              no
causal validity                  no
transfer improvement             no
held-out generalization          no
candidate learning authorization no
Pattern persistence              no
knowledge promotion              no
Hermes integration               no
runtime authority                no
```

All outputs remain `PatternStatus::Proposed` cognition artifacts.

## Artifacts

```text
crates/eval/reports/phase7_2_3_deepseek_readiness_preflight.json
crates/eval/reports/phase7_2_3_real_provider_execution.json
crates/eval/reports/phase7_real_provider_readiness.json
crates/eval/src/phase7_real_provider_readiness.rs
crates/eval/src/bin/phase7_real_provider_readiness.rs
crates/eval/tests/phase7_real_provider_readiness_test.rs
scripts/eval/phase7_real_provider_readiness.py
```

The extraction adapter now accepts phase-specific output identity arguments so a future readiness rerun does not overwrite Phase 7.2.2 history:

```powershell
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User")
python scripts/eval/phase7_model_pattern_extraction.py `
  --execute-design `
  --output crates/eval/reports/phase7_2_3_real_provider_execution.json `
  --execution-id phase7.2.3-deepseek-real-provider-readiness-v1
```

The command performs exactly ten design calls, with no held-out access, retry, or automatic repair.

## Validation

```powershell
cargo test -p synapse-eval --test phase7_real_provider_readiness_test -- --nocapture
cargo test -p synapse-eval --test phase7_pattern_provider_comparison_test -- --nocapture
python scripts/eval/phase7_real_provider_readiness.py
```

Expected decision:

```text
provider_ready_candidates_require_quality_review
```
