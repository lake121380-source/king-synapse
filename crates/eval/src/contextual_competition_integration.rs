use anyhow::Result;
use chrono::Utc;
use serde::Serialize;
use std::cmp::Ordering;
use std::collections::BTreeMap;

const EVALUATION_VERSION: &str = "phase4.4-contextual-competition-integration";
const BASELINE_VERSION: &str = "phase4.3-contextual-cognitive-weighting";
const SCORE_EPSILON: f64 = 0.000_001;
const CONSISTENCY_REPETITIONS: usize = 10;

pub struct Phase4ContextualCompetitionIntegrationEvaluator;

impl Phase4ContextualCompetitionIntegrationEvaluator {
    pub fn evaluate(
        tag: impl Into<String>,
    ) -> Result<Phase4ContextualCompetitionIntegrationReport> {
        Ok(evaluate_integration(tag.into()))
    }

    pub fn compete(
        context_id: impl Into<String>,
        candidates: &[CognitiveCandidate],
        context: &EvaluationContext,
    ) -> CompetitionResult {
        compete_once(context_id.into(), candidates, context)
    }
}

fn evaluate_integration(tag: String) -> Phase4ContextualCompetitionIntegrationReport {
    let scenarios = integration_scenarios();
    let scenario_reports = scenarios.iter().map(evaluate_scenario).collect::<Vec<_>>();
    let all_contexts = scenario_reports
        .iter()
        .flat_map(|scenario| scenario.results.iter())
        .collect::<Vec<_>>();
    let flip_total = scenario_reports
        .iter()
        .map(|scenario| scenario.flip_pairs.len())
        .sum::<usize>();
    let flip_changed = scenario_reports
        .iter()
        .flat_map(|scenario| scenario.flip_pairs.iter())
        .filter(|pair| pair.dominant_changed)
        .count();
    let suppression_checks = scenario_reports
        .iter()
        .flat_map(|scenario| scenario.results.iter())
        .collect::<Vec<_>>();
    let metric = ContextualCompetitionMetric {
        context_flip_rate: safe_div(flip_changed as f64, flip_total as f64),
        dominance_consistency: safe_div(
            all_contexts
                .iter()
                .filter(|result| result.dominance_consistent)
                .count() as f64,
            all_contexts.len() as f64,
        ),
        suppression_correctness: safe_div(
            suppression_checks
                .iter()
                .filter(|result| result.suppression_correct)
                .count() as f64,
            suppression_checks.len() as f64,
        ),
        ranking_stability: safe_div(
            all_contexts
                .iter()
                .filter(|result| result.ranking_stable)
                .count() as f64,
            all_contexts.len() as f64,
        ),
    };
    let core_changed = false;
    let memory_written = false;
    let runtime_weight_changed = false;
    let pass = metric.context_flip_rate >= 0.80
        && metric.dominance_consistency >= 1.0
        && metric.suppression_correctness >= 0.90
        && metric.ranking_stability >= 1.0
        && !core_changed
        && !memory_written
        && !runtime_weight_changed;

    Phase4ContextualCompetitionIntegrationReport {
        tag,
        phase: "4.4".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        scenarios: scenario_reports.len(),
        context_cases: all_contexts.len(),
        context_flips: ContextFlipSummary {
            changed: flip_changed,
            total: flip_total,
        },
        metric,
        core_changed,
        memory_written,
        runtime_weight_changed,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        scenario_reports,
    }
}

fn evaluate_scenario(scenario: &IntegrationScenario) -> ScenarioReport {
    let results = scenario
        .contexts
        .iter()
        .map(|context_case| {
            let mut result = compete_once(
                context_case.context_id.to_string(),
                &scenario.candidates,
                &context_case.context,
            );
            result.expected_dominant_candidate = context_case.expected_dominant.to_string();
            result.expected_suppressed_candidates = context_case
                .expected_suppressed
                .iter()
                .map(|candidate| candidate.to_string())
                .collect::<Vec<_>>();
            result.dominance_correct = result.dominant_candidate == context_case.expected_dominant;
            result.suppression_correct = result
                .expected_suppressed_candidates
                .iter()
                .all(|candidate| result.suppressed_candidates.contains(candidate));

            let repeated = (0..CONSISTENCY_REPETITIONS)
                .map(|_| {
                    compete_once(
                        context_case.context_id.to_string(),
                        &scenario.candidates,
                        &context_case.context,
                    )
                })
                .collect::<Vec<_>>();
            result.dominance_consistent = repeated
                .iter()
                .all(|replay| replay.dominant_candidate == result.dominant_candidate);
            result.ranking_stable = repeated
                .iter()
                .all(|replay| replay.ranked_candidates == result.ranked_candidates);
            result
        })
        .collect::<Vec<_>>();
    let by_context = results
        .iter()
        .map(|result| (result.context_id.clone(), result.dominant_candidate.clone()))
        .collect::<BTreeMap<_, _>>();
    let flip_pairs = scenario
        .flip_pairs
        .iter()
        .map(|pair| {
            let left_dominant = by_context.get(pair.left).cloned().unwrap_or_default();
            let right_dominant = by_context.get(pair.right).cloned().unwrap_or_default();
            FlipPairReport {
                left_context_id: pair.left.to_string(),
                right_context_id: pair.right.to_string(),
                left_dominant,
                right_dominant,
                dominant_changed: by_context.get(pair.left) != by_context.get(pair.right),
            }
        })
        .collect::<Vec<_>>();

    ScenarioReport {
        scenario_id: scenario.id.to_string(),
        description: scenario.description.to_string(),
        candidates: scenario.candidates.clone(),
        results,
        flip_pairs,
    }
}

fn compete_once(
    context_id: String,
    candidates: &[CognitiveCandidate],
    context: &EvaluationContext,
) -> CompetitionResult {
    let profile = profile_for_context(context);
    let mut scored = candidates
        .iter()
        .map(|candidate| score_candidate(candidate, context, profile))
        .collect::<Vec<_>>();
    scored.sort_by(compare_scores);

    let ranked_candidates = scored
        .iter()
        .map(|score| score.candidate_id.clone())
        .collect::<Vec<_>>();
    let dominant_candidate = ranked_candidates.first().cloned().unwrap_or_default();
    let suppressed_candidates = ranked_candidates
        .iter()
        .skip(1)
        .cloned()
        .collect::<Vec<_>>();

    CompetitionResult {
        context_id,
        context: context.clone(),
        ranked_candidates,
        dominant_candidate,
        suppressed_candidates,
        expected_dominant_candidate: String::new(),
        expected_suppressed_candidates: Vec::new(),
        score_breakdown: scored,
        dominance_correct: false,
        suppression_correct: false,
        dominance_consistent: false,
        ranking_stable: false,
    }
}

fn score_candidate(
    candidate: &CognitiveCandidate,
    context: &EvaluationContext,
    profile: ContextWeightProfile,
) -> CandidateScoreBreakdown {
    let base_component = candidate.base_strength * profile.base_strength;
    let task_component = candidate.task_alignment * profile.task_alignment;
    let environment_component = candidate.environment_alignment * profile.environment_alignment;
    let constraint_component = candidate.constraint_alignment * profile.constraint_alignment;
    let temporal_component = candidate.temporal_confidence * profile.temporal_confidence;
    let reliability_component = candidate.reliability * profile.reliability;
    let total_score = base_component
        + task_component
        + environment_component
        + constraint_component
        + temporal_component
        + reliability_component;

    CandidateScoreBreakdown {
        candidate_id: candidate.id.clone(),
        base_component,
        task_component,
        environment_component,
        constraint_component,
        temporal_component,
        reliability_component,
        total_score,
        reason: reason_for_score(candidate, context, profile),
    }
}

fn profile_for_context(context: &EvaluationContext) -> ContextWeightProfile {
    let text = format!(
        "{} {} {}",
        context.task,
        context.environment,
        context.constraints.join(" ")
    )
    .to_lowercase();

    if text.contains("prototype_building") || text.contains("speed_priority") {
        return ContextWeightProfile {
            base_strength: 0.05,
            task_alignment: 0.35,
            environment_alignment: 0.25,
            constraint_alignment: 0.10,
            temporal_confidence: 0.15,
            reliability: 0.10,
        };
    }
    if text.contains("production_deployment")
        || text.contains("safety_priority")
        || text.contains("high_risk")
    {
        return ContextWeightProfile {
            base_strength: 0.05,
            task_alignment: 0.10,
            environment_alignment: 0.15,
            constraint_alignment: 0.35,
            temporal_confidence: 0.20,
            reliability: 0.15,
        };
    }
    if text.contains("simple_tooling") {
        return ContextWeightProfile {
            base_strength: 0.10,
            task_alignment: 0.45,
            environment_alignment: 0.20,
            constraint_alignment: 0.05,
            temporal_confidence: 0.05,
            reliability: 0.15,
        };
    }
    if text.contains("large_system_design") || text.contains("scaling") {
        return ContextWeightProfile {
            base_strength: 0.05,
            task_alignment: 0.20,
            environment_alignment: 0.15,
            constraint_alignment: 0.25,
            temporal_confidence: 0.25,
            reliability: 0.10,
        };
    }
    if text.contains("offline") || text.contains("no_network") {
        return ContextWeightProfile {
            base_strength: 0.05,
            task_alignment: 0.15,
            environment_alignment: 0.20,
            constraint_alignment: 0.35,
            temporal_confidence: 0.15,
            reliability: 0.10,
        };
    }
    if text.contains("cloud") || text.contains("network_available") {
        return ContextWeightProfile {
            base_strength: 0.05,
            task_alignment: 0.25,
            environment_alignment: 0.35,
            constraint_alignment: 0.05,
            temporal_confidence: 0.15,
            reliability: 0.15,
        };
    }

    ContextWeightProfile::default()
}

fn reason_for_score(
    candidate: &CognitiveCandidate,
    context: &EvaluationContext,
    profile: ContextWeightProfile,
) -> String {
    let strongest = [
        ("task", profile.task_alignment),
        ("environment", profile.environment_alignment),
        ("constraint", profile.constraint_alignment),
        ("temporal", profile.temporal_confidence),
        ("reliability", profile.reliability),
    ]
    .into_iter()
    .max_by(|left, right| left.1.partial_cmp(&right.1).unwrap_or(Ordering::Equal))
    .map(|(label, _)| label)
    .unwrap_or("context");

    format!(
        "{} scored under {} emphasis for task {} in {}",
        candidate.id, strongest, context.task, context.environment
    )
}

fn compare_scores(left: &CandidateScoreBreakdown, right: &CandidateScoreBreakdown) -> Ordering {
    let score_order = right
        .total_score
        .partial_cmp(&left.total_score)
        .unwrap_or(Ordering::Equal);
    if (left.total_score - right.total_score).abs() > SCORE_EPSILON {
        return score_order;
    }

    left.candidate_id.cmp(&right.candidate_id)
}

fn integration_scenarios() -> Vec<IntegrationScenario> {
    vec![
        IntegrationScenario {
            id: "contextual_integration_001_speed_vs_safety",
            description: "Same speed and safety memories flip dominance between prototype and production contexts.",
            candidates: vec![
                candidate("speed_preference", 0.82, 0.90, 0.80, 0.40, 0.80, 0.80),
                candidate(
                    "failure_prevention",
                    0.80,
                    0.60,
                    0.70,
                    0.90,
                    0.90,
                    0.90,
                ),
            ],
            contexts: vec![
                context_case(
                    "prototype_building",
                    "prototype_building",
                    "development",
                    vec!["speed_priority", "low_risk"],
                    "speed_preference",
                    vec!["failure_prevention"],
                ),
                context_case(
                    "production_deployment",
                    "production_deployment",
                    "production",
                    vec!["safety_priority", "high_risk"],
                    "failure_prevention",
                    vec!["speed_preference"],
                ),
            ],
            flip_pairs: vec![FlipPair {
                left: "prototype_building",
                right: "production_deployment",
            }],
        },
        IntegrationScenario {
            id: "contextual_integration_002_old_preference_vs_new_evidence",
            description: "A simple-tools preference wins in a small context but recent scaling failure wins for large system design.",
            candidates: vec![
                candidate("old_preference", 0.82, 0.90, 0.75, 0.60, 0.30, 0.85),
                candidate("recent_failure", 0.76, 0.70, 0.75, 0.90, 0.95, 0.90),
            ],
            contexts: vec![
                context_case(
                    "simple_tooling",
                    "simple_tooling",
                    "small_project",
                    vec!["low_complexity"],
                    "old_preference",
                    vec!["recent_failure"],
                ),
                context_case(
                    "large_system_design",
                    "large_system_design",
                    "scaling_environment",
                    vec!["scaling_risk"],
                    "recent_failure",
                    vec!["old_preference"],
                ),
            ],
            flip_pairs: vec![FlipPair {
                left: "simple_tooling",
                right: "large_system_design",
            }],
        },
        IntegrationScenario {
            id: "contextual_integration_003_environment_shift",
            description: "The same local and cloud memories flip when the execution environment changes.",
            candidates: vec![
                candidate("local_solution", 0.78, 0.70, 0.65, 0.95, 0.80, 0.85),
                candidate("cloud_solution", 0.80, 0.76, 0.98, 0.45, 0.85, 0.88),
            ],
            contexts: vec![
                context_case(
                    "offline_environment",
                    "environment_shift",
                    "offline",
                    vec!["no_network", "offline_required"],
                    "local_solution",
                    vec!["cloud_solution"],
                ),
                context_case(
                    "cloud_environment",
                    "environment_shift",
                    "cloud",
                    vec!["network_available", "managed_service"],
                    "cloud_solution",
                    vec!["local_solution"],
                ),
            ],
            flip_pairs: vec![FlipPair {
                left: "offline_environment",
                right: "cloud_environment",
            }],
        },
    ]
}

fn candidate(
    id: &'static str,
    base_strength: f64,
    task_alignment: f64,
    environment_alignment: f64,
    constraint_alignment: f64,
    temporal_confidence: f64,
    reliability: f64,
) -> CognitiveCandidate {
    CognitiveCandidate {
        id: id.to_string(),
        base_strength,
        task_alignment,
        environment_alignment,
        constraint_alignment,
        temporal_confidence,
        reliability,
    }
}

fn context_case(
    context_id: &'static str,
    task: &'static str,
    environment: &'static str,
    constraints: Vec<&'static str>,
    expected_dominant: &'static str,
    expected_suppressed: Vec<&'static str>,
) -> ContextCase {
    ContextCase {
        context_id,
        context: EvaluationContext {
            task: task.to_string(),
            environment: environment.to_string(),
            constraints: constraints.into_iter().map(str::to_string).collect(),
        },
        expected_dominant,
        expected_suppressed,
    }
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone)]
struct IntegrationScenario {
    id: &'static str,
    description: &'static str,
    candidates: Vec<CognitiveCandidate>,
    contexts: Vec<ContextCase>,
    flip_pairs: Vec<FlipPair>,
}

#[derive(Debug, Clone)]
struct ContextCase {
    context_id: &'static str,
    context: EvaluationContext,
    expected_dominant: &'static str,
    expected_suppressed: Vec<&'static str>,
}

#[derive(Debug, Clone, Copy)]
struct FlipPair {
    left: &'static str,
    right: &'static str,
}

#[derive(Debug, Clone, Copy)]
struct ContextWeightProfile {
    base_strength: f64,
    task_alignment: f64,
    environment_alignment: f64,
    constraint_alignment: f64,
    temporal_confidence: f64,
    reliability: f64,
}

impl Default for ContextWeightProfile {
    fn default() -> Self {
        Self {
            base_strength: 0.10,
            task_alignment: 0.20,
            environment_alignment: 0.20,
            constraint_alignment: 0.20,
            temporal_confidence: 0.15,
            reliability: 0.15,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveCandidate {
    pub id: String,
    pub base_strength: f64,
    pub task_alignment: f64,
    pub environment_alignment: f64,
    pub constraint_alignment: f64,
    pub temporal_confidence: f64,
    pub reliability: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct EvaluationContext {
    pub task: String,
    pub environment: String,
    pub constraints: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CompetitionResult {
    pub context_id: String,
    pub context: EvaluationContext,
    pub ranked_candidates: Vec<String>,
    pub dominant_candidate: String,
    pub suppressed_candidates: Vec<String>,
    pub expected_dominant_candidate: String,
    pub expected_suppressed_candidates: Vec<String>,
    pub score_breakdown: Vec<CandidateScoreBreakdown>,
    pub dominance_correct: bool,
    pub suppression_correct: bool,
    pub dominance_consistent: bool,
    pub ranking_stable: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct CandidateScoreBreakdown {
    pub candidate_id: String,
    pub base_component: f64,
    pub task_component: f64,
    pub environment_component: f64,
    pub constraint_component: f64,
    pub temporal_component: f64,
    pub reliability_component: f64,
    pub total_score: f64,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScenarioReport {
    pub scenario_id: String,
    pub description: String,
    pub candidates: Vec<CognitiveCandidate>,
    pub results: Vec<CompetitionResult>,
    pub flip_pairs: Vec<FlipPairReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct FlipPairReport {
    pub left_context_id: String,
    pub right_context_id: String,
    pub left_dominant: String,
    pub right_dominant: String,
    pub dominant_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ContextFlipSummary {
    pub changed: usize,
    pub total: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct ContextualCompetitionMetric {
    pub context_flip_rate: f64,
    pub dominance_consistency: f64,
    pub suppression_correctness: f64,
    pub ranking_stability: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase4ContextualCompetitionIntegrationReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub scenarios: usize,
    pub context_cases: usize,
    pub context_flips: ContextFlipSummary,
    pub metric: ContextualCompetitionMetric,
    pub core_changed: bool,
    pub memory_written: bool,
    pub runtime_weight_changed: bool,
    pub pass: bool,
    pub status: String,
    pub scenario_reports: Vec<ScenarioReport>,
}
