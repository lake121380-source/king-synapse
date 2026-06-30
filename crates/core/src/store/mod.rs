//! SQLite-backed storage for memories + append-only event log.
//!
//! Phase 0 retrieval is FTS5 BM25 keyword search with a scoring kicker
//! (importance * confidence, exponential time decay).
//! Vector index and spreading activation arrive in later phases.

mod recall;
mod schema;

use crate::error::Result;
use crate::model::{Memory, MemoryKind, RecallQuery, WriteInput};
use chrono::Utc;
use rusqlite::{params, Connection, OptionalExtension};
use std::path::Path;
use std::str::FromStr;
use ulid::Ulid;

pub use recall::RecallHit;

pub struct Store {
    pub(crate) conn: Connection,
}

impl Store {
    pub fn open(path: &Path) -> Result<Self> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = Connection::open(path)?;
        conn.execute_batch(schema::SCHEMA_SQL)?;
        Ok(Store { conn })
    }

    pub fn open_in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        conn.execute_batch(schema::SCHEMA_SQL)?;
        Ok(Store { conn })
    }

    pub fn write(&mut self, input: WriteInput) -> Result<Memory> {
        let id = Ulid::new().to_string();
        let now = Utc::now().timestamp();
        let mem = Memory {
            id: id.clone(),
            kind: input.kind,
            scope: input.scope,
            content: input.content,
            source: input.source,
            confidence: input.confidence.unwrap_or(1.0).clamp(0.0, 1.0),
            importance: input.importance.unwrap_or(0.5).clamp(0.0, 1.0),
            valid_from: now,
            valid_to: None,
            superseded_by: None,
            access_count: 0,
            last_accessed_at: None,
        };

        let tx = self.conn.transaction()?;
        tx.execute(
            "INSERT INTO memories (id, kind, scope, content, source, confidence, importance, valid_from) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                mem.id,
                mem.kind.to_string(),
                mem.scope.to_string(),
                mem.content,
                mem.source.to_string(),
                mem.confidence,
                mem.importance,
                mem.valid_from,
            ],
        )?;

        let event_id = Ulid::new().to_string();
        let payload = serde_json::to_string(&mem)?;
        tx.execute(
            "INSERT INTO events (id, kind, memory_id, payload, actor, created_at) VALUES (?1, 'ADD', ?2, ?3, ?4, ?5)",
            params![event_id, mem.id, payload, mem.source.to_string(), now],
        )?;
        tx.commit()?;
        Ok(mem)
    }

    pub fn get(&self, id: &str) -> Result<Option<Memory>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, kind, scope, content, source, confidence, importance, valid_from, valid_to, superseded_by, access_count, last_accessed_at FROM memories WHERE id = ?1",
        )?;
        let mem = stmt.query_row(params![id], row_to_memory).optional()?;
        Ok(mem)
    }

    pub fn list_recent(&self, limit: usize) -> Result<Vec<Memory>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, kind, scope, content, source, confidence, importance, valid_from, valid_to, superseded_by, access_count, last_accessed_at FROM memories WHERE valid_to IS NULL ORDER BY valid_from DESC LIMIT ?1",
        )?;
        let rows = stmt
            .query_map(params![limit as i64], row_to_memory)?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        Ok(rows)
    }

    pub fn invalidate(&mut self, id: &str, actor: &str) -> Result<()> {
        let now = Utc::now().timestamp();
        let tx = self.conn.transaction()?;
        let updated = tx.execute(
            "UPDATE memories SET valid_to = ?2 WHERE id = ?1 AND valid_to IS NULL",
            params![id, now],
        )?;
        if updated == 0 {
            return Err(crate::error::Error::NotFound(id.to_string()));
        }
        let event_id = Ulid::new().to_string();
        tx.execute(
            "INSERT INTO events (id, kind, memory_id, payload, actor, created_at) VALUES (?1, 'INVALIDATE', ?2, '{}', ?3, ?4)",
            params![event_id, id, actor, now],
        )?;
        tx.commit()?;
        Ok(())
    }

    pub fn recall(&mut self, q: &RecallQuery) -> Result<Vec<RecallHit>> {
        recall::recall(self, q)
    }

    pub fn count(&self) -> Result<i64> {
        let n: i64 = self
            .conn
            .query_row("SELECT COUNT(*) FROM memories", [], |r| r.get(0))?;
        Ok(n)
    }
}

pub(crate) fn row_to_memory(row: &rusqlite::Row) -> rusqlite::Result<Memory> {
    let kind_s: String = row.get(1)?;
    let scope_s: String = row.get(2)?;
    let source_s: String = row.get(4)?;
    let kind = MemoryKind::from_str(&kind_s).map_err(|e| {
        rusqlite::Error::FromSqlConversionFailure(1, rusqlite::types::Type::Text, Box::new(e))
    })?;
    let scope = crate::model::Scope::from_str(&scope_s).map_err(|e| {
        rusqlite::Error::FromSqlConversionFailure(2, rusqlite::types::Type::Text, Box::new(e))
    })?;
    let source = crate::model::Source::from_str(&source_s).map_err(|e| {
        rusqlite::Error::FromSqlConversionFailure(4, rusqlite::types::Type::Text, Box::new(e))
    })?;
    Ok(Memory {
        id: row.get(0)?,
        kind,
        scope,
        content: row.get(3)?,
        source,
        confidence: row.get::<_, f64>(5)? as f32,
        importance: row.get::<_, f64>(6)? as f32,
        valid_from: row.get(7)?,
        valid_to: row.get(8)?,
        superseded_by: row.get(9)?,
        access_count: row.get(10)?,
        last_accessed_at: row.get(11)?,
    })
}

pub(crate) fn decay_lambda(kind: MemoryKind) -> f32 {
    // Half-lives, in days:
    //   STATE      ~1d   -> lambda = ln(2)/1
    //   FAILURE   ~30d
    //   FACT      ~180d
    //   PLAYBOOK  ~180d
    //   PREFERENCE ~365d
    match kind {
        MemoryKind::State => 0.693,
        MemoryKind::Failure => 0.0231,
        MemoryKind::Fact => 0.00385,
        MemoryKind::Playbook => 0.00385,
        MemoryKind::Preference => 0.0019,
    }
}
