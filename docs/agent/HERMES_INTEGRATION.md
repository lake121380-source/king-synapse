# Hermes Agent Integration

Status: **default open-source Agent host selected; read-only integration available**

## Decision

King Synapse uses [Hermes Agent](https://github.com/NousResearch/hermes-agent)
as the first product host. [OpenClaw](https://github.com/openclaw/openclaw)
remains a compatible future adapter, not the v0.1 default.

The setup pins Hermes Agent 0.18.2 at Git tag `v2026.7.7.2`, including its
`mcp` extra, under `%LOCALAPPDATA%\king-synapse`. It does not replace a global
`hermes` command or update an existing Hermes gateway.

The decision was checked against the public projects on 2026-07-20:

| Criterion | Hermes Agent | OpenClaw |
| --- | --- | --- |
| Consume local stdio MCP | Native, documented | Supported through `mcpServers` |
| Per-server tool filtering | Native include/exclude | Supported through MCP/tool policy |
| Isolated user configuration | Named Profile with separate `HERMES_HOME` | Agent workspace/configuration |
| Native Windows CLI | Supported | Supported |
| Fit for current Rust MCP | Direct and small | Capable, but substantially broader |

Hermes is preferred because King Synapse already owns memory and governance.
The Agent host only needs to plan, call the MCP tools, and present the answer.
OpenClaw's channels, apps, gateway, canvas, and device surface are useful later,
but are not required to prove the first governed Agent loop.

## Security boundary

The Hermes profile starts the MCP server with:

```text
KING_SYNAPSE_MCP_TOOL_PROFILE=agent_read_only
```

The server then advertises and accepts only:

```text
synapse_recall
synapse_trace
synapse_enterprise_shadow
```

`synapse_write`, `synapse_reinforce`, `synapse_forget`, and every other tool
are rejected inside the Rust MCP process even if a client attempts to call
them directly. Hermes tool filtering is an additional boundary, not the only
boundary.

The dedicated `kingsynapse` Hermes Profile is created without bundled or user
Skills. The setup copies only `config.yaml` and `.env` from the default Profile
so it can reuse the configured inference provider. It has its own
`HERMES_HOME`, session state, SOUL, MCP configuration, and King Synapse
database. It does not replace or restart the user's default Hermes gateway.

## Setup

From the repository root on Windows:

```powershell
.\scripts\agent\setup_hermes_synapse.ps1
```

The setup script:

1. builds `synapse-mcp`;
2. installs the pinned isolated Hermes Runtime when absent;
3. creates an empty isolated `kingsynapse` Hermes Profile when absent and
   copies only the default Profile's model configuration and environment;
4. installs the governed SOUL;
5. registers the local stdio MCP server with the frozen Canonical Packet;
6. enables all three read-only tools;
7. runs `hermes mcp test king-synapse`.

Use a different Packet or database when needed:

```powershell
.\scripts\agent\setup_hermes_synapse.ps1 `
  -PacketPath D:\private\canonical-packet.json `
  -DatabasePath D:\private\synapse.sqlite
```

## Use

Interactive chat:

```powershell
.\scripts\agent\synapse_chat.ps1
```

Single question:

```powershell
.\scripts\agent\synapse_chat.ps1 -Prompt "公司套餐多少钱？"
```

The launcher explicitly enables only the `king-synapse` MCP toolset. It does
not pass Hermes `--yolo`, does not expose shell/browser/web tools, and does not
enable autonomous Synapse writes.

## Validation

Run the local deterministic checks:

```powershell
cargo test -p synapse-mcp
cargo test -p synapse-core --test enterprise_shadow_test
```

The MCP stdio integration test starts the real `synapse-mcp` binary, checks
the three-tool allowlist, executes all 20 frozen governance cases through
JSON-RPC, compares candidates/selection/exclusions/Guards/answer mode, and
proves that a direct write request is rejected.
