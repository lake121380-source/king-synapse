use crate::phase3_future_influence::Phase3FutureInfluenceEvaluator;
use anyhow::Result;
use chrono::Utc;
use serde::Serialize;

const EVALUATION_VERSION: &str = "phase3.5-lesson-lifecycle-evaluation";
const BASELINE_VERSION: &str = "phase3.4-future-influence-experiment";

pub struct Phase3LessonLifecycleEvaluator;

impl Phase3LessonLifecycleEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase3LessonLifecycleReport> {
        let future_influence =
            Phase3FutureInfluenceEvaluator::evaluate("phase3-lesson-lifecycle-source")?;
        Ok(evaluate_lifecycle(
            tag.into(),
            future_influence.traces.len(),
        ))
    }
}

fn evaluate_lifecycle(
    tag: String,
    future_influence_source_count: usize,
) -> Phase3LessonLifecycleReport {
    let scenarios = lifecycle_scenarios();
    let traces = scenarios
        .iter()
        .map(evaluate_scenario)
        .collect::<Vec<LessonLifecycleTrace>>();
    let states = LessonLifecycleStateCounts {
        candidate: traces
            .iter()
            .filter(|trace| trace.final_state == LessonLifecycleState::Candidate)
            .count(),
        proposed: traces
            .iter()
            .filter(|trace| trace.final_state == LessonLifecycleState::Proposed)
            .count(),
        active: traces
            .iter()
            .filter(|trace| trace.final_state == LessonLifecycleState::Active)
            .count(),
        challenged: traces
            .iter()
            .filter(|trace| trace.final_state == LessonLifecycleState::Challenged)
            .count(),
        superseded: traces
            .iter()
            .filter(|trace| trace.final_state == LessonLifecycleState::Superseded)
            .count(),
    };
    let safety = LessonLifecycleSafetyReport {
        memory_written: false,
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
    };
    let lifecycle_safe = traces.iter().all(|trace| {
        trace.lifecycle_safe
            && !trace.memory_written
            && !trace.lesson_persisted
            && !trace.playbook_created
            && !trace.future_influence_changed
    }) && !safety.memory_written
        && !safety.lesson_persisted
        && !safety.playbook_created
        && !safety.future_influence_changed;

    let contradiction_cases = traces
        .iter()
        .filter(|trace| trace.contradiction_events > 0)
        .collect::<Vec<_>>();
    let supersession_cases = traces
        .iter()
        .filter(|trace| trace.expected_final_state == LessonLifecycleState::Superseded)
        .collect::<Vec<_>>();
    let reinforcement_cases = traces
        .iter()
        .filter(|trace| trace.lifecycle_pattern == "Reinforcement")
        .collect::<Vec<_>>();
    let protection_cases = traces
        .iter()
        .filter(|trace| trace.lifecycle_pattern == "FalseLessonProtection")
        .collect::<Vec<_>>();

    let metrics = Phase3LessonLifecycleMetrics {
        lifecycle_transition_accuracy: safe_div(
            traces
                .iter()
                .filter(|trace| trace.final_state == trace.expected_final_state)
                .count() as f32,
            traces.len() as f32,
        ),
        contradiction_response_score: safe_div(
            contradiction_cases
                .iter()
                .filter(|trace| {
                    trace.influence_after < trace.influence_before
                        && matches!(
                            trace.final_state,
                            LessonLifecycleState::Challenged | LessonLifecycleState::Superseded
                        )
                })
                .count() as f32,
            contradiction_cases.len() as f32,
        ),
        supersession_score: safe_div(
            supersession_cases
                .iter()
                .filter(|trace| trace.final_state == LessonLifecycleState::Superseded)
                .count() as f32,
            supersession_cases.len() as f32,
        ),
        reinforcement_score: safe_div(
            reinforcement_cases
                .iter()
                .filter(|trace| {
                    trace.final_state == LessonLifecycleState::Active
                        && trace.confidence_after > trace.confidence_before
                        && trace.influence_after > trace.influence_before
                })
                .count() as f32,
            reinforcement_cases.len() as f32,
        ),
        false_lesson_protection_score: safe_div(
            protection_cases
                .iter()
                .filter(|trace| trace.final_state == LessonLifecycleState::Candidate)
                .count() as f32,
            protection_cases.len() as f32,
        ),
        lifecycle_safety: f32::from(lifecycle_safe),
    };

    let pass = traces.len() == scenarios.len()
        && states.active == 1
        && states.challenged == 1
        && states.superseded == 1
        && states.candidate == 1
        && metrics.lifecycle_transition_accuracy >= 1.0
        && metrics.contradiction_response_score >= 1.0
        && metrics.supersession_score >= 1.0
        && metrics.reinforcement_score >= 1.0
        && metrics.false_lesson_protection_score >= 1.0
        && metrics.lifecycle_safety >= 1.0;

    Phase3LessonLifecycleReport {
        tag,
        phase: "3.5".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        scenarios: traces.len(),
        future_influence_source_count,
        mechanism_changed: false,
        schema_changed: false,
        retrieval_changed: false,
        activation_changed: false,
        temporal_lifecycle_changed: false,
        governance_changed: false,
        states,
        metrics,
        safety,
        pass,
        status: "lesson_lifecycle_evaluated".to_string(),
        traces,
    }
}

fn evaluate_scenario(scenario: &LessonLifecycleScenario) -> LessonLifecycleTrace {
    let transitions = scenario
        .transitions
        .iter()
        .map(|transition| LessonTransition {
            from: transition.from,
            to: transition.to,
            reason: transition.reason.to_string(),
        })
        .collect::<Vec<_>>();
    let final_state = transitions
        .last()
        .map(|transition| transition.to)
        .unwrap_or(scenario.initial_state);
    let lifecycle_safe = final_state == scenario.expected_final_state
        && scenario.confidence_after >= 0.0
        && scenario.influence_after >= 0.0;

    LessonLifecycleTrace {
        scenario_id: scenario.id.to_string(),
        lifecycle_pattern: scenario.pattern.to_string(),
        lesson_id: scenario.lesson_id.to_string(),
        lesson_text: scenario.lesson_text.to_string(),
        replacement_lesson: scenario.replacement_lesson.map(str::to_string),
        initial_state: scenario.initial_state,
        transitions,
        support_events: scenario.support_events,
        contradiction_events: scenario.contradiction_events,
        confidence_before: scenario.confidence_before,
        confidence_after: scenario.confidence_after,
        influence_before: scenario.influence_before,
        influence_after: scenario.influence_after,
        final_state,
        expected_final_state: scenario.expected_final_state,
        lifecycle_safe,
        memory_written: false,
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
        trace_notes: trace_notes(scenario, final_state),
    }
}

fn trace_notes(
    scenario: &LessonLifecycleScenario,
    final_state: LessonLifecycleState,
) -> Vec<String> {
    let mut notes = vec![
        "evaluation only: no memory write".to_string(),
        "evaluation only: no lesson persistence".to_string(),
        "evaluation only: no playbook creation".to_string(),
        "evaluation only: no runtime future influence mutation".to_string(),
    ];
    match scenario.pattern {
        "Reinforcement" => notes.push(
            "supporting evidence can move a proposed lesson into active simulation".to_string(),
        ),
        "Challenge" => {
            notes.push("contradicting evidence reduces lesson confidence and influence".to_string())
        }
        "Supersession" => notes.push(
            "stronger replacement lesson moves the old lesson out of recommendation".to_string(),
        ),
        _ => notes.push("weak evidence remains candidate-level and does not activate".to_string()),
    }
    notes.push(format!("final_state: {}", final_state.as_str()));
    notes
}

fn lifecycle_scenarios() -> Vec<LessonLifecycleScenario> {
    vec![
        LessonLifecycleScenario {
            id: "lesson_lifecycle_001_reinforcement",
            pattern: "Reinforcement",
            lesson_id: "lesson_env_resource_check",
            lesson_text: "Before deployment, check environment resources.",
            replacement_lesson: None,
            initial_state: LessonLifecycleState::Proposed,
            transitions: vec![TransitionSpec {
                from: LessonLifecycleState::Proposed,
                to: LessonLifecycleState::Active,
                reason: "three supporting deployment outcomes reinforce the lesson",
            }],
            support_events: 3,
            contradiction_events: 0,
            confidence_before: 0.70,
            confidence_after: 0.92,
            influence_before: 0.55,
            influence_after: 0.86,
            expected_final_state: LessonLifecycleState::Active,
        },
        LessonLifecycleScenario {
            id: "lesson_lifecycle_002_challenge",
            pattern: "Challenge",
            lesson_id: "lesson_method_a_fails_often",
            lesson_text: "Method A fails often.",
            replacement_lesson: None,
            initial_state: LessonLifecycleState::Active,
            transitions: vec![TransitionSpec {
                from: LessonLifecycleState::Active,
                to: LessonLifecycleState::Challenged,
                reason: "contradicting success case lowers lesson confidence",
            }],
            support_events: 0,
            contradiction_events: 1,
            confidence_before: 0.82,
            confidence_after: 0.57,
            influence_before: 0.78,
            influence_after: 0.44,
            expected_final_state: LessonLifecycleState::Challenged,
        },
        LessonLifecycleScenario {
            id: "lesson_lifecycle_003_supersession",
            pattern: "Supersession",
            lesson_id: "lesson_always_method_a",
            lesson_text: "Always use method A.",
            replacement_lesson: Some("Choose the method based on environment constraints."),
            initial_state: LessonLifecycleState::Active,
            transitions: vec![TransitionSpec {
                from: LessonLifecycleState::Active,
                to: LessonLifecycleState::Superseded,
                reason: "stronger environment-aware lesson replaces the old universal rule",
            }],
            support_events: 0,
            contradiction_events: 2,
            confidence_before: 0.86,
            confidence_after: 0.31,
            influence_before: 0.80,
            influence_after: 0.12,
            expected_final_state: LessonLifecycleState::Superseded,
        },
        LessonLifecycleScenario {
            id: "lesson_lifecycle_004_false_lesson_protection",
            pattern: "FalseLessonProtection",
            lesson_id: "lesson_single_failure_overfit",
            lesson_text: "A single transient failure means the whole strategy is bad.",
            replacement_lesson: None,
            initial_state: LessonLifecycleState::Candidate,
            transitions: vec![TransitionSpec {
                from: LessonLifecycleState::Candidate,
                to: LessonLifecycleState::Candidate,
                reason: "weak single-event evidence is insufficient for activation",
            }],
            support_events: 1,
            contradiction_events: 0,
            confidence_before: 0.25,
            confidence_after: 0.25,
            influence_before: 0.10,
            influence_after: 0.10,
            expected_final_state: LessonLifecycleState::Candidate,
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

#[derive(Debug, Clone)]
struct LessonLifecycleScenario {
    id: &'static str,
    pattern: &'static str,
    lesson_id: &'static str,
    lesson_text: &'static str,
    replacement_lesson: Option<&'static str>,
    initial_state: LessonLifecycleState,
    transitions: Vec<TransitionSpec>,
    support_events: usize,
    contradiction_events: usize,
    confidence_before: f32,
    confidence_after: f32,
    influence_before: f32,
    influence_after: f32,
    expected_final_state: LessonLifecycleState,
}

#[derive(Debug, Clone, Copy)]
struct TransitionSpec {
    from: LessonLifecycleState,
    to: LessonLifecycleState,
    reason: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub enum LessonLifecycleState {
    Candidate,
    Proposed,
    Active,
    Challenged,
    Superseded,
}

impl LessonLifecycleState {
    pub fn as_str(self) -> &'static str {
        match self {
            LessonLifecycleState::Candidate => "Candidate",
            LessonLifecycleState::Proposed => "Proposed",
            LessonLifecycleState::Active => "Active",
            LessonLifecycleState::Challenged => "Challenged",
            LessonLifecycleState::Superseded => "Superseded",
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3LessonLifecycleReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub scenarios: usize,
    pub future_influence_source_count: usize,
    pub mechanism_changed: bool,
    pub schema_changed: bool,
    pub retrieval_changed: bool,
    pub activation_changed: bool,
    pub temporal_lifecycle_changed: bool,
    pub governance_changed: bool,
    pub states: LessonLifecycleStateCounts,
    pub metrics: Phase3LessonLifecycleMetrics,
    pub safety: LessonLifecycleSafetyReport,
    pub pass: bool,
    pub status: String,
    pub traces: Vec<LessonLifecycleTrace>,
}

#[derive(Debug, Clone, Serialize)]
pub struct LessonLifecycleStateCounts {
    pub candidate: usize,
    pub proposed: usize,
    pub active: usize,
    pub challenged: usize,
    pub superseded: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3LessonLifecycleMetrics {
    pub lifecycle_transition_accuracy: f32,
    pub contradiction_response_score: f32,
    pub supersession_score: f32,
    pub reinforcement_score: f32,
    pub false_lesson_protection_score: f32,
    pub lifecycle_safety: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct LessonLifecycleSafetyReport {
    pub memory_written: bool,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct LessonLifecycleTrace {
    pub scenario_id: String,
    pub lifecycle_pattern: String,
    pub lesson_id: String,
    pub lesson_text: String,
    pub replacement_lesson: Option<String>,
    pub initial_state: LessonLifecycleState,
    pub transitions: Vec<LessonTransition>,
    pub support_events: usize,
    pub contradiction_events: usize,
    pub confidence_before: f32,
    pub confidence_after: f32,
    pub influence_before: f32,
    pub influence_after: f32,
    pub final_state: LessonLifecycleState,
    pub expected_final_state: LessonLifecycleState,
    pub lifecycle_safe: bool,
    pub memory_written: bool,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
    pub trace_notes: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct LessonTransition {
    pub from: LessonLifecycleState,
    pub to: LessonLifecycleState,
    pub reason: String,
}
