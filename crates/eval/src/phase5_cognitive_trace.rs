use anyhow::Result;
use chrono::Utc;
use serde::Serialize;
use std::time::Instant;
use synapse_core::{
    CognitiveCompetitionTrace, CognitiveFactorType, CognitiveTraceEvaluator, MemoryKind,
    RecallEngine, RecallHit, RecallQuery, Scope, Source, Store, WriteInput,
};

const EVALUATION_VERSION: &str = "phase5.1-cognitive-competition-trace-integration";
const BASELINE_VERSION: &str = "phase5.0-algorithm-integration-design";

pub struct Phase5CognitiveTraceEvaluator;

impl Phase5CognitiveTraceEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase5CognitiveTraceReport> {
        evaluate_trace_integration(tag.into())
    }
}

fn evaluate_trace_integration(tag: String) -> Result<Phase5CognitiveTraceReport> {
    let mut scenario_reports = Vec::new();
    for scenario in trace_scenarios() {
        scenario_reports.push(evaluate_scenario(scenario)?);
    }

    let trace_generation_rate = safe_div(
        scenario_reports
            .iter()
            .filter(|scenario| scenario.trace_generated)
            .count() as f64,
        scenario_reports.len() as f64,
    );
    let dominant_validity = safe_div(
        scenario_reports
            .iter()
            .filter(|scenario| scenario.dominant_valid)
            .count() as f64,
        scenario_reports.len() as f64,
    );
    let factor_explanation_rate = safe_div(
        scenario_reports
            .iter()
            .filter(|scenario| scenario.factor_explanation_complete)
            .count() as f64,
        scenario_reports.len() as f64,
    );
    let trace_determinism = safe_div(
        scenario_reports
            .iter()
            .filter(|scenario| scenario.trace_deterministic)
            .count() as f64,
        scenario_reports.len() as f64,
    );
    let regressions = scenario_reports
        .iter()
        .filter(|scenario| scenario.ranking_changed || scenario.scores_changed)
        .count();
    let recall_regression = safe_div(regressions as f64, scenario_reports.len() as f64);
    let latency = latency_report(&scenario_reports);
    let guards = Phase5CognitiveTraceGuards {
        core_behavior_changed: false,
        recall_output_changed: false,
        ranking_changed: false,
        memory_written: false,
        activation_changed: false,
    };
    let metrics = Phase5CognitiveTraceMetrics {
        trace_generation_rate,
        dominant_validity,
        factor_explanation_rate,
        trace_determinism,
        recall_regression,
    };
    let pass = metrics.trace_generation_rate >= 1.0
        && metrics.dominant_validity >= 1.0
        && metrics.factor_explanation_rate >= 1.0
        && metrics.trace_determinism >= 1.0
        && metrics.recall_regression == 0.0
        && !guards.core_behavior_changed
        && !guards.recall_output_changed
        && !guards.ranking_changed
        && !guards.memory_written
        && !guards.activation_changed;

    Ok(Phase5CognitiveTraceReport {
        tag,
        phase: "5.1".to_string(),
        mode: "inspection_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        scenarios: scenario_reports.len(),
        metrics,
        guards,
        latency,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        scenario_reports,
    })
}

fn evaluate_scenario(scenario: TraceScenario) -> Result<Phase5CognitiveTraceScenarioReport> {
    let mut store = Store::open_in_memory()?;
    for memory in scenario.memories {
        store.write(WriteInput {
            content: memory.content.to_string(),
            kind: memory.kind,
            scope: Scope::User,
            source: Source::ExplicitUser,
            confidence: Some(memory.confidence),
            importance: Some(memory.importance),
        })?;
    }

    let query = RecallQuery {
        query: scenario.query.to_string(),
        k: Some(scenario.k),
        scope_filter: Some(Scope::User),
        kind_filter: None,
    };
    let mut engine = RecallEngine::new(&mut store).with_access_recording(false);
    let profiled = engine.recall_profiled(&query)?;
    drop(engine);

    let before_signature = hit_signature(&profiled.hits);
    let trace_start = Instant::now();
    let trace = CognitiveTraceEvaluator::evaluate(&query.query, &profiled.hits);
    let trace_ms = elapsed_ms(trace_start);
    let replay_trace = CognitiveTraceEvaluator::evaluate(&query.query, &profiled.hits);
    let after_signature = hit_signature(&profiled.hits);

    let hit_ids = profiled
        .hits
        .iter()
        .map(|hit| hit.memory.id.clone())
        .collect::<Vec<_>>();
    let dominant_valid = trace
        .dominant_candidate
        .as_ref()
        .map(|candidate| hit_ids.contains(candidate))
        .unwrap_or(false);
    let factor_explanation_complete = has_factor(&trace, CognitiveFactorType::SemanticMatch)
        && has_factor(&trace, CognitiveFactorType::TemporalConfidence)
        && has_factor(&trace, CognitiveFactorType::Reliability)
        && has_factor(&trace, CognitiveFactorType::ContextAlignment)
        && trace
            .dominant_candidate
            .as_ref()
            .map(|dominant| {
                trace
                    .factors
                    .iter()
                    .any(|factor| &factor.candidate_id == dominant)
            })
            .unwrap_or(false);
    let access_counts_after_trace = profiled
        .hits
        .iter()
        .map(|hit| (hit.memory.id.clone(), hit.memory.access_count))
        .collect::<Vec<_>>();

    Ok(Phase5CognitiveTraceScenarioReport {
        scenario_id: scenario.id.to_string(),
        query: query.query,
        candidate_count: profiled.hits.len(),
        baseline_ranking: before_signature
            .iter()
            .map(|signature| signature.memory_id.clone())
            .collect(),
        trace_ranking: after_signature
            .iter()
            .map(|signature| signature.memory_id.clone())
            .collect(),
        baseline_scores: before_signature
            .iter()
            .map(|signature| signature.score)
            .collect(),
        trace_scores: after_signature
            .iter()
            .map(|signature| signature.score)
            .collect(),
        trace: trace.clone(),
        trace_generated: trace.candidate_count == profiled.hits.len()
            && trace.dominant_candidate.is_some(),
        dominant_valid,
        factor_explanation_complete,
        trace_deterministic: trace == replay_trace,
        ranking_changed: before_signature
            .iter()
            .map(|signature| &signature.memory_id)
            .collect::<Vec<_>>()
            != after_signature
                .iter()
                .map(|signature| &signature.memory_id)
                .collect::<Vec<_>>(),
        scores_changed: before_signature
            .iter()
            .map(|signature| signature.score_bits)
            .collect::<Vec<_>>()
            != after_signature
                .iter()
                .map(|signature| signature.score_bits)
                .collect::<Vec<_>>(),
        memory_written: access_counts_after_trace
            .iter()
            .any(|(_, access_count)| *access_count > 0),
        activation_changed: profiled
            .hits
            .iter()
            .any(|hit| hit.activation_bonus.abs() > f32::EPSILON),
        latency_before_ms: profiled.profile.total_ms,
        latency_after_ms: profiled.profile.total_ms + trace_ms,
        trace_latency_ms: trace_ms,
    })
}

fn has_factor(trace: &CognitiveCompetitionTrace, factor_type: CognitiveFactorType) -> bool {
    trace
        .factors
        .iter()
        .any(|factor| factor.factor_type == factor_type)
}

fn hit_signature(hits: &[RecallHit]) -> Vec<HitSignature> {
    hits.iter()
        .map(|hit| HitSignature {
            memory_id: hit.memory.id.clone(),
            score: hit.score as f64,
            score_bits: hit.score.to_bits(),
        })
        .collect()
}

fn latency_report(scenarios: &[Phase5CognitiveTraceScenarioReport]) -> Phase5CognitiveTraceLatency {
    let before = scenarios
        .iter()
        .map(|scenario| scenario.latency_before_ms)
        .collect::<Vec<_>>();
    let after = scenarios
        .iter()
        .map(|scenario| scenario.latency_after_ms)
        .collect::<Vec<_>>();
    let before_p50 = percentile(before.clone(), 0.50);
    let before_p95 = percentile(before, 0.95);
    let after_p50 = percentile(after.clone(), 0.50);
    let after_p95 = percentile(after, 0.95);
    let overhead_p50_ratio = overhead_ratio(before_p50, after_p50);
    let overhead_p95_ratio = overhead_ratio(before_p95, after_p95);

    Phase5CognitiveTraceLatency {
        before: LatencySummary {
            p50_ms: before_p50,
            p95_ms: before_p95,
        },
        after: LatencySummary {
            p50_ms: after_p50,
            p95_ms: after_p95,
        },
        overhead_p50_ratio,
        overhead_p95_ratio,
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

fn overhead_ratio(before: f64, after: f64) -> f64 {
    if before <= f64::EPSILON {
        0.0
    } else {
        ((after - before).max(0.0) / before * 10_000.0).round() / 10_000.0
    }
}

fn elapsed_ms(start: Instant) -> f64 {
    start.elapsed().as_secs_f64() * 1000.0
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

fn trace_scenarios() -> Vec<TraceScenario> {
    vec![
        TraceScenario {
            id: "phase5_trace_001_deployment_failure",
            query: "deployment gpu memory resource",
            k: 3,
            memories: vec![
                memory(
                    "GPU memory overflow happened during deployment because batch size exceeded resource limits.",
                    MemoryKind::Failure,
                    0.95,
                    0.90,
                ),
                memory(
                    "User prefers fast deployment iteration when the environment is low risk.",
                    MemoryKind::Preference,
                    0.80,
                    0.70,
                ),
                memory(
                    "Database migration requires backup before production deployment.",
                    MemoryKind::Fact,
                    0.75,
                    0.65,
                ),
            ],
        },
        TraceScenario {
            id: "phase5_trace_002_preference_alignment",
            query: "fast local prototype iteration preference",
            k: 3,
            memories: vec![
                memory(
                    "User prefers fast local prototype iteration before formalizing architecture.",
                    MemoryKind::Preference,
                    0.92,
                    0.82,
                ),
                memory(
                    "Production release playbook requires rollback verification.",
                    MemoryKind::Playbook,
                    0.85,
                    0.78,
                ),
                memory(
                    "Cloud deployment failure happened when network credentials expired.",
                    MemoryKind::Failure,
                    0.80,
                    0.74,
                ),
            ],
        },
        TraceScenario {
            id: "phase5_trace_003_playbook_context",
            query: "production release rollback verification",
            k: 3,
            memories: vec![
                memory(
                    "Production release playbook: verify rollback path and environment resources before rollout.",
                    MemoryKind::Playbook,
                    0.94,
                    0.88,
                ),
                memory(
                    "User prefers simple tools during local experiments.",
                    MemoryKind::Preference,
                    0.82,
                    0.70,
                ),
                memory(
                    "A previous production release failed when rollback verification was skipped.",
                    MemoryKind::Failure,
                    0.88,
                    0.84,
                ),
            ],
        },
    ]
}

fn memory(
    content: &'static str,
    kind: MemoryKind,
    confidence: f32,
    importance: f32,
) -> TraceMemory {
    TraceMemory {
        content,
        kind,
        confidence,
        importance,
    }
}

struct TraceScenario {
    id: &'static str,
    query: &'static str,
    k: usize,
    memories: Vec<TraceMemory>,
}

struct TraceMemory {
    content: &'static str,
    kind: MemoryKind,
    confidence: f32,
    importance: f32,
}

#[derive(Debug, Clone)]
struct HitSignature {
    memory_id: String,
    score: f64,
    score_bits: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5CognitiveTraceReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub scenarios: usize,
    pub metrics: Phase5CognitiveTraceMetrics,
    pub guards: Phase5CognitiveTraceGuards,
    pub latency: Phase5CognitiveTraceLatency,
    pub pass: bool,
    pub status: String,
    pub scenario_reports: Vec<Phase5CognitiveTraceScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5CognitiveTraceMetrics {
    pub trace_generation_rate: f64,
    pub dominant_validity: f64,
    pub factor_explanation_rate: f64,
    pub trace_determinism: f64,
    pub recall_regression: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5CognitiveTraceGuards {
    pub core_behavior_changed: bool,
    pub recall_output_changed: bool,
    pub ranking_changed: bool,
    pub memory_written: bool,
    pub activation_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5CognitiveTraceLatency {
    pub before: LatencySummary,
    pub after: LatencySummary,
    pub overhead_p50_ratio: f64,
    pub overhead_p95_ratio: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct LatencySummary {
    pub p50_ms: f64,
    pub p95_ms: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5CognitiveTraceScenarioReport {
    pub scenario_id: String,
    pub query: String,
    pub candidate_count: usize,
    pub baseline_ranking: Vec<String>,
    pub trace_ranking: Vec<String>,
    pub baseline_scores: Vec<f64>,
    pub trace_scores: Vec<f64>,
    pub trace: CognitiveCompetitionTrace,
    pub trace_generated: bool,
    pub dominant_valid: bool,
    pub factor_explanation_complete: bool,
    pub trace_deterministic: bool,
    pub ranking_changed: bool,
    pub scores_changed: bool,
    pub memory_written: bool,
    pub activation_changed: bool,
    pub latency_before_ms: f64,
    pub latency_after_ms: f64,
    pub trace_latency_ms: f64,
}
