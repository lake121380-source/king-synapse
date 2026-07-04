# Next Validation Preconditions

Date: 2026-07-04

Status: waiting for hosted external configuration; DMR judge scaling complete

This runbook records what must change before the next heavy Phase 6 validation
run. It is not a product plan and does not permit new memory schema, cognitive
layers, CLI features, runtime defaults, Web demo, API server, Docker, or v0.1
packaging work.

Current gate read:

- `current_system_gate_passed: true`
- `current_work_mode: validation_only`
- `recommended_action: wait_for_hosted_external_configuration_or_no_model_failure_analysis`
- `heavy_validation_allowed: false`
- `productization_allowed: false`

The only allowed work while this page is current is no-model / no-external
evidence maintenance, report synchronization, and configuration checks that do
not change runtime behavior.

## Branch A: Top-Context DMR Judge Scoring

Purpose:

- prove whether the top-context DMR answer generator improves judged answer
  quality, not only lexical or ROUGE-L scores;
- DMR 50, DMR 200, and the 500-request / 323-scored view are now complete;
- preserve the Phase 6 GPU rule.

Current read:

- DMR 50 top-context judge scoring is complete in
  `crates/eval/reports/official-dmr-50-top-context-judge.json`;
- DMR 200 top-context judge scoring is complete in
  `crates/eval/reports/official-dmr-200-top-context-judge.json`;
- DMR 500-request top-context judge scoring is complete in
  `crates/eval/reports/official-dmr-500-top-context-judge.json`;
- the latest sanitized DeepSeek preflight returns `judged` / HTTP `200`;
- do not rerun DMR 50/200/500 by default;
- there is no remaining DMR judge-scaling branch selected by this runbook.

Required external condition:

- `DEEPSEEK_API_KEY` must be valid for `deepseek-v4-flash`;
- `DEEPSEEK_BASE_URL` may override the default DeepSeek endpoint;
- `DEEPSEEK_JUDGE_MODEL` may be set, but the validation target is
  `deepseek-v4-flash`.

Before any reproducibility rerun, prove the judge endpoint without reading DMR
data:

```powershell
python scripts/eval/deepseek_judge_preflight.py `
  --judge-model deepseek-v4-flash `
  --output crates/eval/reports/official-dmr-top-context-judge-preflight.json
```

Then refresh the action gates:

```powershell
python scripts/eval/phase6_next_gate_readiness.py
python scripts/eval/next_validation_action_gate.py
python scripts/eval/phase6_current_system_gate.py
```

The completed DMR 500 reproduction command is:

```powershell
python scripts/eval/official_dmr_eval.py `
  --endpoint https://hf-mirror.com `
  --sample-size 500 `
  --mode vectors-rerank `
  --generator top-context-extractive `
  --llm-judge deepseek `
  --judge-model deepseek-v4-flash `
  --accelerator cuda `
  --cuda-device-id 0 `
  --embed-batch-size 32 `
  --embed-max-length 256 `
  --rerank-batch-size 32 `
  --rerank-max-length 256 `
  --output crates/eval/reports/official-dmr-500-top-context-judge.json `
  --cleanup-cache
```

After a successful run, keep
`crates/eval/reports/official-dmr-500-top-context-judge.json` separate from the
pinned baseline files. Before changing any conclusion, explicitly add that new
report to the DMR answer-synthesis / task-gate evidence path or pass it to the
audit command:

```powershell
python scripts/eval/official_dmr_answer_audit.py `
  --reports `
    crates/eval/reports/official-dmr-50.json `
    crates/eval/reports/official-dmr-50-top-context-judge.json `
    crates/eval/reports/official-dmr-200.json `
    crates/eval/reports/official-dmr-200-top-context-judge.json `
    crates/eval/reports/official-dmr-500.json `
    crates/eval/reports/official-dmr-500-top-context-judge.json
python scripts/eval/dmr_generator_ablation_summary.py
python scripts/eval/official_dmr_bottleneck_taxonomy.py
python scripts/eval/official_dmr_task_gate.py
python scripts/eval/phase6_requirements_audit.py
python scripts/eval/phase6_objective_coverage_audit.py
python scripts/eval/productization_decision_gate.py
python scripts/eval/next_validation_action_gate.py
python scripts/eval/readme_claims_support_audit.py
python scripts/eval/phase6_current_system_gate.py
```

Acceptance read:

- judge preflight status is `judged`;
- no API key, prompt text, raw response, raw DMR record, gold answer, generated
  answer, dialog, session, or temporary cache file is committed;
- DMR 50, DMR 200, and DMR 500-request top-context are recorded as completed
  evidence;
- any README or report claim stays scoped until the task gates support it.

## Branch B: Hosted / Official External Comparison

Purpose:

- replace the current hosted-not-configured boundary with measured competitor
  evidence;
- keep all systems on the same 8-chain cognitive fixture;
- keep unsupported capabilities separate from failures.

Required external conditions:

| System | Required configuration |
| --- | --- |
| Graphiti / Zep | `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`; use `GRAPHITI_BACKEND=neo4j` for the hosted/standard path. |
| Mem0 official path | `OPENAI_API_KEY` or `MEM0_CONFIG_JSON` / `MEM0_CONFIG_PATH`; local DeepSeek fallback alone is not enough for an official-hosted claim. |
| Letta | `letta-client` plus `LETTA_API_KEY`, `LETTA_BASE_URL`, or `LETTA_ENVIRONMENT=local`. |

Refresh readiness before the run:

```powershell
python scripts/eval/phase6_next_gate_readiness.py
python scripts/eval/next_validation_action_gate.py
python scripts/eval/phase6_current_system_gate.py
```

Only if hosted external comparison is allowed, run:

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

After a successful run, update the evidence chain:

```powershell
python scripts/eval/external_comparison_task_gate.py
python scripts/eval/phase6_requirements_audit.py
python scripts/eval/phase6_objective_coverage_audit.py
python scripts/eval/productization_decision_gate.py
python scripts/eval/next_validation_action_gate.py
python scripts/eval/readme_claims_support_audit.py
python scripts/eval/phase6_current_system_gate.py
```

Acceptance read:

- the hosted report still uses the shared 8-chain cognitive fixture;
- unsupported trace surfaces remain `unsupported`, not `failed`;
- not-configured systems remain `not_configured`, not hidden from the report;
- no secret values, raw hosted responses, raw memory content, prompts, or
  adapter temporary files are committed;
- hosted superiority is not claimed unless the hosted/official task gate
  explicitly supports it.

## If No Branch Is Selected

Do not run heavy DMR or hosted external validation. The correct work remains:

- maintain documentation/report consistency;
- keep README claims conservative;
- keep Phase 6 gates green;
- wait for hosted configuration or explicitly select the next DMR expansion
  scope.

Useful no-model / no-external checks:

```powershell
python scripts/eval/phase6_next_gate_readiness.py
python scripts/eval/next_validation_action_gate.py
python scripts/eval/readme_claims_support_audit.py
python scripts/eval/phase6_current_system_gate.py
python -m py_compile scripts/eval/phase6_next_gate_readiness.py scripts/eval/next_validation_action_gate.py scripts/eval/phase6_current_system_gate.py
cargo test -p synapse-eval
```

Before any commit, also scan for accidental secrets:

```powershell
rg -l --hidden --glob '!target/**' --glob '!**/.git/**' "sk-[A-Za-z0-9_-]{16,}" .
```

This command should return no files.
