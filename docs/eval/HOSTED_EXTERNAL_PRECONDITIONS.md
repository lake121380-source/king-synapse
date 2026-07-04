# Hosted External Preconditions

Date: 2026-07-04

Status: precondition audit, not a hosted comparison result

Machine-readable report:

`crates/eval/reports/hosted-external-preconditions.json`

Runner:

`scripts/eval/hosted_external_preconditions_audit.py`

## Question

Can Phase 6 run the hosted/official external comparison right now?

Current answer:

`No.`

The audit passes because the blocked state is well-defined, not because hosted
comparison is complete.

## Current Environment Boundary

| System | Required hosted/official mode | Current state |
| --- | --- | --- |
| King Synapse | Current standard local configuration on the shared fixture. | Measured. |
| Graphiti/Zep | Hosted or standard Neo4j/OpenAI path. | Not configured. |
| Mem0 | Official/recommended OpenAI config or explicit `MEM0_CONFIG_JSON/PATH`. | Not configured for hosted/official mode. |
| Letta | Hosted API or local endpoint. | Not configured. |

The current environment has `DEEPSEEK_API_KEY`, but that is not enough for this
hosted/official comparison gate.

DeepSeek remains valid for:

- DMR judge evidence;
- local Mem0 OSS fallback evidence.

DeepSeek-only fallback is **not** counted as:

- hosted Graphiti/Zep;
- official/recommended Mem0;
- live Letta.

## Required Configuration

| Gate | Required configuration |
| --- | --- |
| Graphiti/Zep | `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` |
| Mem0 official | `OPENAI_API_KEY`, or explicit `MEM0_CONFIG_JSON`, or explicit `MEM0_CONFIG_PATH` |
| Letta | `LETTA_API_KEY`, or `LETTA_BASE_URL`, or `LETTA_ENVIRONMENT=local` |

No secret values should be committed. Reports should record presence and
configuration names only.

## Run Command Once Ready

```powershell
cargo run -p synapse-eval --bin kr-external-eval -- `
  --graphiti-command python `
  --graphiti-arg scripts/eval/graphiti_adapter.py `
  --mem0-command python `
  --mem0-arg scripts/eval/mem0_adapter.py `
  --letta-command python `
  --letta-arg scripts/eval/letta_adapter.py `
  --json crates/eval/reports/external-comparison-hosted.json
```

After a real hosted run, refresh the gates:

```powershell
python scripts/eval/phase6_next_gate_readiness.py
python scripts/eval/hosted_external_preconditions_audit.py
python scripts/eval/external_comparison_task_gate.py
python scripts/eval/phase6_requirements_audit.py
python scripts/eval/phase6_objective_coverage_audit.py
python scripts/eval/productization_decision_gate.py
python scripts/eval/phase6_current_system_gate.py
```

## Phase 6 Decision

Hosted external comparison remains open.

This is not an adapter failure:

- the hosted probe has one measured system, King Synapse;
- Graphiti/Zep, Mem0, and Letta are `not_configured`;
- failed systems remain `0`;
- secret values are not recorded.

So the correct current decision is:

`wait for hosted competitor configuration or continue no-model failure analysis`

This does not start Phase 7.
