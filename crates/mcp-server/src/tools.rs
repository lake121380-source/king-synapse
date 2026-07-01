use anyhow::Result;
use serde_json::{json, Value};
use std::str::FromStr;
use std::sync::{Arc, Mutex};
use synapse_core::{
    GraphActivationBooster, LatentActivationContext, LatentActivationProbe, MemoryKind,
    RecallEngine, RecallQuery, Scope, Source, Store, WriteInput,
};

pub type StoreHandle = Arc<Mutex<Store>>;

pub fn descriptors() -> Vec<Value> {
    vec![
        descriptor_write(),
        descriptor_recall(),
        descriptor_list(),
        descriptor_forget(),
        descriptor_entities(),
        descriptor_neighbors(),
        descriptor_edges(),
        descriptor_latent_activation(),
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
                "kind": { "type": "string", "enum": ["fact","preference","failure","playbook","state"] },
                "graph_activation": { "type": "boolean", "default": false },
                "graph_scale": { "type": "number", "default": 0.05 },
                "graph_cap": { "type": "number", "default": 0.15 },
                "graph_steps": { "type": "integer", "minimum": 1, "maximum": 8, "default": 1 },
                "graph_decay": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.5 }
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

fn descriptor_entities() -> Value {
    json!({
        "name": "synapse_entities",
        "description": "List entities extracted from memories (libraries, commands, errors, files, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": { "type": "integer", "minimum": 1, "maximum": 500, "default": 50 }
            }
        }
    })
}

fn descriptor_neighbors() -> Value {
    json!({
        "name": "synapse_neighbors",
        "description": "Return memories that share entities with the given memory id (1-hop graph expansion).",
        "inputSchema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": { "type": "string" },
                "k": { "type": "integer", "minimum": 1, "maximum": 50, "default": 8 }
            }
        }
    })
}

fn descriptor_edges() -> Value {
    json!({
        "name": "synapse_edges",
        "description": "Inspect directed associative edges connected to a memory.",
        "inputSchema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": { "type": "string" },
                "direction": { "type": "string", "enum": ["outgoing", "incoming", "both"], "default": "both" },
                "k": { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 }
            }
        }
    })
}

fn descriptor_latent_activation() -> Value {
    json!({
        "name": "synapse_latent_activation",
        "description": "Probe multi-step latent activation from one memory id without changing recall results.",
        "inputSchema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": { "type": "string" },
                "k": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
                "scale": { "type": "number", "default": 0.05 },
                "cap": { "type": "number", "default": 0.25 },
                "steps": { "type": "integer", "minimum": 1, "maximum": 8, "default": 2 },
                "decay": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.5 },
                "fanout": { "type": "integer", "minimum": 1, "maximum": 200, "default": 16 },
                "state_terms": { "type": "array", "items": { "type": "string" }, "default": [] },
                "goal_terms": { "type": "array", "items": { "type": "string" }, "default": [] }
            }
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
        "synapse_entities" => do_entities(store, &args)?,
        "synapse_neighbors" => do_neighbors(store, &args)?,
        "synapse_edges" => do_edges(store, &args)?,
        "synapse_latent_activation" => do_latent_activation(store, &args)?,
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
    let graph_activation = args
        .get("graph_activation")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let graph_scale = arg_f32(args, "graph_scale", 0.05);
    let graph_cap = arg_f32(args, "graph_cap", 0.15);
    let graph_steps = args
        .get("graph_steps")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(1);
    let graph_decay = arg_f32(args, "graph_decay", 0.5);
    let mut s = store.lock().unwrap();
    let query = RecallQuery {
        query,
        k,
        scope_filter: scope,
        kind_filter: kind,
    };
    let graph_booster = graph_activation.then(|| {
        GraphActivationBooster::with_spreading(graph_scale, graph_cap, graph_steps, graph_decay)
    });
    let hits = {
        let mut engine = RecallEngine::new(&mut s);
        if let Some(booster) = graph_booster.as_ref() {
            engine = engine.with_booster(booster);
        }
        engine.recall(&query)?
    };
    Ok(json!({ "hits": hits }))
}

fn arg_f32(args: &Value, key: &str, default: f32) -> f32 {
    args.get(key)
        .and_then(|v| v.as_f64())
        .map(|x| x as f32)
        .unwrap_or(default)
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

fn do_entities(store: &StoreHandle, args: &Value) -> Result<Value> {
    let limit = args
        .get("limit")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(50);
    let s = store.lock().unwrap();
    let ents = s.list_entities(limit)?;
    Ok(json!({ "entities": ents }))
}

fn do_neighbors(store: &StoreHandle, args: &Value) -> Result<Value> {
    let id = args
        .get("id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("id required"))?
        .to_string();
    let k = args
        .get("k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(8);
    let s = store.lock().unwrap();
    let neighbors = s.neighbors(&id, k)?;
    Ok(json!({ "neighbors": neighbors }))
}

fn do_edges(store: &StoreHandle, args: &Value) -> Result<Value> {
    let id = args
        .get("id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("id required"))?
        .to_string();
    let direction = args
        .get("direction")
        .and_then(|v| v.as_str())
        .unwrap_or("both");
    let k = args
        .get("k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(20);

    let s = store.lock().unwrap();
    let edges = match direction {
        "outgoing" => s.outgoing_edges(&id, k)?,
        "incoming" => s.incoming_edges(&id, k)?,
        "both" => s.memory_edges(&id, k)?,
        other => anyhow::bail!("unsupported edge direction: {other}"),
    };
    Ok(json!({ "edges": edges }))
}

fn do_latent_activation(store: &StoreHandle, args: &Value) -> Result<Value> {
    let id = args
        .get("id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("id required"))?
        .to_string();
    let k = args
        .get("k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(10);
    let scale = arg_f32(args, "scale", 0.05);
    let cap = arg_f32(args, "cap", 0.25);
    let steps = args
        .get("steps")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(2);
    let decay = arg_f32(args, "decay", 0.5);
    let fanout = args
        .get("fanout")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(16);
    let state_terms = string_array(args, "state_terms");
    let goal_terms = string_array(args, "goal_terms");

    let s = store.lock().unwrap();
    let probe = LatentActivationProbe::with_config(scale, cap, steps, decay, fanout);
    let context = LatentActivationContext::new(state_terms, goal_terms);
    let activations = probe.activate_with_context(&s, &[&id], k, &context)?;
    Ok(json!({ "activations": activations }))
}

fn string_array(args: &Value, key: &str) -> Vec<String> {
    args.get(key)
        .and_then(|v| v.as_array())
        .map(|items| {
            items
                .iter()
                .filter_map(|item| item.as_str())
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}
