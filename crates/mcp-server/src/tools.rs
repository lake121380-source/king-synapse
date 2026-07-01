use anyhow::Result;
use chrono::Utc;
use serde_json::{json, Value};
use std::str::FromStr;
use std::sync::{Arc, Mutex};
use synapse_core::{
    AlgorithmContext, CognitiveTraceConfig, CognitiveTraceProbe,
    DeterministicHebbianStoreMutationDispatcher, GraphActivationBooster, HebbianAlgorithm,
    HebbianExecutor, HebbianTarget, InMemoryMemoryEventStream, LatentActivationBooster,
    LatentActivationContext, LatentActivationProbe, MemoryEvent, MemoryEventId, MemoryEventKind,
    MemoryEventPayload, MemoryEventStream, MemoryKind, PersistentStoreExecutor,
    PlanOnlyHebbianExecutor, QueryLatentActivationProbe, RecallEngine, RecallQuery,
    RuleBasedHebbianAlgorithm, SQLitePersistentStoreExecutor, Scope, Source, Store,
    StoreMutationDispatcher, UniformImportanceEstimator, WriteInput,
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
        descriptor_reinforce(),
        descriptor_latent_activation(),
        descriptor_latent_query(),
        descriptor_trace(),
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
                "graph_decay": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.5 },
                "latent_activation": { "type": "boolean", "default": false },
                "latent_seed_k": { "type": "integer", "minimum": 1, "maximum": 16, "default": 3 },
                "latent_scale": { "type": "number", "default": 0.05 },
                "latent_cap": { "type": "number", "default": 0.25 },
                "latent_steps": { "type": "integer", "minimum": 1, "maximum": 8, "default": 2 },
                "latent_decay": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.5 },
                "latent_fanout": { "type": "integer", "minimum": 1, "maximum": 64, "default": 16 },
                "latent_state": { "type": "array", "items": { "type": "string" }, "default": [] },
                "latent_goal": { "type": "array", "items": { "type": "string" }, "default": [] },
                "latent_auto_context": { "type": "boolean", "default": false },
                "reinforce": { "type": "boolean", "default": false },
                "reinforce_k": { "type": "integer", "minimum": 2, "maximum": 16, "default": 3 }
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

fn descriptor_reinforce() -> Value {
    json!({
        "name": "synapse_reinforce",
        "description": "Learn directed associative edges from memories that co-occurred in one event.",
        "inputSchema": {
            "type": "object",
            "required": ["ids"],
            "properties": {
                "ids": { "type": "array", "items": { "type": "string" }, "minItems": 2 },
                "event": { "type": "string", "enum": ["recalled", "written", "updated", "reflected", "reinforced", "merge_completed"], "default": "recalled" },
                "query": { "type": "string", "description": "Query, situation, edge key, or merge target associated with the event." }
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
                "goal_terms": { "type": "array", "items": { "type": "string" }, "default": [] },
                "auto_context": { "type": "boolean", "default": false }
            }
        }
    })
}

fn descriptor_latent_query() -> Value {
    json!({
        "name": "synapse_latent_query",
        "description": "Recall visible seed memories for a query, then probe their latent multi-step activation.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": { "type": "string" },
                "k": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
                "seed_k": { "type": "integer", "minimum": 1, "maximum": 20, "default": 3 },
                "scope": { "type": "string" },
                "kind": { "type": "string", "enum": ["fact","preference","failure","playbook","state"] },
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

fn descriptor_trace() -> Value {
    json!({
        "name": "synapse_trace",
        "description": "Trace the dominant memory candidate, suppressed candidates, and latent influences for a query.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": { "type": "string" },
                "k": { "type": "integer", "minimum": 1, "maximum": 50, "default": 8 },
                "latent_k": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
                "seed_k": { "type": "integer", "minimum": 1, "maximum": 20, "default": 3 },
                "suppressed_k": { "type": "integer", "minimum": 0, "maximum": 50, "default": 7 },
                "scope": { "type": "string" },
                "kind": { "type": "string", "enum": ["fact","preference","failure","playbook","state"] },
                "scale": { "type": "number", "default": 0.05 },
                "cap": { "type": "number", "default": 0.25 },
                "steps": { "type": "integer", "minimum": 1, "maximum": 8, "default": 2 },
                "decay": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.5 },
                "fanout": { "type": "integer", "minimum": 1, "maximum": 200, "default": 16 },
                "state_terms": { "type": "array", "items": { "type": "string" }, "default": [] },
                "goal_terms": { "type": "array", "items": { "type": "string" }, "default": [] },
                "auto_context": { "type": "boolean", "default": false },
                "reinforce": { "type": "boolean", "default": false },
                "reinforce_k": { "type": "integer", "minimum": 1, "maximum": 16, "default": 3 }
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
        "synapse_reinforce" => do_reinforce(store, &args)?,
        "synapse_latent_activation" => do_latent_activation(store, &args)?,
        "synapse_latent_query" => do_latent_query(store, &args)?,
        "synapse_trace" => do_trace(store, &args)?,
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
    let latent_activation = args
        .get("latent_activation")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let latent_seed_k = args
        .get("latent_seed_k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(3);
    let latent_scale = arg_f32(args, "latent_scale", 0.05);
    let latent_cap = arg_f32(args, "latent_cap", 0.25);
    let latent_steps = args
        .get("latent_steps")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(2);
    let latent_decay = arg_f32(args, "latent_decay", 0.5);
    let latent_fanout = args
        .get("latent_fanout")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(16);
    let latent_state_terms = arg_string_array(args, "latent_state");
    let latent_goal_terms = arg_string_array(args, "latent_goal");
    let latent_auto_context = args
        .get("latent_auto_context")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let reinforce = args
        .get("reinforce")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let reinforce_k = args
        .get("reinforce_k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(3);
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
    let latent_context = latent_recall_context(
        &query.query,
        latent_state_terms,
        latent_goal_terms,
        latent_auto_context,
    );
    let latent_booster = latent_activation.then(|| {
        LatentActivationBooster::with_config(
            latent_scale,
            latent_cap,
            latent_steps,
            latent_decay,
            latent_fanout,
            latent_seed_k,
            latent_context,
        )
    });
    let hits = {
        let mut engine = RecallEngine::new(&mut s);
        if let Some(booster) = graph_booster.as_ref() {
            engine = engine.with_booster(booster);
        }
        if let Some(booster) = latent_booster.as_ref() {
            engine = engine.with_booster(booster);
        }
        engine.recall(&query)?
    };
    let reinforcement = if reinforce {
        reinforce_recall_hits(&mut s, &hits, reinforce_k, &query.query)?
    } else {
        None
    };
    Ok(json!({ "hits": hits, "reinforcement": reinforcement }))
}

fn arg_f32(args: &Value, key: &str, default: f32) -> f32 {
    args.get(key)
        .and_then(|v| v.as_f64())
        .map(|x| x as f32)
        .unwrap_or(default)
}

fn arg_string_array(args: &Value, key: &str) -> Vec<String> {
    args.get(key)
        .and_then(|value| value.as_array())
        .map(|values| {
            values
                .iter()
                .filter_map(|value| value.as_str())
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

fn latent_recall_context(
    query: &str,
    state_terms: Vec<String>,
    goal_terms: Vec<String>,
    auto_context: bool,
) -> LatentActivationContext {
    let explicit = LatentActivationContext::new(state_terms, goal_terms);
    if auto_context {
        LatentActivationContext::from_text(query).merge(explicit)
    } else {
        explicit
    }
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

fn do_reinforce(store: &StoreHandle, args: &Value) -> Result<Value> {
    let ids = args
        .get("ids")
        .and_then(|value| value.as_array())
        .ok_or_else(|| anyhow::anyhow!("ids required"))?
        .iter()
        .filter_map(|value| value.as_str())
        .map(str::to_string)
        .collect::<Vec<_>>();
    let ids = normalize_reinforce_ids(ids);
    if ids.len() < 2 {
        anyhow::bail!("synapse_reinforce requires at least two distinct memory ids");
    }

    let event = args
        .get("event")
        .and_then(|value| value.as_str())
        .unwrap_or("recalled");
    let query = args
        .get("query")
        .and_then(|value| value.as_str())
        .map(str::to_string);

    let mut s = store.lock().unwrap();
    reinforce_memory_ids(&mut s, ids, event, query)
}

fn reinforce_recall_hits(
    store: &mut Store,
    hits: &[synapse_core::RecallHit],
    reinforce_k: usize,
    query: &str,
) -> Result<Option<Value>> {
    if reinforce_k < 2 {
        return Ok(None);
    }

    let ids = hits
        .iter()
        .take(reinforce_k)
        .map(|hit| hit.memory.id.clone())
        .collect::<Vec<_>>();
    if ids.len() < 2 {
        return Ok(None);
    }

    reinforce_memory_ids(store, ids, "recalled", Some(query.to_string())).map(Some)
}

fn reinforce_memory_ids(
    store: &mut Store,
    ids: Vec<String>,
    event: &str,
    query: Option<String>,
) -> Result<Value> {
    for id in &ids {
        match store.get(id)? {
            Some(memory) if memory.valid_to.is_none() => {}
            Some(_) => anyhow::bail!("memory is inactive: {id}"),
            None => anyhow::bail!("memory not found: {id}"),
        }
    }

    let now = Utc::now();
    let memory_event = MemoryEvent {
        id: MemoryEventId::new(),
        timestamp: now,
        session_id: None,
        kind: reinforce_event_kind(event)?,
        memory_ids: ids.clone(),
        payload: reinforce_payload(event, query, ids.len())?,
    };
    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(1);
    events.record(memory_event.clone());
    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let output = RuleBasedHebbianAlgorithm::default()
        .reinforce(&HebbianTarget::new(vec![memory_event]), &ctx);
    let hebbian_report = PlanOnlyHebbianExecutor.execute(output.plans());
    let mutation_plan =
        DeterministicHebbianStoreMutationDispatcher::new(hebbian_report.clone()).dispatch();
    let store_report = SQLitePersistentStoreExecutor::new(store).execute(&mutation_plan);

    Ok(json!({
        "hebbian_output": output,
        "hebbian_report": hebbian_report,
        "mutation_plan": mutation_plan,
        "store_report": store_report
    }))
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

fn do_latent_query(store: &StoreHandle, args: &Value) -> Result<Value> {
    let query = args
        .get("query")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("query required"))?
        .to_string();
    let k = args
        .get("k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(10);
    let seed_k = args
        .get("seed_k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(3);
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
    let auto_context = args
        .get("auto_context")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    let mut s = store.lock().unwrap();
    let query = RecallQuery {
        query,
        k: None,
        scope_filter: scope,
        kind_filter: kind,
    };
    let latent_probe = LatentActivationProbe::with_config(scale, cap, steps, decay, fanout);
    let query_probe = QueryLatentActivationProbe::new(latent_probe, seed_k);
    let context = LatentActivationContext::new(state_terms, goal_terms);
    let report = if auto_context {
        query_probe.probe_auto_context(&mut s, &query, k, &context)?
    } else {
        query_probe.probe(&mut s, &query, k, &context)?
    };
    Ok(json!({ "report": report }))
}

fn do_trace(store: &StoreHandle, args: &Value) -> Result<Value> {
    let query = args
        .get("query")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow::anyhow!("query required"))?
        .to_string();
    let k = args
        .get("k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(8);
    let latent_k = args
        .get("latent_k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(10);
    let seed_k = args
        .get("seed_k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(3);
    let suppressed_k = args
        .get("suppressed_k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(7);
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
    let auto_context = args
        .get("auto_context")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let reinforce = args
        .get("reinforce")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let reinforce_k = args
        .get("reinforce_k")
        .and_then(|v| v.as_u64())
        .map(|x| x as usize)
        .unwrap_or(3);

    let mut s = store.lock().unwrap();
    let query = RecallQuery {
        query,
        k: Some(k),
        scope_filter: scope,
        kind_filter: kind,
    };
    let probe = CognitiveTraceProbe::new(CognitiveTraceConfig {
        visible_limit: k,
        latent_limit: latent_k,
        seed_limit: seed_k,
        suppressed_limit: suppressed_k,
        latent_scale: scale,
        latent_cap: cap,
        latent_steps: steps,
        latent_decay: decay,
        latent_fanout: fanout,
    });
    let context = LatentActivationContext::new(state_terms, goal_terms);
    let report = if auto_context {
        probe.trace_auto_context(&mut s, &query, &context)?
    } else {
        probe.trace(&mut s, &query, &context)?
    };
    let reinforcement = if reinforce {
        reinforce_trace_report(&mut s, &report, reinforce_k, &query.query)?
    } else {
        None
    };

    Ok(json!({ "report": report, "reinforcement": reinforcement }))
}

fn reinforce_trace_report(
    store: &mut Store,
    report: &synapse_core::CognitiveTraceReport,
    reinforce_k: usize,
    query: &str,
) -> Result<Option<Value>> {
    if reinforce_k == 0 {
        return Ok(None);
    }

    let Some(dominant) = report.dominant.as_ref() else {
        return Ok(None);
    };

    let mut ids = report
        .visible
        .iter()
        .take(reinforce_k)
        .map(|hit| hit.memory.id.clone())
        .collect::<Vec<_>>();
    ids.push(dominant.memory.id.clone());
    let ids = normalize_reinforce_ids(ids);
    if ids.len() < 2 {
        return Ok(None);
    }

    reinforce_memory_ids(store, ids, "recalled", Some(format!("trace:{query}"))).map(Some)
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

fn normalize_reinforce_ids(ids: Vec<String>) -> Vec<String> {
    let mut out = ids
        .into_iter()
        .map(|id| id.trim().to_string())
        .filter(|id| !id.is_empty())
        .collect::<Vec<_>>();
    out.sort();
    out.dedup();
    out
}

fn reinforce_event_kind(event: &str) -> Result<MemoryEventKind> {
    match event {
        "recalled" => Ok(MemoryEventKind::Recalled),
        "written" => Ok(MemoryEventKind::Written),
        "updated" => Ok(MemoryEventKind::Updated),
        "reflected" => Ok(MemoryEventKind::Reflected),
        "reinforced" => Ok(MemoryEventKind::Reinforced),
        "merge_completed" => Ok(MemoryEventKind::MergeCompleted),
        other => anyhow::bail!("unsupported reinforce event: {other}"),
    }
}

fn reinforce_payload(
    event: &str,
    value: Option<String>,
    memory_count: usize,
) -> Result<MemoryEventPayload> {
    match event {
        "recalled" => Ok(MemoryEventPayload::Recalled {
            query: value.unwrap_or_default(),
            hit_count: memory_count,
        }),
        "reinforced" => Ok(MemoryEventPayload::Reinforced {
            edge_key: value.unwrap_or_default(),
            delta: 0.0,
        }),
        "merge_completed" => Ok(MemoryEventPayload::MergeCompleted {
            into: value.unwrap_or_default(),
        }),
        "written" | "updated" | "reflected" => Ok(MemoryEventPayload::Empty),
        other => anyhow::bail!("unsupported reinforce event: {other}"),
    }
}
