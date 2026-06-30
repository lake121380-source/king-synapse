use anyhow::Result;
use serde_json::{json, Value};
use std::str::FromStr;
use std::sync::{Arc, Mutex};
use synapse_core::{MemoryKind, RecallQuery, Scope, Source, Store, WriteInput};

pub type StoreHandle = Arc<Mutex<Store>>;

pub fn descriptors() -> Vec<Value> {
    vec![
        descriptor_write(),
        descriptor_recall(),
        descriptor_list(),
        descriptor_forget(),
    ]
}

fn descriptor_write() -> Value {
    json!({
        "name": "synapse_write",
        "description": "Persist a memory (fact / preference / failure / playbook / state).",
        "inputSchema": {
            "type": "object",
            "required": ["content"],
            "properties": {
                "content": { "type": "string", "description": "What to remember" },
                "kind": { "type": "string", "enum": ["fact","preference","failure","playbook","state"], "default": "fact" },
                "scope": { "type": "string", "description": "global | user | project:<id> | file:<path> | session:<id>", "default": "global" },
                "source": { "type": "string", "enum": ["explicit_user","agent_self","extracted_from_turn","imported"], "default": "agent_self" },
                "importance": { "type": "number", "minimum": 0, "maximum": 1 },
                "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
            }
        }
    })
}

fn descriptor_recall() -> Value {
    json!({
        "name": "synapse_recall",
        "description": "Recall memories matching a natural language query. Returns scored hits.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": { "type": "string" },
                "k": { "type": "integer", "minimum": 1, "maximum": 50, "default": 8 },
                "scope": { "type": "string" },
                "kind": { "type": "string", "enum": ["fact","preference","failure","playbook","state"] }
            }
        }
    })
}

fn descriptor_list() -> Value {
    json!({
        "name": "synapse_list_recent",
        "description": "List most-recently written memories.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 }
            }
        }
    })
}

fn descriptor_forget() -> Value {
    json!({
        "name": "synapse_forget",
        "description": "Invalidate a memory by id. Soft-delete; the event log is preserved.",
        "inputSchema": {
            "type": "object",
            "required": ["id"],
            "properties": { "id": { "type": "string" } }
        }
    })
}

pub fn call(store: &StoreHandle, params: &Value) -> Result<Value> {
    let name = params
        .get("name")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("missing tool name"))?;
    let args = params.get("arguments").cloned().unwrap_or(json!({}));

    let result = match name {
        "synapse_write" => do_write(store, &args)?,
        "synapse_recall" => do_recall(store, &args)?,
        "synapse_list_recent" => do_list(store, &args)?,
        "synapse_forget" => do_forget(store, &args)?,
        other => anyhow::bail!("unknown tool: {other}"),
    };
    Ok(json!({
        "content": [{ "type": "text", "text": serde_json::to_string_pretty(&result)? }],
        "structuredContent": result,
        "isError": false
    }))
}

fn do_write(store: &StoreHandle, args: &Value) -> Result<Value> {
    let content = args
        .get("content")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("content required"))?
        .to_string();
    let kind = MemoryKind::from_str(args.get("kind").and_then(|v| v.as_str()).unwrap_or("fact"))?;
    let scope = Scope::from_str(
        args.get("scope")
            .and_then(|v| v.as_str())
            .unwrap_or("global"),
    )?;
    let source = Source::from_str(
        args.get("source")
            .and_then(|v| v.as_str())
            .unwrap_or("agent_self"),
    )?;
    let importance = args
        .get("importance")
        .and_then(|v| v.as_f64())
        .map(|x| x as f32);
    let confidence = args
        .get("confidence")
        .and_then(|v| v.as_f64())
        .map(|x| x as f32);

    let mut s = store.lock().unwrap();
    let mem = s.write(WriteInput {
        content,
        kind,
        scope,
        source,
        confidence,
        importance,
    })?;
    Ok(json!({ "id": mem.id, "memory": mem }))
}

fn do_recall(store: &StoreHandle, args: &Value) -> Result<Value> {
    let query = args
        .get("query")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("query required"))?
        .to_string();
    let k = args.get("k").and_then(|v| v.as_u64()).map(|x| x as usize);
    let scope = args
        .get("scope")
        .and_then(|v| v.as_str())
        .map(Scope::from_str)
        .transpose()?;
    let kind = args
        .get("kind")
        .and_then(|v| v.as_str())
        .map(MemoryKind::from_str)
        .transpose()?;
    let mut s = store.lock().unwrap();
    let hits = s.recall(&RecallQuery {
        query,
        k,
        scope_filter: scope,
        kind_filter: kind,
    })?;
    Ok(json!({ "hits": hits }))
}

fn do_list(store: &StoreHandle, args: &Value) -> Result<Value> {
    let limit = args
        .get("limit")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(20);
    let s = store.lock().unwrap();
    let mems = s.list_recent(limit)?;
    Ok(json!({ "memories": mems }))
}

fn do_forget(store: &StoreHandle, args: &Value) -> Result<Value> {
    let id = args
        .get("id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("id required"))?
        .to_string();
    let mut s = store.lock().unwrap();
    s.invalidate(&id, "mcp")?;
    Ok(json!({ "ok": true, "id": id }))
}
