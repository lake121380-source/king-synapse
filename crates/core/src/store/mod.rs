//! SQLite-backed storage for memories + append-only event log.
//!
//! Phase 1 adds entity nodes and `MENTIONS` edges built automatically
//! from extracted entities. Recall now does keyword + 1-hop entity
//! expansion fused.

mod branches;
mod recall;
mod schema;

use crate::entity::{Entity, EntityRef, EntityType};
use crate::error::Result;
use crate::extract;
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

        let entities = extract::extract(&mem.content);

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

        for er in &entities {
            let normalized = er.normalized();
            let etype = er.kind.to_string();
            tx.execute(
                "INSERT OR IGNORE INTO entities (id, type, name, normalized, created_at) VALUES (?1, ?2, ?3, ?4, ?5)",
                params![Ulid::new().to_string(), etype, er.name, normalized, now],
            )?;
            let entity_id: String = tx.query_row(
                "SELECT id FROM entities WHERE type = ?1 AND normalized = ?2",
                params![etype, normalized],
                |r| r.get(0),
            )?;
            tx.execute(
                "INSERT OR IGNORE INTO memory_entities (memory_id, entity_id, edge, weight) VALUES (?1, ?2, 'mentions', 1.0)",
                params![mem.id, entity_id],
            )?;
        }

        let event_id = Ulid::new().to_string();
        let payload = serde_json::to_string(&mem)?;
        tx.execute(
            "INSERT INTO events (id, kind, memory_id, payload, actor, created_at) VALUES (?1, 'ADD', ?2, ?3, ?4, ?5)",
            params![event_id, mem.id, payload, mem.source.to_string(), now],
        )?;
        tx.commit()?;
        Ok(mem)
    }

    /// List all entities, most recently used first (Phase 1: created_at ordering).
    pub fn list_entities(&self, limit: usize) -> Result<Vec<Entity>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, type, name, normalized, created_at FROM entities ORDER BY created_at DESC LIMIT ?1",
        )?;
        let rows = stmt
            .query_map(params![limit as i64], |r| {
                let kind_s: String = r.get(1)?;
                let kind = EntityType::from_str(&kind_s).map_err(|e| {
                    rusqlite::Error::FromSqlConversionFailure(
                        1,
                        rusqlite::types::Type::Text,
                        Box::new(e),
                    )
                })?;
                Ok(Entity {
                    id: r.get(0)?,
                    kind,
                    name: r.get(2)?,
                    normalized: r.get(3)?,
                    created_at: r.get(4)?,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        Ok(rows)
    }

    /// Return memories that share at least one entity with the given memory id.
    /// Phase 1: simple 1-hop adjacency, ordered by number of shared entities.
    pub fn neighbors(&self, memory_id: &str, limit: usize) -> Result<Vec<Memory>> {
        let sql = "SELECT m.id, m.kind, m.scope, m.content, m.source, m.confidence, m.importance, m.valid_from, m.valid_to, m.superseded_by, m.access_count, m.last_accessed_at, COUNT(*) AS shared FROM memory_entities me1 JOIN memory_entities me2 ON me1.entity_id = me2.entity_id AND me2.memory_id != me1.memory_id JOIN memories m ON m.id = me2.memory_id WHERE me1.memory_id = ?1 AND m.valid_to IS NULL GROUP BY m.id ORDER BY shared DESC, m.valid_from DESC LIMIT ?2";
        let mut stmt = self.conn.prepare(sql)?;
        let rows = stmt
            .query_map(params![memory_id, limit as i64], row_to_memory)?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        Ok(rows)
    }

    /// Find entities mentioned in a query string (returns IDs of entities that exist in store).
    pub(crate) fn match_entities_in_query(&self, query: &str) -> Result<Vec<String>> {
        let refs: Vec<EntityRef> = extract::extract(query);
        if refs.is_empty() {
            return Ok(Vec::new());
        }
        let mut ids = Vec::new();
        let mut stmt = self
            .conn
            .prepare("SELECT id FROM entities WHERE type = ?1 AND normalized = ?2")?;
        for er in refs {
            let normalized = er.normalized();
            let id: Option<String> = stmt
                .query_row(params![er.kind.to_string(), normalized], |r| r.get(0))
                .optional()?;
            if let Some(id) = id {
                ids.push(id);
            }
        }
        Ok(ids)
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
