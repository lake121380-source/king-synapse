use crate::error::Result;
use crate::model::{Memory, RecallQuery};
use chrono::Utc;
use rusqlite::params;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use super::branches::{entity_branch, fts_branch};
use super::{decay_lambda, Store};

const ENTITY_BOOST_PER_MATCH: f32 = 0.8;
const ENTITY_BOOST_MAX: f32 = 3.0;
const ENTITY_ONLY_FLOOR: f32 = 0.15;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallHit {
    pub memory: Memory,
    pub score: f32,
    #[serde(default)]
    pub entity_hits: u32,
}

pub(crate) fn recall(store: &mut Store, q: &RecallQuery) -> Result<Vec<RecallHit>> {
    let k = q.k.unwrap_or(8).max(1);
    let limit_pool = (k * 4).max(20) as i64;
    let fts_query = sanitize_fts(&q.query);
    let scope_str = q.scope_filter.as_ref().map(|s| s.to_string());
    let kind_str = q.kind_filter.as_ref().map(|k| k.to_string());

    let fts_rows = fts_branch(store, &fts_query, &scope_str, &kind_str, limit_pool)?;
    let entity_rows = entity_branch(store, &q.query, &scope_str, &kind_str, limit_pool)?;

    let now = Utc::now().timestamp();
    let mut by_id: HashMap<String, RecallHit> = HashMap::new();

    for (mem, bm25) in fts_rows {
        let base = (-bm25 as f32).max(0.001);
        let age_days = ((now - mem.valid_from).max(0) as f32) / 86_400.0;
        let decay = (-decay_lambda(mem.kind) * age_days).exp();
        let score = base * mem.importance.max(0.05) * mem.confidence.max(0.05) * decay;
        let id = mem.id.clone();
        by_id.insert(
            id,
            RecallHit {
                memory: mem,
                score,
                entity_hits: 0,
            },
        );
    }
    for (mem, hits) in entity_rows {
        let boost = (ENTITY_BOOST_PER_MATCH * hits as f32).min(ENTITY_BOOST_MAX);
        let entry = by_id.entry(mem.id.clone()).or_insert_with(|| {
            let age_days = ((now - mem.valid_from).max(0) as f32) / 86_400.0;
            let decay = (-decay_lambda(mem.kind) * age_days).exp();
            RecallHit {
                memory: mem,
                score: ENTITY_ONLY_FLOOR * decay,
                entity_hits: 0,
            }
        });
        entry.entity_hits = hits;
        entry.score += boost;
    }

    let mut hits: Vec<RecallHit> = by_id.into_values().collect();
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
