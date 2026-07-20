use anyhow::{Context, Result};
use chrono::{TimeZone, Utc};
use clap::{Parser, Subcommand, ValueEnum};
use std::path::PathBuf;
use std::process::Command;
use std::str::FromStr;
use synapse_core::{
    config::Config, AlgorithmContext, CognitiveCompetitionTrace, CognitiveTraceConfig,
    CognitiveTraceEvaluator, CognitiveTracePredictionReport, CognitiveTraceProbe,
    CognitiveTraceReport, DeterministicHebbianStoreMutationDispatcher, GraphActivationBooster,
    HebbianAlgorithm, HebbianExecutor, HebbianTarget, InMemoryMemoryEventStream,
    LatentActivationBooster, LatentActivationContext, LatentActivationProbe, MemoryEvent,
    MemoryEventId, MemoryEventKind, MemoryEventPayload, MemoryEventStream, MemoryKind,
    PersistentStoreExecutor, PlanOnlyHebbianExecutor, QueryLatentActivationProbe,
    QueryLatentActivationReport, RecallBooster, RecallEngine, RecallHit, RecallQuery,
    RuleBasedHebbianAlgorithm, SQLitePersistentStoreExecutor, Scope, Source, Store,
    StoreMutationDispatcher, UniformImportanceEstimator, WriteInput,
};

/// King Synapse CLI -- write, recall, and inspect agent memories.
#[derive(Parser)]
#[command(name = "kr", version, about = "King Synapse memory CLI")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Write a memory.
    Write {
        /// Memory content (the thing you want to remember).
        content: String,

        #[arg(long, default_value = "fact")]
        kind: String,

        #[arg(long, default_value = "global")]
        scope: String,

        #[arg(long, default_value = "explicit_user")]
        source: String,

        #[arg(long)]
        importance: Option<f32>,

        #[arg(long)]
        confidence: Option<f32>,
    },
    /// Recall memories matching a query.
    Recall {
        query: String,
        #[arg(long, short = 'k', default_value = "8")]
        k: usize,
        #[arg(long)]
        scope: Option<String>,
        #[arg(long)]
        kind: Option<String>,
        #[arg(long)]
        json: bool,
        /// Also run the dense vector branch (loads the embedder; first run downloads the model).
        #[arg(long)]
        vectors: bool,
        /// Attach the cross-encoder reranker (BGE-Reranker-Base, ~300MB on first run).
        #[arg(long)]
        rerank: bool,
        /// Candidate pool size passed to the reranker before truncating to top-k.
        #[arg(long, default_value = "50")]
        rerank_pool: usize,
        /// Print full provenance for each hit: per-branch ranks, RRF score,
        /// rerank logit, activation bonus, booster list, final score.
        #[arg(long)]
        explain: bool,
        /// Print an inspection-only cognitive competition trace for the recalled candidates.
        #[arg(long)]
        trace: bool,
        /// Enable Store-backed graph activation over existing recall candidates.
        #[arg(long)]
        graph_activation: bool,
        /// Graph activation scale applied to edge weights.
        #[arg(long, default_value = "0.05")]
        graph_scale: f32,
        /// Maximum graph activation bonus per hit.
        #[arg(long, default_value = "0.15")]
        graph_cap: f32,
        /// Number of decayed graph activation propagation steps.
        #[arg(long, default_value = "1")]
        graph_steps: usize,
        /// Decay factor for graph activation after each propagation step.
        #[arg(long, default_value = "0.5")]
        graph_decay: f32,
        /// Enable latent activation over existing recall candidates.
        #[arg(long)]
        latent_activation: bool,
        /// Number of top visible hits used as latent activation seeds.
        #[arg(long, default_value = "3")]
        latent_seed_k: usize,
        /// Latent activation scale applied to edge weights.
        #[arg(long, default_value = "0.05")]
        latent_scale: f32,
        /// Maximum latent activation contribution per propagation path.
        #[arg(long, default_value = "0.25")]
        latent_cap: f32,
        /// Number of decayed latent activation propagation steps.
        #[arg(long, default_value = "2")]
        latent_steps: usize,
        /// Decay factor for latent activation after each propagation step.
        #[arg(long, default_value = "0.5")]
        latent_decay: f32,
        /// Maximum outgoing edges inspected per latent activation step.
        #[arg(long, default_value = "16")]
        latent_fanout: usize,
        /// Current state terms that should increase matching latent activations.
        #[arg(long = "latent-state")]
        latent_state_terms: Vec<String>,
        /// Current goal terms that should increase matching latent activations.
        #[arg(long = "latent-goal")]
        latent_goal_terms: Vec<String>,
        /// Derive additional latent state/goal terms from the recall query.
        #[arg(long)]
        latent_auto_context: bool,
        /// Learn Hebbian associations between the top recall hits after recall.
        #[arg(long)]
        reinforce: bool,
        /// Number of top recall hits used for optional Hebbian reinforcement.
        #[arg(long, default_value = "3")]
        reinforce_k: usize,
    },
    /// List recent memories.
    List {
        #[arg(long, default_value = "20")]
        limit: usize,
        #[arg(long)]
        json: bool,
    },
    /// Forget (invalidate) a memory by id.
    Forget { id: String },
    /// List known entities (extracted from memory contents).
    Entities {
        #[arg(long, default_value = "50")]
        limit: usize,
        #[arg(long)]
        json: bool,
    },
    /// Show memories that share entities with a given memory id (1-hop neighbors).
    Neighbors {
        id: String,
        #[arg(long, short = 'k', default_value = "8")]
        k: usize,
        #[arg(long)]
        json: bool,
    },
    /// Show directed associative edge weights for a memory.
    Edges {
        id: String,
        #[arg(long, value_enum, default_value = "both")]
        direction: EdgeDirection,
        #[arg(long, short = 'k', default_value = "20")]
        k: usize,
        #[arg(long)]
        json: bool,
    },
    /// Reinforce an association between memories that co-occurred.
    Reinforce {
        /// Memory ids that appeared together.
        ids: Vec<String>,
        /// Event kind used to weight the Hebbian update.
        #[arg(long, value_enum, default_value = "recalled")]
        event: ReinforceEvent,
        /// Query or situation that caused the co-occurrence.
        #[arg(long)]
        query: Option<String>,
        /// Emit the full Hebbian, mutation, and store reports.
        #[arg(long)]
        json: bool,
    },
    /// Probe latent multi-step activation from one memory id.
    Latent {
        id: String,
        #[arg(long, short = 'k', default_value = "10")]
        k: usize,
        #[arg(long, default_value = "0.05")]
        scale: f32,
        #[arg(long, default_value = "0.25")]
        cap: f32,
        #[arg(long, default_value = "2")]
        steps: usize,
        #[arg(long, default_value = "0.5")]
        decay: f32,
        #[arg(long, default_value = "16")]
        fanout: usize,
        /// Current state terms that should increase matching latent activations.
        #[arg(long = "state")]
        state_terms: Vec<String>,
        /// Current goal terms that should increase matching latent activations.
        #[arg(long = "goal")]
        goal_terms: Vec<String>,
        #[arg(long)]
        json: bool,
    },
    /// Recall visible seed memories for a query, then probe their latent activation.
    LatentQuery {
        query: String,
        #[arg(long, short = 'k', default_value = "10")]
        k: usize,
        #[arg(long, default_value = "3")]
        seed_k: usize,
        #[arg(long)]
        scope: Option<String>,
        #[arg(long)]
        kind: Option<String>,
        #[arg(long, default_value = "0.05")]
        scale: f32,
        #[arg(long, default_value = "0.25")]
        cap: f32,
        #[arg(long, default_value = "2")]
        steps: usize,
        #[arg(long, default_value = "0.5")]
        decay: f32,
        #[arg(long, default_value = "16")]
        fanout: usize,
        #[arg(long = "state")]
        state_terms: Vec<String>,
        #[arg(long = "goal")]
        goal_terms: Vec<String>,
        /// Derive additional state/goal terms from the query text.
        #[arg(long)]
        auto_context: bool,
        #[arg(long)]
        json: bool,
    },
    /// Trace the dominant thought, suppressed candidates, and latent influences for a query.
    Trace {
        query: String,
        /// Number of visible recall candidates to inspect.
        #[arg(long, short = 'k', default_value = "8")]
        k: usize,
        /// Number of latent activation candidates to inspect.
        #[arg(long = "latent-k", default_value = "10")]
        latent_k: usize,
        /// Number of top visible hits used as latent activation seeds.
        #[arg(long, default_value = "3")]
        seed_k: usize,
        /// Number of non-dominant candidates to report as suppressed.
        #[arg(long, default_value = "7")]
        suppressed_k: usize,
        #[arg(long)]
        scope: Option<String>,
        #[arg(long)]
        kind: Option<String>,
        #[arg(long, default_value = "0.05")]
        scale: f32,
        #[arg(long, default_value = "0.25")]
        cap: f32,
        #[arg(long, default_value = "2")]
        steps: usize,
        #[arg(long, default_value = "0.5")]
        decay: f32,
        #[arg(long, default_value = "16")]
        fanout: usize,
        #[arg(long = "state")]
        state_terms: Vec<String>,
        #[arg(long = "goal")]
        goal_terms: Vec<String>,
        /// Derive additional state/goal terms from the query text.
        #[arg(long)]
        auto_context: bool,
        /// Learn Hebbian associations between visible seed memories and the dominant trace candidate after tracing.
        #[arg(long)]
        reinforce: bool,
        /// Number of top visible trace seeds used for optional Hebbian reinforcement.
        #[arg(long, default_value = "3")]
        reinforce_k: usize,
        /// Predict likely next hidden candidates from the dominant trace candidate.
        #[arg(long)]
        predict: bool,
        /// Number of predicted continuation candidates to report.
        #[arg(long, default_value = "5")]
        prediction_k: usize,
        #[arg(long)]
        json: bool,
    },
    /// Chat through the isolated Hermes Agent host using only governed Synapse tools.
    Chat {
        /// Optional one-shot question. Omit it to start an interactive chat.
        prompt: Option<String>,
        /// Isolated Hermes Profile created by setup_hermes_synapse.ps1.
        #[arg(long, default_value = "kingsynapse")]
        profile: String,
        /// Maximum Agent tool-call iterations per turn.
        #[arg(long, default_value = "12")]
        max_turns: usize,
    },
    /// Show daemon stats.
    Stats,
    /// Show where the database is.
    Where,
    /// Compute embeddings for memories that don't have one yet.
    ///
    /// First run downloads the ~470MB multilingual-e5-base model into the
    /// fastembed cache (override with `FASTEMBED_CACHE_DIR`).
    EmbedBackfill {
        /// Memories per inference batch.
        #[arg(long, default_value = "16")]
        batch: usize,
        /// Maximum memories to embed this run; 0 means "drain the queue".
        #[arg(long, default_value = "0")]
        max: usize,
    },
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum EdgeDirection {
    Outgoing,
    Incoming,
    Both,
}

#[derive(Clone, Copy, Debug, ValueEnum)]
#[value(rename_all = "snake_case")]
enum ReinforceEvent {
    Recalled,
    Written,
    Updated,
    Reflected,
    Reinforced,
    MergeCompleted,
}

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "warn".into()),
        )
        .init();

    let cli = Cli::parse();
    if let Cmd::Chat {
        prompt,
        profile,
        max_turns,
    } = &cli.cmd
    {
        return launch_hermes_chat(prompt.as_deref(), profile, *max_turns);
    }
    let cfg = Config::load_or_default().context("loading config")?;
    cfg.ensure_db_dir()?;
    let mut store = Store::open(&cfg.db_path).context("opening store")?;

    match cli.cmd {
        Cmd::Write {
            content,
            kind,
            scope,
            source,
            importance,
            confidence,
        } => {
            let kind = MemoryKind::from_str(&kind)?;
            let scope = Scope::from_str(&scope)?;
            let source = Source::from_str(&source)?;
            let mem = store.write(WriteInput {
                content,
                kind,
                scope,
                source,
                confidence,
                importance,
            })?;
            println!("written {}", mem.id);
        }
        Cmd::Recall {
            query,
            k,
            scope,
            kind,
            json,
            vectors,
            rerank,
            rerank_pool,
            explain,
            trace,
            graph_activation,
            graph_scale,
            graph_cap,
            graph_steps,
            graph_decay,
            latent_activation,
            latent_seed_k,
            latent_scale,
            latent_cap,
            latent_steps,
            latent_decay,
            latent_fanout,
            latent_state_terms,
            latent_goal_terms,
            latent_auto_context,
            reinforce,
            reinforce_k,
        } => {
            let q = RecallQuery {
                query,
                k: Some(k),
                scope_filter: scope.map(|s| Scope::from_str(&s)).transpose()?,
                kind_filter: kind.map(|s| MemoryKind::from_str(&s)).transpose()?,
            };
            let mut embedder = if vectors {
                Some(synapse_core::Embedder::new().context("loading embedder")?)
            } else {
                None
            };
            let mut reranker = if rerank {
                Some(synapse_core::FastEmbedReranker::new().context("loading reranker")?)
            } else {
                None
            };
            let graph_booster = graph_activation.then(|| {
                GraphActivationBooster::with_spreading(
                    graph_scale,
                    graph_cap,
                    graph_steps,
                    graph_decay,
                )
            });
            let latent_context = latent_recall_context(
                &q.query,
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
            let booster_names: Vec<&'static str> = graph_booster
                .iter()
                .map(|booster| booster.name())
                .chain(latent_booster.iter().map(|booster| booster.name()))
                .collect();
            let hits = {
                let mut engine = RecallEngine::new(&mut store);
                if let Some(e) = embedder.as_mut() {
                    engine = engine.with_embedder(e);
                }
                if let Some(rr) = reranker.as_mut() {
                    engine = engine.with_reranker(rr, rerank_pool);
                }
                if let Some(booster) = graph_booster.as_ref() {
                    engine = engine.with_booster(booster);
                }
                if let Some(booster) = latent_booster.as_ref() {
                    engine = engine.with_booster(booster);
                }
                engine.recall(&q)?
            };
            let reinforcement = if reinforce {
                reinforce_recall_hits(&mut store, &hits, reinforce_k, &q.query)?
            } else {
                None
            };
            let cognitive_trace = trace.then(|| CognitiveTraceEvaluator::evaluate(&q.query, &hits));
            if json {
                if cognitive_trace.is_some() || reinforcement.is_some() {
                    let mut payload = serde_json::Map::new();
                    payload.insert("hits".to_string(), serde_json::to_value(&hits)?);
                    if let Some(trace) = cognitive_trace.as_ref() {
                        payload.insert("cognitive_trace".to_string(), serde_json::to_value(trace)?);
                    }
                    if let Some(reinforcement) = reinforcement.as_ref() {
                        payload.insert(
                            "reinforcement".to_string(),
                            serde_json::to_value(reinforcement)?,
                        );
                    }
                    println!("{}", serde_json::to_string_pretty(&payload)?);
                } else {
                    println!("{}", serde_json::to_string_pretty(&hits)?);
                }
            } else if hits.is_empty() {
                println!("(no matches)");
                if let Some(trace) = cognitive_trace.as_ref() {
                    print_cognitive_competition_trace(trace);
                }
            } else if explain {
                for (i, h) in hits.iter().enumerate() {
                    print_hit_explain(i + 1, h, &booster_names);
                }
                if let Some(trace) = cognitive_trace.as_ref() {
                    print_cognitive_competition_trace(trace);
                }
                if let Some(reinforcement) = reinforcement.as_ref() {
                    print_reinforcement_summary(reinforcement);
                }
            } else {
                for h in &hits {
                    print_hit(h);
                }
                if let Some(trace) = cognitive_trace.as_ref() {
                    print_cognitive_competition_trace(trace);
                }
                if let Some(reinforcement) = reinforcement.as_ref() {
                    print_reinforcement_summary(reinforcement);
                }
            }
        }
        Cmd::List { limit, json } => {
            let mems = store.list_recent(limit)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&mems)?);
            } else if mems.is_empty() {
                println!("(empty)");
            } else {
                for m in mems {
                    println!(
                        "{}  [{}/{}]  {}",
                        m.id,
                        m.kind,
                        m.scope,
                        truncate(&m.content, 80)
                    );
                }
            }
        }
        Cmd::Forget { id } => {
            store.invalidate(&id, "cli")?;
            println!("invalidated {}", id);
        }
        Cmd::Entities { limit, json } => {
            let ents = store.list_entities(limit)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&ents)?);
            } else if ents.is_empty() {
                println!("(no entities)");
            } else {
                for e in ents {
                    println!("[{}] {}  ({})", e.kind, e.name, e.normalized);
                }
            }
        }
        Cmd::Neighbors { id, k, json } => {
            let neighbors = store.neighbors(&id, k)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&neighbors)?);
            } else if neighbors.is_empty() {
                println!("(no neighbors)");
            } else {
                for m in neighbors {
                    println!(
                        "{}  [{}/{}]  {}",
                        &m.id[..8],
                        m.kind,
                        m.scope,
                        truncate(&m.content, 90)
                    );
                }
            }
        }
        Cmd::Edges {
            id,
            direction,
            k,
            json,
        } => {
            let edges = match direction {
                EdgeDirection::Outgoing => store.outgoing_edges(&id, k)?,
                EdgeDirection::Incoming => store.incoming_edges(&id, k)?,
                EdgeDirection::Both => store.memory_edges(&id, k)?,
            };
            if json {
                println!("{}", serde_json::to_string_pretty(&edges)?);
            } else if edges.is_empty() {
                println!("(no edges)");
            } else {
                for edge in edges {
                    print_edge(&edge);
                }
            }
        }
        Cmd::Reinforce {
            ids,
            event,
            query,
            json,
        } => {
            let report = reinforce_memories(&mut store, ids, event, query)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&report)?);
            } else {
                println!(
                    "reinforced {} edge updates ({} skipped)",
                    report["store_report"]["statistics"]["executed"]
                        .as_u64()
                        .unwrap_or(0),
                    report["store_report"]["statistics"]["skipped"]
                        .as_u64()
                        .unwrap_or(0)
                );
            }
        }
        Cmd::Latent {
            id,
            k,
            scale,
            cap,
            steps,
            decay,
            fanout,
            state_terms,
            goal_terms,
            json,
        } => {
            let probe = LatentActivationProbe::with_config(scale, cap, steps, decay, fanout);
            let context = LatentActivationContext::new(state_terms, goal_terms);
            let hits = probe.activate_with_context(&store, &[&id], k, &context)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&hits)?);
            } else if hits.is_empty() {
                println!("(no latent activations)");
            } else {
                for hit in hits {
                    print_latent_hit(&hit);
                }
            }
        }
        Cmd::LatentQuery {
            query,
            k,
            seed_k,
            scope,
            kind,
            scale,
            cap,
            steps,
            decay,
            fanout,
            state_terms,
            goal_terms,
            auto_context,
            json,
        } => {
            let q = RecallQuery {
                query,
                k: None,
                scope_filter: scope.map(|s| Scope::from_str(&s)).transpose()?,
                kind_filter: kind.map(|s| MemoryKind::from_str(&s)).transpose()?,
            };
            let latent_probe = LatentActivationProbe::with_config(scale, cap, steps, decay, fanout);
            let query_probe = QueryLatentActivationProbe::new(latent_probe, seed_k);
            let context = LatentActivationContext::new(state_terms, goal_terms);
            let report = if auto_context {
                query_probe.probe_auto_context(&mut store, &q, k, &context)?
            } else {
                query_probe.probe(&mut store, &q, k, &context)?
            };
            if json {
                println!("{}", serde_json::to_string_pretty(&report)?);
            } else {
                print_query_latent_report(&report);
            }
        }
        Cmd::Trace {
            query,
            k,
            latent_k,
            seed_k,
            suppressed_k,
            scope,
            kind,
            scale,
            cap,
            steps,
            decay,
            fanout,
            state_terms,
            goal_terms,
            auto_context,
            reinforce,
            reinforce_k,
            predict,
            prediction_k,
            json,
        } => {
            let q = RecallQuery {
                query,
                k: Some(k),
                scope_filter: scope.map(|s| Scope::from_str(&s)).transpose()?,
                kind_filter: kind.map(|s| MemoryKind::from_str(&s)).transpose()?,
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
                probe.trace_auto_context(&mut store, &q, &context)?
            } else {
                probe.trace(&mut store, &q, &context)?
            };
            let reinforcement = if reinforce {
                reinforce_trace_report(&mut store, &report, reinforce_k, &q.query)?
            } else {
                None
            };
            let prediction = if predict {
                Some(probe.predict_continuation(&store, &report, prediction_k)?)
            } else {
                None
            };
            if json {
                if prediction.is_some() || reinforcement.is_some() {
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&serde_json::json!({
                            "report": report,
                            "prediction": prediction,
                            "reinforcement": reinforcement,
                        }))?
                    );
                } else {
                    println!("{}", serde_json::to_string_pretty(&report)?);
                }
            } else {
                print_cognitive_trace_report(&report);
                if let Some(prediction) = prediction.as_ref() {
                    print_cognitive_trace_prediction(prediction);
                }
                if let Some(reinforcement) = reinforcement.as_ref() {
                    print_reinforcement_summary(reinforcement);
                }
            }
        }
        Cmd::Chat { .. } => unreachable!("chat is handled before the memory store is opened"),
        Cmd::Stats => {
            let n = store.count()?;
            let (done, pending) = store.embedding_stats()?;
            println!("memories:    {}", n);
            println!("embeddings:  {} done / {} pending", done, pending);
            println!("db_path:     {}", cfg.db_path.display());
        }
        Cmd::Where => {
            println!("{}", cfg.db_path.display());
        }
        Cmd::EmbedBackfill { batch, max } => {
            let batch = batch.max(1);
            let (done0, pending0) = store.embedding_stats()?;
            if pending0 == 0 {
                println!("nothing pending ({} done)", done0);
                return Ok(());
            }
            eprintln!(
                "{} pending, loading embedder (first run downloads ~470MB)...",
                pending0
            );
            let mut emb = synapse_core::Embedder::new().context("loading embedder")?;
            eprintln!("model: {} (dim={})", emb.model_name(), emb.dim());

            let mut total = 0usize;
            loop {
                let limit = if max == 0 {
                    batch
                } else {
                    batch.min(max.saturating_sub(total))
                };
                if limit == 0 {
                    break;
                }
                let pending = store.pending_embeddings(limit)?;
                if pending.is_empty() {
                    break;
                }
                let texts: Vec<&str> = pending.iter().map(|(_, c)| c.as_str()).collect();
                let vecs = emb.embed_documents(&texts).context("embedding batch")?;
                for ((id, _), v) in pending.iter().zip(vecs.iter()) {
                    store.put_embedding(id, emb.model_name(), v)?;
                    total += 1;
                }
                eprintln!("embedded {total}");
                if max != 0 && total >= max {
                    break;
                }
            }
            let (done, pending) = store.embedding_stats()?;
            println!("embedded {total} this run. now: {done} done / {pending} pending");
        }
    }
    Ok(())
}

fn launch_hermes_chat(prompt: Option<&str>, profile: &str, max_turns: usize) -> Result<()> {
    if profile.is_empty()
        || !profile
            .chars()
            .all(|character| character.is_ascii_lowercase() || character.is_ascii_digit())
    {
        anyhow::bail!("Hermes profile must contain only lowercase ASCII letters and digits");
    }

    let local_app_data = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .context("LOCALAPPDATA is required; run scripts/agent/setup_hermes_synapse.ps1")?;
    let hermes = local_app_data
        .join("king-synapse")
        .join("bin")
        .join(if cfg!(windows) {
            "hermes.exe"
        } else {
            "hermes"
        });
    if !hermes.is_file() {
        anyhow::bail!(
            "isolated Hermes runtime not found at {}; run scripts/agent/setup_hermes_synapse.ps1",
            hermes.display()
        );
    }

    let user_home = std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .context("user home directory is unavailable")?;
    let profile_home = user_home.join(".hermes").join("profiles").join(profile);
    if !profile_home.join("config.yaml").is_file() {
        anyhow::bail!(
            "Hermes profile {profile} is not configured; run scripts/agent/setup_hermes_synapse.ps1"
        );
    }

    let integration_root = find_agent_integration_root()?;
    let mut command = Command::new(&hermes);
    command
        .current_dir(integration_root)
        .env("HERMES_HOME", profile_home)
        .args([
            "chat",
            "--toolsets",
            "king-synapse",
            "--max-turns",
            &max_turns.max(1).to_string(),
            "--source",
            "king-synapse",
        ]);
    if let Some(prompt) = prompt {
        command.args(["--query", prompt, "--quiet"]);
    }

    let status = command.status().context("starting isolated Hermes Agent")?;
    if !status.success() {
        anyhow::bail!("Hermes Agent exited with status {status}");
    }
    Ok(())
}

fn find_agent_integration_root() -> Result<PathBuf> {
    if let Some(root) = std::env::var_os("KING_SYNAPSE_HOME").map(PathBuf::from) {
        let integration = root.join("integrations").join("hermes");
        if integration.join("AGENTS.md").is_file() {
            return Ok(integration);
        }
    }

    let mut search_roots = vec![std::env::current_dir()?];
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            search_roots.push(parent.to_path_buf());
        }
    }
    for search_root in search_roots {
        for ancestor in search_root.ancestors() {
            let integration = ancestor.join("integrations").join("hermes");
            if integration.join("AGENTS.md").is_file() {
                return Ok(integration);
            }
        }
    }
    anyhow::bail!(
        "cannot locate integrations/hermes/AGENTS.md; run from the King Synapse repository or set KING_SYNAPSE_HOME"
    )
}

fn reinforce_memories(
    store: &mut Store,
    ids: Vec<String>,
    event: ReinforceEvent,
    query: Option<String>,
) -> Result<serde_json::Value> {
    let ids = normalize_reinforce_ids(ids);
    if ids.len() < 2 {
        anyhow::bail!("reinforce requires at least two distinct memory ids");
    }

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
        kind: event.memory_event_kind(),
        memory_ids: ids.clone(),
        payload: event.payload(query, ids.len()),
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

    Ok(serde_json::json!({
        "hebbian_output": output,
        "hebbian_report": hebbian_report,
        "mutation_plan": mutation_plan,
        "store_report": store_report,
    }))
}

fn reinforce_recall_hits(
    store: &mut Store,
    hits: &[RecallHit],
    reinforce_k: usize,
    query: &str,
) -> Result<Option<serde_json::Value>> {
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

    reinforce_memories(
        store,
        ids,
        ReinforceEvent::Recalled,
        Some(query.to_string()),
    )
    .map(Some)
}

fn reinforce_trace_report(
    store: &mut Store,
    report: &CognitiveTraceReport,
    reinforce_k: usize,
    query: &str,
) -> Result<Option<serde_json::Value>> {
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

    reinforce_memories(
        store,
        ids,
        ReinforceEvent::Recalled,
        Some(format!("trace:{query}")),
    )
    .map(Some)
}

fn print_reinforcement_summary(report: &serde_json::Value) {
    let executed = report["store_report"]["statistics"]["executed"]
        .as_u64()
        .unwrap_or(0);
    let skipped = report["store_report"]["statistics"]["skipped"]
        .as_u64()
        .unwrap_or(0);
    println!("reinforced {executed} edge updates ({skipped} skipped)");
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

impl ReinforceEvent {
    fn memory_event_kind(self) -> MemoryEventKind {
        match self {
            Self::Recalled => MemoryEventKind::Recalled,
            Self::Written => MemoryEventKind::Written,
            Self::Updated => MemoryEventKind::Updated,
            Self::Reflected => MemoryEventKind::Reflected,
            Self::Reinforced => MemoryEventKind::Reinforced,
            Self::MergeCompleted => MemoryEventKind::MergeCompleted,
        }
    }

    fn payload(self, query: Option<String>, memory_count: usize) -> MemoryEventPayload {
        match self {
            Self::Recalled => MemoryEventPayload::Recalled {
                query: query.unwrap_or_default(),
                hit_count: memory_count,
            },
            Self::Reinforced => MemoryEventPayload::Reinforced {
                edge_key: query.unwrap_or_default(),
                delta: 0.0,
            },
            Self::MergeCompleted => MemoryEventPayload::MergeCompleted {
                into: query.unwrap_or_default(),
            },
            Self::Written | Self::Updated | Self::Reflected => MemoryEventPayload::Empty,
        }
    }
}

fn print_edge(edge: &synapse_core::MemoryEdge) {
    let when = Utc
        .timestamp_opt(edge.updated_at, 0)
        .single()
        .map(|t| t.format("%Y-%m-%d %H:%M").to_string())
        .unwrap_or_default();
    println!(
        "{} -> {}  [{}, w={:.3}, {}]",
        short_id(&edge.source),
        short_id(&edge.target),
        edge.edge,
        edge.weight,
        when
    );
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

fn print_latent_hit(hit: &synapse_core::LatentActivationHit) {
    let path = hit
        .path
        .iter()
        .map(|id| short_id(id).to_string())
        .collect::<Vec<_>>()
        .join(" -> ");
    let matched = if hit.matched_terms.is_empty() {
        String::new()
    } else {
        format!("  match={}", hit.matched_terms.join(","))
    };
    println!(
        "[{:.4} depth={} mod={:.2}] {}  path={}{}  {}",
        hit.activation,
        hit.depth,
        hit.modulation,
        short_id(&hit.memory.id),
        path,
        matched,
        truncate(&hit.memory.content, 90)
    );
}

fn print_query_latent_report(report: &QueryLatentActivationReport) {
    if !report.context.state_terms.is_empty() || !report.context.goal_terms.is_empty() {
        println!(
            "Context: state=[{}] goal=[{}]",
            report.context.state_terms.join(","),
            report.context.goal_terms.join(",")
        );
    }

    if report.seeds.is_empty() {
        println!("Seeds: (none)");
    } else {
        println!("Seeds:");
        for hit in &report.seeds {
            println!(
                "  [{:.3}] {}  {}",
                hit.score,
                short_id(&hit.memory.id),
                truncate(&hit.memory.content, 90)
            );
        }
    }

    if report.activations.is_empty() {
        println!("Latent: (none)");
    } else {
        println!("Latent:");
        for hit in &report.activations {
            print!("  ");
            print_latent_hit(hit);
        }
    }
}

fn print_cognitive_trace_report(report: &CognitiveTraceReport) {
    if !report.context.state_terms.is_empty() || !report.context.goal_terms.is_empty() {
        println!(
            "Context: state=[{}] goal=[{}]",
            report.context.state_terms.join(","),
            report.context.goal_terms.join(",")
        );
    }

    if let Some(candidate) = report.dominant.as_ref() {
        println!("Dominant:");
        print_trace_candidate(candidate, "  ");
    } else {
        println!("Dominant: (none)");
    }

    if report.suppressed.is_empty() {
        println!("Suppressed: (none)");
    } else {
        println!("Suppressed:");
        for candidate in &report.suppressed {
            print_trace_candidate(candidate, "  ");
        }
    }

    println!(
        "Stats: visible={} latent={} combined={} suppressed={}",
        report.statistics.visible_candidates,
        report.statistics.latent_candidates,
        report.statistics.combined_candidates,
        report.statistics.suppressed_candidates
    );
}

fn print_cognitive_trace_prediction(report: &CognitiveTracePredictionReport) {
    if let Some(seed) = report.seed.as_ref() {
        println!("Prediction seed:");
        print_trace_candidate(seed, "  ");
    } else {
        println!("Prediction seed: (none)");
    }

    if report.candidates.is_empty() {
        println!("Prediction: (none)");
    } else {
        println!("Prediction:");
        for hit in &report.candidates {
            print!("  ");
            print_latent_hit(hit);
        }
    }
    println!(
        "Prediction stats: candidates={}",
        report.statistics.candidates
    );
}

fn print_trace_candidate(candidate: &synapse_core::CognitiveTraceCandidate, prefix: &str) {
    let visible = candidate
        .visible_score
        .map(|score| format!("{score:.4}"))
        .unwrap_or_else(|| "-".to_string());
    let latent = candidate
        .latent_activation
        .map(|activation| format!("{activation:.4}"))
        .unwrap_or_else(|| "-".to_string());
    let rank = candidate
        .visible_rank
        .map(|rank| rank.to_string())
        .unwrap_or_else(|| "-".to_string());
    let path = if candidate.latent_path.is_empty() {
        String::new()
    } else {
        format!(
            " path={}",
            candidate
                .latent_path
                .iter()
                .map(|id| short_id(id).to_string())
                .collect::<Vec<_>>()
                .join(" -> ")
        )
    };
    let matched = if candidate.matched_terms.is_empty() {
        String::new()
    } else {
        format!(" match={}", candidate.matched_terms.join(","))
    };

    println!(
        "{prefix}[{:.4} src={:?} rank={} visible={} latent={} inhibit={:.4}] {}{}{}  {}",
        candidate.combined_score,
        candidate.source,
        rank,
        visible,
        latent,
        candidate.inhibition,
        short_id(&candidate.memory.id),
        path,
        matched,
        truncate(&candidate.memory.content, 90)
    );
}

fn print_cognitive_competition_trace(trace: &CognitiveCompetitionTrace) {
    println!();
    println!("Cognitive Competition Trace:");
    println!("Candidates:");
    println!("{}", trace.candidate_count);
    println!();
    println!("Dominant:");
    println!(
        "{}",
        trace
            .dominant_candidate
            .as_deref()
            .map(short_id)
            .unwrap_or("(none)")
    );
    println!();
    println!("Influence:");
    if let Some(dominant) = trace.dominant_candidate.as_ref() {
        for factor in trace
            .factors
            .iter()
            .filter(|factor| &factor.candidate_id == dominant)
        {
            println!("+ {:?} ({:.4})", factor.factor_type, factor.contribution);
        }
    } else {
        println!("(none)");
    }
    println!();
    println!("Suppressed:");
    if trace.suppressed_candidates.is_empty() {
        println!("(none)");
    } else {
        for candidate in &trace.suppressed_candidates {
            println!("{}", short_id(candidate));
        }
    }
    println!();
    println!("Confidence:");
    println!("{:.4}", trace.confidence);
}

fn print_hit(h: &synapse_core::RecallHit) {
    let when = Utc
        .timestamp_opt(h.memory.valid_from, 0)
        .single()
        .map(|t| t.format("%Y-%m-%d %H:%M").to_string())
        .unwrap_or_default();
    let mut sources = String::new();
    for s in &h.sources {
        sources.push(s.glyph());
    }
    if h.rerank_score.is_some() {
        sources.push('R');
    }
    let rerank = h
        .rerank_score
        .map(|s| format!(" rr={:.2}", s))
        .unwrap_or_default();
    println!(
        "[{:.3} {:<4}] {}  ({}/{}, {}){}  {}",
        h.score,
        sources,
        &h.memory.id[..8],
        h.memory.kind,
        h.memory.scope,
        when,
        rerank,
        truncate(&h.memory.content, 100)
    );
}

fn short_id(id: &str) -> &str {
    id.get(..8).unwrap_or(id)
}

fn print_hit_explain(idx: usize, h: &RecallHit, booster_names: &[&'static str]) {
    let when = Utc
        .timestamp_opt(h.memory.valid_from, 0)
        .single()
        .map(|t| t.format("%Y-%m-%d %H:%M").to_string())
        .unwrap_or_default();
    println!(
        "#{idx} {}  [{}/{}, {}]",
        h.memory.id, h.memory.kind, h.memory.scope, when
    );
    println!("    {}", truncate(&h.memory.content, 120));
    let mut srcs = String::new();
    for s in &h.sources {
        if !srcs.is_empty() {
            srcs.push(' ');
        }
        srcs.push(s.glyph());
    }
    if srcs.is_empty() {
        srcs.push('-');
    }
    println!("    Sources:          {}", srcs);
    println!("    FTS Rank:         {}", fmt_rank(h.fts_rank));
    println!(
        "    Entity Rank:      {}  (hits={})",
        fmt_rank(h.entity_rank),
        h.entity_hits
    );
    println!("    Vector Rank:      {}", fmt_rank(h.vector_rank));
    println!("    RRF Score:        {:.4}", h.rrf_score);
    println!(
        "    Rerank Score:     {}",
        h.rerank_score
            .map(|s| format!("{:.4}", s))
            .unwrap_or_else(|| "-".into())
    );
    println!("    Activation Bonus: {:+.4}", h.activation_bonus);
    if booster_names.is_empty() {
        println!("    Boosters:         (none)");
    } else {
        println!("    Boosters:         {}", booster_names.join(", "));
    }
    println!("    Final Score:      {:.4}", h.score);
    println!();
}

fn fmt_rank(r: Option<u32>) -> String {
    r.map(|n| n.to_string()).unwrap_or_else(|| "-".into())
}

fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let mut out: String = s.chars().take(max).collect();
        out.push_str("...");
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn write_memory(store: &mut Store, content: &str) -> synapse_core::Memory {
        store
            .write(WriteInput {
                content: content.to_string(),
                kind: MemoryKind::Fact,
                scope: Scope::Global,
                source: Source::ExplicitUser,
                confidence: Some(1.0),
                importance: Some(0.7),
            })
            .unwrap()
    }

    #[test]
    fn recall_reinforcement_learns_only_top_k_cooccurrence_edges() {
        let mut store = Store::open_in_memory().unwrap();
        write_memory(&mut store, "forgot water before commute");
        write_memory(&mut store, "commute attention risk");
        write_memory(&mut store, "commute package manager note");
        let q = RecallQuery {
            query: "commute".to_string(),
            k: Some(3),
            scope_filter: None,
            kind_filter: None,
        };
        let hits = RecallEngine::new(&mut store).recall(&q).unwrap();
        assert_eq!(hits.len(), 3);
        let first = hits[0].memory.id.clone();
        let second = hits[1].memory.id.clone();
        let third = hits[2].memory.id.clone();

        let report = reinforce_recall_hits(&mut store, &hits, 2, "forgot water commute")
            .unwrap()
            .expect("two top hits should reinforce");

        assert_eq!(
            report["store_report"]["statistics"]["executed"]
                .as_u64()
                .unwrap(),
            2
        );
        assert!(store.edge_weight(&first, &second).unwrap().is_some());
        assert!(store.edge_weight(&second, &first).unwrap().is_some());
        assert!(store.edge_weight(&first, &third).unwrap().is_none());
    }

    #[test]
    fn recall_reinforcement_skips_when_top_k_is_too_small() {
        let mut store = Store::open_in_memory().unwrap();
        write_memory(&mut store, "single");
        let q = RecallQuery {
            query: "single".to_string(),
            k: Some(1),
            scope_filter: None,
            kind_filter: None,
        };
        let hits = RecallEngine::new(&mut store).recall(&q).unwrap();

        let report = reinforce_recall_hits(&mut store, &hits, 2, "single").unwrap();

        assert!(report.is_none());
    }

    #[test]
    fn trace_reinforcement_learns_visible_seed_to_dominant_edges() {
        let mut store = Store::open_in_memory().unwrap();
        let seed = write_memory(&mut store, "forgot water before commute").id;
        let visible = write_memory(&mut store, "forgot water calendar note").id;
        let hidden = write_memory(&mut store, "tired attention failure").id;
        store.update_edge(&seed, &hidden, 2.0).unwrap();

        let q = RecallQuery {
            query: "forgot water".to_string(),
            k: Some(2),
            scope_filter: None,
            kind_filter: None,
        };
        let probe = CognitiveTraceProbe::new(CognitiveTraceConfig {
            visible_limit: 2,
            latent_limit: 4,
            seed_limit: 2,
            suppressed_limit: 4,
            latent_scale: 0.05,
            latent_cap: 0.25,
            latent_steps: 2,
            latent_decay: 0.5,
            latent_fanout: 10,
        });
        let context =
            LatentActivationContext::new(vec!["tired".to_string()], vec!["attention".to_string()]);
        let report = probe.trace(&mut store, &q, &context).unwrap();
        assert_eq!(report.dominant.as_ref().unwrap().memory.id, hidden);

        let reinforcement = reinforce_trace_report(&mut store, &report, 2, "forgot water")
            .unwrap()
            .expect("trace should reinforce visible seeds and dominant candidate");

        assert_eq!(
            reinforcement["store_report"]["statistics"]["executed"]
                .as_u64()
                .unwrap(),
            6
        );
        assert!(store.edge_weight(&seed, &hidden).unwrap().is_some());
        assert!(store.edge_weight(&hidden, &seed).unwrap().is_some());
        assert!(store.edge_weight(&visible, &hidden).unwrap().is_some());
        assert!(store.edge_weight(&hidden, &visible).unwrap().is_some());
    }

    #[test]
    fn trace_reinforcement_skips_when_disabled_by_k() {
        let mut store = Store::open_in_memory().unwrap();
        write_memory(&mut store, "forgot water before commute");
        let hidden = write_memory(&mut store, "tired attention failure").id;
        let q = RecallQuery {
            query: "forgot water".to_string(),
            k: Some(1),
            scope_filter: None,
            kind_filter: None,
        };
        let probe = CognitiveTraceProbe::new(CognitiveTraceConfig::default());
        let report = probe
            .trace(
                &mut store,
                &q,
                &LatentActivationContext::new(vec!["tired".to_string()], Vec::new()),
            )
            .unwrap();

        let reinforcement = reinforce_trace_report(&mut store, &report, 0, "forgot water").unwrap();

        assert!(reinforcement.is_none());
        assert!(store.incoming_edges(&hidden, 10).unwrap().is_empty());
    }

    #[test]
    fn trace_prediction_uses_dominant_candidate_as_seed() {
        let mut store = Store::open_in_memory().unwrap();
        let seed = write_memory(&mut store, "forgot water before commute").id;
        let hidden = write_memory(&mut store, "tired attention failure").id;
        let future = write_memory(&mut store, "future commute attention risk").id;
        store.update_edge(&seed, &hidden, 2.0).unwrap();
        store.update_edge(&hidden, &future, 2.0).unwrap();

        let q = RecallQuery {
            query: "forgot water".to_string(),
            k: Some(1),
            scope_filter: None,
            kind_filter: None,
        };
        let probe = CognitiveTraceProbe::new(CognitiveTraceConfig {
            visible_limit: 1,
            latent_limit: 4,
            seed_limit: 1,
            suppressed_limit: 4,
            latent_scale: 0.05,
            latent_cap: 0.25,
            latent_steps: 2,
            latent_decay: 0.5,
            latent_fanout: 10,
        });
        let context = LatentActivationContext::new(
            vec!["future".to_string()],
            vec!["commute".to_string(), "attention".to_string()],
        );
        let report = probe.trace(&mut store, &q, &context).unwrap();
        assert_eq!(report.dominant.as_ref().unwrap().memory.id, hidden);

        let prediction = probe.predict_continuation(&store, &report, 3).unwrap();

        assert_eq!(
            prediction.seed.as_ref().map(|seed| seed.memory.id.as_str()),
            Some(hidden.as_str())
        );
        assert_eq!(prediction.candidates[0].memory.id, future);
    }
}
