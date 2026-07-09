use anyhow::Result;
use chrono::Utc;
use serde::Serialize;
use std::cmp::Ordering;

const EVALUATION_VERSION: &str = "phase4.5-cognitive-competition-stability";
const BASELINE_VERSION: &str = "phase4.4-contextual-competition-integration";
const DETERMINISTIC_RUNS: usize = 100;
const SCORE_EPSILON: f64 = 0.000_001;

pub struct Phase4CognitiveCompetitionStabilityEvaluator;

impl Phase4CognitiveCompetitionStabilityEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase4CognitiveCompetitionStabilityReport> {
        Ok(evaluate_stability(tag.into()))
    }

    pub fn rank_candidates(
        candidates: &[StabilityCandidate],
        context: &StabilityContext,
    ) -> Vec<String> {
        rank_candidates(candidates, context)
            .into_iter()
            .map(|score| score.candidate_id)
            .collect()
    }
}

fn evaluate_stability(tag: String) -> Phase4CognitiveCompetitionStabilityReport {
    let deterministic = evaluate_deterministic_stability();
    let noise = evaluate_noise_resistance();
    let transition = evaluate_evidence_transition();
    let results = vec![
        deterministic.result.clone(),
        noise.result.clone(),
        transition.result.clone(),
    ];
    let metrics = CognitiveCompetitionStabilityMetrics {
        dominance_stability: deterministic.result.stability_score,
        noise_resistance: noise.result.stability_score,
        transition_consistency: transition.transition_consistency,
        oscillation_rate: safe_div(
            results
                .iter()
                .map(|result| result.oscillation_events)
                .sum::<usize>() as f64,
            results
                .iter()
                .map(|result| result.dominant_sequence.len().saturating_sub(1))
                .sum::<usize>() as f64,
        ),
    };
    let experiments = StabilityExperimentStatus {
        deterministic: status(metrics.dominance_stability >= 1.0),
        noise_resistance: status(metrics.noise_resistance >= 0.90),
        evidence_transition: status(
            metrics.transition_consistency >= 1.0 && metrics.oscillation_rate <= 0.0,
        ),
    };
    let core_changed = false;
    let memory_written = false;
    let runtime_weight_changed = false;
    let pass = experiments.deterministic == "PASS"
        && experiments.noise_resistance == "PASS"
        && experiments.evidence_transition == "PASS"
        && !core_changed
        && !memory_written
        && !runtime_weight_changed;

    Phase4CognitiveCompetitionStabilityReport {
        tag,
        phase: "4.5".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        metrics,
        experiments,
        core_changed,
        memory_written,
        runtime_weight_changed,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        deterministic,
        noise,
        transition,
        results,
    }
}

fn evaluate_deterministic_stability() -> DeterministicStabilityReport {
    let candidates = deterministic_candidates();
    let context = StabilityContext {
        task: "production_task".to_string(),
        environment: "safety_constraint".to_string(),
        constraint_strength: 0.90,
    };
    let dominant_sequence = (0..DETERMINISTIC_RUNS)
        .map(|_| dominant_candidate(&candidates, &context))
        .collect::<Vec<_>>();
    let expected = "candidate_a".to_string();
    let same_dominant_count = dominant_sequence
        .iter()
        .filter(|dominant| *dominant == &expected)
        .count();
    let ranking = rank_candidates(&candidates, &context);
    let ranking_order = ranking
        .iter()
        .map(|score| score.candidate_id.clone())
        .collect::<Vec<_>>();
    let oscillation_events = oscillation_events(&dominant_sequence);

    DeterministicStabilityReport {
        runs: DETERMINISTIC_RUNS,
        expected_dominant: expected,
        same_dominant_count,
        ranking_order,
        result: StabilityResult {
            experiment: "deterministic".to_string(),
            dominant_sequence,
            stability_score: safe_div(same_dominant_count as f64, DETERMINISTIC_RUNS as f64),
            oscillation_rate: 0.0,
            oscillation_events,
        },
    }
}

fn evaluate_noise_resistance() -> NoiseResistanceReport {
    let candidates = noise_candidates();
    let contexts = vec![
        NoiseCase {
            case_id: "baseline_safety".to_string(),
            context: StabilityContext {
                task: "production deployment safety priority".to_string(),
                environment: "production".to_string(),
                constraint_strength: 0.95,
            },
            expected_dominant: "failure_prevention".to_string(),
        },
        NoiseCase {
            case_id: "speed_request_noise".to_string(),
            context: StabilityContext {
                task: "production deployment safety priority faster delivery requested".to_string(),
                environment: "production".to_string(),
                constraint_strength: 0.92,
            },
            expected_dominant: "failure_prevention".to_string(),
        },
        NoiseCase {
            case_id: "short_deadline_noise".to_string(),
            context: StabilityContext {
                task: "production deployment safety priority short deadline".to_string(),
                environment: "production".to_string(),
                constraint_strength: 0.90,
            },
            expected_dominant: "failure_prevention".to_string(),
        },
        NoiseCase {
            case_id: "minor_cost_noise".to_string(),
            context: StabilityContext {
                task: "production deployment safety priority minor cost concern".to_string(),
                environment: "production".to_string(),
                constraint_strength: 0.88,
            },
            expected_dominant: "failure_prevention".to_string(),
        },
    ];
    let case_reports = contexts
        .iter()
        .map(|case| {
            let ranking = rank_candidates(&candidates, &case.context);
            NoiseCaseReport {
                case_id: case.case_id.clone(),
                context: case.context.clone(),
                expected_dominant: case.expected_dominant.clone(),
                dominant_candidate: ranking
                    .first()
                    .map(|score| score.candidate_id.clone())
                    .unwrap_or_default(),
                ranking,
            }
        })
        .collect::<Vec<_>>();
    let stable_cases = case_reports
        .iter()
        .filter(|case| case.dominant_candidate == case.expected_dominant)
        .count();
    let dominant_sequence = case_reports
        .iter()
        .map(|case| case.dominant_candidate.clone())
        .collect::<Vec<_>>();
    let oscillation_events = oscillation_events(&dominant_sequence);

    NoiseResistanceReport {
        cases: case_reports.len(),
        unchanged_cases: stable_cases,
        case_reports,
        result: StabilityResult {
            experiment: "noise_resistance".to_string(),
            dominant_sequence,
            stability_score: safe_div(stable_cases as f64, contexts.len() as f64),
            oscillation_rate: safe_div(oscillation_events as f64, contexts.len() as f64),
            oscillation_events,
        },
    }
}

fn evaluate_evidence_transition() -> EvidenceTransitionReport {
    let context = StabilityContext {
        task: "preference update with contradictory evidence".to_string(),
        environment: "long_horizon".to_string(),
        constraint_strength: 0.80,
    };
    let evidence_levels = vec![0.0, 0.2, 0.4, 0.6, 0.8, 1.0];
    let steps = evidence_levels
        .iter()
        .copied()
        .map(|evidence| {
            let candidates = transition_candidates(evidence);
            let ranking = rank_candidates(&candidates, &context);
            EvidenceStepReport {
                evidence_support: evidence,
                dominant_candidate: ranking
                    .first()
                    .map(|score| score.candidate_id.clone())
                    .unwrap_or_default(),
                ranking,
            }
        })
        .collect::<Vec<_>>();
    let dominant_sequence = steps
        .iter()
        .map(|step| step.dominant_candidate.clone())
        .collect::<Vec<_>>();
    let transition_count = transition_count(&dominant_sequence);
    let oscillation_events = oscillation_events(&dominant_sequence);
    let transition_consistency = if transition_count == 1
        && oscillation_events == 0
        && is_monotonic_transition(&dominant_sequence)
    {
        1.0
    } else {
        0.0
    };

    EvidenceTransitionReport {
        evidence_levels,
        transition_count,
        transition_consistency,
        steps,
        result: StabilityResult {
            experiment: "evidence_transition".to_string(),
            dominant_sequence,
            stability_score: transition_consistency,
            oscillation_rate: safe_div(oscillation_events as f64, 5.0),
            oscillation_events,
        },
    }
}

fn rank_candidates(
    candidates: &[StabilityCandidate],
    context: &StabilityContext,
) -> Vec<StabilityScoreBreakdown> {
    let mut scores = candidates
        .iter()
        .map(|candidate| score_candidate(candidate, context))
        .collect::<Vec<_>>();
    scores.sort_by(compare_scores);
    scores
}

fn dominant_candidate(candidates: &[StabilityCandidate], context: &StabilityContext) -> String {
    rank_candidates(candidates, context)
        .first()
        .map(|score| score.candidate_id.clone())
        .unwrap_or_default()
}

fn score_candidate(
    candidate: &StabilityCandidate,
    context: &StabilityContext,
) -> StabilityScoreBreakdown {
    let base_component = candidate.base_strength * 0.35;
    let reliability_component = candidate.reliability * (0.20 + context.constraint_strength * 0.05);
    let temporal_component = candidate.temporal_confidence * 0.15;
    let evidence_component = candidate.evidence_support * 0.20;
    let total_score =
        base_component + reliability_component + temporal_component + evidence_component;

    StabilityScoreBreakdown {
        candidate_id: candidate.id.clone(),
        base_component,
        reliability_component,
        temporal_component,
        evidence_component,
        total_score,
    }
}

fn compare_scores(left: &StabilityScoreBreakdown, right: &StabilityScoreBreakdown) -> Ordering {
    let score_order = right
        .total_score
        .partial_cmp(&left.total_score)
        .unwrap_or(Ordering::Equal);
    if (left.total_score - right.total_score).abs() > SCORE_EPSILON {
        return score_order;
    }

    left.candidate_id.cmp(&right.candidate_id)
}

fn deterministic_candidates() -> Vec<StabilityCandidate> {
    vec![
        stability_candidate("candidate_a", 0.92, 0.95, 0.90, 0.82),
        stability_candidate("candidate_b", 0.74, 0.78, 0.74, 0.68),
        stability_candidate("candidate_c", 0.38, 0.45, 0.40, 0.22),
    ]
}

fn noise_candidates() -> Vec<StabilityCandidate> {
    vec![
        stability_candidate("speed_preference", 0.78, 0.70, 0.72, 0.64),
        stability_candidate("failure_prevention", 0.76, 0.92, 0.90, 0.84),
    ]
}

fn transition_candidates(new_evidence_support: f64) -> Vec<StabilityCandidate> {
    vec![
        stability_candidate("existing_preference", 0.84, 0.85, 0.80, 0.30),
        stability_candidate(
            "new_contradictory_evidence",
            0.55,
            0.88,
            0.95,
            new_evidence_support,
        ),
    ]
}

fn stability_candidate(
    id: &'static str,
    base_strength: f64,
    reliability: f64,
    temporal_confidence: f64,
    evidence_support: f64,
) -> StabilityCandidate {
    StabilityCandidate {
        id: id.to_string(),
        base_strength,
        reliability,
        temporal_confidence,
        evidence_support,
    }
}

fn transition_count(sequence: &[String]) -> usize {
    sequence
        .windows(2)
        .filter(|window| window[0] != window[1])
        .count()
}

fn oscillation_events(sequence: &[String]) -> usize {
    sequence
        .windows(3)
        .filter(|window| window[0] == window[2] && window[0] != window[1])
        .count()
}

fn is_monotonic_transition(sequence: &[String]) -> bool {
    let Some(first) = sequence.first() else {
        return true;
    };
    let mut seen_transition = false;
    let mut post_transition: Option<&String> = None;

    for dominant in sequence.iter().skip(1) {
        if !seen_transition && dominant != first {
            seen_transition = true;
            post_transition = Some(dominant);
            continue;
        }
        if seen_transition {
            if Some(dominant) != post_transition {
                return false;
            }
        }
    }

    true
}

fn status(pass: bool) -> String {
    if pass {
        "PASS".to_string()
    } else {
        "FAIL".to_string()
    }
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct StabilityCandidate {
    pub id: String,
    pub base_strength: f64,
    pub reliability: f64,
    pub temporal_confidence: f64,
    pub evidence_support: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct StabilityContext {
    pub task: String,
    pub environment: String,
    pub constraint_strength: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct StabilityResult {
    pub experiment: String,
    pub dominant_sequence: Vec<String>,
    pub stability_score: f64,
    pub oscillation_rate: f64,
    pub oscillation_events: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct StabilityScoreBreakdown {
    pub candidate_id: String,
    pub base_component: f64,
    pub reliability_component: f64,
    pub temporal_component: f64,
    pub evidence_component: f64,
    pub total_score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct DeterministicStabilityReport {
    pub runs: usize,
    pub expected_dominant: String,
    pub same_dominant_count: usize,
    pub ranking_order: Vec<String>,
    pub result: StabilityResult,
}

#[derive(Debug, Clone, Serialize)]
pub struct NoiseCaseReport {
    pub case_id: String,
    pub context: StabilityContext,
    pub expected_dominant: String,
    pub dominant_candidate: String,
    pub ranking: Vec<StabilityScoreBreakdown>,
}

#[derive(Debug, Clone)]
struct NoiseCase {
    case_id: String,
    context: StabilityContext,
    expected_dominant: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct NoiseResistanceReport {
    pub cases: usize,
    pub unchanged_cases: usize,
    pub case_reports: Vec<NoiseCaseReport>,
    pub result: StabilityResult,
}

#[derive(Debug, Clone, Serialize)]
pub struct EvidenceStepReport {
    pub evidence_support: f64,
    pub dominant_candidate: String,
    pub ranking: Vec<StabilityScoreBreakdown>,
}

#[derive(Debug, Clone, Serialize)]
pub struct EvidenceTransitionReport {
    pub evidence_levels: Vec<f64>,
    pub transition_count: usize,
    pub transition_consistency: f64,
    pub steps: Vec<EvidenceStepReport>,
    pub result: StabilityResult,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveCompetitionStabilityMetrics {
    pub dominance_stability: f64,
    pub noise_resistance: f64,
    pub transition_consistency: f64,
    pub oscillation_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct StabilityExperimentStatus {
    pub deterministic: String,
    pub noise_resistance: String,
    pub evidence_transition: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase4CognitiveCompetitionStabilityReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub metrics: CognitiveCompetitionStabilityMetrics,
    pub experiments: StabilityExperimentStatus,
    pub core_changed: bool,
    pub memory_written: bool,
    pub runtime_weight_changed: bool,
    pub pass: bool,
    pub status: String,
    pub deterministic: DeterministicStabilityReport,
    pub noise: NoiseResistanceReport,
    pub transition: EvidenceTransitionReport,
    pub results: Vec<StabilityResult>,
}
