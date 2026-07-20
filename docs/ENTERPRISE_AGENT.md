# Enterprise Agent Runtime

Status: **Phase A1 Hermes Agent host available; read-only governed execution**

King Synapse exposes governed enterprise knowledge as a local stdio MCP tool:

```text
synapse_enterprise_shadow
```

The tool is the product-facing promotion of the Phase 8 E4 Shadow evaluator.
It executes inside `synapse-core`, is served by `synapse-mcp`, and preserves the
frozen Runtime Trace v1 fields.

## Configure a Canonical Packet

Set the packet path before starting the MCP server:

```powershell
$env:KING_SYNAPSE_ENTERPRISE_PACKET = "D:\path\to\canonical-retrieval-packet.json"
```

Or add it to the King Synapse TOML config:

```toml
enterprise_packet_path = "D:/path/to/canonical-retrieval-packet.json"
```

The packet is loaded and validated once at startup. Restart the MCP server to
load an append-only successor packet.

The runtime rejects a packet when:

- selected Entry IDs do not match the selected Entry objects;
- a selected Entry is not retrieval-eligible;
- Entry IDs are duplicated;
- mandatory Output Guards are missing;
- source documents are embedded in the packet;
- unadjudicated assertions are embedded in the packet.

For the Agent profile, also set:

```text
KING_SYNAPSE_MCP_TOOL_PROFILE=agent_read_only
```

This server-side profile advertises and accepts only `synapse_recall`,
`synapse_trace`, and `synapse_enterprise_shadow`. It rejects direct calls to
write, reinforce, forget, or other mutating tools.

## MCP Tool

Input:

```json
{
  "question": "公司套餐多少钱？"
}
```

Output shape:

```json
{
  "answer": "当前参考套餐为起步1,980元/月、成长2,980元/月、全能3,980元/月。正式报价、合同范围和交付边界仍需人工确认。",
  "trace": {
    "candidate_entries": [
      {
        "entry_id": "canonical-company-007",
        "score": 2,
        "rank": 1,
        "eligibility": "eligible"
      }
    ],
    "selected_entries": ["canonical-company-007"],
    "excluded_entries": [],
    "applied_guards": [
      "binding_customer_quote_requires_human_confirmation"
    ],
    "evidence_basis": [
      {
        "entry_id": "canonical-company-007",
        "basis": "owner_confirmation"
      }
    ],
    "answer_mode": "shadow_draft",
    "lineage": [
      {
        "output_line": 1,
        "entry_ids": ["canonical-company-007"]
      }
    ],
    "runtime_write": false,
    "source_document_filesystem_read_during_generation": false,
    "external_provider_called": false,
    "candidate_or_network_modified": false,
    "learning_or_reflection": false
  }
}
```

`withheld` is a successful governance result when the question matches only a
suspended or unknown Entry. It must not be converted into a guessed answer by
the Agent host.

## Build and Validate

```powershell
cargo build -p synapse-mcp
cargo test -p synapse-core --test enterprise_shadow_test
cargo test -p synapse-mcp
cargo test -p synapse-mcp --test agent_read_only_stdio_test
```

The Rust runtime is checked against the same 20 frozen governance questions as
the Phase 8 Python Shadow evaluator. Regression covers candidate ranking,
selection, exclusion reasons, guards, answer mode, Evidence Basis, and the
read-only authority boundary.

## Agent Host Boundary

The first Agent host should expose only:

```text
synapse_recall
synapse_trace
synapse_enterprise_shadow
```

`synapse_write`, `synapse_reinforce`, and `synapse_forget` are not exposed to
the Hermes Profile. Observation collection and durable writes require a
separate queue and human approval boundary.

The current product host is Hermes Agent 0.18.2, pinned and installed by
`scripts/agent/setup_hermes_synapse.ps1`. Use either:

```powershell
.\scripts\agent\synapse_chat.ps1 -Prompt "公司套餐多少钱？"
cargo run -p synapse-cli -- chat "公司套餐多少钱？"
```

The host uses only the `king-synapse` toolset, does not pass Hermes `--yolo`,
and does not enable shell, browser, web, or autonomous memory tools. Web Search,
Browser, File/PDF, Observation Queue, and durable writes remain later phases.
