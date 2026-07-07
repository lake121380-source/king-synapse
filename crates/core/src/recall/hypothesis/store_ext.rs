//! Store extension methods for edge hypothesis management.
//!
//! These methods implement the lifecycle:
//!   upsert -> update confidence -> graduate -> decay

use crate::error::Result;
use crate::recall::hypothesis::model::{
    CONFIDENCE_FLOOR, CONFIRM_THRESHOLD, DECAY_PER_TURN, EdgeEvidence, EdgeHypothesis,
    EdgeHypothesisStatus, MIN_DIVERSITY_CONTEXTS, MIN_OBSERVATIONS, REOBSERVATION_BOOST,
    W_DIVERSITY, W_FREQUENCY, W_UTILITY,
};
use crate::store::Store;
use chrono::Utc;
use rusqlite::params;

/// Extension trait for Store with hypothesis management.
pub trait HypothesisStore {
    /// Upsert a hypothesis: if new, insert; if existing, update confidence
    /// and observations. Returns the updated hypothesis.
    fn upsert_hypothesis(
        &mut self,
        hyp: &EdgeHypothesis,
        context_hash: &str,
        context_tag: &str,
        supporting_ids: &[String],
        reason: &str,
    ) -> Result<EdgeHypothesis>;

    /// Get all hypotheses for a given source memory.
    fn get_hypotheses_for(&self, memory_id: &str) -> Result<Vec<EdgeHypothesis>>;

    /// Get all hypotheses by status.
    fn get_hypotheses_by_status(&self, status: EdgeHypothesisStatus) -> Result<Vec<EdgeHypothesis>>;

    /// Get all evidence for a hypothesis.
    fn get_evidence(&self, hypothesis_id: &str) -> Result<Vec<EdgeEvidence>>;

    /// Graduate confirmed hypotheses to memory_edges.
    /// Returns the number of edges created.
    fn graduate_confirmed(&mut self) -> Result<usize>;

    /// Decay all hypotheses: decrease confidence for those not recently observed.
    /// Marks forgotten if below floor.
    fn decay_hypotheses(&mut self) -> Result<usize>;

    /// Count hypotheses by status (for metrics).
    fn count_hypotheses_by_status(&self) -> Result<Vec<(String, usize)>>;

    /// Count total edges in memory_edges (for density metric).
    fn count_memory_edges(&self) -> Result<usize>;

    /// Get all distinct relation types currently in memory_edges.
    fn count_edges_by_type(&self) -> Result<Vec<(String, usize)>>;
}

impl HypothesisStore for Store {
    fn upsert_hypothesis(
        &mut self,
        hyp: &EdgeHypothesis,
        context_hash: &str,
        context_tag: &str,
        supporting_ids: &[String],
        reason: &str,
    ) -> Result<EdgeHypothesis> {
        let now = Utc::now().timestamp();

        // Try to find existing hypothesis
        let existing: Option<(f32, usize, usize, f32, i64, i64, String)> = self.conn
            .query_row(
                "SELECT confidence, observations, distinct_contexts, predictive_utility, \
                 first_seen, last_seen, status \
                 FROM edge_hypotheses WHERE id = ?1",
                params![hyp.id],
                |row| {
                    Ok((
                        row.get::<_, f64>(0)? as f32,
                        row.get::<_, usize>(1)?,
                        row.get::<_, usize>(2)?,
                        row.get::<_, f64>(3)? as f32,
                        row.get::<_, i64>(4)?,
                        row.get::<_, i64>(5)?,
                        row.get::<_, String>(6)?,
                    ))
                },
            )
            .optional()?;

        let (confidence, observations, distinct_contexts, first_seen, status) = if let Some((
            existing_conf,
            existing_obs,
            existing_div,
            existing_util,
            existing_first,
            existing_last,
            existing_status,
        )) = existing
        {
            // Check if this context is new
            let context_is_new: bool = self.conn.query_row(
                "SELECT COUNT(*) FROM edge_evidence \
                 WHERE hypothesis_id = ?1 AND query_context_hash = ?2",
                params![hyp.id, context_hash],
                |row| row.get::<_, i64>(0),
            )? == 0;

            let new_observations = existing_obs + 1;
            let new_distinct_contexts = if context_is_new {
                existing_div + 1
            } else {
                existing_div
            };

            // Confidence boost only for new contexts (diversity matters)
            let confidence_delta = if context_is_new {
                REOBSERVATION_BOOST
            } else {
                0.0
            };

            // Recompute composite confidence
            // IDF-weighted frequency: discount edges that appear in too many contexts
            // (like conversation-opening memories that co-retrieve with everything).
            // Formula: freq_score = raw_freq * log(total_contexts / edge_contexts)
            let total_contexts = {
                let count: i64 = self.conn.query_row(
                    "SELECT COUNT(DISTINCT query_context_hash) FROM edge_evidence",
                    [], |row| row.get::<_, i64>(0),
                ).unwrap_or(1);
                count.max(1) as f32
            };
            let idf = (total_contexts / new_distinct_contexts as f32).ln().max(0.1);
            let raw_freq = (new_observations as f32 / 10.0).min(1.0);
            let freq_score = (raw_freq * idf).min(1.0);
            let div_score = (new_distinct_contexts as f32 / MIN_DIVERSITY_CONTEXTS as f32).min(1.0);
            let util_score = existing_util;
            // When utility is not yet tracked (0.0), redistribute its weight
            // to frequency and diversity so the pool can graduate edges
            // before the utility tracking loop is implemented.
            let (wf, wd, wu) = if util_score > 0.0 {
                (W_FREQUENCY, W_DIVERSITY, W_UTILITY)
            } else {
                // Redistribute: freq gets 0.35, div gets 0.65
                (0.35, 0.65, 0.0)
            };
            let new_confidence = (wf * freq_score
                + wd * div_score
                + wu * util_score
                + confidence_delta)
                .min(1.0);

            // Update status
            let new_status = if new_confidence >= CONFIRM_THRESHOLD
                && new_observations >= MIN_OBSERVATIONS
                && new_distinct_contexts >= MIN_DIVERSITY_CONTEXTS
            {
                EdgeHypothesisStatus::Confirmed
            } else if new_observations > 1 {
                EdgeHypothesisStatus::Observed
            } else {
                EdgeHypothesisStatus::Candidate
            };

            let confirmed_at = if new_status == EdgeHypothesisStatus::Confirmed
                && existing_status != "confirmed"
                && existing_status != "strengthened"
            {
                Some(now)
            } else {
                None
            };

            self.conn.execute(
                "UPDATE edge_hypotheses SET \
                 confidence = ?1, observations = ?2, distinct_contexts = ?3, \
                 last_seen = ?4, status = ?5, decayed_turns = 0 \
                 WHERE id = ?6",
                params![
                    new_confidence as f64,
                    new_observations,
                    new_distinct_contexts,
                    now,
                    new_status.as_str(),
                    hyp.id,
                ],
            )?;

            if let Some(ct) = confirmed_at {
                self.conn.execute(
                    "UPDATE edge_hypotheses SET confirmed_at = ?1 WHERE id = ?2",
                    params![ct, hyp.id],
                )?;
            }

            (
                new_confidence,
                new_observations,
                new_distinct_contexts,
                existing_first,
                new_status.as_str().to_string(),
            )
        } else {
            // Insert new hypothesis
            self.conn.execute(
                "INSERT INTO edge_hypotheses \
                 (id, source, target, relation, confidence, observations, distinct_contexts, \
                 predictive_utility, first_seen, last_seen, status, confirmed_at, disputed_at, decayed_turns) \
                 VALUES (?1, ?2, ?3, ?4, ?5, 1, 1, 0.0, ?6, ?7, 'candidate', NULL, NULL, 0)",
                params![
                    hyp.id,
                    hyp.source,
                    hyp.target,
                    hyp.relation.as_str(),
                    hyp.confidence as f64,
                    now,
                    now,
                ],
            )?;
            (
                hyp.confidence,
                1,
                1,
                now,
                "candidate".to_string(),
            )
        };

        // Add evidence record (use uuid-like suffix for uniqueness within same timestamp)
        let evidence_id = format!("ev_{}_{}_{}", hyp.id, now, observations);
        let supporting = supporting_ids.join(",");
        self.conn.execute(
            "INSERT INTO edge_evidence \
             (id, hypothesis_id, query_context_hash, query_context_tag, \
             supporting_memory_ids, reason_summary, utility_before_rank, utility_after_rank, observed_at) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, NULL, NULL, ?7)",
            params![
                evidence_id,
                hyp.id,
                context_hash,
                context_tag,
                supporting,
                reason,
                now,
            ],
        )?;

        // Return updated hypothesis
        let status_enum = EdgeHypothesisStatus::from_str(&status)
            .unwrap_or(EdgeHypothesisStatus::Candidate);
        Ok(EdgeHypothesis {
            id: hyp.id.clone(),
            source: hyp.source.clone(),
            target: hyp.target.clone(),
            relation: hyp.relation,
            confidence,
            observations,
            distinct_contexts,
            predictive_utility: 0.0,
            first_seen,
            last_seen: now,
            status: status_enum,
            confirmed_at: None,
            disputed_at: None,
            decayed_turns: 0,
        })
    }

    fn get_hypotheses_for(&self, memory_id: &str) -> Result<Vec<EdgeHypothesis>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, source, target, relation, confidence, observations, \
             distinct_contexts, predictive_utility, first_seen, last_seen, \
             status, confirmed_at, disputed_at, decayed_turns \
             FROM edge_hypotheses WHERE source = ?1 OR target = ?1",
        )?;
        let rows = stmt.query_map(params![memory_id], row_to_hypothesis)?;
        Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
    }

    fn get_hypotheses_by_status(&self, status: EdgeHypothesisStatus) -> Result<Vec<EdgeHypothesis>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, source, target, relation, confidence, observations, \
             distinct_contexts, predictive_utility, first_seen, last_seen, \
             status, confirmed_at, disputed_at, decayed_turns \
             FROM edge_hypotheses WHERE status = ?1",
        )?;
        let rows = stmt.query_map(params![status.as_str()], row_to_hypothesis)?;
        Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
    }

    fn get_evidence(&self, hypothesis_id: &str) -> Result<Vec<EdgeEvidence>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, hypothesis_id, query_context_hash, query_context_tag, \
             supporting_memory_ids, reason_summary, utility_before_rank, \
             utility_after_rank, observed_at \
             FROM edge_evidence WHERE hypothesis_id = ?1 ORDER BY observed_at",
        )?;
        let rows = stmt.query_map(params![hypothesis_id], |row| {
            Ok(EdgeEvidence {
                id: row.get::<_, String>(0)?,
                hypothesis_id: row.get::<_, String>(1)?,
                query_context_hash: row.get::<_, String>(2)?,
                query_context_tag: row.get::<_, String>(3)?,
                supporting_memory_ids: row.get::<_, String>(4)?,
                reason_summary: row.get::<_, String>(5)?,
                utility_before_rank: row.get::<_, Option<i64>>(6)?,
                utility_after_rank: row.get::<_, Option<i64>>(7)?,
                observed_at: row.get::<_, i64>(8)?,
            })
        })?;
        Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
    }

    fn graduate_confirmed(&mut self) -> Result<usize> {
        let now = Utc::now().timestamp();
        let confirmed: Vec<(String, String, String, f64)> = {
            let mut stmt = self.conn.prepare(
                "SELECT source, target, relation, confidence \
                 FROM edge_hypotheses WHERE status = 'confirmed' OR status = 'strengthened'",
            )?;
            let rows = stmt.query_map([], |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, f64>(3)?,
                ))
            })?;
            rows.collect::<std::result::Result<Vec<_>, _>>()?
        };

        let mut count = 0usize;
        let tx = self.conn.transaction()?;
        for (source, target, relation, confidence) in &confirmed {
            let weight = (*confidence as f32).max(0.0).min(1.0);
            // Bidirectional edges
            tx.execute(
                "INSERT INTO memory_edges (source, target, edge, weight, updated_at) \
                 VALUES (?1, ?2, ?3, ?4, ?5) \
                 ON CONFLICT(source, target, edge) DO UPDATE SET \
                 weight = excluded.weight, updated_at = excluded.updated_at",
                params![source, target, relation, weight, now],
            )?;
            tx.execute(
                "INSERT INTO memory_edges (source, target, edge, weight, updated_at) \
                 VALUES (?1, ?2, ?3, ?4, ?5) \
                 ON CONFLICT(source, target, edge) DO UPDATE SET \
                 weight = excluded.weight, updated_at = excluded.updated_at",
                params![target, source, relation, weight, now],
            )?;
            count += 2;
        }
        tx.commit()?;
        Ok(count)
    }

    fn decay_hypotheses(&mut self) -> Result<usize> {
        let now = Utc::now().timestamp();
        let tx = self.conn.transaction()?;

        // Increment decayed_turns for all non-forgotten, non-confirmed
        tx.execute(
            "UPDATE edge_hypotheses SET decayed_turns = decayed_turns + 1 \
             WHERE status IN ('candidate', 'observed')",
            [],
        )?;

        // Decay confidence
        tx.execute(
            "UPDATE edge_hypotheses \
             SET confidence = MAX(0.0, confidence - ?1) \
             WHERE status IN ('candidate', 'observed') AND decayed_turns > 0",
            params![DECAY_PER_TURN as f64],
        )?;

        // Mark forgotten if below floor
        let forgotten = tx.execute(
            "UPDATE edge_hypotheses SET status = 'forgotten' \
             WHERE confidence < ?1 AND status IN ('candidate', 'observed')",
            params![CONFIDENCE_FLOOR as f64],
        )?;

        tx.commit()?;
        Ok(forgotten)
    }

    fn count_hypotheses_by_status(&self) -> Result<Vec<(String, usize)>> {
        let mut stmt = self.conn.prepare(
            "SELECT status, COUNT(*) FROM edge_hypotheses GROUP BY status ORDER BY status",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, usize>(1)?))
        })?;
        Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
    }

    fn count_memory_edges(&self) -> Result<usize> {
        let count: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM memory_edges",
            [],
            |row| row.get::<_, i64>(0),
        )?;
        Ok(count as usize)
    }

    fn count_edges_by_type(&self) -> Result<Vec<(String, usize)>> {
        let mut stmt = self.conn.prepare(
            "SELECT edge, COUNT(*) FROM memory_edges GROUP BY edge ORDER BY COUNT(*) DESC",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, usize>(1)?))
        })?;
        Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
    }
}

fn row_to_hypothesis(row: &rusqlite::Row<'_>) -> rusqlite::Result<EdgeHypothesis> {
    let status_str: String = row.get(10)?;
    let relation_str: String = row.get(3)?;
    Ok(EdgeHypothesis {
        id: row.get(0)?,
        source: row.get(1)?,
        target: row.get(2)?,
        relation: crate::recall::hypothesis::model::EdgeRelation::from_str(&relation_str)
            .unwrap_or(crate::recall::hypothesis::model::EdgeRelation::CoActivates),
        confidence: row.get::<_, f64>(4)? as f32,
        observations: row.get(5)?,
        distinct_contexts: row.get(6)?,
        predictive_utility: row.get::<_, f64>(7)? as f32,
        first_seen: row.get(8)?,
        last_seen: row.get(9)?,
        status: EdgeHypothesisStatus::from_str(&status_str)
            .unwrap_or(EdgeHypothesisStatus::Candidate),
        confirmed_at: row.get(11)?,
        disputed_at: row.get(12)?,
        decayed_turns: row.get(13)?,
    })
}

use rusqlite::OptionalExtension;
