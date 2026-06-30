use crate::error::Result;
use crate::model::Memory;
use rusqlite::params;

use super::{row_to_memory, Store};

pub(crate) fn fts_branch(
    store: &Store,
    fts_query: &str,
    scope_str: &Option<String>,
    kind_str: &Option<String>,
    limit_pool: i64,
) -> Result<Vec<(Memory, f64)>> {
    if fts_query.is_empty() {
        return Ok(Vec::new());
    }
    let sql = "SELECT m.id, m.kind, m.scope, m.content, m.source, m.confidence, m.importance, m.valid_from, m.valid_to, m.superseded_by, m.access_count, m.last_accessed_at, bm25(memories_fts) AS rank FROM memories_fts JOIN memories m ON m.rowid = memories_fts.rowid WHERE memories_fts MATCH ?1 AND m.valid_to IS NULL AND (?2 IS NULL OR m.scope = ?2) AND (?3 IS NULL OR m.kind = ?3) ORDER BY rank ASC LIMIT ?4";
    let mut stmt = store.conn.prepare(sql)?;
    let mapped: Vec<(Memory, f64)> = stmt
        .query_map(params![fts_query, scope_str, kind_str, limit_pool], |row| {
            let mem = row_to_memory(row)?;
            let bm25: f64 = row.get(12)?;
            Ok((mem, bm25))
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;
    Ok(mapped)
}

pub(crate) fn entity_branch(
    store: &Store,
    query: &str,
    scope_str: &Option<String>,
    kind_str: &Option<String>,
    limit_pool: i64,
) -> Result<Vec<(Memory, u32)>> {
    let entity_ids = store.match_entities_in_query(query)?;
    if entity_ids.is_empty() {
        return Ok(Vec::new());
    }
    let placeholders = (1..=entity_ids.len())
        .map(|i| format!("?{i}"))
        .collect::<Vec<_>>()
        .join(",");
    let scope_pos = entity_ids.len() + 1;
    let kind_pos = entity_ids.len() + 2;
    let limit_pos = entity_ids.len() + 3;
    let sql = format!(
        "SELECT m.id, m.kind, m.scope, m.content, m.source, m.confidence, m.importance, m.valid_from, m.valid_to, m.superseded_by, m.access_count, m.last_accessed_at, COUNT(*) AS hits FROM memory_entities me JOIN memories m ON m.id = me.memory_id WHERE me.entity_id IN ({placeholders}) AND m.valid_to IS NULL AND (?{scope_pos} IS NULL OR m.scope = ?{scope_pos}) AND (?{kind_pos} IS NULL OR m.kind = ?{kind_pos}) GROUP BY m.id ORDER BY hits DESC LIMIT ?{limit_pos}"
    );

    let mut all_params: Vec<rusqlite::types::Value> = entity_ids
        .iter()
        .map(|id| rusqlite::types::Value::Text(id.clone()))
        .collect();
    all_params.push(
        scope_str
            .clone()
            .map_or(rusqlite::types::Value::Null, rusqlite::types::Value::Text),
    );
    all_params.push(
        kind_str
            .clone()
            .map_or(rusqlite::types::Value::Null, rusqlite::types::Value::Text),
    );
    all_params.push(rusqlite::types::Value::Integer(limit_pool));

    let mut stmt = store.conn.prepare(&sql)?;
    let rows = stmt
        .query_map(rusqlite::params_from_iter(all_params.iter()), |row| {
            let mem = row_to_memory(row)?;
            let hits: i64 = row.get(12)?;
            Ok((mem, hits as u32))
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;
    Ok(rows)
}
