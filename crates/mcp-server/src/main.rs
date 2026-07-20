//! King Synapse MCP server over stdio (JSON-RPC 2.0, line-delimited).
//!
//! Implements the minimal slice of MCP 2024-11-05 that opencode and
//! Claude Code need today: `initialize`, `tools/list`, `tools/call`.

mod rpc;
mod tools;

use anyhow::Result;
use rpc::{JsonRpcError, JsonRpcRequest, JsonRpcResponse};
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};
use synapse_core::{config::Config, EnterpriseShadowEngine, Store};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

const PROTOCOL_VERSION: &str = "2024-11-05";

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_writer(std::io::stderr)
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .init();

    let cfg = Config::load_or_default()?;
    let tool_profile = tools::ToolProfile::from_env()?;
    cfg.ensure_db_dir()?;
    let store: tools::StoreHandle = Arc::new(Mutex::new(Store::open(&cfg.db_path)?));
    let enterprise = cfg
        .enterprise_packet_path
        .as_ref()
        .map(EnterpriseShadowEngine::from_path)
        .transpose()?
        .map(Arc::new);

    tracing::info!(
        db = %cfg.db_path.display(),
        tool_profile = tool_profile.as_str(),
        "king-synapse MCP server starting"
    );
    if let Some(engine) = enterprise.as_deref() {
        tracing::info!(
            packet_id = engine.packet_id(),
            packet_sha256 = engine.packet_sha256(),
            "enterprise shadow packet loaded"
        );
    }

    let stdin = tokio::io::stdin();
    let mut reader = BufReader::new(stdin).lines();
    let mut stdout = tokio::io::stdout();

    while let Some(line) = reader.next_line().await? {
        let line = line.trim_start_matches('\u{feff}');
        if line.trim().is_empty() {
            continue;
        }
        let req: JsonRpcRequest = match serde_json::from_str(line) {
            Ok(r) => r,
            Err(e) => {
                tracing::warn!("bad json-rpc input: {e}");
                continue;
            }
        };

        let is_notification = req.id.is_none();
        let id = req.id.clone().unwrap_or(Value::Null);
        let method = req.method.clone();
        let result = handle(&store, enterprise.as_deref(), tool_profile, &req);

        if is_notification {
            continue;
        }

        let resp = match result {
            Ok(v) => JsonRpcResponse {
                jsonrpc: "2.0",
                id,
                result: Some(v),
                error: None,
            },
            Err(e) => JsonRpcResponse {
                jsonrpc: "2.0",
                id,
                result: None,
                error: Some(JsonRpcError {
                    code: -32000,
                    message: format!("{e}"),
                    data: None,
                }),
            },
        };

        let s = serde_json::to_string(&resp)?;
        tracing::debug!(method = %method, "responding");
        stdout.write_all(s.as_bytes()).await?;
        stdout.write_all(b"\n").await?;
        stdout.flush().await?;
    }
    Ok(())
}

fn handle(
    store: &tools::StoreHandle,
    enterprise: Option<&EnterpriseShadowEngine>,
    tool_profile: tools::ToolProfile,
    req: &JsonRpcRequest,
) -> Result<Value> {
    match req.method.as_str() {
        "initialize" => Ok(json!({
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": { "tools": {} },
            "serverInfo": { "name": "king-synapse", "version": env!("CARGO_PKG_VERSION") }
        })),
        "notifications/initialized" => Ok(Value::Null),
        "tools/list" => Ok(json!({ "tools": tools::descriptors(tool_profile) })),
        "tools/call" => tools::call(store, enterprise, tool_profile, &req.params),
        "ping" => Ok(json!({})),
        other => anyhow::bail!("method not found: {other}"),
    }
}
