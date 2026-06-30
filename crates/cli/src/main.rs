use anyhow::{Context, Result};
use chrono::{TimeZone, Utc};
use clap::{Parser, Subcommand};
use std::str::FromStr;
use synapse_core::{config::Config, MemoryKind, RecallQuery, Scope, Source, Store, WriteInput};

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
        } => {
            let q = RecallQuery {
                query,
                k: Some(k),
                scope_filter: scope.map(|s| Scope::from_str(&s)).transpose()?,
                kind_filter: kind.map(|s| MemoryKind::from_str(&s)).transpose()?,
            };
            let hits = store.recall(&q)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&hits)?);
            } else if hits.is_empty() {
                println!("(no matches)");
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
            println!("memories: {}", n);
            println!("db_path:  {}", cfg.db_path.display());
        }
        Cmd::Where => {
            println!("{}", cfg.db_path.display());
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
    println!(
        "[{:.3}] {}  ({}/{}, {})  {}",
        h.score,
        &h.memory.id[..8],
        h.memory.kind,
        h.memory.scope,
        when,
        truncate(&h.memory.content, 100)
    );
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
