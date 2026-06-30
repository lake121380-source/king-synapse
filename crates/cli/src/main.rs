use anyhow::{Context, Result};
use chrono::{TimeZone, Utc};
use clap::{Parser, Subcommand};
use std::str::FromStr;
use synapse_core::{
    config::Config, MemoryKind, RecallEngine, RecallHit, RecallQuery, Scope, Source, Store,
    WriteInput,
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

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "warn".into()),
        )
        .init();

    let cli = Cli::parse();
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
            let booster_names: Vec<&'static str> = Vec::new();
            let hits = {
                let mut engine = RecallEngine::new(&mut store);
                if let Some(e) = embedder.as_mut() {
                    engine = engine.with_embedder(e);
                }
                if let Some(rr) = reranker.as_mut() {
                    engine = engine.with_reranker(rr, rerank_pool);
                }
                engine.recall(&q)?
            };
            if json {
                println!("{}", serde_json::to_string_pretty(&hits)?);
            } else if hits.is_empty() {
                println!("(no matches)");
            } else if explain {
                for (i, h) in hits.iter().enumerate() {
                    print_hit_explain(i + 1, h, &booster_names);
                }
            } else {
                for h in hits {
                    print_hit(&h);
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
