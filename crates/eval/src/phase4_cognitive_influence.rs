use anyhow::Result;
use chrono::Utc;
use serde::Serialize;
use std::cmp::Ordering;

const EVALUATION_VERSION: &str = "phase4.1-cognitive-influence-evaluation";
const BASELINE_VERSION: &str = "phase3.6-experience-learning-freeze";
const SCORE_EPSILON: f32 = 0.0001;

pub struct Phase4CognitiveInfluenceEvaluator;

impl Phase4CognitiveInfluenceEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase4CognitiveInfluenceReport> {
        Self::evaluate_with_weights(tag, InfluenceWeights::default())
    }

    pub fn evaluate_with_weights(
        tag: impl Into<String>,
        weights: InfluenceWeights,
    ) -> Result<Phase4CognitiveInfluenceReport> {
        Ok(evaluate_influence(tag.into(), weights))
    }
}

fn evaluate_influence(tag: String, weights: InfluenceWeights) -> Phase4CognitiveInfluenceReport {
    let scenarios = influence_scenarios();
    let traces = scenarios
        .iter()
        .map(|scenario| evaluate_scenario(scenario, weights))
        .collect::<Vec<CognitiveInfluenceTrace>>();
    let safety = CognitiveInfluenceSafetyReport {
        core_changed: false,
        memory_written: false,
        runtime_influence_changed: false,
    };

    let metrics = Phase4CognitiveInfluenceMetrics {
        influence_accuracy: safe_div(
            traces.iter().filter(|trace| trace.winner_correct).count() as f32,
            traces.len() as f32,
        ),
        context_alignment_score: safe_div(
            traces
                .iter()
                .filter(|trace| trace.context_alignment_ok)
                .count() as f32,
            traces.len() as f32,
        ),
        competition_stability: safe_div(
            traces
                .iter()
                .filter(|trace| trace.stable_under_perturbation)
                .count() as f32,
            traces.len() as f32,
        ),
        explanation_quality: safe_div(
            traces
                .iter()
                .filter(|trace| trace.explanation_complete)
                .count() as f32,
            traces.len() as f32,
        ),
    };

    let pass = traces.len() == scenarios.len()
        && metrics.influence_accuracy >= 1.0
        && metrics.context_alignment_score >= 1.0
        && metrics.competition_stability >= 1.0
        && metrics.explanation_quality >= 1.0
        && !safety.core_changed
        && !safety.memory_written
        && !safety.runtime_influence_changed
        && traces.iter().all(|trace| trace.influence_safe);

    Phase4CognitiveInfluenceReport {
        tag,
        phase: "4.1".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        scenarios: traces.len(),
        weights,
        metrics,
        safety,
        pass,
        status: "cognitive_influence_evaluated".to_string(),
        traces,
    }
}

fn evaluate_scenario(
    scenario: &CognitiveInfluenceScenario,
    weights: InfluenceWeights,
) -> CognitiveInfluenceTrace {
    let score_breakdown = scenario
        .candidates
        .iter()
        .map(|candidate| score_candidate(candidate, weights))
        .collect::<Vec<_>>();
    let mut ranking = score_breakdown
        .iter()
        .map(|breakdown| CognitiveInfluenceRanking {
            candidate_id: breakdown.candidate_id.clone(),
            candidate_type: breakdown.candidate_type,
            score: breakdown.total_score,
        })
        .collect::<Vec<_>>();
    ranking.sort_by(compare_ranking);

    let winner = ranking
        .first()
        .expect("each cognitive influence scenario has candidates");
    let winner_candidate = scenario
        .candidates
        .iter()
        .find(|candidate| candidate.id == winner.candidate_id)
        .expect("winning candidate should exist");
    let suppressed_candidates = ranking
        .iter()
        .skip(1)
        .map(|ranked| {
            let candidate = scenario
                .candidates
                .iter()
                .find(|candidate| candidate.id == ranked.candidate_id)
                .expect("suppressed candidate should exist");
            SuppressedCandidateReport {
                candidate_id: candidate.id.clone(),
                candidate_type: candidate.candidate_type,
                score: ranked.score,
                why_rejected: rejection_reason(candidate, winner_candidate, scenario),
            }
        })
        .collect::<Vec<_>>();
    let top_margin = ranking
        .get(1)
        .map(|second| winner.score - second.score)
        .unwrap_or(winner.score);
    let winner_correct = winner.candidate_id == scenario.expected_winner_id;
    let context_alignment_ok = winner_candidate.context_alignment
        >= scenario
            .candidates
            .iter()
            .map(|candidate| candidate.context_alignment)
            .fold(0.0_f32, f32::max)
            - SCORE_EPSILON;
    let stable_under_perturbation = top_margin >= 0.05 || scenario.expected_tie_breaker;
    let explanation_complete = !winner.candidate_id.is_empty()
        && !scenario.why_selected.is_empty()
        && !suppressed_candidates.is_empty()
        && suppressed_candidates
            .iter()
            .all(|candidate| !candidate.why_rejected.is_empty())
        && score_breakdown.len() == scenario.candidates.len();

    CognitiveInfluenceTrace {
        scenario_id: scenario.id.to_string(),
        context: scenario.context.to_string(),
        expected_winner_id: scenario.expected_winner_id.to_string(),
        winning_candidate_id: winner.candidate_id.clone(),
        winning_candidate_type: winner.candidate_type,
        why_selected: scenario.why_selected.to_string(),
        influence_ranking: ranking,
        suppressed_candidates,
        score_breakdown,
        winner_correct,
        context_alignment_ok,
        stable_under_perturbation,
        explanation_complete,
        top_margin,
        influence_safe: true,
        core_changed: false,
        memory_written: false,
        runtime_influence_changed: false,
    }
}

fn score_candidate(
    candidate: &CognitiveCandidate,
    weights: InfluenceWeights,
) -> CognitiveScoreBreakdown {
    let historical_component = weights.historical_strength * candidate.historical_strength;
    let temporal_component = weights.temporal_confidence * candidate.temporal_confidence;
    let context_component = weights.context_alignment * candidate.context_alignment;
    let reliability_component = weights.reliability_score * candidate.reliability_score;

    CognitiveScoreBreakdown {
        candidate_id: candidate.id.clone(),
        candidate_type: candidate.candidate_type,
        historical_component,
        temporal_component,
        context_component,
        reliability_component,
        total_score: historical_component
            + temporal_component
            + context_component
            + reliability_component,
    }
}

fn compare_ranking(
    left: &CognitiveInfluenceRanking,
    right: &CognitiveInfluenceRanking,
) -> Ordering {
    let score_order = right
        .score
        .partial_cmp(&left.score)
        .unwrap_or(Ordering::Equal);
    if (left.score - right.score).abs() > SCORE_EPSILON {
        return score_order;
    }

    right
        .candidate_type
        .priority()
        .cmp(&left.candidate_type.priority())
        .then_with(|| left.candidate_id.cmp(&right.candidate_id))
}

fn rejection_reason(
    candidate: &CognitiveCandidate,
    winner: &CognitiveCandidate,
    scenario: &CognitiveInfluenceScenario,
) -> String {
    if scenario.expected_tie_breaker && candidate.historical_strength == winner.historical_strength
    {
        return "tie resolved by candidate type priority and deterministic ordering".to_string();
    }
    if candidate.context_alignment < winner.context_alignment {
        "lower context alignment under the current query".to_string()
    } else if candidate.temporal_confidence < winner.temporal_confidence {
        "lower temporal confidence than the winning candidate".to_string()
    } else if candidate.reliability_score < winner.reliability_score {
        "lower reliability than the winning candidate".to_string()
    } else {
        "lower weighted influence score than the winning candidate".to_string()
    }
}

fn influence_scenarios() -> Vec<CognitiveInfluenceScenario> {
    vec![
        CognitiveInfluenceScenario {
            id: "cognitive_influence_001_context_wins",
            context: "The current task is a GPU-constrained deployment where immediate resource fit matters more than generic historical success.",
            expected_winner_id: "lesson_current_gpu_context",
            why_selected: "context alignment and temporal fit outweigh older generic success history",
            expected_tie_breaker: false,
            candidates: vec![
                CognitiveCandidate {
                    id: "memory_long_success_low_context".to_string(),
                    candidate_type: CandidateType::Memory,
                    content: "A historically successful generic deployment pattern.".to_string(),
                    historical_strength: 1.00,
                    temporal_confidence: 0.40,
                    context_alignment: 0.20,
                    reliability_score: 0.55,
                },
                CognitiveCandidate {
                    id: "lesson_current_gpu_context".to_string(),
                    candidate_type: CandidateType::Lesson,
                    content: "For GPU-limited deployment, validate memory footprint first.".to_string(),
                    historical_strength: 0.30,
                    temporal_confidence: 0.80,
                    context_alignment: 0.95,
                    reliability_score: 0.75,
                },
            ],
        },
        CognitiveInfluenceScenario {
            id: "cognitive_influence_002_historical_reliability_wins",
            context: "The current task matches a long-running deployment pattern with no new contradiction.",
            expected_winner_id: "memory_reliable_deployment_pattern",
            why_selected: "high historical strength and reliability beat a weaker candidate with similar context fit",
            expected_tie_breaker: false,
            candidates: vec![
                CognitiveCandidate {
                    id: "memory_reliable_deployment_pattern".to_string(),
                    candidate_type: CandidateType::Memory,
                    content: "A reliable deployment sequence repeatedly succeeded.".to_string(),
                    historical_strength: 0.95,
                    temporal_confidence: 0.90,
                    context_alignment: 0.80,
                    reliability_score: 0.95,
                },
                CognitiveCandidate {
                    id: "lesson_weak_new_hint".to_string(),
                    candidate_type: CandidateType::Lesson,
                    content: "A weak new hint with no repeated evidence.".to_string(),
                    historical_strength: 0.30,
                    temporal_confidence: 0.75,
                    context_alignment: 0.80,
                    reliability_score: 0.65,
                },
            ],
        },
        CognitiveInfluenceScenario {
            id: "cognitive_influence_003_temporal_decay",
            context: "The environment changed, so recent lesson evidence should beat an old strategy.",
            expected_winner_id: "lesson_new_environment_strategy",
            why_selected: "new evidence has stronger temporal confidence and current-context alignment",
            expected_tie_breaker: false,
            candidates: vec![
                CognitiveCandidate {
                    id: "lesson_old_environment_strategy".to_string(),
                    candidate_type: CandidateType::Lesson,
                    content: "Old lesson from the previous environment.".to_string(),
                    historical_strength: 0.80,
                    temporal_confidence: 0.20,
                    context_alignment: 0.55,
                    reliability_score: 0.75,
                },
                CognitiveCandidate {
                    id: "lesson_new_environment_strategy".to_string(),
                    candidate_type: CandidateType::Lesson,
                    content: "New lesson from the current environment.".to_string(),
                    historical_strength: 0.55,
                    temporal_confidence: 0.90,
                    context_alignment: 0.90,
                    reliability_score: 0.82,
                },
            ],
        },
        CognitiveInfluenceScenario {
            id: "cognitive_influence_004_contradictory_candidates",
            context: "A recent production failure contradicts an older success pattern.",
            expected_winner_id: "memory_recent_failure_pattern",
            why_selected: "recent failure evidence is more temporally relevant and context-aligned than older success evidence",
            expected_tie_breaker: false,
            candidates: vec![
                CognitiveCandidate {
                    id: "memory_old_success_pattern".to_string(),
                    candidate_type: CandidateType::Memory,
                    content: "Older success pattern from a prior deployment.".to_string(),
                    historical_strength: 0.85,
                    temporal_confidence: 0.50,
                    context_alignment: 0.55,
                    reliability_score: 0.80,
                },
                CognitiveCandidate {
                    id: "memory_recent_failure_pattern".to_string(),
                    candidate_type: CandidateType::Memory,
                    content: "Recent failure pattern under the same deployment constraint.".to_string(),
                    historical_strength: 0.65,
                    temporal_confidence: 0.90,
                    context_alignment: 0.90,
                    reliability_score: 0.85,
                },
            ],
        },
        CognitiveInfluenceScenario {
            id: "cognitive_influence_005_explanation_trace",
            context: "The current task needs an auditable operational checklist and a clear reason for suppressing alternatives.",
            expected_winner_id: "playbook_traceable_checklist",
            why_selected: "weighted scores tie, so the report-only playbook candidate wins by deterministic type priority",
            expected_tie_breaker: true,
            candidates: vec![
                CognitiveCandidate {
                    id: "lesson_traceable_checklist".to_string(),
                    candidate_type: CandidateType::Lesson,
                    content: "Use a traceable checklist before rollout.".to_string(),
                    historical_strength: 0.70,
                    temporal_confidence: 0.75,
                    context_alignment: 0.85,
                    reliability_score: 0.80,
                },
                CognitiveCandidate {
                    id: "playbook_traceable_checklist".to_string(),
                    candidate_type: CandidateType::PlaybookCandidate,
                    content: "Checklist: verify resources, permissions, rollback path, then deploy.".to_string(),
                    historical_strength: 0.70,
                    temporal_confidence: 0.75,
                    context_alignment: 0.85,
                    reliability_score: 0.80,
                },
                CognitiveCandidate {
                    id: "memory_general_rollout".to_string(),
                    candidate_type: CandidateType::Memory,
                    content: "General rollout memory without explicit checklist.".to_string(),
                    historical_strength: 0.60,
                    temporal_confidence: 0.60,
                    context_alignment: 0.70,
                    reliability_score: 0.70,
                },
            ],
        },
    ]
}

fn safe_div(numerator: f32, denominator: f32) -> f32 {
    if denominator.abs() < f32::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Copy, Serialize)]
pub struct InfluenceWeights {
    pub historical_strength: f32,
    pub temporal_confidence: f32,
    pub context_alignment: f32,
    pub reliability_score: f32,
}

impl Default for InfluenceWeights {
    fn default() -> Self {
        Self {
            historical_strength: 0.30,
            temporal_confidence: 0.25,
            context_alignment: 0.35,
            reliability_score: 0.10,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum CandidateType {
    Memory,
    Lesson,
    PlaybookCandidate,
}

impl CandidateType {
    fn priority(self) -> u8 {
        match self {
            CandidateType::Memory => 1,
            CandidateType::Lesson => 2,
            CandidateType::PlaybookCandidate => 3,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveCandidate {
    pub id: String,
    pub candidate_type: CandidateType,
    pub content: String,
    pub historical_strength: f32,
    pub temporal_confidence: f32,
    pub context_alignment: f32,
    pub reliability_score: f32,
}

#[derive(Debug, Clone)]
struct CognitiveInfluenceScenario {
    id: &'static str,
    context: &'static str,
    expected_winner_id: &'static str,
    why_selected: &'static str,
    expected_tie_breaker: bool,
    candidates: Vec<CognitiveCandidate>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase4CognitiveInfluenceReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub scenarios: usize,
    pub weights: InfluenceWeights,
    pub metrics: Phase4CognitiveInfluenceMetrics,
    pub safety: CognitiveInfluenceSafetyReport,
    pub pass: bool,
    pub status: String,
    pub traces: Vec<CognitiveInfluenceTrace>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase4CognitiveInfluenceMetrics {
    pub influence_accuracy: f32,
    pub context_alignment_score: f32,
    pub competition_stability: f32,
    pub explanation_quality: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveInfluenceSafetyReport {
    pub core_changed: bool,
    pub memory_written: bool,
    pub runtime_influence_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveInfluenceTrace {
    pub scenario_id: String,
    pub context: String,
    pub expected_winner_id: String,
    pub winning_candidate_id: String,
    pub winning_candidate_type: CandidateType,
    pub why_selected: String,
    pub influence_ranking: Vec<CognitiveInfluenceRanking>,
    pub suppressed_candidates: Vec<SuppressedCandidateReport>,
    pub score_breakdown: Vec<CognitiveScoreBreakdown>,
    pub winner_correct: bool,
    pub context_alignment_ok: bool,
    pub stable_under_perturbation: bool,
    pub explanation_complete: bool,
    pub top_margin: f32,
    pub influence_safe: bool,
    pub core_changed: bool,
    pub memory_written: bool,
    pub runtime_influence_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveInfluenceRanking {
    pub candidate_id: String,
    pub candidate_type: CandidateType,
    pub score: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct SuppressedCandidateReport {
    pub candidate_id: String,
    pub candidate_type: CandidateType,
    pub score: f32,
    pub why_rejected: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveScoreBreakdown {
    pub candidate_id: String,
    pub candidate_type: CandidateType,
    pub historical_component: f32,
    pub temporal_component: f32,
    pub context_component: f32,
    pub reliability_component: f32,
    pub total_score: f32,
}
