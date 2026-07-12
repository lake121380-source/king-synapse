# Phase 7.3.1-D Heterogeneous AI Reviewer Execution

Status: **two blind AI reviewer submissions and third-model adjudication completed; silver freeze required.**

## Reviewer identities

| Role | Requested model | Resolved model | Family | Claims |
|---|---|---|---|---:|
| Reviewer A | `gpt-4.1` | `gpt-4.1-2025-04-14` | OpenAI | 74 |
| Reviewer B | `qwen3.5-plus` | `qwen3.5-plus` | Alibaba Qwen | 77 |

DeepSeek was excluded because it generated the frozen Pattern Candidates. Reviewer A and B used separate stateless calls and could not see each other, the frozen Judge, Phase 7.3 aggregates, reference Candidates, held-out cases, tools, web, or memory.

These are **heterogeneous model annotations**, not human review. Until a human adjudicator or an explicitly frozen adjudication protocol resolves disagreements, downstream labels must be described as model-reviewed or silver candidates, never human Gold.

## Frozen execution controls

- canonical prompt: `crates/eval/config/phase7_3_1_ai_reviewer_prompt_v1.md`;
- temperature `0`, top-p `1`;
- API `response_format = json_object` for both accepted submissions;
- ten isolated design-case calls per Reviewer;
- strict exact-key and enum validation;
- exact unique excerpt to Unicode scalar half-open span normalization only;
- no semantic repair or raw response persistence;
- no credentials in repository artifacts.

The prompt, packet, guide, and adapter SHA-256 values are recorded in each Reviewer manifest.

## Readiness failures preserved

Claude Sonnet 4.6 and Gemini 3.1 Pro Preview were rejected because their gateway responses were not consistently valid under the strict JSON boundary. Qwen Max failed the exact schema probe. No raw responses or partial submissions were promoted. See `crates/eval/reports/phase7_3_1_ai_reviewer_readiness_attempts.json`.

## Agreement result

```text
Reviewer A claims                         74
Reviewer B claims                         77
Aligned claim pairs                       74
Exact boundary agreement                  0.9091
Mean matched span IoU                     0.9868
Unmatched claim rate                      0.0199
Per-case claim-count correlation          0.9264
Support raw agreement                     0.7647
Support linear weighted kappa             0.3964
Support Krippendorff alpha (ordinal)       0.4604
Boundary disagreements                    14
Fundamental disagreements                 2
Scope agreement                           0.6892
Prediction-support agreement              0.6622
Falsifiability agreement                  0.8243
```

Interpretation: segmentation agreement is high, while semantic support agreement is only moderate after chance correction. The two AI Reviewers are therefore useful for surfacing disagreement, but not sufficient to declare semantic ground truth.

## Current authorization

```text
Agreement Report       frozen
Adjudication            completed, 77/77 groups
Silver labels           not frozen
Judge calibration       blocked
Held-out                blocked
Memory/runtime/Hermes   blocked
```

The independent adjudication now references the exact SHA-256 values of Reviewer A, Reviewer B, and the frozen Agreement Report. The next valid action is an explicit model-adjudicated silver-label freeze.
