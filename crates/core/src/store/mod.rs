//! SQLite-backed storage for memories + append-only event log.
//!
//! Storage layer only: persistence + atomic search primitives
//! (`search_fts`, `search_vector`, `search_entity`, `expand_neighbors`).
//! Query understanding, fusion, and decay live in `crate::recall`.

mod branches;
mod schema;

use crate::entity::{Entity, EntityRef, EntityType};
use crate::error::Result;
use crate::extract;
use crate::model::{Memory, MemoryKind, WriteInput};
use chrono::Utc;
use rusqlite::{params, Connection, OptionalExtension};
use std::path::Path;
use std::str::FromStr;
use std::sync::Once;
use ulid::Ulid;

static SQLITE_VEC_INIT: Once = Once::new();

fn register_sqlite_vec() {
    SQLITE_VEC_INIT.call_once(|| unsafe {
        #[allow(clippy::missing_transmute_annotations)]
        rusqlite::ffi::sqlite3_auto_extension(Some(std::mem::transmute(
            sqlite_vec::sqlite3_vec_init as *const (),
        )));
    });
}

pub struct Store {
    pub(crate) conn: Connection,
}

impl Store {
    pub fn open(path: &Path) -> Result<Self> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        register_sqlite_vec();
        let conn = Connection::open(path)?;
        conn.execute_batch(schema::SCHEMA_SQL)?;
        conn.execute_batch(&schema::vec_schema_sql())?;
        Ok(Store { conn })
    }

    pub fn open_in_memory() -> Result<Self> {
        register_sqlite_vec();
        let conn = Connection::open_in_memory()?;
        conn.execute_batch(schema::SCHEMA_SQL)?;
        conn.execute_batch(&schema::vec_schema_sql())?;
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
        tx.execute(
            "INSERT OR IGNORE INTO embedding_state (memory_id, model, dim, status, updated_at) VALUES (?1, '', 0, 'pending', ?2)",
            params![mem.id, now],
        )?;
        tx.commit()?;
        Ok(mem)
    }

    /// Return memory ids that still need an embedding, oldest first.
    pub fn pending_embeddings(&self, limit: usize) -> Result<Vec<(String, String)>> {
        let mut stmt = self.conn.prepare(
            "SELECT m.id, m.content FROM embedding_state e JOIN memories m ON m.id = e.memory_id WHERE e.status = 'pending' AND m.valid_to IS NULL ORDER BY e.updated_at ASC LIMIT ?1",
        )?;
        let rows = stmt
            .query_map(params![limit as i64], |r| {
                Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        Ok(rows)
    }

    /// Persist a freshly computed embedding vector for a memory and mark it done.
    pub fn put_embedding(&mut self, memory_id: &str, model: &str, vector: &[f32]) -> Result<()> {
        let now = Utc::now().timestamp();
        let bytes: Vec<u8> = vector.iter().flat_map(|v| v.to_le_bytes()).collect();
        let tx = self.conn.transaction()?;
        tx.execute(
            "INSERT OR REPLACE INTO memory_vecs (memory_id, embedding) VALUES (?1, ?2)",
            params![memory_id, bytes],
        )?;
        tx.execute(
            "INSERT INTO embedding_state (memory_id, model, dim, status, updated_at) VALUES (?1, ?2, ?3, 'done', ?4) ON CONFLICT(memory_id) DO UPDATE SET model = excluded.model, dim = excluded.dim, status = 'done', updated_at = excluded.updated_at",
            params![memory_id, model, vector.len() as i64, now],
        )?;
        tx.commit()?;
        Ok(())
    }

    /// (done_count, pending_count) for embeddings.
    pub fn embedding_stats(&self) -> Result<(i64, i64)> {
        let done: i64 = self
            .conn
            .query_row(
                "SELECT COUNT(*) FROM embedding_state WHERE status = 'done'",
                [],
                |r| r.get(0),
            )
            .unwrap_or(0);
        let pending: i64 = self
            .conn
            .query_row(
                "SELECT COUNT(*) FROM embedding_state WHERE status = 'pending'",
                [],
                |r| r.get(0),
            )
            .unwrap_or(0);
        Ok((done, pending))
    }

    /// Vector branch: nearest-neighbour search over memory_vecs (callers must pass an embedded query).
    /// Vector branch: nearest-neighbour search over `memory_vecs`.
    /// Returns `(memory_id, distance)` ascending. Callers must have produced
    /// the query vector themselves (typically via `crate::embed::Embedder`).
    pub fn search_vector(&self, query_vec: &[f32], limit: usize) -> Result<Vec<(String, f64)>> {
        if query_vec.is_empty() || limit == 0 {
            return Ok(Vec::new());
        }
        let bytes: Vec<u8> = query_vec.iter().flat_map(|v| v.to_le_bytes()).collect();
        let mut stmt = self.conn.prepare(
            "SELECT memory_id, distance FROM memory_vecs WHERE embedding MATCH ?1 AND k = ?2 ORDER BY distance",
        )?;
        let rows = stmt
            .query_map(params![bytes, limit as i64], |r| {
                Ok((r.get::<_, String>(0)?, r.get::<_, f64>(1)?))
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        Ok(rows)
    }

    /// FTS branch: BM25-ranked full-text matches. Returns `(Memory, bm25)`
    /// where lower bm25 = better (rusqlite's bm25 returns negative scores).
    pub fn search_fts(
        &self,
        query: &str,
        scope: Option<&str>,
        kind: Option<&str>,
        limit: usize,
    ) -> Result<Vec<(Memory, f64)>> {
        let fts_query = sanitize_fts(query);
        if fts_query.is_empty() || limit == 0 {
            return Ok(Vec::new());
        }
        let scope_s = scope.map(|s| s.to_string());
        let kind_s = kind.map(|s| s.to_string());
        branches::fts_branch(self, &fts_query, &scope_s, &kind_s, limit as i64)
    }

    /// Entity branch: memories that mention any entity recognized in `query`.
    /// Returns `(Memory, hits)` ordered by shared-entity hit count.
    pub fn search_entity(
        &self,
        query: &str,
        scope: Option<&str>,
        kind: Option<&str>,
        limit: usize,
    ) -> Result<Vec<(Memory, u32)>> {
        if limit == 0 {
            return Ok(Vec::new());
        }
        let scope_s = scope.map(|s| s.to_string());
        let kind_s = kind.map(|s| s.to_string());
        branches::entity_branch(self, query, &scope_s, &kind_s, limit as i64)
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

    pub fn update_content(&mut self, id: &str, content: &str, actor: &str) -> Result<()> {
        let now = Utc::now().timestamp();
        let entities = extract::extract(content);
        let tx = self.conn.transaction()?;
        let updated = tx.execute(
            "UPDATE memories SET content = ?2 WHERE id = ?1 AND valid_to IS NULL",
            params![id, content],
        )?;
        if updated == 0 {
            return Err(crate::error::Error::NotFound(id.to_string()));
        }

        tx.execute(
            "DELETE FROM memory_entities WHERE memory_id = ?1",
            params![id],
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
                params![id, entity_id],
            )?;
        }

        tx.execute("DELETE FROM memory_vecs WHERE memory_id = ?1", params![id])?;
        tx.execute(
            "INSERT INTO embedding_state (memory_id, model, dim, status, updated_at) VALUES (?1, '', 0, 'pending', ?2) ON CONFLICT(memory_id) DO UPDATE SET model = '', dim = 0, status = 'pending', updated_at = excluded.updated_at",
            params![id, now],
        )?;

        let updated_memory = tx.query_row(
            "SELECT id, kind, scope, content, source, confidence, importance, valid_from, valid_to, superseded_by, access_count, last_accessed_at FROM memories WHERE id = ?1",
            params![id],
            row_to_memory,
        )?;
        let event_id = Ulid::new().to_string();
        let payload = serde_json::to_string(&updated_memory)?;
        tx.execute(
            "INSERT INTO events (id, kind, memory_id, payload, actor, created_at) VALUES (?1, 'UPDATE', ?2, ?3, ?4, ?5)",
            params![event_id, id, payload, actor, now],
        )?;
        tx.commit()?;
        Ok(())
    }

    pub fn update_edge(&mut self, source: &str, target: &str, weight_delta: f32) -> Result<()> {
        if source.is_empty() || target.is_empty() || !weight_delta.is_finite() {
            return Err(crate::error::Error::Invalid(
                "edge update requires non-empty source/target and finite weight".to_string(),
            ));
        }

        let now = Utc::now().timestamp();
        let tx = self.conn.transaction()?;
        let source_exists = memory_exists(&tx, source)?;
        if !source_exists {
            return Err(crate::error::Error::NotFound(source.to_string()));
        }
        let target_exists = memory_exists(&tx, target)?;
        if !target_exists {
            return Err(crate::error::Error::NotFound(target.to_string()));
        }

        tx.execute(
            "INSERT INTO memory_edges (source, target, edge, weight, updated_at) VALUES (?1, ?2, 'associates', ?3, ?4) ON CONFLICT(source, target, edge) DO UPDATE SET weight = memory_edges.weight + excluded.weight, updated_at = excluded.updated_at",
            params![source, target, weight_delta, now],
        )?;
        tx.commit()?;
        Ok(())
    }

    pub fn edge_weight(&self, source: &str, target: &str) -> Result<Option<f32>> {
        let weight = self
            .conn
            .query_row(
                "SELECT weight FROM memory_edges WHERE source = ?1 AND target = ?2 AND edge = 'associates'",
                params![source, target],
                |row| row.get::<_, f64>(0),
            )
            .optional()?
            .map(|value| value as f32);
        Ok(weight)
    }

    pub fn edge_weights_between(
        &self,
        source_ids: &[&str],
        target_ids: &[&str],
    ) -> Result<Vec<(String, String, f32)>> {
        if source_ids.is_empty() || target_ids.is_empty() {
            return Ok(Vec::new());
        }

        let mut edges = Vec::new();
        let mut stmt = self.conn.prepare(
            "SELECT weight FROM memory_edges WHERE source = ?1 AND target = ?2 AND edge = 'associates'",
        )?;
        for source in source_ids {
            for target in target_ids {
                if source == target {
                    continue;
                }
                let weight = stmt
                    .query_row(params![source, target], |row| row.get::<_, f64>(0))
                    .optional()?;
                if let Some(weight) = weight {
                    edges.push(((*source).to_string(), (*target).to_string(), weight as f32));
                }
            }
        }
        Ok(edges)
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

    /// Bump `access_count` and stamp `last_accessed_at` for the memories the
    /// recall layer surfaced. Called from `crate::recall::RecallEngine` and
    /// from the 1-hop graph expansion below.
    pub fn record_access(&mut self, ids: &[&str], now: i64) -> Result<()> {
        if ids.is_empty() {
            return Ok(());
        }
        let tx = self.conn.transaction()?;
        for id in ids {
            tx.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ?2 WHERE id = ?1",
                params![id, now],
            )?;
        }
        tx.commit()?;
        Ok(())
    }

    pub fn count(&self) -> Result<i64> {
        let n: i64 = self
            .conn
            .query_row("SELECT COUNT(*) FROM memories", [], |r| r.get(0))?;
        Ok(n)
    }
}

fn memory_exists(conn: &Connection, id: &str) -> Result<bool> {
    let exists: i64 = conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM memories WHERE id = ?1 AND valid_to IS NULL)",
        params![id],
        |row| row.get(0),
    )?;
    Ok(exists != 0)
}

/// Sanitize a freeform user query into an FTS5 MATCH expression.
/// Strips punctuation, keeps unicode letters/digits, OR-joins prefix terms.
fn sanitize_fts(q: &str) -> String {
    let cleaned: String = q
        .chars()
        .map(|c| {
            if c.is_alphanumeric() || c.is_whitespace() || c == '_' || c == '-' {
                c
            } else {
                ' '
            }
        })
        .collect();
    let tokens: Vec<String> = cleaned
        .split_whitespace()
        .filter(|t| !t.is_empty())
        .map(|t| format!("\"{}\"*", t.replace('"', "")))
        .collect();
    tokens.join(" OR ")
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Scope, Source};

    fn make_store() -> Store {
        Store::open_in_memory().unwrap()
    }

    fn make_vec(seed: f32) -> Vec<f32> {
        (0..super::schema::VEC_DIM)
            .map(|i| seed + (i as f32) * 0.001)
            .collect()
    }

    #[test]
    fn write_marks_embedding_pending() {
        let mut s = make_store();
        let m = s
            .write(WriteInput {
                content: "needs embedding".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let pending = s.pending_embeddings(10).unwrap();
        assert!(pending.iter().any(|(id, _)| id == &m.id));
        let (done, pend) = s.embedding_stats().unwrap();
        assert_eq!(done, 0);
        assert_eq!(pend, 1);
    }

    #[test]
    fn update_edge_persists_and_accumulates_weight() {
        let mut s = make_store();
        let source = s
            .write(WriteInput {
                content: "source memory".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let target = s
            .write(WriteInput {
                content: "target memory".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();

        s.update_edge(&source.id, &target.id, 0.2).unwrap();
        s.update_edge(&source.id, &target.id, 0.3).unwrap();

        assert_eq!(s.edge_weight(&source.id, &target.id).unwrap(), Some(0.5));
        assert_eq!(s.edge_weight(&target.id, &source.id).unwrap(), None);
    }

    #[test]
    fn edge_weights_between_returns_directed_edges_inside_candidate_set() {
        let mut s = make_store();
        let source = s
            .write(WriteInput {
                content: "source memory".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let target = s
            .write(WriteInput {
                content: "target memory".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let unrelated = s
            .write(WriteInput {
                content: "unrelated memory".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();

        s.update_edge(&source.id, &target.id, 0.6).unwrap();
        s.update_edge(&target.id, &source.id, 0.2).unwrap();

        let edges = s
            .edge_weights_between(&[&source.id, &target.id], &[&source.id, &target.id])
            .unwrap();

        assert_eq!(edges.len(), 2);
        assert!(edges.contains(&(source.id.clone(), target.id.clone(), 0.6)));
        assert!(edges.contains(&(target.id.clone(), source.id.clone(), 0.2)));
        assert!(s
            .edge_weights_between(&[&unrelated.id], &[&source.id, &target.id])
            .unwrap()
            .is_empty());
    }

    #[test]
    fn update_edge_requires_existing_active_memories() {
        let mut s = make_store();
        let source = s
            .write(WriteInput {
                content: "source memory".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();

        assert!(s.update_edge(&source.id, "missing", 0.2).is_err());
        assert_eq!(s.edge_weight(&source.id, "missing").unwrap(), None);
    }

    #[test]
    fn vector_round_trip_and_neighbors() {
        let mut s = make_store();
        let m1 = s
            .write(WriteInput {
                content: "first memory".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let m2 = s
            .write(WriteInput {
                content: "second memory, far away".into(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();

        let v1 = make_vec(0.0);
        let v2 = make_vec(10.0);
        s.put_embedding(&m1.id, "fake-model", &v1).unwrap();
        s.put_embedding(&m2.id, "fake-model", &v2).unwrap();

        let (done, pend) = s.embedding_stats().unwrap();
        assert_eq!(done, 2);
        assert_eq!(pend, 0);
        assert!(s
            .pending_embeddings(10)
            .unwrap()
            .iter()
            .all(|(id, _)| id != &m1.id && id != &m2.id));

        // Nearest neighbour to v1 should be m1 (distance ~0), then m2.
        let nbrs = s.search_vector(&v1, 2).unwrap();
        assert_eq!(nbrs.len(), 2);
        assert_eq!(nbrs[0].0, m1.id);
        assert!(nbrs[0].1 < nbrs[1].1);
        assert_eq!(nbrs[1].0, m2.id);
    }
}
