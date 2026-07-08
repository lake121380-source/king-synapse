//! Semantic interpretation layer for rule-generated edge candidates.
//!
//! Phase 1c keeps candidate discovery deterministic: co-retrieval proposes
//! pairs, then a semantic judge decides whether the candidate has cognitive
//! meaning and which reasoning relation it supports.

use super::generator::{hypothesis_id, EdgeHypothesisGenerator};
use super::model::{EdgeEvidence, EdgeHypothesis, EdgeRelation, RetrievalContext};
use super::store_ext::HypothesisStore;
use crate::error::{Error, Result};
use crate::model::{Memory, MemoryKind};
use crate::store::Store;
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

const SEMANTIC_JUDGE_PROMPT_VERSION: &str = "phase1c-semantic-edge-judge-v2";

/// How accepted semantic judgements are written back into hypotheses.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SemanticEdgeMode {
    /// Do not run a semantic judge.
    Off,
    /// Reject noise, but keep the original candidate relation.
    Filter,
    /// Reject noise and replace the candidate relation with a semantic one.
    Classify,
}

impl SemanticEdgeMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Off => "off",
            Self::Filter => "filter",
            Self::Classify => "classify",
        }
    }
}

impl Default for SemanticEdgeMode {
    fn default() -> Self {
        Self::Off
    }
}

/// Input seen by an edge semantic judge.
#[derive(Clone, Copy)]
pub struct EdgeJudgeInput<'a> {
    pub context: &'a RetrievalContext<'a>,
    pub candidate: &'a EdgeHypothesis,
    pub memory_a: &'a Memory,
    pub memory_b: &'a Memory,
    pub co_occurrence: &'a EdgeCandidateEvidence,
    pub existing_evidence: &'a [EdgeEvidence],
}

/// Evidence package for the rule-generated candidate itself.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EdgeCandidateEvidence {
    pub observations: usize,
    pub distinct_contexts: usize,
    pub context_hashes: Vec<String>,
    pub context_tags: Vec<String>,
    pub recent_queries: Vec<String>,
}

impl EdgeCandidateEvidence {
    fn record(&mut self, context: &RetrievalContext<'_>) {
        self.observations += 1;
        push_unique_bounded(&mut self.context_hashes, context.query_context_hash, 12);
        push_unique_bounded(&mut self.context_tags, context.query_context_tag, 12);
        push_unique_bounded(&mut self.recent_queries, context.query, 5);
        self.distinct_contexts = self.context_hashes.len();
    }
}

/// Judge output. A valid judgement should choose one of the reasoning
/// relations: supports, explains, or predicts.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EdgeJudgement {
    pub valid: bool,
    pub relation: Option<EdgeRelation>,
    pub confidence: f32,
    pub reason_category: EdgeReasonCategory,
    pub reason: String,
}

impl EdgeJudgement {
    pub fn accept(relation: EdgeRelation, confidence: f32, reason: impl Into<String>) -> Self {
        Self {
            valid: true,
            relation: Some(relation),
            confidence: confidence.clamp(0.0, 1.0),
            reason_category: EdgeReasonCategory::Semantic,
            reason: reason.into(),
        }
    }

    pub fn reject(confidence: f32, reason: impl Into<String>) -> Self {
        Self {
            valid: false,
            relation: None,
            confidence: confidence.clamp(0.0, 1.0),
            reason_category: EdgeReasonCategory::None,
            reason: reason.into(),
        }
    }

    pub fn with_reason_category(mut self, category: EdgeReasonCategory) -> Self {
        self.reason_category = category;
        self
    }
}

/// Fine-grained reason taxonomy for audit. This does not yet change graph
/// activation semantics; graph relations remain supports/explains/predicts.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EdgeReasonCategory {
    Semantic,
    Causal,
    Functional,
    TemporalDependency,
    SameTopic,
    Contradiction,
    None,
}

impl EdgeReasonCategory {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Semantic => "semantic",
            Self::Causal => "causal",
            Self::Functional => "functional",
            Self::TemporalDependency => "temporal_dependency",
            Self::SameTopic => "same_topic",
            Self::Contradiction => "contradiction",
            Self::None => "none",
        }
    }
}

/// Semantic judge contract. Production implementations can call DeepSeek,
/// Claude, GPT, or a local model; tests can use deterministic judges.
pub trait EdgeSemanticJudge: Send + Sync {
    fn name(&self) -> &'static str;
    fn evaluate(&self, input: EdgeJudgeInput<'_>) -> Result<EdgeJudgement>;

    fn evaluate_batch(&self, inputs: &[EdgeJudgeInput<'_>]) -> Result<Vec<EdgeJudgement>> {
        inputs.iter().map(|input| self.evaluate(*input)).collect()
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct SemanticJudgeCacheStats {
    pub hits: usize,
    pub misses: usize,
    pub writes: usize,
}

/// Persistent cache for deterministic semantic judge inputs.
///
/// The cache key intentionally uses memory content/kind and semantic context,
/// not runtime memory IDs, because eval datasets are loaded into fresh
/// in-memory stores for each run.
pub struct CachedSemanticJudge<J> {
    judge: J,
    conn: Mutex<Connection>,
    namespace: String,
    stats: Arc<Mutex<SemanticJudgeCacheStats>>,
}

#[derive(Clone)]
pub struct SemanticJudgeCacheStatsHandle {
    stats: Arc<Mutex<SemanticJudgeCacheStats>>,
}

impl SemanticJudgeCacheStatsHandle {
    pub fn stats(&self) -> Result<SemanticJudgeCacheStats> {
        self.stats
            .lock()
            .map(|stats| *stats)
            .map_err(|_| Error::Invalid("semantic judge cache stats lock poisoned".to_string()))
    }
}

impl<J> CachedSemanticJudge<J>
where
    J: EdgeSemanticJudge,
{
    pub fn open(judge: J, path: impl AsRef<Path>, namespace: impl Into<String>) -> Result<Self> {
        let path = path.as_ref();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = Connection::open(path)?;
        init_semantic_judge_cache(&conn)?;
        Ok(Self {
            judge,
            conn: Mutex::new(conn),
            namespace: namespace.into(),
            stats: Arc::new(Mutex::new(SemanticJudgeCacheStats::default())),
        })
    }

    pub fn stats(&self) -> Result<SemanticJudgeCacheStats> {
        self.stats
            .lock()
            .map(|stats| *stats)
            .map_err(|_| Error::Invalid("semantic judge cache stats lock poisoned".to_string()))
    }

    pub fn stats_handle(&self) -> SemanticJudgeCacheStatsHandle {
        SemanticJudgeCacheStatsHandle {
            stats: Arc::clone(&self.stats),
        }
    }

    fn lookup(&self, key: &str) -> Result<Option<EdgeJudgement>> {
        let conn = self
            .conn
            .lock()
            .map_err(|_| Error::Invalid("semantic judge cache lock poisoned".to_string()))?;
        let cached = conn
            .query_row(
                "SELECT judgement_json FROM semantic_judge_cache WHERE cache_key = ?1",
                params![key],
                |row| row.get::<_, String>(0),
            )
            .optional()?;
        cached
            .map(|json| serde_json::from_str(&json).map_err(Error::from))
            .transpose()
    }

    fn store(&self, key: &str, judgement: &EdgeJudgement) -> Result<()> {
        let judgement_json = serde_json::to_string(judgement)?;
        let now = chrono::Utc::now().timestamp();
        let conn = self
            .conn
            .lock()
            .map_err(|_| Error::Invalid("semantic judge cache lock poisoned".to_string()))?;
        conn.execute(
            "INSERT INTO semantic_judge_cache \
             (cache_key, judge_name, namespace, prompt_version, judgement_json, created_at, last_used_at, hits) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6, 0) \
             ON CONFLICT(cache_key) DO UPDATE SET \
             judgement_json = excluded.judgement_json, \
             last_used_at = excluded.last_used_at",
            params![
                key,
                self.judge.name(),
                self.namespace,
                SEMANTIC_JUDGE_PROMPT_VERSION,
                judgement_json,
                now,
            ],
        )?;
        Ok(())
    }

    fn bump_hit(&self, key: &str) -> Result<()> {
        let now = chrono::Utc::now().timestamp();
        let conn = self
            .conn
            .lock()
            .map_err(|_| Error::Invalid("semantic judge cache lock poisoned".to_string()))?;
        conn.execute(
            "UPDATE semantic_judge_cache \
             SET hits = hits + 1, last_used_at = ?2 \
             WHERE cache_key = ?1",
            params![key, now],
        )?;
        Ok(())
    }

    fn record_stats(&self, f: impl FnOnce(&mut SemanticJudgeCacheStats)) -> Result<()> {
        let mut stats = self
            .stats
            .lock()
            .map_err(|_| Error::Invalid("semantic judge cache stats lock poisoned".to_string()))?;
        f(&mut stats);
        Ok(())
    }
}

impl<J> EdgeSemanticJudge for CachedSemanticJudge<J>
where
    J: EdgeSemanticJudge,
{
    fn name(&self) -> &'static str {
        self.judge.name()
    }

    fn evaluate(&self, input: EdgeJudgeInput<'_>) -> Result<EdgeJudgement> {
        let key = semantic_judge_cache_key(self.judge.name(), &self.namespace, &input)?;
        if let Some(judgement) = self.lookup(&key)? {
            self.bump_hit(&key)?;
            self.record_stats(|stats| stats.hits += 1)?;
            return Ok(judgement);
        }

        self.record_stats(|stats| stats.misses += 1)?;
        let judgement = self.judge.evaluate(input)?;
        self.store(&key, &judgement)?;
        self.record_stats(|stats| stats.writes += 1)?;
        Ok(judgement)
    }

    fn evaluate_batch(&self, inputs: &[EdgeJudgeInput<'_>]) -> Result<Vec<EdgeJudgement>> {
        let mut output: Vec<Option<EdgeJudgement>> = vec![None; inputs.len()];
        let mut missed_inputs = Vec::new();
        let mut missed_keys = Vec::new();
        let mut missed_indices = Vec::new();

        for (index, input) in inputs.iter().enumerate() {
            let key = semantic_judge_cache_key(self.judge.name(), &self.namespace, input)?;
            if let Some(judgement) = self.lookup(&key)? {
                self.bump_hit(&key)?;
                self.record_stats(|stats| stats.hits += 1)?;
                output[index] = Some(judgement);
            } else {
                self.record_stats(|stats| stats.misses += 1)?;
                missed_inputs.push(*input);
                missed_keys.push(key);
                missed_indices.push(index);
            }
        }

        if !missed_inputs.is_empty() {
            let judgements = self.judge.evaluate_batch(&missed_inputs)?;
            if judgements.len() != missed_inputs.len() {
                return Err(Error::Invalid(format!(
                    "semantic judge batch returned {} judgement(s) for {} input(s)",
                    judgements.len(),
                    missed_inputs.len()
                )));
            }
            for (index, key, judgement) in missed_indices
                .into_iter()
                .zip(missed_keys.into_iter())
                .zip(judgements.into_iter())
                .map(|((index, key), judgement)| (index, key, judgement))
            {
                self.store(&key, &judgement)?;
                self.record_stats(|stats| stats.writes += 1)?;
                output[index] = Some(judgement);
            }
        }

        output
            .into_iter()
            .map(|judgement| {
                judgement.ok_or_else(|| {
                    Error::Invalid("semantic judge batch left an output slot empty".to_string())
                })
            })
            .collect()
    }
}

fn init_semantic_judge_cache(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS semantic_judge_cache (
            cache_key       TEXT PRIMARY KEY,
            judge_name      TEXT NOT NULL,
            namespace       TEXT NOT NULL,
            prompt_version  TEXT NOT NULL,
            judgement_json  TEXT NOT NULL,
            created_at      INTEGER NOT NULL,
            last_used_at    INTEGER NOT NULL,
            hits            INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_semantic_judge_cache_judge
            ON semantic_judge_cache(judge_name, namespace);
        CREATE INDEX IF NOT EXISTS idx_semantic_judge_cache_last_used
            ON semantic_judge_cache(last_used_at);",
    )?;
    Ok(())
}

pub fn default_semantic_judge_cache_path() -> PathBuf {
    crate::config::data_dir().join("semantic_judge_cache.sqlite")
}

fn semantic_judge_cache_key(
    judge_name: &str,
    namespace: &str,
    input: &EdgeJudgeInput<'_>,
) -> Result<String> {
    let existing_evidence: Vec<&str> = input
        .existing_evidence
        .iter()
        .rev()
        .take(3)
        .map(|e| e.reason_summary.as_str())
        .collect();
    let canonical = serde_json::json!({
        "prompt_version": SEMANTIC_JUDGE_PROMPT_VERSION,
        "judge_name": judge_name,
        "namespace": namespace,
        "context": {
            "query": input.context.query,
            "context_hash": input.context.query_context_hash,
            "context_tag": input.context.query_context_tag,
        },
        "memory_a": {
            "kind": input.memory_a.kind.to_string(),
            "content": input.memory_a.content,
        },
        "memory_b": {
            "kind": input.memory_b.kind.to_string(),
            "content": input.memory_b.content,
        },
        "candidate_relation": input.candidate.relation.as_str(),
        "co_occurrence": {
            "observations": input.co_occurrence.observations,
            "distinct_contexts": input.co_occurrence.distinct_contexts,
            "context_hashes": input.co_occurrence.context_hashes,
            "context_tags": input.co_occurrence.context_tags,
            "recent_queries": input.co_occurrence.recent_queries,
        },
        "existing_evidence": existing_evidence,
    });
    let bytes = serde_json::to_vec(&canonical)?;
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    Ok(format!("semjudge_{:x}", hasher.finalize()))
}

impl<T> EdgeSemanticJudge for Box<T>
where
    T: EdgeSemanticJudge + ?Sized,
{
    fn name(&self) -> &'static str {
        (**self).name()
    }

    fn evaluate(&self, input: EdgeJudgeInput<'_>) -> Result<EdgeJudgement> {
        (**self).evaluate(input)
    }

    fn evaluate_batch(&self, inputs: &[EdgeJudgeInput<'_>]) -> Result<Vec<EdgeJudgement>> {
        (**self).evaluate_batch(inputs)
    }
}

/// Accepted candidate paired with the judgement that accepted it.
#[derive(Debug, Clone)]
pub struct JudgedEdgeHypothesis {
    pub hypothesis: EdgeHypothesis,
    pub judgement: EdgeJudgement,
}

impl JudgedEdgeHypothesis {
    pub fn evidence_reason(&self, judge_name: &str) -> String {
        let relation = self
            .judgement
            .relation
            .map(|r| r.as_str())
            .unwrap_or(self.hypothesis.relation.as_str());
        format!(
            "{}:{} category={} confidence={:.2}; {}",
            judge_name,
            relation,
            self.judgement.reason_category.as_str(),
            self.judgement.confidence,
            self.judgement.reason
        )
    }
}

/// Rejected candidate retained for precision/hub-suppression metrics.
#[derive(Debug, Clone)]
pub struct RejectedEdgeCandidate {
    pub candidate: EdgeHypothesis,
    pub judgement: EdgeJudgement,
}

#[derive(Debug, Clone, Default)]
pub struct JudgedEdgeGeneration {
    pub accepted: Vec<JudgedEdgeHypothesis>,
    pub rejected: Vec<RejectedEdgeCandidate>,
}

/// Wraps a deterministic candidate generator with a semantic judge.
pub struct JudgedEdgeGenerator<G, J> {
    candidate_generator: G,
    judge: J,
    mode: SemanticEdgeMode,
    candidate_history: Mutex<HashMap<String, EdgeCandidateEvidence>>,
}

impl<G, J> JudgedEdgeGenerator<G, J>
where
    G: EdgeHypothesisGenerator,
    J: EdgeSemanticJudge,
{
    pub fn new(candidate_generator: G, judge: J) -> Self {
        Self {
            candidate_generator,
            judge,
            mode: SemanticEdgeMode::Classify,
            candidate_history: Mutex::new(HashMap::new()),
        }
    }

    pub fn with_mode(mut self, mode: SemanticEdgeMode) -> Self {
        self.mode = mode;
        self
    }

    pub fn mode(&self) -> SemanticEdgeMode {
        self.mode
    }

    pub fn judge_name(&self) -> &'static str {
        self.judge.name()
    }

    pub fn generate(
        &self,
        store: &Store,
        context: &RetrievalContext<'_>,
    ) -> Result<JudgedEdgeGeneration> {
        let mut generated = JudgedEdgeGeneration::default();
        if self.mode == SemanticEdgeMode::Off {
            return Ok(generated);
        }

        let mut candidates = Vec::new();
        let mut memories_a = Vec::new();
        let mut memories_b = Vec::new();
        let mut co_occurrences = Vec::new();
        let mut evidence_sets = Vec::new();

        for candidate in self.candidate_generator.generate(context) {
            let memory_a = store
                .get(&candidate.source)?
                .ok_or_else(|| Error::NotFound(candidate.source.clone()))?;
            let memory_b = store
                .get(&candidate.target)?
                .ok_or_else(|| Error::NotFound(candidate.target.clone()))?;
            let co_occurrence = self.record_candidate_observation(&candidate, context)?;
            let existing_evidence = store.get_evidence(&candidate.id)?;

            candidates.push(candidate);
            memories_a.push(memory_a);
            memories_b.push(memory_b);
            co_occurrences.push(co_occurrence);
            evidence_sets.push(existing_evidence);
        }

        let inputs: Vec<EdgeJudgeInput<'_>> = candidates
            .iter()
            .zip(memories_a.iter())
            .zip(memories_b.iter())
            .zip(co_occurrences.iter())
            .zip(evidence_sets.iter())
            .map(
                |((((candidate, memory_a), memory_b), co_occurrence), existing_evidence)| {
                    EdgeJudgeInput {
                        context,
                        candidate,
                        memory_a,
                        memory_b,
                        co_occurrence,
                        existing_evidence,
                    }
                },
            )
            .collect();
        let judgements = self.judge.evaluate_batch(&inputs)?;
        if judgements.len() != candidates.len() {
            return Err(Error::Invalid(format!(
                "semantic judge returned {} judgement(s) for {} candidate(s)",
                judgements.len(),
                candidates.len()
            )));
        }

        for (candidate, judgement) in candidates.into_iter().zip(judgements.into_iter()) {
            if !judgement.valid {
                generated.rejected.push(RejectedEdgeCandidate {
                    candidate,
                    judgement,
                });
                continue;
            }

            let mut hypothesis = candidate.clone();
            if self.mode == SemanticEdgeMode::Classify {
                let Some(relation) = judgement.relation else {
                    generated.rejected.push(RejectedEdgeCandidate {
                        candidate,
                        judgement: EdgeJudgement::reject(
                            judgement.confidence,
                            "semantic judge accepted without a relation",
                        ),
                    });
                    continue;
                };
                if !relation.is_reasoning() {
                    generated.rejected.push(RejectedEdgeCandidate {
                        candidate,
                        judgement: EdgeJudgement::reject(
                            judgement.confidence,
                            "semantic judge returned a non-reasoning relation",
                        ),
                    });
                    continue;
                }
                hypothesis.relation = relation;
                hypothesis.id = hypothesis_id(&hypothesis.source, &hypothesis.target, relation);
            }
            hypothesis.confidence = hypothesis.confidence.max(judgement.confidence);
            generated.accepted.push(JudgedEdgeHypothesis {
                hypothesis,
                judgement,
            });
        }

        Ok(generated)
    }

    fn record_candidate_observation(
        &self,
        candidate: &EdgeHypothesis,
        context: &RetrievalContext<'_>,
    ) -> Result<EdgeCandidateEvidence> {
        let mut history = self
            .candidate_history
            .lock()
            .map_err(|_| Error::Invalid("semantic candidate history lock poisoned".to_string()))?;
        let evidence = history.entry(candidate.id.clone()).or_default();
        evidence.record(context);
        Ok(evidence.clone())
    }
}

/// Offline deterministic stand-in for an LLM semantic judge.
///
/// This is intentionally conservative enough for tests and local evals, but
/// the production path should plug in a model-backed judge through the same
/// `EdgeSemanticJudge` trait.
#[derive(Debug, Clone)]
pub struct HeuristicSemanticJudge {
    min_confidence: f32,
}

impl HeuristicSemanticJudge {
    pub fn new(min_confidence: f32) -> Self {
        Self {
            min_confidence: min_confidence.clamp(0.0, 1.0),
        }
    }
}

/// DeepSeek-backed semantic judge. This adapter validates rule-generated
/// candidates; it never invents new candidate pairs.
#[derive(Debug, Clone)]
pub struct DeepSeekSemanticJudge {
    api_key: String,
    base_url: String,
    model: String,
    timeout: Duration,
    executor: SemanticJudgeExecutorConfig,
}

/// Execution controls for model-backed semantic judge requests.
#[derive(Debug, Clone)]
pub struct SemanticJudgeExecutorConfig {
    pub batch_size: usize,
    pub max_inflight: usize,
    pub retries: usize,
    pub retry_backoff: Duration,
}

impl Default for SemanticJudgeExecutorConfig {
    fn default() -> Self {
        Self {
            batch_size: 20,
            max_inflight: 3,
            retries: 2,
            retry_backoff: Duration::from_millis(500),
        }
    }
}

impl SemanticJudgeExecutorConfig {
    pub fn sanitized(mut self) -> Self {
        self.batch_size = self.batch_size.clamp(1, 50);
        self.max_inflight = self.max_inflight.clamp(1, 10);
        self.retries = self.retries.min(5);
        self
    }
}

impl DeepSeekSemanticJudge {
    pub fn from_env() -> Result<Self> {
        let raw_api_key = std::env::var("DEEPSEEK_API_KEY").map_err(|_| {
            Error::Invalid("DEEPSEEK_API_KEY is required for DeepSeekSemanticJudge".to_string())
        })?;
        let api_key = normalize_bearer_token(&raw_api_key);
        if api_key.is_empty() {
            return Err(Error::Invalid(
                "DEEPSEEK_API_KEY is empty after normalization".to_string(),
            ));
        }
        Ok(Self {
            api_key,
            base_url: std::env::var("DEEPSEEK_BASE_URL")
                .unwrap_or_else(|_| "https://api.deepseek.com".to_string()),
            model: std::env::var("DEEPSEEK_JUDGE_MODEL")
                .unwrap_or_else(|_| "deepseek-chat".to_string()),
            timeout: Duration::from_secs(
                std::env::var("DEEPSEEK_JUDGE_TIMEOUT_SECS")
                    .ok()
                    .and_then(|v| v.parse::<u64>().ok())
                    .unwrap_or(60),
            ),
            executor: deepseek_executor_config_from_env(),
        })
    }

    pub fn new(
        api_key: impl Into<String>,
        base_url: impl Into<String>,
        model: impl Into<String>,
    ) -> Self {
        Self {
            api_key: api_key.into(),
            base_url: base_url.into(),
            model: model.into(),
            timeout: Duration::from_secs(60),
            executor: SemanticJudgeExecutorConfig::default(),
        }
    }

    pub fn with_timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    pub fn with_executor_config(mut self, config: SemanticJudgeExecutorConfig) -> Self {
        self.executor = config.sanitized();
        self
    }

    pub fn cache_namespace(&self) -> String {
        format!("{}|{}", self.base_url.trim_end_matches('/'), self.model)
    }
}

fn deepseek_executor_config_from_env() -> SemanticJudgeExecutorConfig {
    SemanticJudgeExecutorConfig {
        batch_size: env_usize("DEEPSEEK_JUDGE_BATCH_SIZE").unwrap_or(20),
        max_inflight: env_usize("DEEPSEEK_JUDGE_MAX_INFLIGHT").unwrap_or(3),
        retries: env_usize("DEEPSEEK_JUDGE_RETRIES").unwrap_or(2),
        retry_backoff: Duration::from_millis(
            env_usize("DEEPSEEK_JUDGE_RETRY_BACKOFF_MS").unwrap_or(500) as u64,
        ),
    }
    .sanitized()
}

fn env_usize(name: &str) -> Option<usize> {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
}

fn normalize_bearer_token(value: &str) -> String {
    value
        .trim()
        .trim_matches('"')
        .trim_matches('\'')
        .strip_prefix("Bearer ")
        .or_else(|| value.trim().strip_prefix("bearer "))
        .unwrap_or(value.trim())
        .trim()
        .to_string()
}

fn summarize_response_body(body: &str) -> String {
    if let Ok(value) = serde_json::from_str::<Value>(body) {
        if let Some(error) = value.get("error") {
            let message = error
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("no error message");
            let kind = error
                .get("type")
                .and_then(Value::as_str)
                .unwrap_or("unknown_error");
            let code = error.get("code").and_then(Value::as_str).unwrap_or("");
            return format!("error_type={kind}; code={code}; message={message}");
        }
    }
    let trimmed = body.trim();
    if trimmed.len() > 240 {
        format!("body={}...", &trimmed[..240])
    } else {
        format!("body={trimmed}")
    }
}

impl EdgeSemanticJudge for DeepSeekSemanticJudge {
    fn name(&self) -> &'static str {
        "deepseek_semantic_judge"
    }

    fn evaluate(&self, input: EdgeJudgeInput<'_>) -> Result<EdgeJudgement> {
        let prompt = semantic_judge_prompt(&input);
        let content = self.request_judge_content(prompt, 220)?;
        parse_judgement_json(&content)
    }

    fn evaluate_batch(&self, inputs: &[EdgeJudgeInput<'_>]) -> Result<Vec<EdgeJudgement>> {
        if inputs.is_empty() {
            return Ok(Vec::new());
        }
        let batch_size = self.executor.batch_size.max(1);
        if inputs.len() <= batch_size {
            return self.evaluate_batch_chunk(inputs);
        }

        let mut output = Vec::with_capacity(inputs.len());
        let max_inflight = self.executor.max_inflight.max(1);
        let chunks: Vec<&[EdgeJudgeInput<'_>]> = inputs.chunks(batch_size).collect();
        for wave in chunks.chunks(max_inflight) {
            let wave_results = thread::scope(|scope| {
                let mut handles = Vec::with_capacity(wave.len());
                for chunk in wave {
                    let judge = self.clone();
                    handles.push(scope.spawn(move || judge.evaluate_batch_chunk(chunk)));
                }

                let mut results = Vec::with_capacity(handles.len());
                for handle in handles {
                    let result = handle.join().map_err(|_| {
                        Error::Invalid("semantic judge worker panicked".to_string())
                    })??;
                    results.push(result);
                }
                Ok::<Vec<Vec<EdgeJudgement>>, Error>(results)
            })?;

            for batch in wave_results {
                output.extend(batch);
            }
        }

        Ok(output)
    }
}

impl DeepSeekSemanticJudge {
    fn evaluate_batch_chunk(&self, inputs: &[EdgeJudgeInput<'_>]) -> Result<Vec<EdgeJudgement>> {
        if inputs.is_empty() {
            return Ok(Vec::new());
        }
        if inputs.len() == 1 {
            return Ok(vec![self.evaluate(inputs[0])?]);
        }
        let prompt = semantic_judge_batch_prompt(inputs);
        let max_tokens = 180usize.saturating_mul(inputs.len()).clamp(360, 4096);
        let content = self.request_judge_content(prompt, max_tokens)?;
        parse_batch_judgement_json(&content, inputs.len())
    }
}

impl DeepSeekSemanticJudge {
    fn request_judge_content(&self, prompt: String, max_tokens: usize) -> Result<String> {
        let mut last_error = None;
        for attempt in 0..=self.executor.retries {
            match self.request_judge_content_once(prompt.clone(), max_tokens) {
                Ok(content) => return Ok(content),
                Err(err)
                    if attempt < self.executor.retries && is_retryable_deepseek_error(&err) =>
                {
                    last_error = Some(err);
                    let backoff = self.executor.retry_backoff.mul_f64((attempt + 1) as f64);
                    thread::sleep(backoff);
                }
                Err(err) => return Err(err),
            }
        }
        Err(last_error.unwrap_or_else(|| {
            Error::Invalid("DeepSeek semantic judge request failed after retries".to_string())
        }))
    }

    fn request_judge_content_once(&self, prompt: String, max_tokens: usize) -> Result<String> {
        let client = reqwest::blocking::Client::builder()
            .timeout(self.timeout)
            .build()
            .map_err(|e| Error::Invalid(format!("build DeepSeek client: {e}")))?;
        let payload = serde_json::json!({
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict semantic edge judge for a long-term memory graph. Validate only the given candidate pair. Never invent new memories or new candidate pairs. Return JSON only."
                },
                { "role": "user", "content": prompt }
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": { "type": "json_object" }
        });
        let response = client
            .post(format!(
                "{}/chat/completions",
                self.base_url.trim_end_matches('/')
            ))
            .bearer_auth(&self.api_key)
            .json(&payload)
            .send()
            .map_err(|e| Error::Invalid(format!("DeepSeek semantic judge request failed: {e}")))?;
        let status = response.status();
        let response_text = response
            .text()
            .map_err(|e| Error::Invalid(format!("read DeepSeek response: {e}")))?;
        if !status.is_success() {
            return Err(Error::Invalid(format!(
                "DeepSeek semantic judge request failed: HTTP {status}; {}",
                summarize_response_body(&response_text)
            )));
        }
        let response: Value = serde_json::from_str(&response_text)
            .map_err(|e| Error::Invalid(format!("parse DeepSeek response: {e}")))?;

        let content = response
            .pointer("/choices/0/message/content")
            .and_then(Value::as_str)
            .or_else(|| {
                response
                    .pointer("/choices/0/message/reasoning_content")
                    .and_then(Value::as_str)
            })
            .ok_or_else(|| {
                Error::Invalid("DeepSeek semantic judge returned empty content".to_string())
            })?;
        Ok(content.to_string())
    }
}

fn is_retryable_deepseek_error(error: &Error) -> bool {
    let message = error.to_string().to_ascii_lowercase();
    message.contains("http 429")
        || message.contains("http 5")
        || message.contains("request failed")
        || message.contains("timed out")
        || message.contains("timeout")
        || message.contains("connection")
}

impl Default for HeuristicSemanticJudge {
    fn default() -> Self {
        Self::new(0.65)
    }
}

impl EdgeSemanticJudge for HeuristicSemanticJudge {
    fn name(&self) -> &'static str {
        "heuristic_semantic_judge"
    }

    fn evaluate(&self, input: EdgeJudgeInput<'_>) -> Result<EdgeJudgement> {
        if is_generic_exchange(&input.memory_a.content)
            && is_generic_exchange(&input.memory_b.content)
        {
            return Ok(EdgeJudgement::reject(
                0.90,
                "both memories are generic conversational openings, not a durable knowledge relation",
            ));
        }

        let a_tokens = meaningful_tokens(&input.memory_a.content);
        let b_tokens = meaningful_tokens(&input.memory_b.content);
        let q_tokens = meaningful_tokens(input.context.query);
        if a_tokens.is_empty() || b_tokens.is_empty() {
            return Ok(EdgeJudgement::reject(
                0.70,
                "one side has too little semantic content to justify an edge",
            ));
        }

        let shared = intersection_count(&a_tokens, &b_tokens);
        let context_links =
            intersection_count(&a_tokens, &q_tokens) + intersection_count(&b_tokens, &q_tokens);
        let specificity = ((a_tokens.len() + b_tokens.len()) as f32 / 14.0).min(1.0);
        let relation = classify_relation(&input);
        let cue_bonus = relation_cue_bonus(&input, relation);
        let confidence = (0.42
            + 0.15 * shared.min(3) as f32
            + 0.06 * context_links.min(3) as f32
            + 0.10 * specificity
            + cue_bonus)
            .min(0.95);

        if shared == 0 && context_links < 2 && cue_bonus < 0.15 {
            return Ok(EdgeJudgement::reject(
                confidence,
                "candidate lacks shared concepts or contextual support",
            ));
        }

        if confidence < self.min_confidence {
            return Ok(EdgeJudgement::reject(
                confidence,
                "semantic signal is below the acceptance threshold",
            ));
        }

        Ok(EdgeJudgement::accept(
            relation,
            confidence,
            relation_reason(relation, shared, context_links),
        ))
    }
}

fn classify_relation(input: &EdgeJudgeInput<'_>) -> EdgeRelation {
    let a = input.memory_a.content.to_ascii_lowercase();
    let b = input.memory_b.content.to_ascii_lowercase();
    let q = input.context.query.to_ascii_lowercase();

    if contains_any(
        &b,
        &["likely", "future", "next", "might", "expect", "predict"],
    ) || contains_any(&q, &["future", "next", "likely"])
    {
        return EdgeRelation::Predicts;
    }

    if input.memory_a.kind == MemoryKind::Preference
        || contains_any(&a, &["prefers", "likes", "because", "reason", "motivation"])
        || (contains_any(&a, &["control", "performance", "safety"])
            && contains_any(&b, &["chooses", "selected", "instead", "uses"]))
    {
        return EdgeRelation::Explains;
    }

    EdgeRelation::Supports
}

fn semantic_judge_prompt(input: &EdgeJudgeInput<'_>) -> String {
    let evidence_summaries: Vec<&str> = input
        .existing_evidence
        .iter()
        .rev()
        .take(3)
        .map(|e| e.reason_summary.as_str())
        .collect();
    serde_json::json!({
        "task": "Given this user's current retrieval context and candidate co-retrieval evidence, decide whether memory_a should activate memory_b in future retrieval.",
        "allowed_relations": ["supports", "explains", "predicts", "reject"],
        "rules": [
            "Do not create a new edge or mention memories outside memory_a and memory_b.",
            "Reject generic co-retrieval, greeting/opening artifacts, and broad topical overlap without durable cognitive meaning for future retrieval.",
            "Accept only when the edge would be useful as durable semantic memory consolidation, not because the two texts merely appeared together once.",
            "High co-occurrence frequency alone is NOT sufficient evidence. A valid edge requires a plausible causal, semantic, functional, or temporal relationship.",
            "Use supports when one memory gives evidence or context for interpreting the other.",
            "Use explains when one memory gives a reason, preference, cause, or motivation for the other.",
            "Use predicts when one memory gives directional evidence for a likely future interest, need, or behavior."
        ],
        "required_output": {
            "decision": "accept|reject",
            "valid": "boolean",
            "relation": "supports|explains|predicts|reject",
            "reason_category": "semantic|causal|functional|temporal_dependency|same_topic|contradiction|none",
            "confidence": "number between 0 and 1",
            "reason": "short explanation grounded only in the provided context and memories"
        },
        "query_context": {
            "query": input.context.query,
            "context_hash": input.context.query_context_hash,
            "context_tag": input.context.query_context_tag
        },
        "memory_a": {
            "kind": input.memory_a.kind.to_string(),
            "content": input.memory_a.content
        },
        "memory_b": {
            "kind": input.memory_b.kind.to_string(),
            "content": input.memory_b.content
        },
        "candidate_relation": input.candidate.relation.as_str(),
        "candidate_reason": "memory_a and memory_b were co-retrieved by the rule candidate generator",
        "co_occurrence": {
            "observed_count": input.co_occurrence.observations,
            "distinct_contexts": input.co_occurrence.distinct_contexts,
            "context_tags": &input.co_occurrence.context_tags,
            "recent_queries": &input.co_occurrence.recent_queries
        },
        "existing_evidence": evidence_summaries,
    })
    .to_string()
}

fn semantic_judge_batch_prompt(inputs: &[EdgeJudgeInput<'_>]) -> String {
    let candidates: Vec<Value> = inputs
        .iter()
        .enumerate()
        .map(|(index, input)| {
            let evidence_summaries: Vec<&str> = input
                .existing_evidence
                .iter()
                .rev()
                .take(3)
                .map(|e| e.reason_summary.as_str())
                .collect();
            serde_json::json!({
                "id": batch_candidate_id(index),
                "memory_a": {
                    "kind": input.memory_a.kind.to_string(),
                    "content": input.memory_a.content,
                },
                "memory_b": {
                    "kind": input.memory_b.kind.to_string(),
                    "content": input.memory_b.content,
                },
                "candidate_relation": input.candidate.relation.as_str(),
                "candidate_reason": "memory_a and memory_b were co-retrieved by the rule candidate generator",
                "co_occurrence": {
                    "observed_count": input.co_occurrence.observations,
                    "distinct_contexts": input.co_occurrence.distinct_contexts,
                    "context_tags": &input.co_occurrence.context_tags,
                    "recent_queries": &input.co_occurrence.recent_queries,
                },
                "existing_evidence": evidence_summaries,
            })
        })
        .collect();
    let first = &inputs[0];
    serde_json::json!({
        "task": "Return JSON only. Given this user's current retrieval context and each candidate's co-retrieval evidence, decide whether memory_a should activate memory_b in future retrieval.",
        "allowed_relations": ["supports", "explains", "predicts", "reject"],
        "rules": [
            "Judge each candidate independently. Do not let one candidate influence another.",
            "Return exactly one judgement for each provided candidate id. Preserve the id exactly; ordering does not matter.",
            "Do not create a new edge or mention memories outside memory_a and memory_b.",
            "Reject generic co-retrieval, greeting/opening artifacts, and broad topical overlap without durable cognitive meaning for future retrieval.",
            "Accept only when the edge would be useful as durable semantic memory consolidation, not because the two texts merely appeared together once.",
            "High co-occurrence frequency alone is NOT sufficient evidence. A valid edge requires a plausible causal, semantic, functional, or temporal relationship.",
            "Use supports when one memory gives evidence or context for interpreting the other.",
            "Use explains when one memory gives a reason, preference, cause, or motivation for the other.",
            "Use predicts when one memory gives directional evidence for a likely future interest, need, or behavior."
        ],
        "required_output": {
            "judgements": [
                {
                    "id": "candidate id from input",
                    "decision": "accept|reject",
                    "valid": "boolean",
                    "relation": "supports|explains|predicts|reject",
                    "reason_category": "semantic|causal|functional|temporal_dependency|same_topic|contradiction|none",
                    "confidence": "number between 0 and 1",
                    "reason": "short explanation grounded only in the provided context and memories"
                }
            ]
        },
        "query_context": {
            "query": first.context.query,
            "context_hash": first.context.query_context_hash,
            "context_tag": first.context.query_context_tag,
        },
        "candidates": candidates,
    })
    .to_string()
}

fn batch_candidate_id(index: usize) -> String {
    format!("edge_{index:04}")
}

fn parse_judgement_json(content: &str) -> Result<EdgeJudgement> {
    let value: Value = serde_json::from_str(content)
        .or_else(|_| extract_json_object(content).and_then(|json| serde_json::from_str(json)))?;
    parse_judgement_value(&value)
}

fn parse_batch_judgement_json(content: &str, expected_len: usize) -> Result<Vec<EdgeJudgement>> {
    let value: Value = serde_json::from_str(content)
        .or_else(|_| extract_json_object(content).and_then(|json| serde_json::from_str(json)))?;
    let judgements = value
        .get("judgements")
        .or_else(|| value.get("results"))
        .and_then(Value::as_array)
        .ok_or_else(|| {
            Error::Invalid("semantic judge batch response missing judgements array".to_string())
        })?;

    let mut by_id: HashMap<String, EdgeJudgement> = HashMap::new();
    for item in judgements {
        let id = item
            .get("id")
            .and_then(Value::as_str)
            .ok_or_else(|| Error::Invalid("semantic judge batch item missing id".to_string()))?
            .trim()
            .to_string();
        if by_id.contains_key(&id) {
            return Err(Error::Invalid(format!(
                "semantic judge batch returned duplicate id: {id}"
            )));
        }
        by_id.insert(id, parse_judgement_value(item)?);
    }

    let mut output = Vec::with_capacity(expected_len);
    for index in 0..expected_len {
        let id = batch_candidate_id(index);
        let judgement = by_id
            .remove(&id)
            .ok_or_else(|| Error::Invalid(format!("semantic judge batch missing id: {id}")))?;
        output.push(judgement);
    }
    if !by_id.is_empty() {
        let extra: Vec<String> = by_id.into_keys().collect();
        return Err(Error::Invalid(format!(
            "semantic judge batch returned unexpected id(s): {}",
            extra.join(",")
        )));
    }
    Ok(output)
}

fn parse_judgement_value(value: &Value) -> Result<EdgeJudgement> {
    let decision = value
        .get("decision")
        .and_then(Value::as_str)
        .map(|s| s.trim().to_ascii_lowercase());
    let raw_relation = value
        .get("relation")
        .and_then(Value::as_str)
        .map(|s| s.trim().to_ascii_lowercase());
    let relation = match raw_relation.as_deref() {
        Some("supports") => Some(EdgeRelation::Supports),
        Some("explains") => Some(EdgeRelation::Explains),
        Some("predicts") => Some(EdgeRelation::Predicts),
        Some("reject" | "co_activates" | "related" | "same_topic" | "none") | None => None,
        Some(_) => None,
    };
    let raw_valid = value
        .get("valid")
        .and_then(Value::as_bool)
        .unwrap_or_else(|| {
            decision
                .as_deref()
                .map(|d| d == "accept")
                .or_else(|| {
                    raw_relation
                        .as_deref()
                        .map(|r| matches!(r, "supports" | "explains" | "predicts"))
                })
                .unwrap_or(false)
        });
    let confidence = value
        .get("confidence")
        .and_then(Value::as_f64)
        .unwrap_or(0.0)
        .clamp(0.0, 1.0) as f32;
    let reason = value
        .get("reason")
        .and_then(Value::as_str)
        .unwrap_or("semantic judge did not provide a reason")
        .trim()
        .to_string();
    let reason_category = parse_reason_category(
        value
            .get("reason_category")
            .and_then(Value::as_str)
            .map(|s| s.trim().to_ascii_lowercase())
            .as_deref()
            .unwrap_or(if raw_valid { "semantic" } else { "none" }),
    )?;
    let explicit_reject = matches!(decision.as_deref(), Some("reject"))
        || matches!(raw_relation.as_deref(), Some("reject" | "none"));
    let valid = if explicit_reject {
        false
    } else if relation.is_some() {
        raw_valid
    } else {
        raw_valid && reason_category != EdgeReasonCategory::None && confidence >= 0.65
    };

    if !valid {
        return Ok(EdgeJudgement::reject(confidence, reason).with_reason_category(reason_category));
    }
    Ok(EdgeJudgement {
        valid: true,
        relation,
        confidence,
        reason_category,
        reason,
    })
}

fn parse_reason_category(value: &str) -> Result<EdgeReasonCategory> {
    match value {
        "supports" => Ok(EdgeReasonCategory::Semantic),
        "explains" => Ok(EdgeReasonCategory::Causal),
        "predicts" => Ok(EdgeReasonCategory::Functional),
        "semantic" => Ok(EdgeReasonCategory::Semantic),
        "causal" => Ok(EdgeReasonCategory::Causal),
        "functional" => Ok(EdgeReasonCategory::Functional),
        "temporal_dependency" => Ok(EdgeReasonCategory::TemporalDependency),
        "same_topic" => Ok(EdgeReasonCategory::SameTopic),
        "contradiction" => Ok(EdgeReasonCategory::Contradiction),
        "none" => Ok(EdgeReasonCategory::None),
        other => Err(Error::Invalid(format!(
            "semantic judge returned unsupported reason_category: {other}"
        ))),
    }
}

fn extract_json_object(content: &str) -> std::result::Result<&str, serde_json::Error> {
    let start = content.find('{').unwrap_or(0);
    let end = content.rfind('}').map(|i| i + 1).unwrap_or(content.len());
    Ok(&content[start..end])
}

fn push_unique_bounded(values: &mut Vec<String>, value: &str, limit: usize) {
    if value.trim().is_empty() || values.iter().any(|existing| existing == value) {
        return;
    }
    values.push(value.to_string());
    if values.len() > limit {
        values.remove(0);
    }
}

fn relation_cue_bonus(input: &EdgeJudgeInput<'_>, relation: EdgeRelation) -> f32 {
    let a = input.memory_a.content.to_ascii_lowercase();
    let b = input.memory_b.content.to_ascii_lowercase();
    match relation {
        EdgeRelation::Explains => {
            if input.memory_a.kind == MemoryKind::Preference
                || contains_any(&a, &["prefers", "likes", "because", "reason", "motivation"])
            {
                0.18
            } else {
                0.10
            }
        }
        EdgeRelation::Predicts => {
            if contains_any(
                &b,
                &["likely", "future", "next", "might", "expect", "predict"],
            ) {
                0.16
            } else {
                0.10
            }
        }
        EdgeRelation::Supports => 0.06,
        _ => 0.0,
    }
}

fn relation_reason(relation: EdgeRelation, shared: usize, context_links: usize) -> String {
    match relation {
        EdgeRelation::Supports => format!(
            "the memories share {shared} meaningful concept(s) and {context_links} query-context link(s), so one supports interpretation of the other"
        ),
        EdgeRelation::Explains => format!(
            "one memory expresses a preference or cause that explains the other; shared concepts={shared}, context links={context_links}"
        ),
        EdgeRelation::Predicts => format!(
            "one memory gives directional evidence for the other as a likely future interest; shared concepts={shared}, context links={context_links}"
        ),
        _ => "accepted semantic relation".to_string(),
    }
}

fn meaningful_tokens(text: &str) -> HashSet<String> {
    text.split(|c: char| !c.is_alphanumeric() && c != '_' && c != '-')
        .filter_map(|token| {
            let token = token.trim().to_ascii_lowercase();
            if token.len() < 3 || is_stopword(&token) {
                None
            } else {
                Some(token)
            }
        })
        .collect()
}

fn intersection_count(a: &HashSet<String>, b: &HashSet<String>) -> usize {
    a.intersection(b).count()
}

fn is_generic_exchange(content: &str) -> bool {
    let lower = content.to_ascii_lowercase();
    let generic = contains_any(
        &lower,
        &[
            "hello",
            "hi",
            "how are you",
            "good morning",
            "good afternoon",
            "thanks",
            "thank you",
        ],
    );
    generic && meaningful_tokens(content).len() <= 3
}

fn contains_any(text: &str, needles: &[&str]) -> bool {
    needles.iter().any(|needle| text.contains(needle))
}

fn is_stopword(token: &str) -> bool {
    matches!(
        token,
        "the"
            | "and"
            | "for"
            | "with"
            | "that"
            | "this"
            | "you"
            | "your"
            | "user"
            | "memory"
            | "about"
            | "from"
            | "into"
            | "over"
            | "than"
            | "then"
            | "they"
            | "them"
            | "has"
            | "have"
            | "had"
            | "been"
            | "was"
            | "were"
            | "are"
            | "is"
            | "can"
            | "could"
            | "would"
            | "should"
            | "will"
            | "may"
            | "might"
            | "not"
            | "but"
            | "when"
            | "what"
            | "why"
            | "how"
            | "time"
            | "remember"
    )
}

#[cfg(test)]
mod tests {
    use super::super::generator::RuleBasedEdgeGenerator;
    use super::*;
    use crate::{MemoryKind, Scope, Source, WriteInput};
    use std::sync::{Arc, Mutex};

    fn memory(content: &str, kind: MemoryKind) -> Memory {
        Memory {
            id: "m".to_string(),
            kind,
            scope: Scope::Global,
            content: content.to_string(),
            source: Source::ExplicitUser,
            confidence: 1.0,
            importance: 0.5,
            valid_from: 1,
            valid_to: None,
            superseded_by: None,
            access_count: 0,
            last_accessed_at: None,
        }
    }

    fn context<'a>(query: &'a str, ids: &'a [String], scores: &'a [f32]) -> RetrievalContext<'a> {
        RetrievalContext {
            query,
            query_context_hash: "ctx",
            query_context_tag: "tag",
            hit_memory_ids: ids,
            hit_scores: scores,
            timestamp: 1,
        }
    }

    struct RecordingJudge {
        seen: Arc<Mutex<Vec<EdgeCandidateEvidence>>>,
    }

    struct CountingJudge {
        calls: Arc<Mutex<usize>>,
    }

    impl EdgeSemanticJudge for CountingJudge {
        fn name(&self) -> &'static str {
            "counting_judge"
        }

        fn evaluate(&self, _input: EdgeJudgeInput<'_>) -> Result<EdgeJudgement> {
            *self.calls.lock().unwrap() += 1;
            Ok(EdgeJudgement::accept(
                EdgeRelation::Supports,
                0.8,
                "counting judge accepted",
            ))
        }
    }

    impl EdgeSemanticJudge for RecordingJudge {
        fn name(&self) -> &'static str {
            "recording_judge"
        }

        fn evaluate(&self, input: EdgeJudgeInput<'_>) -> Result<EdgeJudgement> {
            self.seen.lock().unwrap().push(input.co_occurrence.clone());
            Ok(EdgeJudgement::reject(0.9, "recorded evidence only"))
        }
    }

    #[test]
    fn heuristic_judge_rejects_generic_conversation_openings() {
        let judge = HeuristicSemanticJudge::default();
        let candidate = EdgeHypothesis {
            id: "h".to_string(),
            source: "a".to_string(),
            target: "b".to_string(),
            relation: EdgeRelation::CoActivates,
            confidence: 0.2,
            observations: 1,
            distinct_contexts: 1,
            predictive_utility: 0.0,
            first_seen: 1,
            last_seen: 1,
            status: super::super::model::EdgeHypothesisStatus::Candidate,
            confirmed_at: None,
            disputed_at: None,
            decayed_turns: 0,
        };
        let ids = vec!["a".to_string(), "b".to_string()];
        let scores = vec![0.9, 0.8];
        let ctx = context("remember that time", &ids, &scores);
        let a = memory("Hello, how are you?", MemoryKind::Fact);
        let b = memory("Hi, good morning", MemoryKind::Fact);
        let co_occurrence = EdgeCandidateEvidence::default();

        let judgement = judge
            .evaluate(EdgeJudgeInput {
                context: &ctx,
                candidate: &candidate,
                memory_a: &a,
                memory_b: &b,
                co_occurrence: &co_occurrence,
                existing_evidence: &[],
            })
            .unwrap();

        assert!(!judgement.valid);
    }

    #[test]
    fn heuristic_judge_classifies_semantic_support() {
        let judge = HeuristicSemanticJudge::default();
        let candidate = EdgeHypothesis {
            id: "h".to_string(),
            source: "a".to_string(),
            target: "b".to_string(),
            relation: EdgeRelation::CoActivates,
            confidence: 0.2,
            observations: 1,
            distinct_contexts: 1,
            predictive_utility: 0.0,
            first_seen: 1,
            last_seen: 1,
            status: super::super::model::EdgeHypothesisStatus::Candidate,
            confirmed_at: None,
            disputed_at: None,
            decayed_turns: 0,
        };
        let ids = vec!["a".to_string(), "b".to_string()];
        let scores = vec![0.9, 0.8];
        let ctx = context("rust memory architecture", &ids, &scores);
        let a = memory(
            "User studies Rust ownership and lifetimes",
            MemoryKind::Fact,
        );
        let b = memory(
            "User researches Rust borrow checker internals",
            MemoryKind::Fact,
        );
        let co_occurrence = EdgeCandidateEvidence::default();

        let judgement = judge
            .evaluate(EdgeJudgeInput {
                context: &ctx,
                candidate: &candidate,
                memory_a: &a,
                memory_b: &b,
                co_occurrence: &co_occurrence,
                existing_evidence: &[],
            })
            .unwrap();

        assert!(judgement.valid);
        assert_eq!(judgement.relation, Some(EdgeRelation::Supports));
        assert!(judgement.confidence >= 0.65);
    }

    #[test]
    fn judged_generator_only_interprets_rule_candidates() {
        let mut store = Store::open_in_memory().unwrap();
        let a = store
            .write(WriteInput {
                content: "User studies Rust ownership and lifetimes".to_string(),
                kind: MemoryKind::Fact,
                scope: Scope::Global,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let b = store
            .write(WriteInput {
                content: "User researches Rust borrow checker internals".to_string(),
                kind: MemoryKind::Fact,
                scope: Scope::Global,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let ids = vec![a.id.clone(), b.id.clone()];
        let scores = vec![0.9, 0.8];
        let ctx = context("rust memory architecture", &ids, &scores);
        let generator = JudgedEdgeGenerator::new(
            RuleBasedEdgeGenerator::new(),
            HeuristicSemanticJudge::default(),
        );

        let generated = generator.generate(&store, &ctx).unwrap();

        assert_eq!(generated.accepted.len(), 1);
        assert!(generated.rejected.is_empty());
        assert_eq!(
            generated.accepted[0].hypothesis.relation,
            EdgeRelation::Supports
        );
        assert_ne!(
            generated.accepted[0].hypothesis.id,
            hypothesis_id(&a.id, &b.id, EdgeRelation::CoActivates)
        );
    }

    #[test]
    fn judged_generator_accumulates_candidate_co_occurrence_evidence() {
        let mut store = Store::open_in_memory().unwrap();
        let a = store
            .write(WriteInput {
                content: "User studies Rust ownership and lifetimes".to_string(),
                kind: MemoryKind::Fact,
                scope: Scope::Global,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let b = store
            .write(WriteInput {
                content: "User researches Rust borrow checker internals".to_string(),
                kind: MemoryKind::Fact,
                scope: Scope::Global,
                source: Source::ExplicitUser,
                confidence: None,
                importance: None,
            })
            .unwrap();
        let ids = vec![a.id, b.id];
        let scores = vec![0.9, 0.8];
        let seen = Arc::new(Mutex::new(Vec::new()));
        let generator = JudgedEdgeGenerator::new(
            RuleBasedEdgeGenerator::new(),
            RecordingJudge { seen: seen.clone() },
        );

        let ctx_a = RetrievalContext {
            query: "rust ownership",
            query_context_hash: "ctx_rust",
            query_context_tag: "rust",
            hit_memory_ids: &ids,
            hit_scores: &scores,
            timestamp: 1,
        };
        generator.generate(&store, &ctx_a).unwrap();
        let ctx_b = RetrievalContext {
            query: "borrow checker",
            query_context_hash: "ctx_borrow",
            query_context_tag: "borrow",
            hit_memory_ids: &ids,
            hit_scores: &scores,
            timestamp: 2,
        };
        generator.generate(&store, &ctx_b).unwrap();

        let seen = seen.lock().unwrap();
        assert_eq!(seen.len(), 2);
        assert_eq!(seen[0].observations, 1);
        assert_eq!(seen[0].distinct_contexts, 1);
        assert_eq!(seen[1].observations, 2);
        assert_eq!(seen[1].distinct_contexts, 2);
        assert_eq!(seen[1].context_tags, vec!["rust", "borrow"]);
    }

    #[test]
    fn parser_rejects_contradictory_low_confidence_acceptance() {
        let judgement = parse_judgement_json(
            r#"{
                "decision":"accept",
                "valid":true,
                "relation":"none",
                "reason_category":"none",
                "confidence":0.2,
                "reason":"The memories only have broad topical overlap and no durable relationship."
            }"#,
        )
        .unwrap();

        assert!(!judgement.valid);
        assert_eq!(judgement.relation, None);
        assert_eq!(judgement.reason_category, EdgeReasonCategory::None);
    }

    #[test]
    fn parser_allows_high_confidence_filter_accept_without_relation() {
        let judgement = parse_judgement_json(
            r#"{
                "decision":"accept",
                "valid":true,
                "reason_category":"functional",
                "confidence":0.82,
                "reason":"The first memory is a useful future retrieval cue for the second."
            }"#,
        )
        .unwrap();

        assert!(judgement.valid);
        assert_eq!(judgement.relation, None);
        assert_eq!(judgement.reason_category, EdgeReasonCategory::Functional);
    }

    #[test]
    fn parser_maps_relation_words_in_reason_category() {
        let judgement = parse_judgement_json(
            r#"{
                "decision":"accept",
                "valid":true,
                "relation":"explains",
                "reason_category":"explains",
                "confidence":0.82,
                "reason":"The first memory gives a reason for the second."
            }"#,
        )
        .unwrap();

        assert!(judgement.valid);
        assert_eq!(judgement.relation, Some(EdgeRelation::Explains));
        assert_eq!(judgement.reason_category, EdgeReasonCategory::Causal);
    }

    #[test]
    fn parser_reorders_batch_judgements_by_id() {
        let judgements = parse_batch_judgement_json(
            r#"{
                "judgements": [
                    {
                        "id":"edge_0001",
                        "decision":"reject",
                        "valid":false,
                        "relation":"reject",
                        "reason_category":"none",
                        "confidence":0.1,
                        "reason":"no durable relation"
                    },
                    {
                        "id":"edge_0000",
                        "decision":"accept",
                        "valid":true,
                        "relation":"supports",
                        "reason_category":"semantic",
                        "confidence":0.8,
                        "reason":"shared durable detail"
                    }
                ]
            }"#,
            2,
        )
        .unwrap();

        assert!(judgements[0].valid);
        assert_eq!(judgements[0].relation, Some(EdgeRelation::Supports));
        assert!(!judgements[1].valid);
    }

    #[test]
    fn parser_rejects_batch_missing_candidate_id() {
        let err = parse_batch_judgement_json(
            r#"{
                "judgements": [
                    {
                        "id":"edge_0000",
                        "decision":"reject",
                        "valid":false,
                        "relation":"reject",
                        "reason_category":"none",
                        "confidence":0.1,
                        "reason":"no durable relation"
                    }
                ]
            }"#,
            2,
        )
        .unwrap_err();

        assert!(err.to_string().contains("missing id: edge_0001"));
    }

    #[test]
    fn semantic_judge_executor_config_is_bounded() {
        let config = SemanticJudgeExecutorConfig {
            batch_size: 0,
            max_inflight: 999,
            retries: 999,
            retry_backoff: Duration::from_millis(0),
        }
        .sanitized();

        assert_eq!(config.batch_size, 1);
        assert_eq!(config.max_inflight, 10);
        assert_eq!(config.retries, 5);
    }

    #[test]
    fn cached_semantic_judge_reuses_identical_inputs() {
        let calls = Arc::new(Mutex::new(0usize));
        let cache_path = std::env::temp_dir().join(format!(
            "synapse-semantic-cache-test-{}.sqlite",
            ulid::Ulid::new()
        ));
        let judge = CachedSemanticJudge::open(
            CountingJudge {
                calls: calls.clone(),
            },
            &cache_path,
            "test_namespace",
        )
        .unwrap();

        let candidate = EdgeHypothesis {
            id: "h".to_string(),
            source: "a".to_string(),
            target: "b".to_string(),
            relation: EdgeRelation::CoActivates,
            confidence: 0.2,
            observations: 1,
            distinct_contexts: 1,
            predictive_utility: 0.0,
            first_seen: 1,
            last_seen: 1,
            status: super::super::model::EdgeHypothesisStatus::Candidate,
            confirmed_at: None,
            disputed_at: None,
            decayed_turns: 0,
        };
        let ids = vec!["a".to_string(), "b".to_string()];
        let scores = vec![0.9, 0.8];
        let ctx = context("rust memory architecture", &ids, &scores);
        let a = memory("User studies Rust ownership", MemoryKind::Fact);
        let b = memory("User researches Rust borrow checker", MemoryKind::Fact);
        let co_occurrence = EdgeCandidateEvidence {
            observations: 1,
            distinct_contexts: 1,
            context_hashes: vec!["ctx".to_string()],
            context_tags: vec!["tag".to_string()],
            recent_queries: vec!["rust memory architecture".to_string()],
        };

        for _ in 0..2 {
            let judgement = judge
                .evaluate(EdgeJudgeInput {
                    context: &ctx,
                    candidate: &candidate,
                    memory_a: &a,
                    memory_b: &b,
                    co_occurrence: &co_occurrence,
                    existing_evidence: &[],
                })
                .unwrap();
            assert!(judgement.valid);
        }

        assert_eq!(*calls.lock().unwrap(), 1);
        let stats = judge.stats().unwrap();
        assert_eq!(stats.misses, 1);
        assert_eq!(stats.writes, 1);
        assert_eq!(stats.hits, 1);

        let _ = std::fs::remove_file(cache_path);
    }
}
