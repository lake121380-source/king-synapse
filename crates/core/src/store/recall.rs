use crate::error::Result;
use crate::model::{Memory, RecallQuery};
use chrono::Utc;
use rusqlite::params;
use serde::{Deserialize, Serialize};

use super::{decay_lambda, row_to_memory, Store};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallHit {
    pub memory: Memory,
    pub score: f32,
}

pub(crate) fn recall(store: &mut Store, q: &RecallQuery) -> Result<Vec<RecallHit>> {
    let k = q.k.unwrap_or(8).max(1);
    let limit_pool = (k * 4).max(20) as i64;
    let fts_query = sanitize_fts(&q.query);

    if fts_query.is_empty() {
        return Ok(Vec::new());
    }

    let scope_str = q.scope_filter.as_ref().map(|s| s.to_string());
    let kind_str = q.kind_filter.as_ref().map(|k| k.to_string());

    let sql = "SELECT m.id, m.kind, m.scope, m.content, m.source, m.confidence, m.importance, m.valid_from, m.valid_to, m.superseded_by, m.access_count, m.last_accessed_at, bm25(memories_fts) AS rank FROM memories_fts JOIN memories m ON m.rowid = memories_fts.rowid WHERE memories_fts MATCH ?1 AND m.valid_to IS NULL AND (?2 IS NULL OR m.scope = ?2) AND (?3 IS NULL OR m.kind = ?3) ORDER BY rank ASC LIMIT ?4";

    let rows: Vec<(Memory, f64)> = {
        let mut stmt = store.conn.prepare(sql)?;
        let mapped: Vec<(Memory, f64)> = stmt
            .query_map(params![fts_query, scope_str, kind_str, limit_pool], |row| {
                let mem = row_to_memory(row)?;
                let bm25: f64 = row.get(12)?;
                Ok((mem, bm25))
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        mapped
    };

    let now = Utc::now().timestamp();
    let mut hits: Vec<RecallHit> = rows
        .into_iter()
        .map(|(mem, bm25)| {
            let base = (-bm25 as f32).max(0.001);
            let age_days = ((now - mem.valid_from).max(0) as f32) / 86_400.0;
            let lambda = decay_lambda(mem.kind);
            let decay = (-lambda * age_days).exp();
            let score = base * mem.importance.max(0.05) * mem.confidence.max(0.05) * decay;
            RecallHit { memory: mem, score }
        })
        .collect();

    hits.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    hits.truncate(k);

    if !hits.is_empty() {
        let tx = store.conn.transaction()?;
        for hit in &hits {
            tx.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ?2 WHERE id = ?1",
                params![hit.memory.id, now],
            )?;
        }
        tx.commit()?;
    }

    Ok(hits)
}

/// Make a user query safe to pass to FTS5 MATCH.
/// We strip out FTS operator chars and wrap each token as a prefix match.
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{MemoryKind, Scope, Source, WriteInput};

    fn add(store: &mut Store, content: &str, kind: MemoryKind) {
        store
            .write(WriteInput {
                content: content.to_string(),
                kind,
                scope: Scope::Global,
                source: Source::ExplicitUser,
                confidence: Some(1.0),
                importance: Some(0.7),
            })
            .unwrap();
    }

    #[test]
    fn roundtrip_and_recall() {
        let mut s = Store::open_in_memory().unwrap();
        add(
            &mut s,
            "pnpm install hangs on Windows behind proxy",
            MemoryKind::Failure,
        );
        add(
            &mut s,
            "use corepack enable then pnpm",
            MemoryKind::Playbook,
        );
        add(
            &mut s,
            "user prefers TypeScript over JavaScript",
            MemoryKind::Preference,
        );

        let q = RecallQuery {
            query: "pnpm windows".to_string(),
            k: Some(5),
            scope_filter: None,
            kind_filter: None,
        };
        let hits = s.recall(&q).unwrap();
        assert!(!hits.is_empty());
        assert!(hits[0].memory.content.contains("pnpm"));
    }

    #[test]
    fn invalidate_hides_from_recall() {
        let mut s = Store::open_in_memory().unwrap();
        add(&mut s, "use yarn for project foo", MemoryKind::Fact);
        let recent = s.list_recent(10).unwrap();
        let id = recent[0].id.clone();
        s.invalidate(&id, "test").unwrap();

        let q = RecallQuery {
            query: "yarn".to_string(),
            k: Some(5),
            scope_filter: None,
            kind_filter: None,
        };
        let hits = s.recall(&q).unwrap();
        assert!(hits.is_empty());
    }
}
