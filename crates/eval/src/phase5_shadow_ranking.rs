use anyhow::{ensure, Result};
use chrono::Utc;
use serde::Serialize;
use std::{collections::HashMap, time::Instant};
use synapse_core::{
    CognitiveBooster, CognitiveBoosterConfig, CognitiveBoosterInput, CognitiveTraceEvaluator,
    DeterministicCognitiveBoosterV0, MemoryKind, RecallEngine, RecallHit, RecallQuery, Scope,
    Source, Store, WriteInput, MAX_COGNITIVE_BOOSTER_BONUS,
};

const EVALUATION_VERSION: &str = "phase5.3.2-deterministic-cognitive-booster-v0";
const BASELINE_VERSION: &str = "phase5.3.1-bounded-cognitive-booster-interface";
const METRIC_CUTOFF: usize = 3;
const CANDIDATE_LIMIT: usize = 6;
const SCORE_EPSILON: f64 = 1e-12;

pub struct Phase5ShadowRankingEvaluator;

impl Phase5ShadowRankingEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase5ShadowRankingReport> {
        evaluate_shadow_ranking(tag.into())
    }
}

fn evaluate_shadow_ranking(tag: String) -> Result<Phase5ShadowRankingReport> {
    let mut scenario_reports = Vec::new();
    for scenario in shadow_scenarios() {
        scenario_reports.push(evaluate_scenario(scenario)?);
    }

    let total_candidates = scenario_reports
        .iter()
        .map(|scenario| scenario.candidates.len())
        .sum::<usize>();
    let proposed_candidates = scenario_reports
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .filter(|candidate| candidate.proposed_bonus > SCORE_EPSILON)
        .count();
    let changed_positions = scenario_reports
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .filter(|candidate| candidate.position_delta != 0)
        .count();
    let total_abs_rank_delta = scenario_reports
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .map(|candidate| candidate.position_delta.unsigned_abs() as f64)
        .sum::<f64>();
    let max_abs_rank_delta = scenario_reports
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .map(|candidate| candidate.position_delta.unsigned_abs() as usize)
        .max()
        .unwrap_or(0);
    let max_proposed_bonus = scenario_reports
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .map(|candidate| candidate.proposed_bonus)
        .fold(0.0, f64::max);
    let bounded_proposals = scenario_reports
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .filter(|candidate| {
            candidate.proposed_bonus >= 0.0
                && candidate.proposed_bonus <= MAX_COGNITIVE_BOOSTER_BONUS + SCORE_EPSILON
        })
        .count();
    let deterministic_scenarios = scenario_reports
        .iter()
        .filter(|scenario| scenario.deterministic)
        .count();
    let baseline_recall_at_k = mean(
        scenario_reports
            .iter()
            .map(|scenario| scenario.baseline_recall_at_k),
    );
    let shadow_recall_at_k = mean(
        scenario_reports
            .iter()
            .map(|scenario| scenario.shadow_recall_at_k),
    );
    let baseline_mrr = mean(
        scenario_reports
            .iter()
            .map(|scenario| scenario.baseline_reciprocal_rank),
    );
    let shadow_mrr = mean(
        scenario_reports
            .iter()
            .map(|scenario| scenario.shadow_reciprocal_rank),
    );
    let ranking_mutated = scenario_reports
        .iter()
        .any(|scenario| !scenario.baseline_ranking_unchanged);
    let scores_mutated = scenario_reports
        .iter()
        .any(|scenario| !scenario.baseline_scores_unchanged);
    let activation_changed = scenario_reports
        .iter()
        .any(|scenario| !scenario.activation_unchanged);
    let memory_mutated = scenario_reports
        .iter()
        .any(|scenario| !scenario.memory_unchanged);
    let candidate_pool_changed = scenario_reports
        .iter()
        .any(|scenario| !scenario.candidate_pool_preserved);
    let runtime_applied = scenario_reports
        .iter()
        .any(|scenario| scenario.runtime_applied);

    let metrics = Phase5ShadowRankingMetrics {
        proposal_coverage: safe_div(proposed_candidates as f64, total_candidates as f64),
        changed_positions,
        avg_abs_rank_delta: safe_div(total_abs_rank_delta, total_candidates as f64),
        max_abs_rank_delta,
        max_proposed_bonus,
        bounded_rate: safe_div(bounded_proposals as f64, total_candidates as f64),
        determinism: safe_div(
            deterministic_scenarios as f64,
            scenario_reports.len() as f64,
        ),
        baseline_recall_at_k,
        shadow_recall_at_k,
        shadow_recall_delta: shadow_recall_at_k - baseline_recall_at_k,
        baseline_mrr,
        shadow_mrr,
        shadow_mrr_delta: shadow_mrr - baseline_mrr,
    };
    let guards = Phase5ShadowRankingGuards {
        eval_only: true,
        shadow_only: true,
        baseline_authoritative: true,
        runtime_applied,
        memory_written: false,
        memory_mutated,
        ranking_mutated,
        scores_mutated,
        activation_changed,
        candidate_pool_changed,
        recall_engine_integrated: false,
        production_claim_authorized: false,
    };
    let latency = Phase5ShadowRankingLatency {
        recall_p50_ms: percentile(
            scenario_reports
                .iter()
                .map(|scenario| scenario.recall_latency_ms)
                .collect(),
            0.50,
        ),
        recall_p95_ms: percentile(
            scenario_reports
                .iter()
                .map(|scenario| scenario.recall_latency_ms)
                .collect(),
            0.95,
        ),
        shadow_p50_ms: percentile(
            scenario_reports
                .iter()
                .map(|scenario| scenario.shadow_latency_ms)
                .collect(),
            0.50,
        ),
        shadow_p95_ms: percentile(
            scenario_reports
                .iter()
                .map(|scenario| scenario.shadow_latency_ms)
                .collect(),
            0.95,
        ),
    };
    let pass = metrics.bounded_rate >= 1.0
        && metrics.determinism >= 1.0
        && metrics.max_proposed_bonus <= MAX_COGNITIVE_BOOSTER_BONUS + SCORE_EPSILON
        && guards.eval_only
        && guards.shadow_only
        && guards.baseline_authoritative
        && !guards.runtime_applied
        && !guards.memory_written
        && !guards.memory_mutated
        && !guards.ranking_mutated
        && !guards.scores_mutated
        && !guards.activation_changed
        && !guards.candidate_pool_changed
        && !guards.recall_engine_integrated
        && !guards.production_claim_authorized;

    Ok(Phase5ShadowRankingReport {
        schema_version: 1,
        tag,
        phase: "5.3.2".to_string(),
        mode: "offline_shadow_ranking".to_string(),
        algorithm: DeterministicCognitiveBoosterV0.name().to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        metric_cutoff: METRIC_CUTOFF,
        candidate_limit: CANDIDATE_LIMIT,
        max_bonus: MAX_COGNITIVE_BOOSTER_BONUS,
        scenarios: scenario_reports.len(),
        metrics,
        guards,
        latency,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        conclusion: "Local deterministic shadow evidence only; runtime authorization and production ranking benefit are not claimed.".to_string(),
        scenario_reports,
    })
}

fn evaluate_scenario(scenario: ShadowScenario) -> Result<Phase5ShadowRankingScenarioReport> {
    let mut store = Store::open_in_memory()?;
    let mut relevant_ids = Vec::new();
    for memory in scenario.memories {
        let stored = store.write(WriteInput {
            content: memory.content.to_string(),
            kind: memory.kind,
            scope: Scope::User,
            source: Source::ExplicitUser,
            confidence: Some(memory.confidence),
            importance: Some(memory.importance),
        })?;
        if memory.relevant {
            relevant_ids.push(stored.id);
        }
    }

    let query = RecallQuery {
        query: scenario.query.to_string(),
        k: Some(CANDIDATE_LIMIT),
        scope_filter: Some(Scope::User),
        kind_filter: None,
    };
    let recall_start = Instant::now();
    let hits = RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall(&query)?;
    let recall_latency_ms = recall_start.elapsed().as_secs_f64() * 1000.0;
    ensure!(
        !hits.is_empty(),
        "shadow scenario {} returned no candidates",
        scenario.id
    );
    ensure!(
        relevant_ids
            .iter()
            .all(|id| hits.iter().any(|hit| hit.memory.id == *id)),
        "shadow scenario {} did not retrieve all fixture ground-truth memories",
        scenario.id
    );

    let before = hit_snapshot(&hits)?;
    let trace = CognitiveTraceEvaluator::evaluate(&query.query, &hits);
    let config = CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS, CANDIDATE_LIMIT)?;
    let booster = DeterministicCognitiveBoosterV0;

    let shadow_start = Instant::now();
    let output = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));
    let first_shadow = build_shadow_candidates(&hits, output.adjusted_scores(), &relevant_ids);
    let shadow_latency_ms = shadow_start.elapsed().as_secs_f64() * 1000.0;
    let replay_output = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));
    let replay_shadow =
        build_shadow_candidates(&hits, replay_output.adjusted_scores(), &relevant_ids);
    let after = hit_snapshot(&hits)?;

    let baseline_ranking = hits
        .iter()
        .map(|hit| hit.memory.id.clone())
        .collect::<Vec<_>>();
    let shadow_ranking = first_shadow
        .iter()
        .map(|candidate| candidate.candidate_id.clone())
        .collect::<Vec<_>>();
    let baseline_recall_at_k = recall_at_k(&baseline_ranking, &relevant_ids, METRIC_CUTOFF);
    let shadow_recall_at_k = recall_at_k(&shadow_ranking, &relevant_ids, METRIC_CUTOFF);
    let baseline_reciprocal_rank = reciprocal_rank(&baseline_ranking, &relevant_ids);
    let shadow_reciprocal_rank = reciprocal_rank(&shadow_ranking, &relevant_ids);

    let baseline_ids_unchanged = before.ids == after.ids;
    let baseline_scores_unchanged = before.score_bits == after.score_bits;
    let activation_unchanged = before.activation_bits == after.activation_bits;
    let memory_unchanged = before.memory_json == after.memory_json;
    let mut baseline_pool = baseline_ranking.clone();
    let mut shadow_pool = shadow_ranking.clone();
    baseline_pool.sort();
    shadow_pool.sort();
    let candidate_pool_preserved = baseline_pool == shadow_pool;
    let deterministic = output == replay_output && first_shadow == replay_shadow;

    Ok(Phase5ShadowRankingScenarioReport {
        id: scenario.id.to_string(),
        query: scenario.query.to_string(),
        candidate_count: hits.len(),
        relevant_candidate_ids: relevant_ids,
        baseline_ranking,
        shadow_ranking,
        candidates: first_shadow,
        baseline_recall_at_k,
        shadow_recall_at_k,
        shadow_recall_delta: shadow_recall_at_k - baseline_recall_at_k,
        baseline_reciprocal_rank,
        shadow_reciprocal_rank,
        shadow_mrr_delta: shadow_reciprocal_rank - baseline_reciprocal_rank,
        deterministic,
        baseline_ranking_unchanged: baseline_ids_unchanged,
        baseline_scores_unchanged,
        activation_unchanged,
        memory_unchanged,
        candidate_pool_preserved,
        runtime_applied: output.runtime_applied(),
        memory_mutated: output.memory_mutated(),
        recall_latency_ms,
        shadow_latency_ms,
    })
}

fn build_shadow_candidates(
    hits: &[RecallHit],
    adjusted_scores: &[synapse_core::CognitiveAdjustedScore],
    relevant_ids: &[String],
) -> Vec<ShadowCandidateReport> {
    let bonuses = adjusted_scores
        .iter()
        .map(|score| (score.candidate_id.as_str(), score.bounded_bonus))
        .collect::<HashMap<_, _>>();
    let mut rows = hits
        .iter()
        .enumerate()
        .map(|(index, hit)| {
            let baseline_rank = index + 1;
            let proposed_bonus = bonuses.get(hit.memory.id.as_str()).copied().unwrap_or(0.0);
            ShadowCandidateReport {
                candidate_id: hit.memory.id.clone(),
                baseline_rank,
                shadow_rank: 0,
                baseline_score: f64::from(hit.score),
                proposed_bonus,
                shadow_score: f64::from(hit.score) + proposed_bonus,
                position_delta: 0,
                relevant: relevant_ids.contains(&hit.memory.id),
                runtime_applied: false,
            }
        })
        .collect::<Vec<_>>();

    rows.sort_by(|left, right| {
        right
            .shadow_score
            .total_cmp(&left.shadow_score)
            .then_with(|| left.baseline_rank.cmp(&right.baseline_rank))
    });
    for (index, row) in rows.iter_mut().enumerate() {
        row.shadow_rank = index + 1;
        row.position_delta = row.baseline_rank as i64 - row.shadow_rank as i64;
    }
    rows
}

fn recall_at_k(ranking: &[String], relevant_ids: &[String], k: usize) -> f64 {
    if relevant_ids.is_empty() {
        return 0.0;
    }
    let found = ranking
        .iter()
        .take(k)
        .filter(|candidate| relevant_ids.contains(candidate))
        .count();
    found as f64 / relevant_ids.len() as f64
}

fn reciprocal_rank(ranking: &[String], relevant_ids: &[String]) -> f64 {
    ranking
        .iter()
        .position(|candidate| relevant_ids.contains(candidate))
        .map(|index| 1.0 / (index + 1) as f64)
        .unwrap_or(0.0)
}

fn mean(values: impl Iterator<Item = f64>) -> f64 {
    let values = values.collect::<Vec<_>>();
    safe_div(values.iter().sum(), values.len() as f64)
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

fn percentile(mut values: Vec<f64>, percentile: f64) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.sort_by(|left, right| left.total_cmp(right));
    let index = ((values.len() - 1) as f64 * percentile.clamp(0.0, 1.0)).ceil() as usize;
    values[index.min(values.len() - 1)]
}

fn hit_snapshot(hits: &[RecallHit]) -> Result<HitSnapshot> {
    Ok(HitSnapshot {
        ids: hits.iter().map(|hit| hit.memory.id.clone()).collect(),
        score_bits: hits.iter().map(|hit| hit.score.to_bits()).collect(),
        activation_bits: hits
            .iter()
            .map(|hit| hit.activation_bonus.to_bits())
            .collect(),
        memory_json: hits
            .iter()
            .map(|hit| serde_json::to_string(&hit.memory))
            .collect::<std::result::Result<Vec<_>, _>>()?,
    })
}

struct HitSnapshot {
    ids: Vec<String>,
    score_bits: Vec<u32>,
    activation_bits: Vec<u32>,
    memory_json: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ShadowCandidateReport {
    pub candidate_id: String,
    pub baseline_rank: usize,
    pub shadow_rank: usize,
    pub baseline_score: f64,
    pub proposed_bonus: f64,
    pub shadow_score: f64,
    /// `baseline_rank - shadow_rank`; positive values indicate upward movement.
    pub position_delta: i64,
    pub relevant: bool,
    pub runtime_applied: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5ShadowRankingScenarioReport {
    pub id: String,
    pub query: String,
    pub candidate_count: usize,
    pub relevant_candidate_ids: Vec<String>,
    pub baseline_ranking: Vec<String>,
    pub shadow_ranking: Vec<String>,
    pub candidates: Vec<ShadowCandidateReport>,
    pub baseline_recall_at_k: f64,
    pub shadow_recall_at_k: f64,
    pub shadow_recall_delta: f64,
    pub baseline_reciprocal_rank: f64,
    pub shadow_reciprocal_rank: f64,
    pub shadow_mrr_delta: f64,
    pub deterministic: bool,
    pub baseline_ranking_unchanged: bool,
    pub baseline_scores_unchanged: bool,
    pub activation_unchanged: bool,
    pub memory_unchanged: bool,
    pub candidate_pool_preserved: bool,
    pub runtime_applied: bool,
    pub memory_mutated: bool,
    pub recall_latency_ms: f64,
    pub shadow_latency_ms: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5ShadowRankingMetrics {
    pub proposal_coverage: f64,
    pub changed_positions: usize,
    pub avg_abs_rank_delta: f64,
    pub max_abs_rank_delta: usize,
    pub max_proposed_bonus: f64,
    pub bounded_rate: f64,
    pub determinism: f64,
    pub baseline_recall_at_k: f64,
    pub shadow_recall_at_k: f64,
    pub shadow_recall_delta: f64,
    pub baseline_mrr: f64,
    pub shadow_mrr: f64,
    pub shadow_mrr_delta: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5ShadowRankingGuards {
    pub eval_only: bool,
    pub shadow_only: bool,
    pub baseline_authoritative: bool,
    pub runtime_applied: bool,
    pub memory_written: bool,
    pub memory_mutated: bool,
    pub ranking_mutated: bool,
    pub scores_mutated: bool,
    pub activation_changed: bool,
    pub candidate_pool_changed: bool,
    pub recall_engine_integrated: bool,
    pub production_claim_authorized: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5ShadowRankingLatency {
    pub recall_p50_ms: f64,
    pub recall_p95_ms: f64,
    pub shadow_p50_ms: f64,
    pub shadow_p95_ms: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5ShadowRankingReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub algorithm: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub metric_cutoff: usize,
    pub candidate_limit: usize,
    pub max_bonus: f64,
    pub scenarios: usize,
    pub metrics: Phase5ShadowRankingMetrics,
    pub guards: Phase5ShadowRankingGuards,
    pub latency: Phase5ShadowRankingLatency,
    pub pass: bool,
    pub status: String,
    pub conclusion: String,
    pub scenario_reports: Vec<Phase5ShadowRankingScenarioReport>,
}

struct ShadowScenario {
    id: &'static str,
    query: &'static str,
    memories: Vec<ShadowMemory>,
}

struct ShadowMemory {
    content: &'static str,
    kind: MemoryKind,
    confidence: f32,
    importance: f32,
    relevant: bool,
}

fn shadow_scenarios() -> Vec<ShadowScenario> {
    vec![
        ShadowScenario {
            id: "phase5_shadow_001_failure_evidence",
            query: "production rollback resource validation",
            memories: vec![
                memory("Production rollback resource validation checklist for release operations.", MemoryKind::Fact, 0.96, 0.92, false),
                memory("Production release failed when resource limits were skipped.", MemoryKind::Failure, 0.99, 0.84, true),
                memory("Production rollback playbook verifies resources before deployment.", MemoryKind::Playbook, 0.90, 0.84, false),
                memory("User prefers production changes with rollback validation.", MemoryKind::Preference, 0.92, 0.80, false),
                memory("Production resource validation notes for database rollback.", MemoryKind::Fact, 0.76, 0.72, false),
            ],
        },
        ShadowScenario {
            id: "phase5_shadow_002_preference_alignment",
            query: "fast local prototype iteration preference",
            memories: vec![
                memory("Fast local prototype iteration preference guide.", MemoryKind::Fact, 0.84, 0.82, false),
                memory("User prefers fast local prototype iteration before architecture formalization.", MemoryKind::Preference, 0.97, 0.86, true),
                memory("Fast prototype iteration can use a local test environment.", MemoryKind::Playbook, 0.88, 0.80, false),
                memory("Local prototype iteration failure occurred after skipping dependency checks.", MemoryKind::Failure, 0.86, 0.78, false),
                memory("Preference notes for local release iteration.", MemoryKind::Fact, 0.74, 0.70, false),
            ],
        },
        ShadowScenario {
            id: "phase5_shadow_003_playbook_context",
            query: "deployment rollback verification playbook",
            memories: vec![
                memory("Deployment rollback verification playbook for production release.", MemoryKind::Playbook, 0.96, 0.90, true),
                memory("Archived release status record.", MemoryKind::Fact, 0.90, 0.84, false),
                memory("Deployment failed because rollback verification was incomplete.", MemoryKind::Failure, 0.92, 0.82, false),
                memory("User prefers deployment playbooks with rollback steps.", MemoryKind::Preference, 0.88, 0.78, false),
                memory("Rollback verification applies to deployment resources.", MemoryKind::Fact, 0.78, 0.72, false),
            ],
        },
        ShadowScenario {
            id: "phase5_shadow_004_reliability_tradeoff",
            query: "gpu memory deployment capacity evidence",
            memories: vec![
                memory("GPU memory deployment capacity evidence summary.", MemoryKind::Fact, 0.78, 0.86, false),
                memory("GPU deployment failed when memory capacity evidence was ignored.", MemoryKind::Failure, 0.99, 0.84, true),
                memory("GPU memory capacity deployment playbook.", MemoryKind::Playbook, 0.94, 0.82, false),
                memory("User prefers GPU deployment capacity checks.", MemoryKind::Preference, 0.90, 0.80, false),
                memory("Deployment capacity evidence for GPU resource planning.", MemoryKind::Fact, 0.72, 0.74, false),
            ],
        },
    ]
}

fn memory(
    content: &'static str,
    kind: MemoryKind,
    confidence: f32,
    importance: f32,
    relevant: bool,
) -> ShadowMemory {
    ShadowMemory {
        content,
        kind,
        confidence,
        importance,
        relevant,
    }
}
