use crate::phase4_cognitive_influence::CandidateType;
use anyhow::Result;
use chrono::Utc;
use serde::Serialize;
use std::cmp::Ordering;

const EVALUATION_VERSION: &str = "phase4.2-cognitive-competition-model";
const BASELINE_VERSION: &str = "phase4.1-cognitive-influence-evaluation";
const SCORE_EPSILON: f32 = 0.0001;

pub struct Phase4CognitiveCompetitionEvaluator;

impl Phase4CognitiveCompetitionEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase4CognitiveCompetitionReport> {
        Self::evaluate_with_parameters(tag, CompetitionParameters::default())
    }

    pub fn evaluate_with_parameters(
        tag: impl Into<String>,
        parameters: CompetitionParameters,
    ) -> Result<Phase4CognitiveCompetitionReport> {
        Ok(evaluate_competition(tag.into(), parameters))
    }
}

fn evaluate_competition(
    tag: String,
    parameters: CompetitionParameters,
) -> Phase4CognitiveCompetitionReport {
    let scenarios = competition_scenarios();
    let traces = scenarios
        .iter()
        .map(|scenario| evaluate_scenario(scenario, parameters))
        .collect::<Vec<CompetitionTrace>>();
    let safety = CognitiveCompetitionSafetyReport {
        core_changed: false,
        memory_written: false,
        runtime_activation_changed: false,
    };

    let metrics = Phase4CognitiveCompetitionMetrics {
        dominant_selection_accuracy: safe_div(
            traces.iter().filter(|trace| trace.dominant_correct).count() as f32,
            traces.len() as f32,
        ),
        competition_convergence: safe_div(
            traces.iter().filter(|trace| trace.convergence).count() as f32,
            traces.len() as f32,
        ),
        suppression_quality: safe_div(
            traces
                .iter()
                .filter(|trace| trace.suppression_correct)
                .count() as f32,
            traces.len() as f32,
        ),
        activation_stability: safe_div(
            traces
                .iter()
                .filter(|trace| trace.stable_under_noise)
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
        && metrics.dominant_selection_accuracy >= 1.0
        && metrics.competition_convergence >= 1.0
        && metrics.suppression_quality >= 1.0
        && metrics.activation_stability >= 1.0
        && metrics.explanation_quality >= 1.0
        && !safety.core_changed
        && !safety.memory_written
        && !safety.runtime_activation_changed
        && traces.iter().all(|trace| trace.competition_safe);

    Phase4CognitiveCompetitionReport {
        tag,
        phase: "4.2".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        scenarios: traces.len(),
        parameters,
        metrics,
        safety,
        pass,
        status: "cognitive_competition_evaluated".to_string(),
        traces,
    }
}

fn evaluate_scenario(
    scenario: &CompetitionScenario,
    parameters: CompetitionParameters,
) -> CompetitionTrace {
    let mut candidates = scenario.candidates.clone();
    let mut rounds = Vec::new();

    for round_number in 1..=parameters.rounds {
        let round = run_round(round_number, &mut candidates, scenario, parameters);
        rounds.push(round);
    }

    let ranked = rank_candidates(&candidates);
    let dominant = ranked
        .first()
        .expect("competition scenarios always include candidates");
    let suppressed_reports = ranked
        .iter()
        .skip(1)
        .map(|candidate| SuppressedCompetitionCandidate {
            candidate_id: candidate.id.clone(),
            candidate_type: candidate.candidate_type,
            final_activation: candidate.activation,
            inhibited: candidate.inhibited,
            reason: suppression_reason(candidate, dominant),
        })
        .collect::<Vec<_>>();
    let suppressed_candidates = suppressed_reports
        .iter()
        .map(|candidate| candidate.candidate_id.clone())
        .collect::<Vec<_>>();
    let confidence_gap = ranked
        .get(1)
        .map(|second| dominant.activation - second.activation)
        .unwrap_or(dominant.activation);
    let dominant_correct = dominant.id == scenario.expected_dominant_id;
    let expected_suppressed = scenario
        .expected_suppressed
        .iter()
        .map(|id| id.to_string())
        .collect::<Vec<_>>();
    let suppression_correct = expected_suppressed
        .iter()
        .all(|expected| suppressed_candidates.contains(expected));
    let convergence = rounds
        .iter()
        .rev()
        .take(2)
        .all(|round| round.winner_id == dominant.id);
    let stable_under_noise = evaluate_noise_stability(scenario, parameters, &dominant.id);
    let activation_path = scenario
        .path_links
        .iter()
        .map(|path| ActivationPathReport {
            from_candidate: path.from.to_string(),
            to_candidate: path.to.to_string(),
            boost: path.boost,
            reason: path.reason.to_string(),
        })
        .collect::<Vec<_>>();
    let explanation = explanation_for_trace(
        scenario,
        dominant,
        &suppressed_reports,
        confidence_gap,
        &activation_path,
    );
    let explanation_complete = !dominant.id.is_empty()
        && confidence_gap >= 0.0
        && !suppressed_reports.is_empty()
        && !explanation.is_empty()
        && explanation.iter().any(|line| line.contains("dominant"))
        && explanation.iter().any(|line| line.contains("suppressed"))
        && explanation
            .iter()
            .any(|line| line.contains("activation_path"));

    CompetitionTrace {
        scenario_id: scenario.id.to_string(),
        context: scenario.context.to_string(),
        expected_dominant_candidate: scenario.expected_dominant_id.to_string(),
        dominant_candidate: dominant.id.clone(),
        dominant_candidate_type: dominant.candidate_type,
        suppressed_candidates,
        suppressed_candidate_reports: suppressed_reports,
        rounds,
        convergence,
        confidence_gap,
        activation_path,
        explanation,
        dominant_correct,
        suppression_correct,
        stable_under_noise,
        explanation_complete,
        competition_safe: true,
        core_changed: false,
        memory_written: false,
        runtime_activation_changed: false,
    }
}

fn run_round(
    round_number: usize,
    candidates: &mut [CompetitionCandidate],
    scenario: &CompetitionScenario,
    parameters: CompetitionParameters,
) -> CompetitionRound {
    let before = candidates
        .iter()
        .map(|candidate| (candidate.id.clone(), candidate.activation))
        .collect::<Vec<_>>();
    let mut updated = Vec::new();

    for candidate in candidates.iter() {
        let path_boost = incoming_path_boost(candidate, &before, scenario);
        let activation = (candidate.activation * parameters.decay
            + candidate.influence_score * parameters.influence_weight
            + candidate.context_alignment * parameters.context_weight
            + candidate.reliability * parameters.reliability_weight
            + path_boost)
            .clamp(0.0, 1.0);
        updated.push((candidate.id.clone(), activation, path_boost));
    }

    let winner_id = updated
        .iter()
        .max_by(|left, right| compare_activation_tuple(left, right, candidates))
        .map(|(id, _, _)| id.clone())
        .expect("round has candidates");
    let winner_activation = updated
        .iter()
        .find(|(id, _, _)| id == &winner_id)
        .map(|(_, activation, _)| *activation)
        .unwrap_or_default();
    let mut states = Vec::new();

    for candidate in candidates.iter_mut() {
        let activation_before = before
            .iter()
            .find(|(id, _)| id == &candidate.id)
            .map(|(_, activation)| *activation)
            .unwrap_or(candidate.activation);
        let (activation_after_update, path_boost) = updated
            .iter()
            .find(|(id, _, _)| id == &candidate.id)
            .map(|(_, activation, path_boost)| (*activation, *path_boost))
            .unwrap_or((candidate.activation, 0.0));
        let inhibition = if candidate.id == winner_id {
            0.0
        } else {
            ((winner_activation - activation_after_update).max(0.0)
                * parameters.inhibition_strength)
                .clamp(0.0, 1.0)
        };
        let activation_after_inhibition = (activation_after_update - inhibition).clamp(0.0, 1.0);

        candidate.activation = activation_after_inhibition;
        candidate.inhibited = (candidate.inhibited + inhibition).clamp(0.0, 1.0);

        states.push(CompetitionCandidateState {
            candidate_id: candidate.id.clone(),
            candidate_type: candidate.candidate_type,
            activation_before,
            activation_after_update,
            path_boost,
            inhibition,
            activation_after_inhibition,
        });
    }

    states.sort_by(|left, right| {
        right
            .activation_after_inhibition
            .partial_cmp(&left.activation_after_inhibition)
            .unwrap_or(Ordering::Equal)
            .then_with(|| {
                candidate_priority(right.candidate_type)
                    .cmp(&candidate_priority(left.candidate_type))
            })
            .then_with(|| left.candidate_id.cmp(&right.candidate_id))
    });

    CompetitionRound {
        round: round_number,
        winner_id,
        states,
    }
}

fn incoming_path_boost(
    candidate: &CompetitionCandidate,
    before: &[(String, f32)],
    scenario: &CompetitionScenario,
) -> f32 {
    scenario
        .path_links
        .iter()
        .filter(|link| link.to == candidate.id)
        .map(|link| {
            before
                .iter()
                .find(|(id, _)| id == link.from)
                .map(|(_, activation)| activation * link.boost)
                .unwrap_or(0.0)
        })
        .sum::<f32>()
        .clamp(0.0, 1.0)
}

fn compare_activation_tuple(
    left: &(String, f32, f32),
    right: &(String, f32, f32),
    candidates: &[CompetitionCandidate],
) -> Ordering {
    let score_order = left.1.partial_cmp(&right.1).unwrap_or(Ordering::Equal);
    if (left.1 - right.1).abs() > SCORE_EPSILON {
        return score_order;
    }

    let left_type = candidates
        .iter()
        .find(|candidate| candidate.id == left.0)
        .map(|candidate| candidate.candidate_type)
        .unwrap_or(CandidateType::Memory);
    let right_type = candidates
        .iter()
        .find(|candidate| candidate.id == right.0)
        .map(|candidate| candidate.candidate_type)
        .unwrap_or(CandidateType::Memory);

    candidate_priority(left_type)
        .cmp(&candidate_priority(right_type))
        .then_with(|| right.0.cmp(&left.0))
}

fn rank_candidates(candidates: &[CompetitionCandidate]) -> Vec<CompetitionCandidate> {
    let mut ranked = candidates.to_vec();
    ranked.sort_by(|left, right| {
        right
            .activation
            .partial_cmp(&left.activation)
            .unwrap_or(Ordering::Equal)
            .then_with(|| {
                candidate_priority(right.candidate_type)
                    .cmp(&candidate_priority(left.candidate_type))
            })
            .then_with(|| left.id.cmp(&right.id))
    });
    ranked
}

fn evaluate_noise_stability(
    scenario: &CompetitionScenario,
    parameters: CompetitionParameters,
    dominant_id: &str,
) -> bool {
    let Some(noise) = scenario.noise_delta else {
        return true;
    };
    let mut noisy = scenario.clone();
    for candidate in &mut noisy.candidates {
        if candidate.id == dominant_id {
            candidate.initial_activation = (candidate.initial_activation - noise).clamp(0.0, 1.0);
            candidate.activation = candidate.initial_activation;
            candidate.influence_score = (candidate.influence_score - noise).clamp(0.0, 1.0);
        } else {
            candidate.initial_activation = (candidate.initial_activation + noise).clamp(0.0, 1.0);
            candidate.activation = candidate.initial_activation;
            candidate.influence_score = (candidate.influence_score + noise).clamp(0.0, 1.0);
        }
    }
    let trace = evaluate_scenario_without_noise(&noisy, parameters);
    trace == dominant_id
}

fn evaluate_scenario_without_noise(
    scenario: &CompetitionScenario,
    parameters: CompetitionParameters,
) -> String {
    let mut candidates = scenario.candidates.clone();
    for round_number in 1..=parameters.rounds {
        let _ = run_round(round_number, &mut candidates, scenario, parameters);
    }
    rank_candidates(&candidates)
        .first()
        .map(|candidate| candidate.id.clone())
        .unwrap_or_default()
}

fn suppression_reason(candidate: &CompetitionCandidate, dominant: &CompetitionCandidate) -> String {
    if candidate.activation < dominant.activation {
        "lower final activation after lateral inhibition".to_string()
    } else if candidate.context_alignment < dominant.context_alignment {
        "lower context alignment during competition".to_string()
    } else {
        "lower deterministic priority after competition".to_string()
    }
}

fn explanation_for_trace(
    scenario: &CompetitionScenario,
    dominant: &CompetitionCandidate,
    suppressed: &[SuppressedCompetitionCandidate],
    confidence_gap: f32,
    activation_path: &[ActivationPathReport],
) -> Vec<String> {
    vec![
        format!(
            "dominant candidate {} selected with final activation {:.4}",
            dominant.id, dominant.activation
        ),
        format!(
            "suppressed candidates: {}",
            suppressed
                .iter()
                .map(|candidate| candidate.candidate_id.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        ),
        format!("confidence gap: {:.4}", confidence_gap),
        format!(
            "activation_path: {}",
            if activation_path.is_empty() {
                "none".to_string()
            } else {
                activation_path
                    .iter()
                    .map(|path| format!("{} -> {}", path.from_candidate, path.to_candidate))
                    .collect::<Vec<_>>()
                    .join(", ")
            }
        ),
        format!("scenario reason: {}", scenario.reason),
    ]
}

fn candidate_priority(candidate_type: CandidateType) -> u8 {
    match candidate_type {
        CandidateType::Memory => 1,
        CandidateType::Lesson => 2,
        CandidateType::PlaybookCandidate => 3,
    }
}

fn competition_scenarios() -> Vec<CompetitionScenario> {
    vec![
        CompetitionScenario {
            id: "competition_001_clear_winner",
            context: "A candidate has a large initial activation advantage and matching influence.",
            reason: "clear activation advantage should become dominant",
            expected_dominant_id: "memory_clear_a",
            expected_suppressed: vec!["lesson_clear_b", "playbook_clear_c"],
            noise_delta: Some(0.01),
            path_links: vec![],
            candidates: vec![
                candidate("memory_clear_a", CandidateType::Memory, 0.90, 0.85, 0.82, 0.90),
                candidate("lesson_clear_b", CandidateType::Lesson, 0.40, 0.55, 0.48, 0.65),
                candidate(
                    "playbook_clear_c",
                    CandidateType::PlaybookCandidate,
                    0.30,
                    0.45,
                    0.42,
                    0.60,
                ),
            ],
        },
        CompetitionScenario {
            id: "competition_002_context_override",
            context: "Current context strongly matches the medium-history lesson, not the older memory.",
            reason: "context alignment should override older low-context history",
            expected_dominant_id: "lesson_context_high",
            expected_suppressed: vec!["memory_history_high_context_low"],
            noise_delta: Some(0.01),
            path_links: vec![],
            candidates: vec![
                candidate(
                    "memory_history_high_context_low",
                    CandidateType::Memory,
                    0.70,
                    0.95,
                    0.20,
                    0.80,
                ),
                candidate(
                    "lesson_context_high",
                    CandidateType::Lesson,
                    0.55,
                    0.65,
                    0.95,
                    0.85,
                ),
            ],
        },
        CompetitionScenario {
            id: "competition_003_near_tie",
            context: "Two candidates are close enough that deterministic confidence gap reporting matters.",
            reason: "near tie should stay deterministic and report a confidence gap",
            expected_dominant_id: "memory_near_tie_a",
            expected_suppressed: vec!["lesson_near_tie_b"],
            noise_delta: None,
            path_links: vec![],
            candidates: vec![
                candidate(
                    "memory_near_tie_a",
                    CandidateType::Memory,
                    0.80,
                    0.75,
                    0.77,
                    0.80,
                ),
                candidate(
                    "lesson_near_tie_b",
                    CandidateType::Lesson,
                    0.78,
                    0.76,
                    0.76,
                    0.80,
                ),
            ],
        },
        CompetitionScenario {
            id: "competition_004_inhibition",
            context: "The strongest memory should laterally inhibit two weaker alternatives.",
            reason: "winner suppression should leave all candidates present but inhibited",
            expected_dominant_id: "memory_inhibition_a",
            expected_suppressed: vec!["lesson_inhibition_b", "playbook_inhibition_c"],
            noise_delta: Some(0.01),
            path_links: vec![],
            candidates: vec![
                candidate("memory_inhibition_a", CandidateType::Memory, 0.88, 0.85, 0.85, 0.90),
                candidate("lesson_inhibition_b", CandidateType::Lesson, 0.50, 0.55, 0.45, 0.60),
                candidate(
                    "playbook_inhibition_c",
                    CandidateType::PlaybookCandidate,
                    0.45,
                    0.50,
                    0.40,
                    0.55,
                ),
            ],
        },
        CompetitionScenario {
            id: "competition_005_multi_hop",
            context: "Memory supports a lesson, and the lesson supports an operational playbook.",
            reason: "activation path should lift the playbook into dominance",
            expected_dominant_id: "playbook_multihop_c",
            expected_suppressed: vec!["memory_multihop_a", "lesson_multihop_b"],
            noise_delta: Some(0.01),
            path_links: vec![
                PathLink {
                    from: "memory_multihop_a",
                    to: "lesson_multihop_b",
                    boost: 0.08,
                    reason: "memory evidence reinforces lesson",
                },
                PathLink {
                    from: "lesson_multihop_b",
                    to: "playbook_multihop_c",
                    boost: 0.10,
                    reason: "lesson proceduralizes into playbook",
                },
            ],
            candidates: vec![
                candidate("memory_multihop_a", CandidateType::Memory, 0.55, 0.70, 0.70, 0.80),
                candidate("lesson_multihop_b", CandidateType::Lesson, 0.50, 0.75, 0.78, 0.82),
                candidate(
                    "playbook_multihop_c",
                    CandidateType::PlaybookCandidate,
                    0.45,
                    0.78,
                    0.85,
                    0.88,
                ),
            ],
        },
        CompetitionScenario {
            id: "competition_006_stability_under_noise",
            context: "A small perturbation should not cause the dominant candidate to switch.",
            reason: "dominant thought should remain stable under small score noise",
            expected_dominant_id: "lesson_stable_a",
            expected_suppressed: vec!["memory_stable_b", "playbook_stable_c"],
            noise_delta: Some(0.01),
            path_links: vec![],
            candidates: vec![
                candidate("lesson_stable_a", CandidateType::Lesson, 0.82, 0.80, 0.82, 0.85),
                candidate("memory_stable_b", CandidateType::Memory, 0.70, 0.72, 0.70, 0.76),
                candidate(
                    "playbook_stable_c",
                    CandidateType::PlaybookCandidate,
                    0.60,
                    0.60,
                    0.65,
                    0.70,
                ),
            ],
        },
    ]
}

fn candidate(
    id: &'static str,
    candidate_type: CandidateType,
    initial_activation: f32,
    influence_score: f32,
    context_alignment: f32,
    reliability: f32,
) -> CompetitionCandidate {
    CompetitionCandidate {
        id: id.to_string(),
        candidate_type,
        initial_activation,
        influence_score,
        context_alignment,
        reliability,
        activation: initial_activation,
        inhibited: 0.0,
    }
}

fn safe_div(numerator: f32, denominator: f32) -> f32 {
    if denominator.abs() < f32::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Copy, Serialize)]
pub struct CompetitionParameters {
    pub rounds: usize,
    pub decay: f32,
    pub influence_weight: f32,
    pub context_weight: f32,
    pub reliability_weight: f32,
    pub inhibition_strength: f32,
}

impl Default for CompetitionParameters {
    fn default() -> Self {
        Self {
            rounds: 3,
            decay: 0.55,
            influence_weight: 0.25,
            context_weight: 0.25,
            reliability_weight: 0.10,
            inhibition_strength: 0.35,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct CompetitionCandidate {
    pub id: String,
    pub candidate_type: CandidateType,
    pub initial_activation: f32,
    pub influence_score: f32,
    pub context_alignment: f32,
    pub reliability: f32,
    pub activation: f32,
    pub inhibited: f32,
}

#[derive(Debug, Clone)]
struct CompetitionScenario {
    id: &'static str,
    context: &'static str,
    reason: &'static str,
    expected_dominant_id: &'static str,
    expected_suppressed: Vec<&'static str>,
    noise_delta: Option<f32>,
    path_links: Vec<PathLink>,
    candidates: Vec<CompetitionCandidate>,
}

#[derive(Debug, Clone, Copy)]
struct PathLink {
    from: &'static str,
    to: &'static str,
    boost: f32,
    reason: &'static str,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase4CognitiveCompetitionReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub scenarios: usize,
    pub parameters: CompetitionParameters,
    pub metrics: Phase4CognitiveCompetitionMetrics,
    pub safety: CognitiveCompetitionSafetyReport,
    pub pass: bool,
    pub status: String,
    pub traces: Vec<CompetitionTrace>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase4CognitiveCompetitionMetrics {
    pub dominant_selection_accuracy: f32,
    pub competition_convergence: f32,
    pub suppression_quality: f32,
    pub activation_stability: f32,
    pub explanation_quality: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveCompetitionSafetyReport {
    pub core_changed: bool,
    pub memory_written: bool,
    pub runtime_activation_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct CompetitionTrace {
    pub scenario_id: String,
    pub context: String,
    pub expected_dominant_candidate: String,
    pub dominant_candidate: String,
    pub dominant_candidate_type: CandidateType,
    pub suppressed_candidates: Vec<String>,
    pub suppressed_candidate_reports: Vec<SuppressedCompetitionCandidate>,
    pub rounds: Vec<CompetitionRound>,
    pub convergence: bool,
    pub confidence_gap: f32,
    pub activation_path: Vec<ActivationPathReport>,
    pub explanation: Vec<String>,
    pub dominant_correct: bool,
    pub suppression_correct: bool,
    pub stable_under_noise: bool,
    pub explanation_complete: bool,
    pub competition_safe: bool,
    pub core_changed: bool,
    pub memory_written: bool,
    pub runtime_activation_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct CompetitionRound {
    pub round: usize,
    pub winner_id: String,
    pub states: Vec<CompetitionCandidateState>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CompetitionCandidateState {
    pub candidate_id: String,
    pub candidate_type: CandidateType,
    pub activation_before: f32,
    pub activation_after_update: f32,
    pub path_boost: f32,
    pub inhibition: f32,
    pub activation_after_inhibition: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct SuppressedCompetitionCandidate {
    pub candidate_id: String,
    pub candidate_type: CandidateType,
    pub final_activation: f32,
    pub inhibited: f32,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ActivationPathReport {
    pub from_candidate: String,
    pub to_candidate: String,
    pub boost: f32,
    pub reason: String,
}
